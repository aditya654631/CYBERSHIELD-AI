"""
CyberShield AI — LIME Explainability Service for Official V7 Predictions
Phase B.7: Model Decision Support & Tabular Attribution Engine

Provides local surrogate attribution via lime.lime_tabular.LimeTabularExplainer for
cashout-location-xgb-v7-compat predictions.

Inviolable Guarantees:
1. Read-Only / Non-Mutating: Never generates, alters, or replaces official predictions,
   rankings, probabilities, Top-3, or prediction modes.
2. Safety Language: Uses local approximation language; never claims proof or causality.
3. Fidelity Auditing: Tracks R^2 local fidelity and absolute error; marks weak fits as LOW_FIDELITY.
4. Determinism: Uses fixed explainer random_state and seed for stable explanations.
5. Non-Blocking: Catches all exceptions and returns UNAVAILABLE without affecting predictions.
6. Provenance & Provenance Isolation: Strict metadata logging; zero blockchain features injected.
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
from sqlalchemy.orm import Session

from backend.app.models.models import Complaint, Prediction, PredictionLocation
from backend.app.services.ml_feature_service import build_location_features
from backend.app.services.prediction_service import prediction_service

logger = logging.getLogger("cybershield.explainability")

# Exact runtime feature schema for cashout-location-xgb-v7-compat
V4_COMPAT_FEATURES = [
    "v4_candidate_score",
    "v4_candidate_rank_normalized",
    "v4_candidate_percentile",
    "v4_score_gap_from_candidate1"
]

FEATURE_FRIENDLY_NAMES = {
    "v4_candidate_score": "V4 base candidate model score",
    "v4_candidate_rank_normalized": "Normalized candidate ranking order",
    "v4_candidate_percentile": "Candidate ranking percentile",
    "v4_score_gap_from_candidate1": "Score margin gap relative to top candidate",
    "distance_from_victim": "Distance from complaint reporting origin",
    "dist_to_terminal_zone_km": "Distance to downstream transaction account zone",
    "dist_to_complaint_zone_km": "Distance to complaint jurisdiction centroid",
    "candidate_same_terminal_zone": "Candidate matches terminal mule account zone",
    "candidate_same_complaint_zone": "Candidate matches complaint origin zone",
    "candidate_same_any_account_zone": "Candidate matches intermediate transaction account zone",
    "historical_cluster_risk": "Historical cash-out cluster risk prior",
    "historical_cluster_cashout_count": "Historical cluster cash-out frequency",
    "historical_cluster_cashout_amount": "Historical cluster transaction volume",
    "atm_density": "Local commercial ATM density",
    "recent_cluster_activity": "Recent 7-day syndicate cluster activity",
    "fraud_type_cluster_frequency": "Syndicate cluster frequency for specific fraud category",
    "transaction_velocity": "Multi-hop layering transaction velocity",
    "chain_duration_minutes": "Duration of transaction chain before withdrawal",
    "hop_count": "Layering hop depth count",
    "total_transferred": "Total transferred fraud amount",
    "log_amount": "Logarithm of complaint transaction amount",
    "connected_component_size": "Mule network connected component size",
    "mule_connection_count": "Direct mule account connection count",
    "max_pagerank": "Graph PageRank centrality in mule network",
    "max_betweenness": "Graph betweenness centrality in mule network"
}

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ARTIFACTS_DIR = os.path.join(BASE_DIR, "ml", "artifacts")
BACKGROUND_DATA_PATH = os.path.join(ARTIFACTS_DIR, "v7_lime_background.npy")
BACKGROUND_META_PATH = os.path.join(ARTIFACTS_DIR, "v7_lime_background_metadata.json")


class PredictionExplainabilityService:
    """
    Production LIME Explainability Service for official V7-compat predictions.
    Uses tabular candidate-level surrogate linear models.
    """

    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        self.explainer = None
        self.background_matrix: Optional[np.ndarray] = None
        self.background_metadata: Dict[str, Any] = {}
        self.feature_names: List[str] = []
        self.explainer_version: str = "lime_tabular_0.2.0.1"
        self.feature_schema_version: str = "v7_compat"
        self.is_initialized: bool = False
        self._init_error: Optional[str] = None

    def _ensure_initialized(self) -> bool:
        """Lazy-loads background data and initializes LimeTabularExplainer."""
        if self.is_initialized:
            return True

        try:
            from lime.lime_tabular import LimeTabularExplainer

            if not os.path.exists(BACKGROUND_DATA_PATH):
                self._init_error = f"Background matrix not found at {BACKGROUND_DATA_PATH}"
                logger.error(self._init_error)
                return False

            self.background_matrix = np.load(BACKGROUND_DATA_PATH)
            if os.path.exists(BACKGROUND_META_PATH):
                with open(BACKGROUND_META_PATH, "r", encoding="utf-8") as f:
                    self.background_metadata = json.load(f)

            # Load official V7 feature schema
            mlp = prediction_service.ml_provider
            schema_features = (mlp.feature_schema or {}).get("location_features")
            if not schema_features or len(schema_features) != 47:
                from ml.features.feature_pipeline import FEATURE_COLUMNS_LOCATION_V3_1
                schema_features = FEATURE_COLUMNS_LOCATION_V3_1 + V4_COMPAT_FEATURES

            self.feature_names = list(schema_features)

            self.explainer = LimeTabularExplainer(
                training_data=self.background_matrix,
                feature_names=self.feature_names,
                mode="regression",
                random_state=self.random_state
            )
            self.is_initialized = True
            logger.info("Successfully initialized PredictionExplainabilityService with %d background rows", len(self.background_matrix))
            return True
        except Exception as e:
            self._init_error = f"Explainer initialization failed: {e}"
            logger.exception("Failed to initialize LIME explainer: %s", e)
            return False

    def build_candidate_features_for_complaint(
        self,
        db: Session,
        complaint: Complaint
    ) -> Tuple[Optional[Dict[int, np.ndarray]], Optional[List[Dict[str, Any]]], Optional[str]]:
        """
        Reconstructs the exact 47 candidate-level features used by cashout-location-xgb-v7-compat.
        Returns ({cluster_id: feature_vector_47}, candidates_list, error_message).
        """
        try:
            loc_res = build_location_features(db, complaint.id, top_k=25, model_version="v3.1")
            if loc_res.get("status") != "SUCCESS":
                return None, None, f"Candidate feature extraction failed: {loc_res.get('status')}"

            X_loc = loc_res["candidate_rows"]
            candidates = loc_res["candidates"]
            if len(candidates) < 3 or X_loc.shape[0] == 0:
                return None, None, "Insufficient candidates returned by candidate generator"

            mlp = prediction_service.ml_provider
            v4_model = mlp.v4_model
            v4_calibrator = mlp.v4_calibrator

            # V4 base compatibility features
            v4_raw = v4_model.predict_proba(X_loc)[:, 1]
            v4_scores = v4_calibrator.predict_proba(v4_raw.reshape(-1, 1))[:, 1]
            n_cands = len(candidates)
            ranks = np.argsort(-v4_scores)
            rank_positions = np.empty_like(ranks)
            rank_positions[ranks] = np.arange(n_cands)
            v4_ranks_norm = rank_positions / max(1.0, float(n_cands - 1))
            v4_percentiles = (n_cands - 1 - rank_positions) / max(1.0, float(n_cands - 1))
            best_v4_score = float(np.max(v4_scores))
            v4_gaps = best_v4_score - v4_scores

            v4_feats = np.column_stack([v4_scores, v4_ranks_norm, v4_percentiles, v4_gaps])
            X_loc_compat = np.hstack([X_loc, v4_feats])
            X_loc_compat = np.nan_to_num(X_loc_compat, nan=0.0)

            cand_feature_map = {}
            for idx, cand in enumerate(candidates):
                cid = int(cand["id"])
                cand_feature_map[cid] = X_loc_compat[idx]

            return cand_feature_map, candidates, None
        except Exception as e:
            logger.exception("Error extracting candidate features for complaint %s: %s", complaint.complaint_number, e)
            return None, None, str(e)

    @staticmethod
    def classify_fidelity(r2_score: float, abs_error: float) -> str:
        """
        Conservative fidelity classification for local surrogate LIME explanations:
        - R² >= 0.70 (and |err| <= 0.15): HIGH_FIDELITY
        - 0.40 <= R² < 0.70 (and |err| <= 0.25): MODERATE_FIDELITY
        - R² < 0.40 or |err| > 0.25: LOW_FIDELITY

        Absolute approximation error is retained as a separate diagnostic.
        """
        if r2_score >= 0.70 and abs_error <= 0.15:
            return "HIGH_FIDELITY"
        elif r2_score >= 0.40 and abs_error <= 0.25:
            return "MODERATE_FIDELITY"
        else:
            return "LOW_FIDELITY"

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
        num_features: int = 8,
        num_samples: int = 1000
    ) -> Dict[str, Any]:
        """
        Explains an individual candidate location prediction using tabular LIME.
        Deterministic through seed resetting.
        """
        mlp = prediction_service.ml_provider
        v7_model = mlp.location_model
        v7_calibrator = mlp.calibrator

        def predict_fn(X: np.ndarray) -> np.ndarray:
            clean_X = np.nan_to_num(X, nan=0.0)
            raw = v7_model.predict(clean_X)
            return v7_calibrator.predict_proba(raw.reshape(-1, 1))[:, 1]

        # Ensure determinism across repeat calls
        self.explainer.random_state = np.random.RandomState(self.random_state)
        if hasattr(self.explainer, "discretizer") and self.explainer.discretizer:
            self.explainer.discretizer.random_state = np.random.RandomState(self.random_state)
        np.random.seed(self.random_state)

        clean_row = np.nan_to_num(candidate_vector, nan=0.0)
        exp = self.explainer.explain_instance(
            data_row=clean_row,
            predict_fn=predict_fn,
            num_features=num_features,
            num_samples=num_samples
        )

        local_pred = float(exp.local_pred[0]) if hasattr(exp.local_pred, "__getitem__") else float(exp.local_pred)
        r2_score = float(exp.score) if exp.score is not None and not np.isnan(exp.score) else 0.0
        abs_error = abs(float(official_score) - local_pred)

        # Conservative fidelity check
        fidelity_status = self.classify_fidelity(r2_score, abs_error)

        pos_contribs = []
        neg_contribs = []

        # Parse contributions from as_map (label 1 for regression/positive output)
        map_items = exp.as_map().get(1, exp.as_map().get(0, []))
        rule_map = dict(exp.as_list())

        for feat_idx, weight in map_items:
            f_idx = int(feat_idx)
            if f_idx < 0 or f_idx >= len(self.feature_names):
                continue
            fname = self.feature_names[f_idx]
            fval = float(clean_row[f_idx])
            w = float(weight)

            # Match rule string from as_list
            rule_str = ""
            for r_str, r_w in exp.as_list():
                if fname in r_str or f"f_{f_idx}" in r_str:
                    rule_str = r_str.replace(f"f_{f_idx}", fname)
                    break
            if not rule_str:
                rule_str = f"{fname} = {fval:.2f}"

            friendly = FEATURE_FRIENDLY_NAMES.get(fname, fname.replace("_", " ").title())
            if w >= 0:
                desc = f"Factors that contributed to this candidate ranking include {friendly} ({fname} = {fval:.2f}; local rule: {rule_str})."
                pos_contribs.append({
                    "feature_name": fname,
                    "rule": rule_str,
                    "weight": round(w, 4),
                    "feature_value": round(fval, 4),
                    "description": desc
                })
            else:
                desc = f"Factors reducing candidate ranking priority include {friendly} ({fname} = {fval:.2f}; local rule: {rule_str})."
                neg_contribs.append({
                    "feature_name": fname,
                    "rule": rule_str,
                    "weight": round(w, 4),
                    "feature_value": round(fval, 4),
                    "description": desc
                })

        summary = (
            f"Factors that contributed to candidate '{location_name}' (Rank #{rank}) ranking include "
            f"local surrogate alignment across spatial corridor proximity and historical cluster risk priors. "
            f"This is a local surrogate explanation, not proof or causal evidence of criminal activity."
        )

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
            "summary_statement": summary
        }

    def get_or_generate_explanation(
        self,
        db: Session,
        prediction_id: int
    ) -> Dict[str, Any]:
        """
        Retrieves or generates LIME explainability for official V7 prediction.
        Guaranteed:
        - Never creates/recomputes Predictions on GET.
        - Never modifies PredictionLocation or Alert rows.
        - Returns appropriate status: AVAILABLE, LOW_FIDELITY, UNAVAILABLE, or raises NOT_FOUND.
        """
        prediction = db.query(Prediction).filter(Prediction.id == prediction_id).first()
        if not prediction:
            return {
                "explanation_status": "NOT_FOUND",
                "prediction_id": prediction_id,
                "complaint_number": "UNKNOWN",
                "prediction_mode": "unavailable",
                "model_version": "unavailable",
                "message": f"Prediction #{prediction_id} not found in database."
            }

        complaint = db.query(Complaint).filter(Complaint.id == prediction.complaint_id).first()
        c_num = complaint.complaint_number if complaint else f"CMP-{prediction.complaint_id}"

        # Check existing result_metadata cache
        cached_exp = (prediction.result_metadata or {}).get("explainability") if prediction.result_metadata else None
        if isinstance(cached_exp, dict) and cached_exp.get("explanation_status") in ("AVAILABLE", "LOW_FIDELITY"):
            self._apply_conservative_fidelity_classification(cached_exp)
            try:
                current_meta = dict(prediction.result_metadata or {})
                current_meta["explainability"] = cached_exp
                prediction.result_metadata = current_meta
                db.commit()
            except Exception:
                db.rollback()
            return cached_exp

        # Check model applicability
        if prediction.model_version != "cashout-location-xgb-v7-compat":
            return {
                "explanation_status": "UNAVAILABLE",
                "prediction_id": prediction.id,
                "complaint_number": c_num,
                "prediction_mode": prediction.prediction_mode,
                "model_version": prediction.model_version,
                "location_model_version": prediction.model_version,
                "message": f"LIME tabular explanation is only calibrated for official cashout-location-xgb-v7-compat. Active model is {prediction.model_version}."
            }

        # Ensure LIME engine is loaded
        if not self._ensure_initialized():
            return {
                "explanation_status": "UNAVAILABLE",
                "prediction_id": prediction.id,
                "complaint_number": c_num,
                "prediction_mode": prediction.prediction_mode,
                "model_version": prediction.model_version,
                "location_model_version": prediction.model_version,
                "message": f"LIME explainer engine unavailable: {self._init_error}"
            }

        # Query persisted PredictionLocation rows strictly
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
                "message": "Persisted official prediction has fewer than 3 locations."
            }

        top3_locs = locations[:3]

        try:
            # Extract 47 candidate features
            cand_feature_map, _, err = self.build_candidate_features_for_complaint(db, complaint)
            if cand_feature_map is None:
                return {
                    "explanation_status": "UNAVAILABLE",
                    "prediction_id": prediction.id,
                    "complaint_number": c_num,
                    "prediction_mode": prediction.prediction_mode,
                    "model_version": prediction.model_version,
                    "location_model_version": prediction.model_version,
                    "message": f"Could not construct candidate feature vector: {err}"
                }

            top3_exps = []

            for loc in top3_locs:
                cid = int(loc.cluster_id)
                if cid not in cand_feature_map:
                    return {
                        "explanation_status": "UNAVAILABLE",
                        "prediction_id": prediction.id,
                        "complaint_number": c_num,
                        "prediction_mode": prediction.prediction_mode,
                        "model_version": prediction.model_version,
                        "location_model_version": prediction.model_version,
                        "message": f"Cluster ID {cid} (Rank {loc.rank}) not found in generated candidate pool."
                    }

                vec = cand_feature_map[cid]
                cand_exp = self.explain_candidate(
                    candidate_vector=vec,
                    rank=int(loc.rank),
                    cluster_id=cid,
                    location_name=loc.location_name,
                    official_score=float(loc.probability),
                    num_features=8,
                    num_samples=1000
                )
                top3_exps.append(cand_exp)

            # Format backward-compatible factors from Rank 1
            rank1_exp = top3_exps[0]
            compat_factors = []
            all_contribs = rank1_exp.get("positive_contributions", []) + rank1_exp.get("negative_contributions", [])
            total_w = sum(abs(c["weight"]) for c in all_contribs) or 1.0
            for c in sorted(all_contribs, key=lambda x: -abs(x["weight"]))[:5]:
                pct = int(round((abs(c["weight"]) / total_w) * 100))
                compat_factors.append({
                    "name": c["feature_name"],
                    "contribution_percentage": max(5, pct),
                    "description": c["description"]
                })

            response_payload = {
                "explanation_status": "AVAILABLE",
                "prediction_id": prediction.id,
                "complaint_number": c_num,
                "prediction_mode": prediction.prediction_mode,
                "model_version": prediction.model_version,
                "location_model_version": prediction.model_version,
                "explanation_method": "LIME",
                "explainer_version": self.explainer_version,
                "feature_schema_version": self.feature_schema_version,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "overall_fidelity_status": "LOW_FIDELITY",
                "mean_local_fidelity_r2": 0.0,
                "background_sample_size": int(self.background_metadata.get("background_sample_size", 500)),
                "background_seed": int(self.background_metadata.get("seed", 56100)),
                "top3_explanations": top3_exps,
                "factors": compat_factors,
                "narrative": "",
                "disclaimer": (
                    "LIME provides local surrogate linear explanations of model decisions for risk prioritization. "
                    "This is an algorithmic approximation, not proof or causal evidence of criminal activity."
                )
            }

            self._apply_conservative_fidelity_classification(response_payload)

            mean_r2 = response_payload["mean_local_fidelity_r2"]
            overall_status = response_payload["overall_fidelity_status"]
            response_payload["narrative"] = (
                f"Prediction #{prediction.id} explained via {self.explainer_version} (LIME tabular). "
                f"Factors that contributed to candidate rankings include base model score, corridor proximity, "
                f"and historical cluster priors. Local approximation fidelity R² = {mean_r2:.4f} ({overall_status})."
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
                "message": f"Explanation engine encountered an unexpected error: {str(e)}"
            }



# Global singleton instance
prediction_explainability_service = PredictionExplainabilityService(random_state=42)
