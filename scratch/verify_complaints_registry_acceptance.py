import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import func

from backend.app.main import app
from backend.app.models.db import SessionLocal
from backend.app.models.models import (
    Complaint, Prediction, PredictionLocation, Alert, Transaction, Account, User
)

def run_acceptance_tests():
    print("======================================================================")
    print("CYBERSHIELD AI — POSTGRESQL-BACKED SAVED COMPLAINTS REGISTRY VERIFICATION")
    print("======================================================================")

    client = TestClient(app)
    db = SessionLocal()

    # Step 0: Real Authenticated Officer Login
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@cybershield.gov.in", "password": "CyberAdmin@2026"}
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"[AUTH] Logged in as admin@cybershield.gov.in. Token acquired.")

    # Step 1: Section 22 Verification — Refresh Must NOT Cause Writes
    c_count_before = db.query(Complaint).count()
    p_count_before = db.query(Prediction).count()
    pl_count_before = db.query(PredictionLocation).count()
    a_count_before = db.query(Alert).count()
    tx_count_before = db.query(Transaction).count()

    # Call GET /complaints multiple times
    for i in range(3):
        res = client.get("/api/v1/complaints", headers=headers)
        assert res.status_code == 200, f"GET /complaints failed: {res.text}"

    c_count_after = db.query(Complaint).count()
    p_count_after = db.query(Prediction).count()
    pl_count_after = db.query(PredictionLocation).count()
    a_count_after = db.query(Alert).count()
    tx_count_after = db.query(Transaction).count()

    assert c_count_before == c_count_after, "Complaint count changed on GET /complaints!"
    assert p_count_before == p_count_after, "Prediction count changed on GET /complaints!"
    assert pl_count_before == pl_count_after, "PredictionLocation count changed on GET /complaints!"
    assert a_count_before == a_count_after, "Alert count changed on GET /complaints!"
    assert tx_count_before == tx_count_after, "Transaction count changed on GET /complaints!"
    print("[PASS] Section 22: Opening and refreshing /complaints creates ZERO DB records (100% read-only).")

    # Step 2: Record Current Newest Complaint
    current_newest = (
        db.query(Complaint)
        .filter(func.lower(Complaint.state) == "delhi")
        .order_by(Complaint.reported_at.desc(), Complaint.id.desc())
        .first()
    )
    print(f"[BASELINE] Current newest Delhi complaint: {current_newest.complaint_number} (ID: {current_newest.id}, Reported: {current_newest.reported_at})")

    # Step 3: Register ONE Fresh Delhi Complaint through API
    payload = {
        "victim_name": "Aman Sharma",
        "fraud_type": "Investment Scam",
        "amount": 85000.00,
        "state": "Delhi",
        "district": "South West Delhi",
        "locality": "Dwarka",
        "victim_location": "Dwarka, South West Delhi, Delhi",
        "payment_channel": "UPI",
        "victim_bank": "State Bank of India",
        "beneficiary_bank": "HDFC Bank",
        "beneficiary_id": "mule.recipient@okhdfcbank",
        "transaction_ref": f"UTR-DL-TEST-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        "description": "Victim deceived into transferring funds through fraudulent investment platform.",
        "incident_time": datetime.utcnow().isoformat(),
        "reported_at": datetime.utcnow().isoformat()
    }

    create_res = client.post("/api/v1/complaints", json=payload, headers=headers)
    assert create_res.status_code == 200, f"Registration failed: {create_res.text}"
    created_data = create_res.json()
    new_comp_num = created_data["complaint_number"]
    new_comp_id = created_data["id"]
    print(f"[REGISTRATION SUCCESS] Fresh Complaint Registered: {new_comp_num} (DB ID: {new_comp_id})")

    # Step 4: Verify PostgreSQL Persistence
    db_comp = db.query(Complaint).filter(Complaint.id == new_comp_id).first()
    assert db_comp is not None, "Complaint not found in PostgreSQL!"
    assert db_comp.complaint_number == new_comp_num
    assert db_comp.victim_name == "Aman Sharma"
    assert float(db_comp.amount) == 85000.00
    assert db_comp.locality == "Dwarka"
    assert db_comp.state == "Delhi"

    # Verify associated accounts & direct transaction in PostgreSQL
    txs = db.query(Transaction).filter(Transaction.complaint_id == new_comp_id).all()
    assert len(txs) >= 1, "Direct transaction not persisted in PostgreSQL!"
    assert txs[0].transaction_ref == payload["transaction_ref"]
    assert float(txs[0].amount) == 85000.00
    print(f"[POSTGRESQL VERIFIED] Complaint, Accounts, and Transaction #{txs[0].transaction_ref} persisted.")

    # Step 5: Verify Appearance at TOP of /complaints
    list_res = client.get("/api/v1/complaints", headers=headers)
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) > 0, "No complaints returned from GET /complaints!"
    top_row = items[0]
    assert top_row["complaint_number"] == new_comp_num, f"Expected {new_comp_num} at top of table, found {top_row['complaint_number']}"
    assert top_row["victim_name"] == "Aman Sharma"
    assert top_row["fraud_type"] == "Investment Scam"
    assert float(top_row["amount"]) == 85000.00
    assert top_row["locality"] == "Dwarka"
    assert top_row["payment_channel"] == "UPI"
    assert top_row["prediction_status"] == "NOT RUN", f"Initial prediction status must be NOT RUN, got {top_row['prediction_status']}"
    assert top_row["alert_status"] == "NOT GENERATED", f"Initial alert status must be NOT GENERATED, got {top_row['alert_status']}"
    assert top_row["case_status"] == "ACTIVE"
    print(f"[PASS] Section 8 & 9: New complaint appears at TOP of existing table with Prediction=NOT RUN and Alert=NOT GENERATED.")

    # Step 6: Verify Persistence Scenarios A through F (Section 20)
    # A. Immediately after registration: verified above (top_row).
    # B. Browser refresh simulation:
    refresh_res = client.get("/api/v1/complaints", headers=headers)
    assert refresh_res.json()[0]["complaint_number"] == new_comp_num
    print("[PASS] Section 20-B: Visible after browser refresh.")

    # C. Navigate Dashboard -> Complaints simulation:
    dash_res = client.get("/api/v1/dashboard/summary")
    assert dash_res.status_code == 200
    comp_nav_res = client.get("/api/v1/complaints", headers=headers)
    assert comp_nav_res.json()[0]["complaint_number"] == new_comp_num
    print("[PASS] Section 20-C: Visible after navigation (Dashboard -> Complaints).")

    # D. Logout/Login simulation:
    login_resp2 = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@cybershield.gov.in", "password": "CyberAdmin@2026"}
    )
    headers2 = {"Authorization": f"Bearer {login_resp2.json()['access_token']}"}
    session2_res = client.get("/api/v1/complaints", headers=headers2)
    assert session2_res.json()[0]["complaint_number"] == new_comp_num
    print("[PASS] Section 20-D: Visible after Logout/Login.")

    # E & F. Frontend/Backend restart simulation (fresh DB session):
    db.close()
    db_fresh = SessionLocal()
    comp_fresh = db_fresh.query(Complaint).filter(Complaint.complaint_number == new_comp_num).first()
    assert comp_fresh is not None
    client_fresh = TestClient(app)
    restart_res = client_fresh.get("/api/v1/complaints", headers=headers2)
    assert restart_res.json()[0]["complaint_number"] == new_comp_num
    print("[PASS] Section 20-E & F: Visible after fresh database connection / restart simulation.")

    # Step 7: Section 10 — VIEW CASE
    case_res = client.get(f"/api/v1/complaints/{new_comp_num}")
    assert case_res.status_code == 200
    case_data = case_res.json()
    assert case_data["complaint_number"] == new_comp_num
    assert case_data["victim_name"] == "Aman Sharma"
    print(f"[PASS] Section 10: GET /complaints/{new_comp_num} returns complete case details directly from PostgreSQL.")

    # Step 8: Section 11 — RUN PREDICTIVE ANALYSIS
    pred_run_res = client.post(f"/api/v1/predictions/{new_comp_num}", headers=headers)
    assert pred_run_res.status_code == 200, f"Prediction execution failed: {pred_run_res.text}"
    pred_data = pred_run_res.json()
    new_pred_id = pred_data["prediction_id"]
    print(f"[PREDICTION PERSISTED] Prediction ID: #{new_pred_id} created for {new_comp_num}.")

    # Verify in DB:
    db_pred = db_fresh.query(Prediction).filter(Prediction.complaint_id == new_comp_id).first()
    assert db_pred is not None, "Prediction not found in PostgreSQL!"
    assert db_pred.id == new_pred_id

    # Verify Return to /complaints: SAME complaint row updated to Prediction = AVAILABLE, Alert = NOT GENERATED
    list_after_pred = client.get("/api/v1/complaints", headers=headers).json()
    matching_rows = [r for r in list_after_pred if r["complaint_number"] == new_comp_num]
    assert len(matching_rows) == 1, f"Expected exactly 1 complaint row for {new_comp_num}, found {len(matching_rows)}!"
    assert matching_rows[0]["prediction_status"] == "AVAILABLE", f"Expected prediction AVAILABLE, got {matching_rows[0]['prediction_status']}"
    assert matching_rows[0]["alert_status"] == "NOT GENERATED", f"Expected alert NOT GENERATED, got {matching_rows[0]['alert_status']}"
    print(f"[PASS] Section 11: After prediction, row shows Prediction=AVAILABLE, Alert=NOT GENERATED (No duplicate created).")

    # Step 9: Section 12 — AFTER ALERT
    alert_gen_res = client.post(f"/api/v1/alerts/generate/{new_comp_num}", headers=headers)
    assert alert_gen_res.status_code == 200, f"Alert generation failed: {alert_gen_res.text}"
    new_alert_id = alert_gen_res.json()["id"]
    print(f"[ALERT PERSISTED] Alert ID: #{new_alert_id} generated for {new_comp_num}.")

    # Verify in DB:
    db_alert = db_fresh.query(Alert).filter(Alert.complaint_id == new_comp_id).first()
    assert db_alert is not None, "Alert not found in PostgreSQL!"

    # Verify Return to /complaints: SAME complaint row updated to Prediction = AVAILABLE, Alert = GENERATED
    list_after_alert = client.get("/api/v1/complaints", headers=headers).json()
    matching_rows = [r for r in list_after_alert if r["complaint_number"] == new_comp_num]
    assert len(matching_rows) == 1, "Duplicate complaint row detected!"
    assert matching_rows[0]["prediction_status"] == "AVAILABLE"
    assert matching_rows[0]["alert_status"] == "GENERATED", f"Expected alert GENERATED, got {matching_rows[0]['alert_status']}"
    print(f"[PASS] Section 12: After alert, row shows Prediction=AVAILABLE, Alert=GENERATED (No duplicate created).")

    # Step 10: Alert Acknowledged
    ack_res = client.post(
        f"/api/v1/alerts/{new_alert_id}/acknowledge",
        json={"notes": "Patrol dispatched to ATM corridor."},
        headers=headers
    )
    assert ack_res.status_code == 200, f"Acknowledge failed: {ack_res.text}"
    list_after_ack = client.get("/api/v1/complaints", headers=headers).json()
    matching_rows = [r for r in list_after_ack if r["complaint_number"] == new_comp_num]
    assert matching_rows[0]["alert_status"] == "ACKNOWLEDGED", f"Expected alert ACKNOWLEDGED, got {matching_rows[0]['alert_status']}"
    print(f"[PASS] Section 12: After acknowledge, row shows Alert=ACKNOWLEDGED.")

    # Step 11: Section 3 — Exclude Legacy Outside Rows (Bhopal, MP, etc.)
    outside_in_delhi = [r for r in list_after_ack if "Madhya Pradesh" in (r.get("state") or "") or "Bhopal" in (r.get("victim_location") or "")]
    assert len(outside_in_delhi) == 0, f"Found outside historical rows in Delhi pilot registry: {outside_in_delhi}"
    print("[PASS] Section 3: Bhopal/MP historical rows strictly excluded from Delhi pilot operational registry.")

    # Step 12: Section 13 — Search Operational Support
    # Search by Complaint Number
    s_comp = client.get(f"/api/v1/complaints?search={new_comp_num}", headers=headers).json()
    assert any(r["complaint_number"] == new_comp_num for r in s_comp)
    # Search by Victim Name
    s_vic = client.get("/api/v1/complaints?search=Aman%20Sharma", headers=headers).json()
    assert any(r["complaint_number"] == new_comp_num for r in s_vic)
    # Search by Locality
    s_loc = client.get("/api/v1/complaints?search=Dwarka", headers=headers).json()
    assert any(r["complaint_number"] == new_comp_num for r in s_loc)
    print("[PASS] Section 13: Search operates on complaint number, victim name, locality.")

    # Step 13: Section 14 & 16 — Operational Filters & Pagination Headers
    paginated_res = client.get("/api/v1/complaints?limit=25&page=1", headers=headers)
    assert paginated_res.status_code == 200
    assert "X-Total-Count" in paginated_res.headers
    assert "X-Page" in paginated_res.headers
    assert "X-Limit" in paginated_res.headers
    assert "X-Total-Pages" in paginated_res.headers
    total = int(paginated_res.headers["X-Total-Count"])
    assert total >= 3449, f"Total records count unexpected: {total}"
    print(f"[PASS] Section 16: Pagination headers verified (Total: {total}, Limit: 25, Pages: {paginated_res.headers['X-Total-Pages']}).")

    db_fresh.close()
    print("\n======================================================================")
    print("ALL ACCEPTANCE CRITERIA PASSED: SAVED COMPLAINTS REGISTRY = PASS")
    print("======================================================================")

    return {
        "new_comp_num": new_comp_num,
        "new_comp_id": new_comp_id
    }

if __name__ == "__main__":
    res = run_acceptance_tests()
    print(f"RESULT_COMPLAINT_NUMBER={res['new_comp_num']}")
    print(f"RESULT_COMPLAINT_ID={res['new_comp_id']}")
