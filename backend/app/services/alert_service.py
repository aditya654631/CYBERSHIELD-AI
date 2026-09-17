import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from backend.app.models.models import Alert, Complaint, Prediction, PredictionLocation, LocationCluster, User
from backend.app.services.audit_service import log_audit

logger = logging.getLogger(__name__)


def format_window_ist(start_dt: datetime, end_dt: datetime) -> str:
    """Formats start and end UTC datetimes into an IST window string with explicit IST label.
    Includes full dates if window crosses midnight in IST."""
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    s_utc = start_dt.replace(tzinfo=timezone.utc) if start_dt.tzinfo is None else start_dt.astimezone(timezone.utc)
    e_utc = end_dt.replace(tzinfo=timezone.utc) if end_dt.tzinfo is None else end_dt.astimezone(timezone.utc)
    s_ist = s_utc.astimezone(ist_tz)
    e_ist = e_utc.astimezone(ist_tz)
    if s_ist.date() == e_ist.date():
        return f"{s_ist.strftime('%d %b %Y, %H:%M')}–{e_ist.strftime('%H:%M')} IST (Operational Estimate Window)"
    return f"{s_ist.strftime('%d %b %Y, %H:%M')} IST – {e_ist.strftime('%d %b %Y, %H:%M')} IST (Operational Estimate Window)"


def create_alert_for_prediction(
    db: Session,
    prediction_id: int,
    officer_name: Optional[str] = None,
    user: Optional[User] = None
) -> Alert:
    """
    Creates an Alert strictly derived from an EXISTING persisted Prediction.
    
    Invariants:
    1. Caller provides exact prediction_id.
    2. Zero ML inference invocation (read-only from persisted Prediction & PredictionLocation).
    3. Zero Withdrawal ground-truth access.
    4. Prediction.primary_cluster_id == PredictionLocation[rank=1].cluster_id.
    5. Location name and coordinates originate from LocationCluster matching Rank 1.
    6. Idempotent: One active alert per prediction_id. Repeated requests return existing alert.
    7. Atomic commit: Alert only, zero mutations to Prediction or other core tables.
    """
    # 1. Fetch exact persisted Prediction
    prediction = db.query(Prediction).filter(Prediction.id == prediction_id).first()
    if not prediction:
        raise HTTPException(
            status_code=404,
            detail=f"Persisted prediction with ID {prediction_id} not found."
        )

    # 2. Verify eligibility (trained_ml or deterministic_demo)
    if prediction.prediction_mode not in ("trained_ml", "deterministic_demo"):
        raise HTTPException(
            status_code=400,
            detail=f"Prediction #{prediction_id} has mode '{prediction.prediction_mode}'. "
                   f"Alerts can only be generated for successful 'trained_ml' or 'deterministic_demo' predictions."
        )

    # 3. Fetch complaint
    complaint = db.query(Complaint).filter(Complaint.id == prediction.complaint_id).first()
    if not complaint:
        raise HTTPException(
            status_code=404,
            detail=f"Complaint ID {prediction.complaint_id} associated with prediction #{prediction_id} not found."
        )

    # 4. Duplicate prevention / Idempotency Check
    # If an alert already exists for this exact prediction_id and is active/unresolved, return it
    existing_alert = (
        db.query(Alert)
        .filter(
            Alert.prediction_id == prediction.id,
            Alert.status.in_(["NEW", "ACKNOWLEDGED", "ACTION_INITIATED"])
        )
        .order_by(Alert.created_at.desc())
        .first()
    )
    if existing_alert:
        logger.info(
            f"[AlertService] Reusing existing Alert #{existing_alert.id} for Prediction #{prediction.id} "
            f"({complaint.complaint_number})."
        )
        return existing_alert

    # 5. Fetch Rank-1 Location and enforce Primary Cluster Invariant
    locations = (
        db.query(PredictionLocation)
        .filter(PredictionLocation.prediction_id == prediction.id)
        .order_by(PredictionLocation.rank.asc())
        .all()
    )
    if not locations or len(locations) < 1:
        raise HTTPException(
            status_code=409,
            detail=f"Prediction #{prediction_id} has no associated PredictionLocation records."
        )

    rank1_loc = locations[0]
    if rank1_loc.rank != 1:
        raise HTTPException(
            status_code=409,
            detail=f"Data integrity error: first location for prediction #{prediction_id} has rank {rank1_loc.rank}, expected 1."
        )

    # Primary cluster invariant: prediction.primary_cluster_id == rank1_loc.cluster_id
    if prediction.primary_cluster_id is not None and prediction.primary_cluster_id != rank1_loc.cluster_id:
        raise HTTPException(
            status_code=409,
            detail=f"Data integrity mismatch: Prediction.primary_cluster_id ({prediction.primary_cluster_id}) "
                   f"!= PredictionLocation rank-1 cluster_id ({rank1_loc.cluster_id})."
        )

    # Verify cluster exists in LocationCluster
    if rank1_loc.cluster_id:
        cluster_row = db.query(LocationCluster).filter(LocationCluster.id == rank1_loc.cluster_id).first()
        if not cluster_row:
            raise HTTPException(
                status_code=409,
                detail=f"Location cluster ID {rank1_loc.cluster_id} not found in database."
            )
        location_name = cluster_row.cluster_name
    else:
        location_name = rank1_loc.location_name

    # 6. Severity & Risk mapping from persisted fields
    # Use rank1 risk_level if set, or map from intervention_priority
    if rank1_loc.risk_level:
        severity = str(rank1_loc.risk_level).upper()
    elif prediction.intervention_priority is not None:
        if prediction.intervention_priority == 1:
            severity = "CRITICAL"
        elif prediction.intervention_priority == 2:
            severity = "HIGH"
        else:
            severity = "MEDIUM"
    else:
        severity = "HIGH"

    if severity not in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        severity = "HIGH"

    # Risk score from calibrated probability or rank1 probability
    risk_score = float(rank1_loc.probability if rank1_loc.probability is not None else 0.5)

    # Operational estimate window formatted in IST (+05:30)
    if prediction.predicted_window_start and prediction.predicted_window_end:
        expected_window = format_window_ist(prediction.predicted_window_start, prediction.predicted_window_end)
    elif prediction.window_label:
        expected_window = f"{prediction.window_label} (Operational Estimate Window)"
    else:
        expected_window = "Next 2–4 Hours (Operational Estimate Window)"

    amount_at_risk = float(complaint.amount) if complaint.amount else 0.0

    # 7. Construct Alert entity
    title = f"ACTIONABLE ALERT: {location_name} ({complaint.complaint_number})"
    if prediction.prediction_mode == "deterministic_demo":
        title = f"[DEMO] ACTIONABLE ALERT: {location_name} ({complaint.complaint_number})"

    alert = Alert(
        complaint_id=complaint.id,
        prediction_id=prediction.id,
        title=title,
        severity=severity,
        location_name=location_name,
        risk_score=risk_score,
        expected_window=expected_window,
        amount_at_risk=amount_at_risk,
        status="NEW",
        created_at=datetime.utcnow()
    )

    try:
        db.add(alert)
        db.commit()
        db.refresh(alert)
        logger.info(
            f"[AlertService] Successfully created Alert #{alert.id} for Prediction #{prediction.id} "
            f"({complaint.complaint_number}) at {location_name}."
        )

        # Log audit with authoritative user identity when available
        audit_uid = user.id if user else None
        audit_officer = user.full_name if user else (officer_name or "System Dispatcher")
        audit_role = user.role if user else "PREDICTIVE_DISPATCH"
        log_audit(
            db=db,
            user_id=audit_uid,
            officer_name=audit_officer,
            role=audit_role,
            action="ALERT_CREATED",
            case_number=complaint.complaint_number,
            details=f"Alert #{alert.id} generated for {complaint.complaint_number} referencing Prediction #{prediction.id}."
        )
        return alert

    except Exception as exc:
        db.rollback()
        logger.error(
            f"[AlertService] Failed to create Alert for Prediction #{prediction.id}: {exc}",
            exc_info=True
        )
        raise

