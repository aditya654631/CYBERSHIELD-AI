import os
import sys
import numpy as np
from datetime import datetime, timedelta

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import joblib
from backend.app.models.db import SessionLocal
from backend.app.models.models import LocationCluster
from ml.geo.candidate_generator import CandidateLocationGenerator
from ml.features.feature_pipeline import feature_pipeline
from scratch.diagnose_controlled_set import CONTROLLED_CASES

db = SessionLocal()
clusters_db = db.query(LocationCluster).filter((LocationCluster.state == "Delhi") | (LocationCluster.city == "Delhi")).order_by(LocationCluster.id.asc()).all()
cluster_dicts = [{
    "id": c.id, "name": c.cluster_name, "city": c.city or "Delhi", "state": c.state or "Delhi",
    "district": c.district, "zone": c.district,
    "lat": float(c.center_lat) if c.center_lat is not None else 28.6139,
    "lon": float(c.center_lon) if c.center_lon is not None else 77.2090,
    "atm_density": float(c.atm_count) if c.atm_count is not None else 15.0,
    "base_risk": float(c.risk_score) if getattr(c, "risk_score", None) is not None else 0.50,
    "risk": float(c.risk_score) if getattr(c, "risk_score", None) is not None else 0.50
} for c in clusters_db]
cand_gen = CandidateLocationGenerator(clusters=cluster_dicts)

artifacts_dir = os.path.join(BASE_DIR, "ml", "artifacts")
loc_model_v3_1 = joblib.load(os.path.join(artifacts_dir, "location_ranker_v3_1.joblib"))
calibrator_v3_1 = joblib.load(os.path.join(artifacts_dir, "location_calibrator_v3_1.joblib"))
time_model_v2 = joblib.load(os.path.join(artifacts_dir, "time_regressor_v2.joblib"))

loc_model_v4 = joblib.load(os.path.join(artifacts_dir, "location_ranker_v4.joblib"))
calibrator_v4 = joblib.load(os.path.join(artifacts_dir, "location_calibrator_v4.joblib"))
time_model_v3 = joblib.load(os.path.join(artifacts_dir, "time_regressor_v3.joblib"))

now = datetime(2026, 9, 11, 14, 0, 0)
print(f"{'ID':<3} | {'Region':<25} | {'Origin District':<20} | {'Top 1 Predicted':<25} | {'Top 2 Predicted':<25} | {'Top 3 Predicted':<25} | {'Time (min)'}")
print("-" * 145)

top1_list = []
top3_sets = []

for case in CONTROLLED_CASES:
    inc_time = now - timedelta(hours=case['incident_offset_hours'])
    rep_time = now
    tx_time = inc_time + timedelta(minutes=15)
    comp_dict = {
        'complaint_id': 9000 + case['id'],
        'complaint_number': f'CMP-DIAG-{case["id"]:03d}',
        'fraud_type': case['fraud_type'],
        'amount': case['amount'],
        'payment_channel': case['payment_channel'],
        'incident_timestamp': inc_time.isoformat(),
        'incident_time': inc_time.isoformat(),
        'reported_at': rep_time.isoformat(),
        'complaint_timestamp': rep_time.isoformat(),
        'victim_state': 'Delhi',
        'victim_district': case['district'],
        'victim_city': 'Delhi',
        'victim_lat': case['lat'],
        'victim_lon': case['lon'],
        'status': 'UNDER_INVESTIGATION',
        'risk_score': None,
        'risk_level': 'HIGH'
    }
    tx = {
        'amount': case['amount'],
        'sender_account_id': 1000 + case['id'],
        'receiver_account_id': 2000 + case['id'],
        'bank_name': case['bank'],
        'timestamp': tx_time.isoformat(),
        'hop_number': 1,
        'receiver_district': case['terminal_district']
    }
    cands = cand_gen.generate_candidates_for_complaint(
        complaint=comp_dict,
        top_k=25,
        transactions=[tx],
        terminal_zone=case['terminal_district'],
        all_tx_zones={case['terminal_district']}
    )
    X_loc, X_time, _, _ = feature_pipeline.build_candidate_matrix_v3_1(
        complaint=comp_dict,
        candidates=cands,
        transactions=[tx],
        graph_metrics={'node_count': 2, 'edge_count': 1, 'max_degree': 1.0, 'mean_degree': 1.0, 'max_pagerank': 0.5, 'max_betweenness': 0.0, 'connected_components': 1, 'intermediary_count': 0, 'sink_count': 1, 'branching_factor': 1.0, 'max_hop': 1.0},
        terminal_zone=case['terminal_district'],
        all_tx_zones={case['terminal_district']}
    )
    raw_p_v3 = loc_model_v3_1.predict_proba(X_loc)[:, 1]
    cal_p_v3 = calibrator_v3_1.predict_proba(raw_p_v3.reshape(-1, 1))[:, 1]
    r_idx_v3 = np.argsort(-cal_p_v3)
    t_pred_v2 = float(time_model_v2.predict(X_time.reshape(1, -1))[0])

    raw_p_v4 = loc_model_v4.predict_proba(X_loc)[:, 1]
    cal_p_v4 = calibrator_v4.predict_proba(raw_p_v4.reshape(-1, 1))[:, 1]
    r_idx_v4 = np.argsort(-cal_p_v4)
    t_pred_v3 = float(np.expm1(time_model_v3.predict(X_time.reshape(1, -1))[0]))

    t1_v4 = cands[r_idx_v4[0]]['name']
    t2_v4 = cands[r_idx_v4[1]]['name']
    t3_v4 = cands[r_idx_v4[2]]['name']

    top1_list.append(t1_v4)
    top3_sets.append(frozenset([t1_v4, t2_v4, t3_v4]))

    print(f"{case['id']:<3} | {case['region_name']:<25} | {case['district']:<20} | {t1_v4[:24]:<25} | {t2_v4[:24]:<25} | {t3_v4[:24]:<25} | {t_pred_v3:5.1f}m (V2: {t_pred_v2:5.1f}m)")

print("-" * 145)
print(f"Unique Top 1 Predictions: {len(set(top1_list))} / {len(CONTROLLED_CASES)}")
print(f"Unique Top 3 Candidate Sets: {len(set(top3_sets))} / {len(CONTROLLED_CASES)}")
from collections import Counter
print(f"Top 1 Distribution: {dict(Counter(top1_list))}")
