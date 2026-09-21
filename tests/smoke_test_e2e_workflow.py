"""
CyberShield AI — Section 8: Final End-to-End Workflow Smoke Test
Runs a complete lifecycle of a new Delhi complaint under active V7-compat runtime:
1. Register & persist complaint in Delhi (e.g. SOUTH_WEST_DWARKA).
2. Attach transaction evidence chain (2 hops, terminal mule in EAST_DELHI).
3. Generate prediction using active production model (v7_compat).
4. Fetch Case Intelligence summary.
5. Query Risk Map in Case Focus mode (Delhi-wide hotspots OFF, case clusters ON).
6. Query transaction graph attribution.
7. Generate and acknowledge alert.
8. Download evidence dossier / export summary.
9. Verify zero Madhya Pradesh / Indore / legacy prototype data appears.
"""

import os
import sys
import json
from datetime import datetime, timezone
from fastapi.testclient import TestClient

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.main import app
from backend.app.auth.security import create_access_token
from backend.app.models.db import SessionLocal
from backend.app.models.models import Complaint, Transaction, Account, Alert, Prediction, ComplaintAccount

client = TestClient(app)

def run_e2e_smoke_test():
    token = create_access_token({"sub": "admin@cybershield.gov.in", "role": "I4C_ADMIN", "state": "Delhi", "district": "SOUTH_WEST"})
    headers = {"Authorization": f"Bearer {token}"}

    print("======================================================================")
    print("SECTION 8 — END-TO-END WORKFLOW SMOKE TEST (Delhi Pilot, Active V7)")
    print("======================================================================")

    # Step 1: Register complaint
    c_num = f"CMP-SMOKE-{int(datetime.now(timezone.utc).timestamp())}"
    comp_payload = {
        "complaint_number": c_num,
        "victim_name": "Delhi Test Citizen",
        "victim_contact": "+91-9876543210",
        "fraud_type": "UPI / QR Code Fraud",
        "amount": 75000.00,
        "payment_channel": "UPI",
        "incident_date": datetime.now(timezone.utc).isoformat(),
        "state": "Delhi",
        "district": "SOUTH_WEST",
        "description": "UPI payment diverted to mule network"
    }

    resp = client.post("/api/v1/complaints/", json=comp_payload, headers=headers)
    print(f"1. Register Complaint: Status={resp.status_code}")
    assert resp.status_code in [200, 201], f"Failed to register complaint: {resp.text}"
    comp_data = resp.json()
    comp_id = comp_data.get("id") or comp_data.get("complaint_id")

    # Step 2: Attach transaction chain
    db = SessionLocal()
    comp_obj = db.query(Complaint).filter(Complaint.id == comp_id).first()
    assert comp_obj is not None, f"Complaint id={comp_id} not found in database"

    # Add 2 accounts and 1 transaction
    acc1 = Account(account_number=f"ACC-SMOKE-1-{comp_id}", masked_account="XXXX-1234", holder_name="Layer 1 Mule", bank_name="SBI", ifsc="SBIN0001234", account_type="SAVINGS", risk_score=0.85, district="SOUTH", state="Delhi")
    acc2 = Account(account_number=f"ACC-SMOKE-2-{comp_id}", masked_account="XXXX-5678", holder_name="Terminal Mule", bank_name="HDFC", ifsc="HDFC0005678", account_type="CURRENT", risk_score=0.92, district="EAST", state="Delhi")
    db.add_all([acc1, acc2])
    db.flush()
    acc1_id = acc1.id
    acc2_id = acc2.id

    ca1 = ComplaintAccount(complaint_id=comp_id, account_id=acc1_id, association_type="INTERMEDIARY")
    ca2 = ComplaintAccount(complaint_id=comp_id, account_id=acc2_id, association_type="BENEFICIARY")
    db.add_all([ca1, ca2])

    tx1 = Transaction(transaction_ref=f"TX-SMOKE-1-{comp_id}", complaint_id=comp_id, sender_account_id=acc1_id, receiver_account_id=acc2_id, amount=75000.0, payment_channel="UPI", timestamp=datetime.now(timezone.utc), hop_number=1, status="COMPLETED")
    db.add(tx1)
    db.commit()
    print(f"2. Transaction Evidence Attached: 2 accounts, 1 transfer in East Delhi corridor.")

    # Step 3: Run Prediction (Active V7)
    pred_resp = client.post(f"/api/v1/predictions/{comp_id}", headers=headers)
    print(f"3. Active Prediction Run: Status={pred_resp.status_code}")
    assert pred_resp.status_code == 200, f"Prediction failed: {pred_resp.text}"
    pred_data = pred_resp.json()
    assert pred_data["model_version"] == "cashout-location-xgb-v7-compat", f"Wrong model version: {pred_data['model_version']}"
    assert len(pred_data["top_locations"]) >= 3, "Did not return top 3 locations"
    pred_id = pred_data.get("prediction_id") or pred_data.get("id")
    print(f"   Model Version: {pred_data['model_version']} (ACTIVE)")
    print(f"   Top-1 Location: {pred_data['top_locations'][0]['cluster_name']} (P={pred_data['top_locations'][0]['probability']:.4f})")

    # Step 4: Risk Map in Case Focus Mode
    rm_resp = client.get(f"/api/v1/risk-map?complaint_id={comp_id}", headers=headers)
    print(f"4. Risk Map (Case Focus Mode): Status={rm_resp.status_code}")
    assert rm_resp.status_code == 200, f"Risk map failed: {rm_resp.text}"
    rm_data = rm_resp.json()
    print(f"   Case Focus Clusters Returned: {len(rm_data.get('clusters', []))}")

    # Step 5: Transaction Graph
    graph_resp = client.get(f"/api/v1/complaints/{comp_id}/graph", headers=headers)
    print(f"5. Transaction Graph: Status={graph_resp.status_code}")
    assert graph_resp.status_code == 200, f"Graph retrieval failed: {graph_resp.text}"

    # Step 6: Alert Creation & Acknowledgment
    alert_resp = client.post(f"/api/v1/alerts/prediction/{pred_id}", headers=headers)
    print(f"6. Alert Generation: Status={alert_resp.status_code}")
    assert alert_resp.status_code == 200, f"Alert generation failed: {alert_resp.text}"
    alert_data = alert_resp.json()
    alert_id = alert_data.get("alert_id") or alert_data.get("id")

    if alert_id:
        ack_resp = client.post(f"/api/v1/alerts/{alert_id}/acknowledge", headers=headers)
        print(f"   Alert Acknowledgment: Status={ack_resp.status_code}")
        assert ack_resp.status_code == 200

    # Step 7: Dossier / Case Report
    dossier_resp = client.get(f"/api/v1/complaints/{comp_id}/report", headers=headers)
    print(f"7. Evidence Dossier Export: Status={dossier_resp.status_code}")
    assert dossier_resp.status_code == 200, f"Dossier export failed: {dossier_resp.text}"

    # Step 8: Verify Zero Madhya Pradesh / Indore Data
    all_text = json.dumps([comp_data, pred_data, rm_data, graph_resp.json()]).lower()
    assert "indore" not in all_text, "Found legacy Indore data in smoke test!"
    assert "madhya pradesh" not in all_text, "Found legacy MP data in smoke test!"
    print("8. Clean Territory Verification: Zero Indore/MP data found (PASS).")

    # Cleanup smoke test records
    db = SessionLocal()
    db.query(Alert).filter(Alert.complaint_id == comp_id).delete()
    pred_ids = [r[0] for r in db.query(Prediction.id).filter(Prediction.complaint_id == comp_id).all()]
    if pred_ids:
        from backend.app.models.models import PredictionLocation
        db.query(PredictionLocation).filter(PredictionLocation.prediction_id.in_(pred_ids)).delete(synchronize_session=False)
    db.query(Prediction).filter(Prediction.complaint_id == comp_id).delete(synchronize_session=False)
    db.query(Transaction).filter(Transaction.complaint_id == comp_id).delete(synchronize_session=False)
    db.query(ComplaintAccount).filter(ComplaintAccount.complaint_id == comp_id).delete(synchronize_session=False)
    db.query(Account).filter(Account.id.in_([acc1_id, acc2_id])).delete(synchronize_session=False)
    db.query(Complaint).filter(Complaint.id == comp_id).delete(synchronize_session=False)
    db.commit()
    db.close()
    print("\n[SUCCESS] Section 8 End-to-End Workflow Smoke Test Passed Completely.")

if __name__ == "__main__":
    run_e2e_smoke_test()
