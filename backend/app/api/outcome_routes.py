"""
CyberShield AI — Phase 09: Outcome Observation API Routes

Endpoints:
  POST   /api/v1/outcomes/complaints/{complaint_id}        — ingest new outcome
  POST   /api/v1/outcomes/{outcome_id}/correct             — correct ACTIVE outcome (append-only lineage)
  GET    /api/v1/outcomes/complaints/{complaint_id}        — list outcomes for a complaint
  GET    /api/v1/outcomes/{outcome_id}                     — get single outcome (with lineage)
  GET    /api/v1/outcomes/metrics                          — global operational dashboard metrics

RBAC:
  - Ingest / Correct: I4C_ADMIN, STATE_LEA, DISTRICT_LEA (not BANK_OFFICER, ANALYST, AUDITOR)
  - Read: I4C_ADMIN, STATE_LEA, DISTRICT_LEA, ANALYST, AUDITOR
  - Metrics: I4C_ADMIN, ANALYST, AUDITOR (aggregated; no individual case data)

Prediction linkage is ALWAYS server-side by LAST_OPERATIONAL_BEFORE_EVENT policy.
Clients cannot supply a prediction ID.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from backend.app.models.db import get_db
from backend.app.models.models import OutcomeObservation, Complaint
from backend.app.auth.security import get_current_user
from backend.app.auth.rbac import (
    require_roles, verify_complaint_access, RoleEnum,
    is_national_scope, filter_complaints_by_jurisdiction,
)
from backend.app.schemas.schemas import (
    OutcomeCreateRequest,
    OutcomeCorrectRequest,
    OutcomeResponse,
    OutcomeMetricsResponse,
)
from backend.app.services.outcome_service import (
    create_outcome,
    correct_outcome,
    get_outcomes_for_complaint,
    get_outcome_metrics,
)
from backend.app.models.models import User

router = APIRouter(prefix="/outcomes", tags=["Outcomes"])

# Roles allowed to ingest / correct outcome observations
_INGEST_ROLES = [RoleEnum.I4C_ADMIN, RoleEnum.STATE_LEA, RoleEnum.DISTRICT_LEA]
# Roles allowed to read outcomes
_READ_ROLES = [
    RoleEnum.I4C_ADMIN, RoleEnum.STATE_LEA, RoleEnum.DISTRICT_LEA,
    RoleEnum.ANALYST, RoleEnum.AUDITOR,
]
# Roles allowed to view aggregated metrics
_METRICS_ROLES = [RoleEnum.I4C_ADMIN, RoleEnum.ANALYST, RoleEnum.AUDITOR,
                  RoleEnum.STATE_LEA, RoleEnum.DISTRICT_LEA]


def _get_complaint_or_404(complaint_id: int, db: Session, current_user: User) -> Complaint:
    """Returns complaint if accessible, HTTP 404 otherwise (jurisdiction-safe)."""
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint or not verify_complaint_access(complaint, current_user, db):
        raise HTTPException(status_code=404, detail="Complaint not found")
    return complaint


@router.post(
    "/complaints/{complaint_id}",
    response_model=OutcomeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a new outcome observation",
    description=(
        "Create an append-only outcome observation for a complaint. "
        "Prediction linkage is applied server-side using LAST_OPERATIONAL_BEFORE_EVENT policy. "
        "Clients must NOT supply a prediction_id."
    ),
)
def ingest_outcome(
    complaint_id: int,
    body: OutcomeCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_INGEST_ROLES)),
):
    _get_complaint_or_404(complaint_id, db, current_user)
    return create_outcome(
        db=db,
        current_user=current_user,
        complaint_id=complaint_id,
        outcome_type=body.outcome_type,
        source=body.source,
        observed_event_time=body.observed_event_time,
        actual_lat=body.actual_lat,
        actual_lon=body.actual_lon,
        actual_location_name=body.actual_location_name,
        actual_withdrawal_amount_inr=body.actual_withdrawal_amount_inr,
        cashout_events=body.cashout_events,
        actual_atm_id=body.actual_atm_id,
        actual_cluster_id=body.actual_cluster_id,
        linked_alert_id=body.linked_alert_id,
        linked_bank_action_id=body.linked_bank_action_id,
        verified_held_amount_inr=body.verified_held_amount_inr,
        verified_released_amount_inr=body.verified_released_amount_inr,
        actual_recovered_amount_inr=body.actual_recovered_amount_inr,
        recovery_verified_by=body.recovery_verified_by,
        recovery_verified_at=body.recovery_verified_at,
        verifier_user_id=body.verifier_user_id,
        verification_status=body.verification_status,
        is_synthetic=body.is_synthetic,
        is_excluded=body.is_excluded,
        exclusion_reason=body.exclusion_reason,
        notes=body.notes,
    )


@router.post(
    "/{outcome_id}/correct",
    response_model=OutcomeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Correct an existing outcome (append-only lineage)",
    description=(
        "Supersede an ACTIVE outcome by recording a correction. "
        "The original record is preserved with record_status=SUPERSEDED. "
        "A new ACTIVE record is returned with incremented version. "
        "correction_reason is mandatory."
    ),
)
def correct_outcome_endpoint(
    outcome_id: int,
    body: OutcomeCorrectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_INGEST_ROLES)),
):
    outcome = db.query(OutcomeObservation).filter(OutcomeObservation.id == outcome_id).first()
    if not outcome:
        raise HTTPException(status_code=404, detail="OutcomeObservation not found")
    # Verify complaint access server-side
    _get_complaint_or_404(outcome.complaint_id, db, current_user)

    return correct_outcome(
        db=db,
        current_user=current_user,
        outcome_id=outcome_id,
        correction_reason=body.correction_reason,
        outcome_type=body.outcome_type,
        source=body.source,
        observed_event_time=body.observed_event_time,
        actual_lat=body.actual_lat,
        actual_lon=body.actual_lon,
        actual_location_name=body.actual_location_name,
        actual_withdrawal_amount_inr=body.actual_withdrawal_amount_inr,
        cashout_events=body.cashout_events,
        actual_atm_id=body.actual_atm_id,
        actual_cluster_id=body.actual_cluster_id,
        linked_alert_id=body.linked_alert_id,
        linked_bank_action_id=body.linked_bank_action_id,
        verified_held_amount_inr=body.verified_held_amount_inr,
        verified_released_amount_inr=body.verified_released_amount_inr,
        actual_recovered_amount_inr=body.actual_recovered_amount_inr,
        recovery_verified_by=body.recovery_verified_by,
        recovery_verified_at=body.recovery_verified_at,
        verifier_user_id=body.verifier_user_id,
        verification_status=body.verification_status,
        is_excluded=body.is_excluded,
        exclusion_reason=body.exclusion_reason,
        notes=body.notes,
    )


@router.get(
    "/complaints/{complaint_id}",
    response_model=List[OutcomeResponse],
    summary="List outcome observations for a complaint",
)
def list_outcomes_for_complaint(
    complaint_id: int,
    include_superseded: bool = Query(False, description="Include SUPERSEDED records for lineage view"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_READ_ROLES)),
):
    _get_complaint_or_404(complaint_id, db, current_user)
    return get_outcomes_for_complaint(db, complaint_id, include_superseded=include_superseded)


@router.get(
    "/metrics",
    response_model=OutcomeMetricsResponse,
    summary="Aggregated operational outcome metrics",
    description=(
        "Returns dashboard metrics computed from ACTIVE, non-synthetic, non-excluded outcome observations. "
        "Explicit denominators are always returned so unknown and excluded cohorts are visible. "
        "Verified held amounts and actual recovered amounts are reported separately; "
        "their sum is NOT presented as independently saved money."
    ),
)
def outcome_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_METRICS_ROLES)),
):
    return get_outcome_metrics(db)


@router.get(
    "/{outcome_id}",
    response_model=OutcomeResponse,
    summary="Get a single outcome observation",
)
def get_outcome(
    outcome_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_READ_ROLES)),
):
    outcome = db.query(OutcomeObservation).filter(OutcomeObservation.id == outcome_id).first()
    if not outcome:
        raise HTTPException(status_code=404, detail="OutcomeObservation not found")
    _get_complaint_or_404(outcome.complaint_id, db, current_user)
    return outcome
