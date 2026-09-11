from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.models.db import get_db
from backend.app.models.models import Complaint, Prediction, PredictionLocation, User
from backend.app.schemas.schemas import PredictionResponse, ExplanationResponse
from backend.app.auth.security import get_current_user
from backend.app.services.audit_service import log_audit
from backend.app.services.prediction_service import prediction_service

router = APIRouter(prefix="/predictions", tags=["Predictive Intelligence"])


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

    ref_time = complaint.reported_at or complaint.incident_time or prediction.created_at
    if prediction.predicted_window_start and ref_time:
        diff_mins = (prediction.predicted_window_start - ref_time).total_seconds() / 60.0
        est_mins = max(15.0, round(diff_mins + 35.0, 1))
    else:
        est_mins = 120.0

    pred_mode = getattr(prediction, "prediction_mode", None) or (prediction.get("prediction_mode") if isinstance(prediction, dict) else "trained_ml")
    primary_cid = getattr(prediction, "primary_cluster_id", None) or (prediction.get("primary_cluster_id") if isinstance(prediction, dict) else None)
    if not primary_cid and locations:
        primary_cid = locations[0].cluster_id

    if pred_mode == "trained_ml":
        op_scope = "DELHI_PILOT"
        pool_size = 25
    elif pred_mode == "deterministic_demo":
        raw_scope = getattr(prediction, "operational_scope", None) or (prediction.get("operational_scope") if isinstance(prediction, dict) else None)
        op_scope = raw_scope if raw_scope else None
        pool_size = 3
    else:
        op_scope = None
        pool_size = 0

    return {
        "prediction_id": getattr(prediction, "id", 0) if not isinstance(prediction, dict) else prediction.get("prediction_id", 0),
        "complaint_id": complaint.id,
        "complaint_number": complaint.complaint_number,
        "status": "SUCCESS",
        "where_location": primary_loc,
        "primary_cluster_id": primary_cid,
        "when_window": getattr(prediction, "window_label", None) or (prediction.get("when_window") if isinstance(prediction, dict) else ("Next 2–4 Hours" if pred_mode == "deterministic_demo" else "Next 2–4 Hours (operational estimate window)")),
        "risk_score": getattr(prediction, "risk_score", None) if not isinstance(prediction, dict) else prediction.get("risk_score"),
        "risk_percentage": int(((getattr(prediction, "risk_score", None) or 0.0) if not isinstance(prediction, dict) else (prediction.get("risk_score") or 0.0)) * 100),
        "risk_level": getattr(prediction, "risk_level", None) or (prediction.get("risk_level") if isinstance(prediction, dict) else "MEDIUM"),
        "risk_band": getattr(prediction, "risk_level", None) or (prediction.get("risk_level") if isinstance(prediction, dict) else "MEDIUM"),
        "intervention_priority": getattr(prediction, "intervention_priority", 50) if not isinstance(prediction, dict) else prediction.get("intervention_priority", 50),
        "priority_level": "IMMEDIATE ACTION" if ((getattr(prediction, "intervention_priority", 0) or 0) if not isinstance(prediction, dict) else (prediction.get("intervention_priority", 0) or 0)) >= 80 else "HIGH PRIORITY",
        "why_summary": getattr(prediction, "why_explanation", None) or (prediction.get("why_summary") if isinstance(prediction, dict) else "Predicted cash-out cluster"),
        "confidence_score": getattr(prediction, "confidence_score", 0.0) if not isinstance(prediction, dict) else prediction.get("confidence_score", 0.0),
        "ml_score": getattr(prediction, "ml_score", 0.0) if not isinstance(prediction, dict) else prediction.get("ml_score", 0.0),
        "graph_score": getattr(prediction, "graph_score", 0.0) if not isinstance(prediction, dict) else prediction.get("graph_score", 0.0),
        "geo_score": getattr(prediction, "geo_score", 0.0) if not isinstance(prediction, dict) else prediction.get("geo_score", 0.0),
        "temporal_score": getattr(prediction, "temporal_score", 0.0) if not isinstance(prediction, dict) else prediction.get("temporal_score", 0.0),
        "top_locations": top_loc_items,
        "prediction_mode": pred_mode,
        "model_version": getattr(prediction, "model_version", None) or (prediction.get("model_version") if isinstance(prediction, dict) else "cashout-location-xgb-v3.1"),
        "operational_scope": op_scope,
        "candidate_pool_size": pool_size,
        "time_prediction": {
            "predicted_minutes_to_cashout": est_mins,
            "model_version": "cashout-time-xgb-v2" if pred_mode == "trained_ml" else "demo-time-v1",
            "prediction_reference_time": str(ref_time),
            "operational_window": getattr(prediction, "window_label", None) or (prediction.get("when_window") if isinstance(prediction, dict) else "Next 2–4 Hours (operational estimate window)")
        },
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if complaint_id.isdigit():
        complaint = db.query(Complaint).filter(Complaint.id == int(complaint_id)).first()
    else:
        complaint = db.query(Complaint).filter(Complaint.complaint_number == complaint_id).first()

    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    # Step 10: Dynamic inference + atomic persistence into Prediction and PredictionLocation
    result = prediction_service.run_and_persist_prediction(db, complaint.id)

    # Log audit event: PREDICTION_RUN with authoritative user
    pred_id = result.get("prediction_id") or (result.id if hasattr(result, "id") else None)
    log_audit(
        db=db,
        user_id=current_user.id,
        officer_name=current_user.full_name,
        role=current_user.role,
        action="PREDICTION_RUN",
        case_number=complaint.complaint_number,
        details=f"Predictive analysis executed for {complaint.complaint_number} (Prediction ID: #{pred_id}, Mode: {result.get('prediction_mode')}, Model: {result.get('model_version')}, Scope: {result.get('operational_scope')})"
    )

    return _format_prediction_response(result, complaint)


@router.get("/{complaint_id}", response_model=PredictionResponse)
def get_prediction(complaint_id: str, db: Session = Depends(get_db)):
    """
    Strictly read-only endpoint: retrieves the latest persisted prediction for the complaint.
    Returns 404 if no prediction has been persisted yet. Does NOT execute inference or persist from GET.
    """
    if complaint_id.isdigit():
        complaint = db.query(Complaint).filter(Complaint.id == int(complaint_id)).first()
    else:
        complaint = db.query(Complaint).filter(Complaint.complaint_number == complaint_id).first()

    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    from backend.app.services.prediction_persistence_service import prediction_persistence_service
    latest_pred = prediction_persistence_service.get_latest_prediction(db, complaint.id)
    if not latest_pred:
        raise HTTPException(
            status_code=404,
            detail=f"No persisted prediction found for complaint {complaint.complaint_number}. Run prediction first via POST."
        )

    return _format_prediction_response(latest_pred, complaint)


@router.get("/{prediction_id}/explanation", response_model=ExplanationResponse)
def get_prediction_explanation(prediction_id: int, db: Session = Depends(get_db)):
    prediction = db.query(Prediction).filter(Prediction.id == prediction_id).first()
    if prediction:
        complaint = db.query(Complaint).filter(Complaint.id == prediction.complaint_id).first()
        return prediction_service.get_explanation(prediction, complaint)

    # If prediction_id is 0 or unpersisted
    default_comp = db.query(Complaint).first()
    if not default_comp:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return prediction_service.get_explanation({"prediction_id": prediction_id, "prediction_mode": "trained_ml"}, default_comp)
