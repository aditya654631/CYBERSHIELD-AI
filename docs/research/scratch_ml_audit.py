"""
ML Validity Audit Script for CyberShield AI
Calculates exact empirical values required for the 12-section audit:
1. Temporal split timestamps (earliest/latest per split)
2. Natural Candidate Recall on held-out test set (without force-adding ground truth)
3. Entity Overlap (% test mule accounts, beneficiary accounts, clusters seen in train)
4. Label Shuffle Sanity Test (shuffle labels in memory, train XGB, measure Recall@1/3)
5. High-Risk Feature Ablation (drop is_mule_corridor and distance_from_high_risk_account, measure Recall@1/3)
6. Brier Score & Probability Calibration Analysis (positive prevalence, mean prob for pos/neg, calibration curve)
7. Time Model verification
"""

import os
import sys
import math
import random
import numpy as np
import pandas as pd
from datetime import datetime
from xgboost import XGBClassifier, XGBRegressor

from ml.geo.candidate_generator import CandidateLocationGenerator, haversine_km
from ml.features.feature_pipeline import FeaturePipeline, FEATURE_COLUMNS_LOCATION, FEATURE_COLUMNS_TIME

RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

def run_audit():
    print("=" * 70)
    print("STARTING ML VALIDITY EMPIRICAL AUDIT")
    print("=" * 70)

    # 1. Load Data
    data_dir = "ml/data"
    clusters_df = pd.read_csv(os.path.join(data_dir, "clusters.csv.gz"), compression="gzip")
    accounts_df = pd.read_csv(os.path.join(data_dir, "accounts.csv.gz"), compression="gzip")
    complaints_df = pd.read_csv(os.path.join(data_dir, "complaints.csv.gz"), compression="gzip")
    transactions_df = pd.read_csv(os.path.join(data_dir, "transactions.csv.gz"), compression="gzip")
    withdrawals_df = pd.read_csv(os.path.join(data_dir, "withdrawals.csv.gz"), compression="gzip")

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
    fp = FeaturePipeline()

    # Sort chronologically by incident_timestamp
    complaints_df = complaints_df.sort_values(by="incident_timestamp").reset_index(drop=True)
    total_c = len(complaints_df)

    train_n = 14000
    val_n = 3000
    test_n = 3000

    train_df = complaints_df.iloc[:train_n]
    val_df = complaints_df.iloc[train_n : train_n + val_n]
    test_df = complaints_df.iloc[train_n + val_n : train_n + val_n + test_n]

    # SECTION 3: TEMPORAL SPLIT TIMESTAMPS
    print("\n--- SECTION 3: TEMPORAL SPLIT BOUNDARIES ---")
    train_min = train_df["incident_timestamp"].min()
    train_max = train_df["incident_timestamp"].max()
    val_min = val_df["incident_timestamp"].min()
    val_max = val_df["incident_timestamp"].max()
    test_min = test_df["incident_timestamp"].min()
    test_max = test_df["incident_timestamp"].max()

    print(f"Train Earliest:      {train_min} | Latest: {train_max}")
    print(f"Validation Earliest: {val_min} | Latest: {val_max}")
    print(f"Test Earliest:       {test_min} | Latest: {test_max}")

    t_v_strict = train_max <= val_min
    v_t_strict = val_max <= test_min
    print(f"max(train) <= min(val): {t_v_strict} (Diff: {val_min} vs {train_max})")
    print(f"max(val) <= min(test):  {v_t_strict} (Diff: {test_min} vs {val_max})")

    # SECTION 4: ENTITY LEAKAGE
    print("\n--- SECTION 4: ENTITY OVERLAP ANALYSIS ---")
    train_mules = set(train_df["beneficiary_mule_id"].unique())
    test_mules = set(test_df["beneficiary_mule_id"].unique())
    mule_overlap = test_mules.intersection(train_mules)
    pct_mule_overlap = (len(mule_overlap) / len(test_mules)) * 100

    train_clusters = set(train_df["target_cluster_id"].unique())
    test_clusters = set(test_df["target_cluster_id"].unique())
    cluster_overlap = test_clusters.intersection(train_clusters)
    pct_cluster_overlap = (len(cluster_overlap) / len(test_clusters)) * 100

    print(f"Unique mule accounts in test: {len(test_mules)}")
    print(f"Test mule accounts previously seen in train: {len(mule_overlap)} ({pct_mule_overlap:.1f}%)")
    print(f"Unique target clusters in test: {len(test_clusters)}")
    print(f"Test target clusters previously seen in train: {len(cluster_overlap)} ({pct_cluster_overlap:.1f}%)")

    # SECTION 2: CANDIDATE GENERATION AUDIT & NATURAL CANDIDATE RECALL
    print("\n--- SECTION 2: CANDIDATE GENERATION & NATURAL RECALL ---")
    natural_hits = 0
    test_complaints = test_df.to_dict(orient="records")

    for comp in test_complaints:
        target_cl_id = int(comp["target_cluster_id"])
        mule_id = int(comp.get("beneficiary_mule_id", 0))
        mule_cl_id = account_to_cluster.get(mule_id)

        # Generate naturally without force-adding
        cands = cand_gen.generate_candidates_for_complaint(
            comp,
            beneficiary_mule_cluster_id=mule_cl_id,
            top_k=25
        )
        c_ids = [c["cluster_id"] for c in cands]
        if target_cl_id in c_ids:
            natural_hits += 1

    cand_recall = (natural_hits / len(test_complaints)) * 100
    print(f"Natural Candidate Recall on Test (without force-add): {cand_recall:.2f}% ({natural_hits}/{len(test_complaints)})")

    # SECTION 6 & 7: BUILD MATRICES FOR SANITY SHUFFLE & ABLATION
    print("\n--- PREPARING DATA FOR SHUFFLE & ABLATION EXPERIMENTS ---")
    train_complaints = train_df.to_dict(orient="records")
    val_complaints = val_df.to_dict(orient="records")

    def extract_dataset(complaints_subset, force_add=True):
        X_loc_list = []
        y_loc_list = []
        meta_list = []

        for comp in complaints_subset:
            target_cl_id = int(comp["target_cluster_id"])
            mule_id = int(comp.get("beneficiary_mule_id", 0))
            mule_cl_id = account_to_cluster.get(mule_id)

            cands = cand_gen.generate_candidates_for_complaint(
                comp,
                beneficiary_mule_cluster_id=mule_cl_id,
                top_k=25
            )
            cand_ids = [c["cluster_id"] for c in cands]
            if force_add and target_cl_id not in cand_ids and target_cl_id in cand_gen.cluster_by_id:
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
                    "historical_cashout_count": t_cl.get("historical_cashout_count", 500),
                    "historical_cashout_amount": t_cl.get("historical_cashout_amount", 25000000.0),
                    "reasoning": "Corridor node match",
                    "is_mule_corridor": 1 if target_cl_id == mule_cl_id else 0,
                    "distance_from_victim_km": round(haversine_km(comp["victim_lat"], comp["victim_lon"], t_cl["lat"], t_cl["lon"]), 1)
                })

            X_l, _, _, _ = fp.build_candidate_matrix(comp, cands)
            lbls = [1 if c["cluster_id"] == target_cl_id else 0 for c in cands]
            X_loc_list.append(X_l)
            y_loc_list.extend(lbls)
            meta_list.append({
                "target_cluster_id": target_cl_id,
                "candidates": cands,
                "n_cands": len(cands)
            })

        return np.vstack(X_loc_list), np.array(y_loc_list, dtype=np.int32), meta_list

    X_train, y_train, _ = extract_dataset(train_complaints, force_add=True)
    X_val, y_val, _ = extract_dataset(val_complaints, force_add=False)
    X_test, y_test, test_meta = extract_dataset(test_complaints, force_add=False)

    def evaluate_ranking(probs, meta):
        r1_hits = 0
        r3_hits = 0
        idx = 0
        for item in meta:
            n = item["n_cands"]
            p_slice = probs[idx : idx + n]
            cands = item["candidates"]
            target = item["target_cluster_id"]

            ranked = sorted(zip(p_slice, cands), key=lambda x: x[0], reverse=True)
            top1_id = ranked[0][1]["cluster_id"]
            top3_ids = [c[1]["cluster_id"] for c in ranked[:3]]

            if top1_id == target:
                r1_hits += 1
            if target in top3_ids:
                r3_hits += 1
            idx += n

        total = len(meta)
        return (r1_hits / total) * 100, (r3_hits / total) * 100

    # BASELINE MODEL EVALUATION (ON NATURAL TEST SET WITHOUT FORCE-ADD)
    print("\n--- EVALUATING ORIGINAL MODEL ON NATURAL TEST SET (NO FORCE-ADD) ---")
    pos_weight = float((len(y_train) - sum(y_train)) / max(1, sum(y_train)))
    orig_clf = XGBClassifier(
        n_estimators=120, max_depth=5, learning_rate=0.08,
        scale_pos_weight=pos_weight * 0.5, random_state=RANDOM_SEED,
        eval_metric="logloss", n_jobs=-1
    )
    orig_clf.fit(X_train, y_train, verbose=False)
    orig_probs = orig_clf.predict_proba(X_test)[:, 1]
    orig_r1, orig_r3 = evaluate_ranking(orig_probs, test_meta)
    print(f"Original Model (Natural Test Set): Recall@1 = {orig_r1:.2f}%, Recall@3 = {orig_r3:.2f}%")

    # SECTION 6: LABEL SHUFFLE SANITY TEST
    print("\n--- SECTION 6: LABEL SHUFFLE SANITY TEST ---")
    y_train_shuffled = y_train.copy()
    np.random.shuffle(y_train_shuffled)
    shuffle_clf = XGBClassifier(
        n_estimators=120, max_depth=5, learning_rate=0.08,
        scale_pos_weight=pos_weight * 0.5, random_state=RANDOM_SEED,
        eval_metric="logloss", n_jobs=-1
    )
    shuffle_clf.fit(X_train, y_train_shuffled, verbose=False)
    shuffle_probs = shuffle_clf.predict_proba(X_test)[:, 1]
    shuf_r1, shuf_r3 = evaluate_ranking(shuffle_probs, test_meta)
    print(f"Shuffled-Label Model: Recall@1 = {shuf_r1:.2f}%, Recall@3 = {shuf_r3:.2f}%")
    print(f"Expected Random Baseline (1/25 = 4.0% Top-1, 3/25 = 12.0% Top-3)")

    # SECTION 7: HIGH-RISK FEATURE ABLATION
    print("\n--- SECTION 7: HIGH-RISK FEATURE ABLATION TEST ---")
    # Drop "is_mule_corridor" and "distance_from_high_risk_account"
    feature_names = list(FEATURE_COLUMNS_LOCATION)
    drop_cols = ["is_mule_corridor", "distance_from_high_risk_account"]
    keep_indices = [i for i, f in enumerate(feature_names) if f not in drop_cols]
    print(f"Features before ablation: {len(feature_names)}, after dropping {drop_cols}: {len(keep_indices)}")

    X_train_abl = X_train[:, keep_indices]
    X_test_abl = X_test[:, keep_indices]

    abl_clf = XGBClassifier(
        n_estimators=120, max_depth=5, learning_rate=0.08,
        scale_pos_weight=pos_weight * 0.5, random_state=RANDOM_SEED,
        eval_metric="logloss", n_jobs=-1
    )
    abl_clf.fit(X_train_abl, y_train, verbose=False)
    abl_probs = abl_clf.predict_proba(X_test_abl)[:, 1]
    abl_r1, abl_r3 = evaluate_ranking(abl_probs, test_meta)

    print(f"Original Recall@1: {orig_r1:.2f}% | Ablated Recall@1: {abl_r1:.2f}%")
    print(f"Original Recall@3: {orig_r3:.2f}% | Ablated Recall@3: {abl_r3:.2f}%")

    # SECTION 9: PROBABILITY CALIBRATION & BRIER SCORE
    print("\n--- SECTION 9: PROBABILITY CALIBRATION & BRIER AUDIT ---")
    pos_mask = (y_test == 1)
    neg_mask = (y_test == 0)
    pos_prevalence = float(np.mean(y_test))
    mean_prob_pos = float(np.mean(orig_probs[pos_mask]))
    mean_prob_neg = float(np.mean(orig_probs[neg_mask]))
    brier_score = float(np.mean((orig_probs - y_test) ** 2))

    print(f"Positive candidate prevalence in test: {pos_prevalence:.4f} ({pos_prevalence*100:.2f}%)")
    print(f"Mean predicted probability for POSITIVES (Ground Truth): {mean_prob_pos:.4f}")
    print(f"Mean predicted probability for NEGATIVES (Distractors):  {mean_prob_neg:.4f}")
    print(f"Calculated Brier Score: {brier_score:.4f}")

    # Calibration Bins
    bins = [0.0, 0.1, 0.2, 0.4, 0.6, 0.8, 1.0]
    print("Calibration Bins (Confidence vs Observed Positive Rate):")
    for i in range(len(bins) - 1):
        b_low, b_high = bins[i], bins[i+1]
        in_bin = (orig_probs >= b_low) & (orig_probs < b_high)
        n_in_bin = np.sum(in_bin)
        if n_in_bin > 0:
            obs_rate = np.mean(y_test[in_bin])
            avg_conf = np.mean(orig_probs[in_bin])
            print(f"  Bin [{b_low:.1f}, {b_high:.1f}): Count={n_in_bin:5d} | Avg Pred Prob={avg_conf:.3f} | Observed Fraction={obs_rate:.3f}")

if __name__ == "__main__":
    run_audit()
