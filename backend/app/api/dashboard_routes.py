from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.models.db import get_db
from backend.app.models.models import User
from backend.app.schemas.schemas import DashboardSummaryResponse
from backend.app.services.dashboard_service import dashboard_service
from backend.app.auth.security import get_current_user

router = APIRouter(prefix="/dashboard", tags=["Dashboard Analytics"])


@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Read-only dashboard summary endpoint.
    Requires JWT and produces deterministic KPIs and distributions
    scoped by officer jurisdiction.
    """
    return dashboard_service.get_dashboard_summary(db, user=current_user)
