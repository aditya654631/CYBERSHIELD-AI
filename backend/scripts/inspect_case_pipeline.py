#!/usr/bin/env python3
"""
CyberShield AI — Development Case Pipeline Inspector
Usage:
    python backend/scripts/inspect_case_pipeline.py CMP-NEW-XXXXXX
"""

import os
import sys
import argparse

# Add repository root to pythonpath
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.models.db import SessionLocal
from backend.app.models.models import Complaint, Prediction, Alert, Transaction, Account, ComplaintAccount
from backend.app.services.transaction_context_service import resolve_transaction_context
from backend.app.services.graph_service import build_complaint_graph
from backend.app.services.ml_feature_service import build_location_features, build_time_features
from backend.app.services.delhi_origin_resolver import resolve_delhi_origin


def mask_account(acc_no: str) -> str:
    if not acc_no:
        return "N/A"
    s = str(acc_no)
    if len(s) <= 4:
        return "****"
    return f"****{s[-4:]}"


def inspect_pipeline(case_identifier: str):
    db = SessionLocal()
    try:
        if case_identifier.isdigit():
            complaint = db.query(Complaint).filter(Complaint.id == int(case_identifier)).first()
        else:
            complaint = db.query(Complaint).filter(Complaint.complaint_number == case_identifier).first()

        if not complaint:
            print(f"ERROR: Complaint '{case_identifier}' not found in database.")
            sys.exit(1)

        print("=" * 70)
        print("CYBERSHIELD AI — CASE PIPELINE INSPECTION")
        print("=" * 70)

        # 1. Stored Complaint & Accounts
        print(f"Complaint DB ID:        {complaint.id}")
        print(f"Complaint Number:       {complaint.complaint_number}")
        print(f"Stored Locality:        {complaint.locality or complaint.victim_location or 'N/A'}")
        print(f"Amount Lost:            INR {complaint.amount:,.2f}")
        print(f"Fraud Type:             {complaint.fraud_type}")
        print(f"Payment Channel:        {complaint.payment_channel}")

        # Linked Accounts
        cas = db.query(ComplaintAccount).filter(ComplaintAccount.complaint_id == complaint.id).all()
        acc_ids = [ca.account_id for ca in cas]
        print(f"Linked Account IDs:     {acc_ids} (Count: {len(acc_ids)})")

        # Transactions
        txs = db.query(Transaction).filter(Transaction.complaint_id == complaint.id).all()
        tx_ids = [t.id for t in txs]
        print(f"Direct Transaction IDs: {tx_ids} (Count: {len(tx_ids)})")

        # 2. Context Mode
        ctx = resolve_transaction_context(db, complaint)
        print(f"Context Mode:           {ctx.get('context_type')} (Transactions: {ctx.get('transaction_count')})")

        # 3. Resolved Delhi Origin
        loc_str = getattr(complaint, "locality", None) or getattr(complaint, "victim_location", None)
        origin_res = resolve_delhi_origin(
            locality=loc_str,
            district=complaint.district,
            lat=float(complaint.victim_lat) if complaint.victim_lat is not None else None,
            lon=float(complaint.victim_lon) if complaint.victim_lon is not None else None
        )
        print(f"Resolved Delhi Origin:  District={origin_res.get('resolved_district')}, Coords=({origin_res.get('resolved_lat')}, {origin_res.get('resolved_lon')})")
        print(f"Origin Provenance:      {origin_res.get('provenance')}")

        # 4. Graph Metrics
        graph = build_complaint_graph(db, complaint.id)
        g_metrics = graph.get("metrics", {})
        print(f"Graph Node Count:       {g_metrics.get('node_count', 0)}")
        print(f"Graph Edge Count:       {g_metrics.get('edge_count', 0)}")
        print(f"Graph Max Hop:          {g_metrics.get('max_hop', 0)}")

        # 5. Features
        loc_res = build_location_features(db, complaint.id, top_k=25, model_version="v3.1")
        time_res = build_time_features(db, complaint.id)
        loc_shape = loc_res.get("candidate_rows").shape if loc_res.get("candidate_rows") is not None else "N/A"
        time_shape = time_res.get("values").shape if time_res.get("values") is not None else "N/A"
        print(f"Location Feature Shape: {loc_shape}")
        print(f"Time Feature Shape:     {time_shape}")

        # 6. Latest Prediction
        latest_pred = (
            db.query(Prediction)
            .filter(Prediction.complaint_id == complaint.id)
            .order_by(Prediction.created_at.desc(), Prediction.id.desc())
            .first()
        )

        if latest_pred:
            print(f"Latest Prediction ID:   #{latest_pred.id} (Mode: {latest_pred.prediction_mode}, Model: {latest_pred.model_version})")
            print(f"Predicted Window:       {latest_pred.window_label}")
            sorted_locs = sorted(latest_pred.locations, key=lambda l: l.rank)
            for l in sorted_locs:
                print(f"  Top {l.rank}: {l.location_name} (Cluster {l.cluster_id}, Risk: {l.risk_level})")
        else:
            print("Latest Prediction ID:   None (Analysis Not Yet Run)")
            print("Top1:                   N/A")
            print("Top2:                   N/A")
            print("Top3:                   N/A")

        # 7. Alert IDs
        alerts = db.query(Alert).filter(Alert.complaint_id == complaint.id).all()
        alert_ids = [a.id for a in alerts]
        print(f"Alert IDs:              {alert_ids} (Count: {len(alert_ids)})")

        # Developer Only: Raw Scores if prediction exists
        if latest_pred and latest_pred.locations:
            print("\n--- DEVELOPER DIAGNOSTICS (RAW ML SCORES) ---")
            for l in sorted(latest_pred.locations, key=lambda x: x.rank):
                print(f"  Rank #{l.rank} [{l.location_name}]: prob={l.probability:.6f}, distance={l.distance_km:.1f}km")

        print("=" * 70)

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CyberShield AI Case Pipeline Inspector")
    parser.add_argument("case_number", help="Complaint number (e.g. CMP-NEW-000126) or DB ID")
    args = parser.parse_args()
    inspect_pipeline(args.case_number)
