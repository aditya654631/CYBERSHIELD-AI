from typing import Any, Optional, List
from datetime import timedelta, datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.app.models.db import get_db
from backend.app.models.models import Complaint, Prediction, PredictionLocation, User
from backend.app.schemas.schemas import (
    PredictionResponse,
    ExplanationResponse,
    PredictionRunRequest,
    PredictionVersionSummary,
)
from backend.app.auth.security import get_current_user
from backend.app.auth.rbac import require_roles, verify_complaint_access, RoleEnum
from backend.app.services.audit_service import log_audit
from backend.app.services.prediction_service import prediction_service
from backend.app.services.prediction_contract import utc_iso, window_status

router = APIRouter(prefix="/predictions", tags=["Predictive Intelligence"])


def _build_time_prediction_field(
    prediction: Any,
    complaint: "Complaint",
    pred_mode: str,
    res_meta: dict,
) -> dict:
    """
    Phase 11: Builds the time_prediction response field for a persisted Prediction ORM row,
    propagating uncertainty provenance (window_basis, uncertainty_minutes) from
    result_metadata.time_prediction so they survive the persistence round-trip.

    Priority:
      1. Structural fields (minutes, model_version, window_start/end) from ORM columns.
      2. uncertainty_minutes and window_basis recovered from result_metadata.time_prediction
         (written at inference time by build_time_prediction).
    This function never mutates ORM objects or historical data.
    """
    ref_time = complaint.reported_at or complaint.incident_time or getattr(prediction, "created_at", None)
    fallback_label = "Next 2\u20134 Hours" if pred_mode == "deterministic_demo" else "Next 2\u20134 Hours (operational estimate window)"

    # Recover provenance fields from result_metadata.time_prediction (written at inference time)
    meta_time = res_meta.get("time_prediction", {}) if isinstance(res_meta, dict) else {}
    if not isinstance(meta_time, dict):
        meta_time = {}

    persisted_minutes = getattr(prediction, "predicted_minutes_to_cashout", None)
    return {
        "predicted_minutes_to_cashout": persisted_minutes,
        "model_version": getattr(prediction, "time_model_version", None),
        "prediction_reference_time": utc_iso(ref_time),
        "reference_basis": meta_time.get("reference_basis", "complaint_reported_at"),
        "predicted_cashout_at": (
            utc_iso(ref_time + timedelta(minutes=float(persisted_minutes)))
            if ref_time and persisted_minutes is not None
            else None
        ),
        "window_start": utc_iso(getattr(prediction, "predicted_window_start", None)),
        "window_end": utc_iso(getattr(prediction, "predicted_window_end", None)),
        "window_status": window_status(
            getattr(prediction, "predicted_window_start", None),
            getattr(prediction, "predicted_window_end", None),
        ),
        "uncertainty_minutes": meta_time.get("uncertainty_minutes"),
        "window_basis": meta_time.get("window_basis"),
        "operational_window": getattr(prediction, "window_label", None) or fallback_label,
    }


def _derive_priority_level(intervention_priority: Optional[int], risk_level: Optional[str] = None) -> str:
    """
    Aligns priority_level with the live inference response logic from prediction_service.py:
    CRITICAL / >= 80 -> IMMEDIATE ACTION
    HIGH / >= 70 -> HIGH PRIORITY
    MEDIUM / >= 45 -> MONITOR
    otherwise / < 45 -> ROUTINE
    """
    if risk_level:
        band = str(risk_level).upper()
        if band == "CRITICAL":
            return "IMMEDIATE ACTION"
        elif band == "HIGH":
            return "HIGH PRIORITY"
        elif band == "MEDIUM":
            return "MONITOR"
        elif band in ("LOW", "ROUTINE"):
            return "ROUTINE"

    prio = intervention_priority if intervention_priority is not None else 50
    if prio >= 80:
        return "IMMEDIATE ACTION"
    elif prio >= 70:
        return "HIGH PRIORITY"
    elif prio >= 45:
        return "MONITOR"
    else:
        return "ROUTINE"


def _format_prediction_response(prediction: Any, complaint: Complaint) -> dict:
    if isinstance(prediction, dict):
        return prediction

    # Ensure locations are explicitly sorted by rank ASC
    locations = sorted(prediction.locations, key=lambda x: x.rank)
    primary_loc = locations[0].location_name if locations else "Vijay Nagar, Indore"

    top_loc_items = [
        {
            "rank": loc.rank,
            "cluster_id": loc.cluster_id,
            "cluster_name": loc.cluster.cluster_name if loc.cluster else loc.location_name,
            "location_name": loc.location_name,
            "zone": loc.cluster.district if loc.cluster else None,
            "district": loc.cluster.district if loc.cluster else None,
            "state": loc.cluster.state if loc.cluster else None,
            "probability": loc.probability,
            "ml_probability": loc.probability,
            "risk_score": loc.probability,
            "risk_level": loc.risk_level,
            "risk_band": loc.risk_level,
            "distance_km": loc.distance_km,
            "reasoning": loc.reasoning or "Identified cash-out cluster node",
            "evidence": [loc.reasoning] if loc.reasoning else None,
            "latitude": loc.latitude or (loc.cluster.center_lat if loc.cluster else 28.6139),
            "longitude": loc.longitude or (loc.cluster.center_lon if loc.cluster else 77.2090)
        }
        for loc in locations
    ]

    ref_time = complaint.reported_at or complaint.incident_time or getattr(prediction, "created_at", None)

    pred_mode = getattr(prediction, "prediction_mode", None) or "trained_ml"
    primary_cid = getattr(prediction, "primary_cluster_id", None)
    if not primary_cid and locations:
        primary_cid = locations[0].cluster_id

    if pred_mode == "trained_ml":
        op_scope = "DELHI_PILOT"
        pool_size = 25
    elif pred_mode == "deterministic_demo":
        raw_scope = getattr(prediction, "operational_scope", None)
        op_scope = raw_scope if raw_scope else None
        pool_size = 3
    else:
        op_scope = None
        pool_size = 0

    interv_prio = getattr(prediction, "intervention_priority", 50)
    risk_level_val = getattr(prediction, "risk_level", None)
    res_meta = getattr(prediction, "result_metadata", {}) or {}

    return {
        "prediction_id": getattr(prediction, "id", 0) if not isinstance(prediction, dict) else prediction.get("prediction_id", 0),
        "complaint_id": complaint.id,
        "complaint_number": complaint.complaint_number,
        "status": "SUCCESS",
        "where_location": primary_loc,
        "primary_cluster_id": primary_cid,
        "when_window": getattr(prediction, "window_label", None) or ("Next 2–4 Hours" if pred_mode == "deterministic_demo" else "Next 2–4 Hours (operational estimate window)"),
        "risk_score": getattr(prediction, "risk_score", None),
        "risk_percentage": int((getattr(prediction, "risk_score", 0.0) or 0.0) * 100),
        "risk_level": risk_level_val or "MEDIUM",
        "risk_band": risk_level_val or "MEDIUM",
        "intervention_priority": interv_prio,
        "priority_level": _derive_priority_level(interv_prio, risk_level_val),
        "why_summary": getattr(prediction, "why_explanation", None) or "Predicted cash-out cluster",
        "confidence_score": getattr(prediction, "confidence_score", 0.0) or 0.0,
        "ml_score": getattr(prediction, "ml_score", 0.0) or 0.0,
        "graph_score": getattr(prediction, "graph_score", 0.0) or 0.0,
        "geo_score": getattr(prediction, "geo_score", 0.0) or 0.0,
        "temporal_score": getattr(prediction, "temporal_score", 0.0) or 0.0,
        "top_locations": top_loc_items,
        "prediction_mode": pred_mode,
        "model_version": getattr(prediction, "model_version", None) or "unavailable",
        "operational_scope": op_scope,
        "candidate_pool_size": pool_size,
        "version_number": getattr(prediction, "version_number", 1) if not isinstance(prediction, dict) else prediction.get("version_number", 1),
        "parent_prediction_id": getattr(prediction, "parent_prediction_id", None) if not isinstance(prediction, dict) else prediction.get("parent_prediction_id"),
        "analysis_as_of": getattr(prediction, "analysis_as_of", None) if not isinstance(prediction, dict) else prediction.get("analysis_as_of"),
        "analysis_purpose": getattr(prediction, "analysis_purpose", "OPERATIONAL") if not isinstance(prediction, dict) else prediction.get("analysis_purpose", "OPERATIONAL"),
        "input_fingerprint": getattr(prediction, "input_fingerprint", None) if not isinstance(prediction, dict) else prediction.get("input_fingerprint"),
        "discrepancy_detected": res_meta.get("discrepancy_detected", False) if isinstance(res_meta, dict) else False,
        # Phase 11: use helper to propagate window_basis and uncertainty_minutes from result_metadata
        "time_prediction": _build_time_prediction_field(prediction, complaint, pred_mode, res_meta),
        "limitations": [
            "Operational scope is strictly calibrated for Delhi Pilot 60 clusters."
        ] if pred_mode == "trained_ml" else [
            "Deterministic demonstration case reserved for SIH presentation consistency."
        ],
        "created_at": getattr(prediction, "created_at", None) if not isinstance(prediction, dict) else prediction.get("created_at")
    }


@router.post("/{complaint_id}", response_model=PredictionResponse)
def run_prediction(
    complaint_id: str,
    payload: Optional[PredictionRunRequest] = None,
    analysis_as_of: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        RoleEnum.I4C_ADMIN, RoleEnum.STATE_LEA, RoleEnum.DISTRICT_LEA, RoleEnum.ANALYST
    ))
):
    if complaint_id.isdigit():
        complaint = db.query(Complaint).filter(Complaint.id == int(complaint_id)).first()
    else:
        complaint = db.query(Complaint).filter(Complaint.complaint_number == complaint_id).first()

    if not complaint or not verify_complaint_access(complaint, current_user, db):
        raise HTTPException(status_code=404, detail="Complaint not found")

    effective_cutoff = None
    if payload and payload.analysis_as_of:
        effective_cutoff = payload.analysis_as_of
    elif analysis_as_of:
        effective_cutoff = analysis_as_of

    # Step 10: Dynamic inference + atomic persistence into Prediction and PredictionLocation.
    # analysis_purpose is HISTORICAL_REPLAY when the user explicitly specified a cutoff,
    # and OPERATIONAL when no cutoff was provided (live forward-looking analysis).
    resolved_purpose = "HISTORICAL_REPLAY" if effective_cutoff is not None else "OPERATIONAL"
    result = prediction_service.run_and_persist_prediction(
        db, complaint.id, analysis_as_of=effective_cutoff, analysis_purpose=resolved_purpose
    )

    # Log audit event: PREDICTION_RUN with authoritative user
    pred_id = result.get("prediction_id") or (result.id if hasattr(result, "id") else None)
    log_audit(
        db=db,
        user_id=current_user.id,
        officer_name=current_user.full_name,
        role=current_user.role,
        action="PREDICTION_RUN",
        case_number=complaint.complaint_number,
        details=f"Predictive analysis executed for {complaint.complaint_number} (Prediction ID: #{pred_id}, Mode: {result.get('prediction_mode')}, Model: {result.get('model_version')}, Scope: {result.get('operational_scope')}, Cutoff: {effective_cutoff})"
    )

    return _format_prediction_response(result, complaint)


@router.get("/{complaint_id}", response_model=PredictionResponse)
def get_prediction(
    complaint_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Strictly read-only endpoint: retrieves the operational prediction for the complaint.
    Operational "latest" prioritizes the latest analysis cutoff (point in time),
    ensuring a historical replay does not overwrite the live operational intelligence.
    Returns 404 if no prediction has been persisted yet or if complaint is out of jurisdiction.
    """
    if complaint_id.isdigit():
        complaint = db.query(Complaint).filter(Complaint.id == int(complaint_id)).first()
    else:
        complaint = db.query(Complaint).filter(Complaint.complaint_number == complaint_id).first()

    if not complaint or not verify_complaint_access(complaint, current_user, db):
        raise HTTPException(status_code=404, detail="Complaint not found")

    from backend.app.services.prediction_persistence_service import prediction_persistence_service
    latest_pred = prediction_persistence_service.get_latest_operational_prediction(db, complaint.id)
    if not latest_pred:
        latest_pred = prediction_persistence_service.get_latest_prediction(db, complaint.id)

    if not latest_pred:
        raise HTTPException(
            status_code=404,
            detail=f"No persisted prediction found for complaint {complaint.complaint_number}. Run prediction first via POST."
        )

    return _format_prediction_response(latest_pred, complaint)


@router.get("/{complaint_id}/versions", response_model=List[PredictionVersionSummary])
def get_prediction_versions(
    complaint_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves chronological version history of predictive intelligence for a complaint.
    Enables audit inspection across historical replays and incremental transfer updates.
    """
    if complaint_id.isdigit():
        complaint = db.query(Complaint).filter(Complaint.id == int(complaint_id)).first()
    else:
        complaint = db.query(Complaint).filter(Complaint.complaint_number == complaint_id).first()

    if not complaint or not verify_complaint_access(complaint, current_user, db):
        raise HTTPException(status_code=404, detail="Complaint not found")

    from backend.app.services.prediction_persistence_service import prediction_persistence_service
    versions = prediction_persistence_service.get_prediction_versions(db, complaint.id)
    summaries = []
    for pred in versions:
        locs = sorted(pred.locations, key=lambda x: x.rank)
        primary_name = locs[0].location_name if locs else None
        res_meta = pred.result_metadata or {}
        summaries.append(
            PredictionVersionSummary(
                prediction_id=pred.id,
                complaint_id=pred.complaint_id,
                version_number=pred.version_number or 1,
                parent_prediction_id=pred.parent_prediction_id,
                analysis_as_of=pred.analysis_as_of,
                analysis_purpose=pred.analysis_purpose or ("HISTORICAL_REPLAY" if pred.analysis_as_of else "OPERATIONAL"),
                created_at=pred.created_at,
                primary_cluster_id=pred.primary_cluster_id,
                primary_location_name=primary_name,
                risk_score=pred.risk_score or 0.0,
                risk_level=pred.risk_level or "MEDIUM",
                operational_window=pred.window_label,
                input_fingerprint=pred.input_fingerprint,
                discrepancy_detected=res_meta.get("discrepancy_detected", False) if isinstance(res_meta, dict) else False,
            )
        )
    return summaries


@router.get("/version/{prediction_id}", response_model=PredictionResponse)
def get_prediction_version(
    prediction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves a specific immutable historical prediction version by its ID.
    Preserves audit access to historical replays without mutating the operational view.
    """
    prediction = db.query(Prediction).filter(Prediction.id == prediction_id).first()
    if not prediction:
        raise HTTPException(status_code=404, detail=f"Prediction #{prediction_id} not found.")

    complaint = db.query(Complaint).filter(Complaint.id == prediction.complaint_id).first()
    if not complaint or not verify_complaint_access(complaint, current_user, db):
        raise HTTPException(status_code=404, detail="Prediction not found.")

    return _format_prediction_response(prediction, complaint)


@router.get("/{prediction_id}/explanation", response_model=ExplanationResponse)
def get_prediction_explanation(
    prediction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    prediction = db.query(Prediction).filter(Prediction.id == prediction_id).first()
    if not prediction:
        raise HTTPException(
            status_code=404,
            detail=f"Prediction #{prediction_id} not found."
        )

    complaint = db.query(Complaint).filter(Complaint.id == prediction.complaint_id).first()
    if not complaint or not verify_complaint_access(complaint, current_user, db):
        raise HTTPException(
            status_code=404,
            detail=f"Prediction #{prediction_id} not found."
        )

    from backend.app.services.prediction_explainability_service import prediction_explainability_service
    return prediction_explainability_service.get_or_generate_explanation(db, prediction_id)


@router.get("/{prediction_id}/audit-verification")
def verify_prediction_audit(
    prediction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Phase B.5: Tamper-Evident Prediction Audit Verification Endpoint.
    Loads persisted prediction from PostgreSQL, recomputes canonical SHA-256 hash,
    and compares against the immutable Hyperledger Fabric ledger anchor.
    """
    prediction = db.query(Prediction).filter(Prediction.id == prediction_id).first()
    if not prediction:
        raise HTTPException(status_code=404, detail=f"Prediction #{prediction_id} not found.")

    complaint = db.query(Complaint).filter(Complaint.id == prediction.complaint_id).first()
    if not complaint or not verify_complaint_access(complaint, current_user, db):
        raise HTTPException(status_code=404, detail="Prediction not found.")

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

    verification = prediction_audit_client.verify_prediction(audit_dict)
    return {
        "prediction_id": prediction.id,
        "complaint_number": complaint.complaint_number,
        **verification
    }
