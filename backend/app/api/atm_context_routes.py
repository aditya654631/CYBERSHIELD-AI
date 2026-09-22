import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.models.db import get_db
from backend.app.models.models import User
from backend.app.auth.security import get_current_user
from backend.app.schemas.schemas import ATMContextResponse
from backend.app.services.atm_context_service import atm_context_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/predictions", tags=["ATM/CSP Context"])


@router.get("/{prediction_id}/atm-context", response_model=ATMContextResponse)
def get_atm_context(
    prediction_id: int,
    rank: int = Query(1, ge=1, le=3, description="V8 Candidate zone rank (1, 2, or 3)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves the contextual ATM/CSP operational shortlist for a specific V8 candidate zone rank.
    Applies deterministic scoring (Centroid Proximity, Bank Match, Density, Network Proximity).
    Enforces RBAC jurisdiction scoping. Zero V8 model re-inference.
    """
    return atm_context_service.get_atm_context_for_prediction(
        db=db,
        prediction_id=prediction_id,
        rank=rank,
        user=current_user
    )
