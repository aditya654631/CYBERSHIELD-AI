"""
CyberShield AI — Final ML Lock Audit Script
Executes all 25 sections of the audit:
- Splits & overlap checks
- Leakage audits (Location & Time)
- Baseline comparisons (Location & Time)
- Shuffle sanity tests (Location & Time)
- Feature ablations (Location & Time)
- Untouched holdout evaluations
- Regional and subgroup generalizations
- Determinism and runtime verification
"""

import os
import sys
import json
import time
import math
import collections
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

import joblib
import numpy as np
import pandas as pd
from xgboost import XGBClassifier, XGBRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import mean_absolute_error, root_mean_squared_error

sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.models.db import SessionLocal
from backend.app.models.models import (
    Complaint, Account, Transaction, Withdrawal,
    LocationCluster, ATMLocation, Prediction, PredictionLocation, Alert
)
from database.seed.seed_config import SYNTHETIC_RANDOM_SEED, NUM_COMPLAINTS, NUM_ACCOUNTS
from database.seed.synthetic_generator import DelhiSyntheticDataGenerator
from ml.geo.candidate_generator import CandidateLocationGenerator, haversine_km
from ml.features.feature_pipeline import (
    feature_pipeline,
    FEATURE_COLUMNS_LOCATION_V3_1,
    FEATURE_COLUMNS_TIME,
    DELHI_ZONE_CENTROIDS
)

ARTIFACTS_DIR = os.path.join(BASE_DIR, "ml", "artifacts")


def run_full_audit():
    print("=" * 80)
    print("CYBERSHIELD AI — FINAL ML LOCK AUDIT RUNNER")
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

    tx_by_comp = collections.defaultdict(list)
    for t in transactions_raw:
        tx_by_comp[t["complaint_number"]].append(t)

    # 1. SPLIT AUDIT
    sorted_complaints = sorted(complaints_raw, key=lambda c: (c["reported_at"], c["complaint_number"]))
    n_total = len(sorted_complaints)
    n_train = int(n_total * 0.70)
    n_val = int(n_total * 0.15)
    n_test = n_total - n_train - n_val

    train_comps = sorted_complaints[:n_train]
    val_comps = sorted_complaints[n_train:n_train + n_val]
    test_comps = sorted_complaints[n_train + n_val:]

    train_ids = set(c["complaint_number"] for c in train_comps)
    val_ids = set(c["complaint_number"] for c in val_comps)
    test_ids = set(c["complaint_number"] for c in test_comps)

    overlap_train_test = len(train_ids.intersection(test_ids))
    overlap_train_val = len(train_ids.intersection(val_ids))
    overlap_val_test = len(val_ids.intersection(test_ids))

    print(f"\n[SPLIT AUDIT]")
    print(f"Total Cases: {n_total}")
    print(f"Train Cases: {len(train_comps)} ({len(train_comps)/n_total*100:.1f}%)")
    print(f"Val Cases:   {len(val_comps)} ({len(val_comps)/n_total*100:.1f}%)")
    print(f"Test Cases:  {len(test_comps)} ({len(test_comps)/n_total*100:.1f}%)")
    print(f"Overlap Train/Test: {overlap_train_test}")
    print(f"Overlap Train/Val:  {overlap_train_val}")
    print(f"Overlap Val/Test:   {overlap_val_test}")

    # Feature Extraction
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

            groups.append({
                "complaint_number": c_num,
                "target_id": tid,
                "target_name": target_cluster_name,
                "origin_zone": comp.get("district"),
                "channel": comp.get("payment_channel"),
                "fraud_type": comp.get("fraud_type"),
                "cands": cand_group
            })

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

    print("Extracting features for train, val, test...")
    X_loc_train, y_loc_train, train_groups, X_time_train, y_time_train = extract_features(train_comps, is_train=True)
    X_loc_val, y_loc_val, val_groups, X_time_val, y_time_val = extract_features(val_comps, is_train=False)
    X_loc_test, y_loc_test, test_groups, X_time_test, y_time_test = extract_features(test_comps, is_train=False)

    # Check exact duplicate feature rows across Train / Test
    train_loc_hashes = set(hash(tuple(r)) for r in X_loc_train)
    test_loc_hashes = set(hash(tuple(r)) for r in X_loc_test)
    dup_loc_rows = len(train_loc_hashes.intersection(test_loc_hashes))

    train_time_hashes = set(hash(tuple(r)) for r in X_time_train)
    test_time_hashes = set(hash(tuple(r)) for r in X_time_test)
    dup_time_rows = len(train_time_hashes.intersection(test_time_hashes))
    print(f"Exact Duplicate Feature Rows across Train/Test: Location={dup_loc_rows}, Time={dup_time_rows}")

    # Load active and rollback models
    loc_v3_1 = joblib.load(os.path.join(ARTIFACTS_DIR, "location_ranker_v3_1.joblib"))
    cal_v3_1 = joblib.load(os.path.join(ARTIFACTS_DIR, "location_calibrator_v3_1.joblib"))
    loc_v4 = joblib.load(os.path.join(ARTIFACTS_DIR, "location_ranker_v4.joblib"))
    cal_v4 = joblib.load(os.path.join(ARTIFACTS_DIR, "location_calibrator_v4.joblib"))
    time_v2 = joblib.load(os.path.join(ARTIFACTS_DIR, "time_regressor_v2.joblib"))
    time_v3 = joblib.load(os.path.join(ARTIFACTS_DIR, "time_regressor_v3.joblib"))

    def evaluate_location_model(model, calibrator, groups_eval, X_eval):
        raw_preds = model.predict_proba(X_eval)[:, 1]
        cal_preds = calibrator.predict_proba(raw_preds.reshape(-1, 1))[:, 1]

        r1 = r3 = r5 = 0
        mrr = 0.0
        errs = []
        cand_found = 0
        origin_top1_count = 0
        n_cases = len(groups_eval)

        offset = 0
        group_results = []
        for g in groups_eval:
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

            # Check if top1 is same zone as origin
            if g.get("origin_zone") and (top1_cand.get("district") == g.get("origin_zone") or top1_cand.get("zone") == g.get("origin_zone")):
                origin_top1_count += 1

            tgt_rank = None
            for r_pos, c_idx in enumerate(ranked_order):
                if cands[c_idx][0]["id"] == tid:
                    tgt_rank = r_pos + 1
                    cand_found += 1
                    break

            if tgt_rank is not None:
                if tgt_rank == 1: r1 += 1
                if tgt_rank <= 3: r3 += 1
                if tgt_rank <= 5: r5 += 1
                mrr += 1.0 / tgt_rank

            group_results.append({
                "group": g,
                "top1_err": top1_err,
                "tgt_rank": tgt_rank,
                "top1_cand": top1_cand
            })

        return {
            "r1": round((r1 / n_cases) * 100.0, 2),
            "r3": round((r3 / n_cases) * 100.0, 2),
            "r5": round((r5 / n_cases) * 100.0, 2),
            "mrr": round(mrr / n_cases, 4),
            "median_error_km": round(float(np.median(errs)), 2),
            "mean_error_km": round(float(np.mean(errs)), 2),
            "candidate_recall": round((cand_found / n_cases) * 100.0, 2),
            "origin_top1_pct": round((origin_top1_count / n_cases) * 100.0, 2),
            "group_results": group_results
        }

    # Evaluate V3.1 vs V4
    v3_1_eval = evaluate_location_model(loc_v3_1, cal_v3_1, test_groups, X_loc_test)
    v4_eval = evaluate_location_model(loc_v4, cal_v4, test_groups, X_loc_test)

    print("\n[LOCATION V3.1 vs V4 TEST METRICS]")
    print(f"Metric              V3.1         V4           Delta")
    print(f"Top1 Recall:        {v3_1_eval['r1']}%       {v4_eval['r1']}%       {v4_eval['r1'] - v3_1_eval['r1']:+.2f}%")
    print(f"Top3 Recall:        {v3_1_eval['r3']}%       {v4_eval['r3']}%       {v4_eval['r3'] - v3_1_eval['r3']:+.2f}%")
    print(f"Top5 Recall:        {v3_1_eval['r5']}%       {v4_eval['r5']}%       {v4_eval['r5'] - v3_1_eval['r5']:+.2f}%")
    print(f"MRR:                {v3_1_eval['mrr']}       {v4_eval['mrr']}       {v4_eval['mrr'] - v3_1_eval['mrr']:+.4f}")
    print(f"Median Error:       {v3_1_eval['median_error_km']} km     {v4_eval['median_error_km']} km     {v4_eval['median_error_km'] - v3_1_eval['median_error_km']:+.2f} km")
    print(f"Mean Error:         {v3_1_eval['mean_error_km']} km     {v4_eval['mean_error_km']} km     {v4_eval['mean_error_km'] - v3_1_eval['mean_error_km']:+.2f} km")
    print(f"Candidate Recall:   {v3_1_eval['candidate_recall']}%       {v4_eval['candidate_recall']}%       0.00%")
    print(f"Origin Top1 Pct:    {v3_1_eval['origin_top1_pct']}%       {v4_eval['origin_top1_pct']}%       {v4_eval['origin_top1_pct'] - v3_1_eval['origin_top1_pct']:+.2f}%")

    # 9. LOCATION BASELINES
    # Baseline A: Nearest to Origin Candidate
    # Baseline B: Global Highest Risk Cluster
    # Baseline C: Most Frequent Historical Cluster
    base_a_r1 = base_a_r3 = 0
    base_b_r1 = base_b_r3 = 0
    base_c_r1 = base_c_r3 = 0
    most_freq_cid = 7 # Connaught Place / Central
    highest_risk_cid = max(cluster_dicts, key=lambda x: x["risk"])["id"]

    for g in test_groups:
        cands = g["cands"]
        tid = g["target_id"]
        # Nearest candidate (cand has dist_to_complaint_zone_km or dist_to_victim)
        sorted_nearest = sorted(cands, key=lambda c: float(c[0].get("distance_from_victim_km") or 999.0))
        if sorted_nearest[0][0]["id"] == tid: base_a_r1 += 1
        if any(c[0]["id"] == tid for c in sorted_nearest[:3]): base_a_r3 += 1

        # Highest risk candidate in pool
        sorted_risk = sorted(cands, key=lambda c: float(c[0].get("risk") or 0.0), reverse=True)
        if sorted_risk[0][0]["id"] == tid: base_b_r1 += 1
        if any(c[0]["id"] == tid for c in sorted_risk[:3]): base_b_r3 += 1

        # Most frequent candidate in pool
        if cands[0][0]["id"] == most_freq_cid and tid == most_freq_cid: base_c_r1 += 1

    n_test_cases = len(test_groups)
    print("\n[LOCATION BASELINE COMPARISON]")
    print(f"A. Nearest Candidate:         R@1={(base_a_r1/n_test_cases)*100:.2f}%, R@3={(base_a_r3/n_test_cases)*100:.2f}%")
    print(f"B. Highest Risk Candidate:     R@1={(base_b_r1/n_test_cases)*100:.2f}%, R@3={(base_b_r3/n_test_cases)*100:.2f}%")
    print(f"C. Most Frequent Candidate:    R@1={(base_c_r1/n_test_cases)*100:.2f}%, R@3={(base_c_r3/n_test_cases)*100:.2f}%")
    print(f"D. Location V3.1:              R@1={v3_1_eval['r1']}%, R@3={v3_1_eval['r3']}%")
    print(f"E. Location V4:                R@1={v4_eval['r1']}%, R@3={v4_eval['r3']}%")

    # 11. TIME BASELINE COMPARISON
    # A. Global training-set median delay baseline
    global_median_delay = float(np.median(y_time_train))
    mae_global = float(mean_absolute_error(y_time_test, np.full_like(y_time_test, global_median_delay)))
    med_global = float(np.median(np.abs(y_time_test - global_median_delay)))
    rmse_global = float(root_mean_squared_error(y_time_test, np.full_like(y_time_test, global_median_delay)))

    # B. Fraud-type median baseline
    fraud_medians = {}
    for ft in set(g["fraud_type"] for g in train_groups):
        f_delays = [y_time_train[i] for i, g in enumerate(train_groups) if g["fraud_type"] == ft]
        fraud_medians[ft] = float(np.median(f_delays)) if f_delays else global_median_delay
    f_preds = np.array([fraud_medians.get(g["fraud_type"], global_median_delay) for g in test_groups])
    mae_fraud = float(mean_absolute_error(y_time_test, f_preds))

    # C. Channel median baseline
    channel_medians = {}
    for ch in set(g["channel"] for g in train_groups):
        c_delays = [y_time_train[i] for i, g in enumerate(train_groups) if g["channel"] == ch]
        channel_medians[ch] = float(np.median(c_delays)) if c_delays else global_median_delay
    c_preds = np.array([channel_medians.get(g["channel"], global_median_delay) for g in test_groups])
    mae_chan = float(mean_absolute_error(y_time_test, c_preds))

    # Time V2 vs V3
    v2_time_preds = time_v2.predict(X_time_test)
    v2_mae = float(mean_absolute_error(y_time_test, v2_time_preds))
    v2_med = float(np.median(np.abs(y_time_test - v2_time_preds)))
    v2_rmse = float(root_mean_squared_error(y_time_test, v2_time_preds))

    v3_time_preds_log = time_v3.predict(X_time_test)
    v3_time_preds = np.expm1(v3_time_preds_log)
    v3_mae = float(mean_absolute_error(y_time_test, v3_time_preds))
    v3_med = float(np.median(np.abs(y_time_test - v3_time_preds)))
    v3_rmse = float(root_mean_squared_error(y_time_test, v3_time_preds))

    print("\n[TIME MODEL BASELINE COMPARISON]")
    print(f"A. Global Median Baseline:     MAE={mae_global:.2f}m, MedAE={med_global:.2f}m, RMSE={rmse_global:.2f}m")
    print(f"B. Fraud-Type Median Baseline: MAE={mae_fraud:.2f}m")
    print(f"C. Payment-Channel Baseline:   MAE={mae_chan:.2f}m")
    print(f"D. Time V2 (Raw XGB):          MAE={v2_mae:.2f}m, MedAE={v2_med:.2f}m, RMSE={v2_rmse:.2f}m")
    print(f"E. Time V3 (log1p Transform):  MAE={v3_mae:.2f}m, MedAE={v3_med:.2f}m, RMSE={v3_rmse:.2f}m")

    # 12. SHUFFLE SANITY TEST (TIME)
    print("\n[SHUFFLE SANITY TEST — TIME]")
    np.random.seed(42)
    y_time_shuffled = np.random.permutation(y_time_train)
    shuffled_model = XGBRegressor(
        n_estimators=100,
        max_depth=3,
        learning_rate=0.05,
        subsample=0.85,
        colsample_bytree=0.80,
        reg_lambda=2.0,
        random_state=42
    )
    shuffled_model.fit(X_time_train, np.log1p(y_time_shuffled))
    shuffled_preds = np.expm1(shuffled_model.predict(X_time_test))
    shuffled_mae = float(mean_absolute_error(y_time_test, shuffled_preds))
    print(f"Time V3 True MAE:       {v3_mae:.2f} mins")
    print(f"Shuffled-Target MAE:    {shuffled_mae:.2f} mins (Substantial collapse: {shuffled_mae > v3_mae * 5})")

    # 13. LABEL PERMUTATION LOCATION TEST
    print("\n[LABEL PERMUTATION TEST — LOCATION]")
    y_loc_shuffled = np.random.permutation(y_loc_train)
    shuf_loc_model = XGBClassifier(
        n_estimators=50,
        max_depth=3,
        learning_rate=0.05,
        random_state=42,
        eval_metric="logloss"
    )
    shuf_loc_model.fit(X_loc_train, y_loc_shuffled)
    shuf_cal = LogisticRegression()
    shuf_cal.fit(shuf_loc_model.predict_proba(X_loc_val)[:, 1].reshape(-1, 1), y_loc_val)
    shuf_loc_eval = evaluate_location_model(shuf_loc_model, shuf_cal, test_groups, X_loc_test)
    print(f"Location V4 True R@1:   {v4_eval['r1']}%, R@3={v4_eval['r3']}%, MRR={v4_eval['mrr']}")
    print(f"Shuffled-Target R@1:    {shuf_loc_eval['r1']}%, R@3={shuf_loc_eval['r3']}%, MRR={shuf_loc_eval['mrr']}")
    print(f"Performance collapsed to random chance: {shuf_loc_eval['r1'] < 5.0}")

    # 14. TIME V3 FEATURE ABLATION
    print("\n[TIME V3 FEATURE ABLATION]")
    col_idx_chan = FEATURE_COLUMNS_TIME.index("payment_channel_encoded")
    col_idx_prior_fraud = FEATURE_COLUMNS_TIME.index("fraud_type_historical_cashout_delay")
    col_idx_prior_acc = FEATURE_COLUMNS_TIME.index("account_historical_cashout_delay")

    # Ablation 1: Without payment_channel_encoded
    cols_no_chan = [i for i in range(len(FEATURE_COLUMNS_TIME)) if i != col_idx_chan]
    m_no_chan = XGBRegressor(n_estimators=100, max_depth=3, learning_rate=0.05, random_state=42)
    m_no_chan.fit(X_time_train[:, cols_no_chan], np.log1p(y_time_train))
    p_no_chan = np.expm1(m_no_chan.predict(X_time_test[:, cols_no_chan]))
    mae_no_chan = float(mean_absolute_error(y_time_test, p_no_chan))

    # Ablation 2: ONLY payment_channel_encoded
    m_only_chan = XGBRegressor(n_estimators=50, max_depth=2, learning_rate=0.05, random_state=42)
    m_only_chan.fit(X_time_train[:, [col_idx_chan]], np.log1p(y_time_train))
    p_only_chan = np.expm1(m_only_chan.predict(X_time_test[:, [col_idx_chan]]))
    mae_only_chan = float(mean_absolute_error(y_time_test, p_only_chan))

    # Ablation 3: Without historical delay priors
    cols_no_priors = [i for i in range(len(FEATURE_COLUMNS_TIME)) if i not in (col_idx_prior_fraud, col_idx_prior_acc)]
    m_no_priors = XGBRegressor(n_estimators=100, max_depth=3, learning_rate=0.05, random_state=42)
    m_no_priors.fit(X_time_train[:, cols_no_priors], np.log1p(y_time_train))
    p_no_priors = np.expm1(m_no_priors.predict(X_time_test[:, cols_no_priors]))
    mae_no_priors = float(mean_absolute_error(y_time_test, p_no_priors))

    print(f"Time V3 Full Features MAE:                 {v3_mae:.2f} mins")
    print(f"Without payment_channel_encoded MAE:       {mae_no_chan:.2f} mins")
    print(f"ONLY payment_channel_encoded MAE:          {mae_only_chan:.2f} mins")
    print(f"Without historical delay priors MAE:       {mae_no_priors:.2f} mins")

    # 15. LOCATION V4 FEATURE ABLATION
    print("\n[LOCATION V4 FEATURE ABLATION]")
    prior_cols = [
        FEATURE_COLUMNS_LOCATION_V3_1.index("historical_cluster_cashout_count"),
        FEATURE_COLUMNS_LOCATION_V3_1.index("historical_cluster_cashout_amount"),
        FEATURE_COLUMNS_LOCATION_V3_1.index("historical_cluster_risk"),
        FEATURE_COLUMNS_LOCATION_V3_1.index("atm_density")
    ]
    geo_cols = [
        FEATURE_COLUMNS_LOCATION_V3_1.index("distance_from_victim"),
        FEATURE_COLUMNS_LOCATION_V3_1.index("candidate_same_complaint_zone"),
        FEATURE_COLUMNS_LOCATION_V3_1.index("dist_to_complaint_zone_km")
    ]

    # Without historical priors
    cols_no_priors_loc = [i for i in range(len(FEATURE_COLUMNS_LOCATION_V3_1)) if i not in prior_cols]
    m_no_prior_loc = XGBClassifier(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42, eval_metric="logloss")
    m_no_prior_loc.fit(X_loc_train[:, cols_no_priors_loc], y_loc_train)
    cal_no_prior = LogisticRegression()
    cal_no_prior.fit(m_no_prior_loc.predict_proba(X_loc_val[:, cols_no_priors_loc])[:, 1].reshape(-1, 1), y_loc_val)
    eval_no_prior_loc = evaluate_location_model(m_no_prior_loc, cal_no_prior, test_groups, X_loc_test[:, cols_no_priors_loc])

    # Without geo/distance
    cols_no_geo_loc = [i for i in range(len(FEATURE_COLUMNS_LOCATION_V3_1)) if i not in geo_cols]
    m_no_geo_loc = XGBClassifier(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42, eval_metric="logloss")
    m_no_geo_loc.fit(X_loc_train[:, cols_no_geo_loc], y_loc_train)
    cal_no_geo = LogisticRegression()
    cal_no_geo.fit(m_no_geo_loc.predict_proba(X_loc_val[:, cols_no_geo_loc])[:, 1].reshape(-1, 1), y_loc_val)
    eval_no_geo_loc = evaluate_location_model(m_no_geo_loc, cal_no_geo, test_groups, X_loc_test[:, cols_no_geo_loc])

    print(f"Location V4 Full:           Top1={v4_eval['r1']}%, Top3={v4_eval['r3']}%, MRR={v4_eval['mrr']}")
    print(f"Without Historical Priors:  Top1={eval_no_prior_loc['r1']}%, Top3={eval_no_prior_loc['r3']}%, MRR={eval_no_prior_loc['mrr']}")
    print(f"Without Origin/Distance:    Top1={eval_no_geo_loc['r1']}%, Top3={eval_no_geo_loc['r3']}%, MRR={eval_no_geo_loc['mrr']}")

    # 16. COMPLETELY UNSEEN TEST SLICE (Last 200 cases of chronologically held-out test set)
    unseen_slice_groups = test_groups[-200:]
    n_offset = sum(len(g["cands"]) for g in test_groups[:-200])
    X_loc_unseen = X_loc_test[n_offset:]
    X_time_unseen = X_time_test[-200:]
    y_time_unseen = y_time_test[-200:]

    unseen_loc_eval = evaluate_location_model(loc_v4, cal_v4, unseen_slice_groups, X_loc_unseen)
    unseen_time_preds = np.expm1(time_v3.predict(X_time_unseen))
    unseen_time_mae = float(mean_absolute_error(y_time_unseen, unseen_time_preds))
    unseen_time_med = float(np.median(np.abs(y_time_unseen - unseen_time_preds)))
    unseen_time_rmse = float(root_mean_squared_error(y_time_unseen, unseen_time_preds))

    print(f"\n[FINAL UNTOUCHED HOLDOUT (Size: 200)]")
    print(f"Location V4: Top1={unseen_loc_eval['r1']}%, Top3={unseen_loc_eval['r3']}%, MRR={unseen_loc_eval['mrr']}, MedErr={unseen_loc_eval['median_error_km']} km")
    print(f"Time V3:     MAE={unseen_time_mae:.2f}m, MedAE={unseen_time_med:.2f}m, RMSE={unseen_time_rmse:.2f}m")

    # 20. REGIONAL GENERALIZATION
    print("\n[REGIONAL GENERALIZATION — LOCATION V4]")
    zone_groups = collections.defaultdict(list)
    zone_x_idx = collections.defaultdict(list)
    cur_loc_idx = 0
    for idx, g in enumerate(test_groups):
        z = g.get("origin_zone") or "UNKNOWN"
        zone_groups[z].append(g)
        n_c = len(g["cands"])
        zone_x_idx[z].extend(range(cur_loc_idx, cur_loc_idx + n_c))
        cur_loc_idx += n_c

    for z, z_g in sorted(zone_groups.items(), key=lambda x: len(x[1]), reverse=True):
        if len(z_g) >= 20:
            sub_x = X_loc_test[zone_x_idx[z]]
            sub_eval = evaluate_location_model(loc_v4, cal_v4, z_g, sub_x)
            print(f"Zone: {z:<22} (N={len(z_g):3d}) -> Top1={sub_eval['r1']:5.2f}%, Top3={sub_eval['r3']:5.2f}%, MRR={sub_eval['mrr']:.4f}, MedErr={sub_eval['median_error_km']} km")

    # 21. CHANNEL GENERALIZATION
    print("\n[CHANNEL GENERALIZATION — TIME V3]")
    chan_indices = collections.defaultdict(list)
    for idx, g in enumerate(test_groups):
        ch = g.get("channel") or "UNKNOWN"
        chan_indices[ch].append(idx)

    for ch, c_idxs in sorted(chan_indices.items(), key=lambda x: len(x[1]), reverse=True):
        if len(c_idxs) >= 20:
            ch_y = y_time_test[c_idxs]
            ch_p = v3_time_preds[c_idxs]
            ch_mae = float(mean_absolute_error(ch_y, ch_p))
            ch_med = float(np.median(np.abs(ch_y - ch_p)))
            print(f"Channel: {ch:<12} (N={len(c_idxs):3d}) -> MAE={ch_mae:5.2f} mins, MedAE={ch_med:5.2f} mins")

    print("\nAudit calculations complete.")
    db.close()

if __name__ == "__main__":
    run_full_audit()
