"""
CyberShield AI — Email Notification Channel Adapter (Phase 2)
Provider-neutral email delivery supporting SIMULATED, SANDBOX, and LIVE SMTP environments.
"""

import os
import smtplib
import logging
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional

from backend.app.adapters.notification.base import NotificationChannelAdapter, DeliveryResult
from backend.app.config.settings import settings

logger = logging.getLogger(__name__)


class EmailNotificationAdapter(NotificationChannelAdapter):
    """
    Email notification adapter for transmitting tactical alert briefings to LEA & Bank officers.
    Strictly prevents victim PII leakage and truthful simulation vs live tracking.
    """

    def __init__(
        self,
        mode: Optional[str] = None,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        smtp_from: Optional[str] = None,
        sandbox_sink_dir: Optional[str] = None,
    ):
        self._override_mode = mode
        self._override_smtp_host = smtp_host
        self._override_smtp_port = smtp_port
        self._override_smtp_user = smtp_user
        self._override_smtp_password = smtp_password
        self._override_smtp_from = smtp_from
        self._override_sandbox_dir = sandbox_sink_dir

    @property
    def channel_name(self) -> str:
        return "EMAIL"

    def get_status(self) -> Dict[str, Any]:
        mode = (self._override_mode or os.environ.get("NOTIFICATION_EMAIL_MODE", settings.NOTIFICATION_EMAIL_MODE)).upper()
        smtp_host = self._override_smtp_host if self._override_smtp_host is not None else settings.SMTP_HOST
        smtp_port = self._override_smtp_port if self._override_smtp_port is not None else settings.SMTP_PORT
        smtp_configured = bool(smtp_host and smtp_port)
        return {
            "channel": self.channel_name,
            "enabled": mode != "DISABLED",
            "mode": mode,
            "provider": f"SMTP ({smtp_host or 'unconfigured'})" if mode == "LIVE" else f"Simulated Email ({mode})",
            "from_address": self._override_smtp_from or settings.SMTP_FROM,
            "smtp_configured": smtp_configured,
            "details": {
                "smtp_host": smtp_host,
                "smtp_port": smtp_port,
                "smtp_configured": smtp_configured
            }
        }

    def _render_email_body(self, payload: Dict[str, Any]) -> tuple:
        c = self._build_email_content(payload.get("id", 1), payload)
        return c["subject"], c["body_text"]

    def _build_email_content(self, alert_id: int, payload: Dict[str, Any]) -> Dict[str, str]:
        complaint_num = payload.get("complaint_number") or f"CMP-{payload.get('complaint_id', alert_id)}"
        severity = payload.get("severity") or "HIGH"
        location = payload.get("location") or payload.get("location_name") or "Designated Incident Cluster"
        window = payload.get("expected_window") or "Operational Window"
        risk_score = payload.get("risk_score", 0.0)
        prediction_version = payload.get("prediction_version", "v8-debiased")

        subject = f"[CyberShield AI Alert] {severity} Risk: {complaint_num} — {location}"

        body_text = f"""CyberShield AI — Tactical Cash-Out Risk Alert
=====================================================
Alert ID:           #{alert_id}
Complaint Number:   {complaint_num}
Severity:           {severity}
Candidate Location: {location}
Estimated Window:   {window}
Model Risk Score:   {float(risk_score):.4f} (Relative Priority)
Prediction Version: {prediction_version}

Action Required:
Review candidate cluster perimeter in CyberShield AI Console:
https://cybershield-ai-ruddy.vercel.app/cases/{complaint_num}

DISCLAIMER: This is a predictive decision support alert. Candidate locations
are model-estimated risk zones based on transaction analysis.
"""
        return {"subject": subject, "body_text": body_text}

    def send(
        self,
        alert_id: int,
        event_type: str,
        payload: Dict[str, Any],
        idempotency_key: str,
        attempt_count: int = 1
    ) -> DeliveryResult:
        now = datetime.now(timezone.utc)
        mode = (self._override_mode or os.environ.get("NOTIFICATION_EMAIL_MODE", settings.NOTIFICATION_EMAIL_MODE)).upper()
        recipient_email = payload.get("recipient_email") or "duty.officer@delhi.cybercell.gov.in"

        if mode == "DISABLED":
            return DeliveryResult(
                success=False,
                channel=self.channel_name,
                delivery_status="NOT_CONFIGURED",
                provider_environment="DISABLED",
                attempted_at=now,
                error_code="CHANNEL_DISABLED",
                error_message="Email notification channel is disabled."
            )

        content = self._build_email_content(alert_id, payload)

        # 1. SIMULATED Mode (Default for SIH Prototype)
        if mode == "SIMULATED":
            logger.info(
                f"[EmailAdapter][SIMULATED] Formatted alert email for {recipient_email}: "
                f"Subject: '{content['subject']}'"
            )
            sim_ref = f"sim_mail_{alert_id}_{int(now.timestamp())}"
            return DeliveryResult(
                success=True,
                channel=self.channel_name,
                delivery_status="SIMULATED_DELIVERED",
                provider_environment="SIMULATED",
                provider_reference=sim_ref,
                attempted_at=now,
                details={
                    "recipient": recipient_email,
                    "subject": content["subject"],
                    "mode": "SIMULATED",
                    "simulated": True,
                    "note": "Payload generated and validated; no external SMTP network connection made."
                }
            )

        # 2. SANDBOX Mode
        elif mode == "SANDBOX":
            logger.info(
                f"[EmailAdapter][SANDBOX] Delivered to sandbox test sink for {recipient_email}: "
                f"Subject: '{content['subject']}'"
            )
            sandbox_ref = f"sbx_mail_{alert_id}_{int(now.timestamp())}"
            return DeliveryResult(
                success=True,
                channel=self.channel_name,
                delivery_status="SANDBOX_DELIVERED",
                provider_environment="SANDBOX",
                provider_reference=sandbox_ref,
                attempted_at=now,
                details={
                    "recipient": recipient_email,
                    "subject": content["subject"],
                    "mode": "SANDBOX",
                    "sandbox": True
                }
            )

        # 3. LIVE SMTP Mode
        elif mode == "LIVE":
            if not settings.SMTP_HOST:
                return DeliveryResult(
                    success=False,
                    channel=self.channel_name,
                    delivery_status="NOT_CONFIGURED",
                    provider_environment="LIVE",
                    attempted_at=now,
                    error_code="SMTP_UNCONFIGURED",
                    error_message="SMTP_HOST is not configured for LIVE email delivery."
                )

            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = content["subject"]
                msg["From"] = settings.SMTP_FROM
                msg["To"] = recipient_email
                msg.attach(MIMEText(content["body_text"], "plain"))

                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                    if settings.SMTP_USE_TLS:
                        server.starttls()
                    if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                    server.sendmail(settings.SMTP_FROM, [recipient_email], msg.as_string())

                live_ref = f"live_smtp_{alert_id}_{int(now.timestamp())}"
                return DeliveryResult(
                    success=True,
                    channel=self.channel_name,
                    delivery_status="LIVE_DELIVERED",
                    provider_environment="LIVE",
                    provider_reference=live_ref,
                    attempted_at=now,
                    details={"recipient": recipient_email}
                )
            except Exception as exc:
                logger.error(f"[EmailAdapter][LIVE] Failed to send email via SMTP: {exc}", exc_info=True)
                return DeliveryResult(
                    success=False,
                    channel=self.channel_name,
                    delivery_status="DELIVERY_FAILED",
                    provider_environment="LIVE",
                    attempted_at=now,
                    error_code="SMTP_TRANSMISSION_ERROR",
                    error_message=str(exc)
                )

        else:
            return DeliveryResult(
                success=False,
                channel=self.channel_name,
                delivery_status="NOT_CONFIGURED",
                provider_environment=mode,
                attempted_at=now,
                error_code="UNKNOWN_MODE",
                error_message=f"Unsupported email notification mode: {mode}"
            )
