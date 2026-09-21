"""
CyberShield AI — Phase 7: Controlled Cross-State & Cross-District Handoff Endpoints.
Provides authenticated, role-scoped API routes for case handoff workflows,
acknowledgement deadlines, state transitions, and assignment visibility.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.app.models.db import get_db
from backend.app.models.models import Complaint, CaseHandoff, User
from backend.app.schemas.schemas import (
    CaseHandoffCreateRequest, CaseHandoffResponse,
    HandoffRejectRequest, HandoffCancelRequest, HandoffCompleteRequest
)
from backend.app.auth.security import get_current_user
from backend.app.auth.rbac import (
    verify_complaint_access, is_national_scope, RoleEnum
)
from backend.app.services.handoff_service import (
    request_case_handoff, accept_case_handoff, reject_case_handoff,
    start_case_handoff, complete_case_handoff, cancel_case_handoff,
    check_and_expire_handoffs
)


router = APIRouter(tags=["Cross-Jurisdiction Handoffs"])


def _format_handoff_response(h: CaseHandoff) -> CaseHandoffResponse:
    """Helper to populate organization names and actor names in response."""
    return CaseHandoffResponse(
        id=h.id,
        complaint_id=h.complaint_id,
        prediction_id=h.prediction_id,
        prediction_version=h.prediction_version,
        origin_organization_id=h.origin_organization_id,
        origin_organization_name=h.origin_organization.name if h.origin_organization else None,
        destination_organization_id=h.destination_organization_id,
        destination_organization_name=h.destination_organization.name if h.destination_organization else None,
        target_state=h.target_state,
        target_district=h.target_district,
        purpose=h.purpose,
        evidence_scope=h.evidence_scope,
        shared_evidence_ids=h.shared_evidence_ids,
        status=h.status,
        initiator_user_id=h.initiator_user_id,
        initiator_name=h.initiator_user.full_name if h.initiator_user else None,
        recipient_user_id=h.recipient_user_id,
        recipient_name=h.recipient_user.full_name if h.recipient_user else None,
        rejection_reason=h.rejection_reason,
        cancellation_reason=h.cancellation_reason,
        completed_notes=h.completed_notes,
        acknowledgement_deadline=h.acknowledgement_deadline,
        accepted_at=h.accepted_at,
        completed_at=h.completed_at,
        created_at=h.created_at,
        updated_at=h.updated_at,
    )


def _resolve_complaint(complaint_id_or_number: str, db: Session) -> Complaint:
    if complaint_id_or_number.isdigit():
        c = db.query(Complaint).filter(Complaint.id == int(complaint_id_or_number)).first()
    else:
        c = db.query(Complaint).filter(Complaint.complaint_number == complaint_id_or_number).first()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")
    return c


@router.post(
    "/complaints/{complaint_id}/handoffs",
    response_model=CaseHandoffResponse,
    status_code=status.HTTP_201_CREATED
)
def create_complaint_handoff(
    complaint_id: str,
    payload: CaseHandoffCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Initiates a new cross-state or cross-district case handoff request.
    Only the case-owning LEA or I4C Admin can initiate handoffs.
    """
    complaint = _resolve_complaint(complaint_id, db)

    handoff = request_case_handoff(
        db=db,
        complaint_id=complaint.id,
        target_state=payload.target_state,
        target_district=payload.target_district,
        destination_organization_id=payload.destination_organization_id,
        purpose=payload.purpose,
        evidence_scope=payload.evidence_scope,
        shared_evidence_ids=payload.shared_evidence_ids,
        prediction_id=payload.prediction_id,
        prediction_version=payload.prediction_version,
        acknowledgement_hours=payload.acknowledgement_hours,
        initiator_user=current_user
    )
    return _format_handoff_response(handoff)


@router.get(
    "/complaints/{complaint_id}/handoffs",
    response_model=List[CaseHandoffResponse]
)
def list_complaint_handoffs(
    complaint_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists all handoff records associated with a specific complaint.
    """
    complaint = _resolve_complaint(complaint_id, db)
    if not verify_complaint_access(complaint, current_user, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")

    handoffs = db.query(CaseHandoff).filter(
        CaseHandoff.complaint_id == complaint.id
    ).order_by(CaseHandoff.created_at.desc()).all()

    # Scoped visibility: if user is not national and not origin, only show handoffs where user's org is destination
    if not is_national_scope(current_user) and complaint.owner_organization_id != current_user.organization_id:
        handoffs = [h for h in handoffs if h.destination_organization_id == current_user.organization_id]

    return [_format_handoff_response(h) for h in handoffs]


@router.get(
    "/handoffs/incoming",
    response_model=List[CaseHandoffResponse]
)
def list_incoming_handoffs(
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists incoming handoff tasks targeted to the caller's organization.
    """
    query = db.query(CaseHandoff)
    if not is_national_scope(current_user):
        if not current_user.organization_id:
            return []
        query = query.filter(CaseHandoff.destination_organization_id == current_user.organization_id)

    if status_filter:
        query = query.filter(CaseHandoff.status == status_filter.upper())

    handoffs = query.order_by(CaseHandoff.created_at.desc()).all()
    return [_format_handoff_response(h) for h in handoffs]


@router.get(
    "/handoffs/outgoing",
    response_model=List[CaseHandoffResponse]
)
def list_outgoing_handoffs(
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists outgoing handoffs initiated by the caller's organization.
    """
    query = db.query(CaseHandoff)
    if not is_national_scope(current_user):
        if not current_user.organization_id:
            return []
        query = query.filter(CaseHandoff.origin_organization_id == current_user.organization_id)

    if status_filter:
        query = query.filter(CaseHandoff.status == status_filter.upper())

    handoffs = query.order_by(CaseHandoff.created_at.desc()).all()
    return [_format_handoff_response(h) for h in handoffs]


@router.get(
    "/handoffs/{handoff_id}",
    response_model=CaseHandoffResponse
)
def get_handoff_detail(
    handoff_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves detailed metadata for a specific handoff request.
    """
    handoff = db.query(CaseHandoff).filter(CaseHandoff.id == handoff_id).first()
    if not handoff:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Handoff not found")

    if not is_national_scope(current_user):
        if current_user.organization_id not in (handoff.origin_organization_id, handoff.destination_organization_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Handoff not found")

    return _format_handoff_response(handoff)


@router.post(
    "/handoffs/{handoff_id}/accept",
    response_model=CaseHandoffResponse
)
def accept_handoff(
    handoff_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Accepts an incoming handoff request (Destination LEA).
    """
    handoff = accept_case_handoff(db=db, handoff_id=handoff_id, current_user=current_user)
    return _format_handoff_response(handoff)


@router.post(
    "/handoffs/{handoff_id}/reject",
    response_model=CaseHandoffResponse
)
def reject_handoff(
    handoff_id: int,
    payload: HandoffRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Rejects an incoming handoff request with justification (Destination LEA).
    """
    handoff = reject_case_handoff(
        db=db,
        handoff_id=handoff_id,
        rejection_reason=payload.rejection_reason,
        current_user=current_user
    )
    return _format_handoff_response(handoff)


@router.post(
    "/handoffs/{handoff_id}/start",
    response_model=CaseHandoffResponse
)
def start_handoff(
    handoff_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Transitions an accepted handoff to IN_PROGRESS state.
    """
    handoff = start_case_handoff(db=db, handoff_id=handoff_id, current_user=current_user)
    return _format_handoff_response(handoff)


@router.post(
    "/handoffs/{handoff_id}/complete",
    response_model=CaseHandoffResponse
)
def complete_handoff(
    handoff_id: int,
    payload: HandoffCompleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Completes a handoff action with outcome notes (Destination LEA).
    """
    handoff = complete_case_handoff(
        db=db,
        handoff_id=handoff_id,
        completed_notes=payload.completed_notes,
        current_user=current_user
    )
    return _format_handoff_response(handoff)


@router.post(
    "/handoffs/{handoff_id}/cancel",
    response_model=CaseHandoffResponse
)
def cancel_handoff(
    handoff_id: int,
    payload: HandoffCancelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Cancels an active or pending handoff (Originating LEA).
    """
    handoff = cancel_case_handoff(
        db=db,
        handoff_id=handoff_id,
        cancellation_reason=payload.cancellation_reason,
        current_user=current_user
    )
    return _format_handoff_response(handoff)


@router.post(
    "/handoffs/check-expirations",
    response_model=dict
)
def check_expirations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Triggerable endpoint to evaluate acknowledgement deadlines and expire overdue requests.
    """
    expired_ids = check_and_expire_handoffs(db=db)
    return {"status": "SUCCESS", "expired_handoff_ids": expired_ids, "count": len(expired_ids)}
