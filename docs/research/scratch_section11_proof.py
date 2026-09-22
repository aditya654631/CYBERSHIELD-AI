"""
API Inference Proof Script for Section 11 of ML Validity Audit.
Executes inference on a completely new complaint and logs:
- complaint ID
- candidate count
- X_loc shape
- X_time shape
- location_model.predict_proba(X_loc) execution & output
- time_model.predict(X_time) execution & output
- top 3 probabilities
- prediction_mode & model_version
- DB persisted prediction ID
"""

import os
import sys
import time
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.db import SessionLocal
from backend.app.models.models import Complaint, Account, Transaction, Prediction, PredictionLocation
from backend.app.services.prediction_service import prediction_service

def run_proof():
    client = TestClient(app)
    db = SessionLocal()

    ts = int(time.time())
    comp_num = f"CMP-AUDIT-PROOF-{ts}"

    # 1. Create Complaint
    complaint = Complaint(
        complaint_number=comp_num,
        victim_name="Sanjay Kulkarni",
        victim_phone="9876543210",
        victim_location="Pune",
        state="Maharashtra",
        district="Pune",
        fraud_type="Digital Arrest / Extortion",
        amount=240000.0,
        payment_channel="NEFT",
        risk_level="CRITICAL",
        risk_score=0.88,
        reported_at=datetime.utcnow() - timedelta(minutes=30),
        incident_time=datetime.utcnow() - timedelta(hours=3)
    )
    db.add(complaint)
    db.commit()
    db.refresh(complaint)
    comp_id = complaint.id

    # 2. Accounts (Victim + Intermediary + Beneficiary in Bandra / Mumbai)
    acc_vic = Account(
        account_number=f"ACC-VIC-{ts}",
        masked_account="XXXX-XXXX-1122",
        holder_name="Sanjay Kulkarni",
        bank_name="State Bank of India",
        branch="Pune FC Road",
        is_mule=False,
        risk_score=0.05
    )
    acc_mule = Account(
        account_number=f"ACC-MULE-{ts}",
        masked_account="XXXX-XXXX-9988",
        holder_name="Ramesh Solanki",
        bank_name="Axis Bank",
        branch="Bandra West, Mumbai",
        is_mule=True,
        risk_score=0.91
    )
    db.add_all([acc_vic, acc_mule])
    db.commit()

    # 3. Transaction
    tx = Transaction(
        transaction_ref=f"TXN-AUDIT-{ts}",
        complaint_id=comp_id,
        sender_account_id=acc_vic.id,
        receiver_account_id=acc_mule.id,
        amount=240000.0,
        hop_number=1,
        payment_channel="NEFT",
        timestamp=datetime.utcnow() - timedelta(minutes=25)
    )
    db.add(tx)
    db.commit()

    # 4. Extract candidates and feature shapes directly via MLPredictionProvider
    ml_provider = prediction_service.ml_provider
    assert ml_provider.is_available()

    complaint_dict = {
        "complaint_id": comp_id,
        "amount": complaint.amount,
        "fraud_type": complaint.fraud_type,
        "payment_channel": complaint.payment_channel,
        "complaint_timestamp": complaint.reported_at.isoformat(),
        "victim_lat": 18.5204,
        "victim_lon": 73.8567,
        "victim_state": complaint.state,
        "hop_count": 1
    }

    from ml.geo.candidate_generator import CandidateLocationGenerator
    from ml.features.feature_pipeline import feature_pipeline

    cand_gen = CandidateLocationGenerator()
    candidates = cand_gen.generate_candidates_for_complaint(
        complaint_dict,
        beneficiary_mule_cluster_id=20, # Bandra Kurla Complex, Mumbai
        top_k=25
    )
    candidate_count = len(candidates)

    X_loc, X_time, loc_cols, time_cols = feature_pipeline.build_candidate_matrix(
        complaint_dict,
        candidates
    )

    # Actual calls
    cand_probs = ml_provider.location_model.predict_proba(X_loc)[:, 1]
    time_pred = float(ml_provider.time_model.predict(X_time)[0])

    ranked_pairs = sorted(zip(cand_probs, candidates), key=lambda x: x[0], reverse=True)
    top_3 = ranked_pairs[:3]

    # 5. Call API Endpoint
    resp = client.post(f"/api/v1/predictions/{comp_id}")
    assert resp.status_code == 200
    api_data = resp.json()

    # 6. Query Fresh DB
    fresh_db = SessionLocal()
    try:
        persisted = fresh_db.query(Prediction).filter(Prediction.complaint_id == comp_id).order_by(Prediction.id.desc()).first()
        pred_db_id = persisted.id if persisted else None
    finally:
        fresh_db.close()
        db.close()

    print("\n" + "=" * 70)
    print("SECTION 11 AUDIT PROOF OUTPUT")
    print("=" * 70)
    print(f"Complaint ID:                 {comp_id}")
    print(f"Complaint Number:             {comp_num}")
    print(f"Candidate Count:              {candidate_count}")
    print(f"X_loc Shape:                  {X_loc.shape} (Candidates x Features)")
    print(f"X_time Shape:                 {X_time.shape} (Batch x Features)")
    print(f"location_model.predict_proba: Executed -> shape={cand_probs.shape}, range=[{cand_probs.min():.4f}, {cand_probs.max():.4f}]")
    print(f"time_model.predict:           Executed -> output={time_pred:.1f} minutes")
    print(f"Top 3 Candidate Probabilities:")
    for rank, (p, c) in enumerate(top_3, 1):
        print(f"   Rank {rank}: {c['name']} ({c['city']}) -> Probability: {p:.4f}")
    print(f"API Returned prediction_mode: {api_data.get('prediction_mode')}")
    print(f"API Returned model_version:   {api_data.get('model_version')}")
    print(f"DB Persisted Prediction ID:   {pred_db_id}")
    print("=" * 70)

if __name__ == "__main__":
    run_proof()
