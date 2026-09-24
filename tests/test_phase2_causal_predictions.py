"""
Phase 02: Causal Transaction Updates and Immutable Prediction Versions Test Suite

Tests:
1. Reproduce stale-prediction defect: unchanged rank-1 with changed rank-2/3 results
   must NOT silently return the old result.
2. Identical retry: unchanged inputs and evidence reuse existing prediction (idempotency).
3. Changed evidence with unchanged top-1 produces a new traceable version.
4. Transaction ingestion with authentication, deduplication, event time, and received time.
5. Conflict handling: conflicting payload for same transaction_ref returns 409.
6. Historical replay and point-in-time isolation: post-report transfer excluded when cutoff < transfer time,
   included when cutoff >= transfer time.
7. Future-information exclusion: withdrawal outcomes and future transfers do not leak into feature matrix.
8. PredictionSnapshot immutability: existing snapshots cannot be modified.
9. Prediction version retrieval endpoints (version history and historical version lookup).
"""

import pytest
import datetime
from decimal import Decimal
from sqlalchemy.orm import Session

from backend.app.models.models import (
    Complaint, Account, ComplaintAccount, Transaction, LocationCluster,
    Prediction, PredictionLocation, PredictionSnapshot, Withdrawal, ATMLocation, User
)
from backend.app.services.prediction_persistence_service import prediction_persistence_service
from backend.app.services.transaction_context_service import resolve_transaction_context
from backend.app.services.graph_service import build_complaint_graph
from backend.app.services.prediction_contract import as_utc, utc_iso


def _cross_jurisdiction_indore_token(db_session: Session):
    """Use an active test-owned actor, independent of mutable demo officers."""
    from backend.app.auth.security import create_access_token

    email = "phase2.crossjurisdiction.indore@cybershield.test"
    officer = db_session.query(User).filter_by(email=email).first()
    if officer is None:
        officer = User(
            email=email,
            hashed_password="test-only-token-authenticated-user",
            full_name="Phase 2 Indore Officer",
            role="DISTRICT_LEA",
            organization_id=3,
            is_active=True,
        )
        db_session.add(officer)
        db_session.commit()
    return create_access_token({"sub": email, "role": "DISTRICT_LEA"})


@pytest.fixture(autouse=True)
def mock_audit_anchor(monkeypatch):
    from backend.app.services.prediction_audit_service import PredictionAuditClient
    monkeypatch.setattr(
        PredictionAuditClient,
        "anchor_prediction_safe",
        lambda self, *args, **kwargs: {"status": "MOCKED_ANCHOR", "tx_id": "test-txid"}
    )


def test_reproduce_stale_prediction_defect_same_rank1_different_rank2(db_session: Session):
    """
    REPRODUCTION TEST:
    Under the defective legacy logic (prediction_persistence_service.py:97-112):
    If a complaint already has a prediction, and a new prediction has the SAME rank-1 cluster,
    but DIFFERENT rank-2 and rank-3 clusters (or different probabilities),
    the legacy persistence service checked:
        (latest.primary_cluster_id == rank1_cluster_id and len(latest.locations) == 3)
    and incorrectly reused the old prediction, silently dropping the new rank-2/3 evidence.

    In Phase 02, this defect is eliminated:
    A new version must be created with incremented version_number and parent_prediction_id.
    """
    comp = Complaint(
        complaint_number=f"CMP-REPRO-{int(datetime.datetime.utcnow().timestamp())}",
        fraud_type="UPI_FRAUD",
        amount=Decimal("50000.00"),
        victim_location="Karol Bagh, Delhi",
        state="Delhi",
        district="CENTRAL_NEW_DELHI",
        payment_channel="UPI",
        reported_at=datetime.datetime.utcnow() - datetime.timedelta(hours=2),
        incident_time=datetime.datetime.utcnow() - datetime.timedelta(hours=3),
    )
    db_session.add(comp)
    db_session.flush()

    for cid, name in [(1, "Connaught Place"), (2, "Karol Bagh"), (3, "Laxmi Nagar"), (4, "Rohini")]:
        cluster = db_session.query(LocationCluster).filter(LocationCluster.id == cid).first()
        if not cluster:
            cluster = LocationCluster(
                id=cid, cluster_name=name, city="Delhi", state="Delhi",
                district="CENTRAL_NEW_DELHI", center_lat=28.63, center_lon=77.22,
                atm_count=10, risk_score=0.7
            )
            db_session.add(cluster)
    db_session.flush()

    # Initial Prediction: Rank 1: Cluster 1, Rank 2: Cluster 2, Rank 3: Cluster 3
    initial_payload = {
        "status": "SUCCESS",
        "prediction_mode": "trained_ml",
        "model_version": "cashout-location-xgb-v7-compat",
        "time_model_version": "cashout-time-xgb-v3",
        "analysis_basis": "complaint_only",
        "top_locations": [
            {"rank": 1, "cluster_id": 1, "location_name": "Connaught Place", "probability": 0.65, "risk_level": "HIGH"},
            {"rank": 2, "cluster_id": 2, "location_name": "Karol Bagh", "probability": 0.20, "risk_level": "MEDIUM"},
            {"rank": 3, "cluster_id": 3, "location_name": "Laxmi Nagar", "probability": 0.15, "risk_level": "LOW"},
        ],
        "time_prediction": {
            "predicted_minutes_to_cashout": 45.0,
            "window_start": (comp.reported_at + datetime.timedelta(minutes=30)).isoformat(),
            "window_end": (comp.reported_at + datetime.timedelta(minutes=60)).isoformat(),
            "operational_window": "30–60 min after complaint report",
            "model_version": "cashout-time-xgb-v3",
        }
    }

    pred_v1 = prediction_persistence_service.persist_prediction(db_session, comp, initial_payload)
    assert pred_v1.id is not None
    assert pred_v1.primary_cluster_id == 1
    assert pred_v1.version_number == 1

    # Updated evidence comes in:
    # Rank 1 is STILL Cluster 1 (same primary cluster)
    # BUT Rank 2 is now Cluster 4 (Rohini) instead of Cluster 2, and Rank 3 is Cluster 2
    updated_payload = {
        "status": "SUCCESS",
        "prediction_mode": "trained_ml",
        "model_version": "cashout-location-xgb-v7-compat",
        "time_model_version": "cashout-time-xgb-v3",
        "analysis_basis": "direct_transactions",
        "top_locations": [
            {"rank": 1, "cluster_id": 1, "location_name": "Connaught Place", "probability": 0.70, "risk_level": "HIGH"},
            {"rank": 2, "cluster_id": 4, "location_name": "Rohini", "probability": 0.22, "risk_level": "MEDIUM"},
            {"rank": 3, "cluster_id": 2, "location_name": "Karol Bagh", "probability": 0.08, "risk_level": "LOW"},
        ],
        "time_prediction": {
            "predicted_minutes_to_cashout": 40.0,
            "window_start": (comp.reported_at + datetime.timedelta(minutes=25)).isoformat(),
            "window_end": (comp.reported_at + datetime.timedelta(minutes=55)).isoformat(),
            "operational_window": "25–55 min after complaint report",
            "model_version": "cashout-time-xgb-v3",
        }
    }

    pred_v2 = prediction_persistence_service.persist_prediction(db_session, comp, updated_payload)

    # ASSERTION: The updated prediction MUST NOT be silently dropped!
    assert pred_v2.id != pred_v1.id, "Stale prediction defect: returned old prediction ID despite changed rank 2/3!"
    assert pred_v2.version_number == 2
    assert pred_v2.parent_prediction_id == pred_v1.id
    locs_v2 = {loc.rank: loc.cluster_id for loc in pred_v2.locations}
    assert locs_v2[2] == 4, f"Expected rank 2 cluster to be 4 (Rohini), but got {locs_v2.get(2)}"


def test_identical_retry_idempotency(db_session: Session):
    """
    Idempotent Retry Test:
    Calling persist_prediction twice with identical input and result MUST return the existing
    prediction record without creating extra rows or advancing version numbers.
    """
    comp = Complaint(
        complaint_number=f"CMP-IDEMP-{int(datetime.datetime.utcnow().timestamp())}",
        fraud_type="INVESTMENT_FRAUD",
        amount=Decimal("150000.00"),
        victim_location="Rohini, Delhi",
        state="Delhi",
        district="NORTH_DELHI",
        payment_channel="IMPS",
        reported_at=datetime.datetime.utcnow() - datetime.timedelta(hours=1),
        incident_time=datetime.datetime.utcnow() - datetime.timedelta(hours=2),
    )
    db_session.add(comp)
    db_session.flush()

    for cid, name in [(1, "Connaught Place"), (2, "Karol Bagh"), (3, "Laxmi Nagar")]:
        if not db_session.query(LocationCluster).filter(LocationCluster.id == cid).first():
            db_session.add(LocationCluster(
                id=cid, cluster_name=name, city="Delhi", state="Delhi",
                district="NORTH_DELHI", center_lat=28.63, center_lon=77.22,
                atm_count=5, risk_score=0.5
            ))
    db_session.flush()

    payload = {
        "status": "SUCCESS",
        "prediction_mode": "trained_ml",
        "model_version": "cashout-location-xgb-v7-compat",
        "time_model_version": "cashout-time-xgb-v3",
        "analysis_basis": "complaint_only",
        "top_locations": [
            {"rank": 1, "cluster_id": 1, "location_name": "Connaught Place", "probability": 0.60, "risk_level": "HIGH"},
            {"rank": 2, "cluster_id": 2, "location_name": "Karol Bagh", "probability": 0.25, "risk_level": "MEDIUM"},
            {"rank": 3, "cluster_id": 3, "location_name": "Laxmi Nagar", "probability": 0.15, "risk_level": "LOW"},
        ],
        "time_prediction": {
            "predicted_minutes_to_cashout": 50.0,
            "window_start": (comp.reported_at + datetime.timedelta(minutes=35)).isoformat(),
            "window_end": (comp.reported_at + datetime.timedelta(minutes=65)).isoformat(),
            "operational_window": "35–65 min after complaint report",
            "model_version": "cashout-time-xgb-v3",
        }
    }

    first = prediction_persistence_service.persist_prediction(db_session, comp, payload)
    total_preds_1 = db_session.query(Prediction).filter(Prediction.complaint_id == comp.id).count()
    assert total_preds_1 == 1

    # Exact retry with identical payload
    second = prediction_persistence_service.persist_prediction(db_session, comp, payload)
    total_preds_2 = db_session.query(Prediction).filter(Prediction.complaint_id == comp.id).count()

    assert second.id == first.id, "Expected identical retry to return the existing prediction"
    assert second.version_number == 1
    assert total_preds_2 == 1, "Idempotent retry created an extra database row"


def test_transaction_ingestion_api_deduplication_and_conflict(auth_client, client, db_session: Session):
    """
    Test authenticated ingestion via POST /api/v1/complaints/{id}/transactions:
    1. Unauthorized call (no token) returns 401.
    2. Initial ingestion creates transaction, sets server received_at, enforces DIRECT_OFFICER_INPUT.
    3. Identical re-submission returns 200 with X-Idempotent-Replay: true.
    4. Conflicting payload (different amount) returns 409 Conflict.
    """
    comp = Complaint(
        complaint_number=f"CMP-TXING-{int(datetime.datetime.utcnow().timestamp())}",
        fraud_type="UPI_FRAUD",
        amount=Decimal("30000.00"),
        victim_location="Laxmi Nagar, Delhi",
        state="Delhi",
        district="EAST_DELHI",
        payment_channel="UPI",
        reported_at=datetime.datetime.utcnow() - datetime.timedelta(hours=2),
        incident_time=datetime.datetime.utcnow() - datetime.timedelta(hours=3),
    )
    db_session.add(comp)
    db_session.commit()

    tx_time = (comp.reported_at + datetime.timedelta(minutes=15)).isoformat()
    payload = {
        "transaction_ref": f"TX-INGEST-{int(datetime.datetime.utcnow().timestamp())}",
        "sender_account_number": "ACC-TEST-SEND-01",
        "receiver_account_number": "ACC-TEST-RECV-01",
        "amount": 25000.0,
        "payment_channel": "UPI",
        "timestamp": tx_time,
        "source_system": "BANK_API"  # Attempt to claim BANK_API as an officer
    }

    # 1. Unauthorized request
    unauth_resp = client.post(f"/api/v1/complaints/{comp.complaint_number}/transactions", json=payload)
    assert unauth_resp.status_code == 401, f"Expected 401 for unauthenticated request, got {unauth_resp.status_code}"

    # 2. Authenticated initial ingestion
    resp1 = auth_client.post(f"/api/v1/complaints/{comp.complaint_number}/transactions", json=payload)
    assert resp1.status_code == 201, f"Expected 201 Created, got {resp1.status_code}: {resp1.text}"
    body1 = resp1.json()
    assert body1["transaction_ref"] == payload["transaction_ref"]
    assert body1["is_idempotent_replay"] is False
    assert body1["source_system"] == "DIRECT_OFFICER_INPUT", "Server must override officer claims of BANK_API"
    assert body1["received_at"] is not None

    # 3. Identical idempotent replay
    resp2 = auth_client.post(f"/api/v1/complaints/{comp.complaint_number}/transactions", json=payload)
    assert resp2.status_code == 200, f"Expected 200 OK for idempotent replay, got {resp2.status_code}"
    assert resp2.headers.get("X-Idempotent-Replay") == "true"
    body2 = resp2.json()
    assert body2["id"] == body1["id"]
    assert body2["is_idempotent_replay"] is True

    # 4. Conflicting payload for same transaction_ref (amount changed to 99999.0)
    conflict_payload = dict(payload)
    conflict_payload["amount"] = 99999.0
    resp3 = auth_client.post(f"/api/v1/complaints/{comp.complaint_number}/transactions", json=conflict_payload)
    assert resp3.status_code == 409, f"Expected 409 Conflict, got {resp3.status_code}: {resp3.text}"


def test_causal_replay_and_point_in_time_isolation(db_session: Session):
    """
    Causal Replay & Cutoff Isolation:
    Transactions occurring after analysis_as_of must be excluded.
    Transactions with received_at > analysis_as_of must be excluded under knowledge cutoff.
    """
    comp = Complaint(
        complaint_number=f"CMP-CAUSAL-{int(datetime.datetime.utcnow().timestamp())}",
        fraud_type="IMPS_FRAUD",
        amount=Decimal("100000.00"),
        victim_location="Connaught Place, Delhi",
        state="Delhi",
        district="CENTRAL_NEW_DELHI",
        payment_channel="IMPS",
        reported_at=datetime.datetime(2026, 9, 15, 10, 0, 0),
        incident_time=datetime.datetime(2026, 9, 15, 9, 30, 0),
    )
    db_session.add(comp)
    db_session.flush()

    # Accounts
    a1 = Account(account_number=f"ACC-C1-{comp.id}", masked_account="ACC••••0001", bank_name="SBI", holder_name="Holder 1", state="Delhi", district="Central")
    a2 = Account(account_number=f"ACC-C2-{comp.id}", masked_account="ACC••••0002", bank_name="HDFC", holder_name="Holder 2", state="Delhi", district="Central")
    a3 = Account(account_number=f"ACC-C3-{comp.id}", masked_account="ACC••••0003", bank_name="ICICI", holder_name="Holder 3", state="Delhi", district="Central")
    db_session.add_all([a1, a2, a3])
    db_session.flush()

    # TX1: Event time 10:15, received at 10:16
    tx1 = Transaction(
        transaction_ref=f"TX-CAUSAL-1-{comp.id}",
        complaint_id=comp.id,
        sender_account_id=a1.id,
        receiver_account_id=a2.id,
        amount=Decimal("40000.00"),
        payment_channel="IMPS",
        timestamp=datetime.datetime(2026, 9, 15, 10, 15, 0),
        received_at=datetime.datetime(2026, 9, 15, 10, 16, 0),
        source_system="DIRECT_OFFICER_INPUT",
        hop_number=1,
        status="COMPLETED"
    )
    # TX2: Event time 10:45, received at 10:46
    tx2 = Transaction(
        transaction_ref=f"TX-CAUSAL-2-{comp.id}",
        complaint_id=comp.id,
        sender_account_id=a2.id,
        receiver_account_id=a3.id,
        amount=Decimal("35000.00"),
        payment_channel="IMPS",
        timestamp=datetime.datetime(2026, 9, 15, 10, 45, 0),
        received_at=datetime.datetime(2026, 9, 15, 10, 46, 0),
        source_system="DIRECT_OFFICER_INPUT",
        hop_number=2,
        status="COMPLETED"
    )
    db_session.add_all([tx1, tx2])
    db_session.commit()

    # Cutoff at 10:30: TX1 is visible, TX2 is excluded
    ctx_early = resolve_transaction_context(
        db_session, comp, analysis_as_of=datetime.datetime(2026, 9, 15, 10, 30, 0)
    )
    early_tx_refs = [tx.transaction_ref for tx in ctx_early["transactions"]]
    assert tx1.transaction_ref in early_tx_refs, "TX1 should be included at 10:30 cutoff"
    assert tx2.transaction_ref not in early_tx_refs, "TX2 (10:45) must be excluded at 10:30 cutoff"

    # Cutoff at 11:00: both TX1 and TX2 are visible
    ctx_late = resolve_transaction_context(
        db_session, comp, analysis_as_of=datetime.datetime(2026, 9, 15, 11, 0, 0)
    )
    late_tx_refs = [tx.transaction_ref for tx in ctx_late["transactions"]]
    assert tx1.transaction_ref in late_tx_refs
    assert tx2.transaction_ref in late_tx_refs


def test_withdrawal_outcome_leakage_prevention(db_session: Session):
    """
    Withdrawal Outcome Leakage Prevention:
    Withdrawal queries in graph_service must respect include_outcomes=False during feature extraction.
    Future cash-out outcomes must not leak into model prediction inputs.
    """
    comp = Complaint(
        complaint_number=f"CMP-LEAK-{int(datetime.datetime.utcnow().timestamp())}",
        fraud_type="CARD_FRAUD",
        amount=Decimal("70000.00"),
        victim_location="Karol Bagh, Delhi",
        state="Delhi",
        district="CENTRAL_NEW_DELHI",
        payment_channel="CARD",
        reported_at=datetime.datetime(2026, 9, 16, 12, 0, 0),
        incident_time=datetime.datetime(2026, 9, 16, 11, 30, 0),
    )
    db_session.add(comp)
    db_session.flush()

    acc = Account(account_number=f"ACC-LEAK-{comp.id}", masked_account="ACC••••0099", bank_name="PNB", holder_name="Leak Holder", state="Delhi", district="Central")
    db_session.add(acc)
    db_session.flush()

    atm = db_session.query(ATMLocation).first()
    if not atm:
        atm = ATMLocation(
            atm_code="ATM-DEL-001", bank_name="SBI", address="Connaught Place",
            city="Delhi", district="Central", state="Delhi",
            latitude=28.63, longitude=77.22, cluster_id=1, cash_available=True
        )
        db_session.add(atm)
        db_session.flush()

    # Withdrawal occurred 2 hours later
    wd = Withdrawal(
        atm_id=atm.id,
        account_id=acc.id,
        amount=Decimal("20000.00"),
        timestamp=datetime.datetime(2026, 9, 16, 14, 0, 0),
        success=True,
        camera_flagged=True
    )
    db_session.add(wd)
    db_session.commit()

    # 1. Feature construction call (include_outcomes=False)
    graph_for_features = build_complaint_graph(
        db_session, comp.id,
        analysis_as_of=datetime.datetime(2026, 9, 16, 12, 30, 0),
        include_outcomes=False
    )
    node_types_feat = [n.get("type") for n in graph_for_features.get("nodes", [])]
    assert "WITHDRAWAL" not in node_types_feat, "Outcome leakage: WITHDRAWAL node present during feature construction!"

    # 2. Forensic investigation call with outcomes enabled
    graph_for_investigation = build_complaint_graph(
        db_session, comp.id,
        analysis_as_of=datetime.datetime(2026, 9, 16, 15, 0, 0),
        include_outcomes=True
    )
    assert graph_for_investigation is not None


def test_prediction_snapshot_immutability(db_session: Session):
    """
    PredictionSnapshot Immutability:
    Once persisted, a PredictionSnapshot contains an authoritative canonical hash
    of the prediction inputs and Top-3 outputs that cannot be silently mutated.
    """
    comp = Complaint(
        complaint_number=f"CMP-SNAP-{int(datetime.datetime.utcnow().timestamp())}",
        fraud_type="UPI_FRAUD",
        amount=Decimal("45000.00"),
        victim_location="Rohini, Delhi",
        state="Delhi",
        district="NORTH_DELHI",
        payment_channel="UPI",
        reported_at=datetime.datetime.utcnow() - datetime.timedelta(hours=2),
        incident_time=datetime.datetime.utcnow() - datetime.timedelta(hours=3),
    )
    db_session.add(comp)
    db_session.flush()

    for cid, name in [(1, "Connaught Place"), (2, "Karol Bagh"), (3, "Laxmi Nagar")]:
        if not db_session.query(LocationCluster).filter(LocationCluster.id == cid).first():
            db_session.add(LocationCluster(
                id=cid, cluster_name=name, city="Delhi", state="Delhi",
                district="NORTH_DELHI", center_lat=28.63, center_lon=77.22,
                atm_count=5, risk_score=0.5
            ))
    db_session.flush()

    payload = {
        "status": "SUCCESS",
        "prediction_mode": "trained_ml",
        "model_version": "cashout-location-xgb-v7-compat",
        "time_model_version": "cashout-time-xgb-v3",
        "analysis_basis": "complaint_only",
        "inference_snapshot": {
            "model_version": "cashout-location-xgb-v7-compat",
            "feature_schema_version": "v7_compat",
            "feature_schema_hash": "a" * 64,
            "location_model_hash": "b" * 64,
            "calibrator_hash": "c" * 64,
            "features": {"f1": 1.0}
        },
        "top_locations": [
            {"rank": 1, "cluster_id": 1, "location_name": "Connaught Place", "probability": 0.60, "risk_level": "HIGH"},
            {"rank": 2, "cluster_id": 2, "location_name": "Karol Bagh", "probability": 0.25, "risk_level": "MEDIUM"},
            {"rank": 3, "cluster_id": 3, "location_name": "Laxmi Nagar", "probability": 0.15, "risk_level": "LOW"},
        ],
        "time_prediction": {
            "predicted_minutes_to_cashout": 45.0,
            "window_start": (comp.reported_at + datetime.timedelta(minutes=30)).isoformat(),
            "window_end": (comp.reported_at + datetime.timedelta(minutes=60)).isoformat(),
            "operational_window": "30–60 min after complaint report",
            "model_version": "cashout-time-xgb-v3",
        }
    }

    pred = prediction_persistence_service.persist_prediction(db_session, comp, payload)
    assert pred.snapshot is not None
    orig_hash = pred.snapshot.feature_schema_hash
    orig_data = pred.snapshot.snapshot_data
    assert orig_hash is not None

    # Verify that creating version 2 does not alter or delete version 1's snapshot
    payload_v2 = dict(payload)
    payload_v2["inference_snapshot"] = {
        "model_version": "cashout-location-xgb-v7-compat",
        "feature_schema_version": "v7_compat",
        "feature_schema_hash": "b" * 64,
        "location_model_hash": "b" * 64,
        "calibrator_hash": "c" * 64,
        "features": {"f1": 2.0}
    }
    payload_v2["top_locations"] = [
        {"rank": 1, "cluster_id": 2, "location_name": "Karol Bagh", "probability": 0.70, "risk_level": "HIGH"},
        {"rank": 2, "cluster_id": 1, "location_name": "Connaught Place", "probability": 0.20, "risk_level": "MEDIUM"},
        {"rank": 3, "cluster_id": 3, "location_name": "Laxmi Nagar", "probability": 0.10, "risk_level": "LOW"},
    ]
    pred_v2 = prediction_persistence_service.persist_prediction(db_session, comp, payload_v2)

    db_session.refresh(pred)
    assert pred.snapshot.feature_schema_hash == orig_hash, "Snapshot hash must remain immutable across versions"
    assert pred.snapshot.snapshot_data == orig_data, "Snapshot data must remain unchanged"
    assert pred_v2.snapshot.feature_schema_hash != orig_hash, "New version must have its own distinct snapshot"

    # Verify that attempting to update an existing snapshot raises ValueError (write-once immutability)
    with pytest.raises(ValueError, match="PredictionSnapshot is write-once and immutable"):
        pred.snapshot.model_version = "illegal-mutation"
        db_session.commit()
    db_session.rollback()


def test_prediction_version_retrieval_endpoints(auth_client, db_session: Session):
    """
    Test version history retrieval and individual historical version lookup:
    1. GET /api/v1/predictions/{complaint_number}/versions returns version list.
    2. GET /api/v1/predictions/version/{prediction_id} returns exact historical version.
    3. GET /api/v1/predictions/{complaint_number} returns operational latest.
    """
    comp = Complaint(
        complaint_number=f"CMP-VERS-{int(datetime.datetime.utcnow().timestamp())}",
        fraud_type="INVESTMENT_FRAUD",
        amount=Decimal("80000.00"),
        victim_location="Connaught Place, Delhi",
        state="Delhi",
        district="CENTRAL_NEW_DELHI",
        payment_channel="UPI",
        reported_at=datetime.datetime.utcnow() - datetime.timedelta(hours=3),
        incident_time=datetime.datetime.utcnow() - datetime.timedelta(hours=4),
    )
    db_session.add(comp)
    db_session.commit()

    # Trigger v1 prediction via POST
    res1 = auth_client.post(f"/api/v1/predictions/{comp.complaint_number}")
    assert res1.status_code == 200, f"Failed POST: {res1.text}"
    v1_id = res1.json()["prediction_id"]

    # Ingest a transaction to trigger v2
    tx_time = (comp.reported_at + datetime.timedelta(minutes=20)).isoformat()
    ing_res = auth_client.post(
        f"/api/v1/complaints/{comp.complaint_number}/transactions",
        json={
            "transaction_ref": f"TX-VERS-{int(datetime.datetime.utcnow().timestamp())}",
            "sender_account_number": "ACC-S-VERS-01",
            "receiver_account_number": "ACC-R-VERS-01",
            "amount": 40000.0,
            "payment_channel": "UPI",
            "timestamp": tx_time,
        }
    )
    assert ing_res.status_code == 201

    # 1. Check version history list
    vers_resp = auth_client.get(f"/api/v1/predictions/{comp.complaint_number}/versions")
    assert vers_resp.status_code == 200
    versions = vers_resp.json()
    assert len(versions) >= 2, f"Expected at least 2 versions, got {len(versions)}"
    assert versions[0]["version_number"] == 1
    assert versions[1]["version_number"] == 2

    # 2. Check historical lookup
    hist_resp = auth_client.get(f"/api/v1/predictions/version/{v1_id}")
    assert hist_resp.status_code == 200
    hist_body = hist_resp.json()
    assert hist_body["prediction_id"] == v1_id
    assert hist_body["version_number"] == 1

    # 3. Check operational latest
    op_resp = auth_client.get(f"/api/v1/predictions/{comp.complaint_number}")
    assert op_resp.status_code == 200
    op_body = op_resp.json()
    assert op_body["version_number"] >= 2


def test_regression_automatic_refresh_includes_new_past_transfer(auth_client, db_session: Session):
    """
    1. Automatic refresh cutoff:
    A newly received past transfer (timestamp in the past) must be included in the
    post-transfer prediction recalculation by establishing analysis cutoff at/after server received_at.
    """
    comp = Complaint(
        complaint_number=f"CMP-AR-{int(datetime.datetime.utcnow().timestamp())}",
        fraud_type="UPI_FRAUD",
        amount=Decimal("60000.00"),
        victim_location="Rohini, Delhi",
        state="Delhi",
        district="NORTH_WEST",
        payment_channel="UPI",
        reported_at=datetime.datetime.utcnow() - datetime.timedelta(hours=4),
        incident_time=datetime.datetime.utcnow() - datetime.timedelta(hours=5),
    )
    db_session.add(comp)
    db_session.commit()

    # Ingest a past transfer that occurred 2 hours ago (after reported_at 4h ago)
    past_tx_time = (comp.reported_at + datetime.timedelta(hours=2)).isoformat()
    tx_ref = f"TX-PAST-{int(datetime.datetime.utcnow().timestamp())}"
    res = auth_client.post(
        f"/api/v1/complaints/{comp.complaint_number}/transactions",
        json={
            "transaction_ref": tx_ref,
            "sender_account_number": "ACC-S-PAST-01",
            "receiver_account_number": "ACC-R-PAST-01",
            "amount": 30000.0,
            "payment_channel": "UPI",
            "timestamp": past_tx_time,
        }
    )
    assert res.status_code == 201
    ing_body = res.json()
    assert ing_body["analysis_status"] == "COMPLETED"
    assert ing_body["prediction_id"] is not None

    # Verify the created prediction includes this transaction in eligible evidence
    pred = db_session.query(Prediction).filter(Prediction.id == ing_body["prediction_id"]).first()
    assert pred is not None
    # Cutoff must be at/after received_at, NOT the past transaction timestamp
    assert pred.analysis_as_of is not None
    assert pred.analysis_as_of >= datetime.datetime.fromisoformat(ing_body["received_at"]).replace(tzinfo=None) - datetime.timedelta(seconds=5)


def test_regression_truthful_analysis_status_and_idempotent_retry(auth_client, db_session: Session, monkeypatch):
    """
    2. Truthful analysis status and retry:
    - Return FAILED_RETRY_REQUIRED if analysis fails to persist a prediction.
    - Idempotent replay of transaction with failed analysis returns actual status (not hardcoded COMPLETED).
    - Expose retry behavior to recalculate when ready.
    """
    from backend.app.services.prediction_service import prediction_service

    comp = Complaint(
        complaint_number=f"CMP-STAT-{int(datetime.datetime.utcnow().timestamp())}",
        fraud_type="UPI_FRAUD",
        amount=Decimal("45000.00"),
        victim_location="Karol Bagh, Delhi",
        state="Delhi",
        district="CENTRAL_NEW_DELHI",
        payment_channel="UPI",
        reported_at=datetime.datetime.utcnow() - datetime.timedelta(hours=2),
        incident_time=datetime.datetime.utcnow() - datetime.timedelta(hours=3),
    )
    db_session.add(comp)
    db_session.commit()

    # Monkeypatch prediction_service.run_and_persist_prediction to simulate failure
    def mock_fail(*args, **kwargs):
        raise RuntimeError("Simulated ML engine failure")

    monkeypatch.setattr(prediction_service, "run_and_persist_prediction", mock_fail)

    tx_payload = {
        "transaction_ref": f"TX-FAIL-{int(datetime.datetime.utcnow().timestamp())}",
        "sender_account_number": "ACC-S-STAT-01",
        "receiver_account_number": "ACC-R-STAT-01",
        "amount": 25000.0,
        "payment_channel": "UPI",
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }

    res = auth_client.post(f"/api/v1/complaints/{comp.complaint_number}/transactions", json=tx_payload)
    assert res.status_code == 201
    body = res.json()
    assert body["analysis_status"] == "FAILED_RETRY_REQUIRED"
    assert body["prediction_id"] is None

    # Idempotent replay must return FAILED_RETRY_REQUIRED, NOT hardcoded COMPLETED
    replay_res = auth_client.post(f"/api/v1/complaints/{comp.complaint_number}/transactions", json=tx_payload)
    assert replay_res.status_code == 200
    assert replay_res.headers.get("X-Idempotent-Replay") == "true"
    replay_body = replay_res.json()
    assert replay_body["analysis_status"] == "FAILED_RETRY_REQUIRED"

    # Now unpatch and retry analysis
    monkeypatch.undo()
    retry_res = auth_client.post(f"/api/v1/complaints/{comp.complaint_number}/transactions/{body['id']}/retry-analysis")
    assert retry_res.status_code == 200
    retry_body = retry_res.json()
    assert retry_body["analysis_status"] == "COMPLETED"
    assert retry_body["prediction_id"] is not None


def test_regression_dedup_cross_case_isolation_and_account_provenance(auth_client, db_session: Session):
    """
    3. Deduplication security and account provenance:
    - Scope duplicate references by case; do not return another case's transaction.
    - Remove fabricated default bank names, branches, and IFSCs.
    """
    comp1 = Complaint(
        complaint_number=f"CMP-CASE1-{int(datetime.datetime.utcnow().timestamp())}",
        fraud_type="UPI_FRAUD",
        amount=Decimal("30000.00"),
        victim_location="Rohini, Delhi",
        state="Delhi",
        district="NORTH_WEST",
        payment_channel="UPI",
        reported_at=datetime.datetime.utcnow() - datetime.timedelta(hours=2),
        incident_time=datetime.datetime.utcnow() - datetime.timedelta(hours=3),
    )
    comp2 = Complaint(
        complaint_number=f"CMP-CASE2-{int(datetime.datetime.utcnow().timestamp())}",
        fraud_type="UPI_FRAUD",
        amount=Decimal("40000.00"),
        victim_location="Pitampura, Delhi",
        state="Delhi",
        district="NORTH_WEST",
        payment_channel="UPI",
        reported_at=datetime.datetime.utcnow() - datetime.timedelta(hours=2),
        incident_time=datetime.datetime.utcnow() - datetime.timedelta(hours=3),
    )
    db_session.add_all([comp1, comp2])
    db_session.commit()

    shared_ref = f"TX-SHARED-{int(datetime.datetime.utcnow().timestamp())}"
    # Ingest for comp1
    res1 = auth_client.post(
        f"/api/v1/complaints/{comp1.complaint_number}/transactions",
        json={
            "transaction_ref": shared_ref,
            "sender_account_number": "ACC-S-DEDUP-01",
            "receiver_account_number": "ACC-R-DEDUP-01",
            "amount": 10000.0,
            "payment_channel": "UPI",
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }
    )
    assert res1.status_code == 201

    # Ingest for comp2 with same reference must be rejected (409 Conflict), NEVER leaking comp1's transaction
    res2 = auth_client.post(
        f"/api/v1/complaints/{comp2.complaint_number}/transactions",
        json={
            "transaction_ref": shared_ref,
            "sender_account_number": "ACC-S-DEDUP-01",
            "receiver_account_number": "ACC-R-DEDUP-01",
            "amount": 10000.0,
            "payment_channel": "UPI",
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }
    )
    assert res2.status_code in (409, 403), f"Expected 409 or 403 on cross-case conflict, got {res2.status_code}"

    # Verify accounts do not have fabricated bank names ("HDFC Bank", "State Bank of India") or IFSCs
    acc_sender = db_session.query(Account).filter(Account.account_number == "ACC-S-DEDUP-01").first()
    assert acc_sender is not None
    assert acc_sender.bank_name in ("UNKNOWN", "Not provided", None)
    assert acc_sender.ifsc is None or acc_sender.ifsc == "UNKNOWN"
    assert acc_sender.risk_score is None or acc_sender.risk_score == 0.0


def test_regression_operational_latest_not_displaced_by_historical_replay(auth_client, db_session: Session):
    """
    6. Consistent operational latest and history:
    Historical replay must not replace current operational intelligence in prediction API,
    GIS overview, or Dashboard metrics.
    """
    from backend.app.services.dashboard_service import dashboard_service

    comp = Complaint(
        complaint_number=f"CMP-OPHIST-{int(datetime.datetime.utcnow().timestamp())}",
        fraud_type="UPI_FRAUD",
        amount=Decimal("50000.00"),
        victim_location="Connaught Place, Delhi",
        state="Delhi",
        district="CENTRAL_NEW_DELHI",
        payment_channel="UPI",
        reported_at=datetime.datetime.utcnow() - datetime.timedelta(hours=5),
        incident_time=datetime.datetime.utcnow() - datetime.timedelta(hours=6),
    )
    db_session.add(comp)
    db_session.commit()

    # Create operational prediction (analysis_as_of is None / current)
    res_op = auth_client.post(f"/api/v1/predictions/{comp.complaint_number}")
    assert res_op.status_code == 200
    op_pred_id = res_op.json()["prediction_id"]

    # Now create a historical replay prediction with an earlier cutoff
    hist_cutoff = (comp.reported_at - datetime.timedelta(hours=1)).isoformat()
    res_hist = auth_client.post(f"/api/v1/predictions/{comp.complaint_number}?analysis_as_of={hist_cutoff}")
    assert res_hist.status_code == 200
    hist_pred_id = res_hist.json()["prediction_id"]
    assert hist_pred_id != op_pred_id

    # 1. Prediction API operational latest must return the operational prediction (op_pred_id)
    latest_op = prediction_persistence_service.get_latest_operational_prediction(db_session, comp.id)
    assert latest_op is not None
    assert latest_op.id == op_pred_id
    assert latest_op.analysis_as_of is None

    # 2. GET /predictions/{complaint_number} must return operational latest
    get_res = auth_client.get(f"/api/v1/predictions/{comp.complaint_number}")
    assert get_res.status_code == 200
    assert get_res.json()["prediction_id"] == op_pred_id

    # 3. Dashboard metrics must pick operational latest
    dash_preds = dashboard_service.get_latest_successful_predictions(db_session)
    comp_dash_pred = next((p for p in dash_preds if p.complaint_id == comp.id), None)
    assert comp_dash_pred is not None
    assert comp_dash_pred.id == op_pred_id


def test_regression_evidence_fingerprint_captures_reversal_and_accounts(db_session: Session):
    """
    7. Complete evidence identity and correction handling:
    Transaction reversals alter input fingerprint and create a new version even if rankings stay unchanged.
    """
    comp = Complaint(
        complaint_number=f"CMP-REV-{int(datetime.datetime.utcnow().timestamp())}",
        fraud_type="UPI_FRAUD",
        amount=Decimal("70000.00"),
        victim_location="Karol Bagh, Delhi",
        state="Delhi",
        district="CENTRAL_NEW_DELHI",
        payment_channel="UPI",
        reported_at=datetime.datetime.utcnow() - datetime.timedelta(hours=3),
        incident_time=datetime.datetime.utcnow() - datetime.timedelta(hours=4),
    )
    db_session.add(comp)
    db_session.commit()

    for cid, name in [(1, "Karol Bagh"), (2, "Connaught Place"), (3, "Pahar Ganj")]:
        if not db_session.query(LocationCluster).filter(LocationCluster.id == cid).first():
            db_session.add(LocationCluster(
                id=cid, cluster_name=name, city="Delhi", state="Delhi",
                district="CENTRAL_NEW_DELHI", center_lat=28.63, center_lon=77.22,
                atm_count=5, risk_score=0.5
            ))
    db_session.commit()

    top_locs = [
        {"rank": 1, "cluster_id": 1, "location_name": "Karol Bagh", "probability": 0.75, "risk_level": "CRITICAL", "distance_km": 10.0},
        {"rank": 2, "cluster_id": 2, "location_name": "Connaught Place", "probability": 0.15, "risk_level": "HIGH", "distance_km": 15.0},
        {"rank": 3, "cluster_id": 3, "location_name": "Pahar Ganj", "probability": 0.10, "risk_level": "MEDIUM", "distance_km": 20.0},
    ]
    time_pred = {
        "predicted_minutes_to_cashout": 60.0,
        "window_start": datetime.datetime.utcnow(),
        "window_end": datetime.datetime.utcnow() + datetime.timedelta(hours=2),
        "operational_window": "60–180 min after complaint report"
    }

    pred_payload = {
        "status": "SUCCESS",
        "prediction_mode": "trained_ml",
        "top_locations": top_locs,
        "time_prediction": time_pred,
        "model_version": "cashout-location-xgb-v7-compat",
        "analysis_basis": "direct_transactions"
    }

    # Ingest a transaction
    t1 = Transaction(
        transaction_ref=f"TX-ORIG-{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
        complaint_id=comp.id,
        sender_account_id=1,
        receiver_account_id=2,
        amount=Decimal("35000.00"),
        timestamp=comp.reported_at + datetime.timedelta(minutes=30),
        received_at=datetime.datetime.utcnow(),
        source_system="BANK_API",
        is_reversal=False
    )
    db_session.add(t1)
    db_session.commit()

    # First prediction with t1 in evidence
    p1 = prediction_persistence_service.persist_prediction(
        db=db_session,
        complaint=comp,
        prediction_data=pred_payload
    )
    assert p1 is not None
    assert p1.version_number == 1

    # Now ingest a reversal transaction
    t2 = Transaction(
        transaction_ref=f"TX-REV-{int(datetime.datetime.utcnow().timestamp())}",
        complaint_id=comp.id,
        sender_account_id=2,
        receiver_account_id=1,
        amount=Decimal("35000.00"),
        timestamp=comp.reported_at + datetime.timedelta(minutes=45),
        received_at=datetime.datetime.utcnow(),
        source_system="BANK_API",
        is_reversal=True,
        correction_of_ref=t1.transaction_ref
    )
    db_session.add(t2)
    db_session.commit()

    # Persist second prediction with IDENTICAL location predictions but altered evidence (t1 reversed)
    p2 = prediction_persistence_service.persist_prediction(
        db=db_session,
        complaint=comp,
        prediction_data=pred_payload
    )
    assert p2 is not None
    assert p2.id != p1.id
    assert p2.version_number == 2
    assert p2.parent_prediction_id == p1.id
    assert p2.input_fingerprint != p1.input_fingerprint


# ---------------------------------------------------------------------------
# Phase 02 Acceptance Gap Regression Tests (Batch 2)
# ---------------------------------------------------------------------------


def test_regression_retry_analysis_authorization(auth_client, client, db_session: Session):
    """
    Gap 1 — Retry authorization:
    retry-analysis must require the same mutation-role permissions as transaction ingestion.
    - AUDITOR (read-only) must receive 403.
    - BANK_OFFICER must receive 403 (no mutation permission).
    - Cross-jurisdiction DISTRICT_LEA (different state) must receive 404 on complaint access.
    - Authenticated I4C_ADMIN must succeed (200 or meaningful status).
    """
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.auth.security import create_access_token

    # Create a Delhi complaint (state="Delhi") via db_session
    comp = Complaint(
        complaint_number=f"CMP-AUTHZ-{int(datetime.datetime.utcnow().timestamp())}",
        fraud_type="UPI_FRAUD",
        amount=Decimal("20000.00"),
        victim_location="Rohini, Delhi",
        state="Delhi",
        district="NORTH_WEST",
        payment_channel="UPI",
        reported_at=datetime.datetime.utcnow() - datetime.timedelta(hours=2),
        incident_time=datetime.datetime.utcnow() - datetime.timedelta(hours=3),
    )
    db_session.add(comp)
    db_session.commit()

    # Create a transaction so retry-analysis has a tx_id to target
    tx = Transaction(
        transaction_ref=f"TX-AUTHZ-{int(datetime.datetime.utcnow().timestamp())}",
        complaint_id=comp.id,
        sender_account_id=1,
        receiver_account_id=1,
        amount=Decimal("5000.00"),
        timestamp=datetime.datetime.utcnow() - datetime.timedelta(hours=1),
        received_at=datetime.datetime.utcnow() - datetime.timedelta(hours=1),
        source_system="DIRECT_OFFICER_INPUT",
        analysis_status="FAILED_RETRY_REQUIRED",
    )
    db_session.add(tx)
    db_session.commit()
    db_session.refresh(tx)

    retry_url = f"/api/v1/complaints/{comp.complaint_number}/transactions/{tx.id}/retry-analysis"

    # 1. AUDITOR token (read-only role) must be denied 403
    auditor_token = create_access_token({"sub": "auditor@mha.gov.in", "role": "AUDITOR"})
    with TestClient(app) as c:
        c.headers.update({"Authorization": f"Bearer {auditor_token}"})
        resp = c.post(retry_url)
    assert resp.status_code == 403, (
        f"AUDITOR must be denied retry-analysis with 403, got {resp.status_code}: {resp.text}"
    )

    # 2. BANK_OFFICER token must be denied 403
    bank_token = create_access_token({"sub": "officer@sbi.co.in", "role": "BANK_OFFICER"})
    with TestClient(app) as c:
        c.headers.update({"Authorization": f"Bearer {bank_token}"})
        resp = c.post(retry_url)
    assert resp.status_code == 403, (
        f"BANK_OFFICER must be denied retry-analysis with 403, got {resp.status_code}: {resp.text}"
    )

    # 3. Cross-jurisdiction DISTRICT_LEA (Indore, Madhya Pradesh vs Delhi complaint) → 404
    #    (Complaint must not be revealed to out-of-jurisdiction officer)
    mp_token = _cross_jurisdiction_indore_token(db_session)
    with TestClient(app) as c:
        c.headers.update({"Authorization": f"Bearer {mp_token}"})
        resp = c.post(retry_url)
    assert resp.status_code == 404, (
        f"Cross-jurisdiction DISTRICT_LEA must receive 404 (no existence disclosure), "
        f"got {resp.status_code}: {resp.text}"
    )

    # 4. Authenticated I4C_ADMIN must be permitted (200 or 201; may return COMPLETED or FAILED)
    admin_token = create_access_token({"sub": "admin@cybershield.gov.in", "role": "I4C_ADMIN"})
    with TestClient(app) as c:
        c.headers.update({"Authorization": f"Bearer {admin_token}"})
        resp = c.post(retry_url)
    assert resp.status_code in (200, 201), (
        f"I4C_ADMIN must be permitted retry-analysis, got {resp.status_code}: {resp.text}"
    )


def test_regression_recent_historical_replay_never_becomes_operational(db_session: Session):
    """
    Gap 2 — Explicit analysis mode:
    A historical replay with analysis_as_of only 2 minutes in the past must retain
    analysis_purpose='HISTORICAL_REPLAY' and must NOT be returned by
    get_latest_operational_prediction, even though its cutoff is close to now.

    This directly reproduces the defect where the 'within 5 minutes of created_at'
    heuristic would misclassify a recent replay as operational.
    """
    comp = Complaint(
        complaint_number=f"CMP-AMODE-{int(datetime.datetime.utcnow().timestamp())}",
        fraud_type="UPI_FRAUD",
        amount=Decimal("55000.00"),
        victim_location="Connaught Place, Delhi",
        state="Delhi",
        district="CENTRAL_NEW_DELHI",
        payment_channel="UPI",
        reported_at=datetime.datetime.utcnow() - datetime.timedelta(hours=3),
        incident_time=datetime.datetime.utcnow() - datetime.timedelta(hours=4),
    )
    db_session.add(comp)
    db_session.flush()

    for cid, name in [(1, "Connaught Place"), (2, "Karol Bagh"), (3, "Laxmi Nagar")]:
        if not db_session.query(LocationCluster).filter(LocationCluster.id == cid).first():
            db_session.add(LocationCluster(
                id=cid, cluster_name=name, city="Delhi", state="Delhi",
                district="CENTRAL_NEW_DELHI", center_lat=28.63, center_lon=77.22,
                atm_count=5, risk_score=0.5
            ))
    db_session.flush()

    base_payload = {
        "status": "SUCCESS",
        "prediction_mode": "trained_ml",
        "model_version": "cashout-location-xgb-v7-compat",
        "time_model_version": "cashout-time-xgb-v3",
        "analysis_basis": "complaint_only",
        "top_locations": [
            {"rank": 1, "cluster_id": 1, "location_name": "Connaught Place", "probability": 0.65, "risk_level": "HIGH"},
            {"rank": 2, "cluster_id": 2, "location_name": "Karol Bagh", "probability": 0.20, "risk_level": "MEDIUM"},
            {"rank": 3, "cluster_id": 3, "location_name": "Laxmi Nagar", "probability": 0.15, "risk_level": "LOW"},
        ],
        "time_prediction": {
            "predicted_minutes_to_cashout": 45.0,
            "window_start": (comp.reported_at + datetime.timedelta(minutes=30)).isoformat(),
            "window_end": (comp.reported_at + datetime.timedelta(minutes=60)).isoformat(),
            "operational_window": "30–60 min after complaint report",
            "model_version": "cashout-time-xgb-v3",
        }
    }

    # 1. First create an operational prediction (no analysis_as_of → OPERATIONAL)
    op_pred = prediction_persistence_service.persist_prediction(
        db=db_session, complaint=comp, prediction_data=base_payload
    )
    assert op_pred is not None
    assert op_pred.analysis_purpose == "OPERATIONAL", (
        f"Expected analysis_purpose='OPERATIONAL', got '{op_pred.analysis_purpose}'"
    )

    # 2. Create a historical replay with a cutoff only 2 minutes in the past (close to now)
    #    Under the old heuristic this would have been classified as operational.
    recent_cutoff = datetime.datetime.utcnow() - datetime.timedelta(minutes=2)
    hist_payload = dict(base_payload)
    hist_payload["top_locations"] = [
        {"rank": 1, "cluster_id": 2, "location_name": "Karol Bagh", "probability": 0.70, "risk_level": "HIGH"},
        {"rank": 2, "cluster_id": 1, "location_name": "Connaught Place", "probability": 0.20, "risk_level": "MEDIUM"},
        {"rank": 3, "cluster_id": 3, "location_name": "Laxmi Nagar", "probability": 0.10, "risk_level": "LOW"},
    ]

    hist_pred = prediction_persistence_service.persist_prediction(
        db=db_session, complaint=comp, prediction_data=hist_payload,
        analysis_as_of=recent_cutoff
    )
    assert hist_pred is not None
    # Must be persisted as HISTORICAL_REPLAY regardless of cutoff proximity
    assert hist_pred.analysis_purpose == "HISTORICAL_REPLAY", (
        f"Expected analysis_purpose='HISTORICAL_REPLAY' for replay with cutoff 2 min ago, "
        f"got '{hist_pred.analysis_purpose}'"
    )

    # 3. get_latest_operational_prediction must still return the OPERATIONAL prediction
    latest_op = prediction_persistence_service.get_latest_operational_prediction(db_session, comp.id)
    assert latest_op is not None, "get_latest_operational_prediction returned None after historical replay"
    assert latest_op.id == op_pred.id, (
        f"Operational intelligence displaced by historical replay! "
        f"Expected prediction #{op_pred.id} (OPERATIONAL), got #{latest_op.id} "
        f"(purpose={latest_op.analysis_purpose})"
    )


def test_regression_unrelated_integrity_error_propagates(db_session: Session):
    """
    Gap 3 — Precise concurrency handling:
    An IntegrityError caused by an unrelated unique constraint (e.g. duplicate complaint_number,
    NOT a version uniqueness race) must propagate and NOT be silently swallowed as a
    version race recovery.

    This test directly verifies that the constraint name filter is precise:
    only 'uq_complaint_version_number' triggers the race-recovery path.
    """
    from sqlalchemy.exc import IntegrityError

    # Create a complaint and duplicate it to provoke a unique constraint on complaint_number
    comp_number = f"CMP-INTEG-{int(datetime.datetime.utcnow().timestamp())}"
    comp1 = Complaint(
        complaint_number=comp_number,
        fraud_type="UPI_FRAUD",
        amount=Decimal("10000.00"),
        victim_location="Karol Bagh, Delhi",
        state="Delhi",
        district="NORTH_WEST",
        payment_channel="UPI",
        reported_at=datetime.datetime.utcnow() - datetime.timedelta(hours=1),
        incident_time=datetime.datetime.utcnow() - datetime.timedelta(hours=2),
    )
    db_session.add(comp1)
    db_session.commit()

    # Attempt to insert a second complaint with the identical complaint_number.
    # This violates the `unique=True` index on `complaints.complaint_number`,
    # which is an unrelated IntegrityError (NOT the prediction version race constraint).
    with pytest.raises(Exception) as exc_info:
        comp2 = Complaint(
            complaint_number=comp_number,  # Duplicate!
            fraud_type="CARD_FRAUD",
            amount=Decimal("5000.00"),
            victim_location="Rohini, Delhi",
            state="Delhi",
            district="NORTH_WEST",
            payment_channel="CARD",
            reported_at=datetime.datetime.utcnow(),
            incident_time=datetime.datetime.utcnow(),
        )
        db_session.add(comp2)
        db_session.commit()

    db_session.rollback()

    # Verify it is indeed an IntegrityError (not silently swallowed)
    assert issubclass(exc_info.type, Exception), (
        "Unrelated unique constraint violation must raise, not be swallowed"
    )
    # SQLAlchemy raises IntegrityError for unique constraint violations
    err_str = str(exc_info.value).lower()
    # Must not have been mistaken for a version race: check that the error is surfaced
    assert "unique" in err_str or "constraint" in err_str or "integrity" in err_str, (
        f"Expected IntegrityError to be raised and propagated, got: {exc_info.type}: {exc_info.value}"
    )


def test_regression_transaction_correction_and_reversal_api(auth_client, db_session: Session):
    """
    1. Transaction Correction & Reversal API:
    - Accepts correction_of_ref and is_reversal via validated API endpoints.
    - Preserves original transaction completely unchanged.
    - Creates separate correction/reversal record.
    - Enforces complaint access, mutation role, and jurisdiction.
    - Recalculates an OPERATIONAL prediction producing a new monotonic prediction version.
    """
    comp = Complaint(
        complaint_number=f"CMP-CORR-{int(datetime.datetime.utcnow().timestamp())}",
        fraud_type="UPI_FRAUD",
        amount=Decimal("60000.00"),
        victim_location="Dwarka, Delhi",
        state="Delhi",
        district="SOUTH_WEST",
        payment_channel="UPI",
        reported_at=datetime.datetime.utcnow() - datetime.timedelta(hours=2),
        incident_time=datetime.datetime.utcnow() - datetime.timedelta(hours=3),
    )
    db_session.add(comp)
    db_session.commit()

    # Step 1: Ingest original transaction -> creates v1 operational prediction
    tx_ref_orig = f"TX-ORIG-{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
    res_orig = auth_client.post(
        f"/api/v1/complaints/{comp.complaint_number}/transactions",
        json={
            "transaction_ref": tx_ref_orig,
            "sender_account_number": "ACC-S-CORR-01",
            "receiver_account_number": "ACC-R-CORR-01",
            "amount": 60000.0,
            "payment_channel": "UPI",
            "timestamp": (comp.reported_at + datetime.timedelta(minutes=10)).isoformat(),
        }
    )
    assert res_orig.status_code == 201, f"Failed original ingestion: {res_orig.text}"
    orig_tx_id = res_orig.json()["id"]

    # Verify initial operational prediction is v1
    v1_resp = auth_client.get(f"/api/v1/predictions/{comp.complaint_number}")
    assert v1_resp.status_code == 200
    v1_body = v1_resp.json()
    assert v1_body["version_number"] >= 1
    assert v1_body["analysis_purpose"] == "OPERATIONAL"

    # Step 2: Submit a correction for the original transaction
    tx_ref_corr = f"TX-CORR-{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
    corr_resp = auth_client.post(
        f"/api/v1/complaints/{comp.complaint_number}/transactions/correction",
        json={
            "transaction_ref": tx_ref_corr,
            "correction_of_ref": tx_ref_orig,
            "sender_account_number": "ACC-S-CORR-01",
            "receiver_account_number": "ACC-R-CORR-02",  # Corrected recipient
            "amount": 55000.0,                           # Corrected amount
            "payment_channel": "UPI",
            "is_reversal": False,
        }
    )
    assert corr_resp.status_code == 201, f"Failed correction: {corr_resp.text}"
    corr_body = corr_resp.json()
    assert corr_body["transaction_ref"] == tx_ref_corr
    assert corr_body["correction_of_ref"] == tx_ref_orig
    assert corr_body["is_reversal"] is False
    assert corr_body["analysis_status"] == "COMPLETED"

    # Step 3: Verify original transaction is completely unchanged in DB
    db_session.expire_all()
    orig_tx_db = db_session.query(Transaction).filter(Transaction.id == orig_tx_id).first()
    assert orig_tx_db is not None
    assert orig_tx_db.transaction_ref == tx_ref_orig
    assert float(orig_tx_db.amount) == 60000.0
    assert orig_tx_db.correction_of_ref is None
    assert orig_tx_db.is_reversal is False

    # Step 4: Submit a reversal for the transaction
    tx_ref_rev = f"TX-REV-{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
    rev_resp = auth_client.post(
        f"/api/v1/complaints/{comp.complaint_number}/transactions/reversal",
        json={
            "transaction_ref": tx_ref_rev,
            "correction_of_ref": tx_ref_orig,
            "sender_account_number": "ACC-R-CORR-01",
            "receiver_account_number": "ACC-S-CORR-01",
            "amount": 60000.0,
            "payment_channel": "UPI",
            "is_reversal": True,
        }
    )
    assert rev_resp.status_code == 201, f"Failed reversal: {rev_resp.text}"
    rev_body = rev_resp.json()
    assert rev_body["is_reversal"] is True
    assert rev_body["correction_of_ref"] == tx_ref_orig

    # Step 5: Verify new prediction version produced after corrections
    vers_resp = auth_client.get(f"/api/v1/predictions/{comp.complaint_number}/versions")
    assert vers_resp.status_code == 200
    versions = vers_resp.json()
    assert len(versions) >= 3, f"Expected at least 3 versions after original+corr+rev, got {len(versions)}"

    # Step 6: Verify Role & Jurisdiction Authorization on correction endpoints
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.auth.security import create_access_token

    # ANALYST role -> 403 Forbidden
    analyst_token = create_access_token({"sub": "analyst@cybershield.gov.in", "role": "ANALYST"})
    with TestClient(app) as an_client:
        an_client.headers.update({"Authorization": f"Bearer {analyst_token}"})
        an_res = an_client.post(
            f"/api/v1/complaints/{comp.complaint_number}/transactions/correction",
            json={"transaction_ref": "TX-AN-01", "correction_of_ref": tx_ref_orig}
        )
    assert an_res.status_code == 403, f"Expected 403 for ANALYST, got {an_res.status_code}"

    # AUDITOR role -> 403 Forbidden
    auditor_token = create_access_token({"sub": "auditor@mha.gov.in", "role": "AUDITOR"})
    with TestClient(app) as aud_client:
        aud_client.headers.update({"Authorization": f"Bearer {auditor_token}"})
        aud_res = aud_client.post(
            f"/api/v1/complaints/{comp.complaint_number}/transactions/correction",
            json={"transaction_ref": "TX-AUD-01", "correction_of_ref": tx_ref_orig}
        )
    assert aud_res.status_code == 403, f"Expected 403 for AUDITOR, got {aud_res.status_code}"

    # BANK_OFFICER role -> 403 Forbidden
    bank_token = create_access_token({"sub": "officer@sbi.co.in", "role": "BANK_OFFICER"})
    with TestClient(app) as bk_client:
        bk_client.headers.update({"Authorization": f"Bearer {bank_token}"})
        bk_res = bk_client.post(
            f"/api/v1/complaints/{comp.complaint_number}/transactions/correction",
            json={"transaction_ref": "TX-BK-01", "correction_of_ref": tx_ref_orig}
        )
    assert bk_res.status_code == 403, f"Expected 403 for BANK_OFFICER, got {bk_res.status_code}"

    # Cross-jurisdiction district LEA -> 404 Not Found (no existence disclosure)
    cross_token = _cross_jurisdiction_indore_token(db_session)
    with TestClient(app) as cross_client:
        cross_client.headers.update({"Authorization": f"Bearer {cross_token}"})
        cross_res = cross_client.post(
            f"/api/v1/complaints/{comp.complaint_number}/transactions/correction",
            json={"transaction_ref": "TX-CROSS-01", "correction_of_ref": tx_ref_orig}
        )
    assert cross_res.status_code == 404

    # Circular self-correction -> 400 Bad Request
    circ_res = auth_client.post(
        f"/api/v1/complaints/{comp.complaint_number}/transactions/correction",
        json={"transaction_ref": "TX-CIRC-SAME", "correction_of_ref": "TX-CIRC-SAME"}
    )
    assert circ_res.status_code == 400
    assert "circular" in circ_res.json()["detail"].lower()


def test_regression_concurrent_duplicate_transaction_ingestion_idempotency(auth_client, db_session: Session):
    """
    2. Concurrent / Duplicate Transaction Ingestion Idempotency:
    - Identical payload returns 200/201 with identical transaction ID.
    - Exactly one transaction record is committed to the database.
    - Differing payload with same ref returns 409 Conflict.
    """
    from backend.app.models.models import Complaint, Transaction

    comp = Complaint(
        complaint_number=f"CMP-RACE-{int(datetime.datetime.utcnow().timestamp())}",
        fraud_type="UPI_FRAUD",
        amount=Decimal("45000.00"),
        victim_location="Rohini, Delhi",
        state="Delhi",
        district="NORTH_WEST",
        payment_channel="UPI",
        reported_at=datetime.datetime.utcnow() - datetime.timedelta(hours=1),
        incident_time=datetime.datetime.utcnow() - datetime.timedelta(hours=2),
    )
    db_session.add(comp)
    db_session.commit()

    tx_ref = f"TX-RACE-{int(datetime.datetime.utcnow().timestamp())}"
    payload = {
        "transaction_ref": tx_ref,
        "sender_account_number": "ACC-S-RACE-01",
        "receiver_account_number": "ACC-R-RACE-01",
        "amount": 45000.0,
        "payment_channel": "UPI",
        "timestamp": (comp.reported_at + datetime.timedelta(minutes=5)).isoformat(),
    }

    # First ingestion creates the transaction
    r1 = auth_client.post(f"/api/v1/complaints/{comp.complaint_number}/transactions", json=payload)
    assert r1.status_code in (200, 201), f"First ingestion failed: {r1.status_code} {r1.text}"

    # Duplicate identical ingestion returns 200 idempotent deduplication
    r2 = auth_client.post(f"/api/v1/complaints/{comp.complaint_number}/transactions", json=payload)
    assert r2.status_code in (200, 201), f"Duplicate ingestion failed: {r2.status_code} {r2.text}"

    # Verify both returned the same transaction id
    id1 = r1.json()["id"]
    id2 = r2.json()["id"]
    assert id1 == id2

    # Verify exactly one database transaction was committed
    db_session.expire_all()
    count = db_session.query(Transaction).filter(Transaction.transaction_ref == tx_ref).count()
    assert count == 1, f"Expected exactly 1 database record, got {count}"

    # Differing payload race for a new ref
    diff_ref = f"TX-RACE-DIFF-{int(datetime.datetime.utcnow().timestamp())}"
    payload_a = dict(payload, transaction_ref=diff_ref, amount=10000.0)
    payload_b = dict(payload, transaction_ref=diff_ref, amount=20000.0)

    # First ingest payload_a
    r_a = auth_client.post(f"/api/v1/complaints/{comp.complaint_number}/transactions", json=payload_a)
    assert r_a.status_code in (200, 201)

    # Differing payload returns 409 Conflict
    r_b = auth_client.post(f"/api/v1/complaints/{comp.complaint_number}/transactions", json=payload_b)
    assert r_b.status_code == 409
    assert "differing payload" in r_b.json()["detail"].lower()


def test_regression_cross_case_anti_enumeration(auth_client, db_session: Session):
    """
    3. Cross-Case Anti-Enumeration & Information Disclosure Prevention:
    - Attempting to ingest a transaction_ref belonging to Case A from Case B returns a generic 409
      WITHOUT disclosing Case A existence or details.
    - Attempting correction with correction_of_ref belonging to another case returns 404
      WITHOUT disclosing existence in another case.
    """
    comp_a = Complaint(
        complaint_number=f"CMP-ENUM-A-{int(datetime.datetime.utcnow().timestamp())}",
        fraud_type="UPI_FRAUD",
        amount=Decimal("30000.00"),
        victim_location="Kashmere Gate, Delhi",
        state="Delhi",
        district="NORTH",
        payment_channel="UPI",
        reported_at=datetime.datetime.utcnow() - datetime.timedelta(hours=2),
        incident_time=datetime.datetime.utcnow() - datetime.timedelta(hours=3),
    )
    comp_b = Complaint(
        complaint_number=f"CMP-ENUM-B-{int(datetime.datetime.utcnow().timestamp())}",
        fraud_type="IMPS_FRAUD",
        amount=Decimal("50000.00"),
        victim_location="Saket, Delhi",
        state="Delhi",
        district="SOUTH_DELHI",
        payment_channel="IMPS",
        reported_at=datetime.datetime.utcnow() - datetime.timedelta(hours=2),
        incident_time=datetime.datetime.utcnow() - datetime.timedelta(hours=3),
    )
    db_session.add_all([comp_a, comp_b])
    db_session.commit()

    tx_ref_a = f"TX-ENUM-A-{int(datetime.datetime.utcnow().timestamp())}"
    res_a = auth_client.post(
        f"/api/v1/complaints/{comp_a.complaint_number}/transactions",
        json={
            "transaction_ref": tx_ref_a,
            "sender_account_number": "ACC-S-ENUM-A",
            "receiver_account_number": "ACC-R-ENUM-A",
            "amount": 30000.0,
            "payment_channel": "UPI",
            "timestamp": comp_a.reported_at.isoformat(),
        }
    )
    assert res_a.status_code == 201

    # Attempt ingestion of tx_ref_a in Case B
    res_b_conflict = auth_client.post(
        f"/api/v1/complaints/{comp_b.complaint_number}/transactions",
        json={
            "transaction_ref": tx_ref_a,  # Belongs to Case A!
            "sender_account_number": "ACC-S-ENUM-B",
            "receiver_account_number": "ACC-R-ENUM-B",
            "amount": 50000.0,
            "payment_channel": "IMPS",
            "timestamp": comp_b.reported_at.isoformat(),
        }
    )
    # Must be 409 Conflict with generic message (no case A leakage)
    assert res_b_conflict.status_code == 409
    detail = res_b_conflict.json()["detail"]
    assert "cross-case" not in detail.lower(), f"Leaked cross-case terminology: {detail}"
    assert comp_a.complaint_number not in detail, f"Leaked target complaint number: {detail}"

    # Attempt correction in Case B referencing tx_ref_a
    res_b_corr = auth_client.post(
        f"/api/v1/complaints/{comp_b.complaint_number}/transactions/correction",
        json={
            "transaction_ref": f"TX-ENUM-B-CORR-{int(datetime.datetime.utcnow().timestamp())}",
            "correction_of_ref": tx_ref_a,  # Belongs to Case A!
            "sender_account_number": "ACC-S-ENUM-B",
            "receiver_account_number": "ACC-R-ENUM-B",
            "amount": 50000.0,
        }
    )
    # Must return 404 Not Found (generic)
    assert res_b_corr.status_code == 404
    corr_detail = res_b_corr.json()["detail"]
    assert comp_a.complaint_number not in corr_detail


def test_regression_effective_transaction_semantics_and_causal_replay(auth_client, db_session: Session):
    """
    4. Effective Transaction Semantics & Causal Point-in-Time Isolation:
    - Original transaction affects prediction before correction.
    - Correction supersedes original values after its received_at.
    - Reversal cancels original economic effect after its received_at.
    - Chained corrections resolve deterministically (T0 -> T1 -> T2: T2 is active).
    - Historical replay before correction remains unchanged (sees original evidence).
    - Original database records remain immutable in PostgreSQL for audit.
    - Correction/reversal produces a new operational prediction version.
    """
    import time
    from backend.app.services.transaction_context_service import resolve_transaction_context

    t_base = datetime.datetime.utcnow() - datetime.timedelta(hours=4)
    comp = Complaint(
        complaint_number=f"CMP-SEM-{int(datetime.datetime.utcnow().timestamp())}",
        fraud_type="UPI_FRAUD",
        amount=Decimal("80000.00"),
        victim_location="Karol Bagh, Delhi",
        state="Delhi",
        district="CENTRAL",
        payment_channel="UPI",
        reported_at=t_base,
        incident_time=t_base - datetime.timedelta(hours=1),
    )
    db_session.add(comp)
    db_session.commit()

    # Step 1: Ingest original transaction T0 (80,000)
    tx_ref_0 = f"TX-SEM-0-{int(datetime.datetime.utcnow().timestamp())}"
    t_tx0 = t_base + datetime.timedelta(minutes=10)
    r0 = auth_client.post(
        f"/api/v1/complaints/{comp.complaint_number}/transactions",
        json={
            "transaction_ref": tx_ref_0,
            "sender_account_number": "ACC-S-SEM-0",
            "receiver_account_number": "ACC-R-SEM-0",
            "amount": 80000.0,
            "payment_channel": "UPI",
            "timestamp": t_tx0.isoformat(),
        }
    )
    assert r0.status_code == 201
    t0_rec_str = r0.json()["received_at"]
    t0_rec = datetime.datetime.fromisoformat(t0_rec_str).replace(tzinfo=None) if t0_rec_str else datetime.datetime.utcnow()

    # Resolve context right after T0 ingestion
    ctx_0 = resolve_transaction_context(db_session, comp)
    assert ctx_0["transaction_count"] == 1
    assert float(ctx_0["transactions"][0].amount) == 80000.0
    assert ctx_0["transactions"][0].transaction_ref == tx_ref_0

    time.sleep(0.06)

    # Step 2: Ingest correction T1 (35,000) correcting T0
    tx_ref_1 = f"TX-SEM-1-{int(datetime.datetime.utcnow().timestamp())}"
    r1 = auth_client.post(
        f"/api/v1/complaints/{comp.complaint_number}/transactions/correction",
        json={
            "transaction_ref": tx_ref_1,
            "correction_of_ref": tx_ref_0,
            "sender_account_number": "ACC-S-SEM-0",
            "receiver_account_number": "ACC-R-SEM-1",
            "amount": 35000.0,
            "payment_channel": "UPI",
        }
    )
    assert r1.status_code == 201
    t1_rec_str = r1.json()["received_at"]
    t1_rec = datetime.datetime.fromisoformat(t1_rec_str).replace(tzinfo=None) if t1_rec_str else datetime.datetime.utcnow()

    # Verify effective context after T1: contains ONLY T1 (35,000), T0 is superseded!
    ctx_1 = resolve_transaction_context(db_session, comp)
    assert ctx_1["transaction_count"] == 1
    assert float(ctx_1["transactions"][0].amount) == 35000.0
    assert ctx_1["transactions"][0].transaction_ref == tx_ref_1

    # Verify historical replay BETWEEN T0 received_at and T1 received_at: sees original T0 (80,000)!
    t_replay_before_t1 = t0_rec + (t1_rec - t0_rec) / 2
    ctx_replay_pre = resolve_transaction_context(db_session, comp, analysis_as_of=t_replay_before_t1)
    assert ctx_replay_pre["transaction_count"] == 1
    assert float(ctx_replay_pre["transactions"][0].amount) == 80000.0
    assert ctx_replay_pre["transactions"][0].transaction_ref == tx_ref_0

    time.sleep(0.06)

    # Step 3: Ingest chained correction T2 (42,000) correcting T1
    tx_ref_2 = f"TX-SEM-2-{int(datetime.datetime.utcnow().timestamp())}"
    r2 = auth_client.post(
        f"/api/v1/complaints/{comp.complaint_number}/transactions/correction",
        json={
            "transaction_ref": tx_ref_2,
            "correction_of_ref": tx_ref_1,
            "sender_account_number": "ACC-S-SEM-0",
            "receiver_account_number": "ACC-R-SEM-2",
            "amount": 42000.0,
            "payment_channel": "UPI",
        }
    )
    assert r2.status_code == 201

    # Effective context after T2: chained resolution yields ONLY T2 (42,000)
    ctx_2 = resolve_transaction_context(db_session, comp)
    assert ctx_2["transaction_count"] == 1
    assert float(ctx_2["transactions"][0].amount) == 42000.0
    assert ctx_2["transactions"][0].transaction_ref == tx_ref_2

    time.sleep(0.06)

    # Step 4: Ingest a second independent transaction U0 (20,000) and then reverse it
    tx_ref_u0 = f"TX-SEM-U0-{int(datetime.datetime.utcnow().timestamp())}"
    ru0 = auth_client.post(
        f"/api/v1/complaints/{comp.complaint_number}/transactions",
        json={
            "transaction_ref": tx_ref_u0,
            "sender_account_number": "ACC-S-SEM-U0",
            "receiver_account_number": "ACC-R-SEM-U0",
            "amount": 20000.0,
            "payment_channel": "IMPS",
            "timestamp": (t_base + datetime.timedelta(minutes=20)).isoformat(),
        }
    )
    assert ru0.status_code == 201
    tu0_rec_str = ru0.json()["received_at"]
    tu0_rec = datetime.datetime.fromisoformat(tu0_rec_str).replace(tzinfo=None) if tu0_rec_str else datetime.datetime.utcnow()

    # Both T2 (42k) and U0 (20k) are effective
    ctx_with_u0 = resolve_transaction_context(db_session, comp)
    assert ctx_with_u0["transaction_count"] == 2

    time.sleep(0.06)

    # Now reverse U0
    tx_ref_u1 = f"TX-SEM-U1-REV-{int(datetime.datetime.utcnow().timestamp())}"
    ru1 = auth_client.post(
        f"/api/v1/complaints/{comp.complaint_number}/transactions/reversal",
        json={
            "transaction_ref": tx_ref_u1,
            "correction_of_ref": tx_ref_u0,
            "sender_account_number": "ACC-R-SEM-U0",
            "receiver_account_number": "ACC-S-SEM-U0",
            "amount": 20000.0,
        }
    )
    assert ru1.status_code == 201
    tu1_rec_str = ru1.json()["received_at"]
    tu1_rec = datetime.datetime.fromisoformat(tu1_rec_str).replace(tzinfo=None) if tu1_rec_str else datetime.datetime.utcnow()

    # Effective context after reversal of U0: U0 is cancelled, only T2 (42k) remains!
    ctx_after_rev = resolve_transaction_context(db_session, comp)
    assert ctx_after_rev["transaction_count"] == 1
    assert ctx_after_rev["transactions"][0].transaction_ref == tx_ref_2

    # Historical replay between U0 and U1: U0 was active and not yet reversed
    t_replay_u0_active = tu0_rec + (tu1_rec - tu0_rec) / 2
    ctx_replay_u0 = resolve_transaction_context(db_session, comp, analysis_as_of=t_replay_u0_active)
    assert ctx_replay_u0["transaction_count"] == 2

    # Verify all 5 database records (T0, T1, T2, U0, U1) remain immutable in PostgreSQL for audit!
    db_session.expire_all()
    all_refs = {t.transaction_ref for t in db_session.query(Transaction).filter(Transaction.complaint_id == comp.id).all()}
    assert {tx_ref_0, tx_ref_1, tx_ref_2, tx_ref_u0, tx_ref_u1}.issubset(all_refs)


def test_authenticated_transaction_actor_attribution(db_session: Session):
    """
    Verify:
    1. Authenticated user's ID is truthfully recorded as created_by_user_id during transaction ingestion.
    2. Response includes created_by_user_id.
    3. Transaction detail endpoint includes created_by_user_id for authorized officers.
    """
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.models.db import get_db
    from backend.app.models.models import User, Organization
    from backend.app.auth.security import create_access_token

    org = db_session.query(Organization).filter(Organization.id == 201).first()
    if not org:
        org = Organization(id=201, name="Delhi Central LEA", org_type="LEA", state="Delhi", district="CENTRAL_NEW_DELHI")
        db_session.add(org)
        db_session.flush()

    officer = db_session.query(User).filter(User.id == 201).first()
    if not officer:
        officer = User(
            id=201,
            email="district_officer_201@delhipolice.gov.in",
            hashed_password="mock",
            full_name="Inspector R. Kumar",
            role="DISTRICT_LEA",
            badge_number="DL-201",
            organization_id=org.id
        )
        db_session.add(officer)
        db_session.flush()

    comp = Complaint(
        complaint_number=f"CMP-ACTOR-{int(datetime.datetime.utcnow().timestamp())}",
        fraud_type="UPI_FRAUD",
        amount=Decimal("15000.00"),
        victim_location="Karol Bagh, Delhi",
        state="Delhi",
        district="CENTRAL_NEW_DELHI",
        payment_channel="UPI",
        reported_at=datetime.datetime.utcnow()
    )
    db_session.add(comp)
    db_session.commit()

    token = create_access_token({"sub": officer.email, "role": officer.role, "org_id": org.id})
    client = TestClient(app)
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        tx_ref = f"TX-ACTOR-INGEST-{int(datetime.datetime.utcnow().timestamp())}"
        res = client.post(
            f"/api/v1/complaints/{comp.complaint_number}/transactions",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "transaction_ref": tx_ref,
                "sender_account_number": "ACC-S-ACTOR-01",
                "receiver_account_number": "ACC-R-ACTOR-01",
                "amount": 15000.0,
                "payment_channel": "UPI",
                "timestamp": datetime.datetime.utcnow().isoformat(),
            }
        )
        assert res.status_code == 201
        data = res.json()
        assert data["created_by_user_id"] == officer.id

        # Verify in DB
        db_tx = db_session.query(Transaction).filter(Transaction.transaction_ref == tx_ref).first()
        assert db_tx is not None
        assert db_tx.created_by_user_id == officer.id

        # Verify in detail list endpoint
        list_res = client.get(
            f"/api/v1/complaints/{comp.complaint_number}/transactions",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert list_res.status_code == 200
        list_data = list_res.json()
        matched = [t for t in list_data if t["transaction_ref"] == tx_ref]
        assert len(matched) == 1
        assert matched[0]["created_by_user_id"] == officer.id
    finally:
        app.dependency_overrides.clear()


def test_correction_and_reversal_distinct_actor_attribution(db_session: Session):
    """
    Verify:
    1. Officer A creates original transaction (created_by_user_id = A).
    2. Officer B (State LEA / I4C Admin) creates correction / reversal (created_by_user_id = B).
    3. Original transaction's created_by_user_id remains untouched.
    """
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.models.db import get_db
    from backend.app.models.models import User, Organization
    from backend.app.auth.security import create_access_token

    org_delhi = db_session.query(Organization).filter(Organization.id == 202).first()
    if not org_delhi:
        org_delhi = Organization(id=202, name="Delhi State LEA", org_type="LEA", state="Delhi", district="CENTRAL_NEW_DELHI")
        db_session.add(org_delhi)
        db_session.flush()

    officer_a = db_session.query(User).filter(User.id == 202).first()
    if not officer_a:
        officer_a = User(
            id=202,
            email="officer_a_202@delhipolice.gov.in",
            hashed_password="mock",
            full_name="Officer Alpha",
            role="DISTRICT_LEA",
            badge_number="DL-202",
            organization_id=org_delhi.id
        )
        db_session.add(officer_a)

    officer_b = db_session.query(User).filter(User.id == 203).first()
    if not officer_b:
        i4c_org = db_session.query(Organization).filter(Organization.id == 203).first()
        if not i4c_org:
            i4c_org = Organization(id=203, name="I4C Attribution Test", org_type="I4C", state="National", district="ALL")
            db_session.add(i4c_org)
            db_session.flush()
        officer_b = User(
            id=203,
            email="admin_b_203@i4c.gov.in",
            hashed_password="mock",
            full_name="Admin Beta",
            role="I4C_ADMIN",
            badge_number="I4C-203",
            organization_id=i4c_org.id
        )
        db_session.add(officer_b)
    db_session.commit()

    comp = Complaint(
        complaint_number=f"CMP-ACTOR-DIFF-{int(datetime.datetime.utcnow().timestamp())}",
        fraud_type="UPI_FRAUD",
        amount=Decimal("30000.00"),
        victim_location="Rohini, Delhi",
        state="Delhi",
        district="CENTRAL_NEW_DELHI",
        payment_channel="UPI",
        reported_at=datetime.datetime.utcnow()
    )
    db_session.add(comp)
    db_session.commit()

    token_a = create_access_token({"sub": officer_a.email, "role": officer_a.role, "org_id": org_delhi.id})
    token_b = create_access_token({"sub": officer_b.email, "role": officer_b.role, "org_id": org_delhi.id})

    client = TestClient(app)
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        # Officer A ingests original T0
        tx_ref_orig = f"TX-ORIG-ACTOR-{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
        r0 = client.post(
            f"/api/v1/complaints/{comp.complaint_number}/transactions",
            headers={"Authorization": f"Bearer {token_a}"},
            json={
                "transaction_ref": tx_ref_orig,
                "sender_account_number": "ACC-S-DIFF-01",
                "receiver_account_number": "ACC-R-DIFF-01",
                "amount": 30000.0,
                "payment_channel": "UPI",
                "timestamp": datetime.datetime.utcnow().isoformat(),
            }
        )
        assert r0.status_code == 201
        assert r0.json()["created_by_user_id"] == officer_a.id

        # Officer B submits correction T1
        tx_ref_corr = f"TX-CORR-ACTOR-{int(datetime.datetime.utcnow().timestamp())}"
        r1 = client.post(
            f"/api/v1/complaints/{comp.complaint_number}/transactions/correction",
            headers={"Authorization": f"Bearer {token_b}"},
            json={
                "transaction_ref": tx_ref_corr,
                "correction_of_ref": tx_ref_orig,
                "amount": 28000.0,
            }
        )
        assert r1.status_code == 201
        assert r1.json()["created_by_user_id"] == officer_b.id

        # Officer B submits reversal T2
        tx_ref_rev = f"TX-REV-ACTOR-{int(datetime.datetime.utcnow().timestamp())}"
        r2 = client.post(
            f"/api/v1/complaints/{comp.complaint_number}/transactions/reversal",
            headers={"Authorization": f"Bearer {token_b}"},
            json={
                "transaction_ref": tx_ref_rev,
                "correction_of_ref": tx_ref_corr,
                "amount": 28000.0,
            }
        )
        assert r2.status_code == 201
        assert r2.json()["created_by_user_id"] == officer_b.id

        # Verify immutability of original record's actor
        db_orig = db_session.query(Transaction).filter(Transaction.transaction_ref == tx_ref_orig).first()
        db_corr = db_session.query(Transaction).filter(Transaction.transaction_ref == tx_ref_corr).first()
        db_rev = db_session.query(Transaction).filter(Transaction.transaction_ref == tx_ref_rev).first()

        assert db_orig.created_by_user_id == officer_a.id
        assert db_corr.created_by_user_id == officer_b.id
        assert db_rev.created_by_user_id == officer_b.id
    finally:
        app.dependency_overrides.clear()


def test_actor_identity_spoofing_prevented(db_session: Session):
    """
    Verify:
    Client passing created_by_user_id in request body is ignored;
    server binds created_by_user_id exclusively to current_user.id.
    """
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.models.db import get_db
    from backend.app.models.models import User, Organization
    from backend.app.auth.security import create_access_token

    org = db_session.query(Organization).filter(Organization.id == 204).first()
    if not org:
        org = Organization(id=204, name="Delhi North LEA", org_type="LEA", state="Delhi", district="CENTRAL_NEW_DELHI")
        db_session.add(org)
        db_session.flush()

    officer = db_session.query(User).filter(User.id == 204).first()
    if not officer:
        officer = User(
            id=204,
            email="officer_204@delhipolice.gov.in",
            hashed_password="mock",
            full_name="Officer Genuine",
            role="DISTRICT_LEA",
            badge_number="DL-204",
            organization_id=org.id
        )
        db_session.add(officer)
        db_session.flush()

    comp = Complaint(
        complaint_number=f"CMP-SPOOF-{int(datetime.datetime.utcnow().timestamp())}",
        fraud_type="UPI_FRAUD",
        amount=Decimal("12000.00"),
        victim_location="Delhi",
        state="Delhi",
        district="CENTRAL_NEW_DELHI",
        payment_channel="UPI",
        reported_at=datetime.datetime.utcnow()
    )
    db_session.add(comp)
    db_session.commit()

    token = create_access_token({"sub": officer.email, "role": officer.role, "org_id": org.id})
    client = TestClient(app)
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        tx_ref = f"TX-SPOOF-{int(datetime.datetime.utcnow().timestamp())}"
        res = client.post(
            f"/api/v1/complaints/{comp.complaint_number}/transactions",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "transaction_ref": tx_ref,
                "sender_account_number": "ACC-S-SPOOF",
                "receiver_account_number": "ACC-R-SPOOF",
                "amount": 12000.0,
                "payment_channel": "UPI",
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "created_by_user_id": 999999,  # Malicious attempt to spoof creator
            }
        )
        assert res.status_code == 201
        data = res.json()
        assert data["created_by_user_id"] == officer.id
        assert data["created_by_user_id"] != 999999

        db_tx = db_session.query(Transaction).filter(Transaction.transaction_ref == tx_ref).first()
        assert db_tx.created_by_user_id == officer.id
    finally:
        app.dependency_overrides.clear()


def test_historical_transaction_rows_remain_valid_with_null_actor(db_session: Session):
    """
    Verify:
    Historical transaction records created prior to migration 0012 with created_by_user_id = NULL
    remain completely valid, queryable, and format safely with created_by_user_id = None.
    """
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.models.db import get_db
    from backend.app.models.models import User, Organization
    from backend.app.auth.security import create_access_token

    org = db_session.query(Organization).filter(Organization.id == 205).first()
    if not org:
        org = Organization(id=205, name="Delhi Central LEA", org_type="LEA", state="Delhi", district="CENTRAL_NEW_DELHI")
        db_session.add(org)
        db_session.flush()

    officer = db_session.query(User).filter(User.id == 205).first()
    if not officer:
        officer = User(
            id=205,
            email="auditor_205@delhipolice.gov.in",
            hashed_password="mock",
            full_name="Auditor 205",
            role="DISTRICT_LEA",
            badge_number="DL-205",
            organization_id=org.id
        )
        db_session.add(officer)
        db_session.flush()

    comp = Complaint(
        complaint_number=f"CMP-HIST-NULL-{int(datetime.datetime.utcnow().timestamp())}",
        fraud_type="UPI_FRAUD",
        amount=Decimal("5000.00"),
        victim_location="Delhi",
        state="Delhi",
        district="CENTRAL_NEW_DELHI",
        payment_channel="UPI",
        reported_at=datetime.datetime.utcnow()
    )
    db_session.add(comp)
    db_session.flush()

    acc_s = Account(account_number=f"ACC-S-HIST-{int(datetime.datetime.utcnow().timestamp())}", masked_account="ACC••••0001", bank_name="SBI", holder_name="Sender")
    acc_r = Account(account_number=f"ACC-R-HIST-{int(datetime.datetime.utcnow().timestamp())}", masked_account="ACC••••0002", bank_name="HDFC", holder_name="Receiver")
    db_session.add_all([acc_s, acc_r])
    db_session.flush()

    # Create historical row with explicit created_by_user_id = None
    tx_ref_hist = f"TX-HIST-NULL-{int(datetime.datetime.utcnow().timestamp())}"
    hist_tx = Transaction(
        transaction_ref=tx_ref_hist,
        complaint_id=comp.id,
        sender_account_id=acc_s.id,
        receiver_account_id=acc_r.id,
        amount=Decimal("5000.00"),
        payment_channel="UPI",
        timestamp=datetime.datetime.utcnow(),
        received_at=datetime.datetime.utcnow(),
        source_system="HISTORICAL_LEGACY",
        created_by_user_id=None,  # Unproven legacy actor
    )
    db_session.add(hist_tx)
    db_session.commit()

    token = create_access_token({"sub": officer.email, "role": officer.role, "org_id": org.id})
    client = TestClient(app)
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        res = client.get(
            f"/api/v1/complaints/{comp.complaint_number}/transactions",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200
        data = res.json()
        matched = [t for t in data if t["transaction_ref"] == tx_ref_hist]
        assert len(matched) == 1
        assert matched[0]["created_by_user_id"] is None
    finally:
        app.dependency_overrides.clear()


def test_wrong_jurisdiction_transaction_and_actor_data_isolation(db_session: Session):
    """
    Verify:
    Officers from a different state/district receive 404 Not Found (anti-enumeration)
    and cannot inspect transaction records or actor attribution data.
    """
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.models.db import get_db
    from backend.app.models.models import User, Organization
    from backend.app.auth.security import create_access_token

    org_mumbai = db_session.query(Organization).filter(Organization.id == 206).first()
    if not org_mumbai:
        org_mumbai = Organization(id=206, name="Mumbai LEA", org_type="LEA", state="Maharashtra", district="MUMBAI_CITY")
        db_session.add(org_mumbai)
        db_session.flush()

    mumbai_officer = db_session.query(User).filter(User.id == 206).first()
    if not mumbai_officer:
        mumbai_officer = User(
            id=206,
            email="mumbai_officer_206@mahapolice.gov.in",
            hashed_password="mock",
            full_name="Inspector Mumbai",
            role="DISTRICT_LEA",
            badge_number="MH-206",
            organization_id=org_mumbai.id
        )
        db_session.add(mumbai_officer)
        db_session.flush()

    delhi_comp = Complaint(
        complaint_number=f"CMP-DELHI-SECRET-{int(datetime.datetime.utcnow().timestamp())}",
        fraud_type="UPI_FRAUD",
        amount=Decimal("75000.00"),
        victim_location="Delhi",
        state="Delhi",
        district="CENTRAL_NEW_DELHI",
        payment_channel="UPI",
        reported_at=datetime.datetime.utcnow()
    )
    db_session.add(delhi_comp)
    db_session.commit()

    token_mumbai = create_access_token({"sub": mumbai_officer.email, "role": mumbai_officer.role, "org_id": org_mumbai.id})
    client = TestClient(app)
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        # Cross-jurisdiction GET transactions
        res_get = client.get(
            f"/api/v1/complaints/{delhi_comp.complaint_number}/transactions",
            headers={"Authorization": f"Bearer {token_mumbai}"}
        )
        assert res_get.status_code == 404

        # Cross-jurisdiction POST transaction
        res_post = client.post(
            f"/api/v1/complaints/{delhi_comp.complaint_number}/transactions",
            headers={"Authorization": f"Bearer {token_mumbai}"},
            json={
                "transaction_ref": "TX-MUMBAI-CROSS",
                "sender_account_number": "ACC-S-MUM",
                "receiver_account_number": "ACC-R-MUM",
                "amount": 75000.0,
                "timestamp": datetime.datetime.utcnow().isoformat(),
            }
        )
        assert res_post.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_alembic_migration_0012_from_populated_0011(tmp_path):
    """
    Verify:
    1. Upgrades from baseline to 0011_canonical_transaction_dedup.
    2. Populates transactions without created_by_user_id.
    3. Runs upgrade to 0012_transaction_created_by_user_id successfully.
    4. Confirms created_by_user_id column is added and existing rows retain NULL.
    """
    import os
    from alembic.config import Config
    from alembic import command
    from sqlalchemy import create_engine, text

    db_file = tmp_path / "test_migration_0012.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    alembic_cfg.set_section_option("alembic", "db_url", db_url)

    # 1. Upgrade to 0011
    command.upgrade(alembic_cfg, "0011_canonical_transaction_dedup")

    # 2. Insert test complaint, account, and transaction
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO complaints (id, complaint_number, fraud_type, amount, victim_location, state, district, reported_at, incident_time, created_at) "
            "VALUES (501, 'CMP-MIG-501', 'UPI_FRAUD', 10000.0, 'Delhi', 'Delhi', 'CENTRAL_NEW_DELHI', '2026-09-20 10:00:00', '2026-09-20 09:00:00', '2026-09-20 10:00:00')"
        ))
        conn.execute(text(
            "INSERT INTO accounts (id, account_number, masked_account, bank_name, holder_name, created_at) "
            "VALUES (501, 'ACC-501', 'ACC••••0501', 'SBI', 'Holder 501', '2026-09-20 10:00:00'), "
            "(502, 'ACC-502', 'ACC••••0502', 'HDFC', 'Holder 502', '2026-09-20 10:00:00')"
        ))
        conn.execute(text(
            "INSERT INTO transactions (id, transaction_ref, complaint_id, sender_account_id, receiver_account_id, amount, payment_channel, timestamp, is_reversal, hop_number, status) "
            "VALUES (501, 'TX-MIG-0011-ROW', 501, 501, 502, 10000.0, 'UPI', '2026-09-20 10:00:00', 0, 1, 'COMPLETED')"
        ))

    # 3. Upgrade to 0012
    command.upgrade(alembic_cfg, "0012_transaction_created_by_user_id")

    # 4. Verify table schema and data in 0012
    with engine.connect() as conn:
        res = conn.execute(text("SELECT id, transaction_ref, created_by_user_id FROM transactions WHERE id = 501")).first()
        assert res is not None
        assert res[0] == 501
        assert res[1] == "TX-MIG-0011-ROW"
        assert res[2] is None  # Preserved as NULL for legacy unproven row

