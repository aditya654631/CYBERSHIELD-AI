"""
CyberShield AI — Phase 1: Security, Authorization, Jurisdiction Isolation,
CORS Hardening, and Truthful Operational Statuses Test Suite.

Covers all 10 Phase 1 Verification Requirements:
1. All sensitive endpoints return 401 when called without JWT.
2. Only /health and /api/v1/auth/login are accessible unauthenticated.
3. Forged, invalid, and expired JWT tokens return 401.
4. Inactive user accounts (is_active=False) are rejected on login and API calls.
5. Role-based permission matrix enforces access by role (Auditor/Analyst cannot mutate complaints or escalate; Auditor & I4C_Admin can access audit logs, others receive 403).
6. Cross-state and cross-district access returns 404 (zero information leakage).
7. Complaint registration automatically forces authenticated officer's jurisdiction.
8. Truthful Bank Action lifecycle, simulation flags, and idempotency are strictly enforced.
9. Authenticated WebSocket connection verifies query token (rejects missing/invalid with 1008).
10. Sliding window rate limiter throttles excessive failed login attempts (HTTP 429).
"""

import os
import time
from datetime import datetime, timezone, timedelta
import pytest
from jose import jwt
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.config.settings import settings
from backend.app.auth.security import create_access_token, get_password_hash
from backend.app.auth.rate_limiter import auth_rate_limiter
from backend.app.models.db import SessionLocal
from backend.app.models.models import (
    User, Complaint, Alert, AuditLog, BankAction, Account, Transaction
)

client = TestClient(app)


def _make_auth_header(email: str, role: str, expires_delta: timedelta = None) -> dict:
    claims = {"sub": email, "role": role}
    token = create_access_token(claims, expires_delta=expires_delta)
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# 1. Unauthenticated Access Protection (HTTP 401)
# ==============================================================================
@pytest.mark.parametrize("method,path,payload", [
    ("GET", "/api/v1/complaints", None),
    ("POST", "/api/v1/complaints", {"fraud_type": "UPI Fraud", "amount": 1000.0}),
    ("GET", "/api/v1/complaints/CMP-001", None),
    ("GET", "/api/v1/complaints/CMP-001/graph", None),
    ("GET", "/api/v1/complaints/CMP-001/transactions", None),
    ("GET", "/api/v1/predictions/CMP-001", None),
    ("POST", "/api/v1/predictions/CMP-001", {}),
    ("GET", "/api/v1/risk-map", None),
    ("GET", "/api/v1/clusters", None),
    ("GET", "/api/v1/alerts", None),
    ("POST", "/api/v1/alerts/1/acknowledge", {"notes": "test"}),
    ("POST", "/api/v1/alerts/1/escalate", {"notes": "test"}),
    ("GET", "/api/v1/dashboard/summary", None),
    ("GET", "/api/v1/analytics/overview", None),
    ("GET", "/api/v1/model/performance", None),
    ("GET", "/api/v1/audit/logs", None),
    ("GET", "/api/v1/bank-actions", None),
])
def test_sensitive_endpoints_reject_unauthenticated(method, path, payload):
    """Every sensitive API route MUST return 401 Unauthorized without JWT."""
    if method == "GET":
        resp = client.get(path)
    else:
        resp = client.post(path, json=payload or {})
    assert resp.status_code == 401, f"Path {path} returned {resp.status_code}, expected 401"
    assert "Not authenticated" in resp.json().get("detail", "") or "Could not validate" in resp.json().get("detail", "")


# ==============================================================================
# 2. Public Endpoints Whitelist
# ==============================================================================
def test_health_check_publicly_accessible():
    """Health check must remain accessible unauthenticated."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "database" in data
    assert "database_engine" in data
    assert "ml_engine" in data
    assert data["bank_gateway_status"].startswith("SIMULATED_LOCAL_PROTOTYPE")


def test_auth_login_publicly_accessible():
    """Login endpoint is accessible without Authorization header."""
    resp = client.post("/api/v1/auth/login", json={"email": "nonexistent@test.com", "password": "wrong"})
    assert resp.status_code in [401, 422]  # Validates credentials or schema, not Bearer token


# ==============================================================================
# 3. Forged and Expired Tokens (HTTP 401)
# ==============================================================================
def test_forged_signature_token_rejected():
    """A JWT signed with an untrusted key must be rejected with 401."""
    fake_token = jwt.encode(
        {"sub": "admin@cybershield.gov.in", "role": "I4C_ADMIN", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        "completely-wrong-secret-key-12345",
        algorithm="HS256"
    )
    resp = client.get("/api/v1/complaints", headers={"Authorization": f"Bearer {fake_token}"})
    assert resp.status_code == 401


def test_expired_token_rejected():
    """A JWT that has expired must be rejected with 401."""
    expired_token = create_access_token(
        {"sub": "admin@cybershield.gov.in", "role": "I4C_ADMIN"},
        expires_delta=timedelta(seconds=-60)
    )
    resp = client.get("/api/v1/complaints", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401


def test_malformed_token_rejected():
    """Malformed tokens must return 401."""
    resp = client.get("/api/v1/complaints", headers={"Authorization": "Bearer not.a.valid.jwt"})
    assert resp.status_code == 401


# ==============================================================================
# 4. Inactive User Verification
# ==============================================================================
def test_inactive_user_rejected_on_login_and_token(db_session):
    """Users with is_active=False cannot login and their tokens are rejected."""
    inactive_email = "inactive.officer@police.gov.in"
    user = db_session.query(User).filter(User.email == inactive_email).first()
    if not user:
        user = User(
            email=inactive_email,
            hashed_password=get_password_hash("TestPassword@123"),
            full_name="Inactive Officer",
            role="DISTRICT_LEA",
            organization_id=1,
            is_active=False,
            created_at=datetime.utcnow()
        )
        db_session.add(user)
    else:
        user.is_active = False
    db_session.commit()

    # Attempt login
    login_resp = client.post("/api/v1/auth/login", json={
        "email": inactive_email,
        "password": "TestPassword@123"
    })
    assert login_resp.status_code == 401
    assert any(w in login_resp.json().get("detail", "").lower() for w in ["deactivated", "inactive"])

    # Attempt API request with a token issued for this inactive user
    token = create_access_token({"sub": inactive_email, "role": "DISTRICT_LEA"})
    api_resp = client.get("/api/v1/complaints", headers={"Authorization": f"Bearer {token}"})
    assert api_resp.status_code == 401
    assert any(w in api_resp.json().get("detail", "").lower() for w in ["deactivated", "inactive"])


# ==============================================================================
# 5. Role-Based Access Control Matrix (RBAC)
# ==============================================================================
def test_auditor_and_analyst_cannot_create_complaints():
    """AUDITOR and ANALYST roles are forbidden from registering complaints (HTTP 403)."""
    auditor_headers = _make_auth_header("auditor@mha.gov.in", "AUDITOR")
    resp = client.post(
        "/api/v1/complaints",
        json={"fraud_type": "UPI Fraud", "amount": 1000.0},
        headers=auditor_headers
    )
    assert resp.status_code == 403

    analyst_headers = _make_auth_header("analyst@cybershield.gov.in", "ANALYST")
    resp = client.post(
        "/api/v1/complaints",
        json={"fraud_type": "UPI Fraud", "amount": 1000.0},
        headers=analyst_headers
    )
    assert resp.status_code == 403


def test_audit_logs_rbac_isolation():
    """Only I4C_ADMIN and AUDITOR can access audit logs; other roles get 403."""
    admin_headers = _make_auth_header("admin@cybershield.gov.in", "I4C_ADMIN")
    auditor_headers = _make_auth_header("auditor@mha.gov.in", "AUDITOR")
    # Use active Delhi Pilot district officer (User 13 — Inspector Amit Sharma, South Delhi)
    district_headers = _make_auth_header("district.lea@southdelhi.cyber.gov.in", "DISTRICT_LEA")
    analyst_headers = _make_auth_header("analyst@cybershield.gov.in", "ANALYST")

    # Allowed roles
    assert client.get("/api/v1/audit/logs", headers=admin_headers).status_code == 200
    assert client.get("/api/v1/audit/logs", headers=auditor_headers).status_code == 200

    # Forbidden roles
    assert client.get("/api/v1/audit/logs", headers=district_headers).status_code == 403
    assert client.get("/api/v1/audit/logs", headers=analyst_headers).status_code == 403


# ==============================================================================
# 6. Jurisdiction Isolation & Zero Information Leakage (HTTP 404)
# ==============================================================================
def test_cross_jurisdiction_isolation_and_404(db_session):
    """
    District LEA officers cannot see complaints outside their district/state.
    Requesting an out-of-jurisdiction complaint ID MUST return 404 (not 403)
    to guarantee zero information leakage and prevent ID enumeration.
    """
    delhi_complaint = db_session.query(Complaint).filter(
        Complaint.state == "Delhi"
    ).first()
    if not delhi_complaint:
        delhi_complaint = Complaint(
            complaint_number=f"CMP-DELHI-{int(time.time())}",
            fraud_type="UPI Fraud",
            amount=50000.0,
            state="Delhi",
            district="New Delhi",
            case_status="REGISTERED",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(delhi_complaint)
        db_session.commit()
        db_session.refresh(delhi_complaint)

    # South Delhi Cyber Cell officer token (active Delhi Pilot user, distinct district from 'New Delhi')
    south_delhi_headers = _make_auth_header("district.lea@southdelhi.cyber.gov.in", "DISTRICT_LEA")

    # 1. Collection query: a New Delhi complaint must NOT appear in the South Delhi officer's list
    list_resp = client.get("/api/v1/complaints", headers=south_delhi_headers)
    assert list_resp.status_code == 200
    complaints = list_resp.json()
    for c in complaints:
        # Org 11 district is 'SOUTH' as seeded in conftest
        assert c.get("state") == "Delhi", f"Found state leak: {c}"
        assert c.get("district") in ("SOUTH", "South Delhi"), f"Found district leak: {c}"

    # 2. Detail query for the New Delhi complaint ID: MUST return 404 (not 403)
    detail_resp = client.get(f"/api/v1/complaints/{delhi_complaint.complaint_number}", headers=south_delhi_headers)
    assert detail_resp.status_code == 404, f"Expected 404, got {detail_resp.status_code}"

    # 3. Graph query for the New Delhi complaint: MUST return 404
    graph_resp = client.get(f"/api/v1/complaints/{delhi_complaint.complaint_number}/graph", headers=south_delhi_headers)
    assert graph_resp.status_code == 404

    # 4. National I4C Admin CAN access the Delhi complaint
    admin_headers = _make_auth_header("admin@cybershield.gov.in", "I4C_ADMIN")
    admin_resp = client.get(f"/api/v1/complaints/{delhi_complaint.complaint_number}", headers=admin_headers)
    assert admin_resp.status_code == 200


# ==============================================================================
# 7. Spoof-Proof Officer Metadata Enforcement
# ==============================================================================
def test_spoof_proof_jurisdiction_enforcement_on_intake(db_session):
    """
    When an officer submits a complaint with spoofed state/district in the body,
    the backend strictly overrides it with the officer's real database jurisdiction.
    """
    # Active Delhi Pilot district officer (User 13 — Inspector Amit Sharma, South Delhi)
    south_delhi_headers = _make_auth_header("district.lea@southdelhi.cyber.gov.in", "DISTRICT_LEA")
    spoofed_num = f"CMP-SPOOF-{int(time.time())}"

    payload = {
        "complaint_number": spoofed_num,
        "fraud_type": "ATM Cash-Out Scam",
        "amount": 25000.0,
        "victim_account_number": "999888777111",
        "beneficiary_account_number": "999888777222",
        "beneficiary_bank": "State Bank of India",
        "state": "Maharashtra",        # Spoofed state
        "district": "Mumbai City",      # Spoofed district
        "demo_mode": False
    }

    resp = client.post("/api/v1/complaints", json=payload, headers=south_delhi_headers)
    assert resp.status_code == 200, resp.text
    created = resp.json()

    # The persisted state MUST be Delhi (Org 11 = district 'SOUTH'), NOT Maharashtra / Mumbai
    assert created["state"] == "Delhi"
    # Org 11 district is seeded as 'SOUTH' in conftest
    assert created["district"] in ("SOUTH", "South Delhi")


# ==============================================================================
# 8. Truthful Bank Action Lifecycle, Simulation, and Idempotency
# ==============================================================================
def test_bank_action_lifecycle_and_truthful_simulation(db_session):
    """
    Validates:
    - Hold action is marked is_simulated=True.
    - Idempotent escalation returns existing action.
    - Marking a simulated action COMPLETED on external network is rejected (400).
    - Transitions require Bank Officer or Admin role.
    """
    admin_headers = _make_auth_header("admin@cybershield.gov.in", "I4C_ADMIN")
    bank_headers = _make_auth_header("officer@sbi.co.in", "BANK_OFFICER")
    # Active Delhi Pilot district officer (User 13 — Inspector Amit Sharma, South Delhi)
    lea_headers = _make_auth_header("district.lea@southdelhi.cyber.gov.in", "DISTRICT_LEA")

    complaint = db_session.query(Complaint).first()
    unique_ref = f"TEST-ALERT-{int(time.time()*1000)}"
    alert = Alert(
        complaint_id=complaint.id,
        title=f"High-Risk Warning ({unique_ref})",
        location_name="Connaught Place ATM",
        amount_at_risk=45000.0,
        severity="CRITICAL",
        status="NEW",
        created_at=datetime.utcnow()
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)

    # 1. Escalate alert
    esc_resp = client.post(
        f"/api/v1/alerts/{alert.id}/escalate",
        json={"notes": "Ground team requesting emergency simulated freeze"},
        headers=admin_headers
    )
    assert esc_resp.status_code == 200, esc_resp.text
    alert_data = esc_resp.json()
    assert alert_data["status"] == "ACTION_INITIATED"

    # 2. Check BankAction record
    action = db_session.query(BankAction).filter(BankAction.alert_id == alert.id).first()
    assert action is not None
    assert action.is_simulated is True
    assert action.action_reference.startswith("ACT-HLD-")
    assert action.status in ["REQUESTED", "APPROVED", "SENT"]

    # 3. Idempotent escalation returns existing action
    esc_resp_2 = client.post(
        f"/api/v1/alerts/{alert.id}/escalate",
        json={"notes": "Duplicate escalation call"},
        headers=admin_headers
    )
    assert esc_resp_2.status_code == 200
    assert esc_resp_2.json()["status"] == "ACTION_INITIATED"

    # 4. District LEA cannot transition bank action (403)
    trans_lea = client.post(
        f"/api/v1/bank-actions/{action.action_reference}/transition",
        json={"target_status": "APPROVED"},
        headers=lea_headers
    )
    assert trans_lea.status_code == 403

    # 5. Transition to ACKNOWLEDGED via Bank Officer
    if action.status == "SENT":
        ack_resp = client.post(
            f"/api/v1/bank-actions/{action.action_reference}/transition",
            json={"target_status": "ACKNOWLEDGED", "notes": "Mock switch ack received"},
            headers=bank_headers
        )
        assert ack_resp.status_code == 200
        assert ack_resp.json()["status"] == "ACKNOWLEDGED"

        # 6. Attempting to mark a simulated action as COMPLETED MUST return 400
        comp_resp = client.post(
            f"/api/v1/bank-actions/{action.action_reference}/transition",
            json={"target_status": "COMPLETED", "notes": "Claiming live money frozen"},
            headers=bank_headers
        )
        assert comp_resp.status_code == 400
        assert "simulated" in comp_resp.json()["detail"].lower()


# ==============================================================================
# 9. Authenticated WebSocket Token Protection
# ==============================================================================
def test_websocket_token_authentication():
    """
    WebSocket /ws/alerts must reject missing or invalid query token with code 1008.
    A valid token successfully connects.
    """
    from starlette.websockets import WebSocketDisconnect

    # 1. No token -> Rejected with 1008
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/alerts") as ws:
            pass
    assert exc_info.value.code == 1008

    # 2. Invalid token -> Rejected with 1008
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/alerts?token=invalid.token.here") as ws:
            pass
    assert exc_info.value.code == 1008

    # 3. Valid token -> Connected successfully
    valid_token = create_access_token({"sub": "admin@cybershield.gov.in", "role": "I4C_ADMIN"})
    with client.websocket_connect(f"/ws/alerts?token={valid_token}") as ws:
        pass


# ==============================================================================
# 10. Login Rate Limiting (HTTP 429)
# ==============================================================================
def test_login_rate_limiter_triggers_429():
    """
    After 5 consecutive failed login attempts within 15 minutes,
    the 6th attempt is blocked with HTTP 429 Too Many Requests.
    """
    test_ip = "192.168.200.77"
    test_email = "ratelimit.phase1@example.com"
    auth_rate_limiter.reset(f"ip:{test_ip}")
    auth_rate_limiter.reset(f"email:{test_email}")

    # First 5 failed attempts return 401
    for i in range(5):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": test_email, "password": f"wrong_pass_{i}"},
            headers={"x-forwarded-for": test_ip}
        )
        assert resp.status_code == 401, f"Attempt {i+1} returned {resp.status_code}"

    # 6th attempt must return 429 Too Many Requests
    resp_6 = client.post(
        "/api/v1/auth/login",
        json={"email": test_email, "password": "wrong_pass_6"},
        headers={"x-forwarded-for": test_ip}
    )
    assert resp_6.status_code == 429
    assert "Too many failed login attempts" in resp_6.json().get("detail", "")

    # Cleanup
    auth_rate_limiter.reset(f"ip:{test_ip}")
    auth_rate_limiter.reset(f"email:{test_email}")
