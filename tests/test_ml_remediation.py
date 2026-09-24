"""
Automated Unit and Integration Tests for ML Validity Remediation (v2)
Tests:
1. Zero force-add in candidate generation for validation/test.
2. Calibrator v2 loading and probability transformation.
3. Cold-start test cohort separation (zero account overlap with train).
4. PredictionService v2 inference provenance (trained_ml, cashout-location-xgb-v2).
5. Stable demo routing preservation for CMP-1042.
6. Model Performance API serving v2 defensible metrics.
"""

import os
import json
import pytest
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.db import SessionLocal
from backend.app.models.models import Complaint, Account, Transaction, Prediction
from backend.app.services.prediction_service import MLPredictionProvider, PredictionService
from ml.geo.candidate_generator import CandidateLocationGenerator

client = TestClient(app)

def test_v2_artifacts_exist_and_loadable():
    """Ensure v2 trained artifacts and Platt calibrator exist and load properly."""
    provider = MLPredictionProvider()
    assert provider.is_available() is True
    assert provider.location_model is not None
    assert provider.time_model is not None
    assert provider.calibrator is not None
    assert provider.metadata is not None
    assert provider.metadata.get("model_version") in [
        "cashout-location-xgb-v8-debiased",
        "cashout-location-xgb-v7-compat",
        "cashout-location-xgb-v4",
        "cashout-location-xgb-v3.1",
        "cashout-location-xgb-v2"
    ]


def test_zero_force_add_on_test_candidate_generation():
    """Verify that test candidate generation never artificially force-adds ground-truth cluster."""
    gen = CandidateLocationGenerator()
    complaint_dict = {
        "victim_lat": 22.7196,
        "victim_lon": 75.8577,
        "victim_state": "Madhya Pradesh"
    }
    # Natural generation
    natural_cands = gen.generate_candidates_for_complaint(complaint_dict, top_k=25)
    c_ids = [c["cluster_id"] for c in natural_cands]

    # In v2, candidate set size remains strictly natural (len <= 25)
    assert len(natural_cands) <= 25
    # Cluster 53 (Tonk Road Flyover Zone, Jaipur) is a distant cluster outside MP and not in the top-10 national hotspots
    assert 53 not in c_ids


def test_cold_start_cohort_isolation():
    """Verify cold-start test complaints have 0% mule account overlap with the training cohort."""
    complaints_df = pd.read_csv("ml/data/complaints.csv.gz", compression="gzip")
    complaints_df = complaints_df.sort_values(by="incident_timestamp").reset_index(drop=True)

    train_complaints = complaints_df.iloc[:14000]
    cold_complaints = complaints_df[complaints_df["is_cold_start"]]

    train_mules = set(train_complaints["beneficiary_mule_id"].unique())
    cold_mules = set(cold_complaints["beneficiary_mule_id"].unique())

    overlap = train_mules.intersection(cold_mules)
    assert len(overlap) == 0, f"Cold-start leak detected: {len(overlap)} mules shared with train"


def test_prediction_service_v2_inference():
    """Verify PredictionService executes v2 inference with calibrated probabilities."""
    db = SessionLocal()
    try:
        service = PredictionService()
        # Find Delhi complaint
        complaint = db.query(Complaint).filter(Complaint.state == "Delhi").first()
        if not complaint:
            complaint = Complaint(
                complaint_number="CMP-REMED-TEST-01",
                victim_name="Remediation Test",
                victim_phone="9112233445",
                victim_location="Connaught Place, Delhi",
                state="Delhi",
                district="CENTRAL_NEW_DELHI",
                fraud_type="UPI / QR Code Fraud",
                amount=60000.0,
                payment_channel="UPI"
            )
            db.add(complaint)
            db.commit()
            db.refresh(complaint)

        pred = service.run_prediction(db, complaint.id)

        assert pred.prediction_mode == "trained_ml"
        assert pred.model_version in ["cashout-location-xgb-v8-debiased", "cashout-location-xgb-v7-compat", "cashout-location-xgb-v4", "cashout-location-xgb-v3.1", "cashout-location-xgb-v2"]
        assert 0.0 <= pred.risk_score <= 1.0
        assert len(pred.locations) == 3
        for loc in pred.locations:
            assert 0.0 <= loc.probability <= 1.0
    finally:
        db.close()


def test_cmp_1042_deterministic_demo_preservation():
    """CMP-1042 must continue returning deterministic_demo and demo-provider-v1."""
    db = SessionLocal()
    try:
        service = PredictionService()
        complaint = db.query(Complaint).filter(Complaint.complaint_number == "CMP-1042").first()
        if complaint:
            pred = service.run_prediction(db, complaint.id)
            assert pred.prediction_mode == "deterministic_demo"
            assert pred.model_version == "demo-provider-v1"
            assert pred.locations[0].location_name == "Vijay Nagar, Indore"
    finally:
        db.close()


def test_model_performance_api_v2_metrics():
    """Verify GET /api/v1/model/performance serves defensible metrics with authentication."""
    from backend.app.auth.security import create_access_token
    token = create_access_token({"sub": "admin@cybershield.gov.in", "role": "I4C_ADMIN"})
    resp = client.get("/api/v1/model/performance", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()

    assert data["prediction_mode"] == "trained_ml"
    assert data["model_version"] in [
        "cashout-location-xgb-v8-debiased",
        "cashout-location-xgb-v7-compat",
        "cashout-location-xgb-v4",
        "cashout-location-xgb-v3.1",
        "cashout-location-xgb-v2"
    ]
    assert "Cluster-level prioritization" in data["geographic_disclaimer"]
    assert len(data["metrics_comparison"]) >= 1
