"""
CyberShield AI — Phase A.4D Ranker Architecture & Feature Ablation Study
Compares Pointwise (binary:logistic) vs Listwise (rank:ndcg) vs Pairwise (rank:pairwise).
Evaluates candidate priority ablations and relative intra-complaint candidate features.
USES DEVELOPMENT DATA ONLY (TRAIN for fitting, VALIDATION_TUNE for evaluation).
CONSUMED BENCHMARKS (A.4 Test, Holdout 26185) ARE STRICTLY UNTOUCHED.
"""

import os
import sys
import time
import json
import joblib
import numpy as np
import pandas as pd
from xgboost import XGBClassifier, XGBRanker

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from ml.data.generate_delhi_v5_dataset import DELHI_CLUSTERS_V5, haversine_km
from ml.features.build_v5_1_candidate_features import V51FeatureBuilder, LOCATION_FEATURE_NAMES_V5_1

RANDOM_SEED = 26184

def compute_metrics(y_true_cases, pred_scores, n_cases, top_k=25):
    """Computes Top-1, Top-3, Top-5, MRR overall and conditional on target present."""
    top1_hits = 0
    top3_hits = 0
    top5_hits = 0
    mrr_sum = 0.0

    cond_top1_hits = 0
    cond_top3_hits = 0
    cond_top5_hits = 0
    cond_mrr_sum = 0.0
    eligible_count = 0

    spatial_errors = []
    cluster_by_id = {c["id"]: c for c in DELHI_CLUSTERS_V5}

    for i in range(n_cases):
        s_idx = i * top_k
        e_idx = s_idx + top_k
        case_scores = pred_scores[s_idx:e_idx]
        case_labels = y_true_cases[s_idx:e_idx]

        has_target = (case_labels.sum() > 0)
        ranked_idx = np.argsort(case_scores)[::-1]

        if has_target:
            eligible_count += 1
            target_pos = np.where(case_labels[ranked_idx] == 1)[0][0] + 1

            top1_hits += int(target_pos == 1)
            top3_hits += int(target_pos <= 3)
            top5_hits += int(target_pos <= 5)
            mrr_val = 1.0 / target_pos
            mrr_sum += mrr_val

            cond_top1_hits += int(target_pos == 1)
            cond_top3_hits += int(target_pos <= 3)
            cond_top5_hits += int(target_pos <= 5)
            cond_mrr_sum += mrr_val
        else:
            # target not in candidates
            pass

    return {
        "candidate_recall": round(eligible_count / n_cases * 100, 2),
        "overall_top1": round(top1_hits / n_cases * 100, 2),
        "overall_top3": round(top3_hits / n_cases * 100, 2),
        "overall_top5": round(top5_hits / n_cases * 100, 2),
        "overall_mrr": round(mrr_sum / n_cases, 4),
        "eligible_cases": eligible_count,
        "cond_top1": round(cond_top1_hits / eligible_count * 100, 2) if eligible_count > 0 else 0.0,
        "cond_top3": round(cond_top3_hits / eligible_count * 100, 2) if eligible_count > 0 else 0.0,
        "cond_top5": round(cond_top5_hits / eligible_count * 100, 2) if eligible_count > 0 else 0.0,
        "cond_mrr": round(cond_mrr_sum / eligible_count, 4) if eligible_count > 0 else 0.0
    }

def add_relative_features(X_df, n_cases, top_k=25):
    """
    Computes intra-complaint relative ranking features across the 25 candidates of each case.
    Constructed strictly from prediction-time candidate features (no future, no target).
    """
    df = X_df.copy()

    # Pre-allocate relative feature arrays
    rel_dist_ranks = np.zeros(len(df), dtype=np.float32)
    rel_corridor_ranks = np.zeros(len(df), dtype=np.float32)
    rel_atm_ranks = np.zeros(len(df), dtype=np.float32)
    rel_fraud_aff_ranks = np.zeros(len(df), dtype=np.float32)
    rel_term_dist_ranks = np.zeros(len(df), dtype=np.float32)

    dist_vals = df["distance_from_victim"].values
    corridor_vals = df["candidate_corridor_support_score"].values
    atm_vals = df["atm_density"].values
    fraud_aff_vals = df["fraud_type_cluster_frequency"].values
    term_dist_vals = df["dist_to_terminal_zone_km"].values

    for i in range(n_cases):
        s = i * top_k
        e = s + top_k

        # Ascending rank for distance (closest gets rank 1)
        rel_dist_ranks[s:e] = np.argsort(np.argsort(dist_vals[s:e])) + 1
        rel_term_dist_ranks[s:e] = np.argsort(np.argsort(term_dist_vals[s:e])) + 1

        # Descending rank for support, atm density, fraud affinity (highest gets rank 1)
        rel_corridor_ranks[s:e] = np.argsort(np.argsort(-corridor_vals[s:e])) + 1
        rel_atm_ranks[s:e] = np.argsort(np.argsort(-atm_vals[s:e])) + 1
        rel_fraud_aff_ranks[s:e] = np.argsort(np.argsort(-fraud_aff_vals[s:e])) + 1

    df["candidate_victim_distance_rank"] = rel_dist_ranks
    df["candidate_terminal_distance_rank"] = rel_term_dist_ranks
    df["candidate_corridor_support_rank"] = rel_corridor_ranks
    df["candidate_atm_density_rank"] = rel_atm_ranks
    df["candidate_fraud_affinity_rank"] = rel_fraud_aff_ranks

    return df

def run_ablation_study():
    print("=" * 80)
    print("PHASE A.4D: RANKER ARCHITECTURE & FEATURE ABLATION ON DEVELOPMENT DATA")
    print("=" * 80)

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    dev_data_path = os.path.join(base_dir, "ml", "data", "delhi_v5_cases.csv.gz")
    df_dev = pd.read_csv(dev_data_path)

    train_cases = df_dev[df_dev["split"] == "train"].reset_index(drop=True)
    val_cases = df_dev[df_dev["split"] == "validation"].reset_index(drop=True)

    n_val_tune = len(val_cases) // 2
    val_tune_cases = val_cases.iloc[:n_val_tune].reset_index(drop=True)
    val_cal_cases = val_cases.iloc[n_val_tune:].reset_index(drop=True)

    print(f"Development cases:")
    print(f"  TRAIN cases:            {len(train_cases)}")
    print(f"  VALIDATION_TUNE cases:  {len(val_tune_cases)}")
    print(f"  VALIDATION_CAL cases:   {len(val_cal_cases)}")

    fb = V51FeatureBuilder(clusters=DELHI_CLUSTERS_V5)

    print("\nBuilding training candidate matrix (top_k=25)...")
    X_train_base, y_train, _ = fb.build_candidate_matrices(train_cases, top_k=25)
    print("\nBuilding val tune candidate matrix (top_k=25)...")
    X_val_base, y_val, _ = fb.build_candidate_matrices(val_tune_cases, top_k=25, historical_cases=train_cases)

    n_train_cases = len(train_cases)
    n_val_cases = len(val_tune_cases)
    train_groups = [25] * n_train_cases
    val_groups = [25] * n_val_cases

    # Compute relative features
    print("\nComputing intra-complaint relative features...")
    X_train_rel = add_relative_features(X_train_base, n_train_cases, top_k=25)
    X_val_rel = add_relative_features(X_val_base, n_val_cases, top_k=25)

    # Feature sets to ablate
    feature_sets = {
        "base_v5_1": list(LOCATION_FEATURE_NAMES_V5_1),
        "no_priority_rank": [f for f in LOCATION_FEATURE_NAMES_V5_1 if f != "candidate_retrieval_priority_rank"],
        "with_relative_ranks": list(X_train_rel.columns),
        "v5_2_candidate_contract": [
            f for f in X_train_rel.columns
            if f != "candidate_retrieval_priority_rank"
        ]
    }

    # Architectures to compare (controlled, <= 12 configurations)
    configs = [
        # 1. Pointwise baseline (binary:logistic) on base V5.1 features
        {"id": "CFG_01", "arch": "XGBClassifier", "obj": "binary:logistic", "fset": "base_v5_1", "max_depth": 6, "lr": 0.05, "n_est": 180},

        # 2. Pointwise without priority rank
        {"id": "CFG_02", "arch": "XGBClassifier", "obj": "binary:logistic", "fset": "no_priority_rank", "max_depth": 6, "lr": 0.05, "n_est": 180},

        # 3. Pointwise with relative rank features
        {"id": "CFG_03", "arch": "XGBClassifier", "obj": "binary:logistic", "fset": "v5_2_candidate_contract", "max_depth": 6, "lr": 0.05, "n_est": 180},

        # 4. XGBRanker rank:ndcg on base features
        {"id": "CFG_04", "arch": "XGBRanker", "obj": "rank:ndcg", "fset": "base_v5_1", "max_depth": 5, "lr": 0.05, "n_est": 180},

        # 5. XGBRanker rank:ndcg without priority rank
        {"id": "CFG_05", "arch": "XGBRanker", "obj": "rank:ndcg", "fset": "no_priority_rank", "max_depth": 5, "lr": 0.05, "n_est": 180},

        # 6. XGBRanker rank:ndcg with relative rank features (depth 5)
        {"id": "CFG_06", "arch": "XGBRanker", "obj": "rank:ndcg", "fset": "v5_2_candidate_contract", "max_depth": 5, "lr": 0.05, "n_est": 180},

        # 7. XGBRanker rank:ndcg with relative rank features (depth 6)
        {"id": "CFG_07", "arch": "XGBRanker", "obj": "rank:ndcg", "fset": "v5_2_candidate_contract", "max_depth": 6, "lr": 0.05, "n_est": 180},

        # 8. XGBRanker rank:ndcg with lr=0.03, n_est=250
        {"id": "CFG_08", "arch": "XGBRanker", "obj": "rank:ndcg", "fset": "v5_2_candidate_contract", "max_depth": 5, "lr": 0.03, "n_est": 250},

        # 9. XGBRanker rank:pairwise on base features
        {"id": "CFG_09", "arch": "XGBRanker", "obj": "rank:pairwise", "fset": "base_v5_1", "max_depth": 5, "lr": 0.05, "n_est": 180},

        # 10. XGBRanker rank:pairwise with relative features
        {"id": "CFG_10", "arch": "XGBRanker", "obj": "rank:pairwise", "fset": "v5_2_candidate_contract", "max_depth": 5, "lr": 0.05, "n_est": 180},

        # 11. XGBClassifier with relative features + depth 5 + lr 0.03
        {"id": "CFG_11", "arch": "XGBClassifier", "obj": "binary:logistic", "fset": "v5_2_candidate_contract", "max_depth": 5, "lr": 0.03, "n_est": 250}
    ]

    results = []
    print(f"\nRunning {len(configs)} controlled configurations on VALIDATION_TUNE...")

    for cfg in configs:
        f_cols = feature_sets[cfg["fset"]]
        X_tr = X_train_rel[f_cols]
        X_va = X_val_rel[f_cols]

        t0 = time.time()
        if cfg["arch"] == "XGBClassifier":
            model = XGBClassifier(
                objective=cfg["obj"],
                eval_metric="logloss",
                max_depth=cfg["max_depth"],
                learning_rate=cfg["lr"],
                n_estimators=cfg["n_est"],
                subsample=0.85,
                colsample_bytree=0.80,
                scale_pos_weight=1.5,
                random_state=RANDOM_SEED,
                tree_method="hist"
            )
            model.fit(X_tr, y_train, verbose=False)
            preds = model.predict_proba(X_va)[:, 1]
        else:
            model = XGBRanker(
                objective=cfg["obj"],
                eval_metric="ndcg@5",
                max_depth=cfg["max_depth"],
                learning_rate=cfg["lr"],
                n_estimators=cfg["n_est"],
                subsample=0.85,
                colsample_bytree=0.80,
                random_state=RANDOM_SEED,
                tree_method="hist"
            )
            model.fit(
                X_tr, y_train,
                group=train_groups,
                eval_set=[(X_va, y_val)],
                eval_group=[val_groups],
                verbose=False
            )
            preds = model.predict(X_va)

        fit_time = round(time.time() - t0, 2)
        metrics = compute_metrics(y_val, preds, n_val_cases, top_k=25)

        res_entry = {
            "config_id": cfg["id"],
            "architecture": cfg["arch"],
            "objective": cfg["obj"],
            "feature_set": cfg["fset"],
            "feature_count": len(f_cols),
            "max_depth": cfg["max_depth"],
            "learning_rate": cfg["lr"],
            "n_estimators": cfg["n_est"],
            "fit_time_seconds": fit_time,
            "metrics": metrics
        }
        results.append(res_entry)

        print(f"[{cfg['id']}] {cfg['arch']:13s} | {cfg['obj']:15s} | {cfg['fset']:22s} (d={cfg['max_depth']}, lr={cfg['lr']}) | "
              f"Top-1: {metrics['overall_top1']:5.2f}% (Cond: {metrics['cond_top1']:5.2f}%) | "
              f"Top-3: {metrics['overall_top3']:5.2f}% (Cond: {metrics['cond_top3']:5.2f}%) | "
              f"MRR: {metrics['overall_mrr']:.4f} (Cond: {metrics['cond_mrr']:.4f})")

    out_file = os.path.join(base_dir, "ml", "training", "v5_2_ranker_design.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nAll configuration results saved to {out_file}")

if __name__ == "__main__":
    run_ablation_study()
