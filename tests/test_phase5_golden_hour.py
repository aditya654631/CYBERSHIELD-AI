import pytest
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.models.models import (
    User,
    Organization,
    Complaint,
    Prediction,
    InterventionPlan,
    InterventionPlanAction,
)
from backend.app.auth.security import create_access_token
from backend.app.services.golden_hour_service import golden_hour_service, IST_TIMEZONE
from backend.app.services.intervention_service import intervention_service

client = TestClient(app)


# ─── FIXTURES ─────────────────────────────────────────────────────────────────

@pytest.fixture
def phase5_test_users(db_session: Session):
    """Creates test users with different RBAC roles and jurisdictions."""
    users = {}
    uid = str(uuid.uuid4())[:8]

    org_delhi = Organization(name=f"Delhi Central Police {uid}", org_type="LEA", state="Delhi", district="Central")
    org_mumbai = Organization(name=f"Mumbai Police {uid}", org_type="LEA", state="Maharashtra", district="MUMBAI")
    org_sbi = Organization(name=f"State Bank of India {uid}", org_type="BANK", state="Delhi", district="Central")
    org_i4c = Organization(name=f"I4C National Center {uid}", org_type="I4C", state="Delhi", district="NATIONAL")

    db_session.add_all([org_delhi, org_mumbai, org_sbi, org_i4c])
    db_session.commit()

    admin = User(
        email=f"admin_p5_{uid}@cybershield.gov.in",
        hashed_password="hash",
        full_name="Admin P5",
        role="I4C_ADMIN",
        badge_number=f"I4C-{uid}",
        organization_id=org_i4c.id,
        is_active=True,
    )
    delhi_district = User(
        email=f"delhi_p5_{uid}@delhipolice.gov.in",
        hashed_password="hash",
        full_name="Delhi District LEA P5",
        role="DISTRICT_LEA",
        badge_number=f"DL-DIS-{uid}",
        organization_id=org_delhi.id,
        is_active=True,
    )
    mumbai_district = User(
        email=f"mumbai_p5_{uid}@mahapolice.gov.in",
        hashed_password="hash",
        full_name="Mumbai District LEA P5",
        role="DISTRICT_LEA",
        badge_number=f"MH-DIS-{uid}",
        organization_id=org_mumbai.id,
        is_active=True,
    )
    delhi_state = User(
        email=f"delhistate_p5_{uid}@delhipolice.gov.in",
        hashed_password="hash",
        full_name="Delhi State LEA P5",
        role="STATE_LEA",
        badge_number=f"DL-STA-{uid}",
        organization_id=org_delhi.id,
        is_active=True,
    )
    auditor = User(
        email=f"auditor_p5_{uid}@cybershield.gov.in",
        hashed_password="hash",
        full_name="Auditor P5",
        role="AUDITOR",
        badge_number=f"AUD-{uid}",
        organization_id=org_i4c.id,
        is_active=True,
    )

    db_session.add_all([admin, delhi_district, mumbai_district, delhi_state, auditor])
    db_session.commit()

    for u in [admin, delhi_district, mumbai_district, delhi_state, auditor]:
        db_session.refresh(u)

    users["admin"] = (admin, create_access_token({"sub": admin.email}))
    users["delhi_district"] = (delhi_district, create_access_token({"sub": delhi_district.email}))
    users["mumbai_district"] = (mumbai_district, create_access_token({"sub": mumbai_district.email}))
    users["delhi_state"] = (delhi_state, create_access_token({"sub": delhi_state.email}))
    users["auditor"] = (auditor, create_access_token({"sub": auditor.email}))

    return users


@pytest.fixture
def sample_persisted_prediction(db_session: Session):
    """Creates a complaint and persisted Prediction with time-window."""
    uid = str(uuid.uuid4())[:8]
    base_time = datetime(2026, 9, 23, 10, 0, 0, tzinfo=timezone.utc)

    complaint = Complaint(
        complaint_number=f"CMP-P5-{uid}",
        fraud_type="ATM Cashout Fraud",
        amount=250000.0,
        victim_name="Vikram Seth",
        victim_location="Connaught Place, Central Delhi",
        state="Delhi",
        district="Central",
        payment_channel="ATM",
        reported_at=base_time,
        incident_time=base_time - timedelta(minutes=30),
        risk_level="HIGH",
        risk_score=0.88,
        prediction_status="AVAILABLE",
        case_status="ACTIVE",
        created_at=base_time + timedelta(minutes=5),
    )
    db_session.add(complaint)
    db_session.commit()
    db_session.refresh(complaint)

    # Window from T+60m to T+180m
    window_start = base_time + timedelta(hours=2) # 12:00 UTC
    window_end = base_time + timedelta(hours=4)   # 14:00 UTC

    pred = Prediction(
        complaint_id=complaint.id,
        version_number=1,
        prediction_mode="trained_ml",
        model_version="cashout-location-xgb-v8-debiased",
        time_model_version="cashout-time-xgb-v3",
        risk_level="HIGH",
        risk_score=0.88,
        ml_score=0.85,
        primary_cluster_id=1,
        predicted_window_start=window_start,
        predicted_window_end=window_end,
        created_at=base_time + timedelta(minutes=10),
    )
    db_session.add(pred)
    db_session.commit()
    db_session.refresh(pred)

    return complaint, pred, base_time


# ─── UNIT & INTEGRATION TESTS ─────────────────────────────────────────────────

def test_golden_hour_uses_persisted_time_prediction(db_session: Session, phase5_test_users, sample_persisted_prediction):
    """Validates that GoldenHourService reads strictly from persisted Prediction columns."""
    complaint, pred, base_time = sample_persisted_prediction
    user, token = phase5_test_users["admin"]

    result = golden_hour_service.get_golden_hour_for_prediction(
        db=db_session,
        prediction_id=pred.id,
        user=user,
        now_dt=base_time + timedelta(minutes=20)
    )

    assert result["prediction_id"] == pred.id
    assert result["complaint_id"] == complaint.id
    assert result["complaint_number"] == complaint.complaint_number
    assert result["source"]["model_version"] == "cashout-time-xgb-v3"
    assert result["source"]["derived_from_persisted_prediction"] is True
    assert result["window"]["start"].startswith("2026-09-23T12:00:00")
    assert result["window"]["end"].startswith("2026-09-23T14:00:00")


def test_golden_hour_does_not_run_time_model(db_session: Session, phase5_test_users, sample_persisted_prediction):
    """Guardrail: Ensure zero ML inference or time model calls happen during GoldenHour view fetching."""
    complaint, pred, base_time = sample_persisted_prediction
    user, token = phase5_test_users["admin"]

    with patch("backend.app.services.prediction_service.MLPredictionProvider.predict") as mock_predict:
        result = golden_hour_service.get_golden_hour_for_prediction(
            db=db_session,
            prediction_id=pred.id,
            user=user,
            now_dt=base_time
        )
        assert mock_predict.call_count == 0
        assert result["window"]["start"] is not None


def test_golden_hour_does_not_run_v8(db_session: Session, phase5_test_users, sample_persisted_prediction):
    """Guardrail: Ensure V8 location ranker is NOT run during GoldenHour calculation."""
    complaint, pred, base_time = sample_persisted_prediction
    user, token = phase5_test_users["admin"]

    with patch("backend.app.services.prediction_service.PredictionService.predict_complaint") as mock_v8_predict:
        result = golden_hour_service.get_golden_hour_for_prediction(
            db=db_session,
            prediction_id=pred.id,
            user=user,
            now_dt=base_time
        )
        assert mock_v8_predict.call_count == 0


def test_operational_states_progression(db_session: Session, phase5_test_users, sample_persisted_prediction):
    """
    Tests exact state transitions based on reference time relative to predicted window:
    - PLANNING (> 60m before start)
    - ELEVATED (30 - 60m before start)
    - HIGH_URGENCY (0 - 30m before start)
    - WINDOW_ACTIVE (within window)
    - WINDOW_PASSED (after window)
    """
    complaint, pred, base_time = sample_persisted_prediction
    user, token = phase5_test_users["admin"]
    # Window is 12:00 to 14:00 UTC (base_time is 10:00 UTC)

    # 1. PLANNING: At 10:30 UTC -> 90 mins before start
    res_plan = golden_hour_service.get_golden_hour_for_prediction(
        db=db_session, prediction_id=pred.id, user=user,
        now_dt=datetime(2026, 9, 23, 10, 30, 0, tzinfo=timezone.utc)
    )
    assert res_plan["status"] == "PLANNING"
    assert res_plan["minutes_until_start"] == 90

    # 2. ELEVATED: At 11:15 UTC -> 45 mins before start
    res_elev = golden_hour_service.get_golden_hour_for_prediction(
        db=db_session, prediction_id=pred.id, user=user,
        now_dt=datetime(2026, 9, 23, 11, 15, 0, tzinfo=timezone.utc)
    )
    assert res_elev["status"] == "ELEVATED"
    assert res_elev["minutes_until_start"] == 45

    # 3. HIGH_URGENCY: At 11:45 UTC -> 15 mins before start
    res_urg = golden_hour_service.get_golden_hour_for_prediction(
        db=db_session, prediction_id=pred.id, user=user,
        now_dt=datetime(2026, 9, 23, 11, 45, 0, tzinfo=timezone.utc)
    )
    assert res_urg["status"] == "HIGH_URGENCY"
    assert res_urg["minutes_until_start"] == 15

    # 4. WINDOW_ACTIVE: At 13:00 UTC -> inside window (12:00 - 14:00)
    res_act = golden_hour_service.get_golden_hour_for_prediction(
        db=db_session, prediction_id=pred.id, user=user,
        now_dt=datetime(2026, 9, 23, 13, 0, 0, tzinfo=timezone.utc)
    )
    assert res_act["status"] == "WINDOW_ACTIVE"
    assert res_act["minutes_until_end"] == 60

    # 5. WINDOW_PASSED: At 14:15 UTC -> past window end (14:00)
    res_pass = golden_hour_service.get_golden_hour_for_prediction(
        db=db_session, prediction_id=pred.id, user=user,
        now_dt=datetime(2026, 9, 23, 14, 15, 0, tzinfo=timezone.utc)
    )
    assert res_pass["status"] == "WINDOW_PASSED"
    assert res_pass["minutes_until_end"] == -15


def test_timezone_formatting_ist(db_session: Session, phase5_test_users, sample_persisted_prediction):
    """Validates strict Asia/Kolkata (IST) display and conversion."""
    complaint, pred, base_time = sample_persisted_prediction
    user, token = phase5_test_users["admin"]

    # base_time: 10:00 UTC = 15:30 IST
    # window_start: 12:00 UTC = 17:30 IST
    # window_end: 14:00 UTC = 19:30 IST
    result = golden_hour_service.get_golden_hour_for_prediction(
        db=db_session, prediction_id=pred.id, user=user,
        now_dt=datetime(2026, 9, 23, 11, 0, 0, tzinfo=timezone.utc)
    )

    assert result["timezone"] == "Asia/Kolkata"
    assert result["window"]["start_ist"] == "23 Sep 2026, 17:30 IST"
    assert result["window"]["end_ist"] == "23 Sep 2026, 19:30 IST"
    assert result["window"]["start_time_ist"] == "17:30 IST"
    assert result["window"]["end_time_ist"] == "19:30 IST"
    # Offsets relative to complaint reported_at (10:00 UTC)
    assert result["window"]["start_offset_minutes"] == 120
    assert result["window"]["end_offset_minutes"] == 240


def test_non_fabrication_contract(db_session: Session, phase5_test_users, sample_persisted_prediction):
    """
    Contract test: Verifies that NO fabricated minute-by-minute hazard distributions
    or artificial likelihood curves exist in the response payload.
    """
    complaint, pred, base_time = sample_persisted_prediction
    user, token = phase5_test_users["admin"]

    result = golden_hour_service.get_golden_hour_for_prediction(
        db=db_session, prediction_id=pred.id, user=user, now_dt=base_time
    )

    # Assert forbidden speculative fields are completely absent
    assert "hazard_probability" not in result
    assert "minute_probability" not in result
    assert "hazard_curve" not in result
    assert "likelihood_distribution" not in result
    assert "hazard_rate" not in result

    # Check disclaimer exists
    assert "disclaimer" in result
    assert "persisted cash-out time prediction" in result["disclaimer"]
    assert result["source"]["model_version"] == "cashout-time-xgb-v3"


def test_missing_time_prediction_handling(db_session: Session, phase5_test_users, sample_persisted_prediction):
    """When a prediction lacks predicted_window_start/end, returns GOLDEN_HOUR_UNAVAILABLE gracefully."""
    complaint, pred, base_time = sample_persisted_prediction
    user, token = phase5_test_users["admin"]

    with patch.object(pred, "predicted_window_start", None):
        result = golden_hour_service.get_golden_hour_for_prediction(
            db=db_session, prediction_id=pred.id, user=user
        )

        assert result["status"] == "GOLDEN_HOUR_UNAVAILABLE"
        assert result["window"]["start"] is None
        assert result["minutes_until_start"] is None
        assert "Operational time window unavailable" in result["disclaimer"]


def test_rbac_jurisdiction_isolation(db_session: Session, phase5_test_users, sample_persisted_prediction):
    """
    Validates RBAC multi-tenant jurisdiction rules:
    - Delhi District LEA can access Delhi complaint.
    - Mumbai District LEA is blocked (404/denied).
    - Delhi State LEA can access Delhi complaint.
    - I4C Admin can access any complaint.
    - Auditor can access read-only.
    """
    complaint, pred, base_time = sample_persisted_prediction

    # 1. I4C Admin -> 200 OK
    _, admin_token = phase5_test_users["admin"]
    res_admin = client.get(
        f"/api/v1/predictions/{pred.id}/golden-hour",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_admin.status_code == 200
    assert res_admin.json()["prediction_id"] == pred.id

    # 2. Delhi District LEA (Same district/state) -> 200 OK
    _, delhi_token = phase5_test_users["delhi_district"]
    res_delhi = client.get(
        f"/api/v1/predictions/{pred.id}/golden-hour",
        headers={"Authorization": f"Bearer {delhi_token}"}
    )
    assert res_delhi.status_code == 200

    # 3. Delhi State LEA (Same state) -> 200 OK
    _, state_token = phase5_test_users["delhi_state"]
    res_state = client.get(
        f"/api/v1/predictions/{pred.id}/golden-hour",
        headers={"Authorization": f"Bearer {state_token}"}
    )
    assert res_state.status_code == 200

    # 4. Auditor -> 200 OK
    _, auditor_token = phase5_test_users["auditor"]
    res_auditor = client.get(
        f"/api/v1/predictions/{pred.id}/golden-hour",
        headers={"Authorization": f"Bearer {auditor_token}"}
    )
    assert res_auditor.status_code == 200

    # 5. Mumbai District LEA (Different jurisdiction) -> 404 Not Found (Access Denied)
    _, mumbai_token = phase5_test_users["mumbai_district"]
    res_mumbai = client.get(
        f"/api/v1/predictions/{pred.id}/golden-hour",
        headers={"Authorization": f"Bearer {mumbai_token}"}
    )
    assert res_mumbai.status_code == 404


def test_api_deterministic_clock_via_now_iso(db_session: Session, phase5_test_users, sample_persisted_prediction):
    """Tests that now_iso query param allows exact clock testing via REST API."""
    complaint, pred, base_time = sample_persisted_prediction
    _, admin_token = phase5_test_users["admin"]

    # Window: 12:00 to 14:00 UTC. Test with now_iso at 11:50 UTC (10 mins before start)
    iso_str = "2026-09-23T11:50:00+00:00"
    res = client.get(
        f"/api/v1/predictions/{pred.id}/golden-hour?now_iso={iso_str}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "HIGH_URGENCY"
    assert data["minutes_until_start"] == 10


def test_intervention_plan_golden_hour_snapshot(db_session: Session, phase5_test_users, sample_persisted_prediction):
    """
    Validates that:
    1. Newly generated InterventionPlan captures golden_hour_snapshot in summary_json.
    2. Action card REVIEW_GOLDEN_HOUR_WINDOW is present.
    3. Existing plans are not mutated.
    """
    complaint, pred, base_time = sample_persisted_prediction
    user, token = phase5_test_users["admin"]

    # Create historical plan without mutation
    historical_plan = InterventionPlan(
        complaint_id=complaint.id,
        prediction_id=pred.id,
        status="COMPLETED",
        summary_json={"created_version": "v4_legacy", "actions_count": 1},
        created_at=base_time - timedelta(days=1),
    )
    db_session.add(historical_plan)
    db_session.commit()
    db_session.refresh(historical_plan)
    orig_summary = dict(historical_plan.summary_json)

    # Generate new plan using orchestrator
    plan = intervention_service.generate_plan_for_complaint(
        db=db_session,
        complaint_id_or_num=str(complaint.id),
        user=user,
        force_refresh=True
    )

    assert plan is not None
    assert "golden_hour_snapshot" in plan.summary_json
    gh_snapshot = plan.summary_json["golden_hour_snapshot"]
    assert gh_snapshot["window_start_ist"] is not None
    assert gh_snapshot["window_end_ist"] is not None
    assert gh_snapshot["status"] in ["PLANNING", "ELEVATED", "HIGH_URGENCY", "WINDOW_ACTIVE", "WINDOW_PASSED"]

    # Check for REVIEW_GOLDEN_HOUR_WINDOW action card
    actions = db_session.query(InterventionPlanAction).filter(
        InterventionPlanAction.plan_id == plan.id
    ).all()
    action_types = [a.action_type for a in actions]
    assert "REVIEW_GOLDEN_HOUR_WINDOW" in action_types

    # Ensure historical plan was NOT mutated
    db_session.refresh(historical_plan)
    assert historical_plan.summary_json == orig_summary
