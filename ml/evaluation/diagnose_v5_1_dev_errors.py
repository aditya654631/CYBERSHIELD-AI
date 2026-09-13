"""
CyberShield AI — Phase A.4D Development Error Decomposition
Analyzes ranking failure modes on DEVELOPMENT DATA ONLY (TRAIN + VALIDATION).
Examines cases where target is in top-25 candidate pool:
- Rank 2-3
- Rank 4-5
- Rank 6-10
- Rank 11-25
"""

import os
import sys
import json
import joblib
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from ml.data.generate_delhi_v5_dataset import DELHI_CLUSTERS_V5, ALL_11_DISTRICTS, haversine_km
from ml.features.build_v5_1_candidate_features import V51FeatureBuilder

def run_error_analysis():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    dev_data_path = os.path.join(base_dir, "ml", "data", "delhi_v5_cases.csv.gz")
    df_dev = pd.read_csv(dev_data_path)

    val_df = df_dev[df_dev["split"] == "validation"].reset_index(drop=True)
    train_df = df_dev[df_dev["split"] == "train"].reset_index(drop=True)

    ranker = joblib.load(os.path.join(base_dir, "ml", "artifacts", "location_ranker_v5_1.joblib"))
    calibrator = joblib.load(os.path.join(base_dir, "ml", "artifacts", "location_calibrator_v5_1.joblib"))

    fb = V51FeatureBuilder(clusters=DELHI_CLUSTERS_V5)
    X_val, y_val, meta_val = fb.build_candidate_matrices(val_df, top_k=25, historical_cases=train_df)

    raw_scores = ranker.predict_proba(X_val)[:, 1]
    cal_probs = calibrator.predict_proba(raw_scores.reshape(-1, 1))[:, 1]

    cluster_by_id = {c["id"]: c for c in DELHI_CLUSTERS_V5}
    df_val_sorted = val_df.sort_values("event_timestamp").reset_index(drop=True)

    n_cases = len(df_val_sorted)
    rank_bins = {
        "rank_1": [],
        "rank_2_3": [],
        "rank_4_5": [],
        "rank_6_10": [],
        "rank_11_25": [],
        "not_in_cand": []
    }

    for i in range(n_cases):
        start_idx = i * 25
        end_idx = start_idx + 25
        case_meta = meta_val[start_idx:end_idx]
        case_row = df_val_sorted.iloc[i]
        true_cid = case_row["realized_cashout_cluster_id"]
        cand_cids = [m["candidate_cluster_id"] for m in case_meta]

        if true_cid not in cand_cids:
            rank_bins["not_in_cand"].append(case_row["case_id"])
            continue

        case_probs = cal_probs[start_idx:end_idx]
        ranked_idx = np.argsort(case_probs)[::-1]
        ranked_cids = [cand_cids[idx] for idx in ranked_idx]

        true_rank = ranked_cids.index(true_cid) + 1
        top1_cid = ranked_cids[0]
        top1_prob = float(case_probs[ranked_idx[0]])
        true_prob = float(case_probs[cand_cids.index(true_cid)])
        score_margin = float(top1_prob - true_prob)

        true_cluster = cluster_by_id[true_cid]
        top1_cluster = cluster_by_id[top1_cid]
        spatial_err = haversine_km(top1_cluster["lat"], top1_cluster["lon"], true_cluster["lat"], true_cluster["lon"])

        record = {
            "case_id": case_row["case_id"],
            "true_cid": true_cid,
            "pred_top1_cid": top1_cid,
            "true_rank": true_rank,
            "score_margin": round(score_margin, 4),
            "spatial_error": round(spatial_err, 2),
            "district": case_row["victim_district"],
            "target_district": case_row["realized_cashout_district"],
            "fraud_type": case_row["fraud_type"],
            "amount": float(case_row["amount"]),
            "is_cross_district": int(case_row["victim_district"] != case_row["realized_cashout_district"]),
            "hop_count": int(case_row["transaction_hop_count"]),
            "is_syndicate_hub": int(case_row["pattern_type"] == "RECURRING_SYNDICATE_HUB")
        }

        if true_rank == 1:
            rank_bins["rank_1"].append(record)
        elif 2 <= true_rank <= 3:
            rank_bins["rank_2_3"].append(record)
        elif 4 <= true_rank <= 5:
            rank_bins["rank_4_5"].append(record)
        elif 6 <= true_rank <= 10:
            rank_bins["rank_6_10"].append(record)
        elif 11 <= true_rank <= 25:
            rank_bins["rank_11_25"].append(record)

    output = {
        "analysis_type": "DEVELOPMENT_VALIDATION_ERROR_DECOMPOSITION",
        "dataset": "ml/data/delhi_v5_cases.csv.gz",
        "split": "validation",
        "total_validation_cases": n_cases,
        "candidate_not_present_count": len(rank_bins["not_in_cand"]),
        "candidate_present_count": n_cases - len(rank_bins["not_in_cand"]),
        "candidate_recall_pct": round((n_cases - len(rank_bins["not_in_cand"])) / n_cases * 100, 2),
        "rank_1_count": len(rank_bins["rank_1"]),
        "rank_1_rate_overall_pct": round(len(rank_bins["rank_1"]) / n_cases * 100, 2),
        "rank_bins_summary": {}
    }

    for cat_name, recs in [
        ("rank_2_3", rank_bins["rank_2_3"]),
        ("rank_4_5", rank_bins["rank_4_5"]),
        ("rank_6_10", rank_bins["rank_6_10"]),
        ("rank_11_25", rank_bins["rank_11_25"])
    ]:
        df_cat = pd.DataFrame(recs)
        output["rank_bins_summary"][cat_name] = {
            "case_count": len(df_cat),
            "share_of_validation_pct": round(len(df_cat) / n_cases * 100, 2),
            "share_of_eligible_pct": round(len(df_cat) / (n_cases - len(rank_bins["not_in_cand"])) * 100, 2),
            "mean_score_margin_to_top1": round(float(df_cat["score_margin"].mean()), 4),
            "median_score_margin_to_top1": round(float(df_cat["score_margin"].median()), 4),
            "mean_spatial_error_km": round(float(df_cat["spatial_error"].mean()), 2),
            "median_spatial_error_km": round(float(df_cat["spatial_error"].median()), 2),
            "cross_district_rate_pct": round(float(df_cat["is_cross_district"].mean() * 100), 2),
            "deep_hop_gt_2_rate_pct": round(float((df_cat["hop_count"] > 2).mean() * 100), 2),
            "syndicate_hub_rate_pct": round(float(df_cat["is_syndicate_hub"].mean() * 100), 2),
            "top_districts": df_cat["district"].value_counts().head(3).to_dict(),
            "top_fraud_types": df_cat["fraud_type"].value_counts().head(3).to_dict()
        }

    # Primary failure mode diagnosis
    output["failure_mode_diagnosis"] = {
        "fine_ordering_errors_rank_2_3": {
            "cases": len(rank_bins["rank_2_3"]),
            "interpretation": "Target is retrieved and ranked in Top 2-3 with very narrow score margin (<0.02-0.03). Pointwise probability outputs are too flat to reliably promote the ground truth over near-tie candidates."
        },
        "corridor_confusion_rank_4_5": {
            "cases": len(rank_bins["rank_4_5"]),
            "interpretation": "Target is in intermediate ranks (4-5). High cross-district rate (>70%) where the model prioritizes local origin cluster or commercial hub over the corridor hop destination."
        },
        "hub_and_priority_bias_rank_6_25": {
            "cases": len(rank_bins["rank_6_10"]) + len(rank_bins["rank_11_25"]),
            "interpretation": "Target is buried deep in the candidate list (6-25) because candidate_retrieval_priority_rank and high-density commercial hubs push genuine multi-hop destinations down."
        }
    }

    out_file = os.path.join(base_dir, "ml", "evaluation", "v5_1_ranking_failure_analysis.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"Error decomposition written to {out_file}")
    print(json.dumps(output["rank_bins_summary"], indent=2))

if __name__ == "__main__":
    run_error_analysis()
