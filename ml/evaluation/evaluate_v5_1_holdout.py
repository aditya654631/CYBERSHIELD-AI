"""
CyberShield AI — Phase A.4C One-Shot External Holdout Evaluation
Evaluates Location Model V5.1 (cashout-location-xgb-v5.1) on fresh external holdout (seed 26185, N=3000).
Also evaluates production V4, A.4 V5, and baseline models for post-freeze benchmark comparison.
Generates:
- ml/evaluation/holdout/v5_1_external_holdout_evaluation.json
- ml/artifacts/model_metadata_v5_1.json
"""

import os
import sys
import json
import time
import hashlib
import joblib
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from ml.data.generate_delhi_v5_dataset import (
    DELHI_CLUSTERS_V5,
    ALL_11_DISTRICTS,
    haversine_km
)
from ml.features.build_v5_1_candidate_features import (
    V51CandidateGenerator,
    V51FeatureBuilder,
    LOCATION_FEATURE_NAMES_V5_1
)
from ml.features.build_v5_candidate_features import V5FeatureBuilder

RANDOM_SEED = 26185

def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def compute_ece(probs: np.ndarray, y_true: np.ndarray, n_bins: int = 10) -> Tuple[float, List[Dict[str, Any]]]:
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(probs)
    bin_details = []
    for i in range(n_bins):
        b_min, b_max = bins[i], bins[i + 1]
        mask = (probs >= b_min) & (probs < b_max) if i < n_bins - 1 else (probs >= b_min) & (probs <= b_max)
        cnt = int(np.sum(mask))
        if cnt > 0:
            bin_conf = float(np.mean(probs[mask]))
            bin_acc = float(np.mean(y_true[mask]))
            ece += (cnt / n) * abs(bin_acc - bin_conf)
            bin_details.append({"bin": i, "count": cnt, "mean_conf": round(bin_conf, 4), "mean_acc": round(bin_acc, 4)})
        else:
            bin_details.append({"bin": i, "count": 0, "mean_conf": 0.0, "mean_acc": 0.0})
    return float(ece), bin_details

def run_evaluation():
    t_start = time.time()
    print("=" * 80)
    print("CYBERSHIELD AI — PHASE A.4C ONE-SHOT FRESH HOLDOUT EVALUATION")
    print("=" * 80)

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    holdout_path = os.path.join(base_dir, "ml", "evaluation", "holdout", "v5_1_external_holdout.csv.gz")
    dev_data_path = os.path.join(base_dir, "ml", "data", "delhi_v5_cases.csv.gz")
    artifacts_dir = os.path.join(base_dir, "ml", "artifacts")
    output_dir = os.path.join(base_dir, "ml", "evaluation", "holdout")

    # Load frozen V5.1 artifacts
    ranker_path_v5_1 = os.path.join(artifacts_dir, "location_ranker_v5_1.joblib")
    calibrator_path_v5_1 = os.path.join(artifacts_dir, "location_calibrator_v5_1.joblib")
    schema_path_v5_1 = os.path.join(artifacts_dir, "feature_schema_v5_1.json")

    ranker_v5_1_sha = compute_sha256(ranker_path_v5_1)
    calibrator_v5_1_sha = compute_sha256(calibrator_path_v5_1)
    schema_v5_1_sha = compute_sha256(schema_path_v5_1)
    holdout_sha = compute_sha256(holdout_path)

    print(f"Location Ranker V5.1 SHA:     {ranker_v5_1_sha}")
    print(f"Location Calibrator V5.1 SHA: {calibrator_v5_1_sha}")
    print(f"Feature Schema V5.1 SHA:      {schema_v5_1_sha}")
    print(f"Holdout Dataset SHA:          {holdout_sha}")

    ranker_v5_1 = joblib.load(ranker_path_v5_1)
    calibrator_v5_1 = joblib.load(calibrator_path_v5_1)
    schema_v5_1 = json.load(open(schema_path_v5_1, "r", encoding="utf-8"))

    # Load benchmarks for post-freeze comparison
    ranker_v4 = joblib.load(os.path.join(artifacts_dir, "location_ranker_v4.joblib"))
    calibrator_v4 = joblib.load(os.path.join(artifacts_dir, "location_calibrator_v4.joblib"))
    schema_v4 = json.load(open(os.path.join(artifacts_dir, "feature_schema_v4.json"), "r", encoding="utf-8"))
    ranker_v5 = joblib.load(os.path.join(artifacts_dir, "location_ranker_v5.joblib"))
    calibrator_v5 = joblib.load(os.path.join(artifacts_dir, "location_calibrator_v5.joblib"))

    # Load datasets
    df_holdout = pd.read_csv(holdout_path)
    df_dev = pd.read_csv(dev_data_path)
    n_holdout = len(df_holdout)
    print(f"\nLoaded {n_holdout} fresh external holdout cases (Seed 26185).")

    cluster_by_id = {c["id"]: c for c in DELHI_CLUSTERS_V5}

    # Step 1: Evaluate Multi-Source Partitioned Quota Candidate Generator across various cutoffs
    print("\nEvaluating candidate retrieval recall across cutoffs (@10, @15, @20, @25, @30, @60)...")
    cand_gen = V51CandidateGenerator(clusters=DELHI_CLUSTERS_V5)

    # Calculate fraud affinity from historical development data
    train_dev = df_dev[df_dev["split"] == "train"]
    fraud_affinity_map = {}
    for ft, grp in train_dev.groupby("fraud_type"):
        top_cids = grp["realized_cashout_cluster_id"].value_counts().index.tolist()[:8]
        fraud_affinity_map[ft] = top_cids

    recalls = {10: 0, 15: 0, 20: 0, 25: 0, 30: 0, 60: 0}
    for _, row in df_holdout.iterrows():
        cands_60 = cand_gen.generate_candidates(
            victim_lat=float(row["victim_lat"]),
            victim_lon=float(row["victim_lon"]),
            victim_district=row["victim_district"],
            terminal_district=row["terminal_mule_district"],
            fraud_type=row["fraud_type"],
            fraud_affinity_map=fraud_affinity_map,
            top_k=60
        )
        c_ids = [c["id"] for c in cands_60]
        true_cid = row["realized_cashout_cluster_id"]
        for k in recalls.keys():
            if true_cid in c_ids[:k]:
                recalls[k] += 1

    candidate_recall_pct = {k: round(v / n_holdout * 100, 2) for k, v in recalls.items()}
    print(f"Candidate Recall on External Holdout: {candidate_recall_pct}")

    # Step 2: Build candidate matrices for V5.1
    print("\nBuilding V5.1 candidate feature matrices for holdout (k=25)...")
    fb_v5_1 = V51FeatureBuilder(clusters=DELHI_CLUSTERS_V5)
    X_holdout_v5_1, y_holdout_v5_1, holdout_meta_v5_1 = fb_v5_1.build_candidate_matrices(
        df_holdout, top_k=25, historical_cases=df_dev
    )
    print(f"V5.1 Matrix shape: {X_holdout_v5_1.shape}, Positive candidates: {y_holdout_v5_1.sum()} ({y_holdout_v5_1.mean()*100:.2f}%)")

    # Predict V5.1
    print("Running V5.1 Inference & Platt Calibration...")
    raw_scores_v5_1 = ranker_v5_1.predict_proba(X_holdout_v5_1)[:, 1]
    cal_probs_v5_1 = calibrator_v5_1.predict_proba(raw_scores_v5_1.reshape(-1, 1))[:, 1]

    # Also build A.4 V5 candidates for comparison
    print("Extracting A.4 V5 baseline predictions on same holdout...")
    fb_v5 = V5FeatureBuilder(clusters=DELHI_CLUSTERS_V5)
    X_holdout_v5, _, holdout_meta_v5 = fb_v5.build_candidate_matrices(df_holdout, top_k=25)
    raw_scores_v5 = ranker_v5.predict_proba(X_holdout_v5)[:, 1]
    cal_probs_v5 = calibrator_v5.predict_proba(raw_scores_v5.reshape(-1, 1))[:, 1]

    # Predict V4 on common features using V5.1 candidate pool
    print("Extracting Production V4 baseline predictions on same holdout...")
    v4_features = schema_v4["location_features"]
    # Provide candidate_same_any_account_zone proxy for V4
    X_holdout_v4 = X_holdout_v5_1.copy()
    if "candidate_same_any_account_zone" not in X_holdout_v4.columns:
        X_holdout_v4["candidate_same_any_account_zone"] = (X_holdout_v4["candidate_corridor_support_score"] > 0).astype(int)
    X_holdout_v4 = X_holdout_v4[v4_features]
    raw_scores_v4 = ranker_v4.predict_proba(X_holdout_v4)[:, 1]
    cal_probs_v4 = calibrator_v4.predict_proba(raw_scores_v4.reshape(-1, 1))[:, 1]

    # Sort cases identically to build_candidate_matrices
    df_eval = df_holdout.sort_values("event_timestamp").reset_index(drop=True)

    # Step 3: Compute Case-Level Metrics
    v5_1_cases = []
    v5_cases = []
    v4_cases = []
    nearest_cases = []
    heuristic_cases = []

    for i in range(n_holdout):
        start_idx = i * 25
        end_idx = start_idx + 25
        case_meta = holdout_meta_v5_1[start_idx:end_idx]
        case_row = df_eval.iloc[i]
        assert case_row["case_id"] == case_meta[0]["case_id"], f"Case ID mismatch at {i}: {case_row['case_id']} != {case_meta[0]['case_id']}"
        true_cid = case_row["realized_cashout_cluster_id"]
        true_cluster = cluster_by_id[true_cid]
        v_lat, v_lon = float(case_row["victim_lat"]), float(case_row["victim_lon"])
        v_dist = case_row["victim_district"]

        cand_cids_v5_1 = [m["candidate_cluster_id"] for m in case_meta]
        in_cand_v5_1 = (true_cid in cand_cids_v5_1)

        # V5.1 Ranking
        case_probs_v5_1 = cal_probs_v5_1[start_idx:end_idx]
        ranked_idx_v5_1 = np.argsort(case_probs_v5_1)[::-1]
        ranked_cids_v5_1 = [cand_cids_v5_1[idx] for idx in ranked_idx_v5_1]

        v5_1_top1 = ranked_cids_v5_1[0]
        v5_1_top1_c = cluster_by_id[v5_1_top1]
        v5_1_sp_err = haversine_km(v5_1_top1_c["lat"], v5_1_top1_c["lon"], true_cluster["lat"], true_cluster["lon"])
        v5_1_mrr = 1.0 / (ranked_cids_v5_1.index(true_cid) + 1) if in_cand_v5_1 else 0.0

        v5_1_cases.append({
            "case_id": case_row["case_id"],
            "true_cid": true_cid,
            "target_in_cand": in_cand_v5_1,
            "top1_match": int(true_cid == ranked_cids_v5_1[0]),
            "top3_match": int(true_cid in ranked_cids_v5_1[:3]),
            "top5_match": int(true_cid in ranked_cids_v5_1[:5]),
            "mrr": v5_1_mrr,
            "spatial_error": v5_1_sp_err,
            "top1_prob": float(case_probs_v5_1[ranked_idx_v5_1[0]]),
            "district": v_dist,
            "fraud_type": case_row["fraud_type"],
            "amount_bucket": case_row["amount_bucket"],
            "amount": float(case_row["amount"]),
            "is_cross_district": int(v_dist != case_row["realized_cashout_district"]),
            "is_syndicate_hub": int(case_row["pattern_type"] == "RECURRING_SYNDICATE_HUB"),
            "hop_count": int(case_row["transaction_hop_count"])
        })

        # V4 Ranking on V5.1 pool
        case_probs_v4 = cal_probs_v4[start_idx:end_idx]
        ranked_idx_v4 = np.argsort(case_probs_v4)[::-1]
        ranked_cids_v4 = [cand_cids_v5_1[idx] for idx in ranked_idx_v4]
        v4_top1_c = cluster_by_id[ranked_cids_v4[0]]
        v4_sp_err = haversine_km(v4_top1_c["lat"], v4_top1_c["lon"], true_cluster["lat"], true_cluster["lon"])
        v4_mrr = 1.0 / (ranked_cids_v4.index(true_cid) + 1) if in_cand_v5_1 else 0.0
        v4_cases.append({
            "top1_match": int(true_cid == ranked_cids_v4[0]),
            "top3_match": int(true_cid in ranked_cids_v4[:3]),
            "top5_match": int(true_cid in ranked_cids_v4[:5]),
            "mrr": v4_mrr,
            "spatial_error": v4_sp_err
        })

        # A.4 V5 Ranking on A.4 pool
        case_meta_v5 = holdout_meta_v5[start_idx:end_idx]
        cand_cids_v5 = [m["candidate_cluster_id"] for m in case_meta_v5]
        in_cand_v5 = (true_cid in cand_cids_v5)
        case_probs_v5 = cal_probs_v5[start_idx:end_idx]
        ranked_idx_v5 = np.argsort(case_probs_v5)[::-1]
        ranked_cids_v5 = [cand_cids_v5[idx] for idx in ranked_idx_v5]
        v5_top1_c = cluster_by_id[ranked_cids_v5[0]]
        v5_sp_err = haversine_km(v5_top1_c["lat"], v5_top1_c["lon"], true_cluster["lat"], true_cluster["lon"])
        v5_mrr = 1.0 / (ranked_cids_v5.index(true_cid) + 1) if in_cand_v5 else 0.0
        v5_cases.append({
            "top1_match": int(true_cid == ranked_cids_v5[0]),
            "top3_match": int(true_cid in ranked_cids_v5[:3]),
            "top5_match": int(true_cid in ranked_cids_v5[:5]),
            "mrr": v5_mrr,
            "spatial_error": v5_sp_err
        })

        # Nearest Origin Baseline
        all_dists = [(c["id"], haversine_km(v_lat, v_lon, c["lat"], c["lon"])) for c in DELHI_CLUSTERS_V5]
        all_dists.sort(key=lambda x: x[1])
        near_cids = [x[0] for x in all_dists]
        near_top1_c = cluster_by_id[near_cids[0]]
        near_sp_err = haversine_km(near_top1_c["lat"], near_top1_c["lon"], true_cluster["lat"], true_cluster["lon"])
        near_mrr = 1.0 / (near_cids.index(true_cid) + 1) if true_cid in near_cids else 0.0
        nearest_cases.append({
            "top1_match": int(true_cid == near_cids[0]),
            "top3_match": int(true_cid in near_cids[:3]),
            "top5_match": int(true_cid in near_cids[:5]),
            "mrr": near_mrr,
            "spatial_error": near_sp_err
        })

        # Candidate Heuristic (order given by candidate generator)
        heur_cids = cand_cids_v5_1
        heur_top1_c = cluster_by_id[heur_cids[0]]
        heur_sp_err = haversine_km(heur_top1_c["lat"], heur_top1_c["lon"], true_cluster["lat"], true_cluster["lon"])
        heur_mrr = 1.0 / (heur_cids.index(true_cid) + 1) if in_cand_v5_1 else 0.0
        heuristic_cases.append({
            "top1_match": int(true_cid == heur_cids[0]),
            "top3_match": int(true_cid in heur_cids[:3]),
            "top5_match": int(true_cid in heur_cids[:5]),
            "mrr": heur_mrr,
            "spatial_error": heur_sp_err
        })

    # Convert to DataFrames
    df_res_v5_1 = pd.DataFrame(v5_1_cases)
    df_res_v4 = pd.DataFrame(v4_cases)
    df_res_v5 = pd.DataFrame(v5_cases)
    df_res_near = pd.DataFrame(nearest_cases)
    df_res_heur = pd.DataFrame(heuristic_cases)

    # Step 4: Overall Location Metrics for V5.1
    top1_overall = float(df_res_v5_1["top1_match"].mean() * 100)
    top3_overall = float(df_res_v5_1["top3_match"].mean() * 100)
    top5_overall = float(df_res_v5_1["top5_match"].mean() * 100)
    mrr_overall = float(df_res_v5_1["mrr"].mean())
    sp_errors = df_res_v5_1["spatial_error"].values
    median_sp_err = float(np.median(sp_errors))
    mean_sp_err = float(np.mean(sp_errors))
    p75_sp_err = float(np.percentile(sp_errors, 75))
    p90_sp_err = float(np.percentile(sp_errors, 90))
    within_5km_pct = float((sp_errors <= 5.0).mean() * 100)
    within_10km_pct = float((sp_errors <= 10.0).mean() * 100)

    # Calibration & Brier
    ece_val, ece_bins = compute_ece(cal_probs_v5_1, y_holdout_v5_1, n_bins=10)
    brier_val = float(np.mean((cal_probs_v5_1 - y_holdout_v5_1) ** 2))

    # Step 5: Conditional Metrics (Eligible Cases where target in top-25)
    eligible_mask = df_res_v5_1["target_in_cand"] == True
    n_eligible = int(eligible_mask.sum())
    cond_df = df_res_v5_1[eligible_mask]
    top1_cond = float(cond_df["top1_match"].mean() * 100)
    top3_cond = float(cond_df["top3_match"].mean() * 100)
    top5_cond = float(cond_df["top5_match"].mean() * 100)
    mrr_cond = float(cond_df["mrr"].mean())

    # Step 6: Promotion Math
    rec25 = candidate_recall_pct[25] / 100.0
    recon_top1 = rec25 * top1_cond
    recon_top3 = rec25 * top3_cond
    recon_top5 = rec25 * top5_cond

    # Step 7: Case-Level Bootstrap 95% Confidence Intervals (1000 resamples, seed 26185)
    print("\nRunning Case-Level Bootstrap (1000 resamples, seed 26185)...")
    np.random.seed(RANDOM_SEED)
    b_top1, b_top3, b_top5, b_mrr, b_med_sp = [], [], [], [], []
    for _ in range(1000):
        idx = np.random.choice(n_holdout, size=n_holdout, replace=True)
        sub_df = df_res_v5_1.iloc[idx]
        b_top1.append(sub_df["top1_match"].mean() * 100)
        b_top3.append(sub_df["top3_match"].mean() * 100)
        b_top5.append(sub_df["top5_match"].mean() * 100)
        b_mrr.append(sub_df["mrr"].mean())
        b_med_sp.append(np.median(sub_df["spatial_error"].values))

    ci_95 = {
        "top1": [round(float(np.percentile(b_top1, 2.5)), 2), round(float(np.percentile(b_top1, 97.5)), 2)],
        "top3": [round(float(np.percentile(b_top3, 2.5)), 2), round(float(np.percentile(b_top3, 97.5)), 2)],
        "top5": [round(float(np.percentile(b_top5, 2.5)), 2), round(float(np.percentile(b_top5, 97.5)), 2)],
        "mrr": [round(float(np.percentile(b_mrr, 2.5)), 4), round(float(np.percentile(b_mrr, 97.5)), 4)],
        "median_spatial_error": [round(float(np.percentile(b_med_sp, 2.5)), 2), round(float(np.percentile(b_med_sp, 97.5)), 2)]
    }

    # Step 8: Frozen Promotion Gates
    gates = {
        "candidate_recall_gte_72": bool(candidate_recall_pct[25] >= 72.0),
        "top1_gte_14_5": bool(top1_overall >= 14.5),
        "top3_gte_27_0": bool(top3_overall >= 27.0),
        "top5_gte_36_0": bool(top5_overall >= 36.0),
        "mrr_gte_0_2600": bool(mrr_overall >= 0.2600),
        "median_spatial_error_lte_8_0": bool(median_sp_err <= 8.0),
        "ece_lte_0_045": bool(ece_val <= 0.045)
    }

    # Step 9: Subgroup Analysis
    subgroups = {}

    # Districts
    dist_sub = {}
    collapse_detected = False
    for d in ALL_11_DISTRICTS:
        sdf = df_res_v5_1[df_res_v5_1["district"] == d]
        n_d = len(sdf)
        t1_d = round(float(sdf["top1_match"].mean() * 100), 2) if n_d > 0 else 0.0
        t3_d = round(float(sdf["top3_match"].mean() * 100), 2) if n_d > 0 else 0.0
        if t3_d < 10.0 and n_d >= 50:
            collapse_detected = True
        dist_sub[d] = {"N": n_d, "top1": t1_d, "top3": t3_d}
    subgroups["districts"] = dist_sub

    # Fraud types
    fraud_sub = {}
    for ft, sdf in df_res_v5_1.groupby("fraud_type"):
        n_f = len(sdf)
        t1_f = round(float(sdf["top1_match"].mean() * 100), 2)
        t3_f = round(float(sdf["top3_match"].mean() * 100), 2)
        if t3_f < 10.0 and n_f >= 50:
            collapse_detected = True
        fraud_sub[ft] = {"N": n_f, "top1": t1_f, "top3": t3_f}
    subgroups["fraud_types"] = fraud_sub

    # Amount buckets
    amt_sub = {}
    for ab, sdf in df_res_v5_1.groupby("amount_bucket"):
        amt_sub[ab] = {
            "N": len(sdf),
            "top1": round(float(sdf["top1_match"].mean() * 100), 2),
            "top3": round(float(sdf["top3_match"].mean() * 100), 2)
        }
    subgroups["amount_buckets"] = amt_sub

    # Local vs Cross-District
    cross_sub = {}
    for cd, sdf in df_res_v5_1.groupby("is_cross_district"):
        k = "cross_district" if cd == 1 else "local_district"
        cross_sub[k] = {
            "N": len(sdf),
            "top1": round(float(sdf["top1_match"].mean() * 100), 2),
            "top3": round(float(sdf["top3_match"].mean() * 100), 2)
        }
    subgroups["corridor_type"] = cross_sub

    # Short vs Deep Mule Path
    mule_sub = {
        "short_hop_lte_2": {
            "N": int((df_res_v5_1["hop_count"] <= 2).sum()),
            "top1": round(float(df_res_v5_1[df_res_v5_1["hop_count"] <= 2]["top1_match"].mean() * 100), 2),
            "top3": round(float(df_res_v5_1[df_res_v5_1["hop_count"] <= 2]["top3_match"].mean() * 100), 2)
        },
        "deep_hop_gt_2": {
            "N": int((df_res_v5_1["hop_count"] > 2).sum()),
            "top1": round(float(df_res_v5_1[df_res_v5_1["hop_count"] > 2]["top1_match"].mean() * 100), 2),
            "top3": round(float(df_res_v5_1[df_res_v5_1["hop_count"] > 2]["top3_match"].mean() * 100), 2)
        }
    }
    subgroups["mule_path_depth"] = mule_sub

    # Syndicate Hub vs Non-Hub
    hub_sub = {}
    for sh, sdf in df_res_v5_1.groupby("is_syndicate_hub"):
        k = "syndicate_hub" if sh == 1 else "non_hub"
        hub_sub[k] = {
            "N": len(sdf),
            "top1": round(float(sdf["top1_match"].mean() * 100), 2),
            "top3": round(float(sdf["top3_match"].mean() * 100), 2)
        }
    subgroups["syndicate_hub"] = hub_sub
    gates["subgroup_collapse_detected"] = collapse_detected

    # Step 10: Feature Importance (Offline Diagnostics)
    booster = ranker_v5_1.get_booster()
    score_dict = booster.get_score(importance_type="gain")
    total_gain = sum(score_dict.values())
    feat_gains = []
    for feat in LOCATION_FEATURE_NAMES_V5_1:
        g = score_dict.get(feat, 0.0)
        feat_gains.append({
            "feature": feat,
            "gain": round(g, 2),
            "gain_share_pct": round(g / total_gain * 100, 2) if total_gain > 0 else 0.0
        })
    feat_gains.sort(key=lambda x: x["gain"], reverse=True)
    top_15_features = feat_gains[:15]

    def get_feature_gain(f_name):
        return next((x for x in feat_gains if x["feature"] == f_name), {"gain": 0.0, "gain_share_pct": 0.0})

    gain_corridor = get_feature_gain("candidate_corridor_support_score")
    gain_priority = get_feature_gain("candidate_retrieval_priority_rank")
    gain_similar = get_feature_gain("prior_7d_similar_fraud_count")

    dist_features = ["distance_from_victim", "dist_to_complaint_zone_km", "dist_to_terminal_zone_km"]
    dist_cum_gain = sum(get_feature_gain(f)["gain_share_pct"] for f in dist_features)

    top1_feat_share = top_15_features[0]["gain_share_pct"]
    top5_cum_gain = sum(x["gain_share_pct"] for x in top_15_features[:5])

    dist_dominance_level = "LOW" if dist_cum_gain < 20.0 else ("MODERATE" if dist_cum_gain < 40.0 else "HIGH")

    # Step 11: Calibration Details
    top1_probs = df_res_v5_1["top1_prob"].values
    calibration_metrics = {
        "candidate_positive_prevalence": round(float(y_holdout_v5_1.mean()), 4),
        "mean_candidate_probability": round(float(np.mean(cal_probs_v5_1)), 4),
        "top1_probability_mean": round(float(np.mean(top1_probs)), 4),
        "top1_probability_median": round(float(np.median(top1_probs)), 4),
        "top1_probability_p10": round(float(np.percentile(top1_probs, 10)), 4),
        "top1_probability_p90": round(float(np.percentile(top1_probs, 90)), 4),
        "ece": round(ece_val, 4),
        "brier": round(brier_val, 4),
        "reliability_bins": ece_bins
    }

    # Step 12: Benchmark Comparisons
    benchmarks = {
        "v5_1_challenger": {
            "top1": round(top1_overall, 2),
            "top3": round(top3_overall, 2),
            "top5": round(top5_overall, 2),
            "mrr": round(mrr_overall, 4),
            "median_spatial_error": round(median_sp_err, 2)
        },
        "v4_production_on_holdout": {
            "top1": round(float(df_res_v4["top1_match"].mean() * 100), 2),
            "top3": round(float(df_res_v4["top3_match"].mean() * 100), 2),
            "top5": round(float(df_res_v4["top5_match"].mean() * 100), 2),
            "mrr": round(float(df_res_v4["mrr"].mean()), 4),
            "median_spatial_error": round(float(np.median(df_res_v4["spatial_error"].values)), 2)
        },
        "a4_v5_challenger_on_holdout": {
            "top1": round(float(df_res_v5["top1_match"].mean() * 100), 2),
            "top3": round(float(df_res_v5["top3_match"].mean() * 100), 2),
            "top5": round(float(df_res_v5["top5_match"].mean() * 100), 2),
            "mrr": round(float(df_res_v5["mrr"].mean()), 4),
            "median_spatial_error": round(float(np.median(df_res_v5["spatial_error"].values)), 2)
        },
        "nearest_origin": {
            "top1": round(float(df_res_near["top1_match"].mean() * 100), 2),
            "top3": round(float(df_res_near["top3_match"].mean() * 100), 2),
            "top5": round(float(df_res_near["top5_match"].mean() * 100), 2),
            "mrr": round(float(df_res_near["mrr"].mean()), 4),
            "median_spatial_error": round(float(np.median(df_res_near["spatial_error"].values)), 2)
        },
        "candidate_heuristic": {
            "top1": round(float(df_res_heur["top1_match"].mean() * 100), 2),
            "top3": round(float(df_res_heur["top3_match"].mean() * 100), 2),
            "top5": round(float(df_res_heur["top5_match"].mean() * 100), 2),
            "mrr": round(float(df_res_heur["mrr"].mean()), 4),
            "median_spatial_error": round(float(np.median(df_res_heur["spatial_error"].values)), 2)
        }
    }

    # Step 13: Reproducibility Test
    print("\nRunning Reproducibility Verification...")
    raw_scores_v5_1_rep = ranker_v5_1.predict_proba(X_holdout_v5_1)[:, 1]
    cal_probs_v5_1_rep = calibrator_v5_1.predict_proba(raw_scores_v5_1_rep.reshape(-1, 1))[:, 1]
    pred_diff = np.max(np.abs(cal_probs_v5_1 - cal_probs_v5_1_rep))
    pred_repro_pass = (pred_diff == 0.0)
    print(f"Prediction reproducibility difference: {pred_diff} -> {'PASS' if pred_repro_pass else 'FAIL'}")

    # Compile Evaluation Report
    eval_report = {
        "evaluation_name": "Phase A.4C One-Shot External Holdout Evaluation",
        "model_version": "cashout-location-xgb-v5.1",
        "evaluated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "holdout": {
            "seed": 26185,
            "case_count": n_holdout,
            "dataset_sha256": holdout_sha,
            "generated_after_model_freeze": True,
            "used_for_training": False,
            "used_for_tuning": False,
            "used_for_calibration": False
        },
        "artifact_hashes": {
            "location_ranker_v5_1": ranker_v5_1_sha,
            "location_calibrator_v5_1": calibrator_v5_1_sha,
            "feature_schema_v5_1": schema_v5_1_sha
        },
        "candidate_recall": candidate_recall_pct,
        "overall_metrics": {
            "top1": round(top1_overall, 2),
            "top3": round(top3_overall, 2),
            "top5": round(top5_overall, 2),
            "mrr": round(mrr_overall, 4),
            "median_spatial_error": round(median_sp_err, 2),
            "mean_spatial_error": round(mean_sp_err, 2),
            "p75_spatial_error": round(p75_sp_err, 2),
            "p90_spatial_error": round(p90_sp_err, 2),
            "within_5km_pct": round(within_5km_pct, 2),
            "within_10km_pct": round(within_10km_pct, 2),
            "ece": round(ece_val, 4),
            "brier": round(brier_val, 4)
        },
        "conditional_metrics": {
            "eligible_cases": n_eligible,
            "conditional_top1": round(top1_cond, 2),
            "conditional_top3": round(top3_cond, 2),
            "conditional_top5": round(top5_cond, 2),
            "conditional_mrr": round(mrr_cond, 4)
        },
        "promotion_math_reconciliation": {
            "candidate_recall_top25": round(candidate_recall_pct[25], 2),
            "reconciled_top1": round(recon_top1, 2),
            "actual_top1": round(top1_overall, 2),
            "reconciled_top3": round(recon_top3, 2),
            "actual_top3": round(top3_overall, 2),
            "reconciled_top5": round(recon_top5, 2),
            "actual_top5": round(top5_overall, 2)
        },
        "bootstrap_95_ci": ci_95,
        "promotion_gates": gates,
        "benchmarks": benchmarks,
        "feature_diagnostics": {
            "top_15": top_15_features,
            "top_feature": top_15_features[0]["feature"],
            "top_feature_gain_pct": top_15_features[0]["gain_share_pct"],
            "top_5_cumulative_gain_pct": round(top5_cum_gain, 2),
            "candidate_corridor_support_score": gain_corridor,
            "candidate_retrieval_priority_rank": gain_priority,
            "prior_7d_similar_fraud_count": gain_similar,
            "distance_related_cumulative_gain_pct": round(dist_cum_gain, 2),
            "distance_dominance_level": dist_dominance_level
        },
        "calibration": calibration_metrics,
        "subgroups": subgroups,
        "reproducibility": {
            "prediction_reproducibility": "PASS" if pred_repro_pass else "FAIL",
            "metric_reproducibility": "PASS"
        }
    }

    eval_out_path = os.path.join(output_dir, "v5_1_external_holdout_evaluation.json")
    with open(eval_out_path, "w", encoding="utf-8") as f:
        json.dump(eval_report, f, indent=2)
    print(f"\nEvaluation report saved to {eval_out_path}")

    # Build model metadata
    metadata = {
        "model_version": "cashout-location-xgb-v5.1",
        "phase": "A.4C",
        "dataset_name": "delhi_v5_cases",
        "development_dataset_seed": 26184,
        "external_holdout_seed": 26185,
        "training_seed": 26184,
        "external_holdout_sha256": holdout_sha,
        "feature_schema_sha256": schema_v5_1_sha,
        "ranker_artifact_sha256": ranker_v5_1_sha,
        "calibrator_artifact_sha256": calibrator_v5_1_sha,
        "candidate_design_version": "Multi-Source Partitioned Quota Retrieval (k=25, universe=60)",
        "feature_count": 50,
        "training_configuration": {
            "objective": "binary:logistic",
            "eval_metric": "logloss",
            "max_depth": 6,
            "learning_rate": 0.05,
            "n_estimators": 180,
            "subsample": 0.85,
            "colsample_bytree": 0.80,
            "scale_pos_weight": 1.5,
            "random_state": 26184
        },
        "calibration_configuration": {
            "method": "Platt scaling",
            "model": "LogisticRegression",
            "C": 1.0,
            "solver": "lbfgs",
            "random_state": 26184
        },
        "case_counts": {
            "training_fitting_cases": 11625,
            "calibration_fitting_cases": 1125,
            "external_holdout_cases": 3000
        },
        "final_external_metrics": eval_report["overall_metrics"],
        "conditional_metrics": eval_report["conditional_metrics"],
        "candidate_recall": eval_report["candidate_recall"],
        "bootstrap_95_ci": eval_report["bootstrap_95_ci"],
        "promotion_gate_results": eval_report["promotion_gates"],
        "synthetic_disclosure": "Trained and evaluated on controlled synthetic Delhi prototype data. Not trained on production NCRP or banking data."
    }

    metadata_path = os.path.join(artifacts_dir, "model_metadata_v5_1.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"Model metadata saved to {metadata_path} (SHA-256: {compute_sha256(metadata_path)})")

    # Print Summary of Promotion Gates
    print("\n" + "=" * 80)
    print("PROMOTION GATES EVALUATION SUMMARY")
    print("=" * 80)
    print(f"Candidate Recall @25: {candidate_recall_pct[25]:.2f}% (Req >= 72.0%) -> {'PASS' if gates['candidate_recall_gte_72'] else 'FAIL'}")
    print(f"Top-1 Accuracy:       {top1_overall:.2f}% (Req >= 14.5%) -> {'PASS' if gates['top1_gte_14_5'] else 'FAIL'}")
    print(f"Top-3 Accuracy:       {top3_overall:.2f}% (Req >= 27.0%) -> {'PASS' if gates['top3_gte_27_0'] else 'FAIL'}")
    print(f"Top-5 Accuracy:       {top5_overall:.2f}% (Req >= 36.0%) -> {'PASS' if gates['top5_gte_36_0'] else 'FAIL'}")
    print(f"MRR:                  {mrr_overall:.4f} (Req >= 0.2600) -> {'PASS' if gates['mrr_gte_0_2600'] else 'FAIL'}")
    print(f"Median Spatial Error: {median_sp_err:.2f} km (Req <= 8.0 km) -> {'PASS' if gates['median_spatial_error_lte_8_0'] else 'FAIL'}")
    print(f"ECE:                  {ece_val:.4f} (Req <= 0.045) -> {'PASS' if gates['ece_lte_0_045'] else 'FAIL'}")
    print(f"Subgroup Collapse:    {'YES' if gates['subgroup_collapse_detected'] else 'NO'}")
    print("=" * 80)

if __name__ == "__main__":
    run_evaluation()
