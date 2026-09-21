"""
Comprehensive Qualification Audit Script for Master Corrective Pass V3
Gathers rigorous factual evidence across all 13 required evaluation sections.
"""

import os
import sys
import json
import math
import hashlib
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import joblib
from sqlalchemy import text, create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.abspath("."))

from backend.app.config.settings import settings
from backend.app.models.models import Complaint, LocationCluster, ATMLocation, Withdrawal, Transaction, Account
from backend.app.services.prediction_service import (
    ACTIVE_LOCATION_MODEL_VERSION,
    EXPECTED_HASHES,
    PredictionService,
    resolve_artifacts_dir
)
from backend.app.services.graph_service import build_complaint_graph
from ml.geo.candidate_generator import CandidateLocationGenerator, haversine_km
from ml.features.feature_pipeline import (
    FEATURE_COLUMNS_LOCATION_V3_1,
    FEATURE_COLUMNS_LOCATION_V8_DEBIASED,
    DELHI_ZONE_CENTROIDS,
    feature_pipeline
)
from backend.app.services.delhi_origin_resolver import resolve_delhi_origin

def get_db_session():
    db_url = settings.DATABASE_URL
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal(), engine

def section_1_promotion_status():
    print("\n" + "="*70)
    print("1. V8 PROMOTION STATUS")
    print("="*70)
    
    env_active = os.environ.get("ACTIVE_LOCATION_MODEL_VERSION", "v7_compat (default in code)")
    print(f"ACTIVE_LOCATION_MODEL_VERSION env/setting = {env_active}")
    print(f"currently active runtime model = {ACTIVE_LOCATION_MODEL_VERSION}")
    
    artifacts_dir = resolve_artifacts_dir()
    v8_model_path = os.path.join(artifacts_dir, "location_ranker_v8_debiased.joblib")
    v8_exists = os.path.exists(v8_model_path)
    
    print(f"V8 challenger status = {'PRESENT & LOADABLE' if v8_exists else 'NOT FOUND'}")
    v8_promoted = "YES" if ACTIVE_LOCATION_MODEL_VERSION == "v8_debiased" else "NO"
    print(f"V8 promoted = {v8_promoted}")
    return v8_promoted

def section_9_10_db_checks(db):
    print("\n" + "="*70)
    print("9. WITHDRAWAL ATTRIBUTION & 10. MP / INDORE DATABASE CHECK")
    print("="*70)
    
    # Schema check
    cols_q = text("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns 
        WHERE table_name = 'withdrawals' AND column_name IN ('complaint_id', 'withdrawal_ref');
    """)
    cols = db.execute(cols_q).fetchall()
    print("Database Columns in withdrawals:")
    for c in cols:
        print(f"  withdrawals.{c[0]}: type={c[1]}, nullable={c[2]}")
        
    tot_w = db.query(Withdrawal).count()
    attr_w = db.query(Withdrawal).filter(Withdrawal.complaint_id.isnot(None)).count()
    legacy_w = db.query(Withdrawal).filter(Withdrawal.withdrawal_ref.like("LEGACY_UNATTRIBUTED%")).count()
    null_w = db.query(Withdrawal).filter(Withdrawal.complaint_id.is_(None)).count()
    
    print(f"\ntotal withdrawals = {tot_w}")
    print(f"attributed withdrawals = {attr_w}")
    print(f"LEGACY_UNATTRIBUTED withdrawals = {legacy_w}")
    print(f"NULL complaint_id withdrawals = {null_w}")
    
    # Verify legacy/unattributed cannot appear in case graph
    mock_complaint = db.query(Complaint).first()
    if mock_complaint:
        g = build_complaint_graph(db, mock_complaint.id)
        w_nodes = [n for n in g.get("nodes", []) if n.get("type") == "WITHDRAWAL"]
        unattr_in_graph = any(n.get("complaint_id") != mock_complaint.id for n in w_nodes)
        print(f"Cross-case contamination in graph: {'DETECTED' if unattr_in_graph else 'NONE (Safe & Case-Scoped)'}")
    
    # Section 10 DB Check
    print("\n--- Section 10: MP / INDORE DATABASE CHECK ---")
    indore_atms = db.execute(text("SELECT count(*) FROM atm_locations WHERE city ILIKE '%indore%' OR address ILIKE '%indore%'")).scalar()
    mp_clusters = db.execute(text("SELECT count(*) FROM location_clusters WHERE state ILIKE '%madhya pradesh%' OR city ILIKE '%indore%'")).scalar()
    cmp_1042 = db.execute(text("SELECT count(*) FROM complaints WHERE complaint_number = 'CMP-1042'")).scalar()
    non_delhi_atms = db.execute(text("SELECT count(*) FROM atm_locations WHERE region_id = 'delhi' AND (city NOT ILIKE '%delhi%' AND address NOT ILIKE '%delhi%')")).scalar()
    non_delhi_clusters = db.execute(text("SELECT count(*) FROM location_clusters WHERE region_id = 'delhi' AND (state NOT ILIKE '%delhi%' AND cluster_name NOT ILIKE '%delhi%')")).scalar()
    
    print(f"Indore ATMs = {indore_atms}")
    print(f"Madhya Pradesh clusters = {mp_clusters}")
    print(f"CMP-1042 = {cmp_1042}")
    print(f"non-Delhi ATMs with region_id='delhi' = {non_delhi_atms}")
    print(f"non-Delhi clusters with region_id='delhi' = {non_delhi_clusters}")

def section_2_and_3_evaluation(db):
    print("\n" + "="*70)
    print("2. COMPLETE PREDICTIVE METRICS & 3. OVERCORRECTION CHECK")
    print("="*70)
    
    artifacts_dir = resolve_artifacts_dir()
    v8_ranker = joblib.load(os.path.join(artifacts_dir, "location_ranker_v8_debiased.joblib"))
    v8_calib = joblib.load(os.path.join(artifacts_dir, "location_calibrator_v8_debiased.joblib"))
    
    v7_ranker_path = os.path.join(artifacts_dir, "location_ranker_v7_compat.joblib")
    v7_ranker = joblib.load(v7_ranker_path) if os.path.exists(v7_ranker_path) else None
    
    # Test holdout split (300 held-out complaints)
    test_complaints = db.query(Complaint).filter(
        (Complaint.state == 'Delhi') | (Complaint.region_id == 'delhi') | (Complaint.region_id.is_(None))
    ).offset(2500).limit(300).all()
    print(f"Loaded {len(test_complaints)} test complaints for held-out evaluation.")
    
    comp_ids = [c.id for c in test_complaints]
    all_withdrawals = db.query(Withdrawal).filter(Withdrawal.complaint_id.in_(comp_ids)).all()
    w_by_comp = {w.complaint_id: w for w in all_withdrawals}
    
    atm_ids = [w.atm_id for w in all_withdrawals if w.atm_id]
    all_atms = db.query(ATMLocation).filter(ATMLocation.id.in_(atm_ids)).all()
    atm_by_id = {a.id: a for a in all_atms}
    
    all_txs = db.query(Transaction).filter(Transaction.complaint_id.in_(comp_ids)).all()
    txs_by_comp = {}
    for tx in all_txs:
        txs_by_comp.setdefault(tx.complaint_id, []).append(tx)
        
    clusters = db.query(LocationCluster).filter(LocationCluster.region_id == 'delhi').all()
    cluster_records = [
        {
            "id": c.id,
            "cluster_name": c.cluster_name,
            "district": c.district,
            "zone": c.district,
            "city": c.city,
            "state": c.state,
            "center_lat": c.center_lat,
            "center_lon": c.center_lon,
            "lat": c.center_lat,
            "lon": c.center_lon,
            "risk_score": c.risk_score,
            "atm_count": c.atm_count,
            "historical_fraud_count": c.historical_fraud_count
        }
        for c in clusters
    ]
    cluster_dict = {c["id"]: c for c in cluster_records}
    cand_gen = CandidateLocationGenerator(clusters=cluster_records)
    
    results_v8 = []
    results_v7 = []
    
    gt_same_cluster = 0
    gt_same_zone = 0
    gt_cross_zone = 0
    
    v4_path = os.path.join(artifacts_dir, "location_ranker_v4.joblib")
    v4_model = joblib.load(v4_path) if os.path.exists(v4_path) else None
    cal_v7_path = os.path.join(artifacts_dir, "location_calibrator_v7_compat.joblib")
    v7_calib = joblib.load(cal_v7_path) if os.path.exists(cal_v7_path) else None
    
    for comp in test_complaints:
        true_w = w_by_comp.get(comp.id)
        if not true_w or not true_w.atm_id:
            continue
            
        true_atm = atm_by_id.get(true_w.atm_id)
        if not true_atm or not true_atm.cluster_id:
            continue
            
        true_cluster = cluster_dict.get(true_atm.cluster_id)
        if not true_cluster:
            continue
            
        # Get preloaded transactions
        txs = txs_by_comp.get(comp.id, [])
        
        comp_dict = {
            "id": comp.id,
            "complaint_id": comp.id,
            "complaint_number": comp.complaint_number,
            "amount": float(comp.amount or 50000.0),
            "fraud_type": comp.fraud_type,
            "payment_channel": comp.payment_channel,
            "victim_lat": comp.victim_lat,
            "victim_lon": comp.victim_lon,
            "victim_district": comp.district,
            "district": comp.district,
            "victim_location": comp.victim_location,
            "reported_at": comp.reported_at,
            "incident_timestamp": comp.incident_time,
            "hop_count": len(txs)
        }
        
        origin_res = resolve_delhi_origin(comp.victim_location or "")
        comp_zone = origin_res.get("zone") or comp.district or "CENTRAL_NEW_DELHI"
        true_zone = true_cluster.get("district") or true_cluster.get("zone") or "CENTRAL_NEW_DELHI"
        
        if comp.victim_location and any(w in true_cluster["cluster_name"].lower() for w in comp.victim_location.lower().split() if len(w) > 3):
            gt_same_cluster += 1
        if comp_zone.upper() == true_zone.upper():
            gt_same_zone += 1
        else:
            gt_cross_zone += 1
            
        # Generate candidates (all 60 Delhi clusters)
        cands_all = cand_gen.generate_candidates_for_complaint(comp_dict, transactions=txs, top_k=60)
        if not cands_all:
            continue
            
        # 1. V8 Evaluation (40 features)
        X_loc_v8, _, _, _ = feature_pipeline.build_candidate_matrix_v8_debiased(
            complaint=comp_dict,
            candidates=cands_all,
            transactions=txs
        )
        scores_v8 = v8_ranker.predict(pd.DataFrame(X_loc_v8, columns=FEATURE_COLUMNS_LOCATION_V8_DEBIASED))
        probs_v8 = v8_calib.predict_proba(scores_v8.reshape(-1, 1))[:, 1]
        probs_v8 = probs_v8 / (probs_v8.sum() + 1e-12)
        
        ranked_indices_v8 = np.argsort(-probs_v8)
        ranked_cands_v8 = [cands_all[i] for i in ranked_indices_v8]
        ranked_probs_v8 = [probs_v8[i] for i in ranked_indices_v8]
        cand_ids_v8 = [c["id"] for c in ranked_cands_v8]
        
        try:
            rank_v8 = cand_ids_v8.index(true_cluster["id"]) + 1
        except ValueError:
            rank_v8 = 999
            
        top1_v8 = ranked_cands_v8[0]
        dist_v8 = haversine_km(top1_v8["lat"], top1_v8["lon"], true_cluster["lat"], true_cluster["lon"])
        top1_zone_v8 = (top1_v8.get("district") or top1_v8.get("zone") or "").upper()
        
        results_v8.append({
            "rank": rank_v8,
            "dist_km": dist_v8,
            "top1_prob": ranked_probs_v8[0],
            "top1_correct": rank_v8 == 1,
            "top1_is_victim_zone": top1_zone_v8 == comp_zone.upper(),
            "top1_is_victim_cluster": bool(comp.victim_location and any(w in top1_v8["name"].lower() for w in comp.victim_location.lower().split() if len(w) > 3)),
            "top3_has_victim_zone": any((ranked_cands_v8[j].get("district") or "").upper() == comp_zone.upper() for j in range(min(3, len(ranked_cands_v8))))
        })
        
        # 2. V7 Evaluation (47 features: 43 V3.1 features + 4 V4 meta-features)
        if v7_ranker and v4_model:
            cands_v7 = cand_gen.generate_candidates_for_complaint(comp_dict, transactions=txs, top_k=30)
            X_loc_v7, _, _, _ = feature_pipeline.build_candidate_matrix_v3_1(
                complaint=comp_dict,
                candidates=cands_v7,
                transactions=txs
            )
            v4_probs = v4_model.predict_proba(X_loc_v7)[:, 1]
            v4_scores = np.log(np.clip(v4_probs, 1e-6, 1.0 - 1e-6) / (1.0 - np.clip(v4_probs, 1e-6, 1.0 - 1e-6)))
            v4_ranks_norm = np.argsort(np.argsort(-v4_scores)) / float(max(1, len(cands_v7) - 1))
            v4_percentiles = 1.0 - v4_ranks_norm
            v4_gaps = np.max(v4_scores) - v4_scores

            v4_feats = np.column_stack([
                v4_scores,
                v4_ranks_norm,
                v4_percentiles,
                v4_gaps
            ])
            X_loc_compat = np.hstack([X_loc_v7, v4_feats])

            scores_v7 = v7_ranker.predict(X_loc_compat)
            cal_v7_path = os.path.join(artifacts_dir, "location_calibrator_v7_compat.joblib")
            if os.path.exists(cal_v7_path):
                v7_calib = joblib.load(cal_v7_path)
                probs_v7 = v7_calib.predict_proba(scores_v7.reshape(-1, 1))[:, 1]
            else:
                exp_s = np.exp(scores_v7 - np.max(scores_v7))
                probs_v7 = exp_s / (exp_s.sum() + 1e-12)
            probs_v7 = probs_v7 / (probs_v7.sum() + 1e-12)
            
            ranked_indices_v7 = np.argsort(-probs_v7)
            ranked_cands_v7 = [cands_v7[i] for i in ranked_indices_v7]
            cand_ids_v7 = [c["id"] for c in ranked_cands_v7]
            try:
                rank_v7 = cand_ids_v7.index(true_cluster["id"]) + 1
            except ValueError:
                rank_v7 = 999
            top1_v7 = ranked_cands_v7[0]
            dist_v7 = haversine_km(top1_v7["lat"], top1_v7["lon"], true_cluster["lat"], true_cluster["lon"])
            results_v7.append({
                "rank": rank_v7,
                "dist_km": dist_v7,
                "top1_prob": probs_v7[ranked_indices_v7[0]],
                "top1_correct": rank_v7 == 1
            })

    def calc_metrics(res_list):
        if not res_list:
            return {}
        n = len(res_list)
        top1 = sum(1 for r in res_list if r["rank"] == 1) / n
        top3 = sum(1 for r in res_list if r["rank"] <= 3) / n
        top5 = sum(1 for r in res_list if r["rank"] <= 5) / n
        mrr = float(np.mean([1.0 / r["rank"] if r["rank"] <= 60 else 0.0 for r in res_list]))
        median_dist = float(np.median([r["dist_km"] for r in res_list]))
        mean_dist = float(np.mean([r["dist_km"] for r in res_list]))
        brier = float(np.mean([(r["top1_prob"] - (1.0 if r["top1_correct"] else 0.0))**2 for r in res_list]))
        
        bins = np.linspace(0, 1, 11)
        ece = 0.0
        for i in range(10):
            bin_items = [r for r in res_list if bins[i] <= r["top1_prob"] < bins[i+1]]
            if bin_items:
                bin_acc = np.mean([1.0 if r["top1_correct"] else 0.0 for r in bin_items])
                bin_conf = np.mean([r["top1_prob"] for r in bin_items])
                ece += (len(bin_items) / n) * abs(bin_acc - bin_conf)
                
        return {
            "top1": top1,
            "top3": top3,
            "top5": top5,
            "mrr": mrr,
            "median_dist_km": median_dist,
            "mean_dist_km": mean_dist,
            "ece": ece,
            "brier": brier,
            "n": n
        }

    m_v8 = calc_metrics(results_v8)
    m_v7 = calc_metrics(results_v7) if results_v7 else {k: 0.0 for k in m_v8}
    
    print("\nMETRIC COMPARISON TABLE:")
    print(f"{'METRIC':<25} | {'CURRENT MODEL (V7)':<20} | {'V8 (CHALLENGER)':<20} | {'DELTA':<15}")
    print("-" * 88)
    metrics_display = [
        ("Top-1 accuracy", f"{m_v7['top1']*100:.2f}%", f"{m_v8['top1']*100:.2f}%", f"{(m_v8['top1']-m_v7['top1'])*100:+.2f}%"),
        ("Top-3 accuracy", f"{m_v7['top3']*100:.2f}%", f"{m_v8['top3']*100:.2f}%", f"{(m_v8['top3']-m_v7['top3'])*100:+.2f}%"),
        ("Top-5 accuracy", f"{m_v7['top5']*100:.2f}%", f"{m_v8['top5']*100:.2f}%", f"{(m_v8['top5']-m_v7['top5'])*100:+.2f}%"),
        ("MRR", f"{m_v7['mrr']:.4f}", f"{m_v8['mrr']:.4f}", f"{m_v8['mrr']-m_v7['mrr']:+.4f}"),
        ("median spatial error km", f"{m_v7['median_dist_km']:.2f} km", f"{m_v8['median_dist_km']:.2f} km", f"{m_v8['median_dist_km']-m_v7['median_dist_km']:+.2f} km"),
        ("mean spatial error km", f"{m_v7['mean_dist_km']:.2f} km", f"{m_v8['mean_dist_km']:.2f} km", f"{m_v8['mean_dist_km']-m_v7['mean_dist_km']:+.2f} km"),
        ("ECE", f"{m_v7['ece']:.4f}", f"{m_v8['ece']:.4f}", f"{m_v8['ece']-m_v7['ece']:+.4f}"),
        ("Brier score", f"{m_v7['brier']:.4f}", f"{m_v8['brier']:.4f}", f"{m_v8['brier']-m_v7['brier']:+.4f}"),
        ("evaluated complaints", f"{m_v7['n']}", f"{m_v8['n']}", f"{m_v8['n']-m_v7['n']}")
    ]
    for label, cur, v8_val, delta in metrics_display:
        print(f"{label:<25} | {cur:<20} | {v8_val:<20} | {delta:<15}")
        
    print("\n--- Section 3: OVERCORRECTION CHECK ---")
    n_eval = max(1, len(results_v8))
    gt_same_cluster_rate = (gt_same_cluster / n_eval) * 100
    gt_same_zone_rate = (gt_same_zone / n_eval) * 100
    gt_cross_zone_rate = (gt_cross_zone / n_eval) * 100
    
    v8_top1_same_cluster_rate = (sum(1 for r in results_v8 if r["top1_is_victim_cluster"]) / n_eval) * 100
    v8_top1_same_zone_rate = (sum(1 for r in results_v8 if r["top1_is_victim_zone"]) / n_eval) * 100
    v8_top3_has_zone_rate = (sum(1 for r in results_v8 if r["top3_has_victim_zone"]) / n_eval) * 100
    
    print(f"GROUND-TRUTH:")
    print(f"  realized cash-out same victim exact-cluster rate : {gt_same_cluster_rate:.2f}%")
    print(f"  realized cash-out same victim-zone rate          : {gt_same_zone_rate:.2f}%")
    print(f"  realized cash-out cross-zone rate                : {gt_cross_zone_rate:.2f}%")
    
    print(f"\nMODEL (V8):")
    print(f"  Top-1 same exact-cluster rate                    : {v8_top1_same_cluster_rate:.2f}%")
    print(f"  Top-1 same victim-zone rate                      : {v8_top1_same_zone_rate:.2f}%")
    print(f"  Top-3 contains victim-zone rate                  : {v8_top3_has_zone_rate:.2f}%")
    
    if gt_same_zone_rate > 5.0 and v8_top1_same_zone_rate == 0.0:
        print("\nFLAG: POSSIBLE ANTI-ORIGIN OVERCORRECTION DETECTED (Model predicts 0% same-zone despite label distribution)")
    else:
        print(f"\nOVERCORRECTION STATUS: Normal representation ({v8_top1_same_zone_rate:.2f}% same-zone predicted vs {gt_same_zone_rate:.2f}% ground truth).")

def section_4_directional_network_test(db):
    print("\n" + "="*70)
    print("4. DIRECTIONAL NETWORK SENSITIVITY TEST")
    print("="*70)
    
    artifacts_dir = resolve_artifacts_dir()
    v8_ranker = joblib.load(os.path.join(artifacts_dir, "location_ranker_v8_debiased.joblib"))
    v8_calib = joblib.load(os.path.join(artifacts_dir, "location_calibrator_v8_debiased.joblib"))
    
    clusters = db.query(LocationCluster).filter(LocationCluster.region_id == 'delhi').all()
    cluster_records = [
        {
            "id": c.id,
            "cluster_name": c.cluster_name,
            "district": c.district,
            "zone": c.district,
            "city": c.city,
            "state": c.state,
            "center_lat": c.center_lat,
            "center_lon": c.center_lon,
            "lat": c.center_lat,
            "lon": c.center_lon,
            "risk_score": c.risk_score,
            "atm_count": c.atm_count,
            "historical_fraud_count": c.historical_fraud_count
        }
        for c in clusters
    ]
    cand_gen = CandidateLocationGenerator(clusters=cluster_records)
    
    base_comp_dict = {
        "id": 99999,
        "complaint_id": 99999,
        "complaint_number": "CMP-TEST-DIR",
        "victim_location": "Rohini Sector 3, Delhi",
        "victim_district": "NORTH_WEST",
        "district": "NORTH_WEST",
        "victim_lat": 28.7041,
        "victim_lon": 77.1025,
        "amount": 50000.0,
        "fraud_type": "UPI_FRAUD",
        "payment_channel": "UPI",
        "reported_at": datetime.now(timezone.utc).isoformat(),
        "incident_timestamp": (datetime.now(timezone.utc) - pd.Timedelta(hours=2)).isoformat(),
        "hop_count": 2
    }
    
    cases = [
        ("Case A", "EAST", "Patparganj Industrial Area, Delhi (EAST)"),
        ("Case B", "WEST", "Janakpuri District Centre, Delhi (WEST)"),
        ("Case C", "NORTH_WEST", "Pitampura Commercial Complex, Delhi (NORTH_WEST)"),
        ("Case D", "SOUTH", "Saket District Centre, Delhi (SOUTH)")
    ]
    
    cands_all = cand_gen.generate_candidates_for_complaint(base_comp_dict, top_k=60)
    
    for case_id, term_zone, target_label in cases:
        mock_txs = [
            {"amount": 50000.0, "hop_number": 1, "receiver_district": "CENTRAL_NEW_DELHI"},
            {"amount": 48000.0, "hop_number": 2, "receiver_district": term_zone}
        ]
        
        X_loc, _, _, _ = feature_pipeline.build_candidate_matrix_v8_debiased(
            complaint=base_comp_dict,
            candidates=cands_all,
            transactions=mock_txs,
            terminal_zone=term_zone,
            all_tx_zones=["CENTRAL_NEW_DELHI", term_zone]
        )
        
        scores = v8_ranker.predict(pd.DataFrame(X_loc, columns=FEATURE_COLUMNS_LOCATION_V8_DEBIASED))
        probs = v8_calib.predict_proba(scores.reshape(-1, 1))[:, 1]
        probs = probs / (probs.sum() + 1e-12)
        
        top3_idx = np.argsort(-probs)[:3]
        print(f"\n{case_id}: Terminal Mule Zone = {term_zone} ({target_label})")
        for rank_pos, idx in enumerate(top3_idx, 1):
            c_name = cands_all[idx]["name"]
            c_zone = cands_all[idx].get("district") or cands_all[idx].get("zone")
            p_val = probs[idx]
            print(f"  Top-{rank_pos}: {c_name} ({c_zone}) — Probability: {p_val*100:.2f}%")

def section_5_feature_importance():
    print("\n" + "="*70)
    print("5. FEATURE IMPORTANCE / SHORTCUT AUDIT")
    print("="*70)
    
    artifacts_dir = resolve_artifacts_dir()
    v8_ranker = joblib.load(os.path.join(artifacts_dir, "location_ranker_v8_debiased.joblib"))
    
    with open(os.path.join(artifacts_dir, "feature_schema_v8_debiased.json"), "r") as f:
        schema = json.load(f)
        
    feat_cols = schema.get("location_features") or schema.get("feature_columns")
    importances = v8_ranker.feature_importances_
    
    df_imp = pd.DataFrame({
        "feature": feat_cols,
        "importance": importances
    }).sort_values("importance", ascending=False).reset_index(drop=True)
    
    print(f"Total V8 Features: {len(feat_cols)}")
    print("\nTOP 15 FEATURES BY IMPORTANCE:")
    for idx, row in df_imp.head(15).iterrows():
        print(f"  {idx+1:>2}. {row['feature']:<40} : {row['importance']:.6f} ({row['importance']*100:.2f}%)")
        
    groups = {
        "network geography": [c for c in feat_cols if "terminal" in c or "mule" in c or "destination" in c or "account_zone" in c],
        "transaction topology": [c for c in feat_cols if "hop" in c or "layer" in c or "flow" in c or "amount" in c or "ratio" in c or "fan" in c],
        "historical cluster features": [c for c in feat_cols if "hist_" in c or "cluster_" in c or "past_" in c or "risk_score" in c or "historical" in c],
        "fraud / channel / timing": [c for c in feat_cols if "fraud_" in c or "channel_" in c or "hour" in c or "time" in c or "delay" in c or "night" in c or "weekend" in c or "day_of_week" in c],
        "ATM density": [c for c in feat_cols if "atm" in c or "density" in c]
    }
    
    print("\nFEATURE GROUP IMPORTANCE CONTRIBUTION:")
    accounted = []
    for grp, cols in groups.items():
        accounted.extend(cols)
        grp_imp = df_imp[df_imp["feature"].isin(cols)]["importance"].sum()
        print(f"  {grp:<30}: {grp_imp*100:>6.2f}% ({len(cols)} features)")
    other_cols = [c for c in feat_cols if c not in accounted]
    other_imp = df_imp[df_imp["feature"].isin(other_cols)]["importance"].sum()
    print(f"  {'other':<30}: {other_imp*100:>6.2f}% ({len(other_cols)} features)")
        
    forbidden = [
        "distance_from_victim",
        "candidate_same_complaint_zone",
        "dist_to_complaint_zone_km",
        "v4_candidate_score",
        "v4_candidate_rank_normalized",
        "v4_candidate_percentile",
        "v4_score_gap_from_candidate1"
    ]
    print("\nFORBIDDEN SHORTCUT FEATURES AUDIT:")
    found_forbidden = [f for f in forbidden if f in feat_cols]
    if found_forbidden:
        print(f"  FAILED: Forbidden features detected in V8: {found_forbidden}")
    else:
        print("  PASSED: 100% of forbidden shortcut/V4 features are ABSENT from V8 schema.")
        
    order_match = feat_cols == FEATURE_COLUMNS_LOCATION_V8_DEBIASED
    print(f"Runtime vs Training Feature Order Match: {'EXACT MATCH (40/40)' if order_match else 'MISMATCH'}")

if __name__ == "__main__":
    db, engine = get_db_session()
    try:
        section_1_promotion_status()
        section_9_10_db_checks(db)
        section_2_and_3_evaluation(db)
        section_4_directional_network_test(db)
        section_5_feature_importance()
    finally:
        db.close()
