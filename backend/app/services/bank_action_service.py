"""
CyberShield AI — Phase 8: Bank Action Lifecycle & Adapter Service
Authoritative state-machine service managing bank-hold operations,
guaranteeing truthful statuses, environment isolation (SIMULATED, SANDBOX, LIVE),
cryptographic callback authentication, and comprehensive audit logging.

Lifecycle:
REQUESTED -> APPROVED -> SENT -> ACKNOWLEDGED -> PARTIAL_HOLD / CONFIRMED_HOLD -> RELEASED
with FAILED, REJECTED, and CANCELLED branches.

Fundamental Rules:
1. Request Sent != Funds Held. Submitting an action transitions it to SENT, not CONFIRMED_HOLD.
2. Direct client transitions to CONFIRMED_HOLD or PARTIAL_HOLD are strictly rejected.
   Confirmed hold requires verified partner callback evidence or sandbox simulation with valid HMAC signatures.
3. Existing prototype simulated actions retain truthful disclosure: is_simulated=True.
"""

import re
import uuid
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status

from backend.app.models.models import BankAction, Alert, Complaint, User, AuditLog, Account, Organization
from backend.app.services.audit_service import log_audit
from backend.app.auth.rbac import (
    complaint_bank_organization_ids, RoleEnum, is_national_scope, verify_complaint_access
)
from backend.app.adapters.bank_adapter import (
    get_bank_adapter, generate_sandbox_hmac_signature, SANDBOX_SHARED_SECRET
)


VALID_ENVIRONMENTS = {"SIMULATED", "SANDBOX", "LIVE"}

VALID_ACTION_TYPES = {
    "ATM_DISBURSEMENT_HOLD",
    "ACCOUNT_FREEZE",
    "LIEN_HOLD",
    "TRANSACTION_BLOCK"
}

VALID_TRANSITIONS = {
    "REQUESTED": ["APPROVED", "CANCELLED", "FAILED", "REJECTED"],
    "APPROVED": ["SENT", "CANCELLED", "FAILED", "REJECTED"],
    "SENT": ["ACKNOWLEDGED", "PARTIAL_HOLD", "CONFIRMED_HOLD", "REJECTED", "FAILED", "CANCELLED"],
    "ACKNOWLEDGED": ["PARTIAL_HOLD", "CONFIRMED_HOLD", "REJECTED", "FAILED"],
    "PARTIAL_HOLD": ["CONFIRMED_HOLD", "RELEASED", "FAILED"],
    "CONFIRMED_HOLD": ["RELEASED"],
    "RELEASED": [],
    "REJECTED": ["REQUESTED"],  # May re-request with corrected details
    "FAILED": ["REQUESTED"],    # May retry
    "CANCELLED": []
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _generate_action_ref(db: Session) -> str:
    """Generates unique sequential reference: ACT-HLD-YYYYMMDD-XXXX."""
    date_str = _utcnow().strftime("%Y%m%d")
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
    def create_direct_action(
        db: Session,
        complaint_id: int,
        user: User,
        action_type: str = "ATM_DISBURSEMENT_HOLD",
        alert_id: Optional[int] = None,
        account_id: Optional[int] = None,
        target_account_number: Optional[str] = None,
        target_ifsc: Optional[str] = None,
        bank_name: Optional[str] = None,
        bank_organization_id: Optional[int] = None,
        requested_amount: Optional[float] = None,
        currency: str = "INR",
        environment: str = "SIMULATED",
        action_notes: Optional[str] = None,
        idempotency_key: Optional[str] = None
    ) -> BankAction:
        """
        Creates an explicit Bank Action request with strict role & jurisdiction verification.
        """
        env = environment.strip().upper() if environment else "SIMULATED"
        if env not in VALID_ENVIRONMENTS:
            env = "SIMULATED"

        # 1. Idempotency Check
        if idempotency_key:
            existing = db.query(BankAction).filter(BankAction.idempotency_key == idempotency_key).first()
            if existing:
                return existing

        # 2. Complaint & Jurisdiction Verification
        complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
        if not complaint:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")

        verify_complaint_access(complaint, user, db)

        # 3. Role Authorization: Only LEA officers and assigned Bank Officers can request actions
        allowed_roles = [RoleEnum.I4C_ADMIN, RoleEnum.STATE_LEA, RoleEnum.DISTRICT_LEA, RoleEnum.BANK_OFFICER]
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' is not authorized to create bank actions."
            )

        # 4. Bank Organization Resolution & Scoping
        stakeholder_bank_ids = complaint_bank_organization_ids(complaint.id, db)
        resolved_bank_org_id = bank_organization_id

        if user.role == RoleEnum.BANK_OFFICER:
            if not user.organization_id or user.organization_id not in stakeholder_bank_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bank Officer can only initiate actions on cases involving their registered financial institution."
                )
            resolved_bank_org_id = user.organization_id
        elif not resolved_bank_org_id and len(stakeholder_bank_ids) == 1:
            resolved_bank_org_id = next(iter(stakeholder_bank_ids))

        resolved_bank_name = bank_name
        if resolved_bank_org_id:
            bank_org = db.query(Organization).filter(Organization.id == resolved_bank_org_id).first()
            if bank_org:
                resolved_bank_name = bank_org.name

        # 5. Target Account & Amount Resolution
        resolved_acc_num = target_account_number
        resolved_ifsc = target_ifsc
        if account_id and not resolved_acc_num:
            acc = db.query(Account).filter(Account.id == account_id).first()
            if acc:
                resolved_acc_num = acc.account_number
                resolved_ifsc = acc.ifsc
                if not resolved_bank_name:
                    resolved_bank_name = acc.bank_name

        req_amount = requested_amount if requested_amount is not None else float(complaint.amount or 0.0)

        ref = _generate_action_ref(db)
        now = _utcnow()
        is_sim = (env != "LIVE")

        action = BankAction(
            action_reference=ref,
            idempotency_key=idempotency_key or f"IDEMP-{ref}",
            complaint_id=complaint.id,
            alert_id=alert_id,
            account_id=account_id,
            bank_name=resolved_bank_name or "Partner Bank Gateway",
            bank_organization_id=resolved_bank_org_id,
            target_account_number=resolved_acc_num,
            target_ifsc=resolved_ifsc,
            action_type=action_type if action_type in VALID_ACTION_TYPES else "ATM_DISBURSEMENT_HOLD",
            status="REQUESTED",
            environment=env,
            is_simulated=is_sim,
            simulation_notes=(
                "Simulated local action: External core-banking gateway not connected."
                if env == "SIMULATED"
                else f"Sandbox test action: Connected to Sandbox Gateway ({env})."
            ),
            requested_amount=req_amount,
            held_amount=0.0,
            currency=currency or "INR",
            requested_by_user_id=user.id,
            actor_name=user.full_name,
            actor_role=user.role,
            action_notes=action_notes or f"[{env}] Financial hold requested via CyberShield Gateway.",
            provider_reference_id=None,
            status_history=[{
                "status": "REQUESTED",
                "environment": env,
                "user_id": user.id,
                "timestamp": now.isoformat() + "Z",
                "notes": "Action created and awaiting review/dispatch."
            }],
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
            details=f"Bank action {ref} REQUESTED ({env}). Target: {resolved_acc_num or 'N/A'}, Amount: {currency} {req_amount:.2f}."
        )

        # In SIMULATED mode only: optionally simulate automatic progression REQUESTED -> APPROVED -> SENT
        if env == "SIMULATED":
            action.status = "APPROVED"
            action.approved_at = now
            action.status = "SENT"
            action.sent_at = now
            action.provider_reference_id = f"SIM-GW-{ref}"
            history = list(action.status_history or [])
            history.extend([
                {"status": "APPROVED", "environment": "SIMULATED", "timestamp": now.isoformat() + "Z", "notes": "Simulated automatic approval."},
                {"status": "SENT", "environment": "SIMULATED", "timestamp": now.isoformat() + "Z", "notes": "Simulated mock dispatch."}
            ])
            action.status_history = history

            if alert_id:
                alert = db.query(Alert).filter(Alert.id == alert_id).first()
                if alert:
                    alert.status = "ACTION_INITIATED"
                    alert.action_notes = f"[SIMULATED] Bank hold request {ref} sent to mock gateway."

        db.commit()
        db.refresh(action)
        return action

    @staticmethod
    def create_or_get_hold_action(
        db: Session,
        alert_id: int,
        user: User,
        action_notes: Optional[str] = None,
        idempotency_key: Optional[str] = None
    ) -> BankAction:
        """
        Backwards-compatible method for creating a hold action from an Alert.
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
                BankAction.status.in_(["REQUESTED", "APPROVED", "SENT", "ACKNOWLEDGED", "PARTIAL_HOLD", "CONFIRMED_HOLD"])
            )
            .first()
        )
        if existing_alert_action:
            return existing_alert_action

        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

        complaint = db.query(Complaint).filter(Complaint.id == alert.complaint_id).first()
        if not complaint:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")

        return BankActionService.create_direct_action(
            db=db,
            complaint_id=complaint.id,
            user=user,
            action_type="ATM_DISBURSEMENT_HOLD",
            alert_id=alert.id,
            requested_amount=float(alert.amount_at_risk or complaint.amount or 0.0),
            environment="SIMULATED",
            action_notes=action_notes,
            idempotency_key=idempotency_key
        )

    @staticmethod
    def approve_action(db: Session, action_id: int, user: User, notes: Optional[str] = None) -> BankAction:
        """
        Authorizes a requested bank action.
        Restricted to supervisors and authorized reviewers (I4C_ADMIN, STATE_LEA).
        """
        action = db.query(BankAction).filter(BankAction.id == action_id).first()
        if not action:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank action not found")

        allowed_reviewers = [RoleEnum.I4C_ADMIN, RoleEnum.STATE_LEA, RoleEnum.DISTRICT_LEA]
        if user.role not in allowed_reviewers:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to approve bank actions.")

        if action.status != "REQUESTED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot approve action in status '{action.status}'. Must be in 'REQUESTED' state."
            )

        now = _utcnow()
        action.status = "APPROVED"
        action.approved_at = now
        action.reviewed_by_user_id = user.id

        history = list(action.status_history or [])
        history.append({
            "status": "APPROVED",
            "environment": action.environment,
            "reviewed_by_user_id": user.id,
            "timestamp": now.isoformat() + "Z",
            "notes": notes or "Action reviewed and approved for dispatch."
        })
        action.status_history = history

        log_audit(
            db=db,
            user_id=user.id,
            officer_name=user.full_name,
            role=user.role,
            action="BANK_ACTION_APPROVED",
            case_number=f"CMP-{action.complaint_id}",
            details=f"Bank action {action.action_reference} APPROVED by {user.full_name}. Notes: {notes or 'None'}."
        )

        db.commit()
        db.refresh(action)
        return action

    @staticmethod
    def dispatch_action(db: Session, action_id: int, user: User) -> BankAction:
        """
        Dispatches an approved action to the appropriate Bank Adapter.
        Transitions status from APPROVED -> SENT (never CONFIRMED_HOLD).
        """
        action = db.query(BankAction).filter(BankAction.id == action_id).first()
        if not action:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank action not found")

        if action.status not in ("APPROVED", "REQUESTED"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot dispatch action in status '{action.status}'. Must be 'APPROVED' or 'REQUESTED'."
            )

        adapter = get_bank_adapter(action.environment)
        adapter.submit_action_request(action, db)
        return action

    @staticmethod
    def process_partner_callback(
        db: Session,
        payload: Dict[str, Any],
        signature: str,
        timestamp_str: str,
        callback_id: str
    ) -> Dict[str, Any]:
        """
        Validates and applies partner webhook callbacks.
        """
        action_ref = payload.get("action_reference")
        action = db.query(BankAction).filter(BankAction.action_reference == action_ref).first()
        env = action.environment if action else "SANDBOX"

        adapter = get_bank_adapter(env)
        return adapter.process_partner_callback(
            payload=payload,
            signature=signature,
            timestamp_str=timestamp_str,
            callback_id=callback_id,
            db=db
        )

    @staticmethod
    def release_action(
        db: Session,
        action_id: int,
        user: User,
        release_reason: str,
        release_amount: Optional[float] = None
    ) -> BankAction:
        """
        Releases an active hold (CONFIRMED_HOLD or PARTIAL_HOLD).
        """
        action = db.query(BankAction).filter(BankAction.id == action_id).first()
        if not action:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank action not found")

        if action.status not in ("CONFIRMED_HOLD", "PARTIAL_HOLD", "SENT", "ACKNOWLEDGED"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot release action in status '{action.status}'. Active hold not established."
            )

        now = _utcnow()
        action.status = "RELEASED"
        action.released_at = now
        action.release_reason = release_reason

        history = list(action.status_history or [])
        history.append({
            "status": "RELEASED",
            "environment": action.environment,
            "released_by_user_id": user.id,
            "release_reason": release_reason,
            "timestamp": now.isoformat() + "Z",
            "notes": f"Hold released: {release_reason}"
        })
        action.status_history = history

        log_audit(
            db=db,
            user_id=user.id,
            officer_name=user.full_name,
            role=user.role,
            action="BANK_ACTION_RELEASED",
            case_number=f"CMP-{action.complaint_id}",
            details=f"Bank action {action.action_reference} RELEASED. Reason: {release_reason}."
        )

        db.commit()
        db.refresh(action)
        return action

    @staticmethod
    def cancel_action(
        db: Session,
        action_id: int,
        user: User,
        cancellation_reason: str
    ) -> BankAction:
        """
        Cancels a pending bank action request.
        """
        action = db.query(BankAction).filter(BankAction.id == action_id).first()
        if not action:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank action not found")

        if action.status in ("CONFIRMED_HOLD", "RELEASED"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel action in '{action.status}' state. Use release workflow instead."
            )

        now = _utcnow()
        action.status = "CANCELLED"
        action.cancelled_at = now
        action.failure_reason = cancellation_reason

        history = list(action.status_history or [])
        history.append({
            "status": "CANCELLED",
            "environment": action.environment,
            "cancelled_by_user_id": user.id,
            "cancellation_reason": cancellation_reason,
            "timestamp": now.isoformat() + "Z",
            "notes": f"Action cancelled: {cancellation_reason}"
        })
        action.status_history = history

        log_audit(
            db=db,
            user_id=user.id,
            officer_name=user.full_name,
            role=user.role,
            action="BANK_ACTION_CANCELLED",
            case_number=f"CMP-{action.complaint_id}",
            details=f"Bank action {action.action_reference} CANCELLED. Reason: {cancellation_reason}."
        )

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
        Strictly prevents client-forged transitions to CONFIRMED_HOLD or PARTIAL_HOLD.
        """
        action = db.query(BankAction).filter(BankAction.id == action_id).first()
        if not action:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank action not found")

        current = action.status
        target = target_status.upper()

        if target in ("CONFIRMED_HOLD", "PARTIAL_HOLD"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Direct client transition to CONFIRMED_HOLD or PARTIAL_HOLD is strictly prohibited. External holds require verified partner callback evidence."
            )

        # Truthfulness check: Cannot mark COMPLETED if simulated and no live integration
        if target == "COMPLETED" and action.is_simulated:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Simulated actions cannot be reported as COMPLETED externally without live core-banking integration."
            )

        if target not in VALID_TRANSITIONS.get(current, []):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid transition from '{current}' to '{target}'. Allowed: {VALID_TRANSITIONS.get(current, [])}"
            )

        now = _utcnow()
        action.status = target
        if notes:
            action.action_notes = notes

        if target == "APPROVED":
            action.approved_at = now
            action.reviewed_by_user_id = user.id
        elif target == "SENT":
            action.sent_at = now
        elif target == "ACKNOWLEDGED":
            action.acknowledged_at = now
        elif target == "COMPLETED":
            action.completed_at = now
        elif target == "FAILED":
            action.failure_reason = failure_reason or "Gateway rejected hold request."

        history = list(action.status_history or [])
        history.append({
            "status": target,
            "environment": action.environment,
            "user_id": user.id,
            "timestamp": now.isoformat() + "Z",
            "notes": notes or f"Transitioned from {current} to {target}."
        })
        action.status_history = history

        log_audit(
            db=db,
            user_id=user.id,
            officer_name=user.full_name,
            role=user.role,
            action=f"BANK_ACTION_{target}",
            case_number=f"CMP-{action.complaint_id}",
            details=f"Bank action {action.action_reference} transitioned from {current} to {target}. Notes: {notes or 'None'}"
        )

        db.commit()
        db.refresh(action)
        return action

    @staticmethod
    def sandbox_simulate_outcome(
        db: Session,
        action_id: int,
        simulated_outcome: str,
        held_amount: Optional[float] = None,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes a deterministic simulated partner callback for sandbox testing.
        Generates genuine cryptographic signature and processes through formal adapter pipeline.
        """
        action = db.query(BankAction).filter(BankAction.id == action_id).first()
        if not action:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank action not found")

        if action.status not in ("SENT", "ACKNOWLEDGED", "APPROVED", "REQUESTED"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot simulate sandbox outcome for action in status '{action.status}'."
            )

        outcome = simulated_outcome.upper()
        req_amount = float(action.requested_amount or 0.0)
        h_amount = held_amount if held_amount is not None else req_amount

        cb_status_map = {
            "CONFIRMED_HOLD": "HELD",
            "PARTIAL_HOLD": "PARTIAL_HELD",
            "REJECTED": "REJECTED",
            "FAILED": "FAILED",
            "TIMEOUT": "FAILED"
        }
        cb_status = cb_status_map.get(outcome, "HELD")
        if outcome == "PARTIAL_HOLD" and h_amount >= req_amount and req_amount > 0:
            h_amount = req_amount * 0.5

        payload = {
            "action_reference": action.action_reference,
            "provider_reference_id": action.provider_reference_id or f"SBX-{action.action_reference}",
            "target_account_number": action.target_account_number,
            "status": cb_status,
            "held_amount": h_amount,
            "currency": action.currency,
            "failure_reason": reason if outcome in ("REJECTED", "FAILED", "TIMEOUT") else None,
            "timestamp": _utcnow().isoformat() + "Z"
        }

        callback_id = f"CB-{uuid.uuid4().hex[:12]}"
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        signature = generate_sandbox_hmac_signature(payload_bytes.decode("utf-8"), SANDBOX_SHARED_SECRET)

        return BankActionService.process_partner_callback(
            db=db,
            payload=payload,
            signature=signature,
            timestamp_str=payload["timestamp"],
            callback_id=callback_id
        )


bank_action_service = BankActionService()
