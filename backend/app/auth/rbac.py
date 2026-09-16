"""
CyberShield AI — Role-Based Access Control (RBAC) & Jurisdiction Isolation
Centralized authorization dependency and multi-tenant jurisdiction isolation filters.

Roles:
- I4C_ADMIN: Full platform access nationwide.
- STATE_LEA: Access only to records in the officer's state.
- DISTRICT_LEA: Access only to records in the officer's district and state.
- BANK_OFFICER: Access only to cases and hold actions involving the officer's bank.
- ANALYST: Read and intelligence analysis access; forbidden from mutations and bank holds.
- AUDITOR: Read-only audit log and evidence verification access; forbidden from mutations.
"""

from enum import Enum
from typing import Callable, List, Optional
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.auth.security import get_current_user
from backend.app.models.models import User, Complaint, Account, ComplaintAccount, Transaction, Alert


class RoleEnum(str, Enum):
    I4C_ADMIN = "I4C_ADMIN"
    STATE_LEA = "STATE_LEA"
    DISTRICT_LEA = "DISTRICT_LEA"
    BANK_OFFICER = "BANK_OFFICER"
    ANALYST = "ANALYST"
    AUDITOR = "AUDITOR"


def require_roles(*allowed_roles: str) -> Callable:
    """
    FastAPI dependency that verifies the authenticated user has one of the allowed roles.
    Returns HTTP 401 if unauthenticated, and HTTP 403 if authenticated but unauthorized.
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: Officer role '{current_user.role}' lacks permission for this operation."
            )
        return current_user

    return role_checker


def get_user_bank_keyword(user: User) -> Optional[str]:
    """Extracts a bank keyword from the officer's organization name."""
    if not user.organization:
        return None
    org_name = user.organization.name.lower()
    if "sbi" in org_name or "state bank of india" in org_name:
        return "State Bank of India"
    if "hdfc" in org_name:
        return "HDFC Bank"
    if "icici" in org_name:
        return "ICICI Bank"
    if "axis" in org_name:
        return "Axis Bank"
    if "pnb" in org_name or "punjab national bank" in org_name:
        return "Punjab National Bank"
    return user.organization.name


def filter_complaints_by_jurisdiction(query, user: User, db: Session):
    """
    Applies collection-level jurisdiction filters to Complaint queries based on the officer's role.
    Prevents cross-state, cross-district, and cross-bank data leakage.
    """
    role = user.role

    # 1. I4C_ADMIN: Nationwide access
    if role == RoleEnum.I4C_ADMIN:
        return query

    # 2. STATE_LEA: Restricted to officer's state
    if role == RoleEnum.STATE_LEA:
        state = user.organization.state if user.organization else "Delhi"
        return query.filter(func.lower(Complaint.state) == state.lower())

    # 3. DISTRICT_LEA: Restricted to officer's district and state
    if role == RoleEnum.DISTRICT_LEA:
        state = user.organization.state if user.organization else "Delhi"
        district = user.organization.district if user.organization else "Central"
        return query.filter(
            func.lower(Complaint.state) == state.lower(),
            func.lower(Complaint.district) == district.lower()
        )

    # 4. BANK_OFFICER: Restricted to complaints involving the officer's bank
    if role == RoleEnum.BANK_OFFICER:
        bank_kw = get_user_bank_keyword(user)
        if not bank_kw:
            # If no bank association, return empty set
            return query.filter(Complaint.id == -1)

        bank_acct_subq = (
            db.query(ComplaintAccount.complaint_id)
            .join(Account, ComplaintAccount.account_id == Account.id)
            .filter(Account.bank_name.ilike(f"%{bank_kw}%"))
            .subquery()
        )
        return query.filter(Complaint.id.in_(bank_acct_subq))

    # 5. ANALYST / AUDITOR: Permitted read access within platform scope
    if role in (RoleEnum.ANALYST, RoleEnum.AUDITOR):
        return query

    # Default fallback: deny access
    return query.filter(Complaint.id == -1)


def verify_complaint_access(complaint: Complaint, user: User, db: Session) -> bool:
    """
    Performs object-level jurisdiction check.
    Returns True if user has permission to access the complaint, False otherwise.
    When False, endpoints MUST return HTTP 404 to avoid confirming the existence of out-of-jurisdiction records.
    """
    if not complaint or not user:
        return False

    role = user.role

    # 1. I4C_ADMIN has nationwide access
    if role == RoleEnum.I4C_ADMIN:
        return True

    # 2. STATE_LEA: State match required
    if role == RoleEnum.STATE_LEA:
        state = user.organization.state if user.organization else "Delhi"
        return (complaint.state or "").strip().lower() == state.strip().lower()

    # 3. DISTRICT_LEA: State AND District match required
    if role == RoleEnum.DISTRICT_LEA:
        state = user.organization.state if user.organization else "Delhi"
        district = user.organization.district if user.organization else "Central"
        return (
            (complaint.state or "").strip().lower() == state.strip().lower() and
            (complaint.district or "").strip().lower() == district.strip().lower()
        )

    # 4. BANK_OFFICER: Must involve officer's bank
    if role == RoleEnum.BANK_OFFICER:
        bank_kw = get_user_bank_keyword(user)
        if not bank_kw:
            return False

        # Check if any associated account belongs to officer's bank
        has_bank_account = (
            db.query(ComplaintAccount)
            .join(Account, ComplaintAccount.account_id == Account.id)
            .filter(
                ComplaintAccount.complaint_id == complaint.id,
                Account.bank_name.ilike(f"%{bank_kw}%")
            )
            .first()
        ) is not None
        return has_bank_account

    # 5. ANALYST & AUDITOR: Permitted read access to permitted evidence
    if role in (RoleEnum.ANALYST, RoleEnum.AUDITOR):
        return True

    return False


def verify_alert_access(alert: Alert, user: User, db: Session) -> bool:
    """Verifies object-level access to an Alert via its parent Complaint."""
    if not alert:
        return False
    complaint = db.query(Complaint).filter(Complaint.id == alert.complaint_id).first()
    if not complaint:
        return False
    return verify_complaint_access(complaint, user, db)
