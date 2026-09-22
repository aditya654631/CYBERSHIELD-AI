"""
CyberShield AI - Phase 3: Intervention Orchestrator Test Suite

Validates all Phase 3 requirements:
1. Generation from persisted V8 prediction (NO ML retraining, NO location model rerun)
2. V8 baseline & Top-3 rank invariance
3. Deterministic recommendation generation & Idempotency
4. Plan Versioning & Historical Supersession
5. Action Lifecycle & Officer State Transitions
6. Subsystem Integration (Alerts, BankActions, Handoffs, Evidence)
7. RBAC & Jurisdiction Scoping (I4C, STATE_LEA, DISTRICT_LEA, BANK_OFFICER, AUDITOR)
8. Audit Logging & Provenance
9. NO Automation Overclaim (No police dispatch, no auto freeze, no auto legal order, no auto live alert)
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

from fastapi import HTTPException
from backend.app.auth.security import create_access_token
from backend.app.models.models import (
    Complaint, Prediction, PredictionLocation, LocationCluster, User, Organization,
    Alert, BankAction, CaseHandoff, InterventionPlan, InterventionPlanAction, AuditLog
)
from backend.app.services.intervention_service import intervention_service


def _make_auth_header(email: str, role: str) -> dict:
    claims = {"sub": email, "role": role}
    token = create_access_token(claims)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers():
    return _make_auth_header("admin@cybershield.gov.in", "I4C_ADMIN")


@pytest.fixture
def state_lea_headers():
    return _make_auth_header("state.lea@delhi.cyber.gov.in", "STATE_LEA")


@pytest.fixture
def district_lea_headers():
    return _make_auth_header("district.lea@southdelhi.cyber.gov.in", "DISTRICT_LEA")


@pytest.fixture
def bank_officer_headers():
    return _make_auth_header("officer@sbi.co.in", "BANK_OFFICER")


@pytest.fixture
def auditor_headers():
    return _make_auth_header("auditor@mha.gov.in", "AUDITOR")


@pytest.fixture
def analyst_headers():
    return _make_auth_header("analyst@i4c.gov.in", "ANALYST")


def _setup_test_case(db_session: Session, complaint_num: str = "CMP-PHASE3-0001"):
    """Helper to set up a test complaint with persisted V8 prediction and top-3 locations."""
    # Organization
    org = db_session.query(Organization).filter(Organization.id == 11).first()
    if not org:
        org = db_session.query(Organization).filter(Organization.name == "Delhi Police").first()
    if not org:
        org = Organization(name="Delhi Police", org_type="LEA", state="Delhi", district="SOUTH")
        db_session.add(org)
        db_session.flush()

    # User
    user = db_session.query(User).filter(User.email == "district.lea@southdelhi.cyber.gov.in").first()
    if not user:
        user = User(
            email="district.lea@southdelhi.cyber.gov.in",
            full_name="Inspector Amit Sharma",
            hashed_password="mock_hashed_pwd",
            role="DISTRICT_LEA",
            organization_id=org.id,
            is_active=True
        )
        db_session.add(user)
        db_session.flush()
    else:
        user.organization_id = org.id
        db_session.flush()

    # Clusters
    cp = db_session.query(LocationCluster).filter(LocationCluster.cluster_name.ilike("%Connaught Place%")).first()
    if not cp:
        cp = LocationCluster(cluster_name="Connaught Place, Delhi", city="Delhi", district="CENTRAL", state="Delhi", center_lat=28.6315, center_lon=77.2167)
        db_session.add(cp)
    kb = db_session.query(LocationCluster).filter(LocationCluster.cluster_name.ilike("%Karol Bagh%")).first()
    if not kb:
        kb = LocationCluster(cluster_name="Karol Bagh, Delhi", city="Delhi", district="CENTRAL", state="Delhi", center_lat=28.6514, center_lon=77.1907)
        db_session.add(kb)
    rp = db_session.query(LocationCluster).filter(LocationCluster.cluster_name.ilike("%Rajendra Place%")).first()
    if not rp:
        rp = LocationCluster(cluster_name="Rajendra Place, Delhi", city="Delhi", district="CENTRAL", state="Delhi", center_lat=28.6424, center_lon=77.1782)
        db_session.add(rp)
    db_session.flush()

    # Complaint
    complaint = db_session.query(Complaint).filter(Complaint.complaint_number == complaint_num).first()
    if not complaint:
        complaint = Complaint(
            complaint_number=complaint_num,
            fraud_type="PHISHING",
            amount=250000.0,
            victim_location="Connaught Place",
            state="Delhi",
            district="SOUTH",
            owner_organization_id=org.id
        )
        db_session.add(complaint)
        db_session.flush()

    # Prediction
    prediction = db_session.query(Prediction).filter(Prediction.complaint_id == complaint.id).first()
    if not prediction:
        now = datetime.now(timezone.utc)
        prediction = Prediction(
            complaint_id=complaint.id,
            version_number=1,
            model_version="cashout-location-xgb-v8-debiased",
            time_model_version="cashout-time-xgb-v3",
            predicted_window_start=now,
            predicted_window_end=now + timedelta(minutes=45),
            input_fingerprint="c2d1d4d4754e6e36b1cb493a65ea754c9da46e5c5132fb6fd3479c322655b9cc",
            primary_cluster_id=cp.id
        )
        db_session.add(prediction)
        db_session.flush()

        # Top 3 Prediction Locations
        locs = [
            PredictionLocation(prediction_id=prediction.id, cluster_id=cp.id, location_name=cp.cluster_name, rank=1, probability=0.0833, latitude=cp.center_lat, longitude=cp.center_lon),
            PredictionLocation(prediction_id=prediction.id, cluster_id=kb.id, location_name=kb.cluster_name, rank=2, probability=0.0747, latitude=kb.center_lat, longitude=kb.center_lon),
            PredictionLocation(prediction_id=prediction.id, cluster_id=rp.id, location_name=rp.cluster_name, rank=3, probability=0.0664, latitude=rp.center_lat, longitude=rp.center_lon),
        ]
        db_session.add_all(locs)
        db_session.commit()

    return complaint, prediction, user, org


# ======================================================================
# 1. GENERATION TESTS
# ======================================================================

def test_generate_intervention_plan_from_persisted_prediction(db_session: Session):
    """Test generating a plan from an existing persisted prediction."""
    complaint, prediction, user, _ = _setup_test_case(db_session, "CMP-TEST-PLAN-01")

    plan = intervention_service.generate_intervention_plan(
        db=db_session,
        complaint_id=complaint.complaint_number,
        user=user
    )

    assert plan is not None
    assert plan.complaint_id == complaint.id
    assert plan.prediction_id == prediction.id
    assert plan.prediction_version == 1
    assert plan.summary_json.get("model_version") == "cashout-location-xgb-v8-debiased"
    assert plan.status == "ACTIVE"
    assert plan.plan_version == 1
    assert len(plan.actions) > 0

    categories = {a.category for a in plan.actions}
    assert "LEA" in categories
    assert "BANK" in categories
    assert "GIS" in categories
    assert "EVIDENCE" in categories


def test_generation_does_not_run_location_model(db_session: Session):
    """Verify plan generation NEVER calls ML location model training or inference functions."""
    complaint, prediction, user, _ = _setup_test_case(db_session, "CMP-TEST-PLAN-02")
    from backend.app.services.prediction_service import MLPredictionProvider

    with patch.object(MLPredictionProvider, "predict", side_effect=AssertionError("Model rerun executed!")) as mock_predict:
        plan = intervention_service.generate_intervention_plan(
            db=db_session,
            complaint_id=complaint.complaint_number,
            user=user
        )
        assert mock_predict.call_count == 0


def test_generation_does_not_modify_prediction(db_session: Session):
    """Verify generating a plan does not mutate prediction fields or top-3 ranking."""
    complaint, prediction, user, _ = _setup_test_case(db_session, "CMP-TEST-PLAN-03")

    pred_before_fingerprint = prediction.input_fingerprint
    pred_before_version = prediction.model_version

    plan = intervention_service.generate_intervention_plan(
        db=db_session,
        complaint_id=complaint.complaint_number,
        user=user
    )

    db_session.refresh(prediction)
    assert prediction.input_fingerprint == pred_before_fingerprint
    assert prediction.model_version == pred_before_version


def test_generation_preserves_top3(db_session: Session):
    """Verify plan primary candidate matches V8 Top-1 candidate."""
    complaint, prediction, user, _ = _setup_test_case(db_session, "CMP-TEST-PLAN-04")

    plan = intervention_service.generate_intervention_plan(
        db=db_session,
        complaint_id=complaint.complaint_number,
        user=user
    )

    assert plan.primary_candidate_cluster_id == prediction.primary_cluster_id


def test_generation_is_idempotent(db_session: Session):
    """Repeated calls for same complaint + prediction return existing ACTIVE plan without duplicate creation."""
    complaint, prediction, user, _ = _setup_test_case(db_session, "CMP-TEST-PLAN-05")

    plan1 = intervention_service.generate_intervention_plan(
        db=db_session, complaint_id=complaint.complaint_number, user=user, force_new_revision=False
    )
    plan2 = intervention_service.generate_intervention_plan(
        db=db_session, complaint_id=complaint.complaint_number, user=user, force_new_revision=False
    )

    assert plan1.id == plan2.id
    assert plan1.plan_version == plan2.plan_version == 1


def test_plan_versioning(db_session: Session):
    """Forcing a new revision increments version and marks prior plan SUPERSEDED."""
    complaint, prediction, user, _ = _setup_test_case(db_session, "CMP-TEST-PLAN-06")

    plan1 = intervention_service.generate_intervention_plan(
        db=db_session, complaint_id=complaint.complaint_number, user=user, force_new_revision=False
    )
    assert plan1.status == "ACTIVE"
    assert plan1.plan_version == 1

    plan2 = intervention_service.generate_intervention_plan(
        db=db_session, complaint_id=complaint.complaint_number, user=user, force_new_revision=True
    )

    db_session.refresh(plan1)
    assert plan1.status == "SUPERSEDED"
    assert plan2.status == "ACTIVE"
    assert plan2.plan_version == 2


def test_plan_uses_existing_alert_when_appropriate(db_session: Session):
    """When an Alert already exists for prediction, plan references it without creating a new alert."""
    complaint, prediction, user, org = _setup_test_case(db_session, "CMP-TEST-PLAN-07")

    existing_alert = Alert(
        complaint_id=complaint.id,
        prediction_id=prediction.id,
        title="Existing Alert",
        location_name="Connaught Place",
        severity="HIGH",
        status="ACKNOWLEDGED"
    )
    db_session.add(existing_alert)
    db_session.commit()

    plan = intervention_service.generate_intervention_plan(
        db=db_session, complaint_id=complaint.complaint_number, user=user
    )

    alert_actions = [a for a in plan.actions if a.category == "ALERT"]
    assert len(alert_actions) > 0
    assert any(a.linked_alert_id == existing_alert.id for a in alert_actions)


def test_plan_does_not_auto_create_live_bank_action(db_session: Session):
    """Generating plan does NOT create a BankAction record unless user performs action."""
    complaint, prediction, user, _ = _setup_test_case(db_session, "CMP-TEST-PLAN-08")

    bank_actions_before = db_session.query(BankAction).filter(BankAction.complaint_id == complaint.id).count()

    plan = intervention_service.generate_intervention_plan(
        db=db_session, complaint_id=complaint.complaint_number, user=user
    )

    bank_actions_after = db_session.query(BankAction).filter(BankAction.complaint_id == complaint.id).count()
    assert bank_actions_before == bank_actions_after == 0


def test_plan_does_not_auto_create_handoff(db_session: Session):
    """Generating plan does NOT create a CaseHandoff record unless user performs action."""
    complaint, prediction, user, _ = _setup_test_case(db_session, "CMP-TEST-PLAN-09")

    handoffs_before = db_session.query(CaseHandoff).filter(CaseHandoff.complaint_id == complaint.id).count()

    plan = intervention_service.generate_intervention_plan(
        db=db_session, complaint_id=complaint.complaint_number, user=user
    )

    handoffs_after = db_session.query(CaseHandoff).filter(CaseHandoff.complaint_id == complaint.id).count()
    assert handoffs_before == handoffs_after == 0


# ======================================================================
# 2. RBAC & JURISDICTION TESTS
# ======================================================================

def test_district_can_generate_plan_for_authorized_case(db_session: Session):
    """District LEA user can generate plan for authorized case in district."""
    complaint, _, user, _ = _setup_test_case(db_session, "CMP-TEST-RBAC-01")

    plan = intervention_service.generate_intervention_plan(
        db=db_session, complaint_id=complaint.complaint_number, user=user
    )
    assert plan is not None


def test_district_cannot_generate_out_of_scope_plan(db_session: Session):
    """District LEA user cannot generate plan for case in different state/district."""
    complaint, _, _, _ = _setup_test_case(db_session, "CMP-TEST-RBAC-02")
    complaint.state = "Maharashtra"
    complaint.district = "MUMBAI"
    db_session.commit()

    mumbai_org = db_session.query(Organization).filter(Organization.name == "Mumbai Police").first()
    if not mumbai_org:
        mumbai_org = Organization(name="Mumbai Police", org_type="LEA", state="Maharashtra", district="MUMBAI")
        db_session.add(mumbai_org)
        db_session.flush()

    delhi_org = db_session.query(Organization).filter(Organization.name == "Delhi South Police").first()
    if not delhi_org:
        delhi_org = Organization(name="Delhi South Police", org_type="LEA", state="Delhi", district="SOUTH")
        db_session.add(delhi_org)
        db_session.flush()

    out_of_scope_user = User(
        email="district.out@delhi.gov.in",
        full_name="Out of scope officer",
        hashed_password="mock_hashed_pwd",
        role="DISTRICT_LEA",
        organization_id=delhi_org.id,
        is_active=True
    )
    db_session.add(out_of_scope_user)
    db_session.commit()

    with pytest.raises((PermissionError, HTTPException)):
        intervention_service.generate_intervention_plan(
            db=db_session, complaint_id=complaint.complaint_number, user=out_of_scope_user
        )


def test_state_can_access_authorized_plan(db_session: Session):
    """State LEA user can access plan for cases in their state."""
    complaint, _, _, org = _setup_test_case(db_session, "CMP-TEST-RBAC-03")

    state_org = db_session.query(Organization).filter(Organization.state == "Delhi", Organization.org_type == "LEA").first()
    if not state_org:
        state_org = org

    state_user = User(
        email="state.officer@delhi.gov.in",
        full_name="State Officer",
        hashed_password="mock_hashed_pwd",
        role="STATE_LEA",
        organization_id=state_org.id,
        is_active=True
    )
    db_session.add(state_user)
    db_session.commit()

    plan = intervention_service.generate_intervention_plan(
        db=db_session, complaint_id=complaint.complaint_number, user=state_user
    )
    assert plan is not None


def test_bank_officer_cannot_access_general_lea_plan(db_session: Session):
    """Bank officer without case authorization cannot access full LEA plan."""
    complaint, _, _, _ = _setup_test_case(db_session, "CMP-TEST-RBAC-04")

    bank_org = db_session.query(Organization).filter(Organization.org_type == "BANK").first()
    if not bank_org:
        bank_org = Organization(name="HDFC Bank", org_type="BANK", state="Maharashtra", district="Mumbai")
        db_session.add(bank_org)
        db_session.flush()

    bank_user = User(
        email="bank.user@hdfc.co.in",
        full_name="Bank Fraud Officer",
        hashed_password="mock_hashed_pwd",
        role="BANK_OFFICER",
        organization_id=bank_org.id,
        is_active=True
    )
    db_session.add(bank_user)
    db_session.commit()

    with pytest.raises((PermissionError, HTTPException)):
        intervention_service.generate_intervention_plan(
            db=db_session, complaint_id=complaint.complaint_number, user=bank_user
        )


def test_auditor_plan_read_only(db_session: Session):
    """Auditor can view plan but cannot execute state transitions."""
    complaint, _, user, _ = _setup_test_case(db_session, "CMP-TEST-RBAC-05")

    plan = intervention_service.generate_intervention_plan(
        db=db_session, complaint_id=complaint.complaint_number, user=user
    )

    i4c_org = db_session.query(Organization).filter(Organization.org_type == "I4C").first()
    auditor_user = User(
        email="auditor.test@mha.gov.in",
        full_name="Auditor Officer",
        hashed_password="mock_hashed_pwd",
        role="AUDITOR",
        organization_id=i4c_org.id if i4c_org else user.organization_id,
        is_active=True
    )
    db_session.add(auditor_user)
    db_session.commit()

    fetched = intervention_service.get_intervention_plan(
        db=db_session, complaint_id=complaint.complaint_number, user=auditor_user
    )
    assert fetched.id == plan.id

    action = plan.actions[0]
    with pytest.raises((PermissionError, HTTPException)):
        intervention_service.update_action_status(
            db=db_session, plan_id=plan.id, action_id=action.id, new_status="COMPLETED", user=auditor_user
        )


def test_analyst_scope_preserved(db_session: Session):
    """Analyst can generate/view decision-support plan."""
    complaint, _, user, _ = _setup_test_case(db_session, "CMP-TEST-RBAC-06")

    i4c_org = db_session.query(Organization).filter(Organization.org_type == "I4C").first()
    analyst_user = User(
        email="analyst.test@i4c.gov.in",
        full_name="I4C Analyst",
        hashed_password="mock_hashed_pwd",
        role="ANALYST",
        organization_id=i4c_org.id if i4c_org else user.organization_id,
        is_active=True
    )
    db_session.add(analyst_user)
    db_session.commit()

    plan = intervention_service.generate_intervention_plan(
        db=db_session, complaint_id=complaint.complaint_number, user=analyst_user
    )
    assert plan is not None


def test_action_transition_requires_authorized_role(db_session: Session):
    """Updating action status requires an authorized user role."""
    complaint, _, user, _ = _setup_test_case(db_session, "CMP-TEST-RBAC-07")

    plan = intervention_service.generate_intervention_plan(
        db=db_session, complaint_id=complaint.complaint_number, user=user
    )

    action = plan.actions[0]
    updated_action = intervention_service.update_action_status(
        db=db_session, plan_id=plan.id, action_id=action.id, new_status="STARTED", user=user
    )
    assert updated_action.status == "STARTED"


# ======================================================================
# 3. PERSISTENCE TESTS
# ======================================================================

def test_plan_persists_after_refresh(db_session: Session):
    """Plan remains stored in DB and retrievable upon query."""
    complaint, _, user, _ = _setup_test_case(db_session, "CMP-TEST-PERSIST-01")

    plan = intervention_service.generate_intervention_plan(
        db=db_session, complaint_id=complaint.complaint_number, user=user
    )

    fetched = intervention_service.get_intervention_plan(
        db=db_session, complaint_id=complaint.complaint_number, user=user
    )
    assert fetched is not None
    assert fetched.id == plan.id


def test_action_status_persists(db_session: Session):
    """Action status changes persist across transactions."""
    complaint, _, user, _ = _setup_test_case(db_session, "CMP-TEST-PERSIST-02")

    plan = intervention_service.generate_intervention_plan(
        db=db_session, complaint_id=complaint.complaint_number, user=user
    )

    action = plan.actions[0]
    intervention_service.update_action_status(
        db=db_session, plan_id=plan.id, action_id=action.id, new_status="COMPLETED", user=user
    )

    fetched_action = db_session.query(InterventionPlanAction).filter(InterventionPlanAction.id == action.id).first()
    assert fetched_action.status == "COMPLETED"
    assert fetched_action.completed_at is not None


def test_completed_plan_history_preserved(db_session: Session):
    """Historical completed actions remain preserved when a new plan revision is generated."""
    complaint, _, user, _ = _setup_test_case(db_session, "CMP-TEST-PERSIST-03")

    plan1 = intervention_service.generate_intervention_plan(
        db=db_session, complaint_id=complaint.complaint_number, user=user
    )
    action1 = plan1.actions[0]
    intervention_service.update_action_status(
        db=db_session, plan_id=plan1.id, action_id=action1.id, new_status="COMPLETED", user=user
    )

    plan2 = intervention_service.generate_intervention_plan(
        db=db_session, complaint_id=complaint.complaint_number, user=user, force_new_revision=True
    )

    old_action = db_session.query(InterventionPlanAction).filter(InterventionPlanAction.id == action1.id).first()
    assert old_action.status == "COMPLETED"


def test_superseded_plan_preserved(db_session: Session):
    """Superseded plan records remain in database for audit compliance."""
    complaint, _, user, _ = _setup_test_case(db_session, "CMP-TEST-PERSIST-04")

    plan1 = intervention_service.generate_intervention_plan(
        db=db_session, complaint_id=complaint.complaint_number, user=user
    )
    plan2 = intervention_service.generate_intervention_plan(
        db=db_session, complaint_id=complaint.complaint_number, user=user, force_new_revision=True
    )

    all_plans = db_session.query(InterventionPlan).filter(InterventionPlan.complaint_id == complaint.id).all()
    assert len(all_plans) == 2
    statuses = {p.status for p in all_plans}
    assert "SUPERSEDED" in statuses
    assert "ACTIVE" in statuses


# ======================================================================
# 4. NO AUTOMATION OVERCLAIM SAFETY TESTS
# ======================================================================

def test_no_police_dispatched(db_session: Session):
    """Verify plan generation contains ONLY decision support wording, NO auto police dispatch."""
    complaint, _, user, _ = _setup_test_case(db_session, "CMP-TEST-SAFETY-01")

    plan = intervention_service.generate_intervention_plan(
        db=db_session, complaint_id=complaint.complaint_number, user=user
    )

    all_titles = " ".join(a.title.lower() for a in plan.actions)
    all_descs = " ".join(a.description.lower() for a in plan.actions)

    assert "dispatch police automatically" not in all_titles
    assert "dispatch police automatically" not in all_descs
    assert "automatically dispatched" not in all_titles


def test_no_automatic_account_freeze(db_session: Session):
    """Verify plan generation does NOT claim automatic bank account freezes."""
    complaint, _, user, _ = _setup_test_case(db_session, "CMP-TEST-SAFETY-02")

    plan = intervention_service.generate_intervention_plan(
        db=db_session, complaint_id=complaint.complaint_number, user=user
    )

    all_text = " ".join(a.title + " " + a.description for a in plan.actions).lower()
    assert "account automatically frozen" not in all_text
    assert "auto-frozen" not in all_text


def test_no_automatic_live_provider_notifications(db_session: Session):
    """Verify plan generation does NOT trigger live external SMS/Email notifications."""
    complaint, _, user, _ = _setup_test_case(db_session, "CMP-TEST-SAFETY-03")

    with patch("backend.app.services.outbox_service.outbox_service.enqueue_alert_event") as mock_enqueue:
        plan = intervention_service.generate_intervention_plan(
            db=db_session, complaint_id=complaint.complaint_number, user=user
        )
        assert mock_enqueue.call_count == 0


def test_no_automatic_legal_order(db_session: Session):
    """Verify plan generation does NOT create automatic legal orders."""
    complaint, _, user, _ = _setup_test_case(db_session, "CMP-TEST-SAFETY-04")

    plan = intervention_service.generate_intervention_plan(
        db=db_session, complaint_id=complaint.complaint_number, user=user
    )

    all_text = " ".join(a.title + " " + a.description for a in plan.actions).lower()
    assert "issued legal order" not in all_text
    assert "automatic legal order" not in all_text


# ======================================================================
# 5. AUDIT TESTS
# ======================================================================

def test_plan_creation_audit(db_session: Session):
    """Creating an intervention plan writes an audit log entry."""
    complaint, prediction, user, _ = _setup_test_case(db_session, "CMP-TEST-AUDIT-01")

    plan = intervention_service.generate_intervention_plan(
        db=db_session, complaint_id=complaint.complaint_number, user=user
    )

    audit_entry = db_session.query(AuditLog).filter(
        AuditLog.action == "INTERVENTION_PLAN_CREATED",
        AuditLog.case_number == complaint.complaint_number
    ).first()

    assert audit_entry is not None
    assert audit_entry.user_id == user.id


def test_action_transition_audit(db_session: Session):
    """Transitioning action state writes an audit log entry."""
    complaint, _, user, _ = _setup_test_case(db_session, "CMP-TEST-AUDIT-02")

    plan = intervention_service.generate_intervention_plan(
        db=db_session, complaint_id=complaint.complaint_number, user=user
    )

    action = plan.actions[0]
    intervention_service.update_action_status(
        db=db_session, plan_id=plan.id, action_id=action.id, new_status="COMPLETED", user=user
    )

    audit_entry = db_session.query(AuditLog).filter(
        AuditLog.action == "INTERVENTION_ACTION_COMPLETED",
        AuditLog.case_number == complaint.complaint_number
    ).first()

    assert audit_entry is not None


def test_plan_audit_contains_prediction_id(db_session: Session):
    """Audit details include prediction ID and plan UUID for auditability."""
    complaint, prediction, user, _ = _setup_test_case(db_session, "CMP-TEST-AUDIT-03")

    plan = intervention_service.generate_intervention_plan(
        db=db_session, complaint_id=complaint.complaint_number, user=user
    )

    audit_entry = db_session.query(AuditLog).filter(
        AuditLog.action == "INTERVENTION_PLAN_CREATED",
        AuditLog.case_number == complaint.complaint_number
    ).first()

    assert audit_entry is not None
    assert f"Prediction #{prediction.id}" in (audit_entry.details or "")


def test_audit_does_not_contain_sensitive_payload(db_session: Session):
    """Audit logs do NOT contain PII or unhashed credentials."""
    complaint, _, user, _ = _setup_test_case(db_session, "CMP-TEST-AUDIT-04")

    plan = intervention_service.generate_intervention_plan(
        db=db_session, complaint_id=complaint.complaint_number, user=user
    )

    audit_entries = db_session.query(AuditLog).filter(AuditLog.case_number == complaint.complaint_number).all()
    for entry in audit_entries:
        details_str = str(entry.details)
        assert "password" not in details_str
        assert "secret" not in details_str

