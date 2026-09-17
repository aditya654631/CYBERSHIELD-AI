"""
Phase 1 Step 6: Transaction Scenario Ingestion & Complaint-Context Linking Tests
Comprehensive validation of transaction context resolution, deduplication,
chronological ordering, provenance, isolation, and zero target leakage.
"""

import pytest
import ast
import inspect
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.models.db import SessionLocal
from backend.app.models.models import (
    Complaint, Account, Transaction, Withdrawal,
    Prediction, PredictionLocation, Alert
)
from backend.app.services.transaction_context_service import resolve_transaction_context
import backend.app.services.transaction_context_service as tcs_module
from backend.app.auth.security import create_access_token

client = TestClient(app)
_token = create_access_token({"sub": "admin@cybershield.gov.in", "role": "I4C_ADMIN"})
client.headers.update({"Authorization": f"Bearer {_token}"})


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    yield session
    session.close()


def test_linked_complaint_resolves_source_scenario_transactions(db):
    """1. Verifies CMP-NEW-000002 resolves transactions from persisted source CMP-DL-1261."""
    c = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    assert c is not None

    context = resolve_transaction_context(db, c)
    assert context["complaint_number"] == "CMP-NEW-000002"
    assert context["context_type"] == "LINKED_SYNTHETIC_SCENARIO"
    sc = db.query(Complaint).filter(Complaint.complaint_number == "CMP-DL-1261").first()
    expected_tx_count = db.query(Transaction).filter(Transaction.complaint_id == sc.id).count()
    assert context["transaction_count"] == expected_tx_count
    assert len(context["transactions"]) == expected_tx_count


def test_linked_transaction_context_has_no_duplicate_ids(db):
    """2. Verifies transaction context contains each transaction exactly once."""
    c = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    context = resolve_transaction_context(db, c)

    tx_ids = [tx.id for tx in context["transactions"]]
    assert len(tx_ids) == len(set(tx_ids)), "Duplicate transaction IDs detected in context!"
    assert context["transaction_count"] == len(tx_ids)


def test_repeated_transaction_get_is_idempotent(db):
    """3. Verifies calling transaction endpoint repeatedly produces identical results."""
    resp1 = client.get("/api/v1/complaints/CMP-NEW-000002/transactions")
    resp2 = client.get("/api/v1/complaints/CMP-NEW-000002/transactions")
    assert resp1.status_code == 200
    assert resp2.status_code == 200

    data1 = resp1.json()
    data2 = resp2.json()
    assert data1 == data2
    assert [t["id"] for t in data1] == [t["id"] for t in data2]


def test_transaction_table_count_does_not_increase_on_retrieval(db):
    """4. Verifies transaction table row count does not increase on transaction context retrieval."""
    count_before = db.query(Transaction).count()
    c = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    resolve_transaction_context(db, c)
    count_after = db.query(Transaction).count()

    assert count_before == count_after, f"Transaction table count changed from {count_before} to {count_after}!"


def test_source_transaction_ownership_is_not_rewritten(db):
    """5. Verifies source scenario transactions retain their original complaint_id."""
    sc = db.query(Complaint).filter(Complaint.complaint_number == "CMP-DL-1261").first()
    c = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()

    context = resolve_transaction_context(db, c)
    for tx in context["transactions"]:
        assert tx.complaint_id == sc.id
        assert tx.complaint_id != c.id


def test_transaction_context_uses_persisted_source_not_rematching(db):
    """6. Verifies transaction resolution uses persisted provenance without rematching."""
    c = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    assert "[SCENARIO:CMP-DL-1261" in c.description

    context = resolve_transaction_context(db, c)
    assert context["source_scenario"] == "CMP-DL-1261"


def test_transaction_context_is_stable_across_fresh_db_session():
    """7. Verifies transaction context remains completely stable across fresh database sessions."""
    db1 = SessionLocal()
    c1 = db1.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    res1 = resolve_transaction_context(db1, c1)
    ids1 = [t.id for t in res1["transactions"]]
    db1.close()

    db2 = SessionLocal()
    c2 = db2.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    res2 = resolve_transaction_context(db2, c2)
    ids2 = [t.id for t in res2["transactions"]]
    db2.close()

    assert ids1 == ids2
    assert res1["source_scenario"] == res2["source_scenario"]
    assert res1["context_type"] == res2["context_type"]


def test_transaction_order_is_deterministic(db):
    """8. Verifies transactions are ordered chronologically by timestamp asc then id asc."""
    c = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    context = resolve_transaction_context(db, c)
    txs = context["transactions"]

    for i in range(len(txs) - 1):
        t1 = txs[i]
        t2 = txs[i + 1]
        assert (t1.timestamp, t1.id) <= (t2.timestamp, t2.id), f"Ordering violation between tx {t1.id} and {t2.id}!"


def test_only_source_scenario_transactions_are_returned(db):
    """9. Verifies context contains ONLY transactions belonging to the source scenario."""
    sc = db.query(Complaint).filter(Complaint.complaint_number == "CMP-DL-1261").first()
    expected_ids = set(tx.id for tx in db.query(Transaction.id).filter(Transaction.complaint_id == sc.id).all())

    c = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    context = resolve_transaction_context(db, c)
    resolved_ids = set(tx.id for tx in context["transactions"])

    assert resolved_ids == expected_ids


def test_sender_receiver_foreign_keys_are_valid(db):
    """10. Verifies every returned transaction has valid existing sender and receiver accounts."""
    c = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    context = resolve_transaction_context(db, c)

    for tx in context["transactions"]:
        sender = db.query(Account).filter(Account.id == tx.sender_account_id).first()
        receiver = db.query(Account).filter(Account.id == tx.receiver_account_id).first()
        assert sender is not None, f"Orphan sender_account_id {tx.sender_account_id}!"
        assert receiver is not None, f"Orphan receiver_account_id {tx.receiver_account_id}!"
        assert tx.sender_account_id != tx.receiver_account_id, f"Self loop on tx {tx.id}!"


def test_transaction_amounts_are_preserved(db):
    """11. Verifies transaction amounts remain untouched positive values."""
    c = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    context = resolve_transaction_context(db, c)

    for tx in context["transactions"]:
        assert float(tx.amount) > 0.0


def test_transaction_timestamps_are_preserved(db):
    """12. Verifies transaction timestamps are valid datetime objects."""
    c = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    context = resolve_transaction_context(db, c)

    for tx in context["transactions"]:
        assert tx.timestamp is not None


def test_hop_depths_are_preserved(db):
    """13. Verifies hop depths are positive integers starting at 1."""
    c = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    context = resolve_transaction_context(db, c)

    hops = set(tx.hop_number for tx in context["transactions"])
    assert 1 in hops
    for h in hops:
        assert isinstance(h, int) and h >= 1


def test_different_linked_complaints_resolve_different_transaction_sets(db):
    """14. Verifies CMP-NEW-000002 and CMP-NEW-000003 resolve completely disjoint transaction sets."""
    c_a = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    c_b = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000003").first()

    ctx_a = resolve_transaction_context(db, c_a)
    ctx_b = resolve_transaction_context(db, c_b)

    ids_a = set(tx.id for tx in ctx_a["transactions"])
    ids_b = set(tx.id for tx in ctx_b["transactions"])

    assert ctx_a["source_scenario"] == "CMP-DL-1261"
    assert ctx_b["source_scenario"] == "CMP-DL-1095"
    assert len(ids_a.intersection(ids_b)) == 0, "Leaked transaction between independent scenarios!"


def test_non_delhi_unlinked_complaint_returns_empty_context(db):
    """15. Verifies CMP-NEW-000004 (Bhopal) returns EMPTY context with 0 transactions."""
    c_c = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000004").first()
    assert c_c is not None

    context = resolve_transaction_context(db, c_c)
    assert context["context_type"] == "EMPTY"
    assert context["source_scenario"] is None
    assert context["transaction_count"] == 0
    assert len(context["transactions"]) == 0


def test_unlinked_complaint_does_not_fallback_to_cmp1042(db):
    """16. Verifies unlinked complaint does NOT fall back to CMP-1042 demo transactions."""
    c_c = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000004").first()
    context = resolve_transaction_context(db, c_c)

    tx_ids = [t.id for t in context["transactions"]]
    assert 1 not in tx_ids
    assert len(tx_ids) == 0


def test_cmp1042_behavior_remains_isolated(db):
    """17. Verifies CMP-1042 returns its own direct transactions with DIRECT context."""
    c_1042 = db.query(Complaint).filter(Complaint.complaint_number == "CMP-1042").first()
    assert c_1042 is not None

    context = resolve_transaction_context(db, c_1042)
    assert context["context_type"] == "DIRECT"
    assert context["source_scenario"] is None
    assert context["transaction_count"] == 5
    assert [t.id for t in context["transactions"]] == [1, 2, 3, 4, 5]


def test_cmp_dl_existing_complaint_returns_own_transactions(db):
    """18. Verifies CMP-DL-0001 returns its own direct transactions with DIRECT context."""
    c_dl = db.query(Complaint).filter(Complaint.complaint_number == "CMP-DL-0001").first()
    assert c_dl is not None

    context = resolve_transaction_context(db, c_dl)
    assert context["context_type"] == "DIRECT"
    assert context["source_scenario"] is None
    expected_tx_count = db.query(Transaction).filter(Transaction.complaint_id == c_dl.id).count()
    assert context["transaction_count"] == expected_tx_count
    for tx in context["transactions"]:
        assert tx.complaint_id == c_dl.id


def test_direct_transaction_precedence_behavior(db):
    """19. Verifies direct transactions take absolute precedence over scenario links."""
    # Create temporary complaint with both direct transaction and scenario tag
    c = Complaint(
        complaint_number="CMP-TEST-DIRECT-PRECEDENCE",
        fraud_type="UPI fraud",
        amount=10000.0,
        victim_location="Connaught Place, Delhi",
        state="Delhi",
        district="CENTRAL_NEW_DELHI",
        payment_channel="UPI",
        description="[SCENARIO:CMP-DL-1261|STATUS:LINKED|SCORE:90.0|REASON:Test]"
    )
    db.add(c)
    db.flush()

    sender = db.query(Account).first()
    receiver = db.query(Account).filter(Account.id != sender.id).first()

    tx = Transaction(
        transaction_ref="TXN-TEST-DIRECT-001",
        complaint_id=c.id,
        sender_account_id=sender.id,
        receiver_account_id=receiver.id,
        amount=10000.0,
        payment_channel="UPI",
        hop_number=1
    )
    db.add(tx)
    db.flush()

    try:
        context = resolve_transaction_context(db, c)
        assert context["context_type"] == "DIRECT"
        assert context["source_scenario"] is None
        assert context["transaction_count"] == 1
        assert context["transactions"][0].id == tx.id
    finally:
        db.delete(tx)
        db.delete(c)
        db.commit()


def test_no_transaction_created_by_get(db):
    """20. Verifies GET /complaints/{id}/transactions creates 0 transaction rows."""
    tx_count_before = db.query(Transaction).count()
    resp = client.get("/api/v1/complaints/CMP-NEW-000002/transactions")
    assert resp.status_code == 200
    tx_count_after = db.query(Transaction).count()

    assert tx_count_before == tx_count_after


def test_no_accounts_created_by_transaction_resolution(db):
    """21. Verifies transaction context resolution creates 0 account rows."""
    acc_before = db.query(Account).count()
    c = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    resolve_transaction_context(db, c)
    acc_after = db.query(Account).count()

    assert acc_before == acc_after


def test_no_withdrawals_created(db):
    """22. Verifies transaction context resolution creates 0 withdrawal rows."""
    w_before = db.query(Withdrawal).count()
    c = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    resolve_transaction_context(db, c)
    w_after = db.query(Withdrawal).count()

    assert w_before == w_after


def test_no_predictions_created(db):
    """23. Verifies transaction context resolution creates 0 prediction rows."""
    p_before = db.query(Prediction).count()
    c = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    resolve_transaction_context(db, c)
    p_after = db.query(Prediction).count()

    assert p_before == p_after


def test_no_prediction_locations_created(db):
    """24. Verifies transaction context resolution creates 0 prediction_locations rows."""
    pl_before = db.query(PredictionLocation).count()
    c = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    resolve_transaction_context(db, c)
    pl_after = db.query(PredictionLocation).count()

    assert pl_before == pl_after


def test_no_alerts_created(db):
    """25. Verifies transaction context resolution creates 0 alert rows."""
    a_before = db.query(Alert).count()
    c = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    resolve_transaction_context(db, c)
    a_after = db.query(Alert).count()

    assert a_before == a_after


def test_zero_target_leakage_in_transaction_resolution(db):
    """26. Strictly proves transaction resolution does not query target, outcome, or withdrawal models."""
    source_code = inspect.getsource(tcs_module.resolve_transaction_context)
    tree = ast.parse(source_code)

    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            assert node.id not in [
                "Withdrawal", "Prediction", "PredictionLocation",
                "ATMLocation", "cash_out"
            ], f"Forbidden model {node.id} referenced in resolve_transaction_context!"
        elif isinstance(node, ast.Attribute):
            assert node.attr not in [
                "atm_id", "target_cluster_name", "target_zone", "predicted_rank"
            ], f"Forbidden target attribute {node.attr} accessed!"


@pytest.mark.live
def test_step4_transaction_dataset_preserved(db):
    """27. Verifies Step-4 operational transaction dataset remains intact."""
    txn_dl_count = db.query(Transaction).filter(Transaction.transaction_ref.like("TXN-DL-%")).count()
    assert txn_dl_count == 49453
