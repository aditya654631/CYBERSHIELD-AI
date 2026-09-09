from sqlalchemy.orm import Session
from backend.app.models.models import AuditLog
from typing import Optional

def log_audit(
    db: Session,
    officer_name: str,
    role: str,
    action: str,
    case_number: Optional[str] = None,
    details: Optional[str] = None,
    ip_address: str = "127.0.0.1",
    user_id: Optional[int] = None
) -> AuditLog:
    entry = AuditLog(
        user_id=user_id,
        officer_name=officer_name,
        role=role,
        action=action,
        case_number=case_number,
        details=details,
        ip_address=ip_address
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
