"""
CyberShield AI — ML Repetitive Prediction Diagnosis (Parts C1–C5)
Controlled 12-case Delhi audit across all districts and diverse fraud context.
"""

import os
import sys
import math
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List

import numpy as np
import pandas as pd
import joblib

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.models.db import SessionLocal
from backend.app.models.models import LocationCluster
from ml.geo.candidate_generator import CandidateLocationGenerator, haversine_km
from ml.features.feature_pipeline import (
    feature_pipeline,
    DELHI_ZONE_CENTROIDS,
    FEATURE_COLUMNS_LOCATION_V3_1,
    FEATURE_COLUMNS_TIME
)

# 12 Controlled Complaints as defined in C1
CONTROLLED_CASES = [
    {
        "id": 1,
        "region_name": "Connaught Place / Central",
        "district": "CENTRAL_NEW_DELHI",
        "locality": "Connaught Place Inner Circle",
        "lat": 28.6315,
        "lon": 77.2167,
        "amount": 250000.0,
        "fraud_type": "investment scam",
        "payment_channel": "NEFT",
        "incident_offset_hours": 3.0,
        "bank": "HDFC Bank",
        "terminal_district": "CENTRAL_NEW_DELHI"
    },
    {
        "id": 2,
        "region_name": "Dwarka / South-West",
        "district": "SOUTH_WEST_DWARKA",
        "locality": "Sector 12 Dwarka",
        "lat": 28.5823,
        "lon": 77.0500,
        "amount": 45000.0,
        "fraud_type": "job scam",
        "payment_channel": "UPI",
        "incident_offset_hours": 1.5,
        "bank": "State Bank of India",
        "terminal_district": "SOUTH_WEST_DWARKA"
    },
    {
        "id": 3,
        "region_name": "Rohini / North-West",
        "district": "NORTH_WEST",
        "locality": "Sector 10 Rohini",
        "lat": 28.7159,
        "lon": 77.1172,
        "amount": 180000.0,
        "fraud_type": "loan-app scam",
        "payment_channel": "IMPS",
        "incident_offset_hours": 5.0,
        "bank": "ICICI Bank",
        "terminal_district": "NORTH_WEST"
    },
    {
        "id": 4,
        "region_name": "Laxmi Nagar / East",
        "district": "EAST",
        "locality": "Vikas Marg, Laxmi Nagar",
        "lat": 28.6308,
        "lon": 77.2773,
        "amount": 32000.0,
        "fraud_type": "phishing",
        "payment_channel": "UPI",
        "incident_offset_hours": 0.75,
        "bank": "Punjab National Bank",
        "terminal_district": "EAST"
    },
    {
        "id": 5,
        "region_name": "Saket / South",
        "district": "SOUTH",
        "locality": "Saket District Centre",
        "lat": 28.5245,
        "lon": 77.2066,
        "amount": 420000.0,
        "fraud_type": "digital arrest",
        "payment_channel": "RTGS",
        "incident_offset_hours": 2.0,
        "bank": "Axis Bank",
        "terminal_district": "SOUTH"
    },
    {
        "id": 6,
        "region_name": "Karol Bagh / Central-West",
        "district": "CENTRAL_NEW_DELHI",
        "locality": "Arya Samaj Road, Karol Bagh",
        "lat": 28.6514,
        "lon": 77.1907,
        "amount": 85000.0,
        "fraud_type": "marketplace scam",
        "payment_channel": "UPI",
        "incident_offset_hours": 4.0,
        "bank": "Kotak Mahindra Bank",
        "terminal_district": "CENTRAL_NEW_DELHI"
    },
    {
        "id": 7,
        "region_name": "Janakpuri / West",
        "district": "WEST",
        "locality": "District Centre Janakpuri",
        "lat": 28.6219,
        "lon": 77.0878,
        "amount": 62000.0,
        "fraud_type": "remote-access scam",
        "payment_channel": "IMPS",
        "incident_offset_hours": 1.0,
        "bank": "Bank of Baroda",
        "terminal_district": "WEST"
    },
    {
        "id": 8,
        "region_name": "Shahdara / East",
        "district": "NORTH_EAST_SHAHDARA",
        "locality": "Main Market Shahdara",
        "lat": 28.6738,
        "lon": 77.2917,
        "amount": 15000.0,
        "fraud_type": "fake customer-care scam",
        "payment_channel": "UPI",
        "incident_offset_hours": 0.5,
        "bank": "Paytm Payments Bank",
        "terminal_district": "NORTH_EAST_SHAHDARA"
    },
    {
        "id": 9,
        "region_name": "Pitampura / North-West",
        "district": "NORTH_WEST",
        "locality": "Netaji Subhash Place, Pitampura",
        "lat": 28.6990,
        "lon": 77.1384,
        "amount": 115000.0,
        "fraud_type": "account takeover",
        "payment_channel": "NET_BANKING",
        "incident_offset_hours": 6.0,
        "bank": "Canara Bank",
        "terminal_district": "NORTH_WEST"
    },
    {
        "id": 10,
        "region_name": "Vasant Kunj / South-West",
        "district": "SOUTH",
        "locality": "Sector B Vasant Kunj",
        "lat": 28.5293,
        "lon": 77.1528,
        "amount": 310000.0,
        "fraud_type": "impersonation scam",
        "payment_channel": "IMPS",
        "incident_offset_hours": 3.5,
        "bank": "IndusInd Bank",
        "terminal_district": "SOUTH"
    },
    {
        "id": 11,
        "region_name": "Nehru Place / South-East",
        "district": "SOUTH_EAST",
        "locality": "Nehru Place Computer Market",
        "lat": 28.5494,
        "lon": 77.2534,
        "amount": 95000.0,
        "fraud_type": "e-commerce scam",
        "payment_channel": "UPI",
        "incident_offset_hours": 2.5,
        "bank": "Yes Bank",
        "terminal_district": "SOUTH_EAST"
    },
    {
        "id": 12,
        "region_name": "Civil Lines / North",
        "district": "NORTH",
        "locality": "Alipur Road, Civil Lines",
        "lat": 28.6816,
        "lon": 77.2227,
        "amount": 175000.0,
        "fraud_type": "upi fraud",
        "payment_channel": "UPI",
        "incident_offset_hours": 1.2,
        "bank": "Union Bank of India",
        "terminal_district": "NORTH"
    }
]


def run_diagnostics():
    print("=" * 80)
    print("CYBERSHIELD AI — REPETITIVE PREDICTION DIAGNOSTIC (C1 - C5)")
    print("=" * 80)

    db = SessionLocal()
    # Load Delhi clusters from DB
    clusters_db = (
        db.query(LocationCluster)
        .filter((LocationCluster.state == "Delhi") | (LocationCluster.city == "Delhi"))
        .order_by(LocationCluster.id.asc())
        .all()
    )
    cluster_dicts = []
    for c in clusters_db:
        cluster_dicts.append({
            "id": c.id,
            "name": c.cluster_name,
            "city": c.city or "Delhi",
            "state": c.state or "Delhi",
            "district": c.district,
            "zone": c.district,
            "lat": float(c.center_lat) if c.center_lat is not None else 28.6139,
            "lon": float(c.center_lon) if c.center_lon is not None else 77.2090,
            "atm_density": float(c.atm_count) if c.atm_count is not None else 15.0,
            "base_risk": float(c.risk_score) if getattr(c, "risk_score", None) is not None else 0.50,
            "risk": float(c.risk_score) if getattr(c, "risk_score", None) is not None else 0.50
        })

    cand_gen = CandidateLocationGenerator(clusters=cluster_dicts)

    # Load artifacts
    artifacts_dir = os.path.join(BASE_DIR, "ml", "artifacts")
    loc_model = joblib.load(os.path.join(artifacts_dir, "location_ranker_v3_1.joblib"))
    calibrator = joblib.load(os.path.join(artifacts_dir, "location_calibrator_v3_1.joblib"))
    time_model = joblib.load(os.path.join(artifacts_dir, "time_regressor_v2.joblib"))

    now = datetime(2026, 9, 11, 14, 0, 0)

    # Containers for C2 Feature Diversity Audit
    all_X_loc = []  # will be 12 * 25 = 300 rows
    all_X_time = [] # 12 rows
    case_results = []

    print("\n--- C1 & C4: CANDIDATE GENERATION & PREDICTION AUDIT PER COMPLAINT ---")
    print(f"{'ID':<3} | {'Region':<25} | {'Origin':<18} | {'Top 1 Predicted':<25} | {'Top 2 Predicted':<25} | {'Top 3 Predicted':<25} | {'Time (min)':<10}")
    print("-" * 140)

    for case in CONTROLLED_CASES:
        inc_time = now - timedelta(hours=case["incident_offset_hours"])
        rep_time = now
        tx_time = inc_time + timedelta(minutes=15)

        comp_dict = {
            "complaint_id": 9000 + case["id"],
            "complaint_number": f"CMP-DIAG-{case['id']:03d}",
            "fraud_type": case["fraud_type"],
            "amount": case["amount"],
            "payment_channel": case["payment_channel"],
            "incident_timestamp": inc_time.isoformat(),
            "incident_time": inc_time.isoformat(),
            "reported_at": rep_time.isoformat(),
            "complaint_timestamp": rep_time.isoformat(),
            "victim_state": "Delhi",
            "victim_district": case["district"],
            "victim_city": "Delhi",
            "victim_lat": case["lat"],
            "victim_lon": case["lon"],
            "status": "UNDER_INVESTIGATION",
            "risk_score": None,
            "risk_level": "HIGH"
        }

        # Simulated 1-hop transaction
        tx = {
            "amount": case["amount"],
            "sender_account_id": 1000 + case["id"],
            "receiver_account_id": 2000 + case["id"],
            "bank_name": case["bank"],
            "timestamp": tx_time.isoformat(),
            "hop_number": 1,
            "receiver_district": case["terminal_district"]
        }

        # Candidate generation
        candidates = cand_gen.generate_candidates_for_complaint(
            complaint=comp_dict,
            top_k=25,
            transactions=[tx],
            terminal_zone=case["terminal_district"],
            all_tx_zones={case["terminal_district"]}
        )

        # Feature extraction
        X_loc, X_time, loc_cols, time_cols = feature_pipeline.build_candidate_matrix_v3_1(
            complaint=comp_dict,
            candidates=candidates,
            transactions=[tx],
            graph_metrics={"node_count": 2, "edge_count": 1, "max_degree": 1.0, "mean_degree": 1.0, "max_pagerank": 0.5, "max_betweenness": 0.0, "connected_components": 1, "intermediary_count": 0, "sink_count": 1, "branching_factor": 1.0, "max_hop": 1.0},
            terminal_zone=case["terminal_district"],
            all_tx_zones={case["terminal_district"]}
        )

        all_X_loc.append(X_loc)
        all_X_time.append(X_time[0])

        # Inference
        raw_probs = loc_model.predict_proba(X_loc)[:, 1]
        cal_probs = calibrator.predict_proba(raw_probs.reshape(-1, 1))[:, 1]
        time_pred = float(time_model.predict(X_time.reshape(1, -1))[0])

        ranked_idx = np.argsort(-cal_probs)
        top1 = candidates[ranked_idx[0]]
        top2 = candidates[ranked_idx[1]]
        top3 = candidates[ranked_idx[2]]

        case_results.append({
            "case": case,
            "candidates": candidates,
            "top1": top1,
            "top2": top2,
            "top3": top3,
            "top1_prob": float(cal_probs[ranked_idx[0]]),
            "time_pred": time_pred,
            "ranked_indices": ranked_idx
        })

        print(f"{case['id']:<3} | {case['region_name']:<25} | {case['district']:<18} | {top1['name'][:24]:<25} | {top2['name'][:24]:<25} | {top3['name'][:24]:<25} | {time_pred:<10.1f}")

    # Summary of outputs
    top1_names = [r["top1"]["name"] for r in case_results]
    print("\n[C1 SUMMARY]")
    print(f"Total Controlled Cases: {len(CONTROLLED_CASES)}")
    print(f"Unique Top 1 Predictions: {len(set(top1_names))} out of {len(CONTROLLED_CASES)}")
    print(f"Top 1 Frequencies: {pd.Series(top1_names).value_counts().to_dict()}")

    # -------------------------------------------------------------
    # C2: FEATURE DIVERSITY AUDIT
    # -------------------------------------------------------------
    print("\n" + "=" * 80)
    print("--- C2: FEATURE DIVERSITY AUDIT ---")
    print("=" * 80)

    # Time feature matrix: shape (12, 20)
    X_time_mat = np.array(all_X_time, dtype=np.float32)
    df_time = pd.DataFrame(X_time_mat, columns=FEATURE_COLUMNS_TIME)

    print(f"Time Matrix Shape: {X_time_mat.shape}")
    print(f"Unique Time Feature Vectors: {len(np.unique(X_time_mat, axis=0))}")
    print("\nTime Feature Variance & Range:")
    for col in FEATURE_COLUMNS_TIME:
        s = df_time[col]
        print(f"  {col:<30}: min={s.min():10.2f}, max={s.max():10.2f}, std={s.std():10.2f}, nunique={s.nunique()}")

    # Location features across candidates
    # Each case has 25 candidate rows of 43 features
    # Let's inspect complaint-level features vs candidate-specific features
    X_loc_all = np.vstack(all_X_loc) # (300, 43)
    df_loc = pd.DataFrame(X_loc_all, columns=FEATURE_COLUMNS_LOCATION_V3_1)

    print(f"\nLocation Matrix Shape: {X_loc_all.shape}")
    print(f"Unique Location Feature Vectors: {len(np.unique(X_loc_all, axis=0))}")

    # Check key complaint attributes
    print("\nKey Complaint Attributes in Feature Matrix:")
    for feat in ["amount_log", "complaint_amount", "complaint_hour", "fraud_type_encoded", "payment_channel_encoded", "reporting_delay_hours", "distance_from_victim", "candidate_same_complaint_zone", "candidate_same_terminal_zone", "dist_to_complaint_zone_km"]:
        if feat in df_loc.columns:
            s = df_loc[feat]
            print(f"  {feat:<32}: min={s.min():10.2f}, max={s.max():10.2f}, std={s.std():10.2f}, nunique={s.nunique()}")

    # -------------------------------------------------------------
    # C3: LOCATION MODEL DIAGNOSIS (Top 15 Influential Features)
    # -------------------------------------------------------------
    print("\n" + "=" * 80)
    print("--- C3: LOCATION MODEL V3.1 FEATURE IMPORTANCE (TOP 15) ---")
    print("=" * 80)

    importances_gain = loc_model.get_booster().get_score(importance_type="gain")
    importances_weight = loc_model.get_booster().get_score(importance_type="weight")

    # Map f0, f1... to feature names
    named_gain = {}
    for k, v in importances_gain.items():
        idx = int(k.replace("f", ""))
        named_gain[FEATURE_COLUMNS_LOCATION_V3_1[idx]] = v

    sorted_gain = sorted(named_gain.items(), key=lambda x: x[1], reverse=True)

    print(f"{'Rank':<4} | {'Feature Name':<38} | {'Gain':<12}")
    print("-" * 60)
    for r, (fname, gain) in enumerate(sorted_gain[:15], start=1):
        print(f"{r:<4} | {fname:<38} | {gain:<12.4f}")

    # Check if historical cluster priors dominate
    top_feats = [f[0] for f in sorted_gain[:5]]
    print(f"\nTop 5 Gain Features: {top_feats}")

    # -------------------------------------------------------------
    # C4: CANDIDATE GENERATION AUDIT
    # -------------------------------------------------------------
    print("\n" + "=" * 80)
    print("--- C4: CANDIDATE GENERATION AUDIT ---")
    print("=" * 80)
    for cr in case_results:
        c = cr["case"]
        cands = cr["candidates"]
        cand_ids = [cand["id"] for cand in cands]
        cand_names = [cand["name"] for cand in cands[:5]]
        cand_districts = set([cand.get("district") for cand in cands])
        print(f"Case {c['id']:2d} ({c['district']:<20}): {len(cands)} cands | Distr in Pool: {cand_districts} | Top 3 in Pool: {cand_names[:3]}")

    # -------------------------------------------------------------
    # C5: TIME MODEL DIAGNOSIS
    # -------------------------------------------------------------
    print("\n" + "=" * 80)
    print("--- C5: TIME MODEL V2 DIAGNOSIS ---")
    print("=" * 80)

    time_preds = [cr["time_pred"] for cr in case_results]
    print(f"Time Predictions (mins) across 12 cases:")
    for cr in case_results:
        c = cr["case"]
        print(f"  Case {c['id']:2d} | Amount: Rs. {c['amount']:>8,.0f} | Channel: {c['payment_channel']:<10} | Fraud: {c['fraud_type']:<22} | Time: {cr['time_pred']:5.1f} mins")

    print(f"\nTime Pred Stats: min={min(time_preds):.1f}, max={max(time_preds):.1f}, mean={np.mean(time_preds):.1f}, std={np.std(time_preds):.1f}")

    time_importances = time_model.get_booster().get_score(importance_type="gain")
    named_time_gain = {}
    for k, v in time_importances.items():
        idx = int(k.replace("f", ""))
        named_time_gain[FEATURE_COLUMNS_TIME[idx]] = v
    sorted_time_gain = sorted(named_time_gain.items(), key=lambda x: x[1], reverse=True)

    print(f"\nTime V2 Top 10 Features by Gain:")
    for r, (fname, gain) in enumerate(sorted_time_gain[:10], start=1):
        print(f"  {r:<2} | {fname:<30} | {gain:<10.4f}")

    print("\n" + "=" * 80)
    print("DIAGNOSIS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    run_diagnostics()
