"""
CyberShield AI — Phase B.6: Blockchain-Augmented Shadow Geo Re-Ranker
Model: cashout-blockchain-shadow-xgb-v1
Feature Schema: blockchain-feature-schema-v1

Trains and qualifies a SECOND-STAGE learned re-ranker on top of V7-compat candidates,
incorporating pre-outcome consortium intelligence from Hyperledger Fabric.

Strict Gates:
1. Feature Parity: Derives exclusively from frozen blockchain-feature-schema-v1 contract
2. Anti-Leakage: All signals strictly causal and pre-outcome (t_event <= T_ref)
3. Ablation Gate: Top-3_C - Top-3_B >= +1.0 pp combined
4. Regime Safety: No holdout regime drops > 0.5 pp vs V7
5. Zero Disruption: Production request path and official V7 prediction untouched
"""

import os
import sys
import json
import time
import math
import argparse
import hashlib
import collections
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, Optional

import joblib
import pickle
import numpy as np
import pandas as pd
from xgboost import XGBClassifier, XGBRanker
from sklearn.linear_model import LogisticRegression

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.models.db import SessionLocal
from backend.app.models.models import LocationCluster, ATMLocation
from database.seed.synthetic_generator import DelhiSyntheticDataGenerator
from ml.geo.candidate_generator import CandidateLocationGenerator, haversine_km
from ml.features.feature_pipeline import feature_pipeline
from ml.features.blockchain_feature_extractor import (
    extract_candidate_blockchain_features,
    ORDERED_BLOCKCHAIN_FEATURES,
    CONTRACT_SPEC
)
from ml.training.blockchain_signal_generator import CausalBlockchainSignalGenerator

ARTIFACTS_DIR = os.path.join(BASE_DIR, "ml", "artifacts")
DATA_DIR = os.path.join(BASE_DIR, "ml", "data")

V7_CANDIDATE_FEATURES = [
    "v7_candidate_score",
    "v7_candidate_rank_normalized",
    "v7_candidate_percentile",
    "v7_score_gap_from_candidate1",
    "distance_to_victim_km",
    "cluster_base_risk",
    "cluster_atm_density"
]

ALL_SHADOW_FEATURES = V7_CANDIDATE_FEATURES + ORDERED_BLOCKCHAIN_FEATURES + ["fabric_available"]


def load_delhi_clusters() -> List[Dict[str, Any]]:
    cache_path = os.path.join(DATA_DIR, "delhi_clusters_cache.pkl")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "rb") as f:
                return pickle.load(f)
        except Exception:
            pass

    try:
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
        db.close()
        with open(cache_path, "wb") as f:
            pickle.dump(cluster_dicts, f)
        return cluster_dicts
    except Exception as e:
        print(f"Error connecting to database ({e}), check cache.")
        if os.path.exists(cache_path):
            with open(cache_path, "rb") as f:
                return pickle.load(f)
        raise


def generate_legacy_cases(seed: int, num_cases: int, cluster_dicts: List[Dict[str, Any]], tag: str) -> List[Dict[str, Any]]:
    cache_path = os.path.join(DATA_DIR, f"legacy_cases_{seed}_{num_cases}.pkl")
    if os.path.exists(cache_path):
        print(f"Loading cached legacy cases from {cache_path} ({tag})...")
        with open(cache_path, "rb") as f:
            return joblib.load(cache_path)

    print(f"Generating {num_cases} Legacy cases with seed {seed} ({tag})...")
    atm_cache_path = os.path.join(DATA_DIR, "delhi_atms_cache.pkl")
    atm_dicts = None
    if os.path.exists(atm_cache_path):
        try:
            with open(atm_cache_path, "rb") as f:
                atm_dicts = pickle.load(f)
        except Exception:
            pass

    if atm_dicts is None:
        db = SessionLocal()
        delhi_atms = db.query(ATMLocation).filter(ATMLocation.atm_code.like("ATM-DL-%")).all()
        atm_dicts = [
            {
                "atm_code": a.atm_code,
                "bank_name": a.bank_name,
                "cluster_name": [c["name"] for c in cluster_dicts if c["id"] == a.cluster_id][0],
                "id": a.id
            }
            for a in delhi_atms
        ]
        db.close()
        with open(atm_cache_path, "wb") as f:
            pickle.dump(atm_dicts, f)

    gen = DelhiSyntheticDataGenerator(seed)
    gen_count = int(num_cases * 1.45)
    ds = gen.generate_dataset(cluster_dicts, atm_dicts, num_complaints=gen_count, num_accounts=gen_count * 2)

    complaints_raw = ds["complaints"]
    transactions_raw = ds["transactions"]
    accounts_map = {a["account_number"]: a for a in ds["accounts"]}
    withdrawals_map = {w["complaint_number"]: w for w in ds["withdrawals"]}

    tx_by_comp = collections.defaultdict(list)
    for t in transactions_raw:
        tx_by_comp[t["complaint_number"]].append(t)

    cases = []
    for comp in complaints_raw:
        c_num = comp["complaint_number"]
        if c_num not in withdrawals_map:
            continue
        wdl = withdrawals_map[c_num]
        target_id = [c["id"] for c in cluster_dicts if c["name"] == wdl["target_cluster_name"]][0]

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

        cases.append({
            "complaint": comp,
            "transactions": comp_txs,
            "terminal_zone": term_z,
            "all_tx_zones": all_z,
            "target_cluster_id": target_id,
            "source": tag
        })
        if len(cases) >= num_cases:
            break

    joblib.dump(cases, cache_path)
    return cases


def load_tabular_split_cases(csv_path: str, source_name: str, split_name: str, n_cases: int, seed: int) -> List[Dict[str, Any]]:
    print(f"Loading {source_name} ({split_name}, n={n_cases}, seed={seed}) from {csv_path}...")
    df = pd.read_csv(csv_path)
    split_df = df[df["split"] == split_name]
    sample_df = split_df.sample(n=min(n_cases, len(split_df)), random_state=seed)

    cases = []
    for _, row in sample_df.iterrows():
        comp = {
            "complaint_number": row["case_id"],
            "fraud_type": row["fraud_type"],
            "payment_channel": row["payment_channel"],
            "amount": float(row["amount"]),
            "reported_at": row["reported_at"],
            "victim_district": row["victim_district"],
            "victim_lat": float(row["victim_lat"]),
            "victim_lon": float(row["victim_lon"])
        }
        term_z = str(row["terminal_mule_district"]) if pd.notna(row["terminal_mule_district"]) else None
        all_z = {str(row["victim_district"])}
        if term_z:
            all_z.add(term_z)
        if pd.notna(row.get("dominant_account_district")):
            all_z.add(str(row["dominant_account_district"]))

        cases.append({
            "complaint": comp,
            "transactions": None,
            "terminal_zone": term_z,
            "all_tx_zones": all_z,
            "target_cluster_id": int(row["realized_cashout_cluster_id"]),
            "source": source_name
        })
    return cases


def extract_features_and_rankings(
    cases: List[Dict[str, Any]],
    cluster_dicts: List[Dict[str, Any]],
    cand_gen: CandidateLocationGenerator,
    v4_model,
    v4_calibrator,
    v7_model,
    v7_calibrator,
    signal_generator: CausalBlockchainSignalGenerator,
    fabric_available: bool = True,
    is_train: bool = False
):
    """
    Extracts Model B (V7-only) and Model C (V7 + Blockchain) candidate feature matrices.
    """
    cluster_by_id = {c["id"]: c for c in cluster_dicts}

    X_b_list = []
    X_c_list = []
    y_list = []
    q_sizes = []
    case_results = []

    for case in cases:
        comp = case["complaint"]
        txs = case.get("transactions")
        term_z = case.get("terminal_zone")
        all_z = case.get("all_tx_zones")
        tid = case["target_cluster_id"]

        # 1. Top-25 candidates from candidate generator
        cands = cand_gen.generate_candidates_for_complaint(
            complaint=comp,
            top_k=25,
            transactions=txs,
            terminal_zone=term_z,
            all_tx_zones=all_z
        )
        cand_ids = [c["id"] for c in cands]
        if is_train and tid not in cand_ids:
            if tid in cluster_by_id:
                cands.append(cluster_by_id[tid])

        K = len(cands)
        q_sizes.append(K)

        # 2. V7 Base & Compatibility Scoring
        X_base, _, _, _ = feature_pipeline.build_candidate_matrix_v3_1(
            complaint=comp,
            candidates=cands,
            transactions=txs,
            graph_metrics={},
            terminal_zone=term_z,
            all_tx_zones=all_z
        )

        raw_v4 = v4_model.predict_proba(X_base)[:, 1]
        cal_v4 = v4_calibrator.predict_proba(raw_v4.reshape(-1, 1))[:, 1]
        v4_rank_orders = np.argsort(np.argsort(-cal_v4))
        max_v4_score = float(np.max(cal_v4)) if K > 0 else 0.0

        v7_rows = []
        for idx in range(K):
            v4_score = float(cal_v4[idx])
            v4_rank_norm = float(v4_rank_orders[idx]) / max(1.0, float(K - 1))
            v4_percentile = 1.0 - v4_rank_norm
            v4_score_gap = max_v4_score - v4_score
            v7_rows.append(np.append(X_base[idx], [v4_score, v4_rank_norm, v4_percentile, v4_score_gap]))

        X_v7 = np.array(v7_rows, dtype=np.float32)

        if hasattr(v7_model, "predict_proba"):
            raw_v7 = v7_model.predict_proba(X_v7)[:, 1]
        else:
            raw_v7 = v7_model.predict(X_v7)
        cal_v7 = v7_calibrator.predict_proba(raw_v7.reshape(-1, 1))[:, 1]

        v7_rank_orders = np.argsort(np.argsort(-cal_v7))
        max_v7_score = float(np.max(cal_v7)) if K > 0 else 0.0

        # 3. Generate causal pre-outcome blockchain signals
        if fabric_available:
            c_sigs, s_sigs = signal_generator.generate_pre_outcome_signals(
                complaint=comp,
                candidate_clusters=cands,
                all_delhi_clusters=cluster_dicts,
                terminal_zone=term_z,
                all_tx_zones=all_z,
                transactions=txs
            )
        else:
            c_sigs, s_sigs = None, None

        v_lat_raw = comp.get("victim_lat")
        v_lon_raw = comp.get("victim_lon")
        v_lat = float(v_lat_raw) if v_lat_raw is not None else 28.6139
        v_lon = float(v_lon_raw) if v_lon_raw is not None else 77.2090

        cand_records = []
        for idx, cand in enumerate(cands):
            cid = cand["id"]
            is_target = 1 if cid == tid else 0
            y_list.append(is_target)

            # Model B Features
            v7_score = float(cal_v7[idx])
            v7_rank_norm = float(v7_rank_orders[idx]) / max(1.0, float(K - 1))
            v7_percentile = 1.0 - v7_rank_norm
            v7_gap = max_v7_score - v7_score
            c_lat = float(cand.get("lat", 28.6139))
            c_lon = float(cand.get("lon", 77.2090))
            dist_km = haversine_km(v_lat, v_lon, c_lat, c_lon)
            base_risk = float(cand.get("base_risk") or cand.get("historical_risk") or cand.get("risk") or 0.50)
            density = float(cand.get("atm_density", 15.0))

            feat_b = [v7_score, v7_rank_norm, v7_percentile, v7_gap, dist_km, base_risk, density]
            X_b_list.append(feat_b)

            # Blockchain Features
            rep_ts = comp.get("reported_at", "2026-09-14T12:00:00.000Z")
            if not isinstance(rep_ts, str):
                rep_ts = rep_ts.isoformat() if hasattr(rep_ts, "isoformat") else "2026-09-14T12:00:00.000Z"

            opaque_subj = s_sigs[0]["opaque_subject_ref"] if (s_sigs and len(s_sigs) > 0) else None
            extracted_bc = extract_candidate_blockchain_features(
                cluster_id=cid,
                reference_timestamp=rep_ts,
                raw_signals=c_sigs,
                opaque_subject_ref=opaque_subj,
                raw_subject_signals=s_sigs,
                fabric_available=fabric_available
            )
            bc_dict = extracted_bc["features"]
            fab_avail = float(extracted_bc["fabric_available"])

            feat_bc_values = [float(bc_dict.get(fname, 0.0)) for fname in ORDERED_BLOCKCHAIN_FEATURES]
            feat_c = feat_b + feat_bc_values + [fab_avail]
            X_c_list.append(feat_c)

            cand_records.append({
                "cluster_id": cid,
                "is_target": is_target,
                "v7_score": v7_score,
                "cand_obj": cand
            })

        case_results.append({
            "target_cluster_id": tid,
            "candidates": cand_records,
            "v7_scores": cal_v7
        })

    X_b_arr = np.array(X_b_list, dtype=np.float32)
    X_c_arr = np.array(X_c_list, dtype=np.float32)
    y_arr = np.array(y_list, dtype=np.int32)
    v7_scores_all = X_b_arr[:, 0]
    eps = 1e-5
    bm_arr = np.log((v7_scores_all + eps) / (1.0 - v7_scores_all + eps)).astype(np.float32)

    return (
        X_b_arr,
        X_c_arr,
        y_arr,
        bm_arr,
        q_sizes,
        case_results
    )


def evaluate_rankings(
    case_results: List[Dict[str, Any]],
    scores: np.ndarray,
    q_sizes: List[int],
    cluster_dicts: List[Dict[str, Any]]
) -> Dict[str, float]:
    cluster_by_id = {c["id"]: c for c in cluster_dicts}
    offset = 0
    top1_hits = 0
    top3_hits = 0
    top5_hits = 0
    rr_sum = 0.0
    spatial_errors = []
    n_cases = len(case_results)

    for i, case in enumerate(case_results):
        K = q_sizes[i]
        case_scores = scores[offset:offset + K]
        offset += K

        cand_records = case["candidates"]
        tid = case["target_cluster_id"]
        true_cluster = cluster_by_id.get(tid)

        ranked_indices = np.argsort(-case_scores)
        target_rank = None
        for r_idx, cand_idx in enumerate(ranked_indices):
            if cand_records[cand_idx]["cluster_id"] == tid:
                target_rank = r_idx + 1
                break

        if target_rank is not None:
            if target_rank == 1:
                top1_hits += 1
            if target_rank <= 3:
                top3_hits += 1
            if target_rank <= 5:
                top5_hits += 1
            rr_sum += 1.0 / target_rank

        # Spatial error to Top-1 predicted cluster
        pred_top1_cid = cand_records[ranked_indices[0]]["cluster_id"]
        pred_cluster = cluster_by_id.get(pred_top1_cid)
        if pred_cluster and true_cluster:
            err_km = haversine_km(
                true_cluster["lat"], true_cluster["lon"],
                pred_cluster["lat"], pred_cluster["lon"]
            )
            spatial_errors.append(err_km)

    return {
        "top1_accuracy": round(top1_hits / max(1, n_cases), 4),
        "top3_accuracy": round(top3_hits / max(1, n_cases), 4),
        "top5_accuracy": round(top5_hits / max(1, n_cases), 4),
        "mrr": round(rr_sum / max(1, n_cases), 4),
        "mean_spatial_error_km": round(float(np.mean(spatial_errors)) if spatial_errors else 0.0, 2),
        "case_count": n_cases
    }


def main():
    parser = argparse.ArgumentParser(description="Phase B.6 Blockchain Shadow Re-Ranker")
    parser.add_argument("--train", action="store_true", help="Train second-stage rankers and evaluate internal ablation")
    parser.add_argument("--evaluate-holdout", action="store_true", help="Evaluate frozen model on qualification holdout seeds 66261, 66262, 66263")
    parser.add_argument("--test-outage", action="store_true", help="Test fabric outage fallback")
    args = parser.parse_args()

    cluster_dicts = load_delhi_clusters()
    cand_gen = CandidateLocationGenerator(cluster_dicts)

    print("Loading base models (V4 & V7-compat)...")
    v4_model = joblib.load(os.path.join(ARTIFACTS_DIR, "location_ranker_v4.joblib"))
    v4_calibrator = joblib.load(os.path.join(ARTIFACTS_DIR, "location_calibrator_v4.joblib"))
    v7_model = joblib.load(os.path.join(ARTIFACTS_DIR, "location_ranker_v7_compat.joblib"))
    v7_calibrator = joblib.load(os.path.join(ARTIFACTS_DIR, "location_calibrator_v7_compat.joblib"))

    sig_gen = CausalBlockchainSignalGenerator(seed=66210)

    if args.train:
        print("\n=======================================================")
        print("  STEP 1: GENERATING BALANCED TRAINING DATA (SEED 66210)")
        print("=======================================================")
        cases_train_legacy = generate_legacy_cases(66210, 3000, cluster_dicts, "train_legacy")
        cases_train_v62 = load_tabular_split_cases(os.path.join(DATA_DIR, "delhi_v6_2_cases.csv.gz"), "v6.2", "train", 2250, seed=66210)
        cases_train_v63 = load_tabular_split_cases(os.path.join(DATA_DIR, "delhi_v6_3_cases.csv.gz"), "v6.3", "train", 2250, seed=66210)
        train_cases = cases_train_legacy + cases_train_v62 + cases_train_v63
        print(f"Total training cases: {len(train_cases)}")

        print("\nExtracting training features for Model B & Model C...")
        X_b_train, X_c_train, y_train, bm_train, q_train, _ = extract_features_and_rankings(
            cases=train_cases,
            cluster_dicts=cluster_dicts,
            cand_gen=cand_gen,
            v4_model=v4_model,
            v4_calibrator=v4_calibrator,
            v7_model=v7_model,
            v7_calibrator=v7_calibrator,
            signal_generator=sig_gen,
            fabric_available=True,
            is_train=True
        )
        print(f"Training matrices: X_b={X_b_train.shape}, X_c={X_c_train.shape}, y={y_train.shape}")

        print("\n=======================================================")
        print("  STEP 2: GENERATING INTERNAL VALIDATION DATA (SEED 66211)")
        print("=======================================================")
        cases_val_legacy = generate_legacy_cases(66211, 600, cluster_dicts, "val_legacy")
        cases_val_v62 = load_tabular_split_cases(os.path.join(DATA_DIR, "delhi_v6_2_cases.csv.gz"), "v6.2", "validation", 450, seed=66211)
        cases_val_v63 = load_tabular_split_cases(os.path.join(DATA_DIR, "delhi_v6_3_cases.csv.gz"), "v6.3", "validation", 450, seed=66211)
        val_cases = cases_val_legacy + cases_val_v62 + cases_val_v63
        print(f"Total internal validation cases: {len(val_cases)}")

        print("\nExtracting internal validation features...")
        X_b_val, X_c_val, y_val, bm_val, q_val, val_case_results = extract_features_and_rankings(
            cases=val_cases,
            cluster_dicts=cluster_dicts,
            cand_gen=cand_gen,
            v4_model=v4_model,
            v4_calibrator=v4_calibrator,
            v7_model=v7_model,
            v7_calibrator=v7_calibrator,
            signal_generator=sig_gen,
            fabric_available=True,
            is_train=False
        )

        print("\n=======================================================")
        print("  STEP 3: TRAINING CANDIDATE MODELS & REQUIRED ABLATION")
        print("=======================================================")

        # Model A: Baseline Official V7-compat
        v7_scores_val = np.concatenate([c["v7_scores"] for c in val_case_results])
        metrics_a = evaluate_rankings(val_case_results, v7_scores_val, q_val, cluster_dicts)
        print(f"Model A (Official V7-compat Baseline): Top-1={metrics_a['top1_accuracy']}, Top-3={metrics_a['top3_accuracy']}, MRR={metrics_a['mrr']}, Spatial Err={metrics_a['mean_spatial_error_km']}km")

        # Model B: Second-Stage on V7 Features Only
        print("\nTraining Model B (V7-feature-only second stage)...")
        spw = math.sqrt(24.0)
        model_b = XGBClassifier(
            n_estimators=120,
            max_depth=4,
            learning_rate=0.08,
            subsample=0.9,
            colsample_bytree=0.9,
            scale_pos_weight=spw,
            eval_metric="logloss",
            random_state=42,
            n_jobs=-1
        )
        model_b.fit(X_b_train, y_train)
        scores_b_val = model_b.predict_proba(X_b_val)[:, 1]
        metrics_b = evaluate_rankings(val_case_results, scores_b_val, q_val, cluster_dicts)
        print(f"Model B (V7 Features Only): Top-1={metrics_b['top1_accuracy']}, Top-3={metrics_b['top3_accuracy']}, MRR={metrics_b['mrr']}, Spatial Err={metrics_b['mean_spatial_error_km']}km")

        # Model C: Second-Stage on V7 + Blockchain Features
        print("\nTraining Model C (V7 + Blockchain Features second stage)...")
        model_c = XGBClassifier(
            n_estimators=120,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.85,
            colsample_bytree=0.80,
            scale_pos_weight=spw,
            eval_metric="logloss",
            random_state=42,
            n_jobs=-1
        )
        model_c.fit(X_c_train, y_train)
        raw_scores_c_train = model_c.predict_proba(X_c_train)[:, 1]
        raw_scores_c_val = model_c.predict_proba(X_c_val)[:, 1]

        # Train Platt Calibrator for Model C
        print("Training Platt Calibrator for Model C...")
        calibrator_c = LogisticRegression()
        calibrator_c.fit(raw_scores_c_train.reshape(-1, 1), y_train)

        scores_c_val = calibrator_c.predict_proba(raw_scores_c_val.reshape(-1, 1))[:, 1]
        metrics_c = evaluate_rankings(val_case_results, scores_c_val, q_val, cluster_dicts)
        print(f"Model C (V7 + Blockchain Features): Top-1={metrics_c['top1_accuracy']}, Top-3={metrics_c['top3_accuracy']}, MRR={metrics_c['mrr']}, Spatial Err={metrics_c['mean_spatial_error_km']}km")

        delta_top3_cb = (metrics_c["top3_accuracy"] - metrics_b["top3_accuracy"]) * 100.0
        delta_top3_ca = (metrics_c["top3_accuracy"] - metrics_a["top3_accuracy"]) * 100.0
        print(f"\n>>> INTERNAL ABLATION DELTA (Model C vs Model B): Top-3 Delta = {delta_top3_cb:+.2f} percentage points")
        print(f">>> V7 GAIN (Model C vs Official V7): Top-3 Delta = {delta_top3_ca:+.2f} percentage points")

        assert delta_top3_cb >= 0.0, f"Ablation Gate Failed on Internal Validation! Delta {delta_top3_cb:+.2f} pp < 0.0 pp"
        print("Internal Validation Ablation Gate: PASS (Positive incremental gain confirmed)")

        # Freeze and Save Model Artifacts
        print("\n=======================================================")
        print("  STEP 4: FREEZING AND SAVING MODEL ARTIFACTS")
        print("=======================================================")
        model_b_path = os.path.join(ARTIFACTS_DIR, "blockchain_shadow_ranker_b_v1.joblib")
        model_path = os.path.join(ARTIFACTS_DIR, "blockchain_shadow_ranker_v1.joblib")
        cal_path = os.path.join(ARTIFACTS_DIR, "blockchain_shadow_calibrator_v1.joblib")
        schema_path = os.path.join(ARTIFACTS_DIR, "blockchain_shadow_feature_schema_v1.json")
        meta_path = os.path.join(ARTIFACTS_DIR, "blockchain_shadow_metadata_v1.json")

        joblib.dump(model_b, model_b_path)
        joblib.dump(model_c, model_path)
        joblib.dump(calibrator_c, cal_path)

        schema_content = {
            "model_name": "cashout-blockchain-shadow-xgb-v1",
            "schema_version": "blockchain-feature-schema-v1",
            "features": ALL_SHADOW_FEATURES,
            "feature_count": len(ALL_SHADOW_FEATURES),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        with open(schema_path, "w", encoding="utf-8") as f:
            json.dump(schema_content, f, indent=2)

        meta_content = {
            "model_name": "cashout-blockchain-shadow-xgb-v1",
            "model_type": "XGBoost_Classifier_Platt_Calibrated",
            "training_seed": 66210,
            "internal_val_seed": 66211,
            "training_cases": len(train_cases),
            "internal_val_cases": len(val_cases),
            "internal_val_metrics": {
                "model_a_v7": metrics_a,
                "model_b_v7_only": metrics_b,
                "model_c_v7_blockchain": metrics_c,
                "delta_c_minus_b_top3_pp": delta_top3_cb,
                "delta_c_minus_a_top3_pp": delta_top3_ca
            },
            "saved_at": datetime.now(timezone.utc).isoformat()
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta_content, f, indent=2)

        print(f"Artifacts successfully saved to {ARTIFACTS_DIR}")


    if args.evaluate_holdout:
        print("\n=======================================================")
        print("  STEP 5: FINAL QUALIFICATION ON FROZEN HOLDOUT SEEDS")
        print("  Seeds: 66261 (Legacy), 66262 (V6.2), 66263 (V6.3)")
        print("=======================================================")

        model_b_path = os.path.join(ARTIFACTS_DIR, "blockchain_shadow_ranker_b_v1.joblib")
        model_path = os.path.join(ARTIFACTS_DIR, "blockchain_shadow_ranker_v1.joblib")
        cal_path = os.path.join(ARTIFACTS_DIR, "blockchain_shadow_calibrator_v1.joblib")
        if not os.path.exists(model_path) or not os.path.exists(cal_path) or not os.path.exists(model_b_path):
            raise FileNotFoundError("Frozen model artifacts not found. Run --train first!")

        shadow_model_b = joblib.load(model_b_path)
        shadow_model_c = joblib.load(model_path)
        shadow_calibrator = joblib.load(cal_path)

        holdout_results = {}

        # 1. Regime 1: Legacy (Seed 66261, 2000 cases)
        print("\n--- Evaluating Regime 1: Legacy (Seed 66261, 2000 cases) ---")
        cases_h1 = generate_legacy_cases(66261, 2000, cluster_dicts, "holdout_legacy_66261")
        X_b_h1, X_c_h1, y_h1, bm_h1, q_h1, res_h1 = extract_features_and_rankings(
            cases=cases_h1, cluster_dicts=cluster_dicts, cand_gen=cand_gen,
            v4_model=v4_model, v4_calibrator=v4_calibrator,
            v7_model=v7_model, v7_calibrator=v7_calibrator,
            signal_generator=sig_gen, fabric_available=True, is_train=False
        )
        scores_v7_h1 = np.concatenate([c["v7_scores"] for c in res_h1])
        m_a_h1 = evaluate_rankings(res_h1, scores_v7_h1, q_h1, cluster_dicts)

        scores_b_h1 = shadow_model_b.predict_proba(X_b_h1)[:, 1]
        m_b_h1 = evaluate_rankings(res_h1, scores_b_h1, q_h1, cluster_dicts)

        raw_c_h1 = shadow_model_c.predict_proba(X_c_h1)[:, 1]
        scores_c_h1 = shadow_calibrator.predict_proba(raw_c_h1.reshape(-1, 1))[:, 1]
        m_c_h1 = evaluate_rankings(res_h1, scores_c_h1, q_h1, cluster_dicts)

        holdout_results["legacy_seed_66261"] = {"model_a_v7": m_a_h1, "model_b_v7_only": m_b_h1, "model_c_blockchain": m_c_h1}
        print(f"Regime 1: Model A Top-3 = {m_a_h1['top3_accuracy']*100:.2f}%, Model B Top-3 = {m_b_h1['top3_accuracy']*100:.2f}%, Model C Top-3 = {m_c_h1['top3_accuracy']*100:.2f}%")
        print(f"         Delta C vs B = {(m_c_h1['top3_accuracy'] - m_b_h1['top3_accuracy'])*100:+.2f} pp | Delta C vs A = {(m_c_h1['top3_accuracy'] - m_a_h1['top3_accuracy'])*100:+.2f} pp")

        # 2. Regime 2: V6.2 (Seed 66262, 1500 cases)
        print("\n--- Evaluating Regime 2: V6.2 (Seed 66262, 1500 cases) ---")
        cases_h2 = load_tabular_split_cases(os.path.join(DATA_DIR, "delhi_v6_2_cases.csv.gz"), "v6.2", "test", 1500, seed=66262)
        X_b_h2, X_c_h2, y_h2, bm_h2, q_h2, res_h2 = extract_features_and_rankings(
            cases=cases_h2, cluster_dicts=cluster_dicts, cand_gen=cand_gen,
            v4_model=v4_model, v4_calibrator=v4_calibrator,
            v7_model=v7_model, v7_calibrator=v7_calibrator,
            signal_generator=sig_gen, fabric_available=True, is_train=False
        )
        scores_v7_h2 = np.concatenate([c["v7_scores"] for c in res_h2])
        m_a_h2 = evaluate_rankings(res_h2, scores_v7_h2, q_h2, cluster_dicts)

        scores_b_h2 = shadow_model_b.predict_proba(X_b_h2)[:, 1]
        m_b_h2 = evaluate_rankings(res_h2, scores_b_h2, q_h2, cluster_dicts)

        raw_c_h2 = shadow_model_c.predict_proba(X_c_h2)[:, 1]
        scores_c_h2 = shadow_calibrator.predict_proba(raw_c_h2.reshape(-1, 1))[:, 1]
        m_c_h2 = evaluate_rankings(res_h2, scores_c_h2, q_h2, cluster_dicts)

        holdout_results["v6_2_seed_66262"] = {"model_a_v7": m_a_h2, "model_b_v7_only": m_b_h2, "model_c_blockchain": m_c_h2}
        print(f"Regime 2: Model A Top-3 = {m_a_h2['top3_accuracy']*100:.2f}%, Model B Top-3 = {m_b_h2['top3_accuracy']*100:.2f}%, Model C Top-3 = {m_c_h2['top3_accuracy']*100:.2f}%")
        print(f"         Delta C vs B = {(m_c_h2['top3_accuracy'] - m_b_h2['top3_accuracy'])*100:+.2f} pp | Delta C vs A = {(m_c_h2['top3_accuracy'] - m_a_h2['top3_accuracy'])*100:+.2f} pp")

        # 3. Regime 3: V6.3 (Seed 66263, 1500 cases)
        print("\n--- Evaluating Regime 3: V6.3 (Seed 66263, 1500 cases) ---")
        cases_h3 = load_tabular_split_cases(os.path.join(DATA_DIR, "delhi_v6_3_cases.csv.gz"), "v6.3", "test", 1500, seed=66263)
        X_b_h3, X_c_h3, y_h3, bm_h3, q_h3, res_h3 = extract_features_and_rankings(
            cases=cases_h3, cluster_dicts=cluster_dicts, cand_gen=cand_gen,
            v4_model=v4_model, v4_calibrator=v4_calibrator,
            v7_model=v7_model, v7_calibrator=v7_calibrator,
            signal_generator=sig_gen, fabric_available=True, is_train=False
        )
        scores_v7_h3 = np.concatenate([c["v7_scores"] for c in res_h3])
        m_a_h3 = evaluate_rankings(res_h3, scores_v7_h3, q_h3, cluster_dicts)

        scores_b_h3 = shadow_model_b.predict_proba(X_b_h3)[:, 1]
        m_b_h3 = evaluate_rankings(res_h3, scores_b_h3, q_h3, cluster_dicts)

        raw_c_h3 = shadow_model_c.predict_proba(X_c_h3)[:, 1]
        scores_c_h3 = shadow_calibrator.predict_proba(raw_c_h3.reshape(-1, 1))[:, 1]
        m_c_h3 = evaluate_rankings(res_h3, scores_c_h3, q_h3, cluster_dicts)

        holdout_results["v6_3_seed_66263"] = {"model_a_v7": m_a_h3, "model_b_v7_only": m_b_h3, "model_c_blockchain": m_c_h3}
        print(f"Regime 3: Model A Top-3 = {m_a_h3['top3_accuracy']*100:.2f}%, Model B Top-3 = {m_b_h3['top3_accuracy']*100:.2f}%, Model C Top-3 = {m_c_h3['top3_accuracy']*100:.2f}%")
        print(f"         Delta C vs B = {(m_c_h3['top3_accuracy'] - m_b_h3['top3_accuracy'])*100:+.2f} pp | Delta C vs A = {(m_c_h3['top3_accuracy'] - m_a_h3['top3_accuracy'])*100:+.2f} pp")

        # Combined Metrics
        n1 = len(cases_h1)
        n2 = len(cases_h2)
        n3 = len(cases_h3)
        total_cases = n1 + n2 + n3

        combined_a_top1 = (m_a_h1["top1_accuracy"]*n1 + m_a_h2["top1_accuracy"]*n2 + m_a_h3["top1_accuracy"]*n3) / total_cases
        combined_a_top3 = (m_a_h1["top3_accuracy"]*n1 + m_a_h2["top3_accuracy"]*n2 + m_a_h3["top3_accuracy"]*n3) / total_cases

        combined_b_top1 = (m_b_h1["top1_accuracy"]*n1 + m_b_h2["top1_accuracy"]*n2 + m_b_h3["top1_accuracy"]*n3) / total_cases
        combined_b_top3 = (m_b_h1["top3_accuracy"]*n1 + m_b_h2["top3_accuracy"]*n2 + m_b_h3["top3_accuracy"]*n3) / total_cases

        combined_c_top1 = (m_c_h1["top1_accuracy"]*n1 + m_c_h2["top1_accuracy"]*n2 + m_c_h3["top1_accuracy"]*n3) / total_cases
        combined_c_top3 = (m_c_h1["top3_accuracy"]*n1 + m_c_h2["top3_accuracy"]*n2 + m_c_h3["top3_accuracy"]*n3) / total_cases

        combined_delta_cb_top3 = (combined_c_top3 - combined_b_top3) * 100.0
        combined_delta_ca_top3 = (combined_c_top3 - combined_a_top3) * 100.0
        combined_delta_ca_top1 = (combined_c_top1 - combined_a_top1) * 100.0

        print("\n=======================================================")
        print("  FINAL QUALIFICATION GATES VERIFICATION (ABLATION)")
        print("=======================================================")
        print(f"Total holdout cases evaluated: {total_cases}")
        print(f"Model A (V7-compat Baseline):  Top-1: {combined_a_top1*100:.2f}% | Top-3: {combined_a_top3*100:.2f}%")
        print(f"Model B (V7 Features Only):    Top-1: {combined_b_top1*100:.2f}% | Top-3: {combined_b_top3*100:.2f}%")
        print(f"Model C (V7 + Blockchain):     Top-1: {combined_c_top1*100:.2f}% | Top-3: {combined_c_top3*100:.2f}%")
        print(f"Ablation Delta (C Top-3 - B Top-3): {combined_delta_cb_top3:+.2f} percentage points")
        print(f"Improvement vs V7 (C Top-3 - A Top-3): {combined_delta_ca_top3:+.2f} percentage points")
        print(f"Top-1 Non-Regression (C Top-1 - A Top-1): {combined_delta_ca_top1:+.2f} percentage points")

        gate1_ablation = combined_delta_cb_top3 >= 1.0
        gate2_top1 = combined_delta_ca_top1 >= -0.10 # Non-regression
        gate3_regime = all(
            (m["model_c_blockchain"]["top3_accuracy"] - m["model_a_v7"]["top3_accuracy"]) >= -0.005
            for m in holdout_results.values()
        )

        print(f"\nGate 1 (Blockchain Ablation: C Top-3 - B Top-3 >= +1.0 pp): {'PASS' if gate1_ablation else 'FAIL'} ({combined_delta_cb_top3:+.2f} pp)")
        print(f"Gate 2 (Top-1 Non-Regression vs V7):                        {'PASS' if gate2_top1 else 'FAIL'} ({combined_delta_ca_top1:+.2f} pp)")
        print(f"Gate 3 (Regime Safety Slack: max drop <= 0.5 pp vs V7):     {'PASS' if gate3_regime else 'FAIL'}")

        all_gates_pass = gate1_ablation and gate2_top1 and gate3_regime

        report = {
            "qualification_passed": all_gates_pass,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "total_holdout_cases": total_cases,
            "combined_metrics": {
                "model_a_v7": {
                    "top1": round(combined_a_top1, 4),
                    "top3": round(combined_a_top3, 4)
                },
                "model_b_v7_only": {
                    "top1": round(combined_b_top1, 4),
                    "top3": round(combined_b_top3, 4)
                },
                "model_c_blockchain": {
                    "top1": round(combined_c_top1, 4),
                    "top3": round(combined_c_top3, 4)
                },
                "ablation_delta_c_minus_b_top3_pp": round(combined_delta_cb_top3, 2),
                "gain_c_minus_a_top3_pp": round(combined_delta_ca_top3, 2),
                "gain_c_minus_a_top1_pp": round(combined_delta_ca_top1, 2)
            },
            "regimes": holdout_results,
            "gates": {
                "gate1_ablation_delta_ge_1pp": gate1_ablation,
                "gate2_top1_non_regression": gate2_top1,
                "gate3_regime_safety": gate3_regime
            }
        }

        report_path = os.path.join(ARTIFACTS_DIR, "blockchain_shadow_qualification_report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\nQualification report saved to {report_path}")

        if not all_gates_pass:
            sys.exit(1)


    if args.test_outage:
        print("\n=======================================================")
        print("  STEP 6: FABRIC OUTAGE / COLD START FALLBACK TEST")
        print("=======================================================")
        model_path = os.path.join(ARTIFACTS_DIR, "blockchain_shadow_ranker_v1.joblib")
        cal_path = os.path.join(ARTIFACTS_DIR, "blockchain_shadow_calibrator_v1.joblib")
        shadow_model = joblib.load(model_path)
        shadow_calibrator = joblib.load(cal_path)

        cases_outage = load_tabular_split_cases(os.path.join(DATA_DIR, "delhi_v6_2_cases.csv.gz"), "v6.2", "test", 500, seed=99999)
        # Extract with fabric_available = False
        _, X_c_outage, _, bm_outage, q_outage, res_outage = extract_features_and_rankings(
            cases=cases_outage, cluster_dicts=cluster_dicts, cand_gen=cand_gen,
            v4_model=v4_model, v4_calibrator=v4_calibrator,
            v7_model=v7_model, v7_calibrator=v7_calibrator,
            signal_generator=sig_gen, fabric_available=False
        )

        scores_v7_outage = np.concatenate([c["v7_scores"] for c in res_outage])
        m_v7 = evaluate_rankings(res_outage, scores_v7_outage, q_outage, cluster_dicts)

        raw_c_outage = shadow_model.predict_proba(X_c_outage)[:, 1]
        scores_c_outage = shadow_calibrator.predict_proba(raw_c_outage.reshape(-1, 1))[:, 1]
        m_shadow = evaluate_rankings(res_outage, scores_c_outage, q_outage, cluster_dicts)

        print(f"Fabric Outage V7 Top-3 = {m_v7['top3_accuracy']*100:.2f}% | Shadow Fallback Top-3 = {m_shadow['top3_accuracy']*100:.2f}%")
        delta_outage = abs(m_shadow['top3_accuracy'] - m_v7['top3_accuracy']) * 100.0
        print(f"Discrepancy during complete outage: {delta_outage:.2f} percentage points")
        assert delta_outage <= 2.0, f"Outage fallback degraded too far from V7 ({delta_outage:.2f} pp)"
        print("Fabric Outage Safety Gate: PASS")


if __name__ == "__main__":
    main()
