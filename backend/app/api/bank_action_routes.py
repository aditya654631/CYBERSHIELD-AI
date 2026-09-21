"""
CyberShield AI — Phase 8: Bank Action & Financial Intervention Routes
Exposes endpoints for creating, reviewing, dispatching, releasing, and receiving partner callbacks
for bank hold operations with strict jurisdiction isolation, truthful status enforcement,
and environment separation (SIMULATED, SANDBOX, LIVE).
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Header, status, Request
from sqlalchemy.orm import Session

from backend.app.models.db import get_db
from backend.app.models.models import BankAction, Complaint, User
from backend.app.schemas.schemas import (
    BankActionResponse, BankActionCreateRequest, BankActionReleaseRequest,
    BankActionTransitionRequest, BankPartnerCallbackPayload, SandboxSimulateRequest
)
from backend.app.auth.security import get_current_user
from backend.app.auth.rbac import (
    require_roles, filter_complaints_by_jurisdiction,
    verify_bank_action_access, RoleEnum, is_national_scope
)
from backend.app.services.bank_action_service import bank_action_service

router = APIRouter(prefix="/bank-actions", tags=["Bank Actions & Interventions"])


@router.get("", response_model=List[BankActionResponse])
def list_bank_actions(
    status_filter: Optional[str] = None,
    environment_filter: Optional[str] = None,
    complaint_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists bank actions filtered by officer jurisdiction and role.
    LEA officers only see actions for complaints within their state/district or explicit handoffs.
    Bank officers only see actions involving their registered bank.
    Auditors and National Admins have national scope.
    """
    query = db.query(BankAction).join(Complaint, BankAction.complaint_id == Complaint.id)

    if current_user.role == RoleEnum.BANK_OFFICER:
        if not current_user.organization_id or not current_user.organization or current_user.organization.org_type != "BANK":
            return []
        query = query.filter(BankAction.bank_organization_id == current_user.organization_id)
    elif not is_national_scope(current_user):
        visible_ids = filter_complaints_by_jurisdiction(
            db.query(Complaint.id), current_user, db
        )
        query = query.filter(BankAction.complaint_id.in_(visible_ids))

    if complaint_id:
        query = query.filter(BankAction.complaint_id == complaint_id)

    if status_filter and status_filter.upper() != "ALL":
        query = query.filter(BankAction.status == status_filter.upper())

    if environment_filter and environment_filter.upper() != "ALL":
        query = query.filter(BankAction.environment == environment_filter.upper())

    return query.order_by(BankAction.created_at.desc()).all()


@router.get("/{id}", response_model=BankActionResponse)
def get_bank_action(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves bank action details with object-level jurisdiction check.
    Returns 404 if inaccessible to prevent leaking record existence.
    """
    if id.isdigit():
        action = db.query(BankAction).filter(BankAction.id == int(id)).first()
    else:
        action = db.query(BankAction).filter(BankAction.action_reference == id).first()

    if not action:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank action not found")

    if not verify_bank_action_access(action, current_user, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank action not found")

    return action


@router.post("", response_model=BankActionResponse, status_code=status.HTTP_201_CREATED)
def create_bank_action(
    data: BankActionCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Creates a new explicit bank action (hold/freeze request).
    Enforces role, jurisdiction, and target bank relationships.
    """
    return bank_action_service.create_direct_action(
        db=db,
        complaint_id=data.complaint_id,
        user=current_user,
        action_type=data.action_type,
        alert_id=data.alert_id,
        account_id=data.account_id,
        target_account_number=data.target_account_number,
        target_ifsc=data.target_ifsc,
        bank_name=data.bank_name,
        bank_organization_id=data.bank_organization_id,
        requested_amount=data.requested_amount,
        currency=data.currency,
        environment=data.environment,
        action_notes=data.action_notes,
        idempotency_key=data.idempotency_key
    )


@router.post("/{id}/approve", response_model=BankActionResponse)
def approve_bank_action(
    id: str,
    notes: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.I4C_ADMIN, RoleEnum.STATE_LEA, RoleEnum.DISTRICT_LEA))
):
    """
    Approves a requested bank action.
    Restricted to authorized LEA supervisors and I4C National Admins.
    """
    if id.isdigit():
        action = db.query(BankAction).filter(BankAction.id == int(id)).first()
    else:
        action = db.query(BankAction).filter(BankAction.action_reference == id).first()

    if not action:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank action not found")

    if not verify_bank_action_access(action, current_user, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank action not found")

    return bank_action_service.approve_action(db=db, action_id=action.id, user=current_user, notes=notes)


@router.post("/{id}/dispatch", response_model=BankActionResponse)
def dispatch_bank_action(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.I4C_ADMIN, RoleEnum.BANK_OFFICER, RoleEnum.STATE_LEA, RoleEnum.DISTRICT_LEA))
):
    """
    Dispatches an approved bank action to the designated Bank Adapter.
    Transitions status to SENT (never CONFIRMED_HOLD).
    """
    if id.isdigit():
        action = db.query(BankAction).filter(BankAction.id == int(id)).first()
    else:
        action = db.query(BankAction).filter(BankAction.action_reference == id).first()

    if not action:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank action not found")

    if not verify_bank_action_access(action, current_user, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank action not found")

    return bank_action_service.dispatch_action(db=db, action_id=action.id, user=current_user)


@router.post("/{id}/release", response_model=BankActionResponse)
def release_bank_action(
    id: str,
    data: BankActionReleaseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.I4C_ADMIN, RoleEnum.BANK_OFFICER, RoleEnum.STATE_LEA, RoleEnum.DISTRICT_LEA))
):
    """
    Releases an active hold (CONFIRMED_HOLD or PARTIAL_HOLD).
    """
    if id.isdigit():
        action = db.query(BankAction).filter(BankAction.id == int(id)).first()
    else:
        action = db.query(BankAction).filter(BankAction.action_reference == id).first()

    if not action:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank action not found")

    if not verify_bank_action_access(action, current_user, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank action not found")

    return bank_action_service.release_action(
        db=db,
        action_id=action.id,
        user=current_user,
        release_reason=data.release_reason,
        release_amount=data.release_amount
    )


@router.post("/{id}/cancel", response_model=BankActionResponse)
def cancel_bank_action(
    id: str,
    cancellation_reason: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.I4C_ADMIN, RoleEnum.STATE_LEA, RoleEnum.DISTRICT_LEA, RoleEnum.BANK_OFFICER))
):
    """
    Cancels a pending bank action before hold establishment.
    """
    if id.isdigit():
        action = db.query(BankAction).filter(BankAction.id == int(id)).first()
    else:
        action = db.query(BankAction).filter(BankAction.action_reference == id).first()

    if not action:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank action not found")

    if not verify_bank_action_access(action, current_user, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank action not found")

    return bank_action_service.cancel_action(
        db=db,
        action_id=action.id,
        user=current_user,
        cancellation_reason=cancellation_reason
    )


@router.post("/{id}/transition", response_model=BankActionResponse)
def transition_bank_action(
    id: str,
    data: BankActionTransitionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.BANK_OFFICER, RoleEnum.I4C_ADMIN))
):
    """
    Transitions a bank action through standard lifecycle.
    Blocks client-forged transitions to CONFIRMED_HOLD or PARTIAL_HOLD.
    """
    if id.isdigit():
        action = db.query(BankAction).filter(BankAction.id == int(id)).first()
    else:
        action = db.query(BankAction).filter(BankAction.action_reference == id).first()

    if not action:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank action not found")

    if not verify_bank_action_access(action, current_user, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank action not found")

    return bank_action_service.transition_action(
        db=db,
        action_id=action.id,
        target_status=data.target_status,
        user=current_user,
        notes=data.notes,
        failure_reason=data.failure_reason
    )


@router.post("/callback")
def receive_partner_callback(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    x_bank_signature: Optional[str] = Header(None, alias="X-Bank-Signature"),
    x_bank_timestamp: Optional[str] = Header(None, alias="X-Bank-Timestamp"),
    x_bank_callback_id: Optional[str] = Header(None, alias="X-Bank-Callback-Id")
):
    """
    Asynchronous partner callback webhook endpoint.
    Requires cryptographic HMAC signature, timestamp skew validation, and replay protection.
    """
    if not x_bank_signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing required 'X-Bank-Signature' authentication header."
        )

    if not x_bank_timestamp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required 'X-Bank-Timestamp' header."
        )

    if not x_bank_callback_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required 'X-Bank-Callback-Id' header for replay protection."
        )

    return bank_action_service.process_partner_callback(
        db=db,
        payload=payload,
        signature=x_bank_signature,
        timestamp_str=x_bank_timestamp,
        callback_id=x_bank_callback_id
    )


@router.post("/{id}/sandbox-simulate")
def sandbox_simulate_outcome(
    id: str,
    data: SandboxSimulateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.I4C_ADMIN, RoleEnum.BANK_OFFICER, RoleEnum.STATE_LEA, RoleEnum.DISTRICT_LEA))
):
    """
    Triggers a deterministic sandbox callback simulation for integration tests and demo environments.
    """
    if id.isdigit():
        action = db.query(BankAction).filter(BankAction.id == int(id)).first()
    else:
        action = db.query(BankAction).filter(BankAction.action_reference == id).first()

    if not action:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank action not found")

    if not verify_bank_action_access(action, current_user, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank action not found")

    if action.environment == "LIVE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot execute sandbox simulation on LIVE environment actions."
        )

    return bank_action_service.sandbox_simulate_outcome(
        db=db,
        action_id=action.id,
        simulated_outcome=data.simulated_outcome,
        held_amount=data.held_amount,
        reason=data.reason
    )
