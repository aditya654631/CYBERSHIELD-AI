"""Shared UTC time-window contract for inference, persistence and API reads."""

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Optional


def as_utc(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    # Database DateTime columns store UTC without a timezone.
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def utc_iso(value: Any) -> Optional[str]:
    resolved = as_utc(value)
    if not resolved:
        return None
    iso = resolved.isoformat()
    if iso.endswith("+00:00"):
        return iso[:-6] + "Z"
    return iso


def window_status(start: Any, end: Any, now: Any = None) -> Optional[str]:
    if start is None or end is None:
        return None
    current = as_utc(now) or datetime.now(timezone.utc)
    if current >= as_utc(end):
        return "elapsed"
    return "upcoming" if current < as_utc(start) else "active"


def build_time_prediction(
    complaint: Any,
    minutes: float,
    model_version: str,
    uncertainty_minutes: float = 15.0,
    window_basis: str = "operational_estimate",
    now: Any = None,
) -> dict:
    """The trained target is cashout time minus reported_at, never 'from now'."""
    if not math.isfinite(minutes) or not 0 <= minutes <= 43200:
        raise ValueError("Time model returned an invalid cash-out duration")
    ref = as_utc(complaint.reported_at)
    if ref is None:
        raise ValueError("Complaint report time is required for time inference")
    margin = max(0.0, float(uncertainty_minutes))
    low = max(0.0, minutes - margin)
    high = minutes + margin
    start, end = ref + timedelta(minutes=low), ref + timedelta(minutes=high)
    label = f"{math.floor(low)}–{math.ceil(high)} min after complaint report"
    return {
        "predicted_minutes_to_cashout": minutes,
        "model_version": model_version,
        "prediction_reference_time": utc_iso(ref),
        "reference_basis": "complaint_reported_at",
        "predicted_cashout_at": utc_iso(ref + timedelta(minutes=minutes)),
        "window_start": utc_iso(start),
        "window_end": utc_iso(end),
        "window_status": window_status(start, end, now),
        "uncertainty_minutes": margin,
        "window_basis": window_basis,
        "operational_window": label,
    }
