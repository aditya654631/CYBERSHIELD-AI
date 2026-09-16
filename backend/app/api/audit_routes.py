from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.models.db import get_db
from backend.app.models.models import AuditLog, User
from backend.app.schemas.schemas import AuditLogResponse
from backend.app.auth.rbac import require_roles, RoleEnum

router = APIRouter(prefix="/audit", tags=["System Audit & Compliance"])


@router.get("", response_model=List[AuditLogResponse])
@router.get("/logs", response_model=List[AuditLogResponse])
def get_audit_logs(
    action: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.I4C_ADMIN, RoleEnum.AUDITOR))
):
    """
    Retrieves system audit logs. Strictly protected and restricted to I4C_ADMIN and AUDITOR.
    All other roles receive HTTP 403 Forbidden.
    """
    query = db.query(AuditLog)
    if action and action != "ALL":
        query = query.filter(AuditLog.action == action)
    return query.order_by(AuditLog.created_at.desc()).limit(limit).all()
