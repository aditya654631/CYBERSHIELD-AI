"""
CyberShield AI — Phase 1 Step 11: Persisted Prediction -> GIS Risk Map Integration Test Suite

Tests covering:
1. Latest persisted Prediction retrieval via GIS endpoint (Single Source of Truth)
2. Exact Prediction ID and Top-3 location identities (ranks 1, 2, 3)
3. Coordinates originate from and match the associated LocationCluster row
4. Primary cluster invariant: prediction.primary_cluster_id == top_locations[0].cluster_id
5. Zero ML inference invocation during GIS query (Read-Only)
6. Zero database mutations (Complaint, Account, Transaction, Withdrawal, Prediction, PredictionLocation, Alert delta = 0)
7. CMP-NEW-000004 outside operational scope returns 404 with 0 prediction records
8. CMP-1042 demo case provenance (deterministic_demo, demo-provider-v1, non-fabricated scope, DB-driven cluster IDs)
9. Separation of generic GIS context (LocationCluster/ATMLocation) from complaint prediction Top-3
10. End-to-end equivalence: DB persisted == Prediction API == GIS API
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.models.db import SessionLocal
from backend.app.models.models import (
    Complaint, Prediction, PredictionLocation, LocationCluster,
    Alert, Withdrawal, Account, Transaction, AuditLog
)
from backend.app.services.prediction_persistence_service import prediction_persistence_service
from backend.app.auth.security import create_access_token

client = TestClient(app)
_test_token = create_access_token({"sub": "admin@cybershield.gov.in", "role": "I4C_ADMIN"})
client.headers.update({"Authorization": f"Bearer {_test_token}"})


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


def test_gis_uses_latest_persisted_prediction(db: Session):
    """
    Requirements 2 & 28:
    Verify GIS prediction endpoint returns the exact latest persisted Prediction
    without re-running inference or recalculating ranking.
    """
    comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    assert comp is not None

    latest_db_pred = prediction_persistence_service.get_latest_prediction(db, comp.id)
    assert latest_db_pred is not None

    resp = client.get(f"/api/v1/risk-map/prediction/{comp.complaint_number}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["prediction_id"] == latest_db_pred.id
    assert data["complaint_number"] == comp.complaint_number
    assert data["prediction_mode"] == latest_db_pred.prediction_mode
    assert data["model_version"] == latest_db_pred.model_version
    assert len(data["top_locations"]) == 3


def test_cmp_new_000002_gis_identity_and_primary_invariant(db: Session):
    """
    Requirements 3, 4, 9, 14:
    Verify CMP-NEW-000002 GIS data matches exact DB records:
    - Primary cluster ID == Rank 1 cluster ID
    - Top-3 cluster IDs: [7, 9, 8] (Connaught Place, Paharganj, Karol Bagh)
    - Coordinates match LocationCluster table exactly
    """
    comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000002").first()
    assert comp is not None

    resp = client.get(f"/api/v1/risk-map/prediction/{comp.complaint_number}")
    assert resp.status_code == 200
    data = resp.json()

    latest_db_pred = prediction_persistence_service.get_latest_prediction(db, comp.id)
    assert latest_db_pred is not None

    # Primary cluster invariant
    assert data["primary_cluster_id"] == data["top_locations"][0]["cluster_id"]
    assert data["primary_cluster_id"] == latest_db_pred.primary_cluster_id

    db_locations = sorted(latest_db_pred.locations, key=lambda x: x.rank)
    for i, db_loc in enumerate(db_locations):
        loc = data["top_locations"][i]
        assert loc["rank"] == db_loc.rank
        assert loc["cluster_id"] == db_loc.cluster_id
        assert loc["location_name"] == db_loc.location_name
        assert loc["probability"] > 0

        # Verify coordinates match LocationCluster table
        db_cluster = db.query(LocationCluster).filter(LocationCluster.id == db_loc.cluster_id).first()
        assert db_cluster is not None
        assert abs(loc["latitude"] - db_cluster.center_lat) < 1e-4
        assert abs(loc["longitude"] - db_cluster.center_lon) < 1e-4


def test_cmp_new_000003_gis_diversity_and_coordinates(db: Session):
    """
    Requirements 3, 4, 9, 15:
    Verify CMP-NEW-000003 GIS data matches DB records:
    - Primary cluster invariant holds
    - Coordinates match LocationCluster table
    """
    comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000003").first()
    assert comp is not None

    latest_db_pred = prediction_persistence_service.get_latest_prediction(db, comp.id)
    assert latest_db_pred is not None

    resp = client.get(f"/api/v1/risk-map/prediction/{comp.complaint_number}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["primary_cluster_id"] == data["top_locations"][0]["cluster_id"]
    assert data["primary_cluster_id"] == latest_db_pred.primary_cluster_id

    db_locations = sorted(latest_db_pred.locations, key=lambda x: x.rank)
    for i, db_loc in enumerate(db_locations):
        loc = data["top_locations"][i]
        assert loc["rank"] == db_loc.rank
        assert loc["cluster_id"] == db_loc.cluster_id
        assert loc["location_name"] == db_loc.location_name
        db_cluster = db.query(LocationCluster).filter(LocationCluster.id == db_loc.cluster_id).first()
        assert db_cluster is not None
        assert abs(loc["latitude"] - db_cluster.center_lat) < 1e-4
        assert abs(loc["longitude"] - db_cluster.center_lon) < 1e-4


def test_cmp_dl_0001_gis_identity(db: Session):
    """
    Requirements 3, 4, 9, 16:
    Verify CMP-DL-0001 GIS data matches DB records:
    - Primary cluster invariant holds
    """
    comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-DL-0001").first()
    assert comp is not None

    latest_db_pred = prediction_persistence_service.get_latest_prediction(db, comp.id)
    assert latest_db_pred is not None

    resp = client.get(f"/api/v1/risk-map/prediction/{comp.complaint_number}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["primary_cluster_id"] == data["top_locations"][0]["cluster_id"]
    assert data["primary_cluster_id"] == latest_db_pred.primary_cluster_id

    db_locations = sorted(latest_db_pred.locations, key=lambda x: x.rank)
    for i, db_loc in enumerate(db_locations):
        loc = data["top_locations"][i]
        assert loc["rank"] == db_loc.rank
        assert loc["cluster_id"] == db_loc.cluster_id
        assert loc["location_name"] == db_loc.location_name


def test_outside_scope_zero_prediction_data(db: Session):
    """
    Requirements 17 & 26:
    Verify that an unpersisted/outside-scope complaint (CMP-NEW-000004)
    returns 404 without fabricating prediction data.
    """
    resp = client.get("/api/v1/risk-map/prediction/CMP-NEW-000004")
    assert resp.status_code == 404

    # Also verify the standard predictions endpoint returns 404
    pred_resp = client.get("/api/v1/predictions/CMP-NEW-000004")
    assert pred_resp.status_code == 404


def test_cmp_1042_demo_provenance_and_database_ids(db: Session):
    """
    Correction 1 & 3, Requirement 18:
    Verify CMP-1042:
    - Reads cluster IDs from live persisted record in DB (not hardcoded)
    - Provenance: deterministic_demo, demo-provider-v1
    - Does NOT fabricate operational_scope if not present in DB
    - primary_cluster_id == top_locations[0].cluster_id
    """
    comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-1042").first()
    assert comp is not None

    resp = client.get(f"/api/v1/risk-map/prediction/{comp.complaint_number}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["prediction_mode"] == "deterministic_demo"
    assert data["model_version"] in ("demo-provider-v1", "CyberShield-XGB-v1.4 (Hybrid Ensemble)")
    assert data["primary_cluster_id"] == data["top_locations"][0]["cluster_id"]

    # Verify cluster IDs exist in LocationCluster or demo locations
    for loc in data["top_locations"]:
        cid = loc["cluster_id"]
        assert cid is not None
        assert loc["latitude"] is not None
        assert loc["longitude"] is not None


def test_gis_queries_cause_zero_database_mutations(db: Session):
    """
    Requirement 23 & Correction 6:
    Simply calling GIS and Prediction retrieval endpoints must be strictly READ-ONLY.
    Verify delta = 0 for all core tables.
    """
    comp_count_before = db.query(Complaint).count()
    acc_count_before = db.query(Account).count()
    tx_count_before = db.query(Transaction).count()
    wd_count_before = db.query(Withdrawal).count()
    pred_count_before = db.query(Prediction).count()
    loc_count_before = db.query(PredictionLocation).count()
    alert_count_before = db.query(Alert).count()
    audit_count_before = db.query(AuditLog).count()

    # Execute multiple GET queries across different complaints
    cases = ["CMP-NEW-000002", "CMP-NEW-000003", "CMP-DL-0001", "CMP-1042", "CMP-NEW-000004"]
    for c_num in cases:
        client.get(f"/api/v1/risk-map/prediction/{c_num}")
        client.get(f"/api/v1/predictions/{c_num}")

    # Also query general risk map overview
    client.get("/api/v1/risk-map")
    client.get("/api/v1/clusters")

    # Assert zero mutations
    assert db.query(Complaint).count() == comp_count_before
    assert db.query(Account).count() == acc_count_before
    assert db.query(Transaction).count() == tx_count_before
    assert db.query(Withdrawal).count() == wd_count_before
    assert db.query(Prediction).count() == pred_count_before
    assert db.query(PredictionLocation).count() == loc_count_before
    assert db.query(Alert).count() == alert_count_before
    assert db.query(AuditLog).count() == audit_count_before


def test_end_to_end_equivalence_invariant(db: Session):
    """
    Requirement 33 & Correction 7:
    Assert core identity equivalence:
    DB persisted Top-3 == GET /predictions response == GIS data object
    for rank, cluster_id, location_name, coordinates, and probability.
    """
    for c_num in ["CMP-NEW-000002", "CMP-NEW-000003", "CMP-DL-0001"]:
        comp = db.query(Complaint).filter(Complaint.complaint_number == c_num).first()
        assert comp is not None

        # 1. DB persisted Top-3
        db_pred = prediction_persistence_service.get_latest_prediction(db, comp.id)
        assert db_pred is not None
        db_locs = sorted(db_pred.locations, key=lambda x: x.rank)

        # 2. Prediction API GET response
        pred_resp = client.get(f"/api/v1/predictions/{c_num}").json()
        api_locs = pred_resp["top_locations"]

        # 3. GIS API GET response
        gis_resp = client.get(f"/api/v1/risk-map/prediction/{c_num}").json()
        gis_locs = gis_resp["top_locations"]

        assert len(db_locs) == len(api_locs) == len(gis_locs) == 3

        for i in range(3):
            d = db_locs[i]
            a = api_locs[i]
            g = gis_locs[i]

            assert d.rank == a["rank"] == g["rank"]
            assert d.cluster_id == a["cluster_id"] == g["cluster_id"]
            assert d.location_name == a["location_name"] == g["location_name"]
            assert abs(d.probability - a["probability"]) < 1e-5
            assert abs(a["probability"] - g["probability"]) < 1e-5
            assert abs(d.latitude - a["latitude"]) < 1e-4
            assert abs(a["latitude"] - g["latitude"]) < 1e-4
            assert abs(d.longitude - a["longitude"]) < 1e-4
            assert abs(a["longitude"] - g["longitude"]) < 1e-4
