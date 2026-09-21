"""
CyberShield AI — Training Pipeline for cashout-location-xgb-v8-debiased
Master Corrective Pass V3 — Quality Recovery v2

Key Guarantees:
1. Pure Causal Network Features (49 features = 40 base + 9 within-zone discriminators):
   - Excludes victim-origin shortcuts (distance_from_victim, candidate_same_complaint_zone, dist_to_complaint_zone_km).
   - Zero V4 stacking features (no v4_* features).
2. All 60 Delhi Clusters Evaluated per Complaint.
3. Hard Negative Training: same-zone-wrong-cluster candidates demoted to y=0 with 50% probability.
4. 6-Config Hyperparameter Grid Search: winner selected by Top-3, tiebreak by Top-5.
5. Multi-Regime Causal Synthetic Training Corpus (5 seeds × 2000 complaints).
6. Full Artifact Verification with SHA-256 hashes.
"""

import os
import sys
import json
import time
import math
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple

import joblib
import numpy as np
import pandas as pd
from xgboost import XGBRanker
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.models.db import SessionLocal
from backend.app.models.models import LocationCluster, ATMLocation
from database.seed.synthetic_generator import DelhiSyntheticDataGenerator
from ml.geo.candidate_generator import haversine_km
from ml.features.feature_pipeline import (
    feature_pipeline,
    FEATURE_COLUMNS_LOCATION_V8_DEBIASED,
    FEATURE_COLUMNS_TIME
)

ARTIFACTS_DIR = os.path.join(BASE_DIR, "ml", "artifacts")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)


def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def compute_ece(probs: np.ndarray, y_true: np.ndarray, n_bins: int = 10) -> float:
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(probs)
    if n == 0:
        return 0.0
    for i in range(n_bins):
        b_min, b_max = bins[i], bins[i + 1]
        mask = (probs >= b_min) & (probs < b_max) if i < n_bins - 1 else (probs >= b_min) & (probs <= b_max)
        if np.sum(mask) > 0:
            bin_conf = np.mean(probs[mask])
            bin_acc = np.mean(y_true[mask])
            ece += (np.sum(mask) / n) * abs(bin_acc - bin_conf)
    return float(ece)


def load_delhi_clusters_and_atms() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[int, int]]:
    db = SessionLocal()
    delhi_clusters = (
        db.query(LocationCluster)
        .filter(LocationCluster.state == "Delhi")
        .order_by(LocationCluster.id.asc())
        .all()
    )
    cluster_dicts = [
        {
            "id": c.id,
            "cluster_id": c.id,
            "name": c.cluster_name,
            "city": c.city or "Delhi",
            "state": c.state or "Delhi",
            "zone": c.district,
            "district": c.district,
            "lat": float(c.center_lat),
            "lon": float(c.center_lon),
            "risk": float(c.risk_score) if c.risk_score is not None else 0.50,
            "base_risk": float(c.risk_score) if c.risk_score is not None else 0.50,
            "atm_density": float(c.atm_count) if c.atm_count is not None else 15.0,
            "historical_cashout_count": float(c.historical_fraud_count or 230.0),
            "historical_cashout_amount": float(c.historical_fraud_count or 230.0) * 50000.0
        }
        for c in delhi_clusters
    ]

    delhi_atms = (
        db.query(ATMLocation)
        .filter(ATMLocation.atm_code.like("ATM-DL-%"))
        .order_by(ATMLocation.id.asc())
        .all()
    )
    atm_dicts = [
        {
            "id": a.id,
            "atm_code": a.atm_code,
            "bank_name": a.bank_name,
            "cluster_id": a.cluster_id,
            "cluster_name": next((c["name"] for c in cluster_dicts if c["id"] == a.cluster_id), "Unknown"),
            "lat": float(a.latitude) if a.latitude is not None else 28.6139,
            "lon": float(a.longitude) if a.longitude is not None else 77.2090
        }
        for a in delhi_atms
    ]
    atm_to_cluster = {a["id"]: a["cluster_id"] for a in atm_dicts}
    atm_code_to_cluster = {a["atm_code"]: a["cluster_id"] for a in atm_dicts}

    db.close()
    return cluster_dicts, atm_dicts, atm_code_to_cluster


def generate_training_data(
    seeds: List[int],
    cases_per_seed: int,
    cluster_dicts: List[Dict[str, Any]],
    atm_dicts: List[Dict[str, Any]],
    atm_code_to_cluster: Dict[str, int]
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[Dict[str, Any]]]:
    """
    Generates multi-seed causal Delhi complaints and extracts 40 V8 features across all 60 clusters.
    """
    print(f"\n--- Generating Causal Training Data across {len(seeds)} Seeds ({cases_per_seed} cases each) ---")
    all_X_rows = []
    all_y_rows = []
    all_groups = []
    complaint_metadata = []

    for s in seeds:
        print(f"  Generating dataset for seed {s}...")
        gen = DelhiSyntheticDataGenerator(s)
        ds = gen.generate_dataset(cluster_dicts, atm_dicts, num_complaints=cases_per_seed, num_accounts=cases_per_seed * 2)

        # Build lookup maps for transactions and withdrawals per complaint
        tx_by_comp = {}
        for tx in ds["transactions"]:
            c_num = tx["complaint_number"]
            tx_by_comp.setdefault(c_num, []).append(tx)

        wd_by_comp = {}
        for wd in ds["withdrawals"]:
            c_num = wd.get("complaint_number")
            if c_num:
                wd_by_comp.setdefault(c_num, []).append(wd)

        # Build account dictionary
        acc_by_num = {a["account_number"]: a for a in ds["accounts"]}

        for comp in ds["complaints"]:
            c_num = comp["complaint_number"]
            wds = wd_by_comp.get(c_num, [])
            if not wds:
                continue
            
            # Ground truth cashout cluster from withdrawal ATM
            target_wd = wds[0]
            target_atm_code = target_wd["atm_code"]
            target_cluster_id = atm_code_to_cluster.get(target_atm_code)
            if target_cluster_id is None:
                continue

            txs = tx_by_comp.get(c_num, [])

            # Enrich transactions with receiver account info
            enriched_txs = []
            for t in txs:
                rec_acc = acc_by_num.get(t["receiver_account_number"])
                enriched_txs.append({
                    "transaction_ref": t["transaction_ref"],
                    "sender_account_id": t["sender_account_number"],
                    "receiver_account_id": t["receiver_account_number"],
                    "amount": t["amount"],
                    "payment_channel": t["payment_channel"],
                    "timestamp": t["timestamp"],
                    "hop_number": t["hop_number"],
                    "receiver_district": rec_acc.get("district") if rec_acc else None,
                    "bank_name": rec_acc.get("bank_name") if rec_acc else None
                })

            # Evaluate all 60 Delhi clusters
            X_loc, _, feat_cols, _ = feature_pipeline.build_candidate_matrix_v8_debiased(
                complaint=comp,
                candidates=cluster_dicts,
                transactions=enriched_txs,
                graph_metrics=None
            )

            # Target labels: Graded relevance based on true cashout corridor
            target_cl = next((c for c in cluster_dicts if c["id"] == target_cluster_id), None)
            t_lat = target_cl["lat"] if target_cl else 28.6139
            t_lon = target_cl["lon"] if target_cl else 77.2090
            t_zone = (target_cl["zone"] or "").upper() if target_cl else ""

            y_loc = []
            for c in cluster_dicts:
                if c["id"] == target_cluster_id:
                    y_loc.append(4) # Exact target match
                else:
                    d_km = haversine_km(t_lat, t_lon, c["lat"], c["lon"])
                    c_zone = (c["zone"] or "").upper()
                    if d_km <= 3.0 or (t_zone and c_zone == t_zone):
                        y_loc.append(2) # Close corridor / same destination zone
                    elif d_km <= 7.0:
                        y_loc.append(1) # Adjacent corridor
                    else:
                        y_loc.append(0) # Far cluster
            y_loc = np.array(y_loc, dtype=np.int32)

            all_X_rows.append(X_loc)
            all_y_rows.append(y_loc)
            all_groups.append(len(cluster_dicts))

            complaint_metadata.append({
                "complaint_number": c_num,
                "victim_district": comp.get("victim_district"),
                "target_cluster_id": target_cluster_id,
                "target_zone": next((c["zone"] for c in cluster_dicts if c["id"] == target_cluster_id), "Unknown"),
                "num_hops": comp.get("hop_count", 2),
                "fraud_type": comp.get("fraud_type")
            })

    X = np.vstack(all_X_rows)
    y = np.concatenate(all_y_rows)
    groups = np.array(all_groups, dtype=np.int32)
    print(f"  Total Candidate Rows: {X.shape[0]}, Feature Count: {X.shape[1]}, Queries: {len(groups)}")
    return X, y, groups, complaint_metadata


def apply_hard_negatives(y: np.ndarray, groups: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """
    For same-zone-wrong-cluster (y==2) candidates, randomly demote 50% to y=0
    to force within-zone discrimination. Leaves y=4 (target) and y=1 (adjacent) unchanged.
    """
    y_hard = y.copy()
    idx = 0
    for g in groups:
        g = int(g)
        block = y_hard[idx:idx + g]
        y2_pos = np.where(block == 2)[0]
        if len(y2_pos) > 2:
            n_demote = max(1, len(y2_pos) // 2)
            to_demote = rng.choice(y2_pos, size=n_demote, replace=False)
            block[to_demote] = 0
        y_hard[idx:idx + g] = block
        idx += g
    return y_hard


def compute_ranking_metrics(
    cal_probs: np.ndarray,
    y_val: np.ndarray,
    y_val_binary: np.ndarray,
    groups_val: np.ndarray,
    meta_val: list,
    cluster_dicts: list
) -> dict:
    cl_coords = {c["id"]: (c["lat"], c["lon"]) for c in cluster_dicts}
    val_r1 = val_r3 = val_r5 = 0
    mrr_sum = 0.0
    dist_errors = []
    row_idx = 0
    for q_idx, g_size in enumerate(groups_val):
        g_size = int(g_size)
        q_scores = cal_probs[row_idx:row_idx + g_size]
        q_labels = y_val[row_idx:row_idx + g_size]
        target_cl_id = meta_val[q_idx]["target_cluster_id"]
        t_lat, t_lon = cl_coords.get(target_cl_id, (28.6139, 77.2090))
        ranked_indices = np.argsort(-q_scores)
        target_in_cand = np.where(q_labels == 4)[0]
        if len(target_in_cand) > 0:
            true_idx = target_in_cand[0]
            rank = int(np.where(ranked_indices == true_idx)[0][0]) + 1
            if rank == 1: val_r1 += 1
            if rank <= 3: val_r3 += 1
            if rank <= 5: val_r5 += 1
            mrr_sum += 1.0 / rank
            top1_cl = cluster_dicts[ranked_indices[0]]
            dist_errors.append(haversine_km(t_lat, t_lon, top1_cl["lat"], top1_cl["lon"]))
        row_idx += g_size
    n_val = len(groups_val)
    return {
        "r1": (val_r1 / n_val) * 100.0,
        "r3": (val_r3 / n_val) * 100.0,
        "r5": (val_r5 / n_val) * 100.0,
        "mrr": mrr_sum / n_val,
        "median_err": float(np.median(dist_errors)) if dist_errors else 0.0,
        "mean_err": float(np.mean(dist_errors)) if dist_errors else 0.0,
        "ece": compute_ece(cal_probs, y_val_binary),
        "brier": float(brier_score_loss(y_val_binary, cal_probs))
    }


def train_single_config(
    cfg, X_train, y_train, groups_train,
    X_val, y_val, y_val_binary, groups_val, meta_val, cluster_dicts
):
    rng = np.random.default_rng(cfg.get("seed", 42))
    y_train_hn = apply_hard_negatives(y_train, groups_train, rng)
    ranker = XGBRanker(
        n_estimators=cfg["n_estimators"],
        max_depth=cfg["max_depth"],
        learning_rate=cfg["learning_rate"],
        reg_lambda=cfg.get("reg_lambda", 2.0),
        reg_alpha=cfg.get("reg_alpha", 0.0),
        gamma=cfg.get("gamma", 0.0),
        colsample_bytree=cfg.get("colsample_bytree", 0.85),
        subsample=cfg.get("subsample", 0.85),
        min_child_weight=cfg.get("min_child_weight", 2),
        objective="rank:ndcg",
        eval_metric=cfg.get("eval_metric", "ndcg@3"),
        random_state=cfg.get("seed", 42),
        n_jobs=-1,
        verbosity=0
    )
    ranker.fit(
        X_train, y_train_hn,
        group=groups_train,
        eval_set=[(X_val, y_val)],
        eval_group=[groups_val],
        verbose=False
    )
    raw_val = ranker.predict(X_val)
    calibrator = LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000, random_state=42)
    calibrator.fit(raw_val.reshape(-1, 1), y_val_binary)
    cal_probs = calibrator.predict_proba(raw_val.reshape(-1, 1))[:, 1]
    m = compute_ranking_metrics(cal_probs, y_val, y_val_binary, groups_val, meta_val, cluster_dicts)
    return {"ranker": ranker, "calibrator": calibrator, **m}


def train_and_calibrate_v8():
    t0 = time.time()
    print("======================================================================")
    print("CYBERSHIELD AI --- TRAINING LOCATION MODEL V8 DEBIASED (CHALLENGER)")
    print("  Phase: Quality Recovery v2 -- 49-Feature + Hard Negatives + Grid Search")
    print("======================================================================")

    cluster_dicts, atm_dicts, atm_code_to_cluster = load_delhi_clusters_and_atms()
    print(f"Loaded {len(cluster_dicts)} Delhi clusters and {len(atm_dicts)} Delhi ATMs.")

    # 1. Generate multi-regime training dataset (5 diverse seeds)
    train_seeds = [10421, 26184, 34190, 42100, 58921]
    X, y, groups, meta = generate_training_data(
        seeds=train_seeds,
        cases_per_seed=2000,
        cluster_dicts=cluster_dicts,
        atm_dicts=atm_dicts,
        atm_code_to_cluster=atm_code_to_cluster
    )

    # 2. Query-level 80/20 train/validation split
    n_queries = len(groups)
    n_train_queries = int(0.80 * n_queries)
    train_row_end = int(np.sum(groups[:n_train_queries]))
    X_train, y_train = X[:train_row_end], y[:train_row_end]
    groups_train = groups[:n_train_queries]
    X_val, y_val = X[train_row_end:], y[train_row_end:]
    groups_val = groups[n_train_queries:]
    meta_val = meta[n_train_queries:]
    y_val_binary = (y_val == 4).astype(np.int32)

    print(f"\n--- Split Summary ---")
    print(f"  Train: {n_train_queries} queries, {X_train.shape[0]} rows")
    print(f"  Validation: {len(groups_val)} queries, {X_val.shape[0]} rows")
    print(f"  Feature count: {X_train.shape[1]}")

    # 3. Hyperparameter Grid Search (6 configs, primary: Top-3, secondary: Top-5)
    configs = [
        {"name": "A", "n_estimators": 500, "max_depth": 6, "learning_rate": 0.04,
         "reg_lambda": 2.0, "reg_alpha": 0.0, "gamma": 0.0,
         "colsample_bytree": 0.85, "subsample": 0.85, "min_child_weight": 2,
         "eval_metric": "ndcg@3", "seed": 42},
        {"name": "B", "n_estimators": 700, "max_depth": 4, "learning_rate": 0.03,
         "reg_lambda": 3.0, "reg_alpha": 0.5, "gamma": 0.1,
         "colsample_bytree": 0.80, "subsample": 0.80, "min_child_weight": 3,
         "eval_metric": "ndcg@5", "seed": 42},
        {"name": "C", "n_estimators": 600, "max_depth": 5, "learning_rate": 0.035,
         "reg_lambda": 2.5, "reg_alpha": 0.3, "gamma": 0.05,
         "colsample_bytree": 0.85, "subsample": 0.85, "min_child_weight": 2,
         "eval_metric": "ndcg@5", "seed": 42},
        {"name": "D", "n_estimators": 350, "max_depth": 5, "learning_rate": 0.06,
         "reg_lambda": 1.5, "reg_alpha": 0.0, "gamma": 0.1,
         "colsample_bytree": 0.75, "subsample": 0.80, "min_child_weight": 2,
         "eval_metric": "ndcg@3", "seed": 42},
        {"name": "E", "n_estimators": 500, "max_depth": 5, "learning_rate": 0.04,
         "reg_lambda": 4.0, "reg_alpha": 1.0, "gamma": 0.3,
         "colsample_bytree": 0.80, "subsample": 0.75, "min_child_weight": 1,
         "eval_metric": "ndcg@3", "seed": 42},
        {"name": "F", "n_estimators": 600, "max_depth": 6, "learning_rate": 0.04,
         "reg_lambda": 2.0, "reg_alpha": 0.0, "gamma": 0.0,
         "colsample_bytree": 0.90, "subsample": 0.90, "min_child_weight": 2,
         "eval_metric": "ndcg@3", "seed": 42},
    ]

    print("\n--- Hyperparameter Grid Search (6 configs) ---")
    print(f"  {'Config':<8} {'Top-1':>8} {'Top-3':>8} {'Top-5':>8} {'MRR':>8} {'MedErr':>9} {'ECE':>8}")
    print("  " + "-" * 62)

    best_cfg_name = None
    best_r3 = -1.0
    best_r5 = -1.0
    best_result = None
    all_results = []

    for cfg in configs:
        r = train_single_config(
            cfg, X_train, y_train, groups_train,
            X_val, y_val, y_val_binary, groups_val, meta_val, cluster_dicts
        )
        all_results.append({"name": cfg["name"], **{k: v for k, v in r.items() if k not in ("ranker", "calibrator")}})
        print(f"  Cfg {cfg['name']:<5} {r['r1']:>7.2f}% {r['r3']:>7.2f}% {r['r5']:>7.2f}% "
              f"{r['mrr']:>8.4f} {r['median_err']:>8.2f}km {r['ece']:>8.4f}")
        if r["r3"] > best_r3 or (r["r3"] == best_r3 and r["r5"] > best_r5):
            best_r3 = r["r3"]
            best_r5 = r["r5"]
            best_cfg_name = cfg["name"]
            best_result = r

    winning_cfg = next(c for c in configs if c["name"] == best_cfg_name)
    print(f"\n  Winner: Config {best_cfg_name} "
          f"(Top-3={best_r3:.2f}%, Top-5={best_r5:.2f}%, MedErr={best_result['median_err']:.2f}km)")

    ranker = best_result["ranker"]
    calibrator = best_result["calibrator"]
    r1_pct = best_result["r1"]
    r3_pct = best_result["r3"]
    r5_pct = best_result["r5"]
    mrr = best_result["mrr"]
    median_err = best_result["median_err"]
    mean_err = best_result["mean_err"]
    ece = best_result["ece"]
    brier = best_result["brier"]
    n_val = len(groups_val)

    print("\n--- Validation Metrics (Winner) ---")
    print(f"  Validation Queries: {n_val}")
    print(f"  Recall@1: {r1_pct:.2f}%")
    print(f"  Recall@3: {r3_pct:.2f}%")
    print(f"  Recall@5: {r5_pct:.2f}%")
    print(f"  MRR: {mrr:.4f}")
    print(f"  Median Error: {median_err:.2f} km (Mean: {mean_err:.2f} km)")
    print(f"  ECE: {ece:.4f}")
    print(f"  Brier Score: {brier:.4f}")

    # 4. Save Artifacts
    ranker_path = os.path.join(ARTIFACTS_DIR, "location_ranker_v8_debiased.joblib")
    calibrator_path = os.path.join(ARTIFACTS_DIR, "location_calibrator_v8_debiased.joblib")
    schema_path = os.path.join(ARTIFACTS_DIR, "feature_schema_v8_debiased.json")
    metadata_path = os.path.join(ARTIFACTS_DIR, "model_metadata_v8_debiased.json")
    manifest_path = os.path.join(ARTIFACTS_DIR, "v8_training_manifest.json")
    lime_bg_path = os.path.join(ARTIFACTS_DIR, "v8_lime_background.npy")

    print("\n--- Saving Artifacts ---")
    joblib.dump(ranker, ranker_path, compress=3)
    joblib.dump(calibrator, calibrator_path, compress=3)

    np.random.seed(42)
    sample_indices = np.random.choice(X_train.shape[0], size=min(150, X_train.shape[0]), replace=False)
    np.save(lime_bg_path, X_train[sample_indices])

    schema_data = {
        "version": "v8_debiased",
        "location_features": FEATURE_COLUMNS_LOCATION_V8_DEBIASED,
        "total_location_features": len(FEATURE_COLUMNS_LOCATION_V8_DEBIASED),
        "excluded_shortcut_features": [
            "distance_from_victim",
            "candidate_same_complaint_zone",
            "dist_to_complaint_zone_km"
        ],
        "new_within_zone_features": [
            "dist_to_terminal_centroid_km",
            "log_cluster_network_exposure",
            "cluster_fraud_type_match_score",
            "cluster_channel_match_score",
            "cluster_hourly_match_score",
            "cluster_weekday_match_score",
            "atm_density_log",
            "cluster_risk_x_count",
            "dist_to_second_account_zone_km"
        ],
        "time_features": FEATURE_COLUMNS_TIME,
        "time_features_count": len(FEATURE_COLUMNS_TIME)
    }
    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(schema_data, f, indent=2)

    ranker_sha = compute_sha256(ranker_path)
    calibrator_sha = compute_sha256(calibrator_path)
    schema_sha = compute_sha256(schema_path)
    lime_sha = compute_sha256(lime_bg_path)

    metadata = {
        "model_version": "cashout-location-xgb-v8-debiased",
        "time_model_version": "cashout-time-xgb-v3",
        "training_timestamp": datetime.now(timezone.utc).isoformat(),
        "algorithm": "pairwise_xgb_ranker_debiased_v2_hardneg_gridsearch",
        "feature_count": len(FEATURE_COLUMNS_LOCATION_V8_DEBIASED),
        "winning_config": winning_cfg,
        "grid_search_results": all_results,
        "hard_negative_training": True,
        "calibration_method": "platt_logistic",
        "validation_metrics": {
            "r1": round(r1_pct, 2),
            "r3": round(r3_pct, 2),
            "r5": round(r5_pct, 2),
            "mrr": round(mrr, 4),
            "median_error_km": round(median_err, 2),
            "mean_error_km": round(mean_err, 2),
            "ece": round(ece, 4),
            "brier_score": round(brier, 4)
        },
        "dataset_summary": {
            "training_seeds": train_seeds,
            "total_queries": n_queries,
            "train_queries": n_train_queries,
            "val_queries": len(groups_val),
            "total_rows": int(X.shape[0])
        },
        "artifacts": {
            "ranker": {"file": "location_ranker_v8_debiased.joblib", "sha256": ranker_sha},
            "calibrator": {"file": "location_calibrator_v8_debiased.joblib", "sha256": calibrator_sha},
            "feature_schema": {"file": "feature_schema_v8_debiased.json", "sha256": schema_sha},
            "lime_background": {"file": "v8_lime_background.npy", "sha256": lime_sha}
        },
        "promotion_status": {
            "challenger_trained": True,
            "promoted_to_production": False,
            "qualification_gate_passed": False
        },
        "synthetic_disclosure": "Trained on causal money-network synthetic Delhi cybercrime corpus. Free of victim-origin ranking shortcuts."
    }
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    manifest = {
        "manifest_version": "2.0.0",
        "model_id": "cashout-location-xgb-v8-debiased",
        "build_date": datetime.now(timezone.utc).isoformat(),
        "feature_count": len(FEATURE_COLUMNS_LOCATION_V8_DEBIASED),
        "cluster_universe_size": len(cluster_dicts),
        "hashes": {
            "location_ranker_v8_debiased.joblib": ranker_sha,
            "location_calibrator_v8_debiased.joblib": calibrator_sha,
            "feature_schema_v8_debiased.json": schema_sha,
            "v8_lime_background.npy": lime_sha
        },
        "metrics": metadata["validation_metrics"],
        "qualification_status": "PENDING_EVALUATION"
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n[SUCCESS] Model V8 Debiased (Quality Recovery v2) trained in {time.time() - t0:.2f}s.")
    print(f"  Winning Config: {best_cfg_name}")
    print(f"  Ranker SHA256: {ranker_sha}")
    print(f"  Calibrator SHA256: {calibrator_sha}")
    print(f"  Schema SHA256: {schema_sha}")
    print(f"  Feature Count: {len(FEATURE_COLUMNS_LOCATION_V8_DEBIASED)}")


if __name__ == "__main__":
    train_and_calibrate_v8()
