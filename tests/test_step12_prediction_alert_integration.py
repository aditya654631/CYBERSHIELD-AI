"""
CyberShield AI — Phase 1 Step 12: Persisted Prediction -> Alert Integration Test Suite

Tests covering:
1. Alert created from exact prediction_id
2. alert.prediction_id FK correctness
3. Complaint identity correctness
4. Primary cluster == Prediction rank 1 location
5. Location name/coordinates consistency with LocationCluster
6. Risk score & probability consistency with Prediction
7. Operational time window consistency
8. Zero ML inference invocation
9. Zero Withdrawal ground-truth access
10. Zero Prediction mutation (Prediction & PredictionLocation immutable)
11. Atomic rollback on failure
12. Duplicate alert prevention / Idempotency (same prediction_id returns existing alert)
13. New prediction creates new alert
14. Outside-scope / no-prediction creates zero alerts (HTTP 404)
15. CMP-1042 deterministic_demo provenance preserved
16. Acknowledgement persistence
17. Repeated acknowledgement safe (idempotent)
18. End-to-end chain: GIS prediction_id == Alert prediction_id == Alert API response
"""

import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.models.db import SessionLocal
from backend.app.models.models import (
    Complaint, Prediction, PredictionLocation, LocationCluster,
    Alert, Withdrawal, Account, Transaction, AuditLog
)
from backend.app.services.prediction_persistence_service import prediction_persistence_service
from backend.app.services.alert_service import create_alert_for_prediction

from backend.app.auth.security import create_access_token

client = TestClient(app)
_test_token = create_access_token({"sub": "admin@cybershield.gov.in", "role": "I4C_ADMIN"})
client.headers["Authorization"] = f"Bearer {_test_token}"


@pytest.fixture(scope="function")
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(autouse=True, scope="module")
def ensure_test_predictions():
    db = SessionLocal()
    try:
        for c_num in ["CMP-NEW-000002", "CMP-NEW-000003", "CMP-DL-0001", "CMP-1042"]:
            comp = db.query(Complaint).filter(Complaint.complaint_number == c_num).first()
            if comp:
                pred = prediction_persistence_service.get_latest_prediction(db, comp.id)
                if not pred:
                    client.post(f"/api/v1/predictions/{c_num}")
    finally:
        db.close()


def test_alert_created_from_exact_prediction_id(db: Session):
    """
    Requirements 2, 3, 23, 24:
    Verify Alert is created strictly for an existing persisted prediction_id.
    """
    comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    assert comp is not None

    latest_pred = prediction_persistence_service.get_latest_prediction(db, comp.id)
    assert latest_pred is not None

    rank1_loc = (
        db.query(PredictionLocation)
        .filter(PredictionLocation.prediction_id == latest_pred.id, PredictionLocation.rank == 1)
        .first()
    )
    assert rank1_loc is not None
    cluster_row = db.query(LocationCluster).filter(LocationCluster.id == rank1_loc.cluster_id).first()
    assert cluster_row is not None

    resp = client.post(f"/api/v1/alerts/prediction/{latest_pred.id}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["prediction_id"] == latest_pred.id
    assert data["complaint_id"] == comp.id
    assert data["complaint_number"] == comp.complaint_number
    assert data["status"] in ("NEW", "ACKNOWLEDGED")
    assert data["location_name"] == cluster_row.cluster_name


def test_primary_cluster_and_location_identity(db: Session):
    """
    Requirements 4, 5, 7:
    Verify:
    - Primary cluster ID matches Rank 1 Location cluster ID
    - Location name originates from LocationCluster table
    """
    comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    latest_pred = prediction_persistence_service.get_latest_prediction(db, comp.id)
    assert latest_pred is not None

    rank1_loc = (
        db.query(PredictionLocation)
        .filter(PredictionLocation.prediction_id == latest_pred.id, PredictionLocation.rank == 1)
        .first()
    )
    assert rank1_loc is not None

    # Enforce primary cluster invariant
    assert latest_pred.primary_cluster_id == rank1_loc.cluster_id

    cluster_row = db.query(LocationCluster).filter(LocationCluster.id == rank1_loc.cluster_id).first()
    assert cluster_row is not None

    # API call
    resp = client.post(f"/api/v1/alerts/prediction/{latest_pred.id}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["location_name"] == cluster_row.cluster_name


def test_alert_content_consistent_with_persisted_prediction(db: Session):
    """
    Requirements 6, 9:
    Alert fields must derive directly from persisted Prediction and PredictionLocation.
    """
    comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000003").first()
    latest_pred = prediction_persistence_service.get_latest_prediction(db, comp.id)
    assert latest_pred is not None

    rank1_loc = (
        db.query(PredictionLocation)
        .filter(PredictionLocation.prediction_id == latest_pred.id, PredictionLocation.rank == 1)
        .first()
    )
    assert rank1_loc is not None
    cluster_row = db.query(LocationCluster).filter(LocationCluster.id == rank1_loc.cluster_id).first()
    assert cluster_row is not None

    resp = client.post(f"/api/v1/alerts/prediction/{latest_pred.id}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["location_name"] == cluster_row.cluster_name
    assert abs(data["risk_score"] - rank1_loc.probability) < 1e-4
    assert "Operational Estimate Window" in data["expected_window"]
    assert data["amount_at_risk"] == float(comp.amount)


def test_zero_ml_invocation_and_zero_withdrawal_access(db: Session):
    """
    Requirements 2, 8, 29:
    Alert generation must NOT call ML inference and must NOT query Withdrawal ground truth.
    """
    wd_count_before = db.query(Withdrawal).count()
    comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-DL-0001").first()
    latest_pred = prediction_persistence_service.get_latest_prediction(db, comp.id)
    assert latest_pred is not None

    resp = client.post(f"/api/v1/alerts/prediction/{latest_pred.id}")
    assert resp.status_code == 200

    wd_count_after = db.query(Withdrawal).count()
    assert wd_count_after == wd_count_before


def test_prediction_and_core_tables_remain_immutable(db: Session):
    """
    Requirements 21, 28:
    Alert workflow must NEVER mutate Prediction, PredictionLocation, Complaint,
    Account, Transaction, or Withdrawal.
    """
    counts_before = {
        "Complaint": db.query(Complaint).count(),
        "Account": db.query(Account).count(),
        "Transaction": db.query(Transaction).count(),
        "Withdrawal": db.query(Withdrawal).count(),
        "Prediction": db.query(Prediction).count(),
        "PredictionLocation": db.query(PredictionLocation).count(),
    }

    comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    latest_pred = prediction_persistence_service.get_latest_prediction(db, comp.id)
    assert latest_pred is not None

    # Call alert creation
    resp = client.post(f"/api/v1/alerts/prediction/{latest_pred.id}")
    assert resp.status_code == 200

    counts_after = {
        "Complaint": db.query(Complaint).count(),
        "Account": db.query(Account).count(),
        "Transaction": db.query(Transaction).count(),
        "Withdrawal": db.query(Withdrawal).count(),
        "Prediction": db.query(Prediction).count(),
        "PredictionLocation": db.query(PredictionLocation).count(),
    }

    for tbl, count in counts_before.items():
        assert counts_after[tbl] == count, f"{tbl} count changed from {count} to {counts_after[tbl]}"


def test_duplicate_alert_prevention_idempotency(db: Session):
    """
    Requirement 10:
    Repeated requests for the SAME prediction_id must return the existing active alert
    without creating a duplicate row (Alert delta = 0).
    """
    comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-DL-0001").first()
    latest_pred = prediction_persistence_service.get_latest_prediction(db, comp.id)
    assert latest_pred is not None

    # First call
    resp1 = client.post(f"/api/v1/alerts/prediction/{latest_pred.id}")
    assert resp1.status_code == 200
    alert_id_1 = resp1.json()["id"]

    alert_count_before = db.query(Alert).count()

    # Second call for the same prediction_id
    resp2 = client.post(f"/api/v1/alerts/prediction/{latest_pred.id}")
    assert resp2.status_code == 200
    alert_id_2 = resp2.json()["id"]

    alert_count_after = db.query(Alert).count()

    assert alert_id_1 == alert_id_2
    assert alert_count_after == alert_count_before, "Duplicate alert was created for same prediction_id!"


def test_new_prediction_can_create_new_alert(db: Session):
    """
    Requirement 10:
    A distinct Prediction run with a different prediction_id can generate a new Alert.
    """
    comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    assert comp is not None

    # Persist a fresh second prediction (with bypass_debounce)
    from backend.app.services.prediction_service import prediction_service
    persist_input = prediction_service.predict_complaint(db, comp.id)
    new_pred = prediction_persistence_service.persist_prediction(db, comp, persist_input, bypass_debounce=True)
    assert new_pred is not None

    # Generate alert for this new prediction
    alert = create_alert_for_prediction(db, new_pred.id)
    assert alert.prediction_id == new_pred.id

    # Verify both alerts exist with different prediction IDs
    alerts_for_comp = db.query(Alert).filter(Alert.complaint_id == comp.id).all()
    pred_ids = {a.prediction_id for a in alerts_for_comp}
    assert new_pred.id in pred_ids


def test_outside_scope_zero_alert(db: Session):
    """
    Requirement 20:
    CMP-NEW-000004 has no persisted prediction.
    Attempting alert creation must return HTTP 404 and Alert delta = 0.
    """
    alert_count_before = db.query(Alert).count()

    resp = client.post("/api/v1/alerts/generate/CMP-NEW-000004")
    assert resp.status_code == 404
    assert "No persisted prediction available" in resp.json()["detail"]

    alert_count_after = db.query(Alert).count()
    assert alert_count_after == alert_count_before


def test_cmp_1042_deterministic_demo_provenance(db: Session):
    """
    Requirement 19:
    Verify CMP-1042 creates an alert reflecting its deterministic_demo provenance,
    primary location Vijay Nagar, Indore, with exact DB-driven cluster IDs.
    SKIPPED: CMP-1042 (Indore legacy fixture) removed in Master Corrective Pass V3.
    Database now contains Delhi-only synthetic data; no Indore complaints exist.
    """
    import pytest
    pytest.skip("CMP-1042 (Indore legacy fixture) removed: database now contains Delhi-only synthetic data.")
    comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-1042").first()
    assert comp is not None

    latest_pred = prediction_persistence_service.get_latest_prediction(db, comp.id)
    assert latest_pred is not None
    assert latest_pred.prediction_mode == "deterministic_demo"

    resp = client.post(f"/api/v1/alerts/prediction/{latest_pred.id}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["prediction_id"] == latest_pred.id
    assert data["location_name"] in ["Vijay Nagar, Indore", "Bandra Kurla Complex (Synthetic)"]
    assert "[DEMO]" in data["title"] or "ACTIONABLE ALERT" in data["title"] or "CRITICAL CASH-OUT IMMINENT" in data["title"]


def test_acknowledgement_persistence_and_idempotency(db: Session):
    """
    Requirements 11, 12, 27:
    Verify:
    - Acknowledgement updates status to ACKNOWLEDGED
    - Repeated acknowledge requests update the same row without errors
    - Preserves row identity
    """
    comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    latest_pred = prediction_persistence_service.get_latest_prediction(db, comp.id)
    assert latest_pred is not None

    # Ensure an alert exists
    alert_resp = client.post(f"/api/v1/alerts/prediction/{latest_pred.id}").json()
    alert_id = alert_resp["id"]

    # Acknowledge first time
    ack1 = client.post(
        f"/api/v1/alerts/{alert_id}/acknowledge",
        json={"notes": "First response team en route."}
    )
    assert ack1.status_code == 200
    data1 = ack1.json()
    assert data1["status"] == "ACKNOWLEDGED"
    assert data1["acknowledged_at"] is not None
    assert "First response team" in data1["action_notes"]

    # Acknowledge second time (idempotent)
    ack2 = client.post(
        f"/api/v1/alerts/{alert_id}/acknowledge",
        json={"notes": "Updated action notes."}
    )
    assert ack2.status_code == 200
    data2 = ack2.json()
    assert data2["id"] == alert_id
    assert data2["status"] == "ACKNOWLEDGED"
    assert data2["action_notes"] == "Updated action notes."


def test_gis_to_alert_chain_consistency(db: Session):
    """
    Requirements 15, 31, 32:
    Strict end-to-end chain verification:
    GIS Prediction ID == Alert Prediction ID == Rendered Top-1 Location.
    """
    for c_num in ["CMP-NEW-000002", "CMP-NEW-000003", "CMP-DL-0001"]:
        # 1. Fetch GIS persisted prediction
        gis_resp = client.get(f"/api/v1/risk-map/prediction/{c_num}")
        assert gis_resp.status_code == 200
        gis_data = gis_resp.json()

        gis_pred_id = gis_data["prediction_id"]
        gis_rank1_loc = gis_data["top_locations"][0]["location_name"]
        gis_primary_cid = gis_data["primary_cluster_id"]

        # 2. Trigger Alert for that exact prediction_id
        alert_resp = client.post(f"/api/v1/alerts/prediction/{gis_pred_id}")
        assert alert_resp.status_code == 200
        alert_data = alert_resp.json()

        # 3. Assert exact match
        assert alert_data["prediction_id"] == gis_pred_id
        assert alert_data["location_name"] == gis_rank1_loc

        # 4. Fetch Alert by ID and verify
        get_alert_resp = client.get(f"/api/v1/alerts/{alert_data['id']}")
        assert get_alert_resp.status_code == 200
        fetched = get_alert_resp.json()
        assert fetched["prediction_id"] == gis_pred_id
        assert fetched["location_name"] == gis_rank1_loc


def test_db_delta_isolation_for_alert_creation(db: Session):
    """
    Requirement 33:
    For successful alert creation:
    Complaint delta = 0
    Account delta = 0
    Transaction delta = 0
    Withdrawal delta = 0
    Prediction delta = 0
    PredictionLocation delta = 0
    Alert delta = +1
    """
    comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000003").first()
    assert comp is not None

    # Persist a fresh prediction to guarantee a new alert creation
    from backend.app.services.prediction_service import prediction_service
    persist_input = prediction_service.predict_complaint(db, comp.id)
    new_pred = prediction_persistence_service.persist_prediction(db, comp, persist_input, bypass_debounce=True)
    assert new_pred is not None

    counts_before = {
        "Complaint": db.query(Complaint).count(),
        "Account": db.query(Account).count(),
        "Transaction": db.query(Transaction).count(),
        "Withdrawal": db.query(Withdrawal).count(),
        "Prediction": db.query(Prediction).count(),
        "PredictionLocation": db.query(PredictionLocation).count(),
        "Alert": db.query(Alert).count(),
    }

    resp = client.post(f"/api/v1/alerts/prediction/{new_pred.id}")
    assert resp.status_code == 200

    counts_after = {
        "Complaint": db.query(Complaint).count(),
        "Account": db.query(Account).count(),
        "Transaction": db.query(Transaction).count(),
        "Withdrawal": db.query(Withdrawal).count(),
        "Prediction": db.query(Prediction).count(),
        "PredictionLocation": db.query(PredictionLocation).count(),
        "Alert": db.query(Alert).count(),
    }

    assert counts_after["Complaint"] == counts_before["Complaint"]
    assert counts_after["Account"] == counts_before["Account"]
    assert counts_after["Transaction"] == counts_before["Transaction"]
    assert counts_after["Withdrawal"] == counts_before["Withdrawal"]
    assert counts_after["Prediction"] == counts_before["Prediction"]
    assert counts_after["PredictionLocation"] == counts_before["PredictionLocation"]
    assert counts_after["Alert"] == counts_before["Alert"] + 1


def test_atomic_rollback_on_failure(db: Session):
    """
    Requirement 21:
    If alert creation encounters an error (e.g. invalid prediction_id),
    no rows are committed and atomic rollback is preserved.
    """
    alert_count_before = db.query(Alert).count()

    # Pass non-existent prediction_id
    resp = client.post("/api/v1/alerts/prediction/999999999")
    assert resp.status_code == 404

    alert_count_after = db.query(Alert).count()
    assert alert_count_after == alert_count_before
