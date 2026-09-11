"""
CyberShield AI — Final ML Quality Improvement & Contract Verification Suite
Verifies:
1. Raw candidate % absent from Case Intelligence
2. Raw candidate % absent from Alerts
3. Raw candidate % absent from Risk Map
4. No $ sign in INR-only operational UI
5. INR formatter correct
6. Feature vectors differ across diverse cases
7. Candidate sets are deterministic
8. Model artifacts deterministic
9. Operational priority rules documented & graded
10. No forced HIGH
11. No random prediction
12. New model version loaded only if accepted
13. GIS/Alert same Prediction ID remains intact
"""

import re
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.models.db import SessionLocal
from backend.app.models.models import Complaint, Prediction, PredictionLocation, Alert
from backend.app.services.prediction_service import (
    PredictionService,
    MLPredictionProvider,
    CandidateLocationGenerator,
    compute_operational_priority
)
from backend.app.auth.security import create_access_token

client = TestClient(app)

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_1_raw_candidate_pct_absent_from_case_intelligence_reasoning():
    """Requirement A1: Officer-facing reasoning must not contain raw percentages."""
    db = SessionLocal()
    try:
        service = PredictionService()
        complaint = db.query(Complaint).filter(Complaint.state == "Delhi").first()
        assert complaint is not None

        pred = service.run_prediction(db, complaint.id)
        assert pred is not None
        assert len(pred.locations) == 3

        for loc in pred.locations:
            reasoning = loc.reasoning or ""
            # Must NOT contain percentage symbol or calibrated probability
            assert "%" not in reasoning, f"Raw percentage found in reasoning: {reasoning}"
            assert "calibrated probability" not in reasoning.lower(), f"calibrated probability found: {reasoning}"
            assert "probability" not in reasoning.lower(), f"probability found: {reasoning}"
            # Must match standard officer-facing text
            if loc.rank == 1:
                assert "Ranked #1 by Location" in reasoning
            else:
                assert f"Ranked #{loc.rank} candidate zone" in reasoning
    finally:
        db.close()


def test_2_raw_candidate_pct_absent_from_alerts_ui():
    """Requirement A2: AlertCenter UI must not display raw percentage risk score."""
    alerts_file = ROOT_DIR / "frontend" / "src" / "pages" / "AlertsCenter.tsx"
    assert alerts_file.exists()
    content = alerts_file.read_text(encoding="utf-8")

    assert "formatRisk" not in content, "formatRisk still present in AlertsCenter.tsx"
    assert "Risk Score:" not in content, "Risk Score: still present in AlertsCenter.tsx"
    assert "%" not in re.findall(r"Risk Score[^<]*", content)


def test_3_raw_candidate_pct_absent_from_risk_map():
    """Requirement A3: RiskMap popup must not display raw candidate percentage likelihoods."""
    risk_map = ROOT_DIR / "frontend" / "src" / "maps" / "UnifiedRiskMap.tsx"
    leaflet_map = ROOT_DIR / "frontend" / "src" / "maps" / "LeafletFallbackMap.tsx"

    for file_path in [risk_map, leaflet_map]:
        assert file_path.exists()
        content = file_path.read_text(encoding="utf-8")
        assert "Candidate Likelihood:" not in content, f"Candidate Likelihood: found in {file_path.name}"
        assert "Calibrated ML Probability:" not in content, f"Calibrated ML Probability: found in {file_path.name}"
        assert "PRIMARY" in content
        assert "SECONDARY" in content
        assert "TERTIARY" in content


def test_4_no_dollar_sign_in_inr_operational_ui():
    """Requirement B: Alert Center and operational files must not use dollar icons or signs."""
    alerts_file = ROOT_DIR / "frontend" / "src" / "pages" / "AlertsCenter.tsx"
    content = alerts_file.read_text(encoding="utf-8")
    assert "<DollarSign" not in content, "DollarSign icon JSX found in AlertsCenter.tsx"
    assert "DollarSign" not in content, "DollarSign import found in AlertsCenter.tsx"
    # Verify no currency dollar before numbers like $15,000 or $ 15,000
    assert re.search(r"\$\s*\d+", content) is None, "Literal currency dollar sign found before digits"


def test_5_inr_formatter_correct():
    """Requirement B: Centralized INR formatter produces clean ₹ currency strings without $."""
    formatters_file = ROOT_DIR / "frontend" / "src" / "utils" / "formatters.ts"
    assert formatters_file.exists()
    content = formatters_file.read_text(encoding="utf-8")
    assert "formatINR" in content
    assert "currency: 'INR'" in content or 'currency: "INR"' in content
    assert "maximumFractionDigits: 0" in content


def test_6_feature_vectors_differ_across_diverse_cases():
    """Requirement C2: Feature vectors must genuinely differ across diverse DB complaints."""
    from backend.app.services.ml_feature_service import build_location_features, build_time_features
    db = SessionLocal()
    try:
        complaints = db.query(Complaint).filter(Complaint.state == "Delhi").limit(4).all()
        assert len(complaints) >= 4

        time_vectors = []
        loc_matrices = []
        for comp in complaints:
            loc_res = build_location_features(db, comp.id, top_k=5)
            time_res = build_time_features(db, comp.id)
            time_vectors.append(tuple(time_res["values"]))
            loc_matrices.append(loc_res["candidate_rows"])

        # Distinct time feature vectors across distinct complaints
        assert len(set(time_vectors)) > 1, "Time feature vectors are all identical!"

        # Candidate feature matrices differ
        diff_count = 0
        for i in range(len(loc_matrices) - 1):
            if not np.array_equal(loc_matrices[i], loc_matrices[i + 1]):
                diff_count += 1
        assert diff_count > 0, "Location candidate feature matrices are all identical!"
    finally:
        db.close()


def test_7_candidate_sets_are_deterministic():
    """Requirement 7: Candidate sets must be fully deterministic."""
    gen = CandidateLocationGenerator()
    c = {"district": "SOUTH_DELHI", "victim_lat": 28.5244, "victim_lon": 77.2066}
    set1 = [x["cluster_id"] for x in gen.generate_candidates_for_complaint(c, top_k=10)]
    set2 = [x["cluster_id"] for x in gen.generate_candidates_for_complaint(c, top_k=10)]
    assert set1 == set2, "Candidate generation is non-deterministic!"


def test_8_model_artifacts_deterministic():
    """Requirement 8: Model predictions on identical input must produce identical results."""
    db = SessionLocal()
    try:
        provider = MLPredictionProvider()
        comp = db.query(Complaint).filter(Complaint.state == "Delhi").first()
        assert comp is not None

        res1 = provider.predict(comp, db)
        res2 = provider.predict(comp, db)

        assert [l["cluster_id"] for l in res1["top_locations"]] == [l["cluster_id"] for l in res2["top_locations"]]
        assert [l["rank"] for l in res1["top_locations"]] == [l["rank"] for l in res2["top_locations"]]
        assert (
            res1["time_prediction"]["predicted_minutes_to_cashout"]
            == res2["time_prediction"]["predicted_minutes_to_cashout"]
        )
    finally:
        db.close()


def test_9_operational_priority_rules_documented():
    """Requirement E & 9: Operational priority is graded across rank, amount, and time window."""
    now = datetime.utcnow()

    # Rank 1, High amount (>= 150k), urgent cashout (<= 90 min), recent -> CRITICAL
    p1 = compute_operational_priority(1, 150000.0, 45.0, now, now)
    assert p1 == "CRITICAL"

    # Rank 1, moderate amount (50k), window 75 min -> HIGH
    p2 = compute_operational_priority(1, 50000.0, 75.0, now, now)
    assert p2 == "HIGH"

    # Rank 2, high amount (120k) -> MEDIUM
    p3 = compute_operational_priority(2, 120000.0, 100.0, now, now)
    assert p3 == "MEDIUM"

    # Rank 3, low amount (5k), long window (180 min) -> LOW
    p4 = compute_operational_priority(3, 5000.0, 180.0, now, now)
    assert p4 == "LOW"


def test_10_no_forced_high():
    """Requirement 10: Low-urgency, low-value cases must remain LOW, not forced HIGH."""
    now = datetime.utcnow()
    # Rank 3, low amount, long window
    p = compute_operational_priority(3, 3000.0, 240.0, now - timedelta(hours=10), now)
    assert p == "LOW", f"Expected LOW for low urgency case, got {p}"


def test_11_no_random_prediction():
    """Requirement 11: Prediction pipeline contains zero random generation."""
    service_file = ROOT_DIR / "backend" / "app" / "services" / "prediction_service.py"
    content = service_file.read_text(encoding="utf-8")
    assert "random.choice" not in content
    assert "np.random.choice" not in content
    assert "random.random()" not in content


def test_12_new_model_version_loaded_only_if_accepted():
    """Requirement 12: V4/V3 loaded only because promotion status was accepted."""
    provider = MLPredictionProvider()
    assert provider.metadata.get("promotion_status", {}).get("location_v4_accepted") is True
    assert provider.metadata.get("promotion_status", {}).get("time_v3_accepted") is True
    assert provider.model_version == "cashout-location-xgb-v4"


def test_13_gis_and_alert_same_prediction_id_intact():
    """Requirement 13 & Preservation: Prediction ID matches across GIS and Alert."""
    db = SessionLocal()
    try:
        ref = f"TXN-INT-{int(datetime.utcnow().timestamp())}"
        payload = {
            "victim_name": "Ramesh Integrity",
            "fraud_type": "Investment Scam",
            "amount": 125000.0,
            "incident_time": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
            "reported_at": datetime.utcnow().isoformat(),
            "state": "Delhi",
            "district": "New Delhi",
            "locality": "Connaught Place",
            "victim_location": "Connaught Place, New Delhi, Delhi",
            "victim_lat": 28.6315,
            "victim_lon": 77.2167,
            "payment_channel": "UPI",
            "victim_bank": "State Bank of India",
            "beneficiary_bank": "HDFC Bank",
            "beneficiary_id": "synthetic.mule.rg@okhdfc",
            "transaction_ref": ref,
            "transaction_time": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
            "description": "Victim enticed by fraudulent online investment platform.",
            "ifsc_code": "HDFC0000001",
            "beneficiary_account": "50100998877665",
            "beneficiary_upi": "synthetic.mule.rg@okhdfc",
        }
        token = create_access_token({"sub": "admin@cybershield.gov.in", "role": "I4C_ADMIN"})
        auth_headers = {"Authorization": f"Bearer {token}"}
        res_comp = client.post(
            "/api/v1/complaints",
            json=payload,
            headers=auth_headers
        )
        assert res_comp.status_code in (200, 201)
        c_data = res_comp.json()
        c_num = c_data["complaint_number"]

        # Run prediction
        res_pred = client.post(f"/api/v1/predictions/{c_num}", headers=auth_headers)
        assert res_pred.status_code == 200
        p_data = res_pred.json()
        pred_id = p_data["prediction_id"]
        assert pred_id > 0

        # GIS GET
        gis_resp = client.get(f"/api/v1/risk-map/prediction/{c_num}", headers=auth_headers)
        assert gis_resp.status_code == 200
        gis_data = gis_resp.json()
        assert gis_data["prediction_id"] == pred_id

        # Alert POST from prediction
        alert_resp = client.post(
            f"/api/v1/alerts/prediction/{pred_id}",
            headers=auth_headers
        )
        assert alert_resp.status_code == 200
        alert_data = alert_resp.json()
        assert alert_data["prediction_id"] == pred_id
    finally:
        db.close()
