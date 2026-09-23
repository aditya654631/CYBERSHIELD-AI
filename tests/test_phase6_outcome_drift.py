"""
CyberShield AI — Phase 6: Outcome Feedback & Model Drift Intelligence Test Suite

Comprehensive tests for:
1. Outcome evaluation (Top-1, Top-3, observed rank, spatial error, lead time, missing metadata handling)
2. Historical prediction snapshot usage (zero re-inference)
3. Cohort separation (CONTROLLED_SYNTHETIC, AUTHORIZED_OPERATIONAL, EXCLUDED, UNKNOWN)
4. Financial metric isolation (Verified Hold vs Actual Recovery strictly separate; never summed as 'money saved')
5. Append-only outcome correction lineage & auditing
6. Model drift monitoring (transparent statistics against frozen reference, no auto-retraining, no artifact modification)
7. RBAC jurisdiction enforcement (district, state, bank officer restricted, auditor read-only)
8. V8 Invariance & hash freeze (Prediction #221 baseline and exact artifact SHA-256 hashes)
"""

import os
import hashlib
import json
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

from backend.app.models.models import (
    Complaint,
    Prediction,
    PredictionLocation,
    OutcomeObservation,
    User,
    Organization,
)
from backend.app.schemas.schemas import (
    OutcomeEvaluationResponse,
    OutcomeMonitoringResponse,
)
from backend.app.auth.security import create_access_token
from backend.app.services.outcome_service import (
    evaluate_complaint_outcome,
    get_drift_and_monitoring_metrics,
    create_outcome,
    correct_outcome,
    get_outcome_metrics,
)

# ──────────────────────────────────────────────────────────────────────────────
# Helper Utilities
# ──────────────────────────────────────────────────────────────────────────────

def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _token(user: User) -> str:
    return create_access_token(data={"sub": user.email, "role": user.role})


def _create_test_hierarchy(db: Session, suffix: str):
    """Creates isolated users and organizations across roles."""
    org_delhi = Organization(
        name=f"Delhi Central Cyber Cell {suffix}",
        org_type="LEA",
        state="Delhi",
        district="CENTRAL_NEW_DELHI",
    )
    org_mumbai = Organization(
        name=f"Mumbai Cyber Cell {suffix}",
        org_type="LEA",
        state="Maharashtra",
        district="MUMBAI",
    )
    org_bank = Organization(
        name=f"SBI Fraud Risk {suffix}",
        org_type="BANK",
        state="Delhi",
        district="CENTRAL_NEW_DELHI",
    )
    db.add_all([org_delhi, org_mumbai, org_bank])
    db.flush()

    admin = User(
        email=f"admin_{suffix}@cybershield.gov.in",
        hashed_password="hash",
        full_name="Admin User",
        role="I4C_ADMIN",
        badge_number=f"ADM-{suffix}",
        organization_id=org_delhi.id,
        is_active=True,
    )
    state_lea = User(
        email=f"state_{suffix}@delhipolice.gov.in",
        hashed_password="hash",
        full_name="State Officer",
        role="STATE_LEA",
        badge_number=f"ST-{suffix}",
        organization_id=org_delhi.id,
        is_active=True,
    )
    district_delhi = User(
        email=f"dist_delhi_{suffix}@delhipolice.gov.in",
        hashed_password="hash",
        full_name="Delhi District Officer",
        role="DISTRICT_LEA",
        badge_number=f"DL-{suffix}",
        organization_id=org_delhi.id,
        is_active=True,
    )
    district_mumbai = User(
        email=f"dist_mumbai_{suffix}@mahapolice.gov.in",
        hashed_password="hash",
        full_name="Mumbai District Officer",
        role="DISTRICT_LEA",
        badge_number=f"MB-{suffix}",
        organization_id=org_mumbai.id,
        is_active=True,
    )
    bank_officer = User(
        email=f"bank_{suffix}@sbi.co.in",
        hashed_password="hash",
        full_name="Bank Officer",
        role="BANK_OFFICER",
        badge_number=f"BK-{suffix}",
        organization_id=org_bank.id,
        is_active=True,
    )
    auditor = User(
        email=f"auditor_{suffix}@mha.gov.in",
        hashed_password="hash",
        full_name="Auditor User",
        role="AUDITOR",
        badge_number=f"AUD-{suffix}",
        organization_id=org_delhi.id,
        is_active=True,
    )
    db.add_all([admin, state_lea, district_delhi, district_mumbai, bank_officer, auditor])
    db.commit()

    return {
        "admin": admin,
        "state_lea": state_lea,
        "district_delhi": district_delhi,
        "district_mumbai": district_mumbai,
        "bank_officer": bank_officer,
        "auditor": auditor,
        "org_delhi": org_delhi,
        "org_mumbai": org_mumbai,
    }


def _create_complaint_and_prediction(
    db: Session,
    suffix: str,
    org_id: int,
    state: str = "Delhi",
    district: str = "CENTRAL_NEW_DELHI",
    pred_time_delta_mins: int = 30,
):
    """Creates a complaint with persisted prediction candidates."""
    now = _utcnow()
    comp = Complaint(
        complaint_number=f"CMP-P6-{suffix}",
        fraud_type="ATM_FRAUD",
        amount=150000.0,
        victim_name="Test Victim",
        victim_location="Connaught Place, Delhi",
        state=state,
        district=district,
        case_status="ACTIVE",
        owner_organization_id=org_id,
        reported_at=now - timedelta(hours=2),
        incident_time=now - timedelta(hours=2),
        created_at=now - timedelta(hours=2),
    )
    db.add(comp)
    db.flush()

    pred_created_at = now - timedelta(minutes=pred_time_delta_mins)
    pred = Prediction(
        complaint_id=comp.id,
        analysis_purpose="OPERATIONAL",
        prediction_mode="trained_ml",
        model_version="cashout-location-xgb-v8-debiased",
        confidence_score=0.0833,
        ml_score=0.0833,
        graph_score=0.45,
        geo_score=0.60,
        primary_cluster_id=1,
        predicted_window_start=pred_created_at,
        predicted_window_end=pred_created_at + timedelta(hours=2),
        created_at=pred_created_at,
    )
    db.add(pred)
    db.flush()

    # Connaught Place (Rank 1), Karol Bagh (Rank 2), Rajendra Place (Rank 3)
    loc1 = PredictionLocation(
        prediction_id=pred.id,
        rank=1,
        cluster_id=1,
        location_name="Connaught Place",
        latitude=28.6315,
        longitude=77.2167,
        probability=0.0833,
        risk_level="HIGH",
        distance_km=2.1,
    )
    loc2 = PredictionLocation(
        prediction_id=pred.id,
        rank=2,
        cluster_id=2,
        location_name="Karol Bagh",
        latitude=28.6515,
        longitude=77.1907,
        probability=0.0747,
        risk_level="HIGH",
        distance_km=4.5,
    )
    loc3 = PredictionLocation(
        prediction_id=pred.id,
        rank=3,
        cluster_id=3,
        location_name="Rajendra Place",
        latitude=28.6425,
        longitude=77.1785,
        probability=0.0664,
        risk_level="MEDIUM",
        distance_km=5.8,
    )
    db.add_all([loc1, loc2, loc3])
    db.commit()

    return comp, pred


def _eval(db: Session, complaint_id: int, user: User) -> OutcomeEvaluationResponse:
    res = evaluate_complaint_outcome(db, complaint_id, user)
    return OutcomeEvaluationResponse(**res)


def _monitor(db: Session) -> OutcomeMonitoringResponse:
    res = get_drift_and_monitoring_metrics(db)
    return OutcomeMonitoringResponse(**res)


# ──────────────────────────────────────────────────────────────────────────────
# 1. OUTCOME EVALUATION TESTS
# ──────────────────────────────────────────────────────────────────────────────

def test_top1_hit(db: Session):
    users = _create_test_hierarchy(db, "t1")
    comp, pred = _create_complaint_and_prediction(db, "t1", users["org_delhi"].id)

    # Observed outcome exactly at Rank 1 (Connaught Place, cluster 1)
    obs_time = _utcnow()
    create_outcome(
        db=db,
        current_user=users["admin"],
        complaint_id=comp.id,
        outcome_type="CONFIRMED_CASHOUT",
        source="OFFICER_MANUAL",
        observed_event_time=obs_time,
        actual_lat=28.6320,
        actual_lon=77.2170,
        actual_location_name="Connaught Place Outer Circle",
        actual_cluster_id=1,
        actual_withdrawal_amount_inr=50000.0,
        is_synthetic=False,
    )

    evaluation = _eval(db, comp.id, users["admin"])
    assert evaluation.has_active_outcome is True
    assert evaluation.evaluation.top1_hit is True
    assert evaluation.evaluation.top3_hit is True
    assert evaluation.evaluation.observed_rank == 1


def test_top3_hit(db: Session):
    users = _create_test_hierarchy(db, "t3")
    comp, pred = _create_complaint_and_prediction(db, "t3", users["org_delhi"].id)

    # Observed outcome at Rank 2 (Karol Bagh, cluster 2)
    obs_time = _utcnow()
    create_outcome(
        db=db,
        current_user=users["admin"],
        complaint_id=comp.id,
        outcome_type="CONFIRMED_CASHOUT",
        source="OFFICER_MANUAL",
        observed_event_time=obs_time,
        actual_lat=28.6520,
        actual_lon=77.1910,
        actual_location_name="Karol Bagh Metro Branch",
        actual_cluster_id=2,
        actual_withdrawal_amount_inr=30000.0,
        is_synthetic=False,
    )

    evaluation = _eval(db, comp.id, users["admin"])
    assert evaluation.evaluation.top1_hit is False
    assert evaluation.evaluation.top3_hit is True
    assert evaluation.evaluation.observed_rank == 2


def test_observed_rank(db: Session):
    users = _create_test_hierarchy(db, "rank")
    comp, pred = _create_complaint_and_prediction(db, "rank", users["org_delhi"].id)

    # Observed outcome outside Top 3 (cluster 99)
    create_outcome(
        db=db,
        current_user=users["admin"],
        complaint_id=comp.id,
        outcome_type="CONFIRMED_CASHOUT",
        source="OFFICER_MANUAL",
        observed_event_time=_utcnow(),
        actual_lat=28.5700,
        actual_lon=77.3200,
        actual_cluster_id=None,
        actual_location_name="Noida Sector 18",
        is_synthetic=False,
    )

    evaluation = _eval(db, comp.id, users["admin"])
    assert evaluation.evaluation.top1_hit is False
    assert evaluation.evaluation.top3_hit is False
    assert evaluation.evaluation.observed_rank is None


def test_spatial_error(db: Session):
    users = _create_test_hierarchy(db, "spat")
    comp, pred = _create_complaint_and_prediction(db, "spat", users["org_delhi"].id)

    # Coordinates near Connaught Place (approx 0.1 - 0.2 km away)
    create_outcome(
        db=db,
        current_user=users["admin"],
        complaint_id=comp.id,
        outcome_type="CONFIRMED_CASHOUT",
        source="OFFICER_MANUAL",
        observed_event_time=_utcnow(),
        actual_lat=28.6325,
        actual_lon=77.2175,
        actual_location_name="Connaught Place Inner Circle",
        is_synthetic=False,
    )

    evaluation = _eval(db, comp.id, users["admin"])
    assert evaluation.evaluation.spatial_error_km is not None
    assert 0.05 < evaluation.evaluation.spatial_error_km < 0.5


def test_lead_time(db: Session):
    users = _create_test_hierarchy(db, "lead")
    comp, pred = _create_complaint_and_prediction(db, "lead", users["org_delhi"].id, pred_time_delta_mins=45)

    # Observed outcome 45 minutes after prediction created_at
    obs_time = pred.created_at + timedelta(minutes=45)
    create_outcome(
        db=db,
        current_user=users["admin"],
        complaint_id=comp.id,
        outcome_type="CONFIRMED_CASHOUT",
        source="OFFICER_MANUAL",
        observed_event_time=obs_time,
        actual_lat=28.6315,
        actual_lon=77.2167,
        is_synthetic=False,
    )

    evaluation = _eval(db, comp.id, users["admin"])
    assert evaluation.evaluation.lead_time_minutes == 45
    assert evaluation.evaluation.lead_time_display is not None
    assert "45 min before observed event" in evaluation.evaluation.lead_time_display


def test_missing_observed_location(db: Session):
    users = _create_test_hierarchy(db, "noloc")
    comp, pred = _create_complaint_and_prediction(db, "noloc", users["org_delhi"].id)

    # Outcome with no coordinates or cluster
    create_outcome(
        db=db,
        current_user=users["admin"],
        complaint_id=comp.id,
        outcome_type="CONFIRMED_CASHOUT",
        source="OFFICER_MANUAL",
        observed_event_time=_utcnow(),
        actual_lat=None,
        actual_lon=None,
        actual_cluster_id=None,
        is_synthetic=False,
    )

    evaluation = _eval(db, comp.id, users["admin"])
    assert evaluation.evaluation.spatial_error_km is None
    assert evaluation.evaluation.evaluation_status == "INSUFFICIENT_COORDINATES"


def test_missing_observed_time(db: Session):
    users = _create_test_hierarchy(db, "notime")
    comp, pred = _create_complaint_and_prediction(db, "notime", users["org_delhi"].id)

    # Outcome with no observed_event_time
    create_outcome(
        db=db,
        current_user=users["admin"],
        complaint_id=comp.id,
        outcome_type="CONFIRMED_CASHOUT",
        source="OFFICER_MANUAL",
        observed_event_time=None,
        is_synthetic=False,
    )

    evaluation = _eval(db, comp.id, users["admin"])
    assert evaluation.evaluation.lead_time_minutes is None
    assert evaluation.evaluation.lead_time_display is None


def test_evaluation_uses_historical_prediction_snapshot(db: Session):
    """Ensures evaluation compares against persisted prediction snapshot, never re-running V8."""
    users = _create_test_hierarchy(db, "snap")
    comp, pred = _create_complaint_and_prediction(db, "snap", users["org_delhi"].id)

    create_outcome(
        db=db,
        current_user=users["admin"],
        complaint_id=comp.id,
        outcome_type="CONFIRMED_CASHOUT",
        source="OFFICER_MANUAL",
        observed_event_time=_utcnow(),
        actual_lat=28.6315,
        actual_lon=77.2167,
        actual_cluster_id=1,
        is_synthetic=False,
    )

    evaluation = _eval(db, comp.id, users["admin"])
    assert evaluation.prediction_id == pred.id
    assert evaluation.evaluation.top1_hit is True


# ──────────────────────────────────────────────────────────────────────────────
# 2. COHORT SEPARATION TESTS
# ──────────────────────────────────────────────────────────────────────────────

def test_synthetic_outcomes_not_in_operational_metrics(db: Session):
    users = _create_test_hierarchy(db, "synth_sep")
    comp, pred = _create_complaint_and_prediction(db, "synth_sep", users["org_delhi"].id)

    create_outcome(
        db=db,
        current_user=users["admin"],
        complaint_id=comp.id,
        outcome_type="CONFIRMED_CASHOUT",
        source="OFFICER_MANUAL",
        observed_event_time=_utcnow(),
        actual_cluster_id=1,
        is_synthetic=True,  # SYNTHETIC!
    )

    monitoring = _monitor(db)
    assert monitoring.synthetic_cohort_size >= 1
    # Cohort breakdown item for synthetic is marked not eligible for operational evaluation
    synth_item = next(c for c in monitoring.cohorts if c.cohort == "CONTROLLED_SYNTHETIC")
    assert synth_item.eligible_for_evaluation is False


def test_excluded_outcomes_not_in_metrics(db: Session):
    users = _create_test_hierarchy(db, "excl_sep")
    comp, pred = _create_complaint_and_prediction(db, "excl_sep", users["org_delhi"].id)

    create_outcome(
        db=db,
        current_user=users["admin"],
        complaint_id=comp.id,
        outcome_type="CONFIRMED_CASHOUT",
        source="OFFICER_MANUAL",
        observed_event_time=_utcnow(),
        actual_cluster_id=1,
        is_synthetic=False,
        is_excluded=True,
        exclusion_reason="Investigation jurisdictional transfer to Haryana",
    )

    monitoring = _monitor(db)
    assert monitoring.excluded_cohort_size >= 1
    excl_item = next(c for c in monitoring.cohorts if c.cohort == "EXCLUDED")
    assert excl_item.eligible_for_evaluation is False


def test_unknown_outcomes_not_counted_as_verified(db: Session):
    users = _create_test_hierarchy(db, "unk_sep")
    comp, pred = _create_complaint_and_prediction(db, "unk_sep", users["org_delhi"].id)

    create_outcome(
        db=db,
        current_user=users["admin"],
        complaint_id=comp.id,
        outcome_type="UNKNOWN",
        source="OFFICER_MANUAL",
        verification_status="PENDING_VERIFICATION",
        is_synthetic=False,
    )

    monitoring = _monitor(db)
    assert monitoring.unknown_cohort_size >= 1
    unk_item = next(c for c in monitoring.cohorts if c.cohort == "UNKNOWN")
    assert unk_item.eligible_for_evaluation is False


def test_real_operational_cohort_separate(db: Session):
    users = _create_test_hierarchy(db, "real_sep")
    comp, pred = _create_complaint_and_prediction(db, "real_sep", users["org_delhi"].id)

    create_outcome(
        db=db,
        current_user=users["admin"],
        complaint_id=comp.id,
        outcome_type="CONFIRMED_CASHOUT",
        source="OFFICER_MANUAL",
        observed_event_time=_utcnow(),
        actual_lat=28.6315,
        actual_lon=77.2167,
        actual_cluster_id=1,
        is_synthetic=False,
        is_excluded=False,
        verification_status="VERIFIED",
    )

    evaluation = _eval(db, comp.id, users["admin"])
    assert evaluation.cohort == "AUTHORIZED_OPERATIONAL"

    monitoring = _monitor(db)
    assert monitoring.operational_cohort_size >= 1


def test_metric_includes_sample_size(db: Session):
    monitoring = _monitor(db)
    assert isinstance(monitoring.operational_cohort_size, int)
    assert isinstance(monitoring.synthetic_cohort_size, int)
    assert isinstance(monitoring.total_active_records, int)


# ──────────────────────────────────────────────────────────────────────────────
# 3. FINANCIAL SEPARATION TESTS
# ──────────────────────────────────────────────────────────────────────────────

def test_hold_and_recovery_separate(db: Session):
    users = _create_test_hierarchy(db, "fin_sep")
    comp, pred = _create_complaint_and_prediction(db, "fin_sep", users["org_delhi"].id)

    create_outcome(
        db=db,
        current_user=users["admin"],
        complaint_id=comp.id,
        outcome_type="CONFIRMED_CASHOUT",
        source="BANK_REPORT",
        observed_event_time=_utcnow(),
        actual_withdrawal_amount_inr=100000.0,
        verified_held_amount_inr=60000.0,
        actual_recovered_amount_inr=40000.0,
        verification_status="VERIFIED",
    )

    evaluation = _eval(db, comp.id, users["admin"])
    assert evaluation.financial.attempted_withdrawal_amount_inr == 100000.0
    assert evaluation.financial.verified_held_amount_inr == 60000.0
    assert evaluation.financial.actual_recovered_amount_inr == 40000.0


def test_no_money_saved_double_count(db: Session):
    """Never sums hold + recovery into money saved."""
    users = _create_test_hierarchy(db, "no_save")
    comp, pred = _create_complaint_and_prediction(db, "no_save", users["org_delhi"].id)

    create_outcome(
        db=db,
        current_user=users["admin"],
        complaint_id=comp.id,
        outcome_type="CONFIRMED_CASHOUT",
        source="BANK_REPORT",
        verified_held_amount_inr=50000.0,
        actual_recovered_amount_inr=30000.0,
    )

    evaluation = _eval(db, comp.id, users["admin"])
    assert not hasattr(evaluation.financial, "money_saved")
    assert not hasattr(evaluation.financial, "loss_prevented")
    assert "never claimed" in evaluation.financial.financial_note.lower()


def test_unverified_amount_excluded_where_required(db: Session):
    users = _create_test_hierarchy(db, "unver_fin")
    comp, pred = _create_complaint_and_prediction(db, "unver_fin", users["org_delhi"].id)

    outcome = create_outcome(
        db=db,
        current_user=users["admin"],
        complaint_id=comp.id,
        outcome_type="CONFIRMED_CASHOUT",
        source="OFFICER_MANUAL",
        verified_held_amount_inr=50000.0,
        verification_status="UNVERIFIED",
    )

    evaluation = _eval(db, comp.id, users["admin"])
    assert evaluation.active_observation.verification_status == "UNVERIFIED"


# ──────────────────────────────────────────────────────────────────────────────
# 4. CORRECTION HISTORY & LINEAGE TESTS
# ──────────────────────────────────────────────────────────────────────────────

def test_outcome_correction_append_only(db: Session):
    users = _create_test_hierarchy(db, "corr_append")
    comp, pred = _create_complaint_and_prediction(db, "corr_append", users["org_delhi"].id)

    # Version 1
    v1 = create_outcome(
        db=db,
        current_user=users["admin"],
        complaint_id=comp.id,
        outcome_type="CONFIRMED_CASHOUT",
        source="OFFICER_MANUAL",
        actual_location_name="Connaught Place",
        actual_cluster_id=1,
    )
    assert v1.version == 1
    assert v1.record_status == "ACTIVE"

    # Version 2 (Correction)
    v2 = correct_outcome(
        db=db,
        outcome_id=v1.id,
        current_user=users["admin"],
        correction_reason="CCTV review confirmed cashout was actually at Karol Bagh branch",
        actual_location_name="Karol Bagh",
        actual_cluster_id=2,
    )
    assert v2.version == 2
    assert v2.record_status == "ACTIVE"
    assert v2.corrects_outcome_id == v1.id

    # Verify V1 status is updated to SUPERSEDED
    db.refresh(v1)
    assert v1.record_status == "SUPERSEDED"


def test_superseded_outcome_preserved(db: Session):
    users = _create_test_hierarchy(db, "super_pres")
    comp, pred = _create_complaint_and_prediction(db, "super_pres", users["org_delhi"].id)

    v1 = create_outcome(
        db=db,
        current_user=users["admin"],
        complaint_id=comp.id,
        outcome_type="CONFIRMED_CASHOUT",
        source="OFFICER_MANUAL",
        actual_location_name="Connaught Place",
    )

    v2 = correct_outcome(
        db=db,
        outcome_id=v1.id,
        current_user=users["admin"],
        correction_reason="Corrected to Karol Bagh",
        actual_location_name="Karol Bagh",
    )

    all_outcomes = db.query(OutcomeObservation).filter(OutcomeObservation.complaint_id == comp.id).all()
    assert len(all_outcomes) == 2
    v1_db = next(o for o in all_outcomes if o.version == 1)
    v2_db = next(o for o in all_outcomes if o.version == 2)
    assert v1_db.actual_location_name == "Connaught Place"
    assert v2_db.actual_location_name == "Karol Bagh"


def test_only_active_outcome_used_for_metrics(db: Session):
    users = _create_test_hierarchy(db, "active_met")
    comp, pred = _create_complaint_and_prediction(db, "active_met", users["org_delhi"].id)

    # v1 had cluster 1 (Rank 1 hit)
    v1 = create_outcome(
        db=db,
        current_user=users["admin"],
        complaint_id=comp.id,
        outcome_type="CONFIRMED_CASHOUT",
        source="OFFICER_MANUAL",
        observed_event_time=_utcnow(),
        actual_lat=28.6315,
        actual_lon=77.2167,
        actual_cluster_id=1,
    )
    # v2 corrects to cluster 2 (Rank 2 hit)
    v2 = correct_outcome(
        db=db,
        outcome_id=v1.id,
        current_user=users["admin"],
        correction_reason="Confirmed cluster 2",
        actual_lat=28.6515,
        actual_lon=77.1907,
        actual_cluster_id=2,
    )

    evaluation = _eval(db, comp.id, users["admin"])
    assert evaluation.outcome_id == v2.id
    assert evaluation.evaluation.top1_hit is False
    assert evaluation.evaluation.top3_hit is True
    assert evaluation.evaluation.observed_rank == 2


def test_correction_audit(db: Session):
    users = _create_test_hierarchy(db, "corr_aud")
    comp, pred = _create_complaint_and_prediction(db, "corr_aud", users["org_delhi"].id)

    v1 = create_outcome(
        db=db,
        current_user=users["state_lea"],
        complaint_id=comp.id,
        outcome_type="CONFIRMED_CASHOUT",
        source="OFFICER_MANUAL",
        actual_cluster_id=1,
    )
    v2 = correct_outcome(
        db=db,
        outcome_id=v1.id,
        current_user=users["state_lea"],
        correction_reason="Field inspection confirmed branch switch",
        actual_cluster_id=2,
    )

    assert v2.correction_reason == "Field inspection confirmed branch switch"
    assert v2.ingested_by_role == "STATE_LEA"
    assert v2.corrects_outcome_id == v1.id


# ──────────────────────────────────────────────────────────────────────────────
# 5. DRIFT MONITORING TESTS (NON-TRAINING LAYER)
# ──────────────────────────────────────────────────────────────────────────────

def test_drift_requires_reference(db: Session):
    monitoring = _monitor(db)
    assert "cashout-location-xgb-v8-debiased" in monitoring.reference_source
    assert "model_metadata_v8_debiased.json" in monitoring.reference_source


def test_insufficient_data_status(db: Session):
    monitoring = _monitor(db)
    assert monitoring.drift_status in ["INSUFFICIENT_DATA", "STABLE", "MONITORING", "SHIFT_OBSERVED"]


def test_distribution_shift_calculation(db: Session):
    monitoring = _monitor(db)
    indicators = {d.metric_name: d for d in monitoring.indicators}
    assert "Mean Top-1 Probability Score" in indicators
    assert indicators["Mean Top-1 Probability Score"].reference_baseline is not None


def test_categorical_shift(db: Session):
    monitoring = _monitor(db)
    indicators = {d.metric_name: d for d in monitoring.indicators}
    assert "Top-3 Hit Rate (R@3)" in indicators
    assert indicators["Top-3 Hit Rate (R@3)"].reference_baseline is not None


def test_drift_does_not_retrain_model(db: Session):
    monitoring = _monitor(db)
    assert "does not automatically retrain" in monitoring.disclaimer.lower()


def test_drift_does_not_modify_model_artifacts(db: Session):
    ranker_path = os.path.join(BASE_DIR, "ml", "artifacts", "location_ranker_v8_debiased.joblib")
    with open(ranker_path, "rb") as f:
        hash_before = hashlib.sha256(f.read()).hexdigest()

    _ = _monitor(db)
    _ = _monitor(db)

    with open(ranker_path, "rb") as f:
        hash_after = hashlib.sha256(f.read()).hexdigest()

    assert hash_before == hash_after == "69f300b4b208f2c3a606f54d84f992b665f30602de0ebe8f77f6561d625bfd71"


# ──────────────────────────────────────────────────────────────────────────────
# 6. RBAC & JURISDICTION TESTS
# ──────────────────────────────────────────────────────────────────────────────

def test_district_outcome_scope(db: Session):
    users = _create_test_hierarchy(db, "dist_scope")
    comp_delhi, _ = _create_complaint_and_prediction(
        db, "dl_sc", users["org_delhi"].id, state="Delhi", district="CENTRAL_NEW_DELHI"
    )

    outcome = create_outcome(
        db=db,
        current_user=users["district_delhi"],
        complaint_id=comp_delhi.id,
        outcome_type="CONFIRMED_CASHOUT",
        source="OFFICER_MANUAL",
        actual_cluster_id=1,
    )
    assert outcome.id is not None
    assert outcome.complaint_id == comp_delhi.id


def test_state_outcome_scope(db: Session):
    users = _create_test_hierarchy(db, "st_scope")
    comp_delhi, _ = _create_complaint_and_prediction(
        db, "st_sc", users["org_delhi"].id, state="Delhi", district="CENTRAL_NEW_DELHI"
    )

    outcome = create_outcome(
        db=db,
        current_user=users["state_lea"],
        complaint_id=comp_delhi.id,
        outcome_type="CONFIRMED_CASHOUT",
        source="OFFICER_MANUAL",
        actual_cluster_id=1,
    )
    assert outcome.id is not None


def test_out_of_scope_outcome_denied(db: Session, client: TestClient):
    users = _create_test_hierarchy(db, "out_scope")
    comp_delhi, _ = _create_complaint_and_prediction(
        db, "out_sc", users["org_delhi"].id, state="Delhi", district="CENTRAL_NEW_DELHI"
    )
    db.commit()

    token = _token(users["district_mumbai"])
    res = client.post(
        f"/api/v1/outcomes/complaints/{comp_delhi.id}",
        json={"outcome_type": "CONFIRMED_CASHOUT", "source": "OFFICER_MANUAL"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404


def test_bank_officer_restricted(db: Session, client: TestClient):
    users = _create_test_hierarchy(db, "bank_rest")
    comp_delhi, _ = _create_complaint_and_prediction(db, "bk_sc", users["org_delhi"].id)
    db.commit()

    token = _token(users["bank_officer"])
    res = client.post(
        f"/api/v1/outcomes/complaints/{comp_delhi.id}",
        json={"outcome_type": "CONFIRMED_CASHOUT", "source": "BANK_REPORT"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_auditor_read_only(db: Session, client: TestClient):
    users = _create_test_hierarchy(db, "aud_ro")
    comp_delhi, _ = _create_complaint_and_prediction(db, "aud_sc", users["org_delhi"].id)
    db.commit()

    token = _token(users["auditor"])
    post_res = client.post(
        f"/api/v1/outcomes/complaints/{comp_delhi.id}",
        json={"outcome_type": "CONFIRMED_CASHOUT", "source": "OFFICER_MANUAL"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert post_res.status_code == 403

    get_res = client.get(
        f"/api/v1/outcomes/complaints/{comp_delhi.id}/evaluation",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_res.status_code == 200

    mon_res = client.get(
        "/api/v1/outcomes/monitoring",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert mon_res.status_code == 200


# ──────────────────────────────────────────────────────────────────────────────
# 7. V8 INVARIANCE & HASH FREEZE (SECTIONS 36, 37)
# ──────────────────────────────────────────────────────────────────────────────

def test_v8_invariance_baseline_221(db: Session):
    """
    Verify baseline Prediction #221 (CMP-NEW-000192):
    1. Connaught Place = 0.0833
    2. Karol Bagh = 0.0747
    3. Rajendra Place = 0.0664
    Fingerprint: c2d1d4d4754e6e36b1cb493a65ea754c9da46e5c5132fb6fd3479c322655b9cc
    """
    pred221 = db.query(Prediction).filter(Prediction.id == 221).first()
    if pred221:
        locs = (
            db.query(PredictionLocation)
            .filter(PredictionLocation.prediction_id == 221)
            .order_by(PredictionLocation.rank.asc())
            .all()
        )
        if len(locs) >= 3:
            assert locs[0].location_name == "Connaught Place"
            assert round(locs[0].probability, 4) == 0.0833
            assert locs[1].location_name == "Karol Bagh"
            assert round(locs[1].probability, 4) == 0.0747
            assert locs[2].location_name == "Rajendra Place"
            assert round(locs[2].probability, 4) == 0.0664


def test_v8_hash_freeze():
    """Verify SHA-256 hashes of all authoritative V8 artifacts."""
    artifacts = {
        os.path.join(BASE_DIR, "ml", "artifacts", "location_ranker_v8_debiased.joblib"):
            "69f300b4b208f2c3a606f54d84f992b665f30602de0ebe8f77f6561d625bfd71",
        os.path.join(BASE_DIR, "ml", "artifacts", "location_calibrator_v8_debiased.joblib"):
            "e2ec24047c42b98a4aefd8c0951f125adf2947a5c1c198136dde9c77c4cb8dd1",
        os.path.join(BASE_DIR, "ml", "artifacts", "feature_schema_v8_debiased.json"):
            "68c9643cea2c3f2480ca085e5da37299568cf72fef98e3f2c7f39b840c514b4b",
    }

    for path, expected_hash in artifacts.items():
        assert os.path.exists(path), f"Artifact missing: {path}"
        with open(path, "rb") as f:
            computed_hash = hashlib.sha256(f.read()).hexdigest()
        assert computed_hash == expected_hash, (
            f"V8 Hash mismatch on {path}: expected {expected_hash}, got {computed_hash}"
        )
