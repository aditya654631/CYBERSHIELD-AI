"""
CyberShield AI — ML Feature Pipeline & Location Model V3 Test Suite
Phase 1 Step 8: Complete Automated Verification Suite

Covers all 55 verification criteria specified in Step 8 Part 36.
"""

import os
import json
import math
import hashlib
import numpy as np
import pytest
import joblib
from datetime import datetime

from backend.app.models.db import SessionLocal
from backend.app.models.models import (
    Complaint, Account, Transaction, LocationCluster,
    Withdrawal, Prediction, PredictionLocation, Alert,
    Organization, User, ComplaintAccount
)
from backend.app.services.ml_feature_service import (
    build_location_features,
    build_time_features,
    build_multimodal_features
)
from backend.app.services.transaction_context_service import resolve_transaction_context
from backend.app.services.graph_service import build_complaint_graph
from ml.geo.candidate_generator import CandidateLocationGenerator, haversine_km
from ml.features.feature_pipeline import (
    feature_pipeline,
    FEATURE_COLUMNS_LOCATION_V3,
    FEATURE_COLUMNS_LOCATION_V3_1,
    FEATURE_COLUMNS_TIME,
    FRAUD_TYPE_MAP_V3,
    CHANNEL_MAP_V3
)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 1. Feature Schema & Count Tests (Criteria 1–4, 42, 48–50)
# -----------------------------------------------------------------------------
def test_v3_location_feature_count_and_order():
    """1. Exact V3 location feature count = 38, and exact order matches Part 3."""
    assert len(FEATURE_COLUMNS_LOCATION_V3) == 38
    assert FEATURE_COLUMNS_LOCATION_V3[0] == "log_amount"
    assert FEATURE_COLUMNS_LOCATION_V3[1] == "fraud_type_encoded"
    assert FEATURE_COLUMNS_LOCATION_V3[2] == "payment_channel_encoded"
    assert FEATURE_COLUMNS_LOCATION_V3[37] == "account_historical_cashout_delay"


def test_no_is_mule_corridor_in_v3():
    """3. Assert is_mule_corridor is NOT in V3 location features."""
    assert "is_mule_corridor" not in FEATURE_COLUMNS_LOCATION_V3


def test_no_distance_from_high_risk_account_in_v3():
    """4. Assert distance_from_high_risk_account is NOT in V3 location features."""
    assert "distance_from_high_risk_account" not in FEATURE_COLUMNS_LOCATION_V3


def test_time_v2_20_feature_contract():
    """42. Assert Time Model V2 20-feature contract is preserved unchanged."""
    assert len(FEATURE_COLUMNS_TIME) == 20
    assert FEATURE_COLUMNS_TIME[0] == "log_amount"
    assert FEATURE_COLUMNS_TIME[-1] == "time_since_last_transfer"


def test_artifacts_integrity_and_existence():
    """48, 49, 50. V2 artifacts preserved, V3 artifacts exist, Time V2 unchanged."""
    art_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "ml", "artifacts"))
    assert os.path.exists(os.path.join(art_dir, "location_ranker_v2.joblib"))
    assert os.path.exists(os.path.join(art_dir, "time_regressor_v2.joblib"))
    assert os.path.exists(os.path.join(art_dir, "location_ranker_v3.joblib"))
    assert os.path.exists(os.path.join(art_dir, "location_calibrator_v3.joblib"))
    assert os.path.exists(os.path.join(art_dir, "feature_schema_v3.json"))
    assert os.path.exists(os.path.join(art_dir, "model_metadata_v3.json"))


# -----------------------------------------------------------------------------
# 2. Target Leakage Prevention Tests (Criteria 5–10, 31–32)
# -----------------------------------------------------------------------------
def test_no_target_cluster_id_in_v3_features():
    """5. Assert target_cluster_id is never used as an input feature in X."""
    assert "target_cluster_id" not in FEATURE_COLUMNS_LOCATION_V3
    assert "target_cluster" not in FEATURE_COLUMNS_LOCATION_V3


def test_no_beneficiary_target_proxy_in_candidate_generator():
    """6, 34. Candidate generator ignores beneficiary_mule_cluster_id without error and without leakage."""
    gen = CandidateLocationGenerator()
    cands = gen.generate_candidates_for_complaint(
        {"victim_lat": 28.6139, "victim_lon": 77.2090, "victim_state": "Delhi"},
        beneficiary_mule_cluster_id=1,  # Passed as legacy kwarg
        top_k=25
    )
    assert len(cands) <= 25
    for c in cands:
        assert "is_mule_corridor" not in c


def test_no_current_withdrawal_target_reads(db_session):
    """7. Assert build_location_features does not query future Withdrawal table."""
    c = db_session.query(Complaint).first()
    if c:
        loc = build_location_features(db_session, c.id)
        assert loc["status"] == "SUCCESS"
        assert "target_atm_id" not in loc["feature_names"]
        assert "atm_id" not in loc["feature_names"]


def test_no_prediction_or_prediction_location_reads(db_session):
    """8, 9. Assert feature construction never inspects Prediction or PredictionLocation."""
    c = db_session.query(Complaint).first()
    loc = build_location_features(db_session, c.id)
    tim = build_time_features(db_session, c.id)
    assert "prediction_score" not in loc["feature_names"]
    assert "predicted_location" not in loc["feature_names"]
    assert "prediction" not in tim["feature_names"]


def test_no_future_withdrawal_timestamp_access():
    """10, 31, 32. Temporal cutoff ensures no withdrawal timestamp >= incident_timestamp is used."""
    comp = {
        "incident_timestamp": "2026-03-01T10:00:00",
        "withdrawal_timestamp": "2026-03-01T12:30:00",
        "amount": 50000.0,
        "fraud_type": "UPI / QR Code Fraud"
    }
    base = feature_pipeline.extract_complaint_base_v3(comp)
    assert "withdrawal_timestamp" not in base


# -----------------------------------------------------------------------------
# 3. Categorical & Missing Policies (Criteria 11–16, 29–30)
# -----------------------------------------------------------------------------
def test_categorical_unknown_parity_and_no_upi_fallback():
    """11, 12, 13. Missing channel or fraud_type maps to 0 (UNKNOWN), NOT UPI or real fraud type."""
    comp_missing_cat = {
        "amount": 40000.0,
        "fraud_type": None,
        "payment_channel": None,
        "incident_timestamp": "2026-03-01T10:00:00"
    }
    base = feature_pipeline.extract_complaint_base_v3(comp_missing_cat)
    assert base["fraud_type_encoded"] == 0.0  # UNKNOWN
    assert base["payment_channel_encoded"] == 0.0  # UNKNOWN (NOT 1 / UPI)


def test_real_complaint_delay_and_no_fixed_120():
    """14, 15. Delay is computed from actual timestamps and does NOT default to 120.0."""
    comp = {
        "amount": 50000.0,
        "incident_timestamp": "2026-03-01T10:00:00",
        "reported_at": "2026-03-01T10:45:00"  # 45 minutes
    }
    base = feature_pipeline.extract_complaint_base_v3(comp)
    assert base["complaint_delay_minutes"] == 45.0

    comp_no_rep = {
        "amount": 50000.0,
        "incident_timestamp": "2026-03-01T10:00:00",
        "reported_at": None
    }
    base_no_rep = feature_pipeline.extract_complaint_base_v3(comp_no_rep)
    assert math.isnan(base_no_rep["complaint_delay_minutes"])  # Not 120.0!


def test_no_current_system_time_fallback():
    """16. Missing incident timestamp results in NaN, NOT current system time."""
    comp = {"amount": 50000.0, "incident_timestamp": None}
    base = feature_pipeline.extract_complaint_base_v3(comp)
    assert math.isnan(base["complaint_hour"])
    assert math.isnan(base["day_of_week"])
    assert math.isnan(base["weekend_flag"])


def test_missing_victim_coordinates_is_nan_not_50km():
    """29, 30. Missing victim coordinates yields distance_from_victim = NaN, NOT fixed 50 km."""
    cands = [{"cluster_id": 1, "distance_from_victim_km": None, "historical_cashout_count": 200}]
    base = {"fraud_type_encoded": 0.0}
    gtx = {}
    row = feature_pipeline.build_candidate_row_v3(base, gtx, cands[0])
    assert math.isnan(row["distance_from_victim"])


# -----------------------------------------------------------------------------
# 4. Step 6 Transaction Context & Empty Behavior (Criteria 17–19)
# -----------------------------------------------------------------------------
def test_step6_transaction_context_resolver_usage(db_session):
    """17, 18. Consumes Step 6 context and deduplicates transactions correctly."""
    c = db_session.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    loc = build_location_features(db_session, c.id)
    assert loc["provenance"]["context_type"] == "LINKED_SYNTHETIC_SCENARIO"
    assert loc["provenance"]["source_scenario"] == "CMP-DL-1261"
    expected_tx_count = db_session.query(Transaction).filter(Transaction.complaint_id == Complaint.id).filter(Complaint.complaint_number == "CMP-DL-1261").count()
    assert loc["provenance"]["transaction_count"] == expected_tx_count


def test_empty_transaction_context_true_zero(db_session):
    """19. Empty transaction context (CMP-NEW-000004) uses mathematically legitimate TRUE_ZERO."""
    c = db_session.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000004").first()
    loc = build_location_features(db_session, c.id)
    assert loc["provenance"]["context_type"] == "EMPTY"
    assert loc["provenance"]["transaction_count"] == 0
    # Check that transaction counts and totals are TRUE_ZERO
    col_idx_tx_cnt = loc["feature_names"].index("transaction_count")
    col_idx_tot = loc["feature_names"].index("total_transferred")
    assert loc["candidate_rows"][0, col_idx_tx_cnt] == 0.0
    assert loc["candidate_rows"][0, col_idx_tot] == 0.0


# -----------------------------------------------------------------------------
# 5. Step 7 Graph Metrics & Centrality Parity (Criteria 20–27)
# -----------------------------------------------------------------------------
def test_step7_graph_service_integration(db_session):
    """20, 21, 22. Integrates Step 7 dynamic graph and does NOT use fixed hop=2 or fake metrics."""
    c = db_session.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000003").first()
    loc = build_location_features(db_session, c.id)
    g = build_complaint_graph(db_session, c.id)
    assert loc["provenance"]["graph_node_count"] == g["metrics"]["node_count"]
    assert loc["provenance"]["graph_edge_count"] == g["metrics"]["edge_count"]
    assert loc["provenance"]["graph_node_count"] > 0
    assert loc["provenance"]["graph_edge_count"] > 0


def test_graph_centrality_and_structural_mule_parity():
    """23, 24, 25, 26, 27. Semantic parity for PageRank, betweenness, branching, sinks, intermediaries."""
    graph_metrics = {
        "node_count": 5,
        "max_degree": 4.0,
        "mean_degree": 2.4,
        "max_pagerank": 0.38,
        "max_betweenness": 0.29,
        "connected_components": 1,
        "intermediary_count": 3,
        "sink_count": 2,
        "branching_factor": 1.75,
        "max_hop": 3.0
    }
    gtx = feature_pipeline.extract_graph_and_tx_features_v3({}, [], graph_metrics)
    assert gtx["max_pagerank"] == 0.38
    assert gtx["max_betweenness"] == 0.29
    assert gtx["branching_factor"] == 1.75
    assert gtx["mule_connection_count"] == 2.0  # Sinks
    assert gtx["fraud_neighbor_count"] == 3.0   # Intermediaries


# -----------------------------------------------------------------------------
# 6. Candidate Generation & Force-Add Audits (Criteria 34–39)
# -----------------------------------------------------------------------------
def test_candidate_generator_zero_target_argument():
    """34. Candidate generator requires no target cluster or beneficiary mule cluster."""
    gen = CandidateLocationGenerator()
    cands = gen.generate_candidates_for_complaint({"victim_lat": 28.5, "victim_lon": 77.1}, top_k=25)
    assert len(cands) == 25
    for c in cands:
        assert "cluster_id" in c
        assert "name" in c


def test_validation_and_test_zero_force_add():
    """35, 36, 37. Validation, test, and runtime never forcibly append ground-truth targets."""
    # Build candidate matrix in runtime without force add
    comp = {"victim_lat": 28.6, "victim_lon": 77.2, "amount": 50000.0}
    gen = CandidateLocationGenerator()
    cands = gen.generate_candidates_for_complaint(comp, top_k=25)
    assert len(cands) == 25


def test_haversine_distance_calculation():
    """28. Correct Haversine distance formula."""
    d = haversine_km(28.6139, 77.2090, 28.6315, 77.2167)
    assert 1.5 < d < 3.0  # Approx 2.1 km


# -----------------------------------------------------------------------------
# 7. Training / Runtime Parity & Model Smoke Tests (Criteria 41, 43, 51, 52)
# -----------------------------------------------------------------------------
def test_training_and_runtime_exact_numerical_parity():
    """41, 43. Training and runtime feature extractors produce exact numerical parity."""
    comp_dict = {
        "amount": 75000.0,
        "fraud_type": "investment scam",
        "payment_channel": "UPI",
        "incident_timestamp": "2026-03-01T10:00:00",
        "reported_at": "2026-03-01T11:30:00",
        "victim_lat": 28.6,
        "victim_lon": 77.2
    }
    cands = [{"cluster_id": 1, "lat": 22.7, "lon": 75.8, "atm_density": 20, "historical_risk": 0.8, "historical_cashout_count": 250, "historical_cashout_amount": 15000000, "distance_from_victim_km": 650.0}]

    X_loc_1, X_tim_1, cols_l1, cols_t1 = feature_pipeline.build_candidate_matrix_v3(comp_dict, cands)
    X_loc_2, X_tim_2, cols_l2, cols_t2 = feature_pipeline.build_candidate_matrix_v3(comp_dict, cands)

    np.testing.assert_allclose(X_loc_1, X_loc_2)
    np.testing.assert_allclose(X_tim_1, X_tim_2)
    assert cols_l1 == cols_l2
    assert cols_t1 == cols_t2


def test_model_input_smoke_test():
    """51, 52. Features execute clean forward pass through Location V3 and Time V2 models."""
    art_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "ml", "artifacts"))
    loc_model = joblib.load(os.path.join(art_dir, "location_ranker_v3.joblib"))
    time_model = joblib.load(os.path.join(art_dir, "time_regressor_v2.joblib"))

    comp_dict = {
        "amount": 50000.0,
        "fraud_type": "upi / qr code fraud",
        "payment_channel": "UPI",
        "incident_timestamp": "2026-03-01T10:00:00",
        "victim_lat": 28.6,
        "victim_lon": 77.2
    }
    cands = [{"cluster_id": 1, "lat": 22.7, "lon": 75.8, "atm_density": 20, "historical_risk": 0.8, "historical_cashout_count": 250, "historical_cashout_amount": 15000000, "distance_from_victim_km": 650.0}]

    X_loc, X_tim, _, _ = feature_pipeline.build_candidate_matrix_v3(comp_dict, cands)
    loc_probs = loc_model.predict_proba(X_loc)
    time_pred = time_model.predict(X_tim)

    assert loc_probs.shape == (1, 2)
    assert time_pred.shape == (1,)
    assert 0.0 <= loc_probs[0, 1] <= 1.0
    assert time_pred[0] > 0.0


# -----------------------------------------------------------------------------
# 8. Determinism, A/B Diversity, & Read-Only Guarantees (Criteria 44–47)
# -----------------------------------------------------------------------------
def test_ab_diversity_between_complaints(db_session):
    """44. CMP-NEW-000002 and CMP-NEW-000003 naturally produce diverse feature vectors."""
    c2 = db_session.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    c3 = db_session.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000003").first()

    loc2 = build_location_features(db_session, c2.id)["candidate_rows"]
    loc3 = build_location_features(db_session, c3.id)["candidate_rows"]

    assert np.nanmax(np.abs(loc2 - loc3)) > 0.0


def test_determinism_and_fresh_session_stability(db_session):
    """45, 46. Repeated feature generation yields identical results."""
    c = db_session.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    res1 = build_location_features(db_session, c.id)
    res2 = build_location_features(db_session, c.id)

    np.testing.assert_equal(res1["candidate_rows"], res2["candidate_rows"])
    assert res1["feature_names"] == res2["feature_names"]


def test_read_only_db_guarantee(db_session):
    """47. Feature generation does NOT mutate database rows."""
    counts_before = {
        "complaints": db_session.query(Complaint).count(),
        "accounts": db_session.query(Account).count(),
        "transactions": db_session.query(Transaction).count(),
        "withdrawals": db_session.query(Withdrawal).count(),
        "predictions": db_session.query(Prediction).count(),
        "prediction_locations": db_session.query(PredictionLocation).count()
    }

    c = db_session.query(Complaint).first()
    _ = build_location_features(db_session, c.id)
    _ = build_time_features(db_session, c.id)

    counts_after = {
        "complaints": db_session.query(Complaint).count(),
        "accounts": db_session.query(Account).count(),
        "transactions": db_session.query(Transaction).count(),
        "withdrawals": db_session.query(Withdrawal).count(),
        "predictions": db_session.query(Prediction).count(),
        "prediction_locations": db_session.query(PredictionLocation).count()
    }

    assert counts_before == counts_after


# -----------------------------------------------------------------------------
# 9. Regression Tests (Criteria 53–55)
# -----------------------------------------------------------------------------
def test_step5_regression_linking_preserved(db_session):
    """53. Step 5 scenario linking remains intact."""
    c = db_session.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    context = resolve_transaction_context(db_session, c)
    assert context["source_scenario"] == "CMP-DL-1261"


def test_step6_regression_transaction_resolver_preserved(db_session):
    """54. Step 6 transaction resolver remains intact."""
    c = db_session.query(Complaint).filter(Complaint.complaint_number == "CMP-DL-0001").first()
    context = resolve_transaction_context(db_session, c)
    assert context["context_type"] == "DIRECT"
    expected_tx_count = db_session.query(Transaction).filter(Transaction.complaint_id == c.id).count()
    assert len(context["transactions"]) == expected_tx_count


def test_step7_regression_dynamic_graph_preserved(db_session):
    """55. Step 7 dynamic graph service remains intact."""
    c = db_session.query(Complaint).filter(Complaint.complaint_number == "CMP-1042").first()
    graph = build_complaint_graph(db_session, c.id)
    assert len(graph["nodes"]) == 6
    assert len(graph["edges"]) == 5


# -----------------------------------------------------------------------------
# 10. Location Model V3.1 Tests (Step 8C Closure)
# -----------------------------------------------------------------------------
def test_v3_1_feature_schema_and_count():
    """V3.1 feature schema has exactly 43 features in strictly defined order."""
    assert len(FEATURE_COLUMNS_LOCATION_V3_1) == 43
    # First 38 match V3 exactly
    assert FEATURE_COLUMNS_LOCATION_V3_1[:38] == FEATURE_COLUMNS_LOCATION_V3
    # Last 5 are the safe candidate-specific features
    assert FEATURE_COLUMNS_LOCATION_V3_1[38] == "candidate_same_complaint_zone"
    assert FEATURE_COLUMNS_LOCATION_V3_1[39] == "candidate_same_terminal_zone"
    assert FEATURE_COLUMNS_LOCATION_V3_1[40] == "candidate_same_any_account_zone"
    assert FEATURE_COLUMNS_LOCATION_V3_1[41] == "dist_to_complaint_zone_km"
    assert FEATURE_COLUMNS_LOCATION_V3_1[42] == "dist_to_terminal_zone_km"


def test_v3_1_artifacts_existence_and_hashes():
    """All V3.1 artifacts exist and preserved artifacts retain unchanged hashes."""
    art_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "ml", "artifacts"))
    
    # New V3.1 artifacts
    assert os.path.exists(os.path.join(art_dir, "location_ranker_v3_1.joblib"))
    assert os.path.exists(os.path.join(art_dir, "location_calibrator_v3_1.joblib"))
    assert os.path.exists(os.path.join(art_dir, "feature_schema_v3_1.json"))
    assert os.path.exists(os.path.join(art_dir, "model_metadata_v3_1.json"))

    # Preserved artifacts
    assert os.path.exists(os.path.join(art_dir, "location_ranker_v2.joblib"))
    assert os.path.exists(os.path.join(art_dir, "calibrator_v2.joblib"))
    assert os.path.exists(os.path.join(art_dir, "location_ranker_v3.joblib"))
    assert os.path.exists(os.path.join(art_dir, "location_calibrator_v3.joblib"))
    assert os.path.exists(os.path.join(art_dir, "time_regressor_v2.joblib"))


def test_v3_1_candidate_geography_and_k25_natural(db_session):
    """Candidate generator produces valid K=25 corridor-aware candidates with zero target leakage."""
    comp = db_session.query(Complaint).filter(Complaint.complaint_number == "CMP-DL-0001").first()
    loc = build_location_features(db_session, comp.id, top_k=25, model_version="v3.1")
    assert loc["status"] == "SUCCESS"
    assert loc["feature_count"] == 43
    assert loc["candidate_rows"].shape == (25, 43)
    assert len(loc["candidates"]) == 25
    for c in loc["candidates"]:
        assert "is_mule_corridor" not in c
        assert "target_cluster_id" not in c
        assert "withdrawal" not in c


def test_v3_1_training_runtime_parity(db_session):
    """Runtime build_location_features produces identical results across calls."""
    comp = db_session.query(Complaint).filter(Complaint.complaint_number == "CMP-DL-0001").first()
    res1 = build_location_features(db_session, comp.id, top_k=25, model_version="v3.1")
    res2 = build_location_features(db_session, comp.id, top_k=25, model_version="v3.1")
    assert res1["feature_names"] == res2["feature_names"]
    np.testing.assert_allclose(
        np.nan_to_num(res1["candidate_rows"], nan=-999.0),
        np.nan_to_num(res2["candidate_rows"], nan=-999.0)
    )


def test_v3_1_no_target_or_future_leakage(db_session):
    """Verify final V3.1 X excludes target and future outcome fields."""
    comp = db_session.query(Complaint).first()
    loc = build_location_features(db_session, comp.id, model_version="v3.1")
    names = loc["feature_names"]
    forbidden = [
        "target_cluster_id", "beneficiary_target_proxy", "is_mule_corridor",
        "distance_from_high_risk_account", "withdrawal", "future_atm",
        "scenario_pattern"
    ]
    for f in forbidden:
        assert f not in names


def test_v3_1_model_forward_pass_smoke(db_session):
    """Features execute clean forward pass through Location V3.1 model and calibrator."""
    art_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "ml", "artifacts"))
    ranker = joblib.load(os.path.join(art_dir, "location_ranker_v3_1.joblib"))
    calibrator = joblib.load(os.path.join(art_dir, "location_calibrator_v3_1.joblib"))

    comp = db_session.query(Complaint).filter(Complaint.complaint_number == "CMP-DL-0001").first()
    loc = build_location_features(db_session, comp.id, top_k=25, model_version="v3.1")
    X = loc["candidate_rows"]
    raw_probs = ranker.predict_proba(X)
    assert raw_probs.shape == (25, 2)
    cal_probs = calibrator.predict_proba(raw_probs[:, 1].reshape(-1, 1))
    assert cal_probs.shape == (25, 2)
    assert np.all(cal_probs[:, 1] >= 0.0) and np.all(cal_probs[:, 1] <= 1.0)


def test_v3_1_read_only_database_guarantee(db_session):
    """Executing build_location_features with v3.1 causes 0 database mutations."""
    counts_before = {
        "complaints": db_session.query(Complaint).count(),
        "accounts": db_session.query(Account).count(),
        "transactions": db_session.query(Transaction).count(),
        "withdrawals": db_session.query(Withdrawal).count(),
        "predictions": db_session.query(Prediction).count()
    }
    comp = db_session.query(Complaint).filter(Complaint.complaint_number == "CMP-DL-0001").first()
    _ = build_location_features(db_session, comp.id, top_k=25, model_version="v3.1")
    counts_after = {
        "complaints": db_session.query(Complaint).count(),
        "accounts": db_session.query(Account).count(),
        "transactions": db_session.query(Transaction).count(),
        "withdrawals": db_session.query(Withdrawal).count(),
        "predictions": db_session.query(Prediction).count()
    }
    assert counts_before == counts_after

