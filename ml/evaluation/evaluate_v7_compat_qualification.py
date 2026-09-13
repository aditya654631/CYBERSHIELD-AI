"""
CyberShield AI — V7 Compatibility Model 3-Regime External Qualification Benchmark
Phase A.4Q: Fresh 3-Regime Holdout Evaluation (Seeds 56261, 56262, 56263 — 6000 cases total)

Evaluates:
- cashout-location-xgb-v4 (+ location_calibrator_v4.joblib)
vs
- cashout-location-xgb-v7-compat (+ location_calibrator_v7_compat.joblib)

Strict Gates:
- Legacy 56261: Top-1 >= V4 - 0.5pp, Top-3 >= V4 - 0.5pp, MRR >= V4 - 0.005, Error <= V4 + 0.5km
- V6.2 56262: Top-3 >= V4 + 3.0pp, MRR > V4, Error <= V4
- V6.3 56263: Top-3 >= V4 + 2.0pp, MRR > V4, Error <= V4
- Combined 6000: Recall@25 >= 72% & >= V4 - 0.5pp, Top-1 >= V4, Top-3 >= V4 + 3.0pp, Top-5 >= V4 + 2.0pp, MRR >= V4 + 0.010, Error <= V4, ECE <= 0.05
"""

import os
import sys
import json
import math
import pickle
import collections
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple

import joblib
import numpy as np
import pandas as pd

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.models.db import SessionLocal
from backend.app.models.models import LocationCluster
from ml.geo.candidate_generator import CandidateLocationGenerator, haversine_km
from ml.features.feature_pipeline import (
    feature_pipeline,
    FEATURE_COLUMNS_LOCATION_V3_1,
    DELHI_ZONE_CENTROIDS
)

ARTIFACTS_DIR = os.path.join(BASE_DIR, "ml", "artifacts")
DATA_DIR = os.path.join(BASE_DIR, "ml", "data")
EVAL_DIR = os.path.join(BASE_DIR, "ml", "evaluation")

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


def load_legacy_holdout_56261(pkl_path: str, cluster_dicts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    with open(pkl_path, "rb") as f:
        ds = pickle.load(f)

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
            "regime": "legacy_56261"
        })
    return cases


def load_tabular_holdout(csv_path: str, regime_name: str) -> List[Dict[str, Any]]:
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


def evaluate_models_on_cases(
    cases: List[Dict[str, Any]],
    cluster_dicts: List[Dict[str, Any]],
    cand_gen: CandidateLocationGenerator,
    v4_model,
    v4_calibrator,
    v7_model,
    v7_calibrator
):
    cluster_by_id = {c["id"]: c for c in cluster_dicts}
    n_cases = len(cases)

    # Accumulators for V4
    v4_r1, v4_r3, v4_r5 = 0, 0, 0
    v4_rr = 0.0
    v4_spatial = []
    v4_probs, v4_labels = [], []

    # Accumulators for V7-compat
    v7_r1, v7_r3, v7_r5 = 0, 0, 0
    v7_rr = 0.0
    v7_spatial = []
    v7_probs = []

    cand_recall_hits = 0

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

        # Base 43 features
        X_base, _, _, _ = feature_pipeline.build_candidate_matrix_v3_1(
            complaint=comp,
            candidates=cands,
            transactions=txs,
            graph_metrics={},
            terminal_zone=term_z,
            all_tx_zones=all_z
        )

        # Compute V4 predictions
        raw_v4 = v4_model.predict_proba(X_base)[:, 1]
        cal_v4 = v4_calibrator.predict_proba(raw_v4.reshape(-1, 1))[:, 1]

        K = len(cands)
        rank_orders = np.argsort(np.argsort(-cal_v4))
        max_v4_score = float(np.max(cal_v4)) if K > 0 else 0.0

        # Construct 47-feature matrix for V7-compat
        v7_rows = []
        for idx in range(K):
            v4_score = float(cal_v4[idx])
            v4_rank_norm = float(rank_orders[idx]) / max(1.0, float(K - 1))
            v4_percentile = 1.0 - v4_rank_norm
            v4_score_gap = max_v4_score - v4_score
            v7_rows.append(np.append(X_base[idx], [v4_score, v4_rank_norm, v4_percentile, v4_score_gap]))

        X_v7 = np.array(v7_rows, dtype=np.float32)

        # V7 predictions
        if hasattr(v7_model, "predict_proba"):
            raw_v7 = v7_model.predict_proba(X_v7)[:, 1]
        else:
            raw_v7 = v7_model.predict(X_v7)
        cal_v7 = v7_calibrator.predict_proba(raw_v7.reshape(-1, 1))[:, 1]

        # Targets & Rankings
        target_cluster = cluster_by_id.get(tid)

        # V4 Rankings
        v4_ranked_idx = np.argsort(cal_v4)[::-1]
        v4_ranked_cands = [cands[i] for i in v4_ranked_idx]

        # V7 Rankings
        v7_ranked_idx = np.argsort(cal_v7)[::-1]
        v7_ranked_cands = [cands[i] for i in v7_ranked_idx]

        for idx, c in enumerate(cands):
            is_pos = 1 if c["id"] == tid else 0
            v4_probs.append(float(cal_v4[idx]))
            v7_probs.append(float(cal_v7[idx]))
            v4_labels.append(is_pos)

        # Check V4 hits
        if v4_ranked_cands and v4_ranked_cands[0]["id"] == tid:
            v4_r1 += 1
        if tid in [c["id"] for c in v4_ranked_cands[:3]]:
            v4_r3 += 1
        if tid in [c["id"] for c in v4_ranked_cands[:5]]:
            v4_r5 += 1
        for rank_idx, c in enumerate(v4_ranked_cands):
            if c["id"] == tid:
                v4_rr += 1.0 / (rank_idx + 1)
                break
        if v4_ranked_cands and target_cluster:
            v4_spatial.append(haversine_km(float(v4_ranked_cands[0]["lat"]), float(v4_ranked_cands[0]["lon"]), float(target_cluster["lat"]), float(target_cluster["lon"])))
        else:
            v4_spatial.append(25.0)

        # Check V7 hits
        if v7_ranked_cands and v7_ranked_cands[0]["id"] == tid:
            v7_r1 += 1
        if tid in [c["id"] for c in v7_ranked_cands[:3]]:
            v7_r3 += 1
        if tid in [c["id"] for c in v7_ranked_cands[:5]]:
            v7_r5 += 1
        for rank_idx, c in enumerate(v7_ranked_cands):
            if c["id"] == tid:
                v7_rr += 1.0 / (rank_idx + 1)
                break
        if v7_ranked_cands and target_cluster:
            v7_spatial.append(haversine_km(float(v7_ranked_cands[0]["lat"]), float(v7_ranked_cands[0]["lon"]), float(target_cluster["lat"]), float(target_cluster["lon"])))
        else:
            v7_spatial.append(25.0)

    res_v4 = {
        "candidate_recall@25": round((cand_recall_hits / n_cases) * 100.0, 2),
        "r1": round((v4_r1 / n_cases) * 100.0, 2),
        "r3": round((v4_r3 / n_cases) * 100.0, 2),
        "r5": round((v4_r5 / n_cases) * 100.0, 2),
        "mrr": round(v4_rr / n_cases, 4),
        "median_error_km": round(float(np.median(v4_spatial)), 2),
        "ece": round(compute_ece(np.array(v4_probs), np.array(v4_labels)), 5)
    }

    res_v7 = {
        "candidate_recall@25": round((cand_recall_hits / n_cases) * 100.0, 2),
        "r1": round((v7_r1 / n_cases) * 100.0, 2),
        "r3": round((v7_r3 / n_cases) * 100.0, 2),
        "r5": round((v7_r5 / n_cases) * 100.0, 2),
        "mrr": round(v7_rr / n_cases, 4),
        "median_error_km": round(float(np.median(v7_spatial)), 2),
        "ece": round(compute_ece(np.array(v7_probs), np.array(v4_labels)), 5)
    }

    return res_v4, res_v7


def analyze_feature_importance(v7_model):
    importances = v7_model.feature_importances_
    sorted_idx = np.argsort(importances)[::-1]

    top_features = []
    for i in sorted_idx[:7]:
        top_features.append({"feature": FEATURE_COLUMNS_V7_COMPAT[i], "importance": round(float(importances[i]), 4)})

    v4_score_imp = float(importances[FEATURE_COLUMNS_V7_COMPAT.index("v4_candidate_score")])
    v4_total_imp = sum(float(importances[i]) for i, f in enumerate(FEATURE_COLUMNS_V7_COMPAT) if "v4_" in f)
    hist_risk_imp = float(importances[FEATURE_COLUMNS_V7_COMPAT.index("historical_cluster_risk")])
    terminal_imp = sum(float(importances[i]) for i, f in enumerate(FEATURE_COLUMNS_V7_COMPAT) if "terminal" in f)
    trajectory_imp = sum(float(importances[i]) for i, f in enumerate(FEATURE_COLUMNS_V7_COMPAT) if "hop" in f or "chain" in f or "transfer" in f or "velocity" in f)

    return {
        "v4_candidate_score_importance": round(v4_score_imp, 4),
        "v4_features_combined_importance": round(v4_total_imp, 4),
        "historical_cluster_risk_importance": round(hist_risk_imp, 4),
        "terminal_geography_importance": round(terminal_imp, 4),
        "trajectory_features_importance": round(trajectory_imp, 4),
        "top_features": top_features
    }


def main():
    print("=" * 80)
    print("CYBERSHIELD AI — V7-COMPAT 3-REGIME EXTERNAL QUALIFICATION EVALUATION")
    print("=" * 80)

    cluster_dicts = load_delhi_clusters()
    cand_gen = CandidateLocationGenerator(clusters=cluster_dicts)

    # 1. Load models
    v4_model = joblib.load(os.path.join(ARTIFACTS_DIR, "location_ranker_v4.joblib"))
    v4_calibrator = joblib.load(os.path.join(ARTIFACTS_DIR, "location_calibrator_v4.joblib"))
    v7_model = joblib.load(os.path.join(ARTIFACTS_DIR, "location_ranker_v7_compat.joblib"))
    v7_calibrator = joblib.load(os.path.join(ARTIFACTS_DIR, "location_calibrator_v7_compat.joblib"))

    # 2. Load 3 fresh holdouts (6000 cases total)
    cases_legacy = load_legacy_holdout_56261(os.path.join(DATA_DIR, "qualification_holdout_56261.pkl"), cluster_dicts)
    cases_v62 = load_tabular_holdout(os.path.join(DATA_DIR, "qualification_holdout_56262.csv.gz"), "v6.2_holdout")
    cases_v63 = load_tabular_holdout(os.path.join(DATA_DIR, "qualification_holdout_56263.csv.gz"), "v6.3_holdout")
    cases_combined = cases_legacy + cases_v62 + cases_v63

    print(f"Loaded cases: Legacy={len(cases_legacy)}, V6.2={len(cases_v62)}, V6.3={len(cases_v63)} (Total: {len(cases_combined)})")

    # 3. Evaluate each regime
    print("\n--- Evaluating Regime 1: Legacy V4-style (Seed 56261, 2000 cases) ---")
    v4_legacy, v7_legacy = evaluate_models_on_cases(cases_legacy, cluster_dicts, cand_gen, v4_model, v4_calibrator, v7_model, v7_calibrator)
    print("V4 Legacy:", v4_legacy)
    print("V7-compat Legacy:", v7_legacy)

    print("\n--- Evaluating Regime 2: V6.2-style (Seed 56262, 2000 cases) ---")
    v4_v62, v7_v62 = evaluate_models_on_cases(cases_v62, cluster_dicts, cand_gen, v4_model, v4_calibrator, v7_model, v7_calibrator)
    print("V4 V6.2:", v4_v62)
    print("V7-compat V6.2:", v7_v62)

    print("\n--- Evaluating Regime 3: V6.3-style (Seed 56263, 2000 cases) ---")
    v4_v63, v7_v63 = evaluate_models_on_cases(cases_v63, cluster_dicts, cand_gen, v4_model, v4_calibrator, v7_model, v7_calibrator)
    print("V4 V6.3:", v4_v63)
    print("V7-compat V6.3:", v7_v63)

    print("\n--- Evaluating Combined 3-Regime Holdout (6000 cases) ---")
    v4_comb, v7_comb = evaluate_models_on_cases(cases_combined, cluster_dicts, cand_gen, v4_model, v4_calibrator, v7_model, v7_calibrator)
    print("V4 Combined:", v4_comb)
    print("V7-compat Combined:", v7_comb)

    # 4. Feature importance audit
    feat_audit = analyze_feature_importance(v7_model)
    print("\nFeature Importance Audit:", feat_audit)

    # 5. Check all promotion gates
    # A. Legacy Gates
    legacy_r1_pass = v7_legacy["r1"] >= v4_legacy["r1"] - 0.5
    legacy_r3_pass = v7_legacy["r3"] >= v4_legacy["r3"] - 0.5
    legacy_mrr_pass = v7_legacy["mrr"] >= v4_legacy["mrr"] - 0.005
    legacy_err_pass = v7_legacy["median_error_km"] <= v4_legacy["median_error_km"] + 0.50
    legacy_gates_pass = legacy_r1_pass and legacy_r3_pass and legacy_mrr_pass and legacy_err_pass

    # B. V6.2 Gates
    v62_r3_pass = v7_v62["r3"] >= v4_v62["r3"] + 3.0
    v62_mrr_pass = v7_v62["mrr"] > v4_v62["mrr"]
    v62_err_pass = v7_v62["median_error_km"] <= v4_v62["median_error_km"]
    v62_gates_pass = v62_r3_pass and v62_mrr_pass and v62_err_pass

    # C. V6.3 Gates
    v63_r3_pass = v7_v63["r3"] >= v4_v63["r3"] + 2.0
    v63_mrr_pass = v7_v63["mrr"] > v4_v63["mrr"]
    v63_err_pass = v7_v63["median_error_km"] <= v4_v63["median_error_km"]
    v63_gates_pass = v63_r3_pass and v63_mrr_pass and v63_err_pass

    # D. Combined Gates
    comb_recall_pass = (v7_comb["candidate_recall@25"] >= 72.0) and (v7_comb["candidate_recall@25"] >= v4_comb["candidate_recall@25"] - 0.5)
    comb_r1_pass = v7_comb["r1"] >= v4_comb["r1"]
    comb_r3_pass = v7_comb["r3"] >= v4_comb["r3"] + 3.0
    comb_r5_pass = v7_comb["r5"] >= v4_comb["r5"] + 2.0
    comb_mrr_pass = v7_comb["mrr"] >= v4_comb["mrr"] + 0.010
    comb_err_pass = v7_comb["median_error_km"] <= v4_comb["median_error_km"]
    comb_ece_pass = (v7_comb["ece"] <= 0.05) and (v7_comb["ece"] <= v4_comb["ece"] + 0.005)
    combined_gates_pass = (
        comb_recall_pass and comb_r1_pass and comb_r3_pass and comb_r5_pass and
        comb_mrr_pass and comb_err_pass and comb_ece_pass
    )

    all_gates_pass = legacy_gates_pass and v62_gates_pass and v63_gates_pass and combined_gates_pass

    print("\n" + "=" * 80)
    print("PROMOTION GATES EVALUATION SUMMARY:")
    print(f"1. Legacy Compatibility Gates: {legacy_gates_pass} (Top-1: {v7_legacy['r1']}% vs V4 {v4_legacy['r1']}%, Top-3: {v7_legacy['r3']}% vs V4 {v4_legacy['r3']}%, MRR: {v7_legacy['mrr']} vs V4 {v4_legacy['mrr']})")
    print(f"2. V6.2 Regime Gates: {v62_gates_pass} (Top-3: {v7_v62['r3']}% vs V4 {v4_v62['r3']}%, MRR: {v7_v62['mrr']} vs V4 {v4_v62['mrr']})")
    print(f"3. V6.3 Regime Gates: {v63_gates_pass} (Top-3: {v7_v63['r3']}% vs V4 {v4_v63['r3']}%, MRR: {v7_v63['mrr']} vs V4 {v4_v63['mrr']})")
    print(f"4. Combined 6000 Gates: {combined_gates_pass}")
    print(f"   - Candidate Recall: {comb_recall_pass} ({v7_comb['candidate_recall@25']}% vs V4 {v4_comb['candidate_recall@25']}%)")
    print(f"   - Top-1: {comb_r1_pass} ({v7_comb['r1']}% vs V4 {v4_comb['r1']}%)")
    print(f"   - Top-3: {comb_r3_pass} ({v7_comb['r3']}% vs V4 {v4_comb['r3']}%, Delta: +{v7_comb['r3'] - v4_comb['r3']:.2f}pp)")
    print(f"   - Top-5: {comb_r5_pass} ({v7_comb['r5']}% vs V4 {v4_comb['r5']}%, Delta: +{v7_comb['r5'] - v4_comb['r5']:.2f}pp)")
    print(f"   - MRR: {comb_mrr_pass} ({v7_comb['mrr']} vs V4 {v4_comb['mrr']}, Delta: +{v7_comb['mrr'] - v4_comb['mrr']:.4f})")
    print(f"   - Median Spatial Error: {comb_err_pass} ({v7_comb['median_error_km']} km vs V4 {v4_comb['median_error_km']} km)")
    print(f"   - ECE: {comb_ece_pass} ({v7_comb['ece']} vs V4 {v4_comb['ece']})")
    print(f"\nFINAL QUALIFICATION VERDICT: {'V7_COMPAT_QUALIFIED' if all_gates_pass else 'DISQUALIFIED'}")
    print("=" * 80)

    report = {
        "evaluation_timestamp": datetime.now(timezone.utc).isoformat(),
        "holdouts": {
            "legacy_seed_56261": {"cases": len(cases_legacy), "v4": v4_legacy, "v7_compat": v7_legacy, "pass": legacy_gates_pass},
            "v6_2_seed_56262": {"cases": len(cases_v62), "v4": v4_v62, "v7_compat": v7_v62, "pass": v62_gates_pass},
            "v6_3_seed_56263": {"cases": len(cases_v63), "v4": v4_v63, "v7_compat": v7_v63, "pass": v63_gates_pass}
        },
        "combined_6000": {
            "v4": v4_comb,
            "v7_compat": v7_comb,
            "improvement": {
                "top3_delta_pp": round(v7_comb["r3"] - v4_comb["r3"], 2),
                "mrr_delta": round(v7_comb["mrr"] - v4_comb["mrr"], 4),
                "spatial_error_delta_km": round(v4_comb["median_error_km"] - v7_comb["median_error_km"], 2)
            },
            "pass": combined_gates_pass
        },
        "feature_audit": feat_audit,
        "gates": {
            "legacy_gates_pass": legacy_gates_pass,
            "v62_gates_pass": v62_gates_pass,
            "v63_gates_pass": v63_gates_pass,
            "combined_gates_pass": combined_gates_pass,
            "all_gates_pass": all_gates_pass
        },
        "status": "V7_COMPAT_QUALIFIED" if all_gates_pass else "DISQUALIFIED"
    }

    out_path = os.path.join(EVAL_DIR, "v7_compat_external_qualification.json")
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Saved report to {out_path}")


if __name__ == "__main__":
    main()
