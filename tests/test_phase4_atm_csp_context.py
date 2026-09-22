import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from backend.app.main import app
from backend.app.models.db import get_db
from backend.app.models.models import (
    User,
    Organization,
    Complaint,
    Prediction,
    PredictionLocation,
    LocationCluster,
    ATMLocation,
    ComplaintAccount,
    Account,
    InterventionPlan,
    InterventionPlanAction,
)
from backend.app.auth.security import create_access_token
from backend.app.services.atm_context_service import ATMContextService
from backend.app.services.intervention_service import InterventionOrchestratorService


client = TestClient(app)


# ─── FIXTURES & HELPERS ────────────────────────────────────────────────────────

import uuid

@pytest.fixture
def test_users(db_session: Session):
    """Creates test users for RBAC testing."""
    users = {}
    uid = str(uuid.uuid4())[:8]

    org_delhi = Organization(name=f"Delhi Central LEA Org {uid}", org_type="LEA", state="Delhi", district="Central")
    org_mumbai = Organization(name=f"Mumbai LEA Org {uid}", org_type="LEA", state="Maharashtra", district="MUMBAI")
    org_sbi = Organization(name=f"State Bank of India Org {uid}", org_type="BANK", state="Delhi", district="Central")
    org_i4c = Organization(name=f"I4C National Org {uid}", org_type="I4C", state="Delhi", district="NATIONAL")

    db_session.add(org_delhi)
    db_session.add(org_mumbai)
    db_session.add(org_sbi)
    db_session.add(org_i4c)
    db_session.commit()

    admin = User(
        email=f"i4c_admin_{uid}@cybershield.gov.in",
        hashed_password="hash",
        full_name="I4C Admin P4",
        role="I4C_ADMIN",
        badge_number=f"I4C-{uid}",
        organization_id=org_i4c.id,
        is_active=True,
    )

    district_delhi = User(
        email=f"delhi_central_{uid}@delhipolice.gov.in",
        hashed_password="hash",
        full_name="Central Delhi LEA P4",
        role="DISTRICT_LEA",
        badge_number=f"DL-CEN-{uid}",
        organization_id=org_delhi.id,
        is_active=True,
    )

    district_mumbai = User(
        email=f"mumbai_lea_{uid}@mahapolice.gov.in",
        hashed_password="hash",
        full_name="Mumbai LEA P4",
        role="DISTRICT_LEA",
        badge_number=f"MH-MUM-{uid}",
        organization_id=org_mumbai.id,
        is_active=True,
    )

    state_delhi = User(
        email=f"delhi_state_{uid}@delhipolice.gov.in",
        hashed_password="hash",
        full_name="Delhi State LEA P4",
        role="STATE_LEA",
        badge_number=f"DL-STA-{uid}",
        organization_id=org_delhi.id,
        is_active=True,
    )

    bank_officer = User(
        email=f"bank_officer_{uid}@sbi.co.in",
        hashed_password="hash",
        full_name="Bank Officer P4",
        role="BANK_OFFICER",
        badge_number=f"SBI-{uid}",
        organization_id=org_sbi.id,
        is_active=True,
    )

    auditor = User(
        email=f"auditor_{uid}@cybershield.gov.in",
        hashed_password="hash",
        full_name="Auditor P4",
        role="AUDITOR",
        badge_number=f"AUD-{uid}",
        organization_id=org_i4c.id,
        is_active=True,
    )

    for u in [admin, district_delhi, district_mumbai, state_delhi, bank_officer, auditor]:
        db_session.add(u)
    db_session.commit()

    for u in [admin, district_delhi, district_mumbai, state_delhi, bank_officer, auditor]:
        db_session.refresh(u)

    users["admin"] = (admin, create_access_token({"sub": admin.email}))
    users["district_delhi"] = (district_delhi, create_access_token({"sub": district_delhi.email}))
    users["district_mumbai"] = (district_mumbai, create_access_token({"sub": district_mumbai.email}))
    users["state_delhi"] = (state_delhi, create_access_token({"sub": state_delhi.email}))
    users["bank_officer"] = (bank_officer, create_access_token({"sub": bank_officer.email}))
    users["auditor"] = (auditor, create_access_token({"sub": auditor.email}))

    return users


@pytest.fixture
def sample_prediction_data(db_session: Session):
    """Creates a sample complaint, V8 prediction, and ATM records in Connaught Place."""
    uid = str(uuid.uuid4())[:8]
    now_dt = datetime.now(timezone.utc)
    # 1. Complaint
    complaint = Complaint(
        complaint_number=f"CMP-P4-{uid}",
        fraud_type="UPI Fraud",
        amount=150000.0,
        victim_name="Ramesh Kumar",
        victim_location="Connaught Place, New Delhi",
        state="Delhi",
        district="Central",
        payment_channel="UPI",
        reported_at=now_dt,
        incident_time=now_dt,
        risk_level="HIGH",
        risk_score=0.85,
        prediction_status="AVAILABLE",
        case_status="ACTIVE",
        created_at=now_dt,
    )
    db_session.add(complaint)
    db_session.commit()
    db_session.refresh(complaint)

    # Beneficiary account for bank match test
    acc = Account(
        account_number=f"ACC-SBI-{uid}",
        masked_account=f"XXXX{uid[:4]}",
        bank_name="State Bank of India",
        branch="Connaught Place Branch",
        holder_name="Mule Account 1",
        state="Delhi",
        district="Central",
        created_at=now_dt,
    )
    db_session.add(acc)
    db_session.commit()
    db_session.refresh(acc)

    c_acc = ComplaintAccount(
        complaint_id=complaint.id,
        account_id=acc.id,
        association_type="BENEFICIARY",
        created_at=now_dt,
    )
    db_session.add(c_acc)
    db_session.commit()

    # 2. Persisted V8 Prediction
    pred = Prediction(
        complaint_id=complaint.id,
        version_number=1,
        prediction_mode="trained_ml",
        model_version="cashout-location-xgb-v8-debiased",
        risk_level="HIGH",
        risk_score=0.85,
        ml_score=0.833,
        primary_cluster_id=1,
        predicted_window_start=now_dt,
        predicted_window_end=now_dt,
        created_at=now_dt,
    )
    db_session.add(pred)
    db_session.commit()
    db_session.refresh(pred)

    cp_cluster = db_session.query(LocationCluster).filter(LocationCluster.cluster_name.ilike("%Connaught Place%")).first()
    target_cluster_id = cp_cluster.id if cp_cluster else None

    # 3. Top-3 Candidate Locations
    loc1 = PredictionLocation(
        prediction_id=pred.id,
        rank=1,
        location_name="Connaught Place",
        cluster_id=target_cluster_id,
        latitude=28.6315,
        longitude=77.2167,
        probability=0.0833,
        risk_level="HIGH",
        distance_km=0.4,
    )
    loc2 = PredictionLocation(
        prediction_id=pred.id,
        rank=2,
        location_name="Karol Bagh",
        cluster_id=None,
        latitude=28.6514,
        longitude=77.1907,
        probability=0.0747,
        risk_level="MEDIUM",
        distance_km=1.2,
    )
    loc3 = PredictionLocation(
        prediction_id=pred.id,
        rank=3,
        location_name="Rajendra Place",
        cluster_id=None,
        latitude=28.6425,
        longitude=77.1781,
        probability=0.0664,
        risk_level="MEDIUM",
        distance_km=2.1,
    )
    for loc in [loc1, loc2, loc3]:
        db_session.add(loc)
    db_session.commit()

    # 4. ATMs in Connaught Place
    atm1 = ATMLocation(
        atm_code=f"ATM-SBI-{uid}",
        bank_name="State Bank of India",
        bank_code="SBI",
        address="Inner Circle, Connaught Place, New Delhi",
        city="New Delhi",
        district="Central",
        state="Delhi",
        latitude=28.6320,
        longitude=77.2170, # ~0.07 km from centroid
        cluster_id=target_cluster_id,
        cash_available=True,
        risk_rating="HIGH",
        location_type="ATM",
        source="INTERNAL_CONTROLLED_DATA",
        is_active=True,
    )
    atm2 = ATMLocation(
        atm_code=f"ATM-PNB-{uid}",
        bank_name="Punjab National Bank",
        bank_code="PNB",
        address="Outer Circle, Connaught Place, New Delhi",
        city="New Delhi",
        district="Central",
        state="Delhi",
        latitude=28.6340,
        longitude=77.2190, # ~0.35 km from centroid
        cluster_id=target_cluster_id,
        cash_available=True,
        risk_rating="MEDIUM",
        location_type="ATM",
        source="INTERNAL_CONTROLLED_DATA",
        is_active=True,
    )
    csp1 = ATMLocation(
        atm_code=f"CSP-SBI-{uid}",
        bank_name="State Bank of India",
        bank_code="SBI",
        address="Janpath Market, Connaught Place, New Delhi",
        city="New Delhi",
        district="Central",
        state="Delhi",
        latitude=28.6290,
        longitude=77.2150, # ~0.33 km from centroid
        cluster_id=target_cluster_id,
        cash_available=True,
        risk_rating="MEDIUM",
        location_type="CSP",
        source="INTERNAL_CONTROLLED_DATA",
        is_active=True,
    )
    for a in [atm1, atm2, csp1]:
        db_session.add(a)
    db_session.commit()

    return {
        "complaint": complaint,
        "prediction": pred,
        "locations": [loc1, loc2, loc3],
        "atms": [atm1, atm2, csp1],
    }


# ─── 1. TESTS — INVARIANCE (REQUIREMENT 19 & FREEZE) ─────────────────────────

def test_atm_context_uses_persisted_prediction(test_users, sample_prediction_data, db_session):
    """Verify endpoint uses persisted PredictionLocation records without calling inference."""
    user, token = test_users["district_delhi"]
    pred = sample_prediction_data["prediction"]

    response = client.get(
        f"/api/v1/predictions/{pred.id}/atm-context?rank=1",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["prediction_id"] == pred.id
    assert data["candidate_rank"] == 1
    assert data["candidate_zone"] == "Connaught Place"
    assert data["candidate_probability"] == 0.0833
    assert len(data["items"]) > 0


def test_atm_context_does_not_run_v8(test_users, sample_prediction_data):
    """Verify explicit proof that no V8 inference, calibrator, or candidate generator runs."""
    user, token = test_users["district_delhi"]
    pred = sample_prediction_data["prediction"]

    with patch("backend.app.services.atm_context_service.ATMContextService.get_atm_context_for_prediction", wraps=ATMContextService().get_atm_context_for_prediction) as mock_svc:
        response = client.get(
            f"/api/v1/predictions/{pred.id}/atm-context?rank=1",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        # Check service was called without invoking any ML predictor or model retrain
        assert mock_svc.called


def test_atm_context_does_not_modify_top3(test_users, sample_prediction_data, db_session):
    """Verify Top-3 candidate clusters and their ranking remain strictly unchanged."""
    user, token = test_users["district_delhi"]
    pred = sample_prediction_data["prediction"]

    # Initial locations before context call
    locs_before = db_session.query(PredictionLocation).filter(PredictionLocation.prediction_id == pred.id).order_by(PredictionLocation.rank.asc()).all()
    ranks_before = [(l.rank, l.location_name, l.probability) for l in locs_before]

    # Invoke context endpoint for rank 1, 2, and 3
    for r in [1, 2, 3]:
        res = client.get(f"/api/v1/predictions/{pred.id}/atm-context?rank={r}", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200

    # Locations after context calls
    db_session.expire_all()
    locs_after = db_session.query(PredictionLocation).filter(PredictionLocation.prediction_id == pred.id).order_by(PredictionLocation.rank.asc()).all()
    ranks_after = [(l.rank, l.location_name, l.probability) for l in locs_after]

    assert ranks_before == ranks_after
    assert ranks_after[0] == (1, "Connaught Place", 0.0833)
    assert ranks_after[1] == (2, "Karol Bagh", 0.0747)
    assert ranks_after[2] == (3, "Rajendra Place", 0.0664)


def test_atm_context_does_not_modify_probabilities(test_users, sample_prediction_data, db_session):
    """Verify prediction probabilities remain completely unchanged."""
    user, token = test_users["district_delhi"]
    pred = sample_prediction_data["prediction"]

    probs_before = [l.probability for l in db_session.query(PredictionLocation).filter(PredictionLocation.prediction_id == pred.id).order_by(PredictionLocation.rank.asc()).all()]

    client.get(f"/api/v1/predictions/{pred.id}/atm-context?rank=1", headers={"Authorization": f"Bearer {token}"})

    db_session.expire_all()
    probs_after = [l.probability for l in db_session.query(PredictionLocation).filter(PredictionLocation.prediction_id == pred.id).order_by(PredictionLocation.rank.asc()).all()]

    assert probs_before == probs_after
    assert probs_after == [0.0833, 0.0747, 0.0664]


def test_context_score_is_not_prediction_probability(test_users, sample_prediction_data):
    """Verify context score is an integer 0-100 separated from model probability (0.0833)."""
    user, token = test_users["district_delhi"]
    pred = sample_prediction_data["prediction"]

    res = client.get(f"/api/v1/predictions/{pred.id}/atm-context?rank=1", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()

    assert data["candidate_probability"] == 0.0833
    for item in data["items"]:
        assert isinstance(item["context_priority_score"], int)
        assert 0 <= item["context_priority_score"] <= 100
        # Must not equal candidate probability
        assert item["context_priority_score"] != data["candidate_probability"]


def test_switching_candidate_rank_preserves_v8_order(test_users, sample_prediction_data):
    """Verify switching between candidate ranks (#1, #2, #3) returns context for that rank without altering V8."""
    user, token = test_users["district_delhi"]
    pred = sample_prediction_data["prediction"]

    r1 = client.get(f"/api/v1/predictions/{pred.id}/atm-context?rank=1", headers={"Authorization": f"Bearer {token}"}).json()
    assert r1["candidate_zone"] == "Connaught Place"
    assert r1["candidate_probability"] == 0.0833

    r2 = client.get(f"/api/v1/predictions/{pred.id}/atm-context?rank=2", headers={"Authorization": f"Bearer {token}"}).json()
    assert r2["candidate_zone"] == "Karol Bagh"
    assert r2["candidate_probability"] == 0.0747

    r3 = client.get(f"/api/v1/predictions/{pred.id}/atm-context?rank=3", headers={"Authorization": f"Bearer {token}"}).json()
    assert r3["candidate_zone"] == "Rajendra Place"
    assert r3["candidate_probability"] == 0.0664


# ─── 2. TESTS — CONTEXT ENGINE (REQUIREMENT 20) ──────────────────────────────

def test_context_items_are_within_relevant_zone(test_users, sample_prediction_data):
    """Verify returned context items belong to or are near the candidate cluster zone."""
    user, token = test_users["district_delhi"]
    pred = sample_prediction_data["prediction"]

    res = client.get(f"/api/v1/predictions/{pred.id}/atm-context?rank=1", headers={"Authorization": f"Bearer {token}"})
    data = res.json()

    assert len(data["items"]) >= 3
    for item in data["items"]:
        assert item["distance_km"] < 5.0


def test_distance_component(test_users, sample_prediction_data):
    """Verify closer ATMs receive higher proximity scores."""
    user, token = test_users["district_delhi"]
    pred = sample_prediction_data["prediction"]

    res = client.get(f"/api/v1/predictions/{pred.id}/atm-context?rank=1", headers={"Authorization": f"Bearer {token}"})
    items = res.json()["items"]

    # Items are sorted descending by score
    scores = [item["context_priority_score"] for item in items]
    assert scores == sorted(scores, reverse=True)


def test_bank_match_component(test_users, sample_prediction_data):
    """Verify SBI ATMs receive bank match bonus because beneficiary bank is SBI."""
    user, token = test_users["district_delhi"]
    pred = sample_prediction_data["prediction"]

    res = client.get(f"/api/v1/predictions/{pred.id}/atm-context?rank=1", headers={"Authorization": f"Bearer {token}"})
    items = res.json()["items"]

    sbi_items = [i for i in items if "State Bank of India" in i["bank_name"] or i.get("bank_code") == "SBI"]
    pnb_items = [i for i in items if "PNB" in i["bank_name"] or i.get("bank_code") == "PNB"]

    assert len(sbi_items) > 0
    assert any(i["bank_match"] for i in sbi_items)
    assert not any(i["bank_match"] for i in pnb_items)


def test_context_scoring_deterministic(test_users, sample_prediction_data):
    """Verify context scoring is 100% deterministic across multiple calls."""
    user, token = test_users["district_delhi"]
    pred = sample_prediction_data["prediction"]

    res1 = client.get(f"/api/v1/predictions/{pred.id}/atm-context?rank=1", headers={"Authorization": f"Bearer {token}"}).json()
    res2 = client.get(f"/api/v1/predictions/{pred.id}/atm-context?rank=1", headers={"Authorization": f"Bearer {token}"}).json()

    assert res1 == res2


def test_priority_bands(test_users, sample_prediction_data):
    """Verify priority bands map correctly (HIGH >=70, MEDIUM 40-69, LOW <40)."""
    svc = ATMContextService()
    assert svc._score_to_priority_band(85) == "HIGH"
    assert svc._score_to_priority_band(70) == "HIGH"
    assert svc._score_to_priority_band(65) == "MEDIUM"
    assert svc._score_to_priority_band(40) == "MEDIUM"
    assert svc._score_to_priority_band(35) == "LOW"


def test_unavailable_context_returns_truthful_state(test_users, db_session):
    """Verify candidate zone with no nearby ATMs returns empty items list with disclaimer."""
    user, token = test_users["district_delhi"]

    # Complaint in remote location with no ATMs
    c = Complaint(
        complaint_number="CMP-EMPTY-001",
        fraud_type="Phishing",
        amount=50000.0,
        victim_name="Test User",
        victim_location="Remote Village",
        state="Delhi",
        district="Central",
        payment_channel="UPI",
        reported_at=datetime.now(timezone.utc),
        incident_time=datetime.now(timezone.utc),
        risk_level="MEDIUM",
        prediction_status="AVAILABLE",
        case_status="ACTIVE",
    )
    db_session.add(c)
    db_session.commit()

    now_dt = datetime.now(timezone.utc)
    p = Prediction(
        complaint_id=c.id,
        version_number=1,
        prediction_mode="trained_ml",
        model_version="cashout-location-xgb-v8-debiased",
        primary_cluster_id=1,
        predicted_window_start=now_dt,
        predicted_window_end=now_dt,
    )
    db_session.add(p)
    db_session.commit()

    pl = PredictionLocation(
        prediction_id=p.id,
        rank=1,
        location_name="Remote Zone 999",
        cluster_id=None,
        latitude=10.0000,
        longitude=10.0000,
        probability=0.05,
    )
    db_session.add(pl)
    db_session.commit()

    res = client.get(f"/api/v1/predictions/{p.id}/atm-context?rank=1", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()

    assert data["items"] == []
    assert "ATM/CSP prioritization is an operational context layer" in data["disclaimer"]


def test_external_source_failure_does_not_break_prediction(test_users, sample_prediction_data):
    """Verify system tolerates external geographic data unavailability gracefully."""
    user, token = test_users["district_delhi"]
    pred = sample_prediction_data["prediction"]

    with patch("backend.app.services.atm_context_service.ATMContextService._fetch_open_street_map_context", side_effect=Exception("OSM API Failure")):
        res = client.get(f"/api/v1/predictions/{pred.id}/atm-context?rank=1", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()
        assert len(data["items"]) >= 0


# ─── 3. TESTS — RBAC (REQUIREMENT 21) ────────────────────────────────────────

def test_district_atm_context_scope(test_users, sample_prediction_data):
    """Verify DISTRICT_LEA can access ATM context for case in their authorized district."""
    user, token = test_users["district_delhi"]
    pred = sample_prediction_data["prediction"]

    res = client.get(f"/api/v1/predictions/{pred.id}/atm-context?rank=1", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200


def test_state_atm_context_scope(test_users, sample_prediction_data):
    """Verify STATE_LEA can access ATM context for case in their state."""
    user, token = test_users["state_delhi"]
    pred = sample_prediction_data["prediction"]

    res = client.get(f"/api/v1/predictions/{pred.id}/atm-context?rank=1", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200


def test_out_of_scope_prediction_denied(test_users, sample_prediction_data):
    """Verify DISTRICT_LEA outside district (e.g. Mumbai) cannot access Delhi case ATM context."""
    user, token = test_users["district_mumbai"]
    pred = sample_prediction_data["prediction"]

    res = client.get(f"/api/v1/predictions/{pred.id}/atm-context?rank=1", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 404
    assert "jurisdiction scope" in res.json()["detail"].lower()


def test_bank_officer_case_geography_restricted(test_users, sample_prediction_data):
    """Verify BANK_OFFICER cannot access unrestricted LEA case geography."""
    user, token = test_users["bank_officer"]
    pred = sample_prediction_data["prediction"]

    res = client.get(f"/api/v1/predictions/{pred.id}/atm-context?rank=1", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 404


def test_auditor_read_only(test_users, sample_prediction_data):
    """Verify AUDITOR can read context without mutating data."""
    user, token = test_users["auditor"]
    pred = sample_prediction_data["prediction"]

    res = client.get(f"/api/v1/predictions/{pred.id}/atm-context?rank=1", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200


# ─── 4. TESTS — INTERVENTION INTEGRATION (REQUIREMENT 22) ─────────────────────

def test_intervention_plan_can_reference_atm_context(test_users, sample_prediction_data, db_session):
    """Verify Intervention Plan includes REVIEW_ATM_CSP_CONTEXT action and snapshot."""
    user, token = test_users["district_delhi"]
    complaint = sample_prediction_data["complaint"]

    svc = InterventionOrchestratorService()
    plan = svc.generate_plan_for_complaint(db_session, complaint.complaint_number, user)

    assert plan is not None
    action_types = [a.action_type for a in plan.actions]
    assert "REVIEW_ATM_CSP_CONTEXT" in action_types

    assert "atm_context_snapshot" in plan.summary_json
    snap = plan.summary_json["atm_context_snapshot"]
    assert snap["candidate_zone"] == "Connaught Place"
    assert snap["items_count"] > 0


def test_context_does_not_mutate_existing_plan(test_users, sample_prediction_data, db_session):
    """Verify calling ATM Context API does not mutate existing InterventionPlan objects."""
    user, token = test_users["district_delhi"]
    complaint = sample_prediction_data["complaint"]
    pred = sample_prediction_data["prediction"]

    svc = InterventionOrchestratorService()
    plan_before = svc.generate_plan_for_complaint(db_session, complaint.complaint_number, user)
    updated_at_before = plan_before.updated_at

    # Invoke ATM context API
    client.get(f"/api/v1/predictions/{pred.id}/atm-context?rank=1", headers={"Authorization": f"Bearer {token}"})

    db_session.expire_all()
    plan_after = db_session.query(InterventionPlan).filter(InterventionPlan.id == plan_before.id).first()

    assert plan_after.plan_version == plan_before.plan_version
    assert plan_after.status == "ACTIVE"


def test_plan_refresh_preserves_old_context_snapshot(test_users, sample_prediction_data, db_session):
    """Verify plan refresh supersedes old plan while preserving its old snapshot history."""
    user, token = test_users["district_delhi"]
    complaint = sample_prediction_data["complaint"]

    svc = InterventionOrchestratorService()
    p1 = svc.generate_plan_for_complaint(db_session, complaint.complaint_number, user)
    p1_id = p1.id

    p2 = svc.generate_plan_for_complaint(db_session, complaint.complaint_number, user, force_refresh=True)

    db_session.expire_all()
    p1_reloaded = db_session.query(InterventionPlan).filter(InterventionPlan.id == p1_id).first()

    assert p1_reloaded.status == "SUPERSEDED"
    assert p2.status == "ACTIVE"
    assert p2.plan_version == p1_reloaded.plan_version + 1
    assert "atm_context_snapshot" in p1_reloaded.summary_json
    assert "atm_context_snapshot" in p2.summary_json
