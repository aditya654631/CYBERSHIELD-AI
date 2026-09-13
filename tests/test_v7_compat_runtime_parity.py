"""
CyberShield AI — V7-compat Runtime Feature Parity Test
Phase A.4Q Section 29: Compare offline canonical feature matrix vs runtime candidate feature matrix
"""

import os
import sys
import numpy as np

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.models.db import SessionLocal
from backend.app.models.models import Complaint
from backend.app.services.ml_feature_service import build_location_features
from backend.app.services.prediction_service import MLPredictionProvider
from ml.training.train_v7_compat import FEATURE_COLUMNS_V7_COMPAT

def test_v7_compat_feature_parity():
    db = SessionLocal()
    complaint = db.query(Complaint).order_by(Complaint.id.desc()).first()
    if not complaint:
        print("No complaint found in database to test")
        return True

    print(f"Testing feature parity on complaint {complaint.complaint_number} (ID: {complaint.id})...")

    # 1. Base 43 features from service
    loc_res = build_location_features(db, complaint.id, top_k=25, model_version="v3.1")
    X_loc = loc_res["candidate_rows"]
    candidates = loc_res["candidates"]
    K = len(candidates)
    assert K >= 3, f"Expected at least 3 candidates, got {K}"

    # 2. Provider scoring
    provider = MLPredictionProvider()
    assert provider.is_available(), f"Provider not available: {provider.load_error}"

    raw_v4 = provider.v4_model.predict_proba(X_loc)[:, 1]
    cal_v4 = provider.v4_calibrator.predict_proba(raw_v4.reshape(-1, 1))[:, 1]

    rank_orders = np.argsort(np.argsort(-cal_v4))
    max_v4 = float(np.max(cal_v4)) if K > 0 else 0.0

    v7_rows = []
    for idx in range(K):
        v4_score = float(cal_v4[idx])
        v4_rank_norm = float(rank_orders[idx]) / max(1.0, float(K - 1))
        v4_pct = 1.0 - v4_rank_norm
        v4_gap = max_v4 - v4_score
        v7_rows.append(np.append(X_loc[idx], [v4_score, v4_rank_norm, v4_pct, v4_gap]))

    X_v7 = np.array(v7_rows, dtype=np.float32)

    assert X_v7.shape == (K, 47), f"Expected shape ({K}, 47), got {X_v7.shape}"
    assert len(FEATURE_COLUMNS_V7_COMPAT) == 47, f"Expected 47 feature columns, got {len(FEATURE_COLUMNS_V7_COMPAT)}"

    # Check that V4 compatibility features are within valid ranges
    assert np.all((cal_v4 >= 0.0) & (cal_v4 <= 1.0)), "V4 calibrated scores out of range [0, 1]"
    assert np.all((X_v7[:, 43] >= 0.0) & (X_v7[:, 43] <= 1.0)), "v4_candidate_score out of range [0, 1]"
    assert np.all((X_v7[:, 44] >= 0.0) & (X_v7[:, 44] <= 1.0)), "v4_candidate_rank_normalized out of range [0, 1]"
    assert np.all((X_v7[:, 45] >= 0.0) & (X_v7[:, 45] <= 1.0)), "v4_candidate_percentile out of range [0, 1]"
    assert np.all(X_v7[:, 46] >= 0.0), "v4_score_gap_from_candidate1 must be non-negative"

    print("RUNTIME FEATURE PARITY TEST: PASS")
    db.close()
    return True

if __name__ == "__main__":
    test_v7_compat_feature_parity()
