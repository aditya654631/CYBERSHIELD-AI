from datetime import datetime
from sqlalchemy.orm import Session
from backend.app.models.models import Alert, Complaint
from typing import Optional

def trigger_alert_if_needed(
    db: Session,
    complaint_id: int,
    prediction_id: Optional[int],
    location_name: str,
    risk_score: float,
    expected_window: str,
    amount_at_risk: float
) -> Optional[Alert]:
    # If risk >= 0.80, create CRITICAL alert if not already exists for this complaint
    if risk_score >= 0.80:
        complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
        comp_num = complaint.complaint_number if complaint else f"CMP-{complaint_id}"

        # Check existing alert
        existing = db.query(Alert).filter(
            Alert.complaint_id == complaint_id,
            Alert.status.in_(["NEW", "ACKNOWLEDGED", "ACTION_INITIATED"])
        ).first()

        if existing:
            # Update existing alert with latest location and risk
            existing.risk_score = risk_score
            existing.location_name = location_name
            existing.expected_window = expected_window
            existing.prediction_id = prediction_id
            db.commit()
            db.refresh(existing)
            return existing

        alert = Alert(
            complaint_id=complaint_id,
            prediction_id=prediction_id,
            title=f"CRITICAL CASH-OUT IMMINENT: {location_name} ({comp_num})",
            severity="CRITICAL",
            location_name=location_name,
            risk_score=risk_score,
            expected_window=expected_window,
            amount_at_risk=amount_at_risk,
            status="NEW",
            created_at=datetime.utcnow()
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        return alert
    elif risk_score >= 0.60:
        # High alert
        alert = Alert(
            complaint_id=complaint_id,
            prediction_id=prediction_id,
            title=f"HIGH RISK CASH-OUT WARNING: {location_name}",
            severity="HIGH",
            location_name=location_name,
            risk_score=risk_score,
            expected_window=expected_window,
            amount_at_risk=amount_at_risk,
            status="NEW",
            created_at=datetime.utcnow()
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        return alert
    return None
