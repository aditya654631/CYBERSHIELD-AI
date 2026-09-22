"""
CyberShield AI — Notification Subsystem (Phase 2)
Provider-neutral base notification channel adapter interface and delivery result model.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any


@dataclass
class DeliveryResult:
    """
    Structured outcome of a notification channel delivery attempt.
    Enforces truthful status reporting without leaking sensitive credentials or PII.
    """
    success: bool
    channel: str
    delivery_status: str  # SIMULATED_DELIVERED, SANDBOX_DELIVERED, LIVE_DELIVERED, DELIVERY_FAILED, NOT_CONFIGURED, PERMANENT_FAILURE
    provider_environment: str  # SIMULATED, SANDBOX, LIVE, DISABLED
    provider_reference: Optional[str] = None
    attempted_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def status(self) -> str:
        return self.delivery_status

    @property
    def recipient(self) -> Optional[str]:
        return self.details.get("recipient") or self.details.get("masked_recipient")

    @property
    def retryable(self) -> bool:
        if self.delivery_status in ("NOT_CONFIGURED", "PERMANENT_FAILURE"):
            return False
        return not self.success

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "channel": self.channel,
            "delivery_status": self.delivery_status,
            "provider_environment": self.provider_environment,
            "provider_reference": self.provider_reference,
            "attempted_at": self.attempted_at.isoformat() if self.attempted_at else None,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "details": self.details
        }


class NotificationChannelAdapter(ABC):
    """
    Abstract Base Class for notification channel adapters (WebSocket, Email, SMS, Webhook).
    """

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """Canonical identifier for the channel (e.g., DASHBOARD_WEBSOCKET, EMAIL, SMS, PARTNER_WEBHOOK)."""
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """
        Returns safe channel operational status and environment mode without leaking secrets.
        """
        pass

    @abstractmethod
    def send(
        self,
        alert_id: int,
        event_type: str,
        payload: Dict[str, Any],
        idempotency_key: str,
        attempt_count: int = 1
    ) -> DeliveryResult:
        """
        Executes a delivery attempt over the specific channel.
        Must return a structured DeliveryResult without raising exceptions that break callers.
        """
        pass

    def deliver(
        self,
        alert_dict: Optional[Dict[str, Any]] = None,
        recipient: Optional[str] = None,
        recipient_role: Optional[str] = None,
        idempotency_key: str = "test_idempotency_key",
        **kwargs
    ) -> DeliveryResult:
        """
        Convenience delivery method bridging alert dictionaries directly to channel send.
        """
        payload = dict(alert_dict or {})
        if recipient:
            if "@" in str(recipient):
                payload["recipient_email"] = recipient
            elif str(recipient).startswith("http"):
                payload["target_url"] = recipient
            else:
                payload["recipient_phone"] = recipient
        if recipient_role:
            payload["recipient_role"] = recipient_role
        payload.update(kwargs)
        alert_id = payload.get("id") or payload.get("alert_id") or 1
        event_type = payload.get("event_type") or "ALERT_GENERATED"
        return self.send(
            alert_id=alert_id,
            event_type=event_type,
            payload=payload,
            idempotency_key=idempotency_key
        )
