"""
CyberShield AI — Phase 8: Bank Adapter Interface & Implementations
Provides a formal, extensible adapter interface for core-banking and CFCFRMS financial interventions.
Supports SIMULATED, SANDBOX, and LIVE environments with cryptographic HMAC-SHA256 callback verification,
timestamp skew checks, replay protection, and strict target/amount validation.
"""

import hmac
import hashlib
import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.models.models import BankAction, Alert, Complaint, AuditLog, Account, Organization
from backend.app.services.audit_service import log_audit


# Sandbox HMAC secret is sourced from environment config.
# The fallback is a dev-only placeholder and MUST NOT be used in production.
import os as _os
SANDBOX_SHARED_SECRET: str = _os.environ.get(
    "SANDBOX_BANK_SECRET",
    "cybershield_sandbox_dev_only_2026"  # DEV-ONLY FALLBACK — override via SANDBOX_BANK_SECRET env var
)
MAX_TIMESTAMP_SKEW_SECONDS = 300  # 5 minutes


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def generate_sandbox_hmac_signature(payload_str: str, secret: str = SANDBOX_SHARED_SECRET) -> str:
    """Generates an HMAC-SHA256 hex signature for webhook payload authentication."""
    return hmac.new(secret.encode("utf-8"), payload_str.encode("utf-8"), hashlib.sha256).hexdigest()


class BankAdapter(ABC):
    """Abstract interface for partner bank integrations."""

    @abstractmethod
    def submit_action_request(self, action: BankAction, db: Session) -> Dict[str, Any]:
        """Submits a hold/freeze instruction to the external partner."""
        pass

    @abstractmethod
    def query_action_status(self, action: BankAction, db: Session) -> Dict[str, Any]:
        """Queries the external partner for current execution status."""
        pass

    @abstractmethod
    def process_partner_callback(
        self,
        payload: Dict[str, Any],
        signature: str,
        timestamp_str: str,
        callback_id: str,
        db: Session
    ) -> Dict[str, Any]:
        """Authenticates and processes an incoming asynchronous partner callback."""
        pass


class SandboxBankAdapter(BankAdapter):
    """
    Deterministic Sandbox Bank Adapter.
    Executes mock core-banking operations with full cryptographic verification,
    tamper detection, replay protection, and truthful state tracking.
    """

    def __init__(self, secret: str = SANDBOX_SHARED_SECRET):
        self.secret = secret

    def submit_action_request(self, action: BankAction, db: Session) -> Dict[str, Any]:
        now = _utcnow()
        provider_ref = f"SBX-GW-{action.action_reference}-{now.strftime('%H%M%S')}"
        action.provider_reference_id = provider_ref
        action.sent_at = now
        action.status = "SENT"
        
        # Append status history
        history = list(action.status_history or [])
        history.append({
            "status": "SENT",
            "environment": "SANDBOX",
            "provider_reference_id": provider_ref,
            "timestamp": now.isoformat() + "Z",
            "notes": "Action dispatched to Sandbox Core-Banking Gateway."
        })
        action.status_history = history

        log_audit(
            db=db,
            user_id=action.requested_by_user_id,
            officer_name=action.actor_name or "System",
            role=action.actor_role or "BANK_OFFICER",
            action="BANK_ACTION_DISPATCHED",
            case_number=f"CMP-{action.complaint_id}",
            details=f"Bank action {action.action_reference} dispatched to Sandbox Gateway (Ref: {provider_ref}). Environment: SANDBOX."
        )

        db.commit()
        db.refresh(action)

        return {
            "action_reference": action.action_reference,
            "provider_reference_id": provider_ref,
            "status": "SENT",
            "environment": "SANDBOX",
            "message": "Action request received and queued by Sandbox Gateway. Awaiting external callback."
        }

    def query_action_status(self, action: BankAction, db: Session) -> Dict[str, Any]:
        return {
            "action_reference": action.action_reference,
            "provider_reference_id": action.provider_reference_id,
            "status": action.status,
            "environment": action.environment,
            "requested_amount": float(action.requested_amount or 0.0),
            "held_amount": float(action.held_amount or 0.0),
            "currency": action.currency,
            "is_simulated": action.is_simulated,
        }

    def verify_signature(self, payload_bytes: bytes, signature: str) -> bool:
        if not signature:
            return False
        expected = generate_sandbox_hmac_signature(payload_bytes.decode("utf-8"), self.secret)
        return hmac.compare_digest(expected, signature.strip())

    def process_partner_callback(
        self,
        payload: Dict[str, Any],
        signature: str,
        timestamp_str: str,
        callback_id: str,
        db: Session
    ) -> Dict[str, Any]:
        # 1. Signature Verification
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        if not self.verify_signature(payload_bytes, signature):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or forged partner callback signature (HMAC-SHA256 mismatch)."
            )

        # 2. Timestamp Skew Verification
        now = _utcnow()
        try:
            cb_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            if cb_time.tzinfo is not None:
                cb_time_naive = cb_time.astimezone(timezone.utc).replace(tzinfo=None)
            else:
                cb_time_naive = cb_time
            skew = abs((now - cb_time_naive).total_seconds())
            if skew > MAX_TIMESTAMP_SKEW_SECONDS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Callback timestamp skew ({skew:.1f}s) exceeds maximum allowed threshold ({MAX_TIMESTAMP_SKEW_SECONDS}s)."
                )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid callback timestamp format: {e}"
            )

        # 3. Replay Protection
        for act in db.query(BankAction).filter(BankAction.callback_evidence != None).all():
            if act.callback_evidence and isinstance(act.callback_evidence, dict) and act.callback_evidence.get("callback_id") == callback_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Duplicate or replayed callback ID '{callback_id}' detected."
                )

        # 4. Action Lookup
        action_ref = payload.get("action_reference")
        if not action_ref:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing action_reference in callback payload.")

        action = db.query(BankAction).filter(BankAction.action_reference == action_ref).first()
        if not action:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bank action '{action_ref}' not found.")

        # 5. Validate Provider Reference
        cb_provider_ref = payload.get("provider_reference_id")
        if action.provider_reference_id and cb_provider_ref and action.provider_reference_id != cb_provider_ref:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Provider reference mismatch. Expected '{action.provider_reference_id}', got '{cb_provider_ref}'."
            )

        # 6. Target Account Validation
        cb_target_account = payload.get("target_account_number")
        if cb_target_account and action.target_account_number:
            if cb_target_account.strip().upper() != action.target_account_number.strip().upper():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Target account mismatch. Expected '{action.target_account_number}', received '{cb_target_account}'."
                )

        # 7. Status Machine Transition Evaluation
        cb_status = str(payload.get("status", "")).upper()
        held_amount = float(payload.get("held_amount", 0.0))
        requested_amount = float(action.requested_amount or 0.0)
        failure_reason = payload.get("failure_reason")

        if action.status in ("CONFIRMED_HOLD", "RELEASED", "CANCELLED") and cb_status not in ("RELEASED",):
            # Idempotent return if already confirmed with same details
            if action.status == "CONFIRMED_HOLD" and cb_status == "HELD" and float(action.held_amount) == held_amount:
                return {
                    "success": True,
                    "action_reference": action.action_reference,
                    "status": action.status,
                    "held_amount": float(action.held_amount),
                    "environment": action.environment,
                    "message": "Idempotent duplicate callback acknowledged."
                }
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot apply callback status '{cb_status}' to action in terminal/confirmed state '{action.status}'."
            )

        new_status = action.status
        if cb_status in ("HELD", "CONFIRMED_HOLD", "SUCCESS"):
            if requested_amount > 0 and held_amount < requested_amount:
                new_status = "PARTIAL_HOLD"
            else:
                new_status = "CONFIRMED_HOLD"
            action.held_at = now
            action.held_amount = held_amount
        elif cb_status in ("PARTIAL_HELD", "PARTIAL_HOLD"):
            new_status = "PARTIAL_HOLD"
            action.held_at = now
            action.held_amount = held_amount
        elif cb_status in ("REJECTED", "DECLINED"):
            new_status = "REJECTED"
            action.rejection_reason = failure_reason or "Partner bank rejected hold instruction."
        elif cb_status in ("FAILED", "ERROR", "TIMEOUT"):
            new_status = "FAILED"
            action.failure_reason = failure_reason or "Partner bank reported execution failure."
        elif cb_status in ("RELEASED", "UNLOCKED"):
            new_status = "RELEASED"
            action.released_at = now
            action.release_reason = payload.get("release_reason") or "Hold released per partner callback."
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported partner callback status '{cb_status}'."
            )

        # 8. Record Evidence and Status History
        sanitized_payload = {k: v for k, v in payload.items() if "secret" not in k.lower() and "password" not in k.lower()}
        action.status = new_status
        action.is_simulated = False if action.environment == "LIVE" else True
        action.callback_evidence = {
            "callback_id": callback_id,
            "received_at": now.isoformat() + "Z",
            "signature_verified": True,
            "partner_status": cb_status,
            "held_amount": held_amount,
            "currency": action.currency,
            "payload": sanitized_payload
        }

        history = list(action.status_history or [])
        history.append({
            "status": new_status,
            "environment": action.environment,
            "callback_id": callback_id,
            "held_amount": held_amount,
            "timestamp": now.isoformat() + "Z",
            "notes": f"Partner callback processed. Status updated to {new_status}."
        })
        action.status_history = history

        # Update associated alert if applicable
        if action.alert_id:
            alert = db.query(Alert).filter(Alert.id == action.alert_id).first()
            if alert:
                if new_status in ("CONFIRMED_HOLD", "PARTIAL_HOLD"):
                    alert.status = "ACTION_COMPLETED"
                    alert.action_notes = f"[{action.environment}] Bank hold confirmed ({action.currency} {held_amount:.2f}). Ref: {action.action_reference}"
                elif new_status == "REJECTED":
                    alert.status = "ACTION_FAILED"
                    alert.action_notes = f"[{action.environment}] Bank hold rejected: {action.rejection_reason}"

        log_audit(
            db=db,
            user_id=None,
            officer_name="Partner Bank Gateway",
            role="PARTNER_BANK",
            action=f"BANK_ACTION_CALLBACK_{new_status}",
            case_number=f"CMP-{action.complaint_id}",
            details=(
                f"Partner callback verified for action {action.action_reference}. "
                f"Status: {new_status}, Held: {action.currency} {held_amount:.2f}/{requested_amount:.2f}. "
                f"Callback ID: {callback_id}. Environment: {action.environment}."
            )
        )

        db.commit()
        db.refresh(action)

        return {
            "success": True,
            "action_reference": action.action_reference,
            "status": new_status,
            "held_amount": float(action.held_amount),
            "environment": action.environment,
            "message": f"Partner callback successfully processed. Action status is {new_status}."
        }


class LiveBankAdapter(BankAdapter):
    """
    Live Core-Banking Gateway Adapter.
    Requires official CFCFRMS / SFMS / partner core-banking API credentials.
    Pending external certification gate.
    """

    def submit_action_request(self, action: BankAction, db: Session) -> Dict[str, Any]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Live Core-Banking Gateway is not configured. "
                "Production bank API credentials, bilateral SLA, and CFCFRMS integration are pending external partner gate. "
                "Please select SANDBOX or SIMULATED environment for testing."
            )
        )

    def query_action_status(self, action: BankAction, db: Session) -> Dict[str, Any]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Live Gateway status query unavailable pending external partner onboarding."
        )

    def process_partner_callback(
        self,
        payload: Dict[str, Any],
        signature: str,
        timestamp_str: str,
        callback_id: str,
        db: Session
    ) -> Dict[str, Any]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Live Gateway callback processing unavailable pending external partner onboarding."
        )


def get_bank_adapter(environment: str = "SANDBOX") -> BankAdapter:
    """Factory returning the appropriate BankAdapter for the given environment."""
    env = environment.strip().upper()
    if env == "LIVE":
        return LiveBankAdapter()
    return SandboxBankAdapter()
