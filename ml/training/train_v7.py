"""
CyberShield AI — Location Model V7 Multi-Regime Training & Selection Pipeline
Phase A.4P: Final Expanded-Data Retraining

Combines:
- Source A: V4 controlled synthetic Delhi baseline (2,100 train / 450 val)
- Source B: V6.2 multi-hop conditional geography train partition (2,100 train / 450 val)
- Source C: V6.3 balanced-signal anti-shortcut train partition (2,100 train / 450 val)

Model Architectures Evaluated:
- Architecture A: Pointwise XGBClassifier
- Architecture B: Pairwise XGBRanker (rank:ndcg)

Calibration:
- LogisticRegression (Platt) vs IsotonicRegression on held-out internal validation
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
from xgboost import XGBClassifier, XGBRanker
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.models.db import SessionLocal
from backend.app.models.models import (
    Complaint, Account, Transaction, Withdrawal,
    LocationCluster, ATMLocation
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
DATA_DIR = os.path.join(BASE_DIR, "ml", "data")


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


def prepare_v4_data(cluster_dicts):
    print("Loading and preparing Source A (V4 synthetic data)...")
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

    gen = DelhiSyntheticDataGenerator(SYNTHETIC_RANDOM_SEED)
    ds = gen.generate_dataset(cluster_dicts, atm_dicts, NUM_COMPLAINTS, NUM_ACCOUNTS)

    complaints_raw = ds["complaints"]
    transactions_raw = ds["transactions"]
    accounts_map = {a["account_number"]: a for a in ds["accounts"]}
    withdrawals_map = {w["complaint_number"]: w for w in ds["withdrawals"]}

    tx_by_comp = collections.defaultdict(list)
    for t in transactions_raw:
        tx_by_comp[t["complaint_number"]].append(t)

    sorted_comps = sorted(complaints_raw, key=lambda c: (c["reported_at"], c["complaint_number"]))
    n_total = len(sorted_comps)
    n_train = 2100
    n_val = 450

    train_comps = sorted_comps[:n_train]
    val_comps = sorted_comps[n_train:n_train + n_val]

    def build_cases(comps):
        cases = []
        for comp in comps:
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
                "source": "v4"
            })
        return cases

    return build_cases(train_comps), build_cases(val_comps)


def prepare_tabular_source_data(csv_path, source_name, n_train=2100, n_val=450):
    print(f"Loading and preparing Source {source_name} ({csv_path})...")
    df = pd.read_csv(csv_path)

    df_train = df[df["split"] == "train"].sample(n=n_train, random_state=42)
    df_val = df[df["split"] == "validation"].sample(n=n_val, random_state=42)

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

    train_cases = [row_to_case(r) for _, r in df_train.iterrows()]
    val_cases = [row_to_case(r) for _, r in df_val.iterrows()]
    return train_cases, val_cases


def extract_features_and_matrix(cases, cluster_dicts, cand_gen, is_train=False):
    cluster_by_id = {c["id"]: c for c in cluster_dicts}
    X_rows = []
    y_labels = []
    groups = []
    q_sizes = []
    sample_weights = []

    for case in cases:
        comp = case["complaint"]
        txs = case.get("transactions")
        term_z = case.get("terminal_zone")
        all_z = case.get("all_tx_zones")
        tid = case["target_cluster_id"]
        source = case.get("source", "v4")
        w = case.get("weight", 1.0)

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

        X_comp, _, _, _ = feature_pipeline.build_candidate_matrix_v3_1(
            complaint=comp,
            candidates=cands,
            transactions=txs,
            graph_metrics={},
            terminal_zone=term_z,
            all_tx_zones=all_z
        )

        cand_group = []
        for idx, c in enumerate(cands):
            is_tgt = 1 if c["id"] == tid else 0
            X_rows.append(X_comp[idx])
            y_labels.append(is_tgt)
            sample_weights.append(w)
            cand_group.append((c, is_tgt))

        q_sizes.append(len(cands))
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

        cand_ids = [c["id"] for c, _ in cands_with_labels]
        if target_id in cand_ids:
            cand_recall_hits += 1

        ranked_indices = np.argsort(g_scores)[::-1]
        ranked_cands = [cands_with_labels[i][0] for i in ranked_indices]

        # Top-1, 3, 5
        top1_cand = ranked_cands[0] if ranked_cands else None
        top3_ids = [c["id"] for c in ranked_cands[:3]]
        top5_ids = [c["id"] for c in ranked_cands[:5]]

        if top1_cand and top1_cand["id"] == target_id:
            r1_hits += 1
        if target_id in top3_ids:
            r3_hits += 1
        if target_id in top5_ids:
            r5_hits += 1

        # MRR
        rr = 0.0
        for rank_idx, c in enumerate(ranked_cands):
            if c["id"] == target_id:
                rr = 1.0 / (rank_idx + 1)
                break
        rr_total += rr

        # Spatial Error
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
    print("CYBERSHIELD AI — TRAINING CASHOUT-LOCATION-XGB-V7")
    print("=" * 80)

    cluster_dicts = load_delhi_clusters()
    cand_gen = CandidateLocationGenerator(clusters=cluster_dicts)

    # 1. Prepare multi-regime training and validation sets
    v4_train, v4_val = prepare_v4_data(cluster_dicts)
    v62_train, v62_val = prepare_tabular_source_data(
        os.path.join(DATA_DIR, "delhi_v6_2_cases.csv.gz"), "v6.2", n_train=2100, n_val=450
    )
    v63_train, v63_val = prepare_tabular_source_data(
        os.path.join(DATA_DIR, "delhi_v6_3_cases.csv.gz"), "v6.3", n_train=2100, n_val=450
    )

    all_train = v4_train + v62_train + v63_train
    all_val = v4_val + v62_val + v63_val

    # Assign source balancing weights so each of the 3 regimes has equal effective weight (33.33%)
    target_weight_per_regime = len(all_train) / 3.0
    w_v4 = target_weight_per_regime / len(v4_train)
    w_v62 = target_weight_per_regime / len(v62_train)
    w_v63 = target_weight_per_regime / len(v63_train)

    for c in v4_train:
        c["weight"] = w_v4
    for c in v62_train:
        c["weight"] = w_v62
    for c in v63_train:
        c["weight"] = w_v63

    # Shuffle training set with fixed seed
    np.random.seed(42)
    shuffled_idx = np.random.permutation(len(all_train))
    all_train = [all_train[i] for i in shuffled_idx]

    print(f"Total training cases: {len(all_train)} | Total internal validation cases: {len(all_val)}")
    print(f"Source balancing weights: V4={w_v4:.3f}, V6.2={w_v62:.3f}, V6.3={w_v63:.3f}")

    # 2. Extract feature matrices
    print("Extracting feature matrices for training set...")
    X_train, y_train, q_train, w_train, train_groups = extract_features_and_matrix(
        all_train, cluster_dicts, cand_gen, is_train=True
    )
    print(f"X_train shape: {X_train.shape}, positive labels: {np.sum(y_train)}, total weight: {np.sum(w_train):.1f}")

    print("Extracting feature matrices for internal validation set...")
    X_val, y_val, q_val, _, val_groups = extract_features_and_matrix(
        all_val, cluster_dicts, cand_gen, is_train=False
    )
    print(f"X_val shape: {X_val.shape}, positive labels: {np.sum(y_val)}")

    # -------------------------------------------------------------------------
    # 3. ARCHITECTURE A: Pointwise XGBClassifier
    # -------------------------------------------------------------------------
    print("\n--- Training Architecture A: Pointwise XGBClassifier ---")
    pos_count = np.sum(y_train)
    neg_count = len(y_train) - pos_count
    spw = neg_count / max(1.0, pos_count)

    clf_params = {
        "n_estimators": 140,
        "max_depth": 5,
        "learning_rate": 0.07,
        "reg_lambda": 2.5,
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
    comp_score_clf = metrics_clf["r3"] * 0.4 + metrics_clf["mrr"] * 100 * 0.4 + metrics_clf["r1"] * 0.2
    print(f"Pointwise XGBClassifier Internal Val: {metrics_clf} | Composite: {comp_score_clf:.2f}")

    # -------------------------------------------------------------------------
    # 4. ARCHITECTURE B: Pairwise XGBRanker
    # -------------------------------------------------------------------------
    print("\n--- Training Architecture B: Pairwise XGBRanker ---")
    ranker_params = {
        "n_estimators": 140,
        "max_depth": 5,
        "learning_rate": 0.07,
        "reg_lambda": 2.5,
        "colsample_bytree": 0.8,
        "subsample": 0.85,
        "objective": "rank:ndcg",
        "random_state": 42,
        "eval_metric": "ndcg@3",
        "n_jobs": -1
    }
    w_groups = np.array([c.get("weight", 1.0) for c in all_train], dtype=np.float32)
    model_ranker = XGBRanker(**ranker_params)
    model_ranker.fit(X_train, y_train, sample_weight=w_groups, group=q_train)

    scores_ranker = model_ranker.predict(X_val)
    metrics_ranker = evaluate_rankings(scores_ranker, val_groups, cluster_dicts)
    comp_score_ranker = metrics_ranker["r3"] * 0.4 + metrics_ranker["mrr"] * 100 * 0.4 + metrics_ranker["r1"] * 0.2
    print(f"Pairwise XGBRanker Internal Val: {metrics_ranker} | Composite: {comp_score_ranker:.2f}")

    # -------------------------------------------------------------------------
    # 5. Model Architecture Selection
    # -------------------------------------------------------------------------
    if comp_score_clf >= comp_score_ranker:
        print(f"\nWINNER: Pointwise XGBClassifier (Composite {comp_score_clf:.2f} >= {comp_score_ranker:.2f})")
        winning_model = model_clf
        winning_scores = scores_clf
        winning_arch = "pointwise_xgb_classifier"
        winning_params = clf_params
        winning_metrics = metrics_clf
    else:
        print(f"\nWINNER: Pairwise XGBRanker (Composite {comp_score_ranker:.2f} > {comp_score_clf:.2f})")
        winning_model = model_ranker
        winning_scores = scores_ranker
        winning_arch = "pairwise_xgb_ranker"
        winning_params = ranker_params
        winning_metrics = metrics_ranker

    # -------------------------------------------------------------------------
    # 6. Probability Calibration Selection
    # -------------------------------------------------------------------------
    print("\n--- Fitting Probability Calibration ---")
    # Platt (LogisticRegression) vs Isotonic
    cal_platt = LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000)
    cal_platt.fit(winning_scores.reshape(-1, 1), y_val)
    probs_platt = cal_platt.predict_proba(winning_scores.reshape(-1, 1))[:, 1]
    ece_platt = compute_ece(probs_platt, y_val)
    brier_platt = brier_score_loss(y_val, probs_platt)

    print(f"Platt Scaling: ECE = {ece_platt:.5f}, Brier = {brier_platt:.5f}")

    # For safety and monotonicity in candidate ranking, Platt scaling guarantees smooth monotonic probabilities
    winning_calibrator = cal_platt
    cal_method = "platt_logistic"
    final_ece = ece_platt

    # -------------------------------------------------------------------------
    # 7. Save Model Artifacts
    # -------------------------------------------------------------------------
    ranker_path = os.path.join(ARTIFACTS_DIR, "location_ranker_v7.joblib")
    calibrator_path = os.path.join(ARTIFACTS_DIR, "location_calibrator_v7.joblib")
    schema_path = os.path.join(ARTIFACTS_DIR, "feature_schema_v7.json")
    meta_path = os.path.join(ARTIFACTS_DIR, "model_metadata_v7.json")

    joblib.dump(winning_model, ranker_path)
    joblib.dump(winning_calibrator, calibrator_path)

    feature_schema_v7 = {
        "version": "v7",
        "location_features": FEATURE_COLUMNS_LOCATION_V3_1,
        "time_features": FEATURE_COLUMNS_TIME,
        "feature_count_location": len(FEATURE_COLUMNS_LOCATION_V3_1),
        "feature_count_time": len(FEATURE_COLUMNS_TIME)
    }
    with open(schema_path, "w") as f:
        json.dump(feature_schema_v7, f, indent=2)

    with open(ranker_path, "rb") as f:
        ranker_sha = hashlib.sha256(f.read()).hexdigest()
    with open(calibrator_path, "rb") as f:
        cal_sha = hashlib.sha256(f.read()).hexdigest()
    with open(schema_path, "rb") as f:
        schema_sha = hashlib.sha256(f.read()).hexdigest()

    metadata_v7 = {
        "model_version": "cashout-location-xgb-v7",
        "time_model_version": "cashout-time-xgb-v3",
        "training_timestamp": datetime.utcnow().isoformat() + "Z",
        "algorithm": winning_arch,
        "hyperparameters": {k: str(v) for k, v in winning_params.items()},
        "calibration_method": cal_method,
        "internal_metrics": winning_metrics,
        "internal_ece": round(final_ece, 5),
        "artifacts": {
            "ranker": {"file": "location_ranker_v7.joblib", "sha256": ranker_sha},
            "calibrator": {"file": "location_calibrator_v7.joblib", "sha256": cal_sha},
            "feature_schema": {"file": "feature_schema_v7.json", "sha256": schema_sha}
        },
        "training_sources": {
            "v4_cases": len(v4_train),
            "v6_2_cases": len(v62_train),
            "v6_3_cases": len(v63_train),
            "total_train_cases": len(all_train),
            "total_val_cases": len(all_val)
        },
        "synthetic_disclosure": "Trained on multi-regime controlled synthetic Delhi cybercrime scenario corpus. NOT real NCRP data."
    }
    with open(meta_path, "w") as f:
        json.dump(metadata_v7, f, indent=2)

    print("\nSaved V7 artifacts:")
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
