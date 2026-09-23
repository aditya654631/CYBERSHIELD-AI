from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.models.db import get_db
from backend.app.models.models import User
from backend.app.schemas.schemas import GoldenHourResponse
from backend.app.auth.security import get_current_user
from backend.app.services.golden_hour_service import golden_hour_service

router = APIRouter(prefix="/predictions", tags=["Golden-Hour Operational Intelligence"])


@router.get("/{prediction_id}/golden-hour", response_model=GoldenHourResponse)
def get_golden_hour_operational_view(
    prediction_id: int,
    now_iso: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Phase 5: Converts the persisted time-window prediction into a clear, officer-facing operational Golden-Hour view.

    Guardrails:
    - ZERO ML re-inference or model retraining.
    - Derived strictly from persisted Prediction records.
    - Multi-tenant jurisdiction isolation enforced.
    - Explicit Asia/Kolkata (IST) timezone display.
    """
    ref_dt: Optional[datetime] = None
    if now_iso:
        clean_iso = now_iso.strip().replace(" ", "+")
        if clean_iso.endswith("Z"):
            clean_iso = clean_iso[:-1] + "+00:00"
        try:
            ref_dt = datetime.fromisoformat(clean_iso)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid now_iso timestamp format. Use valid ISO 8601 string."
            )

    return golden_hour_service.get_golden_hour_for_prediction(
        db=db,
        prediction_id=prediction_id,
        user=current_user,
        now_dt=ref_dt
    )
