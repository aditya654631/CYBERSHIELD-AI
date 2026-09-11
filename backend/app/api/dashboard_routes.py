from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.models.db import get_db
from backend.app.schemas.schemas import DashboardSummaryResponse
from backend.app.services.dashboard_service import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard Analytics"])


@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(db: Session = Depends(get_db)):
    """
    Read-only dashboard summary endpoint.
    Produces deterministic KPIs, risk distribution, recent complaints,
    recent predictions, and recent alerts in a single database read transaction.
    Zero mutations, zero ML invocations, zero prediction writes, zero alert writes.
    """
    return dashboard_service.get_dashboard_summary(db)
