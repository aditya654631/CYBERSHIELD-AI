import os
import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor

def train_models():
    os.makedirs("ml/artifacts", exist_ok=True)
    print("[MLTraining] Training candidate location ranking model and time regressor...")

    # Generate synthetic training matrices
    np.random.seed(42)
    n_samples = 1200
    n_features = 10

    X = np.random.randn(n_samples, n_features)
    # Binary/multi-class target for location ranking
    y_rank = np.random.choice([0, 1, 2], size=n_samples, p=[0.6, 0.25, 0.15])
    # Time until cash-out in minutes (target: 60 - 360 mins)
    y_time = np.random.normal(loc=180, scale=45, size=n_samples)

    clf = GradientBoostingClassifier(n_estimators=50, random_state=42)
    clf.fit(X, y_rank)

    reg = GradientBoostingRegressor(n_estimators=50, random_state=42)
    reg.fit(X, y_time)

    loc_model_path = "ml/artifacts/location_ranker.joblib"
    time_model_path = "ml/artifacts/time_regressor.joblib"

    joblib.dump(clf, loc_model_path)
    joblib.dump(reg, time_model_path)

    print(f"[MLTraining] Saved location ranker to {loc_model_path}")
    print(f"[MLTraining] Saved time regressor to {time_model_path}")

if __name__ == "__main__":
    train_models()
