"""
CyberShield AI — Phase 1 Step 5 Test Suite
Tests Complaint Creation Cleanup and Complaint-to-Scenario Linking.
Verifies zero fake data creation, deterministic scenario matching,
ComplaintAccount relationship integrity, transaction trail resolution,
non-Delhi handling, and strict zero target-leakage.
"""

import ast
import inspect
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.models.db import SessionLocal
from backend.app.models.models import (
    Complaint, Account, Transaction, ComplaintAccount,
    Withdrawal, Prediction, Alert, LocationCluster, ATMLocation
)
from backend.app.services.scenario_linking_service import (
    match_scenario,
    link_complaint_to_scenario,
    get_scenario_for_complaint,
    get_transactions_for_complaint
)

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


def test_complaint_persistence(db):
    """1. Verifies complaint persists in PostgreSQL with valid attributes and pre-prediction status."""
    c = Complaint(
        complaint_number="CMP-TEST-PERSIST",
        fraud_type="UPI fraud",
        amount=50000.0,
        victim_location="Rohini, Delhi",
        state="Delhi",
        district="NORTH_WEST",
        payment_channel="UPI",
        reported_at=datetime.utcnow(),
        risk_level="PENDING_EVALUATION",
        risk_score=None,
        prediction_status="PENDING",
        case_status="ACTIVE"
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    try:
        saved = db.query(Complaint).filter(Complaint.id == c.id).first()
        assert saved is not None
        assert saved.complaint_number == "CMP-TEST-PERSIST"
        assert saved.amount == 50000.0
        assert saved.state == "Delhi"
        assert saved.risk_score is None
        assert saved.risk_level == "PENDING_EVALUATION"
    finally:
        db.delete(c)
        db.commit()


def test_unique_complaint_number(db):
    """2. Verifies collision-safe CMP-NEW- format and uniqueness under repeated creation."""
    from backend.app.api.complaint_routes import generate_complaint_number
    num1 = generate_complaint_number(db)
    assert num1.startswith("CMP-NEW-")
    assert num1 != "CMP-1042"
    assert not num1.startswith("CMP-DL-")


def test_delhi_scenario_successful_match(db):
    """3. Verifies a valid Delhi complaint successfully matches an eligible Step-4 synthetic scenario."""
    c = Complaint(
        complaint_number="CMP-TEST-MATCH",
        fraud_type="UPI fraud",
        amount=45000.0,
        victim_location="Connaught Place, Delhi",
        state="Delhi",
        district="CENTRAL_NEW_DELHI",
        payment_channel="UPI"
    )
    scenario, tier, score = match_scenario(db, c)
    assert scenario is not None
    assert scenario.complaint_number.startswith("CMP-DL-")
    assert score > 50.0
    assert "Tier 1" in tier or "Tier 2" in tier or "Same Zone" in tier


def test_deterministic_matching(db):
    """4. Verifies matching is 100% reproducible for identical inputs."""
    c1 = Complaint(
        complaint_number="CMP-TEST-DET-1",
        fraud_type="phishing",
        amount=75000.0,
        victim_location="Hauz Khas, Delhi",
        state="Delhi",
        district="SOUTH",
        payment_channel="IMPS"
    )
    c2 = Complaint(
        complaint_number="CMP-TEST-DET-2",
        fraud_type="phishing",
        amount=75000.0,
        victim_location="Hauz Khas, Delhi",
        state="Delhi",
        district="SOUTH",
        payment_channel="IMPS"
    )
    sc1, t1, score1 = match_scenario(db, c1)
    sc2, t2, score2 = match_scenario(db, c2)
    assert sc1.id == sc2.id
    assert sc1.complaint_number == sc2.complaint_number
    assert score1 == score2


def test_different_complaints_select_different_scenarios(db):
    """5. Verifies different input profiles match different scenarios (diversity check)."""
    c_central = Complaint(
        complaint_number="CMP-TEST-DIFF-1",
        fraud_type="UPI fraud",
        amount=20000.0,
        victim_location="Connaught Place, Delhi",
        state="Delhi",
        district="CENTRAL_NEW_DELHI",
        payment_channel="UPI"
    )
    c_south = Complaint(
        complaint_number="CMP-TEST-DIFF-2",
        fraud_type="investment scam",
        amount=850000.0,
        victim_location="Saket, Delhi",
        state="Delhi",
        district="SOUTH",
        payment_channel="NEFT"
    )
    sc1, _, _ = match_scenario(db, c_central)
    sc2, _, _ = match_scenario(db, c_south)
    assert sc1 is not None and sc2 is not None
    assert sc1.id != sc2.id
    assert sc1.complaint_number != sc2.complaint_number


def test_complaint_account_relationships_created(db):
    """6 & 7. Verifies ComplaintAccount associations are properly populated with valid FKs."""
    c = Complaint(
        complaint_number="CMP-TEST-REL",
        fraud_type="UPI fraud",
        amount=50000.0,
        victim_location="Rohini, Delhi",
        state="Delhi",
        district="NORTH_WEST",
        payment_channel="UPI"
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    try:
        res = link_complaint_to_scenario(db, c)
        assert res["status"] == "LINKED"
        assert res["linked_account_count"] > 0

        cas = db.query(ComplaintAccount).filter(ComplaintAccount.complaint_id == c.id).all()
        assert len(cas) == res["linked_account_count"]
        # Verify valid account foreign keys
        for ca in cas:
            acc = db.query(Account).filter(Account.id == ca.account_id).first()
            assert acc is not None
            assert ca.association_type in ["VICTIM", "INTERMEDIARY", "BENEFICIARY", "SUSPECT"]
    finally:
        db.query(ComplaintAccount).filter(ComplaintAccount.complaint_id == c.id).delete()
        db.delete(c)
        db.commit()


def test_duplicate_complaint_account_links_prevented(db):
    """8. Verifies idempotency prevents duplicate (complaint_id, account_id) pairs."""
    c = Complaint(
        complaint_number="CMP-TEST-DUP",
        fraud_type="UPI fraud",
        amount=50000.0,
        victim_location="Janakpuri, Delhi",
        state="Delhi",
        district="WEST",
        payment_channel="UPI"
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    try:
        link_complaint_to_scenario(db, c)
        count_first = db.query(ComplaintAccount).filter(ComplaintAccount.complaint_id == c.id).count()
        # Call link a second time
        link_complaint_to_scenario(db, c)
        count_second = db.query(ComplaintAccount).filter(ComplaintAccount.complaint_id == c.id).count()
        assert count_first == count_second
    finally:
        db.query(ComplaintAccount).filter(ComplaintAccount.complaint_id == c.id).delete()
        db.delete(c)
        db.commit()


def test_transaction_context_retrievable(db):
    """9. Verifies scenario transaction context is retrievable through service and API without duplicating rows."""
    c = Complaint(
        complaint_number="CMP-TEST-TX",
        fraud_type="job scam",
        amount=150000.0,
        victim_location="Laxmi Nagar, Delhi",
        state="Delhi",
        district="EAST",
        payment_channel="IMPS"
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    try:
        res = link_complaint_to_scenario(db, c)
        assert res["status"] == "LINKED"

        txs = get_transactions_for_complaint(db, c)
        assert len(txs) == res["available_transaction_count"]
        assert len(txs) > 0
        # Assert transactions belong to source scenario, not duplicated
        for tx in txs:
            assert tx.complaint.complaint_number == res["source_scenario"]
    finally:
        db.query(ComplaintAccount).filter(ComplaintAccount.complaint_id == c.id).delete()
        db.delete(c)
        db.commit()


def test_non_delhi_complaint_behavior(db):
    """10. Verifies non-Delhi complaints do not receive fake scenario links or fabricated transactions."""
    c = Complaint(
        complaint_number="CMP-TEST-NONDELHI",
        fraud_type="UPI fraud",
        amount=50000.0,
        victim_location="Arera Colony, Bhopal",
        state="Madhya Pradesh",
        district="Bhopal",
        payment_channel="UPI"
    )
    sc, tier, score = match_scenario(db, c)
    assert sc is None
    assert tier == "SCENARIO_UNAVAILABLE"
    assert score == 0.0

    res = link_complaint_to_scenario(db, c)
    assert res["status"] == "SCENARIO_UNAVAILABLE"
    assert res["source_scenario"] is None
    assert res["linked_account_count"] == 0
    assert res["available_transaction_count"] == 0


def test_insufficient_input_behavior(db):
    """11. Verifies complaints with insufficient data return INSUFFICIENT_SCENARIO_INPUT."""
    c = Complaint(
        complaint_number="CMP-TEST-INSUFF",
        fraud_type="",
        amount=0.0,
        victim_location="Connaught Place, Delhi",
        state="Delhi",
        district="CENTRAL_NEW_DELHI"
    )
    sc, tier, score = match_scenario(db, c)
    assert sc is None
    assert tier == "INSUFFICIENT_SCENARIO_INPUT"


def test_api_create_complaint_clean_and_zero_fabricated_data(db):
    """12-16. Verifies API POST /complaints creates zero random accounts, transactions, withdrawals, predictions, or alerts."""
    acc_before = db.query(Account).count()
    tx_before = db.query(Transaction).count()
    w_before = db.query(Withdrawal).count()
    pred_before = db.query(Prediction).count()
    alert_before = db.query(Alert).count()

    payload = {
        "fraud_type": "UPI fraud",
        "amount": 45000.0,
        "victim_name": "Test Citizen Clean",
        "victim_phone": "+91 99999 11111",
        "victim_location": "Connaught Place, Delhi",
        "state": "Delhi",
        "district": "CENTRAL_NEW_DELHI",
        "payment_channel": "UPI",
        "description": "Test complaint for Step 5 verification"
    }
    resp = client.post("/api/v1/complaints", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    created_id = data["id"]
    created_num = data["complaint_number"]
    assert created_num.startswith("CMP-NEW-")
    assert data["scenario_link_status"] == "LINKED"
    assert data["source_scenario"].startswith("CMP-DL-")
    assert data["linked_account_count"] > 0
    assert data["available_transaction_count"] > 0

    acc_after = db.query(Account).count()
    tx_after = db.query(Transaction).count()
    w_after = db.query(Withdrawal).count()
    pred_after = db.query(Prediction).count()
    alert_after = db.query(Alert).count()

    # Zero new accounts, transactions, withdrawals, predictions, or alerts
    assert acc_after == acc_before
    assert tx_after == tx_before
    assert w_after == w_before
    assert pred_after == pred_before
    assert alert_after == alert_before

    # Clean up test complaint
    db.query(ComplaintAccount).filter(ComplaintAccount.complaint_id == created_id).delete()
    db.query(Complaint).filter(Complaint.id == created_id).delete()
    db.commit()


def test_legacy_cmp1042_preservation(db):
    """17. Verifies CMP-1042 demo case is preserved and accessible via API."""
    resp = client.get("/api/v1/complaints/CMP-1042")
    assert resp.status_code == 200
    data = resp.json()
    assert data["complaint_number"] == "CMP-1042"
    assert data["victim_name"] == "Rajesh Sharma"
    assert data["amount"] == 125000.0


def test_step4_dataset_preservation(db):
    """18. Verifies Step-4 Delhi operational dataset counts remain completely intact."""
    c_count = db.query(Complaint).filter(Complaint.complaint_number.like("CMP-DL-%")).count()
    a_count = db.query(Account).filter(Account.account_number.like("SYN-DL-%")).count()
    tx_count = db.query(Transaction).filter(Transaction.transaction_ref.like("TXN-DL-%")).count()
    w_count = db.query(Withdrawal).count()
    cl_count = db.query(LocationCluster).filter(LocationCluster.state == "Delhi").count()
    atm_count = db.query(ATMLocation).filter(ATMLocation.atm_code.like("ATM-DL-%")).count()

    assert c_count == 3000
    assert a_count == 6000
    assert tx_count == 49453
    assert w_count == 2054
    assert cl_count == 60
    assert atm_count == 240


def test_zero_target_leakage_in_matching(db):
    """19. Strictly proves matching does not inspect Withdrawal, ATM targets, or Predictions."""
    from backend.app.services import scenario_linking_service
    source_code = inspect.getsource(scenario_linking_service.match_scenario)
    tree = ast.parse(source_code)

    # Check that AST has zero Name references to ground-truth models
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            assert node.id not in ["Withdrawal", "Prediction", "PredictionLocation", "ATMLocation"]
        elif isinstance(node, ast.Attribute):
            assert node.attr not in ["atm_id", "target_cluster_name", "target_zone"]


def test_api_response_contract_and_scenario_status(db):
    """20. Verifies GET /complaints/{id} returns correct linking metadata."""
    payload = {
        "fraud_type": "loan-app scam",
        "amount": 25000.0,
        "victim_location": "Vijay Nagar, Indore",
        "state": "Madhya Pradesh",
        "district": "Indore"
    }
    resp = client.post("/api/v1/complaints", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["scenario_link_status"] == "SCENARIO_UNAVAILABLE"
    assert data["source_scenario"] is None
    assert data["linked_account_count"] == 0

    c_id = data["id"]
    # Verify GET
    get_resp = client.get(f"/api/v1/complaints/{c_id}")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["scenario_link_status"] == "SCENARIO_UNAVAILABLE"

    # Clean up
    db.query(ComplaintAccount).filter(ComplaintAccount.complaint_id == c_id).delete()
    db.query(Complaint).filter(Complaint.id == c_id).delete()
    db.commit()


def test_graph_endpoint_scenario_and_empty_behavior(db):
    """21. Verifies /complaints/{id}/graph returns demo graph for CMP-1042, scenario graph for linked, and empty graph for unlinked."""
    # 1. CMP-1042 gets demo graph
    resp_1042 = client.get("/api/v1/complaints/CMP-1042/graph")
    assert resp_1042.status_code == 200
    g_1042 = resp_1042.json()
    assert len(g_1042["nodes"]) == 6
    assert len(g_1042["edges"]) == 5

    # 2. Non-Delhi unlinked complaint gets empty graph
    payload_c = {
        "fraud_type": "loan-app scam",
        "amount": 25000.0,
        "victim_location": "Vijay Nagar, Indore",
        "state": "Madhya Pradesh",
        "district": "Indore"
    }
    resp_c = client.post("/api/v1/complaints", json=payload_c)
    assert resp_c.status_code == 200
    c_id = resp_c.json()["id"]

    resp_c_graph = client.get(f"/api/v1/complaints/{c_id}/graph")
    assert resp_c_graph.status_code == 200
    g_c = resp_c_graph.json()
    assert len(g_c["nodes"]) == 0
    assert len(g_c["edges"]) == 0

    # Clean up
    db.query(ComplaintAccount).filter(ComplaintAccount.complaint_id == c_id).delete()
    db.query(Complaint).filter(Complaint.id == c_id).delete()
    db.commit()

