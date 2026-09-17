"""
Phase 6: Readable Transaction Network Layout & Graph Contract Verification Tests
Validates graph telemetry contracts, non-mutation invariants, directional integrity,
role representations, and compatibility with the deterministic layered layout.
"""

from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.auth.security import create_access_token
from backend.app.models.db import SessionLocal
from backend.app.models.models import (
    Complaint, Account, Transaction, ComplaintAccount, Withdrawal, Prediction, ATMLocation
)
from backend.app.services.graph_service import (
    build_complaint_graph,
    _empty_graph_response
)
from backend.app.services.transaction_context_service import resolve_transaction_context

client = TestClient(app)
_test_token = create_access_token({"sub": "admin@cybershield.gov.in", "role": "I4C_ADMIN"})
auth_headers = {"Authorization": f"Bearer {_test_token}"}


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def hermetic_graph_fixtures(db: Session):
    """
    Seeds a self-contained multi-hop transaction trail with an ATM cash-out endpoint
    and an unlinked empty complaint for hermetic Phase 6 contract testing.
    """
    now = datetime.now(timezone.utc)

    # 1. Multi-hop Complaint
    complaint = db.query(Complaint).filter_by(complaint_number="CMP-P6-MULTI").first()
    if not complaint:
        complaint = Complaint(
            complaint_number="CMP-P6-MULTI",
            fraud_type="UPI Fraud",
            amount=85000.0,
            victim_location="Connaught Place, Delhi",
            state="Delhi",
            district="CENTRAL_NEW_DELHI",
            payment_channel="UPI",
            reported_at=now,
            case_status="UNDER_INVESTIGATION",
            risk_level="HIGH",
            risk_score=0.88,
        )
        db.add(complaint)
        db.flush()

        # Accounts: Victim -> Intermediary -> Mule
        vic_acc = Account(
            account_number="P6-ACC-VIC-001",
            masked_account="ACC••••1001",
            holder_name="Victim Account",
            bank_name="HDFC Bank",
            risk_score=0.05,
            is_mule=False,
        )
        inter_acc = Account(
            account_number="P6-ACC-INT-002",
            masked_account="ACC••••2002",
            holder_name="Intermediary Rapid Layer",
            bank_name="Axis Bank",
            risk_score=0.65,
            is_mule=False,
        )
        mule_acc = Account(
            account_number="P6-ACC-MUL-003",
            masked_account="ACC••••3003",
            holder_name="Flagged Cashout Mule",
            bank_name="State Bank of India",
            risk_score=0.92,
            is_mule=True,
        )
        db.add_all([vic_acc, inter_acc, mule_acc])
        db.flush()

        # Link victim as SOURCE and mule as BENEFICIARY
        ca_vic = ComplaintAccount(
            complaint_id=complaint.id,
            account_id=vic_acc.id,
            association_type="SOURCE",
        )
        ca_mule = ComplaintAccount(
            complaint_id=complaint.id,
            account_id=mule_acc.id,
            association_type="BENEFICIARY",
        )
        db.add_all([ca_vic, ca_mule])
        db.flush()

        # Transactions: Vic -> Inter (85k), Inter -> Mule (80k)
        tx1 = Transaction(
            transaction_ref="TX-P6-001",
            complaint_id=complaint.id,
            sender_account_id=vic_acc.id,
            receiver_account_id=inter_acc.id,
            amount=85000.0,
            payment_channel="UPI",
            timestamp=now - timedelta(minutes=45),
            suspicious_flag=False,
        )
        tx2 = Transaction(
            transaction_ref="TX-P6-002",
            complaint_id=complaint.id,
            sender_account_id=inter_acc.id,
            receiver_account_id=mule_acc.id,
            amount=80000.0,
            payment_channel="IMPS",
            timestamp=now - timedelta(minutes=30),
            suspicious_flag=True,
        )
        db.add_all([tx1, tx2])
        db.flush()

        # ATM withdrawal terminal
        atm = db.query(ATMLocation).first()
        if atm:
            wdl = Withdrawal(
                account_id=mule_acc.id,
                atm_id=atm.id,
                amount=75000.0,
                timestamp=now - timedelta(minutes=15),
                success=True,
                camera_flagged=True,
            )
            db.add(wdl)
            db.flush()

        db.commit()

    # 2. Empty Complaint (No transactions)
    empty_comp = db.query(Complaint).filter_by(complaint_number="CMP-P6-EMPTY").first()
    if not empty_comp:
        empty_comp = Complaint(
            complaint_number="CMP-P6-EMPTY",
            fraud_type="Job Fraud",
            amount=15000.0,
            victim_location="Dwarka, Delhi",
            state="Delhi",
            district="SOUTH_WEST",
            payment_channel="NEFT",
            reported_at=now,
            case_status="REGISTERED",
            risk_level="PENDING_EVALUATION",
        )
        db.add(empty_comp)
        db.commit()

    return {
        "multi_complaint": complaint,
        "empty_complaint": empty_comp,
    }


# ==============================================================================
# 1. GRAPH PAYLOAD CONTRACT & COUNT CONSERVATION
# ==============================================================================

def test_phase6_graph_endpoint_contract(db: Session, hermetic_graph_fixtures):
    """Verifies that the graph API returns a well-formed Phase 6 GraphData payload."""
    comp = hermetic_graph_fixtures["multi_complaint"]

    response = client.get(
        f"/api/v1/complaints/{comp.complaint_number}/graph",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()

    assert "nodes" in data
    assert "edges" in data
    assert "metrics" in data

    # Count conservation: node array length == metrics.node_count
    assert len(data["nodes"]) == data["metrics"]["node_count"]
    assert len(data["edges"]) == data["metrics"]["edge_count"]
    assert data["metrics"]["node_count"] >= 3
    assert data["metrics"]["edge_count"] >= 2

    # Each node contains required fields for rendering and layered layout
    for node in data["nodes"]:
        nd = node["data"]
        assert "id" in nd
        assert "label" in nd
        assert "node_type" in nd
        assert "masked_id" in nd
        assert "bank" in nd
        assert "risk_score" in nd
        assert "amount_received" in nd
        assert "amount_sent" in nd
        assert "connections_count" in nd
        assert "hop_level" in nd
        assert nd["masked_id"] != ""

    # Each edge contains source, target, amount, hop
    node_ids = {n["data"]["id"] for n in data["nodes"]}
    for edge in data["edges"]:
        ed = edge["data"]
        assert "id" in ed
        assert "source" in ed
        assert "target" in ed
        assert "amount" in ed
        assert "hop" in ed
        # Referential integrity: source and target must exist in node set
        assert ed["source"] in node_ids
        assert ed["target"] in node_ids
        assert ed["amount"] >= 0


def test_phase6_zero_mutation_invariant(db: Session, hermetic_graph_fixtures):
    """Verifies that requesting the graph does not mutate any DB rows or generate side effects."""
    comp = hermetic_graph_fixtures["multi_complaint"]

    tx_count_before = db.query(Transaction).count()
    acc_count_before = db.query(Account).count()
    comp_count_before = db.query(Complaint).count()
    pred_count_before = db.query(Prediction).count()

    # Call graph generation multiple times
    _ = build_complaint_graph(db, comp.id)
    _ = client.get(f"/api/v1/complaints/{comp.complaint_number}/graph", headers=auth_headers)
    _ = build_complaint_graph(db, comp.id)

    # Invariant: Counts must remain identical
    assert db.query(Transaction).count() == tx_count_before
    assert db.query(Account).count() == acc_count_before
    assert db.query(Complaint).count() == comp_count_before
    assert db.query(Prediction).count() == pred_count_before


def test_phase6_directional_and_amount_invariance(db: Session, hermetic_graph_fixtures):
    """Verifies that edge directions and amounts exactly match underlying transactions."""
    comp = hermetic_graph_fixtures["multi_complaint"]

    graph = build_complaint_graph(db, comp.id)
    ctx = resolve_transaction_context(db, comp)

    inter_account_edges = [
        e for e in graph["edges"]
        if not str(e["data"].get("channel", "")).upper().startswith("ATM")
    ]
    inter_account_edge_amount = sum(e["data"]["amount"] for e in inter_account_edges)
    total_ctx_amount = sum(float(tx.amount) for tx in ctx["transactions"])
    assert inter_account_edge_amount == pytest.approx(total_ctx_amount, rel=1e-2)

    # ATM withdrawal edges match physical cash-out records
    atm_edges = [
        e for e in graph["edges"]
        if str(e["data"].get("channel", "")).upper().startswith("ATM")
    ]
    if atm_edges:
        total_atm_amount = sum(e["data"]["amount"] for e in atm_edges)
        assert total_atm_amount == pytest.approx(75000.0, rel=1e-2)

    # Referential and flow validity
    node_map = {n["data"]["id"]: n["data"] for n in graph["nodes"]}
    for edge in graph["edges"]:
        src_id = edge["data"]["source"]
        tgt_id = edge["data"]["target"]
        assert src_id in node_map
        assert tgt_id in node_map
        assert node_map[tgt_id]["amount_received"] > 0


def test_phase6_empty_complaint_graph_honesty(db: Session, hermetic_graph_fixtures):
    """Verifies that an unlinked or transaction-less complaint returns honest empty telemetry."""
    empty_comp = hermetic_graph_fixtures["empty_complaint"]

    graph = build_complaint_graph(db, empty_comp.id)
    assert graph["nodes"] == []
    assert graph["edges"] == []
    assert graph["metrics"]["node_count"] == 0
    assert graph["metrics"]["edge_count"] == 0
    assert graph["metrics"]["max_hop"] == 0


def test_phase6_role_classification_contract(db: Session, hermetic_graph_fixtures):
    """Verifies that node roles are classified legitimately without defamatory hardcoding."""
    comp = hermetic_graph_fixtures["multi_complaint"]

    graph = build_complaint_graph(db, comp.id)
    roles = {n["data"]["node_type"] for n in graph["nodes"]}

    assert "victim" in roles
    victim_nodes = [n for n in graph["nodes"] if n["data"]["node_type"] == "victim"]
    assert len(victim_nodes) >= 1
    assert victim_nodes[0]["data"]["is_source"] is True
    assert victim_nodes[0]["data"]["hop_level"] == 0


def test_phase6_unauthenticated_access_rejected():
    """Verifies that graph endpoint strictly rejects unauthenticated calls (HTTP 401)."""
    response = client.get("/api/v1/complaints/CMP-P6-MULTI/graph")
    assert response.status_code == 401
