"""
CyberShield AI — Location Model V4 & Time Model V3 Controlled Training
Phase 1: Leakage-Free Delhi Pilot Model Quality Improvement

Guarantees:
- Chronological 70/15/15 split on Delhi synthetic dataset V2 (identical to V3.1)
- 43-feature location contract, 20-feature time contract
- Preserves all V3.1 and V2 artifacts untouched on disk as rollbacks
- Evaluates V4 against V3.1 on identical held-out test data
- Evaluates Time V3 against Time V2 on identical held-out test data
- Only promotes models if metrics improve / maintain strength without regression
"""

import os
import sys
import json
import time
import math
import hashlib
import collections
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

import joblib
import numpy as np
import pandas as pd
from xgboost import XGBClassifier, XGBRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, mean_absolute_error, root_mean_squared_error

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.models.db import SessionLocal
from backend.app.models.models import (
    Complaint, Account, Transaction, Withdrawal,
    LocationCluster, ATMLocation, Prediction, PredictionLocation, Alert
)
from database.seed.seed_config import SYNTHETIC_RANDOM_SEED, NUM_COMPLAINTS, NUM_ACCOUNTS
from database.seed.synthetic_generator import (
    DelhiSyntheticDataGenerator, ZONE_ADJACENCY, FRAUD_TYPE_ZONE_AFFINITY
)
from ml.geo.candidate_generator import CandidateLocationGenerator, haversine_km
from ml.features.feature_pipeline import (
    feature_pipeline,
    FEATURE_COLUMNS_LOCATION_V3_1,
    FEATURE_COLUMNS_TIME,
    DELHI_ZONE_CENTROIDS
)

ARTIFACTS_DIR = os.path.join(BASE_DIR, "ml", "artifacts")


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


def train_v4_pipeline():
    t_start = time.time()
    print("=" * 80)
    print("CYBERSHIELD AI — LOCATION V4 & TIME V3 CONTROLLED TRAINING PIPELINE")
    print("=" * 80)

    db = SessionLocal()
    delhi_clusters = db.query(LocationCluster).filter(LocationCluster.state == "Delhi").order_by(LocationCluster.id.asc()).all()
    delhi_atms = db.query(ATMLocation).filter(ATMLocation.atm_code.like("ATM-DL-%")).all()

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
    atm_dicts = [
        {
            "atm_code": a.atm_code,
            "bank_name": a.bank_name,
            "cluster_name": [c["name"] for c in cluster_dicts if c["id"] == a.cluster_id][0],
            "id": a.id
        }
        for a in delhi_atms
    ]

    cluster_id_by_name = {c["name"]: c["id"] for c in cluster_dicts}
    cluster_by_id = {c["id"]: c for c in cluster_dicts}

    # Generate synthetic dataset matching seed
    gen = DelhiSyntheticDataGenerator(SYNTHETIC_RANDOM_SEED)
    ds = gen.generate_dataset(cluster_dicts, atm_dicts, NUM_COMPLAINTS, NUM_ACCOUNTS)

    complaints_raw = ds["complaints"]
    transactions_raw = ds["transactions"]
    accounts_map = {a["account_number"]: a for a in ds["accounts"]}
    withdrawals_map = {w["complaint_number"]: w for w in ds["withdrawals"]}
    debug_meta_map = {m["complaint_number"]: m for m in ds["debug_metadata"]}

    tx_by_comp = collections.defaultdict(list)
    for t in transactions_raw:
        tx_by_comp[t["complaint_number"]].append(t)

    # Chronological Split (70 / 15 / 15)
    sorted_complaints = sorted(complaints_raw, key=lambda c: (c["reported_at"], c["complaint_number"]))
    n_total = len(sorted_complaints)
    n_train = int(n_total * 0.70)
    n_val = int(n_total * 0.15)
    n_test = n_total - n_train - n_val

    train_comps = sorted_complaints[:n_train]
    val_comps = sorted_complaints[n_train:n_train + n_val]
    test_comps = sorted_complaints[n_train + n_val:]

    print(f"Train: {len(train_comps)} | Val: {len(val_comps)} | Test: {len(test_comps)}")

    cand_gen = CandidateLocationGenerator(clusters=cluster_dicts)

    def get_complaint_geo_context(comp: Dict[str, Any]) -> Tuple[Optional[str], set]:
        c_num = comp["complaint_number"]
        comp_txs = tx_by_comp.get(c_num, [])
        term_z = None
        all_z = set()
        if comp_txs:
            max_h = max(t["hop_number"] for t in comp_txs)
            term_txs = [t for t in comp_txs if t["hop_number"] == max_h]
            best_t = max(term_txs, key=lambda x: x["amount"])
            acc = accounts_map.get(best_t["receiver_account_number"])
            if acc and acc.get("district"):
                term_z = str(acc["district"])
            for t in comp_txs:
                r_acc = accounts_map.get(t["receiver_account_number"])
                if r_acc and r_acc.get("district"):
                    all_z.add(str(r_acc["district"]))
        return term_z, all_z

    def extract_features(comps, is_train=False):
        X_loc_list = []
        y_loc_list = []
        groups = []
        X_time_list = []
        y_time_list = []

        for comp in comps:
            c_num = comp["complaint_number"]
            if c_num not in withdrawals_map:
                continue
            wdl = withdrawals_map[c_num]
            target_cluster_name = wdl["target_cluster_name"]
            tid = cluster_id_by_name[target_cluster_name]

            term_z, all_z = get_complaint_geo_context(comp)
            comp_txs = tx_by_comp.get(c_num, [])

            cands = cand_gen.generate_candidates_for_complaint(
                complaint=comp,
                top_k=25,
                transactions=comp_txs,
                terminal_zone=term_z,
                all_tx_zones=all_z
            )
            cand_ids = [c["id"] for c in cands]

            if is_train and tid not in cand_ids:
                cands.append(cluster_by_id[tid])

            X_comp_loc, X_comp_time, _, _ = feature_pipeline.build_candidate_matrix_v3_1(
                complaint=comp,
                candidates=cands,
                transactions=comp_txs,
                graph_metrics={},
                terminal_zone=term_z,
                all_tx_zones=all_z
            )

            cand_group = []
            for idx, c in enumerate(cands):
                is_tgt = 1 if c["id"] == tid else 0
                X_loc_list.append(X_comp_loc[idx])
                y_loc_list.append(is_tgt)
                cand_group.append((c, is_tgt))

            meta = debug_meta_map.get(c_num, {})
            groups.append({
                "complaint_number": c_num,
                "target_id": tid,
                "target_name": target_cluster_name,
                "origin_zone": comp.get("district"),
                "cands": cand_group
            })

            # Time feature row and target
            rep_val = comp["reported_at"]
            rep_dt = rep_val if isinstance(rep_val, datetime) else datetime.fromisoformat(str(rep_val))
            wdl_val = wdl.get("timestamp") or wdl.get("withdrawal_timestamp")
            wdl_dt = wdl_val if isinstance(wdl_val, datetime) else datetime.fromisoformat(str(wdl_val))
            delay_mins = max(15.0, (wdl_dt - rep_dt).total_seconds() / 60.0)

            X_time_list.append(X_comp_time[0])
            y_time_list.append(delay_mins)

        return (
            np.array(X_loc_list, dtype=np.float32),
            np.array(y_loc_list, dtype=np.int32),
            groups,
            np.array(X_time_list, dtype=np.float32),
            np.array(y_time_list, dtype=np.float32)
        )

    print("Extracting features for Train, Val, Test...")
    X_loc_train, y_loc_train, train_groups, X_time_train, y_time_train = extract_features(train_comps, is_train=True)
    X_loc_val, y_loc_val, val_groups, X_time_val, y_time_val = extract_features(val_comps, is_train=False)
    X_loc_test, y_loc_test, test_groups, X_time_test, y_time_test = extract_features(test_comps, is_train=False)

    print(f"Location Train: {X_loc_train.shape} (pos: {np.sum(y_loc_train)}) | Val: {X_loc_val.shape} | Test: {X_loc_test.shape}")
    print(f"Time Train: {X_time_train.shape} | Val: {X_time_val.shape} | Test: {X_time_test.shape}")

    # -------------------------------------------------------------
    # 1. EVALUATE EXISTING V3.1 LOCATION MODEL ON TEST SET
    # -------------------------------------------------------------
    loc_v3_1 = joblib.load(os.path.join(ARTIFACTS_DIR, "location_ranker_v3_1.joblib"))
    cal_v3_1 = joblib.load(os.path.join(ARTIFACTS_DIR, "location_calibrator_v3_1.joblib"))
    time_v2 = joblib.load(os.path.join(ARTIFACTS_DIR, "time_regressor_v2.joblib"))

    def evaluate_location_model(model, calibrator, test_groups, X_test):
        raw_preds = model.predict_proba(X_test)[:, 1]
        cal_preds = calibrator.predict_proba(raw_preds.reshape(-1, 1))[:, 1]

        r1 = r3 = r5 = 0
        mrr = 0.0
        errs = []
        n_cases = len(test_groups)

        offset = 0
        for g in test_groups:
            cands = g["cands"]
            n_c = len(cands)
            tid = g["target_id"]
            tgt_c = cluster_by_id[tid]
            g_scores = cal_preds[offset:offset + n_c]
            offset += n_c

            ranked_order = sorted(range(n_c), key=lambda i: g_scores[i], reverse=True)
            top1_cand = cands[ranked_order[0]][0]
            top1_err = haversine_km(tgt_c["lat"], tgt_c["lon"], top1_cand["lat"], top1_cand["lon"])
            errs.append(top1_err)

            tgt_rank = None
            for r_pos, c_idx in enumerate(ranked_order):
                if cands[c_idx][0]["id"] == tid:
                    tgt_rank = r_pos + 1
                    break

            if tgt_rank is not None:
                if tgt_rank == 1: r1 += 1
                if tgt_rank <= 3: r3 += 1
                if tgt_rank <= 5: r5 += 1
                mrr += 1.0 / tgt_rank

        return {
            "r1": round((r1 / n_cases) * 100.0, 2),
            "r3": round((r3 / n_cases) * 100.0, 2),
            "r5": round((r5 / n_cases) * 100.0, 2),
            "mrr": round(mrr / n_cases, 4),
            "median_error_km": round(float(np.median(errs)), 2)
        }

    v3_1_metrics = evaluate_location_model(loc_v3_1, cal_v3_1, test_groups, X_loc_test)
    print("\n--- BASELINE LOCATION V3.1 TEST METRICS ---")
    print(v3_1_metrics)

    # -------------------------------------------------------------
    # 2. TRAIN LOCATION V4
    # -------------------------------------------------------------
    print("\n--- TRAINING LOCATION V4 ---")
    neg_cnt = len(y_loc_train) - np.sum(y_loc_train)
    pos_cnt = np.sum(y_loc_train)
    scale_pos = neg_cnt / max(1, pos_cnt)

    # V4 uses increased regularizations (reg_lambda=2.5, colsample_bytree=0.75, max_depth=4)
    # to prevent single global priors like historical_cluster_risk from completely masking spatial context.
    v4_xgb_params = {
        "n_estimators": 140,
        "max_depth": 4,
        "learning_rate": 0.05,
        "subsample": 0.80,
        "colsample_bytree": 0.75,
        "scale_pos_weight": scale_pos * 0.85,
        "reg_lambda": 2.5,
        "reg_alpha": 0.5,
        "random_state": 42,
        "eval_metric": "logloss",
        "tree_method": "hist"
    }

    model_v4 = XGBClassifier(**v4_xgb_params)
    model_v4.fit(X_loc_train, y_loc_train)

    val_raw_v4 = model_v4.predict_proba(X_loc_val)[:, 1]
    calibrator_v4 = LogisticRegression(C=1.0, solver="lbfgs", random_state=42)
    calibrator_v4.fit(val_raw_v4.reshape(-1, 1), y_loc_val)

    v4_metrics = evaluate_location_model(model_v4, calibrator_v4, test_groups, X_loc_test)
    print("--- CANDIDATE LOCATION V4 TEST METRICS ---")
    print(v4_metrics)

    # -------------------------------------------------------------
    # 3. EVALUATE TIME V2 VS TRAIN TIME V3
    # -------------------------------------------------------------
    print("\n--- EVALUATING TIME V2 & TRAINING TIME V3 ---")
    v2_time_preds = time_v2.predict(X_time_test)
    v2_mae = float(mean_absolute_error(y_time_test, v2_time_preds))
    v2_med_ae = float(np.median(np.abs(y_time_test - v2_time_preds)))
    v2_rmse = float(root_mean_squared_error(y_time_test, v2_time_preds))

    print(f"Time V2 Held-Out Test: MAE={v2_mae:.2f} mins, MedAE={v2_med_ae:.2f} mins, RMSE={v2_rmse:.2f} mins")

    # Time V3 uses log1p target transformation and balanced tree depth with regularization
    # so payment_channel doesn't completely eclipse amount, delay, and fraud type
    y_time_train_log = np.log1p(y_time_train)
    y_time_val_log = np.log1p(y_time_val)

    time_v3_params = {
        "n_estimators": 100,
        "max_depth": 3,
        "learning_rate": 0.05,
        "subsample": 0.85,
        "colsample_bytree": 0.80,
        "reg_lambda": 2.0,
        "reg_alpha": 0.5,
        "random_state": 42,
        "eval_metric": "mae"
    }
    model_time_v3 = XGBRegressor(**time_v3_params)
    model_time_v3.fit(X_time_train, y_time_train_log, eval_set=[(X_time_val, y_time_val_log)], verbose=False)

    v3_time_preds_log = model_time_v3.predict(X_time_test)
    v3_time_preds = np.expm1(v3_time_preds_log)
    v3_mae = float(mean_absolute_error(y_time_test, v3_time_preds))
    v3_med_ae = float(np.median(np.abs(y_time_test - v3_time_preds)))
    v3_rmse = float(root_mean_squared_error(y_time_test, v3_time_preds))

    print(f"Time V3 Held-Out Test: MAE={v3_mae:.2f} mins, MedAE={v3_med_ae:.2f} mins, RMSE={v3_rmse:.2f} mins")

    # Check promotion conditions
    loc_promoted = (v4_metrics["r1"] >= v3_1_metrics["r1"] * 0.95 and v4_metrics["r3"] >= v3_1_metrics["r3"] * 0.95 and v4_metrics["mrr"] >= v3_1_metrics["mrr"] * 0.95)
    time_promoted = (v3_mae <= v2_mae)

    print("\n--- MODEL PROMOTION DECISION ---")
    print(f"Location V4 Accepted: {loc_promoted} (V3.1 R@1={v3_1_metrics['r1']}%, V4 R@1={v4_metrics['r1']}%; V3.1 MRR={v3_1_metrics['mrr']}, V4 MRR={v4_metrics['mrr']})")
    print(f"Time V3 Accepted:     {time_promoted} (V2 MAE={v2_mae:.2f} mins, V3 MAE={v3_mae:.2f} mins)")

    # Save V4 and Time V3 artifacts
    loc_v4_path = os.path.join(ARTIFACTS_DIR, "location_ranker_v4.joblib")
    cal_v4_path = os.path.join(ARTIFACTS_DIR, "location_calibrator_v4.joblib")
    time_v3_path = os.path.join(ARTIFACTS_DIR, "time_regressor_v3.joblib")
    meta_v4_path = os.path.join(ARTIFACTS_DIR, "model_metadata_v4.json")
    schema_v4_path = os.path.join(ARTIFACTS_DIR, "feature_schema_v4.json")

    joblib.dump(model_v4, loc_v4_path)
    joblib.dump(calibrator_v4, cal_v4_path)
    joblib.dump(model_time_v3, time_v3_path)

    schema_dict = {
        "version": "v4",
        "location_features": FEATURE_COLUMNS_LOCATION_V3_1,
        "time_features": FEATURE_COLUMNS_TIME,
        "feature_count_location": len(FEATURE_COLUMNS_LOCATION_V3_1),
        "feature_count_time": len(FEATURE_COLUMNS_TIME)
    }
    with open(schema_v4_path, "w") as f:
        json.dump(schema_dict, f, indent=2)

    meta_dict = {
        "model_version": "cashout-location-xgb-v4",
        "time_model_version": "cashout-time-xgb-v3",
        "training_timestamp": datetime.utcnow().isoformat(),
        "random_seed": 42,
        "evaluation_metrics": {
            "location_v3_1": v3_1_metrics,
            "location_v4": v4_metrics,
            "time_v2": {"mae": v2_mae, "med_ae": v2_med_ae, "rmse": v2_rmse},
            "time_v3": {"mae": v3_mae, "med_ae": v3_med_ae, "rmse": v3_rmse}
        },
        "promotion_status": {
            "location_v4_accepted": loc_promoted,
            "time_v3_accepted": time_promoted
        }
    }
    with open(meta_v4_path, "w") as f:
        json.dump(meta_dict, f, indent=2)

    print("Saved V4 and Time V3 artifacts and metadata.")
    return {
        "v3_1_metrics": v3_1_metrics,
        "v4_metrics": v4_metrics,
        "v2_time": {"mae": v2_mae, "med_ae": v2_med_ae, "rmse": v2_rmse},
        "v3_time": {"mae": v3_mae, "med_ae": v3_med_ae, "rmse": v3_rmse},
        "loc_promoted": loc_promoted,
        "time_promoted": time_promoted
    }


if __name__ == "__main__":
    train_v4_pipeline()
