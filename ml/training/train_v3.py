"""
CyberShield AI — Location Model V3 Leakage-Free Training Pipeline
Phase 1 Step 8: Multi-Modal XGBoost Model Retraining

This script trains Location Model V3 (38 features) without target identity leakage:
- ZERO mule corridor flag (is_mule_corridor removed)
- ZERO distance to high risk account proxy (distance_from_high_risk_account removed)
- ZERO candidate generator target knowledge (no beneficiary_mule_cluster_id)
- STRICT temporal train / validation / test splits
- Candidate force-add ONLY in training for supervised sample generation with identical feature construction
- Strict ZERO force-add in validation and test evaluation
- Evaluates honest Natural Candidate Recall and Top-K metrics on held-out test data
- Produces location_ranker_v3.joblib, location_calibrator_v3.joblib, feature_schema_v3.json, model_metadata_v3.json
- Preserves Time Model V2 and legacy V2 artifacts untouched
"""

import os
import sys
import json
import math
import hashlib
import collections
from datetime import datetime
import numpy as np
import pandas as pd
import joblib
import networkx as nx
from xgboost import XGBClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from ml.geo.candidate_generator import CandidateLocationGenerator, haversine_km
from ml.features.feature_pipeline import (
    feature_pipeline,
    FEATURE_COLUMNS_LOCATION_V3,
    FEATURE_COLUMNS_TIME,
    FRAUD_TYPE_MAP_V3,
    CHANNEL_MAP_V3
)

RANDOM_SEED = 42


def compute_ece(probs: np.ndarray, labels: np.ndarray, n_bins: int = 10) -> float:
    """Computes Expected Calibration Error across n_bins."""
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        bin_lower, bin_upper = bin_boundaries[i], bin_boundaries[i + 1]
        in_bin = (probs >= bin_lower) & (probs < bin_upper) if i < n_bins - 1 else (probs >= bin_lower) & (probs <= bin_upper)
        prop_in_bin = np.mean(in_bin)
        if prop_in_bin > 0:
            accuracy_in_bin = np.mean(labels[in_bin])
            avg_confidence_in_bin = np.mean(probs[in_bin])
            ece += np.abs(accuracy_in_bin - avg_confidence_in_bin) * prop_in_bin
    return float(ece)


def main():
    print("=" * 80)
    print("CYBERSHIELD AI — LEAKAGE-FREE LOCATION MODEL V3 RETRAINING")
    print("=" * 80)

    artifacts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "artifacts"))
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
    os.makedirs(artifacts_dir, exist_ok=True)
    np.random.seed(RANDOM_SEED)

    # 1. Load Data
    print("[1/7] Loading dataset...")
    clusters_df = pd.read_csv(os.path.join(data_dir, "clusters.csv.gz"), compression="gzip")
    complaints_df = pd.read_csv(os.path.join(data_dir, "complaints.csv.gz"), compression="gzip")
    transactions_df = pd.read_csv(os.path.join(data_dir, "transactions.csv.gz"), compression="gzip")

    clusters_list = clusters_df.to_dict(orient="records")
    for c in clusters_list:
        c["id"] = int(c["id"])
        c["lat"] = float(c["lat"])
        c["lon"] = float(c["lon"])
        c["base_risk"] = float(c.get("base_risk", 0.5))
        c["atm_density"] = float(c.get("atm_density", 15))

    cluster_by_id = {c["id"]: c for c in clusters_list}
    cluster_coords = {c["id"]: (c["lat"], c["lon"]) for c in clusters_list}

    # 2. Chronological Split (70% Train, 15% Val, 15% Test)
    print("[2/7] Enforcing strict chronological train/validation/test split...")
    complaints_df = complaints_df.sort_values(by="incident_timestamp").reset_index(drop=True)

    train_n = 14000
    val_n = 3000
    test_n = 3000

    train_df = complaints_df.iloc[:train_n].copy()
    val_df = complaints_df.iloc[train_n : train_n + val_n].copy()
    test_df = complaints_df.iloc[train_n + val_n : train_n + val_n + test_n].copy()

    assert train_df["incident_timestamp"].max() <= val_df["incident_timestamp"].min(), "Temporal leak: train overlap with validation"
    assert val_df["incident_timestamp"].max() <= test_df["incident_timestamp"].min(), "Temporal leak: val overlap with test"
    print(f" -> Temporal non-overlap verified.")
    print(f"    Train: {len(train_df)} ({train_df['incident_timestamp'].min()} to {train_df['incident_timestamp'].max()})")
    print(f"    Val:   {len(val_df)} ({val_df['incident_timestamp'].min()} to {val_df['incident_timestamp'].max()})")
    print(f"    Test:  {len(test_df)} ({test_df['incident_timestamp'].min()} to {test_df['incident_timestamp'].max()})")

    # 3. Fit Frozen Cluster Baselines EXCLUSIVELY on Train Split
    print("[3/7] Fitting frozen cluster historical baselines from train split only...")
    train_cluster_counts = train_df["target_cluster_id"].value_counts().to_dict()
    train_cluster_amounts = train_df.groupby("target_cluster_id")["amount"].sum().to_dict()

    for c in clusters_list:
        cid = c["id"]
        c["historical_cashout_count"] = float(train_cluster_counts.get(cid, 200.0))
        c["historical_cashout_amount"] = float(train_cluster_amounts.get(cid, 10000000.0))

    cand_gen = CandidateLocationGenerator(clusters_list)

    # Pre-index transactions by complaint_id
    print(" -> Indexing transactions and building NetworkX graph metrics per complaint...")
    tx_by_comp = collections.defaultdict(list)
    for row in transactions_df.to_dict(orient="records"):
        tx_by_comp[int(row["complaint_id"])].append(row)

    def extract_graph_for_complaint(cid: int, tx_list: list) -> dict:
        if not tx_list:
            return {
                "node_count": 0, "max_degree": 0.0, "mean_degree": 0.0,
                "max_pagerank": 0.0, "max_betweenness": 0.0, "connected_components": 0,
                "intermediary_count": 0, "sink_count": 0, "branching_factor": 0.0, "max_hop": 0.0
            }

        G = nx.DiGraph()
        for t in tx_list:
            u, v = str(t["from_account"]), str(t["to_account"])
            G.add_edge(u, v, weight=float(t.get("amount", 0.0)))

        deg = [G.degree(n) for n in G.nodes()]
        max_deg = float(max(deg)) if deg else 0.0
        mean_deg = float(np.mean(deg)) if deg else 0.0

        pr = nx.pagerank(G, weight="weight", alpha=0.85) if len(G) > 0 else {}
        max_pr = float(max(pr.values())) if pr else 0.0

        btw = nx.betweenness_centrality(G, weight="weight") if len(G) > 0 else {}
        max_btw = float(max(btw.values())) if btw else 0.0

        cc = nx.number_weakly_connected_components(G) if len(G) > 0 else 0
        sinks = sum(1 for n in G.nodes() if G.in_degree(n) > 0 and G.out_degree(n) == 0)
        intermediaries = sum(1 for n in G.nodes() if G.in_degree(n) > 0 and G.out_degree(n) > 0)

        out_deg = [G.out_degree(n) for n in G.nodes() if G.out_degree(n) > 0]
        branching = float(round(sum(out_deg) / len(out_deg), 2)) if out_deg else 0.0

        max_h = float(max(int(t.get("hop_number", 1)) for t in tx_list))

        return {
            "node_count": len(G.nodes()),
            "max_degree": max_deg,
            "mean_degree": mean_deg,
            "max_pagerank": max_pr,
            "max_betweenness": max_btw,
            "connected_components": cc,
            "intermediary_count": intermediaries,
            "sink_count": sinks,
            "branching_factor": branching,
            "max_hop": max_h
        }

    graph_metrics_by_comp = {cid: extract_graph_for_complaint(cid, txs) for cid, txs in tx_by_comp.items()}

    # 4. Build Candidate Matrices
    print("[4/7] Generating candidate pools and multimodal feature rows...")

    def build_split_data(complaints_subset, is_training=False):
        X_loc_list = []
        y_loc_list = []
        eval_meta = []
        natural_hits = 0

        for comp in complaints_subset:
            cid = int(comp["complaint_id"])
            target_cl_id = int(comp["target_cluster_id"])
            txs = tx_by_comp.get(cid, [])
            gm = graph_metrics_by_comp.get(cid)

            # Generate natural candidates (ZERO target knowledge)
            cands = cand_gen.generate_candidates_for_complaint(comp, top_k=25)
            cand_ids = [c["cluster_id"] for c in cands]
            target_in_cands = (target_cl_id in cand_ids)

            if target_in_cands:
                natural_hits += 1

            if is_training:
                # Training ONLY: append positive target if absent so supervised sample has y=1
                # CRITICAL: Constructed with identical feature formula as distractors!
                if not target_in_cands and target_cl_id in cluster_by_id:
                    t_cl = cluster_by_id[target_cl_id]
                    v_lat = float(comp.get("victim_lat", t_cl["lat"]))
                    v_lon = float(comp.get("victim_lon", t_cl["lon"]))
                    dist_v = round(haversine_km(v_lat, v_lon, t_cl["lat"], t_cl["lon"]), 1)
                    cands.append({
                        "cluster_id": t_cl["id"],
                        "name": t_cl["name"],
                        "city": t_cl["city"],
                        "state": t_cl["state"],
                        "lat": t_cl["lat"],
                        "lon": t_cl["lon"],
                        "latitude": t_cl["lat"],
                        "longitude": t_cl["lon"],
                        "atm_density": float(t_cl.get("atm_density", 15.0)),
                        "historical_risk": float(t_cl.get("base_risk", 0.5)),
                        "historical_cashout_count": float(t_cl.get("historical_cashout_count", 200.0)),
                        "historical_cashout_amount": float(t_cl.get("historical_cashout_amount", 10000000.0)),
                        "distance_from_victim_km": dist_v,
                        "reasoning": "Regional candidate (training supervision sample)"
                    })

            # Build feature rows (38 features)
            X_loc, _, _, _ = feature_pipeline.build_candidate_matrix_v3(comp, cands, txs, gm)
            labels = [1 if c["cluster_id"] == target_cl_id else 0 for c in cands]

            X_loc_list.append(X_loc)
            y_loc_list.extend(labels)

            eval_meta.append({
                "complaint_id": cid,
                "target_cluster_id": target_cl_id,
                "target_coords": cluster_coords.get(target_cl_id, (comp.get("victim_lat", 28.6), comp.get("victim_lon", 77.2))),
                "candidates": cands,
                "n_candidates": len(cands),
                "target_in_candidates": target_in_cands
            })

        X_location = np.vstack(X_loc_list) if X_loc_list else np.empty((0, len(FEATURE_COLUMNS_LOCATION_V3)), dtype=np.float32)
        y_location = np.array(y_loc_list, dtype=np.int32)
        cand_recall_pct = (natural_hits / max(1, len(complaints_subset))) * 100.0

        return X_location, y_location, eval_meta, cand_recall_pct

    train_complaints = train_df.to_dict(orient="records")
    val_complaints = val_df.to_dict(orient="records")
    test_complaints = test_df.to_dict(orient="records")

    print(" -> Building train feature matrix (target appended if absent for supervision)...")
    X_train_loc, y_train_loc, _, train_cand_recall = build_split_data(train_complaints, is_training=True)

    print(" -> Building validation feature matrix (STRICT ZERO FORCE-ADD)...")
    X_val_loc, y_val_loc, val_meta, val_cand_recall = build_split_data(val_complaints, is_training=False)

    print(" -> Building test feature matrix (STRICT ZERO FORCE-ADD)...")
    X_test_loc, y_test_loc, test_meta, test_cand_recall = build_split_data(test_complaints, is_training=False)

    print(f" -> Natural Candidate Recall (Zero Force-Add):")
    print(f"    Train natural: {train_cand_recall:.2f}%")
    print(f"    Validation:    {val_cand_recall:.2f}%")
    print(f"    Test:          {test_cand_recall:.2f}%")
    print(f" -> Feature dimensions: {X_train_loc.shape[1]} location features.")
    assert X_train_loc.shape[1] == 38, f"Expected 38 features, got {X_train_loc.shape[1]}"

    # 5. Train Location Ranking XGBoost Model V3
    print("[5/7] Training Location Ranking XGBoost Model V3...")
    pos_count = sum(y_train_loc)
    neg_count = len(y_train_loc) - pos_count
    pos_weight = float(neg_count / max(1, pos_count))

    location_clf_v3 = XGBClassifier(
        n_estimators=130,
        max_depth=5,
        learning_rate=0.07,
        scale_pos_weight=pos_weight * 0.5,
        random_state=RANDOM_SEED,
        eval_metric="logloss",
        n_jobs=-1
    )
    location_clf_v3.fit(X_train_loc, y_train_loc, eval_set=[(X_val_loc, y_val_loc)], verbose=False)
    print(" -> Location Model V3 trained successfully.")

    # 6. Fit Platt Calibrator on Validation Split
    print("[6/7] Fitting Platt Calibrator on validation predictions only...")
    val_raw_probs = location_clf_v3.predict_proba(X_val_loc)[:, 1]
    val_logits = np.log(np.clip(val_raw_probs, 1e-6, 1 - 1e-6) / (1 - np.clip(val_raw_probs, 1e-6, 1 - 1e-6))).reshape(-1, 1)

    calibrator_v3 = LogisticRegression(solver="lbfgs", random_state=RANDOM_SEED)
    calibrator_v3.fit(val_logits, y_val_loc)
    print(" -> Platt Calibrator V3 fitted successfully.")

    # 7. Evaluate on Held-Out Test Data (Zero Force-Add)
    print("[7/7] Evaluating Location Model V3 on held-out test data...")
    test_raw_probs = location_clf_v3.predict_proba(X_test_loc)[:, 1]
    test_logits = np.log(np.clip(test_raw_probs, 1e-6, 1 - 1e-6) / (1 - np.clip(test_raw_probs, 1e-6, 1 - 1e-6))).reshape(-1, 1)
    test_cal_probs = calibrator_v3.predict_proba(test_logits)[:, 1]

    # Evaluate ranking across complaints
    r1_hits = 0
    r3_hits = 0
    r5_hits = 0
    reciprocal_ranks = []
    centroid_errors = []

    offset = 0
    for meta in test_meta:
        n_c = meta["n_candidates"]
        comp_probs = test_cal_probs[offset : offset + n_c]
        cands = meta["candidates"]
        t_id = meta["target_cluster_id"]
        t_coords = meta["target_coords"]
        offset += n_c

        # Rank candidates by probability descending
        ranked_indices = np.argsort(-comp_probs)
        ranked_cand_ids = [cands[idx]["cluster_id"] for idx in ranked_indices]

        # Centroid error for Top-1
        top_cand = cands[ranked_indices[0]]
        top_coords = (top_cand["lat"], top_cand["lon"])
        dist_err = haversine_km(top_coords[0], top_coords[1], t_coords[0], t_coords[1])
        centroid_errors.append(dist_err)

        if t_id in ranked_cand_ids:
            rank = ranked_cand_ids.index(t_id) + 1
            reciprocal_ranks.append(1.0 / rank)
            if rank == 1:
                r1_hits += 1
            if rank <= 3:
                r3_hits += 1
            if rank <= 5:
                r5_hits += 1
        else:
            # Complete miss because candidate was not in natural pool
            reciprocal_ranks.append(0.0)

    total_test = len(test_meta)
    recall_1 = (r1_hits / total_test) * 100.0
    recall_3 = (r3_hits / total_test) * 100.0
    recall_5 = (r5_hits / total_test) * 100.0
    mrr = float(np.mean(reciprocal_ranks))
    median_centroid_err = float(np.median(centroid_errors))
    brier = float(brier_score_loss(y_test_loc, test_cal_probs))
    ece = compute_ece(test_cal_probs, y_test_loc)

    print("\n" + "=" * 50)
    print("LOCATION MODEL V3 TEST RESULTS (HELD-OUT TEMPORAL)")
    print("=" * 50)
    print(f"Natural Candidate Recall: {test_cand_recall:.2f}%")
    print(f"Recall@1:                 {recall_1:.2f}%")
    print(f"Recall@3:                 {recall_3:.2f}%")
    print(f"Recall@5:                 {recall_5:.2f}%")
    print(f"MRR:                      {mrr:.4f}")
    print(f"Median Centroid Error:    {median_centroid_err:.2f} km")
    print(f"Brier Score:              {brier:.4f}")
    print(f"ECE:                      {ece:.4f}")
    print("=" * 50)

    # 8. Save Artifacts
    print("\nSaving V3 artifacts (preserving V2 artifacts untouched)...")
    v3_model_path = os.path.join(artifacts_dir, "location_ranker_v3.joblib")
    v3_calibrator_path = os.path.join(artifacts_dir, "location_calibrator_v3.joblib")
    v3_schema_path = os.path.join(artifacts_dir, "feature_schema_v3.json")
    v3_metadata_path = os.path.join(artifacts_dir, "model_metadata_v3.json")

    joblib.dump(location_clf_v3, v3_model_path)
    joblib.dump(calibrator_v3, v3_calibrator_path)

    # V3 Feature Schema
    schema_v3 = {
        "version": "v3",
        "description": "Leakage-free feature schema for CyberShield AI Location Model V3 & Time Model V2",
        "location_features": FEATURE_COLUMNS_LOCATION_V3,
        "time_features": FEATURE_COLUMNS_TIME,
        "feature_count_location": len(FEATURE_COLUMNS_LOCATION_V3),
        "feature_count_time": len(FEATURE_COLUMNS_TIME),
        "categorical_encodings": {
            "fraud_type_encoded": FRAUD_TYPE_MAP_V3,
            "payment_channel_encoded": CHANNEL_MAP_V3
        },
        "missing_policies": {
            "amount": "np.nan if missing or invalid; log1p(amount) otherwise",
            "fraud_type_encoded": "Explicit 0 = UNKNOWN",
            "payment_channel_encoded": "Explicit 0 = UNKNOWN",
            "incident_timestamp": "np.nan for time/hour features if missing; NO system-time fallback",
            "complaint_delay_minutes": "np.nan if reported_at or incident_timestamp missing",
            "empty_transactions": "TRUE_ZERO (count=0, total=0, velocity=0, duration=0, interval=0)",
            "empty_graph": "TRUE_ZERO (degrees=0, pagerank=0, betweenness=0, branching=0, sinks=0)",
            "victim_coordinates": "np.nan for distance_from_victim; NO default coordinate fabrication"
        },
        "removed_leakage_features": [
            "is_mule_corridor",
            "distance_from_high_risk_account"
        ],
        "created_at": datetime.utcnow().isoformat()
    }

    with open(v3_schema_path, "w") as f:
        json.dump(schema_v3, f, indent=2)

    # V3 Metadata
    metadata_v3 = {
        "model_name": "CyberShield AI Location Ranker V3",
        "model_version": "v3",
        "model_type": "XGBClassifier (Leakage-Free Ranking)",
        "training_date": datetime.utcnow().strftime("%Y-%m-%d"),
        "dataset_type": "Synthetic/anonymized Delhi-NCR prototype operational dataset",
        "geographic_scope": "Delhi Pilot (validated prototype architecture expandable to authorized regional datasets)",
        "features": {
            "location_feature_count": 38,
            "time_feature_count": 20,
            "location_features": FEATURE_COLUMNS_LOCATION_V3,
            "time_features": FEATURE_COLUMNS_TIME
        },
        "removed_leakage_features": [
            "is_mule_corridor",
            "distance_from_high_risk_account"
        ],
        "candidate_generation_policy": "Spatial proximity + historical hotspot ranking without beneficiary mule account prior or target cluster identity",
        "temporal_split": {
            "train_size": len(train_df),
            "val_size": len(val_df),
            "test_size": len(test_df),
            "train_temporal_range": [str(train_df["incident_timestamp"].min()), str(train_df["incident_timestamp"].max())],
            "val_temporal_range": [str(val_df["incident_timestamp"].min()), str(val_df["incident_timestamp"].max())],
            "test_temporal_range": [str(test_df["incident_timestamp"].min()), str(test_df["incident_timestamp"].max())]
        },
        "evaluation_metrics_held_out_test": {
            "candidate_recall_pct": round(test_cand_recall, 2),
            "recall_at_1": round(recall_1, 2),
            "recall_at_3": round(recall_3, 2),
            "recall_at_5": round(recall_5, 2),
            "mrr": round(mrr, 4),
            "median_centroid_error_km": round(median_centroid_err, 2),
            "brier_score": round(brier, 4),
            "expected_calibration_error": round(ece, 4)
        },
        "comparison_v2_vs_v3": {
            "v2_recall_at_1": 99.1,
            "v2_leakage_warning": "V2 metrics were artificially inflated by structural target proxy features (distance_from_high_risk_account and is_mule_corridor) and are NOT legitimate production metrics.",
            "v3_recall_at_1": round(recall_1, 2),
            "v3_evaluation_nature": "Scientifically defensible, honest evaluation on held-out temporal data with zero target leakage."
        },
        "calibration": "Platt probability scaling via Logistic Regression fitted strictly on validation split logits",
        "limitations": [
            "Trained and evaluated on synthetic cybercrime transaction topologies",
            "Decision-support ranking intended for regional cluster prioritization, not automated punitive actions or exact ATM certainty"
        ]
    }

    with open(v3_metadata_path, "w") as f:
        json.dump(metadata_v3, f, indent=2)

    print(" -> location_ranker_v3.joblib created.")
    print(" -> location_calibrator_v3.joblib created.")
    print(" -> feature_schema_v3.json created.")
    print(" -> model_metadata_v3.json created.")
    print("Location Model V3 Retraining Pipeline Completed Successfully.")


if __name__ == "__main__":
    main()
