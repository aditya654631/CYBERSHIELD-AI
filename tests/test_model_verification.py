import os
import pytest
from backend.app.services.model_verification_service import ModelVerificationService, _compute_file_sha256


def test_model_verification_official_artifacts():
    service = ModelVerificationService()
    report = service.verify_model_artifacts("model_metadata_v7_compat.json")

    # Invariants
    assert "status" in report
    assert report["status"] in ("COMPATIBLE", "VERSION_MISMATCH")
    assert report["is_ready"] is True
    assert report["artifacts_verified"] is True
    assert "runtime_versions" in report

    # Check required ML libraries are detected
    runtime = report["runtime_versions"]
    assert "scikit_learn" in runtime
    assert "xgboost" in runtime
    assert "numpy" in runtime
    assert "pandas" in runtime

    # Check declared artifacts were examined
    details = report["artifact_details"]
    assert "ranker" in details
    assert details["ranker"]["status"] == "VERIFIED"


def test_model_verification_active_v8_artifacts():
    """The deployed V8 metadata must verify after checkout on every CI OS."""
    report = ModelVerificationService().verify_model_artifacts(
        "model_metadata_v8_debiased.json"
    )
    assert report["is_ready"] is True
    assert report["artifacts_verified"] is True
    assert report["artifact_details"]["feature_schema"]["status"] == "VERIFIED"


def test_model_verification_missing_metadata(tmp_path):
    # Empty directory without metadata file
    service = ModelVerificationService(artifacts_dir=str(tmp_path))
    report = service.verify_model_artifacts("nonexistent_meta.json")

    assert report["status"] == "MISSING_METADATA"
    assert report["is_ready"] is False
    assert report["artifacts_verified"] is False


def test_compute_sha256_missing_file():
    assert _compute_file_sha256("/path/to/nonexistent/file.bin") is None
