import pytest
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.auth.security import create_access_token
from backend.app.services.prediction_service import prediction_service

client = TestClient(app)

@pytest.fixture
def auth_headers():
    token = create_access_token({"sub": "admin@cybershield.gov.in", "role": "I4C_ADMIN"})
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def officer_headers():
    token = create_access_token({"sub": "officer@sbi.co.in", "role": "BANK_OFFICER"})
    return {"Authorization": f"Bearer {token}"}


def test_endpoint_authorization_gate():
    """Verify GET /api/v1/model/performance requires valid authentication."""
    # 1. Unauthenticated request must return 401
    unauth_resp = client.get("/api/v1/model/performance")
    assert unauth_resp.status_code == 401

    # 2. Authenticated request must return 200
    token = create_access_token({"sub": "analyst@cybershield.gov.in", "role": "ANALYST"})
    auth_resp = client.get("/api/v1/model/performance", headers={"Authorization": f"Bearer {token}"})
    assert auth_resp.status_code == 200


def test_trained_runtime_with_matching_v8_metadata(auth_headers):
    """
    Verify the active V8 runtime binds only its own held-out synthetic evaluation.
    """
    resp = client.get("/api/v1/model/performance", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    # Part A: Authoritative Runtime
    assert data["prediction_mode"] == "trained_ml"
    assert data["model_version"] == "cashout-location-xgb-v8-debiased"
    assert data["location_model_version"] == "cashout-location-xgb-v8-debiased"
    assert data["time_model_version"] == "cashout-time-xgb-v3"
    assert data["location_features_count"] == 49
    assert "Platt" in data["calibration_method"]

    # Runtime info block
    assert "runtime_info" in data
    r_info = data["runtime_info"]
    assert r_info["runtime_status"] == "TRAINED_READY"
    assert r_info["is_loaded"] is True
    assert r_info["is_available"] is True
    assert r_info["algorithm"] == "pairwise_xgb_ranker"
    assert r_info["location_features_count"] == 49
    assert r_info["location_artifact_hash"] is not None
    assert len(r_info["location_artifact_hash"]) == 64

    # Part B: Bound Evaluation
    assert "evaluation_info" in data
    e_info = data["evaluation_info"]
    assert e_info["evaluation_status"] == "AVAILABLE"
    assert e_info["evaluated_model_version"] == "cashout-location-xgb-v8-debiased"
    assert "synthetic" in e_info["synthetic_disclosure"].lower()

    # Values come from model_metadata_v8_debiased.json, not legacy V7 results.
    assert data["Recall@1"] == "7.62%"
    assert data["Recall@3"] == "23.80%"
    assert data["Recall@5"] == "34.87%"
    assert data["natural_candidate_recall"] is None
    assert data["MRR"] == 0.2141
    assert data["median_cluster_centroid_distance_error_km"] == "7.10 km"
    assert data["internal_ece"] == 0.0001

    # Sample counts truthful: training count present, validation/test NOT inferred
    assert data["training_samples"] is None
    assert data["validation_samples"] is None
    assert data["test_samples"] is None
    assert data["cold_start_test_samples"] is None

    # Part C: Real feature importances extracted from XGBRanker
    assert len(data["feature_importances"]) >= 5
    top_feature = data["feature_importances"][0]
    assert top_feature["importance"] > 0


def test_trained_runtime_with_missing_evaluation_metadata(auth_headers):
    """
    Verify that if evaluation metadata is missing, the runtime status remains
    TRAINED_READY and does NOT fall back to deterministic demo mode.
    Missing metrics must be null with an explicit availability reason.
    """
    mock_prov = MagicMock()
    mock_prov.is_available.return_value = True
    mock_prov.is_loaded = True
    mock_prov.model_version = "cashout-location-xgb-v99-unregistered"
    mock_prov.time_model_version = "cashout-time-xgb-v3"
    mock_prov.load_error = None
    mock_prov.feature_schema = {"location_features": [f"f{i}" for i in range(40)]}
    mock_prov.location_feature_version = "v99"
    mock_prov.location_hash = "11223344556677889900aabbccddeeff" * 2
    mock_prov.calibrator_hash = "aabbccddeeff00112233445566778899" * 2
    mock_prov.location_model = None
    mock_prov.calibrator = None

    with patch("backend.app.services.prediction_service.prediction_service.ml_provider", mock_prov):
        resp = client.get("/api/v1/model/performance", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()

        # Runtime status MUST remain TRAINED_READY (never imply demo!)
        assert data["prediction_mode"] == "trained_ml"
        assert data["runtime_info"]["runtime_status"] == "TRAINED_READY"

        # Evaluation MUST be UNAVAILABLE with explicit availability reason
        assert data["evaluation_info"]["evaluation_status"] == "UNAVAILABLE"
        assert "No registered evaluation metadata" in data["evaluation_info"]["availability_reason"]

        # Missing metrics must be null (never fabricate 65% or 35%!)
        assert data["Recall@1"] is None
        assert data["Recall@3"] is None
        assert data["natural_candidate_recall"] is None
        assert data["MRR"] is None
        assert data["training_samples"] is None
        assert data["validation_samples"] is None


def test_explicit_demo_runtime(auth_headers):
    """
    Verify behavior when explicit demo provider is active.
    Must not report fake training or test metrics.
    """
    with patch("backend.app.services.prediction_service.prediction_service.ml_provider", None):
        resp = client.get("/api/v1/model/performance", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()

        assert data["prediction_mode"] == "deterministic_demo"
        assert data["runtime_info"]["runtime_status"] == "DEMO_ACTIVE"
        assert data["evaluation_info"]["evaluation_status"] == "NOT_EVALUATED"

        # Metrics must be null, not fabricated
        assert data["Recall@1"] is None
        assert data["Recall@3"] is None
        assert data["training_samples"] is None


def test_failed_model_loading_and_error_sanitization(auth_headers):
    """
    Verify behavior when model loading fails.
    Must report LOAD_FAILED, prediction_mode unavailable, and sanitize any filesystem paths.
    """
    mock_prov = MagicMock()
    mock_prov.is_available.return_value = False
    mock_prov.is_loaded = False
    mock_prov.model_version = "cashout-location-xgb-v7-compat"
    mock_prov.time_model_version = "cashout-time-xgb-v3"
    # Provide an error containing internal paths and secrets
    mock_prov.load_error = (
        "Base V4 integrity check failed on C:\\Users\\Administrator\\SecretRepo\\ml\\artifacts\\location_ranker_v4.joblib: "
        "sha256 mismatch /app/secrets/token.key"
    )
    mock_prov.feature_schema = None
    mock_prov.location_hash = None
    mock_prov.calibrator_hash = None
    mock_prov.location_model = None
    mock_prov.calibrator = None

    with patch("backend.app.services.prediction_service.prediction_service.ml_provider", mock_prov):
        resp = client.get("/api/v1/model/performance", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()

        assert data["prediction_mode"] == "unavailable"
        assert data["runtime_info"]["runtime_status"] == "LOAD_FAILED"

        # Check path sanitization: NO Windows drive or Linux absolute path leaked
        load_err = data["runtime_info"]["load_error"]
        assert "C:\\Users" not in load_err
        assert "SecretRepo" not in load_err
        assert "/app/secrets" not in load_err
        assert "<internal_path>" in load_err


def test_metadata_for_wrong_model_version(auth_headers):
    """
    Verify that if the metadata specifies a different model_version than loaded,
    it rejects the metadata with VERSION_MISMATCH and does not bind incorrect numbers.
    """
    mock_prov = MagicMock()
    mock_prov.is_available.return_value = True
    mock_prov.is_loaded = True
    mock_prov.model_version = "cashout-location-xgb-v7-compat"
    mock_prov.time_model_version = "cashout-time-xgb-v3"
    mock_prov.load_error = None
    mock_prov.feature_schema = {"location_features": [f"f{i}" for i in range(47)]}
    mock_prov.location_feature_version = "v7_compat"
    mock_prov.location_hash = "89057bce1000cb82e10f29077b9e168bc0cbd254e979106998e1d623e072c2a6"
    mock_prov.calibrator_hash = "1c14d5aba1b0556a47519ea435804a86b34173c76743a77bcf52cea43d3a2c6d"
    mock_prov.location_model = None
    mock_prov.calibrator = None

    # Return metadata with old V2 model_version
    mismatched_meta = {
        "model_version": "cashout-location-xgb-v2",
        "metrics": {"recall_at_1": "42.4%", "recall_at_3": "50.8%"}
    }

    with patch("backend.app.services.prediction_service.prediction_service.ml_provider", mock_prov):
        with patch("json.load", return_value=mismatched_meta):
            resp = client.get("/api/v1/model/performance", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()

            assert data["runtime_info"]["runtime_status"] == "TRAINED_READY"
            assert data["evaluation_info"]["evaluation_status"] == "VERSION_MISMATCH"
            assert "does not match" in data["evaluation_info"]["availability_reason"]

            # Must NOT bind V2 metrics!
            assert data["Recall@1"] is None
            assert data["Recall@3"] is None


def test_benchmark_comparability_truthfulness(auth_headers):
    """
    Verify that comparisons against baseline explicitly mark deltas as 'Not comparable'
    when objectives and evaluation sets differ, avoiding fabricated +38.4% gains.
    """
    resp = client.get("/api/v1/model/performance", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    matrix = data["metrics_comparison"]
    assert len(matrix) >= 10

    # V8 has no same-cohort distance baseline, so it must not invent a gain.
    dist_item = next((item for item in matrix if "location error" in item["metric"].lower()), None)
    assert dist_item is not None
    assert dist_item["delta"] is None
    assert dist_item["comparable"] is False

    # The random reference is labelled, but a numerical gain is not claimed.
    r1_item = next((item for item in matrix if "Recall@1" in item["metric"]), None)
    assert r1_item is not None
    assert r1_item["comparable"] is True
    assert r1_item["delta"] is None


def test_research_models_governance(auth_headers):
    """
    Verify research models are clearly marked inactive and explain promotion failure truthfully.
    """
    resp = client.get("/api/v1/model/performance", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert "research_models" in data
    assert len(data["research_models"]) >= 1

    shadow_model = data["research_models"][0]
    assert shadow_model["model_name"] == "Blockchain Shadow Re-Ranker V1"
    assert shadow_model["status"] == "RESEARCH_ONLY"
    assert shadow_model["promotion_status"] == "DID NOT MEET PROMOTION GATE"
    assert shadow_model["production_affected"] is False
    assert "+0.07 pp" in shadow_model["observed_gain"]
    assert "+1.00 pp" in shadow_model["required_gain"]


def test_saved_prediction_provenance_card(auth_headers):
    """
    Verify saved prediction provenance clearly distinguishes historical predictions
    from current runtime model.
    """
    resp = client.get("/api/v1/model/performance", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert "saved_prediction_provenance" in data
    prov = data["saved_prediction_provenance"]
    assert prov["current_runtime_model"] == "cashout-location-xgb-v8-debiased"
    assert "Immutable" in prov["historical_policy"]
    assert "demo-provider-v1" in prov["description"]


def test_artifact_hash_mismatch_rejection(auth_headers):
    """
    Verify that if the metadata artifact hash does not match the loaded artifact hash,
    the evaluation is rejected with HASH_MISMATCH and metrics are null.
    """
    mock_prov = MagicMock()
    mock_prov.is_available.return_value = True
    mock_prov.is_loaded = True
    mock_prov.model_version = "cashout-location-xgb-v7-compat"
    mock_prov.time_model_version = "cashout-time-xgb-v3"
    mock_prov.load_error = None
    mock_prov.feature_schema = {"location_features": [f"f{i}" for i in range(47)]}
    mock_prov.location_feature_version = "v7_compat"
    # Provide actual loaded hash
    mock_prov.location_hash = "89057bce1000cb82e10f29077b9e168bc0cbd254e979106998e1d623e072c2a6"
    mock_prov.calibrator_hash = "1c14d5aba1b0556a47519ea435804a86b34173c76743a77bcf52cea43d3a2c6d"
    mock_prov.location_model = None
    mock_prov.calibrator = None

    # Metadata claims a completely different ranker hash
    tampered_meta = {
        "model_version": "cashout-location-xgb-v7-compat",
        "artifacts": {
            "ranker": {
                "file": "location_ranker_v7_compat.joblib",
                "sha256": "9999999999999999999999999999999999999999999999999999999999999999"
            }
        },
        "internal_metrics": {"r1": 99.9, "r3": 99.9}
    }

    with patch("backend.app.services.prediction_service.prediction_service.ml_provider", mock_prov):
        with patch("json.load", return_value=tampered_meta):
            resp = client.get("/api/v1/model/performance", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()

            assert data["runtime_info"]["runtime_status"] == "TRAINED_READY"
            assert data["evaluation_info"]["evaluation_status"] == "HASH_MISMATCH"
            assert "does not match" in data["evaluation_info"]["availability_reason"]
            assert data["Recall@1"] is None


def test_legitimate_zero_metrics_preserved(auth_headers):
    """
    Verify that genuine zero values (e.g. 0.0% error or 0.0000 ECE) are preserved
    and not coerced to null.
    """
    mock_prov = MagicMock()
    mock_prov.is_available.return_value = True
    mock_prov.is_loaded = True
    mock_prov.model_version = "cashout-location-xgb-v7-compat"
    mock_prov.time_model_version = "cashout-time-xgb-v3"
    mock_prov.load_error = None
    mock_prov.feature_schema = {"location_features": [f"f{i}" for i in range(47)]}
    mock_prov.location_feature_version = "v7_compat"
    mock_prov.location_hash = "89057bce1000cb82e10f29077b9e168bc0cbd254e979106998e1d623e072c2a6"
    mock_prov.calibrator_hash = "1c14d5aba1b0556a47519ea435804a86b34173c76743a77bcf52cea43d3a2c6d"
    mock_prov.location_model = None
    mock_prov.calibrator = None

    zero_meta = {
        "model_version": "cashout-location-xgb-v7-compat",
        "internal_metrics": {
            "candidate_recall@25": 0.0,
            "r1": 0.0,
            "r3": 0.0,
            "mrr": 0.0,
            "median_error_km": 0.0
        },
        "internal_ece": 0.0,
        "source_balancing": {"total_train_cases": 1000}
    }

    with patch("backend.app.services.prediction_service.prediction_service.ml_provider", mock_prov):
        with patch("json.load", return_value=zero_meta):
            resp = client.get("/api/v1/model/performance", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()

            assert data["Recall@1"] == "0.0%"
            assert data["natural_candidate_recall"] == "0.0%"
            assert data["MRR"] == 0.0
            assert data["internal_ece"] == 0.0
            assert data["median_cluster_centroid_distance_error_km"] == "0.00 km"


def test_no_percentage_double_conversion(auth_headers):
    """
    Verify V8 metrics already expressed as percentages are not multiplied by 100.
    """
    resp = client.get("/api/v1/model/performance", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    # If double-conversion happened, numbers would be > 1000%
    assert data["Recall@1"] == "7.62%"
    assert data["Recall@3"] == "23.80%"
    assert data["natural_candidate_recall"] is None

