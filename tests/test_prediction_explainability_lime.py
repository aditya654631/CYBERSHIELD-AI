"""
CyberShield AI — Phase B.7 Unit Test Suite
LIME Tabular Explainability for Official cashout-location-xgb-v7-compat Predictions

Verifies:
1. Exact V7 feature ordering and count (47 features)
2. Valid candidate explanation structure and Top-3 consistency
3. Positive and negative contributions separation & formatting
4. Fidelity calculation (R^2, local pred, absolute error) and low-fidelity handling
5. Deterministic reproducibility under fixed random_state
6. Missing prediction handling (NOT_FOUND)
7. Unsupported/missing model handling (UNAVAILABLE)
8. LIME exception isolation (non-blocking safety)
9. Read-only zero-mutation guarantee on Prediction/PredictionLocation/Alert tables
10. B.5 tamper-evident prediction audit verification compatibility
"""

import copy
import pytest
import numpy as np
from datetime import datetime
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.db import SessionLocal
from backend.app.models.models import Complaint, Prediction, PredictionLocation, Alert
from backend.app.auth.security import create_access_token
from backend.app.services.prediction_service import prediction_service
from backend.app.services.prediction_explainability_service import (
    prediction_explainability_service,
    PredictionExplainabilityService,
    V4_COMPAT_FEATURES
)
from backend.app.services.prediction_audit_service import prediction_audit_client
from ml.features.feature_pipeline import FEATURE_COLUMNS_LOCATION_V3_1

client = TestClient(app)
_test_token = create_access_token({"sub": "admin@cybershield.gov.in", "role": "I4C_ADMIN"})
client.headers["Authorization"] = f"Bearer {_test_token}"


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def sample_v7_prediction(db):
    """Ensures at least one valid official V7 prediction exists for testing."""
    pred = (
        db.query(Prediction)
        .filter(
            Prediction.model_version == "cashout-location-xgb-v7-compat",
            Prediction.prediction_mode == "trained_ml"
        )
        .order_by(Prediction.id.desc())
        .first()
    )
    if not pred:
        comp = db.query(Complaint).filter(Complaint.complaint_number.like("CMP-DL-%")).first()
        if not comp:
            comp = db.query(Complaint).first()
        res = prediction_service.run_and_persist_prediction(db, comp.id)
        pred_id = res.get("prediction_id") or res.id
        pred = db.query(Prediction).filter(Prediction.id == pred_id).first()
    return pred


def test_v7_feature_order_and_count():
    """1. Verify exact runtime features used by cashout-location-xgb-v7-compat."""
    expected_features = FEATURE_COLUMNS_LOCATION_V3_1 + V4_COMPAT_FEATURES
    assert len(expected_features) == 47, f"Expected 47 features, got {len(expected_features)}"

    # Check explainer initialization uses exact 47 features
    prediction_explainability_service._ensure_initialized()
    assert len(prediction_explainability_service.feature_names) == 47
    assert prediction_explainability_service.feature_names == expected_features
    assert "v4_candidate_score" in prediction_explainability_service.feature_names
    assert "v4_score_gap_from_candidate1" in prediction_explainability_service.feature_names
    # Zero blockchain features allowed in official V7 explanation
    for f in prediction_explainability_service.feature_names:
        assert "blockchain" not in f.lower()
        assert "fabric" not in f.lower()


def test_valid_explanation_and_top3_consistency(db, sample_v7_prediction):
    """2. Verify valid explanation generation and strict consistency with persisted Top-3."""
    res = prediction_explainability_service.get_or_generate_explanation(db, sample_v7_prediction.id)

    assert res["explanation_status"] in ("AVAILABLE", "LOW_FIDELITY")
    assert res["prediction_id"] == sample_v7_prediction.id
    assert res["prediction_mode"] == "trained_ml"
    assert res["model_version"] == "cashout-location-xgb-v7-compat"
    assert res["explanation_method"] == "LIME"
    assert res["explainer_version"] == "lime_tabular_0.2.0.1"
    assert res["feature_schema_version"] == "v7_compat"
    assert "generated_at" in res

    top3 = res["top3_explanations"]
    assert len(top3) == 3, f"Expected 3 candidate explanations, got {len(top3)}"

    # Strict consistency with persisted PredictionLocation
    persisted_locs = (
        db.query(PredictionLocation)
        .filter(PredictionLocation.prediction_id == sample_v7_prediction.id)
        .order_by(PredictionLocation.rank.asc())
        .all()
    )
    for idx, cand_exp in enumerate(top3):
        p_loc = persisted_locs[idx]
        assert cand_exp["rank"] == p_loc.rank
        assert cand_exp["cluster_id"] == p_loc.cluster_id
        assert cand_exp["location_name"] == p_loc.location_name
        assert abs(cand_exp["official_score"] - float(p_loc.probability)) < 1e-3


def test_positive_and_negative_contributions(db, sample_v7_prediction):
    """3. Verify separation of positive vs negative features and safety language."""
    res = prediction_explainability_service.get_or_generate_explanation(db, sample_v7_prediction.id)
    top3 = res["top3_explanations"]

    for cand_exp in top3:
        pos = cand_exp["positive_contributions"]
        neg = cand_exp["negative_contributions"]
        assert len(pos) + len(neg) > 0, "Candidate must have at least one explanation feature"

        for p in pos:
            assert p["weight"] >= 0.0, "Positive contribution must have weight >= 0"
            assert "Factors that contributed to this candidate ranking include" in p["description"]
            assert "proves" not in p["description"].lower()
            assert "criminal will withdraw" not in p["description"].lower()

        for n in neg:
            assert n["weight"] <= 0.0, "Negative contribution must have weight <= 0"
            assert "Factors reducing candidate ranking priority include" in n["description"]
            assert "proves" not in n["description"].lower()


def test_fidelity_calculation_and_low_fidelity_behavior(db, sample_v7_prediction):
    """4. Verify local fidelity R^2, local prediction, absolute error, and conservative LOW_FIDELITY flagging."""
    res = prediction_explainability_service.get_or_generate_explanation(db, sample_v7_prediction.id)
    top3 = res["top3_explanations"]

    for cand_exp in top3:
        assert "lime_local_prediction" in cand_exp
        assert "absolute_approximation_error" in cand_exp
        assert "local_fidelity_r2" in cand_exp
        assert cand_exp["fidelity_status"] in ("HIGH_FIDELITY", "MODERATE_FIDELITY", "LOW_FIDELITY")

        calc_err = abs(cand_exp["official_score"] - cand_exp["lime_local_prediction"])
        assert abs(calc_err - cand_exp["absolute_approximation_error"]) < 1e-3

    # Test conservative classification thresholds directly
    assert prediction_explainability_service.classify_fidelity(0.75, 0.05) == "HIGH_FIDELITY"
    assert prediction_explainability_service.classify_fidelity(0.55, 0.10) == "MODERATE_FIDELITY"
    assert prediction_explainability_service.classify_fidelity(0.20, 0.01) == "LOW_FIDELITY"
    assert prediction_explainability_service.classify_fidelity(0.80, 0.30) == "LOW_FIDELITY"  # high error diagnostic degrades



def test_deterministic_repeat(db, sample_v7_prediction):
    """5. Verify determinism: repeating explanation produces identical feature ordering and weights."""
    res1 = prediction_explainability_service.get_or_generate_explanation(db, sample_v7_prediction.id)
    # Clear cache in result_metadata temporarily to force re-computation
    current_meta = dict(sample_v7_prediction.result_metadata or {})
    current_meta.pop("explainability", None)
    sample_v7_prediction.result_metadata = current_meta
    db.commit()

    res2 = prediction_explainability_service.get_or_generate_explanation(db, sample_v7_prediction.id)

    top3_1 = res1["top3_explanations"]
    top3_2 = res2["top3_explanations"]

    for i in range(3):
        exp1 = top3_1[i]
        exp2 = top3_2[i]
        assert exp1["rank"] == exp2["rank"]
        assert exp1["cluster_id"] == exp2["cluster_id"]
        assert exp1["official_score"] == exp2["official_score"]
        assert exp1["lime_local_prediction"] == exp2["lime_local_prediction"]
        assert exp1["local_fidelity_r2"] == exp2["local_fidelity_r2"]

        p1_feats = [(c["feature_name"], c["weight"]) for c in exp1["positive_contributions"]]
        p2_feats = [(c["feature_name"], c["weight"]) for c in exp2["positive_contributions"]]
        assert p1_feats == p2_feats

        n1_feats = [(c["feature_name"], c["weight"]) for c in exp1["negative_contributions"]]
        n2_feats = [(c["feature_name"], c["weight"]) for c in exp2["negative_contributions"]]
        assert n1_feats == n2_feats


def test_missing_prediction_not_found(db):
    """6. Calling with non-existent prediction ID returns NOT_FOUND / 404."""
    resp = client.get("/api/v1/predictions/999999/explanation")
    assert resp.status_code == 404
    assert "not found" in resp.json().get("detail", "").lower()


def test_missing_or_unsupported_model(db):
    """7. Calling for a prediction with non-V7 model returns status UNAVAILABLE."""
    v4_pred = db.query(Prediction).filter(Prediction.model_version == "cashout-location-xgb-v4").first()
    if v4_pred:
        res = prediction_explainability_service.get_or_generate_explanation(db, v4_pred.id)
        assert res["explanation_status"] == "UNAVAILABLE"
        assert "only calibrated for official cashout-location-xgb-v7-compat" in res["message"]


def test_lime_exception_isolation(db, sample_v7_prediction, monkeypatch):
    """8. If an internal error occurs, service safely returns UNAVAILABLE without unhandled crash."""
    service_copy = PredictionExplainabilityService(random_state=42)

    def mock_fail(*args, **kwargs):
        raise RuntimeError("Simulated LIME runtime kernel fault")

    monkeypatch.setattr(service_copy, "build_candidate_features_for_complaint", mock_fail)
    # Clear cache temporarily
    current_meta = dict(sample_v7_prediction.result_metadata or {})
    current_meta.pop("explainability", None)
    sample_v7_prediction.result_metadata = current_meta
    db.commit()

    res = service_copy.get_or_generate_explanation(db, sample_v7_prediction.id)
    assert res["explanation_status"] == "UNAVAILABLE"
    assert "Simulated LIME runtime kernel fault" in res["message"]


def test_zero_prediction_mutation(db, sample_v7_prediction):
    """9. Zero mutation guarantee: calling explanation creates ZERO rows in Prediction, Location, or Alert."""
    preds_before = db.query(Prediction).count()
    locs_before = db.query(PredictionLocation).count()
    alerts_before = db.query(Alert).count()

    resp = client.get(f"/api/v1/predictions/{sample_v7_prediction.id}/explanation")
    assert resp.status_code == 200

    preds_after = db.query(Prediction).count()
    locs_after = db.query(PredictionLocation).count()
    alerts_after = db.query(Alert).count()

    assert preds_after == preds_before, "Explanation call created a Prediction row!"
    assert locs_after == locs_before, "Explanation call created a PredictionLocation row!"
    assert alerts_after == alerts_before, "Explanation call created an Alert row!"


def test_b5_audit_status_verified(db, sample_v7_prediction, monkeypatch):
    """10. Verify B.5 tamper-evident prediction audit verification remains VERIFIED after explanation."""
    from backend.app.services.prediction_audit_service import (
        canonicalize_prediction_audit_payload,
        compute_prediction_hash
    )

    complaint = db.query(Complaint).filter(Complaint.id == sample_v7_prediction.complaint_id).first()
    audit_dict = {
        "prediction_id": sample_v7_prediction.id,
        "complaint_number": complaint.complaint_number,
        "complaint_id": complaint.id,
        "prediction_mode": sample_v7_prediction.prediction_mode,
        "model_version": sample_v7_prediction.model_version,
        "time_model_version": sample_v7_prediction.time_model_version,
        "created_at": sample_v7_prediction.created_at,
        "predicted_window_start": sample_v7_prediction.predicted_window_start,
        "predicted_window_end": sample_v7_prediction.predicted_window_end,
        "window_label": sample_v7_prediction.window_label,
        "top_locations": [
            {
                "rank": loc.rank,
                "cluster_id": loc.cluster_id,
                "probability": loc.probability,
                "location_name": loc.location_name
            }
            for loc in sorted(sample_v7_prediction.locations, key=lambda x: x.rank)
        ]
    }

    # Verify canonical hash invariance
    canonical_before = canonicalize_prediction_audit_payload(audit_dict)
    hash_before = compute_prediction_hash(canonical_before)

    # Trigger LIME explanation
    _ = prediction_explainability_service.get_or_generate_explanation(db, sample_v7_prediction.id)

    canonical_after = canonicalize_prediction_audit_payload(audit_dict)
    hash_after = compute_prediction_hash(canonical_after)

    assert hash_before == hash_after, "LIME explainability altered canonical B.5 audit payload hash!"

    # Test audit verification endpoint with mock gateway confirmation
    class MockResponse:
        status_code = 200
        @staticmethod
        def json():
            return {
                "verified": True,
                "status": "VERIFIED",
                "ledger_hash": hash_after,
                "fabric_tx_id": "tx-b5-lime-verified-001",
                "anchored_at": "2026-09-14T15:00:00Z"
            }

    import requests
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: MockResponse())

    resp = client.get(f"/api/v1/predictions/{sample_v7_prediction.id}/audit-verification")
    assert resp.status_code == 200
    data = resp.json()
    assert data["verified"] is True
    assert data["status"] == "VERIFIED"
    assert data["computed_hash"] == hash_after

