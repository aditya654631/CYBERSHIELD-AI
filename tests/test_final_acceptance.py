"""
Final Pre-Push Acceptance Test for CyberShield AI.
Verifies controlled demo complaint vs real complaint invariants.
"""
import pytest
import json
import hashlib
from fastapi.testclient import TestClient
from backend.app.models.models import Complaint, Account, ComplaintAccount, Transaction, Withdrawal, Prediction, Alert, ATMLocation


def test_controlled_demo_acceptance(auth_client: TestClient, db):
    """
    Step 4: Controlled Demo Acceptance Test
    Creates one fresh demo complaint with demo_mode=True and asserts:
    - 6 account entities
    - 5 persisted transactions
    - 3 transaction hops
    - 2 withdrawals
    - 8 total graph nodes
    - 7 total graph edges
    - 2 ATM cash-out endpoints
    - is_potential_mule_indicator correctly assigned
    """
    demo_payload = {
        "victim_name": "Test Demo Citizen",
        "victim_account": "ACC-DEMO-SRC-99",
        "victim_bank": "State Bank of India",
        "suspect_account": "ACC-DEMO-MULE-A9",
        "suspect_bank": "HDFC Bank",
        "amount": 250000.0,
        "incident_time": "2026-09-21T10:00:00Z",
        "fraud_type": "UPI Fraud",
        "description": "Controlled demo multi-hop test",
        "state": "Delhi",
        "district": "Central Delhi",
        "city": "New Delhi",
        "demo_mode": True
    }
    res_demo = auth_client.post("/api/v1/complaints/", json=demo_payload)
    assert res_demo.status_code in (200, 201), f"Create demo complaint failed: {res_demo.text}"
    demo_c_data = res_demo.json()
    demo_c_num = demo_c_data["complaint_number"]
    assert demo_c_data.get("provenance_mode") == "CONTROLLED_SYNTHETIC_DEMO"

    # Query Graph
    graph_res = auth_client.get(f"/api/v1/complaints/{demo_c_num}/graph")
    assert graph_res.status_code == 200, f"Graph failed: {graph_res.text}"
    graph_data = graph_res.json()

    # Query DB entities
    comp_row = db.query(Complaint).filter(Complaint.complaint_number == demo_c_num).first()
    assert comp_row is not None
    ca_rows = db.query(ComplaintAccount).filter(ComplaintAccount.complaint_id == comp_row.id).all()
    acc_count = len(ca_rows)
    acc_ids = [ca.account_id for ca in ca_rows]

    tx_count = db.query(Transaction).filter(Transaction.complaint_id == comp_row.id).count()
    wd_count = db.query(Withdrawal).filter(Withdrawal.account_id.in_(acc_ids)).count()

    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])
    for n in nodes:
        print("NODE:", n.get("data", {}).get("id"), n.get("data", {}).get("label"), "type:", n.get("data", {}).get("node_type"), "mule_indicator:", n.get("data", {}).get("is_potential_mule_indicator"), "risk:", n.get("data", {}).get("risk_score"))
    mule_nodes = [n for n in nodes if n.get("data", {}).get("is_potential_mule_indicator") is True]
    atm_nodes = [n for n in nodes if n.get("data", {}).get("node_type") == "atm"]

    print("\n--- CONTROLLED DEMO METRICS ---")
    print(f"complaint number: {demo_c_num}")
    print(f"provenance_mode: {demo_c_data.get('provenance_mode')}")
    print(f"account rows: {acc_count}")
    print(f"transaction rows: {tx_count}")
    print(f"transaction hop depth: {graph_data.get('metrics', {}).get('transaction_hop_depth')}")
    print(f"withdrawal rows: {wd_count}")
    print(f"graph nodes: {len(nodes)}")
    print(f"graph edges: {len(edges)}")
    print(f"potential mule indicators: {len(mule_nodes)}")
    print(f"ATM endpoint count: {len(atm_nodes)}")

    # Exact assertions as specified in requirements
    assert acc_count == 6
    assert tx_count == 5
    assert graph_data.get("metrics", {}).get("transaction_hop_depth") == 3
    assert wd_count == 2
    assert len(nodes) == 8
    assert len(edges) == 7
    assert len(atm_nodes) == 2
    assert len(mule_nodes) >= 1


def test_real_complaint_safety(auth_client: TestClient, db):
    """
    Step 5: Real Complaint Safety Test
    Creates a fresh demo_mode=false officer complaint and asserts:
    - DIRECT_OFFICER_INPUT
    - 2 account nodes / rows
    - 1 transaction edge / row
    - 1 hop depth
    - 0 synthetic downstream accounts
    - 0 synthetic withdrawals
    """
    real_payload = {
        "victim_name": "Officer Input Citizen",
        "victim_account": "ACC-REAL-SRC-01",
        "victim_bank": "Punjab National Bank",
        "suspect_account": "ACC-REAL-DST-01",
        "suspect_bank": "ICICI Bank",
        "amount": 75000.0,
        "incident_time": "2026-09-21T11:00:00Z",
        "fraud_type": "Investment Scam",
        "description": "Real officer intake without demo mode",
        "state": "Delhi",
        "district": "South Delhi",
        "city": "New Delhi",
        "demo_mode": False
    }
    res_real = auth_client.post("/api/v1/complaints/", json=real_payload)
    assert res_real.status_code in (200, 201), f"Create real complaint failed: {res_real.text}"
    real_c_data = res_real.json()
    real_c_num = real_c_data["complaint_number"]
    assert real_c_data.get("provenance_mode") == "DIRECT_OFFICER_INPUT"

    real_comp_row = db.query(Complaint).filter(Complaint.complaint_number == real_c_num).first()
    assert real_comp_row is not None
    real_ca_rows = db.query(ComplaintAccount).filter(ComplaintAccount.complaint_id == real_comp_row.id).all()
    real_acc_count = len(real_ca_rows)
    real_acc_ids = [ca.account_id for ca in real_ca_rows]

    real_tx_count = db.query(Transaction).filter(Transaction.complaint_id == real_comp_row.id).count()
    real_wd_count = db.query(Withdrawal).filter(Withdrawal.account_id.in_(real_acc_ids)).count() if real_acc_ids else 0

    real_graph_res = auth_client.get(f"/api/v1/complaints/{real_c_num}/graph")
    assert real_graph_res.status_code == 200, f"Real graph failed: {real_graph_res.text}"
    real_graph_data = real_graph_res.json()
    real_nodes = real_graph_data.get("nodes", [])
    real_edges = real_graph_data.get("edges", [])

    print("\n--- REAL COMPLAINT METRICS ---")
    print(f"complaint number: {real_c_num}")
    print(f"provenance_mode: {real_c_data.get('provenance_mode')}")
    print(f"account rows: {real_acc_count}")
    print(f"account nodes: {len(real_nodes)}")
    print(f"transaction rows: {real_tx_count}")
    print(f"transaction edges: {len(real_edges)}")
    print(f"transaction hop depth: {real_graph_data.get('metrics', {}).get('transaction_hop_depth')}")
    print(f"synthetic downstream accounts: {real_acc_count - 2}")
    print(f"synthetic withdrawals: {real_wd_count}")

    # Exact assertions as specified in requirements
    assert real_acc_count == 2
    assert len(real_nodes) == 2
    assert real_tx_count == 1
    assert len(real_edges) == 1
    assert real_graph_data.get("metrics", {}).get("transaction_hop_depth") == 1
    assert real_acc_count - 2 == 0
    assert real_wd_count == 0


def test_system_modules_flow_and_idempotency(auth_client: TestClient, db):
    """
    Verify Complaint creation, Prediction, Case Intelligence, Risk Map,
    Alert, Transaction Network, and Refresh/idempotency.
    """
    # 1. Create Complaint
    payload = {
        "victim_name": "Demo System Test User",
        "victim_account": "ACC-SYS-SRC-01",
        "victim_bank": "State Bank of India",
        "suspect_account": "ACC-SYS-DST-01",
        "suspect_bank": "HDFC Bank",
        "amount": 180000.0,
        "incident_time": "2026-09-21T09:00:00Z",
        "fraud_type": "UPI Fraud",
        "description": "System flow verification complaint",
        "state": "Delhi",
        "district": "Central Delhi",
        "city": "New Delhi",
        "demo_mode": True
    }
    c_res = auth_client.post("/api/v1/complaints/", json=payload)
    assert c_res.status_code in (200, 201)
    c_num = c_res.json()["complaint_number"]

    # 2. Prediction PASS
    pred_res = auth_client.post(f"/api/v1/predictions/{c_num}")
    assert pred_res.status_code == 200
    pred_data = pred_res.json()
    pred_id = pred_data.get("prediction_id") or pred_data.get("id")
    assert pred_id is not None

    # 3. Case Intelligence PASS
    ci_res = auth_client.get(f"/api/v1/complaints/{c_num}")
    assert ci_res.status_code == 200

    # 4. Risk Map PASS
    rm_res = auth_client.get(f"/api/v1/risk-map/prediction/{c_num}")
    assert rm_res.status_code == 200

    # 5. Alert PASS
    alert_res = auth_client.post(f"/api/v1/alerts/prediction/{pred_id}")
    assert alert_res.status_code == 200

    # 6. Transaction Network PASS
    tn_res = auth_client.get(f"/api/v1/complaints/{c_num}/graph")
    assert tn_res.status_code == 200

    # 7. Refresh/Idempotency PASS
    tn_res_cached = auth_client.get(f"/api/v1/complaints/{c_num}/graph")
    assert tn_res_cached.status_code == 200
    assert tn_res.json() == tn_res_cached.json()


def test_v7_artifacts_integrity():
    """
    Verify SHA-256 baseline hashes for all V7 ML artifacts.
    """
    with open("ml/artifacts/model_metadata_v7_compat.json", "r") as f:
        v7_meta = json.load(f)
    artifacts = v7_meta.get("artifacts", {})
    assert len(artifacts) > 0
    for name, art_info in artifacts.items():
        fname = art_info["file"]
        expected_hash = art_info["sha256"]
        fpath = f"ml/artifacts/{fname}"
        with open(fpath, "rb") as f:
            actual_hash = hashlib.sha256(f.read()).hexdigest()
        assert actual_hash == expected_hash, f"Hash mismatch for {fname}"
