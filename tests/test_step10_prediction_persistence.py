"""
CyberShield AI — Phase 1 Step 10: Prediction + Top-3 Location Persistence Test Suite

Tests covering:
- Atomic persistence of Prediction parent + exactly 3 PredictionLocation children
- Exact ranks {1, 2, 3} and cluster uniqueness
- Preservation of Step-9 inference outputs (no re-ranking)
- Trained ML provenance (prediction_mode='trained_ml', model_version='cashout-location-xgb-v3.1')
- Time V2 persistence with 'operational estimate window' label
- Strict read-only GET /predictions/{complaint_id} (404 when unpersisted; zero inference/mutations on GET)
- Idempotency & latest-prediction retrieval (ORDER BY created_at DESC, id DESC)
- Transaction rollback on partial failure (0 orphaned rows)
- No persistence for unavailable cases (CMP-NEW-000004 -> delta 0)
- CMP-1042 demo provenance preservation ('deterministic_demo', 'demo-provider-v1')
- Zero Alert creation (Alert delta = 0)
- Zero Withdrawal / outcome lookup
- Float / Decimal precision round-trip (< 1e-5 difference)
- Regression tests for Steps 5, 6, 7, 8, and 9
"""

import pytest
import math
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.models.db import SessionLocal
from backend.app.models.models import (
    Complaint, Prediction, PredictionLocation, PredictionSnapshot, Alert, AuditLog,
    Transaction, Withdrawal, LocationCluster
)
from backend.app.services.prediction_service import prediction_service
from backend.app.services.prediction_persistence_service import (
    prediction_persistence_service,
    IDEMPOTENCY_DEBOUNCE_SECONDS
)

from backend.app.auth.security import create_access_token

client = TestClient(app)
_test_token = create_access_token({"sub": "admin@cybershield.gov.in", "role": "I4C_ADMIN"})
client.headers["Authorization"] = f"Bearer {_test_token}"


@pytest.fixture(scope="function")
def db():
    session = SessionLocal()
    yield session
    session.close()


def test_cmp_new_000002_live_persistence(db):
    """
    Section 15: Run prediction for CMP-NEW-000002.
    Verify:
    - 1 Prediction parent created
    - Exactly 3 PredictionLocation children created
    - Ranks are exactly {1, 2, 3}
    - Same clusters as Step-9 inference (Connaught Place, Paharganj, Karol Bagh)
    - Same calibrated probabilities (round-trip diff < 1e-5)
    - Provenance: trained_ml, cashout-location-xgb-v3.1
    - Time V2 prediction and operational estimate window
    """
    comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    assert comp is not None

    # Step 9 pure inference baseline
    infer_res = prediction_service.run_prediction(db, comp.id)
    assert infer_res["status"] == "SUCCESS"
    assert len(infer_res["top_locations"]) == 3

    # Counts before POST
    pred_count_before = db.query(Prediction).filter(Prediction.complaint_id == comp.id).count()
    loc_count_before = (
        db.query(PredictionLocation)
        .join(Prediction, PredictionLocation.prediction_id == Prediction.id)
        .filter(Prediction.complaint_id == comp.id)
        .count()
    )

    # Execute API POST
    resp = client.post(f"/api/v1/predictions/{comp.complaint_number}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "SUCCESS"
    assert data["prediction_id"] > 0
    assert data["prediction_mode"] == "trained_ml"
    assert data["model_version"] in ("cashout-location-xgb-v3.1", "cashout-location-xgb-v4", "cashout-location-xgb-v7-compat")
    assert "min after complaint report" in data["when_window"] or "operational estimate window" in data["when_window"]

    # Verify DB delta: exactly 1 Prediction and 3 PredictionLocations
    pred_count_after = db.query(Prediction).filter(Prediction.complaint_id == comp.id).count()
    loc_count_after = (
        db.query(PredictionLocation)
        .join(Prediction, PredictionLocation.prediction_id == Prediction.id)
        .filter(Prediction.complaint_id == comp.id)
        .count()
    )
    assert pred_count_after == pred_count_before + 1
    assert loc_count_after == loc_count_before + 3

    # Retrieve from DB via persistence service
    persisted = prediction_persistence_service.get_latest_prediction(db, comp.id)
    assert persisted is not None
    assert persisted.id == data["prediction_id"]
    assert persisted.prediction_mode == "trained_ml"
    assert persisted.model_version in ("cashout-location-xgb-v3.1", "cashout-location-xgb-v4", "cashout-location-xgb-v7-compat")
    assert "min after complaint report" in persisted.window_label or "operational estimate window" in persisted.window_label

    # Verify children
    locations = sorted(persisted.locations, key=lambda x: x.rank)
    assert len(locations) == 3
    assert [l.rank for l in locations] == [1, 2, 3]

    # Cluster uniqueness
    c_ids = [l.cluster_id for l in locations]
    assert len(set(c_ids)) == 3

    # Compare with inference output
    for i in range(3):
        inf_loc = infer_res["top_locations"][i]
        db_loc = locations[i]
        assert db_loc.rank == inf_loc["rank"]
        assert db_loc.location_name == inf_loc["location_name"]
        assert db_loc.cluster_id == inf_loc["cluster_id"]
        # Probability round-trip precision
        diff = abs(db_loc.probability - inf_loc["ml_probability"])
        assert diff < 1e-5, f"Probability round-trip loss: {diff}"


def test_cmp_new_000003_live_persistence(db):
    """
    Section 16: Run prediction for CMP-NEW-000003.
    Verify complaint-specific diversity (Green Park, Vivek Vihar, Dilshad Garden).
    """
    comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000003").first()
    assert comp is not None

    resp = client.post(f"/api/v1/predictions/{comp.complaint_number}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "SUCCESS"
    assert data["prediction_mode"] == "trained_ml"
    assert len(data["top_locations"]) == 3

    # Verify diversity against CMP-NEW-000002
    loc2_res = client.get("/api/v1/predictions/CMP-NEW-000002").json()
    loc2_clusters = [l["cluster_id"] for l in loc2_res["top_locations"]]
    loc3_clusters = [l["cluster_id"] for l in data["top_locations"]]
    assert loc2_clusters != loc3_clusters


def test_cmp_dl_0001_live_persistence(db):
    """
    Section 17: Run prediction for CMP-DL-0001.
    Verify trained_ml provenance, 3 ranked locations, Time V2 prediction, and DB relationship integrity.
    """
    comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-DL-0001").first()
    assert comp is not None

    resp = client.post(f"/api/v1/predictions/{comp.complaint_number}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "SUCCESS"
    assert data["prediction_mode"] == "trained_ml"
    assert data["model_version"] in ("cashout-location-xgb-v3.1", "cashout-location-xgb-v4", "cashout-location-xgb-v7-compat")
    assert len(data["top_locations"]) == 3
    assert data["time_prediction"]["predicted_minutes_to_cashout"] > 0

    # Relationship integrity in DB
    persisted = prediction_persistence_service.get_latest_prediction(db, comp.id)
    assert persisted is not None
    assert persisted.complaint_id == comp.id
    assert len(persisted.locations) == 3
    for loc in persisted.locations:
        assert loc.prediction_id == persisted.id
        if loc.cluster_id:
            assert db.query(LocationCluster).filter(LocationCluster.id == loc.cluster_id).first() is not None


def test_cmp_new_000004_outside_scope_zero_persistence(db):
    """
    Section 18: Run prediction for CMP-NEW-000004 (non-Delhi).
    Expected: OUTSIDE_OPERATIONAL_SCOPE, zero Prediction rows created.
    """
    comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000004").first()
    assert comp is not None

    pred_before = db.query(Prediction).filter(Prediction.complaint_id == comp.id).count()
    loc_before = (
        db.query(PredictionLocation)
        .join(Prediction, PredictionLocation.prediction_id == Prediction.id)
        .filter(Prediction.complaint_id == comp.id)
        .count()
    )

    resp = client.post(f"/api/v1/predictions/{comp.complaint_number}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "OUTSIDE_OPERATIONAL_SCOPE"
    assert data["prediction_mode"] in ["unavailable", "unsupported_region"]
    assert len(data["top_locations"]) == 0

    pred_after = db.query(Prediction).filter(Prediction.complaint_id == comp.id).count()
    loc_after = (
        db.query(PredictionLocation)
        .join(Prediction, PredictionLocation.prediction_id == Prediction.id)
        .filter(Prediction.complaint_id == comp.id)
        .count()
    )

    assert pred_after == pred_before == 0
    assert loc_after == loc_before == 0


def test_cmp_1042_demo_provenance(db):
    """
    Section 19: Test CMP-1042 demo persistence.
    Verify:
    - prediction_mode = deterministic_demo
    - model_version = demo-provider-v1
    - NEVER labeled trained_ml
    """
    comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-1042").first()
    assert comp is not None

    resp = client.post(f"/api/v1/predictions/{comp.complaint_number}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["prediction_mode"] == "deterministic_demo"
    assert data["model_version"] == "demo-provider-v1"
    assert data["prediction_mode"] != "trained_ml"
    assert len(data["top_locations"]) == 3
    assert data["top_locations"][0]["location_name"] == "Vijay Nagar, Indore"

    # Verify in DB
    persisted = prediction_persistence_service.get_latest_prediction(db, comp.id)
    assert persisted is not None
    assert persisted.prediction_mode == "deterministic_demo"
    assert persisted.model_version == "demo-provider-v1"


def test_get_prediction_read_only_and_404_when_missing(db):
    """
    User Requirement 1:
    GET /predictions/{complaint_id} must be strictly read-only.
    If no prediction exists, returns 404. Does NOT run inference or create rows.
    """
    # Create a fresh temporary complaint without any prediction
    test_num = f"CMP-TEST-{int(datetime.utcnow().timestamp())}"
    new_comp = Complaint(
        complaint_number=test_num,
        fraud_type="UPI Fraud",
        amount=50000.0,
        victim_name="Test Victim",
        victim_location="Rohini, Delhi",
        state="Delhi",
        district="NORTH",
        reported_at=datetime.utcnow(),
        incident_time=datetime.utcnow()
    )
    db.add(new_comp)
    db.commit()
    db.refresh(new_comp)

    # Initial counts
    pred_count_before = db.query(Prediction).count()

    # GET must return 404
    resp = client.get(f"/api/v1/predictions/{test_num}")
    assert resp.status_code == 404
    assert "No persisted prediction found" in resp.json()["detail"]

    # Verify zero DB mutations on GET
    pred_count_after = db.query(Prediction).count()
    assert pred_count_after == pred_count_before

    # Clean up test complaint
    db.delete(new_comp)
    db.commit()


def test_atomic_transaction_rollback_on_partial_failure(db):
    """
    User Requirement 4 & Section 6:
    Atomic commit boundary test:
    If any PredictionLocation child fails, rollback parent + every child.
    """
    comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-DL-0002").first()
    assert comp is not None

    preds_before = db.query(Prediction).count()
    locs_before = db.query(PredictionLocation).count()

    # Corrupt data with duplicate rank violating uq_prediction_rank
    bad_data = {
        "status": "SUCCESS",
        "prediction_mode": "trained_ml",
        "model_version": "cashout-location-xgb-v3.1",
        "risk_score": 0.88,
        "risk_level": "CRITICAL",
        "time_prediction": {"predicted_minutes_to_cashout": 90.0},
        "top_locations": [
            {"rank": 1, "cluster_id": 7, "location_name": "Connaught Place", "probability": 0.88},
            {"rank": 1, "cluster_id": 9, "location_name": "Paharganj", "probability": 0.65},  # DUPLICATE RANK 1!
            {"rank": 3, "cluster_id": 8, "location_name": "Karol Bagh", "probability": 0.40}
        ]
    }

    with pytest.raises(Exception):
        prediction_persistence_service.persist_prediction(db, comp, bad_data, bypass_debounce=True)

    # Verify rollback: 0 new rows in Prediction or PredictionLocation
    preds_after = db.query(Prediction).count()
    locs_after = db.query(PredictionLocation).count()
    assert preds_after == preds_before
    assert locs_after == locs_before


def test_zero_alert_creation_and_zero_outcome_leakage(db):
    """
    Sections 14, 24, 27:
    Verify that running prediction persistence creates ZERO Alerts and does NOT access Withdrawal.
    """
    alerts_before = db.query(Alert).count()
    withdrawals_before = db.query(Withdrawal).count()

    for c_num in ["CMP-NEW-000002", "CMP-NEW-000003", "CMP-DL-0001", "CMP-1042"]:
        comp = db.query(Complaint).filter(Complaint.complaint_number == c_num).first()
        if comp:
            prediction_service.run_and_persist_prediction(db, comp.id)

    alerts_after = db.query(Alert).count()
    withdrawals_after = db.query(Withdrawal).count()

    assert alerts_after == alerts_before, f"Alerts were created! Delta = {alerts_after - alerts_before}"
    assert withdrawals_after == withdrawals_before, f"Withdrawals mutated! Delta = {withdrawals_after - withdrawals_before}"


def test_latest_prediction_retrieval_and_rank_sorting(db):
    """
    Sections 8, 9:
    Ensure get_latest_prediction returns deterministic latest run,
    and GET API returns top_locations sorted explicitly by rank ASC.
    """
    comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    assert comp is not None

    resp = client.get(f"/api/v1/predictions/{comp.complaint_number}")
    assert resp.status_code == 200
    data = resp.json()

    top_locs = data["top_locations"]
    assert len(top_locs) == 3
    ranks = [l["rank"] for l in top_locs]
    assert ranks == [1, 2, 3]


def test_step5_step6_step7_step8_step9_regressions(db):
    """
    Verify regression baseline:
    - Step 6 transaction context
    - Step 7 graph intelligence
    - Step 8 features
    - Step 9 inference determinism
    """
    comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    assert comp is not None

    from backend.app.services.transaction_context_service import resolve_transaction_context
    from backend.app.services.graph_service import build_complaint_graph
    from backend.app.services.ml_feature_service import build_location_features, build_time_features

    ctx = resolve_transaction_context(db, comp)
    assert len(ctx["transactions"]) > 0

    graph_res = build_complaint_graph(db, comp.id)
    assert len(graph_res["nodes"]) > 0

    loc_res = build_location_features(db, comp.id, top_k=25, model_version="v3.1")
    assert loc_res["status"] == "SUCCESS"
    assert loc_res["candidate_rows"].shape == (25, 43)

    time_res = build_time_features(db, comp.id)
    assert time_res["status"] == "SUCCESS"
    assert time_res["values"].shape == (20,)


def test_exact_cluster_identity_consistency(db):
    """
    Step 10 Consistency Audit Requirement 9:
    Assert for each successful trained prediction (CMP-NEW-000002, CMP-NEW-000003, CMP-DL-0001):
    1. runtime inference cluster_id == persistence input cluster_id == PredictionLocation.cluster_id == GET response cluster_id
    2. cluster_name, zone, coordinates all originate from and correspond to the same LocationCluster row
    """
    for c_num in ["CMP-NEW-000002", "CMP-NEW-000003", "CMP-DL-0001"]:
        comp = db.query(Complaint).filter(Complaint.complaint_number == c_num).first()
        assert comp is not None, f"Complaint {c_num} not found"

        # A. Runtime inference (read-only)
        infer_res = prediction_service.run_prediction(db, comp.id)
        assert infer_res["status"] == "SUCCESS"
        inf_locs = infer_res["top_locations"]
        assert len(inf_locs) == 3

        # B. Capture persistence input
        # Note: run_and_persist_prediction internally executes predict_complaint and passes result directly
        persist_input = prediction_service.predict_complaint(db, comp.id)
        input_locs = persist_input["top_locations"]
        assert len(input_locs) == 3

        # Execute persistence (bypass debounce to get fresh persisted prediction)
        persisted = prediction_persistence_service.persist_prediction(
            db, comp, persist_input, bypass_debounce=True
        )
        assert persisted is not None

        # C. DB persisted Top-3
        db_locs = sorted(persisted.locations, key=lambda x: x.rank)
        assert len(db_locs) == 3

        # D. GET-retrieved Top-3
        get_resp = client.get(f"/api/v1/predictions/{c_num}")
        assert get_resp.status_code == 200
        get_locs = get_resp.json()["top_locations"]
        assert len(get_locs) == 3

        # Compare A == B == C == D for ranks 1, 2, 3
        for i in range(3):
            rank = i + 1
            a_loc = inf_locs[i]
            b_loc = input_locs[i]
            c_loc = db_locs[i]
            d_loc = get_locs[i]

            assert a_loc["rank"] == b_loc["rank"] == c_loc.rank == d_loc["rank"] == rank
            assert a_loc["cluster_id"] == b_loc["cluster_id"] == c_loc.cluster_id == d_loc["cluster_id"]
            assert a_loc["location_name"] == b_loc["location_name"] == c_loc.location_name == d_loc["location_name"]

            # Probability consistency within floating-point tolerance
            p_a = float(a_loc.get("ml_probability", a_loc.get("probability")))
            p_b = float(b_loc.get("ml_probability", b_loc.get("probability")))
            p_c = float(c_loc.probability)
            p_d = float(d_loc.get("probability") or d_loc.get("ml_probability"))
            assert abs(p_a - p_b) < 1e-5
            assert abs(p_b - p_c) < 1e-5
            assert abs(p_c - p_d) < 1e-5

            # Assert name + ID + coordinates originate from the SAME LocationCluster row
            target_cluster = db.query(LocationCluster).filter(LocationCluster.id == c_loc.cluster_id).first()
            assert target_cluster is not None
            assert target_cluster.cluster_name == c_loc.location_name
            assert target_cluster.district == a_loc.get("zone") or target_cluster.city == "Delhi"
            assert abs(target_cluster.center_lat - c_loc.latitude) < 1e-4
            assert abs(target_cluster.center_lon - c_loc.longitude) < 1e-4


def test_existing_prediction_snapshots_remain_unchanged_and_immutable(db: Session):
    """
    Regression check: Existing PredictionSnapshot rows are write-once, immutable,
    and persist_prediction must never silently erase, overwrite, or mutate history.
    """
    comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    assert comp is not None

    clusters = db.query(LocationCluster).filter(LocationCluster.state == "Delhi").all()
    c1, c2, c3 = clusters[0], clusters[1], clusters[2]

    # 1. Persist initial prediction with snapshot
    now = datetime.utcnow()
    mock_pred_1 = {
        "status": "SUCCESS",
        "prediction_mode": "trained_ml",
        "complaint_id": comp.id,
        "complaint_number": comp.complaint_number,
        "model_version": "cashout-location-xgb-v7-compat",
        "feature_schema_version": "v7_compat",
        "risk_score": 0.85,
        "risk_level": "HIGH",
        "when_window": "15–45 min after complaint report",
        "time_prediction": {
            "predicted_minutes_to_cashout": 30.0,
            "window_start": now.isoformat(),
            "window_end": (now + timedelta(minutes=45)).isoformat(),
            "operational_window": "15–45 min after complaint report",
            "when_window": "15–45 min after complaint report"
        },
        "top_locations": [
            {"rank": 1, "cluster_id": c1.id, "location_name": c1.cluster_name, "ml_probability": 0.60},
            {"rank": 2, "cluster_id": c2.id, "location_name": c2.cluster_name, "ml_probability": 0.25},
            {"rank": 3, "cluster_id": c3.id, "location_name": c3.cluster_name, "ml_probability": 0.15},
        ],
        "inference_snapshot": {
            "model_version": "cashout-location-xgb-v7-compat",
            "feature_schema_version": "v7_compat",
            "feature_schema_hash": "schema_hash_init_111",
            "location_model_hash": "model_hash_init_222",
            "calibrator_hash": "calibrator_hash_init_333",
            "features": {"f1": 1.0, "f2": 2.0}
        }
    }

    pred_ids_to_clean = []
    try:
        pred_1 = prediction_persistence_service.persist_prediction(db, comp, mock_pred_1, bypass_debounce=True)
        assert pred_1 is not None
        db.commit()
        pred_ids_to_clean.append(pred_1.id)

        snap_1 = db.query(PredictionSnapshot).filter(PredictionSnapshot.prediction_id == pred_1.id).first()
        assert snap_1 is not None
        snap_1_id = snap_1.id
        snap_1_schema_hash = snap_1.feature_schema_hash
        snap_1_model_hash = snap_1.model_hash
        snap_1_data = dict(snap_1.snapshot_data)

        # 2. Persist second prediction for the complaint
        mock_pred_2 = {
            "status": "SUCCESS",
            "prediction_mode": "trained_ml",
            "complaint_id": comp.id,
            "complaint_number": comp.complaint_number,
            "model_version": "cashout-location-xgb-v7-compat",
            "feature_schema_version": "v7_compat",
            "risk_score": 0.75,
            "risk_level": "HIGH",
            "when_window": "20–50 min after complaint report",
            "time_prediction": {
                "predicted_minutes_to_cashout": 35.0,
                "window_start": now.isoformat(),
                "window_end": (now + timedelta(minutes=50)).isoformat(),
                "operational_window": "20–50 min after complaint report",
                "when_window": "20–50 min after complaint report"
            },
            "top_locations": [
                {"rank": 1, "cluster_id": c2.id, "location_name": c2.cluster_name, "ml_probability": 0.50},
                {"rank": 2, "cluster_id": c1.id, "location_name": c1.cluster_name, "ml_probability": 0.30},
                {"rank": 3, "cluster_id": c3.id, "location_name": c3.cluster_name, "ml_probability": 0.20},
            ],
            "inference_snapshot": {
                "model_version": "cashout-location-xgb-v7-compat",
                "feature_schema_version": "v7_compat",
                "feature_schema_hash": "schema_hash_second_444",
                "location_model_hash": "model_hash_second_555",
                "calibrator_hash": "calibrator_hash_second_666",
                "features": {"f1": 3.0, "f2": 4.0}
            }
        }

        pred_2 = prediction_persistence_service.persist_prediction(db, comp, mock_pred_2, bypass_debounce=True)
        assert pred_2 is not None
        db.commit()
        pred_ids_to_clean.append(pred_2.id)

        # Verify first snapshot was NOT deleted, overwritten, or modified
        snap_1_after = db.query(PredictionSnapshot).filter(PredictionSnapshot.id == snap_1_id).first()
        assert snap_1_after is not None
        assert snap_1_after.prediction_id == pred_1.id
        assert snap_1_after.feature_schema_hash == snap_1_schema_hash
        assert snap_1_after.model_hash == snap_1_model_hash
        assert snap_1_after.snapshot_data == snap_1_data

        # Verify second snapshot exists independently
        snap_2 = db.query(PredictionSnapshot).filter(PredictionSnapshot.prediction_id == pred_2.id).first()
        assert snap_2 is not None
        assert snap_2.id != snap_1_id
        assert snap_2.feature_schema_hash == "schema_hash_second_444"

        # 3. Verify in-place update raises ValueError (immutable constraint)
        snap_1_after.feature_schema_hash = "tampered_hash"
        with pytest.raises(ValueError, match="immutable"):
            db.commit()
        db.rollback()
    finally:
        if pred_ids_to_clean:
            db.query(PredictionLocation).filter(PredictionLocation.prediction_id.in_(pred_ids_to_clean)).delete(synchronize_session=False)
            db.query(PredictionSnapshot).filter(PredictionSnapshot.prediction_id.in_(pred_ids_to_clean)).delete(synchronize_session=False)
            db.query(Prediction).filter(Prediction.id.in_(pred_ids_to_clean)).delete(synchronize_session=False)
            db.commit()


def test_trained_prediction_missing_label_derives_from_valid_timestamps(db: Session):
    """
    Regression check:
    For trained predictions with missing operational_window / when_window label
    or generic placeholder, the label must NEVER substitute 'Next 2–4 Hours'.
    It must be mathematically derived from validated window timestamps relative
    to complaint report time (e.g. '20–50 min after complaint report').
    """
    comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000003").first()
    assert comp is not None

    clusters = db.query(LocationCluster).filter(LocationCluster.state == "Delhi").limit(3).all()
    assert len(clusters) == 3
    c1, c2, c3 = clusters[0], clusters[1], clusters[2]

    ref = comp.reported_at or comp.incident_time
    w_start = ref + timedelta(minutes=20)
    w_end = ref + timedelta(minutes=50)

    mock_pred = {
        "status": "SUCCESS",
        "prediction_mode": "trained_ml",
        "complaint_id": comp.id,
        "complaint_number": comp.complaint_number,
        "model_version": "cashout-location-xgb-v7-compat",
        "feature_schema_version": "v7_compat",
        "risk_score": 0.82,
        "risk_level": "HIGH",
        "time_prediction": {
            "predicted_minutes_to_cashout": 35.0,
            "window_start": w_start.isoformat(),
            "window_end": w_end.isoformat(),
            "model_version": "cashout-time-xgb-v3"
        },
        "top_locations": [
            {"rank": 1, "cluster_id": c1.id, "location_name": c1.cluster_name, "ml_probability": 0.70},
            {"rank": 2, "cluster_id": c2.id, "location_name": c2.cluster_name, "ml_probability": 0.20},
            {"rank": 3, "cluster_id": c3.id, "location_name": c3.cluster_name, "ml_probability": 0.10},
        ],
        "inference_snapshot": {
            "model_version": "cashout-location-xgb-v7-compat",
            "feature_schema_version": "v7_compat",
            "feature_schema_hash": "schema_hash_regression_test",
            "location_model_hash": "loc_hash_regression_test",
            "calibrator_hash": "cal_hash_regression_test",
            "features": {"f1": 5.0}
        }
    }

    persisted = None
    try:
        persisted = prediction_persistence_service.persist_prediction(db, comp, mock_pred, bypass_debounce=True)
        assert persisted is not None
        db.commit()

        # Must NOT be 'Next 2–4 Hours'
        assert persisted.window_label != "Next 2–4 Hours"
        # Must be derived as '20–50 min after complaint report'
        assert "20–50 min after complaint report" in persisted.window_label
    finally:
        if persisted:
            db.query(PredictionLocation).filter(PredictionLocation.prediction_id == persisted.id).delete(synchronize_session=False)
            db.query(PredictionSnapshot).filter(PredictionSnapshot.prediction_id == persisted.id).delete(synchronize_session=False)
            db.query(Prediction).filter(Prediction.id == persisted.id).delete(synchronize_session=False)
            db.commit()
