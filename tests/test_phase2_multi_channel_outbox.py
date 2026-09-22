import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.models.db import Base
from backend.app.models.models import Alert, Complaint, NotificationOutbox, User, Organization
from backend.app.services.outbox_service import OutboxService
from backend.app.services.notification_dispatcher import NotificationDispatcher
from backend.app.adapters.notification.base import DeliveryResult
from backend.app.adapters.notification.dashboard_adapter import DashboardNotificationAdapter
from backend.app.adapters.notification.email_adapter import EmailNotificationAdapter
from backend.app.adapters.notification.sms_adapter import SMSNotificationAdapter
from backend.app.adapters.notification.webhook_adapter import PartnerWebhookAdapter


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create dummy org and user
    org = Organization(id=1, name="Delhi Cyber Crime Police", org_type="LEA", state="DELHI", district="NEW DELHI")
    session.add(org)
    session.commit()

    user = User(
        id=1,
        email="officer.delhi@gov.in",
        full_name="Delhi Officer",
        hashed_password="mock_hashed_password",
        role="STATE_LEA",
        organization_id=1,
        is_active=True,
    )
    session.add(user)

    # Create complaint and alert
    complaint = Complaint(
        id=1,
        complaint_number="CMP-NEW-000192",
        fraud_type="ATM_CLONING",
        amount=75000.0,
        victim_name="Ramesh Kumar",
        victim_location="Connaught Place, New Delhi",
        state="DELHI",
        district="NEW DELHI",
        reported_at=datetime.utcnow(),
        incident_time=datetime.utcnow(),
        case_status="OPEN",
        risk_level="CRITICAL",
        prediction_status="GENERATED",
    )
    session.add(complaint)
    session.commit()

    alert = Alert(
        id=1,
        complaint_id=1,
        prediction_id=221,
        title="Tactical Interception Alert: High Risk Cashout Predicted",
        severity="CRITICAL",
        location_name="Connaught Place / Central Delhi ATM Cluster",
        risk_score=0.885,
        expected_window="09:30 - 11:30 IST",
        amount_at_risk=75000.0,
        status="NEW",
        created_at=datetime.utcnow(),
    )
    session.add(alert)
    session.commit()

    yield session
    session.close()


def test_enqueue_multi_channel_alert(db_session):
    outbox_svc = OutboxService()
    alert = db_session.query(Alert).first()

    items = outbox_svc.enqueue_multi_channel_alert(
        db_session,
        alert=alert,
        channels=["DASHBOARD_WEBSOCKET", "EMAIL", "SMS", "PARTNER_WEBHOOK"],
        recipient_role="STATE_LEA",
        recipient_organization_id=1,
        recipient_state="DELHI",
        recipient_district="NEW DELHI",
    )

    assert len(items) == 4
    channels_created = {it.channel for it in items}
    assert channels_created == {"DASHBOARD_WEBSOCKET", "EMAIL", "SMS", "PARTNER_WEBHOOK"}

    for it in items:
        assert it.status in ("QUEUED", "PENDING")
        assert it.attempt_count == 0
        assert it.alert_id == alert.id
        assert it.prediction_id == 221
        assert "outbox_1_ALERT_GENERATED_" in it.idempotency_key


def test_idempotent_enqueue_does_not_duplicate(db_session):
    outbox_svc = OutboxService()
    alert = db_session.query(Alert).first()

    # First enqueue
    outbox_svc.enqueue_multi_channel_alert(
        db_session,
        alert=alert,
        channels=["EMAIL", "SMS"],
        recipient_role="STATE_LEA",
    )
    count_first = db_session.query(NotificationOutbox).count()
    assert count_first == 2

    # Second enqueue with same parameters
    outbox_svc.enqueue_multi_channel_alert(
        db_session,
        alert=alert,
        channels=["EMAIL", "SMS"],
        recipient_role="STATE_LEA",
    )
    count_second = db_session.query(NotificationOutbox).count()
    assert count_second == 2  # Idempotent - no duplicate records inserted


def test_process_event_multi_channel_dispatcher(db_session):
    outbox_svc = OutboxService()
    alert = db_session.query(Alert).first()

    # Enqueue multi-channel records
    items = outbox_svc.enqueue_multi_channel_alert(
        db_session,
        alert=alert,
        channels=["DASHBOARD_WEBSOCKET", "EMAIL", "SMS", "PARTNER_WEBHOOK"],
    )

    for item in items:
        success = outbox_svc.process_event(db_session, item.id)
        assert success is True

    # Verify all records delivered
    db_session.expire_all()
    all_outbox = db_session.query(NotificationOutbox).all()
    for ob in all_outbox:
        assert ob.status in ("DELIVERED", "SIMULATED_DELIVERED")
        assert ob.delivered_at is not None
        assert ob.attempt_count == 1
        assert ob.payload is not None
        assert "delivery_result" in ob.payload


def test_channel_failure_isolation(db_session):
    """Test that a failure in Webhook channel does not block or fail Email/SMS delivery."""
    outbox_svc = OutboxService()
    alert = db_session.query(Alert).first()

    items = outbox_svc.enqueue_multi_channel_alert(
        db_session,
        alert=alert,
        channels=["EMAIL", "PARTNER_WEBHOOK"],
    )
    email_item = [it for it in items if it.channel == "EMAIL"][0]
    webhook_item = [it for it in items if it.channel == "PARTNER_WEBHOOK"][0]

    # Deliver Email successfully
    email_success = outbox_svc.process_event(db_session, email_item.id)
    assert email_success is True

    # Mock webhook adapter to fail
    with pytest.MonkeyPatch.context() as mp:
        def mock_failed_deliver(*args, **kwargs):
            return DeliveryResult(
                success=False,
                channel="PARTNER_WEBHOOK",
                delivery_status="FAILED",
                provider_environment="LIVE",
                error_code="TIMEOUT",
                error_message="Connection timed out to partner gateway",
            )
        from backend.app.services.notification_dispatcher import notification_dispatcher
        mp.setattr(notification_dispatcher.webhook_adapter, "deliver", mock_failed_deliver)
        mp.setattr(notification_dispatcher.webhook_adapter, "send", mock_failed_deliver)

        webhook_success = outbox_svc.process_event(db_session, webhook_item.id)
        assert webhook_success is False

    db_session.expire_all()
    reloaded_email = db_session.query(NotificationOutbox).filter_by(id=email_item.id).one()
    reloaded_webhook = db_session.query(NotificationOutbox).filter_by(id=webhook_item.id).one()

    assert reloaded_email.status in ("DELIVERED", "SIMULATED_DELIVERED")
    assert reloaded_webhook.status == "FAILED"
    assert "Connection timed out" in reloaded_webhook.last_error
    assert reloaded_webhook.next_retry_at is not None
