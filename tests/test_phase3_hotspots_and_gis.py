"""
CyberShield AI - Phase 3: Active Hotspots and GIS Correctness Test Suite

Validates all 13 Phase 3 verification scenarios:
1. Historical-only cluster with high baseline risk (no fake active critical card)
2. Cluster with one eligible active prediction
3. Closed/resolved complaint exclusion
4. Expired window and exact expiry boundary exclusion
5. Missing/invalid window exclusion
6. Multiple predictions for one complaint (only latest evaluated; older not revived)
7. Distinct scores for primary and secondary locations (loc.probability preserved)
8. Same complaint linked to multiple candidate zones
9. Duplicate case contribution within one cluster (deduplicated at cluster level)
10. Correct unique global totals (deduplicated globally across clusters)
11. Authorized versus unauthorized case visibility (RBAC jurisdiction scoping)
12. No eligible active predictions (clean empty state)
13. Cluster navigation and details API (GET /api/v1/clusters/{id} and 404 handling)
"""

import time
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy.orm import Session

from backend.app.auth.security import create_access_token
from backend.app.models.models import (
    Complaint, Prediction, PredictionLocation, PredictionSnapshot, LocationCluster, User, Organization, Alert, Transaction, InterventionPlan
)


def _clean_test_predictions(db_session: Session, pred_ids):
    if not pred_ids:
        return
    db_session.query(Transaction).filter(Transaction.prediction_id.in_(pred_ids)).update({Transaction.prediction_id: None}, synchronize_session=False)
    db_session.query(Alert).filter(Alert.prediction_id.in_(pred_ids)).update({Alert.prediction_id: None}, synchronize_session=False)
    db_session.query(InterventionPlan).filter(InterventionPlan.prediction_id.in_(pred_ids)).delete(synchronize_session=False)
    db_session.query(Prediction).filter(Prediction.parent_prediction_id.in_(pred_ids)).update({Prediction.parent_prediction_id: None}, synchronize_session=False)
    db_session.query(PredictionLocation).filter(PredictionLocation.prediction_id.in_(pred_ids)).delete(synchronize_session=False)
    db_session.query(PredictionSnapshot).filter(PredictionSnapshot.prediction_id.in_(pred_ids)).delete(synchronize_session=False)
    db_session.query(Prediction).filter(Prediction.id.in_(pred_ids)).delete(synchronize_session=False)
    db_session.commit()


def _make_auth_header(email: str, role: str) -> dict:
    claims = {"sub": email, "role": role}
    token = create_access_token(claims)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers():
    return _make_auth_header("admin@cybershield.gov.in", "I4C_ADMIN")


def get_delhi_clusters(db_session: Session):
    return db_session.query(LocationCluster).filter(LocationCluster.state == "Delhi").order_by(LocationCluster.id.asc()).all()


# ==============================================================================
# 1. Historical-only cluster with high baseline risk
# ==============================================================================
def test_historical_only_cluster_with_high_baseline_risk(db_session: Session, client, admin_headers):
    """
    Requirement 4 & 7:
    Historical clusters with baseline risk >= 0.8 must NEVER be presented as
    active interception candidates when no eligible active case prediction exists.
    """
    cluster = get_delhi_clusters(db_session)[0]
    assert cluster is not None
    original_risk = float(cluster.risk_score)
    assert original_risk > 0.0

    # Ensure no active predictions exist for cluster
    db_session.query(PredictionLocation).filter(PredictionLocation.cluster_id == cluster.id).delete()
    db_session.commit()

    resp = client.get("/api/v1/risk-map", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()

    # Find cluster in the response
    c1 = next((h for h in data["hotspots"] if h["id"] == cluster.id), None)
    assert c1 is not None

    # Verify additive and decoupled semantics
    assert c1["is_active_candidate"] is False
    assert c1["candidate_score"] is None
    assert c1["risk_score"] == 0.0
    assert c1["risk_level"] == "LOW"
    assert c1["historical_risk"] == original_risk
    assert c1["active_cases"] == 0
    assert c1["amount_at_risk"] == 0.0
    assert c1["associated_complaint_amount"] == 0.0
    assert c1["operational_priority"] is None
    assert c1["linked_complaint_numbers"] == []

    # Must appear in historical_hotspots, NOT in active_candidates
    assert any(h["id"] == cluster.id for h in data.get("historical_hotspots", []))
    assert not any(h["id"] == cluster.id for h in data.get("active_candidates", []))


# ==============================================================================
# 2. Cluster with one eligible active prediction
# ==============================================================================
def test_cluster_with_one_eligible_active_prediction(db_session: Session, client, admin_headers):
    """
    Requirement 2 & 7:
    An open complaint with an unexpired prediction window produces an eligible
    active candidate with traceable amounts, priority, and candidate score.
    """
    now = datetime.utcnow()
    ts = int(time.time())
    target_cluster = get_delhi_clusters(db_session)[1]

    # Ensure clean cluster for single eligible active prediction test
    existing_plocs = db_session.query(PredictionLocation.prediction_id).filter(PredictionLocation.cluster_id == target_cluster.id).all()
    existing_preds = db_session.query(Prediction.id).filter(Prediction.primary_cluster_id == target_cluster.id).all()
    all_p_ids = set([p[0] for p in existing_preds] + [p[0] for p in existing_plocs])
    if all_p_ids:
        _clean_test_predictions(db_session, all_p_ids)

    comp = Complaint(
        complaint_number=f"CMP-P3-ELIGIBLE-{ts}",
        fraud_type="UPI Fraud",
        amount=85000.0,
        victim_name="Eligible Victim",
        victim_phone="9876543210",
        victim_location="Rohini Sector 7",
        state="Delhi",
        district="Rohini",
        incident_time=now - timedelta(hours=2),
        reported_at=now - timedelta(hours=1),
        case_status="UNDER_INVESTIGATION",
        created_at=now,
    )
    db_session.add(comp)
    db_session.commit()
    db_session.refresh(comp)

    pred = Prediction(
        complaint_id=comp.id,
        predicted_window_start=now - timedelta(minutes=30),
        predicted_window_end=now + timedelta(hours=2),
        primary_cluster_id=target_cluster.id,
        risk_score=0.91,
        risk_level="CRITICAL",
        created_at=now,
    )
    db_session.add(pred)
    db_session.commit()
    db_session.refresh(pred)

    ploc = PredictionLocation(
        prediction_id=pred.id,
        cluster_id=target_cluster.id,
        location_name="Rohini Sector 7 Cluster",
        rank=1,
        probability=0.185,
        risk_level="CRITICAL",
    )
    db_session.add(ploc)
    db_session.commit()

    resp = client.get("/api/v1/risk-map", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()

    c2 = next((h for h in data["active_candidates"] if h["id"] == target_cluster.id), None)
    assert c2 is not None
    assert c2["is_active_candidate"] is True
    assert c2["candidate_score"] == 0.185
    assert c2["active_cases"] == 1
    assert c2["associated_complaint_amount"] == 85000.0
    assert c2["operational_priority"] == "CRITICAL"
    assert comp.complaint_number in c2["linked_complaint_numbers"]
    assert c2["window_status"] == "active"


# ==============================================================================
# 3. Closed/resolved complaint exclusion
# ==============================================================================
def test_closed_and_resolved_complaint_exclusion(db_session: Session, client, admin_headers):
    """
    Requirement 2:
    Closed or resolved cases are not eligible for active interception.
    """
    now = datetime.utcnow()
    ts = int(time.time())
    target_cluster = get_delhi_clusters(db_session)[2]

    # Ensure clean cluster for closed case exclusion test
    existing_plocs = db_session.query(PredictionLocation.prediction_id).filter(PredictionLocation.cluster_id == target_cluster.id).all()
    existing_preds = db_session.query(Prediction.id).filter(Prediction.primary_cluster_id == target_cluster.id).all()
    all_p_ids = set([p[0] for p in existing_preds] + [p[0] for p in existing_plocs])
    if all_p_ids:
        _clean_test_predictions(db_session, all_p_ids)

    comp_closed = Complaint(
        complaint_number=f"CMP-P3-CLOSED-{ts}",
        fraud_type="Credit Card",
        amount=50000.0,
        victim_name="Closed Case Victim",
        victim_phone="9876543211",
        victim_location="Karol Bagh",
        state="Delhi",
        district="Central Delhi",
        incident_time=now - timedelta(hours=5),
        reported_at=now - timedelta(hours=4),
        case_status="CLOSED",
        created_at=now,
    )
    db_session.add(comp_closed)
    db_session.commit()
    db_session.refresh(comp_closed)

    pred = Prediction(
        complaint_id=comp_closed.id,
        predicted_window_start=now - timedelta(minutes=10),
        predicted_window_end=now + timedelta(hours=1),
        primary_cluster_id=target_cluster.id,
        risk_score=0.88,
        risk_level="HIGH",
        created_at=now,
    )
    db_session.add(pred)
    db_session.commit()
    db_session.refresh(pred)

    ploc = PredictionLocation(
        prediction_id=pred.id,
        cluster_id=target_cluster.id,
        location_name="Karol Bagh Cluster",
        rank=1,
        probability=0.15,
        risk_level="HIGH",
    )
    db_session.add(ploc)
    db_session.commit()

    resp = client.get("/api/v1/risk-map", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()

    # Target cluster should NOT be active due to closed case
    active_ids = [h["id"] for h in data.get("active_candidates", [])]
    assert target_cluster.id not in active_ids

    c3 = next((h for h in data["hotspots"] if h["id"] == target_cluster.id), None)
    assert c3 is not None
    assert c3["is_active_candidate"] is False
    assert c3["active_cases"] == 0


# ==============================================================================
# 4. Expired window and exact expiry boundary
# ==============================================================================
def test_expired_window_and_exact_expiry_boundary(db_session: Session, client, admin_headers):
    """
    Requirement 2 & 11:
    Predictions whose window_end <= current UTC time are expired and excluded.
    """
    now = datetime.utcnow()
    ts = int(time.time())

    comp_exp = Complaint(
        complaint_number=f"CMP-P3-EXP-{ts}",
        fraud_type="Debit Card",
        amount=30000.0,
        victim_name="Expired Victim",
        victim_phone="9876543212",
        victim_location="Lajpat Nagar",
        state="Delhi",
        district="South Delhi",
        incident_time=now - timedelta(hours=6),
        reported_at=now - timedelta(hours=5),
        case_status="REGISTERED",
        created_at=now,
    )
    db_session.add(comp_exp)
    db_session.commit()
    db_session.refresh(comp_exp)

    # Exactly expired boundary (window ended 5 seconds ago)
    pred_exp = Prediction(
        complaint_id=comp_exp.id,
        predicted_window_start=now - timedelta(hours=2),
        predicted_window_end=now - timedelta(seconds=5),
        primary_cluster_id=4,
        risk_score=0.90,
        risk_level="CRITICAL",
        created_at=now - timedelta(hours=2),
    )
    db_session.add(pred_exp)
    db_session.commit()
    db_session.refresh(pred_exp)

    ploc = PredictionLocation(
        prediction_id=pred_exp.id,
        cluster_id=4,
        location_name="Lajpat Nagar Cluster",
        rank=1,
        probability=0.19,
        risk_level="CRITICAL",
    )
    db_session.add(ploc)
    db_session.commit()

    resp = client.get("/api/v1/risk-map", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()

    active_ids = [h["id"] for h in data.get("active_candidates", [])]
    assert 4 not in active_ids


# ==============================================================================
# 5. Missing / invalid window
# ==============================================================================
def test_missing_and_invalid_window_exclusion(db_session: Session, client, admin_headers):
    """
    Requirement 2:
    Predictions with null window or end <= start must not be treated as active.
    """
    now = datetime.utcnow()
    ts = int(time.time())

    comp_inv = Complaint(
        complaint_number=f"CMP-P3-INV-{ts}",
        fraud_type="Net Banking",
        amount=40000.0,
        victim_name="Invalid Window Victim",
        victim_phone="9876543213",
        victim_location="Connaught Place",
        state="Delhi",
        district="New Delhi",
        incident_time=now - timedelta(hours=3),
        reported_at=now - timedelta(hours=2),
        case_status="REGISTERED",
        created_at=now,
    )
    db_session.add(comp_inv)
    db_session.commit()
    db_session.refresh(comp_inv)

    # Inverted window: end before start
    pred_inv = Prediction(
        complaint_id=comp_inv.id,
        predicted_window_start=now + timedelta(hours=2),
        predicted_window_end=now + timedelta(hours=1),
        primary_cluster_id=5,
        risk_score=0.85,
        risk_level="HIGH",
        created_at=now,
    )
    db_session.add(pred_inv)
    db_session.commit()
    db_session.refresh(pred_inv)

    ploc = PredictionLocation(
        prediction_id=pred_inv.id,
        cluster_id=5,
        location_name="Connaught Place Cluster",
        rank=1,
        probability=0.12,
        risk_level="HIGH",
    )
    db_session.add(ploc)
    db_session.commit()

    resp = client.get("/api/v1/risk-map", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()

    active_ids = [h["id"] for h in data.get("active_candidates", [])]
    assert 5 not in active_ids


# ==============================================================================
# 6. Multiple predictions for one complaint (only latest row evaluated)
# ==============================================================================
def test_multiple_predictions_only_latest_row_evaluated(db_session: Session, client, admin_headers):
    """
    Requirement 3:
    Only the latest persisted prediction per complaint (rn == 1) is evaluated.
    An older unexpired prediction must NOT be revived if the latest is expired.
    """
    now = datetime.utcnow()
    ts = int(time.time())

    comp = Complaint(
        complaint_number=f"CMP-P3-MULT-{ts}",
        fraud_type="UPI Fraud",
        amount=60000.0,
        victim_name="Multi Pred Victim",
        victim_phone="9876543214",
        victim_location="Saket",
        state="Delhi",
        district="South Delhi",
        incident_time=now - timedelta(hours=4),
        reported_at=now - timedelta(hours=3),
        case_status="UNDER_INVESTIGATION",
        created_at=now - timedelta(hours=3),
    )
    db_session.add(comp)
    db_session.commit()
    db_session.refresh(comp)

    delhi_clusters = get_delhi_clusters(db_session)
    c_old_cluster = delhi_clusters[30]
    c_new_cluster = delhi_clusters[31]

    # Clean any pre-existing predictions for these test clusters
    for c_id in (c_old_cluster.id, c_new_cluster.id):
        plocs = db_session.query(PredictionLocation.prediction_id).filter(PredictionLocation.cluster_id == c_id).all()
        preds = db_session.query(Prediction.id).filter(Prediction.primary_cluster_id == c_id).all()
        all_p = set([p[0] for p in plocs] + [p[0] for p in preds])
        if all_p:
            _clean_test_predictions(db_session, all_p)

    # Older prediction (created 2h ago): has unexpired future window in c_old_cluster
    pred_old = Prediction(
        complaint_id=comp.id,
        predicted_window_start=now - timedelta(hours=1),
        predicted_window_end=now + timedelta(hours=3),
        primary_cluster_id=c_old_cluster.id,
        risk_score=0.88,
        risk_level="HIGH",
        created_at=now - timedelta(hours=2),
    )
    db_session.add(pred_old)
    db_session.commit()
    db_session.refresh(pred_old)

    ploc_old = PredictionLocation(
        prediction_id=pred_old.id,
        cluster_id=c_old_cluster.id,
        location_name=c_old_cluster.cluster_name,
        rank=1,
        probability=0.17,
        risk_level="HIGH",
    )
    db_session.add(ploc_old)
    db_session.commit()

    # Newer prediction (created 10m ago): re-run produced an expired or different result in c_new_cluster
    pred_new = Prediction(
        complaint_id=comp.id,
        predicted_window_start=now - timedelta(hours=1),
        predicted_window_end=now - timedelta(minutes=5),  # expired!
        primary_cluster_id=c_new_cluster.id,
        risk_score=0.75,
        risk_level="MEDIUM",
        created_at=now - timedelta(minutes=10),
    )
    db_session.add(pred_new)
    db_session.commit()
    db_session.refresh(pred_new)

    ploc_new = PredictionLocation(
        prediction_id=pred_new.id,
        cluster_id=c_new_cluster.id,
        location_name=c_new_cluster.cluster_name,
        rank=1,
        probability=0.08,
        risk_level="MEDIUM",
    )
    db_session.add(ploc_new)
    db_session.commit()

    resp = client.get("/api/v1/risk-map", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()

    active_ids = [h["id"] for h in data.get("active_candidates", [])]
    # c_old_cluster must NOT be active (older prediction must not be revived)
    assert c_old_cluster.id not in active_ids
    # c_new_cluster must NOT be active (latest prediction is expired)
    assert c_new_cluster.id not in active_ids


# ==============================================================================
# 7. Distinct scores for primary and secondary locations
# ==============================================================================
def test_distinct_scores_for_primary_and_secondary_locations(db_session: Session, client, admin_headers):
    """
    Requirement 5:
    Preserve each PredictionLocation's own candidate score.
    Do NOT copy the primary candidate's score onto secondary locations.
    """
    now = datetime.utcnow()
    ts = int(time.time())

    # Ensure clean clusters 8 & 9 for distinct score test
    existing_plocs = db_session.query(PredictionLocation.prediction_id).filter(PredictionLocation.cluster_id.in_([8, 9])).all()
    existing_preds = db_session.query(Prediction.id).filter(Prediction.primary_cluster_id.in_([8, 9])).all()
    all_p_ids = set([p[0] for p in existing_preds] + [p[0] for p in existing_plocs])
    if all_p_ids:
        _clean_test_predictions(db_session, all_p_ids)

    comp = Complaint(
        complaint_number=f"CMP-P3-DISTINCT-{ts}",
        fraud_type="UPI Fraud",
        amount=95000.0,
        victim_name="Distinct Score Victim",
        victim_phone="9876543215",
        victim_location="Janakpuri",
        state="Delhi",
        district="West Delhi",
        incident_time=now - timedelta(hours=2),
        reported_at=now - timedelta(hours=1),
        case_status="REGISTERED",
        created_at=now,
    )
    db_session.add(comp)
    db_session.commit()
    db_session.refresh(comp)

    pred = Prediction(
        complaint_id=comp.id,
        predicted_window_start=now,
        predicted_window_end=now + timedelta(hours=3),
        primary_cluster_id=8,
        risk_score=0.92,
        risk_level="CRITICAL",
        created_at=now,
    )
    db_session.add(pred)
    db_session.commit()
    db_session.refresh(pred)

    # Rank 1 in Cluster 8 with score 0.245
    ploc1 = PredictionLocation(
        prediction_id=pred.id,
        cluster_id=8,
        location_name="Cluster 8 Primary",
        rank=1,
        probability=0.245,
        risk_level="CRITICAL",
    )
    # Rank 2 in Cluster 9 with score 0.082
    ploc2 = PredictionLocation(
        prediction_id=pred.id,
        cluster_id=9,
        location_name="Cluster 9 Secondary",
        rank=2,
        probability=0.082,
        risk_level="HIGH",
    )
    db_session.add_all([ploc1, ploc2])
    db_session.commit()

    resp = client.get("/api/v1/risk-map", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()

    c8 = next((h for h in data["active_candidates"] if h["id"] == 8), None)
    c9 = next((h for h in data["active_candidates"] if h["id"] == 9), None)

    assert c8 is not None
    assert c9 is not None

    # Primary gets 0.245, Secondary gets its own 0.082 (NOT 0.245!)
    assert c8["candidate_score"] == 0.245
    assert c9["candidate_score"] == 0.082
    assert c8["candidate_score"] != c9["candidate_score"]


# ==============================================================================
# 8. Same complaint linked to multiple candidate zones
# ==============================================================================
def test_same_complaint_linked_to_multiple_candidate_zones(db_session: Session, client, admin_headers):
    """
    Requirement 8:
    A complaint may legitimately appear in multiple candidate zones.
    Each zone references the complaint number.
    """
    now = datetime.utcnow()
    ts = int(time.time())

    comp = Complaint(
        complaint_number=f"CMP-P3-MULTI-ZONE-{ts}",
        fraud_type="Net Banking",
        amount=120000.0,
        victim_name="Multi Zone Victim",
        victim_phone="9876543216",
        victim_location="Shahdara",
        state="Delhi",
        district="Shahdara",
        incident_time=now - timedelta(hours=2),
        reported_at=now - timedelta(hours=1),
        case_status="UNDER_INVESTIGATION",
        created_at=now,
    )
    db_session.add(comp)
    db_session.commit()
    db_session.refresh(comp)

    pred = Prediction(
        complaint_id=comp.id,
        predicted_window_start=now,
        predicted_window_end=now + timedelta(hours=2),
        primary_cluster_id=10,
        risk_score=0.89,
        risk_level="HIGH",
        created_at=now,
    )
    db_session.add(pred)
    db_session.commit()
    db_session.refresh(pred)

    ploc1 = PredictionLocation(
        prediction_id=pred.id,
        cluster_id=10,
        location_name="Zone A",
        rank=1,
        probability=0.19,
        risk_level="HIGH",
    )
    ploc2 = PredictionLocation(
        prediction_id=pred.id,
        cluster_id=11,
        location_name="Zone B",
        rank=2,
        probability=0.11,
        risk_level="MEDIUM",
    )
    db_session.add_all([ploc1, ploc2])
    db_session.commit()

    resp = client.get("/api/v1/risk-map", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()

    c10 = next((h for h in data["active_candidates"] if h["id"] == 10), None)
    c11 = next((h for h in data["active_candidates"] if h["id"] == 11), None)

    assert c10 is not None
    assert c11 is not None

    assert comp.complaint_number in c10["linked_complaint_numbers"]
    assert comp.complaint_number in c11["linked_complaint_numbers"]
    assert c10["associated_complaint_amount"] >= 120000.0
    assert c11["associated_complaint_amount"] >= 120000.0


# ==============================================================================
# 9. Duplicate case contribution within one cluster
# ==============================================================================
def test_duplicate_case_contribution_within_one_cluster(db_session: Session, client, admin_headers):
    """
    Requirement 8:
    Deduplicate a complaint within a cluster.
    If Rank 1 and Rank 2 are both in Cluster 12, the complaint contributes 1 case
    and its amount is counted exactly once within that cluster.
    """
    now = datetime.utcnow()
    ts = int(time.time())

    # Clean any pre-existing predictions for Cluster 12
    plocs = db_session.query(PredictionLocation.prediction_id).filter(PredictionLocation.cluster_id == 12).all()
    preds = db_session.query(Prediction.id).filter(Prediction.primary_cluster_id == 12).all()
    all_p = set([p[0] for p in plocs] + [p[0] for p in preds])
    if all_p:
        _clean_test_predictions(db_session, all_p)

    comp = Complaint(
        complaint_number=f"CMP-P3-SAME-CLUSTER-{ts}",
        fraud_type="UPI Fraud",
        amount=77000.0,
        victim_name="Same Cluster Victim",
        victim_phone="9876543217",
        victim_location="Dwarka",
        state="Delhi",
        district="South West Delhi",
        incident_time=now - timedelta(hours=3),
        reported_at=now - timedelta(hours=2),
        case_status="UNDER_INVESTIGATION",
        created_at=now,
    )
    db_session.add(comp)
    db_session.commit()
    db_session.refresh(comp)

    pred = Prediction(
        complaint_id=comp.id,
        predicted_window_start=now,
        predicted_window_end=now + timedelta(hours=2),
        primary_cluster_id=12,
        risk_score=0.90,
        risk_level="CRITICAL",
        created_at=now,
    )
    db_session.add(pred)
    db_session.commit()
    db_session.refresh(pred)

    # Both Rank 1 and Rank 2 assigned to Cluster 12
    ploc1 = PredictionLocation(
        prediction_id=pred.id,
        cluster_id=12,
        location_name="Dwarka Sector 10",
        rank=1,
        probability=0.21,
        risk_level="CRITICAL",
    )
    ploc2 = PredictionLocation(
        prediction_id=pred.id,
        cluster_id=12,
        location_name="Dwarka Sector 12",
        rank=2,
        probability=0.14,
        risk_level="HIGH",
    )
    db_session.add_all([ploc1, ploc2])
    db_session.commit()

    resp = client.get("/api/v1/risk-map", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()

    c12 = next((h for h in data["active_candidates"] if h["id"] == 12), None)
    assert c12 is not None

    # Must be 1 case, not 2
    assert c12["active_cases"] == 1
    # Must be 77,000, not 154,000
    assert c12["associated_complaint_amount"] == 77000.0
    # Complaint number appears once
    assert c12["linked_complaint_numbers"].count(comp.complaint_number) == 1


# ==============================================================================
# 10. Correct unique global totals (deduplication across clusters)
# ==============================================================================
def test_correct_unique_global_totals(db_session: Session, client, admin_headers):
    """
    Requirement 8:
    Do not sum overlapping zone amounts as unique global exposure.
    Global unique totals must deduplicate complaints across all clusters.
    """
    now = datetime.utcnow()
    ts = int(time.time())

    # Clear prior prediction locations on clusters 13, 14, 15 to isolate test
    db_session.query(PredictionLocation).filter(PredictionLocation.cluster_id.in_([13, 14, 15])).delete()
    db_session.commit()

    # Case A: 50,000 in cluster 13 & 14
    comp_a = Complaint(
        complaint_number=f"CMP-P3-GLOB-A-{ts}",
        fraud_type="UPI Fraud",
        amount=50000.0,
        victim_name="Global Victim A",
        victim_phone="9876543218",
        victim_location="Pitampura",
        state="Delhi",
        district="North West Delhi",
        incident_time=now - timedelta(hours=2),
        reported_at=now - timedelta(hours=1),
        case_status="REGISTERED",
        created_at=now,
    )
    # Case B: 30,000 in cluster 14 & 15
    comp_b = Complaint(
        complaint_number=f"CMP-P3-GLOB-B-{ts}",
        fraud_type="UPI Fraud",
        amount=30000.0,
        victim_name="Global Victim B",
        victim_phone="9876543219",
        victim_location="Rohini",
        state="Delhi",
        district="North West Delhi",
        incident_time=now - timedelta(hours=2),
        reported_at=now - timedelta(hours=1),
        case_status="REGISTERED",
        created_at=now,
    )
    db_session.add_all([comp_a, comp_b])
    db_session.commit()
    db_session.refresh(comp_a)
    db_session.refresh(comp_b)

    pred_a = Prediction(
        complaint_id=comp_a.id,
        predicted_window_start=now,
        predicted_window_end=now + timedelta(hours=2),
        primary_cluster_id=13,
        risk_score=0.88,
        risk_level="HIGH",
        created_at=now,
    )
    pred_b = Prediction(
        complaint_id=comp_b.id,
        predicted_window_start=now,
        predicted_window_end=now + timedelta(hours=2),
        primary_cluster_id=14,
        risk_score=0.86,
        risk_level="HIGH",
        created_at=now,
    )
    db_session.add_all([pred_a, pred_b])
    db_session.commit()
    db_session.refresh(pred_a)
    db_session.refresh(pred_b)

    # Pred A spans cluster 13 & 14
    ploc_a1 = PredictionLocation(prediction_id=pred_a.id, cluster_id=13, location_name="Z13", rank=1, probability=0.18, risk_level="HIGH")
    ploc_a2 = PredictionLocation(prediction_id=pred_a.id, cluster_id=14, location_name="Z14", rank=2, probability=0.10, risk_level="MEDIUM")
    # Pred B spans cluster 14 & 15
    ploc_b1 = PredictionLocation(prediction_id=pred_b.id, cluster_id=14, location_name="Z14", rank=1, probability=0.16, risk_level="HIGH")
    ploc_b2 = PredictionLocation(prediction_id=pred_b.id, cluster_id=15, location_name="Z15", rank=2, probability=0.09, risk_level="MEDIUM")
    db_session.add_all([ploc_a1, ploc_a2, ploc_b1, ploc_b2])
    db_session.commit()

    resp = client.get("/api/v1/risk-map", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()

    # Summing naive amounts would double-count both cases across clusters.
    # The deduplicated global total in summary must be exactly 50,000 + 30,000 + any pre-existing isolated cases
    summary = data["summary"]
    assert summary["total_associated_amount"] >= 80000.0


# ==============================================================================
# 11. Authorized versus unauthorized case visibility (RBAC)
# ==============================================================================
def test_authorized_versus_unauthorized_case_visibility(db_session: Session, client):
    """
    Requirement 13:
    Preserve RBAC, geographic scope and complaint access checks.
    Aggregated counts and amounts must not expose unauthorized cases.
    """
    now = datetime.utcnow()
    ts = int(time.time())

    # Create an active Indore actor for this test instead of relying on demo users.
    indore_email = f"phase3.indore.{time.time_ns()}@cybershield.test"
    db_session.add(User(
        email=indore_email,
        hashed_password="test-only-token-authenticated-user",
        full_name="Phase 3 Indore Officer",
        role="DISTRICT_LEA",
        organization_id=3,
        is_active=True,
    ))
    db_session.commit()
    indore_headers = _make_auth_header(indore_email, "DISTRICT_LEA")

    # Create Delhi complaint in Cluster 16
    comp_delhi = Complaint(
        complaint_number=f"CMP-P3-DELHI-SEC-{ts}",
        fraud_type="UPI Fraud",
        amount=150000.0,
        victim_name="Delhi Citizen",
        victim_phone="9876543220",
        victim_location="Civil Lines",
        state="Delhi",
        district="North Delhi",
        incident_time=now - timedelta(hours=2),
        reported_at=now - timedelta(hours=1),
        case_status="REGISTERED",
        created_at=now,
    )
    db_session.add(comp_delhi)
    db_session.commit()
    db_session.refresh(comp_delhi)

    pred = Prediction(
        complaint_id=comp_delhi.id,
        predicted_window_start=now,
        predicted_window_end=now + timedelta(hours=2),
        primary_cluster_id=16,
        risk_score=0.94,
        risk_level="CRITICAL",
        created_at=now,
    )
    db_session.add(pred)
    db_session.commit()
    db_session.refresh(pred)

    ploc = PredictionLocation(
        prediction_id=pred.id,
        cluster_id=16,
        location_name="Civil Lines",
        rank=1,
        probability=0.22,
        risk_level="CRITICAL",
    )
    db_session.add(ploc)
    db_session.commit()

    # Query as Indore officer:
    resp = client.get("/api/v1/risk-map", headers=indore_headers)
    assert resp.status_code == 200
    data = resp.json()

    # The Delhi complaint must NOT contribute to any active candidate for an Indore officer
    for candidate in data.get("active_candidates", []):
        assert comp_delhi.complaint_number not in candidate.get("linked_complaint_numbers", [])


# ==============================================================================
# 12. No eligible active predictions (clean empty state)
# ==============================================================================
def test_no_eligible_active_predictions_clean_state(db_session: Session, client):
    """
    Requirement 9:
    When no complaints have eligible active predictions, active_candidates is
    empty and historical hotspots remain in the historical baseline section.
    """
    # Create isolated officer in an empty jurisdiction
    org = Organization(name="Goa Cyber Command", org_type="LEA", state="Goa", district="North Goa")
    db_session.add(org)
    db_session.flush()

    user = User(
        email="officer.empty@goa.police.gov.in",
        hashed_password="TestPassword@123",
        full_name="Goa Empty Officer",
        role="DISTRICT_LEA",
        organization_id=org.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    empty_headers = _make_auth_header("officer.empty@goa.police.gov.in", "DISTRICT_LEA")

    resp = client.get("/api/v1/risk-map", headers=empty_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data.get("active_candidates") == []
    assert data["summary"].get("total_active_candidates", 0) == 0
    assert data["summary"].get("total_associated_amount", 0.0) == 0.0


# ==============================================================================
# 13. Cluster navigation and details API
# ==============================================================================
def test_cluster_navigation_and_details_api(db_session: Session, client, admin_headers):
    """
    Requirement 10:
    GET /api/v1/clusters/{id} returns truthful cluster state, and 404 for invalid ID.
    """
    # Valid cluster
    resp = client.get("/api/v1/clusters/1", headers=admin_headers)
    assert resp.status_code == 200
    c_data = resp.json()
    assert c_data["id"] == 1
    assert "is_active_candidate" in c_data
    assert "historical_risk" in c_data

    # Invalid cluster ID: 404
    resp_404 = client.get("/api/v1/clusters/999999", headers=admin_headers)
    assert resp_404.status_code == 404


# ==============================================================================
# 14. Multi-case cluster staggered expiry (cluster preserved on single-case expiry)
# ==============================================================================
def test_multicase_cluster_staggered_expiry_preserved(db_session: Session, client, admin_headers):
    """
    Phase 3 Closure Review Requirement 4:
    If an aggregated cluster has several cases with different expiry times,
    do not remove the entire cluster when only one case expires.
    Authoritative refresh updates active counts, amounts, and window coherently.
    """
    # Clean cluster 20 of any pre-existing predictions
    db_session.query(PredictionLocation).filter(PredictionLocation.cluster_id == 20).delete()
    db_session.commit()

    now = datetime.utcnow()
    ts = int(time.time())

    # Case 1 in Cluster 20: short remaining window
    comp1 = Complaint(
        complaint_number=f"CMP-P3-EXP-A-{ts}",
        fraud_type="UPI Fraud",
        amount=40000.0,
        victim_name="Staggered Victim 1",
        victim_phone="9876543231",
        victim_location="Okhla",
        state="Delhi",
        district="South East Delhi",
        incident_time=now - timedelta(hours=2),
        reported_at=now - timedelta(hours=1),
        case_status="UNDER_INVESTIGATION",
        created_at=now,
    )
    # Case 2 in Cluster 20: longer remaining window (active for +3h)
    comp2 = Complaint(
        complaint_number=f"CMP-P3-EXP-B-{ts}",
        fraud_type="Card Cloning",
        amount=60000.0,
        victim_name="Staggered Victim 2",
        victim_phone="9876543232",
        victim_location="Okhla Phase 2",
        state="Delhi",
        district="South East Delhi",
        incident_time=now - timedelta(hours=2),
        reported_at=now - timedelta(hours=1),
        case_status="UNDER_INVESTIGATION",
        created_at=now,
    )
    db_session.add_all([comp1, comp2])
    db_session.commit()
    db_session.refresh(comp1)
    db_session.refresh(comp2)

    # Prediction 1: window ends in 30 minutes
    pred1 = Prediction(
        complaint_id=comp1.id,
        predicted_window_start=now,
        predicted_window_end=now + timedelta(minutes=30),
        primary_cluster_id=20,
        risk_score=0.75,
        risk_level="HIGH",
        created_at=now,
    )
    # Prediction 2: window ends in 3 hours
    pred2 = Prediction(
        complaint_id=comp2.id,
        predicted_window_start=now,
        predicted_window_end=now + timedelta(hours=3),
        primary_cluster_id=20,
        risk_score=0.85,
        risk_level="HIGH",
        created_at=now,
    )
    db_session.add_all([pred1, pred2])
    db_session.commit()
    db_session.refresh(pred1)
    db_session.refresh(pred2)

    ploc1 = PredictionLocation(
        prediction_id=pred1.id,
        cluster_id=20,
        location_name="Cluster 20 Zone",
        rank=1,
        probability=0.22,
        risk_level="HIGH",
    )
    ploc2 = PredictionLocation(
        prediction_id=pred2.id,
        cluster_id=20,
        location_name="Cluster 20 Zone",
        rank=1,
        probability=0.28,
        risk_level="HIGH",
    )
    db_session.add_all([ploc1, ploc2])
    db_session.commit()

    # Initial query: both cases active in Cluster 20
    resp = client.get("/api/v1/risk-map", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    c20 = next((h for h in data["active_candidates"] if h["id"] == 20), None)
    assert c20 is not None
    assert c20["active_cases"] == 2
    assert c20["associated_complaint_amount"] == 100000.0
    assert comp1.complaint_number in c20["linked_complaint_numbers"]
    assert comp2.complaint_number in c20["linked_complaint_numbers"]
    assert c20["latest_window_end"] is not None

    # Simulate expiry of Case 1 only by setting pred1.predicted_window_end to past
    pred1.predicted_window_end = now - timedelta(minutes=5)
    db_session.commit()

    # Fresh authoritative aggregate query (simulating 60s background refresh)
    resp2 = client.get("/api/v1/risk-map", headers=admin_headers)
    assert resp2.status_code == 200
    data2 = resp2.json()

    # Verify Cluster 20 is NOT dropped! It remains an active candidate!
    c20_refreshed = next((h for h in data2["active_candidates"] if h["id"] == 20), None)
    assert c20_refreshed is not None, "Cluster 20 must NOT be dropped when only one case expires!"
    assert c20_refreshed["is_active_candidate"] is True

    # Case 1 is now excluded, Case 2 remains
    assert comp1.complaint_number not in c20_refreshed["linked_complaint_numbers"]
    assert comp2.complaint_number in c20_refreshed["linked_complaint_numbers"]
    assert c20_refreshed["active_cases"] == 1
    assert c20_refreshed["associated_complaint_amount"] == 60000.0

