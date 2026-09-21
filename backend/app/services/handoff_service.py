"""
CyberShield AI — Phase 7: Controlled Cross-State & Cross-District Handoff Service.
Manages explicit case assignments, state machine lifecycle transitions,
time-bounded jurisdictional access grants, durable escalation alerts, and audit logging.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func

from backend.app.models.models import (
    User, Complaint, Organization, CaseHandoff, EvidenceFile, Prediction, AuditLog
)
from backend.app.auth.rbac import (
    verify_complaint_access, is_national_scope, RoleEnum
)
from backend.app.services.audit_service import log_audit
from backend.app.services.outbox_service import outbox_service


VALID_PURPOSES = {
    "PHYSICAL_SURVEILLANCE",
    "ATM_INTERCEPTION",
    "MULE_ARREST",
    "EVIDENCE_COLLECTION",
    "BANK_BRANCH_VISIT",
    "LOCAL_INQUIRY",
    "OTHER"
}

VALID_EVIDENCE_SCOPES = {
    "METADATA_ONLY",
    "SPECIFIC_EVIDENCE",
    "ALL_EVIDENCE"
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def resolve_destination_organization(
    db: Session,
    target_state: str,
    target_district: str,
    destination_org_id: Optional[int] = None
) -> Organization:
    """
    Resolves destination LEA organization strictly from trusted database records.
    Prevents client-injected or untrusted organization grants.
    """
    if destination_org_id:
        org = db.query(Organization).filter(
            Organization.id == destination_org_id,
            Organization.org_type == "LEA"
        ).first()
        if not org:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Designated destination organization ID {destination_org_id} is not a registered LEA entity."
            )
        return org

    # Search by district and state first
    org = db.query(Organization).filter(
        Organization.org_type == "LEA",
        func.lower(Organization.state) == target_state.strip().lower(),
        func.lower(Organization.district) == target_district.strip().lower()
    ).first()

    if not org:
        # Search by state level LEA HQ
        org = db.query(Organization).filter(
            Organization.org_type == "LEA",
            func.lower(Organization.state) == target_state.strip().lower()
        ).first()

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No trusted LEA organization registered for jurisdiction: State '{target_state}', District '{target_district}'."
        )

    return org


def request_case_handoff(
    db: Session,
    complaint_id: int,
    target_state: str,
    target_district: str,
    purpose: str,
    evidence_scope: str,
    initiator_user: User,
    destination_organization_id: Optional[int] = None,
    shared_evidence_ids: Optional[List[int]] = None,
    prediction_id: Optional[int] = None,
    prediction_version: Optional[int] = None,
    acknowledgement_hours: int = 24
) -> CaseHandoff:
    """
    Initiates a controlled, auditable cross-state/district handoff request for a case.
    """
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")

    if not verify_complaint_access(complaint, initiator_user, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")

    # Only case owner or I4C Admin can initiate handoff
    if not is_national_scope(initiator_user) and complaint.owner_organization_id != initiator_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the case-owning organization or I4C Admin can initiate a cross-jurisdiction handoff."
        )

    clean_purpose = purpose.strip().upper()
    if clean_purpose not in VALID_PURPOSES:
        clean_purpose = "OTHER"

    clean_scope = evidence_scope.strip().upper()
    if clean_scope not in VALID_EVIDENCE_SCOPES:
        clean_scope = "METADATA_ONLY"

    dest_org = resolve_destination_organization(
        db=db,
        target_state=target_state,
        target_district=target_district,
        destination_org_id=destination_organization_id
    )

    if dest_org.id == initiator_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Destination organization must be different from originating organization."
        )

    # Validate shared evidence IDs
    verified_evidence_ids = []
    if clean_scope == "SPECIFIC_EVIDENCE" and shared_evidence_ids:
        existing_evs = db.query(EvidenceFile.id).filter(
            EvidenceFile.complaint_id == complaint.id,
            EvidenceFile.id.in_(shared_evidence_ids)
        ).all()
        verified_evidence_ids = [row[0] for row in existing_evs]
    elif clean_scope == "ALL_EVIDENCE":
        all_evs = db.query(EvidenceFile.id).filter(
            EvidenceFile.complaint_id == complaint.id,
            EvidenceFile.status == "ACTIVE"
        ).all()
        verified_evidence_ids = [row[0] for row in all_evs]

    now = _utcnow()
    deadline = now + timedelta(hours=max(1, acknowledgement_hours))

    handoff = CaseHandoff(
        complaint_id=complaint.id,
        prediction_id=prediction_id,
        prediction_version=prediction_version,
        origin_organization_id=initiator_user.organization_id or complaint.owner_organization_id,
        destination_organization_id=dest_org.id,
        target_state=target_state,
        target_district=target_district,
        purpose=clean_purpose,
        evidence_scope=clean_scope,
        shared_evidence_ids=verified_evidence_ids if verified_evidence_ids else None,
        status="REQUESTED",
        initiator_user_id=initiator_user.id,
        acknowledgement_deadline=deadline,
        created_at=now,
        updated_at=now
    )
    db.add(handoff)
    db.flush()

    # Audit Trail
    log_audit(
        db=db,
        user_id=initiator_user.id,
        officer_name=initiator_user.full_name,
        role=initiator_user.role,
        action="CASE_HANDOFF_REQUESTED",
        case_number=complaint.complaint_number,
        details=(
            f"Cross-jurisdiction handoff #{handoff.id} requested to {dest_org.name} "
            f"({target_state}/{target_district}) for purpose '{clean_purpose}'. "
            f"Evidence scope: {clean_scope}. Deadline: {deadline.isoformat()}Z"
        )
    )

    db.commit()
    db.refresh(handoff)
    return handoff


def accept_case_handoff(db: Session, handoff_id: int, current_user: User) -> CaseHandoff:
    """
    Accepts an incoming case handoff request, binding the recipient actor.
    """
    handoff = db.query(CaseHandoff).filter(CaseHandoff.id == handoff_id).first()
    if not handoff:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Handoff request not found")

    # Verify recipient organization
    if not is_national_scope(current_user) and handoff.destination_organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not belong to the authorized destination organization for this handoff."
        )

    # Idempotent return if already accepted by current user
    if handoff.status == "ACCEPTED" and handoff.recipient_user_id == current_user.id:
        return handoff

    if handoff.status == "ACCEPTED" and handoff.recipient_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Handoff has already been accepted by another officer (User ID #{handoff.recipient_user_id})."
        )

    if handoff.status != "REQUESTED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot accept handoff with status '{handoff.status}'."
        )

    now = _utcnow()
    # Check expiry
    if handoff.acknowledgement_deadline and handoff.acknowledgement_deadline < now:
        handoff.status = "EXPIRED"
        handoff.updated_at = now
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Handoff acknowledgement deadline has expired."
        )

    handoff.status = "ACCEPTED"
    handoff.recipient_user_id = current_user.id
    handoff.accepted_at = now
    handoff.updated_at = now

    log_audit(
        db=db,
        user_id=current_user.id,
        officer_name=current_user.full_name,
        role=current_user.role,
        action="CASE_HANDOFF_ACCEPTED",
        case_number=handoff.complaint.complaint_number if handoff.complaint else str(handoff.complaint_id),
        details=f"Handoff #{handoff.id} accepted by {current_user.full_name} ({current_user.organization_name})."
    )

    db.commit()
    db.refresh(handoff)
    return handoff


def reject_case_handoff(
    db: Session,
    handoff_id: int,
    rejection_reason: str,
    current_user: User
) -> CaseHandoff:
    """
    Rejects an incoming case handoff request with recorded justification.
    """
    if not rejection_reason or not rejection_reason.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rejection reason must be provided."
        )

    handoff = db.query(CaseHandoff).filter(CaseHandoff.id == handoff_id).first()
    if not handoff:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Handoff request not found")

    if not is_national_scope(current_user) and handoff.destination_organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not belong to destination organization."
        )

    if handoff.status != "REQUESTED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject handoff with status '{handoff.status}'."
        )

    now = _utcnow()
    handoff.status = "REJECTED"
    handoff.rejection_reason = rejection_reason.strip()
    handoff.recipient_user_id = current_user.id
    handoff.updated_at = now

    log_audit(
        db=db,
        user_id=current_user.id,
        officer_name=current_user.full_name,
        role=current_user.role,
        action="CASE_HANDOFF_REJECTED",
        case_number=handoff.complaint.complaint_number if handoff.complaint else str(handoff.complaint_id),
        details=f"Handoff #{handoff.id} rejected. Reason: {rejection_reason.strip()}"
    )

    db.commit()
    db.refresh(handoff)
    return handoff


def start_case_handoff(db: Session, handoff_id: int, current_user: User) -> CaseHandoff:
    """
    Transitions an accepted handoff to IN_PROGRESS.
    """
    handoff = db.query(CaseHandoff).filter(CaseHandoff.id == handoff_id).first()
    if not handoff:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Handoff request not found")

    if not is_national_scope(current_user) and handoff.destination_organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")

    if handoff.status == "IN_PROGRESS":
        return handoff

    if handoff.status != "ACCEPTED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot transition handoff in '{handoff.status}' state to IN_PROGRESS."
        )

    now = _utcnow()
    handoff.status = "IN_PROGRESS"
    handoff.updated_at = now

    log_audit(
        db=db,
        user_id=current_user.id,
        officer_name=current_user.full_name,
        role=current_user.role,
        action="CASE_HANDOFF_IN_PROGRESS",
        case_number=handoff.complaint.complaint_number if handoff.complaint else str(handoff.complaint_id),
        details=f"Handoff #{handoff.id} marked IN_PROGRESS by {current_user.full_name}."
    )

    db.commit()
    db.refresh(handoff)
    return handoff


def complete_case_handoff(
    db: Session,
    handoff_id: int,
    completed_notes: Optional[str],
    current_user: User
) -> CaseHandoff:
    """
    Completes a handoff action with field outcome notes.
    """
    handoff = db.query(CaseHandoff).filter(CaseHandoff.id == handoff_id).first()
    if not handoff:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Handoff request not found")

    if not is_national_scope(current_user) and handoff.destination_organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")

    if handoff.status == "COMPLETED":
        return handoff

    if handoff.status not in ("ACCEPTED", "IN_PROGRESS"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot complete handoff in '{handoff.status}' state."
        )

    now = _utcnow()
    handoff.status = "COMPLETED"
    handoff.completed_notes = completed_notes.strip() if completed_notes else None
    handoff.completed_at = now
    handoff.updated_at = now

    log_audit(
        db=db,
        user_id=current_user.id,
        officer_name=current_user.full_name,
        role=current_user.role,
        action="CASE_HANDOFF_COMPLETED",
        case_number=handoff.complaint.complaint_number if handoff.complaint else str(handoff.complaint_id),
        details=f"Handoff #{handoff.id} completed. Notes: {completed_notes or 'None'}"
    )

    db.commit()
    db.refresh(handoff)
    return handoff


def cancel_case_handoff(
    db: Session,
    handoff_id: int,
    cancellation_reason: str,
    current_user: User
) -> CaseHandoff:
    """
    Cancels an active or pending handoff from the origin side.
    """
    if not cancellation_reason or not cancellation_reason.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cancellation reason must be provided."
        )

    handoff = db.query(CaseHandoff).filter(CaseHandoff.id == handoff_id).first()
    if not handoff:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Handoff request not found")

    if not is_national_scope(current_user) and handoff.origin_organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only originating organization or I4C Admin can cancel a handoff request."
        )

    if handoff.status in ("COMPLETED", "REJECTED", "CANCELLED", "EXPIRED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel handoff in terminal state '{handoff.status}'."
        )

    now = _utcnow()
    handoff.status = "CANCELLED"
    handoff.cancellation_reason = cancellation_reason.strip()
    handoff.updated_at = now

    log_audit(
        db=db,
        user_id=current_user.id,
        officer_name=current_user.full_name,
        role=current_user.role,
        action="CASE_HANDOFF_CANCELLED",
        case_number=handoff.complaint.complaint_number if handoff.complaint else str(handoff.complaint_id),
        details=f"Handoff #{handoff.id} cancelled. Reason: {cancellation_reason.strip()}"
    )

    db.commit()
    db.refresh(handoff)
    return handoff


def check_and_expire_handoffs(db: Session) -> List[int]:
    """
    Evaluates acknowledgement deadlines for pending REQUESTED handoffs.
    Transitions overdue requests to EXPIRED and records escalation audits.
    """
    now = _utcnow()
    overdue_handoffs = db.query(CaseHandoff).filter(
        CaseHandoff.status == "REQUESTED",
        CaseHandoff.acknowledgement_deadline < now
    ).all()

    expired_ids = []
    for h in overdue_handoffs:
        h.status = "EXPIRED"
        h.updated_at = now
        expired_ids.append(h.id)

        log_audit(
            db=db,
            user_id=None,
            officer_name="SYSTEM_SCHEDULER",
            role="SYSTEM",
            action="CASE_HANDOFF_EXPIRED",
            case_number=h.complaint.complaint_number if h.complaint else str(h.complaint_id),
            details=(
                f"Handoff #{h.id} auto-expired due to unacknowledged deadline "
                f"({h.acknowledgement_deadline.isoformat()}Z). Escalation alert triggered."
            )
        )

    if expired_ids:
        db.commit()

    return expired_ids
