"""
CyberShield AI — Phase 9: Outcome Observation Service

Handles creation, correction, and querying of outcome observations.
Enforces the pre-committed prediction evaluation policy:
  LAST_OPERATIONAL_BEFORE_EVENT — selects the last Prediction with
  analysis_purpose='OPERATIONAL' created strictly before observed_event_time
  for the same complaint. Never cherry-picks the best prediction after seeing
  the outcome.

Denominator rules enforced in metrics:
  - CONFIRMED_CASHOUT and NO_OBSERVED_CASHOUT → measured cohort
  - UNKNOWN → excluded from success/failure, counted in unknown denominator
  - DATA_EXCLUDED → excluded cohort, reason required
  - is_synthetic=True → synthetic cohort, never mixed with real outcomes
  - verified_held_amount_inr and actual_recovered_amount_inr reported separately
"""

import math
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc
from fastapi import HTTPException, status

from backend.app.models.models import (
    OutcomeObservation, Complaint, Prediction, PredictionLocation,
    Alert, BankAction, AuditLog, User, LocationCluster,
)
from backend.app.services.audit_service import log_audit
from backend.app.auth.rbac import verify_complaint_access


VALID_OUTCOME_TYPES = {
    "CONFIRMED_CASHOUT",
    "MULTIPLE_CASHOUT",
    "NO_OBSERVED_CASHOUT",
    "UNKNOWN",
    "DATA_EXCLUDED",
}

VALID_SOURCES = {
    "OFFICER_MANUAL",
    "CFCFRMS_IMPORT",
    "BANK_REPORT",
    "COURT_RECORD",
    "AUTOMATED_MONITORING",
}

VALID_VERIFICATION_STATUSES = {"VERIFIED", "UNVERIFIED", "PENDING_VERIFICATION"}

# Outcome types that contribute to the success/failure measured denominator
MEASURED_OUTCOME_TYPES = {"CONFIRMED_CASHOUT", "NO_OBSERVED_CASHOUT", "MULTIPLE_CASHOUT"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine great-circle distance in kilometres."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _select_eligible_prediction(
    db: Session,
    complaint_id: int,
    observed_event_time: Optional[datetime],
) -> Optional[Prediction]:
    """
    PREDICTION EVALUATION POLICY: LAST_OPERATIONAL_BEFORE_EVENT.
    Returns the last Prediction with analysis_purpose='OPERATIONAL' created
    strictly before observed_event_time for the given complaint.
    If observed_event_time is None or no eligible prediction exists, returns None.
    """
    if observed_event_time is None:
        return None
    return (
        db.query(Prediction)
        .filter(
            Prediction.complaint_id == complaint_id,
            Prediction.analysis_purpose == "OPERATIONAL",
            Prediction.created_at < observed_event_time,
        )
        .order_by(desc(Prediction.created_at))
        .first()
    )


def _compute_prediction_rank(
    db: Session,
    prediction: Prediction,
    actual_lat: Optional[float],
    actual_lon: Optional[float],
) -> Optional[int]:
    """Find which rank position the actual cashout cluster appears at in the prediction.
    Returns None if no location data or actual location doesn't match any predicted cluster."""
    if prediction is None or actual_lat is None or actual_lon is None:
        return None

    locs = (
        db.query(PredictionLocation)
        .filter(PredictionLocation.prediction_id == prediction.id)
        .order_by(PredictionLocation.rank)
        .all()
    )
    if not locs:
        return None

    # Find the closest cluster centroid to the actual cashout location
    best_rank = None
    best_dist = float("inf")
    for loc in locs:
        if loc.latitude is None or loc.longitude is None:
            # Try via cluster
            if loc.cluster_id:
                cluster = db.query(LocationCluster).filter(LocationCluster.id == loc.cluster_id).first()
                if cluster:
                    d = _haversine_km(actual_lat, actual_lon, cluster.center_lat, cluster.center_lon)
                    if d < best_dist:
                        best_dist = d
                        best_rank = loc.rank
            continue
        d = _haversine_km(actual_lat, actual_lon, loc.latitude, loc.longitude)
        if d < best_dist:
            best_dist = d
            best_rank = loc.rank

    # Only count as a match if within 10 km of some predicted location
    return best_rank if best_dist <= 10.0 else None


def _compute_distance_error(
    db: Session,
    prediction: Prediction,
    actual_lat: Optional[float],
    actual_lon: Optional[float],
) -> Optional[float]:
    """Haversine distance between rank-1 predicted cluster centroid and actual cashout (km)."""
    if prediction is None or actual_lat is None or actual_lon is None:
        return None

    rank1 = (
        db.query(PredictionLocation)
        .filter(
            PredictionLocation.prediction_id == prediction.id,
            PredictionLocation.rank == 1,
        )
        .first()
    )
    if not rank1:
        return None

    pred_lat = rank1.latitude
    pred_lon = rank1.longitude
    if pred_lat is None or pred_lon is None:
        if rank1.cluster_id:
            cluster = db.query(LocationCluster).filter(LocationCluster.id == rank1.cluster_id).first()
            if cluster:
                pred_lat, pred_lon = cluster.center_lat, cluster.center_lon

    if pred_lat is None or pred_lon is None:
        return None

    return round(_haversine_km(actual_lat, actual_lon, pred_lat, pred_lon), 3)


def _minutes_between(t1: Optional[datetime], t2: Optional[datetime]) -> Optional[float]:
    if t1 is None or t2 is None:
        return None
    if t1.tzinfo is not None:
        t1 = t1.astimezone(timezone.utc).replace(tzinfo=None)
    if t2.tzinfo is not None:
        t2 = t2.astimezone(timezone.utc).replace(tzinfo=None)
    diff = (t2 - t1).total_seconds() / 60.0
    return round(diff, 2)


def create_outcome(
    db: Session,
    current_user: User,
    complaint_id: int,
    outcome_type: str,
    source: str,
    observed_event_time: Optional[datetime] = None,
    actual_lat: Optional[float] = None,
    actual_lon: Optional[float] = None,
    actual_location_name: Optional[str] = None,
    actual_withdrawal_amount_inr: Optional[float] = None,
    cashout_events: Optional[list] = None,
    actual_atm_id: Optional[int] = None,
    actual_cluster_id: Optional[int] = None,
    linked_alert_id: Optional[int] = None,
    linked_bank_action_id: Optional[int] = None,
    verified_held_amount_inr: Optional[float] = None,
    verified_released_amount_inr: Optional[float] = None,
    actual_recovered_amount_inr: Optional[float] = None,
    recovery_verified_by: Optional[str] = None,
    recovery_verified_at: Optional[datetime] = None,
    verifier_user_id: Optional[int] = None,
    verification_status: str = "PENDING_VERIFICATION",
    is_synthetic: bool = False,
    is_excluded: bool = False,
    exclusion_reason: Optional[str] = None,
    notes: Optional[str] = None,
) -> OutcomeObservation:
    """Create a new outcome observation. Prediction is linked by policy — never manually."""

    # Validate complaint access
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    if outcome_type not in VALID_OUTCOME_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid outcome_type. Must be one of: {sorted(VALID_OUTCOME_TYPES)}")
    if source not in VALID_SOURCES:
        raise HTTPException(status_code=400, detail=f"Invalid source. Must be one of: {sorted(VALID_SOURCES)}")
    if verification_status not in VALID_VERIFICATION_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid verification_status. Must be one of: {sorted(VALID_VERIFICATION_STATUSES)}")
    if is_excluded and not exclusion_reason:
        raise HTTPException(status_code=400, detail="exclusion_reason is required when is_excluded=True")
    if outcome_type == "DATA_EXCLUDED" and not is_excluded:
        is_excluded = True
        if not exclusion_reason:
            raise HTTPException(status_code=400, detail="exclusion_reason is required for DATA_EXCLUDED outcome_type")

    # ── PREDICTION EVALUATION POLICY ──────────────────────────────────────────
    # Select last OPERATIONAL prediction created STRICTLY BEFORE observed_event_time.
    # This is done server-side with no client input. Never cherry-picked from outcome.
    eligible_prediction = _select_eligible_prediction(db, complaint_id, observed_event_time)
    linked_prediction_id = eligible_prediction.id if eligible_prediction else None
    linked_prediction_version = eligible_prediction.version_number if eligible_prediction else None

    # ── DERIVE METRICS ─────────────────────────────────────────────────────────
    prediction_rank_matched = None
    distance_error_km = None
    prediction_lead_time_minutes = None
    alert_lead_time_minutes = None
    alert_acknowledgement_latency_minutes = None
    bank_response_latency_minutes = None

    if eligible_prediction:
        prediction_rank_matched = _compute_prediction_rank(db, eligible_prediction, actual_lat, actual_lon)
        distance_error_km = _compute_distance_error(db, eligible_prediction, actual_lat, actual_lon)
        prediction_lead_time_minutes = _minutes_between(eligible_prediction.created_at, observed_event_time)

    # Alert metrics
    alert_obj = None
    if linked_alert_id:
        alert_obj = db.query(Alert).filter(Alert.id == linked_alert_id).first()
    elif eligible_prediction:
        # Try to find the most recent alert linked to the eligible prediction
        alert_obj = (
            db.query(Alert)
            .filter(
                Alert.prediction_id == eligible_prediction.id,
                Alert.complaint_id == complaint_id,
            )
            .order_by(desc(Alert.created_at))
            .first()
        )
        if alert_obj:
            linked_alert_id = alert_obj.id

    if alert_obj:
        alert_lead_time_minutes = _minutes_between(alert_obj.created_at, observed_event_time)
        alert_acknowledgement_latency_minutes = _minutes_between(alert_obj.created_at, alert_obj.acknowledged_at)

    # Bank action metrics
    bank_action_obj = None
    if linked_bank_action_id:
        bank_action_obj = db.query(BankAction).filter(BankAction.id == linked_bank_action_id).first()
    if bank_action_obj:
        bank_response_latency_minutes = _minutes_between(bank_action_obj.requested_at, bank_action_obj.held_at)
        # Copy verified held amount from bank action if not explicitly provided
        if verified_held_amount_inr is None and bank_action_obj.held_amount:
            verified_held_amount_inr = float(bank_action_obj.held_amount)

    # ── VERIFIER ATTRIBUTION ───────────────────────────────────────────────────
    verifier_name = None
    verifier_role = None
    if verifier_user_id:
        verifier_user = db.query(User).filter(User.id == verifier_user_id).first()
        if verifier_user:
            verifier_name = verifier_user.full_name
            verifier_role = verifier_user.role

    # ── AUTO-DETECT SYNTHETIC FROM COMPLAINT ──────────────────────────────────
    if not is_synthetic:
        provenance = (complaint.provenance_mode or "").upper()
        is_synthetic = provenance in ("DEMO", "SYNTHETIC", "SEEDED", "TEST")

    now = _utcnow()
    outcome = OutcomeObservation(
        complaint_id=complaint_id,
        linked_prediction_id=linked_prediction_id,
        linked_prediction_version=linked_prediction_version,
        prediction_selection_policy="LAST_OPERATIONAL_BEFORE_EVENT",
        linked_alert_id=linked_alert_id,
        linked_bank_action_id=linked_bank_action_id,
        outcome_type=outcome_type,
        observed_event_time=observed_event_time,
        actual_atm_id=actual_atm_id,
        actual_cluster_id=actual_cluster_id,
        actual_lat=actual_lat,
        actual_lon=actual_lon,
        actual_location_name=actual_location_name,
        actual_withdrawal_amount_inr=actual_withdrawal_amount_inr,
        cashout_events=cashout_events,
        verified_held_amount_inr=verified_held_amount_inr,
        verified_released_amount_inr=verified_released_amount_inr,
        actual_recovered_amount_inr=actual_recovered_amount_inr,
        recovery_verified_by=recovery_verified_by,
        recovery_verified_at=recovery_verified_at,
        prediction_rank_matched=prediction_rank_matched,
        distance_error_km=distance_error_km,
        prediction_lead_time_minutes=prediction_lead_time_minutes,
        alert_lead_time_minutes=alert_lead_time_minutes,
        alert_acknowledgement_latency_minutes=alert_acknowledgement_latency_minutes,
        bank_response_latency_minutes=bank_response_latency_minutes,
        is_synthetic=is_synthetic,
        is_excluded=is_excluded,
        exclusion_reason=exclusion_reason,
        verification_status=verification_status,
        source=source,
        verifier_user_id=verifier_user_id,
        verifier_name=verifier_name,
        verifier_role=verifier_role,
        ingested_by_user_id=current_user.id,
        ingested_by_role=current_user.role,
        received_at=now,
        version=1,
        corrects_outcome_id=None,
        record_status="ACTIVE",
        correction_reason=None,
        notes=notes,
        created_at=now,
        updated_at=now,
    )
    db.add(outcome)
    db.flush()

    log_audit(
        db=db,
        user_id=getattr(current_user, "id", None),
        officer_name=getattr(current_user, "full_name", getattr(current_user, "username", "SYSTEM")),
        role=getattr(current_user, "role", "UNKNOWN"),
        action="OUTCOME_INGESTED",
        case_number=complaint.complaint_number,
        details=(
            f"OutcomeObservation id={outcome.id} created: "
            f"type={outcome_type}, source={source}, "
            f"synthetic={is_synthetic}, linked_pred_id={linked_prediction_id}"
        ),
    )
    db.commit()
    db.refresh(outcome)
    return outcome


def correct_outcome(
    db: Session,
    current_user: User,
    outcome_id: int,
    correction_reason: str,
    outcome_type: Optional[str] = None,
    source: Optional[str] = None,
    observed_event_time: Optional[datetime] = None,
    actual_lat: Optional[float] = None,
    actual_lon: Optional[float] = None,
    actual_location_name: Optional[str] = None,
    actual_withdrawal_amount_inr: Optional[float] = None,
    cashout_events: Optional[list] = None,
    actual_atm_id: Optional[int] = None,
    actual_cluster_id: Optional[int] = None,
    linked_alert_id: Optional[int] = None,
    linked_bank_action_id: Optional[int] = None,
    verified_held_amount_inr: Optional[float] = None,
    verified_released_amount_inr: Optional[float] = None,
    actual_recovered_amount_inr: Optional[float] = None,
    recovery_verified_by: Optional[str] = None,
    recovery_verified_at: Optional[datetime] = None,
    verifier_user_id: Optional[int] = None,
    verification_status: Optional[str] = None,
    is_excluded: Optional[bool] = None,
    exclusion_reason: Optional[str] = None,
    notes: Optional[str] = None,
) -> OutcomeObservation:
    """
    Correct an outcome by superseding the old record and creating a new active one.
    The original record is marked SUPERSEDED but never deleted (append-only lineage).
    """
    if not correction_reason or not correction_reason.strip():
        raise HTTPException(status_code=400, detail="correction_reason is required for outcome corrections")

    original = db.query(OutcomeObservation).filter(OutcomeObservation.id == outcome_id).first()
    if not original:
        raise HTTPException(status_code=404, detail="OutcomeObservation not found")
    if original.record_status != "ACTIVE":
        raise HTTPException(status_code=409, detail="Cannot correct a SUPERSEDED outcome; correct the latest ACTIVE version")

    # Inherit unchanged fields from original
    new_outcome_type = outcome_type or original.outcome_type
    new_source = source or original.source
    new_observed_event_time = observed_event_time if observed_event_time is not None else original.observed_event_time
    new_actual_lat = actual_lat if actual_lat is not None else original.actual_lat
    new_actual_lon = actual_lon if actual_lon is not None else original.actual_lon
    new_verification_status = verification_status or original.verification_status
    new_is_excluded = is_excluded if is_excluded is not None else original.is_excluded
    new_exclusion_reason = exclusion_reason if exclusion_reason is not None else original.exclusion_reason

    # Validation
    if new_outcome_type not in VALID_OUTCOME_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid outcome_type: {new_outcome_type}")
    if new_is_excluded and not new_exclusion_reason:
        raise HTTPException(status_code=400, detail="exclusion_reason required when is_excluded=True")

    # Re-apply prediction evaluation policy on new observed_event_time (if changed)
    if observed_event_time is not None and observed_event_time != original.observed_event_time:
        eligible_prediction = _select_eligible_prediction(db, original.complaint_id, new_observed_event_time)
        new_linked_pred_id = eligible_prediction.id if eligible_prediction else None
        new_linked_pred_version = eligible_prediction.version_number if eligible_prediction else None
    else:
        new_linked_pred_id = original.linked_prediction_id
        new_linked_pred_version = original.linked_prediction_version

    # Recompute derived metrics
    eligible_pred = None
    if new_linked_pred_id:
        eligible_pred = db.query(Prediction).filter(Prediction.id == new_linked_pred_id).first()

    prediction_rank_matched = _compute_prediction_rank(db, eligible_pred, new_actual_lat, new_actual_lon)
    distance_error_km = _compute_distance_error(db, eligible_pred, new_actual_lat, new_actual_lon)
    prediction_lead_time_minutes = _minutes_between(eligible_pred.created_at if eligible_pred else None, new_observed_event_time)

    new_linked_alert_id = linked_alert_id if linked_alert_id is not None else original.linked_alert_id
    alert_obj = None
    if new_linked_alert_id:
        alert_obj = db.query(Alert).filter(Alert.id == new_linked_alert_id).first()
    alert_lead_time_minutes = _minutes_between(alert_obj.created_at if alert_obj else None, new_observed_event_time)
    alert_acknowledgement_latency_minutes = _minutes_between(
        alert_obj.created_at if alert_obj else None,
        alert_obj.acknowledged_at if alert_obj else None,
    )

    new_linked_bank_action_id = linked_bank_action_id if linked_bank_action_id is not None else original.linked_bank_action_id
    bank_action_obj = None
    if new_linked_bank_action_id:
        bank_action_obj = db.query(BankAction).filter(BankAction.id == new_linked_bank_action_id).first()
    bank_response_latency_minutes = _minutes_between(
        bank_action_obj.requested_at if bank_action_obj else None,
        bank_action_obj.held_at if bank_action_obj else None,
    )

    # Verifier attribution
    new_verifier_name = original.verifier_name
    new_verifier_role = original.verifier_role
    new_verifier_user_id = verifier_user_id if verifier_user_id is not None else original.verifier_user_id
    if verifier_user_id:
        v = db.query(User).filter(User.id == verifier_user_id).first()
        if v:
            new_verifier_name = v.full_name
            new_verifier_role = v.role

    now = _utcnow()

    # Mark original as SUPERSEDED (update only record_status; all data preserved)
    original.record_status = "SUPERSEDED"
    original.updated_at = now
    db.flush()

    corrected = OutcomeObservation(
        complaint_id=original.complaint_id,
        linked_prediction_id=new_linked_pred_id,
        linked_prediction_version=new_linked_pred_version,
        prediction_selection_policy=original.prediction_selection_policy,
        linked_alert_id=new_linked_alert_id,
        linked_bank_action_id=new_linked_bank_action_id,
        outcome_type=new_outcome_type,
        observed_event_time=new_observed_event_time,
        actual_atm_id=actual_atm_id if actual_atm_id is not None else original.actual_atm_id,
        actual_cluster_id=actual_cluster_id if actual_cluster_id is not None else original.actual_cluster_id,
        actual_lat=new_actual_lat,
        actual_lon=new_actual_lon,
        actual_location_name=actual_location_name if actual_location_name is not None else original.actual_location_name,
        actual_withdrawal_amount_inr=actual_withdrawal_amount_inr if actual_withdrawal_amount_inr is not None else original.actual_withdrawal_amount_inr,
        cashout_events=cashout_events if cashout_events is not None else original.cashout_events,
        verified_held_amount_inr=verified_held_amount_inr if verified_held_amount_inr is not None else original.verified_held_amount_inr,
        verified_released_amount_inr=verified_released_amount_inr if verified_released_amount_inr is not None else original.verified_released_amount_inr,
        actual_recovered_amount_inr=actual_recovered_amount_inr if actual_recovered_amount_inr is not None else original.actual_recovered_amount_inr,
        recovery_verified_by=recovery_verified_by if recovery_verified_by is not None else original.recovery_verified_by,
        recovery_verified_at=recovery_verified_at if recovery_verified_at is not None else original.recovery_verified_at,
        prediction_rank_matched=prediction_rank_matched,
        distance_error_km=distance_error_km,
        prediction_lead_time_minutes=prediction_lead_time_minutes,
        alert_lead_time_minutes=alert_lead_time_minutes,
        alert_acknowledgement_latency_minutes=alert_acknowledgement_latency_minutes,
        bank_response_latency_minutes=bank_response_latency_minutes,
        is_synthetic=original.is_synthetic,
        is_excluded=new_is_excluded,
        exclusion_reason=new_exclusion_reason,
        verification_status=new_verification_status,
        source=new_source,
        verifier_user_id=new_verifier_user_id,
        verifier_name=new_verifier_name,
        verifier_role=new_verifier_role,
        ingested_by_user_id=current_user.id,
        ingested_by_role=current_user.role,
        received_at=original.received_at,  # Original intake time preserved
        version=original.version + 1,
        corrects_outcome_id=original.id,
        record_status="ACTIVE",
        correction_reason=correction_reason,
        notes=notes if notes is not None else original.notes,
        created_at=now,
        updated_at=now,
    )
    db.add(corrected)
    db.flush()

    complaint = db.query(Complaint).filter(Complaint.id == original.complaint_id).first()
    log_audit(
        db=db,
        user_id=getattr(current_user, "id", None),
        officer_name=getattr(current_user, "full_name", getattr(current_user, "username", "SYSTEM")),
        role=getattr(current_user, "role", "UNKNOWN"),
        action="OUTCOME_CORRECTED",
        case_number=complaint.complaint_number if complaint else str(original.complaint_id),
        details=(
            f"OutcomeObservation id={original.id} SUPERSEDED -> new id={corrected.id} "
            f"v{original.version}→v{corrected.version}; reason={correction_reason[:120]}"
        ),
    )
    db.commit()
    db.refresh(corrected)
    return corrected


def get_outcomes_for_complaint(
    db: Session,
    complaint_id: int,
    include_superseded: bool = False,
) -> List[OutcomeObservation]:
    q = db.query(OutcomeObservation).filter(OutcomeObservation.complaint_id == complaint_id)
    if not include_superseded:
        q = q.filter(OutcomeObservation.record_status == "ACTIVE")
    return q.order_by(OutcomeObservation.version.desc()).all()


def get_outcome_metrics(db: Session) -> Dict[str, Any]:
    """
    Compute operational metrics from ACTIVE non-synthetic outcomes.
    Returns explicit denominator values for each cohort.

    METRIC FORMULAS:
    - denominator_measured: count of CONFIRMED_CASHOUT + MULTIPLE_CASHOUT + NO_OBSERVED_CASHOUT (active, non-excluded)
    - denominator_unknown: count of UNKNOWN outcomes (active, non-excluded)
    - denominator_excluded: count of DATA_EXCLUDED outcomes (active)
    - denominator_synthetic: count of is_synthetic=True outcomes (active)
    - rank1_accuracy: count of prediction_rank_matched=1 / denominator_measured
    - topk_accuracy: count of prediction_rank_matched IS NOT NULL / denominator_measured
    - mean_distance_error_km: average distance_error_km over measured cashout outcomes
    - mean_prediction_lead_time_min: average prediction_lead_time_minutes over measured
    - mean_alert_lead_time_min: average alert_lead_time_minutes
    - mean_ack_latency_min: average alert_acknowledgement_latency_minutes
    - mean_bank_latency_min: average bank_response_latency_minutes
    - total_verified_held_inr: sum of verified_held_amount_inr (non-double-counted)
    - total_verified_released_inr: sum of verified_released_amount_inr
    - total_actual_recovered_inr: sum of actual_recovered_amount_inr (separate from held)
    - false_alert_count: count of NO_OBSERVED_CASHOUT outcomes with a linked alert
    """
    # Base query: only ACTIVE real outcomes
    real_active = (
        db.query(OutcomeObservation)
        .filter(
            OutcomeObservation.record_status == "ACTIVE",
            OutcomeObservation.is_synthetic == False,
        )
    )

    measured = real_active.filter(
        OutcomeObservation.outcome_type.in_(MEASURED_OUTCOME_TYPES),
        OutcomeObservation.is_excluded == False,
    )
    unknown_q = real_active.filter(
        OutcomeObservation.outcome_type == "UNKNOWN",
        OutcomeObservation.is_excluded == False,
    )
    excluded_q = real_active.filter(OutcomeObservation.is_excluded == True)
    synthetic_q = (
        db.query(OutcomeObservation)
        .filter(
            OutcomeObservation.record_status == "ACTIVE",
            OutcomeObservation.is_synthetic == True,
        )
    )

    denom_measured = measured.count()
    denom_unknown = unknown_q.count()
    denom_excluded = excluded_q.count()
    denom_synthetic = synthetic_q.count()

    # Cashout-specific sub-query for location metrics
    cashout_q = measured.filter(
        OutcomeObservation.outcome_type.in_(["CONFIRMED_CASHOUT", "MULTIPLE_CASHOUT"]),
    )
    cashout_count = cashout_q.count()

    rank1_count = cashout_q.filter(OutcomeObservation.prediction_rank_matched == 1).count()
    topk_count = cashout_q.filter(OutcomeObservation.prediction_rank_matched.isnot(None)).count()

    mean_dist = cashout_q.filter(OutcomeObservation.distance_error_km.isnot(None)).with_entities(
        func.avg(OutcomeObservation.distance_error_km)
    ).scalar()

    mean_pred_lead = measured.filter(OutcomeObservation.prediction_lead_time_minutes.isnot(None)).with_entities(
        func.avg(OutcomeObservation.prediction_lead_time_minutes)
    ).scalar()

    mean_alert_lead = measured.filter(OutcomeObservation.alert_lead_time_minutes.isnot(None)).with_entities(
        func.avg(OutcomeObservation.alert_lead_time_minutes)
    ).scalar()

    mean_ack_lat = real_active.filter(OutcomeObservation.alert_acknowledgement_latency_minutes.isnot(None)).with_entities(
        func.avg(OutcomeObservation.alert_acknowledgement_latency_minutes)
    ).scalar()

    mean_bank_lat = real_active.filter(OutcomeObservation.bank_response_latency_minutes.isnot(None)).with_entities(
        func.avg(OutcomeObservation.bank_response_latency_minutes)
    ).scalar()

    total_held = real_active.filter(OutcomeObservation.verified_held_amount_inr.isnot(None)).with_entities(
        func.sum(OutcomeObservation.verified_held_amount_inr)
    ).scalar()

    total_released = real_active.filter(OutcomeObservation.verified_released_amount_inr.isnot(None)).with_entities(
        func.sum(OutcomeObservation.verified_released_amount_inr)
    ).scalar()

    total_recovered = real_active.filter(OutcomeObservation.actual_recovered_amount_inr.isnot(None)).with_entities(
        func.sum(OutcomeObservation.actual_recovered_amount_inr)
    ).scalar()

    false_alert_count = measured.filter(
        OutcomeObservation.outcome_type == "NO_OBSERVED_CASHOUT",
        OutcomeObservation.linked_alert_id.isnot(None),
    ).count()

    def safe_rate(numerator: int, denominator: int) -> Optional[float]:
        if denominator == 0:
            return None
        return round(numerator / denominator, 4)

    return {
        # Denominators — explicitly shown on dashboard
        "denominator_measured": denom_measured,
        "denominator_unknown": denom_unknown,
        "denominator_excluded": denom_excluded,
        "denominator_synthetic": denom_synthetic,
        "denominator_total_active": denom_measured + denom_unknown + denom_excluded,

        # Location Accuracy
        "denominator_cashout": cashout_count,
        "rank1_count": rank1_count,
        "topk_count": topk_count,
        "rank1_accuracy_rate": safe_rate(rank1_count, cashout_count),
        "topk_accuracy_rate": safe_rate(topk_count, cashout_count),
        "mean_distance_error_km": round(float(mean_dist), 3) if mean_dist is not None else None,

        # Timing Metrics
        "mean_prediction_lead_time_minutes": round(float(mean_pred_lead), 2) if mean_pred_lead is not None else None,
        "mean_alert_lead_time_minutes": round(float(mean_alert_lead), 2) if mean_alert_lead is not None else None,
        "mean_alert_acknowledgement_latency_minutes": round(float(mean_ack_lat), 2) if mean_ack_lat is not None else None,
        "mean_bank_response_latency_minutes": round(float(mean_bank_lat), 2) if mean_bank_lat is not None else None,

        # Financial Figures (reported separately; NOT summed as total saved)
        "total_verified_held_inr": float(total_held) if total_held is not None else 0.0,
        "total_verified_released_inr": float(total_released) if total_released is not None else 0.0,
        "total_actual_recovered_inr": float(total_recovered) if total_recovered is not None else 0.0,
        "financial_note": (
            "Verified held amount and actual recovered amount are reported separately. "
            "Their sum is NOT presented as independently saved money. "
            "These are observational figures; causal attribution to the model alone is not claimed."
        ),

        # Alert Workload
        "false_alert_count": false_alert_count,

        # Policy metadata
        "prediction_selection_policy": "LAST_OPERATIONAL_BEFORE_EVENT",
        "policy_description": (
            "Prediction linked is the last OPERATIONAL prediction created strictly before "
            "observed_event_time. No hindsight cherry-picking. If no eligible prediction "
            "exists, linked_prediction_id is NULL and it contributes to the unknown-prediction cohort."
        ),
    }


def evaluate_complaint_outcome(
    db: Session,
    complaint_id: int,
    current_user: User
) -> Dict[str, Any]:
    """
    Phase 6: Comprehensive Prediction vs Observed Outcome Evaluation.
    Evaluates historical persisted prediction against the active outcome observation.
    Zero re-inference of V8 or time-model.
    """
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint or not verify_complaint_access(complaint, current_user, db):
        raise HTTPException(status_code=404, detail="Complaint not found")

    # Fetch active outcome observation and full lineage
    active_outcome = (
        db.query(OutcomeObservation)
        .filter(
            OutcomeObservation.complaint_id == complaint.id,
            OutcomeObservation.record_status == "ACTIVE"
        )
        .first()
    )

    lineage_records = (
        db.query(OutcomeObservation)
        .filter(OutcomeObservation.complaint_id == complaint.id)
        .order_by(OutcomeObservation.version.desc())
        .all()
    )

    if not active_outcome:
        # Check if an operational prediction exists for context
        pred = (
            db.query(Prediction)
            .filter(Prediction.complaint_id == complaint.id)
            .order_by(desc(Prediction.created_at))
            .first()
        )
        return {
            "complaint_id": complaint.id,
            "complaint_number": complaint.complaint_number,
            "prediction_id": pred.id if pred else None,
            "outcome_id": None,
            "cohort": "NONE",
            "cohort_display": "No Outcome Recorded",
            "has_active_outcome": False,
            "evaluation": {
                "top1_hit": None,
                "top3_hit": None,
                "top5_hit": None,
                "observed_rank": None,
                "spatial_error_km": None,
                "lead_time_minutes": None,
                "lead_time_display": None,
                "evaluation_status": "PENDING_OUTCOME",
                "prediction_snapshot_version": pred.version_number if pred else None,
                "evaluation_basis": "HISTORICAL_PERSISTED_PREDICTION"
            },
            "financial": {
                "attempted_withdrawal_amount_inr": None,
                "verified_held_amount_inr": None,
                "verified_released_amount_inr": None,
                "actual_recovered_amount_inr": None,
                "recovery_verified_by": None,
                "recovery_verified_at": None,
                "financial_note": (
                    "Verified held amount and actual recovered amount are recorded separately. "
                    "Their sum is never claimed as independently prevented loss."
                )
            },
            "active_observation": None,
            "lineage": lineage_records,
            "disclaimer": (
                "Outcome evaluation is derived strictly from historical persisted predictions and verified incident reports. "
                "Causal attribution to the model alone is not claimed; real-world and synthetic cohorts remain separate."
            )
        }

    # Determine cohort
    if active_outcome.is_synthetic:
        cohort = "CONTROLLED_SYNTHETIC"
        cohort_display = "Controlled Synthetic Evaluation"
    elif active_outcome.is_excluded:
        cohort = "EXCLUDED"
        cohort_display = "Data Excluded"
    elif active_outcome.outcome_type == "UNKNOWN":
        cohort = "UNKNOWN"
        cohort_display = "Inconclusive / Unknown"
    else:
        cohort = "AUTHORIZED_OPERATIONAL"
        cohort_display = "Authorized Operational Evaluation"

    # Resolve linked historical prediction snapshot
    pred = None
    if active_outcome.linked_prediction_id:
        pred = db.query(Prediction).filter(Prediction.id == active_outcome.linked_prediction_id).first()
    if not pred:
        pred = _select_eligible_prediction(db, complaint.id, active_outcome.observed_event_time)

    # Derived hits & ranks
    observed_rank = active_outcome.prediction_rank_matched
    is_cashout_event = active_outcome.outcome_type in ("CONFIRMED_CASHOUT", "MULTIPLE_CASHOUT")

    top1_hit = None
    top3_hit = None
    top5_hit = None
    if is_cashout_event and pred is not None:
        if observed_rank is not None:
            top1_hit = (observed_rank == 1)
            top3_hit = (observed_rank in (1, 2, 3))
            top5_hit = (observed_rank in (1, 2, 3, 4, 5))
        else:
            top1_hit = False
            top3_hit = False
            top5_hit = False

    # Spatial Error
    spatial_error_km = active_outcome.distance_error_km
    if spatial_error_km is None and pred is not None and active_outcome.actual_lat is not None and active_outcome.actual_lon is not None:
        spatial_error_km = _compute_distance_error(db, pred, active_outcome.actual_lat, active_outcome.actual_lon)

    # Lead time
    lead_time_min = active_outcome.prediction_lead_time_minutes
    if lead_time_min is None and pred is not None and active_outcome.observed_event_time is not None:
        lead_time_min = _minutes_between(pred.created_at, active_outcome.observed_event_time)

    lead_display = None
    if lead_time_min is not None:
        if lead_time_min > 1.0:
            lead_display = f"{lead_time_min:.0f} min before observed event"
        elif lead_time_min < -1.0:
            lead_display = f"{abs(lead_time_min):.0f} min after event (late prediction)"
        else:
            lead_display = "< 1 min (simultaneous)"

    # Evaluation status
    if not is_cashout_event:
        eval_status = "NO_CASHOUT_OBSERVED" if active_outcome.outcome_type == "NO_OBSERVED_CASHOUT" else "INCONCLUSIVE"
    elif pred is None:
        eval_status = "NO_PREDICTION_LINKED"
    elif active_outcome.actual_lat is None or active_outcome.actual_lon is None:
        eval_status = "INSUFFICIENT_COORDINATES"
    else:
        eval_status = "EVALUATED"

    financial_details = {
        "attempted_withdrawal_amount_inr": float(active_outcome.actual_withdrawal_amount_inr) if active_outcome.actual_withdrawal_amount_inr is not None else None,
        "verified_held_amount_inr": float(active_outcome.verified_held_amount_inr) if active_outcome.verified_held_amount_inr is not None else None,
        "verified_released_amount_inr": float(active_outcome.verified_released_amount_inr) if active_outcome.verified_released_amount_inr is not None else None,
        "actual_recovered_amount_inr": float(active_outcome.actual_recovered_amount_inr) if active_outcome.actual_recovered_amount_inr is not None else None,
        "recovery_verified_by": active_outcome.recovery_verified_by,
        "recovery_verified_at": active_outcome.recovery_verified_at,
        "financial_note": (
            "Verified held amount and actual recovered amount are recorded separately. "
            "Their sum is never claimed as independently prevented loss."
        )
    }

    return {
        "complaint_id": complaint.id,
        "complaint_number": complaint.complaint_number,
        "prediction_id": pred.id if pred else active_outcome.linked_prediction_id,
        "outcome_id": active_outcome.id,
        "cohort": cohort,
        "cohort_display": cohort_display,
        "has_active_outcome": True,
        "evaluation": {
            "top1_hit": top1_hit,
            "top3_hit": top3_hit,
            "top5_hit": top5_hit,
            "observed_rank": observed_rank,
            "spatial_error_km": round(spatial_error_km, 2) if spatial_error_km is not None else None,
            "lead_time_minutes": round(lead_time_min, 1) if lead_time_min is not None else None,
            "lead_time_display": lead_display,
            "evaluation_status": eval_status,
            "prediction_snapshot_version": pred.version_number if pred else active_outcome.linked_prediction_version,
            "evaluation_basis": "HISTORICAL_PERSISTED_PREDICTION"
        },
        "financial": financial_details,
        "active_observation": active_outcome,
        "lineage": lineage_records,
        "disclaimer": (
            "Outcome evaluation is derived strictly from historical persisted predictions and verified incident reports. "
            "Causal attribution to the model alone is not claimed; real-world and synthetic cohorts remain separate."
        )
    }


def get_drift_and_monitoring_metrics(db: Session) -> Dict[str, Any]:
    """
    Phase 6: Multi-Cohort Governance and Distribution Drift Monitoring.
    Evaluates incoming prediction distributions against approved V8 reference metadata.
    Zero automated retraining or artifact modification.
    """
    op_q = db.query(OutcomeObservation).filter(
        OutcomeObservation.record_status == "ACTIVE",
        OutcomeObservation.is_synthetic == False,
        OutcomeObservation.is_excluded == False,
        OutcomeObservation.outcome_type != "UNKNOWN"
    )
    synth_q = db.query(OutcomeObservation).filter(
        OutcomeObservation.record_status == "ACTIVE",
        OutcomeObservation.is_synthetic == True
    )
    excl_q = db.query(OutcomeObservation).filter(
        OutcomeObservation.record_status == "ACTIVE",
        OutcomeObservation.is_excluded == True
    )
    unk_q = db.query(OutcomeObservation).filter(
        OutcomeObservation.record_status == "ACTIVE",
        OutcomeObservation.is_synthetic == False,
        OutcomeObservation.is_excluded == False,
        OutcomeObservation.outcome_type == "UNKNOWN"
    )

    op_count = op_q.count()
    synth_count = synth_q.count()
    excl_count = excl_q.count()
    unk_count = unk_q.count()
    total_active = op_count + synth_count + excl_count + unk_count

    cohorts = [
        {
            "cohort": "AUTHORIZED_OPERATIONAL",
            "count": op_count,
            "label": "Authorized Operational Cohort",
            "description": "Real verified field outcomes from law enforcement casework and confirmed bank investigations.",
            "eligible_for_evaluation": True
        },
        {
            "cohort": "CONTROLLED_SYNTHETIC",
            "count": synth_count,
            "label": "Controlled Synthetic Cohort",
            "description": "High-fidelity controlled simulation outcomes reserved for regression testing and pilot calibration.",
            "eligible_for_evaluation": False
        },
        {
            "cohort": "EXCLUDED",
            "count": excl_count,
            "label": "Excluded Outcomes",
            "description": "Observations with confirmed data quality flaws, jurisdictional disputes, or court sealed status.",
            "eligible_for_evaluation": False
        },
        {
            "cohort": "UNKNOWN",
            "count": unk_count,
            "label": "Inconclusive / Unknown",
            "description": "Complaints with pending verification, inconclusive monitoring, or insufficient physical evidence.",
            "eligible_for_evaluation": False
        }
    ]

    operational_metrics = get_outcome_metrics(db)
    empty_state_msg = None
    if op_count == 0:
        empty_state_msg = "No authorized real-world evaluation cohort is available yet."

    # Compute controlled synthetic metrics separately
    synthetic_metrics = None
    if synth_count > 0:
        synth_cashouts = synth_q.filter(OutcomeObservation.outcome_type.in_(MEASURED_OUTCOME_TYPES)).count()
        synth_top3 = synth_q.filter(OutcomeObservation.prediction_rank_matched.in_([1, 2, 3])).count()
        synth_dist = synth_q.filter(OutcomeObservation.distance_error_km.isnot(None)).with_entities(func.avg(OutcomeObservation.distance_error_km)).scalar()
        synthetic_metrics = {
            "cohort_size": synth_count,
            "cashout_events_count": synth_cashouts,
            "top3_hit_count": synth_top3,
            "controlled_synthetic_top3_hit_rate": round(synth_top3 / synth_cashouts, 4) if synth_cashouts > 0 else None,
            "mean_distance_error_km": round(float(synth_dist), 2) if synth_dist is not None else None,
            "label": "CONTROLLED SYNTHETIC EVALUATION"
        }

    # Reference metadata from V8 debiased model
    ref_source = "cashout-location-xgb-v8-debiased baseline (model_metadata_v8_debiased.json)"

    # Drift Indicators across distributions
    indicators = []

    # Indicator 1: Top-1 Prediction Score Distribution
    ref_top1_score = 0.0833
    recent_top1_scores = (
        db.query(PredictionLocation.probability)
        .filter(PredictionLocation.rank == 1)
        .order_by(PredictionLocation.id.desc())
        .limit(100)
        .all()
    )
    if recent_top1_scores:
        curr_mean_score = sum(s[0] for s in recent_top1_scores if s[0] is not None) / len(recent_top1_scores)
        drift_delta_score = round(abs(curr_mean_score - ref_top1_score), 4)
        status_score = "STABLE" if drift_delta_score <= 0.03 else ("MONITORING" if drift_delta_score <= 0.06 else "SHIFT_OBSERVED")
        indicators.append({
            "dimension": "Confidence Scores",
            "metric_name": "Mean Top-1 Probability Score",
            "reference_baseline": ref_top1_score,
            "current_monitoring": round(curr_mean_score, 4),
            "drift_delta": drift_delta_score,
            "status": status_score
        })
    else:
        indicators.append({
            "dimension": "Confidence Scores",
            "metric_name": "Mean Top-1 Probability Score",
            "reference_baseline": ref_top1_score,
            "current_monitoring": None,
            "drift_delta": None,
            "status": "INSUFFICIENT_DATA"
        })

    # Indicator 2: Spatial Error Distribution (km)
    ref_spatial_err = 8.98
    curr_spatial_err = operational_metrics.get("mean_distance_error_km")
    if curr_spatial_err is not None:
        drift_delta_spatial = round(abs(curr_spatial_err - ref_spatial_err), 2)
        status_spatial = "STABLE" if drift_delta_spatial <= 3.0 else ("MONITORING" if drift_delta_spatial <= 6.0 else "SHIFT_OBSERVED")
        indicators.append({
            "dimension": "Spatial Accuracy",
            "metric_name": "Mean Spatial Error (km)",
            "reference_baseline": ref_spatial_err,
            "current_monitoring": curr_spatial_err,
            "drift_delta": drift_delta_spatial,
            "status": status_spatial
        })
    else:
        indicators.append({
            "dimension": "Spatial Accuracy",
            "metric_name": "Mean Spatial Error (km)",
            "reference_baseline": ref_spatial_err,
            "current_monitoring": None,
            "drift_delta": None,
            "status": "INSUFFICIENT_DATA"
        })

    # Indicator 3: Top-3 Hit Rate (R@3)
    ref_r3 = 0.238
    curr_r3 = operational_metrics.get("topk_accuracy_rate")
    if curr_r3 is not None and operational_metrics.get("denominator_cashout", 0) >= 5:
        drift_delta_r3 = round(abs(curr_r3 - ref_r3), 4)
        status_r3 = "STABLE" if drift_delta_r3 <= 0.08 else ("MONITORING" if drift_delta_r3 <= 0.15 else "SHIFT_OBSERVED")
        indicators.append({
            "dimension": "Recall Metrics",
            "metric_name": "Top-3 Hit Rate (R@3)",
            "reference_baseline": ref_r3,
            "current_monitoring": curr_r3,
            "drift_delta": drift_delta_r3,
            "status": status_r3
        })
    else:
        indicators.append({
            "dimension": "Recall Metrics",
            "metric_name": "Top-3 Hit Rate (R@3)",
            "reference_baseline": ref_r3,
            "current_monitoring": curr_r3,
            "drift_delta": None,
            "status": "INSUFFICIENT_DATA"
        })

    # Indicator 4: Incident-to-Prediction Lead Time (minutes)
    ref_lead = 60.0
    curr_lead = operational_metrics.get("mean_prediction_lead_time_minutes")
    if curr_lead is not None:
        drift_delta_lead = round(abs(curr_lead - ref_lead), 1)
        status_lead = "STABLE" if drift_delta_lead <= 30.0 else ("MONITORING" if drift_delta_lead <= 60.0 else "SHIFT_OBSERVED")
        indicators.append({
            "dimension": "Temporal Response",
            "metric_name": "Mean Prediction Lead Time (min)",
            "reference_baseline": ref_lead,
            "current_monitoring": curr_lead,
            "drift_delta": drift_delta_lead,
            "status": status_lead
        })
    else:
        indicators.append({
            "dimension": "Temporal Response",
            "metric_name": "Mean Prediction Lead Time (min)",
            "reference_baseline": ref_lead,
            "current_monitoring": None,
            "drift_delta": None,
            "status": "INSUFFICIENT_DATA"
        })

    # Overall Drift Status
    active_statuses = [ind["status"] for ind in indicators if ind["status"] != "INSUFFICIENT_DATA"]
    if op_count < 5 or not active_statuses:
        overall_drift_status = "INSUFFICIENT_DATA"
    elif "SHIFT_OBSERVED" in active_statuses:
        overall_drift_status = "SHIFT_OBSERVED"
    elif "MONITORING" in active_statuses:
        overall_drift_status = "MONITORING"
    else:
        overall_drift_status = "STABLE"

    return {
        "cohorts": cohorts,
        "total_active_records": total_active,
        "operational_cohort_size": op_count,
        "synthetic_cohort_size": synth_count,
        "excluded_cohort_size": excl_count,
        "unknown_cohort_size": unk_count,
        "drift_status": overall_drift_status,
        "reference_source": ref_source,
        "indicators": indicators,
        "operational_metrics": operational_metrics,
        "synthetic_metrics": synthetic_metrics,
        "empty_state_message": empty_state_msg,
        "disclaimer": (
            "Drift monitoring checks whether incoming case and prediction distributions are changing relative to an approved reference. "
            "It does not automatically retrain, replace, or promote any model."
        )
    }
