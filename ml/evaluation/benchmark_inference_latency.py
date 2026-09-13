"""
CyberShield AI — Phase A.4Q Pure ML Inference Latency Benchmark
Measures pure ML inference latency for V4 baseline and V7-compat stacked ranker
across 200 iterations on 25 candidate locations.
Uses the exact inference methods used in production without network/DB overhead.
"""

import os
import sys
import time
import numpy as np
import joblib

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.services.prediction_service import resolve_artifacts_dir


def run_latency_benchmark(n_iterations: int = 200):
    artifacts_dir = resolve_artifacts_dir()
    loc_v4_path = os.path.join(artifacts_dir, "location_ranker_v4.joblib")
    cal_v4_path = os.path.join(artifacts_dir, "location_calibrator_v4.joblib")
    loc_v7_path = os.path.join(artifacts_dir, "location_ranker_v7_compat.joblib")
    cal_v7_path = os.path.join(artifacts_dir, "location_calibrator_v7_compat.joblib")

    print(f"[Latency Benchmark] Loading artifacts from: {artifacts_dir}")
    m4 = joblib.load(loc_v4_path)
    c4 = joblib.load(cal_v4_path)
    m7 = joblib.load(loc_v7_path)
    c7 = joblib.load(cal_v7_path)

    # Standard candidate pool of 25 candidates with 43 canonical base features
    np.random.seed(42)
    X_loc = np.random.randn(25, 43).astype(np.float32)

    # Robust helper for V4 inference matching production
    def run_v4_inference(X):
        if hasattr(m4, "predict_proba"):
            raw = m4.predict_proba(X)[:, 1]
        else:
            raw = m4.predict(X)
        return c4.predict_proba(raw.reshape(-1, 1))[:, 1]

    # Warm-up runs
    for _ in range(10):
        _ = run_v4_inference(X_loc)

    # 1. Benchmark V4 pure ML latency
    t_v4 = []
    for _ in range(n_iterations):
        t0 = time.perf_counter()
        _ = run_v4_inference(X_loc)
        t_v4.append((time.perf_counter() - t0) * 1000.0)

    # 2. Benchmark V7-compat stacked ML latency
    # Warm-up
    for _ in range(10):
        v4_scores = run_v4_inference(X_loc)
        n_cands = 25
        ranks = np.argsort(-v4_scores)
        rank_pos = np.empty_like(ranks)
        rank_pos[ranks] = np.arange(n_cands)
        v4_ranks_norm = rank_pos / max(1.0, float(n_cands - 1))
        v4_percentiles = (n_cands - 1 - rank_pos) / max(1.0, float(n_cands - 1))
        best_v4 = float(np.max(v4_scores))
        v4_gaps = best_v4 - v4_scores
        v4_compat = np.column_stack([v4_scores, v4_ranks_norm, v4_percentiles, v4_gaps])
        X_compat = np.hstack([X_loc, v4_compat])
        raw_v7 = m7.predict(X_compat)
        _ = c7.predict_proba(raw_v7.reshape(-1, 1))[:, 1]

    t_v7 = []
    for _ in range(n_iterations):
        t0 = time.perf_counter()
        # Step A: V4 base score
        v4_scores = run_v4_inference(X_loc)
        # Step B: 4 compatibility features
        n_cands = 25
        ranks = np.argsort(-v4_scores)
        rank_pos = np.empty_like(ranks)
        rank_pos[ranks] = np.arange(n_cands)
        v4_ranks_norm = rank_pos / max(1.0, float(n_cands - 1))
        v4_percentiles = (n_cands - 1 - rank_pos) / max(1.0, float(n_cands - 1))
        best_v4 = float(np.max(v4_scores))
        v4_gaps = best_v4 - v4_scores
        v4_compat = np.column_stack([v4_scores, v4_ranks_norm, v4_percentiles, v4_gaps])
        X_compat = np.hstack([X_loc, v4_compat])
        # Step C: V7-compat ranker prediction
        raw_v7 = m7.predict(X_compat)
        # Step D: Platt calibration
        _ = c7.predict_proba(raw_v7.reshape(-1, 1))[:, 1]
        t_v7.append((time.perf_counter() - t0) * 1000.0)

    results = {
        "iterations": n_iterations,
        "candidate_pool_size": 25,
        "v4_latency_median_ms": float(np.median(t_v4)),
        "v4_latency_p95_ms": float(np.percentile(t_v4, 95)),
        "v4_latency_mean_ms": float(np.mean(t_v4)),
        "v7_compat_latency_median_ms": float(np.median(t_v7)),
        "v7_compat_latency_p95_ms": float(np.percentile(t_v7, 95)),
        "v7_compat_latency_mean_ms": float(np.mean(t_v7)),
        "stacked_overhead_median_ms": float(np.median(t_v7) - np.median(t_v4))
    }

    print("\n========================================================")
    print("CYBERSHIELD AI — PURE ML INFERENCE LATENCY BENCHMARK")
    print("========================================================")
    print(f"Iterations: {n_iterations} on 25 candidates")
    print(f"V4 Baseline:")
    print(f"  Median: {results['v4_latency_median_ms']:.2f} ms")
    print(f"  p95:    {results['v4_latency_p95_ms']:.2f} ms")
    print(f"V7-compat Stacked Ranker:")
    print(f"  Median: {results['v7_compat_latency_median_ms']:.2f} ms")
    print(f"  p95:    {results['v7_compat_latency_p95_ms']:.2f} ms")
    print(f"Stacking Overhead (V7-compat vs V4):")
    print(f"  Delta:  +{results['stacked_overhead_median_ms']:.2f} ms")
    print("========================================================\n")

    return results


if __name__ == "__main__":
    run_latency_benchmark()
