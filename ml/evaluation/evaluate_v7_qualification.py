"""
CyberShield AI — V7 External Qualification Benchmark & Gate Verification
Phase A.4P: Dual-Regime Holdout Evaluation (Seeds 52162 & 52163, 4000 cases)

Evaluates:
- cashout-location-xgb-v4 + location_calibrator_v4.joblib
vs
- cashout-location-xgb-v7 + location_calibrator_v7.joblib

Under identical conditions, candidate universes, and metric calculations.
"""

import os
import sys
import json
import math
import hashlib
import collections
from datetime import datetime
from typing import Dict, Any, List, Tuple

import joblib
import numpy as np
import pandas as pd

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
    DELHI_ZONE_CENTROIDS
)

ARTIFACTS_DIR = os.path.join(BASE_DIR, "ml", "artifacts")
DATA_DIR = os.path.join(BASE_DIR, "ml", "data")
EVAL_DIR = os.path.join(BASE_DIR, "ml", "evaluation")


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


def load_holdout_cases(csv_path: str, regime_name: str) -> List[Dict[str, Any]]:
    df = pd.read_csv(csv_path)
    cases = []
    for _, row in df.iterrows():
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
            "regime": regime_name
        })
    return cases


def load_v4_test_cases(cluster_dicts) -> List[Dict[str, Any]]:
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
    n_train = int(len(sorted_comps) * 0.70)
    n_val = int(len(sorted_comps) * 0.15)
    test_comps = sorted_comps[n_train + n_val:]

    cases = []
    for comp in test_comps:
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
            "regime": "v4_original"
        })
    return cases


def evaluate_model_on_cases(model, calibrator, cases, cluster_dicts, cand_gen):
    cluster_by_id = {c["id"]: c for c in cluster_dicts}
    r1_hits = 0
    r3_hits = 0
    r5_hits = 0
    rr_total = 0.0
    spatial_errors = []
    cand_recall_hits = 0
    all_cal_probs = []
    all_labels = []

    for case in cases:
        comp = case["complaint"]
        txs = case.get("transactions")
        term_z = case.get("terminal_zone")
        all_z = case.get("all_tx_zones")
        tid = case["target_cluster_id"]

        cands = cand_gen.generate_candidates_for_complaint(
            complaint=comp,
            top_k=25,
            transactions=txs,
            terminal_zone=term_z,
            all_tx_zones=all_z
        )
        cand_ids = [c["id"] for c in cands]

        if tid in cand_ids:
            cand_recall_hits += 1

        X_comp, _, _, _ = feature_pipeline.build_candidate_matrix_v3_1(
            complaint=comp,
            candidates=cands,
            transactions=txs,
            graph_metrics={},
            terminal_zone=term_z,
            all_tx_zones=all_z
        )

        raw_scores = model.predict_proba(X_comp)[:, 1]
        cal_scores = calibrator.predict_proba(raw_scores.reshape(-1, 1))[:, 1]

        target_cluster = cluster_by_id.get(tid)
        ranked_indices = np.argsort(cal_scores)[::-1]
        ranked_cands = [cands[i] for i in ranked_indices]

        for idx, c in enumerate(cands):
            is_pos = 1 if c["id"] == tid else 0
            all_cal_probs.append(float(cal_scores[idx]))
            all_labels.append(is_pos)

        # Top-1, 3, 5
        top1_cand = ranked_cands[0] if ranked_cands else None
        top3_ids = [c["id"] for c in ranked_cands[:3]]
        top5_ids = [c["id"] for c in ranked_cands[:5]]

        if top1_cand and top1_cand["id"] == tid:
            r1_hits += 1
        if tid in top3_ids:
            r3_hits += 1
        if tid in top5_ids:
            r5_hits += 1

        # MRR
        rr = 0.0
        for rank_idx, c in enumerate(ranked_cands):
            if c["id"] == tid:
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

    n_cases = len(cases)
    ece = compute_ece(np.array(all_cal_probs), np.array(all_labels))

    return {
        "candidate_recall@25": round((cand_recall_hits / n_cases) * 100.0, 2),
        "r1": round((r1_hits / n_cases) * 100.0, 2),
        "r3": round((r3_hits / n_cases) * 100.0, 2),
        "r5": round((r5_hits / n_cases) * 100.0, 2),
        "mrr": round(rr_total / n_cases, 4),
        "median_error_km": round(float(np.median(spatial_errors)), 2),
        "ece": round(ece, 5)
    }


def analyze_feature_importance(model, feature_names):
    importances = model.feature_importances_
    sorted_idx = np.argsort(importances)[::-1]

    top_features = []
    for i in sorted_idx[:5]:
        top_features.append({"feature": feature_names[i], "importance": round(float(importances[i]), 4)})

    terminal_related = sum(float(importances[i]) for i, f in enumerate(feature_names) if "terminal" in f)
    dominant_acc_related = sum(float(importances[i]) for i, f in enumerate(feature_names) if "account" in f)
    spatial_dist_related = sum(float(importances[i]) for i, f in enumerate(feature_names) if "dist" in f)
    cluster_hist_related = sum(float(importances[i]) for i, f in enumerate(feature_names) if "historical" in f or "cluster" in f)

    return {
        "largest_feature_contribution": round(float(importances[sorted_idx[0]]), 4),
        "largest_feature_name": feature_names[sorted_idx[0]],
        "top_5_features": top_features,
        "terminal_related_contribution": round(terminal_related, 4),
        "dominant_account_related_contribution": round(dominant_acc_related, 4),
        "spatial_distance_contribution": round(spatial_dist_related, 4),
        "cluster_history_contribution": round(cluster_hist_related, 4)
    }


def main():
    print("=" * 80)
    print("CYBERSHIELD AI — V7 EXTERNAL QUALIFICATION EVALUATION")
    print("=" * 80)

    cluster_dicts = load_delhi_clusters()
    cand_gen = CandidateLocationGenerator(clusters=cluster_dicts)

    # 1. Load Models
    v4_model = joblib.load(os.path.join(ARTIFACTS_DIR, "location_ranker_v4.joblib"))
    v4_calibrator = joblib.load(os.path.join(ARTIFACTS_DIR, "location_calibrator_v4.joblib"))
    v7_model = joblib.load(os.path.join(ARTIFACTS_DIR, "location_ranker_v7.joblib"))
    v7_calibrator = joblib.load(os.path.join(ARTIFACTS_DIR, "location_calibrator_v7.joblib"))

    # 2. Load External Holdouts
    cases_52162 = load_holdout_cases(os.path.join(DATA_DIR, "qualification_holdout_52162.csv.gz"), "v6.2_holdout")
    cases_52163 = load_holdout_cases(os.path.join(DATA_DIR, "qualification_holdout_52163.csv.gz"), "v6.3_holdout")
    cases_combined = cases_52162 + cases_52163
    v4_test_cases = load_v4_test_cases(cluster_dicts)

    print(f"Loaded {len(cases_52162)} V6.2 holdout cases, {len(cases_52163)} V6.3 holdout cases (Total: {len(cases_combined)})")
    print(f"Loaded {len(v4_test_cases)} original V4 test cases for regression check.")

    # 3. Evaluate on Combined External Holdout
    print("\nEvaluating V4 on Combined External Holdout (4000 cases)...")
    v4_combined = evaluate_model_on_cases(v4_model, v4_calibrator, cases_combined, cluster_dicts, cand_gen)
    print("V4 Combined:", v4_combined)

    print("\nEvaluating V7 on Combined External Holdout (4000 cases)...")
    v7_combined = evaluate_model_on_cases(v7_model, v7_calibrator, cases_combined, cluster_dicts, cand_gen)
    print("V7 Combined:", v7_combined)

    # 4. Evaluate on Separate Regimes
    print("\nEvaluating V4 and V7 on V6.2-style Holdout (2000 cases)...")
    v4_regime_62 = evaluate_model_on_cases(v4_model, v4_calibrator, cases_52162, cluster_dicts, cand_gen)
    v7_regime_62 = evaluate_model_on_cases(v7_model, v7_calibrator, cases_52162, cluster_dicts, cand_gen)
    print("V4 Regime 6.2:", v4_regime_62)
    print("V7 Regime 6.2:", v7_regime_62)

    print("\nEvaluating V4 and V7 on V6.3-style Holdout (2000 cases)...")
    v4_regime_63 = evaluate_model_on_cases(v4_model, v4_calibrator, cases_52163, cluster_dicts, cand_gen)
    v7_regime_63 = evaluate_model_on_cases(v7_model, v7_calibrator, cases_52163, cluster_dicts, cand_gen)
    print("V4 Regime 6.3:", v4_regime_63)
    print("V7 Regime 6.3:", v7_regime_63)

    # 5. Original V4 Historical Regression Check
    print("\nEvaluating V4 and V7 on Original V4 Test Set (450 cases)...")
    v4_orig_test = evaluate_model_on_cases(v4_model, v4_calibrator, v4_test_cases, cluster_dicts, cand_gen)
    v7_orig_test = evaluate_model_on_cases(v7_model, v7_calibrator, v4_test_cases, cluster_dicts, cand_gen)
    print("V4 Original Test:", v4_orig_test)
    print("V7 Original Test:", v7_orig_test)

    # 6. Feature Importance Audit
    feat_audit = analyze_feature_importance(v7_model, FEATURE_COLUMNS_LOCATION_V3_1)
    print("\nV7 Feature Importance Audit:", feat_audit)

    # -------------------------------------------------------------------------
    # 7. Check Promotion Gates Relative to V4
    # -------------------------------------------------------------------------
    cand_recall_pass = (v7_combined["candidate_recall@25"] >= 72.0) and (v7_combined["candidate_recall@25"] >= v4_combined["candidate_recall@25"] - 0.5)
    r1_pass = v7_combined["r1"] >= v4_combined["r1"] - 0.5
    r3_pass = v7_combined["r3"] >= v4_combined["r3"] + 1.5
    r5_pass = v7_combined["r5"] >= v4_combined["r5"] + 1.0
    mrr_pass = v7_combined["mrr"] >= v4_combined["mrr"] + 0.005
    spatial_err_pass = v7_combined["median_error_km"] <= v4_combined["median_error_km"]
    ece_pass = (v7_combined["ece"] <= 0.05) and (v7_combined["ece"] <= v4_combined["ece"] + 0.005)

    # Regime robustness checks
    regime_62_robust = v7_regime_62["r3"] >= v4_regime_62["r3"] - 1.0
    regime_63_robust = v7_regime_63["r3"] >= v4_regime_63["r3"] - 1.0
    regime_robustness_pass = regime_62_robust and regime_63_robust

    # Original V4 regression check
    v4_reg_r1 = v7_orig_test["r1"] >= v4_orig_test["r1"] - 0.5
    v4_reg_r3 = v7_orig_test["r3"] >= v4_orig_test["r3"] - 0.5
    v4_reg_mrr = v7_orig_test["mrr"] >= v4_orig_test["mrr"] - 0.005
    v4_reg_dist = v7_orig_test["median_error_km"] <= v4_orig_test["median_error_km"] + 0.5
    v4_regression_pass = v4_reg_r1 and v4_reg_r3 and v4_reg_mrr and v4_reg_dist

    # Feature shortcut safety: largest feature contribution < 0.35
    feature_safety_pass = feat_audit["largest_feature_contribution"] < 0.35

    all_gates_pass = (
        cand_recall_pass and
        r1_pass and
        r3_pass and
        r5_pass and
        mrr_pass and
        spatial_err_pass and
        ece_pass and
        regime_robustness_pass and
        v4_regression_pass and
        feature_safety_pass
    )

    print("\n" + "=" * 80)
    print("PROMOTION GATES EVALUATION SUMMARY:")
    print(f"- Candidate Recall@25 (V7 >= 72% & >= V4-0.5pp): {cand_recall_pass} (V7: {v7_combined['candidate_recall@25']}%, V4: {v4_combined['candidate_recall@25']}%)")
    print(f"- Top-1 (V7 >= V4 - 0.5pp): {r1_pass} (V7: {v7_combined['r1']}%, V4: {v4_combined['r1']}%)")
    print(f"- Top-3 (V7 >= V4 + 1.5pp): {r3_pass} (V7: {v7_combined['r3']}%, V4: {v4_combined['r3']}%, Delta: +{v7_combined['r3'] - v4_combined['r3']:.2f}pp)")
    print(f"- Top-5 (V7 >= V4 + 1.0pp): {r5_pass} (V7: {v7_combined['r5']}%, V4: {v4_combined['r5']}%, Delta: +{v7_combined['r5'] - v4_combined['r5']:.2f}pp)")
    print(f"- MRR (V7 >= V4 + 0.005): {mrr_pass} (V7: {v7_combined['mrr']}, V4: {v4_combined['mrr']}, Delta: +{v7_combined['mrr'] - v4_combined['mrr']:.4f})")
    print(f"- Median Spatial Error (V7 <= V4): {spatial_err_pass} (V7: {v7_combined['median_error_km']} km, V4: {v4_combined['median_error_km']} km)")
    print(f"- ECE (V7 <= 0.05 & <= V4 + 0.005): {ece_pass} (V7: {v7_combined['ece']}, V4: {v4_combined['ece']})")
    print(f"- Regime Robustness (V6.2: {v7_regime_62['r3']}% vs V4 {v4_regime_62['r3']}%, V6.3: {v7_regime_63['r3']}% vs V4 {v4_regime_63['r3']}%): {regime_robustness_pass}")
    print(f"- Original V4 Distribution Regression Check: {v4_regression_pass}")
    print(f"- Feature Shortcut Safety (max contrib {feat_audit['largest_feature_contribution']:.4f} < 0.35): {feature_safety_pass}")
    print(f"- OVERALL QUALIFICATION RESULT: {'PASS (PROMOTION CANDIDATE)' if all_gates_pass else 'FAIL (KEEP V4)'}")
    print("=" * 80)

    report = {
        "evaluation_timestamp": datetime.utcnow().isoformat() + "Z",
        "dual_regime_holdouts": {
            "regime_a": {"seed": 52162, "cases": len(cases_52162), "style": "v6.2_two_stage"},
            "regime_b": {"seed": 52163, "cases": len(cases_52163), "style": "v6.3_balanced_signal"},
            "total_holdout_cases": len(cases_combined)
        },
        "combined_holdout_metrics": {
            "v4": v4_combined,
            "v7": v7_combined,
            "improvement": {
                "top3_delta_pp": round(v7_combined["r3"] - v4_combined["r3"], 2),
                "top5_delta_pp": round(v7_combined["r5"] - v4_combined["r5"], 2),
                "mrr_delta": round(v7_combined["mrr"] - v4_combined["mrr"], 4),
                "spatial_error_reduction_km": round(v4_combined["median_error_km"] - v7_combined["median_error_km"], 2)
            }
        },
        "per_regime_metrics": {
            "v6_2_holdout": {"v4": v4_regime_62, "v7": v7_regime_62},
            "v6_3_holdout": {"v4": v4_regime_63, "v7": v7_regime_63}
        },
        "original_v4_test_regression_check": {
            "v4": v4_orig_test,
            "v7": v7_orig_test,
            "pass": v4_regression_pass
        },
        "feature_audit": feat_audit,
        "gates": {
            "candidate_recall_pass": cand_recall_pass,
            "r1_pass": r1_pass,
            "r3_pass": r3_pass,
            "r5_pass": r5_pass,
            "mrr_pass": mrr_pass,
            "spatial_error_pass": spatial_err_pass,
            "ece_pass": ece_pass,
            "regime_robustness_pass": regime_robustness_pass,
            "v4_regression_pass": v4_regression_pass,
            "feature_safety_pass": feature_safety_pass,
            "all_gates_pass": all_gates_pass
        },
        "qualification_status": "QUALIFIED_PROMOTION_CANDIDATE" if all_gates_pass else "DISQUALIFIED_KEEP_V4"
    }

    out_json = os.path.join(EVAL_DIR, "v7_external_qualification.json")
    with open(out_json, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Saved qualification report to {out_json}")


if __name__ == "__main__":
    main()
