"""Phase 03 authorization, object scope, and WebSocket recipient matrix."""
import asyncio
import concurrent.futures
import datetime as dt
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from unittest.mock import AsyncMock

from backend.app.main import app
from backend.app.config.settings import settings
from backend.app.auth.security import create_access_token, get_password_hash
from backend.app.models.models import (
    Organization, User, Complaint, Account, ComplaintAccount, Alert, BankAction,
)
from backend.app.websocket.manager import ConnectionManager


def _headers(email: str, claimed_role: str = "DISTRICT_LEA"):
    return {"Authorization": f"Bearer {create_access_token({'sub': email, 'role': claimed_role})}"}


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/v1/auth/me"),
    ("GET", "/api/v1/complaints"),
    ("GET", "/api/v1/complaints/1"),
    ("GET", "/api/v1/complaints/1/transactions"),
    ("GET", "/api/v1/complaints/1/transactions/context"),
    ("GET", "/api/v1/complaints/1/graph"),
    ("GET", "/api/v1/predictions/1"),
    ("GET", "/api/v1/predictions/1/versions"),
    ("GET", "/api/v1/predictions/version/1"),
    ("GET", "/api/v1/predictions/1/explanation"),
    ("GET", "/api/v1/predictions/1/audit-verification"),
    ("GET", "/api/v1/risk-map"),
    ("GET", "/api/v1/clusters"),
    ("GET", "/api/v1/clusters/1"),
    ("GET", "/api/v1/risk-map/prediction/1"),
    ("GET", "/api/v1/alerts"),
    ("GET", "/api/v1/alerts/1"),
    ("GET", "/api/v1/bank-actions"),
    ("GET", "/api/v1/bank-actions/1"),
    ("GET", "/api/v1/dashboard/summary"),
    ("GET", "/api/v1/analytics/overview"),
    ("GET", "/api/v1/model/performance"),
    ("GET", "/api/v1/audit/logs"),
    ("GET", "/api/v1/system/status"),
])
def test_all_sensitive_route_families_require_authentication(method, path):
    with TestClient(app) as client:
        response = client.request(method, path)
    assert response.status_code == 401, (path, response.status_code, response.text)


def test_forged_expired_and_inactive_sessions_are_rejected(db_session):
    inactive = User(
        email="phase3.inactive@example.gov.in", hashed_password=get_password_hash("Unused@123"),
        full_name="Inactive Phase 3", role="DISTRICT_LEA", organization_id=3, is_active=False,
    )
    db_session.add(inactive)
    db_session.commit()

    forged = jwt.encode(
        {"sub": "admin@cybershield.gov.in", "exp": dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)},
        "wrong-phase3-secret", algorithm=settings.ALGORITHM,
    )
    expired = create_access_token(
        {"sub": "admin@cybershield.gov.in"}, expires_delta=dt.timedelta(seconds=-1)
    )
    inactive_token = create_access_token({"sub": inactive.email, "role": "I4C_ADMIN"})
    with TestClient(app) as client:
        assert client.get("/api/v1/complaints", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
        assert client.get("/api/v1/complaints", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
        assert client.get("/api/v1/complaints", headers={"Authorization": f"Bearer {inactive_token}"}).status_code == 401


@pytest.fixture
def phase3_scope_data(db_session):
    suffix = str(int(dt.datetime.now().timestamp() * 1_000_000))
    delhi_a = Organization(name=f"Delhi A {suffix}", org_type="LEA", state="Delhi", district="District A")
    delhi_b = Organization(name=f"Delhi B {suffix}", org_type="LEA", state="Delhi", district="District B")
    mh = Organization(name=f"Maharashtra {suffix}", org_type="LEA", state="Maharashtra", district="Mumbai")
    bank_a = Organization(name=f"Trusted Bank A {suffix}", org_type="BANK", state="Delhi", district="District A")
    bank_b = Organization(name=f"Trusted Bank B {suffix}", org_type="BANK", state="Delhi", district="District B")
    db_session.add_all([delhi_a, delhi_b, mh, bank_a, bank_b])
    db_session.flush()

    users = {}
    for key, role, org in [
        ("district_a", "DISTRICT_LEA", delhi_a),
        ("district_b", "DISTRICT_LEA", delhi_b),
        ("state_mh", "STATE_LEA", mh),
        ("analyst_a", "ANALYST", delhi_a),
        ("auditor_a", "AUDITOR", delhi_a),
        ("bank_a", "BANK_OFFICER", bank_a),
        ("bank_b", "BANK_OFFICER", bank_b),
    ]:
        user = User(
            email=f"{key}.{suffix}@phase3.test", hashed_password=get_password_hash("Phase3@123"),
            full_name=key, role=role, organization_id=org.id, is_active=True,
        )
        db_session.add(user)
        users[key] = user
    db_session.flush()

    complaints = {}
    for key, state, district, owner in [
        ("a", "Delhi", "District A", delhi_a),
        ("b", "Delhi", "District B", delhi_b),
        ("mh", "Maharashtra", "Mumbai", mh),
    ]:
        complaint = Complaint(
            complaint_number=f"CMP-P3-{key.upper()}-{suffix}", fraud_type="UPI Fraud", amount=1000,
            victim_location=f"{district}, {state}", state=state, district=district,
            reported_at=dt.datetime.utcnow(), incident_time=dt.datetime.utcnow(),
            owner_organization_id=owner.id,
        )
        db_session.add(complaint)
        complaints[key] = complaint
    db_session.flush()

    account_a = Account(
        account_number=f"P3A{suffix}", masked_account="ACC••••0001", bank_name="Display Bank A",
        bank_organization_id=bank_a.id, holder_name="A", state="Delhi", district="District A",
    )
    account_b = Account(
        account_number=f"P3B{suffix}", masked_account="ACC••••0002", bank_name="Display Bank B",
        bank_organization_id=bank_b.id, holder_name="B", state="Delhi", district="District B",
    )
    db_session.add_all([account_a, account_b])
    db_session.flush()
    db_session.add_all([
        ComplaintAccount(complaint_id=complaints["a"].id, account_id=account_a.id, association_type="BENEFICIARY"),
        ComplaintAccount(complaint_id=complaints["b"].id, account_id=account_b.id, association_type="BENEFICIARY"),
    ])
    alerts = {}
    actions = {}
    for key, complaint, bank_org in [
        ("a", complaints["a"], bank_a), ("b", complaints["b"], bank_b)
    ]:
        alert = Alert(
            complaint_id=complaint.id, title=f"P3 {key}", severity="HIGH",
            location_name=complaint.victim_location, status="NEW", created_at=dt.datetime.utcnow(),
        )
        db_session.add(alert)
        db_session.flush()
        action = BankAction(
            action_reference=f"ACT-P3-{key.upper()}-{suffix}", complaint_id=complaint.id,
            alert_id=alert.id, bank_name=f"Display {key}", bank_organization_id=bank_org.id,
            status="SENT", is_simulated=True, requested_at=dt.datetime.utcnow(), created_at=dt.datetime.utcnow(),
        )
        db_session.add(action)
        alerts[key] = alert
        actions[key] = action
    db_session.commit()
    return {"users": users, "complaints": complaints, "alerts": alerts, "actions": actions,
            "banks": {"a": bank_a, "b": bank_b}}


def test_list_and_direct_object_scope_agree(phase3_scope_data):
    d = phase3_scope_data
    user = d["users"]["district_a"]
    # A forged role claim is ignored; the database identity remains DISTRICT_LEA.
    headers = _headers(user.email, claimed_role="I4C_ADMIN")
    with TestClient(app) as client:
        listed = client.get("/api/v1/complaints", headers=headers)
        assert listed.status_code == 200
        numbers = {row["complaint_number"] for row in listed.json()}
        assert d["complaints"]["a"].complaint_number in numbers
        assert d["complaints"]["b"].complaint_number not in numbers
        assert d["complaints"]["mh"].complaint_number not in numbers

        assert client.get(f"/api/v1/complaints/{d['complaints']['a'].id}", headers=headers).status_code == 200
        assert client.get(f"/api/v1/complaints/{d['complaints']['b'].id}", headers=headers).status_code == 404
        assert client.get(f"/api/v1/complaints/{d['complaints']['mh'].id}", headers=headers).status_code == 404
        assert client.get(f"/api/v1/alerts/{d['alerts']['b'].id}", headers=headers).status_code == 404


def test_cross_bank_scope_uses_organization_ids(phase3_scope_data):
    d = phase3_scope_data
    headers_a = _headers(d["users"]["bank_a"].email, "I4C_ADMIN")
    with TestClient(app) as client:
        complaints = client.get("/api/v1/complaints", headers=headers_a).json()
        numbers = {row["complaint_number"] for row in complaints}
        assert d["complaints"]["a"].complaint_number in numbers
        assert d["complaints"]["b"].complaint_number not in numbers
        assert client.get(f"/api/v1/alerts/{d['alerts']['a'].id}", headers=headers_a).status_code == 200
        assert client.get(f"/api/v1/alerts/{d['alerts']['b'].id}", headers=headers_a).status_code == 404
        assert client.get(f"/api/v1/bank-actions/{d['actions']['a'].id}", headers=headers_a).status_code == 200
        assert client.get(f"/api/v1/bank-actions/{d['actions']['b'].id}", headers=headers_a).status_code == 404


def test_analyst_and_auditor_are_scoped_and_auditor_is_read_only(phase3_scope_data):
    d = phase3_scope_data
    for key in ("analyst_a", "auditor_a"):
        headers = _headers(d["users"][key].email, "I4C_ADMIN")
        with TestClient(app) as client:
            rows = client.get("/api/v1/complaints", headers=headers).json()
            numbers = {row["complaint_number"] for row in rows}
            assert d["complaints"]["a"].complaint_number in numbers
            assert d["complaints"]["b"].complaint_number not in numbers
    with TestClient(app) as client:
        auditor_headers = _headers(d["users"]["auditor_a"].email)
        response = client.post(
            f"/api/v1/alerts/{d['alerts']['a'].id}/acknowledge",
            headers=auditor_headers, json={"notes": "must not mutate"},
        )
        assert response.status_code == 403


def test_dashboard_and_analytics_use_the_same_object_scope(phase3_scope_data):
    d = phase3_scope_data
    headers = _headers(d["users"]["district_a"].email, "I4C_ADMIN")
    with TestClient(app) as client:
        dashboard = client.get("/api/v1/dashboard/summary", headers=headers)
        analytics = client.get("/api/v1/analytics/timeline", headers=headers)
    assert dashboard.status_code == 200
    assert analytics.status_code == 200
    recent_numbers = {row["complaint_number"] for row in dashboard.json()["recent_complaints"]}
    timeline_numbers = {row["complaint_number"] for row in analytics.json()}
    assert d["complaints"]["a"].complaint_number in recent_numbers
    assert d["complaints"]["b"].complaint_number not in recent_numbers
    assert d["complaints"]["mh"].complaint_number not in recent_numbers
    assert d["complaints"]["b"].complaint_number not in timeline_numbers


def test_national_admin_can_read_scoped_direct_objects(phase3_scope_data):
    d = phase3_scope_data
    headers = _headers("admin@cybershield.gov.in", "DISTRICT_LEA")
    with TestClient(app) as client:
        for complaint in d["complaints"].values():
            assert client.get(f"/api/v1/complaints/{complaint.id}", headers=headers).status_code == 200
        for alert in d["alerts"].values():
            assert client.get(f"/api/v1/alerts/{alert.id}", headers=headers).status_code == 200


def test_websocket_recipient_scope_matches_http_scope(phase3_scope_data):
    d = phase3_scope_data

    async def run():
        manager = ConnectionManager()
        sockets = {key: AsyncMock() for key in ("district_a", "district_b", "bank_a", "bank_b")}
        for key, socket in sockets.items():
            await manager.connect(socket, d["users"][key])
        admin_socket = AsyncMock()
        class Admin:
            id = 1
            role = "I4C_ADMIN"
            state = "Delhi"
            district = "CENTRAL_NEW_DELHI"
            organization_id = 1
            organization = type("Org", (), {"org_type": "I4C"})()
        await manager.connect(admin_socket, Admin())

        await manager.broadcast(
            {"event": "ALERT_CREATED", "state": "Delhi", "district": "District A"},
            target_state="Delhi", target_district="District A",
            target_organization_ids=[d["banks"]["a"].id],
            required_roles=["I4C_ADMIN", "DISTRICT_LEA", "BANK_OFFICER"],
        )
        sockets["district_a"].send_text.assert_called_once()
        sockets["district_b"].send_text.assert_not_called()
        sockets["bank_a"].send_text.assert_called_once()
        sockets["bank_b"].send_text.assert_not_called()
        admin_socket.send_text.assert_called_once()

    asyncio.run(run())


def test_migration_0013_from_populated_0012(tmp_path):
    """A populated 0012 database upgrades without invented ownership mappings."""
    from alembic import command
    from alembic.config import Config

    db_path = tmp_path / "phase3_0012.db"
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path.as_posix()}")
    command.upgrade(cfg, "0012_transaction_created_by_user_id")

    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    with engine.begin() as conn:
        conn.exec_driver_sql("INSERT INTO organizations (id, name, org_type) VALUES (9001, 'Legacy Org', 'LEA')")
        conn.exec_driver_sql(
            "INSERT INTO complaints (id, complaint_number, fraud_type, amount, victim_location, state, district, reported_at, incident_time, created_at) "
            "VALUES (9001, 'CMP-P3-LEGACY', 'UPI Fraud', 1000, 'Legacy', 'Delhi', 'Central', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
    command.upgrade(cfg, "head")
    cols = {c["name"] for c in inspect(engine).get_columns("complaints")}
    assert {"owner_organization_id", "owner_user_id"}.issubset(cols)
    with engine.connect() as conn:
        row = conn.exec_driver_sql(
            "SELECT owner_organization_id, owner_user_id FROM complaints WHERE id=9001"
        ).one()
    assert row == (None, None)
    engine.dispose()
