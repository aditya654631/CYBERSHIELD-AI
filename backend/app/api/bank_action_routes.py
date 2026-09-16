"""
CyberShield AI — Bank Action Routes
Exposes endpoints for listing, viewing, and transitioning bank hold actions
with strict jurisdiction isolation and truthful status enforcement.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.models.db import get_db
from backend.app.models.models import BankAction, Complaint, User
from backend.app.schemas.schemas import BankActionResponse, BankActionTransitionRequest
from backend.app.auth.security import get_current_user
from backend.app.auth.rbac import require_roles, verify_complaint_access, RoleEnum
from backend.app.services.bank_action_service import bank_action_service

router = APIRouter(prefix="/bank-actions", tags=["Bank Actions & Interventions"])


@router.get("", response_model=List[BankActionResponse])
def list_bank_actions(
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists bank actions filtered by officer jurisdiction.
    LEA officers only see actions for complaints within their state/district.
    Bank officers only see actions involving their bank.
    """
    query = db.query(BankAction).join(Complaint, BankAction.complaint_id == Complaint.id)

    # Jurisdiction filter
    if current_user.role == RoleEnum.STATE_LEA:
        state = current_user.organization.state if current_user.organization else "Delhi"
        query = query.filter(Complaint.state.ilike(state))
    elif current_user.role == RoleEnum.DISTRICT_LEA:
        state = current_user.organization.state if current_user.organization else "Delhi"
        district = current_user.organization.district if current_user.organization else "Central"
        query = query.filter(Complaint.state.ilike(state), Complaint.district.ilike(district))
    elif current_user.role == RoleEnum.BANK_OFFICER:
        bank_kw = current_user.organization.name if current_user.organization else ""
        if bank_kw:
            query = query.filter(BankAction.bank_name.ilike(f"%{bank_kw}%"))
        else:
            return []

    if status_filter and status_filter.upper() != "ALL":
        query = query.filter(BankAction.status == status_filter.upper())

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

    complaint = db.query(Complaint).filter(Complaint.id == action.complaint_id).first()
    if not complaint or not verify_complaint_access(complaint, current_user, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank action not found")

    return action


@router.post("/{id}/transition", response_model=BankActionResponse)
def transition_bank_action(
    id: str,
    data: BankActionTransitionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.BANK_OFFICER, RoleEnum.I4C_ADMIN))
):
    """
    Transitions a bank action through its lifecycle.
    Restricted to BANK_OFFICER and I4C_ADMIN.
    """
    if id.isdigit():
        action = db.query(BankAction).filter(BankAction.id == int(id)).first()
    else:
        action = db.query(BankAction).filter(BankAction.action_reference == id).first()

    if not action:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank action not found")

    complaint = db.query(Complaint).filter(Complaint.id == action.complaint_id).first()
    if not complaint or not verify_complaint_access(complaint, current_user, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank action not found")

    return bank_action_service.transition_action(
        db=db,
        action_id=action.id,
        target_status=data.target_status,
        user=current_user,
        notes=data.notes,
        failure_reason=data.failure_reason
    )

