"""
CyberShield AI — Notification Channel Adapters Package (Phase 2)
"""

from backend.app.adapters.notification.base import (
    NotificationChannelAdapter,
    DeliveryResult,
)
from backend.app.adapters.notification.dashboard_adapter import DashboardNotificationAdapter
from backend.app.adapters.notification.email_adapter import EmailNotificationAdapter
from backend.app.adapters.notification.sms_adapter import SmsNotificationAdapter, mask_phone_number
from backend.app.adapters.notification.webhook_adapter import (
    WebhookNotificationAdapter,
    compute_webhook_signature,
    verify_webhook_signature,
)

__all__ = [
    "NotificationChannelAdapter",
    "DeliveryResult",
    "DashboardNotificationAdapter",
    "EmailNotificationAdapter",
    "SmsNotificationAdapter",
    "WebhookNotificationAdapter",
    "compute_webhook_signature",
    "verify_webhook_signature",
    "mask_phone_number",
]
