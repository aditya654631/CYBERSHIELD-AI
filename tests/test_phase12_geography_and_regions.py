"""
CyberShield AI — Phase 12 Comprehensive Test Suite
Tests Geography Catalog, Explicit Region Support, Zero Cross-Region Leakage,
Prediction Refusal on Unvalidated Regions, and Strict Parity for Delhi.
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.auth.security import create_access_token
from backend.app.models import models
from backend.app.services.geography_catalog_service import (
    GeographyCatalogValidator,
    ensure_default_regions_and_catalogs,
    resolve_region_for_complaint,
    get_region_by_id,
)
from ml.evaluation.second_region_readiness import evaluate_region_readiness
from conftest import TestingSessionLocal


@pytest.fixture
def auth_headers(client):
    """Admin credentials for privileged operations."""
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@cybershield.gov.in", "password": "CyberAdmin@2026"}
    )
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def delhi_lea_headers(client):
    """Authenticated canonical Delhi State LEA identity for the RBAC contract."""
    # Login behavior is covered by the authentication suite.  This geography
    # authorization test uses a token so it cannot depend on password-hash
    # mutations made by unrelated tests sharing the session database.
    token = create_access_token({"sub": "state.lea@delhi.cyber.gov.in", "role": "STATE_LEA"})
    return {"Authorization": f"Bearer {token}"}


# =====================================================================
# 1. Geography Catalog & Region Endpoints
# =====================================================================

def test_geography_regions_list(client, auth_headers):
    """GET /api/v1/geography/regions returns both Delhi and Mumbai MMR."""
    res = client.get("/api/v1/geography/regions", headers=auth_headers)
    assert res.status_code == 200, res.text
    regions = res.json()
    assert len(regions) >= 2

    region_map = {r["id"]: r for r in regions}
    assert "delhi" in region_map
    assert "mumbai_mmr" in region_map

    # Check Delhi metadata
    delhi = region_map["delhi"]
    assert delhi["state"] == "Delhi"
    assert delhi["data_completeness_status"] == "COMPLETE"
    assert delhi["model_support_status"] == "MODEL_SUPPORTED"
    assert delhi["supported_model_version"] == "cashout-location-xgb-v8-debiased"
    assert delhi["is_synthetic"] is False
    assert delhi["total_clusters"] == 60
    assert delhi["total_atms"] in (120, 240)

    # Check Mumbai MMR metadata
    mmr = region_map["mumbai_mmr"]
    assert mmr["state"] == "Maharashtra"
    assert mmr["data_completeness_status"] in ("PARTIAL", "SYNTHETIC_FIXTURE_ONLY")
    assert mmr["model_support_status"] == "VALIDATION_PENDING"
    assert mmr["supported_model_version"] is None
    assert mmr["is_synthetic"] is True
    assert mmr["total_clusters"] == 6
    assert mmr["total_atms"] == 12


def test_geography_region_detail_and_clusters(client, auth_headers):
    """GET /api/v1/geography/regions/{id} and /clusters return valid regional payload."""
    res = client.get("/api/v1/geography/regions/mumbai_mmr", headers=auth_headers)
    assert res.status_code == 200, res.text
    detail = res.json()
    assert detail["id"] == "mumbai_mmr"
    assert 18.80 <= detail["bounds"]["min_lat"] <= 18.90
    assert detail["bounds"]["max_lat"] == 19.35

    clusters_res = client.get("/api/v1/geography/regions/mumbai_mmr/clusters", headers=auth_headers)
    assert clusters_res.status_code == 200, clusters_res.text
    clusters = clusters_res.json()
    assert len(clusters) == 6
    for c in clusters:
        assert c["state"] == "Maharashtra"
        assert c["region_id"] == "mumbai_mmr"
        # Within MMR bounds
        assert 18.80 <= c["latitude"] <= 19.35
        assert 72.75 <= c["longitude"] <= 73.15


# =====================================================================
# 2. Delhi Prediction Parity Preservation
# =====================================================================

def test_delhi_prediction_parity(client, auth_headers):
    """Delhi prediction produces valid top-3 locations using qualified model with zero regression."""
    res = client.post("/api/v1/predictions/CMP-NEW-000002", headers=auth_headers)
    assert res.status_code == 200, res.text
    pred = res.json()
    assert pred["complaint_number"] == "CMP-NEW-000002"
    assert pred["status"] in ("AVAILABLE", "SUCCESS")
    assert pred["prediction_mode"] == "trained_ml"
    assert pred["model_version"] == "cashout-location-xgb-v8-debiased"
    assert len(pred["top_locations"]) == 3
    assert pred["top_locations"][0]["rank"] == 1
    assert pred["top_locations"][0]["probability"] > 0.0
    # Location coordinates within Delhi bounding box
    lat = pred["top_locations"][0].get("latitude")
    lon = pred["top_locations"][0].get("longitude")
    assert 28.38 <= lat <= 28.92
    assert 76.80 <= lon <= 77.45


# =====================================================================
# 3. Second-Region Refusal and No Silent Delhi Fallback
# =====================================================================

def test_second_region_prediction_strict_refusal(client, auth_headers, db):
    """A complaint in Mumbai MMR returns MODEL_NOT_SUPPORTED_FOR_REGION with ZERO candidate locations and NO Delhi fallback."""
    # Register complaint in Mumbai MMR
    comp_data = {
        "victim_name": "Rohit Deshmukh",
        "fraud_type": "UPI Fraud",
        "amount": 65000.0,
        "state": "Maharashtra",
        "district": "MUMBAI",
        "locality": "Colaba Causeway",
        "victim_lat": 18.9155,
        "victim_lon": 72.8260,
        "payment_channel": "UPI",
        "beneficiary_id": "mule.mum@icici",
        "transaction_ref": "UTR-MUM-TEST-001",
        "region_id": "mumbai_mmr",
        "demo_mode": True,
    }
    create_res = client.post("/api/v1/complaints", json=comp_data, headers=auth_headers)
    assert create_res.status_code == 200, create_res.text
    created_comp = create_res.json()
    assert created_comp["region_id"] == "mumbai_mmr"
    assert created_comp["state"] == "Maharashtra"
    c_num = created_comp["complaint_number"]

    # Request prediction on unvalidated region
    pred_res = client.post(f"/api/v1/predictions/{c_num}", headers=auth_headers)
    assert pred_res.status_code == 200, pred_res.text
    pred = pred_res.json()

    # Verify strict refusal contracts
    assert pred["status"] == "MODEL_NOT_SUPPORTED_FOR_REGION"
    assert pred["prediction_mode"] == "unsupported_region"
    assert pred["model_version"] is None
    assert pred["confidence_score"] == 0.0
    assert pred["top_locations"] == [], "Must return empty top_locations, never fallback to Delhi clusters!"
    assert pred["time_prediction"] is None, "Must not fabricate time window for unvalidated region."
    assert "refusal_reason" in pred or "explanation" in pred
    refusal_text = pred.get("refusal_reason") or (pred.get("explanation") or {}).get("summary", "")
    assert "Mumbai MMR" in refusal_text or "MODEL_NOT_SUPPORTED" in refusal_text or "validation" in refusal_text.lower()


def test_unregistered_region_prediction_refusal(client, auth_headers, db):
    """A complaint in an unregistered region (e.g. Bhopal, MP) returns OUTSIDE_OPERATIONAL_SCOPE with ZERO candidate locations."""
    c4 = db.query(models.Complaint).filter_by(complaint_number="CMP-NEW-000004").first()
    assert c4 is not None
    assert c4.state == "Madhya Pradesh"

    pred_res = client.post(f"/api/v1/predictions/{c4.complaint_number}", headers=auth_headers)
    assert pred_res.status_code == 200, pred_res.text
    pred = pred_res.json()

    assert pred["status"] in ("OUTSIDE_OPERATIONAL_SCOPE", "UNSUPPORTED_REGION")
    assert pred["top_locations"] == []


# =====================================================================
# 4. GIS Cross-Region Isolation
# =====================================================================

def test_gis_cross_region_isolation(client, auth_headers):
    """GIS queries partitioned by region_id must have zero cross-region cluster leakage."""
    # Delhi Clusters
    delhi_res = client.get("/api/v1/clusters?region_id=delhi", headers=auth_headers)
    assert delhi_res.status_code == 200, delhi_res.text
    delhi_clusters = delhi_res.json()
    assert len(delhi_clusters) == 60
    for c in delhi_clusters:
        assert c["region_id"] == "delhi"
        assert c["state"].lower() == "delhi"
        assert 28.38 <= c["latitude"] <= 28.92
        assert 76.80 <= c["longitude"] <= 77.45

    # Mumbai Clusters
    mumbai_res = client.get("/api/v1/clusters?region_id=mumbai_mmr", headers=auth_headers)
    assert mumbai_res.status_code == 200, mumbai_res.text
    mumbai_clusters = mumbai_res.json()
    assert len(mumbai_clusters) == 6
    for c in mumbai_clusters:
        assert c["region_id"] == "mumbai_mmr"
        assert c["state"] == "Maharashtra"
        assert 18.80 <= c["latitude"] <= 19.35
        assert 72.75 <= c["longitude"] <= 73.15

    # Mutual exclusion check
    delhi_names = set(c["cluster_name"] for c in delhi_clusters)
    mumbai_names = set(c["cluster_name"] for c in mumbai_clusters)
    assert len(delhi_names.intersection(mumbai_names)) == 0, "No cluster name overlap permitted across regions!"

    # Risk Map Overview Isolation
    delhi_map = client.get("/api/v1/risk-map?region_id=delhi", headers=auth_headers).json()
    assert delhi_map["summary"]["region_id"] == "delhi"
    assert len(delhi_map["hotspots"]) == 60

    mumbai_map = client.get("/api/v1/risk-map?region_id=mumbai_mmr", headers=auth_headers).json()
    assert mumbai_map["summary"]["region_id"] == "mumbai_mmr"
    assert len(mumbai_map["hotspots"]) == 6


# =====================================================================
# 5. Geography Catalog Validator Robustness
# =====================================================================

def test_catalog_validator_out_of_bounds_rejection():
    """Validator rejects clusters placed outside the region bounds."""
    region_meta = {
        "id": "test_region",
        "name": "Test Region",
        "state": "TestState",
        "catalog_version": "test_v1.0",
        "source": "Open Data Test",
        "license": "ODbL 1.0",
        "bounds": {"min_lat": 10.0, "max_lat": 11.0, "min_lon": 70.0, "max_lon": 71.0},
        "model_support_status": "VALIDATION_PENDING"
    }
    clusters = [
        {
            "id": 1,
            "cluster_name": "Out of Bounds Cluster",
            "city": "TestCity",
            "district": "TestDistrict",
            "state": "TestState",
            "latitude": 28.61,  # In Delhi, not in 10-11 range!
            "longitude": 77.20,
        }
    ]
    report = GeographyCatalogValidator.validate_catalog_payload(region_meta, clusters, [])
    assert report["valid"] is False
    assert any("bounds" in err.lower() for err in report["errors"])


def test_catalog_validator_duplicate_rejection():
    """Validator rejects duplicate cluster IDs and duplicate ATM codes."""
    region_meta = {
        "id": "test_region",
        "name": "Test Region",
        "state": "TestState",
        "catalog_version": "test_v1.0",
        "source": "Open Data Test",
        "license": "ODbL 1.0",
        "bounds": {"min_lat": 10.0, "max_lat": 11.0, "min_lon": 70.0, "max_lon": 71.0},
        "model_support_status": "VALIDATION_PENDING"
    }
    clusters = [
        {"id": 1, "cluster_name": "Cluster A", "city": "C", "district": "D", "state": "TestState", "latitude": 10.5, "longitude": 70.5},
        {"id": 1, "cluster_name": "Cluster B", "city": "C", "district": "D", "state": "TestState", "latitude": 10.6, "longitude": 70.6},
    ]
    atms = [
        {"atm_code": "ATM-001", "bank_name": "B", "latitude": 10.5, "longitude": 70.5, "city": "C", "district": "D", "state": "TestState"},
        {"atm_code": "ATM-001", "bank_name": "B2", "latitude": 10.6, "longitude": 70.6, "city": "C", "district": "D", "state": "TestState"},
    ]
    report = GeographyCatalogValidator.validate_catalog_payload(region_meta, clusters, atms)
    assert report["valid"] is False
    assert any("duplicate cluster id" in err.lower() for err in report["errors"])
    assert any("duplicate atm code" in err.lower() for err in report["errors"])


def test_catalog_validator_unqualified_model_supported_rejection():
    """Validator rejects declaring MODEL_SUPPORTED without an approved qualified model version."""
    region_meta = {
        "id": "new_region",
        "name": "New Region",
        "state": "NewState",
        "catalog_version": "v1.0",
        "source": "Open Data",
        "license": "ODbL 1.0",
        "bounds": {"min_lat": 12.0, "max_lat": 13.0, "min_lon": 77.0, "max_lon": 78.0},
        "model_support_status": "MODEL_SUPPORTED",  # Invalid: cannot claim model support without approved promotion
        "supported_model_version": None,
    }
    report = GeographyCatalogValidator.validate_catalog_payload(region_meta, [], [])
    assert report["valid"] is False
    assert any("supported_model_version" in err.lower() or "cannot declare model_supported" in err.lower() for err in report["errors"])


# =====================================================================
# 6. RBAC Regional Scoping
# =====================================================================

def test_rbac_delhi_officer_cannot_view_mumbai_clusters(client, delhi_lea_headers):
    """A Delhi LEA officer querying Mumbai region clusters returns an empty list under RBAC jurisdiction filtering."""
    res = client.get("/api/v1/clusters?region_id=mumbai_mmr", headers=delhi_lea_headers)
    assert res.status_code == 200, res.text
    clusters = res.json()
    assert len(clusters) == 0, "Delhi LEA officer cannot receive clusters outside their state jurisdiction!"


# =====================================================================
# 7. Second-Region Readiness Gate Module
# =====================================================================

def test_second_region_readiness_module():
    """Evaluates readiness reports for Delhi, Mumbai MMR, and unregistered regions."""
    # Delhi must be approved
    delhi_report = evaluate_region_readiness("delhi")
    assert delhi_report["readiness_status"] == "READY_AND_SUPPORTED"
    assert delhi_report["overall_decision"] == "APPROVED_FOR_PRODUCTION_PREDICTIONS"
    assert delhi_report["gates"]["catalog_completeness"]["passed"] is True
    assert delhi_report["gates"]["regional_model_artifacts"]["passed"] is True

    # Mumbai MMR must report validation pending
    mmr_report = evaluate_region_readiness("mumbai_mmr")
    assert mmr_report["readiness_status"] == "VALIDATION_PENDING"
    assert mmr_report["overall_decision"] == "REFUSED_MODEL_PREDICTIONS_VALIDATION_PENDING"
    assert mmr_report["gates"]["ground_truth_dataset"]["passed"] is False
    assert mmr_report["gates"]["regional_model_artifacts"]["passed"] is False
    assert "MODEL_NOT_SUPPORTED_FOR_REGION" in mmr_report["refusal_reason"]

    # Unknown region
    unk_report = evaluate_region_readiness("chennai")
    assert unk_report["readiness_status"] == "UNREGISTERED_REGION"
    assert unk_report["overall_decision"] == "REFUSED_UNREGISTERED_REGION"
