from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.models.db import get_db
from backend.app.models.models import Alert, Complaint, User
from backend.app.schemas.schemas import AlertResponse, AlertActionRequest
from backend.app.auth.security import get_current_user
from backend.app.auth.rbac import (
    require_roles,
    verify_alert_access,
    verify_complaint_access,
    filter_complaints_by_jurisdiction,
    RoleEnum
)
from backend.app.services.alert_service import create_alert_for_prediction
from backend.app.services.prediction_persistence_service import prediction_persistence_service
from backend.app.services.audit_service import log_audit
from backend.app.services.bank_action_service import bank_action_service
from backend.app.websocket.manager import ws_manager

router = APIRouter(prefix="/alerts", tags=["Alerts Center"])


@router.get("", response_model=List[AlertResponse])
def list_alerts(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists alerts filtered by officer jurisdiction.
    LEA officers see alerts for complaints in their jurisdiction;
    Bank officers see alerts involving their bank.
    """
    # Join Complaint to enforce jurisdiction
    query = db.query(Alert).join(Complaint, Alert.complaint_id == Complaint.id)

    # Apply jurisdiction filtering on complaints
    filtered_comp_subq = filter_complaints_by_jurisdiction(db.query(Complaint.id), current_user, db).subquery()
    query = query.filter(Alert.complaint_id.in_(filtered_comp_subq))

    if status and status != "ALL":
        query = query.filter(Alert.status == status)
    if severity and severity != "ALL":
        query = query.filter(Alert.severity == severity)

    alerts = query.order_by(Alert.created_at.desc()).all()

    comp_ids = [a.complaint_id for a in alerts]
    complaints = {c.id: c for c in db.query(Complaint).filter(Complaint.id.in_(comp_ids)).all()} if comp_ids else {}

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
def get_alert(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves alert details with object-level jurisdiction check.
    Returns 404 if outside jurisdiction to avoid leaking record existence.
    """
    alert = db.query(Alert).filter(Alert.id == id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    if not verify_alert_access(alert, current_user, db):
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
    current_user: User = Depends(require_roles(
        RoleEnum.I4C_ADMIN, RoleEnum.STATE_LEA, RoleEnum.DISTRICT_LEA, RoleEnum.ANALYST
    ))
):
    """
    Generates an Alert strictly from an existing persisted Prediction ID.
    Enforces role authorization and complaint jurisdiction.
    """
    from backend.app.models.models import Prediction
    pred = db.query(Prediction).filter(Prediction.id == prediction_id).first()
    if not pred:
        raise HTTPException(status_code=404, detail="Prediction not found")

    complaint = db.query(Complaint).filter(Complaint.id == pred.complaint_id).first()
    if not complaint or not verify_complaint_access(complaint, current_user, db):
        raise HTTPException(status_code=404, detail="Prediction not found")

    alert = create_alert_for_prediction(db, prediction_id, user=current_user)

    # Safely broadcast via websocket
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
    current_user: User = Depends(require_roles(
        RoleEnum.I4C_ADMIN, RoleEnum.STATE_LEA, RoleEnum.DISTRICT_LEA, RoleEnum.ANALYST
    ))
):
    """
    Convenience endpoint to resolve latest prediction and generate alert.
    Requires role authorization and jurisdiction match.
    """
    if complaint_id.isdigit():
        complaint = db.query(Complaint).filter(Complaint.id == int(complaint_id)).first()
    else:
        complaint = db.query(Complaint).filter(Complaint.complaint_number == complaint_id).first()

    if not complaint or not verify_complaint_access(complaint, current_user, db):
        raise HTTPException(status_code=404, detail="Complaint not found")

    latest_pred = prediction_persistence_service.get_latest_prediction(db, complaint.id)
    if not latest_pred:
        raise HTTPException(
            status_code=404,
            detail=f"No persisted prediction available for complaint {complaint.complaint_number}."
        )

    alert = create_alert_for_prediction(db, latest_pred.id, user=current_user)

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
    current_user: User = Depends(require_roles(
        RoleEnum.I4C_ADMIN, RoleEnum.STATE_LEA, RoleEnum.DISTRICT_LEA, RoleEnum.BANK_OFFICER, RoleEnum.AUDITOR
    ))
):
    """
    Acknowledges an alert. Enforces jurisdiction check and records authoritative officer in AuditLog.
    """
    alert = db.query(Alert).filter(Alert.id == id).first()
    if not alert or not verify_alert_access(alert, current_user, db):
        raise HTTPException(status_code=404, detail="Alert not found")

    complaint = db.query(Complaint).filter(Complaint.id == alert.complaint_id).first()

    if alert.status != "ACKNOWLEDGED":
        alert.status = "ACKNOWLEDGED"
        alert.acknowledged_by = f"{current_user.full_name} ({current_user.role})"
        alert.acknowledged_at = datetime.utcnow()

    if data and data.notes:
        alert.action_notes = data.notes
    elif not alert.action_notes:
        alert.action_notes = "Dispatched field unit to ATM cluster perimeter"

    if complaint:
        complaint.case_status = "ALERTED"

    db.commit()
    db.refresh(alert)

    # Log authoritative audit event
    log_audit(
        db=db,
        user_id=current_user.id,
        officer_name=current_user.full_name,
        role=current_user.role,
        action="ALERT_ACKNOWLEDGED",
        case_number=complaint.complaint_number if complaint else f"CMP-{alert.complaint_id}",
        details=f"Alert #{alert.id} acknowledged for {alert.location_name}. Field unit notified."
    )

    try:
        await ws_manager.broadcast({
            "event": "ALERT_ACKNOWLEDGED",
            "alert_id": alert.id,
            "location": alert.location_name,
            "officer": alert.acknowledged_by
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


@router.post("/{id}/escalate", response_model=AlertResponse)
async def escalate_alert(
    id: int,
    data: Optional[AlertActionRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        RoleEnum.I4C_ADMIN, RoleEnum.STATE_LEA, RoleEnum.DISTRICT_LEA, RoleEnum.BANK_OFFICER
    ))
):
    """
    Escalates an alert to request an automated bank hold.
    Truthfully records a SIMULATED BankAction lifecycle entity.
    Never claims external completion without live core-banking integration.
    """
    alert = db.query(Alert).filter(Alert.id == id).first()
    if not alert or not verify_alert_access(alert, current_user, db):
        raise HTTPException(status_code=404, detail="Alert not found")

    complaint = db.query(Complaint).filter(Complaint.id == alert.complaint_id).first()

    user_note = data.notes if (data and data.notes) else None
    action = bank_action_service.create_or_get_hold_action(
        db=db,
        alert_id=alert.id,
        user=current_user,
        action_notes=user_note
    )

    # Log audit event for escalation
    log_audit(
        db=db,
        user_id=current_user.id,
        officer_name=current_user.full_name,
        role=current_user.role,
        action="ALERT_ESCALATED",
        case_number=complaint.complaint_number if complaint else f"CMP-{alert.complaint_id}",
        details=f"Alert #{alert.id} escalated. Simulated bank hold action {action.action_reference} generated (Status: {action.status})."
    )

    # Broadcast via websocket with truthful simulation indicator
    try:
        await ws_manager.broadcast({
            "event": "ALERT_ESCALATED",
            "alert_id": alert.id,
            "location": alert.location_name,
            "action": "SIMULATED_HOLD_REQUESTED",
            "action_reference": action.action_reference,
            "is_simulated": True
        })
    except Exception:
        pass

    db.refresh(alert)
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
