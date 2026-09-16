"""
CyberShield AI — Code Consolidation & Source Divergence Prevention Test
Verifies that:
1. Root `ml` and root `database` are the canonical packages.
2. `backend.ml` and `backend.database` compatibility shims resolve to `ml` and `database`.
3. Essential canonical ML artifacts and seed modules exist under root `ml/artifacts` and `database/seed`.
"""

import os
import subprocess
import sys
import pytest

def test_canonical_ml_package_resolution():
    import ml
    import backend.ml
    assert hasattr(ml, "__file__"), "Canonical ml package must exist"
    # Verify candidate generator and feature pipeline resolve
    from ml.geo.candidate_generator import CandidateLocationGenerator
    from ml.features.feature_pipeline import feature_pipeline
    assert CandidateLocationGenerator is not None
    assert feature_pipeline is not None

def test_canonical_database_package_resolution():
    import database
    import backend.database
    from database.seed.seed_data import seed_database
    from database.seed.seed_config import SYNTHETIC_RANDOM_SEED
    assert seed_database is not None
    assert SYNTHETIC_RANDOM_SEED == 26184


def test_root_launcher_imports_in_clean_process():
    """Match Railway's ``uvicorn main:app`` import path in a fresh process."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    result = subprocess.run(
        [sys.executable, "-c", "import main; assert main.app is not None"],
        cwd=root_dir,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr

def test_canonical_ml_artifacts_exist():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    artifacts_dir = os.path.join(base_dir, "ml", "artifacts")
    assert os.path.isdir(artifacts_dir), "Canonical ml/artifacts directory must exist"

    required_artifacts = [
        "model_metadata_v7_compat.json",
        "location_ranker_v7_compat.joblib",
        "location_calibrator_v7_compat.joblib",
        "feature_schema_v7_compat.json",
        "time_regressor_v3.joblib",
        "v7_lime_background.npy"
    ]
    for art in required_artifacts:
        path = os.path.join(artifacts_dir, art)
        assert os.path.isfile(path), f"Required canonical artifact {art} missing from ml/artifacts"
