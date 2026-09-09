from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.models.db import get_db
from backend.app.models.models import Alert, Complaint
from backend.app.schemas.schemas import AlertResponse, AlertActionRequest
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

@router.post("/generate/{complaint_id}", response_model=AlertResponse)
def generate_alert_for_complaint(complaint_id: str, db: Session = Depends(get_db)):
    if complaint_id.isdigit():
        complaint = db.query(Complaint).filter(Complaint.id == int(complaint_id)).first()
    else:
        complaint = db.query(Complaint).filter(Complaint.complaint_number == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    
    alert = db.query(Alert).filter(Alert.complaint_id == complaint.id).order_by(Alert.created_at.desc()).first()
    if not alert:
        alert = Alert(
            complaint_id=complaint.id,
            title=f"CRITICAL CASH-OUT IMMINENT: {complaint.victim_location} ({complaint.complaint_number})",
            severity="CRITICAL" if (complaint.risk_score or 0) >= 0.8 else "HIGH",
            location_name=complaint.victim_location,
            risk_score=complaint.risk_score or 0.85,
            expected_window="Next 2–4 Hours",
            amount_at_risk=complaint.amount,
            status="NEW",
            created_at=datetime.utcnow()
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        
        log_audit(
            db=db,
            officer_name="Inspector R. Verma",
            role="DISTRICT_LEA",
            action="ALERT_CREATED",
            case_number=complaint.complaint_number,
            details=f"Alert #{alert.id} generated for {complaint.complaint_number}."
        )

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
    db: Session = Depends(get_db)
):
    alert = db.query(Alert).filter(Alert.id == id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = "ACKNOWLEDGED"
    alert.acknowledged_by = "Inspector R. Verma (District LEA Indore)"
    alert.acknowledged_at = datetime.utcnow()
    alert.action_notes = (data.notes if data else None) or "Dispatched field unit to ATM cluster"

    # Also update complaint status if needed
    complaint = db.query(Complaint).filter(Complaint.id == alert.complaint_id).first()
    if complaint:
        complaint.case_status = "ALERTED"

    db.commit()
    db.refresh(alert)

    # Log audit
    log_audit(
        db=db,
        officer_name="Inspector R. Verma",
        role="DISTRICT_LEA",
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
    db: Session = Depends(get_db)
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
        officer_name="Inspector R. Verma",
        role="DISTRICT_LEA",
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
