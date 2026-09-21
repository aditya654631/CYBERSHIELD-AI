"""
Unit and Regression Tests for Model V8 Debiasing and Candidate Generator Invariance
Master Corrective Pass V3
"""

import math
import pytest
import numpy as np
import joblib
import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from ml.features.feature_pipeline import (
    feature_pipeline,
    FEATURE_COLUMNS_LOCATION_V8_DEBIASED,
    FEATURE_COLUMNS_LOCATION_V3_1
)
from ml.geo.candidate_generator import CandidateLocationGenerator


def test_v8_feature_schema_count_and_exclusions():
    """Verify V8 Debiased schema has 49 features (40 base + 9 within-zone discriminators)
    and excludes all victim-origin shortcuts.
    Updated in Quality Recovery v2: 9 new within-zone discriminative features added.
    """
    assert len(FEATURE_COLUMNS_LOCATION_V8_DEBIASED) == 49, (
        f"Expected 49 V8 features (40 base + 9 within-zone), got {len(FEATURE_COLUMNS_LOCATION_V8_DEBIASED)}"
    )
    assert "distance_from_victim" not in FEATURE_COLUMNS_LOCATION_V8_DEBIASED
    assert "candidate_same_complaint_zone" not in FEATURE_COLUMNS_LOCATION_V8_DEBIASED
    assert "dist_to_complaint_zone_km" not in FEATURE_COLUMNS_LOCATION_V8_DEBIASED
    # Retained features (within-zone discriminators)
    assert "candidate_same_terminal_zone" in FEATURE_COLUMNS_LOCATION_V8_DEBIASED
    assert "dist_to_terminal_zone_km" in FEATURE_COLUMNS_LOCATION_V8_DEBIASED
    # New within-zone features
    assert "dist_to_terminal_centroid_km" in FEATURE_COLUMNS_LOCATION_V8_DEBIASED
    assert "log_cluster_network_exposure" in FEATURE_COLUMNS_LOCATION_V8_DEBIASED
    assert "cluster_fraud_type_match_score" in FEATURE_COLUMNS_LOCATION_V8_DEBIASED
    assert "atm_density_log" in FEATURE_COLUMNS_LOCATION_V8_DEBIASED
    assert "cluster_risk_x_count" in FEATURE_COLUMNS_LOCATION_V8_DEBIASED


def test_candidate_generator_victim_invariance():
    """Verify CandidateLocationGenerator candidate scoring is invariant to victim location."""
    clusters = [
        {"id": 1, "name": "Dwarka Sector 10", "zone": "SOUTH_WEST_DWARKA", "lat": 28.5758, "lon": 77.0731, "risk": 0.6, "atm_density": 10},
        {"id": 2, "name": "Rohini Sector 7", "zone": "NORTH_WEST", "lat": 28.7255, "lon": 77.1355, "risk": 0.6, "atm_density": 10},
        {"id": 3, "name": "Laxmi Nagar", "zone": "EAST", "lat": 28.6252, "lon": 77.2953, "risk": 0.6, "atm_density": 10}
    ]
    gen = CandidateLocationGenerator(clusters=clusters)

    comp_dwarka = {"victim_district": "SOUTH_WEST_DWARKA", "victim_lat": 28.5758, "victim_lon": 77.0731, "fraud_type": "investment"}
    comp_rohini = {"victim_district": "NORTH_WEST", "victim_lat": 28.7255, "victim_lon": 77.1355, "fraud_type": "investment"}

    # Fixed terminal mule in East Delhi
    cands_dwarka = gen.generate_candidates_for_complaint(comp_dwarka, terminal_zone="EAST", all_tx_zones={"EAST"}, top_k=None)
    cands_rohini = gen.generate_candidates_for_complaint(comp_rohini, terminal_zone="EAST", all_tx_zones={"EAST"}, top_k=None)

    # Top-1 candidate must be Laxmi Nagar (EAST) in both scenarios with exact same score
    assert cands_dwarka[0]["name"] == "Laxmi Nagar"
    assert cands_rohini[0]["name"] == "Laxmi Nagar"
    assert cands_dwarka[0]["candidate_generation_score"] == cands_rohini[0]["candidate_generation_score"]


def test_v8_model_artifacts_and_counterfactual_invariance():
    """Test trained V8 model ranker and calibrator against counterfactual victim origin shifts."""
    ranker_path = os.path.join(BASE_DIR, "ml", "artifacts", "location_ranker_v8_debiased.joblib")
    calibrator_path = os.path.join(BASE_DIR, "ml", "artifacts", "location_calibrator_v8_debiased.joblib")

    if not os.path.exists(ranker_path) or not os.path.exists(calibrator_path):
        pytest.skip("V8 model artifacts not yet trained")

    ranker = joblib.load(ranker_path)
    calibrator = joblib.load(calibrator_path)

    clusters = [
        {"id": 1, "name": "Dwarka Sector 10", "zone": "SOUTH_WEST_DWARKA", "lat": 28.5758, "lon": 77.0731, "risk": 0.5, "atm_density": 12, "historical_cashout_count": 200, "historical_cashout_amount": 10000000.0},
        {"id": 2, "name": "Rohini Sector 7", "zone": "NORTH_WEST", "lat": 28.7255, "lon": 77.1355, "risk": 0.5, "atm_density": 12, "historical_cashout_count": 200, "historical_cashout_amount": 10000000.0},
        {"id": 3, "name": "Laxmi Nagar", "zone": "EAST", "lat": 28.6252, "lon": 77.2953, "risk": 0.5, "atm_density": 12, "historical_cashout_count": 200, "historical_cashout_amount": 10000000.0}
    ]

    txs = [
        {
            "transaction_ref": "TX-T1",
            "sender_account_id": "ACC-1",
            "receiver_account_id": "ACC-2",
            "amount": 50000.0,
            "payment_channel": "UPI",
            "timestamp": "2026-03-01T10:00:00",
            "hop_number": 1,
            "receiver_district": "EAST"
        }
    ]

    comp_a = {"complaint_number": "CMP-A", "victim_district": "SOUTH_WEST_DWARKA", "victim_lat": 28.5758, "victim_lon": 77.0731, "amount": 50000.0, "fraud_type": "investment"}
    comp_b = {"complaint_number": "CMP-B", "victim_district": "NORTH_WEST", "victim_lat": 28.7255, "victim_lon": 77.1355, "amount": 50000.0, "fraud_type": "investment"}

    X_a, _, _, _ = feature_pipeline.build_candidate_matrix_v8_debiased(comp_a, candidates=clusters, transactions=txs, terminal_zone="EAST", all_tx_zones={"EAST"})
    X_b, _, _, _ = feature_pipeline.build_candidate_matrix_v8_debiased(comp_b, candidates=clusters, transactions=txs, terminal_zone="EAST", all_tx_zones={"EAST"})

    scores_a = ranker.predict(X_a)
    scores_b = ranker.predict(X_b)

    probs_a = calibrator.predict_proba(scores_a.reshape(-1, 1))[:, 1]
    probs_b = calibrator.predict_proba(scores_b.reshape(-1, 1))[:, 1]

    # Scores and probabilities must be identical because non-causal victim location is excluded
    np.testing.assert_allclose(probs_a, probs_b, atol=1e-5)
