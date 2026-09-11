"""
CyberShield AI — Phase 1 Step 14: JWT Authentication + Real User Audit Test Suite

20 dedicated tests validating:
1. Valid JWT authentication and user response
2. Invalid credentials rejection (HTTP 401)
3. Missing JWT rejection across all protected mutation endpoints (HTTP 401)
4. Forged/invalid signature JWT rejection (HTTP 401)
5. Expired JWT rejection (HTTP 401)
6. Complaint registration records authenticated officer in AuditLog
7. Request body actor spoofing ignored on complaint registration
8. Predictive analysis execution records authenticated officer in AuditLog
9. Predictive analysis requires authentication (HTTP 401 on unauthenticated)
10. Alert generation records authenticated officer in AuditLog
11. Alert generation requires authentication (HTTP 401 on unauthenticated)
12. Alert acknowledgement records authenticated officer in Alert and AuditLog
13. Request body actor spoofing ignored on alert acknowledgement
14. Alert escalation records authenticated officer in AuditLog
15. GET /api/v1/auth/me returns authentic PostgreSQL profile
16. Audit Log API response includes user_id
17. Read-only endpoints generate zero fake/mutation audit events
18. Public endpoints (e.g. /health) remain accessible without JWT
19. Production settings strictly require non-default JWT_SECRET
20. Preservation of CMP-NEW-000126, Prediction #277, Alert #97, and historical audit records
"""

import os
from datetime import datetime, timedelta
import pytest
from jose import jwt
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.config.settings import settings, Settings, DEV_ONLY_JWT_SECRET
from backend.app.auth.security import create_access_token
from backend.app.models.db import SessionLocal
from backend.app.models.models import User, Complaint, Prediction, Alert, AuditLog

client = TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _get_auth_headers(email: str = "admin@cybershield.gov.in", role: str = "I4C_ADMIN") -> dict:
    token = create_access_token({"sub": email, "role": role})
    return {"Authorization": f"Bearer {token}"}


# 1. Valid JWT login
def test_auth_login_valid_credentials():
    resp = client.post("/api/v1/auth/login", json={
        "email": "admin@cybershield.gov.in",
        "password": "CyberAdmin@2026"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "admin@cybershield.gov.in"
    assert data["user"]["full_name"] == "Dr. Vikramaditya Sen"
    assert data["user"]["role"] == "I4C_ADMIN"


# 2. Invalid credentials rejection
def test_auth_login_invalid_credentials():
    resp = client.post("/api/v1/auth/login", json={
        "email": "admin@cybershield.gov.in",
        "password": "WrongPassword@2026"
    })
    assert resp.status_code == 401
    assert "Invalid officer credentials" in resp.json()["detail"]


# 3. Missing JWT rejected across protected endpoints
def test_missing_jwt_rejected_on_protected_endpoints():
    # Unauthenticated POST /complaints
    resp1 = client.post("/api/v1/complaints", json={"amount": 1000})
    assert resp1.status_code == 401

    # Unauthenticated POST /predictions/{id}
    resp2 = client.post("/api/v1/predictions/CMP-NEW-000126")
    assert resp2.status_code == 401

    # Unauthenticated POST /alerts/prediction/{id}
    resp3 = client.post("/api/v1/alerts/prediction/277")
    assert resp3.status_code == 401

    # Unauthenticated POST /alerts/{id}/acknowledge
    resp4 = client.post("/api/v1/alerts/97/acknowledge", json={"notes": "test"})
    assert resp4.status_code == 401

    # Unauthenticated POST /alerts/{id}/escalate
    resp5 = client.post("/api/v1/alerts/97/escalate", json={"notes": "test"})
    assert resp5.status_code == 401


# 4. Invalid JWT signature rejected
def test_invalid_jwt_signature_rejected():
    fake_token = jwt.encode({"sub": "admin@cybershield.gov.in"}, "wrong-secret-key-12345", algorithm="HS256")
    resp = client.post("/api/v1/complaints", json={"amount": 1000}, headers={"Authorization": f"Bearer {fake_token}"})
    assert resp.status_code == 401


# 5. Expired JWT rejected
def test_expired_jwt_rejected():
    expired_token = create_access_token(
        {"sub": "admin@cybershield.gov.in", "role": "I4C_ADMIN"},
        expires_delta=timedelta(minutes=-10)
    )
    resp = client.post("/api/v1/complaints", json={"amount": 1000}, headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401


# 6. Complaint creation records authenticated officer in AuditLog
def test_complaint_creation_records_authenticated_officer_in_audit(db):
    headers = _get_auth_headers("admin@cybershield.gov.in", "I4C_ADMIN")
    ts = int(datetime.utcnow().timestamp())

    payload = {
        "victim_name": "Rohan Gupta",
        "fraud_type": "UPI Phishing",
        "amount": 42000.0,
        "state": "Delhi",
        "district": "North Delhi",
        "locality": "Civil Lines",
        "payment_channel": "UPI",
        "incident_time": datetime.utcnow().isoformat(),
        "reported_at": datetime.utcnow().isoformat()
    }

    resp = client.post("/api/v1/complaints", json=payload, headers=headers)
    assert resp.status_code == 200
    created_comp_num = resp.json()["complaint_number"]

    # Verify audit record
    audit = db.query(AuditLog).filter(
        AuditLog.case_number == created_comp_num,
        AuditLog.action == "COMPLAINT_CREATED"
    ).order_by(AuditLog.id.desc()).first()

    assert audit is not None
    assert audit.user_id == 1  # Dr. Vikramaditya Sen
    assert audit.officer_name == "Dr. Vikramaditya Sen"
    assert audit.role == "I4C_ADMIN"


# 7. Request body actor spoofing ignored on complaint registration
def test_complaint_creation_ignores_body_spoofed_officer(db):
    # Authenticate as User 5 (Pooja Kulkarni, ANALYST)
    headers = _get_auth_headers("analyst@cybershield.gov.in", "ANALYST")

    payload = {
        "victim_name": "Sunil Sharma",
        "fraud_type": "Debit Card Fraud",
        "amount": 25000.0,
        "state": "Delhi",
        "district": "Central Delhi",
        "locality": "Karol Bagh",
        "payment_channel": "ATM",
        "incident_time": datetime.utcnow().isoformat(),
        "reported_at": datetime.utcnow().isoformat(),
        # Spoofed actor fields in request body
        "user_id": 9999,
        "officer_name": "Ghost Hacker",
        "created_by": "Fake Officer",
        "role": "SUPER_ADMIN"
    }

    resp = client.post("/api/v1/complaints", json=payload, headers=headers)
    assert resp.status_code == 200
    created_comp_num = resp.json()["complaint_number"]

    audit = db.query(AuditLog).filter(
        AuditLog.case_number == created_comp_num,
        AuditLog.action == "COMPLAINT_CREATED"
    ).order_by(AuditLog.id.desc()).first()

    assert audit is not None
    # Authoritative identity must match token, NOT spoofed payload
    assert audit.user_id == 5
    assert audit.officer_name == "Pooja Kulkarni"
    assert audit.role == "ANALYST"
    assert "Ghost Hacker" not in audit.officer_name


# 8. Predictive analysis execution records authenticated officer in AuditLog
def test_prediction_run_records_authenticated_officer_in_audit(db):
    headers = _get_auth_headers("state.lea@mp.police.gov.in", "STATE_LEA")
    resp = client.post("/api/v1/predictions/CMP-NEW-000126", headers=headers)
    assert resp.status_code == 200

    audit = db.query(AuditLog).filter(
        AuditLog.case_number == "CMP-NEW-000126",
        AuditLog.action == "PREDICTION_RUN"
    ).order_by(AuditLog.id.desc()).first()

    assert audit is not None
    assert audit.user_id == 2  # SP Anand Shekhawat, IPS
    assert audit.officer_name == "SP Anand Shekhawat, IPS"
    assert audit.role == "STATE_LEA"


# 9. Predictive analysis requires authentication
def test_prediction_run_requires_auth(db):
    pred_count_before = db.query(Prediction).count()
    audit_count_before = db.query(AuditLog).count()

    resp = client.post("/api/v1/predictions/CMP-NEW-000126")
    assert resp.status_code == 401

    db.expire_all()
    assert db.query(Prediction).count() == pred_count_before
    assert db.query(AuditLog).count() == audit_count_before


# 10. Alert generation records authenticated officer in AuditLog
def test_alert_generation_records_authenticated_officer_in_audit(db):
    # Register fresh complaint and run prediction so we get a fresh prediction without an existing alert
    headers_officer = _get_auth_headers("officer@sbi.co.in", "BANK_OFFICER")
    comp_resp = client.post("/api/v1/complaints", json={
        "victim_name": "Test Alert Target",
        "fraud_type": "Net Banking",
        "amount": 75000.0,
        "state": "Delhi",
        "district": "South Delhi",
        "locality": "Saket",
        "payment_channel": "IMPS",
        "sender_account_number": "ACC-55667788",
        "beneficiary_account_number": "ACC-99887766",
        "transaction_ref": f"TXN-S14-{int(datetime.utcnow().timestamp())}",
        "incident_time": datetime.utcnow().isoformat(),
        "reported_at": datetime.utcnow().isoformat()
    }, headers=headers_officer)
    assert comp_resp.status_code == 200
    comp_num = comp_resp.json()["complaint_number"]

    pred_resp = client.post(f"/api/v1/predictions/{comp_num}", headers=headers_officer)
    assert pred_resp.status_code == 200
    pred_id = pred_resp.json()["prediction_id"]

    resp = client.post(f"/api/v1/alerts/prediction/{pred_id}", headers=headers_officer)
    assert resp.status_code == 200

    alert_id = resp.json()["id"]
    audit = db.query(AuditLog).filter(
        AuditLog.action == "ALERT_CREATED",
        AuditLog.details.like(f"%Alert #{alert_id}%")
    ).order_by(AuditLog.id.desc()).first()

    assert audit is not None
    assert audit.user_id == 4  # Sunita Deshmukh
    assert audit.officer_name == "Sunita Deshmukh"
    assert audit.role == "BANK_OFFICER"


# 11. Alert generation requires authentication
def test_alert_generation_requires_auth(db):
    alert_count_before = db.query(Alert).count()
    resp = client.post("/api/v1/alerts/prediction/277")
    assert resp.status_code == 401

    db.expire_all()
    assert db.query(Alert).count() == alert_count_before


# 12. Alert acknowledgement records authenticated officer
def test_alert_acknowledgement_records_authenticated_officer(db):
    headers = _get_auth_headers("auditor@mha.gov.in", "AUDITOR")
    resp = client.post(
        "/api/v1/alerts/97/acknowledge",
        json={"notes": "Verified by MHA compliance audit team"},
        headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ACKNOWLEDGED"

    audit = db.query(AuditLog).filter(
        AuditLog.action == "ALERT_ACKNOWLEDGED",
        AuditLog.details.like("%Alert #97 acknowledged%")
    ).order_by(AuditLog.id.desc()).first()

    assert audit is not None
    assert audit.user_id == 6  # Col. Sanjeev Nair (Retd.)
    assert audit.officer_name == "Col. Sanjeev Nair (Retd.)"
    assert audit.role == "AUDITOR"


# 13. Alert acknowledgement ignores body spoofed officer
def test_alert_acknowledgement_ignores_body_spoofed_officer(db):
    # Create a fresh alert to acknowledge
    headers_user1 = _get_auth_headers("admin@cybershield.gov.in", "I4C_ADMIN")
    comp_resp = client.post("/api/v1/complaints", json={
        "victim_name": "Test Spoof Target",
        "fraud_type": "UPI Fraud",
        "amount": 33000.0,
        "state": "Delhi",
        "district": "North Delhi",
        "locality": "Rohini",
        "payment_channel": "UPI",
        "sender_account_number": "ACC-11223344",
        "beneficiary_account_number": "ACC-44332211",
        "transaction_ref": f"TXN-SPOOF-{int(datetime.utcnow().timestamp())}",
        "incident_time": datetime.utcnow().isoformat(),
        "reported_at": datetime.utcnow().isoformat()
    }, headers=headers_user1)
    assert comp_resp.status_code == 200
    comp_num = comp_resp.json()["complaint_number"]

    pred_resp = client.post(f"/api/v1/predictions/{comp_num}", headers=headers_user1)
    assert pred_resp.status_code == 200
    pred_id = pred_resp.json()["prediction_id"]

    alert_resp = client.post(f"/api/v1/alerts/prediction/{pred_id}", headers=headers_user1)
    assert alert_resp.status_code == 200
    fresh_alert_id = alert_resp.json()["id"]

    spoofed_body = {
        "notes": "Legitimate action taken",
        "acknowledged_by": "Fictional Deputy Commissioner",
        "officer_name": "Rogue Agent",
        "user_id": 8888
    }

    resp = client.post(f"/api/v1/alerts/{fresh_alert_id}/acknowledge", json=spoofed_body, headers=headers_user1)
    assert resp.status_code == 200
    data = resp.json()
    assert "Dr. Vikramaditya Sen" in data["acknowledged_by"]
    assert "Fictional Deputy Commissioner" not in data["acknowledged_by"]

    audit = db.query(AuditLog).filter(
        AuditLog.action == "ALERT_ACKNOWLEDGED",
        AuditLog.details.like(f"%Alert #{fresh_alert_id} acknowledged%")
    ).order_by(AuditLog.id.desc()).first()

    assert audit is not None
    assert audit.user_id == 1
    assert audit.officer_name == "Dr. Vikramaditya Sen"
    assert "Rogue Agent" not in audit.officer_name


# 14. Alert escalation records authenticated officer
def test_alert_escalation_records_authenticated_officer(db):
    headers = _get_auth_headers("state.lea@mp.police.gov.in", "STATE_LEA")
    resp = client.post(
        "/api/v1/alerts/97/escalate",
        json={"notes": "State-level bank freeze request initiated"},
        headers=headers
    )
    assert resp.status_code == 200

    audit = db.query(AuditLog).filter(
        AuditLog.action == "ALERT_ESCALATED",
        AuditLog.details.like("%Alert #97 escalated%")
    ).order_by(AuditLog.id.desc()).first()

    assert audit is not None
    assert audit.user_id == 2
    assert audit.officer_name == "SP Anand Shekhawat, IPS"
    assert audit.role == "STATE_LEA"


# 15. GET /api/v1/auth/me returns authoritative profile
def test_get_me_returns_authoritative_profile():
    headers = _get_auth_headers("analyst@cybershield.gov.in", "ANALYST")
    resp = client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "analyst@cybershield.gov.in"
    assert data["full_name"] == "Pooja Kulkarni"
    assert data["role"] == "ANALYST"
    assert data["badge_number"] == "CS-AN-102"


# 16. Audit Log API response includes user_id
def test_audit_api_returns_user_id():
    resp = client.get("/api/v1/audit")
    assert resp.status_code == 200
    logs = resp.json()
    assert len(logs) > 0
    # Verify user_id field is present in response schema
    assert "user_id" in logs[0]


# 17. Read-only endpoints generate zero fake/mutation audit events
def test_read_only_endpoints_generate_zero_fake_audits(db):
    audit_count_before = db.query(AuditLog).count()

    # GET /complaints/CMP-NEW-000126
    resp1 = client.get("/api/v1/complaints/CMP-NEW-000126")
    assert resp1.status_code == 200

    # GET /complaints/CMP-NEW-000126/graph
    resp2 = client.get("/api/v1/complaints/CMP-NEW-000126/graph")
    assert resp2.status_code == 200

    # GET /predictions/CMP-NEW-000126
    resp3 = client.get("/api/v1/predictions/CMP-NEW-000126")
    assert resp3.status_code == 200

    db.expire_all()
    audit_count_after = db.query(AuditLog).count()
    assert audit_count_after == audit_count_before, "Read-only GET endpoints must not generate mutation audit events!"


# 18. Public endpoints (e.g. /health) remain accessible without JWT
def test_health_remains_public():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["engine"] == "Online"


# 19. Production settings strictly require non-default JWT_SECRET
def test_jwt_secret_environment_enforcement():
    # Production without JWT_SECRET or with default must fail
    with pytest.raises(ValueError, match="Production configuration error: JWT_SECRET"):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET=DEV_ONLY_JWT_SECRET,
            _env_file=None
        )

    with pytest.raises(ValueError, match="Production configuration error: JWT_SECRET"):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET="",
            _env_file=None
        )

    # Production with valid secure secret passes
    prod_settings = Settings(
        ENVIRONMENT="production",
        JWT_SECRET="super-secure-production-random-secret-key-987654321",
        _env_file=None
    )
    assert prod_settings.JWT_SECRET == "super-secure-production-random-secret-key-987654321"


# 20. Preservation of CMP-NEW-000126, Prediction #277, Alert #97, and historical records
def test_cmp_new_000126_and_historical_integrity_preserved(db):
    # Verify CMP-NEW-000126
    comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000126").first()
    assert comp is not None
    assert comp.id == 15561
    assert comp.state == "Delhi"

    # Verify Prediction #277
    pred = db.query(Prediction).filter(Prediction.id == 277).first()
    assert pred is not None
    assert pred.complaint_id == 15561
    assert pred.prediction_mode == "trained_ml"
    assert pred.model_version == "cashout-location-xgb-v3.1"

    # Verify Alert #97
    alert = db.query(Alert).filter(Alert.id == 97).first()
    assert alert is not None
    assert alert.complaint_id == 15561
    assert alert.prediction_id == 277
    assert alert.location_name == "Nehru Place, Delhi"

    # Verify historical audit logs exist
    historical_logs = db.query(AuditLog).filter(AuditLog.id <= 30).count()
    assert historical_logs > 0
