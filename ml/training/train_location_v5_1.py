"""
CyberShield AI — Delhi V5.1 Location Challenger Training Pipeline
Phase A.4C: Trains cashout-location-xgb-v5.1 & location_calibrator_v5_1

Rules:
- Trained on TRAIN (10,500 cases) + VALIDATION_TUNE (1,125 cases) = 11,625 cases
- Calibrator trained strictly on VALIDATION_CALIBRATION (1,125 cases)
- ZERO test set exposure
- Outputs:
  ml/artifacts/location_ranker_v5_1.joblib
  ml/artifacts/location_calibrator_v5_1.joblib
"""

import os
import sys
import time
import json
import hashlib
import joblib
import numpy as np
import pandas as pd
from xgboost import XGBClassifier
from sklearn.linear_model import LogisticRegression

from ml.features.build_v5_1_candidate_features import (
    V51FeatureBuilder,
    LOCATION_FEATURE_NAMES_V5_1
)

RANDOM_SEED = 26184

def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def train_v5_1_pipeline():
    t_start = time.time()
    print("=" * 80)
    print("CYBERSHIELD AI — LOCATION V5.1 CONTROLLED TRAINING PIPELINE")
    print("=" * 80)

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    data_path = os.path.join(base_dir, "ml", "data", "delhi_v5_cases.csv.gz")
    artifacts_dir = os.path.join(base_dir, "ml", "artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)

    df_cases = pd.read_csv(data_path)
    train_cases = df_cases[df_cases["split"] == "train"].reset_index(drop=True)
    val_cases = df_cases[df_cases["split"] == "validation"].reset_index(drop=True)

    n_val_tune = len(val_cases) // 2
    val_tune_cases = val_cases.iloc[:n_val_tune].reset_index(drop=True)
    val_cal_cases = val_cases.iloc[n_val_tune:].reset_index(drop=True)

    # Final training set for ranker: TRAIN + VALIDATION_TUNE
    train_plus_tune_cases = pd.concat([train_cases, val_tune_cases]).sort_values("event_timestamp").reset_index(drop=True)

    print(f"Cases Breakdown:")
    print(f"  Train cases: {len(train_cases)}")
    print(f"  Validation Tune cases: {len(val_tune_cases)}")
    print(f"  Combined Ranker Fitting Cases: {len(train_plus_tune_cases)}")
    print(f"  Validation Calibration cases (Calibrator Only): {len(val_cal_cases)}")
    print(f"  Original Test cases (Untouched): {len(df_cases[df_cases['split'] == 'test'])}")

    fb = V51FeatureBuilder()

    print("\nBuilding candidate feature matrices for COMBINED TRAINING (TRAIN + TUNE)...")
    X_fit, y_fit, _ = fb.build_candidate_matrices(train_plus_tune_cases, top_k=25)
    print(f"Fitting candidate matrix: {X_fit.shape}, Positives: {y_fit.sum()} ({y_fit.mean()*100:.2f}%)")

    print("\nBuilding candidate feature matrices for VALIDATION CALIBRATION...")
    X_val_cal, y_val_cal, _ = fb.build_candidate_matrices(val_cal_cases, top_k=25, historical_cases=train_plus_tune_cases)
    print(f"Val Cal candidate matrix: {X_val_cal.shape}, Positives: {y_val_cal.sum()} ({y_val_cal.mean()*100:.2f}%)")

    # Train Location Model V5.1 with frozen hyperparameters
    print("\nTraining XGBClassifier (cashout-location-xgb-v5.1)...")
    model = XGBClassifier(
        n_estimators=180,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.85,
        colsample_bytree=0.80,
        scale_pos_weight=1.5,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=RANDOM_SEED,
        tree_method="hist"
    )

    t_fit_start = time.time()
    model.fit(X_fit, y_fit, verbose=40)
    fit_duration = time.time() - t_fit_start
    print(f"XGBClassifier v5.1 fitted in {fit_duration:.2f} seconds.")

    # Save Location Model V5.1
    model_path = os.path.join(artifacts_dir, "location_ranker_v5_1.joblib")
    joblib.dump(model, model_path, compress=3)
    model_sha = compute_sha256(model_path)
    print(f"Location model v5.1 saved to {model_path} (SHA-256: {model_sha})")

    # Fit Platt Calibrator on VALIDATION CALIBRATION ONLY
    print("\nFitting Platt calibrator on VALIDATION CALIBRATION...")
    raw_cal_preds = model.predict_proba(X_val_cal)[:, 1]

    calibrator = LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000, random_state=RANDOM_SEED)
    calibrator.fit(raw_cal_preds.reshape(-1, 1), y_val_cal)

    cal_path = os.path.join(artifacts_dir, "location_calibrator_v5_1.joblib")
    joblib.dump(calibrator, cal_path, compress=3)
    cal_sha = compute_sha256(cal_path)
    print(f"Calibrator v5.1 saved to {cal_path} (SHA-256: {cal_sha})")

    print("\n" + "=" * 80)
    print("LOCATION V5.1 TRAINING & CALIBRATION COMPLETE.")
    print("=" * 80)

if __name__ == "__main__":
    train_v5_1_pipeline()
