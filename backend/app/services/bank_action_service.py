"""
CyberShield AI — Bank Action Lifecycle Service
Authoritative state-machine service managing bank-hold operations,
guaranteeing truthful statuses, simulation indicators, idempotency, and audit logging.

Lifecycle:
REQUESTED -> APPROVED -> SENT -> ACKNOWLEDGED -> COMPLETED
with FAILED and CANCELLED branches.

Prototype Rule:
All prototype actions are marked is_simulated=True.
Never display or claim 'Bank hold successful' or 'ATM hold triggered'
unless an actual external core banking gateway acknowledges it.
"""

import re
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status

from backend.app.models.models import BankAction, Alert, Complaint, User, AuditLog
from backend.app.services.audit_service import log_audit


VALID_TRANSITIONS = {
    "REQUESTED": ["APPROVED", "CANCELLED", "FAILED"],
    "APPROVED": ["SENT", "CANCELLED", "FAILED"],
    "SENT": ["ACKNOWLEDGED", "FAILED"],
    "ACKNOWLEDGED": ["COMPLETED", "FAILED"],
    "COMPLETED": [],
    "FAILED": ["REQUESTED"],  # May retry
    "CANCELLED": []
}


def _generate_action_ref(db: Session) -> str:
    """Generates unique sequential reference: ACT-HLD-YYYYMMDD-XXXX."""
    date_str = datetime.utcnow().strftime("%Y%m%d")
    prefix = f"ACT-HLD-{date_str}-"

    latest = (
        db.query(BankAction.action_reference)
        .filter(BankAction.action_reference.like(f"{prefix}%"))
        .order_by(BankAction.id.desc())
        .first()
    )

    next_seq = 1
    if latest and latest[0]:
        match = re.search(r"-(\d+)$", latest[0])
        if match:
            next_seq = int(match.group(1)) + 1

    ref = f"{prefix}{next_seq:04d}"
    while db.query(BankAction.id).filter(BankAction.action_reference == ref).first():
        next_seq += 1
        ref = f"{prefix}{next_seq:04d}"

    return ref


class BankActionService:
    @staticmethod
    def create_or_get_hold_action(
        db: Session,
        alert_id: int,
        user: User,
        action_notes: Optional[str] = None,
        idempotency_key: Optional[str] = None
    ) -> BankAction:
        """
        Idempotently creates or retrieves an escalation bank hold action.
        Transitions simulated actions up to SENT (Mock Dispatch).
        """
        # 1. Check idempotency by key
        if idempotency_key:
            existing = db.query(BankAction).filter(BankAction.idempotency_key == idempotency_key).first()
            if existing:
                return existing

        # 2. Check existing active action for this alert
        existing_alert_action = (
            db.query(BankAction)
            .filter(
                BankAction.alert_id == alert_id,
                BankAction.status.in_(["REQUESTED", "APPROVED", "SENT", "ACKNOWLEDGED"])
            )
            .first()
        )
        if existing_alert_action:
            return existing_alert_action

        # 3. Retrieve alert and complaint
        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

        complaint = db.query(Complaint).filter(Complaint.id == alert.complaint_id).first()
        if not complaint:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")

        ref = _generate_action_ref(db)
        now = datetime.utcnow()

        # Build new simulated action
        action = BankAction(
            action_reference=ref,
            idempotency_key=idempotency_key or f"IDEMP-{ref}",
            complaint_id=complaint.id,
            alert_id=alert.id,
            bank_name="Multi-Bank Intermediary Ring",
            action_type="ATM_DISBURSEMENT_HOLD",
            status="REQUESTED",
            is_simulated=True,
            simulation_notes="Simulated local action: External core-banking gateway not connected.",
            requested_by_user_id=user.id,
            actor_name=user.full_name,
            actor_role=user.role,
            action_notes=action_notes or "[SIMULATED] Automated ATM disbursement hold requested via CyberShield Gateway.",
            provider_reference_id=f"MOCK-GW-{ref}",
            requested_at=now,
            created_at=now
        )
        db.add(action)
        db.flush()

        # Audit initial request
        log_audit(
            db=db,
            user_id=user.id,
            officer_name=user.full_name,
            role=user.role,
            action="BANK_ACTION_REQUESTED",
            case_number=complaint.complaint_number,
            details=f"Bank hold {ref} REQUESTED for {alert.location_name} (SIMULATED). Notes: {action.action_notes}"
        )

        # In prototype: simulate automated progression REQUESTED -> APPROVED -> SENT
        action.status = "APPROVED"
        action.approved_at = now
        log_audit(
            db=db,
            user_id=user.id,
            officer_name=user.full_name,
            role=user.role,
            action="BANK_ACTION_APPROVED",
            case_number=complaint.complaint_number,
            details=f"Bank hold {ref} APPROVED (SIMULATED)."
        )

        action.status = "SENT"
        action.sent_at = now
        log_audit(
            db=db,
            user_id=user.id,
            officer_name=user.full_name,
            role=user.role,
            action="BANK_ACTION_SENT",
            case_number=complaint.complaint_number,
            details=f"Bank hold {ref} SENT to Mock Core-Banking Gateway (SIMULATED)."
        )

        # Update alert status truthfully
        alert.status = "ACTION_INITIATED"
        alert.action_notes = f"[SIMULATED] Bank hold request {ref} sent to gateway. Awaiting core banking integration."
        complaint.case_status = "ALERTED"

        db.commit()
        db.refresh(action)
        return action

    @staticmethod
    def transition_action(
        db: Session,
        action_id: int,
        target_status: str,
        user: User,
        notes: Optional[str] = None,
        failure_reason: Optional[str] = None
    ) -> BankAction:
        """
        Transitions an existing BankAction through its lifecycle.
        Validates allowed transition paths and prevents simulated actions from falsely claiming real external completion.
        """
        action = db.query(BankAction).filter(BankAction.id == action_id).first()
        if not action:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank action not found")

        current = action.status
        target = target_status.upper()

        if target not in VALID_TRANSITIONS.get(current, []):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid transition from '{current}' to '{target}'. Allowed: {VALID_TRANSITIONS.get(current, [])}"
            )

        # Truthfulness check: Cannot mark COMPLETED if simulated and no live integration
        if target == "COMPLETED" and action.is_simulated:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Simulated actions cannot be reported as COMPLETED externally without live core-banking integration."
            )

        now = datetime.utcnow()
        action.status = target
        if notes:
            action.action_notes = notes

        if target == "APPROVED":
            action.approved_at = now
        elif target == "SENT":
            action.sent_at = now
        elif target == "ACKNOWLEDGED":
            action.acknowledged_at = now
        elif target == "COMPLETED":
            action.completed_at = now
        elif target == "FAILED":
            action.failure_reason = failure_reason or "Gateway rejected hold request."

        complaint = db.query(Complaint).filter(Complaint.id == action.complaint_id).first()
        case_num = complaint.complaint_number if complaint else f"CMP-{action.complaint_id}"

        # Record every transition in the audit log
        log_audit(
            db=db,
            user_id=user.id,
            officer_name=user.full_name,
            role=user.role,
            action=f"BANK_ACTION_{target}",
            case_number=case_num,
            details=f"Bank action {action.action_reference} transitioned from {current} to {target}. Notes: {notes or 'None'}"
        )

        db.commit()
        db.refresh(action)
        return action


bank_action_service = BankActionService()
