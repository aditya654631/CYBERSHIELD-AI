import hmac
import hashlib
import time
import pytest
from unittest.mock import MagicMock, patch

from backend.app.adapters.notification.base import DeliveryResult
from backend.app.adapters.notification.email_adapter import EmailNotificationAdapter
from backend.app.adapters.notification.sms_adapter import SMSNotificationAdapter, mask_phone_number
from backend.app.adapters.notification.webhook_adapter import (
    PartnerWebhookAdapter,
    compute_webhook_signature,
    verify_webhook_signature,
)
from backend.app.schemas.schemas import AlertResponse


@pytest.fixture
def sample_alert_data():
    return {
        "id": 101,
        "complaint_id": 50,
        "complaint_number": "CMP-NEW-000192",
        "prediction_id": 221,
        "title": "Tactical Interception Alert: High Risk Cashout Predicted",
        "severity": "CRITICAL",
        "location_name": "Connaught Place / Central Delhi ATM Cluster",
        "risk_score": 0.885,
        "expected_window": "09:30 - 11:30 IST",
        "amount_at_risk": 75000.0,
        "status": "NEW",
    }


def test_mask_phone_number():
    assert mask_phone_number("+919876543210") == "+91****3210"
    assert mask_phone_number("9876543210") == "+91****3210"
    assert mask_phone_number("123") == "***"
    assert mask_phone_number("") == ""
    assert mask_phone_number(None) == ""


def test_email_adapter_simulated(sample_alert_data):
    adapter = EmailNotificationAdapter(mode="SIMULATED", smtp_host="", smtp_port=587)
    res = adapter.deliver(
        alert_dict=sample_alert_data,
        recipient="officer.delhi@gov.in",
        recipient_role="STATE_LEA",
    )
    assert res.success is True
    assert res.status == "SIMULATED_DELIVERED"
    assert res.channel == "EMAIL"
    assert res.recipient == "officer.delhi@gov.in"
    assert "CMP-NEW-000192" in res.details.get("subject", "")
    assert res.details.get("mode") == "SIMULATED"


def test_email_adapter_sandbox(sample_alert_data):
    adapter = EmailNotificationAdapter(mode="SANDBOX", sandbox_sink_dir="artifacts/test_sink")
    res = adapter.deliver(
        alert_dict=sample_alert_data,
        recipient="officer.delhi@gov.in",
    )
    assert res.success is True
    assert res.status == "SANDBOX_DELIVERED"
    assert res.details.get("mode") == "SANDBOX"


def test_email_adapter_zero_pii(sample_alert_data):
    adapter = EmailNotificationAdapter(mode="SIMULATED")
    # Simulate an alert payload with victim sensitive info
    alert_with_pii = dict(sample_alert_data)
    alert_with_pii["victim_name"] = "John Doe"
    alert_with_pii["victim_aadhaar"] = "1234-5678-9012"

    subject, body_text = adapter._render_email_body(alert_with_pii)
    assert "John Doe" not in subject
    assert "John Doe" not in body_text
    assert "1234-5678-9012" not in body_text
    assert "Connaught Place" in body_text
    assert "CRITICAL" in body_text


def test_sms_adapter_simulated(sample_alert_data):
    adapter = SMSNotificationAdapter(mode="SIMULATED")
    res = adapter.deliver(
        alert_dict=sample_alert_data,
        recipient="+919876543210",
        recipient_role="DISTRICT_LEA",
    )
    assert res.success is True
    assert res.status == "SIMULATED_DELIVERED"
    assert res.channel == "SMS"
    assert res.recipient == "+91****3210"
    message_text = res.details.get("message_text", "")
    assert "CYBERSHIELD CRITICAL ALERT" in message_text
    assert "CMP-NEW-000192" in message_text
    assert len(message_text) <= 320


def test_sms_adapter_unconfigured():
    adapter = SMSNotificationAdapter(mode="LIVE", gateway_url="")
    res = adapter.deliver(alert_dict={"id": 1}, recipient="+919876543210")
    assert res.success is False
    assert res.status == "NOT_CONFIGURED"
    assert res.retryable is False


def test_webhook_signature_generation_and_verification():
    secret = "my_super_secret_webhook_key_2026"
    body = '{"event":"ALERT_GENERATED","alert_id":101}'
    ts = str(int(time.time()))

    sig = compute_webhook_signature(body, secret, ts)
    assert isinstance(sig, str)
    assert len(sig) == 64  # SHA-256 hex length

    # Valid verification
    assert verify_webhook_signature(body, secret, ts, sig) is True

    # Tampered body verification fails
    assert verify_webhook_signature(body + " ", secret, ts, sig) is False

    # Tampered timestamp fails
    assert verify_webhook_signature(body, secret, str(int(ts) + 1), sig) is False

    # Expired timestamp (older than tolerance) fails
    old_ts = str(int(time.time()) - 600)
    old_sig = compute_webhook_signature(body, secret, old_ts)
    assert verify_webhook_signature(body, secret, old_ts, old_sig, max_age_seconds=300) is False


def test_partner_webhook_adapter_simulated(sample_alert_data):
    adapter = PartnerWebhookAdapter(mode="SIMULATED", secret="test_secret_123")
    res = adapter.deliver(
        alert_dict=sample_alert_data,
        recipient="https://partner.i4c.gov.in/api/v1/webhooks/alerts",
        idempotency_key="outbox_101_ALERT_PARTNER_v1",
    )
    assert res.success is True
    assert res.status == "SIMULATED_DELIVERED"
    assert res.channel == "PARTNER_WEBHOOK"
    assert res.details.get("signature_algorithm") == "HMAC-SHA256"
    assert res.details.get("mode") == "SIMULATED"


def test_partner_webhook_secret_not_leaked():
    secret = "ultra_sensitive_secret_token_abcdef123456"
    adapter = PartnerWebhookAdapter(mode="SIMULATED", secret=secret)
    status_dict = adapter.get_status()
    # The secret itself or raw token must never appear in get_status
    assert secret not in str(status_dict)
    assert status_dict["details"]["secret_configured"] is True

    res = adapter.deliver(alert_dict={"id": 1}, recipient="https://partner.org/webhook")
    # Secret must not appear in delivery result details
    assert secret not in str(res.details)
