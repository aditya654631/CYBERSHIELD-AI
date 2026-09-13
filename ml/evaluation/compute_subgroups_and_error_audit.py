"""
CyberShield AI — Phase A.4F Subgroup Safety & Rank-2 Error Audit
Augments ml/evaluation/v5_hierarchical_routing_report.json with:
1. Subgroup safety across 11 districts, 9 fraud types, local vs cross-district, short vs deep hops, high vs low delay.
2. Error audit for cases where target rank == 2.
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from xgboost import XGBRanker

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from ml.data.generate_delhi_v5_dataset import DELHI_CLUSTERS_V5, ALL_11_DISTRICTS, haversine_km
from ml.features.v5_2_pipeline import (
    V52Pipeline,
    LOCATION_FEATURE_NAMES_V5_2,
    ALL_11_DISTRICTS
)
from ml.training.train_hierarchical_routing import (
    DIST_TO_IDX,
    evaluate_ranker_predictions,
    RANDOM_SEED
)

def compute_subgroups_and_audit():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    dev_data_path = os.path.join(base_dir, "ml", "data", "delhi_v5_cases.csv.gz")
    report_path = os.path.join(base_dir, "ml", "evaluation", "v5_hierarchical_routing_report.json")

    df_dev = pd.read_csv(dev_data_path)
    train_cases = df_dev[df_dev["split"] == "train"].reset_index(drop=True)
    val_cases = df_dev[df_dev["split"] == "validation"].reset_index(drop=True)
    n_val_tune = len(val_cases) // 2
    val_tune_cases = val_cases.iloc[:n_val_tune].reset_index(drop=True)

    pipe = V52Pipeline(clusters=DELHI_CLUSTERS_V5)
    cluster_by_id = {c["id"]: c for c in DELHI_CLUSTERS_V5}
    n_train = len(train_cases)
    n_val = len(val_tune_cases)

    # We evaluate Model B (pairwise_plus_district_posterior) as best performing hierarchical model
    # (Top-1: 12.0%, Top-3: 26.13%, MRR: 0.2449, MedErr: 8.05 km)
    # Extract ranking matrices
    X_train_base, y_train_base, meta_train = pipe.build_ranking_matrices(train_cases, top_k=25)
    X_val_base, y_val_base, meta_val = pipe.build_ranking_matrices(val_tune_cases, top_k=25, historical_cases=train_cases)

    # Train stage 1 district model to get probabilities
    from xgboost import XGBClassifier
    X_train_mc, _ = pipe.extract_multiclass_features(train_cases)
    X_val_mc, _ = pipe.extract_multiclass_features(val_tune_cases, historical_cases=train_cases)
    y_train_dist = np.array([DIST_TO_IDX[d] for d in train_cases["realized_cashout_district"].values], dtype=np.int32)

    dist_model = XGBClassifier(
        objective="multi:softprob",
        num_class=11,
        max_depth=5,
        learning_rate=0.05,
        n_estimators=180,
        subsample=0.85,
        colsample_bytree=0.80,
        random_state=RANDOM_SEED,
        tree_method="hist"
    )
    dist_model.fit(X_train_mc, y_train_dist, verbose=False)
    val_dist_probs = dist_model.predict_proba(X_val_mc)

    # Build features for Model B
    def add_dist_posterior_features(X_base, meta_rows, dist_probs, df_cases):
        n_c = len(df_cases)
        c_dist_probs = []
        c_dist_ranks = []
        c_in_top2 = []
        c_in_top3 = []
        for i in range(n_c):
            s = i * 25
            e = s + 25
            probs_11 = dist_probs[i]
            sorted_dist_indices = np.argsort(probs_11)[::-1].tolist()
            for k in range(s, e):
                cid = meta_rows[k]["candidate_cluster_id"]
                c_dist = cluster_by_id[cid]["district"]
                d_idx = DIST_TO_IDX[c_dist]
                prob = float(probs_11[d_idx])
                rank = float(sorted_dist_indices.index(d_idx) + 1)
                c_dist_probs.append(prob)
                c_dist_ranks.append(rank)
                c_in_top2.append(float(rank <= 2))
                c_in_top3.append(float(rank <= 3))
        X_ext = X_base.copy()
        X_ext["candidate_district_probability"] = c_dist_probs
        X_ext["candidate_district_rank"] = c_dist_ranks
        X_ext["candidate_in_top2_predicted_districts"] = c_in_top2
        X_ext["candidate_in_top3_predicted_districts"] = c_in_top3
        return X_ext

    from sklearn.model_selection import KFold
    oof_train_dist_probs = np.zeros((n_train, 11), dtype=np.float32)
    kf = KFold(n_splits=5, shuffle=True, random_state=RANDOM_SEED)
    for fold, (trn_idx, oof_idx) in enumerate(kf.split(X_train_mc)):
        f_model = XGBClassifier(
            objective="multi:softprob",
            num_class=11,
            max_depth=5,
            learning_rate=0.05,
            n_estimators=180,
            subsample=0.85,
            colsample_bytree=0.80,
            random_state=RANDOM_SEED + fold,
            tree_method="hist"
        )
        f_model.fit(X_train_mc.iloc[trn_idx], y_train_dist[trn_idx], verbose=False)
        oof_train_dist_probs[oof_idx] = f_model.predict_proba(X_train_mc.iloc[oof_idx])

    X_train_b = add_dist_posterior_features(X_train_base, meta_train, oof_train_dist_probs, train_cases)
    X_val_b = add_dist_posterior_features(X_val_base, meta_val, val_dist_probs, val_tune_cases)

    feature_cols = LOCATION_FEATURE_NAMES_V5_2 + [
        "candidate_district_probability",
        "candidate_district_rank",
        "candidate_in_top2_predicted_districts",
        "candidate_in_top3_predicted_districts"
    ]

    train_groups = [25] * n_train
    val_groups = [25] * n_val
    m_b = XGBRanker(
        objective="rank:pairwise",
        eval_metric="ndcg@5",
        max_depth=5,
        learning_rate=0.05,
        n_estimators=180,
        subsample=0.85,
        colsample_bytree=0.80,
        random_state=RANDOM_SEED,
        tree_method="hist"
    )
    m_b.fit(X_train_b[feature_cols], y_train_base, group=train_groups, verbose=False)
    preds = m_b.predict(X_val_b[feature_cols])

    true_cids = val_tune_cases["realized_cashout_cluster_id"].values.tolist()
    ranked_cids = []
    ranked_scores = []
    for i in range(n_val):
        s = i * 25
        e = s + 25
        sc = preds[s:e]
        cids = [meta_val[k]["candidate_cluster_id"] for k in range(s, e)]
        s_idx = np.argsort(sc)[::-1]
        ranked_cids.append([cids[k] for k in s_idx])
        ranked_scores.append([sc[k] for k in s_idx])

    # 1. Subgroup breakdowns
    subgroups = {}

    # A. 11 Districts
    subgroups["by_district"] = {}
    for d in sorted(ALL_11_DISTRICTS):
        mask = (val_tune_cases["realized_cashout_district"] == d).values
        idxs = np.where(mask)[0]
        if len(idxs) > 0:
            subgroups["by_district"][d] = evaluate_ranker_predictions(
                [ranked_cids[i] for i in idxs],
                [true_cids[i] for i in idxs],
                cluster_by_id
            )
            subgroups["by_district"][d]["n_cases"] = int(len(idxs))

    # B. 9 Fraud Types
    subgroups["by_fraud_type"] = {}
    for ft in sorted(val_tune_cases["fraud_type"].unique()):
        mask = (val_tune_cases["fraud_type"] == ft).values
        idxs = np.where(mask)[0]
        if len(idxs) > 0:
            subgroups["by_fraud_type"][ft] = evaluate_ranker_predictions(
                [ranked_cids[i] for i in idxs],
                [true_cids[i] for i in idxs],
                cluster_by_id
            )
            subgroups["by_fraud_type"][ft]["n_cases"] = int(len(idxs))

    # C. Local vs Cross-District
    is_cross = (val_tune_cases["victim_district"] != val_tune_cases["realized_cashout_district"]).values
    idxs_local = np.where(~is_cross)[0]
    idxs_cross = np.where(is_cross)[0]
    subgroups["local_vs_cross"] = {
        "local": {
            **evaluate_ranker_predictions([ranked_cids[i] for i in idxs_local], [true_cids[i] for i in idxs_local], cluster_by_id),
            "n_cases": int(len(idxs_local))
        },
        "cross_district": {
            **evaluate_ranker_predictions([ranked_cids[i] for i in idxs_cross], [true_cids[i] for i in idxs_cross], cluster_by_id),
            "n_cases": int(len(idxs_cross))
        }
    }

    # D. Short vs Deep Mule Chain
    is_deep = (val_tune_cases["transaction_hop_count"] > 2).values
    idxs_short = np.where(~is_deep)[0]
    idxs_deep = np.where(is_deep)[0]
    subgroups["hop_depth"] = {
        "short_chain_lte_2": {
            **evaluate_ranker_predictions([ranked_cids[i] for i in idxs_short], [true_cids[i] for i in idxs_short], cluster_by_id),
            "n_cases": int(len(idxs_short))
        },
        "deep_chain_gt_2": {
            **evaluate_ranker_predictions([ranked_cids[i] for i in idxs_deep], [true_cids[i] for i in idxs_deep], cluster_by_id),
            "n_cases": int(len(idxs_deep))
        }
    }

    # E. High vs Low Reporting Delay (median split)
    med_delay = float(val_tune_cases["reporting_delay_minutes"].median())
    is_high_delay = (val_tune_cases["reporting_delay_minutes"] > med_delay).values
    idxs_low_del = np.where(~is_high_delay)[0]
    idxs_high_del = np.where(is_high_delay)[0]
    subgroups["reporting_delay"] = {
        "low_delay": {
            **evaluate_ranker_predictions([ranked_cids[i] for i in idxs_low_del], [true_cids[i] for i in idxs_low_del], cluster_by_id),
            "n_cases": int(len(idxs_low_del))
        },
        "high_delay": {
            **evaluate_ranker_predictions([ranked_cids[i] for i in idxs_high_del], [true_cids[i] for i in idxs_high_del], cluster_by_id),
            "n_cases": int(len(idxs_high_del))
        }
    }

    # 2. Top-1 Error Audit (Cases where target rank == 2)
    rank2_cases = []
    score_margins = []
    same_dist_count = 0
    dist_diffs_km = []

    for i in range(n_val):
        t_cid = true_cids[i]
        cids = ranked_cids[i]
        scs = ranked_scores[i]
        if t_cid in cids and cids.index(t_cid) == 1:
            # Target was rank 2 (0-indexed position 1)
            p1_cid = cids[0]
            target_cid = t_cid
            p1_clust = cluster_by_id[p1_cid]
            t_clust = cluster_by_id[target_cid]

            score_margin = float(scs[0] - scs[1])
            score_margins.append(score_margin)

            same_dist = (p1_clust["district"] == t_clust["district"])
            if same_dist:
                same_dist_count += 1

            dist_between_p1_and_t = haversine_km(p1_clust["lat"], p1_clust["lon"], t_clust["lat"], t_clust["lon"])
            dist_diffs_km.append(dist_between_p1_and_t)

            rank2_cases.append({
                "case_id": val_tune_cases.iloc[i]["case_id"],
                "true_cluster": target_cid,
                "pred_cluster": p1_cid,
                "score_margin": round(score_margin, 4),
                "same_district": bool(same_dist),
                "distance_km": round(dist_between_p1_and_t, 2)
            })

    n_rank2 = len(rank2_cases)
    error_audit = {
        "cases_at_rank_2_count": n_rank2,
        "cases_at_rank_2_pct": round(n_rank2 / n_val * 100, 2),
        "mean_score_margin": round(float(np.mean(score_margins)), 4) if score_margins else 0.0,
        "median_score_margin": round(float(np.median(score_margins)), 4) if score_margins else 0.0,
        "same_district_pct": round(same_dist_count / max(1, n_rank2) * 100, 2),
        "mean_distance_between_p1_and_target_km": round(float(np.mean(dist_diffs_km)), 2) if dist_diffs_km else 0.0,
        "median_distance_between_p1_and_target_km": round(float(np.median(dist_diffs_km)), 2) if dist_diffs_km else 0.0,
        "sample_rank2_cases": rank2_cases[:5]
    }

    # Update report json
    with open(report_path, "r", encoding="utf-8") as f:
        rep = json.load(f)

    rep["subgroup_safety"] = subgroups
    rep["top1_error_audit_rank2"] = error_audit

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=2)

    print("Subgroup safety and Rank-2 error audit computed and saved to report.")

if __name__ == "__main__":
    compute_subgroups_and_audit()
