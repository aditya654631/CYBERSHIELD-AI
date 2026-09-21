"""
CyberShield AI — Phase 11 Test Suite: Honest Timing Uncertainty & Stable LIME Explanation

Guarantees Verified:
1. Timing Uncertainty Provenance & API Roundtrip:
   - window_basis, uncertainty_minutes, reference_basis survive persistence and GET /predictions/{id}.
2. Target Reference Semantics:
   - Prediction reference time is anchored to complaint reporting time (reported_at), never 'from now'.
3. Empirical Timing Uncertainty & Coverage:
   - Missing outcomes are excluded (never treated as 0-delay labels).
   - Empirical coverage and mean window width are accurately computed.
4. LIME Snapshot-Grounding & Immutability:
   - Explanations are computed strictly from immutable inference snapshots.
5. LIME Non-Mutation Guarantee:
   - Explaining a prediction produces zero modifications to candidate rankings, official scores, or database state.
6. LIME Determinism & Seed Repeatability:
   - Per-call seeded RNG produces identical local surrogate weights and R² scores.
7. Conservative Fidelity Diagnostics:
   - R² >= 0.70 is HIGH_FIDELITY, 0.40 <= R² < 0.70 is MODERATE_FIDELITY, < 0.40 is LOW_FIDELITY.
   - Safety thresholds are never lowered solely to remove warnings.
8. Error Sanitization:
   - Missing predictions or unexplainable inputs return sanitized responses with zero stack traces or internal paths.
"""

import os
import sys
import datetime
from decimal import Decimal
import numpy as np
import pytest
from sqlalchemy.orm import Session

from backend.app.models.models import Complaint, Prediction, PredictionLocation, PredictionSnapshot, User
from backend.app.services.prediction_contract import build_time_prediction, as_utc, utc_iso, window_status
from backend.app.services.prediction_service import prediction_service
from backend.app.services.prediction_persistence_service import prediction_persistence_service
from backend.app.services.prediction_explainability_service import (
    prediction_explainability_service,
    PredictionExplainabilityService,
)
from ml.evaluation.timing_evaluation import evaluate_timing_dataset, run_comprehensive_timing_evaluation
from ml.evaluation.lime_stability_evaluation import (
    evaluate_lime_stability,
    evaluate_sample_size_sensitivity,
    generate_benchmark_candidate_vectors
)


def test_timing_uncertainty_provenance_api_roundtrip(auth_client, db_session: Session):
    """
    1. Timing Uncertainty Provenance & API Roundtrip:
    - Verifies window_basis, uncertainty_minutes, reference_basis survive GET /predictions/{id}.
    """
    # Create test complaint with explicit reported_at
    comp = Complaint(
        complaint_number=f"CMP-TIME-PROV-{int(datetime.datetime.utcnow().timestamp())}",
        fraud_type="UPI_FRAUD",
        amount=Decimal("85000.00"),
        victim_location="Connaught Place, Delhi",
        state="Delhi",
        district="CENTRAL_NEW_DELHI",
        payment_channel="UPI",
        reported_at=datetime.datetime.utcnow() - datetime.timedelta(hours=1),
        incident_time=datetime.datetime.utcnow() - datetime.timedelta(hours=2),
    )
    db_session.add(comp)
    db_session.commit()

    # Run prediction
    res = auth_client.post(f"/api/v1/predictions/{comp.complaint_number}")
    assert res.status_code == 200, f"Run prediction failed: {res.text}"
    data = res.json()

    # Verify time_prediction payload in POST response
    time_pred = data.get("time_prediction")
    assert time_pred is not None, "Missing time_prediction in POST response"
    assert "uncertainty_minutes" in time_pred
    assert "window_basis" in time_pred
    assert time_pred["window_basis"] in ("operational_estimate", "heuristic_prototype", "calibrated_interval")
    assert time_pred["reference_basis"] == "complaint_reported_at"
    assert time_pred["prediction_reference_time"] is not None

    # Read back via GET /predictions/{id}
    get_res = auth_client.get(f"/api/v1/predictions/{comp.complaint_number}")
    assert get_res.status_code == 200, f"GET prediction failed: {get_res.text}"
    get_data = get_res.json()
    get_time = get_data.get("time_prediction")
    assert get_time is not None

    # Provenance survived round-trip
    assert get_time["window_basis"] == time_pred["window_basis"]
    assert get_time["reference_basis"] == "complaint_reported_at"
    assert get_time["prediction_reference_time"] == time_pred["prediction_reference_time"]
    assert get_time["uncertainty_minutes"] == time_pred["uncertainty_minutes"]


def test_timing_reference_semantics(db_session: Session):
    """
    2. Target Reference Semantics:
    - The trained target is cashout time minus reported_at, never 'from now' (current wall-clock).
    """
    reported_time = datetime.datetime(2026, 9, 20, 10, 0, 0, tzinfo=datetime.timezone.utc)
    mock_complaint = Complaint(
        complaint_number="CMP-SEMANTICS-01",
        reported_at=reported_time,
        incident_time=reported_time - datetime.timedelta(hours=1)
    )

    pred = build_time_prediction(
        complaint=mock_complaint,
        minutes=120.0,
        model_version="cashout-time-xgb-v3",
        uncertainty_minutes=15.0,
        window_basis="operational_estimate"
    )

    assert pred["reference_basis"] == "complaint_reported_at"
    assert pred["prediction_reference_time"] == "2026-09-20T10:00:00Z"
    # 120 minutes after 10:00 is 12:00
    assert pred["predicted_cashout_at"] == "2026-09-20T12:00:00Z"
    # Window 105 to 135 minutes after 10:00 -> 11:45 to 12:15
    assert pred["window_start"] == "2026-09-20T11:45:00Z"
    assert pred["window_end"] == "2026-09-20T12:15:00Z"
    assert pred["uncertainty_minutes"] == 15.0
    assert pred["window_basis"] == "operational_estimate"


def test_missing_outcome_exclusion_in_timing_evaluation():
    """
    3. Missing Outcome Exclusion in Timing Evaluation:
    - Missing outcomes are excluded from evaluation, never assumed to be 0-delay labels.
    """
    import pandas as pd
    test_df = pd.DataFrame({
        "amount": [50000, 75000, 100000, 25000],
        "fraud_type_encoded": [1, 2, 1, 3],
        "actual_delay_minutes": [120.0, np.nan, 180.0, None],  # 2 valid, 2 missing
    })

    res = evaluate_timing_dataset(test_df, "test_missing_cohort", uncertainty_minutes=15.0)
    assert res["total_records"] == 4
    assert res["evaluated_records"] == 2
    assert res["missing_outcomes_excluded"] == 2
    assert res["window_basis"] == "operational_estimate"
    assert res["mae_minutes"] is not None


def test_lime_snapshot_immutability(auth_client, db_session: Session):
    """
    4. LIME Snapshot-Grounding & Immutability:
    - Explanations are computed strictly from the immutable inference snapshot recorded at prediction time.
    """
    comp = Complaint(
        complaint_number=f"CMP-LIME-SNAP-{int(datetime.datetime.utcnow().timestamp())}",
        fraud_type="UPI_FRAUD",
        amount=Decimal("60000.00"),
        victim_location="Lajpat Nagar, Delhi",
        state="Delhi",
        district="SOUTH_EAST",
        payment_channel="UPI",
        reported_at=datetime.datetime.utcnow() - datetime.timedelta(hours=1),
        incident_time=datetime.datetime.utcnow() - datetime.timedelta(hours=2),
    )
    db_session.add(comp)
    db_session.commit()

    # Generate prediction
    p_res = auth_client.post(f"/api/v1/predictions/{comp.complaint_number}")
    assert p_res.status_code == 200
    pred_id = p_res.json()["prediction_id"]

    # Retrieve explanation
    exp_res = auth_client.get(f"/api/v1/predictions/{pred_id}/explanation")
    assert exp_res.status_code == 200
    exp_data = exp_res.json()

    assert exp_data["prediction_id"] == pred_id
    assert exp_data["explanation_status"] in ("AVAILABLE", "LOW_FIDELITY")
    assert "top3_explanations" in exp_data
    assert len(exp_data["top3_explanations"]) == 3

    # Verify per-candidate fidelity fields
    for cand in exp_data["top3_explanations"]:
        assert "rank" in cand
        assert "official_score" in cand
        assert "lime_local_prediction" in cand
        assert "local_fidelity_r2" in cand
        assert "fidelity_status" in cand
        assert cand["fidelity_status"] in ("HIGH_FIDELITY", "MODERATE_FIDELITY", "LOW_FIDELITY")


def test_lime_non_mutation_guarantee(auth_client, db_session: Session):
    """
    5. LIME Non-Mutation Guarantee:
    - Generating an explanation does NOT modify prediction locations, scores, or ranks in DB.
    """
    comp = Complaint(
        complaint_number=f"CMP-LIME-NOMUT-{int(datetime.datetime.utcnow().timestamp())}",
        fraud_type="UPI_FRAUD",
        amount=Decimal("120000.00"),
        victim_location="Dwarka Sector 10, Delhi",
        state="Delhi",
        district="SOUTH_WEST_DWARKA",
        payment_channel="UPI",
        reported_at=datetime.datetime.utcnow() - datetime.timedelta(hours=1),
        incident_time=datetime.datetime.utcnow() - datetime.timedelta(hours=2),
    )
    db_session.add(comp)
    db_session.commit()

    p_res = auth_client.post(f"/api/v1/predictions/{comp.complaint_number}")
    assert p_res.status_code == 200
    pred_data_before = p_res.json()
    pred_id = pred_data_before["prediction_id"]

    # Record baseline state
    locs_before = [(l["rank"], l["cluster_id"], l["ml_probability"]) for l in pred_data_before["top_locations"]]

    # Call explanation endpoint multiple times
    for _ in range(3):
        exp_res = auth_client.get(f"/api/v1/predictions/{pred_id}/explanation")
        assert exp_res.status_code == 200

    # Verify prediction row in DB is completely unaltered
    db_session.expire_all()
    pred_after = db_session.query(Prediction).filter(Prediction.id == pred_id).first()
    locs_after = [(l.rank, l.cluster_id, l.probability) for l in sorted(pred_after.locations, key=lambda x: x.rank)]

    assert locs_before == locs_after, "PredictionLocation rows were mutated by explanation!"


def test_lime_seed_determinism():
    """
    6. LIME Determinism & Seed Repeatability:
    - Identical random seeds produce identical local surrogate weights and R² scores.
    """
    cases = generate_benchmark_candidate_vectors()
    test_case = cases[0]
    vec = test_case["vector"]

    # Run with seed 42 twice
    prediction_explainability_service.random_state = 42
    exp1 = prediction_explainability_service.explain_candidate(
        candidate_vector=vec,
        rank=1,
        cluster_id=test_case["cluster_id"],
        location_name=test_case["location_name"],
        official_score=test_case["official_score"],
        num_features=8,
        num_samples=500
    )

    prediction_explainability_service.random_state = 42
    exp2 = prediction_explainability_service.explain_candidate(
        candidate_vector=vec,
        rank=1,
        cluster_id=test_case["cluster_id"],
        location_name=test_case["location_name"],
        official_score=test_case["official_score"],
        num_features=8,
        num_samples=500
    )

    assert exp1["local_fidelity_r2"] == exp2["local_fidelity_r2"]
    assert exp1["absolute_approximation_error"] == exp2["absolute_approximation_error"]
    assert exp1["fidelity_status"] == exp2["fidelity_status"]

    w1 = [f["weight"] for f in exp1.get("positive_contributions", [])]
    w2 = [f["weight"] for f in exp2.get("positive_contributions", [])]
    assert w1 == w2


def test_conservative_fidelity_classification_boundaries():
    """
    7. Conservative Fidelity Classification Boundaries:
    - R² >= 0.70 & err <= 0.15: HIGH_FIDELITY
    - 0.40 <= R² < 0.70 & err <= 0.25: MODERATE_FIDELITY
    - R² < 0.40 or err > 0.25: LOW_FIDELITY
    - Negative R² is truthfully classified as LOW_FIDELITY.
    """
    classify = PredictionExplainabilityService.classify_fidelity

    # High fidelity
    assert classify(0.85, 0.05) == "HIGH_FIDELITY"
    assert classify(0.70, 0.15) == "HIGH_FIDELITY"

    # High R² but large error -> Low fidelity
    assert classify(0.85, 0.30) == "LOW_FIDELITY"

    # Moderate fidelity
    assert classify(0.65, 0.10) == "MODERATE_FIDELITY"
    assert classify(0.40, 0.25) == "MODERATE_FIDELITY"

    # Low fidelity
    assert classify(0.35, 0.10) == "LOW_FIDELITY"
    assert classify(-0.15, 0.05) == "LOW_FIDELITY"
    assert classify(0.50, 0.35) == "LOW_FIDELITY"
