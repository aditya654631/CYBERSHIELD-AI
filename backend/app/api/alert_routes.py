from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.models.db import get_db
from backend.app.models.models import Alert, Complaint, User
from backend.app.schemas.schemas import AlertResponse, AlertActionRequest
from backend.app.auth.security import get_current_user
from backend.app.services.alert_service import create_alert_for_prediction
from backend.app.services.prediction_persistence_service import prediction_persistence_service
from backend.app.services.audit_service import log_audit
from backend.app.websocket.manager import ws_manager

router = APIRouter(prefix="/alerts", tags=["Alerts Center"])

@router.get("", response_model=List[AlertResponse])
def list_alerts(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Alert)
    if status and status != "ALL":
        query = query.filter(Alert.status == status)
    if severity and severity != "ALL":
        query = query.filter(Alert.severity == severity)

    alerts = query.order_by(Alert.created_at.desc()).all()

    # Pre-fetch complaint numbers
    comp_ids = [a.complaint_id for a in alerts]
    complaints = {c.id: c for c in db.query(Complaint).filter(Complaint.id.in_(comp_ids)).all()}

    results = []
    for a in alerts:
        comp = complaints.get(a.complaint_id)
        results.append({
            "id": a.id,
            "complaint_id": a.complaint_id,
            "complaint_number": comp.complaint_number if comp else f"CMP-{a.complaint_id}",
            "prediction_id": a.prediction_id,
            "title": a.title,
            "severity": a.severity,
            "location_name": a.location_name,
            "risk_score": a.risk_score,
            "expected_window": a.expected_window,
            "amount_at_risk": a.amount_at_risk,
            "status": a.status,
            "acknowledged_by": a.acknowledged_by,
            "acknowledged_at": a.acknowledged_at,
            "action_notes": a.action_notes,
            "created_at": a.created_at
        })
    return results

@router.get("/{id}", response_model=AlertResponse)
def get_alert(id: int, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    complaint = db.query(Complaint).filter(Complaint.id == alert.complaint_id).first()
    return {
        "id": alert.id,
        "complaint_id": alert.complaint_id,
        "complaint_number": complaint.complaint_number if complaint else f"CMP-{alert.complaint_id}",
        "prediction_id": alert.prediction_id,
        "title": alert.title,
        "severity": alert.severity,
        "location_name": alert.location_name,
        "risk_score": alert.risk_score,
        "expected_window": alert.expected_window,
        "amount_at_risk": alert.amount_at_risk,
        "status": alert.status,
        "acknowledged_by": alert.acknowledged_by,
        "acknowledged_at": alert.acknowledged_at,
        "action_notes": alert.action_notes,
        "created_at": alert.created_at
    }

@router.post("/prediction/{prediction_id}", response_model=AlertResponse)
async def generate_alert_for_prediction(
    prediction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Primary Step-12 endpoint: creates an Alert strictly from an existing persisted Prediction ID.
    Enforces primary cluster invariant, duplicate prevention, and zero ML invocation.
    """
    alert = create_alert_for_prediction(db, prediction_id, user=current_user)
    complaint = db.query(Complaint).filter(Complaint.id == alert.complaint_id).first()

    # Safely broadcast via websocket after DB commit
    try:
        await ws_manager.broadcast({
            "event": "ALERT_CREATED",
            "alert_id": alert.id,
            "prediction_id": alert.prediction_id,
            "complaint_number": complaint.complaint_number if complaint else f"CMP-{alert.complaint_id}",
            "location": alert.location_name,
            "severity": alert.severity,
            "risk_score": alert.risk_score
        })
    except Exception:
        pass

    return {
        "id": alert.id,
        "complaint_id": alert.complaint_id,
        "complaint_number": complaint.complaint_number if complaint else f"CMP-{alert.complaint_id}",
        "prediction_id": alert.prediction_id,
        "title": alert.title,
        "severity": alert.severity,
        "location_name": alert.location_name,
        "risk_score": alert.risk_score,
        "expected_window": alert.expected_window,
        "amount_at_risk": alert.amount_at_risk,
        "status": alert.status,
        "acknowledged_by": alert.acknowledged_by,
        "acknowledged_at": alert.acknowledged_at,
        "action_notes": alert.action_notes,
        "created_at": alert.created_at
    }

@router.post("/generate/{complaint_id}", response_model=AlertResponse)
async def generate_alert_for_complaint(
    complaint_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Convenience endpoint: resolves the latest persisted Prediction for a complaint ONCE,
    captures prediction.id, and delegates to create_alert_for_prediction.
    Fails cleanly (HTTP 404) if no persisted prediction exists.
    """
    if complaint_id.isdigit():
        complaint = db.query(Complaint).filter(Complaint.id == int(complaint_id)).first()
    else:
        complaint = db.query(Complaint).filter(Complaint.complaint_number == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    latest_pred = prediction_persistence_service.get_latest_prediction(db, complaint.id)
    if not latest_pred:
        raise HTTPException(
            status_code=404,
            detail=f"No persisted prediction available for complaint {complaint.complaint_number}. "
                   f"Alerts cannot be generated without an existing persisted prediction."
        )

    alert = create_alert_for_prediction(db, latest_pred.id, user=current_user)

    # Safely broadcast via websocket after DB commit
    try:
        await ws_manager.broadcast({
            "event": "ALERT_CREATED",
            "alert_id": alert.id,
            "prediction_id": alert.prediction_id,
            "complaint_number": complaint.complaint_number,
            "location": alert.location_name,
            "severity": alert.severity,
            "risk_score": alert.risk_score
        })
    except Exception:
        pass

    return {
        "id": alert.id,
        "complaint_id": alert.complaint_id,
        "complaint_number": complaint.complaint_number,
        "prediction_id": alert.prediction_id,
        "title": alert.title,
        "severity": alert.severity,
        "location_name": alert.location_name,
        "risk_score": alert.risk_score,
        "expected_window": alert.expected_window,
        "amount_at_risk": alert.amount_at_risk,
        "status": alert.status,
        "acknowledged_by": alert.acknowledged_by,
        "acknowledged_at": alert.acknowledged_at,
        "action_notes": alert.action_notes,
        "created_at": alert.created_at
    }

@router.post("/{id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(
    id: int,
    data: Optional[AlertActionRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    alert = db.query(Alert).filter(Alert.id == id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    if alert.status != "ACKNOWLEDGED":
        alert.status = "ACKNOWLEDGED"
        alert.acknowledged_by = f"{current_user.full_name} ({current_user.role})"
        alert.acknowledged_at = datetime.utcnow()
    if data and data.notes:
        alert.action_notes = data.notes
    elif not alert.action_notes:
        alert.action_notes = "Dispatched field unit to ATM cluster"

    # Also update complaint status if needed
    complaint = db.query(Complaint).filter(Complaint.id == alert.complaint_id).first()
    if complaint:
        complaint.case_status = "ALERTED"

    db.commit()
    db.refresh(alert)

    # Log audit
    log_audit(
        db=db,
        user_id=current_user.id,
        officer_name=current_user.full_name,
        role=current_user.role,
        action="ALERT_ACKNOWLEDGED",
        case_number=complaint.complaint_number if complaint else f"CMP-{alert.complaint_id}",
        details=f"Alert #{alert.id} acknowledged for {alert.location_name}. Field unit notified."
    )

    # Broadcast via websocket
    await ws_manager.broadcast({
        "event": "ALERT_ACKNOWLEDGED",
        "alert_id": alert.id,
        "location": alert.location_name,
        "officer": alert.acknowledged_by
    })

    return {
        "id": alert.id,
        "complaint_id": alert.complaint_id,
        "complaint_number": complaint.complaint_number if complaint else f"CMP-{alert.complaint_id}",
        "prediction_id": alert.prediction_id,
        "title": alert.title,
        "severity": alert.severity,
        "location_name": alert.location_name,
        "risk_score": alert.risk_score,
        "expected_window": alert.expected_window,
        "amount_at_risk": alert.amount_at_risk,
        "status": alert.status,
        "acknowledged_by": alert.acknowledged_by,
        "acknowledged_at": alert.acknowledged_at,
        "action_notes": alert.action_notes,
        "created_at": alert.created_at
    }

@router.post("/{id}/escalate", response_model=AlertResponse)
async def escalate_alert(
    id: int,
    data: Optional[AlertActionRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    alert = db.query(Alert).filter(Alert.id == id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = "ACTION_INITIATED"
    alert.action_notes = (data.notes if data else None) or "Automated bank ATM hold request transmitted via I4C Gateway"
    db.commit()
    db.refresh(alert)

    complaint = db.query(Complaint).filter(Complaint.id == alert.complaint_id).first()

    # Log audit
    log_audit(
        db=db,
        user_id=current_user.id,
        officer_name=current_user.full_name,
        role=current_user.role,
        action="ALERT_ESCALATED",
        case_number=complaint.complaint_number if complaint else f"CMP-{alert.complaint_id}",
        details=f"Alert #{alert.id} escalated. ATM transaction hold triggered at {alert.location_name}."
    )

    # Broadcast via websocket
    await ws_manager.broadcast({
        "event": "ALERT_ESCALATED",
        "alert_id": alert.id,
        "location": alert.location_name,
        "action": "BANK_HOLD_TRIGGERED"
    })

    return {
        "id": alert.id,
        "complaint_id": alert.complaint_id,
        "complaint_number": complaint.complaint_number if complaint else f"CMP-{alert.complaint_id}",
        "prediction_id": alert.prediction_id,
        "title": alert.title,
        "severity": alert.severity,
        "location_name": alert.location_name,
        "risk_score": alert.risk_score,
        "expected_window": alert.expected_window,
        "amount_at_risk": alert.amount_at_risk,
        "status": alert.status,
        "acknowledged_by": alert.acknowledged_by,
        "acknowledged_at": alert.acknowledged_at,
        "action_notes": alert.action_notes,
        "created_at": alert.created_at
    }
