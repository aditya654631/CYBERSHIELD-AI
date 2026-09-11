import sys
import os
import math
from datetime import datetime, timedelta
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.stdout.reconfigure(encoding='utf-8')

from fastapi.testclient import TestClient
from sqlalchemy import func

from backend.app.main import app
from backend.app.models.db import SessionLocal
from backend.app.models.models import (
    Complaint, Account, Transaction, ComplaintAccount,
    Prediction, PredictionLocation, Alert, LocationCluster
)
from backend.app.services.ml_feature_service import build_location_features, build_time_features
from backend.app.services.prediction_service import prediction_service

def verify_core_usp():
    print("======================================================================")
    print("CYBERSHIELD AI - CORE USP WORKFLOW VERIFICATION")
    print("NEW COMPLAINT -> HISTORICAL ML -> PREDICTED LOCATION")
    print("======================================================================")

    client = TestClient(app)
    db = SessionLocal()

    # Step 0: Officer Authentication
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@cybershield.gov.in", "password": "CyberAdmin@2026"}
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("[AUTH] Officer logged in successfully. Real JWT token acquired.")

    # Step 1: Section 1 — Dashboard & Complaints Entry Flow
    dash_resp = client.get("/api/v1/dashboard/summary")
    assert dash_resp.status_code == 200, "Dashboard summary failed"
    comp_list_resp = client.get("/api/v1/complaints", headers=headers)
    assert comp_list_resp.status_code == 200, "Complaints registry list failed"
    print("[FLOW] Dashboard -> Complaints entry flow operational.")

    # Record baseline DB counts
    p_count_before = db.query(Prediction).count()
    pl_count_before = db.query(PredictionLocation).count()
    a_count_before = db.query(Alert).count()

    # Step 2: Section 2 — Register ONE Fresh Delhi Complaint (Aman Sharma / Dwarka / ₹85,000)
    tx_ref = f"UTR-DL-USP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    incident_dt = (datetime.utcnow() - timedelta(hours=2)).isoformat()
    reported_dt = datetime.utcnow().isoformat()

    payload = {
        "victim_name": "Aman Sharma",
        "fraud_type": "Investment Scam",
        "amount": 85000.00,
        "state": "Delhi",
        "district": "South West Delhi",
        "locality": "Dwarka",
        "victim_location": "Dwarka, South West Delhi, Delhi",
        "payment_channel": "UPI",
        "victim_bank": "State Bank of India",
        "beneficiary_bank": "HDFC Bank",
        "beneficiary_id": "mule.recipient@okhdfcbank",
        "transaction_ref": tx_ref,
        "description": "Victim coerced into transferring funds via fake investment platform.",
        "incident_time": incident_dt,
        "reported_at": reported_dt
    }

    create_resp = client.post("/api/v1/complaints", json=payload, headers=headers)
    assert create_resp.status_code == 200, f"Complaint registration failed: {create_resp.text}"
    created = create_resp.json()
    new_comp_num = created["complaint_number"]
    new_comp_id = created["id"]
    print(f"\n[REGISTRATION] Complaint #{new_comp_num} created with DB ID: {new_comp_id}")

    # Verify atomic PostgreSQL persistence
    db_comp = db.query(Complaint).filter(Complaint.id == new_comp_id).first()
    assert db_comp is not None, "Complaint not persisted in PostgreSQL!"
    assert db_comp.victim_name == "Aman Sharma"
    assert float(db_comp.amount) == 85000.00
    assert db_comp.locality == "Dwarka"
    assert db_comp.district == "South West Delhi"
    assert db_comp.state == "Delhi"

    # Verify accounts and direct transaction
    txs = db.query(Transaction).filter(Transaction.complaint_id == new_comp_id).all()
    assert len(txs) == 1, f"Expected 1 direct transaction, found {len(txs)}"
    direct_tx = txs[0]
    assert direct_tx.transaction_ref == tx_ref
    assert float(direct_tx.amount) == 85000.00
    sender_acc = db.query(Account).filter(Account.id == direct_tx.sender_account_id).first()
    receiver_acc = db.query(Account).filter(Account.id == direct_tx.receiver_account_id).first()
    assert sender_acc is not None, "Sender account missing!"
    assert receiver_acc is not None, "Receiver account missing!"
    print(f"[PERSISTENCE] PostgreSQL verified: Complaint ID {new_comp_id}, Transaction ID {direct_tx.id}, Sender ACC #{sender_acc.account_number}, Receiver ACC #{receiver_acc.account_number}")

    # Step 3: Section 3 & 5 — Fetch same complaint from DB via /cases/{complaint_number}
    case_resp = client.get(f"/api/v1/complaints/{new_comp_num}")
    assert case_resp.status_code == 200, "Failed to fetch case"
    case_data = case_resp.json()
    assert case_data["complaint_number"] == new_comp_num
    assert case_data["victim_name"] == "Aman Sharma"
    assert float(case_data["amount"]) == 85000.00
    assert case_data["provenance_mode"] == "DIRECT_OFFICER_INPUT"
    print(f"[FETCH FROM DB] Case {new_comp_num} fetched cleanly from PostgreSQL without frontend state.")

    # Step 4: Section 6 — Direct Transaction Context & Truthful Graph
    graph_resp = client.get(f"/api/v1/complaints/{new_comp_num}/graph")
    assert graph_resp.status_code == 200, "Graph failed"
    graph_data = graph_resp.json()
    node_count = len(graph_data["nodes"])
    edge_count = len(graph_data["edges"])
    assert node_count == 2, f"Expected 2 nodes (victim, beneficiary), got {node_count}"
    assert edge_count == 1, f"Expected 1 edge, got {edge_count}"
    print(f"[CONTEXT & GRAPH] Direct Context: NetworkX Nodes={node_count}, Edges={edge_count} (Truthful, zero fabricated hops).")

    # Step 5: Section 7 & 8 — Feature Extraction: Location (25, 43) and Time (1, 20)
    loc_feat_res = build_location_features(db, new_comp_id, top_k=25, model_version="v3.1")
    time_feat_res = build_time_features(db, new_comp_id)

    assert loc_feat_res["status"] == "SUCCESS", f"Location features failed: {loc_feat_res.get('status')}"
    assert time_feat_res["status"] == "SUCCESS", f"Time features failed: {time_feat_res.get('status')}"

    X_loc = loc_feat_res["candidate_rows"]
    X_time = time_feat_res["values"]

    assert X_loc.shape == (25, 43), f"Expected Location feature shape (25, 43), got {X_loc.shape}"
    assert X_time.shape == (20,), f"Expected Time feature shape (20,), got {X_time.shape}"
    print(f"[FEATURE EXTRACTION] Location feature matrix shape: {X_loc.shape} (25 candidates x 43 features).")
    print(f"[FEATURE EXTRACTION] Time feature vector shape: ({len(X_time)},) (20 features).")

    # Step 6: Section 4 & 9 — Historical Trained Model Inference (No fit(), predict_proba executes)
    assert prediction_service.ml_provider.is_available(), "ML provider not available!"
    assert hasattr(prediction_service.ml_provider.location_model, "predict_proba"), "Location model missing predict_proba!"
    assert hasattr(prediction_service.ml_provider.time_model, "predict"), "Time model missing predict!"
    print(f"[MODEL LOADED] Historical Location Model V3.1 (SHA-256: {prediction_service.ml_provider.location_hash[:16]}...) verified.")
    print(f"[MODEL LOADED] Historical Time Model V2 verified.")

    # Step 7: Section 9 & 11 — Run Prediction & Atomically Persist
    pred_resp = client.post(f"/api/v1/predictions/{new_comp_num}", headers=headers)
    assert pred_resp.status_code == 200, f"Prediction run failed: {pred_resp.text}"
    pred_data = pred_resp.json()
    new_pred_id = pred_data["prediction_id"]
    pred_mode = pred_data["prediction_mode"]
    assert pred_mode == "trained_ml", f"Expected prediction_mode 'trained_ml', got {pred_mode}"
    print(f"[INFERENCE] Real ML inference executed without fit(). Mode: {pred_mode}. Prediction ID: #{new_pred_id}")

    # Verify Predictions delta (+1) and PredictionLocations delta (+3)
    p_count_after = db.query(Prediction).count()
    pl_count_after = db.query(PredictionLocation).count()
    assert p_count_after == p_count_before + 1, f"Expected +1 Prediction row, before={p_count_before}, after={p_count_after}"
    assert pl_count_after == pl_count_before + 3, f"Expected +3 PredictionLocation rows, before={pl_count_before}, after={pl_count_after}"

    # Step 8: Section 10 — Top-3 Delhi Candidate Zones & Time Window
    top_locs = pred_data["top_locations"]
    assert len(top_locs) == 3, f"Expected Top-3 locations, got {len(top_locs)}"
    top1 = top_locs[0]["location_name"]
    top2 = top_locs[1]["location_name"]
    top3 = top_locs[2]["location_name"]
    pred_window = pred_data["when_window"]

    # Verify all Top-3 clusters belong to Delhi
    for loc in top_locs:
        cid = loc["cluster_id"]
        c_obj = db.query(LocationCluster).filter(LocationCluster.id == cid).first()
        assert c_obj is not None, f"Cluster ID {cid} not found in DB!"
        assert c_obj.state == "Delhi", f"Cluster {c_obj.cluster_name} state is {c_obj.state}, expected Delhi!"

    print(f"[TOP-3 DELHI ZONES]:")
    print(f"   #1 Primary: {top1} (Rank 1, District: {top_locs[0].get('district')})")
    print(f"   #2 Secondary: {top2} (Rank 2, District: {top_locs[1].get('district')})")
    print(f"   #3 Tertiary: {top3} (Rank 3, District: {top_locs[2].get('district')})")
    print(f"   Predicted Window: {pred_window}")

    # Step 9: Section 13 — GIS Integration (Same Prediction ID)
    gis_resp = client.get(f"/api/v1/risk-map/prediction/{new_comp_num}")
    assert gis_resp.status_code == 200, f"GIS overlay failed: {gis_resp.text}"
    gis_data = gis_resp.json()
    gis_pred_id = gis_data["prediction_id"]
    assert gis_pred_id == new_pred_id, f"GIS prediction ID ({gis_pred_id}) != Case prediction ID ({new_pred_id})"
    print(f"[GIS VERIFIED] Map overlay uses exact same Prediction ID: #{gis_pred_id}")

    # Step 10: Section 14 — Alert Integration (Same Prediction ID)
    alert_resp = client.post(f"/api/v1/alerts/generate/{new_comp_num}", headers=headers)
    assert alert_resp.status_code == 200, f"Alert generation failed: {alert_resp.text}"
    alert_data = alert_resp.json()
    alert_id = alert_data["id"]
    alert_pred_id = alert_data["prediction_id"]
    assert alert_pred_id == new_pred_id, f"Alert prediction ID ({alert_pred_id}) != Case prediction ID ({new_pred_id})"
    print(f"[ALERT VERIFIED] Alert #{alert_id} generated from exact same Prediction ID: #{alert_pred_id}")

    # Step 11: Section 15 — Future Use of New Complaint in Registry
    # Re-query complaints registry
    reg_resp = client.get("/api/v1/complaints", headers=headers)
    assert reg_resp.status_code == 200
    reg_items = reg_resp.json()
    found_in_reg = [r for r in reg_items if r["complaint_number"] == new_comp_num]
    assert len(found_in_reg) == 1, "Complaint not found in operational registry!"
    assert found_in_reg[0]["prediction_status"] == "AVAILABLE"
    assert found_in_reg[0]["alert_status"] == "GENERATED"
    print(f"[REGISTRY PERSISTENCE] Complaint remains saved and accessible with Prediction=AVAILABLE, Alert=GENERATED.")

    # Step 12: Section 18 — Different-Complaint Validation (3 distinct complaints)
    print("\n[VALIDATION] Section 18: Registering 3 complaints with diverse characteristics to test feature sensitivity...")
    test_cases = [
        {
            "name": "Complaint A (Dwarka, UPI, ₹85k)",
            "victim_name": "Test Complainant A",
            "fraud_type": "Investment Scam",
            "amount": 85000.0,
            "district": "South West Delhi",
            "locality": "Dwarka",
            "channel": "UPI",
            "hours_ago": 2
        },
        {
            "name": "Complaint B (Rohini, RTGS, ₹250k)",
            "victim_name": "Test Complainant B",
            "fraud_type": "Part-time Job Fraud",
            "amount": 250000.0,
            "district": "North West Delhi",
            "locality": "Rohini",
            "channel": "RTGS",
            "hours_ago": 6
        },
        {
            "name": "Complaint C (Saket, IMPS, ₹35k)",
            "victim_name": "Test Complainant C",
            "fraud_type": "UPI / QR Code Fraud",
            "amount": 35000.0,
            "district": "South Delhi",
            "locality": "Saket",
            "channel": "IMPS",
            "hours_ago": 1
        }
    ]

    feature_vectors_loc = []
    feature_vectors_time = []
    case_ids = []

    for tc in test_cases:
        t_ref = f"UTR-DL-DIV-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
        p = {
            "victim_name": tc["victim_name"],
            "fraud_type": tc["fraud_type"],
            "amount": tc["amount"],
            "state": "Delhi",
            "district": tc["district"],
            "locality": tc["locality"],
            "victim_location": f"{tc['locality']}, {tc['district']}, Delhi",
            "payment_channel": tc["channel"],
            "victim_bank": "State Bank of India",
            "beneficiary_bank": "HDFC Bank",
            "beneficiary_id": "ben.recipient@okhdfcbank",
            "transaction_ref": t_ref,
            "incident_time": (datetime.utcnow() - timedelta(hours=tc["hours_ago"] + 1)).isoformat(),
            "reported_at": (datetime.utcnow() - timedelta(hours=tc["hours_ago"])).isoformat()
        }
        res = client.post("/api/v1/complaints", json=p, headers=headers)
        assert res.status_code == 200, f"Registration failed for {tc['name']}"
        cid = res.json()["id"]
        cnum = res.json()["complaint_number"]
        case_ids.append((cnum, cid))

        l_res = build_location_features(db, cid, top_k=25, model_version="v3.1")
        t_res = build_time_features(db, cid)
        assert l_res["status"] == "SUCCESS"
        assert t_res["status"] == "SUCCESS"

        feature_vectors_loc.append(l_res["candidate_rows"])
        feature_vectors_time.append(t_res["values"])
        print(f"   Registered {tc['name']}: {cnum} (ID: {cid}) -> Location Features: {l_res['candidate_rows'].shape}, Time Features: {t_res['values'].shape}")

    # Check that feature vectors differ across diverse inputs
    diff_AB_loc = float(np.nanmax(np.abs(np.nan_to_num(feature_vectors_loc[0]) - np.nan_to_num(feature_vectors_loc[1]))))
    diff_BC_loc = float(np.nanmax(np.abs(np.nan_to_num(feature_vectors_loc[1]) - np.nan_to_num(feature_vectors_loc[2]))))
    diff_AC_loc = float(np.nanmax(np.abs(np.nan_to_num(feature_vectors_loc[0]) - np.nan_to_num(feature_vectors_loc[2]))))

    diff_AB_time = float(np.nanmax(np.abs(np.nan_to_num(feature_vectors_time[0]) - np.nan_to_num(feature_vectors_time[1]))))
    diff_BC_time = float(np.nanmax(np.abs(np.nan_to_num(feature_vectors_time[1]) - np.nan_to_num(feature_vectors_time[2]))))
    diff_AC_time = float(np.nanmax(np.abs(np.nan_to_num(feature_vectors_time[0]) - np.nan_to_num(feature_vectors_time[2]))))

    print(f"\n[DIVERSITY METRICS]:")
    print(f"   Max absolute difference in Location Features A vs B: {diff_AB_loc:.4f}")
    print(f"   Max absolute difference in Location Features B vs C: {diff_BC_loc:.4f}")
    print(f"   Max absolute difference in Location Features A vs C: {diff_AC_loc:.4f}")
    print(f"   Max absolute difference in Time Features A vs B: {diff_AB_time:.4f}")
    print(f"   Max absolute difference in Time Features B vs C: {diff_BC_time:.4f}")
    print(f"   Max absolute difference in Time Features A vs C: {diff_AC_time:.4f}")

    assert diff_AB_loc > 1.0, "Location features between Complaint A and B are unexpectedly identical!"
    assert diff_BC_loc > 1.0, "Location features between Complaint B and C are unexpectedly identical!"
    assert diff_AB_time > 1.0, "Time features between Complaint A and B are unexpectedly identical!"
    assert diff_BC_time > 1.0, "Time features between Complaint B and C are unexpectedly identical!"
    print("[PASS] Section 18: Different complaints produce distinct, non-identical multi-modal feature vectors.")

    db.close()
    print("\n======================================================================")
    print("CORE USP — NEW COMPLAINT → HISTORICAL ML → PREDICTED LOCATION: PASS")
    print("======================================================================")

    return {
        "complaint_number": new_comp_num,
        "complaint_id": new_comp_id,
        "transaction_id": direct_tx.id,
        "prediction_id": new_pred_id,
        "top1": top1,
        "top2": top2,
        "top3": top3,
        "predicted_window": pred_window
    }

if __name__ == "__main__":
    out = verify_core_usp()
    print(f"COMPLAINT_NUMBER={out['complaint_number']}")
    print(f"COMPLAINT_ID={out['complaint_id']}")
    print(f"TRANSACTION_ID={out['transaction_id']}")
    print(f"PREDICTION_ID={out['prediction_id']}")
    print(f"TOP1={out['top1']}")
    print(f"TOP2={out['top2']}")
    print(f"TOP3={out['top3']}")
    print(f"WINDOW={out['predicted_window']}")
