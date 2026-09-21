"""
CyberShield AI — Phase 13 Pillar 3: Unhappy Paths & Fault Recovery Test Suite
Verifies:
1. Outbox Worker Crash & Stale Lease Recovery: Reclaiming crashed worker tasks, exponential backoff, poison-pill max retries.
2. Alert Expiration: Auto-expiration of stale alerts past the operational window.
3. Bank Partner Callback Security: Forged signature (401), timestamp skew (400), replayed callback ID (409), manual hold spoofing (400).
4. Cross-State Handoff Fault Boundaries: Self-acceptance rejection (403), unauthorized cancellation (403), expired deadline (EXPIRED).
5. Evidence Tamper Detection: Disk modification detection, cryptographic SHA-256 mismatch detection (is_valid=False).
6. Outcome Domain Boundary Validation: Negative recovery amount rejection (422).
7. Unsupported Region Refusal: Non-validated region prediction refusal (MODEL_NOT_SUPPORTED_FOR_REGION) with zero fake predictions.
"""

import io
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
    Prediction, Alert, BankAction, EvidenceFile, Organization, NotificationOutbox, CaseHandoff
)
from backend.app.auth.security import create_access_token
from backend.app.services.outbox_service import outbox_service
from backend.app.services.handoff_service import request_case_handoff, accept_case_handoff
from backend.app.services.evidence_service import get_absolute_file_path
from backend.app.adapters.bank_adapter import (
    generate_sandbox_hmac_signature, SANDBOX_SHARED_SECRET
)


@pytest.fixture
def auth_tokens():
    return {
        "admin": {"Authorization": f"Bearer {create_access_token({'sub': 'admin@cybershield.gov.in', 'role': 'I4C_ADMIN'})}"},
        "delhi_lea": {"Authorization": f"Bearer {create_access_token({'sub': 'officer@delhipolice.gov.in', 'role': 'DISTRICT_LEA'})}"},
        "indore_lea": {"Authorization": f"Bearer {create_access_token({'sub': 'district.lea@indore.police.gov.in', 'role': 'DISTRICT_LEA'})}"},
        "bank_officer": {"Authorization": f"Bearer {create_access_token({'sub': 'officer@sbi.co.in', 'role': 'BANK_OFFICER'})}"},
        "auditor": {"Authorization": f"Bearer {create_access_token({'sub': 'auditor@mha.gov.in', 'role': 'AUDITOR'})}"},
    }


@pytest.fixture
def registered_delhi_case(client: TestClient, auth_tokens):
    """Creates an authenticated, properly scoped Delhi complaint with an associated beneficiary account."""
    unique = uuid.uuid4().hex[:6].upper()
    ben_acc = f"SBIN{uuid.uuid4().int % 10000000000:010d}"
    res = client.post(
        "/api/v1/complaints",
        json={
            "fraud_type": "UPI Fraud",
            "amount": 75000.0,
            "victim_name": "Fault Test Complainant",
            "victim_location": "Connaught Place, Central Delhi",
            "locality": "Connaught Place",
            "state": "Delhi",
            "district": "Central Delhi",
            "region_id": "delhi",
            "payment_channel": "UPI",
            "description": "Fault testing operational complaint",
            "transaction_ref": f"UTR-FAULT-{unique}",
            "victim_bank": "State Bank of India",
            "beneficiary_bank": "State Bank of India",
            "beneficiary_account_number": ben_acc,
            "beneficiary_id": ben_acc,
            "ifsc_code": "SBIN0001234",
            "demo_mode": False
        },
        headers=auth_tokens["delhi_lea"]
    )
    assert res.status_code == 200, f"Complaint creation failed: {res.text}"
    return res.json()


# =============================================================================
# 1. Notification Outbox Worker Crash & Stale Lease Recovery
# =============================================================================

def test_outbox_stale_lease_recovery_and_backoff(db_session: Session):
    """
    Verifies that an outbox item locked by a crashed worker whose lease expired is reclaimed,
    increments attempt_count, applies exponential retry backoff on failure,
    and transitions to PERMANENT_FAILURE when max attempts are reached.
    """
    now = datetime.utcnow()
    crashed_worker = f"worker-crashed-{uuid.uuid4().hex[:6]}"
    recovery_worker = f"worker-recovery-{uuid.uuid4().hex[:6]}"

    comp = Complaint(
        complaint_number=f"CMP-FAULT-{uuid.uuid4().hex[:6]}",
        fraud_type="UPI Fraud",
        amount=50000.0,
        victim_location="Connaught Place, Delhi",
        state="Delhi",
        district="Central Delhi",
        region_id="delhi"
    )
    db_session.add(comp)
    db_session.flush()

    alert = Alert(
        complaint_id=comp.id,
        title="Test Lease Failure Alert",
        severity="HIGH",
        location_name="Connaught Place",
        status="NEW"
    )
    db_session.add(alert)
    db_session.flush()

    ev = outbox_service.enqueue_alert_event(db_session, alert, event_type="ALERT_CREATED")
    db_session.commit()

    # Simulate crashed worker: item locked in PROCESSING with expired lease
    ev.status = "PROCESSING"
    ev.worker_id = crashed_worker
    ev.locked_at = now - timedelta(minutes=10)
    ev.lease_expires_at = now - timedelta(minutes=5)
    ev.attempt_count = 1
    db_session.commit()

    # Recovery worker claims pending events
    claimed = outbox_service.claim_pending_events(db_session, worker_id=recovery_worker, limit=10)
    claimed_ids = [item.id for item in claimed]
    assert ev.id in claimed_ids

    reclaimed_ev = db_session.query(NotificationOutbox).filter_by(id=ev.id).first()
    assert reclaimed_ev.worker_id == recovery_worker
    assert reclaimed_ev.status == "PROCESSING"

    # Process with temporary failure
    success = outbox_service.process_event(db_session, reclaimed_ev, simulated_failure="TEMPORARY")
    assert success is False
    assert reclaimed_ev.status == "FAILED"
    assert reclaimed_ev.attempt_count == 2
    assert reclaimed_ev.next_retry_at > now
    assert reclaimed_ev.lease_expires_at is None

    # Exhaust remaining attempts to verify poison pill handling
    for _ in range(reclaimed_ev.max_attempts - reclaimed_ev.attempt_count):
        outbox_service.process_event(db_session, reclaimed_ev, simulated_failure="TEMPORARY")

    assert reclaimed_ev.status == "PERMANENT_FAILURE"
    assert reclaimed_ev.next_retry_at is None


# =============================================================================
# 2. Alert Window Expiration
# =============================================================================

def test_alert_window_expiration(db_session: Session):
    """
    Verifies that active alerts with expires_at in the past automatically expire
    via expire_stale_alerts, enqueuing an ALERT_EXPIRED outbox event.
    """
    now = datetime.utcnow()
    comp = Complaint(
        complaint_number=f"CMP-EXP-{uuid.uuid4().hex[:6]}",
        fraud_type="UPI Fraud",
        amount=40000.0,
        victim_location="Rohini, Delhi",
        state="Delhi",
        district="North West Delhi",
        region_id="delhi"
    )
    db_session.add(comp)
    db_session.flush()

    alert = Alert(
        complaint_id=comp.id,
        title="Stale Test Alert",
        severity="MEDIUM",
        location_name="Rohini Sector 7",
        status="NEW",
        expires_at=now - timedelta(hours=2)
    )
    db_session.add(alert)
    db_session.commit()

    expired = outbox_service.expire_stale_alerts(db_session)
    assert any(a.id == alert.id for a in expired)

    db_session.refresh(alert)
    assert alert.status == "EXPIRED"

    # Verify outbox event enqueued
    ob = db_session.query(NotificationOutbox).filter_by(alert_id=alert.id, event_type="ALERT_EXPIRED").first()
    assert ob is not None


# =============================================================================
# 3. Bank Callback Fault Handling & Replay Protection
# =============================================================================

def test_bank_callback_forgery_replay_and_spoofing(client: TestClient, db_session: Session, auth_tokens, registered_delhi_case):
    """
    Verifies:
    - Forged HMAC signature is rejected with 401.
    - Timestamp skew (>300s) is rejected with 400.
    - Replayed callback ID is rejected with 409.
    - Client manual transition to CONFIRMED_HOLD is rejected with 400.
    """
    case_id = registered_delhi_case["id"]
    now_iso = datetime.now(timezone.utc).isoformat()
    unique_ref = f"ACT-FLT-{uuid.uuid4().hex[:6].upper()}"

    # Setup BankAction in SENT state
    action = BankAction(
        action_reference=unique_ref,
        complaint_id=case_id,
        bank_organization_id=4,
        action_type="FREEZE_ACCOUNT",
        status="SENT",
        environment="SANDBOX",
        requested_amount=50000.0,
        requested_by_user_id=7
    )
    db_session.add(action)
    db_session.commit()

    callback_payload = {
        "action_reference": unique_ref,
        "bank_reference": f"BNK-REF-{uuid.uuid4().hex[:6]}",
        "status": "HELD",
        "held_amount": 50000.0,
        "currency": "INR",
        "timestamp": now_iso
    }
    payload_str = json.dumps(callback_payload, sort_keys=True)
    valid_sig = generate_sandbox_hmac_signature(payload_str, SANDBOX_SHARED_SECRET)

    # 1. Forged Signature -> 401
    forged_resp = client.post(
        "/api/v1/bank-actions/callback",
        json=callback_payload,
        headers={
            "X-Bank-Signature": "forged_invalid_hmac_signature",
            "X-Bank-Timestamp": now_iso,
            "X-Bank-Callback-Id": f"CB-FORGED-{uuid.uuid4().hex[:6]}"
        }
    )
    assert forged_resp.status_code == 401

    # 2. Timestamp Skew (>300s in past) -> 400
    stale_time = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
    stale_resp = client.post(
        "/api/v1/bank-actions/callback",
        json=callback_payload,
        headers={
            "X-Bank-Signature": valid_sig,
            "X-Bank-Timestamp": stale_time,
            "X-Bank-Callback-Id": f"CB-SKEW-{uuid.uuid4().hex[:6]}"
        }
    )
    assert stale_resp.status_code == 400

    # 3. Valid callback succeeds
    cb_id = f"CB-REPLAY-{uuid.uuid4().hex[:6]}"
    valid_resp = client.post(
        "/api/v1/bank-actions/callback",
        json=callback_payload,
        headers={
            "X-Bank-Signature": valid_sig,
            "X-Bank-Timestamp": now_iso,
            "X-Bank-Callback-Id": cb_id
        }
    )
    assert valid_resp.status_code == 200
    assert valid_resp.json()["status"] == "CONFIRMED_HOLD"

    # 4. Replay of same callback ID -> 409
    replay_resp = client.post(
        "/api/v1/bank-actions/callback",
        json=callback_payload,
        headers={
            "X-Bank-Signature": valid_sig,
            "X-Bank-Timestamp": now_iso,
            "X-Bank-Callback-Id": cb_id
        }
    )
    assert replay_resp.status_code == 409

    # 5. Client manual status transition to CONFIRMED_HOLD blocked -> 400
    spoof_action = BankAction(
        action_reference=f"ACT-SPOOF-{uuid.uuid4().hex[:6].upper()}",
        complaint_id=case_id,
        bank_organization_id=4,
        action_type="FREEZE_ACCOUNT",
        status="SENT",
        environment="SANDBOX",
        requested_amount=25000.0,
        requested_by_user_id=7
    )
    db_session.add(spoof_action)
    db_session.commit()

    manual_resp = client.post(
        f"/api/v1/bank-actions/{spoof_action.id}/transition",
        json={"target_status": "CONFIRMED_HOLD", "notes": "Spoofed confirmation attempt"},
        headers=auth_tokens["admin"]
    )
    assert manual_resp.status_code == 400


# =============================================================================
# 4. Cross-State Handoff Fault Boundaries
# =============================================================================

def test_cross_state_handoff_fault_rules(client: TestClient, db_session: Session, auth_tokens, registered_delhi_case):
    """
    Verifies:
    - Origin officer cannot accept its own handoff (403).
    - Destination officer cannot cancel an initiated handoff (403).
    - Expired acknowledgement window results in refusal (EXPIRED).
    """
    case_id = registered_delhi_case["id"]
    delhi_user = db_session.query(User).filter_by(id=7).first()  # Delhi LEA
    handoff = request_case_handoff(
        db=db_session,
        complaint_id=case_id,
        target_state="Madhya Pradesh",
        target_district="Indore",
        destination_organization_id=3,
        purpose="Fault test handoff",
        evidence_scope="FULL_CASE",
        initiator_user=delhi_user,
        acknowledgement_hours=24
    )
    db_session.commit()

    # 1. Delhi LEA tries to accept its own handoff -> 403 Forbidden
    self_accept_resp = client.post(f"/api/v1/handoffs/{handoff.id}/accept", headers=auth_tokens["delhi_lea"])
    assert self_accept_resp.status_code == 403

    # 2. Indore LEA tries to cancel the handoff -> 403 Forbidden
    cancel_resp = client.post(
        f"/api/v1/handoffs/{handoff.id}/cancel",
        json={"cancellation_reason": "Unauthorized attempt by recipient"},
        headers=auth_tokens["indore_lea"]
    )
    assert cancel_resp.status_code == 403

    # 3. Simulate expired acknowledgement deadline
    handoff.acknowledgement_deadline = datetime.utcnow() - timedelta(hours=1)
    db_session.commit()

    expired_accept_resp = client.post(f"/api/v1/handoffs/{handoff.id}/accept", headers=auth_tokens["indore_lea"])
    assert expired_accept_resp.status_code == 400
    assert "expired" in expired_accept_resp.text.lower()


# =============================================================================
# 5. Evidence Tampering Detection
# =============================================================================

def test_evidence_tampering_detection(client: TestClient, db_session: Session, auth_tokens, registered_delhi_case):
    """
    Verifies that modifying evidence file bytes directly on disk is detected
    by verify_evidence_integrity, returning is_valid=False and hash mismatch.
    """
    case_id = registered_delhi_case["id"]
    content = b"ORIGINAL CERTIFIED POLICE EVIDENCE RECORD CONTENT"
    files = {"file": ("case_log.txt", io.BytesIO(content), "text/plain")}
    data = {"source": "POLICE_REPORT", "description": "Tamper test evidence"}

    upload_resp = client.post(f"/api/v1/complaints/{case_id}/evidence", files=files, data=data, headers=auth_tokens["delhi_lea"])
    assert upload_resp.status_code == 201
    ev_id = upload_resp.json()["id"]

    # Initial integrity check -> valid
    check1 = client.get(f"/api/v1/complaints/{case_id}/evidence/{ev_id}/integrity", headers=auth_tokens["delhi_lea"])
    assert check1.status_code == 200
    assert check1.json()["is_valid"] is True

    # Tamper: overwrite file content on disk
    ev_record = db_session.query(EvidenceFile).filter_by(id=ev_id).first()
    abs_path = get_absolute_file_path(ev_record.storage_key)
    with open(abs_path, "wb") as f:
        f.write(b"TAMPERED CORRUPTED FORGED RECORD CONTENT")

    # Second integrity check -> detects tampering
    check2 = client.get(f"/api/v1/complaints/{case_id}/evidence/{ev_id}/integrity", headers=auth_tokens["delhi_lea"])
    assert check2.status_code == 200
    assert check2.json()["is_valid"] is False
    assert check2.json()["stored_hash"] != check2.json()["computed_hash"]


# =============================================================================
# 6. Case Outcome Domain Boundary Validation
# =============================================================================

def test_case_outcome_negative_amount_rejected(client: TestClient, auth_tokens, registered_delhi_case):
    """
    Verifies that negative recovery amounts are rejected by Pydantic validation (422).
    """
    case_id = registered_delhi_case["id"]
    payload = {
        "outcome_type": "CONFIRMED_CASHOUT",
        "source": "OFFICER_MANUAL",
        "observed_event_time": datetime.utcnow().isoformat() + "Z",
        "actual_recovered_amount_inr": -50000.0,
        "notes": "Negative amount test"
    }
    resp = client.post(f"/api/v1/outcomes/complaints/{case_id}", json=payload, headers=auth_tokens["delhi_lea"])
    assert resp.status_code in (400, 422)


# =============================================================================
# 7. Unsupported Region Refusal (Zero Fake Predictions / Silent Fallback)
# =============================================================================

def test_unsupported_region_strict_refusal(client: TestClient, db_session: Session, auth_tokens):
    """
    Verifies that requesting prediction on a complaint in an unvalidated region (e.g. Mumbai MMR)
    is strictly refused with MODEL_NOT_SUPPORTED_FOR_REGION, returning 0 candidate locations
    and refusing silent Delhi fallback.
    """
    comp_payload = {
        "fraud_type": "Investment Scam",
        "amount": 250000.0,
        "victim_name": "Rajesh Merchant",
        "victim_location": "Bandra Kurla Complex, Mumbai",
        "locality": "Bandra Kurla Complex",
        "state": "Maharashtra",
        "district": "MUMBAI",
        "region_id": "mumbai_mmr",
        "payment_channel": "Net Banking",
        "description": "Cross-region unvalidated Mumbai complaint"
    }

    reg_resp = client.post("/api/v1/complaints", json=comp_payload, headers=auth_tokens["admin"])
    assert reg_resp.status_code == 200
    comp_number = reg_resp.json()["complaint_number"]
    assert reg_resp.json()["region_id"] == "mumbai_mmr"

    # Run prediction -> Must refuse inference
    pred_resp = client.post(f"/api/v1/predictions/{comp_number}", headers=auth_tokens["admin"])
    assert pred_resp.status_code == 200
    pred_data = pred_resp.json()

    assert pred_data["status"] == "MODEL_NOT_SUPPORTED_FOR_REGION"
    assert pred_data["prediction_mode"] == "unsupported_region"
    assert pred_data["region_id"] == "mumbai_mmr"
    assert pred_data["candidate_pool_size"] == 0
    assert len(pred_data["top_locations"]) == 0
    assert "strictly calibrated for Delhi Pilot" in pred_data["refusal_reason"]
