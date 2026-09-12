"""
CyberShield AI — Leakage-Free Training and Scientific Evaluation Pipeline (v2)
Version: cashout-location-xgb-v2 & time-regressor-xgb-v2

Remediations Enforced:
1. Zero Force-Add on Validation and Test:
   - Only Training may append target cluster if absent to construct positive examples.
   - Validation and Test strictly evaluate natural CandidateLocationGenerator output.
   - Natural Candidate Recall reported separately from End-to-End Recall@K.
2. Platt Probability Calibration:
   - Calibrator is fitted on VALIDATION data only (Test labels remain completely untouched).
3. Dual Evaluation:
   - Chronological Temporal Test Set (3,000 complaints)
   - Cold-Start Test Set (1,500 complaints with 0.0% mule account overlap with training)
4. Defensible Geographic Metric:
   - Renamed to "Median Cluster-Centroid Distance Error"
5. Label-Shuffle and High-Risk Feature Ablation Sanity Experiments
"""

import os
import sys
import json
import math
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List, Tuple
from xgboost import XGBClassifier, XGBRegressor
from sklearn.linear_model import LogisticRegression

# Add workspace root to path
workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from ml.geo.candidate_generator import CandidateLocationGenerator, haversine_km
from ml.features.feature_pipeline import FeaturePipeline, FEATURE_COLUMNS_LOCATION, FEATURE_COLUMNS_TIME

RANDOM_SEED = 42
MODEL_VERSION = "cashout-location-xgb-v2"
TIME_MODEL_VERSION = "time-regressor-xgb-v2"

def train_and_evaluate_v2_pipeline(
    data_dir: str = "ml/data",
    artifacts_dir: str = "ml/artifacts"
) -> Dict[str, Any]:
    print("=" * 75)
    print(f"CyberShield AI — Scientifically Defensible ML Training [{MODEL_VERSION}]")
    print("=" * 75)

    os.makedirs(artifacts_dir, exist_ok=True)
    np.random.seed(RANDOM_SEED)

    # 1. Load Dataset
    print("[1/7] Loading synthetic cybercrime dataset v2...")
    clusters_df = pd.read_csv(os.path.join(data_dir, "clusters.csv.gz"), compression="gzip")
    accounts_df = pd.read_csv(os.path.join(data_dir, "accounts.csv.gz"), compression="gzip")
    complaints_df = pd.read_csv(os.path.join(data_dir, "complaints.csv.gz"), compression="gzip")
    transactions_df = pd.read_csv(os.path.join(data_dir, "transactions.csv.gz"), compression="gzip")

    clusters_list = clusters_df.to_dict(orient="records")
    for c in clusters_list:
        c["id"] = int(c["id"])
        c["lat"] = float(c["lat"])
        c["lon"] = float(c["lon"])
        c["base_risk"] = float(c.get("base_risk", 0.5))
        c["atm_density"] = float(c.get("atm_density", 15))

    cluster_coords = {c["id"]: (c["lat"], c["lon"]) for c in clusters_list}
    account_to_cluster = dict(zip(accounts_df["account_id"], accounts_df["home_cluster_id"]))
    cand_gen = CandidateLocationGenerator(clusters_list)
    feature_pipeline = FeaturePipeline()

    total_c = len(complaints_df)
    print(f"Loaded {total_c} complaints, {len(clusters_list)} clusters, {len(accounts_df)} accounts.")

    # 2. Chronological Temporal Split
    print("[2/7] Enforcing strict chronological train/validation/test split...")
    complaints_df = complaints_df.sort_values(by="incident_timestamp").reset_index(drop=True)

    train_n = 14000
    val_n = 3000
    test_n = 3000

    train_df = complaints_df.iloc[:train_n].copy()
    val_df = complaints_df.iloc[train_n : train_n + val_n].copy()
    test_df = complaints_df.iloc[train_n + val_n : train_n + val_n + test_n].copy()

    train_complaints = train_df.to_dict(orient="records")
    val_complaints = val_df.to_dict(orient="records")
    test_complaints = test_df.to_dict(orient="records")

    print(f" - Train Split:       {len(train_complaints)} complaints ({train_df['incident_timestamp'].min()} to {train_df['incident_timestamp'].max()})")
    print(f" - Validation Split:  {len(val_complaints)} complaints ({val_df['incident_timestamp'].min()} to {val_df['incident_timestamp'].max()})")
    print(f" - Test Split:        {len(test_complaints)} complaints ({test_df['incident_timestamp'].min()} to {test_df['incident_timestamp'].max()})")

    # Verify temporal gap
    assert train_df['incident_timestamp'].max() <= val_df['incident_timestamp'].min(), "Temporal leak: train overlap with validation"
    assert val_df['incident_timestamp'].max() <= test_df['incident_timestamp'].min(), "Temporal leak: val overlap with test"
    print(" -> Temporal separation verified: max(train) <= min(val) and max(val) <= min(test).")

    # 3. Feature Extraction & Zero Force-Add Candidate Generation
    print("[3/7] Generating candidates and extracting multimodal feature matrices...")

    def build_dataset(complaints_subset, is_training=False):
        X_loc_list = []
        y_loc_list = []
        X_time_list = []
        y_time_list = []
        eval_meta = []
        natural_hits = 0

        for comp in complaints_subset:
            target_cl_id = int(comp["target_cluster_id"])
            mule_id = int(comp.get("beneficiary_mule_id", 0))
            mule_cl_id = account_to_cluster.get(mule_id)

            # Generate natural candidates
            cands = cand_gen.generate_candidates_for_complaint(
                comp,
                beneficiary_mule_cluster_id=mule_cl_id,
                top_k=25
            )

            cand_ids = [c["cluster_id"] for c in cands]
            target_in_cands = (target_cl_id in cand_ids)
            if target_in_cands:
                natural_hits += 1

            # ZERO FORCE-ADD ON VALIDATION AND TEST
            if is_training:
                # Training only: append positive target if absent so supervised sample exists
                if not target_in_cands and target_cl_id in cand_gen.cluster_by_id:
                    t_cl = cand_gen.cluster_by_id[target_cl_id]
                    cands.append({
                        "cluster_id": t_cl["id"],
                        "name": t_cl["name"],
                        "city": t_cl["city"],
                        "state": t_cl["state"],
                        "lat": t_cl["lat"],
                        "lon": t_cl["lon"],
                        "atm_density": t_cl.get("atm_density", 15),
                        "historical_risk": t_cl.get("base_risk", 0.5),
                        "historical_cashout_count": comp.get("hist_cluster_cashout_count", 200),
                        "historical_cashout_amount": comp.get("hist_cluster_cashout_amount", 10000000.0),
                        "reasoning": "Corridor prior match",
                        "is_mule_corridor": 1 if target_cl_id == mule_cl_id else 0,
                        "distance_from_victim_km": round(haversine_km(comp["victim_lat"], comp["victim_lon"], t_cl["lat"], t_cl["lon"]), 1)
                    })

            # Build feature rows
            X_loc, X_t, _, _ = feature_pipeline.build_candidate_matrix(comp, cands)

            # Ground truth binary labels (if target not in natural candidates, all labels are 0)
            labels = [1 if c["cluster_id"] == target_cl_id else 0 for c in cands]

            X_loc_list.append(X_loc)
            y_loc_list.extend(labels)

            delay_target = float(comp.get("minutes_until_cashout", 120.0))
            X_time_list.append(X_t[0])
            y_time_list.append(delay_target)

            eval_meta.append({
                "complaint_id": comp["complaint_id"],
                "target_cluster_id": target_cl_id,
                "target_coords": cluster_coords.get(target_cl_id, (comp["victim_lat"], comp["victim_lon"])),
                "candidates": cands,
                "n_candidates": len(cands),
                "is_cold_start": bool(comp.get("is_cold_start", False)),
                "target_in_candidates": target_in_cands,
                "target_mechanism": comp.get("target_mechanism", "unknown")
            })

        X_location = np.vstack(X_loc_list)
        y_location = np.array(y_loc_list, dtype=np.int32)
        X_time = np.array(X_time_list, dtype=np.float32)
        y_time = np.array(y_time_list, dtype=np.float32)
        cand_recall_pct = (natural_hits / len(complaints_subset)) * 100

        return X_location, y_location, X_time, y_time, eval_meta, cand_recall_pct

    print(" -> Building training feature matrices (target ensured for supervised learning)...")
    X_train_loc, y_train_loc, X_train_time, y_train_time, _, train_cand_recall = build_dataset(train_complaints, is_training=True)

    print(" -> Building validation feature matrices (STRICT ZERO FORCE-ADD)...")
    X_val_loc, y_val_loc, X_val_time, y_val_time, val_meta, val_cand_recall = build_dataset(val_complaints, is_training=False)

    print(" -> Building held-out test feature matrices (STRICT ZERO FORCE-ADD)...")
    X_test_loc, y_test_loc, X_test_time, y_test_time, test_meta, test_cand_recall = build_dataset(test_complaints, is_training=False)

    print(f" -> Natural Candidate Recall (Zero Force-Add):")
    print(f"    Validation: {val_cand_recall:.2f}%")
    print(f"    Test:       {test_cand_recall:.2f}%")

    # 4. Train Location Ranking Model
    print("[4/7] Training Location Ranking XGBoost Model...")
    pos_weight = float((len(y_train_loc) - sum(y_train_loc)) / max(1, sum(y_train_loc)))
    location_clf = XGBClassifier(
        n_estimators=130,
        max_depth=5,
        learning_rate=0.07,
        scale_pos_weight=pos_weight * 0.5,
        random_state=RANDOM_SEED,
        eval_metric="logloss",
        n_jobs=-1
    )
    location_clf.fit(X_train_loc, y_train_loc, eval_set=[(X_val_loc, y_val_loc)], verbose=False)
    print(" -> Location model trained successfully.")

    # 5. Train Time-to-Cashout Regressor
    print("[5/7] Training Time-to-Cashout Regressor...")
    time_reg = XGBRegressor(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.07,
        random_state=RANDOM_SEED,
        eval_metric="mae",
        n_jobs=-1
    )
    time_reg.fit(X_train_time, y_train_time, eval_set=[(X_val_time, y_val_time)], verbose=False)
    print(" -> Time model trained successfully.")

    # 6. Platt Probability Calibration (Validation Data Only)
    print("[6/7] Fitting Platt Probability Calibrator on VALIDATION split only...")
    val_raw_probs = location_clf.predict_proba(X_val_loc)[:, 1]

    # Convert to log-odds / logit for logistic regression calibration
    val_logits = np.log(np.clip(val_raw_probs, 1e-6, 1 - 1e-6) / (1 - np.clip(val_raw_probs, 1e-6, 1 - 1e-6))).reshape(-1, 1)

    calibrator = LogisticRegression(solver="lbfgs", random_state=RANDOM_SEED)
    calibrator.fit(val_logits, y_val_loc)
    print(" -> Probability calibrator successfully fitted on validation predictions.")

    # 7. Comprehensive Evaluation on Held-Out Test Data
    print("[7/7] Computing Defensible Evaluation Metrics on Held-Out Test Data...")

    test_raw_probs = location_clf.predict_proba(X_test_loc)[:, 1]
    test_logits = np.log(np.clip(test_raw_probs, 1e-6, 1 - 1e-6) / (1 - np.clip(test_raw_probs, 1e-6, 1 - 1e-6))).reshape(-1, 1)
    test_cal_probs = calibrator.predict_proba(test_logits)[:, 1]

    test_time_preds = time_reg.predict(X_test_time)

    # Ranking evaluation helper
    def evaluate_ranking(probs, meta_list):
        r1_hits = 0
        r3_hits = 0
        r5_hits = 0
        p3_hits = 0
        mrr_sum = 0.0
        dist_errors_km = []
        idx = 0

        for item in meta_list:
            n = item["n_candidates"]
            p_slice = probs[idx : idx + n]
            cands = item["candidates"]
            target = item["target_cluster_id"]
            target_coords = item["target_coords"]

            ranked = sorted(zip(p_slice, cands), key=lambda x: x[0], reverse=True)
            ranked_ids = [c[1]["cluster_id"] for c in ranked]

            # Top 1
            top1_cand = ranked[0][1]
            top1_id = top1_cand["cluster_id"]
            if top1_id == target:
                r1_hits += 1
                dist_errors_km.append(0.0)
            else:
                top1_coords = (top1_cand["lat"], top1_cand["lon"])
                dist_errors_km.append(haversine_km(target_coords[0], target_coords[1], top1_coords[0], top1_coords[1]))

            # Top 3
            top3_ids = ranked_ids[:3]
            if target in top3_ids:
                r3_hits += 1
                p3_hits += 1

            # Top 5
            top5_ids = ranked_ids[:5]
            if target in top5_ids:
                r5_hits += 1

            # MRR
            if target in ranked_ids:
                rank_pos = ranked_ids.index(target) + 1
                mrr_sum += (1.0 / rank_pos)
            else:
                mrr_sum += 0.0 # Missed candidate = 0 MRR

            idx += n

        total = len(meta_list)
        d_arr = np.array(dist_errors_km)
        return {
            "recall_at_1": round((r1_hits / total) * 100, 2),
            "recall_at_3": round((r3_hits / total) * 100, 2),
            "recall_at_5": round((r5_hits / total) * 100, 2),
            "precision_at_3": round((p3_hits / (total * 3)) * 100, 2),
            "mrr": round(mrr_sum / total, 3),
            "median_distance_error_km": round(float(np.median(d_arr)), 1),
            "within_5km": round(float(np.mean(d_arr <= 5.0) * 100), 1),
            "within_10km": round(float(np.mean(d_arr <= 10.0) * 100), 1),
            "within_25km": round(float(np.mean(d_arr <= 25.0) * 100), 1)
        }

    # A. Full Temporal Test Metrics (Calibrated)
    temporal_metrics = evaluate_ranking(test_cal_probs, test_meta)

    # B. Cold-Start Subset Metrics (1,500 complaints with unseen mule rings)
    cold_start_meta = [m for m in test_meta if m["is_cold_start"]]
    cold_start_indices = []
    curr = 0
    for m in test_meta:
        n = m["n_candidates"]
        if m["is_cold_start"]:
            cold_start_indices.extend(range(curr, curr + n))
        curr += n

    cold_start_probs = test_cal_probs[cold_start_indices]
    cold_start_metrics = evaluate_ranking(cold_start_probs, cold_start_meta)
    cold_cand_recall = (sum(1 for m in cold_start_meta if m["target_in_candidates"]) / len(cold_start_meta)) * 100

    # C. Probability Calibration Metrics
    brier_before = float(np.mean((test_raw_probs - y_test_loc) ** 2))
    brier_after = float(np.mean((test_cal_probs - y_test_loc) ** 2))
    pos_mask = (y_test_loc == 1)
    neg_mask = (y_test_loc == 0)

    # D. Time Model Metrics
    time_mae = float(np.mean(np.abs(test_time_preds - y_test_time)))
    time_med_ae = float(np.median(np.abs(test_time_preds - y_test_time)))
    time_window_cov = float(np.mean(np.abs(test_time_preds - y_test_time) <= 60.0) * 100)

    # 8. Sanity Experiments: Label Shuffle & Feature Ablation
    print("\n[8/7] Running Sanity Experiments (Label Shuffle & Feature Ablation)...")

    # Label shuffle
    y_shuffled = y_train_loc.copy()
    np.random.shuffle(y_shuffled)
    shuf_clf = XGBClassifier(n_estimators=100, max_depth=5, learning_rate=0.07, random_state=RANDOM_SEED, n_jobs=-1)
    shuf_clf.fit(X_train_loc, y_shuffled, verbose=False)
    shuf_probs = shuf_clf.predict_proba(X_test_loc)[:, 1]
    shuf_metrics = evaluate_ranking(shuf_probs, test_meta)

    # Feature ablation: drop is_mule_corridor and distance_from_high_risk_account
    feature_names = list(FEATURE_COLUMNS_LOCATION)
    drop_cols = ["is_mule_corridor", "distance_from_high_risk_account"]
    keep_indices = [i for i, f in enumerate(feature_names) if f not in drop_cols]
    abl_clf = XGBClassifier(n_estimators=100, max_depth=5, learning_rate=0.07, random_state=RANDOM_SEED, n_jobs=-1)
    abl_clf.fit(X_train_loc[:, keep_indices], y_train_loc, verbose=False)
    abl_probs = abl_clf.predict_proba(X_test_loc[:, keep_indices])[:, 1]
    abl_metrics = evaluate_ranking(abl_probs, test_meta)

    print("\n" + "=" * 70)
    print("SCIENTIFICALLY DEFENSIBLE TEST EVALUATION RESULTS")
    print("=" * 70)
    print(f"Natural Candidate Recall (Zero Force-Add): {test_cand_recall:.2f}%")
    print(f"Temporal Test Recall@1:                    {temporal_metrics['recall_at_1']}%")
    print(f"Temporal Test Recall@3:                    {temporal_metrics['recall_at_3']}%")
    print(f"Temporal Test Recall@5:                    {temporal_metrics['recall_at_5']}%")
    print(f"Temporal Test MRR:                         {temporal_metrics['mrr']}")
    print(f"Median Cluster-Centroid Distance Error:    {temporal_metrics['median_distance_error_km']} km")
    print(f"Predictions Within 5 km:                   {temporal_metrics['within_5km']}%")
    print(f"Predictions Within 10 km:                  {temporal_metrics['within_10km']}%")
    print(f"Predictions Within 25 km:                  {temporal_metrics['within_25km']}%")
    print(f"Brier Score (Calibrated):                  {brier_after:.4f} (Before: {brier_before:.4f})")
    print(f"Cold-Start Test Recall@1:                  {cold_start_metrics['recall_at_1']}% (Candidate Recall: {cold_cand_recall:.2f}%)")
    print(f"Cold-Start Test Recall@3:                  {cold_start_metrics['recall_at_3']}%")
    print(f"Label-Shuffle Sanity Recall@1:             {shuf_metrics['recall_at_1']}% (Baseline chance ~4.0%)")
    print(f"Feature-Ablated Recall@1 (No Mule Feats):  {abl_metrics['recall_at_1']}%")
    print(f"Time-to-Cashout MAE:                       {time_mae:.1f} mins (Median: {time_med_ae:.1f} mins)")
    print("=" * 70)

    # 9. Save Version 2 Artifacts & Metadata
    loc_artifact_v2 = os.path.join(artifacts_dir, "location_ranker_v2.joblib")
    time_artifact_v2 = os.path.join(artifacts_dir, "time_regressor_v2.joblib")
    cal_artifact_v2 = os.path.join(artifacts_dir, "calibrator_v2.joblib")
    schema_artifact_v2 = os.path.join(artifacts_dir, "feature_schema_v2.json")
    meta_artifact_v2 = os.path.join(artifacts_dir, "model_metadata_v2.json")

    joblib.dump(location_clf, loc_artifact_v2)
    joblib.dump(time_reg, time_artifact_v2)
    joblib.dump(calibrator, cal_artifact_v2)

    schema_dict = {
        "version": "v2",
        "location_features": FEATURE_COLUMNS_LOCATION,
        "time_features": FEATURE_COLUMNS_TIME,
        "feature_count_location": len(FEATURE_COLUMNS_LOCATION),
        "feature_count_time": len(FEATURE_COLUMNS_TIME)
    }
    with open(schema_artifact_v2, "w") as f:
        json.dump(schema_dict, f, indent=2)

    meta_dict = {
        "model_version": MODEL_VERSION,
        "time_model_version": TIME_MODEL_VERSION,
        "training_timestamp": datetime.utcnow().isoformat(),
        "random_seed": RANDOM_SEED,
        "dataset_type": "domain_meaningful_synthetic_v2",
        "dataset_split": "Chronological Temporal Split (70% Train / 15% Val / 15% Test)",
        "training_complaints": len(train_complaints),
        "validation_complaints": len(val_complaints),
        "test_complaints": len(test_complaints),
        "cold_start_test_complaints": len(cold_start_meta),
        "model_class_location": "xgboost.XGBClassifier",
        "model_class_time": "xgboost.XGBRegressor",
        "calibrator_class": "sklearn.linear_model.LogisticRegression (Platt Scaling on Validation)",
        "evaluation_label": "Prototype Evaluation — Synthetic/Anonymized Demo Data",
        "metrics": {
            "natural_candidate_recall": f"{test_cand_recall:.1f}%",
            "recall_at_1": f"{temporal_metrics['recall_at_1']}%",
            "recall_at_3": f"{temporal_metrics['recall_at_3']}%",
            "recall_at_5": f"{temporal_metrics['recall_at_5']}%",
            "precision_at_3": f"{temporal_metrics['precision_at_3']}%",
            "mrr": temporal_metrics["mrr"],
            "median_cluster_centroid_distance_error_km": f"{temporal_metrics['median_distance_error_km']} km",
            "within_5km": f"{temporal_metrics['within_5km']}%",
            "within_10km": f"{temporal_metrics['within_10km']}%",
            "within_25km": f"{temporal_metrics['within_25km']}%",
            "brier_score": round(brier_after, 4),
            "brier_score_uncalibrated": round(brier_before, 4),
            "cold_start_candidate_recall": f"{cold_cand_recall:.1f}%",
            "cold_start_recall_at_1": f"{cold_start_metrics['recall_at_1']}%",
            "cold_start_recall_at_3": f"{cold_start_metrics['recall_at_3']}%",
            "shuffled_recall_at_1": f"{shuf_metrics['recall_at_1']}%",
            "ablated_recall_at_1": f"{abl_metrics['recall_at_1']}%",
            "time_mae_minutes": f"{time_mae:.1f} mins",
            "time_median_absolute_error_minutes": f"{time_med_ae:.1f} mins",
            "time_window_coverage": f"{time_window_cov:.1f}%"
        },
        "disclaimer": "Evaluation uses domain-meaningful synthetic data. Production performance requires validation and retraining on authorized historical NCRP/banking data.",
        "geographic_scope": "Cluster-level prioritization (2.5 km radius); not exact physical ATM/GPS coordinate prediction."
    }

    with open(meta_artifact_v2, "w") as f:
        json.dump(meta_dict, f, indent=2)

    print(f" -> Artifacts v2 saved to {artifacts_dir}:")
    print(f"    - {loc_artifact_v2}")
    print(f"    - {time_artifact_v2}")
    print(f"    - {cal_artifact_v2}")
    print(f"    - {meta_artifact_v2}")
    print(f"    - {schema_artifact_v2}")

    return meta_dict

if __name__ == "__main__":
    train_and_evaluate_v2_pipeline()
