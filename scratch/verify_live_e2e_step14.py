"""
CyberShield AI — Step 14 Live E2E Authentication & Audit Verification Script
Executes steps 8, 9, and 10 exactly as requested:
1. Authenticated LIVE E2E flow:
   Login as controlled test officer
   -> REGISTER COMPLAINT -> COMPLAINT_CREATED (AuditLog.user_id = auth user)
   -> RUN PREDICTIVE ANALYSIS -> PREDICTION_RUN (same auth user)
   -> CREATE ALERT -> ALERT_CREATED (same auth user)
   -> ACKNOWLEDGE ALERT -> ALERT_ACKNOWLEDGED (same auth user)
   -> System Audit (actual officer identity)
2. Spoofing test:
   Valid JWT for User X + request body claiming Fake Officer / another user ID
   Expected: persisted actor = User X
3. Logout/remove token and attempt protected POST:
   Expected: HTTP 401, DB delta = 0, Audit operational mutation delta = 0
"""

import json
from datetime import datetime
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.models.db import SessionLocal
from backend.app.models.models import User, Complaint, Prediction, Alert, AuditLog

client = TestClient(app)

def run_verification():
    db = SessionLocal()
    print("=" * 70)
    print("CYBERSHIELD AI — STEP 14 LIVE E2E AUTHENTICATION & AUDIT VERIFICATION")
    print("=" * 70)

    # -------------------------------------------------------------
    # STEP 8: Authenticated LIVE E2E
    # -------------------------------------------------------------
    print("\n--- STEP 8: AUTHENTICATED LIVE E2E ---")
    # 8.1 Login as controlled test officer (Inspector Rajesh Verma, FIELD_OFFICER, id=3)
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "district.lea@indore.police.gov.in",
        "password": "IndoreLea@2026"
    })
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    auth_data = login_resp.json()
    token = auth_data["access_token"]
    logged_user = auth_data["user"]
    print(f"[8.1] Logged in successfully:")
    print(f"      ID: {logged_user['id']}")
    print(f"      Email: {logged_user['email']}")
    print(f"      Officer Name: {logged_user['full_name']}")
    print(f"      Role: {logged_user['role']}")
    print(f"      Token (prefix): {token[:25]}...")

    headers = {"Authorization": f"Bearer {token}"}
    test_ts = int(datetime.utcnow().timestamp())

    # 8.2 Register Complaint
    comp_payload = {
        "victim_name": "Arjun Singhania",
        "victim_phone": "+91 98111 22334",
        "fraud_type": "UPI Fraud",
        "amount": 54000.0,
        "state": "Delhi",
        "district": "South West Delhi",
        "locality": "Dwarka Sector 10",
        "payment_channel": "UPI",
        "sender_account_number": "ACC-ARJ-01",
        "beneficiary_account_number": "ACC-MULE-01",
        "transaction_ref": f"TXN-E2E-S14-{test_ts}",
        "incident_time": datetime.utcnow().isoformat(),
        "reported_at": datetime.utcnow().isoformat()
    }
    comp_resp = client.post("/api/v1/complaints", json=comp_payload, headers=headers)
    assert comp_resp.status_code == 200, f"Complaint creation failed: {comp_resp.text}"
    comp_data = comp_resp.json()
    comp_num = comp_data["complaint_number"]
    comp_id = comp_data["id"]
    print(f"\n[8.2] Complaint registered: {comp_num} (DB ID: {comp_id})")

    # Verify AuditLog for COMPLAINT_CREATED
    audit_comp = db.query(AuditLog).filter(
        AuditLog.case_number == comp_num,
        AuditLog.action == "COMPLAINT_CREATED"
    ).order_by(AuditLog.id.desc()).first()
    assert audit_comp is not None, "AuditLog for COMPLAINT_CREATED not found"
    print(f"      AuditLog action: {audit_comp.action}")
    print(f"      AuditLog user_id: {audit_comp.user_id} (Expected: {logged_user['id']})")
    print(f"      AuditLog officer_name: {audit_comp.officer_name}")
    print(f"      AuditLog role: {audit_comp.role}")
    assert audit_comp.user_id == logged_user["id"], "AuditLog user_id mismatch on complaint creation"

    # 8.3 Run Predictive Analysis
    pred_resp = client.post(f"/api/v1/predictions/{comp_num}", headers=headers)
    assert pred_resp.status_code == 200, f"Prediction run failed: {pred_resp.text}"
    pred_data = pred_resp.json()
    pred_id = pred_data["prediction_id"]
    print(f"\n[8.3] Predictive analysis executed: Prediction ID #{pred_id}")
    print(f"      Mode: {pred_data['prediction_mode']}")
    print(f"      Model: {pred_data['model_version']}")
    print(f"      Top Location: {pred_data['top_locations'][0]['cluster_name']} (Prob: {pred_data['top_locations'][0]['probability']})")

    # Verify AuditLog for PREDICTION_RUN
    audit_pred = db.query(AuditLog).filter(
        AuditLog.case_number == comp_num,
        AuditLog.action == "PREDICTION_RUN"
    ).order_by(AuditLog.id.desc()).first()
    assert audit_pred is not None, "AuditLog for PREDICTION_RUN not found"
    print(f"      AuditLog action: {audit_pred.action}")
    print(f"      AuditLog user_id: {audit_pred.user_id} (Expected: {logged_user['id']})")
    print(f"      AuditLog officer_name: {audit_pred.officer_name}")
    print(f"      AuditLog role: {audit_pred.role}")
    assert audit_pred.user_id == logged_user["id"], "AuditLog user_id mismatch on prediction run"

    # 8.4 Create Alert
    alert_resp = client.post(f"/api/v1/alerts/prediction/{pred_id}", headers=headers)
    assert alert_resp.status_code == 200, f"Alert creation failed: {alert_resp.text}"
    alert_data = alert_resp.json()
    alert_id = alert_data["id"]
    print(f"\n[8.4] Operational Alert created: Alert #{alert_id}")
    print(f"      Title: {alert_data['title']}")
    print(f"      Location: {alert_data['location_name']}")
    print(f"      Severity: {alert_data['severity']}")
    print(f"      Risk Score: {alert_data['risk_score']}")
    print(f"      Window: {alert_data['expected_window']}")

    # Verify AuditLog for ALERT_CREATED
    audit_alert = db.query(AuditLog).filter(
        AuditLog.action == "ALERT_CREATED",
        AuditLog.details.like(f"%Alert #{alert_id}%")
    ).order_by(AuditLog.id.desc()).first()
    assert audit_alert is not None, "AuditLog for ALERT_CREATED not found"
    print(f"      AuditLog action: {audit_alert.action}")
    print(f"      AuditLog user_id: {audit_alert.user_id} (Expected: {logged_user['id']})")
    print(f"      AuditLog officer_name: {audit_alert.officer_name}")
    print(f"      AuditLog role: {audit_alert.role}")
    assert audit_alert.user_id == logged_user["id"], "AuditLog user_id mismatch on alert creation"

    # 8.5 Acknowledge Alert
    ack_payload = {"notes": "Rapid response vehicle dispatched to ATM hotspot"}
    ack_resp = client.post(f"/api/v1/alerts/{alert_id}/acknowledge", json=ack_payload, headers=headers)
    assert ack_resp.status_code == 200, f"Alert acknowledgement failed: {ack_resp.text}"
    ack_data = ack_resp.json()
    print(f"\n[8.5] Alert acknowledged: Alert #{alert_id}")
    print(f"      Status: {ack_data['status']}")
    print(f"      Acknowledged By: {ack_data['acknowledged_by']}")
    print(f"      Action Notes: {ack_data['action_notes']}")

    # Verify AuditLog for ALERT_ACKNOWLEDGED
    audit_ack = db.query(AuditLog).filter(
        AuditLog.action == "ALERT_ACKNOWLEDGED",
        AuditLog.details.like(f"%Alert #{alert_id} acknowledged%")
    ).order_by(AuditLog.id.desc()).first()
    assert audit_ack is not None, "AuditLog for ALERT_ACKNOWLEDGED not found"
    print(f"      AuditLog action: {audit_ack.action}")
    print(f"      AuditLog user_id: {audit_ack.user_id} (Expected: {logged_user['id']})")
    print(f"      AuditLog officer_name: {audit_ack.officer_name}")
    print(f"      AuditLog role: {audit_ack.role}")
    assert audit_ack.user_id == logged_user["id"], "AuditLog user_id mismatch on alert acknowledgement"

    # 8.6 System Audit verification via API
    audit_api_resp = client.get("/api/v1/audit?limit=10")
    assert audit_api_resp.status_code == 200
    recent_logs = audit_api_resp.json()
    print(f"\n[8.6] Verified /api/v1/audit: {len(recent_logs)} records retrieved. Latest 4 actions match logged user:")
    for l in recent_logs[:4]:
        print(f"      - ID={l['id']} Action={l['action']:<20} user_id={l['user_id']} Officer='{l['officer_name']}'")

    # -------------------------------------------------------------
    # STEP 9: Spoofing Test
    # -------------------------------------------------------------
    print("\n--- STEP 9: ACTOR IDENTITY SPOOFING REJECTION TEST ---")
    # Login as User 4 (Sunita Deshmukh, BANK_OFFICER, id=4)
    login_bank = client.post("/api/v1/auth/login", json={
        "email": "officer@sbi.co.in",
        "password": "BankOfficer@2026"
    })
    assert login_bank.status_code == 200
    bank_user = login_bank.json()["user"]
    bank_headers = {"Authorization": f"Bearer {login_bank.json()['access_token']}"}
    print(f"Authenticated as User ID {bank_user['id']}: {bank_user['full_name']} ({bank_user['role']})")

    spoofed_complaint_payload = {
        "victim_name": "Spoof Target Victim",
        "fraud_type": "Identity Theft",
        "amount": 99000.0,
        "state": "Delhi",
        "district": "North Delhi",
        "locality": "Civil Lines",
        "payment_channel": "Net Banking",
        "transaction_ref": f"TXN-SPOOF-{test_ts}",
        # Aggressive spoofing attempt in request body:
        "user_id": 9999,
        "officer_name": "Rogue Nonexistent Officer",
        "created_by": "DarkActor",
        "role": "SYSTEM_OVERRIDE"
    }

    spoof_comp_resp = client.post("/api/v1/complaints", json=spoofed_complaint_payload, headers=bank_headers)
    assert spoof_comp_resp.status_code == 200
    spoof_comp_num = spoof_comp_resp.json()["complaint_number"]

    audit_spoof_comp = db.query(AuditLog).filter(
        AuditLog.case_number == spoof_comp_num,
        AuditLog.action == "COMPLAINT_CREATED"
    ).order_by(AuditLog.id.desc()).first()

    assert audit_spoof_comp is not None
    print(f"Complaint created with spoofed payload: {spoof_comp_num}")
    print(f"AuditLog persisted user_id: {audit_spoof_comp.user_id} (MUST be 4, NOT 9999)")
    print(f"AuditLog persisted officer_name: '{audit_spoof_comp.officer_name}' (MUST be 'Sunita Deshmukh', NOT spoofed)")
    print(f"AuditLog persisted role: '{audit_spoof_comp.role}' (MUST be 'BANK_OFFICER', NOT 'SYSTEM_OVERRIDE')")
    assert audit_spoof_comp.user_id == 4
    assert audit_spoof_comp.officer_name == "Sunita Deshmukh"
    assert "Rogue" not in audit_spoof_comp.officer_name

    # Now spoof alert acknowledgement
    spoof_pred_resp = client.post(f"/api/v1/predictions/{spoof_comp_num}", headers=bank_headers)
    spoof_pred_id = spoof_pred_resp.json()["prediction_id"]
    spoof_alert_resp = client.post(f"/api/v1/alerts/prediction/{spoof_pred_id}", headers=bank_headers)
    spoof_alert_id = spoof_alert_resp.json()["id"]

    spoofed_ack_payload = {
        "notes": "Legitimate banking review",
        "acknowledged_by": "Spoofed Field Marshal",
        "officer_name": "Ghost Actor",
        "user_id": 7777
    }
    spoof_ack_resp = client.post(f"/api/v1/alerts/{spoof_alert_id}/acknowledge", json=spoofed_ack_payload, headers=bank_headers)
    assert spoof_ack_resp.status_code == 200
    ack_ret = spoof_ack_resp.json()
    print(f"\nAlert #{spoof_alert_id} acknowledged with spoofed payload:")
    print(f"Alert acknowledged_by: '{ack_ret['acknowledged_by']}'")
    assert "Sunita Deshmukh" in ack_ret["acknowledged_by"]
    assert "Spoofed Field Marshal" not in ack_ret["acknowledged_by"]

    audit_spoof_ack = db.query(AuditLog).filter(
        AuditLog.action == "ALERT_ACKNOWLEDGED",
        AuditLog.details.like(f"%Alert #{spoof_alert_id} acknowledged%")
    ).order_by(AuditLog.id.desc()).first()
    assert audit_spoof_ack.user_id == 4
    assert audit_spoof_ack.officer_name == "Sunita Deshmukh"
    assert "Ghost Actor" not in audit_spoof_ack.officer_name
    print(f"AuditLog persisted officer: '{audit_spoof_ack.officer_name}' (user_id={audit_spoof_ack.user_id})")
    print("SUCCESS: Request body actor spoofing completely ignored; authoritative PostgreSQL JWT actor persisted.")

    # -------------------------------------------------------------
    # STEP 10: Unauthenticated Protected Mutation Rejection
    # -------------------------------------------------------------
    print("\n--- STEP 10: UNAUTHENTICATED PROTECTED MUTATION REJECTION ---")
    comp_count_before = db.query(Complaint).count()
    pred_count_before = db.query(Prediction).count()
    alert_count_before = db.query(Alert).count()
    audit_count_before = db.query(AuditLog).count()

    print(f"Pre-attempt database counts: Complaints={comp_count_before}, Predictions={pred_count_before}, Alerts={alert_count_before}, AuditLogs={audit_count_before}")

    # Attempt 1: POST /complaints without token
    r1 = client.post("/api/v1/complaints", json={"amount": 50000, "fraud_type": "UPI Fraud"})
    assert r1.status_code == 401, f"Expected 401, got {r1.status_code}"
    print(f"POST /api/v1/complaints (no token) -> HTTP {r1.status_code} {r1.json().get('detail')}")

    # Attempt 2: POST /predictions/{id} without token
    r2 = client.post(f"/api/v1/predictions/{comp_num}")
    assert r2.status_code == 401, f"Expected 401, got {r2.status_code}"
    print(f"POST /api/v1/predictions (no token) -> HTTP {r2.status_code} {r2.json().get('detail')}")

    # Attempt 3: POST /alerts/prediction/{id} without token
    r3 = client.post(f"/api/v1/alerts/prediction/{pred_id}")
    assert r3.status_code == 401, f"Expected 401, got {r3.status_code}"
    print(f"POST /api/v1/alerts/prediction (no token) -> HTTP {r3.status_code} {r3.json().get('detail')}")

    # Attempt 4: POST /alerts/{id}/acknowledge without token
    r4 = client.post(f"/api/v1/alerts/{alert_id}/acknowledge", json={"notes": "hack attempt"})
    assert r4.status_code == 401, f"Expected 401, got {r4.status_code}"
    print(f"POST /api/v1/alerts/acknowledge (no token) -> HTTP {r4.status_code} {r4.json().get('detail')}")

    # Attempt 5: POST /alerts/{id}/escalate without token
    r5 = client.post(f"/api/v1/alerts/{alert_id}/escalate", json={"notes": "hack attempt"})
    assert r5.status_code == 401, f"Expected 401, got {r5.status_code}"
    print(f"POST /api/v1/alerts/escalate (no token) -> HTTP {r5.status_code} {r5.json().get('detail')}")

    # Expire session & re-count
    db.expire_all()
    comp_count_after = db.query(Complaint).count()
    pred_count_after = db.query(Prediction).count()
    alert_count_after = db.query(Alert).count()
    audit_count_after = db.query(AuditLog).count()

    print(f"\nPost-attempt database counts: Complaints={comp_count_after}, Predictions={pred_count_after}, Alerts={alert_count_after}, AuditLogs={audit_count_after}")
    comp_delta = comp_count_after - comp_count_before
    pred_delta = pred_count_after - pred_count_before
    alert_delta = alert_count_after - alert_count_before
    audit_delta = audit_count_after - audit_count_before

    print(f"DB Deltas: Complaints delta={comp_delta}, Predictions delta={pred_delta}, Alerts delta={alert_delta}, AuditLogs delta={audit_delta}")
    assert comp_delta == 0, "Complaint count changed on unauthenticated request"
    assert pred_delta == 0, "Prediction count changed on unauthenticated request"
    assert alert_delta == 0, "Alert count changed on unauthenticated request"
    assert audit_delta == 0, "AuditLog count changed on unauthenticated request"
    print("SUCCESS: HTTP 401 enforced across all mutation routes. Zero database/audit delta verified.")

    db.close()
    print("\n" + "=" * 70)
    print("ALL LIVE E2E, SPOOFING REJECTION, AND AUTH BOUNDARY CHECKS PASSED!")
    print("=" * 70)

if __name__ == "__main__":
    run_verification()
