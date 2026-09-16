"""
CyberShield AI — Isolated Prediction & Alert Idempotency Test
Verifies that:
1. First prediction POST creates exactly 1 Prediction and exactly 3 PredictionLocations.
2. Repeated prediction POST reuses the existing prediction_id.
3. Prediction count remains 1, PredictionLocation count remains 3.
4. Alert creation for the prediction is idempotent (no duplicates).
"""

import sys
import os
import time
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import backend.app.models.db as db_mod
from backend.app.models.models import Complaint, Prediction, PredictionLocation, Alert
from backend.app.auth.security import create_access_token
from fastapi.testclient import TestClient
from backend.app.main import app


def test_prediction_idempotency_repeat_post():
    client = TestClient(app)
    token = create_access_token({"sub": "admin@cybershield.gov.in", "role": "I4C_ADMIN"})
    client.headers["Authorization"] = f"Bearer {token}"

    ts = int(time.time())
    c_num_expected = f"CMP-IDEMP-TEST-{ts}"
    complaint_payload = {
        "victim_name": "Idempotency Test Complainant",
        "fraud_type": "UPI / QR Code Fraud",
        "amount": 150000.0,
        "district": "Central Delhi",
        "locality": "Connaught Place",
        "payment_channel": "UPI",
        "victim_bank": "SBI",
        "beneficiary_bank": "HDFC",
        "beneficiary_id": "mule.idemp@okhdfc",
        "transaction_ref": f"UTR-IDEMP-{ts}",
        "description": "Idempotency verification complaint.",
    }

    res_comp = client.post("/api/v1/complaints", json=complaint_payload)
    assert res_comp.status_code in (200, 201), f"Complaint creation failed: {res_comp.text}"
    c_data = res_comp.json()
    c_id = c_data["id"]
    c_num = c_data["complaint_number"]
    print(f"Complaint created: {c_num} (ID: {c_id})")

    # Run 1: First prediction POST
    res1 = client.post(f"/api/v1/predictions/{c_num}")
    assert res1.status_code == 200, f"Run 1 failed: {res1.text}"
    data1 = res1.json()
    print("DATA1 IS:", data1)
    pred_id_1 = data1["prediction_id"]
    assert pred_id_1 > 0
    print(f"Run 1 success: prediction_id={pred_id_1}, mode={data1['prediction_mode']}, model={data1['model_version']}")

    db = db_mod.SessionLocal()
    count_preds_1 = db.query(Prediction).filter(Prediction.complaint_id == c_id).count()
    count_locs_1 = db.query(PredictionLocation).filter(PredictionLocation.prediction_id == pred_id_1).count()
    assert count_preds_1 == 1, f"Expected 1 prediction, got {count_preds_1}"
    assert count_locs_1 == 3, f"Expected 3 locations, got {count_locs_1}"
    print(f"DB verification after Run 1: Predictions={count_preds_1}, PredictionLocations={count_locs_1}")
    db.close()

    # Sleep 6 seconds to prove idempotency holds well beyond any 5s window
    print("Waiting 6 seconds to verify idempotency across debounce boundary...")
    time.sleep(6)

    # Run 2: Second prediction POST (must reuse existing prediction)
    res2 = client.post(f"/api/v1/predictions/{c_num}")
    assert res2.status_code == 200, f"Run 2 failed: {res2.text}"
    data2 = res2.json()
    pred_id_2 = data2["prediction_id"]
    assert pred_id_2 == pred_id_1, f"Expected reused prediction_id {pred_id_1}, got {pred_id_2}"
    print(f"Run 2 success: prediction_id={pred_id_2} (reused existing #{pred_id_1})")

    db = db_mod.SessionLocal()
    count_preds_2 = db.query(Prediction).filter(Prediction.complaint_id == c_id).count()
    count_locs_2 = db.query(PredictionLocation).filter(PredictionLocation.prediction_id == pred_id_1).count()
    total_locs_for_complaint = (
        db.query(PredictionLocation)
        .join(Prediction, PredictionLocation.prediction_id == Prediction.id)
        .filter(Prediction.complaint_id == c_id)
        .count()
    )
    assert count_preds_2 == 1, f"Prediction count must remain 1, got {count_preds_2}"
    assert count_locs_2 == 3, f"PredictionLocation count must remain 3, got {count_locs_2}"
    assert total_locs_for_complaint == 3, f"Total locations for complaint must remain 3, got {total_locs_for_complaint}"
    print(f"DB verification after Run 2: Predictions={count_preds_2} (0 new), PredictionLocations={total_locs_for_complaint} (0 new)")

    # Run 3: Third prediction POST immediately
    res3 = client.post(f"/api/v1/predictions/{c_num}")
    assert res3.status_code == 200
    assert res3.json()["prediction_id"] == pred_id_1
    count_preds_3 = db.query(Prediction).filter(Prediction.complaint_id == c_id).count()
    assert count_preds_3 == 1
    print(f"Run 3 success: prediction_id still {pred_id_1}, count remains 1")

    # Test Alert creation idempotency
    res_alert1 = client.post(f"/api/v1/alerts/prediction/{pred_id_1}")
    assert res_alert1.status_code in (200, 201), f"Alert 1 failed: {res_alert1.text}"
    alert1_id = res_alert1.json()["id"]
    print(f"Alert 1 created: alert_id={alert1_id}")

    res_alert2 = client.post(f"/api/v1/alerts/prediction/{pred_id_1}")
    assert res_alert2.status_code in (200, 201), f"Alert 2 failed: {res_alert2.text}"
    alert2_id = res_alert2.json()["id"]
    assert alert2_id == alert1_id, f"Expected reused alert_id {alert1_id}, got {alert2_id}"
    print(f"Alert 2 reused: alert_id={alert2_id} (0 duplicate alerts)")

    alerts_count = db.query(Alert).filter(Alert.prediction_id == pred_id_1).count()
    assert alerts_count == 1, f"Expected exactly 1 alert, got {alerts_count}"
    print(f"Alert count for prediction #{pred_id_1} remains exactly 1")

    db.close()
    print("ALL IDEMPOTENCY CHECKS PASSED: SUCCESS!")


if __name__ == "__main__":
    test_prediction_idempotency_repeat_post()
