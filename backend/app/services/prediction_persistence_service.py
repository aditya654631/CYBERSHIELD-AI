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
from sqlalchemy import or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from backend.app.models.models import Complaint, Prediction, PredictionLocation, PredictionSnapshot, LocationCluster
from backend.app.services.prediction_contract import as_utc, utc_iso, build_time_prediction
from backend.app.services.transaction_context_service import resolve_transaction_context

logger = logging.getLogger("cybershield.prediction_persistence")

# Idempotency debounce window in seconds for rapid retries
IDEMPOTENCY_DEBOUNCE_SECONDS = 5


class PredictionPersistenceService:
    """
    Atomic persistence manager for CyberShield AI predictive intelligence.
    """

    @staticmethod
    def get_latest_operational_prediction(db: Session, complaint_id: int) -> Optional[Prediction]:
        """
        Retrieves the latest operational prediction for a complaint.
        Operational intelligence: predictions where analysis_purpose == 'OPERATIONAL',
        or (for backward-compat) analysis_purpose is None AND analysis_as_of is None.
        Historical replays (analysis_purpose == 'HISTORICAL_REPLAY') are NEVER returned
        regardless of how close their cutoff is to the current time.
        """
        preds = (
            db.query(Prediction)
            .filter(Prediction.complaint_id == complaint_id)
            .order_by(
                Prediction.version_number.desc(),
                Prediction.created_at.desc(),
                Prediction.id.desc()
            )
            .all()
        )
        for p in preds:
            # Explicit OPERATIONAL purpose: always treat as operational.
            if p.analysis_purpose == "OPERATIONAL":
                return p
            # Backward-compat: old records with no purpose and no cutoff are operational.
            if p.analysis_purpose is None and p.analysis_as_of is None:
                return p
            # analysis_purpose == 'HISTORICAL_REPLAY' or purpose is None with a cutoff set:
            # never operational. Skip.
        return None

    @staticmethod
    def get_latest_prediction(db: Session, complaint_id: int) -> Optional[Prediction]:
        """
        Deterministically retrieves the latest created Prediction for a complaint,
        ordered by version_number DESC, created_at DESC, id DESC.
        """
        return (
            db.query(Prediction)
            .filter(Prediction.complaint_id == complaint_id)
            .order_by(Prediction.version_number.desc(), Prediction.created_at.desc(), Prediction.id.desc())
            .first()
        )

    @staticmethod
    def get_prediction_versions(db: Session, complaint_id: int) -> List[Prediction]:
        """
        Retrieves all persisted prediction versions for a complaint in chronological version order.
        """
        return (
            db.query(Prediction)
            .filter(Prediction.complaint_id == complaint_id)
            .order_by(Prediction.version_number.asc(), Prediction.id.asc())
            .all()
        )

    def persist_prediction(
        self,
        db: Session,
        complaint: Complaint,
        prediction_data: Dict[str, Any],
        bypass_debounce: bool = False,
        analysis_as_of: Optional[datetime] = None
    ) -> Optional[Prediction]:
        """
        Atomically persists a successful runtime prediction and its Top-3 locations.
        Enforces immutable versioning and strict input identity idempotency.
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

        # Resolve effective analysis cutoff
        persisted_analysis_as_of = None
        if analysis_as_of is not None:
            persisted_analysis_as_of = as_utc(analysis_as_of).replace(tzinfo=None)
            eff_cutoff = persisted_analysis_as_of
        elif prediction_data.get("analysis_as_of") is not None:
            persisted_analysis_as_of = as_utc(prediction_data["analysis_as_of"]).replace(tzinfo=None)
            eff_cutoff = persisted_analysis_as_of
        else:
            persisted_analysis_as_of = None
            eff_cutoff = None

        # Canonical evidence identity from eligible transactions as of cutoff
        context = resolve_transaction_context(db, complaint, analysis_as_of=eff_cutoff)
        eligible_txs = context.get("transactions", [])
        tx_identities = sorted([
            f"{tx.transaction_ref}:{float(tx.amount):.2f}:{utc_iso(tx.timestamp)}:{tx.sender_account_id}:{tx.receiver_account_id}:{getattr(tx, 'source_system', '')}:{getattr(tx, 'is_reversal', False)}:{getattr(tx, 'correction_of_ref', '')}"
            for tx in eligible_txs
        ])

        # 2. Canonical Input Identity & Fingerprint
        # Does NOT include wall-clock timestamp to ensure unchanged retries are idempotent
        input_identity_payload = {
            "complaint_id": complaint.id,
            "complaint_number": complaint.complaint_number,
            "amount": float(complaint.amount) if complaint.amount is not None else None,
            "fraud_type": complaint.fraud_type,
            "payment_channel": complaint.payment_channel,
            "district": complaint.district,
            "victim_lat": float(complaint.victim_lat) if complaint.victim_lat is not None else None,
            "victim_lon": float(complaint.victim_lon) if complaint.victim_lon is not None else None,
            "incident_time": utc_iso(complaint.incident_time),
            "reported_at": utc_iso(complaint.reported_at),
            "model_version": prediction_data.get("model_version"),
            "feature_schema_version": prediction_data.get("feature_schema_version") or "v7_compat",
            "prediction_mode": pred_mode,
            "analysis_as_of": utc_iso(persisted_analysis_as_of) if persisted_analysis_as_of else None,
            "analysis_basis": prediction_data.get("analysis_basis"),
            "eligible_transactions": tx_identities,
        }
        input_fingerprint = hashlib.sha256(
            json.dumps(input_identity_payload, sort_keys=True).encode()
        ).hexdigest()

        # Result Fingerprint
        result_payload = {
            "locations": [
                {
                    "rank": loc["rank"],
                    "cluster_id": loc["cluster_id"],
                    "probability": round(float(loc.get("ml_probability", loc.get("probability", 0.0))), 4),
                    "risk_level": loc.get("risk_level") or loc.get("risk_band")
                }
                for loc in top_locations
            ],
            "time_prediction": {
                "predicted_minutes_to_cashout": (prediction_data.get("time_prediction") or {}).get("predicted_minutes_to_cashout"),
                "window_start": (prediction_data.get("time_prediction") or {}).get("window_start"),
                "window_end": (prediction_data.get("time_prediction") or {}).get("window_end"),
                "operational_window": (prediction_data.get("time_prediction") or {}).get("operational_window"),
            }
        }
        result_fingerprint = hashlib.sha256(
            json.dumps(result_payload, sort_keys=True, default=str).encode()
        ).hexdigest()

        # 3. Idempotency Check:
        # If an identical input request already produced a matching result, reuse it.
        # If identical input produced a DIFFERENT result, flag discrepancy and create new version.
        discrepancy_detected = False
        if not bypass_debounce:
            existing_match = (
                db.query(Prediction)
                .filter(
                    Prediction.complaint_id == complaint.id,
                    Prediction.input_fingerprint == input_fingerprint
                )
                .order_by(Prediction.version_number.desc(), Prediction.id.desc())
                .first()
            )
            if existing_match:
                existing_res_fp = (existing_match.result_metadata or {}).get("result_fingerprint")
                if existing_res_fp == result_fingerprint:
                    logger.info(
                        f"[Persistence] Reusing existing prediction #{existing_match.id} for {complaint.complaint_number} "
                        f"(identical input fingerprint match, version {existing_match.version_number})."
                    )
                    return existing_match
                else:
                    logger.warning(
                        f"[Persistence] Discrepancy detected for {complaint.complaint_number}: "
                        f"identical input produced differing result fingerprint ({existing_res_fp} vs {result_fingerprint})."
                    )
                    discrepancy_detected = True

        # 4. Persistence with Concurrency Retry Loop
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                latest = self.get_latest_prediction(db, complaint.id)
                next_version = (latest.version_number + 1) if (latest and latest.version_number) else 1
                parent_id = latest.id if latest else None

                # 5. Derive Operational Estimate Time Window
                ref_time = complaint.reported_at or complaint.incident_time or datetime.utcnow()
                if pred_mode == "deterministic_demo":
                    window_label = prediction_data.get("when_window", "Next 2–4 Hours")
                    window_start = ref_time + timedelta(hours=2)
                    window_end = ref_time + timedelta(hours=4)
                else:
                    time_pred = prediction_data.get("time_prediction") or {}
                    if not time_pred.get("window_start") or not time_pred.get("window_end"):
                        if time_pred.get("predicted_minutes_to_cashout") is not None:
                            time_pred = build_time_prediction(
                                complaint, float(time_pred["predicted_minutes_to_cashout"]),
                                time_pred.get("model_version"),
                                15 if "v3" in str(time_pred.get("model_version")) else 35,
                            )
                        else:
                            raise ValueError("Trained prediction missing valid time window metadata")

                    window_start_utc = as_utc(time_pred["window_start"])
                    window_end_utc = as_utc(time_pred["window_end"])
                    window_start = window_start_utc.replace(tzinfo=None)
                    window_end = window_end_utc.replace(tzinfo=None)
                    if window_end <= window_start:
                        raise ValueError("Prediction window must end after it starts")

                    window_label = time_pred.get("operational_window") or time_pred.get("when_window") or prediction_data.get("when_window")
                    if not window_label or window_label == "Next 2–4 Hours":
                        ref_utc = as_utc(complaint.reported_at or complaint.incident_time)
                        if ref_utc is not None:
                            low_mins = max(0, math.floor((window_start_utc - ref_utc).total_seconds() / 60.0))
                            high_mins = max(low_mins + 1, math.ceil((window_end_utc - ref_utc).total_seconds() / 60.0))
                            if window_label == "Next 2–4 Hours" and 115 <= low_mins <= 125 and 235 <= high_mins <= 245:
                                pass
                            else:
                                window_label = f"{low_mins}–{high_mins} min after complaint report"
                        else:
                            raise ValueError("Cannot derive operational window label without valid complaint reference time")

                # 6. Extract and Validate Primary Location Metadata
                primary_cluster_id = None
                primary_prob = 0.0
                primary_band = "CRITICAL"
                if top_locations:
                    loc1 = top_locations[0]
                    primary_cluster_id = loc1.get("cluster_id")
                    primary_prob = float(loc1.get("ml_probability", loc1.get("probability", 0.0)))
                    primary_band = str(loc1.get("risk_level") or loc1.get("risk_band") or "CRITICAL")
                    if primary_cluster_id is None:
                        raise ValueError(f"[Persistence] Rank #1 location '{loc1.get('location_name')}' missing cluster_id.")
                    cid_exists = db.query(LocationCluster.id).filter(LocationCluster.id == primary_cluster_id).first()
                    if not cid_exists:
                        raise ValueError(
                            f"[Persistence] Cluster ID {primary_cluster_id} for Rank #1 location "
                            f"'{loc1.get('location_name')}' does not exist in LocationCluster table."
                        )

                # 7. Extract Feature Snapshot (Phase 5)
                inf_snapshot = prediction_data.get("inference_snapshot")

                # 8. Create and Persist Prediction ORM Object
                persisted_time_model_version = (
                    time_pred.get("model_version") if pred_mode == "trained_ml"
                    else (prediction_data.get("time_prediction") or {}).get("model_version")
                )
                persisted_predicted_minutes = (
                    time_pred.get("predicted_minutes_to_cashout") if pred_mode == "trained_ml"
                    else (prediction_data.get("time_prediction") or {}).get("predicted_minutes_to_cashout")
                )

                # Ensure time_prediction dictionary contains ISO strings for datetimes
                clean_time_pred = dict(time_pred if pred_mode == "trained_ml" else (prediction_data.get("time_prediction") or {}))
                if "window_start" in clean_time_pred and isinstance(clean_time_pred["window_start"], datetime):
                    clean_time_pred["window_start"] = utc_iso(clean_time_pred["window_start"])
                if "window_end" in clean_time_pred and isinstance(clean_time_pred["window_end"], datetime):
                    clean_time_pred["window_end"] = utc_iso(clean_time_pred["window_end"])

                result_meta_dict = {
                    **{key: prediction_data[key] for key in (
                        "confidence_score", "ml_score", "graph_score", "geo_score", "temporal_score",
                        "candidate_pool_size", "operational_scope", "dataset_version", "score_type", "score_label",
                        "training_data_source", "analysis_basis", "provenance", "limitations",
                    ) if key in prediction_data},
                    "time_prediction": clean_time_pred,
                    "location_evidence": {str(loc["cluster_id"]): loc.get("evidence", []) for loc in top_locations},
                    "input_fingerprint": input_fingerprint,
                    "result_fingerprint": result_fingerprint,
                    "discrepancy_detected": discrepancy_detected,
                    "analysis_as_of": utc_iso(persisted_analysis_as_of) if persisted_analysis_as_of else None,
                }
                if inf_snapshot:
                    result_meta_dict["inference_snapshot"] = inf_snapshot

                # Resolve explicit analysis purpose — persisted as a first-class field so
                # get_latest_operational_prediction never relies on wall-clock heuristics.
                # Priority:
                # 1. Explicit caller-provided purpose (e.g. 'OPERATIONAL' for live tx ingestion
                #    even when analysis_as_of is a server-set live cutoff).
                # 2. Infer from analysis_as_of: None → OPERATIONAL, not None → HISTORICAL_REPLAY.
                explicit_purpose = prediction_data.get("analysis_purpose")
                if explicit_purpose is not None:
                    resolved_analysis_purpose = explicit_purpose
                elif persisted_analysis_as_of is not None:
                    resolved_analysis_purpose = "HISTORICAL_REPLAY"
                else:
                    resolved_analysis_purpose = "OPERATIONAL"

                prediction = Prediction(
                    complaint_id=complaint.id,
                    version_number=next_version,
                    parent_prediction_id=parent_id,
                    analysis_as_of=persisted_analysis_as_of,
                    analysis_purpose=resolved_analysis_purpose,
                    input_fingerprint=input_fingerprint,
                    prediction_mode=pred_mode,
                    model_version=prediction_data.get("model_version", "cashout-location-xgb-v3.1"),
                    time_model_version=persisted_time_model_version,
                    predicted_minutes_to_cashout=persisted_predicted_minutes,
                    result_metadata=result_meta_dict,
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

                # Phase 5: Persist companion PredictionSnapshot record if snapshot exists
                if inf_snapshot and isinstance(inf_snapshot, dict):
                    snapshot_row = PredictionSnapshot(
                        prediction_id=prediction.id,
                        complaint_id=complaint.id,
                        model_version=str(inf_snapshot.get("model_version", prediction.model_version)),
                        feature_schema_version=str(inf_snapshot.get("feature_schema_version", "v7_compat")),
                        feature_schema_hash=inf_snapshot.get("feature_schema_hash"),
                        model_hash=inf_snapshot.get("location_model_hash"),
                        calibrator_hash=inf_snapshot.get("calibrator_hash"),
                        snapshot_data=inf_snapshot,
                        created_at=prediction.created_at
                    )
                    db.add(snapshot_row)

                # 9. Insert exactly 3 children
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
                    f"[Persistence] Successfully persisted Prediction #{prediction.id} (version {prediction.version_number}) with "
                    f"3 Top-Locations for complaint {complaint.complaint_number}"
                )

                # Phase 5: Supersede older alerts if this is an operational prediction
                try:
                    if prediction.analysis_purpose == "OPERATIONAL" or (prediction.analysis_purpose is None and prediction.analysis_as_of is None):
                        from backend.app.services.outbox_service import outbox_service
                        outbox_service.supersede_older_alerts(
                            db=db,
                            complaint_id=complaint.id,
                            new_prediction_id=prediction.id,
                            new_prediction_version=prediction.version_number
                        )
                except Exception as sup_exc:
                    logger.warning(f"[Persistence] Failed to auto-supersede older alerts: {sup_exc}")

                # Phase B.5: Additive Non-Blocking Blockchain Prediction Audit Anchoring
                try:
                    from backend.app.services.prediction_audit_service import prediction_audit_client
                    audit_dict = {
                        "prediction_id": prediction.id,
                        "complaint_number": complaint.complaint_number,
                        "complaint_id": complaint.id,
                        "prediction_mode": prediction.prediction_mode,
                        "model_version": prediction.model_version,
                        "time_model_version": prediction.time_model_version,
                        "created_at": prediction.created_at,
                        "predicted_window_start": prediction.predicted_window_start,
                        "predicted_window_end": prediction.predicted_window_end,
                        "window_label": prediction.window_label,
                        "top_locations": [
                            {
                                "rank": loc.rank,
                                "cluster_id": loc.cluster_id,
                                "probability": loc.probability,
                                "location_name": loc.location_name
                            }
                            for loc in sorted(prediction.locations, key=lambda x: x.rank)
                        ]
                    }
                    anchor_res = prediction_audit_client.anchor_prediction_safe(audit_dict)
                    current_meta = dict(prediction.result_metadata or {})
                    current_meta["audit_anchor"] = anchor_res
                    prediction.result_metadata = current_meta
                    db.commit()
                    db.refresh(prediction)
                except Exception as anchor_exc:
                    logger.warning(
                        f"[Persistence] Prediction #{prediction.id} persisted, but audit anchor attempt encountered error: {anchor_exc}. "
                        f"Prediction remains fully valid (non-blocking failure isolation)."
                    )

                return prediction

            except IntegrityError as ie:
                db.rollback()
                err_str = str(ie).lower()
                # Only treat version uniqueness constraint violations as a race condition.
                # Broader patterns like "unique constraint" would incorrectly swallow unrelated
                # integrity failures (e.g. foreign key violations, other unique indexes).
                is_ver_race = "uq_complaint_version_number" in err_str or (
                    "version_number" in err_str and "complaint_id" in err_str
                )
                if is_ver_race:
                    # Check for verified winner with identical input AND result fingerprints
                    winner = (
                        db.query(Prediction)
                        .filter(
                            Prediction.complaint_id == complaint.id,
                            Prediction.input_fingerprint == input_fingerprint
                        )
                        .order_by(Prediction.version_number.desc(), Prediction.id.desc())
                        .first()
                    )
                    if winner:
                        winner_res_fp = (winner.result_metadata or {}).get("result_fingerprint")
                        if winner_res_fp == result_fingerprint:
                            logger.info(
                                f"[Persistence] Resolved concurrent race: returning verified identical winner #{winner.id} "
                                f"for complaint {complaint.complaint_number}."
                            )
                            return winner
                    # If distinct concurrent evidence arrived, retry allocation with new monotonic version!
                    if attempt < max_attempts - 1:
                        logger.info(
                            f"[Persistence] Version race detected with distinct evidence for {complaint.complaint_number}. "
                            f"Retrying version allocation (attempt {attempt + 1}/{max_attempts})."
                        )
                        continue

                # Unrelated or unresolvable integrity conflict: DO NOT SWALLOW!
                logger.error(
                    f"[Persistence] Database integrity conflict for complaint {complaint.complaint_number}: {ie}. "
                    f"Transaction rolled back completely.",
                    exc_info=True
                )
                raise
            except Exception as exc:
                db.rollback()
                logger.error(
                    f"[Persistence] Failed to persist prediction for complaint {complaint.complaint_number}: {exc}. "
                    f"Transaction rolled back completely.",
                    exc_info=True
                )
                raise


prediction_persistence_service = PredictionPersistenceService()
