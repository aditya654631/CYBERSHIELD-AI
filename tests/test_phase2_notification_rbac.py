import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app
from backend.app.models.db import Base, get_db
from backend.app.models.models import Alert, Complaint, NotificationOutbox, User, Organization
from backend.app.auth.security import create_access_token


@pytest.fixture
def client_and_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = TestingSessionLocal()

    # Seed Orgs
    delhi_org = Organization(id=1, name="Delhi Police", org_type="LEA", state="DELHI", district="NEW DELHI")
    mumbai_org = Organization(id=2, name="Mumbai Police", org_type="LEA", state="MAHARASHTRA", district="MUMBAI CITY")
    db.add_all([delhi_org, mumbai_org])
    db.commit()

    # Seed Users
    delhi_officer = User(
        id=1,
        email="officer.delhi@gov.in",
        full_name="Delhi LEA Officer",
        hashed_password="mock_hashed_password",
        role="STATE_LEA",
        organization_id=1,
        is_active=True,
    )
    mumbai_officer = User(
        id=2,
        email="officer.mumbai@gov.in",
        full_name="Mumbai LEA Officer",
        hashed_password="mock_hashed_password",
        role="STATE_LEA",
        organization_id=2,
        is_active=True,
    )
    admin_user = User(
        id=3,
        email="admin@i4c.gov.in",
        full_name="I4C Admin User",
        hashed_password="mock_hashed_password",
        role="I4C_ADMIN",
        organization_id=1,
        is_active=True,
    )
    db.add_all([delhi_officer, mumbai_officer, admin_user])
    db.commit()

    # Seed Complaints & Alerts
    delhi_comp = Complaint(
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
    db.add(delhi_comp)
    db.commit()

    delhi_alert = Alert(
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
    db.add(delhi_alert)
    db.commit()

    # Seed Outbox
    ob_ws = NotificationOutbox(
        id=1,
        alert_id=1,
        event_type="ALERT_GENERATED",
        prediction_id=221,
        channel="DASHBOARD_WEBSOCKET",
        status="DELIVERED",
        attempt_count=1,
        max_attempts=5,
        payload={"event": "ALERT_GENERATED", "title": "Tactical Interception Alert"},
        idempotency_key="ob_1_ws",
        created_at=datetime.utcnow(),
    )
    ob_email = NotificationOutbox(
        id=2,
        alert_id=1,
        event_type="ALERT_GENERATED",
        prediction_id=221,
        channel="EMAIL",
        status="DELIVERED",
        attempt_count=1,
        max_attempts=5,
        payload={"event": "ALERT_GENERATED", "title": "Tactical Interception Alert"},
        idempotency_key="ob_1_email",
        created_at=datetime.utcnow(),
    )
    db.add_all([ob_ws, ob_email])
    db.commit()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    yield client, db, delhi_officer, mumbai_officer, admin_user

    app.dependency_overrides.clear()
    db.close()


def test_channels_status_endpoint_rbac(client_and_db):
    client, db, delhi_officer, mumbai_officer, admin_user = client_and_db

    # Unauthorized access (no token) -> 401
    res = client.get("/api/v1/alerts/channels/status")
    assert res.status_code == 401

    # Authorized access (Delhi LEA) -> 200
    token = create_access_token(data={"sub": delhi_officer.email, "role": delhi_officer.role})
    res = client.get("/api/v1/alerts/channels/status", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "dashboard_websocket" in data
    assert "email" in data
    assert "sms" in data
    assert "partner_webhook" in data

    # Ensure no secrets or passwords leaked in response
    resp_str = str(data)
    assert "password" not in resp_str.lower()
    assert "token" not in resp_str.lower() or "active_connections" in resp_str


def test_channel_delivery_status_in_alerts_api(client_and_db):
    client, db, delhi_officer, mumbai_officer, admin_user = client_and_db

    # Delhi officer lists alerts -> should see alert #1 with channel_delivery_status
    token_delhi = create_access_token(data={"sub": delhi_officer.email, "role": delhi_officer.role})
    res = client.get("/api/v1/alerts", headers={"Authorization": f"Bearer {token_delhi}"})
    assert res.status_code == 200
    alerts = res.json()
    assert len(alerts) >= 1
    alert1 = [a for a in alerts if a["id"] == 1][0]
    assert "channel_delivery_status" in alert1
    assert "DASHBOARD_WEBSOCKET" in alert1["channel_delivery_status"]
    assert "EMAIL" in alert1["channel_delivery_status"]
    assert alert1["channel_delivery_status"]["EMAIL"]["status"] == "DELIVERED"

    # Mumbai officer lists alerts -> 0 alerts (jurisdiction isolation)
    token_mumbai = create_access_token(data={"sub": mumbai_officer.email, "role": mumbai_officer.role})
    res_mumbai = client.get("/api/v1/alerts", headers={"Authorization": f"Bearer {token_mumbai}"})
    assert res_mumbai.status_code == 200
    assert len(res_mumbai.json()) == 0

    # Mumbai officer accesses /alerts/1 directly -> 404 (does not leak existence)
    res_single = client.get("/api/v1/alerts/1", headers={"Authorization": f"Bearer {token_mumbai}"})
    assert res_single.status_code == 404
