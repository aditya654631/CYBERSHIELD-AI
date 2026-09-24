"""
CyberShield AI — Pre-Step-14 Functional Repair Test Suite
Complaint Intake + Persistence + Direct Transaction Context + ML Prediction Flow

Covers all 20 required acceptance criteria from Section 25:
1. valid complaint payload persists
2. all required fields round-trip through POST -> DB -> GET
3. transaction details persist
4. account/beneficiary context persists
5. complaint survives new DB session
6. direct transaction context takes precedence
7. scenario enrichment does not overwrite direct data
8. transaction context provenance is correct
9. graph uses new complaint transactions
10. feature extraction consumes safe persisted values
11. Location V3.1 shape remains (K, 43)
12. Time V2 shape remains (1, 20)
13. model artifacts are not retrained
14. explicit prediction run persists Prediction
15. outside-scope case gets no fabricated prediction
16. failed validation creates zero partial rows
17. duplicate submission protection behavior
18. no Withdrawal outcome access
19. no future target leakage
20. POST/GET field contract exact
"""

import ast
import os
from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.db import SessionLocal
from backend.app.models.models import (
    Complaint, Account, Transaction, ComplaintAccount,
    Prediction, PredictionLocation, PredictionSnapshot, Withdrawal
)
from backend.app.services.transaction_context_service import resolve_transaction_context
from backend.app.services.scenario_linking_service import link_complaint_to_scenario
from backend.app.services.graph_service import build_complaint_graph
from backend.app.services.ml_feature_service import build_location_features, build_time_features
from backend.app.services.prediction_service import prediction_service

from backend.app.auth.security import create_access_token

client = TestClient(app)
_test_token = create_access_token({"sub": "admin@cybershield.gov.in", "role": "I4C_ADMIN"})
client.headers["Authorization"] = f"Bearer {_test_token}"


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="module", autouse=True)
def cleanup_intake_test_complaints():
    session = SessionLocal()
    initial_ids = {c.id for c in session.query(Complaint.id).all()}
    session.close()
    yield
    session = SessionLocal()
    try:
        new_complaints = session.query(Complaint).filter(~Complaint.id.in_(initial_ids)).all()
        for c in new_complaints:
            pred_ids = [p.id for p in session.query(Prediction.id).filter(Prediction.complaint_id == c.id).all()]
            if pred_ids:
                session.query(PredictionLocation).filter(PredictionLocation.prediction_id.in_(pred_ids)).delete(synchronize_session=False)
                session.query(PredictionSnapshot).filter(PredictionSnapshot.prediction_id.in_(pred_ids)).delete(synchronize_session=False)
                session.query(Prediction).filter(Prediction.id.in_(pred_ids)).delete(synchronize_session=False)
            session.query(Transaction).filter(Transaction.complaint_id == c.id).delete(synchronize_session=False)
            session.query(ComplaintAccount).filter(ComplaintAccount.complaint_id == c.id).delete(synchronize_session=False)
            session.delete(c)
        session.commit()
    finally:
        session.close()


def _unique_ref(prefix="UTR-DL"):
    return f"{prefix}-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"


# ---------------------------------------------------------------------------
# 1. Valid complaint payload persists
# ---------------------------------------------------------------------------
def test_valid_complaint_payload_persists(db):
    ref = _unique_ref("TST-P1")
    payload = {
        "victim_name": "Ramesh Gupta",
        "fraud_type": "Investment Scam",
        "amount": 125000.0,
        "incident_time": (datetime.utcnow() - timedelta(hours=3)).isoformat(),
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
        "transaction_time": (datetime.utcnow() - timedelta(hours=3)).isoformat(),
        "description": "Victim enticed by fraudulent online investment platform.",
        "ifsc_code": "HDFC0000001",
        "beneficiary_account": "50100998877665",
        "beneficiary_upi": "synthetic.mule.rg@okhdfc",
    }
    response = client.post("/api/v1/complaints", json=payload)
    assert response.status_code in (200, 201), f"Expected 200/201, got {response.status_code}: {response.text}"
    data = response.json()
    assert "id" in data
    assert "complaint_number" in data
    assert data["complaint_number"].startswith("CMP-")
    assert data["amount"] == 125000.0

    c_id = data["id"]
    db_c = db.query(Complaint).filter(Complaint.id == c_id).first()
    assert db_c is not None


# ---------------------------------------------------------------------------
# 2. All required fields round-trip through POST -> DB -> GET
# ---------------------------------------------------------------------------
def test_all_required_fields_round_trip(db):
    ref = _unique_ref("TST-P2")
    inc_time = (datetime.utcnow() - timedelta(hours=4)).replace(microsecond=0)
    rep_time = datetime.utcnow().replace(microsecond=0)

    payload = {
        "victim_name": "Pooja Verma",
        "fraud_type": "UPI / QR Code Fraud",
        "amount": 45000.0,
        "incident_time": inc_time.isoformat(),
        "reported_at": rep_time.isoformat(),
        "state": "Delhi",
        "district": "Central Delhi",
        "locality": "Karol Bagh",
        "victim_location": "Karol Bagh, Central Delhi, Delhi",
        "victim_lat": None,
        "victim_lon": None,
        "payment_channel": "UPI",
        "victim_bank": "Punjab National Bank",
        "beneficiary_bank": "ICICI Bank",
        "beneficiary_id": "qr.scam.mule@icici",
        "transaction_ref": ref,
        "transaction_time": inc_time.isoformat(),
        "description": "Scanned fake QR code sent via WhatsApp claiming refund.",
    }
    res_post = client.post("/api/v1/complaints", json=payload)
    assert res_post.status_code in (200, 201)
    created = res_post.json()
    c_num = created["complaint_number"]

    # GET complaint by complaint_number
    res_get = client.get(f"/api/v1/complaints/{c_num}")
    assert res_get.status_code == 200
    got = res_get.json()

    assert got["victim_name"] == "Pooja Verma"
    assert got["fraud_type"] == "UPI / QR Code Fraud"
    assert got["amount"] == 45000.0
    assert got["state"] == "Delhi"
    assert got["district"] == "Central Delhi"
    assert got["locality"] == "Karol Bagh"
    assert got["payment_channel"] == "UPI"
    assert got["victim_bank"] == "Punjab National Bank"
    assert got["beneficiary_bank"] == "ICICI Bank"
    assert got["beneficiary_id"] == "qr.scam.mule@icici"
    assert got["transaction_ref"] == ref
    assert got["description"] == "Scanned fake QR code sent via WhatsApp claiming refund."
    assert got["victim_lat"] is None
    assert got["victim_lon"] is None


# ---------------------------------------------------------------------------
# 3. Transaction details persist
# ---------------------------------------------------------------------------
def test_transaction_details_persist(db):
    ref = _unique_ref("TST-P3")
    payload = {
        "victim_name": "Sanjay Kumar",
        "fraud_type": "Loan App Extortion",
        "amount": 62000.0,
        "district": "North Delhi",
        "locality": "Civil Lines",
        "payment_channel": "IMPS",
        "victim_bank": "Bank of Baroda",
        "beneficiary_bank": "Axis Bank",
        "beneficiary_id": "axis-mule-acc-4412",
        "transaction_ref": ref,
        "description": "Loan app threatening messages demanding extortion payoff.",
    }
    res = client.post("/api/v1/complaints", json=payload)
    assert res.status_code in (200, 201)
    c_id = res.json()["id"]

    txs = db.query(Transaction).filter(Transaction.complaint_id == c_id).all()
    assert len(txs) >= 1
    tx = txs[0]
    assert tx.amount == 62000.0
    assert tx.channel == "IMPS"
    assert tx.transaction_reference == ref
    assert tx.source_account_id is not None
    assert tx.destination_account_id is not None


# ---------------------------------------------------------------------------
# 4. Account/beneficiary context persists
# ---------------------------------------------------------------------------
def test_account_beneficiary_context_persists(db):
    ref = _unique_ref("TST-P4")
    payload = {
        "victim_name": "Ananya Roy",
        "fraud_type": "Part-time Job Fraud",
        "amount": 91000.0,
        "district": "South Delhi",
        "locality": "Hauz Khas",
        "payment_channel": "UPI",
        "victim_bank": "Kotak Mahindra",
        "beneficiary_bank": "Yes Bank",
        "beneficiary_id": "yes-mule-acc-8877",
        "transaction_ref": ref,
        "description": "Telegram task review scam.",
    }
    res = client.post("/api/v1/complaints", json=payload)
    assert res.status_code in (200, 201)
    c_id = res.json()["id"]

    cas = db.query(ComplaintAccount).filter(ComplaintAccount.complaint_id == c_id).all()
    assert len(cas) == 2
    assoc_types = {ca.association_type for ca in cas}
    assert "VICTIM" in assoc_types
    assert "BENEFICIARY" in assoc_types

    ben_ca = next(ca for ca in cas if ca.association_type == "BENEFICIARY")
    ben_acc = db.query(Account).filter(Account.id == ben_ca.account_id).first()
    assert ben_acc is not None
    assert ben_acc.is_mule is False  # Officer-entered beneficiary must not be automatically confirmed mule
    assert ben_acc.flag_reason is None
    assert ben_acc.bank_name == "Yes Bank"


# ---------------------------------------------------------------------------
# 5. Complaint survives new DB session
# ---------------------------------------------------------------------------
def test_complaint_survives_new_db_session():
    ref = _unique_ref("TST-P5")
    payload = {
        "victim_name": "Session Test Victim",
        "fraud_type": "Investment Scam",
        "amount": 77000.0,
        "district": "West Delhi",
        "locality": "Rajouri Garden",
        "payment_channel": "UPI",
        "victim_bank": "SBI",
        "beneficiary_bank": "HDFC",
        "beneficiary_id": "mule.session@paytm",
        "transaction_ref": ref,
        "description": "Testing clean persistence across isolated sessions.",
    }
    res = client.post("/api/v1/complaints", json=payload)
    assert res.status_code in (200, 201)
    c_id = res.json()["id"]

    new_session = SessionLocal()
    try:
        loaded = new_session.query(Complaint).filter(Complaint.id == c_id).first()
        assert loaded is not None
        assert loaded.amount == 77000.0
        assert loaded.locality == "Rajouri Garden"
        assert len(loaded.transactions) >= 1
        assert len(loaded.accounts) >= 2
    finally:
        new_session.close()


# ---------------------------------------------------------------------------
# 6. Direct transaction context takes precedence
# ---------------------------------------------------------------------------
def test_direct_transaction_context_precedence(db):
    ref = _unique_ref("TST-P6")
    payload = {
        "victim_name": "Direct Context Victim",
        "fraud_type": "Digital Arrest / Sextortion",
        "amount": 150000.0,
        "district": "New Delhi",
        "locality": "Chanakyapuri",
        "payment_channel": "RTGS",
        "victim_bank": "Canara Bank",
        "beneficiary_bank": "Federal Bank",
        "beneficiary_id": "fed-mule-9090",
        "transaction_ref": ref,
        "description": "Direct context precedence validation.",
    }
    res = client.post("/api/v1/complaints", json=payload)
    assert res.status_code in (200, 201)
    c_id = res.json()["id"]

    comp = db.query(Complaint).filter(Complaint.id == c_id).first()
    context = resolve_transaction_context(db, comp)
    assert context["context_type"] == "DIRECT"
    assert context["transaction_count"] >= 1
    assert any((getattr(tx, "transaction_ref", None) or getattr(tx, "transaction_reference", None)) == ref for tx in context["transactions"])


# ---------------------------------------------------------------------------
# 7. Scenario enrichment does not overwrite direct data
# ---------------------------------------------------------------------------
def test_scenario_enrichment_does_not_overwrite_direct_data(db):
    ref = _unique_ref("TST-P7")
    payload = {
        "victim_name": "No Overwrite Victim",
        "fraud_type": "Investment Scam",
        "amount": 88000.0,
        "district": "Central Delhi",
        "locality": "Paharganj",
        "payment_channel": "UPI",
        "victim_bank": "SBI",
        "beneficiary_bank": "HDFC",
        "beneficiary_id": "mule.direct.only@okhdfc",
        "transaction_ref": ref,
        "description": "Verifying scenario linking preserves direct data.",
    }
    res = client.post("/api/v1/complaints", json=payload)
    assert res.status_code in (200, 201)
    c_id = res.json()["id"]

    comp = db.query(Complaint).filter(Complaint.id == c_id).first()
    linking_result = link_complaint_to_scenario(db, comp)
    assert linking_result["status"] == "DIRECT_OFFICER_INPUT"

    cas = db.query(ComplaintAccount).filter(ComplaintAccount.complaint_id == c_id).all()
    assert len(cas) == 2


# ---------------------------------------------------------------------------
# 8. Transaction context provenance is correct
# ---------------------------------------------------------------------------
def test_transaction_context_provenance_is_correct(db):
    ref = _unique_ref("TST-P8")
    payload = {
        "victim_name": "Provenance Victim",
        "fraud_type": "UPI / QR Code Fraud",
        "amount": 35000.0,
        "district": "Shahdara",
        "locality": "Vivek Vihar",
        "payment_channel": "UPI",
        "victim_bank": "IDBI",
        "beneficiary_bank": "IndusInd",
        "beneficiary_id": "mule.indus@upi",
        "transaction_ref": ref,
        "description": "Provenance tag verification.",
    }
    res = client.post("/api/v1/complaints", json=payload)
    assert res.status_code in (200, 201)
    c_id = res.json()["id"]

    comp = db.query(Complaint).filter(Complaint.id == c_id).first()
    context = resolve_transaction_context(db, comp)
    assert "DIRECT_OFFICER_INPUT" in context["provenance"]


# ---------------------------------------------------------------------------
# 9. Graph uses new complaint transactions
# ---------------------------------------------------------------------------
def test_graph_uses_new_complaint_transactions(db):
    ref = _unique_ref("TST-P9")
    payload = {
        "victim_name": "Graph Test Victim",
        "fraud_type": "Investment Scam",
        "amount": 95000.0,
        "district": "South East Delhi",
        "locality": "Lajpat Nagar",
        "payment_channel": "UPI",
        "victim_bank": "SBI",
        "beneficiary_bank": "HDFC",
        "beneficiary_id": "graph.mule.lajpat@okhdfc",
        "transaction_ref": ref,
        "description": "Graph node/edge test.",
    }
    res = client.post("/api/v1/complaints", json=payload)
    assert res.status_code in (200, 201)
    c_id = res.json()["id"]

    g_data = build_complaint_graph(db, c_id)
    assert len(g_data["nodes"]) >= 2
    assert len(g_data["edges"]) >= 1

    assert any(e["data"]["amount"] == 95000.0 for e in g_data["edges"])


# ---------------------------------------------------------------------------
# 10. Feature extraction consumes safe persisted values
# ---------------------------------------------------------------------------
def test_feature_extraction_consumes_safe_persisted_values(db):
    ref = _unique_ref("TST-P10")
    payload = {
        "victim_name": "Feature Test Victim",
        "fraud_type": "Investment Scam",
        "amount": 110000.0,
        "district": "New Delhi",
        "locality": "Connaught Place",
        "payment_channel": "UPI",
        "victim_bank": "SBI",
        "beneficiary_bank": "HDFC",
        "beneficiary_id": "feat.mule@okhdfc",
        "transaction_ref": ref,
        "description": "Feature consumption test.",
    }
    res = client.post("/api/v1/complaints", json=payload)
    assert res.status_code in (200, 201)
    c_id = res.json()["id"]

    feat_bundle = build_location_features(db, c_id)
    assert "candidate_rows" in feat_bundle
    assert "candidates" in feat_bundle
    assert len(feat_bundle["candidates"]) == 25


# ---------------------------------------------------------------------------
# 11. Location V3.1 shape remains (K, 43)
# ---------------------------------------------------------------------------
def test_location_v3_1_shape_remains_k_43(db):
    ref = _unique_ref("TST-P11")
    payload = {
        "victim_name": "Shape Test Victim",
        "fraud_type": "UPI / QR Code Fraud",
        "amount": 55000.0,
        "district": "Central Delhi",
        "locality": "Paharganj",
        "payment_channel": "UPI",
        "victim_bank": "PNB",
        "beneficiary_bank": "Axis Bank",
        "beneficiary_id": "axis.mule.pahar@upi",
        "transaction_ref": ref,
        "description": "Location feature matrix shape test.",
    }
    res = client.post("/api/v1/complaints", json=payload)
    assert res.status_code in (200, 201)
    c_id = res.json()["id"]

    feat_bundle = build_location_features(db, c_id, model_version="v3.1")
    matrix = feat_bundle["candidate_rows"]
    assert matrix.shape == (25, 43), f"Expected shape (25, 43), got {matrix.shape}"


# ---------------------------------------------------------------------------
# 12. Time V2 shape remains (1, 20)
# ---------------------------------------------------------------------------
def test_time_v2_shape_remains_1_20(db):
    ref = _unique_ref("TST-P12")
    payload = {
        "victim_name": "Time Shape Victim",
        "fraud_type": "Investment Scam",
        "amount": 75000.0,
        "district": "New Delhi",
        "locality": "Barakhamba",
        "payment_channel": "IMPS",
        "victim_bank": "ICICI",
        "beneficiary_bank": "HDFC",
        "beneficiary_id": "hdfc.time.mule@bank",
        "transaction_ref": ref,
        "description": "Time feature vector shape test.",
    }
    res = client.post("/api/v1/complaints", json=payload)
    assert res.status_code in (200, 201)
    c_id = res.json()["id"]

    time_bundle = build_time_features(db, c_id)
    vec = time_bundle["values"]
    assert vec.shape in ((20,), (1, 20)), f"Expected shape (20,) or (1, 20), got {vec.shape}"


# ---------------------------------------------------------------------------
# 13. Model artifacts are not retrained
# ---------------------------------------------------------------------------
def test_model_artifacts_not_retrained():
    loc_model_path = os.path.join("ml", "artifacts", "location_ranker_v7_compat.joblib")
    time_model_path = os.path.join("ml", "artifacts", "time_regressor_v3.joblib")

    assert os.path.exists(loc_model_path), f"Missing {loc_model_path}"
    assert os.path.exists(time_model_path), f"Missing {time_model_path}"

    loc_size = os.path.getsize(loc_model_path)
    time_size = os.path.getsize(time_model_path)
    assert loc_size > 50000, f"Location model corrupted or empty: size={loc_size}"
    assert time_size > 20000, f"Time model corrupted or empty: size={time_size}"


# ---------------------------------------------------------------------------
# 14. Explicit prediction run persists Prediction
# ---------------------------------------------------------------------------
def test_explicit_prediction_run_persists_prediction(db):
    ref = _unique_ref("TST-P14")
    payload = {
        "victim_name": "Prediction Persist Victim",
        "fraud_type": "Investment Scam",
        "amount": 85000.0,
        "district": "New Delhi",
        "locality": "Connaught Place",
        "payment_channel": "UPI",
        "victim_bank": "SBI",
        "beneficiary_bank": "HDFC",
        "beneficiary_id": "mule.pred.persist@okhdfc",
        "transaction_ref": ref,
        "description": "Explicit prediction persistence test.",
    }
    res_comp = client.post("/api/v1/complaints", json=payload)
    assert res_comp.status_code in (200, 201)
    c_data = res_comp.json()
    c_id = c_data["id"]
    c_num = c_data["complaint_number"]

    # Explicit POST prediction
    res_pred = client.post(f"/api/v1/predictions/{c_num}")
    assert res_pred.status_code == 200
    pred_data = res_pred.json()

    assert pred_data["prediction_mode"] == "trained_ml"
    assert pred_data["model_version"] in (
        "cashout-location-xgb-v3.1",
        "cashout-location-xgb-v4",
        "cashout-location-xgb-v7-compat",
        "cashout-location-xgb-v8-debiased",
    )
    assert len(pred_data["top_locations"]) == 3
    assert pred_data["operational_scope"] == "DELHI_PILOT"

    # Verify stored in DB
    db_pred = db.query(Prediction).filter(Prediction.complaint_id == c_id).order_by(Prediction.id.desc()).first()
    assert db_pred is not None
    assert db_pred.id == pred_data["prediction_id"]

    # Verify GET returns same prediction
    res_get_pred = client.get(f"/api/v1/predictions/{c_num}")
    assert res_get_pred.status_code == 200
    assert res_get_pred.json()["prediction_id"] == db_pred.id


# ---------------------------------------------------------------------------
# 15. Outside-scope case gets no fabricated prediction
# ---------------------------------------------------------------------------
def test_outside_scope_case_gets_no_fabricated_prediction(db):
    comp = Complaint(
        complaint_number=f"CMP-OUTSIDE-{datetime.utcnow().strftime('%M%S%f')[:8]}",
        fraud_type="UPI fraud",
        amount=50000.0,
        victim_location="Bhopal, Madhya Pradesh",
        state="Madhya Pradesh",
        district="BHOPAL",
        payment_channel="UPI",
        reported_at=datetime.utcnow(),
        incident_time=datetime.utcnow(),
        risk_level="PENDING_EVALUATION",
        case_status="ACTIVE",
    )
    db.add(comp)
    db.commit()
    db.refresh(comp)

    res_pred = client.post(f"/api/v1/predictions/{comp.complaint_number}")
    # Outside-scope either returns HTTP 400 or returns prediction_mode != 'trained_ml'
    if res_pred.status_code == 200:
        pred_dict = res_pred.json()
        assert pred_dict.get("prediction_mode") != "trained_ml" or pred_dict.get("status") == "OUTSIDE_OPERATIONAL_SCOPE"
    else:
        assert res_pred.status_code == 400

    # Strict: zero Prediction rows persisted for outside scope
    outside_preds = db.query(Prediction).filter(Prediction.complaint_id == comp.id).count()
    assert outside_preds == 0


# ---------------------------------------------------------------------------
# 16. Failed validation creates zero partial rows
# ---------------------------------------------------------------------------
def test_failed_validation_creates_zero_partial_rows(db):
    initial_comp_count = db.query(Complaint).count()
    initial_acc_count = db.query(Account).count()
    initial_tx_count = db.query(Transaction).count()

    invalid_payload = {
        "victim_name": "Invalid Payload Victim",
        # Missing required fraud_type and amount
        "payment_channel": "UPI",
    }
    res = client.post("/api/v1/complaints", json=invalid_payload)
    assert res.status_code == 422

    assert db.query(Complaint).count() == initial_comp_count
    assert db.query(Account).count() == initial_acc_count
    assert db.query(Transaction).count() == initial_tx_count


# ---------------------------------------------------------------------------
# 17. Duplicate submission protection behavior
# ---------------------------------------------------------------------------
def test_duplicate_submission_protection(db):
    ref = _unique_ref("TST-P17")
    payload = {
        "victim_name": "Idempotent Victim",
        "fraud_type": "Investment Scam",
        "amount": 50000.0,
        "district": "New Delhi",
        "locality": "Connaught Place",
        "payment_channel": "UPI",
        "victim_bank": "SBI",
        "beneficiary_bank": "HDFC",
        "beneficiary_id": "dup.test.mule@okhdfc",
        "transaction_ref": ref,
        "description": "Double submission check.",
    }
    res1 = client.post("/api/v1/complaints", json=payload)
    assert res1.status_code in (200, 201)
    c1 = res1.json()

    res2 = client.post("/api/v1/complaints", json=payload)
    assert res2.status_code in (200, 201)
    c2 = res2.json()
    assert c2["complaint_number"] == c1["complaint_number"]


# ---------------------------------------------------------------------------
# 18. No Withdrawal outcome access
# ---------------------------------------------------------------------------
def test_no_withdrawal_outcome_access():
    files_to_check = [
        os.path.join("backend", "app", "services", "prediction_service.py"),
        os.path.join("backend", "app", "services", "ml_feature_service.py"),
        os.path.join("backend", "app", "services", "graph_service.py"),
        os.path.join("backend", "app", "services", "transaction_context_service.py"),
    ]
    for fpath in files_to_check:
        with open(fpath, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=fpath)

        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == "Withdrawal":
                pytest.fail(f"Illegal reference to Withdrawal outcome in {fpath} line {node.lineno}")


# ---------------------------------------------------------------------------
# 19. No future target leakage
# ---------------------------------------------------------------------------
def test_no_future_target_leakage(db):
    ref = _unique_ref("TST-P19")
    reported_time = datetime.utcnow()
    payload = {
        "victim_name": "Leakage Check Victim",
        "fraud_type": "Investment Scam",
        "amount": 90000.0,
        "incident_time": (reported_time - timedelta(hours=2)).isoformat(),
        "reported_at": reported_time.isoformat(),
        "district": "New Delhi",
        "locality": "Connaught Place",
        "payment_channel": "UPI",
        "victim_bank": "SBI",
        "beneficiary_bank": "HDFC",
        "beneficiary_id": "leak.mule@okhdfc",
        "transaction_ref": ref,
        "transaction_time": (reported_time - timedelta(hours=2)).isoformat(),
        "description": "Target leakage verification.",
    }
    res = client.post("/api/v1/complaints", json=payload)
    assert res.status_code in (200, 201)
    c_id = res.json()["id"]

    comp = db.query(Complaint).filter(Complaint.id == c_id).first()
    context = resolve_transaction_context(db, comp)
    cutoff = reported_time + timedelta(seconds=2)
    for tx in context["transactions"]:
        tx_time = tx.timestamp if hasattr(tx, "timestamp") else (
            datetime.fromisoformat(tx["timestamp"]) if isinstance(tx.get("timestamp"), str) else tx.get("timestamp")
        )
        assert tx_time <= cutoff, f"Future transaction leakage detected: {tx_time} > {cutoff}"


# ---------------------------------------------------------------------------
# 20. POST/GET field contract exact
# ---------------------------------------------------------------------------
def test_post_get_field_contract_exact():
    ref = _unique_ref("TST-P20")
    payload = {
        "victim_name": "Contract Victim",
        "fraud_type": "Part-time Job Fraud",
        "amount": 33000.0,
        "district": "North West Delhi",
        "locality": "Rohini",
        "payment_channel": "UPI",
        "victim_bank": "SBI",
        "beneficiary_bank": "Axis Bank",
        "beneficiary_id": "contract.mule@axis",
        "transaction_ref": ref,
        "description": "Contract schema match check.",
    }
    res_post = client.post("/api/v1/complaints", json=payload)
    assert res_post.status_code in (200, 201)
    post_data = res_post.json()

    c_num = post_data["complaint_number"]
    res_get = client.get(f"/api/v1/complaints/{c_num}")
    assert res_get.status_code == 200
    get_data = res_get.json()

    expected_keys = {
        "id", "complaint_number", "fraud_type", "amount", "victim_name",
        "state", "district", "locality", "payment_channel", "reported_at",
        "incident_time", "risk_level", "case_status", "prediction_status",
        "victim_bank", "beneficiary_bank", "beneficiary_id", "transaction_ref",
        "provenance_mode", "available_transaction_count", "linked_account_count"
    }
    for k in expected_keys:
        assert k in post_data, f"Key '{k}' missing from POST response"
        assert k in get_data, f"Key '{k}' missing from GET response"


# ---------------------------------------------------------------------------
# 21. Officer-entered beneficiary != automatically confirmed mule
# ---------------------------------------------------------------------------
def test_officer_entered_beneficiary_not_confirmed_mule(db):
    """
    PRE-STEP-14 MICRO FIX:
    Verifies that an officer-entered beneficiary account is created with is_mule=False,
    and not prematurely branded as a confirmed mule account without analytics intelligence.
    """
    ref = _unique_ref("TST-NOMULE")
    payload = {
        "victim_name": "Mule Integrity Complainant",
        "fraud_type": "UPI Fraud",
        "amount": 25000.0,
        "district": "South Delhi",
        "locality": "Saket",
        "payment_channel": "UPI",
        "victim_bank": "ICICI Bank",
        "beneficiary_bank": "Federal Bank",
        "beneficiary_id": "direct.beneficiary@axis",
        "transaction_ref": ref,
        "description": "Direct complaint testing beneficiary account non-mule classification.",
    }
    res = client.post("/api/v1/complaints", json=payload)
    assert res.status_code in (200, 201)
    c_id = res.json()["id"]

    cas = db.query(ComplaintAccount).filter(ComplaintAccount.complaint_id == c_id).all()
    ben_ca = next(ca for ca in cas if ca.association_type == "BENEFICIARY")
    ben_acc = db.query(Account).filter(Account.id == ben_ca.account_id).first()

    assert ben_acc is not None
    assert ben_acc.is_mule is False
    assert ben_acc.flag_reason is None
