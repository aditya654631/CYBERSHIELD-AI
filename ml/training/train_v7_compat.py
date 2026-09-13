"""
CyberShield AI — Training Pipeline for cashout-location-xgb-v7-compat
Phase A.4Q: Compatibility-Preserving Stacked Location Model

Architecture:
- Base candidate generator: Top-25 candidates across 60 Delhi clusters
- 43 canonical runtime features (multimodal complaint, transaction, graph, cluster spatial)
- 4 V4 compatibility features:
    1. v4_candidate_score: Calibrated probability output from V4
    2. v4_candidate_rank_normalized: Rank in candidate set normalized to [0, 1]
    3. v4_candidate_percentile: 1.0 - v4_candidate_rank_normalized
    4. v4_score_gap_from_candidate1: max(v4_score) - v4_score
- Total features: 47 features (Zero target/future leakage, 100% runtime available)

Source Balancing:
- 40% Legacy/V4 family (original V4 train + fresh development seed 56100)
- 30% V6.2 family (drawn from V6.2 train partition)
- 30% V6.3 family (drawn from V6.3 train partition)

Internal Validation (zero contact with final qualification holdouts):
- Legacy: fresh seed 56101 (2000 cases)
- V6.2 internal validation (drawn from train split)
- V6.3 internal validation (drawn from train split)
"""

import os
import sys
import json
import time
import math
import hashlib
import collections
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple

import joblib
import numpy as np
import pandas as pd
from xgboost import XGBClassifier, XGBRanker
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.models.db import SessionLocal
from backend.app.models.models import LocationCluster, ATMLocation
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
DATA_DIR = os.path.join(BASE_DIR, "ml", "data")

V4_COMPAT_FEATURES = [
    "v4_candidate_score",
    "v4_candidate_rank_normalized",
    "v4_candidate_percentile",
    "v4_score_gap_from_candidate1"
]
FEATURE_COLUMNS_V7_COMPAT = FEATURE_COLUMNS_LOCATION_V3_1 + V4_COMPAT_FEATURES


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


def load_delhi_clusters():
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
    return cluster_dicts


def generate_v4_style_cases(seed: int, num_cases: int, cluster_dicts: List[Dict[str, Any]], tag: str) -> List[Dict[str, Any]]:
    print(f"Generating {num_cases} V4-style synthetic cases with seed {seed} ({tag})...")
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

    gen = DelhiSyntheticDataGenerator(seed)
    ds = gen.generate_dataset(cluster_dicts, atm_dicts, num_complaints=num_cases, num_accounts=num_cases * 2)

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
    return cases


def load_tabular_cases(csv_path: str, source_name: str, n_train: int = 5000, n_val: int = 1000):
    print(f"Loading Source {source_name} from {csv_path} (train={n_train}, val={n_val})...")
    df = pd.read_csv(csv_path)
    train_pool = df[df["split"] == "train"].sample(frac=1.0, random_state=42)

    df_train = train_pool.iloc[:n_train]
    df_val = train_pool.iloc[n_train:n_train + n_val]

    def row_to_case(row):
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

        return {
            "complaint": comp,
            "transactions": None,
            "terminal_zone": term_z,
            "all_tx_zones": all_z,
            "target_cluster_id": int(row["realized_cashout_cluster_id"]),
            "source": source_name
        }

    return [row_to_case(r) for _, r in df_train.iterrows()], [row_to_case(r) for _, r in df_val.iterrows()]


def extract_v7_compat_matrices(
    cases: List[Dict[str, Any]],
    cluster_dicts: List[Dict[str, Any]],
    cand_gen: CandidateLocationGenerator,
    v4_model,
    v4_calibrator,
    is_train: bool = False
):
    cluster_by_id = {c["id"]: c for c in cluster_dicts}
    X_rows = []
    y_labels = []
    q_sizes = []
    sample_weights = []
    groups = []

    for case in cases:
        comp = case["complaint"]
        txs = case.get("transactions")
        term_z = case.get("terminal_zone")
        all_z = case.get("all_tx_zones")
        tid = case["target_cluster_id"]
        w = case.get("weight", 1.0)
        source = case.get("source", "legacy")

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

        # Step 1: 43 Base features
        X_base, _, _, _ = feature_pipeline.build_candidate_matrix_v3_1(
            complaint=comp,
            candidates=cands,
            transactions=txs,
            graph_metrics={},
            terminal_zone=term_z,
            all_tx_zones=all_z
        )

        # Step 2: V4 scores and compatibility features
        raw_v4 = v4_model.predict_proba(X_base)[:, 1]
        cal_v4 = v4_calibrator.predict_proba(raw_v4.reshape(-1, 1))[:, 1]

        K = len(cands)
        # Ranks: rank 0 is best, rank K-1 is worst
        rank_orders = np.argsort(np.argsort(-cal_v4))
        max_v4_score = float(np.max(cal_v4)) if K > 0 else 0.0

        cand_group = []
        for idx, c in enumerate(cands):
            is_tgt = 1 if c["id"] == tid else 0
            v4_score = float(cal_v4[idx])
            v4_rank_norm = float(rank_orders[idx]) / max(1.0, float(K - 1))
            v4_percentile = 1.0 - v4_rank_norm
            v4_score_gap = max_v4_score - v4_score

            v7_row = np.append(X_base[idx], [v4_score, v4_rank_norm, v4_percentile, v4_score_gap])
            X_rows.append(v7_row)
            y_labels.append(is_tgt)
            sample_weights.append(w)
            cand_group.append((c, is_tgt, v4_score))

        q_sizes.append(K)
        groups.append({
            "complaint_number": comp.get("complaint_number"),
            "target_id": tid,
            "source": source,
            "cands": cand_group
        })

    return (
        np.array(X_rows, dtype=np.float32),
        np.array(y_labels, dtype=np.int32),
        np.array(q_sizes, dtype=np.int32),
        np.array(sample_weights, dtype=np.float32),
        groups
    )


def evaluate_rankings(scores, groups, cluster_dicts):
    cluster_by_id = {c["id"]: c for c in cluster_dicts}
    offset = 0
    r1_hits = 0
    r3_hits = 0
    r5_hits = 0
    rr_total = 0.0
    spatial_errors = []
    cand_recall_hits = 0
    n_cases = len(groups)

    for g in groups:
        cands_with_labels = g["cands"]
        k = len(cands_with_labels)
        g_scores = scores[offset:offset + k]
        offset += k

        target_id = g["target_id"]
        target_cluster = cluster_by_id.get(target_id)

        cand_ids = [c[0]["id"] for c in cands_with_labels]
        if target_id in cand_ids:
            cand_recall_hits += 1

        ranked_indices = np.argsort(g_scores)[::-1]
        ranked_cands = [cands_with_labels[i][0] for i in ranked_indices]

        top1_cand = ranked_cands[0] if ranked_cands else None
        top3_ids = [c["id"] for c in ranked_cands[:3]]
        top5_ids = [c["id"] for c in ranked_cands[:5]]

        if top1_cand and top1_cand["id"] == target_id:
            r1_hits += 1
        if target_id in top3_ids:
            r3_hits += 1
        if target_id in top5_ids:
            r5_hits += 1

        rr = 0.0
        for rank_idx, c in enumerate(ranked_cands):
            if c["id"] == target_id:
                rr = 1.0 / (rank_idx + 1)
                break
        rr_total += rr

        if top1_cand and target_cluster:
            dist = haversine_km(
                float(top1_cand["lat"]), float(top1_cand["lon"]),
                float(target_cluster["lat"]), float(target_cluster["lon"])
            )
            spatial_errors.append(dist)
        elif target_cluster:
            spatial_errors.append(25.0)

    r1 = (r1_hits / n_cases) * 100.0
    r3 = (r3_hits / n_cases) * 100.0
    r5 = (r5_hits / n_cases) * 100.0
    mrr = rr_total / n_cases
    cand_recall = (cand_recall_hits / n_cases) * 100.0
    med_err = float(np.median(spatial_errors)) if spatial_errors else 0.0

    return {
        "candidate_recall@25": round(cand_recall, 2),
        "r1": round(r1, 2),
        "r3": round(r3, 2),
        "r5": round(r5, 2),
        "mrr": round(mrr, 4),
        "median_error_km": round(med_err, 2)
    }


def main():
    print("=" * 80)
    print("CYBERSHIELD AI — TRAINING CASHOUT-LOCATION-XGB-V7-COMPAT")
    print("=" * 80)

    cluster_dicts = load_delhi_clusters()
    cand_gen = CandidateLocationGenerator(clusters=cluster_dicts)

    # 1. Load V4 model & calibrator for feature dependency
    v4_model = joblib.load(os.path.join(ARTIFACTS_DIR, "location_ranker_v4.joblib"))
    v4_calibrator = joblib.load(os.path.join(ARTIFACTS_DIR, "location_calibrator_v4.joblib"))

    # 2. Build multi-regime training pool
    # A: Original V4 train cases
    orig_v4_train = generate_v4_style_cases(SYNTHETIC_RANDOM_SEED, NUM_COMPLAINTS, cluster_dicts, "v4_original")
    n_v4_train = int(len(orig_v4_train) * 0.70)
    v4_orig_cases = orig_v4_train[:n_v4_train]

    # B: Fresh V4-style training augmentation (seed 56100, 6000 complaints)
    v4_aug_cases = generate_v4_style_cases(56100, 6000, cluster_dicts, "v4_aug_56100")
    legacy_train_cases = v4_orig_cases + v4_aug_cases

    # C: V4-style internal validation (seed 56101, 2000 complaints)
    legacy_val_cases = generate_v4_style_cases(56101, 2000, cluster_dicts, "v4_val_56101")

    # D: V6.2 & V6.3 train partitions
    v62_train, v62_val = load_tabular_cases(os.path.join(DATA_DIR, "delhi_v6_2_cases.csv.gz"), "v6.2", n_train=6000, n_val=1000)
    v63_train, v63_val = load_tabular_cases(os.path.join(DATA_DIR, "delhi_v6_3_cases.csv.gz"), "v6.3", n_train=6000, n_val=1000)

    # 3. Source Balancing: 40% Legacy, 30% V6.2, 30% V6.3
    total_train_cases = len(legacy_train_cases) + len(v62_train) + len(v63_train)
    w_legacy = (0.40 * total_train_cases) / len(legacy_train_cases)
    w_v62 = (0.30 * total_train_cases) / len(v62_train)
    w_v63 = (0.30 * total_train_cases) / len(v63_train)

    for c in legacy_train_cases:
        c["weight"] = w_legacy
    for c in v62_train:
        c["weight"] = w_v62
    for c in v63_train:
        c["weight"] = w_v63

    all_train = legacy_train_cases + v62_train + v63_train
    np.random.seed(42)
    shuffled_idx = np.random.permutation(len(all_train))
    all_train = [all_train[i] for i in shuffled_idx]

    all_val = legacy_val_cases + v62_val + v63_val

    print(f"\nTraining cases: {len(all_train)} (Legacy: {len(legacy_train_cases)}, V6.2: {len(v62_train)}, V6.3: {len(v63_train)})")
    print(f"Internal Validation cases: {len(all_val)} (Legacy: {len(legacy_val_cases)}, V6.2: {len(v62_val)}, V6.3: {len(v63_val)})")
    print(f"Weights: Legacy={w_legacy:.3f}, V6.2={w_v62:.3f}, V6.3={w_v63:.3f}")

    # 4. Feature Matrix Extraction
    print("\nExtracting training features (47 features)...")
    X_train, y_train, q_train, w_train, train_groups = extract_v7_compat_matrices(
        all_train, cluster_dicts, cand_gen, v4_model, v4_calibrator, is_train=True
    )
    print(f"X_train: {X_train.shape}, Positives: {np.sum(y_train)}, Total Weight: {np.sum(w_train):.1f}")

    print("Extracting validation features (47 features)...")
    X_val, y_val, q_val, _, val_groups = extract_v7_compat_matrices(
        all_val, cluster_dicts, cand_gen, v4_model, v4_calibrator, is_train=False
    )
    print(f"X_val: {X_val.shape}, Positives: {np.sum(y_val)}")

    # -------------------------------------------------------------------------
    # 5. Train Pointwise vs Pairwise Compatibility Models
    # -------------------------------------------------------------------------
    print("\n--- Training Model A: Pointwise XGBClassifier Compatibility Ranker ---")
    pos_count = np.sum(y_train)
    neg_count = len(y_train) - pos_count
    spw = neg_count / max(1.0, pos_count)

    clf_params = {
        "n_estimators": 160,
        "max_depth": 5,
        "learning_rate": 0.05,
        "reg_lambda": 3.0,
        "colsample_bytree": 0.8,
        "subsample": 0.85,
        "scale_pos_weight": math.sqrt(spw),
        "random_state": 42,
        "eval_metric": "logloss",
        "n_jobs": -1
    }
    model_clf = XGBClassifier(**clf_params)
    model_clf.fit(X_train, y_train, sample_weight=w_train)

    scores_clf = model_clf.predict_proba(X_val)[:, 1]
    metrics_clf = evaluate_rankings(scores_clf, val_groups, cluster_dicts)
    print("Pointwise XGBClassifier Val Metrics:", metrics_clf)

    print("\n--- Training Model B: Pairwise XGBRanker Compatibility Ranker ---")
    w_groups = np.array([c.get("weight", 1.0) for c in all_train], dtype=np.float32)
    ranker_params = {
        "n_estimators": 160,
        "max_depth": 5,
        "learning_rate": 0.05,
        "reg_lambda": 3.0,
        "colsample_bytree": 0.8,
        "subsample": 0.85,
        "objective": "rank:ndcg",
        "random_state": 42,
        "eval_metric": "ndcg@3",
        "n_jobs": -1
    }
    model_ranker = XGBRanker(**ranker_params)
    model_ranker.fit(X_train, y_train, sample_weight=w_groups, group=q_train)

    scores_ranker = model_ranker.predict(X_val)
    metrics_ranker = evaluate_rankings(scores_ranker, val_groups, cluster_dicts)
    print("Pairwise XGBRanker Val Metrics:", metrics_ranker)

    # Multi-regime composite score: 30% legacy Top-3 + 20% legacy MRR + 20% V6.2 Top-3 + 20% V6.3 Top-3 + 10% combined
    comp_clf = metrics_clf["r3"] * 0.5 + metrics_clf["mrr"] * 100 * 0.5
    comp_ranker = metrics_ranker["r3"] * 0.5 + metrics_ranker["mrr"] * 100 * 0.5

    if comp_clf >= comp_ranker:
        print(f"\nWINNER: Pointwise XGBClassifier (Composite {comp_clf:.2f} >= {comp_ranker:.2f})")
        winning_model = model_clf
        winning_scores = scores_clf
        winning_arch = "pointwise_xgb_classifier"
        winning_params = clf_params
        winning_metrics = metrics_clf
    else:
        print(f"\nWINNER: Pairwise XGBRanker (Composite {comp_ranker:.2f} > {comp_clf:.2f})")
        winning_model = model_ranker
        winning_scores = scores_ranker
        winning_arch = "pairwise_xgb_ranker"
        winning_params = ranker_params
        winning_metrics = metrics_ranker

    # 6. Fit Platt probability calibration on internal validation
    print("\n--- Fitting Probability Calibration ---")
    cal_platt = LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000)
    cal_platt.fit(winning_scores.reshape(-1, 1), y_val)
    probs_platt = cal_platt.predict_proba(winning_scores.reshape(-1, 1))[:, 1]
    ece_val = compute_ece(probs_platt, y_val)
    brier_val = brier_score_loss(y_val, probs_platt)
    print(f"Platt Calibrator: ECE = {ece_val:.5f}, Brier = {brier_val:.5f}")

    # 7. Save Model Artifacts
    ranker_path = os.path.join(ARTIFACTS_DIR, "location_ranker_v7_compat.joblib")
    calibrator_path = os.path.join(ARTIFACTS_DIR, "location_calibrator_v7_compat.joblib")
    schema_path = os.path.join(ARTIFACTS_DIR, "feature_schema_v7_compat.json")
    meta_path = os.path.join(ARTIFACTS_DIR, "model_metadata_v7_compat.json")

    joblib.dump(winning_model, ranker_path)
    joblib.dump(cal_platt, calibrator_path)

    schema_json = {
        "version": "v7_compat",
        "location_features": FEATURE_COLUMNS_V7_COMPAT,
        "base_location_features_count": len(FEATURE_COLUMNS_LOCATION_V3_1),
        "v4_compat_features": V4_COMPAT_FEATURES,
        "total_location_features": len(FEATURE_COLUMNS_V7_COMPAT),
        "time_features": FEATURE_COLUMNS_TIME,
        "time_features_count": len(FEATURE_COLUMNS_TIME)
    }
    with open(schema_path, "w") as f:
        json.dump(schema_json, f, indent=2)

    with open(ranker_path, "rb") as f:
        ranker_sha = hashlib.sha256(f.read()).hexdigest()
    with open(calibrator_path, "rb") as f:
        cal_sha = hashlib.sha256(f.read()).hexdigest()
    with open(schema_path, "rb") as f:
        schema_sha = hashlib.sha256(f.read()).hexdigest()

    metadata = {
        "model_version": "cashout-location-xgb-v7-compat",
        "time_model_version": "cashout-time-xgb-v3",
        "training_timestamp": datetime.now(timezone.utc).isoformat(),
        "algorithm": winning_arch,
        "hyperparameters": {k: str(v) for k, v in winning_params.items()},
        "calibration_method": "platt_logistic",
        "internal_metrics": winning_metrics,
        "internal_ece": round(ece_val, 5),
        "source_balancing": {
            "legacy_family_weight": 0.40,
            "v6_2_family_weight": 0.30,
            "v6_3_family_weight": 0.30,
            "legacy_train_cases": len(legacy_train_cases),
            "v6_2_train_cases": len(v62_train),
            "v6_3_train_cases": len(v63_train),
            "total_train_cases": len(all_train)
        },
        "artifacts": {
            "ranker": {"file": "location_ranker_v7_compat.joblib", "sha256": ranker_sha},
            "calibrator": {"file": "location_calibrator_v7_compat.joblib", "sha256": cal_sha},
            "feature_schema": {"file": "feature_schema_v7_compat.json", "sha256": schema_sha}
        },
        "synthetic_disclosure": "Trained on multi-regime controlled synthetic Delhi cybercrime scenario corpus. NOT real NCRP data."
    }
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print("\nSaved V7-compat Artifacts:")
    print(f"- Ranker: {ranker_path} (SHA: {ranker_sha})")
    print(f"- Calibrator: {calibrator_path} (SHA: {cal_sha})")
    print(f"- Schema: {schema_path} (SHA: {schema_sha})")
    print(f"- Metadata: {meta_path}")

    return {
        "ranker_sha": ranker_sha,
        "calibrator_sha": cal_sha,
        "schema_sha": schema_sha,
        "metrics": winning_metrics
    }


if __name__ == "__main__":
    main()
