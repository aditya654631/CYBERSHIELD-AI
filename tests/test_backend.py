import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.models.db import engine, Base, SessionLocal
import backend.app.models.models
from database.seed.seed_data import seed_database

# Ensure tables and seed data exist
Base.metadata.create_all(bind=engine)
db_session = SessionLocal()
try:
    seed_database(db_session)
finally:
    db_session.close()

from backend.app.auth.security import create_access_token

client = TestClient(app)
_test_token = create_access_token({"sub": "admin@cybershield.gov.in", "role": "I4C_ADMIN"})
client.headers["Authorization"] = f"Bearer {_test_token}"

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["engine"] == "Online"
    assert "database" in data
    assert data["database"]["status"] == "connected"
    assert data["database"]["engine"] in ["sqlite", "postgresql"]


def test_auth_login_all_roles():
    roles_creds = [
        ("admin@cybershield.gov.in", "CyberAdmin@2026", "I4C_ADMIN"),
        ("state.lea@mp.police.gov.in", "StateLea@2026", "STATE_LEA"),
        ("district.lea@indore.police.gov.in", "IndoreLea@2026", "DISTRICT_LEA"),
        ("officer@sbi.co.in", "BankOfficer@2026", "BANK_OFFICER"),
        ("analyst@cybershield.gov.in", "Analyst@2026", "ANALYST"),
        ("auditor@mha.gov.in", "Auditor@2026", "AUDITOR"),
    ]
    for email, password, expected_role in roles_creds:
        resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert resp.status_code == 200, f"Login failed for {email}"
        data = resp.json()
        assert "access_token" in data
        assert data["user"]["role"] == expected_role

def test_cmp_1042_case_retrieval():
    resp = client.get("/api/v1/complaints/CMP-1042")
    assert resp.status_code == 200
    data = resp.json()
    assert data["complaint_number"] == "CMP-1042"
    assert data["fraud_type"] == "Investment Scam"
    assert data["amount"] == 125000.0
    assert "Bhopal" in data["victim_location"]

def test_cmp_1042_prediction_endpoint():
    resp = client.post("/api/v1/predictions/CMP-1042")
    assert resp.status_code == 200
    data = resp.json()
    assert data["complaint_number"] == "CMP-1042"
    assert data["where_location"] == "Vijay Nagar, Indore"
    assert data["when_window"] == "Next 2–4 Hours"
    assert data["risk_percentage"] == 87
    assert data["risk_level"] == "CRITICAL"
    assert data["intervention_priority"] == 94
    assert len(data["top_locations"]) == 3

    loc1, loc2, loc3 = data["top_locations"]
    assert "Vijay Nagar" in loc1["location_name"]
    assert loc1["probability"] == 0.87
    assert "Palasia" in loc2["location_name"]
    assert loc2["probability"] == 0.61
    assert "Rau" in loc3["location_name"]
    assert loc3["probability"] == 0.34

def test_explanation_endpoint():
    # Fetch prediction first
    pred_resp = client.get("/api/v1/predictions/CMP-1042")
    pred_id = pred_resp.json()["prediction_id"]

    resp = client.get(f"/api/v1/predictions/{pred_id}/explanation")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["factors"]) >= 5
    assert "Vijay Nagar" in data["narrative"] or "cluster" in data["narrative"]
    assert "AI-generated decision support" in data["disclaimer"]

def test_graph_endpoint():
    resp = client.get("/api/v1/complaints/CMP-1042/graph")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["nodes"]) >= 6
    assert len(data["edges"]) >= 5
    assert "metrics" in data
    assert "target_cashout_cluster" not in data["metrics"]

def test_gis_risk_map():
    resp = client.get("/api/v1/risk-map")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["hotspots"]) >= 3
    assert len(data["atms"]) >= 5
    assert len(data["summary"]["primary_threat_epicenter"]) > 0

def test_alerts_and_acknowledgement():
    resp = client.get("/api/v1/alerts")
    assert resp.status_code == 200
    alerts = resp.json()
    assert len(alerts) > 0

    first_alert = alerts[0]
    ack_resp = client.post(f"/api/v1/alerts/{first_alert['id']}/acknowledge", json={"notes": "Ground unit deployed"})
    assert ack_resp.status_code == 200
    assert ack_resp.json()["status"] == "ACKNOWLEDGED"

def test_model_performance():
    resp = client.get("/api/v1/model/performance")
    assert resp.status_code == 200
    data = resp.json()
    assert data["evaluation_label"] in ["Prototype Evaluation — Synthetic/Anonymized Demo Data", "SYNTHETIC PROTOTYPE EVALUATION"]
    assert len(data["metrics_comparison"]) >= 10

def test_audit_log():
    resp = client.get("/api/v1/audit")
    assert resp.status_code == 200
    logs = resp.json()
    assert len(logs) > 0

def test_database_connectivity_helper():
    from backend.app.models.db import check_database_connection, get_database_engine_type
    engine_type = get_database_engine_type()
    assert engine_type in ["sqlite", "postgresql"]
    res = check_database_connection()
    assert res["status"] == "connected"
    assert res["engine"] == engine_type
    assert "error" not in res

