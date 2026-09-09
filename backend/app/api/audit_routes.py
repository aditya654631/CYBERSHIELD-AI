from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.models.db import get_db
from backend.app.models.models import AuditLog
from backend.app.schemas.schemas import AuditLogResponse

router = APIRouter(prefix="/audit", tags=["System Audit & Compliance"])

@router.get("", response_model=List[AuditLogResponse])
@router.get("/logs", response_model=List[AuditLogResponse])
def get_audit_logs(
    action: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    query = db.query(AuditLog)
    if action and action != "ALL":
        query = query.filter(AuditLog.action == action)
    return query.order_by(AuditLog.created_at.desc()).limit(limit).all()
