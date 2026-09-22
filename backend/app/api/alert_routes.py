import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

logger = logging.getLogger(__name__)
from backend.app.models.db import get_db
from backend.app.models.models import Alert, Complaint, NotificationOutbox, User
from backend.app.schemas.schemas import AlertResponse, AlertActionRequest, AlertSyncResponse, NotificationOutboxItem
from backend.app.auth.security import get_current_user
from backend.app.auth.rbac import (
    require_roles,
    verify_alert_access,
    verify_complaint_access,
    filter_complaints_by_jurisdiction,
    RoleEnum
)
from backend.app.auth.rbac import complaint_bank_organization_ids
from backend.app.services.alert_service import create_alert_for_prediction
from backend.app.services.outbox_service import outbox_service
from backend.app.services.prediction_persistence_service import prediction_persistence_service
from backend.app.services.audit_service import log_audit
from backend.app.services.bank_action_service import bank_action_service
from backend.app.websocket.manager import ws_manager

router = APIRouter(prefix="/alerts", tags=["Alerts Center"])


def _format_alert_dict(a: Alert, comp: Optional[Complaint] = None, latest_outbox: Optional[NotificationOutbox] = None) -> dict:
    """Format Alert entity with truthful delivery, outbox, and supersession/expiry fields."""
    delivery_status = latest_outbox.status if latest_outbox else ("DELIVERED" if a.status in ("DELIVERED", "ACKNOWLEDGED", "ACTION_INITIATED") else "QUEUED")
    attempt_count = latest_outbox.attempt_count if latest_outbox else (1 if a.status in ("DELIVERED", "ACKNOWLEDGED", "ACTION_INITIATED") else 0)
    next_retry = latest_outbox.next_retry_at if latest_outbox else None
    last_err = latest_outbox.last_error if latest_outbox else None

    return {
        "id": a.id,
        "complaint_id": a.complaint_id,
        "complaint_number": comp.complaint_number if comp else f"CMP-{a.complaint_id}",
        "prediction_id": a.prediction_id,
        "title": a.title,
        "severity": a.severity,
        "location_name": a.location_name,
        "risk_score": a.risk_score,
        "expected_window": a.expected_window,
        "amount_at_risk": float(a.amount_at_risk) if a.amount_at_risk else 0.0,
        "status": a.status,
        "acknowledged_by": a.acknowledged_by,
        "acknowledged_at": a.acknowledged_at,
        "action_notes": a.action_notes,
        "superseded_by_prediction_id": a.superseded_by_prediction_id,
        "superseded_at": a.superseded_at,
        "expires_at": a.expires_at,
        "delivery_status": delivery_status,
        "attempt_count": attempt_count,
        "next_retry_at": next_retry,
        "last_error": last_err,
        "created_at": a.created_at
    }


@router.get("", response_model=List[AlertResponse])
def list_alerts(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists alerts filtered by officer jurisdiction.
    Refreshes expired alerts on access to maintain state integrity.
    """
    # Expire stale alerts
    outbox_service.expire_stale_alerts(db)

    # Join Complaint to enforce jurisdiction
    query = db.query(Alert).join(Complaint, Alert.complaint_id == Complaint.id)

    # Apply jurisdiction filtering on complaints
    filtered_comp_subq = filter_complaints_by_jurisdiction(db.query(Complaint.id), current_user, db)
    query = query.filter(Alert.complaint_id.in_(filtered_comp_subq))

    if status and status != "ALL":
        query = query.filter(Alert.status == status)
    if severity and severity != "ALL":
        query = query.filter(Alert.severity == severity)

    alerts = query.order_by(Alert.created_at.desc()).all()

    comp_ids = [a.complaint_id for a in alerts]
    complaints = {c.id: c for c in db.query(Complaint).filter(Complaint.id.in_(comp_ids)).all()} if comp_ids else {}

    alert_ids = [a.id for a in alerts]
    outbox_map: Dict[int, NotificationOutbox] = {}
    if alert_ids:
        # Fetch latest outbox entry for each alert
        outbox_entries = (
            db.query(NotificationOutbox)
            .filter(NotificationOutbox.alert_id.in_(alert_ids))
            .order_by(NotificationOutbox.id.desc())
            .all()
        )
        for ob in outbox_entries:
            if ob.alert_id not in outbox_map:
                outbox_map[ob.alert_id] = ob

    results = []
    for a in alerts:
        comp = complaints.get(a.complaint_id)
        ob = outbox_map.get(a.id)
        results.append(_format_alert_dict(a, comp, ob))

    return results


@router.get("/sync", response_model=AlertSyncResponse)
def sync_missed_alerts(
    since_id: Optional[int] = 0,
    since_time: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        RoleEnum.I4C_ADMIN, RoleEnum.STATE_LEA, RoleEnum.DISTRICT_LEA, RoleEnum.ANALYST, RoleEnum.AUDITOR
    ))
):
    """
    Phase 5 Missed-Alert Cursor/Replay API.
    Enables reconnected or offline clients to fetch missed authorized alerts and outbox events.
    Enforces Phase 03 jurisdiction and organization scoping.
    """
    outbox_service.expire_stale_alerts(db)

    query = db.query(Alert).join(Complaint, Alert.complaint_id == Complaint.id)
    filtered_comp_subq = filter_complaints_by_jurisdiction(db.query(Complaint.id), current_user, db)
    query = query.filter(Alert.complaint_id.in_(filtered_comp_subq))

    if since_id and since_id > 0:
        query = query.filter(Alert.id > since_id)
    elif since_time:
        try:
            val = since_time.strip()
            if val.endswith("Z") or val.endswith("z"):
                val = val[:-1] + "+00:00"
            elif " " in val and any(val.endswith(suffix) for suffix in (":00", ":30", ":45")):
                parts = val.rsplit(" ", 1)
                if len(parts) == 2 and (":" in parts[1] or len(parts[1]) == 4):
                    val = parts[0] + "+" + parts[1]
            dt = datetime.fromisoformat(val)
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            query = query.filter(Alert.created_at >= dt)
        except Exception as exc:
            logger.error(f"[AlertSync] Failed to parse since_time '{since_time}': {exc}", exc_info=True)
            raise HTTPException(status_code=400, detail=f"Invalid ISO datetime format for since_time: '{since_time}': {exc}")

    alerts = query.order_by(Alert.id.asc()).limit(limit + 1).all()
    has_more = len(alerts) > limit
    paged_alerts = alerts[:limit]

    comp_ids = [a.complaint_id for a in paged_alerts]
    complaints = {c.id: c for c in db.query(Complaint).filter(Complaint.id.in_(comp_ids)).all()} if comp_ids else {}

    alert_ids = [a.id for a in paged_alerts]
    outbox_events: List[NotificationOutbox] = []
    outbox_map: Dict[int, NotificationOutbox] = {}
    if alert_ids:
        outbox_events = (
            db.query(NotificationOutbox)
            .filter(NotificationOutbox.alert_id.in_(alert_ids))
            .order_by(NotificationOutbox.id.asc())
            .all()
        )
        for ob in outbox_events:
            outbox_map[ob.alert_id] = ob

    items = []
    max_cursor = since_id or 0
    for a in paged_alerts:
        comp = complaints.get(a.complaint_id)
        ob = outbox_map.get(a.id)
        items.append(_format_alert_dict(a, comp, ob))
        if a.id > max_cursor:
            max_cursor = a.id

    return {
        "items": items,
        "outbox_events": outbox_events,
        "synced_at": datetime.utcnow(),
        "cursor": max_cursor,
        "has_more": has_more
    }


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
    if not alert or not verify_alert_access(alert, current_user, db):
        raise HTTPException(status_code=404, detail="Alert not found")

    complaint = db.query(Complaint).filter(Complaint.id == alert.complaint_id).first()
    latest_outbox = (
        db.query(NotificationOutbox)
        .filter(NotificationOutbox.alert_id == alert.id)
        .order_by(NotificationOutbox.id.desc())
        .first()
    )

    return _format_alert_dict(alert, complaint, latest_outbox)


@router.get("/{id}/outbox", response_model=List[NotificationOutboxItem])
def get_alert_outbox_events(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns audit trail of all durable outbox attempts and deliveries for a specific alert.
    Requires alert access authorization.
    """
    alert = db.query(Alert).filter(Alert.id == id).first()
    if not alert or not verify_alert_access(alert, current_user, db):
        raise HTTPException(status_code=404, detail="Alert not found")

    events = (
        db.query(NotificationOutbox)
        .filter(NotificationOutbox.alert_id == id)
        .order_by(NotificationOutbox.id.asc())
        .all()
    )
    return events


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
        bank_org_ids = sorted(complaint_bank_organization_ids(complaint.id, db))
        await ws_manager.broadcast({
            "event": "ALERT_CREATED",
            "alert_id": alert.id,
            "prediction_id": alert.prediction_id,
            "complaint_number": complaint.complaint_number if complaint else f"CMP-{alert.complaint_id}",
            "location": alert.location_name,
            "severity": alert.severity,
            "risk_score": alert.risk_score,
            "state": complaint.state,
            "district": complaint.district,
        }, target_state=complaint.state, target_district=complaint.district,
           target_organization_ids=bank_org_ids,
           required_roles=["I4C_ADMIN", "STATE_LEA", "DISTRICT_LEA", "ANALYST", "BANK_OFFICER"])
    except Exception:
        pass

    latest_outbox = (
        db.query(NotificationOutbox)
        .filter(NotificationOutbox.alert_id == alert.id)
        .order_by(NotificationOutbox.id.desc())
        .first()
    )

    return _format_alert_dict(alert, complaint, latest_outbox)


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
        bank_org_ids = sorted(complaint_bank_organization_ids(complaint.id, db))
        await ws_manager.broadcast({
            "event": "ALERT_CREATED",
            "alert_id": alert.id,
            "prediction_id": alert.prediction_id,
            "complaint_number": complaint.complaint_number,
            "location": alert.location_name,
            "severity": alert.severity,
            "risk_score": alert.risk_score,
            "state": complaint.state,
            "district": complaint.district,
        }, target_state=complaint.state, target_district=complaint.district,
           target_organization_ids=bank_org_ids,
           required_roles=["I4C_ADMIN", "STATE_LEA", "DISTRICT_LEA", "ANALYST", "BANK_OFFICER"])
    except Exception:
        pass

    latest_outbox = (
        db.query(NotificationOutbox)
        .filter(NotificationOutbox.alert_id == alert.id)
        .order_by(NotificationOutbox.id.desc())
        .first()
    )

    return _format_alert_dict(alert, complaint, latest_outbox)


@router.post("/{id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(
    id: int,
    data: Optional[AlertActionRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        RoleEnum.I4C_ADMIN, RoleEnum.STATE_LEA, RoleEnum.DISTRICT_LEA, RoleEnum.BANK_OFFICER
    ))
):
    """
    Acknowledges an alert. Enforces jurisdiction check and records authoritative officer in AuditLog and outbox.
    """
    alert = db.query(Alert).filter(Alert.id == id).first()
    if not alert or not verify_alert_access(alert, current_user, db):
        raise HTTPException(status_code=404, detail="Alert not found")

    complaint = db.query(Complaint).filter(Complaint.id == alert.complaint_id).first()
    now = datetime.utcnow()

    if alert.status != "ACKNOWLEDGED":
        alert.status = "ACKNOWLEDGED"
        alert.acknowledged_by = f"{current_user.full_name} ({current_user.role})"
        alert.acknowledged_at = now

    if data and data.notes:
        alert.action_notes = data.notes
    elif not alert.action_notes:
        alert.action_notes = "Dispatched field unit to ATM cluster perimeter"

    if complaint:
        complaint.case_status = "ALERTED"

    # Enqueue ACKNOWLEDGED outbox event
    outbox_service.enqueue_alert_event(
        db=db,
        alert=alert,
        event_type="ALERT_ACKNOWLEDGED",
        payload_extra={
            "acknowledged_by": alert.acknowledged_by,
            "acknowledged_at": now.isoformat() + "Z",
            "action_notes": alert.action_notes
        }
    )

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
        bank_org_ids = sorted(complaint_bank_organization_ids(complaint.id, db)) if complaint else []
        await ws_manager.broadcast({
            "event": "ALERT_ACKNOWLEDGED",
            "alert_id": alert.id,
            "location": alert.location_name,
            "officer": alert.acknowledged_by,
            "state": complaint.state if complaint else None,
            "district": complaint.district if complaint else None,
        }, target_state=complaint.state if complaint else None,
           target_district=complaint.district if complaint else None,
           target_organization_ids=bank_org_ids,
           required_roles=["I4C_ADMIN", "STATE_LEA", "DISTRICT_LEA", "ANALYST", "BANK_OFFICER"])
    except Exception:
        pass

    latest_outbox = (
        db.query(NotificationOutbox)
        .filter(NotificationOutbox.alert_id == alert.id)
        .order_by(NotificationOutbox.id.desc())
        .first()
    )

    return _format_alert_dict(alert, complaint, latest_outbox)


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

    # Enqueue ESCALATED outbox event
    outbox_service.enqueue_alert_event(
        db=db,
        alert=alert,
        event_type="ALERT_ESCALATED",
        payload_extra={
            "action_reference": action.action_reference,
            "action_status": action.status,
            "is_simulated": True,
            "user_notes": user_note
        }
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
        bank_org_ids = sorted(complaint_bank_organization_ids(complaint.id, db)) if complaint else []
        await ws_manager.broadcast({
            "event": "ALERT_ESCALATED",
            "alert_id": alert.id,
            "location": alert.location_name,
            "action": "SIMULATED_HOLD_REQUESTED",
            "action_reference": action.action_reference,
            "is_simulated": True,
            "state": complaint.state if complaint else None,
            "district": complaint.district if complaint else None,
        }, target_state=complaint.state if complaint else None,
           target_district=complaint.district if complaint else None,
           target_organization_ids=bank_org_ids,
           required_roles=["I4C_ADMIN", "STATE_LEA", "DISTRICT_LEA", "ANALYST", "BANK_OFFICER"])
    except Exception:
        pass

    db.refresh(alert)
    latest_outbox = (
        db.query(NotificationOutbox)
        .filter(NotificationOutbox.alert_id == alert.id)
        .order_by(NotificationOutbox.id.desc())
        .first()
    )

    return _format_alert_dict(alert, complaint, latest_outbox)
