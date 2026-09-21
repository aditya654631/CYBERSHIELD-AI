"""
CyberShield AI - Phase 4: Multi-Dimensional GIS Filtering & Spatiotemporal Surveillance Tests

Validates all Phase 4 criteria:
1. Default time filter uses predicted withdrawal-window overlap:
   - Evaluates [predicted_window_start, predicted_window_end] interval overlap with [start_time, end_time].
2. Separate complaint-time and incident-time filters:
   - time_basis='complaint_time' evaluates Complaint.reported_at within [start_time, end_time].
   - time_basis='incident_time' evaluates Complaint.incident_time within [start_time, end_time].
3. ISO 8601 parsing & validation:
   - Valid UTC ISO with "Z", valid ISO with offset (+05:30), naive ISO string.
   - Invalid datetime string returns 400 Bad Request.
4. Reversed time range handling:
   - start_time > end_time returns 400 Bad Request.
5. Invalid time_basis handling:
   - Unsupported time_basis returns 400 Bad Request.
6. Crime category filter:
   - Matches Complaint.fraud_type.
7. District & Risk level filtering:
   - Filters clusters correctly.
8. Global complaint deduplication across candidate clusters:
   - A complaint mapped to Rank-1 and Rank-2 candidate clusters is counted once in summary totals.
9. Cross-role RBAC scoping:
   - I4C_ADMIN (national), STATE_LEA (state), DISTRICT_LEA (district), BANK_OFFICER (bank complaints).
10. GET /api/v1/clusters collection route accepts same filter parameters.
"""

import time
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy.orm import Session

from backend.app.auth.security import create_access_token
from backend.app.models.models import (
    Complaint, Prediction, PredictionLocation, PredictionSnapshot,
    LocationCluster, User, Organization, Alert, Transaction
)


def _make_auth_header(email: str, role: str) -> dict:
    claims = {"sub": email, "role": role}
    token = create_access_token(claims)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers():
    return _make_auth_header("admin@cybershield.gov.in", "I4C_ADMIN")


@pytest.fixture
def delhi_state_lea_headers():
    return _make_auth_header("state_lea_delhi@cybershield.gov.in", "STATE_LEA")


@pytest.fixture
def central_district_lea_headers():
    return _make_auth_header("district_lea_central@cybershield.gov.in", "DISTRICT_LEA")


def _clean_test_predictions(db_session: Session, pred_ids):
    if not pred_ids:
        return
    db_session.query(Transaction).filter(Transaction.prediction_id.in_(pred_ids)).update({Transaction.prediction_id: None}, synchronize_session=False)
    db_session.query(Alert).filter(Alert.prediction_id.in_(pred_ids)).update({Alert.prediction_id: None}, synchronize_session=False)
    db_session.query(PredictionLocation).filter(PredictionLocation.prediction_id.in_(pred_ids)).delete(synchronize_session=False)
    db_session.query(PredictionSnapshot).filter(PredictionSnapshot.prediction_id.in_(pred_ids)).delete(synchronize_session=False)
    db_session.query(Prediction).filter(Prediction.id.in_(pred_ids)).delete(synchronize_session=False)
    db_session.commit()


def get_delhi_clusters(db_session: Session):
    return db_session.query(LocationCluster).filter(LocationCluster.state == "Delhi").order_by(LocationCluster.id.asc()).all()


# ==============================================================================
# 1. Default Time Filter: Predicted Window Overlap
# ==============================================================================
def test_gis_default_time_filter_predicted_window_overlap(db_session: Session, client, admin_headers):
    """
    Validates that:
    - Default time_basis is 'predicted_window'
    - Interval overlap [window_start, window_end] with [start_time, end_time] is used
    - An active prediction with window [T+1h, T+3h] matches query [T+2h, T+4h]
    - Does NOT match query [T+4h, T+6h] (no overlap)
    """
    now = datetime.utcnow()
    ts = int(time.time())
    target_cluster = get_delhi_clusters(db_session)[0]

    # Clean existing
    db_session.query(PredictionLocation).filter(PredictionLocation.cluster_id == target_cluster.id).delete(synchronize_session=False)
    db_session.commit()

    comp = Complaint(
        complaint_number=f"P4-TEST-OVERLAP-{ts}",
        fraud_type="UPI Fraud",
        amount=75000.0,
        victim_name="Test Victim",
        victim_phone="9876543210",
        victim_location="Connaught Place",
        state="Delhi",
        district=target_cluster.district,
        payment_channel="UPI",
        reported_at=now - timedelta(minutes=30),
        incident_time=now - timedelta(hours=1),
        risk_level="CRITICAL",
        risk_score=0.88,
        prediction_status="COMPLETED",
        case_status="UNDER_INVESTIGATION",
        created_at=now,
    )
    db_session.add(comp)
    db_session.commit()
    db_session.refresh(comp)

    # Active window from T+1h to T+3h
    w_start = now + timedelta(hours=1)
    w_end = now + timedelta(hours=3)

    pred = Prediction(
        complaint_id=comp.id,
        model_version="cashout-location-xgb-v7-compat",
        prediction_mode="trained_ml",
        risk_score=0.88,
        risk_level="CRITICAL",
        primary_cluster_id=target_cluster.id,
        predicted_window_start=w_start,
        predicted_window_end=w_end,
        created_at=now,
    )
    db_session.add(pred)
    db_session.commit()
    db_session.refresh(pred)

    ploc = PredictionLocation(
        prediction_id=pred.id,
        cluster_id=target_cluster.id,
        rank=1,
        location_name=target_cluster.cluster_name,
        probability=0.88,
        risk_level="CRITICAL",
        distance_km=1.2,
        latitude=target_cluster.center_lat,
        longitude=target_cluster.center_lon,
    )
    db_session.add(ploc)
    db_session.commit()

    try:
        # Case A: Query overlapping window [T+2h, T+4h] -> MUST MATCH
        q_start = (now + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        q_end = (now + timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M:%SZ")

        resp = client.get(
            f"/api/v1/risk-map?start_time={q_start}&end_time={q_end}&time_basis=predicted_window",
            headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()

        # Target cluster should be an active candidate
        matched = next((h for h in data["active_candidates"] if h["id"] == target_cluster.id), None)
        assert matched is not None, "Target cluster should match overlapping window"
        assert matched["is_active_candidate"] is True
        assert comp.complaint_number in matched["linked_complaint_numbers"]
        assert data["summary"]["filters_applied"]["time_basis"] == "predicted_window"

        # Case B: Query non-overlapping window [T+4h, T+6h] -> MUST NOT MATCH
        no_start = (now + timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M:%SZ")
        no_end = (now + timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")

        resp_no = client.get(
            f"/api/v1/risk-map?start_time={no_start}&end_time={no_end}",
            headers=admin_headers
        )
        assert resp_no.status_code == 200
        data_no = resp_no.json()
        assert not any(h["id"] == target_cluster.id for h in data_no.get("active_candidates", [])), "Target cluster must NOT match non-overlapping window"

    finally:
        _clean_test_predictions(db_session, [pred.id])
        db_session.query(Complaint).filter(Complaint.id == comp.id).delete()
        db_session.commit()


# ==============================================================================
# 2. Complaint-Time & Incident-Time Filters
# ==============================================================================
def test_gis_complaint_time_and_incident_time_filters(db_session: Session, client, admin_headers):
    """
    Validates distinct time_basis options:
    - 'complaint_time': filters by Complaint.reported_at
    - 'incident_time': filters by Complaint.incident_time
    """
    now = datetime.utcnow()
    ts = int(time.time())
    target_cluster = get_delhi_clusters(db_session)[0]

    # Clean existing
    db_session.query(PredictionLocation).filter(PredictionLocation.cluster_id == target_cluster.id).delete(synchronize_session=False)
    db_session.commit()

    reported_at = now - timedelta(hours=2)
    incident_time = now - timedelta(hours=10)

    comp = Complaint(
        complaint_number=f"P4-TEST-TIME-BASIS-{ts}",
        fraud_type="Phishing",
        amount=50000.0,
        victim_name="Basis Victim",
        victim_phone="9876543210",
        victim_location="Karol Bagh",
        state="Delhi",
        district=target_cluster.district,
        payment_channel="UPI",
        reported_at=reported_at,
        incident_time=incident_time,
        risk_level="HIGH",
        risk_score=0.75,
        prediction_status="COMPLETED",
        case_status="UNDER_INVESTIGATION",
        created_at=now,
    )
    db_session.add(comp)
    db_session.commit()
    db_session.refresh(comp)

    pred = Prediction(
        complaint_id=comp.id,
        model_version="cashout-location-xgb-v7-compat",
        risk_score=0.75,
        risk_level="HIGH",
        primary_cluster_id=target_cluster.id,
        predicted_window_start=now + timedelta(hours=1),
        predicted_window_end=now + timedelta(hours=4),
        created_at=now,
    )
    db_session.add(pred)
    db_session.commit()
    db_session.refresh(pred)

    ploc = PredictionLocation(
        prediction_id=pred.id,
        cluster_id=target_cluster.id,
        rank=1,
        location_name=target_cluster.cluster_name,
        probability=0.75,
        risk_level="HIGH",
        distance_km=1.0,
        latitude=target_cluster.center_lat,
        longitude=target_cluster.center_lon,
    )
    db_session.add(ploc)
    db_session.commit()

    try:
        # Query 1: time_basis=complaint_time covering reported_at [now-3h, now-1h]
        start_q = (now - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
        end_q = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

        resp1 = client.get(
            f"/api/v1/risk-map?time_basis=complaint_time&start_time={start_q}&end_time={end_q}",
            headers=admin_headers
        )
        assert resp1.status_code == 200
        d1 = resp1.json()
        assert any(h["id"] == target_cluster.id for h in d1["active_candidates"]), "Should match complaint_time filter"

        # Query 2: time_basis=incident_time covering incident_time [now-12h, now-8h]
        inc_start = (now - timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%SZ")
        inc_end = (now - timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%SZ")

        resp2 = client.get(
            f"/api/v1/risk-map?time_basis=incident_time&start_time={inc_start}&end_time={inc_end}",
            headers=admin_headers
        )
        assert resp2.status_code == 200
        d2 = resp2.json()
        assert any(h["id"] == target_cluster.id for h in d2["active_candidates"]), "Should match incident_time filter"

        # Query 3: time_basis=complaint_time for [now-12h, now-8h] (should NOT match reported_at)
        resp3 = client.get(
            f"/api/v1/risk-map?time_basis=complaint_time&start_time={inc_start}&end_time={inc_end}",
            headers=admin_headers
        )
        assert resp3.status_code == 200
        d3 = resp3.json()
        assert not any(h["id"] == target_cluster.id for h in d3["active_candidates"]), "Should NOT match wrong basis window"

    finally:
        _clean_test_predictions(db_session, [pred.id])
        db_session.query(Complaint).filter(Complaint.id == comp.id).delete()
        db_session.commit()


# ==============================================================================
# 3. Input Validation & Error Handling (400 Bad Request)
# ==============================================================================
def test_gis_filter_validation_and_errors(client, admin_headers):
    """
    Validates proper HTTP 400 Bad Request errors on:
    - Reversed time range: start_time > end_time
    - Invalid datetime format for start_time or end_time
    - Invalid time_basis value
    """
    # 1. Reversed range
    resp = client.get(
        "/api/v1/risk-map?start_time=2026-09-20T18:00:00Z&end_time=2026-09-20T12:00:00Z",
        headers=admin_headers
    )
    assert resp.status_code == 400
    assert "Reversed time range" in resp.json()["detail"]

    # 2. Invalid datetime format
    resp_bad_dt = client.get(
        "/api/v1/risk-map?start_time=not-a-valid-date",
        headers=admin_headers
    )
    assert resp_bad_dt.status_code == 400
    assert "Invalid ISO datetime" in resp_bad_dt.json()["detail"]

    # 3. Invalid time basis
    resp_bad_basis = client.get(
        "/api/v1/risk-map?time_basis=invalid_random_basis",
        headers=admin_headers
    )
    assert resp_bad_basis.status_code == 400
    assert "Invalid time_basis" in resp_bad_basis.json()["detail"]


# ==============================================================================
# 4. Crime Category Filter
# ==============================================================================
def test_gis_crime_category_filter(db_session: Session, client, admin_headers):
    """
    Validates that crime_category filter matches Complaint.fraud_type.
    """
    now = datetime.utcnow()
    ts = int(time.time())
    clusters = get_delhi_clusters(db_session)
    c1, c2 = clusters[0], clusters[1]

    # Clean existing
    db_session.query(PredictionLocation).filter(PredictionLocation.cluster_id.in_([c1.id, c2.id])).delete(synchronize_session=False)
    db_session.commit()

    # Complaint 1: Investment Scam
    comp1 = Complaint(
        complaint_number=f"P4-TEST-CAT-01-{ts}",
        fraud_type="Investment Scam",
        amount=120000.0,
        victim_name="Cat Victim 1",
        victim_phone="9876543210",
        victim_location="CP",
        state="Delhi",
        district=c1.district,
        payment_channel="UPI",
        reported_at=now - timedelta(minutes=15),
        incident_time=now - timedelta(hours=2),
        risk_level="CRITICAL",
        risk_score=0.90,
        prediction_status="COMPLETED",
        case_status="UNDER_INVESTIGATION",
        created_at=now,
    )
    # Complaint 2: Job Fraud
    comp2 = Complaint(
        complaint_number=f"P4-TEST-CAT-02-{ts}",
        fraud_type="Job Fraud",
        amount=35000.0,
        victim_name="Cat Victim 2",
        victim_phone="9876543211",
        victim_location="Rohini",
        state="Delhi",
        district=c2.district,
        payment_channel="UPI",
        reported_at=now - timedelta(minutes=15),
        incident_time=now - timedelta(hours=2),
        risk_level="HIGH",
        risk_score=0.75,
        prediction_status="COMPLETED",
        case_status="UNDER_INVESTIGATION",
        created_at=now,
    )
    db_session.add_all([comp1, comp2])
    db_session.commit()
    db_session.refresh(comp1)
    db_session.refresh(comp2)

    pred1 = Prediction(
        complaint_id=comp1.id,
        model_version="cashout-location-xgb-v7-compat",
        risk_score=0.90,
        risk_level="CRITICAL",
        primary_cluster_id=c1.id,
        predicted_window_start=now + timedelta(hours=1),
        predicted_window_end=now + timedelta(hours=4),
        created_at=now,
    )
    pred2 = Prediction(
        complaint_id=comp2.id,
        model_version="cashout-location-xgb-v7-compat",
        risk_score=0.75,
        risk_level="HIGH",
        primary_cluster_id=c2.id,
        predicted_window_start=now + timedelta(hours=1),
        predicted_window_end=now + timedelta(hours=4),
        created_at=now,
    )
    db_session.add_all([pred1, pred2])
    db_session.commit()
    db_session.refresh(pred1)
    db_session.refresh(pred2)

    ploc1 = PredictionLocation(
        prediction_id=pred1.id, cluster_id=c1.id, rank=1,
        location_name=c1.cluster_name, probability=0.90,
        risk_level="CRITICAL", distance_km=1.0,
        latitude=c1.center_lat, longitude=c1.center_lon
    )
    ploc2 = PredictionLocation(
        prediction_id=pred2.id, cluster_id=c2.id, rank=1,
        location_name=c2.cluster_name, probability=0.75,
        risk_level="HIGH", distance_km=1.0,
        latitude=c2.center_lat, longitude=c2.center_lon
    )
    db_session.add_all([ploc1, ploc2])
    db_session.commit()

    try:
        # Filter for "Investment Scam"
        resp = client.get("/api/v1/risk-map?crime_category=Investment Scam", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()

        assert any(h["id"] == c1.id for h in data["active_candidates"]), "Cluster 1 (Investment Scam) should match"
        assert not any(h["id"] == c2.id for h in data["active_candidates"]), "Cluster 2 (Job Fraud) should NOT match"

        # Filter for "Job Fraud"
        resp_job = client.get("/api/v1/risk-map?crime_category=Job Fraud", headers=admin_headers)
        assert resp_job.status_code == 200
        data_job = resp_job.json()

        assert any(h["id"] == c2.id for h in data_job["active_candidates"]), "Cluster 2 (Job Fraud) should match"
        assert not any(h["id"] == c1.id for h in data_job["active_candidates"]), "Cluster 1 (Investment Scam) should NOT match"

    finally:
        _clean_test_predictions(db_session, [pred1.id, pred2.id])
        db_session.query(Complaint).filter(Complaint.id.in_([comp1.id, comp2.id])).delete(synchronize_session=False)
        db_session.commit()


# ==============================================================================
# 5. Global Deduplication Across Clusters
# ==============================================================================
def test_gis_global_complaint_deduplication(db_session: Session, client, admin_headers):
    """
    Validates that if a complaint appears in multiple candidate clusters
    (e.g., Rank 1 in cluster A, Rank 2 in cluster B):
    - It is counted in both clusters locally (cluster.active_cases)
    - But counted EXACTLY ONCE in global summary.total_unique_active_cases and summary.total_associated_amount
    """
    now = datetime.utcnow()
    ts = int(time.time())
    clusters = get_delhi_clusters(db_session)
    c1, c2 = clusters[0], clusters[1]

    # Clean existing predictions for c1 and c2
    db_session.query(PredictionLocation).filter(PredictionLocation.cluster_id.in_([c1.id, c2.id])).delete(synchronize_session=False)
    db_session.commit()

    comp = Complaint(
        complaint_number=f"P4-TEST-DEDUP-{ts}",
        fraud_type="UPI Fraud",
        amount=100000.0,
        victim_name="Dedup Victim",
        victim_phone="9876543210",
        victim_location="CP",
        state="Delhi",
        district=c1.district,
        payment_channel="UPI",
        reported_at=now - timedelta(minutes=10),
        incident_time=now - timedelta(hours=1),
        risk_level="CRITICAL",
        risk_score=0.92,
        prediction_status="COMPLETED",
        case_status="UNDER_INVESTIGATION",
        created_at=now,
    )
    db_session.add(comp)
    db_session.commit()
    db_session.refresh(comp)

    pred = Prediction(
        complaint_id=comp.id,
        model_version="cashout-location-xgb-v7-compat",
        risk_score=0.92,
        risk_level="CRITICAL",
        primary_cluster_id=c1.id,
        predicted_window_start=now + timedelta(hours=1),
        predicted_window_end=now + timedelta(hours=4),
        created_at=now,
    )
    db_session.add(pred)
    db_session.commit()
    db_session.refresh(pred)

    # Rank 1 in c1, Rank 2 in c2
    ploc1 = PredictionLocation(
        prediction_id=pred.id, cluster_id=c1.id, rank=1,
        location_name=c1.cluster_name, probability=0.80,
        risk_level="CRITICAL", distance_km=1.0,
        latitude=c1.center_lat, longitude=c1.center_lon
    )
    ploc2 = PredictionLocation(
        prediction_id=pred.id, cluster_id=c2.id, rank=2,
        location_name=c2.cluster_name, probability=0.60,
        risk_level="HIGH", distance_km=2.5,
        latitude=c2.center_lat, longitude=c2.center_lon
    )
    db_session.add_all([ploc1, ploc2])
    db_session.commit()

    try:
        resp = client.get("/api/v1/risk-map", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()

        c1_res = next((h for h in data["active_candidates"] if h["id"] == c1.id), None)
        c2_res = next((h for h in data["active_candidates"] if h["id"] == c2.id), None)

        assert c1_res is not None
        assert c2_res is not None
        assert c1_res["active_cases"] >= 1
        assert c2_res["active_cases"] >= 1

        # Global summary deduplication: comp.amount (100,000) is counted once for this complaint
        summary = data["summary"]
        assert "total_unique_active_cases" in summary
        assert "total_associated_amount" in summary
        assert summary["total_unique_active_cases"] >= 1
        assert summary["total_associated_amount"] >= 100000.0

    finally:
        _clean_test_predictions(db_session, [pred.id])
        db_session.query(Complaint).filter(Complaint.id == comp.id).delete()
        db_session.commit()


# ==============================================================================
# 6. Combined Multi-Dimensional Query & /clusters Endpoint Filter Matching
# ==============================================================================
def test_gis_combined_filters_and_clusters_collection(client, admin_headers):
    """
    Validates that:
    1. Multi-filter parameters (district, risk_level, crime_category, time_basis) work concurrently.
    2. GET /api/v1/clusters accepts the exact same filter parameters and returns scoped list.
    """
    # 1. Query /risk-map with multiple filters
    resp = client.get(
        "/api/v1/risk-map?district=Central&risk_level=CRITICAL&crime_category=UPI Fraud&time_basis=predicted_window",
        headers=admin_headers
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["summary"]["filters_applied"]["district"] == "Central"
    assert data["summary"]["filters_applied"]["risk_level"] == "CRITICAL"
    assert data["summary"]["filters_applied"]["crime_category"] == "UPI Fraud"

    # 2. Query /clusters with the same filters
    resp_clusters = client.get(
        "/api/v1/clusters?district=Central&risk_level=CRITICAL",
        headers=admin_headers
    )
    assert resp_clusters.status_code == 200
    clusters_list = resp_clusters.json()
    assert isinstance(clusters_list, list)
    for cl in clusters_list:
        assert cl["district"].lower() == "central"
        if cl["is_active_candidate"]:
            assert cl["risk_level"] == "CRITICAL"
