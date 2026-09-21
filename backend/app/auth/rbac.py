"""
CyberShield AI — Role-Based Access Control (RBAC) & Jurisdiction Isolation
Centralized authorization dependency and multi-tenant jurisdiction isolation filters.

Roles:
- I4C_ADMIN: Full platform access nationwide.
- STATE_LEA: Access only to records in the officer's state.
- DISTRICT_LEA: Access only to records in the officer's district and state.
- BANK_OFFICER: Access only to cases and hold actions involving the officer's bank.
- ANALYST: Scoped read and intelligence-analysis access; forbidden from operational mutations and bank holds.
- AUDITOR: Read-only audit log and evidence verification access; forbidden from mutations.
"""

from enum import Enum
import re
from typing import Callable, List, Optional, Set
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from backend.app.auth.security import get_current_user
from backend.app.models.models import (
    User, Complaint, Account, ComplaintAccount, Transaction, Alert,
    Organization, BankAction, CaseHandoff,
)


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
        normalized_allowed = {getattr(role, "value", role) for role in allowed_roles}
        if current_user.role not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: Officer role '{current_user.role}' lacks permission for this operation."
            )
        return current_user

    return role_checker


def _normalized(value: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").strip().lower()).strip()


def _valid_org(user: User, expected_type: Optional[str] = None) -> bool:
    org = getattr(user, "organization", None)
    if not org or not getattr(user, "organization_id", None):
        return False
    if expected_type and (org.org_type or "").upper() != expected_type.upper():
        return False
    return True


def is_national_scope(user: User) -> bool:
    """National access is derived from trusted database role and organization."""
    if user.role == RoleEnum.I4C_ADMIN:
        return True
    return (
        user.role in (RoleEnum.ANALYST, RoleEnum.AUDITOR)
        and _valid_org(user, "I4C")
    )


def resolve_bank_organization_id(db: Session, bank_name: Optional[str]) -> Optional[int]:
    """Resolve display text once against the server-side bank organization registry.

    Authorization never compares free-text names after this mapping is stored. Ambiguous
    or unknown names deliberately remain unscoped.
    """
    target = _normalized(bank_name)
    if not target or target == "unknown":
        return None
    banks = db.query(Organization).filter(func.upper(Organization.org_type) == "BANK").all()
    exact = [org for org in banks if _normalized(org.name) == target]
    if len(exact) == 1:
        return exact[0].id
    # Registered organizations may include a unit suffix. Accept only a unique,
    # directional registry match, never a substring supplied at authorization time.
    prefixed = [org for org in banks if _normalized(org.name).startswith(target + " ")]
    return prefixed[0].id if len(prefixed) == 1 else None


def complaint_bank_organization_ids(complaint_id: int, db: Session) -> Set[int]:
    account_ids = {
        row[0] for row in db.query(Account.bank_organization_id)
        .join(ComplaintAccount, ComplaintAccount.account_id == Account.id)
        .filter(
            ComplaintAccount.complaint_id == complaint_id,
            Account.bank_organization_id.isnot(None),
        ).all()
    }
    action_ids = {
        row[0] for row in db.query(BankAction.bank_organization_id)
        .filter(
            BankAction.complaint_id == complaint_id,
            BankAction.bank_organization_id.isnot(None),
        ).all()
    }
    return account_ids | action_ids


def _filter_geographic_scope(query, user: User, db: Optional[Session] = None):
    if not _valid_org(user):
        return query.filter(Complaint.id == -1)
    state = (user.organization.state or "").strip()
    district = (user.organization.district or "").strip()
    if not state:
        return query.filter(Complaint.id == -1)
    geographic_conditions = [func.lower(Complaint.state) == state.lower()]
    if user.role == RoleEnum.DISTRICT_LEA or (
        user.role in (RoleEnum.ANALYST, RoleEnum.AUDITOR)
        and district and district.upper() not in ("ALL", "NATIONAL")
    ):
        if not district:
            return query.filter(Complaint.id == -1)
        geographic_conditions.append(func.lower(Complaint.district) == district.lower())
    geographic_scope = geographic_conditions[0]
    for condition in geographic_conditions[1:]:
        geographic_scope = geographic_scope & condition

    access_conditions = [
        Complaint.owner_organization_id == user.organization_id,
        geographic_scope,
    ]

    # Phase 7: Explicit active cross-jurisdiction handoff grants
    if db is not None and user.organization_id:
        active_handoff_comp_ids = (
            db.query(CaseHandoff.complaint_id)
            .filter(
                CaseHandoff.destination_organization_id == user.organization_id,
                CaseHandoff.status.in_(["REQUESTED", "ACCEPTED", "IN_PROGRESS"])
            )
        )
        access_conditions.append(Complaint.id.in_(active_handoff_comp_ids))

    return query.filter(or_(*access_conditions))


def filter_complaints_by_jurisdiction(query, user: User, db: Session):
    """
    Applies collection-level jurisdiction filters to Complaint queries based on the officer's role.
    Prevents cross-state, cross-district, and cross-bank data leakage while honoring explicit Phase 7 handoffs.
    """
    role = user.role

    # National access is explicit and server-derived.
    if is_national_scope(user):
        return query

    # 2. STATE_LEA: Restricted to officer's state or explicit handoffs
    if role == RoleEnum.STATE_LEA:
        return _filter_geographic_scope(query, user, db)

    # 3. DISTRICT_LEA: Restricted to officer's district and state or explicit handoffs
    if role == RoleEnum.DISTRICT_LEA:
        return _filter_geographic_scope(query, user, db)

    # 4. BANK_OFFICER: Restricted to complaints involving the officer's bank
    if role == RoleEnum.BANK_OFFICER:
        if not _valid_org(user, "BANK"):
            return query.filter(Complaint.id == -1)
        bank_acct_ids = (
            db.query(ComplaintAccount.complaint_id)
            .join(Account, ComplaintAccount.account_id == Account.id)
            .filter(Account.bank_organization_id == user.organization_id)
        )
        bank_action_ids = db.query(BankAction.complaint_id).filter(
            BankAction.bank_organization_id == user.organization_id
        )
        return query.filter(or_(Complaint.id.in_(bank_acct_ids), Complaint.id.in_(bank_action_ids)))

    # 5. ANALYST / AUDITOR: Permitted read access within platform scope
    if role in (RoleEnum.ANALYST, RoleEnum.AUDITOR):
        return _filter_geographic_scope(query, user, db)

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

    if is_national_scope(user):
        return True

    # 2. STATE_LEA & DISTRICT_LEA: Match required
    if role in (RoleEnum.STATE_LEA, RoleEnum.DISTRICT_LEA):
        return filter_complaints_by_jurisdiction(
            db.query(Complaint), user, db
        ).filter(Complaint.id == complaint.id).first() is not None

    # 4. BANK_OFFICER: Must involve officer's bank
    if role == RoleEnum.BANK_OFFICER:
        if not _valid_org(user, "BANK"):
            return False
        return user.organization_id in complaint_bank_organization_ids(complaint.id, db)

    # 5. ANALYST & AUDITOR: Permitted read access
    if role in (RoleEnum.ANALYST, RoleEnum.AUDITOR):
        scoped = filter_complaints_by_jurisdiction(
            db.query(Complaint), user, db
        ).filter(Complaint.id == complaint.id).first()
        return scoped is not None

    return False


def verify_alert_access(alert: Alert, user: User, db: Session) -> bool:
    """Verifies object-level access to an Alert via its parent Complaint."""
    if not alert:
        return False
    complaint = db.query(Complaint).filter(Complaint.id == alert.complaint_id).first()
    if not complaint:
        return False
    return verify_complaint_access(complaint, user, db)


def verify_bank_action_access(action: BankAction, user: User, db: Session) -> bool:
    if not action or not user:
        return False
    if user.role == RoleEnum.BANK_OFFICER:
        return (
            _valid_org(user, "BANK")
            and action.bank_organization_id is not None
            and action.bank_organization_id == user.organization_id
        )
    complaint = db.query(Complaint).filter(Complaint.id == action.complaint_id).first()
    return bool(complaint and verify_complaint_access(complaint, user, db))


def get_active_complaint_handoff(complaint_id: int, user: User, db: Session) -> Optional[CaseHandoff]:
    """
    Returns active CaseHandoff granting the user's organization access to the complaint, if any.
    """
    if not user or not user.organization_id:
        return None
    return (
        db.query(CaseHandoff)
        .filter(
            CaseHandoff.complaint_id == complaint_id,
            CaseHandoff.destination_organization_id == user.organization_id,
            CaseHandoff.status.in_(["REQUESTED", "ACCEPTED", "IN_PROGRESS"])
        )
        .order_by(CaseHandoff.id.desc())
        .first()
    )
