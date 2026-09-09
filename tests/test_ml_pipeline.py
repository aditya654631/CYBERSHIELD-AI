import os
import json
import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch
from datetime import datetime

from ml.features.feature_pipeline import FeaturePipeline, FEATURE_COLUMNS_LOCATION, FEATURE_COLUMNS_TIME
from ml.geo.candidate_generator import CandidateLocationGenerator
from backend.app.services.prediction_service import MLPredictionProvider, DemoPredictionProvider, PredictionService
from backend.app.models.models import Complaint, Prediction, Alert, AuditLog, Account, Transaction
from backend.app.models.db import SessionLocal


def test_feature_pipeline_zero_leakage():
    """Verify that actual withdrawal target fields are NOT in the feature lists."""
    forbidden_leakage = [
        "actual_withdrawal_cluster",
        "withdrawal_cluster_id",
        "actual_atm_id",
        "cashout_timestamp",
        "actual_withdrawal_lat",
        "actual_withdrawal_lon",
        "minutes_until_cashout"
    ]
    for feat in forbidden_leakage:
        assert feat not in FEATURE_COLUMNS_LOCATION, f"Leakage detected in FEATURE_COLUMNS_LOCATION: {feat}"
        assert feat not in FEATURE_COLUMNS_TIME, f"Leakage detected in FEATURE_COLUMNS_TIME: {feat}"


def test_candidate_generator_output():
    """Verify candidate generation produces between 15 and 40 candidates with valid schema."""
    gen = CandidateLocationGenerator()
    assert len(gen.clusters) >= 50
    complaint_dict = {
        "victim_lat": 22.7196,
        "victim_lon": 75.8577,
        "victim_state": "Madhya Pradesh"
    }
    candidates = gen.generate_candidates_for_complaint(
        complaint=complaint_dict,
        top_k=25
    )
    assert 15 <= len(candidates) <= 40
    for cand in candidates:
        assert "cluster_id" in cand
        assert "name" in cand
        assert "latitude" in cand
        assert "longitude" in cand
        assert "reasoning" in cand


def test_ml_artifacts_exist_and_loadable():
    """Ensure trained artifacts v1 exist and load properly."""
    provider = MLPredictionProvider()
    assert provider.is_available() is True
    assert provider.location_model is not None
    assert provider.time_model is not None
    assert provider.metadata is not None
    assert provider.metadata.get("model_version") in ["cashout-location-xgb-v2", "cashout-location-xgb-v1"]
    assert "XGBClassifier" in provider.metadata.get("model_class_location", "")


def test_ml_predict_proba_and_predict():
    """Verify MLPredictionProvider invokes actual predict_proba and predict on a complaint."""
    db = SessionLocal()
    try:
        provider = MLPredictionProvider()
        # Find or create a non-CMP-1042 complaint for ML test
        complaint = db.query(Complaint).filter(Complaint.complaint_number != "CMP-1042").first()
        if not complaint:
            complaint = Complaint(
                complaint_number="CMP-TEST-UNIT-99",
                complainant_name="Test User",
                complainant_phone="9876543210",
                fraud_type="UPI / QR Code Fraud",
                amount=75000.0,
                victim_lat=22.7196,
                victim_lon=75.8577,
                victim_state="Madhya Pradesh",
                payment_channel="UPI",
                status="OPEN"
            )
            db.add(complaint)
            db.commit()
            db.refresh(complaint)

        result = provider.predict(complaint, db)

        assert result["prediction_mode"] == "trained_ml"
        assert result["model_version"] in ["cashout-location-xgb-v2", "cashout-location-xgb-v1"]
        assert len(result["top_locations"]) == 3
        assert 0.0 <= result["ml_score"] <= 1.0
        assert 0.0 <= result["graph_score"] <= 1.0
        assert 0.0 <= result["geo_score"] <= 1.0
        assert 0.0 <= result["temporal_score"] <= 1.0
        assert 0.0 <= result["risk_score"] <= 1.0
        assert "hour" in result["when_window"].lower() or "min" in result["when_window"].lower()
    finally:
        db.close()


def test_demo_provider_for_cmp_1042():
    """CMP-1042 must explicitly route to DemoPredictionProvider."""
    db = SessionLocal()
    try:
        service = PredictionService()
        complaint = db.query(Complaint).filter(Complaint.complaint_number == "CMP-1042").first()
        if complaint:
            res = service.run_prediction(db, complaint.id)
            assert res.prediction_mode == "deterministic_demo"
            assert res.model_version == "demo-provider-v1"
            assert len(res.locations) == 3
    finally:
        db.close()


def test_fallback_on_ml_error():
    """If MLPredictionProvider throws an exception, PredictionService must safely fall back to deterministic_demo."""
    db = SessionLocal()
    try:
        service = PredictionService()
        with patch.object(service.ml_provider, "predict", side_effect=RuntimeError("Simulated GPU/Inference Crash")):
            complaint = db.query(Complaint).filter(Complaint.complaint_number != "CMP-1042").first()
            if complaint:
                res = service.run_prediction(db, complaint.id)
                assert res.prediction_mode == "deterministic_demo"
                assert res.model_version == "demo-provider-v1"
    finally:
        db.close()
