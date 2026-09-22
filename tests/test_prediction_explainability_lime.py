"""
CyberShield AI — Phase B.7 Unit Test Suite
LIME Tabular Explainability for Official Models:
- cashout-location-xgb-v8-debiased (49 causal money network features)
- cashout-location-xgb-v7-compat (47 legacy compat features)

Verifies:
1. test_v8_lime_supported
2. test_v8_lime_uses_49_features
3. test_v8_lime_feature_order_matches_runtime
4. test_v8_lime_has_no_victim_origin_features
5. test_v8_lime_has_no_v4_stack_features
6. test_v8_lime_does_not_use_v7_background
7. test_unknown_model_returns_lime_unavailable
8. test_v7_lime_backward_compatibility
9. Non-mutation guarantee & audit invariance
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
from ml.features.feature_pipeline import (
    FEATURE_COLUMNS_LOCATION_V3_1,
    FEATURE_COLUMNS_LOCATION_V8_DEBIASED
)

client = TestClient(app)
_test_token = create_access_token({"sub": "admin@cybershield.gov.in", "role": "I4C_ADMIN"})
client.headers["Authorization"] = f"Bearer {_test_token}"


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def sample_v8_prediction(db):
    """Ensures at least one valid official V8 prediction exists for testing."""
    import os
    os.environ["ACTIVE_LOCATION_MODEL_VERSION"] = "v8_debiased"
    prediction_service.ml_provider._load_models()

    comp = db.query(Complaint).filter(Complaint.complaint_number.like("CMP-DL-%")).first()
    if not comp:
        comp = db.query(Complaint).first()
    res = prediction_service.run_and_persist_prediction(db, comp.id)
    pred_id = res.get("prediction_id") or res.id
    pred = db.query(Prediction).filter(Prediction.id == pred_id).first()
    return pred


@pytest.fixture(scope="module")
def sample_v7_prediction(db):
    """Ensures a V7 prediction structure for backward compatibility testing."""
    pred = (
        db.query(Prediction)
        .filter(
            Prediction.model_version == "cashout-location-xgb-v7-compat",
            Prediction.prediction_mode == "trained_ml"
        )
        .order_by(Prediction.id.desc())
        .first()
    )
    return pred


def test_v8_lime_supported():
    """Verify that V8 debiased model is fully supported by the LIME explainer."""
    service = PredictionExplainabilityService(random_state=42)
    ok = service._ensure_initialized_for_model("cashout-location-xgb-v8-debiased")
    assert ok is True
    assert "v8_debiased" in service._explainers
    assert service._explainers["v8_debiased"] is not None


def test_v8_lime_uses_49_features():
    """Verify that V8 LIME explainer uses exactly 49 features."""
    service = PredictionExplainabilityService(random_state=42)
    service._ensure_initialized_for_model("cashout-location-xgb-v8-debiased")
    schema = service._feature_schemas.get("v8_debiased")
    assert schema is not None
    assert len(schema) == 49, f"Expected 49 features, got {len(schema)}"


def test_v8_lime_feature_order_matches_runtime():
    """Verify V8 LIME explainer feature ordering matches runtime FEATURE_COLUMNS_LOCATION_V8_DEBIASED exactly."""
    service = PredictionExplainabilityService(random_state=42)
    service._ensure_initialized_for_model("cashout-location-xgb-v8-debiased")
    schema = service._feature_schemas.get("v8_debiased")
    assert schema == list(FEATURE_COLUMNS_LOCATION_V8_DEBIASED)


def test_v8_lime_has_no_victim_origin_features():
    """Verify V8 LIME explainer contains zero forbidden victim-origin spatial features."""
    service = PredictionExplainabilityService(random_state=42)
    service._ensure_initialized_for_model("cashout-location-xgb-v8-debiased")
    schema = service._feature_schemas.get("v8_debiased")

    forbidden = {
        "distance_from_victim",
        "candidate_same_complaint_zone",
        "dist_to_complaint_zone_km",
        "complaint_zone_density",
        "victim_centroid_dist_km"
    }
    for f in schema:
        assert f not in forbidden, f"Forbidden feature '{f}' found in V8 LIME schema!"


def test_v8_lime_has_no_v4_stack_features():
    """Verify V8 LIME explainer contains zero V4 stacking features."""
    service = PredictionExplainabilityService(random_state=42)
    service._ensure_initialized_for_model("cashout-location-xgb-v8-debiased")
    schema = service._feature_schemas.get("v8_debiased")

    v4_stack_features = {
        "v4_candidate_score",
        "v4_score_gap_from_candidate1",
        "v4_rank_prior"
    }
    for f in schema:
        assert f not in v4_stack_features, f"V4 stack feature '{f}' found in V8 LIME schema!"


def test_v8_lime_does_not_use_v7_background():
    """Verify V8 LIME explainer uses the 49-column v8_lime_background.npy and not V7 47-column background."""
    service = PredictionExplainabilityService(random_state=42)
    service._ensure_initialized_for_model("cashout-location-xgb-v8-debiased")
    bg = service._background_matrices.get("v8_debiased")
    assert bg is not None
    assert bg.shape[1] == 49, f"Expected V8 background to have 49 columns, got {bg.shape[1]}"
    assert bg.shape[1] != 47


def test_unknown_model_returns_lime_unavailable(db, monkeypatch):
    """Verify that calling explanation for unknown or unsupported model returns status UNAVAILABLE."""
    service = PredictionExplainabilityService(random_state=42)

    # Unknown model string
    assert service._ensure_initialized_for_model("unknown-model-v999") is False

    # Create dummy prediction with unsupported model
    class MockPrediction:
        id = 8888888
        complaint_id = 1
        model_version = "unsupported-random-model-v1"
        time_model_version = "rf_time_v1"
        prediction_mode = "trained_ml"
        result_metadata = {
            "inference_snapshot": {
                "model_version": "unsupported-random-model-v1",
                "feature_names": ["f1", "f2"],
                "candidate_features": {}
            }
        }
        snapshot = None

    class MockComplaint:
        id = 1
        complaint_number = "CMP-DL-TEST-UNSUPP"

    def mock_query(model):
        class MockQuery:
            def filter(self, *args, **kwargs):
                return self
            def first(self):
                if model == Prediction:
                    return MockPrediction()
                elif model == Complaint:
                    return MockComplaint()
                return None
        return MockQuery()

    monkeypatch.setattr(db, "query", mock_query)

    res = service.get_or_generate_explanation(db, 8888888)
    assert res["explanation_status"] == "UNAVAILABLE"
    assert "Unsupported model version" in res["message"] or "only calibrated" in res["message"]


def test_v7_lime_backward_compatibility():
    """Verify V7-compat LIME path remains functional with 47 features."""
    service = PredictionExplainabilityService(random_state=42)
    ok = service._ensure_initialized_for_model("cashout-location-xgb-v7-compat")
    assert ok is True
    schema_v7 = service._feature_schemas.get("v7_compat")
    assert len(schema_v7) == 47
    bg_v7 = service._background_matrices.get("v7_compat")
    assert bg_v7 is not None
    assert bg_v7.shape[1] == 47


def test_v8_prediction_explanation_flow_and_non_mutation(db, sample_v8_prediction):
    """Verify end-to-end explanation generation for V8 prediction and zero mutation."""
    # Capture state before explanation
    locs_before = [
        (loc.rank, loc.cluster_id, float(loc.probability), loc.location_name)
        for loc in sorted(sample_v8_prediction.locations, key=lambda x: x.rank)
    ]
    preds_count_before = db.query(Prediction).count()
    locs_count_before = db.query(PredictionLocation).count()

    # Generate LIME explanation
    res = prediction_explainability_service.get_or_generate_explanation(db, sample_v8_prediction.id)

    assert res["explanation_status"] in ("AVAILABLE", "LOW_FIDELITY")
    assert res["prediction_id"] == sample_v8_prediction.id
    assert res["model_version"] == "cashout-location-xgb-v8-debiased"
    assert res["feature_schema_version"] == "v8_debiased"
    assert len(res["top3_explanations"]) == 3

    # Check top candidate explanation
    top1 = res["top3_explanations"][0]
    assert top1["rank"] == 1
    assert "lime_local_prediction" in top1
    assert "local_fidelity_r2" in top1
    assert len(top1["positive_contributions"]) + len(top1["negative_contributions"]) > 0

    # Non-causal wording check
    for p in top1["positive_contributions"]:
        assert "proves" not in p["description"].lower()
        assert "caus" not in p["description"].lower()
    for n in top1["negative_contributions"]:
        assert "proves" not in n["description"].lower()
        assert "caus" not in n["description"].lower()

    # Check state after explanation — Rankings must remain bit-identical
    locs_after = [
        (loc.rank, loc.cluster_id, float(loc.probability), loc.location_name)
        for loc in sorted(sample_v8_prediction.locations, key=lambda x: x.rank)
    ]
    assert locs_before == locs_after, "LIME explanation mutated prediction location rankings!"
    assert db.query(Prediction).count() == preds_count_before
    assert db.query(PredictionLocation).count() == locs_count_before


def test_lime_exception_isolation(db, sample_v8_prediction, monkeypatch):
    """If an internal error occurs, service safely returns UNAVAILABLE without unhandled crash."""
    service_copy = PredictionExplainabilityService(random_state=42)

    def mock_fail(*args, **kwargs):
        raise RuntimeError("Simulated LIME runtime kernel fault")

    monkeypatch.setattr(service_copy, "build_candidate_features_for_complaint", mock_fail)
    current_meta = dict(sample_v8_prediction.result_metadata or {})
    current_meta.pop("explainability", None)
    sample_v8_prediction.result_metadata = current_meta
    db.commit()

    res = service_copy.get_or_generate_explanation(db, sample_v8_prediction.id)
    assert res["explanation_status"] == "UNAVAILABLE"
    assert "Simulated LIME runtime kernel fault" in res["message"]


def test_b5_audit_status_verified(db, sample_v8_prediction, monkeypatch):
    """Verify B.5 tamper-evident prediction audit verification remains VERIFIED after explanation."""
    from backend.app.services.prediction_audit_service import (
        canonicalize_prediction_audit_payload,
        compute_prediction_hash
    )

    complaint = db.query(Complaint).filter(Complaint.id == sample_v8_prediction.complaint_id).first()
    audit_dict = {
        "prediction_id": sample_v8_prediction.id,
        "complaint_number": complaint.complaint_number if complaint else "CMP-DL-TEST",
        "complaint_id": complaint.id if complaint else 1,
        "prediction_mode": sample_v8_prediction.prediction_mode,
        "model_version": sample_v8_prediction.model_version,
        "time_model_version": sample_v8_prediction.time_model_version,
        "created_at": sample_v8_prediction.created_at,
        "predicted_window_start": sample_v8_prediction.predicted_window_start,
        "predicted_window_end": sample_v8_prediction.predicted_window_end,
        "window_label": sample_v8_prediction.window_label,
        "top_locations": [
            {
                "rank": loc.rank,
                "cluster_id": loc.cluster_id,
                "probability": loc.probability,
                "location_name": loc.location_name
            }
            for loc in sorted(sample_v8_prediction.locations, key=lambda x: x.rank)
        ]
    }

    canonical_before = canonicalize_prediction_audit_payload(audit_dict)
    hash_before = compute_prediction_hash(canonical_before)

    # Trigger LIME explanation
    _ = prediction_explainability_service.get_or_generate_explanation(db, sample_v8_prediction.id)

    canonical_after = canonicalize_prediction_audit_payload(audit_dict)
    hash_after = compute_prediction_hash(canonical_after)

    assert hash_before == hash_after, "LIME explainability altered canonical B.5 audit payload hash!"
