"""
CyberShield AI — Delhi V4 Time Model Training Pipeline
Phase A.4: Controlled Offline Time Regressor Training

Model Produced:
- ml/artifacts/time_regressor_v4.joblib (XGBRegressor)
"""

import os
import sys
import time
import json
import hashlib
import joblib
import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from ml.features.build_v5_candidate_features import (
    V5FeatureBuilder,
    TIME_FEATURE_NAMES_V4
)

RANDOM_SEED = 26184

def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def train_time_pipeline():
    t_start = time.time()
    print("=" * 80)
    print("CYBERSHIELD AI — TIME V4 CONTROLLED OFFLINE TRAINING PIPELINE")
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

    fb = V5FeatureBuilder()

    print("Extracting time features for TRAIN...")
    X_train_time = fb.extract_time_features(train_cases)
    y_train_time = np.log1p(train_cases["realized_cashout_minutes"].values)

    print("Extracting time features for VALIDATION TUNE...")
    X_val_time = fb.extract_time_features(val_tune_cases)
    y_val_time = np.log1p(val_tune_cases["realized_cashout_minutes"].values)

    print(f"Train time matrix: {X_train_time.shape}, Val time matrix: {X_val_time.shape}")

    print("\nTraining XGBRegressor (cashout-time-xgb-v4)...")
    model = XGBRegressor(
        n_estimators=150,
        max_depth=5,
        learning_rate=0.06,
        subsample=0.85,
        colsample_bytree=0.80,
        objective="reg:squarederror",
        eval_metric="rmse",
        random_state=RANDOM_SEED,
        tree_method="hist"
    )

    t_fit_start = time.time()
    model.fit(
        X_train_time, y_train_time,
        eval_set=[(X_val_time, y_val_time)],
        verbose=30
    )
    fit_duration = time.time() - t_fit_start
    print(f"XGBRegressor fitted in {fit_duration:.2f} seconds.")

    # Save Time Model
    model_path = os.path.join(artifacts_dir, "time_regressor_v4.joblib")
    joblib.dump(model, model_path, compress=3)
    model_sha = compute_sha256(model_path)
    print(f"Time model saved to {model_path} (SHA-256: {model_sha})")

    print("\n" + "=" * 80)
    print("TIME V4 TRAINING COMPLETE.")
    print("=" * 80)

if __name__ == "__main__":
    train_time_pipeline()
