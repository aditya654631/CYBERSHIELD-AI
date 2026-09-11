from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.models.db import get_db
from backend.app.models.models import Complaint, Alert, Prediction, LocationCluster
from backend.app.schemas.schemas import AnalyticsOverviewResponse

router = APIRouter(prefix="/analytics", tags=["Analytics & Overview"])

@router.get("/overview", response_model=AnalyticsOverviewResponse)
def get_analytics_overview(db: Session = Depends(get_db)):
    from backend.app.services.dashboard_service import dashboard_service
    summary = dashboard_service.get_dashboard_summary(db)
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
def get_fraud_types():
    return [
        {"type": "Investment Scam", "cases": 184, "avg_amount": 77173, "risk_velocity": "Moderate (4-8h)"},
        {"type": "UPI / QR Code Fraud", "cases": 142, "avg_amount": 43661, "risk_velocity": "Ultra Fast (<2h)"},
        {"type": "Digital Arrest / Sextortion", "cases": 78, "avg_amount": 108974, "risk_velocity": "Fast (2-4h)"},
        {"type": "Part-time Job Scam", "cases": 56, "avg_amount": 60714, "risk_velocity": "Moderate (4-6h)"},
        {"type": "Loan App Extortion", "cases": 40, "avg_amount": 55000, "risk_velocity": "Slow (>8h)"}
    ]

@router.get("/timeline")
def get_timeline():
    return [
        {"timestamp": "20:15", "event": "CMP-1042: AI Prediction flagged Vijay Nagar ATM Cluster (87% Risk)"},
        {"timestamp": "19:42", "event": "CMP-1042: Layer 2 fund split into Mule accounts ACC••••8129 and ACC••••6291"},
        {"timestamp": "19:35", "event": "CMP-1042: Initial victim transfer ₹1,25,000 via UPI (SBI -> HDFC)"},
        {"timestamp": "19:28", "event": "CMP-1042: Cybercrime complaint registered by victim Rajesh Sharma in Bhopal"}
    ]
