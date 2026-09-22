"""
CyberShield AI — Faithful LIME Explainability Service for Official V7 Predictions
Phase 5: Faithful, Snapshot-Grounded and Officer-Readable Tabular Attribution Engine

Provides local surrogate attribution via lime.lime_tabular.LimeTabularExplainer for
cashout-location-xgb-v7-compat predictions using immutable inference snapshots.

Inviolable Guarantees:
1. Snapshot-Faithful: Explanations are computed strictly from the immutable inference
   snapshot recorded at prediction time. Live database features are NEVER reconstructed
   for historical complaints to prevent evidence drift.
2. Read-Only / Non-Mutating: Never generates, alters, or replaces official predictions,
   rankings, probabilities, Top-3, or prediction modes.
3. Safety Language: Uses local approximation language; never claims proof or causality.
4. Fidelity Honesty: Preserves genuine R² values (including low or negative) without
   fabricated fallbacks like 0.2252; marks weak fits as LOW_FIDELITY.
5. Determinism & Concurrency: Uses per-call seeded RNG instances; never mutates global np.random.
6. Non-Blocking & Sanitized: Catches all exceptions and returns sanitized UNAVAILABLE states
   without internal paths or stack traces.
"""

import os
import re
import json
import logging
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
from sqlalchemy.orm import Session

from backend.app.models.models import Complaint, Prediction, PredictionLocation, PredictionSnapshot
from backend.app.services.prediction_service import resolve_artifacts_dir, compute_file_sha256, prediction_service

logger = logging.getLogger("cybershield.explainability")

# Exact runtime feature schema for cashout-location-xgb-v7-compat
V4_COMPAT_FEATURES = [
    "v4_candidate_score",
    "v4_candidate_rank_normalized",
    "v4_candidate_percentile",
    "v4_score_gap_from_candidate1"
]

# Forbidden victim-origin features in V8
V8_FORBIDDEN_FEATURES = {
    "distance_from_victim",
    "candidate_same_complaint_zone",
    "dist_to_complaint_zone_km",
    "v4_candidate_score",
    "v4_candidate_rank_normalized",
    "v4_candidate_percentile",
    "v4_score_gap_from_candidate1"
}

# Officer-readable definitions, units, categories, provenance types, and honest descriptions
FEATURE_METADATA: Dict[str, Dict[str, str]] = {
    "log_amount": {
        "label": "Logarithm of Complaint Amount",
        "category": "Complaint Intake",
        "provenance_type": "DIRECT_INTAKE",
        "unit": "log(₹)",
        "honest_description": "Logarithm of total reported loss in complaint intake."
    },
    "fraud_type_encoded": {
        "label": "Fraud Category Code",
        "category": "Complaint Intake",
        "provenance_type": "DIRECT_INTAKE",
        "unit": "category code",
        "honest_description": "Categorical encoding of fraud modus operandi from complaint intake (UPI phishing, loan scam, etc.)."
    },
    "payment_channel_encoded": {
        "label": "Initial Payment Channel",
        "category": "Complaint Intake",
        "provenance_type": "DIRECT_INTAKE",
        "unit": "channel code",
        "honest_description": "Categorical encoding of primary victim payment channel (UPI, IMPS, RTGS, Card) reported during intake."
    },
    "complaint_hour": {
        "label": "Complaint Reporting Hour",
        "category": "Temporal Pattern",
        "provenance_type": "DIRECT_INTAKE",
        "unit": "hour (0–23)",
        "honest_description": "Clock hour when complaint was formally registered in NCRP intake."
    },
    "day_of_week": {
        "label": "Day of Week of Report",
        "category": "Temporal Pattern",
        "provenance_type": "DIRECT_INTAKE",
        "unit": "day (0–6)",
        "honest_description": "Day of the week when complaint was registered in NCRP intake."
    },
    "weekend_flag": {
        "label": "Weekend Incident Indicator",
        "category": "Temporal Pattern",
        "provenance_type": "DIRECT_INTAKE",
        "unit": "flag",
        "honest_description": "Binary indicator whether reported incident occurred during weekend."
    },
    "night_flag": {
        "label": "Night Incident Indicator",
        "category": "Temporal Pattern",
        "provenance_type": "DIRECT_INTAKE",
        "unit": "flag",
        "honest_description": "Binary indicator whether incident occurred during nighttime hours (22:00–06:00)."
    },
    "complaint_delay_minutes": {
        "label": "Incident-to-Report Intake Delay",
        "category": "Temporal Pattern",
        "provenance_type": "DIRECT_INTAKE",
        "unit": "minutes",
        "honest_description": "Time elapsed between incident occurrence and formal complaint intake registration."
    },
    "transaction_count": {
        "label": "Transaction Hop Count in Layering Chain",
        "category": "Transaction Trail",
        "provenance_type": "DERIVED_TRANSFER",
        "unit": "transactions",
        "honest_description": "Number of recorded inter-account transfer steps in transaction trail."
    },
    "hop_count": {
        "label": "Layering Hop Depth",
        "category": "Transaction Trail",
        "provenance_type": "DERIVED_TRANSFER",
        "unit": "hops",
        "honest_description": "Count of recorded inter-account transfer steps from victim account to destination recipient account."
    },
    "unique_accounts": {
        "label": "Unique Intermediary Accounts",
        "category": "Transaction Trail",
        "provenance_type": "DERIVED_TRANSFER",
        "unit": "accounts",
        "honest_description": "Count of distinct bank or fintech recipient accounts in transaction path."
    },
    "unique_banks": {
        "label": "Unique Banking Institutions",
        "category": "Transaction Trail",
        "provenance_type": "DERIVED_TRANSFER",
        "unit": "banks",
        "honest_description": "Count of distinct banking institutions involved across transfer hops."
    },
    "total_transferred": {
        "label": "Total Layered Fraud Volume",
        "category": "Financial Flow",
        "provenance_type": "DERIVED_TRANSFER",
        "unit": "₹",
        "honest_description": "Aggregate monetary sum transferred across identified layering hops."
    },
    "mean_transfer_amount": {
        "label": "Average Layering Transfer Amount",
        "category": "Financial Flow",
        "provenance_type": "DERIVED_TRANSFER",
        "unit": "₹",
        "honest_description": "Mean monetary value per observed transfer hop."
    },
    "max_transfer_amount": {
        "label": "Maximum Single Transfer Amount",
        "category": "Financial Flow",
        "provenance_type": "DERIVED_TRANSFER",
        "unit": "₹",
        "honest_description": "Peak monetary transfer amount observed across hops."
    },
    "transaction_velocity": {
        "label": "Transaction Layering Velocity",
        "category": "Financial Flow",
        "provenance_type": "DERIVED_TRANSFER",
        "unit": "₹/min",
        "honest_description": "Rate of financial movement through identified transfer hops."
    },
    "chain_duration_minutes": {
        "label": "Transaction Chain Duration",
        "category": "Temporal Pattern",
        "provenance_type": "DERIVED_TRANSFER",
        "unit": "minutes",
        "honest_description": "Total elapsed time across observed transaction transfer hops."
    },
    "average_hop_interval": {
        "label": "Average Inter-Hop Interval",
        "category": "Temporal Pattern",
        "provenance_type": "DERIVED_TRANSFER",
        "unit": "minutes",
        "honest_description": "Mean duration elapsed between consecutive transaction hops."
    },
    "branching_factor": {
        "label": "Network Branching Factor",
        "category": "Network Topology",
        "provenance_type": "DERIVED_TRANSFER",
        "unit": "ratio",
        "honest_description": "Ratio of output transaction splits to incoming accounts in transfer graph."
    },
    "max_degree": {
        "label": "Peak Account Connection Degree",
        "category": "Network Topology",
        "provenance_type": "DERIVED_TRANSFER",
        "unit": "connections",
        "honest_description": "Maximum in/out transaction degree observed among linked accounts in transaction graph."
    },
    "mean_degree": {
        "label": "Average Account Connection Degree",
        "category": "Network Topology",
        "provenance_type": "DERIVED_TRANSFER",
        "unit": "connections",
        "honest_description": "Mean degree across all accounts in linked transaction subgraph."
    },
    "max_pagerank": {
        "label": "Peak Account Subgraph PageRank Centrality",
        "category": "Network Topology",
        "provenance_type": "DERIVED_TRANSFER",
        "unit": "centrality",
        "honest_description": "Highest PageRank centrality score among linked accounts in transaction graph."
    },
    "max_betweenness": {
        "label": "Peak Account Subgraph Betweenness Centrality",
        "category": "Network Topology",
        "provenance_type": "DERIVED_TRANSFER",
        "unit": "centrality",
        "honest_description": "Highest betweenness centrality score among linked accounts in transaction graph."
    },
    "connected_component_size": {
        "label": "Connected Transfer Subgraph Size",
        "category": "Network Topology",
        "provenance_type": "DERIVED_TRANSFER",
        "unit": "accounts",
        "honest_description": "Total count of accounts in connected transfer component of transaction graph."
    },
    "fraud_neighbor_count": {
        "label": "Flagged Fraud Neighbor Accounts",
        "category": "Network Topology",
        "provenance_type": "DERIVED_TRANSFER",
        "unit": "accounts",
        "honest_description": "Count of neighboring accounts previously flagged in suspect transaction reports."
    },
    "mule_connection_count": {
        "label": "Flagged Recipient Account Connections",
        "category": "Network Topology",
        "provenance_type": "DERIVED_TRANSFER",
        "unit": "connections",
        "honest_description": "Count of links to accounts previously flagged in suspect recipient clusters (heuristic indicator, not judicial confirmation)."
    },
    "historical_cluster_cashout_count": {
        "label": "Historical Cluster Baseline Cash-Out Frequency",
        "category": "Syndicate History",
        "provenance_type": "SYNTHETIC_HISTORICAL_BASELINE",
        "unit": "incidents",
        "honest_description": "Synthetic baseline frequency of cash-out events associated with this cluster in model training data (not verified real-world incidents)."
    },
    "historical_cluster_cashout_amount": {
        "label": "Historical Cluster Baseline Cash-Out Volume",
        "category": "Syndicate History",
        "provenance_type": "SYNTHETIC_HISTORICAL_BASELINE",
        "unit": "₹",
        "honest_description": "Synthetic baseline monetary volume cashed out in this cluster in training corpus."
    },
    "historical_cluster_risk": {
        "label": "Historical Cash-Out Cluster Risk Prior",
        "category": "Syndicate History",
        "provenance_type": "SYNTHETIC_HISTORICAL_BASELINE",
        "unit": "prior risk score",
        "honest_description": "Empirical historical risk prior for this location cluster in training corpus."
    },
    "atm_density": {
        "label": "Local Commercial ATM Density",
        "category": "Infrastructure",
        "provenance_type": "SPATIAL_DERIVED",
        "unit": "ATMs/zone",
        "honest_description": "Count of registered commercial ATM kiosks in candidate cluster zone."
    },
    "distance_from_victim": {
        "label": "Distance from Complaint Origin",
        "category": "Spatial Corridor",
        "provenance_type": "SPATIAL_DERIVED",
        "unit": "km",
        "honest_description": "Haversine distance from reported victim location to candidate cluster centroid."
    },
    "recent_cluster_activity": {
        "label": "Recent 7-Day Cluster Activity",
        "category": "Syndicate History",
        "provenance_type": "SYNTHETIC_HISTORICAL_BASELINE",
        "unit": "incidents",
        "honest_description": "Derived count of synthetic scenario incidents or recorded complaints linked to this cluster in previous 7 days."
    },
    "fraud_type_cluster_frequency": {
        "label": "Cluster Frequency for Fraud Modus Operandi",
        "category": "Syndicate History",
        "provenance_type": "SYNTHETIC_HISTORICAL_BASELINE",
        "unit": "incidents",
        "honest_description": "Historical synthetic baseline frequency of same-category fraud cash-outs in this cluster."
    },
    "transaction_hour": {
        "label": "Hour of Primary Transaction",
        "category": "Temporal Pattern",
        "provenance_type": "DERIVED_TRANSFER",
        "unit": "hour (0–23)",
        "honest_description": "Clock hour when primary fraudulent transfer was initiated."
    },
    "time_since_first_transfer": {
        "label": "Time Elapsed Since First Transfer",
        "category": "Temporal Pattern",
        "provenance_type": "DERIVED_TRANSFER",
        "unit": "minutes",
        "honest_description": "Minutes elapsed between initial victim transfer and prediction."
    },
    "time_since_last_transfer": {
        "label": "Time Elapsed Since Last Transfer",
        "category": "Temporal Pattern",
        "provenance_type": "DERIVED_TRANSFER",
        "unit": "minutes",
        "honest_description": "Minutes elapsed between terminal account transfer and prediction."
    },
    "fraud_type_historical_cashout_delay": {
        "label": "Historical Delay for Fraud Type",
        "category": "Syndicate History",
        "provenance_type": "SYNTHETIC_HISTORICAL_BASELINE",
        "unit": "minutes",
        "honest_description": "Mean historical synthetic delay from fraud execution to withdrawal for this fraud type."
    },
    "account_historical_cashout_delay": {
        "label": "Historical Delay for Recipient Account",
        "category": "Syndicate History",
        "provenance_type": "SYNTHETIC_HISTORICAL_BASELINE",
        "unit": "minutes",
        "honest_description": "Mean historical synthetic delay from transfer to cash-out for linked terminal account."
    },
    "candidate_same_complaint_zone": {
        "label": "Candidate Matches Complaint Origin Zone",
        "category": "Spatial Corridor",
        "provenance_type": "SPATIAL_DERIVED",
        "unit": "flag",
        "honest_description": "Binary indicator whether candidate cluster is located in victim's district."
    },
    "candidate_same_terminal_zone": {
        "label": "Candidate Matches Terminal Account Zone",
        "category": "Spatial Corridor",
        "provenance_type": "SPATIAL_DERIVED",
        "unit": "flag",
        "honest_description": "Binary indicator whether candidate cluster matches jurisdiction of terminal recipient account."
    },
    "candidate_same_any_account_zone": {
        "label": "Candidate Matches Any Transfer Account Zone",
        "category": "Spatial Corridor",
        "provenance_type": "SPATIAL_DERIVED",
        "unit": "flag",
        "honest_description": "Binary indicator whether candidate cluster matches jurisdiction of any intermediate account in chain."
    },
    "dist_to_complaint_zone_km": {
        "label": "Distance to Complaint Jurisdiction Centroid",
        "category": "Spatial Corridor",
        "provenance_type": "SPATIAL_DERIVED",
        "unit": "km",
        "honest_description": "Haversine distance from candidate cluster to centroid of complaint reporting district."
    },
    "dist_to_terminal_zone_km": {
        "label": "Distance to Terminal Account Zone Centroid",
        "category": "Spatial Corridor",
        "provenance_type": "SPATIAL_DERIVED",
        "unit": "km",
        "honest_description": "Haversine distance from candidate cluster to centroid of terminal recipient account district."
    },
    "dist_to_terminal_centroid_km": {
        "label": "Distance to Terminal Account Zone Centroid",
        "category": "Spatial Corridor",
        "provenance_type": "SPATIAL_DERIVED",
        "unit": "km",
        "honest_description": "Continuous Haversine distance from candidate cluster centroid to the centroid of the terminal recipient account's district."
    },
    "log_cluster_network_exposure": {
        "label": "Risk-Weighted Historical Exposure",
        "category": "Syndicate History",
        "provenance_type": "SYNTHETIC_HISTORICAL_BASELINE",
        "unit": "log exposure",
        "honest_description": "Logarithm of risk-weighted historical cash-out volume and incident count for this cluster in baseline data."
    },
    "cluster_fraud_type_match_score": {
        "label": "Fraud-Type Cluster Co-occurrence Affinity",
        "category": "Syndicate History",
        "provenance_type": "SYNTHETIC_HISTORICAL_BASELINE",
        "unit": "affinity score",
        "honest_description": "Historical affinity score between the reported fraud modus operandi and this location cluster."
    },
    "cluster_channel_match_score": {
        "label": "Payment Channel Cluster Co-occurrence",
        "category": "Financial Flow",
        "provenance_type": "SYNTHETIC_HISTORICAL_BASELINE",
        "unit": "affinity score",
        "honest_description": "Historical co-occurrence score between the payment channel (UPI, IMPS, etc.) and cash-out activity in this cluster."
    },
    "cluster_hourly_match_score": {
        "label": "Hour-of-Day Cluster Cash-Out Affinity",
        "category": "Temporal Pattern",
        "provenance_type": "SYNTHETIC_HISTORICAL_BASELINE",
        "unit": "affinity score",
        "honest_description": "Estimated temporal probability of cash-out occurring in this cluster during this clock hour."
    },
    "cluster_weekday_match_score": {
        "label": "Weekday-Class Cluster Cash-Out Affinity",
        "category": "Temporal Pattern",
        "provenance_type": "SYNTHETIC_HISTORICAL_BASELINE",
        "unit": "affinity score",
        "honest_description": "Estimated temporal probability of cash-out in this cluster for this day of the week."
    },
    "atm_density_log": {
        "label": "Log Commercial ATM Density",
        "category": "Infrastructure",
        "provenance_type": "SPATIAL_DERIVED",
        "unit": "log(ATMs)",
        "honest_description": "Logarithm of commercial ATM kiosks in candidate cluster zone."
    },
    "cluster_risk_x_count": {
        "label": "Cluster Risk-Volume Composite Prior",
        "category": "Syndicate History",
        "provenance_type": "SYNTHETIC_HISTORICAL_BASELINE",
        "unit": "composite index",
        "honest_description": "Composite index of baseline historical cluster risk prior multiplied by log historical incident frequency."
    },
    "dist_to_second_account_zone_km": {
        "label": "Distance to Intermediary Account Zone Centroid",
        "category": "Spatial Corridor",
        "provenance_type": "SPATIAL_DERIVED",
        "unit": "km",
        "honest_description": "Continuous Haversine distance from candidate cluster centroid to the second-most-active intermediary transfer account jurisdiction."
    },
    "v4_candidate_score": {
        "label": "V4 Foundation Model Score Prior",
        "category": "Model Prior",
        "provenance_type": "MODEL_PRIOR",
        "unit": "score (0–1)",
        "honest_description": "Base candidate ranking score produced by V4 foundation XGBoost model. Represents algorithmic ranking prior, NOT direct transaction or physical evidence."
    },
    "v4_candidate_rank_normalized": {
        "label": "Normalized Candidate Rank Order",
        "category": "Model Prior",
        "provenance_type": "MODEL_PRIOR",
        "unit": "rank (0–1)",
        "honest_description": "Relative rank position of this candidate in V4 base candidate pool."
    },
    "v4_candidate_percentile": {
        "label": "Candidate Ranking Percentile",
        "category": "Model Prior",
        "provenance_type": "MODEL_PRIOR",
        "unit": "percentile",
        "honest_description": "Percentile ranking of this candidate in V4 base candidate pool."
    },
    "v4_score_gap_from_candidate1": {
        "label": "Score Margin Gap vs Top Candidate",
        "category": "Model Prior",
        "provenance_type": "MODEL_PRIOR",
        "unit": "score gap",
        "honest_description": "Score deficit of this candidate relative to highest-scoring candidate in V4 foundation prior."
    }
}

# Compatibility mapping
FEATURE_FRIENDLY_NAMES = {k: v["label"] for k, v in FEATURE_METADATA.items()}


def format_feature_value(feature_name: str, value: float) -> str:
    """Formats raw numerical feature values into clear, officer-readable strings with units."""
    if value is None or np.isnan(value):
        return "N/A"

    if feature_name in ("v4_candidate_score", "v4_score_gap_from_candidate1", "max_pagerank", "max_betweenness"):
        return f"{value:.4f}"
    elif feature_name == "v4_candidate_rank_normalized":
        return f"{value:.2f}"
    elif feature_name == "v4_candidate_percentile":
        return f"{value * 100:.1f}%"
    elif feature_name in ("distance_from_victim", "dist_to_terminal_zone_km", "dist_to_complaint_zone_km", "dist_to_terminal_centroid_km", "dist_to_second_account_zone_km"):
        return f"{value:.1f} km"
    elif feature_name in ("candidate_same_terminal_zone", "candidate_same_complaint_zone", "candidate_same_any_account_zone", "weekend_flag", "night_flag"):
        return "Yes" if value >= 0.5 else "No"
    elif feature_name in ("historical_cluster_risk", "log_cluster_network_exposure", "cluster_fraud_type_match_score", "cluster_channel_match_score", "cluster_hourly_match_score", "cluster_weekday_match_score", "atm_density_log", "cluster_risk_x_count"):
        return f"{value:.2f}"
    elif feature_name in ("total_transferred", "mean_transfer_amount", "max_transfer_amount", "historical_cluster_cashout_amount"):
        return f"₹{int(round(value)):,}"
    elif feature_name == "transaction_velocity":
        return f"₹{value:.0f}/min"
    elif feature_name in ("chain_duration_minutes", "complaint_delay_minutes", "average_hop_interval", "time_since_first_transfer", "time_since_last_transfer"):
        return f"{value:.1f} min"
    elif feature_name in ("atm_density",):
        return f"{int(round(value))} ATMs"
    elif feature_name in ("hop_count", "transaction_count", "unique_accounts", "unique_banks", "connected_component_size", "mule_connection_count", "historical_cluster_cashout_count", "recent_cluster_activity", "fraud_type_cluster_frequency", "fraud_neighbor_count"):
        return f"{int(round(value))}"
    elif feature_name in ("complaint_hour", "transaction_hour"):
        return f"{int(round(value)):02d}:00 hrs"
    else:
        return f"{value:.2f}"


def sanitize_error(err: Optional[str]) -> str:
    """Sanitizes internal system paths, secrets, or raw tracebacks from user-facing error messages."""
    if not err:
        return "An unknown error occurred."
    cleaned = re.sub(r"[a-zA-Z]:\\[^\s:]+", "<internal_path>", str(err))
    cleaned = re.sub(r"/(?:[a-zA-Z0-9_-]+/)+[a-zA-Z0-9_.-]+", "<internal_path>", cleaned)
    cleaned = re.sub(r"Traceback.*", "", cleaned, flags=re.DOTALL)
    if len(cleaned) > 160:
        cleaned = cleaned[:157] + "..."
    return cleaned.strip()


def compute_snapshot_digest(snap_dict: Optional[Dict[str, Any]]) -> str:
    """
    Computes a canonical SHA-256 digest of an inference snapshot dictionary.
    Ensures key sorting and normalized separators for deterministic hashing.
    """
    if not isinstance(snap_dict, dict):
        return ""
    canonical_json = json.dumps(snap_dict, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class PredictionExplainabilityService:
    """
    Production LIME Explainability Service supporting verified official models:
    - cashout-location-xgb-v8-debiased (49 causal money network features, 0 victim features)
    - cashout-location-xgb-v7-compat (47 legacy compat features)

    Uses tabular candidate-level surrogate linear models grounded strictly
    in immutable prediction snapshots.
    """

    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        self._explainers: Dict[str, Any] = {}
        self._background_matrices: Dict[str, np.ndarray] = {}
        self._background_metadatas: Dict[str, Dict[str, Any]] = {}
        self._feature_schemas: Dict[str, List[str]] = {}
        self._models: Dict[str, Any] = {}
        self._calibrators: Dict[str, Any] = {}
        self._init_errors: Dict[str, str] = {}

    @property
    def _init_error(self) -> Optional[str]:
        return self._init_errors.get("v8_debiased") or self._init_errors.get("v7_compat") or (next(iter(self._init_errors.values())) if self._init_errors else None)

    @property
    def is_initialized(self) -> bool:
        return bool(self._explainers)

    @is_initialized.setter
    def is_initialized(self, val: bool) -> None:
        if not val:
            self._explainers.clear()

    @property
    def explainer(self) -> Any:
        # Default / active explainer (prefer v8 if loaded, else v7)
        if "v8_debiased" in self._explainers:
            return self._explainers["v8_debiased"]
        return self._explainers.get("v7_compat")

    @property
    def background_matrix(self) -> Optional[np.ndarray]:
        if "v8_debiased" in self._background_matrices:
            return self._background_matrices["v8_debiased"]
        if "v7_compat" in self._background_matrices:
            return self._background_matrices["v7_compat"]
        return None

    @property
    def background_metadata(self) -> Dict[str, Any]:
        return self._background_metadatas.get("v8_debiased") or self._background_metadatas.get("v7_compat") or {}

    @property
    def feature_names(self) -> List[str]:
        return self._feature_schemas.get("v8_debiased") or self._feature_schemas.get("v7_compat") or []

    @property
    def explainer_version(self) -> str:
        if "v8_debiased" in self._explainers:
            return "lime_tabular_v8_debiased"
        return "lime_tabular_0.2.0.1"

    @property
    def feature_schema_version(self) -> str:
        if "v8_debiased" in self._explainers:
            return "v8_debiased"
        return "v7_compat"

    def _normalize_model_key(self, model_version: Optional[str]) -> Optional[str]:
        if not model_version:
            return None
        m_str = str(model_version).lower().strip()
        if "v8" in m_str or "debiased" in m_str:
            return "v8_debiased"
        elif "v7" in m_str or "compat" in m_str:
            return "v7_compat"
        return None

    def _ensure_initialized_for_model(self, model_version: str) -> bool:
        """Lazy-loads model artifacts, background matrix, and LimeTabularExplainer for specified model."""
        key = self._normalize_model_key(model_version)
        if not key:
            self._init_errors[str(model_version)] = f"Unsupported model version '{model_version}' for LIME explainability."
            return False

        if key in self._explainers and self._explainers[key] is not None:
            return True

        try:
            from lime.lime_tabular import LimeTabularExplainer
            import joblib
            artifacts_dir = resolve_artifacts_dir()

            if key == "v8_debiased":
                from ml.features.feature_pipeline import FEATURE_COLUMNS_LOCATION_V8_DEBIASED

                bg_path = os.path.join(artifacts_dir, "v8_lime_background.npy")
                bg_meta_path = os.path.join(artifacts_dir, "v8_lime_background_metadata.json")
                ranker_path = os.path.join(artifacts_dir, "location_ranker_v8_debiased.joblib")
                calibrator_path = os.path.join(artifacts_dir, "location_calibrator_v8_debiased.joblib")

                if not os.path.exists(bg_path):
                    err = "V8 background matrix artifact 'v8_lime_background.npy' not found."
                    self._init_errors[key] = err
                    logger.error(err)
                    return False

                if not os.path.exists(ranker_path) or not os.path.exists(calibrator_path):
                    err = "V8 ranker or calibrator artifact not found in artifacts directory."
                    self._init_errors[key] = err
                    logger.error(err)
                    return False

                raw_bg = np.load(bg_path)
                if raw_bg.shape[1] != 49:
                    err = f"V8 background matrix has {raw_bg.shape[1]} columns, expected exactly 49."
                    self._init_errors[key] = err
                    logger.error(err)
                    return False

                bg_clean = np.nan_to_num(raw_bg, nan=0.0)
                feature_names = list(FEATURE_COLUMNS_LOCATION_V8_DEBIASED)
                assert len(feature_names) == 49, f"Expected 49 V8 features, got {len(feature_names)}"

                # Verify 0 forbidden victim-origin features and 0 V4 stack features
                for f in feature_names:
                    if f in V8_FORBIDDEN_FEATURES:
                        raise ValueError(f"Forbidden feature '{f}' detected in V8 LIME feature schema.")

                # Categorical / binary feature indices in 49-feature schema
                cat_names = [
                    "fraud_type_encoded", "payment_channel_encoded", "weekend_flag",
                    "night_flag", "candidate_same_terminal_zone", "candidate_same_any_account_zone"
                ]
                categorical_features = [feature_names.index(c) for c in cat_names if c in feature_names]

                ranker = joblib.load(ranker_path)
                calibrator = joblib.load(calibrator_path)

                explainer = LimeTabularExplainer(
                    training_data=bg_clean,
                    feature_names=feature_names,
                    categorical_features=categorical_features,
                    mode="regression",
                    random_state=self.random_state
                )

                bg_metadata = {}
                if os.path.exists(bg_meta_path):
                    try:
                        with open(bg_meta_path, "r", encoding="utf-8") as f:
                            bg_metadata = json.load(f)
                        expected_hash = bg_metadata.get("sha256_npy")
                        if expected_hash:
                            actual_hash = compute_file_sha256(bg_path)
                            if actual_hash != expected_hash:
                                err = "Background matrix SHA-256 integrity check failed for v8_debiased."
                                self._init_errors[key] = err
                                logger.error(err)
                                return False
                    except Exception as meta_e:
                        if "Background matrix SHA-256 integrity check failed" in str(meta_e):
                            raise
                        logger.warning("Could not read v8_lime_background_metadata.json: %s", meta_e)
                else:
                    bg_metadata = {
                        "background_sample_size": len(bg_clean),
                        "feature_count": 49,
                        "feature_schema_version": "v8_debiased",
                        "seed": 56100
                    }

                self._background_matrices[key] = bg_clean
                self._background_metadatas[key] = bg_metadata
                self._feature_schemas[key] = feature_names
                self._models[key] = ranker
                self._calibrators[key] = calibrator
                self._explainers[key] = explainer

                logger.info("Successfully initialized V8 LIME explainer with %d background rows and 49 features", len(bg_clean))
                return True

            elif key == "v7_compat":
                from ml.features.feature_pipeline import FEATURE_COLUMNS_LOCATION_V3_1

                bg_path = os.path.join(artifacts_dir, "v7_lime_background.npy")
                bg_meta_path = os.path.join(artifacts_dir, "v7_lime_background_metadata.json")
                ranker_path = os.path.join(artifacts_dir, "location_ranker_v7_compat.joblib")
                calibrator_path = os.path.join(artifacts_dir, "location_calibrator_v7_compat.joblib")

                if not os.path.exists(bg_path):
                    err = "V7 background matrix artifact 'v7_lime_background.npy' not found."
                    self._init_errors[key] = err
                    logger.error(err)
                    return False

                raw_bg = np.load(bg_path)
                if raw_bg.shape[1] != 47:
                    err = f"V7 background matrix has {raw_bg.shape[1]} columns, expected 47."
                    self._init_errors[key] = err
                    logger.error(err)
                    return False

                bg_clean = np.nan_to_num(raw_bg, nan=0.0)
                feature_names = FEATURE_COLUMNS_LOCATION_V3_1 + V4_COMPAT_FEATURES
                categorical_features = [1, 2, 5, 6, 38, 39, 40]

                ranker = joblib.load(ranker_path) if os.path.exists(ranker_path) else getattr(prediction_service.ml_provider, "location_model", None)
                calibrator = joblib.load(calibrator_path) if os.path.exists(calibrator_path) else getattr(prediction_service.ml_provider, "calibrator", None)

                explainer = LimeTabularExplainer(
                    training_data=bg_clean,
                    feature_names=feature_names,
                    categorical_features=categorical_features,
                    mode="regression",
                    random_state=self.random_state
                )

                bg_metadata = {}
                if os.path.exists(bg_meta_path):
                    try:
                        with open(bg_meta_path, "r", encoding="utf-8") as f:
                            bg_metadata = json.load(f)
                        expected_hash = bg_metadata.get("sha256_npy")
                        if expected_hash:
                            actual_hash = compute_file_sha256(bg_path)
                            if actual_hash != expected_hash:
                                err = "Background matrix SHA-256 integrity check failed for v7_compat."
                                self._init_errors[key] = err
                                logger.error(err)
                                return False
                    except Exception as meta_e:
                        if "Background matrix SHA-256 integrity check failed" in str(meta_e):
                            raise
                        logger.warning("Could not read v7_lime_background_metadata.json: %s", meta_e)

                self._background_matrices[key] = bg_clean
                self._background_metadatas[key] = bg_metadata
                self._feature_schemas[key] = feature_names
                self._models[key] = ranker
                self._calibrators[key] = calibrator
                self._explainers[key] = explainer

                logger.info("Successfully initialized V7 LIME explainer with %d background rows and 47 features", len(bg_clean))
                return True

            return False
        except Exception as e:
            err = f"Explainer initialization failed for {key}: {sanitize_error(str(e))}"
            self._init_errors[key] = err
            logger.exception("Failed to initialize LIME explainer for %s: %s", key, e)
            return False

    def _ensure_initialized(self) -> bool:
        """Backward-compatible initializer: ensures active runtime model explainer is loaded."""
        mlp = getattr(prediction_service, "ml_provider", None)
        active_ver = getattr(mlp, "model_version", "cashout-location-xgb-v8-debiased") if mlp else "cashout-location-xgb-v8-debiased"
        return self._ensure_initialized_for_model(active_ver) or self._ensure_initialized_for_model("v7_compat")

    @staticmethod
    def classify_fidelity(r2_score: float, abs_error: float) -> str:
        """
        Conservative fidelity classification for local surrogate LIME explanations:
        - R² >= 0.70 (and |err| <= 0.15): HIGH_FIDELITY
        - 0.40 <= R² < 0.70 (and |err| <= 0.25): MODERATE_FIDELITY
        - R² < 0.40 or |err| > 0.25: LOW_FIDELITY

        Absolute approximation error is retained as a separate diagnostic.
        Negative R² is classified truthfully as LOW_FIDELITY.
        """
        if r2_score >= 0.70 and abs_error <= 0.15:
            return "HIGH_FIDELITY"
        elif r2_score >= 0.40 and abs_error <= 0.25:
            return "MODERATE_FIDELITY"
        else:
            return "LOW_FIDELITY"

    def build_candidate_features_for_complaint(self, db, complaint, candidate_cluster_ids=None):
        """
        Maintained for backward compatibility and test error injection hooks.
        For snapshot-grounded explanations, features are retrieved directly from snapshot.
        """
        return {}

    def _apply_conservative_fidelity_classification(self, exp_payload: Dict[str, Any]) -> None:
        """Applies conservative fidelity rules across candidate and overall levels."""
        top3 = exp_payload.get("top3_explanations", [])
        if not top3:
            return

        any_low = False
        any_mod = False
        r2_vals = []
        for cand in top3:
            r2 = float(cand.get("local_fidelity_r2", 0.0) or 0.0)
            err = float(cand.get("absolute_approximation_error", 0.0) or 0.0)
            status = self.classify_fidelity(r2, err)
            cand["fidelity_status"] = status
            r2_vals.append(r2)
            if status == "LOW_FIDELITY":
                any_low = True
            elif status == "MODERATE_FIDELITY":
                any_mod = True

        mean_r2 = float(np.mean(r2_vals)) if r2_vals else 0.0
        exp_payload["mean_local_fidelity_r2"] = round(mean_r2, 4)

        if any_low or mean_r2 < 0.40:
            overall = "LOW_FIDELITY"
            exp_status = "LOW_FIDELITY"
        elif any_mod or mean_r2 < 0.70:
            overall = "MODERATE_FIDELITY"
            exp_status = "AVAILABLE"
        else:
            overall = "HIGH_FIDELITY"
            exp_status = "AVAILABLE"

        exp_payload["overall_fidelity_status"] = overall
        exp_payload["explanation_status"] = exp_status

    def explain_candidate(
        self,
        candidate_vector: np.ndarray,
        rank: int,
        cluster_id: int,
        location_name: str,
        official_score: float,
        model_version: Optional[str] = None,
        num_features: int = 8,
        num_samples: int = 1000
    ) -> Dict[str, Any]:
        """
        Explains an individual candidate location prediction using tabular LIME.
        Deterministic through local per-call RNG without mutating global np.random.
        Applies version-aware model dispatch and exact runtime feature schemas.
        """
        if model_version is None:
            if len(candidate_vector) == 47:
                model_version = "cashout-location-xgb-v7-compat"
            else:
                model_version = "cashout-location-xgb-v8-debiased"

        key = self._normalize_model_key(model_version)
        if not key or not self._ensure_initialized_for_model(model_version):
            raise RuntimeError(self._init_errors.get(key or str(model_version), f"Explainer initialization failed for {model_version}"))

        explainer = self._explainers[key]
        feature_names = self._feature_schemas[key]
        ranker = self._models[key]
        calibrator = self._calibrators[key]

        def predict_fn(X: np.ndarray) -> np.ndarray:
            clean_X = np.nan_to_num(X, nan=0.0)
            raw = ranker.predict(clean_X)
            return calibrator.predict_proba(raw.reshape(-1, 1))[:, 1]

        # Use independent seeded RNG per rank call for thread-safe determinism
        local_rng = np.random.RandomState(self.random_state + rank)
        explainer.random_state = local_rng
        if hasattr(explainer, "discretizer") and explainer.discretizer:
            explainer.discretizer.random_state = local_rng

        clean_row = np.nan_to_num(candidate_vector, nan=0.0)
        exp = explainer.explain_instance(
            data_row=clean_row,
            predict_fn=predict_fn,
            num_features=num_features,
            num_samples=num_samples
        )

        local_pred = float(exp.local_pred[0]) if hasattr(exp.local_pred, "__getitem__") else float(exp.local_pred)
        r2_score = float(exp.score) if exp.score is not None and not np.isnan(exp.score) else 0.0
        abs_error = abs(float(official_score) - local_pred)

        fidelity_status = self.classify_fidelity(r2_score, abs_error)

        map_items = exp.as_map().get(1, exp.as_map().get(0, []))
        total_w = sum(abs(float(w)) for _, w in map_items) or 1.0

        pos_contribs = []
        neg_contribs = []

        for feat_idx, weight in map_items:
            f_idx = int(feat_idx)
            if f_idx < 0 or f_idx >= len(feature_names):
                continue
            fname = feature_names[f_idx]
            fval = float(clean_row[f_idx])
            w = float(weight)

            meta = FEATURE_METADATA.get(fname, {})
            friendly = meta.get("label", fname.replace("_", " ").title())
            cat = meta.get("category", "General Signal")
            prov_type = meta.get("provenance_type", "DERIVED_TRANSFER")
            honest_desc = meta.get("honest_description", f"Factor attribution for {friendly}.")
            val_formatted = format_feature_value(fname, fval)

            # Match rule string from as_list
            rule_str = ""
            for r_str, _ in exp.as_list():
                if fname in r_str or f"f_{f_idx}" in r_str:
                    rule_str = r_str.replace(f"f_{f_idx}", fname)
                    break
            if not rule_str:
                rule_str = f"{fname} = {fval:.2f}"

            share = round((abs(w) / total_w) * 100, 1)

            contrib_payload = {
                "feature_name": fname,
                "friendly_label": friendly,
                "category": cat,
                "provenance_type": prov_type,
                "rule": rule_str,
                "weight": round(w, 4),
                "raw_weight": round(w, 6),
                "feature_value": round(fval, 4),
                "formatted_value": val_formatted,
                "share_denominator_formula": r"\sum_{k \in \text{TopFactors}} |w_k|",
                "share_denominator_note": "Surrogate linear weight fraction (|w_i| / sum(|w_k|)). Represents local surrogate attribution magnitude, NOT real-world withdrawal probability or causal percentage.",
                "honest_explanation": honest_desc
            }

            if w >= 0:
                contrib_payload["direction"] = "SUPPORTING"
                contrib_payload["contribution_share"] = share
                contrib_payload["description"] = (
                    f"Factors that locally increased this candidate's ranking priority include {friendly} "
                    f"({val_formatted}; local rule: {rule_str})."
                )
                pos_contribs.append(contrib_payload)
            else:
                contrib_payload["direction"] = "OPPOSING"
                contrib_payload["contribution_share"] = -share
                contrib_payload["description"] = (
                    f"Factors that locally decreased this candidate's ranking priority include {friendly} "
                    f"({val_formatted}; local rule: {rule_str})."
                )
                neg_contribs.append(contrib_payload)

        # Ground dynamic summary in actual top factors
        top_pos = pos_contribs[0] if pos_contribs else None
        top_neg = neg_contribs[0] if neg_contribs else None

        summary_parts = [
            f"Candidate '{location_name}' (Rank #{rank}) has an official model score of {official_score * 100:.1f}%."
        ]
        if top_pos:
            summary_parts.append(
                f"Primary supporting local factor: {top_pos['friendly_label']} ({top_pos['formatted_value']}, attribution weight {top_pos['weight']:+.4f})."
            )
        if top_neg:
            summary_parts.append(
                f"Primary down-weighting local factor: {top_neg['friendly_label']} ({top_neg['formatted_value']}, attribution weight {top_neg['weight']:+.4f})."
            )
        summary_parts.append(
            f"Local surrogate fit achieved R² = {r2_score:.4f} ({fidelity_status.replace('_', ' ')})."
        )
        summary_statement = " ".join(summary_parts)

        return {
            "rank": rank,
            "cluster_id": cluster_id,
            "location_name": location_name,
            "official_score": round(float(official_score), 4),
            "lime_local_prediction": round(local_pred, 4),
            "absolute_approximation_error": round(abs_error, 4),
            "local_fidelity_r2": round(r2_score, 4),
            "fidelity_status": fidelity_status,
            "positive_contributions": pos_contribs,
            "negative_contributions": neg_contribs,
            "summary_statement": summary_statement
        }

    def get_or_generate_explanation(
        self,
        db: Session,
        prediction_id: int
    ) -> Dict[str, Any]:
        """
        Retrieves or generates LIME explainability for official V8 or V7 predictions using
        faithful inference snapshot provenance.

        Guaranteed:
        - Never creates/recomputes Predictions on GET.
        - Never modifies PredictionLocation or Alert rows.
        - Never reconstructs features from live database for historical complaints.
        - Returns appropriate status: AVAILABLE, LOW_FIDELITY, UNAVAILABLE, or NOT_FOUND.
        - Supports version-aware dispatch for V8 debiased (49 features) and V7 compat (47 features).
        """
        prediction = db.query(Prediction).filter(Prediction.id == prediction_id).first()
        if not prediction:
            return {
                "explanation_status": "NOT_FOUND",
                "prediction_id": prediction_id,
                "complaint_number": "UNKNOWN",
                "prediction_mode": "unavailable",
                "model_version": "unavailable",
                "message": f"Prediction #{prediction_id} not found in database.",
                "actionable_next_step": "Verify the prediction ID or generate a new prediction for this case."
            }

        complaint = db.query(Complaint).filter(Complaint.id == prediction.complaint_id).first()
        c_num = complaint.complaint_number if complaint else f"CMP-{prediction.complaint_id}"

        # 1. Deterministic Demo Route: Return explicit demo disclaimer without pretending LIME fit
        if prediction.prediction_mode == "deterministic_demo":
            demo_exp = prediction_service.get_explanation(prediction, complaint) if hasattr(prediction_service, "get_explanation") else {}
            return {
                "explanation_status": "AVAILABLE",
                "prediction_id": prediction.id,
                "complaint_number": c_num,
                "prediction_mode": "deterministic_demo",
                "model_version": prediction.model_version,
                "explanation_method": "DEMO_HEURISTIC",
                "explainer_version": "demo_provider_v1",
                "feature_schema_version": "demo_fixtures",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "overall_fidelity_status": "NOT_EVALUATED",
                "mean_local_fidelity_r2": None,
                "background_sample_size": None,
                "background_seed": None,
                "top3_explanations": [],
                "factors": demo_exp.get("factors", []),
                "narrative": demo_exp.get(
                    "narrative",
                    "Deterministic demonstration prediction based on fixed scenario fixtures and geographic cluster rules."
                ),
                "disclaimer": (
                    f"{demo_exp.get('disclaimer', 'AI-generated decision support.')} "
                    "Demonstration prediction uses predetermined heuristics and is not generated by trained statistical models."
                ).strip()
            }

        # 2. Snapshot Authority and Consistency Resolution
        companion_snapshot = getattr(prediction, "snapshot", None)
        metadata_snapshot = (
            prediction.result_metadata.get("inference_snapshot")
            if (prediction.result_metadata and isinstance(prediction.result_metadata, dict))
            else None
        )

        snapshot = None
        snapshot_source = None
        snapshot_digest = None

        if companion_snapshot and companion_snapshot.snapshot_data:
            # Primary authoritative source: relational companion table
            snapshot = companion_snapshot.snapshot_data
            snapshot_source = "prediction_snapshots_table"
            snapshot_digest = compute_snapshot_digest(snapshot)

            # If duplicate copy exists in result_metadata, detect conflict
            if metadata_snapshot:
                meta_digest = compute_snapshot_digest(metadata_snapshot)
                if meta_digest != snapshot_digest:
                    logger.error(
                        "Snapshot conflict detected for Prediction #%d: companion table digest %s != metadata digest %s",
                        prediction.id, snapshot_digest, meta_digest
                    )
                    return {
                        "explanation_status": "UNAVAILABLE",
                        "prediction_id": prediction.id,
                        "complaint_number": c_num,
                        "prediction_mode": prediction.prediction_mode,
                        "model_version": prediction.model_version,
                        "location_model_version": prediction.model_version,
                        "integrity_conflict": True,
                        "snapshot_digest": snapshot_digest,
                        "snapshot_source": snapshot_source,
                        "message": (
                            f"Integrity conflict detected: Authoritative snapshot in 'prediction_snapshots' "
                            f"(digest {snapshot_digest[:12]}...) diverges from 'result_metadata.inference_snapshot' "
                            f"(digest {meta_digest[:12]}...). Refusing explanation due to possible tampering or uncoordinated update."
                        ),
                        "actionable_next_step": "Investigate database integrity or re-run prediction to record a unified snapshot.",
                        "disclaimer": "LIME explainability requires an authoritative, non-conflicting snapshot."
                    }
        elif metadata_snapshot:
            # Fallback source: metadata (e.g. pre-migration snapshot)
            snapshot = metadata_snapshot
            snapshot_source = "result_metadata_snapshot"
            snapshot_digest = compute_snapshot_digest(snapshot)

        # 3. Handle Legacy Predictions Without Faithful Snapshot
        if not snapshot or not isinstance(snapshot, dict):
            return {
                "explanation_status": "UNAVAILABLE",
                "prediction_id": prediction.id,
                "complaint_number": c_num,
                "prediction_mode": prediction.prediction_mode,
                "model_version": prediction.model_version,
                "location_model_version": prediction.model_version,
                "message": (
                    f"Historical prediction #{prediction.id} (Complaint {c_num}) lacks an immutable inference snapshot. "
                    f"CyberShield AI does not reconstruct feature inputs from current database state to prevent historical evidence drift."
                ),
                "actionable_next_step": "Generate a new prediction for this complaint to capture an immutable snapshot with full LIME explainability.",
                "is_legacy_prediction": True,
                "factors": [],
                "top3_explanations": [],
                "narrative": "Explanation unavailable: Historical prediction lacks an immutable inference feature snapshot.",
                "disclaimer": "LIME explainability requires an immutable snapshot captured at prediction time."
            }

        # 4. Model Version Dispatch & Feature Schema Validation
        snapshot_model = snapshot.get("model_version") or prediction.model_version
        model_key = self._normalize_model_key(snapshot_model)

        if not model_key:
            return {
                "explanation_status": "UNAVAILABLE",
                "prediction_id": prediction.id,
                "complaint_number": c_num,
                "prediction_mode": prediction.prediction_mode,
                "model_version": snapshot_model,
                "location_model_version": snapshot_model,
                "snapshot_digest": snapshot_digest,
                "snapshot_source": snapshot_source,
                "message": (
                    f"LIME tabular explanation is only calibrated for official verified models "
                    f"(cashout-location-xgb-v8-debiased, cashout-location-xgb-v7-compat). "
                    f"Snapshot model version is '{snapshot_model}'. Unsupported model version is refused."
                ),
                "actionable_next_step": "Model version is not supported by the LIME tabular explainer."
            }

        if not self._ensure_initialized_for_model(snapshot_model):
            return {
                "explanation_status": "UNAVAILABLE",
                "prediction_id": prediction.id,
                "complaint_number": c_num,
                "prediction_mode": prediction.prediction_mode,
                "model_version": snapshot_model,
                "location_model_version": snapshot_model,
                "message": f"LIME explainer engine unavailable for {snapshot_model}: {self._init_errors.get(model_key)}",
                "actionable_next_step": "Verify that LIME dependencies and background artifacts are present."
            }

        expected_schema = self._feature_schemas[model_key]
        expected_count = len(expected_schema)
        snapshot_features = snapshot.get("feature_names", [])

        if len(snapshot_features) != expected_count:
            return {
                "explanation_status": "UNAVAILABLE",
                "prediction_id": prediction.id,
                "complaint_number": c_num,
                "prediction_mode": prediction.prediction_mode,
                "model_version": snapshot_model,
                "location_model_version": snapshot_model,
                "snapshot_digest": snapshot_digest,
                "snapshot_source": snapshot_source,
                "message": f"Snapshot feature schema contains {len(snapshot_features)} features, expected exactly {expected_count} for {snapshot_model}.",
                "actionable_next_step": f"Ensure complaint feature schema is compatible with {snapshot_model}."
            }

        if list(snapshot_features) != list(expected_schema):
            return {
                "explanation_status": "UNAVAILABLE",
                "prediction_id": prediction.id,
                "complaint_number": c_num,
                "prediction_mode": prediction.prediction_mode,
                "model_version": snapshot_model,
                "location_model_version": snapshot_model,
                "snapshot_digest": snapshot_digest,
                "snapshot_source": snapshot_source,
                "message": f"Snapshot feature schema names do not match official {snapshot_model} feature schema.",
                "actionable_next_step": f"Ensure feature schema matches the {expected_count} official {snapshot_model} feature definitions."
            }

        # Verify calibrator artifact hash against canonical artifact hash
        snap_cal_hash = snapshot.get("calibrator_hash")
        if snap_cal_hash:
            artifacts_dir = resolve_artifacts_dir()
            cal_file = "location_calibrator_v8_debiased.joblib" if model_key == "v8_debiased" else "location_calibrator_v7_compat.joblib"
            cal_path = os.path.join(artifacts_dir, cal_file)
            if os.path.exists(cal_path):
                expected_cal_hash = compute_file_sha256(cal_path)
                if snap_cal_hash != expected_cal_hash:
                    return {
                        "explanation_status": "UNAVAILABLE",
                        "prediction_id": prediction.id,
                        "complaint_number": c_num,
                        "prediction_mode": prediction.prediction_mode,
                        "model_version": snapshot_model,
                        "location_model_version": snapshot_model,
                        "snapshot_digest": snapshot_digest,
                        "snapshot_source": snapshot_source,
                        "reason": "CALIBRATOR_HASH_MISMATCH",
                        "snapshot_calibrator_hash_prefix": snap_cal_hash[:16] + "...",
                        "runtime_calibrator_hash_prefix": expected_cal_hash[:16] + "...",
                        "message": (
                            f"Calibrator mismatch: This prediction was generated with a different calibrator artifact than the one currently "
                            f"loaded in the runtime. CyberShield does not generate explanations using mismatched "
                            f"artifacts — historical predictions remain tied to the exact model artifacts used at "
                            f"prediction time."
                        ),
                        "actionable_next_step": "Run a new V8 analysis for this complaint to generate a fresh prediction with full LIME explainability under the current runtime."
                    }

        # 5. Check Cache Identity (Snapshot Digest + Model Version + Explainer Configuration + Official Outputs)
        explainer_version_label = f"lime_tabular_{model_key}"
        schema_version_label = model_key

        cache_identity = hashlib.sha256(
            f"{prediction.id}:{snapshot_digest}:{snapshot_model}:{explainer_version_label}:{self.random_state}".encode("utf-8")
        ).hexdigest()

        cached_exp = (prediction.result_metadata or {}).get("explainability") if prediction.result_metadata else None
        if (
            isinstance(cached_exp, dict)
            and cached_exp.get("cache_identity") == cache_identity
            and cached_exp.get("snapshot_digest") == snapshot_digest
            and cached_exp.get("snapshot_provenance") is True
            and cached_exp.get("model_version") == snapshot_model
            and cached_exp.get("explanation_status") in ("AVAILABLE", "LOW_FIDELITY")
        ):
            # Validate candidate and official output correspondence in cache against persisted PredictionLocations
            persisted_locs = (
                db.query(PredictionLocation)
                .filter(PredictionLocation.prediction_id == prediction.id)
                .order_by(PredictionLocation.rank.asc())
                .all()
            )
            cached_top3 = cached_exp.get("top3_explanations", [])
            if (
                len(cached_top3) == len(persisted_locs[:3])
                and all(
                    c.get("cluster_id") == p.cluster_id
                    and abs(float(c.get("official_score", -999.0)) - float(p.probability)) < 1e-3
                    for c, p in zip(cached_top3, persisted_locs[:3])
                )
            ):
                return cached_exp

        # 6. Query persisted Top-3 PredictionLocations
        locations = (
            db.query(PredictionLocation)
            .filter(PredictionLocation.prediction_id == prediction.id)
            .order_by(PredictionLocation.rank.asc())
            .all()
        )
        if len(locations) < 3:
            return {
                "explanation_status": "UNAVAILABLE",
                "prediction_id": prediction.id,
                "complaint_number": c_num,
                "prediction_mode": prediction.prediction_mode,
                "model_version": prediction.model_version,
                "location_model_version": prediction.model_version,
                "message": "Persisted official prediction has fewer than 3 locations.",
                "actionable_next_step": "Regenerate prediction to yield full Top-3 location set."
            }

        top3_locs = locations[:3]
        candidate_features_map = snapshot.get("candidate_features", {})

        try:
            # Hook for testing exception isolation / feature build failures
            self.build_candidate_features_for_complaint(db, complaint)

            top3_exps = []
            for loc in top3_locs:
                cid_str = str(loc.cluster_id)
                if cid_str not in candidate_features_map:
                    return {
                        "explanation_status": "UNAVAILABLE",
                        "prediction_id": prediction.id,
                        "complaint_number": c_num,
                        "prediction_mode": prediction.prediction_mode,
                        "model_version": prediction.model_version,
                        "location_model_version": prediction.model_version,
                        "message": f"Cluster ID {loc.cluster_id} (Rank #{loc.rank}) not found in faithful inference snapshot.",
                        "actionable_next_step": "Generate a new prediction to record an updated snapshot."
                    }

                cand_vector = np.array(candidate_features_map[cid_str], dtype=float)
                cand_exp = self.explain_candidate(
                    candidate_vector=cand_vector,
                    rank=int(loc.rank),
                    cluster_id=int(loc.cluster_id),
                    location_name=str(loc.location_name),
                    official_score=float(loc.probability),
                    model_version=snapshot_model,
                    num_features=8,
                    num_samples=1000
                )
                top3_exps.append(cand_exp)

            # Backward-compatible factor list from Rank 1
            rank1_exp = top3_exps[0]
            compat_factors = []
            all_contribs = rank1_exp.get("positive_contributions", []) + rank1_exp.get("negative_contributions", [])
            total_w = sum(abs(c["weight"]) for c in all_contribs) or 1.0

            for c in sorted(all_contribs, key=lambda x: -abs(x["weight"]))[:5]:
                share = round((abs(c["weight"]) / total_w) * 100, 1)
                compat_factors.append({
                    "name": c["friendly_label"],
                    "feature_code": c["feature_name"],
                    "contribution_percentage": share,
                    "direction": c["direction"],
                    "description": c["description"]
                })

            bg_meta = self._background_metadatas.get(model_key, {})

            response_payload = {
                "explanation_status": "AVAILABLE",
                "prediction_id": prediction.id,
                "complaint_number": c_num,
                "prediction_mode": prediction.prediction_mode,
                "model_version": snapshot_model,
                "location_model_version": snapshot_model,
                "explanation_method": "LIME",
                "explainer_version": explainer_version_label,
                "feature_schema_version": schema_version_label,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "overall_fidelity_status": "LOW_FIDELITY",
                "mean_local_fidelity_r2": 0.0,
                "background_sample_size": int(bg_meta.get("background_sample_size", len(self._background_matrices.get(model_key, [])))),
                "background_seed": int(bg_meta.get("seed", 56100)),
                "top3_explanations": top3_exps,
                "factors": compat_factors,
                "narrative": "",
                "cache_identity": cache_identity,
                "snapshot_digest": snapshot_digest,
                "snapshot_source": snapshot_source,
                "snapshot_provenance": True,
                "disclaimer": (
                    "LIME provides local surrogate linear explanations of model decisions for risk prioritization. "
                    "This is an algorithmic approximation of local feature influence, not proof or causal evidence of criminal activity."
                )
            }

            self._apply_conservative_fidelity_classification(response_payload)

            mean_r2 = response_payload["mean_local_fidelity_r2"]
            overall_status = response_payload["overall_fidelity_status"]
            response_payload["narrative"] = (
                f"Prediction #{prediction.id} explained via {explainer_version_label} (LIME tabular) grounded in immutable snapshot. "
                f"Local surrogate fit achieved mean R² = {mean_r2:.4f} ({overall_status.replace('_', ' ')})."
            )

            # Safely cache into result_metadata without creating new rows or altering audit hash contract
            try:
                current_meta = dict(prediction.result_metadata or {})
                current_meta["explainability"] = response_payload
                prediction.result_metadata = current_meta
                db.commit()
            except Exception as e:
                db.rollback()
                logger.warning("Could not cache explainability into prediction result_metadata: %s", e)

            return response_payload

        except Exception as e:
            logger.exception("Unexpected error generating LIME explanation: %s", e)
            return {
                "explanation_status": "UNAVAILABLE",
                "prediction_id": prediction.id,
                "complaint_number": c_num,
                "prediction_mode": prediction.prediction_mode,
                "model_version": prediction.model_version,
                "location_model_version": prediction.model_version,
                "message": f"Explanation engine encountered an error: {sanitize_error(str(e))}",
                "actionable_next_step": "Check server logs or retry explanation request."
            }


# Global singleton instance
prediction_explainability_service = PredictionExplainabilityService(random_state=42)

