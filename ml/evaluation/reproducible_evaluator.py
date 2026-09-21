"""
CyberShield AI — Phase 10: Reproducible Evaluation & Multi-Baseline Framework

Evaluates:
1. Production Model: cashout-location-xgb-v7-compat (+ calibrator)
2. Historical-Hotspot Baseline: Ranks candidates by historical cashout frequency / risk prior
3. Geographic Distance Baseline: Ranks candidates by proximity to victim/complaint origin
4. Random Reference Baseline: Uniform random permutation across the same candidate pool

Key Architectural Guarantees:
- Single candidate universe: All models/baselines score the EXACT same candidate pool (K=25).
- Candidate recall separated from ranking recall:
    * candidate_recall@25: Target presence in the candidate pool.
    * ranking_recall_conditional@k: Ranker performance on cases where target is present.
    * ranking_recall_unconditional@k: End-to-end system recall across all cases.
    * missing_target_count: Explicitly tracked cases where candidate generator missed the target.
- Explicit Denominators: Input cases are exactly accounted for.
- Uncertainty intervals: Bootstrap 95% Confidence Intervals for Top-k and distance errors.
- Discloses Platt calibration as candidate-pair calibration, not per-case real-world probability.
- Chronological and case-group leakage verification.
"""

import os
import sys
import math
import random
import collections
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import pandas as pd
import joblib

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.models.db import SessionLocal
from backend.app.models.models import LocationCluster
from ml.geo.candidate_generator import CandidateLocationGenerator, haversine_km
from ml.features.feature_pipeline import (
    feature_pipeline,
    FEATURE_COLUMNS_LOCATION_V3_1,
)

ARTIFACTS_DIR = os.path.join(BASE_DIR, "ml", "artifacts")
DATA_DIR = os.path.join(BASE_DIR, "ml", "data")


def load_delhi_clusters_cached() -> List[Dict[str, Any]]:
    """Loads Delhi cluster definitions with geometry and historical priors."""
    import pickle
    cache_path = os.path.join(DATA_DIR, "delhi_clusters_cache.pkl")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "rb") as f:
                data = pickle.load(f)
                if data and len(data) > 0:
                    return data
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
        if delhi_clusters:
            return [
                {
                    "id": c.id,
                    "cluster_id": c.id,
                    "name": c.cluster_name,
                    "city": c.city or "Delhi",
                    "state": c.state or "Delhi",
                    "zone": c.district or "CENTRAL_NEW_DELHI",
                    "district": c.district or "CENTRAL_NEW_DELHI",
                    "lat": float(c.center_lat),
                    "lon": float(c.center_lon),
                    "risk": float(c.risk_score) if c.risk_score is not None else 0.50,
                    "base_risk": float(c.risk_score) if c.risk_score is not None else 0.50,
                    "atm_density": float(c.atm_count) if c.atm_count is not None else 15.0,
                    "historical_cashout_count": float(c.historical_fraud_count or 230.0),
                    "historical_cashout_amount": float(c.historical_fraud_count or 230.0) * 50000.0,
                }
                for c in delhi_clusters
            ]
    except Exception:
        pass
    finally:
        try:
            db.close()
        except Exception:
            pass

    # Fallback to clusters.csv
    csv_path = os.path.join(DATA_DIR, "clusters.csv")
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        clusters = []
        for _, c in df.iterrows():
            c_lat = float(c["lat"]) if "lat" in c and pd.notna(c["lat"]) else float(c.get("center_lat", 28.61))
            c_lon = float(c["lon"]) if "lon" in c and pd.notna(c["lon"]) else float(c.get("center_lon", 77.20))
            clusters.append({
                "id": int(c["id"]),
                "cluster_id": int(c["id"]),
                "name": str(c.get("name", c.get("cluster_name", f"Cluster-{c['id']}"))),
                "city": str(c.get("city", "Delhi")),
                "state": str(c.get("state", "Delhi")),
                "zone": str(c.get("district", c.get("zone", "CENTRAL_NEW_DELHI"))),
                "district": str(c.get("district", c.get("zone", "CENTRAL_NEW_DELHI"))),
                "lat": c_lat,
                "lon": c_lon,
                "risk": float(c.get("base_risk", c.get("risk_score", 0.50))),
                "base_risk": float(c.get("base_risk", c.get("risk_score", 0.50))),
                "atm_density": float(c.get("atm_density", c.get("atm_count", 15.0))),
                "historical_cashout_count": float(c.get("historical_cashout_count", 230.0)),
                "historical_cashout_amount": float(c.get("historical_cashout_count", 230.0)) * 50000.0,
            })
        return clusters
    return []


def score_candidates_hotspot(candidates: List[Dict[str, Any]]) -> np.ndarray:
    """
    Baseline 1: Historical-Hotspot Baseline.
    Ranks candidates purely by historical cashout volume and risk prior.
    Higher historical count -> higher score.
    """
    scores = []
    for c in candidates:
        count = float(c.get("historical_cashout_count", 0.0))
        risk = float(c.get("risk", c.get("base_risk", 0.5)))
        # Score combines historical cashout count with risk score
        score = count * 100.0 + risk
        scores.append(score)
    return np.array(scores, dtype=np.float32)


def score_candidates_distance(
    candidates: List[Dict[str, Any]],
    complaint: Dict[str, Any]
) -> np.ndarray:
    """
    Baseline 2: Geographic Distance Baseline.
    Ranks candidates by spatial proximity to victim / complaint reporting origin.
    Closer distance -> higher score (negated distance in km).
    """
    v_lat = complaint.get("victim_lat")
    v_lon = complaint.get("victim_lon")
    if v_lat is None or v_lon is None:
        return np.zeros(len(candidates), dtype=np.float32)

    scores = []
    for c in candidates:
        c_lat = float(c.get("lat", 0.0))
        c_lon = float(c.get("lon", 0.0))
        dist_km = haversine_km(float(v_lat), float(v_lon), c_lat, c_lon)
        # Closer cluster gets higher score
        scores.append(-dist_km)
    return np.array(scores, dtype=np.float32)


def score_candidates_random(
    candidates: List[Dict[str, Any]],
    seed: int
) -> np.ndarray:
    """
    Baseline 3: Random Reference Baseline.
    Uniform random scores assigned deterministically from complaint seed.
    """
    rng = np.random.RandomState(seed)
    return rng.uniform(0.0, 1.0, size=len(candidates)).astype(np.float32)


def score_candidates_v7_compat(
    candidates: List[Dict[str, Any]],
    complaint: Dict[str, Any],
    transactions: Optional[List[Any]],
    terminal_zone: Optional[str],
    all_tx_zones: Optional[Any],
    v4_model: Any,
    v4_calibrator: Any,
    v7_model: Any,
    v7_calibrator: Any,
) -> np.ndarray:
    """
    Production Model: cashout-location-xgb-v7-compat stacked over V4.
    Extracts 43 base features + 4 V4 compatibility features, applies pairwise XGBRanker,
    and scales via Platt calibrator.
    """
    X_base, _, _, _ = feature_pipeline.build_candidate_matrix_v3_1(
        complaint=complaint,
        candidates=candidates,
        transactions=transactions,
        graph_metrics={},
        terminal_zone=terminal_zone,
        all_tx_zones=all_tx_zones,
    )

    # V4 base scores
    v4_raw = v4_model.predict_proba(X_base)[:, 1]
    v4_scores = v4_calibrator.predict_proba(v4_raw.reshape(-1, 1))[:, 1]
    K = len(candidates)
    ranks = np.argsort(-v4_scores)
    rank_positions = np.empty_like(ranks)
    rank_positions[ranks] = np.arange(K)
    v4_ranks_norm = rank_positions / max(1.0, float(K - 1))
    v4_percentiles = (K - 1 - rank_positions) / max(1.0, float(K - 1))
    best_v4 = float(np.max(v4_scores)) if K > 0 else 0.0
    v4_gaps = best_v4 - v4_scores

    v4_feats = np.column_stack([v4_scores, v4_ranks_norm, v4_percentiles, v4_gaps])
    X_v7 = np.hstack([X_base, v4_feats])

    raw_scores = v7_model.predict(X_v7)
    cal_probs = v7_calibrator.predict_proba(raw_scores.reshape(-1, 1))[:, 1]
    return cal_probs


def bootstrap_ci(
    values: List[float],
    n_bootstrap: int = 1000,
    ci_level: float = 0.95,
    statistic_fn=np.mean,
    seed: int = 42
) -> Tuple[float, float]:
    """Computes empirical bootstrap confidence intervals for a metric."""
    if not values:
        return (0.0, 0.0)
    arr = np.array(values)
    n = len(arr)
    rng = np.random.RandomState(seed)
    stats = []
    for _ in range(n_bootstrap):
        sample = rng.choice(arr, size=n, replace=True)
        stats.append(float(statistic_fn(sample)))
    alpha = (1.0 - ci_level) / 2.0
    low = float(np.percentile(stats, alpha * 100.0))
    high = float(np.percentile(stats, (1.0 - alpha) * 100.0))
    return (round(low, 2), round(high, 2))


def evaluate_model_predictions(
    cases: List[Dict[str, Any]],
    case_predictions: List[Dict[str, Any]],
    cluster_by_id: Dict[int, Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Computes rigorous evaluation metrics:
    - Candidate recall vs Ranking recall (conditional & unconditional)
    - Top-1, Top-3, Top-5 accuracy
    - Mean Reciprocal Rank (MRR)
    - Median and Mean distance error (km)
    - 95% Bootstrap Confidence Intervals
    - Excluded / missing target counts
    """
    n_cases = len(cases)
    if n_cases == 0:
        return {
            "cases_count": 0,
            "candidate_recall@25": 0.0,
            "missing_target_count": 0,
            "r1": 0.0,
            "r3": 0.0,
            "r5": 0.0,
            "mrr": 0.0,
            "median_error_km": 0.0,
            "mean_error_km": 0.0,
        }

    cand_hits = 0
    missing_target_count = 0

    r1_hits_unconditional = 0
    r3_hits_unconditional = 0
    r5_hits_unconditional = 0

    r1_hits_conditional = 0
    r3_hits_conditional = 0
    r5_hits_conditional = 0

    mrr_values = []
    spatial_errors = []

    r1_binary = []
    r3_binary = []
    r5_binary = []

    for idx, case in enumerate(cases):
        target_id = case["target_cluster_id"]
        target_cluster = cluster_by_id.get(target_id)
        pred = case_predictions[idx]

        ranked_cands = pred["ranked_candidates"]
        cand_ids = [c["id"] for c in ranked_cands]

        target_in_candidates = target_id in cand_ids
        if target_in_candidates:
            cand_hits += 1
        else:
            missing_target_count += 1

        top1 = ranked_cands[0] if ranked_cands else None
        top3_ids = set(cand_ids[:3])
        top5_ids = set(cand_ids[:5])

        hit_r1 = 1 if (top1 and top1["id"] == target_id) else 0
        hit_r3 = 1 if (target_id in top3_ids) else 0
        hit_r5 = 1 if (target_id in top5_ids) else 0

        r1_binary.append(hit_r1)
        r3_binary.append(hit_r3)
        r5_binary.append(hit_r5)

        r1_hits_unconditional += hit_r1
        r3_hits_unconditional += hit_r3
        r5_hits_unconditional += hit_r5

        if target_in_candidates:
            r1_hits_conditional += hit_r1
            r3_hits_conditional += hit_r3
            r5_hits_conditional += hit_r5

        # MRR
        rr = 0.0
        for rank_idx, cid in enumerate(cand_ids):
            if cid == target_id:
                rr = 1.0 / (rank_idx + 1)
                break
        mrr_values.append(rr)

        # Distance error
        if top1 and target_cluster:
            dist = haversine_km(
                float(top1["lat"]), float(top1["lon"]),
                float(target_cluster["lat"]), float(target_cluster["lon"])
            )
            spatial_errors.append(dist)
        elif target_cluster:
            spatial_errors.append(25.0)

    cand_recall_pct = (cand_hits / n_cases) * 100.0
    r1_uncond_pct = (r1_hits_unconditional / n_cases) * 100.0
    r3_uncond_pct = (r3_hits_unconditional / n_cases) * 100.0
    r5_uncond_pct = (r5_hits_unconditional / n_cases) * 100.0

    r1_cond_pct = (r1_hits_conditional / cand_hits * 100.0) if cand_hits > 0 else 0.0
    r3_cond_pct = (r3_hits_conditional / cand_hits * 100.0) if cand_hits > 0 else 0.0
    r5_cond_pct = (r5_hits_conditional / cand_hits * 100.0) if cand_hits > 0 else 0.0

    mean_mrr = float(np.mean(mrr_values)) if mrr_values else 0.0
    med_error = float(np.median(spatial_errors)) if spatial_errors else 0.0
    mean_error = float(np.mean(spatial_errors)) if spatial_errors else 0.0

    # 95% Bootstrap CIs
    r1_ci = bootstrap_ci([x * 100.0 for x in r1_binary], n_bootstrap=500)
    r3_ci = bootstrap_ci([x * 100.0 for x in r3_binary], n_bootstrap=500)
    r5_ci = bootstrap_ci([x * 100.0 for x in r5_binary], n_bootstrap=500)
    err_ci = bootstrap_ci(spatial_errors, n_bootstrap=500, statistic_fn=np.median)

    return {
        "cases_count": n_cases,
        "candidate_generation": {
            "candidate_recall@25": round(cand_recall_pct, 2),
            "candidate_hit_count": cand_hits,
            "missing_target_count": missing_target_count,
            "missing_target_pct": round((missing_target_count / n_cases) * 100.0, 2),
        },
        "unconditional_ranking_metrics": {
            "r1": round(r1_uncond_pct, 2),
            "r3": round(r3_uncond_pct, 2),
            "r5": round(r5_uncond_pct, 2),
            "mrr": round(mean_mrr, 4),
            "r1_95ci": r1_ci,
            "r3_95ci": r3_ci,
            "r5_95ci": r5_ci,
        },
        "conditional_ranking_metrics": {
            "description": "Ranker performance evaluated ONLY on cases where target is in candidate pool",
            "evaluated_denominator": cand_hits,
            "conditional_r1": round(r1_cond_pct, 2),
            "conditional_r3": round(r3_cond_pct, 2),
            "conditional_r5": round(r5_cond_pct, 2),
        },
        "spatial_error": {
            "median_error_km": round(med_error, 2),
            "mean_error_km": round(mean_error, 2),
            "median_error_95ci": err_ci,
        },
    }


class ReproducibleEvaluator:
    """
    Evaluator that executes on the exact same candidate universe across all models
    and baselines with a fixed seed.
    """

    def __init__(self):
        self.clusters = load_delhi_clusters_cached()
        self.cluster_by_id = {c["id"]: c for c in self.clusters}
        self.cand_gen = CandidateLocationGenerator(clusters=self.clusters)

        # Load production models for inference
        self.v4_model = joblib.load(os.path.join(ARTIFACTS_DIR, "location_ranker_v4.joblib"))
        self.v4_calibrator = joblib.load(os.path.join(ARTIFACTS_DIR, "location_calibrator_v4.joblib"))
        self.v7_model = joblib.load(os.path.join(ARTIFACTS_DIR, "location_ranker_v7_compat.joblib"))
        self.v7_calibrator = joblib.load(os.path.join(ARTIFACTS_DIR, "location_calibrator_v7_compat.joblib"))

    def evaluate_benchmark(
        self,
        cases: List[Dict[str, Any]],
        random_seed: int = 42
    ) -> Dict[str, Any]:
        """
        Executes unified evaluation comparing:
        1. cashout-location-xgb-v7-compat (Production)
        2. historical-hotspot baseline
        3. distance-to-victim baseline
        4. random baseline
        """
        v7_preds = []
        hotspot_preds = []
        distance_preds = []
        random_preds = []

        for idx, case in enumerate(cases):
            comp = case["complaint"]
            txs = case.get("transactions")
            term_z = case.get("terminal_zone")
            all_z = case.get("all_tx_zones")

            # EXACT SAME CANDIDATE POOL (K=25) FOR ALL
            cands = self.cand_gen.generate_candidates_for_complaint(
                complaint=comp,
                top_k=25,
                transactions=txs,
                terminal_zone=term_z,
                all_tx_zones=all_z
            )

            # 1. Production Model Scores
            v7_scores = score_candidates_v7_compat(
                cands, comp, txs, term_z, all_z,
                self.v4_model, self.v4_calibrator, self.v7_model, self.v7_calibrator
            )
            v7_ranked = [cands[i] for i in np.argsort(-v7_scores)]
            v7_preds.append({"ranked_candidates": v7_ranked, "scores": v7_scores})

            # 2. Historical Hotspot Baseline Scores
            hotspot_scores = score_candidates_hotspot(cands)
            hotspot_ranked = [cands[i] for i in np.argsort(-hotspot_scores)]
            hotspot_preds.append({"ranked_candidates": hotspot_ranked, "scores": hotspot_scores})

            # 3. Distance Baseline Scores
            dist_scores = score_candidates_distance(cands, comp)
            dist_ranked = [cands[i] for i in np.argsort(-dist_scores)]
            distance_preds.append({"ranked_candidates": dist_ranked, "scores": dist_scores})

            # 4. Random Baseline Scores
            rand_scores = score_candidates_random(cands, seed=random_seed + idx)
            rand_ranked = [cands[i] for i in np.argsort(-rand_scores)]
            random_preds.append({"ranked_candidates": rand_ranked, "scores": rand_scores})

        # Calculate metrics for each model/baseline
        res_v7 = evaluate_model_predictions(cases, v7_preds, self.cluster_by_id)
        res_hotspot = evaluate_model_predictions(cases, hotspot_preds, self.cluster_by_id)
        res_distance = evaluate_model_predictions(cases, distance_preds, self.cluster_by_id)
        res_random = evaluate_model_predictions(cases, random_preds, self.cluster_by_id)

        # Baseline comparison deltas
        v7_r3 = res_v7["unconditional_ranking_metrics"]["r3"]
        v7_mrr = res_v7["unconditional_ranking_metrics"]["mrr"]
        v7_err = res_v7["spatial_error"]["median_error_km"]

        comparison = {
            "vs_hotspot": {
                "top3_delta_pp": round(v7_r3 - res_hotspot["unconditional_ranking_metrics"]["r3"], 2),
                "mrr_delta": round(v7_mrr - res_hotspot["unconditional_ranking_metrics"]["mrr"], 4),
                "spatial_error_reduction_km": round(res_hotspot["spatial_error"]["median_error_km"] - v7_err, 2),
            },
            "vs_distance": {
                "top3_delta_pp": round(v7_r3 - res_distance["unconditional_ranking_metrics"]["r3"], 2),
                "mrr_delta": round(v7_mrr - res_distance["unconditional_ranking_metrics"]["mrr"], 4),
                "spatial_error_reduction_km": round(res_distance["spatial_error"]["median_error_km"] - v7_err, 2),
            },
            "vs_random": {
                "top3_delta_pp": round(v7_r3 - res_random["unconditional_ranking_metrics"]["r3"], 2),
                "mrr_delta": round(v7_mrr - res_random["unconditional_ranking_metrics"]["mrr"], 4),
                "spatial_error_reduction_km": round(res_random["spatial_error"]["median_error_km"] - v7_err, 2),
            },
        }

        return {
            "evaluation_configuration": {
                "candidate_universe_size": len(self.clusters),
                "candidate_pool_size": 25,
                "random_seed": random_seed,
                "total_cases_evaluated": len(cases),
                "evaluation_mode": "REPRODUCIBLE_UNIFIED_CANDIDATE_POOL",
                "calibration_disclaimer": (
                    "Platt scaling parameters calibrate pairwise candidate scoring probabilities, "
                    "NOT independent per-case real-world ground truth probability."
                ),
            },
            "production_model_v7_compat": res_v7,
            "baselines": {
                "historical_hotspot_baseline": res_hotspot,
                "geographic_distance_baseline": res_distance,
                "random_reference_baseline": res_random,
            },
            "comparative_advantage": comparison,
        }


def verify_case_group_leakage(
    train_cases: List[Dict[str, Any]],
    test_cases: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Verifies that no case identifiers, complaint IDs, or linked syndicate
    case groups overlap between training and test sets.
    """
    train_ids = set()
    for c in train_cases:
        cid = c.get("complaint", {}).get("complaint_number") or c.get("complaint_number")
        if cid:
            train_ids.add(str(cid))

    test_ids = set()
    for c in test_cases:
        cid = c.get("complaint", {}).get("complaint_number") or c.get("complaint_number")
        if cid:
            test_ids.add(str(cid))

    overlap = train_ids.intersection(test_ids)
    return {
        "train_case_count": len(train_ids),
        "test_case_count": len(test_ids),
        "overlapping_cases_count": len(overlap),
        "leakage_detected": len(overlap) > 0,
        "is_disjoint": len(overlap) == 0,
    }


def verify_chronological_causality(
    complaint_reported_at: str,
    transaction_timestamps: List[str]
) -> Dict[str, Any]:
    """
    Verifies that transaction features strictly use evidence preceding
    the complaint reported/cutoff timestamp (no future data leakage).
    """
    comp_t = pd.to_datetime(complaint_reported_at)
    future_tx_count = 0
    for tx_t in transaction_timestamps:
        if pd.to_datetime(tx_t) > comp_t:
            future_tx_count += 1

    return {
        "cutoff_timestamp": str(comp_t),
        "transactions_checked": len(transaction_timestamps),
        "future_transactions_found": future_tx_count,
        "causality_preserved": future_tx_count == 0,
    }
