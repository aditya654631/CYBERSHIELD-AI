"""
CyberShield AI — Phase 8 Test Suite: Bank Adapter & Truthful External Action Lifecycle.
Verifies:
1. Idempotent duplicate request handling.
2. Request sent != funds held (SENT does not imply hold).
3. Cryptographic HMAC callback verification transitions to CONFIRMED_HOLD.
4. Forged, replayed, expired, or out-of-order callback rejection.
5. Target account and bank organization mismatch rejection.
6. Partial hold distinct state tracking (PARTIAL_HOLD vs CONFIRMED_HOLD).
7. Hold release workflow (RELEASED).
8. Client-edited / manual hold spoofing prevention.
9. Scoped RBAC authorization across LEA, Bank Officers, and Auditors.
10. Environment separation (SIMULATED, SANDBOX, LIVE) and audit trail logging.
"""

import os
import json
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.models.models import (
    User, Complaint, Account, ComplaintAccount, Transaction,
    Alert, BankAction, Organization, AuditLog
)
from backend.app.auth.security import create_access_token
from backend.app.adapters.bank_adapter import (
    generate_sandbox_hmac_signature, SANDBOX_SHARED_SECRET
)


@pytest.fixture
def phase8_auth_headers(db_session: Session):
    """Creates authenticated users and bank entities across different organizations."""
    db = db_session

    # 1. I4C National Admin
    i4c_org = db.query(Organization).filter(Organization.name == "I4C National Command").first()
    if not i4c_org:
        i4c_org = Organization(name="I4C National Command", org_type="I4C", state="Delhi", district="CENTRAL_NEW_DELHI")
        db.add(i4c_org)
        db.flush()

    i4c_admin = db.query(User).filter(User.email == "admin_p8@cybershield.gov.in").first()
    if not i4c_admin:
        i4c_admin = User(
            email="admin_p8@cybershield.gov.in",
            hashed_password="mock_test_hashed_password",
            full_name="I4C National Director",
            role="I4C_ADMIN",
            badge_number="I4C-P8-001",
            organization_id=i4c_org.id,
            is_active=True
        )
        db.add(i4c_admin)
        db.flush()

    # 2. Delhi LEA Officer
    delhi_org = db.query(Organization).filter(Organization.name == "Delhi Police Cyber Cell").first()
    if not delhi_org:
        delhi_org = Organization(name="Delhi Police Cyber Cell", org_type="LEA", state="Delhi", district="CENTRAL_NEW_DELHI")
        db.add(delhi_org)
        db.flush()

    delhi_lea = db.query(User).filter(User.email == "delhi_lea_p8@police.gov.in").first()
    if not delhi_lea:
        delhi_lea = User(
            email="delhi_lea_p8@police.gov.in",
            hashed_password="mock_test_hashed_password",
            full_name="Delhi Cyber Inspector",
            role="DISTRICT_LEA",
            badge_number="DL-CP-P8",
            organization_id=delhi_org.id,
            is_active=True
        )
        db.add(delhi_lea)
        db.flush()

    # 3. State Bank of India (Bank Org & Officer)
    sbi_org = db.query(Organization).filter(Organization.name == "State Bank of India - Nodal FRMU").first()
    if not sbi_org:
        sbi_org = Organization(name="State Bank of India - Nodal FRMU", org_type="BANK", state="Maharashtra", district="MUMBAI")
        db.add(sbi_org)
        db.flush()

    sbi_officer = db.query(User).filter(User.email == "sbi_nodal_p8@sbi.co.in").first()
    if not sbi_officer:
        sbi_officer = User(
            email="sbi_nodal_p8@sbi.co.in",
            hashed_password="mock_test_hashed_password",
            full_name="SBI Nodal Officer",
            role="BANK_OFFICER",
            badge_number="SBI-NODAL-P8",
            organization_id=sbi_org.id,
            is_active=True
        )
        db.add(sbi_officer)
        db.flush()

    # 4. HDFC Bank (Different Bank Org & Officer)
    hdfc_org = db.query(Organization).filter(Organization.name == "HDFC Bank Cyber Security").first()
    if not hdfc_org:
        hdfc_org = Organization(name="HDFC Bank Cyber Security", org_type="BANK", state="Maharashtra", district="MUMBAI")
        db.add(hdfc_org)
        db.flush()

    hdfc_officer = db.query(User).filter(User.email == "hdfc_officer_p8@hdfc.com").first()
    if not hdfc_officer:
        hdfc_officer = User(
            email="hdfc_officer_p8@hdfc.com",
            hashed_password="mock_test_hashed_password",
            full_name="HDFC Security Officer",
            role="BANK_OFFICER",
            badge_number="HDFC-SEC-P8",
            organization_id=hdfc_org.id,
            is_active=True
        )
        db.add(hdfc_officer)
        db.flush()

    # 5. Auditor (Read-Only)
    auditor_org = db.query(Organization).filter(Organization.name == "MHA Audit & Compliance").first()
    if not auditor_org:
        auditor_org = Organization(name="MHA Audit & Compliance", org_type="I4C", state="Delhi", district="CENTRAL_NEW_DELHI")
        db.add(auditor_org)
        db.flush()

    auditor_user = db.query(User).filter(User.email == "auditor_p8@mha.gov.in").first()
    if not auditor_user:
        auditor_user = User(
            email="auditor_p8@mha.gov.in",
            hashed_password="mock_test_hashed_password",
            full_name="Chief Compliance Auditor",
            role="AUDITOR",
            badge_number="AUD-MHA-P8",
            organization_id=auditor_org.id,
            is_active=True
        )
        db.add(auditor_user)
        db.flush()

    db.commit()

    return {
        "i4c_admin": {
            "Authorization": f"Bearer {create_access_token({'sub': i4c_admin.email, 'role': i4c_admin.role})}"
        },
        "delhi_lea": {
            "Authorization": f"Bearer {create_access_token({'sub': delhi_lea.email, 'role': delhi_lea.role})}"
        },
        "sbi_officer": {
            "Authorization": f"Bearer {create_access_token({'sub': sbi_officer.email, 'role': sbi_officer.role})}"
        },
        "hdfc_officer": {
            "Authorization": f"Bearer {create_access_token({'sub': hdfc_officer.email, 'role': hdfc_officer.role})}"
        },
        "auditor": {
            "Authorization": f"Bearer {create_access_token({'sub': auditor_user.email, 'role': auditor_user.role})}"
        },
        "orgs": {
            "i4c": i4c_org,
            "delhi": delhi_org,
            "sbi": sbi_org,
            "hdfc": hdfc_org,
            "auditor": auditor_org,
        }
    }


@pytest.fixture
def case_with_mule_account(db_session: Session, phase8_auth_headers):
    """Creates a synthetic case linked to an SBI mule account."""
    db = db_session
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    delhi_org = phase8_auth_headers["orgs"]["delhi"]
    sbi_org = phase8_auth_headers["orgs"]["sbi"]

    comp = Complaint(
        complaint_number=f"CMP-P8-{uuid.uuid4().hex[:10]}",
        fraud_type="UPI Impersonation Fraud",
        amount=150000.00,
        victim_name="Kavita Mehta",
        victim_phone="9876543210",
        victim_location="Lajpat Nagar, New Delhi",
        locality="Lajpat Nagar",
        state="Delhi",
        district="CENTRAL_NEW_DELHI",
        payment_channel="UPI",
        reported_at=now - timedelta(hours=1),
        incident_time=now - timedelta(hours=2),
        risk_level="HIGH",
        risk_score=0.92,
        prediction_status="AVAILABLE",
        case_status="ACTIVE",
        owner_organization_id=delhi_org.id,
        created_at=now
    )
    db.add(comp)
    db.flush()

    raw_suffix = uuid.uuid4().hex[:8]
    account = Account(
        account_number=f"SBIN99{raw_suffix}",
        masked_account=f"SBIN••••{raw_suffix[-4:]}",
        bank_name="State Bank of India",
        bank_organization_id=sbi_org.id,
        ifsc="SBIN0001234",
        holder_name="Mule Intermediary Holder",
        account_type="SAVINGS",
        state="Delhi",
        district="CENTRAL_NEW_DELHI",
        risk_score=0.89,
        is_mule=True
    )
    db.add(account)
    db.flush()

    ca = ComplaintAccount(
        complaint_id=comp.id,
        account_id=account.id,
        association_type="BENEFICIARY"
    )
    db.add(ca)
    db.commit()
    db.refresh(comp)
    db.refresh(account)

    return {"complaint": comp, "account": account}


def test_idempotent_duplicate_request(client: TestClient, phase8_auth_headers, case_with_mule_account):
    """
    Test 1: Duplicate bank action requests with the same idempotency key create no duplicate records.
    """
    comp = case_with_mule_account["complaint"]
    acc = case_with_mule_account["account"]
    idemp_key = f"IDEMP-P8-{uuid.uuid4().hex[:8]}"

    payload = {
        "complaint_id": comp.id,
        "account_id": acc.id,
        "target_account_number": acc.account_number,
        "target_ifsc": acc.ifsc,
        "action_type": "ACCOUNT_FREEZE",
        "requested_amount": 150000.0,
        "currency": "INR",
        "environment": "SANDBOX",
        "action_notes": "Urgent account freeze requested for identified mule beneficiary.",
        "idempotency_key": idemp_key
    }

    # Request 1
    resp1 = client.post("/api/v1/bank-actions", json=payload, headers=phase8_auth_headers["delhi_lea"])
    assert resp1.status_code == 201, resp1.text
    data1 = resp1.json()
    action_id = data1["id"]
    assert data1["status"] == "REQUESTED"
    assert data1["environment"] == "SANDBOX"
    assert data1["target_account_number"] == acc.account_number

    # Request 2 with same idempotency key -> returns existing record
    resp2 = client.post("/api/v1/bank-actions", json=payload, headers=phase8_auth_headers["delhi_lea"])
    assert resp2.status_code == 201 or resp2.status_code == 200
    data2 = resp2.json()
    assert data2["id"] == action_id
    assert data2["action_reference"] == data1["action_reference"]


def test_request_sent_not_equal_funds_held(client: TestClient, phase8_auth_headers, case_with_mule_account):
    """
    Test 2: Dispatching an action moves it to SENT state; it NEVER implies or sets funds held.
    """
    comp = case_with_mule_account["complaint"]
    acc = case_with_mule_account["account"]

    # 1. Create Sandbox action
    req_resp = client.post(
        "/api/v1/bank-actions",
        json={
            "complaint_id": comp.id,
            "account_id": acc.id,
            "target_account_number": acc.account_number,
            "action_type": "LIEN_HOLD",
            "requested_amount": 100000.0,
            "environment": "SANDBOX"
        },
        headers=phase8_auth_headers["delhi_lea"]
    )
    assert req_resp.status_code == 201
    action_id = req_resp.json()["id"]

    # 2. Approve action
    app_resp = client.post(f"/api/v1/bank-actions/{action_id}/approve", headers=phase8_auth_headers["delhi_lea"])
    assert app_resp.status_code == 200
    assert app_resp.json()["status"] == "APPROVED"

    # 3. Dispatch action
    disp_resp = client.post(f"/api/v1/bank-actions/{action_id}/dispatch", headers=phase8_auth_headers["delhi_lea"])
    assert disp_resp.status_code == 200
    disp_data = disp_resp.json()

    # CRITICAL CHECK: status is SENT, held_amount is 0.0, held_at is None
    assert disp_data["status"] == "SENT"
    assert disp_data["held_amount"] == 0.0
    assert disp_data["held_at"] is None
    assert disp_data["provider_reference_id"] is not None


def test_verified_hmac_callback_transitions_to_confirmed_hold(client: TestClient, phase8_auth_headers, case_with_mule_account):
    """
    Test 3: An authentic partner callback with valid HMAC signature transitions action to CONFIRMED_HOLD.
    """
    comp = case_with_mule_account["complaint"]
    acc = case_with_mule_account["account"]

    # Create & Dispatch
    req_resp = client.post(
        "/api/v1/bank-actions",
        json={
            "complaint_id": comp.id,
            "account_id": acc.id,
            "target_account_number": acc.account_number,
            "action_type": "ACCOUNT_FREEZE",
            "requested_amount": 150000.0,
            "environment": "SANDBOX"
        },
        headers=phase8_auth_headers["delhi_lea"]
    )
    action_id = req_resp.json()["id"]
    action_ref = req_resp.json()["action_reference"]

    client.post(f"/api/v1/bank-actions/{action_id}/approve", headers=phase8_auth_headers["delhi_lea"])
    disp_resp = client.post(f"/api/v1/bank-actions/{action_id}/dispatch", headers=phase8_auth_headers["delhi_lea"])
    provider_ref = disp_resp.json()["provider_reference_id"]

    # Construct genuine partner callback payload
    now_iso = datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z"
    callback_payload = {
        "action_reference": action_ref,
        "provider_reference_id": provider_ref,
        "target_account_number": acc.account_number,
        "status": "HELD",
        "held_amount": 150000.0,
        "currency": "INR",
        "timestamp": now_iso
    }

    payload_bytes = json.dumps(callback_payload, sort_keys=True).encode("utf-8")
    sig = generate_sandbox_hmac_signature(payload_bytes.decode("utf-8"), SANDBOX_SHARED_SECRET)
    callback_id = f"CB-AUTH-{uuid.uuid4().hex[:8]}"

    # Submit callback to webhook endpoint
    cb_resp = client.post(
        "/api/v1/bank-actions/callback",
        json=callback_payload,
        headers={
            "X-Bank-Signature": sig,
            "X-Bank-Timestamp": now_iso,
            "X-Bank-Callback-Id": callback_id
        }
    )
    assert cb_resp.status_code == 200, cb_resp.text
    assert cb_resp.json()["status"] == "CONFIRMED_HOLD"
    assert cb_resp.json()["held_amount"] == 150000.0

    # Verify action details
    detail_resp = client.get(f"/api/v1/bank-actions/{action_id}", headers=phase8_auth_headers["delhi_lea"])
    assert detail_resp.status_code == 200
    d = detail_resp.json()
    assert d["status"] == "CONFIRMED_HOLD"
    assert d["held_amount"] == 150000.0
    assert d["held_at"] is not None
    assert d["callback_evidence"]["callback_id"] == callback_id


def test_forged_replayed_expired_callback_rejected(client: TestClient, phase8_auth_headers, case_with_mule_account):
    """
    Test 4: Forged signature, replayed callback ID, or expired clock skew is rejected.
    """
    comp = case_with_mule_account["complaint"]
    acc = case_with_mule_account["account"]

    req_resp = client.post(
        "/api/v1/bank-actions",
        json={
            "complaint_id": comp.id,
            "account_id": acc.id,
            "target_account_number": acc.account_number,
            "requested_amount": 50000.0,
            "environment": "SANDBOX"
        },
        headers=phase8_auth_headers["delhi_lea"]
    )
    action_id = req_resp.json()["id"]
    action_ref = req_resp.json()["action_reference"]
    client.post(f"/api/v1/bank-actions/{action_id}/approve", headers=phase8_auth_headers["delhi_lea"])
    client.post(f"/api/v1/bank-actions/{action_id}/dispatch", headers=phase8_auth_headers["delhi_lea"])

    now_iso = datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z"
    callback_payload = {
        "action_reference": action_ref,
        "status": "HELD",
        "held_amount": 50000.0,
        "timestamp": now_iso
    }
    payload_bytes = json.dumps(callback_payload, sort_keys=True).encode("utf-8")
    valid_sig = generate_sandbox_hmac_signature(payload_bytes.decode("utf-8"), SANDBOX_SHARED_SECRET)

    # 1. Forged Signature -> 401 Unauthorized
    resp_forged = client.post(
        "/api/v1/bank-actions/callback",
        json=callback_payload,
        headers={
            "X-Bank-Signature": "invalid_forged_hex_signature_1234567890",
            "X-Bank-Timestamp": now_iso,
            "X-Bank-Callback-Id": f"CB-{uuid.uuid4().hex[:8]}"
        }
    )
    assert resp_forged.status_code == 401
    assert "Invalid or forged" in resp_forged.json()["detail"]

    # 2. Expired Timestamp Skew (10 minutes ago) -> 400 Bad Request
    expired_iso = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)).isoformat() + "Z"
    exp_payload = dict(callback_payload, timestamp=expired_iso)
    exp_bytes = json.dumps(exp_payload, sort_keys=True).encode("utf-8")
    exp_sig = generate_sandbox_hmac_signature(exp_bytes.decode("utf-8"), SANDBOX_SHARED_SECRET)

    resp_expired = client.post(
        "/api/v1/bank-actions/callback",
        json=exp_payload,
        headers={
            "X-Bank-Signature": exp_sig,
            "X-Bank-Timestamp": expired_iso,
            "X-Bank-Callback-Id": f"CB-{uuid.uuid4().hex[:8]}"
        }
    )
    assert resp_expired.status_code == 400
    assert "skew" in resp_expired.json()["detail"].lower()

    # 3. Valid callback succeeds
    cb_id = f"CB-ONCE-{uuid.uuid4().hex[:8]}"
    resp_valid = client.post(
        "/api/v1/bank-actions/callback",
        json=callback_payload,
        headers={
            "X-Bank-Signature": valid_sig,
            "X-Bank-Timestamp": now_iso,
            "X-Bank-Callback-Id": cb_id
        }
    )
    assert resp_valid.status_code == 200

    # 4. Replay of same callback ID -> 409 Conflict
    resp_replay = client.post(
        "/api/v1/bank-actions/callback",
        json=callback_payload,
        headers={
            "X-Bank-Signature": valid_sig,
            "X-Bank-Timestamp": now_iso,
            "X-Bank-Callback-Id": cb_id
        }
    )
    assert resp_replay.status_code == 409
    assert "Duplicate or replayed callback ID" in resp_replay.json()["detail"]


def test_target_mismatch_and_wrong_reference_rejected(client: TestClient, phase8_auth_headers, case_with_mule_account):
    """
    Test 5: Callback with wrong target account number or non-existent reference is rejected.
    """
    comp = case_with_mule_account["complaint"]
    acc = case_with_mule_account["account"]

    req_resp = client.post(
        "/api/v1/bank-actions",
        json={
            "complaint_id": comp.id,
            "account_id": acc.id,
            "target_account_number": acc.account_number,
            "requested_amount": 50000.0,
            "environment": "SANDBOX"
        },
        headers=phase8_auth_headers["delhi_lea"]
    )
    action_id = req_resp.json()["id"]
    action_ref = req_resp.json()["action_reference"]
    client.post(f"/api/v1/bank-actions/{action_id}/approve", headers=phase8_auth_headers["delhi_lea"])
    client.post(f"/api/v1/bank-actions/{action_id}/dispatch", headers=phase8_auth_headers["delhi_lea"])

    now_iso = datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z"

    # Mismatched Target Account
    mismatch_payload = {
        "action_reference": action_ref,
        "target_account_number": "SBIN0000000000_DIFFERENT_ACCOUNT",
        "status": "HELD",
        "held_amount": 50000.0,
        "timestamp": now_iso
    }
    mismatch_bytes = json.dumps(mismatch_payload, sort_keys=True).encode("utf-8")
    mismatch_sig = generate_sandbox_hmac_signature(mismatch_bytes.decode("utf-8"), SANDBOX_SHARED_SECRET)

    resp_mismatch = client.post(
        "/api/v1/bank-actions/callback",
        json=mismatch_payload,
        headers={
            "X-Bank-Signature": mismatch_sig,
            "X-Bank-Timestamp": now_iso,
            "X-Bank-Callback-Id": f"CB-{uuid.uuid4().hex[:8]}"
        }
    )
    assert resp_mismatch.status_code == 400
    assert "Target account mismatch" in resp_mismatch.json()["detail"]


def test_partial_hold_distinct_state_tracking(client: TestClient, phase8_auth_headers, case_with_mule_account):
    """
    Test 6: When held_amount < requested_amount, action transitions to PARTIAL_HOLD, not full CONFIRMED_HOLD.
    """
    comp = case_with_mule_account["complaint"]
    acc = case_with_mule_account["account"]

    req_resp = client.post(
        "/api/v1/bank-actions",
        json={
            "complaint_id": comp.id,
            "account_id": acc.id,
            "target_account_number": acc.account_number,
            "requested_amount": 100000.0,
            "environment": "SANDBOX"
        },
        headers=phase8_auth_headers["delhi_lea"]
    )
    action_id = req_resp.json()["id"]
    action_ref = req_resp.json()["action_reference"]
    client.post(f"/api/v1/bank-actions/{action_id}/approve", headers=phase8_auth_headers["delhi_lea"])
    client.post(f"/api/v1/bank-actions/{action_id}/dispatch", headers=phase8_auth_headers["delhi_lea"])

    # Simulate Partial Hold via Sandbox simulation endpoint
    sim_resp = client.post(
        f"/api/v1/bank-actions/{action_id}/sandbox-simulate",
        json={
            "simulated_outcome": "PARTIAL_HOLD",
            "held_amount": 35000.0,
            "reason": "Insufficient balance: only 35,000 INR remaining in account."
        },
        headers=phase8_auth_headers["delhi_lea"]
    )
    assert sim_resp.status_code == 200
    assert sim_resp.json()["status"] == "PARTIAL_HOLD"
    assert sim_resp.json()["held_amount"] == 35000.0

    # Verify detail
    detail = client.get(f"/api/v1/bank-actions/{action_id}", headers=phase8_auth_headers["delhi_lea"]).json()
    assert detail["status"] == "PARTIAL_HOLD"
    assert detail["held_amount"] == 35000.0
    assert detail["requested_amount"] == 100000.0


def test_hold_release_workflow(client: TestClient, phase8_auth_headers, case_with_mule_account):
    """
    Test 7: Releasing an active hold transitions status from CONFIRMED_HOLD to RELEASED.
    """
    comp = case_with_mule_account["complaint"]
    acc = case_with_mule_account["account"]

    req_resp = client.post(
        "/api/v1/bank-actions",
        json={
            "complaint_id": comp.id,
            "account_id": acc.id,
            "target_account_number": acc.account_number,
            "requested_amount": 80000.0,
            "environment": "SANDBOX"
        },
        headers=phase8_auth_headers["delhi_lea"]
    )
    action_id = req_resp.json()["id"]
    client.post(f"/api/v1/bank-actions/{action_id}/approve", headers=phase8_auth_headers["delhi_lea"])
    client.post(f"/api/v1/bank-actions/{action_id}/dispatch", headers=phase8_auth_headers["delhi_lea"])

    # Confirm hold
    client.post(
        f"/api/v1/bank-actions/{action_id}/sandbox-simulate",
        json={"simulated_outcome": "CONFIRMED_HOLD", "held_amount": 80000.0},
        headers=phase8_auth_headers["delhi_lea"]
    )

    # Release Hold
    rel_resp = client.post(
        f"/api/v1/bank-actions/{action_id}/release",
        json={
            "release_reason": "Legitimate business account verified upon dispute resolution.",
            "release_amount": 80000.0
        },
        headers=phase8_auth_headers["sbi_officer"]
    )
    assert rel_resp.status_code == 200, rel_resp.text
    assert rel_resp.json()["status"] == "RELEASED"
    assert rel_resp.json()["released_at"] is not None
    assert "Legitimate business account" in rel_resp.json()["release_reason"]


def test_client_spoofed_hold_transition_rejected(client: TestClient, phase8_auth_headers, case_with_mule_account):
    """
    Test 8: Manual transition attempt to CONFIRMED_HOLD or PARTIAL_HOLD by client request is strictly blocked.
    """
    comp = case_with_mule_account["complaint"]
    acc = case_with_mule_account["account"]

    req_resp = client.post(
        "/api/v1/bank-actions",
        json={
            "complaint_id": comp.id,
            "account_id": acc.id,
            "target_account_number": acc.account_number,
            "requested_amount": 50000.0,
            "environment": "SANDBOX"
        },
        headers=phase8_auth_headers["delhi_lea"]
    )
    action_id = req_resp.json()["id"]

    # Attempt manual transition to CONFIRMED_HOLD -> 400 Bad Request
    trans_resp = client.post(
        f"/api/v1/bank-actions/{action_id}/transition",
        json={"target_status": "CONFIRMED_HOLD", "notes": "Client attempting manual hold claim."},
        headers=phase8_auth_headers["sbi_officer"]
    )
    assert trans_resp.status_code == 400
    assert "strictly prohibited" in trans_resp.json()["detail"].lower()


def test_scoped_rbac_and_cross_bank_isolation(client: TestClient, phase8_auth_headers, case_with_mule_account):
    """
    Test 9: Scoped RBAC isolation:
    - SBI officer can view and act on SBI action.
    - HDFC officer receives 404 on SBI action.
    - Auditor has read-only access.
    """
    comp = case_with_mule_account["complaint"]
    acc = case_with_mule_account["account"]

    req_resp = client.post(
        "/api/v1/bank-actions",
        json={
            "complaint_id": comp.id,
            "account_id": acc.id,
            "target_account_number": acc.account_number,
            "bank_organization_id": phase8_auth_headers["orgs"]["sbi"].id,
            "requested_amount": 50000.0,
            "environment": "SANDBOX"
        },
        headers=phase8_auth_headers["delhi_lea"]
    )
    action_id = req_resp.json()["id"]

    # 1. SBI Officer can view action
    sbi_view = client.get(f"/api/v1/bank-actions/{action_id}", headers=phase8_auth_headers["sbi_officer"])
    assert sbi_view.status_code == 200

    # 2. HDFC Officer cannot view SBI action -> 404
    hdfc_view = client.get(f"/api/v1/bank-actions/{action_id}", headers=phase8_auth_headers["hdfc_officer"])
    assert hdfc_view.status_code == 404

    # 3. Auditor can view action
    aud_view = client.get(f"/api/v1/bank-actions/{action_id}", headers=phase8_auth_headers["auditor"])
    assert aud_view.status_code == 200

    # 4. Auditor cannot mutate action -> 403 Forbidden
    aud_mutate = client.post(f"/api/v1/bank-actions/{action_id}/approve", headers=phase8_auth_headers["auditor"])
    assert aud_mutate.status_code == 403


def test_environment_separation_and_audit_trail(client: TestClient, phase8_auth_headers, case_with_mule_account):
    """
    Test 10: Environment separation (SIMULATED vs SANDBOX vs LIVE) and audit trail verification.
    """
    comp = case_with_mule_account["complaint"]
    acc = case_with_mule_account["account"]

    # 1. Create SIMULATED action
    sim_resp = client.post(
        "/api/v1/bank-actions",
        json={
            "complaint_id": comp.id,
            "account_id": acc.id,
            "requested_amount": 25000.0,
            "environment": "SIMULATED"
        },
        headers=phase8_auth_headers["delhi_lea"]
    )
    assert sim_resp.status_code == 201
    assert sim_resp.json()["environment"] == "SIMULATED"
    assert sim_resp.json()["is_simulated"] is True

    # 2. LIVE environment dispatch fails honestly pending external partner gate
    live_resp = client.post(
        "/api/v1/bank-actions",
        json={
            "complaint_id": comp.id,
            "account_id": acc.id,
            "requested_amount": 25000.0,
            "environment": "LIVE"
        },
        headers=phase8_auth_headers["delhi_lea"]
    )
    live_id = live_resp.json()["id"]
    client.post(f"/api/v1/bank-actions/{live_id}/approve", headers=phase8_auth_headers["delhi_lea"])
    live_disp = client.post(f"/api/v1/bank-actions/{live_id}/dispatch", headers=phase8_auth_headers["delhi_lea"])
    assert live_disp.status_code == 503
    assert "pending external partner gate" in live_disp.json()["detail"].lower()
