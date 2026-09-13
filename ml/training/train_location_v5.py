"""
CyberShield AI — Delhi V5 Location Model & Calibrator Training Pipeline
Phase A.4: Controlled Offline Model Training & Platt Calibration

Models Produced:
1. ml/artifacts/location_ranker_v5.joblib (XGBClassifier)
2. ml/artifacts/location_calibrator_v5.joblib (LogisticRegression Platt scaling)
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

from ml.features.build_v5_candidate_features import (
    V5FeatureBuilder,
    LOCATION_FEATURE_NAMES_V5
)

RANDOM_SEED = 26184

def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def train_location_pipeline():
    t_start = time.time()
    print("=" * 80)
    print("CYBERSHIELD AI — LOCATION V5 CONTROLLED OFFLINE TRAINING PIPELINE")
    print("=" * 80)

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    data_path = os.path.join(base_dir, "ml", "data", "delhi_v5_cases.csv.gz")
    artifacts_dir = os.path.join(base_dir, "ml", "artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)

    df_cases = pd.read_csv(data_path)
    print(f"Loaded {len(df_cases)} cases from {data_path}")

    # Split assignments
    train_cases = df_cases[df_cases["split"] == "train"].reset_index(drop=True)
    val_cases = df_cases[df_cases["split"] == "validation"].reset_index(drop=True)

    # Sub-partition validation chronologically into tune (~50%) and calibration (~50%)
    n_val_tune = len(val_cases) // 2
    val_tune_cases = val_cases.iloc[:n_val_tune].reset_index(drop=True)
    val_cal_cases = val_cases.iloc[n_val_tune:].reset_index(drop=True)

    print(f"Cases breakdown:")
    print(f"  Train cases: {len(train_cases)}")
    print(f"  Validation Tune cases: {len(val_tune_cases)}")
    print(f"  Validation Calibration cases: {len(val_cal_cases)}")
    print(f"  Test cases (Held-out untouched): {len(df_cases[df_cases['split'] == 'test'])}")

    fb = V5FeatureBuilder()

    print("\nExtracting candidate feature matrices for TRAIN...")
    X_train, y_train, _ = fb.build_candidate_matrices(train_cases, top_k=25)
    print(f"Train candidate matrix: {X_train.shape}, positive labels: {y_train.sum()} ({y_train.mean()*100:.2f}%)")

    print("\nExtracting candidate feature matrices for VALIDATION TUNE...")
    X_val_tune, y_val_tune, _ = fb.build_candidate_matrices(val_tune_cases, top_k=25)
    print(f"Val tune candidate matrix: {X_val_tune.shape}, positive labels: {y_val_tune.sum()} ({y_val_tune.mean()*100:.2f}%)")

    print("\nExtracting candidate feature matrices for VALIDATION CALIBRATION...")
    X_val_cal, y_val_cal, _ = fb.build_candidate_matrices(val_cal_cases, top_k=25)
    print(f"Val cal candidate matrix: {X_val_cal.shape}, positive labels: {y_val_cal.sum()} ({y_val_cal.mean()*100:.2f}%)")

    # Positive-to-negative ratio
    pos_neg_ratio = (len(y_train) - y_train.sum()) / max(1, y_train.sum())
    print(f"\nPositive-to-negative ratio: {pos_neg_ratio:.2f}:1")

    # Model training with frozen hyperparameters
    print("\nTraining XGBClassifier (cashout-location-xgb-v5)...")
    model = XGBClassifier(
        n_estimators=180,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.85,
        colsample_bytree=0.80,
        objective="binary:logistic",
        eval_metric="logloss",
        scale_pos_weight=1.5, # Mild weight to prevent extreme probabilities before calibration
        random_state=RANDOM_SEED,
        tree_method="hist"
    )

    t_fit_start = time.time()
    model.fit(
        X_train, y_train,
        eval_set=[(X_val_tune, y_val_tune)],
        verbose=40
    )
    fit_duration = time.time() - t_fit_start
    print(f"XGBClassifier fitted in {fit_duration:.2f} seconds.")

    # Save Location Model
    model_path = os.path.join(artifacts_dir, "location_ranker_v5.joblib")
    joblib.dump(model, model_path, compress=3)
    model_sha = compute_sha256(model_path)
    print(f"Location model saved to {model_path} (SHA-256: {model_sha})")

    # Platt Calibration fitting on VALIDATION CALIBRATION
    print("\nFitting Platt calibrator on VALIDATION CALIBRATION...")
    raw_cal_preds = model.predict_proba(X_val_cal)[:, 1]

    calibrator = LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000, random_state=RANDOM_SEED)
    calibrator.fit(raw_cal_preds.reshape(-1, 1), y_val_cal)

    cal_path = os.path.join(artifacts_dir, "location_calibrator_v5.joblib")
    joblib.dump(calibrator, cal_path, compress=3)
    cal_sha = compute_sha256(cal_path)
    print(f"Calibrator saved to {cal_path} (SHA-256: {cal_sha})")

    print("\n" + "=" * 80)
    print("LOCATION V5 TRAINING & CALIBRATION COMPLETE.")
    print("=" * 80)

if __name__ == "__main__":
    train_location_pipeline()
