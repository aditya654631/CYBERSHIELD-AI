"""
CyberShield AI — Phase 1 Step 10: Prediction + Top-3 Location Persistence Service

Provides atomic persistence for runtime predictions into:
- Prediction (parent row with model provenance, time window, risk metrics)
- PredictionLocation (exactly 3 children corresponding to Top-3 locations)

Strict Guarantees:
1. Atomic commit boundary: parent + all 3 children in single transaction; rollback on any failure.
2. Read-only GET /predictions/{complaint_id}: returns latest persisted or 404. Never executes or persists from GET.
3. Preserves exact Step-9 inference results: exact cluster IDs, ranks (1, 2, 3), calibrated probabilities, provenance.
4. Zero outcome leakage: does not touch Withdrawal or target clusters.
5. Zero alert creation: does not mutate Alert or send WebSocket alerts.
6. Time window labeled as 'operational estimate window'.
"""

import logging
import math
import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from backend.app.models.models import Complaint, Prediction, PredictionLocation
from backend.app.services.prediction_contract import as_utc, build_time_prediction

logger = logging.getLogger("cybershield.prediction_persistence")

# Idempotency debounce window in seconds for rapid retries
IDEMPOTENCY_DEBOUNCE_SECONDS = 5


class PredictionPersistenceService:
    """
    Atomic persistence manager for CyberShield AI predictive intelligence.
    """

    @staticmethod
    def get_latest_prediction(db: Session, complaint_id: int) -> Optional[Prediction]:
        """
        Deterministically retrieves the latest persisted Prediction for a complaint,
        ordered by created_at DESC, id DESC.
        """
        return (
            db.query(Prediction)
            .filter(Prediction.complaint_id == complaint_id)
            .order_by(Prediction.created_at.desc(), Prediction.id.desc())
            .first()
        )

    def persist_prediction(
        self,
        db: Session,
        complaint: Complaint,
        prediction_data: Dict[str, Any],
        bypass_debounce: bool = False
    ) -> Optional[Prediction]:
        """
        Atomically persists a successful runtime prediction and its Top-3 locations.
        Returns the created Prediction ORM object, or None if the prediction is unavailable/ineligible.
        """
        # 1. Gate: Only persist successful predictions with valid modes
        status = prediction_data.get("status")
        pred_mode = prediction_data.get("prediction_mode")
        if status != "SUCCESS" or pred_mode not in ("trained_ml", "deterministic_demo"):
            logger.info(
                f"[Persistence] Skipping persistence for complaint {complaint.complaint_number}: "
                f"status='{status}', mode='{pred_mode}'"
            )
            return None

        top_locations = prediction_data.get("top_locations", [])
        if len(top_locations) != 3:
            logger.warning(
                f"[Persistence] Cannot persist prediction for {complaint.complaint_number}: "
                f"expected exactly 3 locations, got {len(top_locations)}"
            )
            return None

        if len({loc.get("cluster_id") for loc in top_locations}) != 3 or sorted(loc.get("rank") for loc in top_locations) != [1, 2, 3]:
            raise ValueError("Predictions require three distinct clusters ranked 1, 2, 3")
        top_locations = sorted(top_locations, key=lambda loc: loc["rank"])
        fingerprint_payload = {
            "locations": top_locations,
            "time_prediction": {key: value for key, value in (prediction_data.get("time_prediction") or {}).items() if key != "window_status"},
            "analysis_basis": prediction_data.get("analysis_basis"),
        }
        fingerprint = hashlib.sha256(json.dumps(fingerprint_payload, sort_keys=True, default=str).encode()).hexdigest()

        # 2. Idempotency / Debounce Check
        # If an identical/valid prediction already exists for this complaint, reuse it to preserve strict idempotency
        if not bypass_debounce:
            latest = self.get_latest_prediction(db, complaint.id)
            if latest:
                time_diff = (as_utc(datetime.utcnow()) - as_utc(latest.created_at)).total_seconds() if latest.created_at else 0.0
                existing_fp = (latest.result_metadata or {}).get("result_fingerprint") if latest.result_metadata else None
                rank1_cluster_id = top_locations[0].get("cluster_id")
                is_identical = (
                    latest.prediction_mode == pred_mode
                    and latest.model_version == prediction_data.get("model_version")
                    and (
                        (existing_fp is not None and existing_fp == fingerprint)
                        or (latest.primary_cluster_id == rank1_cluster_id and len(latest.locations) == 3)
                    )
                )
                if is_identical:
                    logger.info(
                        f"[Persistence] Reusing existing prediction #{latest.id} for {complaint.complaint_number} "
                        f"(idempotency match / {time_diff:.1f}s ago)."
                    )
                    return latest

        # 3. Derive Operational Estimate Time Window
        ref_time = complaint.reported_at or complaint.incident_time or datetime.utcnow()
        if pred_mode == "deterministic_demo":
            window_label = prediction_data.get("when_window", "Next 2–4 Hours")
            window_start = ref_time + timedelta(hours=2)
            window_end = ref_time + timedelta(hours=4)
        else:
            time_pred = prediction_data.get("time_prediction") or {}
            if not time_pred.get("window_start") or not time_pred.get("window_end"):
                time_pred = build_time_prediction(
                    complaint, float(time_pred["predicted_minutes_to_cashout"]),
                    time_pred.get("model_version"),
                    15 if "v3" in str(time_pred.get("model_version")) else 35,
                )
            window_label = time_pred["operational_window"]
            window_start = as_utc(time_pred["window_start"]).replace(tzinfo=None)
            window_end = as_utc(time_pred["window_end"]).replace(tzinfo=None)
            if window_end <= window_start:
                raise ValueError("Prediction window must end after it starts")

        # 4. Extract and Validate Primary Location Metadata
        from backend.app.models.models import LocationCluster

        rank1_loc = top_locations[0]
        primary_cluster_id = rank1_loc.get("cluster_id")
        if primary_cluster_id is None:
            raise ValueError(
                f"[Persistence] Rank 1 location '{rank1_loc.get('location_name')}' has no cluster_id."
            )
        primary_exists = db.query(LocationCluster.id).filter(LocationCluster.id == primary_cluster_id).first()
        if not primary_exists:
            raise ValueError(
                f"[Persistence] Primary cluster_id {primary_cluster_id} for '{rank1_loc.get('location_name')}' "
                f"does not exist in LocationCluster table. Remapping is strictly forbidden."
            )

        primary_prob = float(rank1_loc.get("ml_probability", rank1_loc.get("probability", 0.0)))
        primary_band = rank1_loc.get("risk_band") or rank1_loc.get("risk_level", "CRITICAL")

        # 5. Atomic Transaction Execution
        try:
            persisted_time_model_version = None
            persisted_predicted_minutes = None
            if pred_mode == "trained_ml":
                raw_time_pred = prediction_data.get("time_prediction")
                if isinstance(raw_time_pred, dict):
                    persisted_predicted_minutes = raw_time_pred.get("predicted_minutes_to_cashout")
                    persisted_time_model_version = raw_time_pred.get("model_version") or None

            prediction = Prediction(
                complaint_id=complaint.id,
                prediction_mode=pred_mode,
                model_version=prediction_data.get("model_version", "cashout-location-xgb-v3.1"),
                time_model_version=persisted_time_model_version,
                predicted_minutes_to_cashout=persisted_predicted_minutes,
                result_metadata={
                    **{key: prediction_data[key] for key in (
                        "candidate_pool_size", "operational_scope", "dataset_version", "score_type", "score_label",
                        "training_data_source", "analysis_basis", "provenance", "limitations",
                    ) if key in prediction_data},
                    "time_prediction": time_pred if pred_mode == "trained_ml" else prediction_data.get("time_prediction"),
                    "location_evidence": {str(loc["cluster_id"]): loc.get("evidence", []) for loc in top_locations},
                    "result_fingerprint": fingerprint,
                },
                predicted_window_start=window_start,
                predicted_window_end=window_end,
                window_label=window_label,
                primary_cluster_id=primary_cluster_id,
                risk_score=float(prediction_data.get("risk_score", primary_prob)),
                risk_level=prediction_data.get("risk_level", primary_band),
                confidence_score=float(prediction_data.get("confidence_score", primary_prob)),
                ml_score=float(prediction_data.get("ml_score", primary_prob)),
                graph_score=float(prediction_data.get("graph_score", 0.0)),
                geo_score=float(prediction_data.get("geo_score", 0.0)),
                temporal_score=float(prediction_data.get("temporal_score", 0.0)),
                intervention_priority=int(prediction_data.get("intervention_priority", 50)),
                why_explanation=prediction_data.get("why_summary", "Rank #1 predicted cash-out cluster"),
                created_at=datetime.utcnow()
            )
            db.add(prediction)
            db.flush()  # Allocates prediction.id while remaining inside transaction

            # Insert exactly 3 children
            for loc in top_locations:
                prob_val = float(loc.get("ml_probability", loc.get("probability", 0.0)))
                if not math.isfinite(prob_val) or not 0 <= prob_val <= 1:
                    raise ValueError("Location score must be finite and between zero and one")
                reason_val = loc.get("reasoning")
                if not reason_val and loc.get("evidence"):
                    reason_val = "; ".join(loc.get("evidence", []))[:250]

                loc_cid = loc.get("cluster_id")
                if loc_cid is None:
                    raise ValueError(
                        f"[Persistence] Location rank {loc.get('rank')} '{loc.get('location_name')}' has no cluster_id."
                    )
                cid_exists = db.query(LocationCluster.id).filter(LocationCluster.id == loc_cid).first()
                if not cid_exists:
                    raise ValueError(
                        f"[Persistence] Cluster ID {loc_cid} for rank {loc.get('rank')} '{loc.get('location_name')}' "
                        f"does not exist in LocationCluster table. Name-based remapping or substitution is strictly forbidden."
                    )

                pred_loc = PredictionLocation(
                    prediction_id=prediction.id,
                    cluster_id=loc_cid,
                    location_name=str(loc.get("location_name") or loc.get("cluster_name") or "Unknown"),
                    rank=int(loc["rank"]),
                    probability=prob_val,
                    risk_level=str(loc.get("risk_level") or loc.get("risk_band") or "CRITICAL"),
                    distance_km=float(loc.get("distance_km", 0.0)),
                    reasoning=reason_val,
                    latitude=float(loc["latitude"]) if loc.get("latitude") is not None else None,
                    longitude=float(loc["longitude"]) if loc.get("longitude") is not None else None
                )
                db.add(pred_loc)

            db.commit()
            db.refresh(prediction)
            logger.info(
                f"[Persistence] Successfully persisted Prediction #{prediction.id} with "
                f"3 Top-Locations for complaint {complaint.complaint_number}"
            )
            return prediction

        except Exception as exc:
            db.rollback()
            logger.error(
                f"[Persistence] Failed to persist prediction for complaint {complaint.complaint_number}: {exc}. "
                f"Transaction rolled back completely.",
                exc_info=True
            )
            raise


prediction_persistence_service = PredictionPersistenceService()
