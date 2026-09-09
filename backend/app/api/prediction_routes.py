from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.models.db import get_db
from backend.app.models.models import Complaint, Prediction, PredictionLocation
from backend.app.schemas.schemas import PredictionResponse, ExplanationResponse
from backend.app.services.prediction_service import prediction_service
from backend.app.services.audit_service import log_audit

router = APIRouter(prefix="/predictions", tags=["Predictive Intelligence"])

def _format_prediction_response(prediction: Prediction, complaint: Complaint) -> dict:
    locations = sorted(prediction.locations, key=lambda x: x.rank)
    primary_loc = locations[0].location_name if locations else "Vijay Nagar, Indore"

    top_loc_items = [
        {
            "rank": loc.rank,
            "location_name": loc.location_name,
            "probability": loc.probability,
            "risk_level": loc.risk_level,
            "distance_km": loc.distance_km,
            "reasoning": loc.reasoning or "Identified cash-out cluster node",
            "latitude": loc.latitude or 22.7533,
            "longitude": loc.longitude or 75.8937
        }
        for loc in locations
    ]

    return {
        "prediction_id": prediction.id,
        "complaint_id": complaint.id,
        "complaint_number": complaint.complaint_number,
        "where_location": primary_loc,
        "when_window": prediction.window_label or "Next 2–4 Hours",
        "risk_score": prediction.risk_score,
        "risk_percentage": int(prediction.risk_score * 100),
        "risk_level": prediction.risk_level,
        "intervention_priority": prediction.intervention_priority,
        "priority_level": "IMMEDIATE ACTION" if prediction.intervention_priority >= 85 else "HIGH PRIORITY",
        "why_summary": "High Mule-Network Similarity",
        "confidence_score": prediction.confidence_score,
        "ml_score": prediction.ml_score,
        "graph_score": prediction.graph_score,
        "geo_score": prediction.geo_score,
        "temporal_score": prediction.temporal_score,
        "top_locations": top_loc_items,
        "prediction_mode": getattr(prediction, "prediction_mode", "deterministic_demo") or "deterministic_demo",
        "model_version": getattr(prediction, "model_version", "demo-provider-v1") or "demo-provider-v1",
        "created_at": prediction.created_at
    }

@router.post("/{complaint_id}", response_model=PredictionResponse)
def run_prediction(complaint_id: str, db: Session = Depends(get_db)):
    if complaint_id.isdigit():
        complaint = db.query(Complaint).filter(Complaint.id == int(complaint_id)).first()
    else:
        complaint = db.query(Complaint).filter(Complaint.complaint_number == complaint_id).first()

    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    prediction = prediction_service.run_prediction(db, complaint.id)

    # Log audit
    log_audit(
        db=db,
        officer_name="Inspector R. Verma",
        role="STATE_LEA",
        action="PREDICTION_RUN",
        case_number=complaint.complaint_number,
        details=f"Predictive cash-out inference executed for {complaint.complaint_number}. Risk: {int(prediction.risk_score * 100)}%"
    )

    return _format_prediction_response(prediction, complaint)

@router.get("/{complaint_id}", response_model=PredictionResponse)
def get_prediction(complaint_id: str, db: Session = Depends(get_db)):
    if complaint_id.isdigit():
        complaint = db.query(Complaint).filter(Complaint.id == int(complaint_id)).first()
    else:
        complaint = db.query(Complaint).filter(Complaint.complaint_number == complaint_id).first()

    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    # Get latest prediction or run on-demand
    prediction = db.query(Prediction).filter(
        Prediction.complaint_id == complaint.id
    ).order_by(Prediction.created_at.desc()).first()

    if not prediction:
        prediction = prediction_service.run_prediction(db, complaint.id)

    return _format_prediction_response(prediction, complaint)

@router.get("/{prediction_id}/explanation", response_model=ExplanationResponse)
def get_prediction_explanation(prediction_id: int, db: Session = Depends(get_db)):
    prediction = db.query(Prediction).filter(Prediction.id == prediction_id).first()
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")

    complaint = db.query(Complaint).filter(Complaint.id == prediction.complaint_id).first()
    return prediction_service.get_explanation(prediction, complaint)
