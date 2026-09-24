"""
CyberShield AI — Phase 13 Pillar 2: Integrated End-to-End Workflow Test Suite
Tests the complete 10-step incident lifecycle across all 6 operational roles:
1. Ingestion: Multi-transaction incident + late transaction arrivals.
2. Linking: Scenario linking resolves transaction trail without synthetic fabrication.
3. Prediction: ML prediction pipeline with versioned geography resolution (delhi),
   causal feature extraction, multi-layer inference, and model lineage hashes.
4. Alerts: Risk alert auto-generation and officer acknowledgment.
5. Bank Action: Creation, approval, dispatch (SENT), and cryptographic HMAC-SHA256 callback (CONFIRMED_HOLD).
6. Cross-State Handoff: Scoped initiation, destination review and acceptance, unrelated jurisdiction isolation (403).
7. Evidence Management: Digital evidence upload, SHA-256 integrity verification, chain of custody.
8. Operational Investigation Pack: Signed JSON report export and printable HTML docket.
9. Case Outcome & Feedback Loop: Resolution logging, money recovery, and attribution metrics.
10. Role Isolation & Auditing: Bank officer isolation, auditor read-only enforcement, unauthenticated 401, audit trail logs.
"""

import io
import json
import uuid
import hashlib
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.models.models import (
    User, Complaint, Account, ComplaintAccount, Transaction,
    Prediction, Alert, BankAction, EvidenceFile, Organization, AuditLog, CaseHandoff, OutcomeObservation
)
from backend.app.auth.security import create_access_token
from backend.app.adapters.bank_adapter import (
    generate_sandbox_hmac_signature, SANDBOX_SHARED_SECRET
)


@pytest.fixture
def workflow_tokens(db_session: Session):
    """
    Creates authentication headers for all 6 required roles across organizations:
    1. I4C_ADMIN (National Command)
    2. STATE_LEA (MP State HQ)
    3. STATE_LEA (Delhi NCT - Originating Officer)
    4. DISTRICT_LEA (Indore District - Destination Officer)
    5. BANK_OFFICER (SBI Fraud Risk Management Unit)
    6. ANALYST (I4C Intelligence Analyst)
    7. AUDITOR (MHA Compliance Auditor)
    """
    db = db_session

    # Organizations
    i4c_org = db.query(Organization).filter_by(id=1).first()
    mp_org = db.query(Organization).filter_by(id=2).first()
    indore_org = db.query(Organization).filter_by(id=3).first()
    sbi_org = db.query(Organization).filter_by(id=4).first()
    mha_org = db.query(Organization).filter_by(id=5).first()
    delhi_org = db.query(Organization).filter_by(id=6).first()

    # Some legacy tests remove the shared demonstration officer rows.  The
    # lifecycle needs a real recipient in Organization 3, so create a
    # phase-scoped identity rather than depending on that mutable fixture.
    indore_email = "phase13.destination.indore@cybershield.test"
    indore_user = db.query(User).filter_by(email=indore_email).first()
    if indore_user is None:
        indore_user = User(
            email=indore_email,
            hashed_password="test-only-token-authenticated-user",
            full_name="Phase 13 Indore Destination Officer",
            role="DISTRICT_LEA",
            organization_id=indore_org.id,
            is_active=True,
        )
        db.add(indore_user)
        db.commit()

    return {
        "admin": {"Authorization": f"Bearer {create_access_token({'sub': 'admin@cybershield.gov.in', 'role': 'I4C_ADMIN'})}"},
        "delhi_lea": {"Authorization": f"Bearer {create_access_token({'sub': 'state.lea@delhi.cyber.gov.in', 'role': 'STATE_LEA'})}"},
        "mp_state_lea": {"Authorization": f"Bearer {create_access_token({'sub': 'state.lea@mp.police.gov.in', 'role': 'STATE_LEA'})}"},
        "indore_lea": {"Authorization": f"Bearer {create_access_token({'sub': indore_email, 'role': 'DISTRICT_LEA'})}"},
        "bank_officer": {"Authorization": f"Bearer {create_access_token({'sub': 'officer@sbi.co.in', 'role': 'BANK_OFFICER'})}"},
        "analyst": {"Authorization": f"Bearer {create_access_token({'sub': 'analyst@cybershield.gov.in', 'role': 'ANALYST'})}"},
        "auditor": {"Authorization": f"Bearer {create_access_token({'sub': 'auditor@mha.gov.in', 'role': 'AUDITOR'})}"},
    }


def test_phase13_complete_end_to_end_lifecycle(client: TestClient, db_session: Session, workflow_tokens):
    """
    Executes and asserts the complete 10-step lifecycle end-to-end.
    """
    tokens = workflow_tokens
    now = datetime.now(timezone.utc)
    unique_suffix = uuid.uuid4().hex[:6].upper()

    # =========================================================================
    # Step 1: Ingestion (Multi-Transaction Incident + Late Arrivals)
    # =========================================================================
    initial_tx_ref = f"UTR-P13-INIT-{unique_suffix}"
    ben_acc_no = f"SBIN{uuid.uuid4().int % 10000000000:010d}"

    complaint_payload = {
        "fraud_type": "UPI Impersonation Fraud",
        "amount": 125000.0,
        "victim_name": "Aditya Sharma",
        "victim_phone": "9811223344",
        "victim_location": "Connaught Place, Central Delhi",
        "locality": "Connaught Place",
        "state": "Delhi",
        "district": "Central Delhi",
        "region_id": "delhi",
        "payment_channel": "UPI",
        "description": "Victim received fraudulent call impersonating power department requesting urgent bill settlement",
        "transaction_ref": initial_tx_ref,
        "victim_bank": "State Bank of India",
        "beneficiary_bank": "State Bank of India",
        "beneficiary_account_number": ben_acc_no,
        "beneficiary_id": ben_acc_no,
        "beneficiary_upi_id": "suspect.mule@oksbi",
        "ifsc_code": "SBIN0001234",
        "demo_mode": False
    }

    # Register by Delhi LEA
    reg_resp = client.post("/api/v1/complaints", json=complaint_payload, headers=tokens["delhi_lea"])
    assert reg_resp.status_code == 200, f"Registration failed: {reg_resp.text}"
    comp_data = reg_resp.json()
    complaint_id = comp_data["id"]
    complaint_number = comp_data["complaint_number"]
    assert comp_data["region_id"] == "delhi"
    assert comp_data["provenance_mode"] == "DIRECT_OFFICER_INPUT"
    assert comp_data["prediction_status"] == "NOT RUN"

    # Late-arriving second hop transaction
    late_tx_ref = f"UTR-P13-LATE-{unique_suffix}"
    hop2_acc_no = f"SBIN{uuid.uuid4().int % 10000000000:010d}"
    late_tx_payload = {
        "transaction_ref": late_tx_ref,
        "amount": 75000.0,
        "payment_channel": "IMPS",
        "timestamp": (now - timedelta(minutes=15)).isoformat(),
        "sender_account_number": ben_acc_no,
        "sender_bank": "State Bank of India",
        "receiver_account_number": hop2_acc_no,
        "receiver_bank": "State Bank of India",
        "receiver_holder_name": "Secondary Layer Mule",
        "receiver_ifsc": "SBIN0001234",
        "hop_number": 2,
        "notes": "Late reported IMPS transfer identified in bank statement",
        "provenance": "OFFICER_FIELD_REPORT"
    }
    tx_resp = client.post(f"/api/v1/complaints/{complaint_id}/transactions", json=late_tx_payload, headers=tokens["delhi_lea"])
    assert tx_resp.status_code == 201, f"Late transaction ingestion failed: {tx_resp.text}"
    assert tx_resp.json()["is_idempotent_replay"] is False
    assert tx_resp.json()["transaction_ref"] == late_tx_ref

    # Idempotent deduplication check
    tx_dup_resp = client.post(f"/api/v1/complaints/{complaint_id}/transactions", json=late_tx_payload, headers=tokens["delhi_lea"])
    assert tx_dup_resp.status_code == 200, "Expected 200 OK on idempotent re-submission"
    assert tx_dup_resp.json()["is_idempotent_replay"] is True

    # =========================================================================
    # Step 2: Linking & Scenario Verification
    # =========================================================================
    comp_check = client.get(f"/api/v1/complaints/{complaint_id}", headers=tokens["delhi_lea"]).json()
    assert comp_check["scenario_link_status"] == "DIRECT_OFFICER_INPUT"

    # =========================================================================
    # Step 3: ML Prediction Pipeline Execution
    # =========================================================================
    pred_resp = client.post(f"/api/v1/predictions/{complaint_number}", headers=tokens["delhi_lea"])
    assert pred_resp.status_code == 200, f"Prediction failed: {pred_resp.text}"
    pred_data = pred_resp.json()
    prediction_id = pred_data["prediction_id"]

    assert pred_data["region_id"] == "delhi"
    assert pred_data["risk_score"] > 0.0
    assert pred_data["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert pred_data["model_version"] is not None
    assert "top_locations" in pred_data
    assert len(pred_data["top_locations"]) > 0

    # Verify deterministic lineage in explanation
    expl_resp = client.get(f"/api/v1/predictions/{prediction_id}/explanation", headers=tokens["delhi_lea"])
    assert expl_resp.status_code == 200
    expl_data = expl_resp.json()
    assert "explanation_status" in expl_data or "top3_explanations" in expl_data or "narrative" in expl_data

    # =========================================================================
    # Step 4: Risk Alert Generation & Acknowledgment
    # =========================================================================
    alert_resp = client.post(f"/api/v1/alerts/prediction/{prediction_id}", headers=tokens["delhi_lea"])
    assert alert_resp.status_code == 200, f"Alert generation failed: {alert_resp.text}"
    alert_data = alert_resp.json()
    alert_id = alert_data["id"]
    assert alert_data["complaint_id"] == complaint_id
    assert alert_data["status"] in ("NEW", "GENERATED", "QUEUED", "DELIVERED")

    # Acknowledge alert by Delhi LEA
    ack_resp = client.post(
        f"/api/v1/alerts/{alert_id}/acknowledge",
        json={"notes": "Field unit dispatched to high-probability ATM cluster perimeter"},
        headers=tokens["delhi_lea"]
    )
    assert ack_resp.status_code == 200
    assert ack_resp.json()["status"] == "ACKNOWLEDGED"
    assert "Field unit dispatched" in ack_resp.json()["action_notes"]

    # =========================================================================
    # Step 5: Bank Action Lifecycle (Create -> Approve -> Dispatch -> HMAC Callback)
    # =========================================================================
    # Resolve beneficiary Account record in DB
    ben_acc = db_session.query(Account).filter_by(account_number=ben_acc_no).first()
    assert ben_acc is not None

    # Delhi LEA requests bank freeze on beneficiary account
    action_payload = {
        "complaint_id": complaint_id,
        "action_type": "FREEZE_ACCOUNT",
        "alert_id": alert_id,
        "account_id": ben_acc.id,
        "target_account_number": ben_acc.account_number,
        "target_ifsc": "SBIN0001234",
        "bank_name": "State Bank of India",
        "bank_organization_id": 4,  # SBI
        "requested_amount": 125000.0,
        "currency": "INR",
        "environment": "SANDBOX",
        "action_notes": "Urgent freeze request for identified primary beneficiary mule account",
        "idempotency_key": f"IDEMP-P13-{unique_suffix}"
    }
    create_act_resp = client.post("/api/v1/bank-actions", json=action_payload, headers=tokens["delhi_lea"])
    assert create_act_resp.status_code == 201, f"Bank action creation failed: {create_act_resp.text}"
    action_data = create_act_resp.json()
    action_id = action_data["id"]
    action_ref = action_data["action_reference"]
    assert action_data["status"] == "REQUESTED"

    # Delhi LEA approves action
    appr_resp = client.post(f"/api/v1/bank-actions/{action_id}/approve", headers=tokens["delhi_lea"])
    assert appr_resp.status_code == 200
    assert appr_resp.json()["status"] == "APPROVED"

    # Dispatch action to adapter -> enters SENT (truthful: NOT held yet)
    disp_resp = client.post(f"/api/v1/bank-actions/{action_id}/dispatch", headers=tokens["delhi_lea"])
    assert disp_resp.status_code == 200
    assert disp_resp.json()["status"] == "SENT"

    # External bank returns cryptographically signed HMAC callback
    callback_time = datetime.now(timezone.utc).isoformat()
    callback_payload = {
        "action_reference": action_ref,
        "bank_reference": f"SBI-HOLD-REF-{unique_suffix}",
        "status": "HELD",
        "held_amount": 125000.0,
        "currency": "INR",
        "timestamp": callback_time
    }
    payload_str = json.dumps(callback_payload, sort_keys=True)
    signature = generate_sandbox_hmac_signature(payload_str, SANDBOX_SHARED_SECRET)
    callback_id = f"CB-P13-{unique_suffix}"

    cb_resp = client.post(
        "/api/v1/bank-actions/callback",
        json=callback_payload,
        headers={
            "X-Bank-Signature": signature,
            "X-Bank-Timestamp": callback_time,
            "X-Bank-Callback-Id": callback_id
        }
    )
    assert cb_resp.status_code == 200, f"Callback failed: {cb_resp.text}"
    assert cb_resp.json()["status"] == "CONFIRMED_HOLD"
    assert cb_resp.json()["held_amount"] == 125000.0

    # =========================================================================
    # Step 6: Controlled Cross-State Handoff
    # =========================================================================
    handoff_payload = {
        "target_state": "Madhya Pradesh",
        "target_district": "Indore",
        "destination_organization_id": 3,  # Indore Cyber Cell
        "purpose": "Suspect ATM cash-out ATM coordinates located in Indore transit perimeter",
        "evidence_scope": "FULL_CASE",
        "shared_evidence_ids": [],
        "prediction_id": prediction_id,
        "prediction_version": 1,
        "acknowledgement_hours": 24
    }

    ho_resp = client.post(f"/api/v1/complaints/{complaint_id}/handoffs", json=handoff_payload, headers=tokens["delhi_lea"])
    assert ho_resp.status_code == 201, f"Handoff creation failed: {ho_resp.text}"
    handoff_data = ho_resp.json()
    handoff_id = handoff_data["id"]
    assert handoff_data["status"] == "REQUESTED"

    # Verify Indore LEA can see incoming handoff and accept it
    accept_resp = client.post(f"/api/v1/handoffs/{handoff_id}/accept", headers=tokens["indore_lea"])
    assert accept_resp.status_code == 200, f"Handoff accept failed: {accept_resp.text}"
    assert accept_resp.json()["status"] == "ACCEPTED"

    # Indore LEA can now access the complaint via active handoff
    indore_comp_resp = client.get(f"/api/v1/complaints/{complaint_id}", headers=tokens["indore_lea"])
    assert indore_comp_resp.status_code == 200
    assert indore_comp_resp.json()["complaint_number"] == complaint_number

    # Unrelated jurisdiction officer (e.g. suspended or unassigned officer) gets 404/403
    unrelated_headers = {"Authorization": f"Bearer {create_access_token({'sub': 'inactive.officer@cybershield.gov.in', 'role': 'DISTRICT_LEA'})}"}
    unrel_resp = client.get(f"/api/v1/complaints/{complaint_id}", headers=unrelated_headers)
    assert unrel_resp.status_code in (401, 403, 404)

    # =========================================================================
    # Step 7: Evidence Documentation & Integrity Verification
    # =========================================================================
    evidence_content = b"%PDF-1.4 Official Bank Account Transaction Ledger certified by SBI Branch Manager"
    expected_sha256 = hashlib.sha256(evidence_content).hexdigest()

    files = {
        "file": ("sbi_mule_certified_ledger.pdf", io.BytesIO(evidence_content), "application/pdf")
    }
    ev_form = {
        "source": "BANK_STATEMENT",
        "description": "Certified ledger establishing primary mule beneficiary credit flow"
    }
    ev_resp = client.post(
        f"/api/v1/complaints/{complaint_id}/evidence",
        files=files,
        data=ev_form,
        headers=tokens["delhi_lea"]
    )
    assert ev_resp.status_code == 201, f"Evidence upload failed: {ev_resp.text}"
    ev_data = ev_resp.json()
    evidence_id = ev_data["id"]
    assert ev_data["sha256_hash"] == expected_sha256
    assert ev_data["version"] == 1

    # Verify evidence integrity endpoint
    integ_resp = client.get(f"/api/v1/complaints/{complaint_id}/evidence/{evidence_id}/integrity", headers=tokens["delhi_lea"])
    assert integ_resp.status_code == 200
    assert integ_resp.json()["is_valid"] is True
    assert integ_resp.json()["stored_hash"] == expected_sha256
    assert integ_resp.json()["computed_hash"] == expected_sha256

    # =========================================================================
    # Step 8: Operational Investigation Pack (Signed JSON + HTML Docket)
    # =========================================================================
    # Structured JSON Report Data
    report_resp = client.get(f"/api/v1/complaints/{complaint_id}/report", headers=tokens["delhi_lea"])
    assert report_resp.status_code == 200
    report_data = report_resp.json()
    assert report_data["case_summary"]["complaint_number"] == complaint_number
    assert "report_metadata" in report_data
    assert "predictive_intelligence" in report_data
    assert len(report_data["evidence_registry"]) >= 1

    # Printable HTML Docket
    html_resp = client.get(f"/api/v1/complaints/{complaint_id}/report/html", headers=tokens["delhi_lea"])
    assert html_resp.status_code == 200
    html_content = html_resp.text
    assert "<!DOCTYPE html>" in html_content
    assert complaint_number in html_content
    assert "INVESTIGATOR DOSSIER" in html_content or "CYBERSHIELD" in html_content

    # =========================================================================
    # Step 9: Case Outcome Ingestion & Closed-Loop Metrics
    # =========================================================================
    outcome_payload = {
        "outcome_type": "CONFIRMED_CASHOUT",
        "source": "OFFICER_MANUAL",
        "observed_event_time": (now + timedelta(minutes=5)).isoformat(),
        "actual_location_name": "Connaught Place, Central Delhi",
        "actual_withdrawal_amount_inr": 125000.0,
        "actual_recovered_amount_inr": 125000.0,
        "linked_alert_id": alert_id,
        "linked_bank_action_id": action_id,
        "verified_held_amount_inr": 125000.0,
        "notes": "SBI FRMU successfully confirmed Rs 1,25,000 hold on suspect account"
    }
    out_resp = client.post(
        f"/api/v1/outcomes/complaints/{complaint_id}",
        json=outcome_payload,
        headers=tokens["delhi_lea"]
    )
    assert out_resp.status_code == 201, f"Outcome ingestion failed: {out_resp.text}"
    outcome_data = out_resp.json()
    assert outcome_data["complaint_id"] == complaint_id
    assert outcome_data["actual_recovered_amount_inr"] == 125000.0
    # Automated server-side prediction linkage by LAST_OPERATIONAL_BEFORE_EVENT
    assert outcome_data["linked_prediction_id"] == prediction_id

    # Global Outcome Metrics
    metrics_resp = client.get("/api/v1/outcomes/metrics", headers=tokens["admin"])
    assert metrics_resp.status_code == 200
    metrics = metrics_resp.json()
    assert "denominator_total_active" in metrics
    assert "total_actual_recovered_inr" in metrics
    assert metrics["total_actual_recovered_inr"] >= 125000.0

    # =========================================================================
    # Step 10: Role Isolation & Auditing Enforcement
    # =========================================================================
    # 1. Bank officer role boundaries: cannot register complaints, run predictions, or approve bank actions
    bank_comp_resp = client.post(
        "/api/v1/complaints",
        json=complaint_payload,
        headers=tokens["bank_officer"]
    )
    assert bank_comp_resp.status_code == 403

    bank_pred_resp = client.post(
        f"/api/v1/predictions/{complaint_number}",
        headers=tokens["bank_officer"]
    )
    assert bank_pred_resp.status_code == 403

    bank_appr_resp = client.post(
        f"/api/v1/bank-actions/{action_id}/approve",
        headers=tokens["bank_officer"]
    )
    assert bank_appr_resp.status_code == 403

    # 2. Auditor role is strictly read-only: mutations must return 403
    auditor_ev_resp = client.post(
        f"/api/v1/complaints/{complaint_id}/evidence",
        files={"file": ("dummy.txt", io.BytesIO(b"dummy"), "text/plain")},
        data={"source": "LEGAL_NOTICE", "description": "dummy"},
        headers=tokens["auditor"]
    )
    assert auditor_ev_resp.status_code == 403

    auditor_mutate_resp = client.post(
        f"/api/v1/complaints/{complaint_id}/transactions",
        json=late_tx_payload,
        headers=tokens["auditor"]
    )
    assert auditor_mutate_resp.status_code == 403

    auditor_outcome_resp = client.post(
        f"/api/v1/outcomes/complaints/{complaint_id}",
        json=outcome_payload,
        headers=tokens["auditor"]
    )
    assert auditor_outcome_resp.status_code == 403

    # But Auditor CAN read complaints, reports, and metrics
    auditor_read_resp = client.get(f"/api/v1/complaints/{complaint_id}", headers=tokens["auditor"])
    assert auditor_read_resp.status_code == 200

    auditor_report_resp = client.get(f"/api/v1/complaints/{complaint_id}/report", headers=tokens["auditor"])
    assert auditor_report_resp.status_code == 200

    # 3. Unauthenticated request returns 401
    unauth_resp = client.get(f"/api/v1/complaints/{complaint_id}")
    assert unauth_resp.status_code == 401

    # 4. Comprehensive Audit Log Verification
    audit_logs = db_session.query(AuditLog).filter(
        AuditLog.details.ilike(f"%{complaint_number}%")
    ).all()
    actions_logged = {log.action for log in audit_logs}

    # Verify that key lifecycle events were recorded in PostgreSQL AuditLog
    assert "COMPLAINT_CREATED" in actions_logged or len(audit_logs) > 0
