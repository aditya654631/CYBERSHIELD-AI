import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from backend.app.models.models import Alert, Complaint, NotificationOutbox, Prediction, User, Organization
from backend.app.auth.rbac import complaint_bank_organization_ids

logger = logging.getLogger(__name__)


def calculate_backoff(attempt: int) -> timedelta:
    """Bounded exponential backoff: min(5 * 2^(attempt - 1), 3600) seconds."""
    seconds = min(5 * (2 ** max(0, attempt - 1)), 3600)
    return timedelta(seconds=seconds)


class OutboxService:
    """
    Phase 5 Transactional Notification Outbox & Worker Service.
    Handles durable alert event enqueuing, worker lease-locking,
    exponential retry backoff, channel dispatching, prediction supersession,
    and window expiration.
    """

    def enqueue_alert_event(
        self,
        db: Session,
        alert: Alert,
        event_type: str,
        prediction_version: Optional[int] = None,
        channel: str = "DASHBOARD_WEBSOCKET",
        payload_extra: Optional[Dict[str, Any]] = None,
        recipient_role: Optional[str] = None,
        recipient_user_id: Optional[int] = None,
        recipient_org_id: Optional[int] = None,
        recipient_state: Optional[str] = None,
        recipient_district: Optional[str] = None,
    ) -> NotificationOutbox:
        """
        Atomically enqueues a NotificationOutbox record within the caller's active database transaction.
        Enforces idempotency and captures full routing context.
        """
        now_utc = datetime.utcnow()
        complaint = alert.complaint or db.query(Complaint).filter(Complaint.id == alert.complaint_id).first()
        pred = alert.prediction or (db.query(Prediction).filter(Prediction.id == alert.prediction_id).first() if alert.prediction_id else None)
        version = prediction_version or (pred.version_number if pred else 1)

        idempotency_key = f"outbox_{alert.id}_{event_type}_{channel}_v{version}_{recipient_org_id or 0}_{recipient_user_id or 0}"

        # Deduplication check
        existing = db.query(NotificationOutbox).filter(
            NotificationOutbox.idempotency_key == idempotency_key
        ).first()
        if existing:
            logger.info(f"[Outbox] Reusing existing outbox event #{existing.id} (key: {idempotency_key})")
            return existing

        bank_org_ids = sorted(complaint_bank_organization_ids(complaint.id, db)) if complaint else []

        payload = {
            "event": event_type,
            "alert_id": alert.id,
            "complaint_id": alert.complaint_id,
            "complaint_number": complaint.complaint_number if complaint else f"CMP-{alert.complaint_id}",
            "prediction_id": alert.prediction_id,
            "prediction_version": version,
            "title": alert.title,
            "severity": alert.severity,
            "location": alert.location_name,
            "risk_score": alert.risk_score,
            "expected_window": alert.expected_window,
            "amount_at_risk": float(alert.amount_at_risk) if alert.amount_at_risk else 0.0,
            "status": alert.status,
            "state": recipient_state or (complaint.state if complaint else None),
            "district": recipient_district or (complaint.district if complaint else None),
            "target_organization_ids": bank_org_ids,
            "timestamp": now_utc.isoformat() + "Z",
        }
        if payload_extra:
            payload.update(payload_extra)

        outbox_entry = NotificationOutbox(
            alert_id=alert.id,
            event_type=event_type,
            prediction_id=alert.prediction_id,
            prediction_version=version,
            channel=channel,
            recipient_role=recipient_role or "ALL_AUTHORIZED",
            recipient_user_id=recipient_user_id,
            recipient_organization_id=recipient_org_id,
            recipient_state=recipient_state or (complaint.state if complaint else None),
            recipient_district=recipient_district or (complaint.district if complaint else None),
            payload=payload,
            status="QUEUED",
            attempt_count=0,
            max_attempts=5,
            next_retry_at=now_utc,
            idempotency_key=idempotency_key,
            created_at=now_utc,
        )

        db.add(outbox_entry)
        # We do not commit here: the caller commits atomically with the Alert mutation.
        db.flush()
        return outbox_entry

    def enqueue_multi_channel_alert(
        self,
        db: Session,
        alert: Alert,
        event_type: str = "ALERT_GENERATED",
        prediction_version: Optional[int] = None,
        payload_extra: Optional[Dict[str, Any]] = None,
        channels: Optional[List[str]] = None,
        recipient_role: Optional[str] = None,
        recipient_user_id: Optional[int] = None,
        recipient_organization_id: Optional[int] = None,
        recipient_org_id: Optional[int] = None,
        recipient_state: Optional[str] = None,
        recipient_district: Optional[str] = None,
    ) -> List[NotificationOutbox]:
        """
        Atomically enqueues durable outbox notification records for multiple delivery channels
        (Dashboard WebSocket, Email, SMS, Partner Webhook) for an alert event.
        """
        target_channels = channels or ["DASHBOARD_WEBSOCKET", "EMAIL", "SMS", "PARTNER_WEBHOOK"]
        resolved_org_id = recipient_organization_id or recipient_org_id
        events = []
        for ch in target_channels:
            ev = self.enqueue_alert_event(
                db=db,
                alert=alert,
                event_type=event_type,
                prediction_version=prediction_version,
                channel=ch,
                payload_extra=payload_extra,
                recipient_role=recipient_role,
                recipient_user_id=recipient_user_id,
                recipient_org_id=resolved_org_id,
                recipient_state=recipient_state,
                recipient_district=recipient_district,
            )
            events.append(ev)
        return events

    def claim_pending_events(
        self,
        db: Session,
        worker_id: str,
        limit: int = 20,
        lease_seconds: int = 30
    ) -> List[NotificationOutbox]:
        """
        Atomically claims queued or retryable failed outbox items using worker lease locking.
        Stale/crashed worker leases are reclaimed automatically when lease_expires_at < now.
        """
        now = datetime.utcnow()
        lease_deadline = now + timedelta(seconds=lease_seconds)

        eligible_query = (
            db.query(NotificationOutbox)
            .filter(
                or_(
                    NotificationOutbox.status.in_(["QUEUED", "FAILED"]),
                    ((NotificationOutbox.status == "PROCESSING") & (NotificationOutbox.lease_expires_at < now))
                ),
                NotificationOutbox.attempt_count < NotificationOutbox.max_attempts,
                (NotificationOutbox.next_retry_at.is_(None) | (NotificationOutbox.next_retry_at <= now)),
                (NotificationOutbox.lease_expires_at.is_(None) | (NotificationOutbox.lease_expires_at < now))
            )
            .order_by(NotificationOutbox.created_at.asc())
            .limit(limit)
        )

        events = eligible_query.all()
        claimed = []
        for ev in events:
            ev.status = "PROCESSING"
            ev.worker_id = worker_id
            ev.locked_at = now
            ev.lease_expires_at = lease_deadline
            claimed.append(ev)

        if claimed:
            db.commit()
            for ev in claimed:
                db.refresh(ev)

        return claimed

    def process_event(
        self,
        db: Session,
        event: Any,
        simulated_failure: Optional[str] = None,
        custom_error: Optional[str] = None
    ) -> bool:
        """
        Executes delivery for a claimed outbox event across supported channels via NotificationDispatcher.
        Handles temporary and permanent simulated failures for comprehensive testing.
        """
        from backend.app.services.notification_dispatcher import notification_dispatcher

        if isinstance(event, int):
            event_obj = db.query(NotificationOutbox).filter(NotificationOutbox.id == event).first()
            if not event_obj:
                logger.error(f"[Outbox] Event ID #{event} not found in database.")
                return False
            event = event_obj

        now = datetime.utcnow()
        event.attempt_count += 1
        event.last_attempt_at = now

        # 1. Check for simulated test failure (for legacy test harness support)
        if simulated_failure == "TEMPORARY":
            error_msg = custom_error or f"Temporary provider connection timeout on attempt {event.attempt_count}"
            event.last_error = error_msg
            if event.attempt_count >= event.max_attempts:
                event.status = "PERMANENT_FAILURE"
                event.next_retry_at = None
                logger.error(f"[Outbox] Event #{event.id} reached max attempts ({event.max_attempts}). Status: PERMANENT_FAILURE.")
            else:
                event.status = "FAILED"
                event.next_retry_at = now + calculate_backoff(event.attempt_count)
                logger.warning(f"[Outbox] Event #{event.id} failed attempt {event.attempt_count}. Next retry at {event.next_retry_at}.")
            event.lease_expires_at = None
            db.commit()
            return False

        elif simulated_failure == "PERMANENT":
            error_msg = custom_error or "Fatal unrecoverable provider rejection (400 Bad Payload)"
            event.last_error = error_msg
            event.status = "PERMANENT_FAILURE"
            event.next_retry_at = None
            event.lease_expires_at = None
            db.commit()
            logger.error(f"[Outbox] Event #{event.id} marked PERMANENT_FAILURE: {error_msg}")
            return False

        # 2. Dispatch via channel adapter
        try:
            result = notification_dispatcher.dispatch(event)

            if result.success:
                event.status = "DELIVERED"
                event.delivered_at = now
                event.last_error = None
                event.lease_expires_at = None

                if isinstance(event.payload, dict):
                    p = dict(event.payload)
                    p["delivery_result"] = result.to_dict()
                    event.payload = p

                # Update associated Alert status if it was NEW
                alert = db.query(Alert).filter(Alert.id == event.alert_id).first()
                if alert and alert.status == "NEW":
                    alert.status = "DELIVERED"

                db.commit()
                logger.info(f"[Outbox] Event #{event.id} successfully delivered via {event.channel} ({result.delivery_status}).")
                return True
            else:
                event.last_error = result.error_message or f"Delivery failed on {event.channel}"
                if result.delivery_status == "PERMANENT_FAILURE" or event.attempt_count >= event.max_attempts:
                    event.status = "PERMANENT_FAILURE"
                    event.next_retry_at = None
                    logger.error(f"[Outbox] Event #{event.id} reached permanent failure: {event.last_error}")
                else:
                    event.status = "FAILED"
                    event.next_retry_at = now + calculate_backoff(event.attempt_count)
                    logger.warning(f"[Outbox] Event #{event.id} failed attempt {event.attempt_count}. Next retry at {event.next_retry_at}.")
                event.lease_expires_at = None

                if isinstance(event.payload, dict):
                    p = dict(event.payload)
                    p["delivery_result"] = result.to_dict()
                    event.payload = p

                db.commit()
                return False

        except Exception as exc:
            db.rollback()
            event.last_error = str(exc)
            if event.attempt_count >= event.max_attempts:
                event.status = "PERMANENT_FAILURE"
                event.next_retry_at = None
            else:
                event.status = "FAILED"
                event.next_retry_at = now + calculate_backoff(event.attempt_count)
            event.lease_expires_at = None
            db.commit()
            logger.error(f"[Outbox] Unexpected exception processing event #{event.id}: {exc}", exc_info=True)
            return False

    def supersede_older_alerts(
        self,
        db: Session,
        complaint_id: int,
        new_prediction_id: int,
        new_prediction_version: int
    ) -> List[Alert]:
        """
        When a new prediction version is generated for a complaint,
        supersedes any previous active/delivered alerts for that complaint.
        """
        now = datetime.utcnow()
        older_alerts = (
            db.query(Alert)
            .filter(
                Alert.complaint_id == complaint_id,
                Alert.prediction_id != new_prediction_id,
                Alert.status.in_(["NEW", "DELIVERED", "ACKNOWLEDGED"])
            )
            .all()
        )

        superseded = []
        for old_alert in older_alerts:
            old_alert.status = "SUPERSEDED"
            old_alert.superseded_by_prediction_id = new_prediction_id
            old_alert.superseded_at = now
            superseded.append(old_alert)

            # Enqueue supersession event
            self.enqueue_alert_event(
                db=db,
                alert=old_alert,
                event_type="ALERT_SUPERSEDED",
                prediction_version=new_prediction_version,
                payload_extra={
                    "superseded_by_prediction_id": new_prediction_id,
                    "superseded_at": now.isoformat() + "Z",
                    "reason": f"Superseded by Prediction #{new_prediction_id} (Version {new_prediction_version})"
                }
            )

        if superseded:
            db.commit()
            logger.info(f"[Outbox] Superseded {len(superseded)} older alerts for complaint {complaint_id}.")

        return superseded

    def expire_stale_alerts(self, db: Session) -> List[Alert]:
        """
        Scans active alerts past their expiration window and marks them EXPIRED.
        """
        now = datetime.utcnow()
        stale_alerts = (
            db.query(Alert)
            .filter(
                Alert.status.in_(["NEW", "DELIVERED"]),
                Alert.expires_at.isnot(None),
                Alert.expires_at <= now
            )
            .all()
        )

        expired = []
        for al in stale_alerts:
            al.status = "EXPIRED"
            expired.append(al)

            self.enqueue_alert_event(
                db=db,
                alert=al,
                event_type="ALERT_EXPIRED",
                payload_extra={
                    "expired_at": now.isoformat() + "Z",
                    "reason": f"Operational window expired at {al.expires_at.isoformat() if al.expires_at else 'N/A'}"
                }
            )

        if expired:
            db.commit()
            logger.info(f"[Outbox] Expired {len(expired)} stale alerts.")

        return expired


outbox_service = OutboxService()
