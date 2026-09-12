"""
CyberShield AI - Prediction Time-Metadata Persistence & Response Formatting Regression Tests

Tests verifying:
1. Exact time metadata persistence in Prediction ORM table (no rounding, no reconstruction)
2. Persisted / GIS response formatting exactness (35.3, cashout-time-xgb-v3, MONITOR for priority=50)
3. Legacy NULL metadata formatting (None, not fake fallback versions)
4. Preservation of persisted operational window (window_label as when_window / operational_window)
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.models.db import Base
from backend.app.models.models import Complaint, Prediction, LocationCluster
from backend.app.services.prediction_persistence_service import prediction_persistence_service
from backend.app.api.prediction_routes import _format_prediction_response, _derive_priority_level
from backend.app.schemas.schemas import PredictionResponse


@pytest.fixture(scope="function")
def sqlite_db():
    """
    Isolated in-memory SQLite fixture with full metadata schema.
    Validates model persistence independently of pending unapplied Alembic migrations.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed clusters needed for Top-3 location persistence
    for i, cid in enumerate([7, 8, 9], start=1):
        cluster = LocationCluster(
            id=cid,
            cluster_name=f"Cluster-{cid}",
            city="Delhi",
            district="New Delhi",
            state="Delhi",
            center_lat=28.60 + 0.01 * i,
            center_lon=77.20 + 0.01 * i
        )
        session.add(cluster)

    # Seed minimal complaint
    complaint = Complaint(
        id=101,
        complaint_number="CMP-TEST-TIME-001",
        fraud_type="UPI Fraud",
        amount=65000.0,
        victim_location="Rohini, Delhi",
        reported_at=datetime.now(timezone.utc)
    )
    session.add(complaint)
    session.commit()

    yield session
    session.close()


def test_exact_time_metadata_persistence(sqlite_db):
    """
    Goal 1: Exact time metadata persistence
    When trained prediction contains:
      "time_prediction": {
          "predicted_minutes_to_cashout": 35.3,
          "model_version": "cashout-time-xgb-v3"
      }
    the persisted Prediction row must store:
      prediction.predicted_minutes_to_cashout == 35.3
      prediction.time_model_version == "cashout-time-xgb-v3"
    """
    complaint = sqlite_db.query(Complaint).filter(Complaint.id == 101).first()
    assert complaint is not None

    prediction_data = {
        "status": "SUCCESS",
        "prediction_mode": "trained_ml",
        "model_version": "cashout-location-xgb-v4",
        "risk_score": 0.88,
        "risk_level": "MEDIUM",
        "intervention_priority": 50,
        "top_locations": [
            {"rank": 1, "cluster_id": 7, "location_name": "Cluster-7", "ml_probability": 0.88, "risk_band": "MEDIUM", "distance_km": 1.2},
            {"rank": 2, "cluster_id": 8, "location_name": "Cluster-8", "ml_probability": 0.75, "risk_band": "MEDIUM", "distance_km": 2.2},
            {"rank": 3, "cluster_id": 9, "location_name": "Cluster-9", "ml_probability": 0.60, "risk_band": "LOW", "distance_km": 3.2}
        ],
        "time_prediction": {
            "predicted_minutes_to_cashout": 35.3,
            "model_version": "cashout-time-xgb-v3"
        }
    }

    persisted = prediction_persistence_service.persist_prediction(
        sqlite_db, complaint, prediction_data, bypass_debounce=True
    )
    assert persisted is not None

    # Verify directly on returned ORM entity
    assert persisted.predicted_minutes_to_cashout == 35.3
    assert persisted.time_model_version == "cashout-time-xgb-v3"

    # Query afresh from DB to verify raw storage round-trip
    reloaded = sqlite_db.query(Prediction).filter(Prediction.id == persisted.id).first()
    assert reloaded is not None
    assert reloaded.predicted_minutes_to_cashout == 35.3
    assert reloaded.time_model_version == "cashout-time-xgb-v3"
    assert isinstance(reloaded.predicted_minutes_to_cashout, float)


def test_persisted_response_exactness():
    """
    Goal 2: Persisted / GIS response exactness
    A Prediction row with:
      predicted_minutes_to_cashout = 35.3
      time_model_version = "cashout-time-xgb-v3"
      intervention_priority = 50
      risk_level = "MEDIUM"
    must return:
      time_prediction.predicted_minutes_to_cashout == 35.3
      time_prediction.model_version == "cashout-time-xgb-v3"
      priority_level == "MONITOR"
    """
    comp = Complaint(
        id=201,
        complaint_number="CMP-TEST-TIME-002",
        fraud_type="UPI Fraud",
        amount=50000.0,
        victim_location="Connaught Place, Delhi",
        reported_at=datetime.now(timezone.utc)
    )

    pred = Prediction(
        id=1001,
        complaint_id=201,
        prediction_mode="trained_ml",
        model_version="cashout-location-xgb-v4",
        time_model_version="cashout-time-xgb-v3",
        predicted_minutes_to_cashout=35.3,
        predicted_window_start=datetime.now(timezone.utc),
        predicted_window_end=datetime.now(timezone.utc),
        window_label="Next 10–70 Minutes (operational estimate window)",
        intervention_priority=50,
        risk_level="MEDIUM",
        risk_score=0.88,
        confidence_score=0.90,
        ml_score=0.88
    )
    pred.locations = []

    res = _format_prediction_response(pred, comp)

    assert res["time_prediction"]["predicted_minutes_to_cashout"] == 35.3
    assert res["time_prediction"]["model_version"] == "cashout-time-xgb-v3"
    assert res["priority_level"] == "MONITOR"
    assert res["intervention_priority"] == 50

    # Ensure response passes Pydantic schema validation
    validated = PredictionResponse.model_validate(res)
    assert validated.time_prediction.predicted_minutes_to_cashout == 35.3
    assert validated.time_prediction.model_version == "cashout-time-xgb-v3"
    assert validated.priority_level == "MONITOR"


def test_legacy_null_metadata():
    """
    Goal 3: Legacy NULL metadata
    A legacy Prediction row with:
      predicted_minutes_to_cashout = None
      time_model_version = None
    must return:
      time_prediction.predicted_minutes_to_cashout is None
      time_prediction.model_version is None
    No fake 'cashout-time-xgb-v2', 'cashout-time-xgb-v3', or other fallback version.
    """
    comp = Complaint(
        id=202,
        complaint_number="CMP-TEST-TIME-003",
        fraud_type="NetBanking",
        amount=25000.0,
        victim_location="Karol Bagh, Delhi",
        reported_at=datetime.now(timezone.utc)
    )

    legacy_pred = Prediction(
        id=1002,
        complaint_id=202,
        prediction_mode="trained_ml",
        model_version="cashout-location-xgb-v3.1",
        time_model_version=None,
        predicted_minutes_to_cashout=None,
        predicted_window_start=datetime.now(timezone.utc),
        predicted_window_end=datetime.now(timezone.utc),
        window_label="Next 2–4 Hours (operational estimate window)",
        intervention_priority=50,
        risk_level="MEDIUM",
        risk_score=0.75
    )
    legacy_pred.locations = []

    res = _format_prediction_response(legacy_pred, comp)

    assert res["time_prediction"]["predicted_minutes_to_cashout"] is None
    assert res["time_prediction"]["model_version"] is None
    assert res["time_prediction"]["model_version"] != "cashout-time-xgb-v2"
    assert res["time_prediction"]["model_version"] != "cashout-time-xgb-v3"
    assert res["priority_level"] == "MONITOR"

    # Schema validation must succeed with null legacy time metadata
    validated = PredictionResponse.model_validate(res)
    assert validated.time_prediction.predicted_minutes_to_cashout is None
    assert validated.time_prediction.model_version is None


def test_preserve_persisted_operational_window():
    """
    Goal 4: Preserve persisted operational window
    Existing persisted window_label must be returned unchanged as
    when_window and time_prediction.operational_window.
    """
    comp = Complaint(
        id=203,
        complaint_number="CMP-TEST-TIME-004",
        fraud_type="UPI Fraud",
        amount=10000.0,
        victim_location="Paharganj, Delhi",
        reported_at=datetime.now(timezone.utc)
    )

    custom_window = "Next 15–85 Minutes (custom operational estimate window)"
    pred = Prediction(
        id=1003,
        complaint_id=203,
        prediction_mode="trained_ml",
        model_version="cashout-location-xgb-v4",
        time_model_version="cashout-time-xgb-v3",
        predicted_minutes_to_cashout=50.0,
        predicted_window_start=datetime.now(timezone.utc),
        predicted_window_end=datetime.now(timezone.utc),
        window_label=custom_window,
        intervention_priority=90,
        risk_level="CRITICAL",
        risk_score=0.95
    )
    pred.locations = []

    res = _format_prediction_response(pred, comp)

    assert res["when_window"] == custom_window
    assert res["time_prediction"]["operational_window"] == custom_window
    assert res["priority_level"] == "IMMEDIATE ACTION"
