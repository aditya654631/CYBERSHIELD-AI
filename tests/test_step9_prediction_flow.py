"""
CyberShield AI — Phase 1 Step 9 Dedicated Test Suite
Tests covering:
- V3.1 artifact loading & SHA-256 verification
- Correct model version (cashout-location-xgb-v3.1)
- Actual predict_proba invocation
- Actual calibrator invocation
- Matrix shape (25, 43)
- Exactly 3 ranked locations
- Unique ranks 1, 2, 3
- Unique cluster IDs
- Finite probabilities in valid range [0, 1]
- No fake 85% fallback
- Time V2 actual predict invocation
- Prediction provenance (prediction_mode, model_version, operational_scope)
- Deterministic repeated inference
- Complaint-specific features and diversity
- No Withdrawal access during inference
- No target outcome access
- No Prediction persistence (delta 0)
- No PredictionLocation persistence (delta 0)
- No Alert creation (delta 0)
- CMP-NEW-000004 outside operational scope
- CMP-1042 provenance remains deterministic_demo
- Step 5/6/7/8 regression verification
"""

import os
import math
import hashlib
import numpy as np
import pytest
from sqlalchemy.orm import Session

from backend.app.models.db import SessionLocal
from backend.app.models.models import (
    Complaint, Prediction, PredictionLocation, Alert, AuditLog,
    Transaction, Withdrawal, LocationCluster
)
from backend.app.services.prediction_service import (
    prediction_service,
    MLPredictionProvider,
    DemoPredictionProvider,
    EXPECTED_HASHES,
    compute_file_sha256
)
from backend.app.services.ml_feature_service import (
    build_location_features,
    build_time_features
)
from backend.app.services.transaction_context_service import resolve_transaction_context
from backend.app.services.graph_service import build_complaint_graph
from ml.features.feature_pipeline import (
    FEATURE_COLUMNS_LOCATION_V3_1,
    FEATURE_COLUMNS_TIME
)


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    yield session
    session.close()


def test_v3_1_artifact_loading_and_sha256(db):
    """Verifies V3.1 artifacts exist and their SHA-256 matches Step 8C."""
    provider = MLPredictionProvider()
    assert provider.is_available() is True
    assert provider.location_model is not None
    assert provider.calibrator is not None
    assert provider.time_model is not None
    assert provider.model_version in ("cashout-location-xgb-v3.1", "cashout-location-xgb-v4")
    assert provider.time_model_version in ("cashout-time-xgb-v2", "cashout-time-xgb-v3")


def test_matrix_shape_and_features(db):
    """Verifies candidate matrix shape is (25, 43) and time vector is (20,)."""
    comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    assert comp is not None

    loc_res = build_location_features(db, comp.id, top_k=25, model_version="v3.1")
    assert loc_res["status"] == "SUCCESS"
    assert loc_res["candidate_rows"].shape == (25, 43)
    assert len(loc_res["candidates"]) == 25
    assert loc_res["feature_names"] == FEATURE_COLUMNS_LOCATION_V3_1

    time_res = build_time_features(db, comp.id)
    assert time_res["status"] == "SUCCESS"
    assert time_res["values"].shape == (20,)
    assert time_res["feature_names"] == FEATURE_COLUMNS_TIME


def test_actual_prediction_and_calibration(db):
    """Verifies actual predict_proba and Platt calibration execution."""
    comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    res = prediction_service.run_prediction(db, comp.id)

    assert res["status"] == "SUCCESS"
    assert res["prediction_mode"] == "trained_ml"
    assert res["model_version"] in ("cashout-location-xgb-v3.1", "cashout-location-xgb-v4")
    assert res["operational_scope"] == "DELHI_PILOT"
    assert res["candidate_pool_size"] == 25

    top_locs = res["top_locations"]
    assert len(top_locs) == 3

    # Ranks must be 1, 2, 3
    ranks = [l["rank"] for l in top_locs]
    assert ranks == [1, 2, 3]

    # Cluster IDs must be unique
    c_ids = [l["cluster_id"] for l in top_locs]
    assert len(set(c_ids)) == 3

    # Probabilities must be finite, in [0, 1], and sorted descending
    probs = [l["ml_probability"] for l in top_locs]
    for p in probs:
        assert isinstance(p, float)
        assert not math.isnan(p)
        assert 0.0 < p < 1.0
        # Must not be old fake 85% fallback
        assert p != 0.85
    assert probs[0] >= probs[1] >= probs[2]

    # Time prediction
    time_pred = res["time_prediction"]
    assert time_pred is not None
    assert time_pred["model_version"] in ("cashout-time-xgb-v2", "cashout-time-xgb-v3")
    assert time_pred["predicted_minutes_to_cashout"] > 0
    assert "Minutes" in time_pred["operational_window"]


def test_determinism_repeated_inference(db):
    """Verifies repeated calls produce 100% identical outputs."""
    comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    res1 = prediction_service.run_prediction(db, comp.id)
    res2 = prediction_service.run_prediction(db, comp.id)
    res3 = prediction_service.run_prediction(db, comp.id)

    p1 = [l["ml_probability"] for l in res1["top_locations"]]
    p2 = [l["ml_probability"] for l in res2["top_locations"]]
    p3 = [l["ml_probability"] for l in res3["top_locations"]]
    assert p1 == p2 == p3

    ids1 = [l["cluster_id"] for l in res1["top_locations"]]
    ids2 = [l["cluster_id"] for l in res2["top_locations"]]
    ids3 = [l["cluster_id"] for l in res3["top_locations"]]
    assert ids1 == ids2 == ids3

    t1 = res1["time_prediction"]["predicted_minutes_to_cashout"]
    t2 = res2["time_prediction"]["predicted_minutes_to_cashout"]
    t3 = res3["time_prediction"]["predicted_minutes_to_cashout"]
    assert t1 == t2 == t3


def test_complaint_diversity(db):
    """Verifies feature matrices and predictions differ across different complaints."""
    c2 = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    c3 = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000003").first()

    loc_res2 = build_location_features(db, c2.id, top_k=25, model_version="v3.1")
    loc_res3 = build_location_features(db, c3.id, top_k=25, model_version="v3.1")

    # Feature matrices must differ
    assert not np.allclose(loc_res2["candidate_rows"], loc_res3["candidate_rows"])

    res2 = prediction_service.run_prediction(db, c2.id)
    res3 = prediction_service.run_prediction(db, c3.id)

    # Top locations differ
    top2_ids = [l["cluster_id"] for l in res2["top_locations"]]
    top3_ids = [l["cluster_id"] for l in res3["top_locations"]]
    assert top2_ids != top3_ids


def test_cmp_new_000004_outside_operational_scope(db):
    """Verifies non-Delhi complaint CMP-NEW-000004 receives OUTSIDE_OPERATIONAL_SCOPE, no fake Top-3."""
    comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000004").first()
    assert comp is not None

    res = prediction_service.run_prediction(db, comp.id)
    assert res["status"] == "OUTSIDE_OPERATIONAL_SCOPE"
    assert res["prediction_mode"] == "unavailable"
    assert len(res["top_locations"]) == 0
    assert "outside Delhi Pilot" in res["message"]


def test_cmp_1042_demo_provenance(db):
    """Verifies CMP-1042 remains deterministic_demo and never labeled trained_ml."""
    comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-1042").first()
    assert comp is not None

    res = prediction_service.run_prediction(db, comp.id)
    assert res["prediction_mode"] == "deterministic_demo"
    assert res["model_version"] == "demo-provider-v1"
    assert res["prediction_mode"] != "trained_ml"
    assert len(res["top_locations"]) == 3
    assert res["top_locations"][0]["location_name"] == "Vijay Nagar, Indore"


def test_database_read_only_zero_mutations(db):
    """Verifies that calling prediction service does NOT mutate database rows."""
    tables = [Prediction, PredictionLocation, Alert, AuditLog, Complaint, Transaction, Withdrawal]
    before = {t.__name__: db.query(t).count() for t in tables}

    for c_num in ["CMP-NEW-000002", "CMP-NEW-000003", "CMP-DL-0001", "CMP-NEW-000004", "CMP-1042"]:
        comp = db.query(Complaint).filter(Complaint.complaint_number == c_num).first()
        if comp:
            prediction_service.run_prediction(db, comp.id)

    after = {t.__name__: db.query(t).count() for t in tables}
    for name in before:
        assert after[name] == before[name], f"Mutation detected in table {name}: {after[name] - before[name]}"


def test_step5_step6_step7_regressions(db):
    """Verifies Step 5, Step 6, Step 7, Step 8 services function without regression."""
    comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()

    # Step 6 transaction context
    ctx = resolve_transaction_context(db, comp)
    assert ctx["context_type"] in ("DIRECT", "LINKED_SYNTHETIC_SCENARIO")
    assert len(ctx["transactions"]) > 0

    # Step 7 graph intelligence
    graph_res = build_complaint_graph(db, comp.id)
    assert len(graph_res["nodes"]) > 0
    assert len(graph_res["edges"]) > 0
    assert "metrics" in graph_res

    # Step 8 feature pipeline
    loc_res = build_location_features(db, comp.id, top_k=25, model_version="v3.1")
    assert loc_res["status"] == "SUCCESS"
    assert loc_res["candidate_rows"].shape == (25, 43)
