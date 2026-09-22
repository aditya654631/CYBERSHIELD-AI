import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.models.db import get_db
from backend.app.models.models import User
from backend.app.schemas.schemas import (
    InterventionPlanResponse,
    InterventionPlanActionResponse,
    InterventionActionTransitionRequest,
)
from backend.app.auth.security import get_current_user
from backend.app.auth.rbac import require_roles, RoleEnum
from backend.app.services.intervention_service import intervention_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Intervention Orchestrator"])


@router.post(
    "/complaints/{complaint_id}/intervention-plan",
    response_model=InterventionPlanResponse,
    summary="Generate or return active Decision-Support Intervention Plan"
)
def generate_intervention_plan(
    complaint_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        RoleEnum.I4C_ADMIN, RoleEnum.STATE_LEA, RoleEnum.DISTRICT_LEA, RoleEnum.ANALYST, RoleEnum.AUDITOR
    ))
):
    """
    Generates a structured, reviewable decision-support action plan for a complaint strictly derived
    from existing persisted V8 predictions and case intelligence. Zero ML model reruns.
    """
    if current_user.role == RoleEnum.AUDITOR.value:
        # Auditor is read-only; return existing plan if available, or generate read-only view
        return intervention_service.generate_plan_for_complaint(db, complaint_id, current_user, force_refresh=False)

    return intervention_service.generate_plan_for_complaint(db, complaint_id, current_user, force_refresh=False)


@router.get(
    "/complaints/{complaint_id}/intervention-plan",
    response_model=InterventionPlanResponse,
    summary="Get active Decision-Support Intervention Plan for complaint"
)
def get_intervention_plan_for_complaint(
    complaint_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves the current active intervention plan for a complaint.
    """
    return intervention_service.generate_plan_for_complaint(db, complaint_id, current_user, force_refresh=False)


@router.get(
    "/intervention-plans/{plan_id}",
    response_model=InterventionPlanResponse,
    summary="Get Intervention Plan by ID"
)
def get_intervention_plan_by_id(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves a specific intervention plan by ID.
    """
    return intervention_service.get_plan(db, plan_id, current_user)


@router.patch(
    "/intervention-plans/{plan_id}/actions/{action_id}",
    response_model=InterventionPlanActionResponse,
    summary="Update Intervention Plan Action status"
)
def transition_intervention_action_status(
    plan_id: int,
    action_id: int,
    req: InterventionActionTransitionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Transitions the lifecycle status of an intervention action card (e.g. RECOMMENDED -> STARTED -> COMPLETED).
    """
    return intervention_service.transition_action_status(
        db=db,
        plan_id=plan_id,
        action_id=action_id,
        new_status=req.status,
        user=current_user,
        notes=req.notes
    )


@router.post(
    "/intervention-plans/{plan_id}/refresh",
    response_model=InterventionPlanResponse,
    summary="Force refresh Intervention Plan to incorporate latest case updates"
)
def refresh_intervention_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        RoleEnum.I4C_ADMIN, RoleEnum.STATE_LEA, RoleEnum.DISTRICT_LEA, RoleEnum.ANALYST
    ))
):
    """
    Creates a new plan revision (e.g. v2) that supersedes the previous plan to reflect
    acknowledged alerts, accepted handoffs, or updated bank actions.
    """
    plan = intervention_service.get_plan(db, plan_id, current_user)
    return intervention_service.generate_plan_for_complaint(
        db=db,
        complaint_id_or_num=str(plan.complaint_id),
        user=current_user,
        force_refresh=True
    )
