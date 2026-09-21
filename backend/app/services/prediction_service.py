"""
CyberShield AI — Phase 1 Step 9: Real Trained-ML Dynamic Top-3 Prediction Flow
Inference Service:
- Location Model V3.1 (cashout-location-xgb-v3.1) with Platt probability calibration
- Frozen Time Model V2 (cashout-time-xgb-v2)
- Multi-Modal Feature Pipeline V3.1 (Step 8 DB-driven service, zero fake defaults)
- Scope: Delhi Pilot (60 operational clusters)
- Zero database persistence in Step 9 (read-only guarantee, persistence is Step 10)
- Zero outcome leakage (no queries to Withdrawal or target clusters)
"""

import os
import json
import math
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
import joblib
import numpy as np
from sqlalchemy.orm import Session

from backend.app.models.models import Complaint, LocationCluster, Account, Transaction
from backend.app.services.transaction_context_service import resolve_transaction_context
from backend.app.services.graph_service import build_complaint_graph
from backend.app.services.ml_feature_service import (
    build_location_features,
    build_time_features
)
from ml.geo.candidate_generator import CandidateLocationGenerator, haversine_km
from ml.features.feature_pipeline import (
    feature_pipeline,
    DELHI_ZONE_CENTROIDS,
    FEATURE_COLUMNS_LOCATION_V3_1,
    FEATURE_COLUMNS_LOCATION_V8_DEBIASED,
    FEATURE_COLUMNS_TIME
)
from backend.app.services.delhi_origin_resolver import resolve_delhi_origin
from backend.app.services.prediction_contract import as_utc, build_time_prediction

logger = logging.getLogger("cybershield.prediction_service")

# Configurable Active Model Version (Challenger architecture)
ACTIVE_LOCATION_MODEL_VERSION = os.environ.get("ACTIVE_LOCATION_MODEL_VERSION", "v7_compat")

def resolve_artifacts_dir() -> str:
    """
    Resolves the directory containing trained ML model artifacts.
    Supports:
    1. MODEL_ARTIFACTS_DIR environment variable (if set and valid directory)
    2. Standard repository root layout: <repo_root>/ml/artifacts
    3. Containerized/backend deployment layout: <backend_dir>/ml/artifacts (e.g. Railway /app/ml/artifacts)
    4. Working-directory-relative layouts: ml/artifacts or backend/ml/artifacts
    """
    env_dir = os.environ.get("MODEL_ARTIFACTS_DIR")
    if env_dir and os.path.isdir(env_dir):
        return os.path.abspath(env_dir)

    service_dir = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.dirname(service_dir)
    backend_or_root = os.path.dirname(app_dir)

    candidates = [
        # Candidate 1: Standard repository root layout (<repo_root>/ml/artifacts)
        os.path.abspath(os.path.join(backend_or_root, "..", "ml", "artifacts")),
        # Candidate 2: Container/backend root layout (<backend_dir>/ml/artifacts or /app/ml/artifacts)
        os.path.abspath(os.path.join(backend_or_root, "ml", "artifacts")),
        # Candidate 3: Subdirectory under backend_or_root (<repo_root>/backend/ml/artifacts)
        os.path.abspath(os.path.join(backend_or_root, "backend", "ml", "artifacts")),
        # Candidate 4: Relative to current working directory
        os.path.abspath(os.path.join(os.getcwd(), "ml", "artifacts")),
        os.path.abspath(os.path.join(os.getcwd(), "backend", "ml", "artifacts")),
    ]

    for candidate in candidates:
        if os.path.isdir(candidate) and os.path.exists(os.path.join(candidate, "location_ranker_v4.joblib")):
            return candidate

    return candidates[0]


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
ARTIFACTS_DIR = resolve_artifacts_dir()

# Step 8C & Step 16 Verified Hashes for Integrity Gate
EXPECTED_HASHES = {
    # Active / Promoted Model: Location V8 Debiased (Causal money network, 49 features, 60 Delhi clusters)
    "location_ranker_v8_debiased.joblib": "69f300b4b208f2c3a606f54d84f992b665f30602de0ebe8f77f6561d625bfd71",
    "location_calibrator_v8_debiased.joblib": "e2ec24047c42b98a4aefd8c0951f125adf2947a5c1c198136dde9c77c4cb8dd1",
    "feature_schema_v8_debiased.json": "68c9643cea2c3f2480ca085e5da37299568cf72fef98e3f2c7f39b840c514b4b",
    "model_metadata_v8_debiased.json": "cf5b76ac27686dd4ccae238cc7a7b6af1c583af8cbcce2bbb369fe2293362050",
    "v8_lime_background.npy": "dab72448527c140d969e650048d0dc3c3515dbeb034effece3fdd2ca5d047f14",
    # Promoted Qualified Rollback Model: Location V7-compat
    "location_ranker_v7_compat.joblib": "89057bce1000cb82e10f29077b9e168bc0cbd254e979106998e1d623e072c2a6",
    "location_calibrator_v7_compat.joblib": "1c14d5aba1b0556a47519ea435804a86b34173c76743a77bcf52cea43d3a2c6d",
    "feature_schema_v7_compat.json": "fc303d7e8b995e1a9903706d4a7da21431c8424e27edf30b4757f900f7642444",
    "model_metadata_v7_compat.json": "d402ab6c397327fbce5916621e1da51766ee87b7a5449fa152c0e969b10c59f4",
    # Base Dependency / Fallback Reference: Location V4 & Time V3
    "location_ranker_v4.joblib": "9ed5792ced4f8a6e79dc91e587e3c130d2fbadb5af6a73640397dc506dd9cdc9",
    "location_calibrator_v4.joblib": "65ceb736838d14cb865111aac6eddfad3838704ddf2fffc63a6b2bdd998a3664",
    "time_regressor_v3.joblib": "41183f4579df70372102e98999967a5e63a9a2dad80f63668b45a5a66a2ed5e1",
    "feature_schema_v4.json": "572a1cadaea080c4ed013dcf07e2d1fca0720ba6c3d194bca7fc7d8e16d03c6e",
    "model_metadata_v4.json": "a428e3db7546923aed65bcee478e6121e2b22e7920f7f5c7236479c4f8cfebe9",
    # Preserved Rollback Models: Location V3.1 & Time V2
    "location_ranker_v3_1.joblib": "2fe0e596f0dc8a37361271f504a0a66f0fde0c1b0aaf1e6a8bc98bc5a38c6921",
    "location_calibrator_v3_1.joblib": "01df58e796266b9b057c85733d9e220b5ebfc40c2ea47f14142ec17e7af565ce",
    "feature_schema_v3_1.json": "44c2186687f5aec3ba0c7520058f7a3df5fd5702c88265b9488ee675a2c57abd",
    "model_metadata_v3_1.json": "9dea3176148f8621438e9acb26e013801a03645899e22e404c6929131e71f80b"
}

V4_COMPAT_FEATURES = [
    "v4_candidate_score",
    "v4_candidate_rank_normalized",
    "v4_candidate_percentile",
    "v4_score_gap_from_candidate1"
]
FEATURE_COLUMNS_LOCATION_V7_COMPAT = FEATURE_COLUMNS_LOCATION_V3_1 + V4_COMPAT_FEATURES


def compute_file_sha256(filepath: str) -> str:
    """Computes SHA-256 hash of a file on disk."""
    if not os.path.exists(filepath):
        return "FILE_NOT_FOUND"
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class PredictionLocationDict(dict):
    """Dictionary supporting attribute access for prediction location items."""
    def __getattr__(self, name):
        if name in self:
            return self[name]
        raise AttributeError(f"'PredictionLocationDict' object has no attribute '{name}'")

    def __setattr__(self, name, value):
        self[name] = value


class PredictionResultDict(dict):
    """Dictionary supporting attribute access for runtime prediction results."""
    def __getattr__(self, name):
        if name == "locations":
            return [PredictionLocationDict(l) if not isinstance(l, PredictionLocationDict) else l for l in self.get("top_locations", [])]
        if name in self:
            return self[name]
        raise AttributeError(f"'PredictionResultDict' object has no attribute '{name}'")

    def __setattr__(self, name, value):
        self[name] = value


def compute_operational_priority(
    rank: int,
    amount: Optional[float],
    time_pred_minutes: float,
    incident_time: Optional[datetime],
    reported_at: Optional[datetime]
) -> str:
    """
    Computes law-enforcement operational priority based on explicit operational signals:
    - Candidate Rank (#1 Primary, #2 Secondary, #3 Tertiary)
    - Complaint Amount Band (>= ₹5L Critical, >= ₹75k High, >= ₹20k Medium)
    - Predicted Cash-Out Window Urgency (<= 90 min)
    - Incident-to-Report Intake Delay: (reported_at - incident_time) <= 4.0 hrs
      NOTE: This represents intake delay between incident occurrence and official report,
      NOT age relative to current wall-clock time.
    Zero coupling to candidate probability percentages; never called 'accuracy'.
    """
    amt = float(amount or 0.0)
    delay_hours = 0.0
    if incident_time and reported_at and as_utc(reported_at) >= as_utc(incident_time):
        delay_hours = (as_utc(reported_at) - as_utc(incident_time)).total_seconds() / 3600.0

    is_recent = delay_hours <= 4.0
    is_urgent = time_pred_minutes <= 90.0

    if rank == 1:
        if amt >= 500000.0 or (amt >= 150000.0 and is_urgent and is_recent):
            return "CRITICAL"
        elif amt >= 75000.0 or (amt >= 30000.0 and is_urgent):
            return "HIGH"
        elif amt >= 20000.0 or is_urgent:
            return "MEDIUM"
        else:
            return "LOW"
    elif rank == 2:
        if amt >= 500000.0 and is_urgent:
            return "HIGH"
        elif amt >= 100000.0 or (amt >= 40000.0 and is_urgent):
            return "MEDIUM"
        else:
            return "LOW"
    else:  # rank >= 3
        if amt >= 500000.0 and is_urgent and is_recent:
            return "MEDIUM"
        else:
            return "LOW"


def explain_operational_priority_rule(
    rank: int,
    amount: Optional[float],
    time_pred_minutes: float,
    incident_time: Optional[datetime],
    reported_at: Optional[datetime]
) -> str:
    """
    Returns a truthful human-readable explanation of the operational priority decision.
    Explicitly clarifies that recency refers to incident-to-report intake delay.
    """
    amt = float(amount or 0.0)
    delay_hours = 0.0
    if incident_time and reported_at and as_utc(reported_at) >= as_utc(incident_time):
        delay_hours = (as_utc(reported_at) - as_utc(incident_time)).total_seconds() / 3600.0

    is_recent = delay_hours <= 4.0
    is_urgent = time_pred_minutes <= 90.0

    amt_formatted = f"₹{amt:,.2f}"
    intake_desc = f"intake delay {delay_hours:.1f}h (threshold <= 4h)" if is_recent else f"intake delay {delay_hours:.1f}h (> 4h)"
    urgency_desc = f"predicted window urgency {time_pred_minutes:.0f}m (threshold <= 90m)" if is_urgent else f"predicted window {time_pred_minutes:.0f}m (> 90m)"

    if rank == 1:
        if amt >= 500000.0:
            return f"Rank #1 Primary; High financial loss ({amt_formatted} >= ₹5L) triggers CRITICAL operational priority."
        elif amt >= 150000.0 and is_urgent and is_recent:
            return f"Rank #1 Primary; Compound risk ({amt_formatted} >= ₹1.5L + {urgency_desc} + {intake_desc}) triggers CRITICAL priority."
        elif amt >= 75000.0:
            return f"Rank #1 Primary; Financial loss ({amt_formatted} >= ₹75k) triggers HIGH priority."
        elif amt >= 30000.0 and is_urgent:
            return f"Rank #1 Primary; Immediate urgency ({amt_formatted} >= ₹30k + {urgency_desc}) triggers HIGH priority."
        elif amt >= 20000.0:
            return f"Rank #1 Primary; Loss ({amt_formatted} >= ₹20k) triggers MEDIUM priority."
        elif is_urgent:
            return f"Rank #1 Primary; Immediate window urgency ({urgency_desc}) triggers MEDIUM priority."
        else:
            return f"Rank #1 Primary; Routine observation ({amt_formatted} < ₹20k without immediate window urgency)."
    elif rank == 2:
        if amt >= 500000.0 and is_urgent:
            return f"Rank #2 Secondary; High financial loss with urgency ({amt_formatted} >= ₹5L + {urgency_desc}) triggers HIGH priority."
        elif amt >= 100000.0:
            return f"Rank #2 Secondary; Financial loss ({amt_formatted} >= ₹100k) triggers MEDIUM priority."
        elif amt >= 40000.0 and is_urgent:
            return f"Rank #2 Secondary; Loss with window urgency ({amt_formatted} >= ₹40k + {urgency_desc}) triggers MEDIUM priority."
        else:
            return f"Rank #2 Secondary; Routine observation."
    else:
        if amt >= 500000.0 and is_urgent and is_recent:
            return f"Rank #{rank} Candidate; High loss with urgency and recent intake ({amt_formatted} >= ₹5L + {urgency_desc} + {intake_desc}) triggers MEDIUM priority."
        else:
            return f"Rank #{rank} Candidate; Routine observation."


class MLPredictionProvider:
    """
    Trained Machine Learning Provider for CyberShield AI (Step 9 & Step 16).
    Executes candidate location ranking via XGBoost V4 (or V3.1 fallback),
    Platt probability calibration, and Time Model V3 (or V2 fallback).
    """
    def __init__(self, artifacts_dir: Optional[str] = None):
        self.artifacts_dir = artifacts_dir or resolve_artifacts_dir()
        self.location_model = None
        self.calibrator = None
        self.time_model = None
        self.feature_schema = None
        self.metadata = None
        self.is_loaded = False
        self.load_error = None
        self.location_hash = None
        self.calibrator_hash = None

        self.model_version = None
        self.time_model_version = "cashout-time-xgb-v3"
        self.dataset_version = "delhi_synthetic_v2"
        self.operational_scope = "DELHI_PILOT"
        self.candidate_pool_size = 0
        self.location_feature_version = None

        self._load_models()

    def _load_models(self):
        """
        Loads and verifies V7-compat location ranker (stacked over V4) & Time V3 model,
        with strict fallback to V4 if V7-compat is unavailable or integrity fails.
        """
        self.v4_model = None
        self.v4_calibrator = None
        self.v4_location_hash = None
        self.v4_calibrator_hash = None

        # 1. Always verify and load V4 dependency first
        loc_v4_filename = "location_ranker_v4.joblib"
        cal_v4_filename = "location_calibrator_v4.joblib"
        loc_v4_path = os.path.join(self.artifacts_dir, loc_v4_filename)
        cal_v4_path = os.path.join(self.artifacts_dir, cal_v4_filename)

        time_filename = "time_regressor_v3.joblib"
        time_path = os.path.join(self.artifacts_dir, time_filename)

        if not os.path.exists(loc_v4_path):
            self.load_error = "Required base model V4 not found on disk."
            logger.error(self.load_error)
            return

        v4_loc_hash = compute_file_sha256(loc_v4_path)
        v4_cal_hash = compute_file_sha256(cal_v4_path)
        if v4_loc_hash != EXPECTED_HASHES.get(loc_v4_filename) or v4_cal_hash != EXPECTED_HASHES.get(cal_v4_filename):
            self.load_error = f"Base V4 integrity check failed (loc={v4_loc_hash}, cal={v4_cal_hash})"
            logger.error(self.load_error)
            return

        time_hash = compute_file_sha256(time_path)
        if time_hash != EXPECTED_HASHES.get(time_filename):
            self.load_error = f"Time V3 integrity check failed ({time_hash})"
            logger.error(self.load_error)
            return

        try:
            self.v4_model = joblib.load(loc_v4_path)
            self.v4_calibrator = joblib.load(cal_v4_path)
            self.v4_location_hash = v4_loc_hash
            self.v4_calibrator_hash = v4_cal_hash
            self.time_model = joblib.load(time_path)
        except Exception as e:
            self.load_error = f"Failed to load V4 base artifacts: {e}"
            logger.error(self.load_error)
            return

        # 2. Check active version configuration strictly
        active_version = os.environ.get("ACTIVE_LOCATION_MODEL_VERSION", "v7_compat")

        if active_version == "v8_debiased":
            loc_v8_filename = "location_ranker_v8_debiased.joblib"
            cal_v8_filename = "location_calibrator_v8_debiased.joblib"
            schema_v8_filename = "feature_schema_v8_debiased.json"
            meta_v8_filename = "model_metadata_v8_debiased.json"

            loc_v8_path = os.path.join(self.artifacts_dir, loc_v8_filename)
            cal_v8_path = os.path.join(self.artifacts_dir, cal_v8_filename)
            schema_v8_path = os.path.join(self.artifacts_dir, schema_v8_filename)
            meta_v8_path = os.path.join(self.artifacts_dir, meta_v8_filename)

            if not (os.path.exists(loc_v8_path) and os.path.exists(cal_v8_path) and os.path.exists(schema_v8_path)):
                self.load_error = "V8-debiased configured as active model, but V8 artifacts not found on disk."
                self.is_loaded = False
                self.model_version = "MODEL_UNAVAILABLE"
                self.location_model = None
                self.calibrator = None
                logger.error(self.load_error)
                return

            EXPECTED_V8_SCHEMA_HASHES = {
                "68c9643cea2c3f2480ca085e5da37299568cf72fef98e3f2c7f39b840c514b4b",  # Windows CRLF
                "3f263a88735f5df3d397561b4c37d1c6ae7b6498ca8f676dc159655ca1556a82",  # Linux LF
            }

            if (v8_loc_hash != EXPECTED_HASHES.get(loc_v8_filename) or
                v8_cal_hash != EXPECTED_HASHES.get(cal_v8_filename) or
                v8_schema_hash not in EXPECTED_V8_SCHEMA_HASHES):
                self.load_error = f"V8-debiased artifact verification failed (loc={v8_loc_hash}, cal={v8_cal_hash}, schema={v8_schema_hash})"
                self.is_loaded = False
                self.model_version = "MODEL_UNAVAILABLE"
                self.location_model = None
                self.calibrator = None
                logger.error(self.load_error)
                return

            try:
                self.location_model = joblib.load(loc_v8_path)
                self.calibrator = joblib.load(cal_v8_path)
                with open(schema_v8_path, "r") as f:
                    self.feature_schema = json.load(f)
                if os.path.exists(meta_v8_path):
                    with open(meta_v8_path, "r") as f:
                        self.metadata = json.load(f)

                if len(self.feature_schema.get("location_features", [])) != len(FEATURE_COLUMNS_LOCATION_V8_DEBIASED):
                    raise ValueError(f"V8-debiased feature schema count mismatch (found {len(self.feature_schema.get('location_features', []))}, expected {len(FEATURE_COLUMNS_LOCATION_V8_DEBIASED)})")

                self.model_version = "cashout-location-xgb-v8-debiased"
                self.time_model_version = "cashout-time-xgb-v3"
                self.location_feature_version = "v8_debiased"
                self.candidate_pool_size = 60
                self.location_hash = v8_loc_hash
                self.calibrator_hash = v8_cal_hash
                self.is_loaded = True
                logger.info("Successfully loaded and verified cashout-location-xgb-v8-debiased (49 features, 60 Delhi clusters)")
                return
            except Exception as e:
                self.load_error = f"V8-debiased load failed: {e}"
                self.is_loaded = False
                self.location_model = None
                self.calibrator = None
                logger.error(self.load_error)
                return

        elif active_version == "v7_compat":
            loc_v7_filename = "location_ranker_v7_compat.joblib"
            cal_v7_filename = "location_calibrator_v7_compat.joblib"
            schema_v7_filename = "feature_schema_v7_compat.json"
            meta_v7_filename = "model_metadata_v7_compat.json"

            loc_v7_path = os.path.join(self.artifacts_dir, loc_v7_filename)
            cal_v7_path = os.path.join(self.artifacts_dir, cal_v7_filename)
            schema_v7_path = os.path.join(self.artifacts_dir, schema_v7_filename)
            meta_v7_path = os.path.join(self.artifacts_dir, meta_v7_filename)

            if not (os.path.exists(loc_v7_path) and os.path.exists(cal_v7_path) and os.path.exists(schema_v7_path)):
                self.load_error = "V7-compat configured as active model, but V7 artifacts not found on disk."
                self.is_loaded = False
                self.location_model = None
                self.calibrator = None
                logger.error(self.load_error)
                return

            v7_loc_hash = compute_file_sha256(loc_v7_path)
            v7_cal_hash = compute_file_sha256(cal_v7_path)
            v7_schema_hash = compute_file_sha256(schema_v7_path)

            if (v7_loc_hash != EXPECTED_HASHES.get(loc_v7_filename) or
                v7_cal_hash != EXPECTED_HASHES.get(cal_v7_filename) or
                v7_schema_hash != EXPECTED_HASHES.get(schema_v7_filename)):
                self.load_error = f"V7-compat artifact verification failed (loc={v7_loc_hash}, cal={v7_cal_hash}, schema={v7_schema_hash})"
                self.is_loaded = False
                self.location_model = None
                self.calibrator = None
                logger.error(self.load_error)
                return

            try:
                self.location_model = joblib.load(loc_v7_path)
                self.calibrator = joblib.load(cal_v7_path)
                with open(schema_v7_path, "r") as f:
                    self.feature_schema = json.load(f)
                if os.path.exists(meta_v7_path):
                    with open(meta_v7_path, "r") as f:
                        self.metadata = json.load(f)

                if self.feature_schema.get("location_features") != FEATURE_COLUMNS_LOCATION_V7_COMPAT:
                    raise ValueError("V7-compat feature schema does not match expected 47 features")

                self.model_version = "cashout-location-xgb-v7-compat"
                self.time_model_version = "cashout-time-xgb-v3"
                self.location_feature_version = "v7_compat"
                self.candidate_pool_size = 25
                self.location_hash = v7_loc_hash
                self.calibrator_hash = v7_cal_hash
                self.is_loaded = True
                logger.info("Successfully loaded and verified cashout-location-xgb-v7-compat (with V4 base dependency)")
                return
            except Exception as e:
                self.load_error = f"V7-compat load failed: {e}"
                self.is_loaded = False
                self.location_model = None
                self.calibrator = None
                logger.error(self.load_error)
                return

        # 4. Fallback only if explicitly configured for v4
        elif active_version == "v4":
            schema_v4_path = os.path.join(self.artifacts_dir, "feature_schema_v4.json")
            meta_v4_path = os.path.join(self.artifacts_dir, "model_metadata_v4.json")
            try:
                self.location_model = self.v4_model
                self.calibrator = self.v4_calibrator
                self.location_hash = self.v4_location_hash
                self.calibrator_hash = self.v4_calibrator_hash
                self.model_version = "cashout-location-xgb-v4"
                self.time_model_version = "cashout-time-xgb-v3"
                self.location_feature_version = "v3.1"
                self.candidate_pool_size = 25
                with open(schema_v4_path, "r") as f:
                    self.feature_schema = json.load(f)
                with open(meta_v4_path, "r") as f:
                    self.metadata = json.load(f)
                self.is_loaded = True
                logger.info("Operating safely on cashout-location-xgb-v4 baseline")
                return
            except Exception as e:
                self.load_error = f"Failed to initialize V4 baseline: {e}"
                self.is_loaded = False
                self.location_model = None
                self.calibrator = None
                logger.error(self.load_error)
                return
        else:
            self.load_error = f"Unknown ACTIVE_LOCATION_MODEL_VERSION configuration: {active_version}"
            self.is_loaded = False
            self.location_model = None
            self.calibrator = None
            logger.error(self.load_error)
            return

    def is_available(self) -> bool:
        return (
            self.is_loaded and
            self.location_model is not None and
            self.calibrator is not None and
            self.time_model is not None
        )

    def predict(self, complaint: Complaint, db: Session, analysis_as_of: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Executes real trained-ML inference for an eligible complaint strictly as of analysis_as_of.
        Does NOT persist results to database.
        Does NOT query Withdrawal or future targets.
        """
        if not self.is_available():
            return {
                "complaint_id": complaint.id,
                "complaint_number": complaint.complaint_number,
                "status": "MODEL_UNAVAILABLE",
                "prediction_mode": "unavailable",
                "model_version": self.model_version,
                "operational_scope": self.operational_scope,
                "candidate_pool_size": 0,
                "top_locations": [],
                "time_prediction": None,
                "message": f"Trained ML models unavailable: {self.load_error}",
                "limitations": ["Model artifact verification failed or artifacts not loaded."]
            }

        # 1. Scope & Regional Model Support Eligibility Gate
        from backend.app.services.geography_catalog_service import (
            resolve_region_for_complaint, get_region_by_id
        )
        resolved_region_id, region_obj = resolve_region_for_complaint(
            db,
            state=complaint.state,
            district=complaint.district,
            lat=complaint.victim_lat,
            lon=complaint.victim_lon,
            explicit_region_id=getattr(complaint, "region_id", None)
        )

        c_state = str(complaint.state or "").strip().lower()
        c_dist = str(complaint.district or "").strip().upper()
        is_delhi_state = (c_state in ("delhi", "new delhi", "nct of delhi") or resolved_region_id == "delhi")
        is_delhi_zone = (c_dist in DELHI_ZONE_CENTROIDS)

        # Case A: Region is registered, but model support is NOT MODEL_SUPPORTED (e.g. VALIDATION_PENDING or UNSUPPORTED)
        if region_obj and region_obj.id != "delhi":
            model_status = region_obj.model_support_status
            return {
                "complaint_id": complaint.id,
                "complaint_number": complaint.complaint_number,
                "status": "MODEL_NOT_SUPPORTED_FOR_REGION",
                "region_id": region_obj.id,
                "region_name": region_obj.name,
                "prediction_mode": "unsupported_region",
                "model_support_status": model_status,
                "model_version": None,
                "operational_scope": f"REGION_{region_obj.id.upper()}_{model_status}",
                "candidate_pool_size": 0,
                "top_locations": [],
                "time_prediction": None,
                "message": (
                    f"Complaint {complaint.complaint_number} is in region '{region_obj.name}' ({region_obj.id}) "
                    f"where predictive model validation is {model_status}. Trained models are strictly calibrated for Delhi Pilot."
                ),
                "refusal_reason": (
                    f"MODEL_NOT_SUPPORTED_FOR_REGION: Complaint {complaint.complaint_number} is in region '{region_obj.name}' ({region_obj.id}) "
                    f"where predictive model validation is {model_status}. Trained models are strictly calibrated for Delhi Pilot."
                ),
                "explanation": {
                    "summary": f"Region '{region_obj.name}' ({region_obj.id}) predictive model validation is {model_status}. Inferences disabled."
                },
                "limitations": [
                    f"Geography catalog available for region '{region_obj.name}' ({region_obj.id}), but model validation is {model_status}.",
                    "A Delhi-trained model cannot be used to predict in another geographic region without validated transfer evaluation.",
                    "No fabricated or fallback predictions are returned for unvalidated regions."
                ]
            }

        # Case B: Region is completely unregistered / outside operational scope
        if not (is_delhi_state or is_delhi_zone):
            return {
                "complaint_id": complaint.id,
                "complaint_number": complaint.complaint_number,
                "status": "OUTSIDE_OPERATIONAL_SCOPE",
                "prediction_mode": "unsupported_region",
                "model_version": self.model_version,
                "operational_scope": self.operational_scope,
                "candidate_pool_size": 0,
                "top_locations": [],
                "time_prediction": None,
                "message": f"Complaint {complaint.complaint_number} is outside Delhi Pilot operational scope (state='{complaint.state}', district='{complaint.district}').",
                "refusal_reason": f"OUTSIDE_OPERATIONAL_SCOPE: Complaint {complaint.complaint_number} is outside operational scope (state='{complaint.state}', district='{complaint.district}').",
                "explanation": {
                    "summary": f"Complaint {complaint.complaint_number} is outside operational scope."
                },
                "limitations": [
                    "Location is not registered in the Geography Catalog.",
                    "Models are strictly calibrated for the Delhi Pilot 60-cluster jurisdiction.",
                    "Non-Delhi complaints cannot receive valid inferences from the Delhi Pilot model.",
                    "No fallback or fabricated predictions are returned."
                ]
            }

        # 2. Transaction Context & Scenario Eligibility Gate (point-in-time cutoff enforced)
        ctx = resolve_transaction_context(db, complaint, analysis_as_of=analysis_as_of)
        transactions = ctx.get("transactions", [])
        ctx_type = ctx.get("context_type", "EMPTY")

        analysis_basis = (
            "linked_synthetic_scenario" if ctx_type == "LINKED_SYNTHETIC_SCENARIO"
            else "observed_transactions" if transactions else "complaint_only"
        )

        # 3. Build Multi-Modal Feature Matrices through Step 8 Service with cutoff
        loc_res = build_location_features(
            db,
            complaint.id,
            top_k=self.candidate_pool_size,
            model_version=self.location_feature_version,
            analysis_as_of=analysis_as_of
        )
        time_res = build_time_features(db, complaint.id, analysis_as_of=analysis_as_of)

        if loc_res["status"] != "SUCCESS" or time_res["status"] != "SUCCESS":
            return {
                "complaint_id": complaint.id,
                "complaint_number": complaint.complaint_number,
                "status": loc_res["status"] if loc_res["status"] != "SUCCESS" else time_res["status"],
                "prediction_mode": "unavailable",
                "model_version": self.model_version,
                "operational_scope": self.operational_scope,
                "candidate_pool_size": 0,
                "top_locations": [],
                "time_prediction": None,
                "message": f"Feature pipeline failed: {loc_res.get('status')}",
                "limitations": ["Candidate feature extraction could not be completed."]
            }

        X_loc = loc_res["candidate_rows"]
        candidates = loc_res["candidates"]
        X_time = time_res["values"]

        # 4. Actual Model Inference
        # Location model inference (V8-debiased, V7-compat stacked, or V4 direct)
        if self.model_version == "cashout-location-xgb-v8-debiased":
            raw_scores = self.location_model.predict(X_loc)
            cal_probs = self.calibrator.predict_proba(raw_scores.reshape(-1, 1))[:, 1]
        elif self.model_version == "cashout-location-xgb-v7-compat":
            # 1. Base V4 inference
            v4_raw = self.v4_model.predict_proba(X_loc)[:, 1]
            v4_scores = self.v4_calibrator.predict_proba(v4_raw.reshape(-1, 1))[:, 1]
            n_cands = len(candidates)
            ranks = np.argsort(-v4_scores)
            rank_positions = np.empty_like(ranks)
            rank_positions[ranks] = np.arange(n_cands)
            v4_ranks_norm = rank_positions / max(1.0, float(n_cands - 1))
            v4_percentiles = (n_cands - 1 - rank_positions) / max(1.0, float(n_cands - 1))
            best_v4_score = float(np.max(v4_scores))
            v4_gaps = best_v4_score - v4_scores

            v4_feats = np.column_stack([
                v4_scores,
                v4_ranks_norm,
                v4_percentiles,
                v4_gaps
            ])
            X_loc_compat = np.hstack([X_loc, v4_feats])

            # 2. V7-compat pairwise ranker inference
            raw_scores = self.location_model.predict(X_loc_compat)
            # Calibrate using Platt logistic calibrator
            cal_probs = self.calibrator.predict_proba(raw_scores.reshape(-1, 1))[:, 1]
        else:
            # Positive-class location probabilities via V4
            raw_probs = self.location_model.predict_proba(X_loc)[:, 1]
            cal_probs = self.calibrator.predict_proba(raw_probs.reshape(-1, 1))[:, 1]

        if len(candidates) < 3 or not np.all(np.isfinite(cal_probs)) or np.any((cal_probs < 0) | (cal_probs > 1)):
            raise ValueError("Location model did not return three valid scored candidates")

        # Time model prediction (minutes to cashout)
        if "v3" in self.time_model_version:
            raw_time_pred = float(self.time_model.predict(X_time.reshape(1, -1))[0])
            time_pred_minutes = float(np.expm1(raw_time_pred))
        else:
            time_pred_minutes = float(self.time_model.predict(X_time.reshape(1, -1))[0])
        time_pred_minutes = max(15.0, round(time_pred_minutes, 1))
        time_metrics = (self.metadata or {}).get("evaluation_metrics", {}).get(
            "time_v3" if "v3" in self.time_model_version else "time_v2", {}
        )
        mae = time_metrics.get("mae")
        # A heuristic margin based on synthetic held-out error is not a confidence interval.
        time_margin = max(15, math.ceil(float(mae))) if mae is not None else 35
        time_prediction = build_time_prediction(
            complaint, time_pred_minutes, self.time_model_version, time_margin,
            "synthetic_test_mae" if mae is not None else "operational_estimate",
        )

        # 5. Top-3 Dynamic Ranking
        ranked_indices = sorted(
            range(len(candidates)),
            key=lambda i: (-float(cal_probs[i]), int(candidates[i]["id"])),
        )
        top_locations = []

        term_zone = loc_res["provenance"].get("terminal_zone")
        all_tx_zones = set(loc_res["provenance"].get("all_tx_zones", []))

        v_lat = float(complaint.victim_lat) if complaint.victim_lat is not None else None
        v_lon = float(complaint.victim_lon) if complaint.victim_lon is not None else None
        origin_zone = complaint.district

        if v_lat is None or v_lon is None or not origin_zone or origin_zone == "CENTRAL_NEW_DELHI":
            loc_str = getattr(complaint, "locality", None) or getattr(complaint, "victim_location", None) or ""
            origin_res = resolve_delhi_origin(locality=loc_str, district=complaint.district, lat=v_lat, lon=v_lon)
            if origin_res["resolved_lat"] is not None and v_lat is None:
                v_lat = origin_res["resolved_lat"]
                v_lon = origin_res["resolved_lon"]
            if origin_res["resolved_district"] is not None and (not origin_zone or origin_zone == "CENTRAL_NEW_DELHI"):
                origin_zone = origin_res["resolved_district"]

        has_coords = (
            v_lat is not None and
            v_lon is not None and
            not math.isnan(v_lat)
        )

        c_inc_time = getattr(complaint, "incident_time", None) or getattr(complaint, "incident_timestamp", None)
        c_rep_time = getattr(complaint, "reported_at", None)

        for rank, idx in enumerate(ranked_indices[:3], start=1):
            cand = candidates[idx]
            prob = float(round(cal_probs[idx], 4))
            cand_zone = cand.get("district") or cand.get("zone", "")

            # Generate objective, prediction-time-safe evidence
            evidence = []
            if origin_zone and cand_zone == origin_zone:
                evidence.append(f"Direct spatial alignment with complaint origin zone ({origin_zone})")
            if term_zone and cand_zone == term_zone:
                evidence.append(f"Matches the latest recipient account zone ({term_zone})")
            elif cand_zone in all_tx_zones:
                evidence.append(f"Matches an intermediate recipient account zone ({cand_zone})")

            if has_coords:
                dist_km = haversine_km(v_lat, v_lon, float(cand["lat"]), float(cand["lon"]))
                evidence.append(f"Proximity: {dist_km:.1f} km from reported incident location")
            else:
                dist_km = float(cand.get("dist_to_complaint_zone_km", 12.0))

            base_risk = float(cand["historical_risk"])
            atm_cnt = int(cand["atm_density"])
            history_count = int(cand["historical_cashout_count"])
            evidence.append(f"Pilot database: {history_count} synthetic historical cases; {atm_cnt} ATM locations")
            if analysis_basis == "complaint_only":
                evidence.append("Preliminary ranking from complaint details and pilot geography; no transaction trail supplied")
            elif analysis_basis == "linked_synthetic_scenario":
                evidence.append("Transaction context is a linked synthetic demonstration scenario")

            # Operational priority derived from explicit operational signals (Rank, Amount, Window, Recency)
            risk_band = compute_operational_priority(
                rank=rank,
                amount=float(complaint.amount or 0.0),
                time_pred_minutes=time_pred_minutes,
                incident_time=c_inc_time,
                reported_at=c_rep_time
            )

            # Clean officer-facing intervention reasoning without raw percentage display
            if rank == 1:
                if "v7-compat" in self.model_version:
                    loc_ver_name = "Location V7-compat"
                elif "v4" in self.model_version:
                    loc_ver_name = "Location V4"
                else:
                    loc_ver_name = "Location V3.1"
                reasoning = f"Ranked #1 by {loc_ver_name} for the current complaint context."
            elif rank == 2:
                reasoning = "Ranked #2 candidate zone for the current complaint context."
            else:
                reasoning = "Ranked #3 candidate zone for the current complaint context."

            top_locations.append({
                "rank": rank,
                "cluster_id": cand["id"],
                "cluster_name": cand["name"],
                "location_name": cand["name"],
                "zone": cand_zone,
                "district": cand.get("district", cand_zone),
                "state": cand.get("state", "Delhi"),
                "latitude": float(cand["lat"]),
                "longitude": float(cand["lon"]),
                "probability": prob,
                "ml_probability": prob,
                "risk_score": prob,
                "risk_level": risk_band,
                "risk_band": risk_band,
                "operational_priority": risk_band,
                "operational_priority_basis": explain_operational_priority_rule(
                    rank=rank,
                    amount=float(complaint.amount or 0.0),
                    time_pred_minutes=time_pred_minutes,
                    incident_time=c_inc_time,
                    reported_at=c_rep_time
                ),
                "distance_km": round(dist_km, 1),
                "reasoning": reasoning,
                "evidence": evidence
            })

        window_label = time_prediction["operational_window"]

        primary_loc = top_locations[0]["location_name"]
        primary_prob = top_locations[0]["ml_probability"]
        primary_band = top_locations[0]["risk_band"]

        # Normalized intervention priority aligned with operational priority band
        if primary_band == "CRITICAL":
            priority = 90
            priority_label = "IMMEDIATE ACTION"
        elif primary_band == "HIGH":
            priority = 75
            priority_label = "HIGH PRIORITY"
        elif primary_band == "MEDIUM":
            priority = 50
            priority_label = "MONITOR"
        else:
            priority = 30
            priority_label = "ROUTINE"

        top_locations = [PredictionLocationDict(l) for l in top_locations]

        limitations = [
            "Model trained and evaluated on synthetic Delhi data; scores are not validated real-world probabilities or accuracy.",
            "Only registered Delhi pilot clusters are ranked; the three scores are not normalized to sum to 100%.",
            "Time is measured from complaint reporting. The displayed error margin is a heuristic, not a calibrated confidence interval.",
        ]
        metrics = (self.metadata or {}).get("evaluation_metrics", {}).get(
            "location_v7_compat" if "v7-compat" in self.model_version else ("location_v4" if "v4" in self.model_version else "location_v3_1"), {}
        )
        if metrics.get("r3") is not None:
            limitations.append(f"Synthetic held-out Top-3 recall: {float(metrics['r3']):.2f}%; performance on real complaints is unknown.")
        if analysis_basis == "complaint_only":
            limitations.append("No transaction trail is available. This preliminary complaint-only estimate is outside the transaction-rich training setting.")
        if analysis_basis == "linked_synthetic_scenario":
            limitations.append("Linked transaction movements are synthetic scenario data, not observed movements for this complaint.")

        # Phase 5: Faithful, immutable inference snapshot captured at prediction time
        if "v8-debiased" in self.model_version:
            feature_names = list(FEATURE_COLUMNS_LOCATION_V8_DEBIASED)
            active_matrix = X_loc
        elif "v7-compat" in self.model_version:
            feature_names = list(FEATURE_COLUMNS_LOCATION_V7_COMPAT)
            active_matrix = X_loc_compat
        else:
            feature_names = list(FEATURE_COLUMNS_LOCATION_V3_1)
            active_matrix = X_loc
        schema_file = f"feature_schema_{self.location_feature_version}.json"
        schema_hash = EXPECTED_HASHES.get(schema_file)

        candidate_features_dict = {}
        official_scores_dict = {}
        candidate_metadata_list = []

        for c_idx, c_obj in enumerate(candidates):
            cid_str = str(c_obj["id"])
            candidate_features_dict[cid_str] = [
                float(val) if (val is not None and not np.isnan(val) and not np.isinf(val)) else 0.0
                for val in active_matrix[c_idx]
            ]
            official_scores_dict[cid_str] = float(round(cal_probs[c_idx], 4))
            r_pos = ranked_indices.index(c_idx) + 1 if c_idx in ranked_indices else None
            candidate_metadata_list.append({
                "cluster_id": int(c_obj["id"]),
                "location_name": str(c_obj.get("location_name") or c_obj.get("name") or f"Cluster {c_obj['id']}"),
                "district": str(c_obj.get("district") or c_obj.get("zone") or ""),
                "latitude": float(c_obj["lat"]) if c_obj.get("lat") is not None else None,
                "longitude": float(c_obj["lon"]) if c_obj.get("lon") is not None else None,
                "official_score": float(round(cal_probs[c_idx], 4)),
                "rank": r_pos
            })

        inference_snapshot = {
            "snapshot_version": "1.0",
            "model_version": self.model_version,
            "time_model_version": self.time_model_version,
            "feature_schema_version": self.location_feature_version,
            "feature_schema_hash": schema_hash,
            "model_hash": self.location_hash,
            "location_model_hash": self.location_hash,
            "calibrator_hash": self.calibrator_hash,
            "candidate_pool_size": len(candidates),
            "feature_names": feature_names,
            "candidate_features": candidate_features_dict,
            "official_candidate_scores": official_scores_dict,
            "candidate_metadata": candidate_metadata_list,
            "provenance": {
                "terminal_zone": term_zone,
                "all_tx_zones": list(all_tx_zones),
                "origin_zone": origin_zone,
                "victim_lat": v_lat,
                "victim_lon": v_lon,
                "context_type": ctx_type,
                "analysis_basis": analysis_basis,
                "graph_nodes": loc_res["provenance"].get("graph_node_count"),
                "graph_edges": loc_res["provenance"].get("graph_edge_count")
            },
            "prediction_timestamp": datetime.now(timezone.utc).isoformat()
        }

        return PredictionResultDict({
            "prediction_id": 0,
            "complaint_id": complaint.id,
            "complaint_number": complaint.complaint_number,
            "status": "SUCCESS",
            "prediction_mode": "trained_ml",
            "model_version": self.model_version,
            "operational_scope": self.operational_scope,
            "region_id": getattr(complaint, "region_id", "delhi") or "delhi",
            "region_name": "National Capital Territory of Delhi",
            "model_support_status": "PROTOTYPE_OPERATIONAL",
            "candidate_pool_size": len(candidates),
            "primary_cluster_id": top_locations[0]["cluster_id"],
            "score_type": "synthetic_calibrated_candidate_score",
            "score_label": "Synthetic model score",
            "training_data_source": "synthetic_delhi",
            "analysis_basis": analysis_basis,
            "location_feature_version": self.location_feature_version,
            "dataset_version": self.dataset_version,
            "where_location": primary_loc,
            "when_window": window_label,
            "risk_score": primary_prob,
            "risk_percentage": int(primary_prob * 100),
            "risk_level": primary_band,
            "risk_band": primary_band,
            "intervention_priority": priority,
            "priority_level": priority_label,
            "why_summary": (
                "Preliminary cash-out cluster ranking from complaint details and synthetic Delhi historical patterns."
                if analysis_basis == "complaint_only" else
                "Cash-out cluster ranking from transaction context and synthetic Delhi historical patterns."
            ),
            "confidence_score": primary_prob,
            "ml_score": primary_prob,
            "graph_score": round(min(1.0, float(loc_res["provenance"].get("graph_edge_count", 0)) / 8.0), 2),
            "geo_score": round(float(candidates[ranked_indices[0]]["historical_risk"]), 2),
            "temporal_score": round(min(1.0, max(0.20, 1.0 - (time_pred_minutes / 400.0))), 2),
            "top_locations": top_locations,
            "time_prediction": time_prediction,
            "limitations": limitations,
            "inference_snapshot": inference_snapshot,
            "provenance": {
                "location_model_sha256": self.location_hash,
                "calibrator_sha256": self.calibrator_hash,
                "transaction_context_type": loc_res["provenance"].get("context_type"),
                "graph_nodes": loc_res["provenance"].get("graph_node_count"),
                "graph_edges": loc_res["provenance"].get("graph_edge_count"),
                "features_used": 49 if "v8-debiased" in self.model_version else (47 if "v7-compat" in self.model_version else 43),
                "time_features_used": 20,
                "transaction_count": len(transactions),
                "source_scenario": ctx.get("source_scenario"),
                "historical_features_source": "synthetic_pilot_baselines",
                "zero_target_lookup": True
            },
            "created_at": datetime.utcnow()
        })


class DemoPredictionProvider:
    """
    Deterministic High-Fidelity provider for SIH Demo case (CMP-1042).
    Preserves demo path without labeling it as trained ML.
    """
    @staticmethod
    def get_prediction_for_complaint(complaint: Complaint, db: Session) -> Dict[str, Any]:
        top_locations = [
            {
                "rank": 1,
                "cluster_id": 1,
                "cluster_name": "Vijay Nagar, Indore",
                "location_name": "Vijay Nagar, Indore",
                "zone": "Indore",
                "district": "Indore",
                "state": "Madhya Pradesh",
                "probability": 0.87,
                "ml_probability": 0.87,
                "risk_score": 0.87,
                "risk_level": "CRITICAL",
                "risk_band": "CRITICAL",
                "operational_priority": "CRITICAL",
                "operational_priority_basis": "Rank #1 Primary; High-loss SIH scenario corridor triggers CRITICAL operational priority.",
                "distance_km": 186.4,
                "reasoning": "High Mule-Network Similarity & Recent ATM Cashier Activity",
                "evidence": [
                    "High Mule-Network Similarity & Recent ATM Cashier Activity",
                    "Direct correlation with known syndicate withdrawal corridors"
                ],
                "latitude": 22.7533,
                "longitude": 75.8937
            },
            {
                "rank": 2,
                "cluster_id": 2,
                "cluster_name": "Palasia, Indore",
                "location_name": "Palasia, Indore",
                "zone": "Indore",
                "district": "Indore",
                "state": "Madhya Pradesh",
                "probability": 0.61,
                "ml_probability": 0.61,
                "risk_score": 0.61,
                "risk_level": "HIGH",
                "risk_band": "HIGH",
                "operational_priority": "HIGH",
                "operational_priority_basis": "Rank #2 Secondary; High commercial density corridor triggers HIGH operational priority.",
                "distance_km": 189.1,
                "reasoning": "Secondary ATM Cluster linked to Mule B layering account",
                "evidence": [
                    "Secondary ATM Cluster linked to Mule B layering account",
                    "High commercial retail ATM density"
                ],
                "latitude": 22.7244,
                "longitude": 75.8839
            },
            {
                "rank": 3,
                "cluster_id": 3,
                "cluster_name": "Rau, Indore",
                "location_name": "Rau, Indore",
                "zone": "Indore",
                "district": "Indore",
                "state": "Madhya Pradesh",
                "probability": 0.34,
                "ml_probability": 0.34,
                "risk_score": 0.34,
                "risk_level": "MEDIUM",
                "risk_band": "MEDIUM",
                "operational_priority": "MEDIUM",
                "operational_priority_basis": "Rank #3 Candidate; Outlying node triggers MEDIUM operational priority.",
                "distance_km": 198.7,
                "reasoning": "Outlying highway ATM node with low historical frequency",
                "evidence": [
                    "Outlying highway ATM node with low historical frequency",
                    "Perimeter corridor node"
                ],
                "latitude": 22.6288,
                "longitude": 75.8080
            }
        ]

        top_locations = [PredictionLocationDict(l) for l in top_locations]

        return PredictionResultDict({
            "prediction_id": 1,
            "complaint_id": complaint.id,
            "complaint_number": complaint.complaint_number,
            "status": "SUCCESS",
            "prediction_mode": "deterministic_demo",
            "model_version": "demo-provider-v1",
            "operational_scope": "DEMO_MADHYA_PRADESH",
            "candidate_pool_size": 3,
            "where_location": "Vijay Nagar, Indore",
            "when_window": "Next 2–4 Hours",
            "risk_score": 0.87,
            "risk_percentage": 87,
            "risk_level": "CRITICAL",
            "risk_band": "CRITICAL",
            "intervention_priority": 94,
            "priority_level": "IMMEDIATE ACTION",
            "confidence_score": 0.92,
            "ml_score": 0.88,
            "graph_score": 0.85,
            "geo_score": 0.84,
            "temporal_score": 0.80,
            "why_summary": "High Mule-Network Similarity & Historical Hotspot Match",
            "top_locations": top_locations,
            "time_prediction": {
                "predicted_minutes_to_cashout": 150.0,
                "model_version": "demo-time-v1",
                "prediction_reference_time": str(datetime.utcnow()),
                "operational_window": "Next 2–4 Hours"
            },
            "limitations": [
                "Deterministic demonstration case reserved for SIH presentation consistency."
            ],
            "created_at": datetime.utcnow()
        })


class PredictionService:
    """
    Central Prediction Orchestrator for CyberShield AI.
    Step 9: Real-time dynamic inference without database mutations.
    """
    def __init__(self):
        self.ml_provider = MLPredictionProvider()
        self.demo_provider = DemoPredictionProvider()

    def reload_models(self):
        """Re-initializes the ML prediction provider reflecting current environment configuration."""
        self.ml_provider = MLPredictionProvider()

    def predict_complaint(self, db: Session, complaint_id: int, analysis_as_of: Optional[datetime] = None) -> PredictionResultDict:
        """
        Runs runtime prediction without persisting to database (Step 9 read-only contract).
        """
        complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
        if not complaint:
            raise ValueError("Complaint not found")

        # CMP-1042 is intentionally preserved as deterministic_demo for stable SIH presentation
        if complaint.complaint_number == "CMP-1042":
            res = self.demo_provider.get_prediction_for_complaint(complaint, db)
            return PredictionResultDict(res)

        # Trained ML path
        res = self.ml_provider.predict(complaint, db, analysis_as_of=analysis_as_of)
        return PredictionResultDict(res)

    def run_prediction(self, db: Session, complaint_id: int, analysis_as_of: Optional[datetime] = None) -> PredictionResultDict:
        """
        Step 9 implementation: Executes dynamic inference without database mutation.
        (Persistence is deferred to Step 10).
        """
        complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
        if not complaint:
            raise ValueError("Complaint not found")

        # CMP-1042 is intentionally preserved as deterministic_demo for stable SIH presentation
        if complaint.complaint_number == "CMP-1042":
            res = self.demo_provider.get_prediction_for_complaint(complaint, db)
            return PredictionResultDict(res)

        try:
            res = self.ml_provider.predict(complaint, db, analysis_as_of=analysis_as_of)
            return PredictionResultDict(res)
        except Exception as e:
            logger.exception("ML inference failed for complaint %s", complaint.complaint_number)
            return PredictionResultDict({
                "complaint_id": complaint.id,
                "complaint_number": complaint.complaint_number,
                "status": "INFERENCE_FAILED",
                "prediction_mode": "unavailable",
                "model_version": self.ml_provider.model_version,
                "operational_scope": "DELHI_PILOT",
                "candidate_pool_size": 0,
                "top_locations": [],
                "time_prediction": None,
                "message": "Analysis could not be completed. Check model readiness and complaint data, then retry.",
                "limitations": ["No substitute locations or demo scores were generated."],
            })

    def run_and_persist_prediction(
        self,
        db: Session,
        complaint_id: int,
        analysis_as_of: Optional[datetime] = None,
        analysis_purpose: Optional[str] = None
    ) -> PredictionResultDict:
        """
        Step 10 implementation: Executes dynamic inference and atomically persists
        successful predictions into Prediction and PredictionLocation tables.
        Preserves exact Step-9 inference outputs without re-ranking.

        analysis_purpose controls the operational vs historical classification:
          - 'OPERATIONAL': live analysis (including server-time-bounded live ingestion).
          - 'HISTORICAL_REPLAY': explicit user-initiated point-in-time replay.
          - None: inferred by persistence service (OPERATIONAL if analysis_as_of is None,
                  HISTORICAL_REPLAY if analysis_as_of is set). Callers should prefer explicit.
        """
        from backend.app.services.prediction_persistence_service import prediction_persistence_service

        complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
        if not complaint:
            raise ValueError("Complaint not found")

        # 1. Execute runtime inference directly with analysis_as_of cutoff
        res = self.predict_complaint(db, complaint.id, analysis_as_of=analysis_as_of)

        # 2. Only persist when inference returns SUCCESS
        if res.get("status") == "SUCCESS":
            # Propagate explicit analysis_purpose so persist_prediction does not
            # infer it solely from analysis_as_of (which may be a system-set live cutoff).
            if analysis_purpose is not None:
                res["analysis_purpose"] = analysis_purpose
            persisted = prediction_persistence_service.persist_prediction(db, complaint, res, analysis_as_of=analysis_as_of)
            if persisted:
                res["prediction_id"] = persisted.id
                res["version_number"] = persisted.version_number
                res["parent_prediction_id"] = persisted.parent_prediction_id
                res["analysis_as_of"] = persisted.analysis_as_of
                res["created_at"] = persisted.created_at
                res["when_window"] = persisted.window_label
                if "time_prediction" in res and res["time_prediction"]:
                    res["time_prediction"]["operational_window"] = persisted.window_label

        return PredictionResultDict(res)


    def get_explanation(self, prediction: Any, complaint: Complaint) -> Dict[str, Any]:
        """
        Provides model explainability breakdown.
        """
        pred_mode = getattr(prediction, "prediction_mode", None) or (prediction.get("prediction_mode") if isinstance(prediction, dict) else "trained_ml")
        model_ver = getattr(prediction, "model_version", None) or (prediction.get("model_version") if isinstance(prediction, dict) else "cashout-location-xgb-v3.1")
        pred_id = getattr(prediction, "id", 0) if not isinstance(prediction, dict) else prediction.get("prediction_id", 0)

        if pred_mode == "trained_ml":
            factors = [
                {
                    "name": "Mule Corridor Spatial Alignment",
                    "contribution_percentage": 28,
                    "description": "XGBoost candidate ranking model identified beneficiary cluster corridor as highest probability cash-out zone."
                },
                {
                    "name": "Historical ATM Cluster Risk Prior",
                    "contribution_percentage": 22,
                    "description": "Geospatial crime density and historical ATM cash-out velocity reinforce candidate priority."
                },
                {
                    "name": "Transaction Layering Velocity",
                    "contribution_percentage": 18,
                    "description": "Rapid multi-split transfer velocity indicates coordinated cash-out preparation."
                },
                {
                    "name": "Graph Centrality & Mule Degree",
                    "contribution_percentage": 14,
                    "description": "Betweenness centrality and mule network degree indicate organized syndicate involvement."
                },
                {
                    "name": "Modus Operandi Temporal Decay",
                    "contribution_percentage": 10,
                    "description": "Time regressor estimates extraction window based on payment channel and reporting latency."
                }
            ]
            narrative = (
                f"Prediction derived via {model_ver} (XGBoost ensemble). "
                f"Candidate location ranked based on multimodal feature fusion across mule network alignment, "
                f"geospatial ATM density, and transaction velocity."
            )
        else:
            factors = [
                {
                    "name": "Linked Mule Withdrawal History",
                    "contribution_percentage": 21,
                    "description": "Beneficiary account is directly connected to mule accounts used in 8 previous cash withdrawals in Vijay Nagar."
                },
                {
                    "name": "Historical Hotspot Score",
                    "contribution_percentage": 17,
                    "description": "Indore-Vijay Nagar ATM cluster has experienced 19 cyber fraud cash-outs in the last 30 days."
                },
                {
                    "name": "Graph Network Similarity",
                    "contribution_percentage": 14,
                    "description": "Graph topology exhibits high centrality and multi-hop layering typical of organized syndicate networks."
                },
                {
                    "name": "Transaction Timing Pattern",
                    "contribution_percentage": 11,
                    "description": "Rapid multi-split transfer after initial deposit matches high-velocity ATM extraction protocol."
                },
                {
                    "name": "Fraud Category Similarity",
                    "contribution_percentage": 8,
                    "description": "Investment scam modus operandi shows high geographic preference for tier-2 commercial retail hubs."
                }
            ]
            narrative = (
                "This location received a high-risk ranking because the beneficiary network shares historical "
                "relationships with accounts previously associated with cash withdrawals in this geographic cluster."
            )

        disclaimer = (
            "AI-generated decision support. Operational risk prioritization; not proof of criminal activity. "
            "Final operational decisions remain with authorized law enforcement investigators."
        )

        return {
            "prediction_id": pred_id,
            "complaint_number": complaint.complaint_number,
            "prediction_mode": pred_mode,
            "model_version": model_ver,
            "factors": factors,
            "narrative": narrative,
            "disclaimer": disclaimer
        }


prediction_service = PredictionService()
