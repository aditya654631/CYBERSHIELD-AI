import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from backend.app.models.models import Prediction, Complaint, User
from backend.app.auth.rbac import verify_complaint_access

logger = logging.getLogger(__name__)

IST_TIMEZONE = timezone(timedelta(hours=5, minutes=30))


def to_utc_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Converts a naive or timezone-aware datetime to a UTC timezone-aware datetime."""
    if not dt:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def format_ist_full(dt_utc: Optional[datetime]) -> Optional[str]:
    """Formats a UTC datetime into explicit IST string representation (e.g. '22 Sep 2026, 17:28 IST')."""
    if not dt_utc:
        return None
    dt_ist = dt_utc.astimezone(IST_TIMEZONE)
    return dt_ist.strftime("%d %b %Y, %H:%M IST")


def format_ist_time_only(dt_utc: Optional[datetime]) -> Optional[str]:
    """Formats a UTC datetime into explicit IST time-only string representation (e.g. '17:28 IST')."""
    if not dt_utc:
        return None
    dt_ist = dt_utc.astimezone(IST_TIMEZONE)
    return dt_ist.strftime("%H:%M IST")


def format_utc_iso(dt_utc: Optional[datetime]) -> Optional[str]:
    if not dt_utc:
        return None
    return dt_utc.isoformat()


class GoldenHourService:
    """
    Phase 5: Golden-Hour Operational Intelligence Service.
    Converts persisted V8 time-window predictions into clear, officer-facing operational views.

    Guardrails:
    - ZERO V8 or time-model re-inference or retraining.
    - Consume strictly persisted Prediction columns (predicted_window_start, predicted_window_end).
    - Absolute Timezone-Aware Asia/Kolkata (IST) formatting.
    - Deterministic UI operational states derived strictly from time remaining.
    - Absolute non-fabrication of hazard curves or minute-by-minute distributions.
    """

    def calculate_operational_status(
        self,
        now_dt: datetime,
        start_utc: datetime,
        end_utc: datetime
    ) -> Dict[str, Any]:
        """
        Determines the operational status and countdown metrics from current time and window bounds.
        """
        mins_until_start = int(round((start_utc - now_dt).total_seconds() / 60.0))
        mins_until_end = int(round((end_utc - now_dt).total_seconds() / 60.0))

        if now_dt > end_utc:
            status_code = "WINDOW_PASSED"
            status_display = "WINDOW PASSED"
        elif start_utc <= now_dt <= end_utc:
            status_code = "WINDOW_ACTIVE"
            status_display = "WINDOW ACTIVE"
        else:
            # now_dt < start_utc
            if mins_until_start <= 30:
                status_code = "HIGH_URGENCY"
                status_display = "HIGH URGENCY"
            elif mins_until_start <= 60:
                status_code = "ELEVATED"
                status_display = "ELEVATED"
            else:
                status_code = "PLANNING"
                status_display = "PLANNING"

        return {
            "status": status_code,
            "status_display": status_display,
            "minutes_until_start": mins_until_start,
            "minutes_until_end": mins_until_end,
        }

    def get_golden_hour_for_prediction(
        self,
        db: Session,
        prediction_id: int,
        user: User,
        now_dt: Optional[datetime] = None
    ) -> Dict[str, Any]:
        # 1. Fetch persisted Prediction & Complaint
        prediction = db.query(Prediction).filter(Prediction.id == prediction_id).first()
        if not prediction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prediction #{prediction_id} not found."
            )

        complaint = db.query(Complaint).filter(Complaint.id == prediction.complaint_id).first()
        if not complaint or not verify_complaint_access(complaint, user, db):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prediction not found or access denied by jurisdiction scope."
            )

        # Reference current time
        if now_dt is None:
            now_dt = datetime.now(timezone.utc)
        else:
            now_dt = to_utc_aware(now_dt)

        pred_created_utc = to_utc_aware(prediction.created_at)
        comp_reported_utc = to_utc_aware(complaint.reported_at or complaint.incident_time or complaint.created_at)

        # Check if persisted time prediction exists
        start_raw = getattr(prediction, "predicted_window_start", None)
        end_raw = getattr(prediction, "predicted_window_end", None)

        if not start_raw or not end_raw:
            return {
                "prediction_id": prediction.id,
                "complaint_id": complaint.id,
                "complaint_number": complaint.complaint_number,
                "generated_at": format_utc_iso(pred_created_utc),
                "timezone": "Asia/Kolkata",
                "reference_time": format_utc_iso(comp_reported_utc),
                "window": {
                    "start": None,
                    "end": None,
                    "start_ist": None,
                    "end_ist": None,
                    "start_time_ist": None,
                    "end_time_ist": None,
                    "start_offset_minutes": None,
                    "end_offset_minutes": None,
                },
                "status": "GOLDEN_HOUR_UNAVAILABLE",
                "status_display": "GOLDEN HOUR UNAVAILABLE",
                "minutes_until_start": None,
                "minutes_until_end": None,
                "timeline": [],
                "disclaimer": "Operational time window unavailable for this prediction.",
                "source": {
                    "model_version": getattr(prediction, "time_model_version", None) or "cashout-time-xgb-v3",
                    "derived_from_persisted_prediction": True
                }
            }

        start_utc = to_utc_aware(start_raw)
        end_utc = to_utc_aware(end_raw)

        # Calculate offsets from complaint reference time
        start_offset = int(round((start_utc - comp_reported_utc).total_seconds() / 60.0)) if comp_reported_utc else None
        end_offset = int(round((end_utc - comp_reported_utc).total_seconds() / 60.0)) if comp_reported_utc else None

        # Calculate operational state
        op_state = self.calculate_operational_status(now_dt, start_utc, end_utc)

        # Build Response Timeline
        timeline = []
        if comp_reported_utc:
            timeline.append({
                "step": "Complaint Received",
                "timestamp": format_utc_iso(comp_reported_utc),
                "timestamp_ist": format_ist_full(comp_reported_utc)
            })

        comp_created_utc = to_utc_aware(complaint.created_at)
        if comp_created_utc and comp_created_utc != comp_reported_utc:
            timeline.append({
                "step": "Money Trail Built",
                "timestamp": format_utc_iso(comp_created_utc),
                "timestamp_ist": format_ist_full(comp_created_utc)
            })

        if pred_created_utc:
            timeline.append({
                "step": "Prediction Generated",
                "timestamp": format_utc_iso(pred_created_utc),
                "timestamp_ist": format_ist_full(pred_created_utc)
            })

        timeline.append({
            "step": "Expected Cash-Out Window Start",
            "timestamp": format_utc_iso(start_utc),
            "timestamp_ist": format_ist_full(start_utc)
        })

        timeline.append({
            "step": "Expected Cash-Out Window End",
            "timestamp": format_utc_iso(end_utc),
            "timestamp_ist": format_ist_full(end_utc)
        })

        return {
            "prediction_id": prediction.id,
            "complaint_id": complaint.id,
            "complaint_number": complaint.complaint_number,
            "generated_at": format_utc_iso(pred_created_utc),
            "timezone": "Asia/Kolkata",
            "reference_time": format_utc_iso(comp_reported_utc),
            "window": {
                "start": format_utc_iso(start_utc),
                "end": format_utc_iso(end_utc),
                "start_ist": format_ist_full(start_utc),
                "end_ist": format_ist_full(end_utc),
                "start_time_ist": format_ist_time_only(start_utc),
                "end_time_ist": format_ist_time_only(end_utc),
                "start_offset_minutes": start_offset,
                "end_offset_minutes": end_offset,
            },
            "status": op_state["status"],
            "status_display": op_state["status_display"],
            "minutes_until_start": op_state["minutes_until_start"],
            "minutes_until_end": op_state["minutes_until_end"],
            "timeline": timeline,
            "disclaimer": (
                "Golden-Hour shows the operational time window derived from the persisted cash-out time prediction. "
                "Countdown and urgency labels support response planning and are not independent probability estimates."
            ),
            "source": {
                "model_version": getattr(prediction, "time_model_version", None) or "cashout-time-xgb-v3",
                "derived_from_persisted_prediction": True
            }
        }


golden_hour_service = GoldenHourService()
