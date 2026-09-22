"""
CyberShield AI — Multi-Channel Notification Dispatcher (Phase 2)
Coordinates delivery across Dashboard WebSocket, Email, SMS, and Signed Partner Webhook channels.
"""

import logging
from typing import Dict, Any, Optional

from backend.app.adapters.notification.base import (
    NotificationChannelAdapter,
    DeliveryResult,
)
from backend.app.adapters.notification.dashboard_adapter import DashboardNotificationAdapter
from backend.app.adapters.notification.email_adapter import EmailNotificationAdapter
from backend.app.adapters.notification.sms_adapter import SmsNotificationAdapter
from backend.app.adapters.notification.webhook_adapter import WebhookNotificationAdapter
from backend.app.models.models import NotificationOutbox

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    """
    Central dispatcher routing claimed outbox events to their respective channel adapters.
    """

    def __init__(self):
        self._adapters: Dict[str, NotificationChannelAdapter] = {
            "DASHBOARD_WEBSOCKET": DashboardNotificationAdapter(),
            "EMAIL": EmailNotificationAdapter(),
            "SMS": SmsNotificationAdapter(),
            "PARTNER_WEBHOOK": WebhookNotificationAdapter(),
            # Aliases for backwards compatibility
            "SIMULATED_EMAIL": EmailNotificationAdapter(),
            "SIMULATED_SMS": SmsNotificationAdapter(),
            "API_POLL": DashboardNotificationAdapter(),
        }

    @property
    def dashboard_adapter(self) -> Optional[NotificationChannelAdapter]:
        return self._adapters.get("DASHBOARD_WEBSOCKET")

    @dashboard_adapter.setter
    def dashboard_adapter(self, adapter: NotificationChannelAdapter) -> None:
        self._adapters["DASHBOARD_WEBSOCKET"] = adapter

    @property
    def email_adapter(self) -> Optional[NotificationChannelAdapter]:
        return self._adapters.get("EMAIL")

    @email_adapter.setter
    def email_adapter(self, adapter: NotificationChannelAdapter) -> None:
        self._adapters["EMAIL"] = adapter

    @property
    def sms_adapter(self) -> Optional[NotificationChannelAdapter]:
        return self._adapters.get("SMS")

    @sms_adapter.setter
    def sms_adapter(self, adapter: NotificationChannelAdapter) -> None:
        self._adapters["SMS"] = adapter

    @property
    def webhook_adapter(self) -> Optional[NotificationChannelAdapter]:
        return self._adapters.get("PARTNER_WEBHOOK")

    @webhook_adapter.setter
    def webhook_adapter(self, adapter: NotificationChannelAdapter) -> None:
        self._adapters["PARTNER_WEBHOOK"] = adapter

    def register_adapter(self, adapter: NotificationChannelAdapter) -> None:
        """Register or override a channel adapter."""
        self._adapters[adapter.channel_name] = adapter

    def get_adapter(self, channel: str) -> Optional[NotificationChannelAdapter]:
        """Retrieve registered adapter for channel."""
        return self._adapters.get(channel)

    def get_channels_status(self) -> Dict[str, Any]:
        """
        Returns safe channel operational statuses without exposing secrets or credentials.
        """
        status_map = {}
        for canonical_name in ["DASHBOARD_WEBSOCKET", "EMAIL", "SMS", "PARTNER_WEBHOOK"]:
            adapter = self._adapters.get(canonical_name)
            if adapter:
                status_map[canonical_name.lower()] = adapter.get_status()
            else:
                status_map[canonical_name.lower()] = {
                    "channel": canonical_name,
                    "enabled": False,
                    "mode": "DISABLED"
                }
        return status_map

    get_channel_statuses = get_channels_status

    def dispatch(self, event: NotificationOutbox) -> DeliveryResult:
        """
        Dispatches a claimed outbox event to its appropriate channel adapter.
        """
        adapter = self.get_adapter(event.channel)
        if not adapter:
            logger.error(f"[Dispatcher] No registered adapter for channel '{event.channel}'.")
            return DeliveryResult(
                success=False,
                channel=event.channel,
                delivery_status="NOT_CONFIGURED",
                provider_environment="UNKNOWN",
                error_code="UNSUPPORTED_CHANNEL",
                error_message=f"No notification adapter registered for channel '{event.channel}'."
            )

        try:
            return adapter.send(
                alert_id=event.alert_id,
                event_type=event.event_type,
                payload=event.payload or {},
                idempotency_key=event.idempotency_key,
                attempt_count=event.attempt_count
            )
        except Exception as exc:
            logger.error(
                f"[Dispatcher] Uncaught exception dispatching Event #{event.id} across {event.channel}: {exc}",
                exc_info=True
            )
            return DeliveryResult(
                success=False,
                channel=event.channel,
                delivery_status="DELIVERY_FAILED",
                provider_environment="ERROR",
                error_code="DISPATCH_EXCEPTION",
                error_message=str(exc)
            )


notification_dispatcher = NotificationDispatcher()
