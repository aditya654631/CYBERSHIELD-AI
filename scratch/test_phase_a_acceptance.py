from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.models.db import SessionLocal
from backend.app.models.models import Complaint, Prediction, Alert
from backend.app.auth.security import create_access_token

client = TestClient(app)

def test_acceptance():
    print("=== VISUAL & CONTRACT ACCEPTANCE CHECKS ===")
    
    # 1. Verify CMP-NEW-000126
    db = SessionLocal()
    comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000126").first()
    assert comp is not None, "CMP-NEW-000126 not found in DB"
    print(f"[OK] CMP-NEW-000126 exists (DB ID: {comp.id}, Amount: INR {comp.amount})")

    # 2. Verify Prediction #277
    pred = db.query(Prediction).filter(Prediction.id == 277).first()
    assert pred is not None, "Prediction #277 not found in DB"
    assert pred.complaint_id == comp.id
    assert pred.prediction_mode == "trained_ml"
    assert pred.model_version == "cashout-location-xgb-v3.1"
    print(f"[OK] Prediction #277 exists (Mode: {pred.prediction_mode}, Model: {pred.model_version})")

    # 3. Verify Alert #97
    alert = db.query(Alert).filter(Alert.id == 97).first()
    assert alert is not None, "Alert #97 not found in DB"
    assert alert.complaint_id == comp.id
    assert alert.prediction_id == 277
    print(f"[OK] Alert #97 exists (Title: {alert.title}, Status: {alert.status})")

    # 4. Authenticated fetch of Prediction via API
    token = create_access_token({"sub": "admin@cybershield.gov.in", "role": "I4C_ADMIN"})
    headers = {"Authorization": f"Bearer {token}"}
    
    resp_pred = client.get(f"/api/v1/predictions/CMP-NEW-000126")
    assert resp_pred.status_code == 200, f"Get prediction failed: {resp_pred.text}"
    p_data = resp_pred.json()
    print(f"[OK] GET /api/v1/predictions/CMP-NEW-000126 returned latest Prediction #{p_data['prediction_id']}")
    assert p_data["prediction_mode"] == "trained_ml"
    assert p_data["model_version"] in ("cashout-location-xgb-v3.1", "cashout-location-xgb-v4")
    assert len(p_data["top_locations"]) >= 3
    print(f"[OK] GET /api/v1/predictions/CMP-NEW-000126 returned Prediction #{p_data['prediction_id']}")
    print(f"     Top-3 Locations:")
    for loc in p_data["top_locations"][:3]:
        print(f"       - Rank #{loc['rank']} {loc['cluster_name']} (Prob: {loc['probability']:.3f})")
    print(f"     Time Window: {p_data['time_prediction']['operational_window']}")

    # 5. Auth /me test
    resp_me = client.get("/api/v1/auth/me", headers=headers)
    assert resp_me.status_code == 200
    user_data = resp_me.json()
    assert user_data["email"] == "admin@cybershield.gov.in"
    assert user_data["full_name"] == "Dr. Vikramaditya Sen"
    print(f"[OK] GET /api/v1/auth/me: {user_data['full_name']} ({user_data['role']})")

    db.close()
    print("=== ALL ACCEPTANCE CHECKS PASSED ===")

if __name__ == "__main__":
    test_acceptance()
