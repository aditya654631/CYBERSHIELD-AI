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
