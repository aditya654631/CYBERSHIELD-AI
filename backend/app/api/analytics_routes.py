from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.models.db import get_db
from backend.app.models.models import User
from backend.app.schemas.schemas import AnalyticsOverviewResponse
from backend.app.auth.security import get_current_user

router = APIRouter(prefix="/analytics", tags=["Analytics & Overview"])


@router.get("/overview", response_model=AnalyticsOverviewResponse)
def get_analytics_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from backend.app.services.dashboard_service import dashboard_service
    summary = dashboard_service.get_dashboard_summary(db, user=current_user)
    kpis = summary["kpis"]

    return {
        "active_complaints": kpis["active_complaints"],
        "critical_risk_cases": kpis["high_risk_predictions"],
        "predicted_cashout_events": summary["mode_distribution"]["total"],
        "high_risk_districts": len(summary["regional_distribution"]),
        "total_amount_at_risk": kpis["total_amount_at_risk"],
        "alerts_acknowledged_today": kpis["acknowledged_alerts"],
        "fraud_types": summary["fraud_type_distribution"],
        "cases_over_time": summary["cases_over_time"],
        "hourly_risk": summary.get("hourly_risk") or [],
        "regional_risk": summary["regional_distribution"]
    }


@router.get("/fraud-types")
def get_fraud_types(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from backend.app.services.dashboard_service import dashboard_service
    rows = dashboard_service.get_dashboard_summary(db, user=current_user)["fraud_type_distribution"]
    return [
        {
            "type": row["name"],
            "cases": row["count"],
            "amount": row["amount"],
            "percentage": row["percentage"],
            "data_basis": "authorized_persisted_cases",
        }
        for row in rows
    ]


@router.get("/timeline")
def get_timeline(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from backend.app.services.dashboard_service import dashboard_service
    rows = dashboard_service.get_dashboard_summary(db, user=current_user)["recent_complaints"]
    return [
        {
            "timestamp": row["reported_at"],
            "event": f"{row['complaint_number']}: complaint status {row['case_status']}",
            "complaint_number": row["complaint_number"],
            "data_basis": "authorized_persisted_case",
        }
        for row in rows
    ]
