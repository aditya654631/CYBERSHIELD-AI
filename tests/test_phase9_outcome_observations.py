"""
CyberShield AI — Phase 09 Test Suite: Verified Outcome Observations

Tests all acceptance criteria from PHASE_09.md.
Uses the standard conftest.py db / client fixtures (function-scoped, isolated SQLite).

Tested categories:
1.  CONFIRMED_CASHOUT creates outcome with LAST_OPERATIONAL_BEFORE_EVENT linkage
2.  UNKNOWN outcome — no prediction required
3.  Invalid outcome_type rejected
4.  is_excluded=True without exclusion_reason rejected
5.  MULTIPLE_CASHOUT stores cashout_events list
6.  MULTIPLE_CASHOUT partial amounts stored separately (verified_held / actual_recovered)
7.  Prediction created AFTER event_time is NEVER linked (no hindsight)
8.  HISTORICAL_REPLAY predictions never linked
9.  Latest OPERATIONAL prediction before event is selected
10. Correction creates new ACTIVE version, supersedes old
11. Correcting a SUPERSEDED record is rejected (409)
12. Correction without reason is rejected (400)
13. UNKNOWN excluded from measured denominator
14. Synthetic outcomes counted separately
15. DATA_EXCLUDED counted in excluded denominator
16. Metrics returns None rates when denominator_cashout=0
17. Verified held + actual_recovered stored as separate fields
18. Metrics financial_note is present
19. Metrics financials are three separate keys (not summed)
20. ANALYST cannot POST (403)
21. AUDITOR cannot POST (403)
22. STATE_LEA can POST (201) — via API
23. ANALYST can GET /metrics (200)
24. Ingest and retrieve single outcome via API
25. List outcomes for complaint via API
26. Correct outcome via API
"""

import datetime as dt
import pytest

from backend.app.auth.security import get_password_hash, create_access_token
from backend.app.models.models import (
    Complaint, Prediction, PredictionLocation,
    BankAction, User, Organization, OutcomeObservation,
)
from backend.app.services.outcome_service import (
    create_outcome,
    correct_outcome,
    get_outcome_metrics,
    get_outcomes_for_complaint,
)
from fastapi import HTTPException


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _utcnow():
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def _utc(hours_offset=0):
    return _utcnow() + dt.timedelta(hours=hours_offset)


def _uid():
    """Unique suffix from microseconds."""
    return str(_utcnow().microsecond)


def _make_org(db, state="Delhi", org_type="LEA"):
    uid = _uid()
    org = Organization(name=f"Test Org {uid}", org_type=org_type, state=state, district="Test District")
    db.add(org)
    db.flush()
    return org


def _make_user(db, role="I4C_ADMIN", org=None, email=None):
    uid = _uid()
    u = User(
        email=email or f"user{uid}@test.gov",
        hashed_password=get_password_hash("test1234"),
        full_name=f"Test User {uid}",
        role=role,
        organization_id=org.id if org else None,
        is_active=True,
    )
    db.add(u)
    db.flush()
    return u


def _make_complaint(db, org=None, provenance="DIRECT_OFFICER_INPUT"):
    uid = _uid()
    c = Complaint(
        complaint_number=f"CMP-P09-{uid}",
        fraud_type="ATM_FRAUD",
        amount=150000,
        victim_name="Test Victim",
        victim_location="New Delhi",
        state="Delhi",
        district="CENTRAL_NEW_DELHI",
        payment_channel="ATM",
        provenance_mode=provenance,
        reported_at=_utcnow(),
        incident_time=_utcnow(),
        created_at=_utcnow(),
        owner_organization_id=org.id if org else None,
    )
    db.add(c)
    db.flush()
    return c


def _make_prediction(db, complaint, hours_before_event=2, purpose="OPERATIONAL"):
    created = _utc(-hours_before_event)
    pred = Prediction(
        complaint_id=complaint.id,
        version_number=None,
        analysis_purpose=purpose,
        analysis_as_of=created,
        predicted_window_start=created,
        predicted_window_end=created + dt.timedelta(hours=4),
        risk_score=0.87,
        risk_level="CRITICAL",
        confidence_score=0.92,
        created_at=created,
    )
    db.add(pred)
    db.flush()
    loc = PredictionLocation(
        prediction_id=pred.id,
        location_name="Connaught Place ATM",
        rank=1,
        probability=0.87,
        latitude=28.6315,
        longitude=77.2167,
    )
    db.add(loc)
    db.flush()
    return pred


def _make_bank_action(db, complaint, held_amount=100000):
    uid = _uid()
    ba = BankAction(
        action_reference=f"BA-{uid}",
        complaint_id=complaint.id,
        action_type="ATM_DISBURSEMENT_HOLD",
        status="CONFIRMED_HOLD",
        environment="SIMULATED",
        is_simulated=True,
        requested_amount=150000,
        held_amount=held_amount,
        currency="INR",
        requested_at=_utc(-2),
        held_at=_utc(-1),
    )
    db.add(ba)
    db.flush()
    return ba


def _token(user):
    return create_access_token(data={"sub": user.email, "role": user.role})


# ──────────────────────────────────────────────────────────────────────────────
# 1–4: Outcome Creation & Validation
# ──────────────────────────────────────────────────────────────────────────────

def test_confirmed_cashout_creates_outcome(db):
    """1. CONFIRMED_CASHOUT links LAST_OPERATIONAL_BEFORE_EVENT prediction."""
    user = _make_user(db, "I4C_ADMIN")
    complaint = _make_complaint(db)
    pred = _make_prediction(db, complaint, hours_before_event=2)
    db.commit()

    event_time = _utcnow()
    outcome = create_outcome(
        db=db, current_user=user, complaint_id=complaint.id,
        outcome_type="CONFIRMED_CASHOUT",
        source="OFFICER_MANUAL",
        observed_event_time=event_time,
        actual_lat=28.6315, actual_lon=77.2167,
        actual_location_name="Connaught Place ATM",
        actual_withdrawal_amount_inr=120000,
    )
    assert outcome.id is not None
    assert outcome.outcome_type == "CONFIRMED_CASHOUT"
    assert outcome.record_status == "ACTIVE"
    assert outcome.version == 1
    assert outcome.ingested_by_role == "I4C_ADMIN"
    assert outcome.linked_prediction_id == pred.id
    assert outcome.prediction_selection_policy == "LAST_OPERATIONAL_BEFORE_EVENT"


def test_unknown_outcome_no_prediction_required(db):
    """2. UNKNOWN outcome can be created without a prediction or event time."""
    user = _make_user(db, "I4C_ADMIN")
    complaint = _make_complaint(db)
    db.commit()

    outcome = create_outcome(
        db=db, current_user=user, complaint_id=complaint.id,
        outcome_type="UNKNOWN",
        source="OFFICER_MANUAL",
    )
    assert outcome.outcome_type == "UNKNOWN"
    assert outcome.linked_prediction_id is None


def test_invalid_outcome_type_rejected(db):
    """3. Invalid outcome_type must raise HTTP 400."""
    user = _make_user(db, "I4C_ADMIN")
    complaint = _make_complaint(db)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        create_outcome(
            db=db, current_user=user, complaint_id=complaint.id,
            outcome_type="TOTALLY_WRONG",
            source="OFFICER_MANUAL",
        )
    assert exc.value.status_code == 400


def test_excluded_without_reason_rejected(db):
    """4. is_excluded=True without exclusion_reason must raise HTTP 400."""
    user = _make_user(db, "I4C_ADMIN")
    complaint = _make_complaint(db)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        create_outcome(
            db=db, current_user=user, complaint_id=complaint.id,
            outcome_type="CONFIRMED_CASHOUT",
            source="OFFICER_MANUAL",
            is_excluded=True,
            exclusion_reason=None,
        )
    assert exc.value.status_code == 400


# ──────────────────────────────────────────────────────────────────────────────
# 5–6: Multiple Cashouts
# ──────────────────────────────────────────────────────────────────────────────

def test_multiple_cashout_stores_cashout_events(db):
    """5. MULTIPLE_CASHOUT stores list of cashout_events."""
    user = _make_user(db, "I4C_ADMIN")
    complaint = _make_complaint(db)
    pred = _make_prediction(db, complaint, hours_before_event=3)
    db.commit()

    events = [
        {"time": _utcnow().isoformat(), "lat": 28.63, "lon": 77.21, "amount": 50000, "atm_code": "ATM001"},
        {"time": _utcnow().isoformat(), "lat": 28.62, "lon": 77.20, "amount": 45000, "atm_code": "ATM002"},
    ]
    outcome = create_outcome(
        db=db, current_user=user, complaint_id=complaint.id,
        outcome_type="MULTIPLE_CASHOUT",
        source="CFCFRMS_IMPORT",
        observed_event_time=_utcnow(),
        cashout_events=events,
    )
    assert outcome.outcome_type == "MULTIPLE_CASHOUT"
    assert isinstance(outcome.cashout_events, list)
    assert len(outcome.cashout_events) == 2
    assert outcome.linked_prediction_id == pred.id


def test_multiple_cashout_partial_amounts_stored_separately(db):
    """6. verified_held and actual_recovered are stored as separate fields."""
    user = _make_user(db, "I4C_ADMIN")
    complaint = _make_complaint(db)
    ba = _make_bank_action(db, complaint, held_amount=80000)
    _make_prediction(db, complaint, hours_before_event=2)
    db.commit()

    outcome = create_outcome(
        db=db, current_user=user, complaint_id=complaint.id,
        outcome_type="MULTIPLE_CASHOUT",
        source="OFFICER_MANUAL",
        observed_event_time=_utcnow(),
        linked_bank_action_id=ba.id,
        actual_recovered_amount_inr=30000,
    )
    assert float(outcome.verified_held_amount_inr) == 80000.0
    assert float(outcome.actual_recovered_amount_inr) == 30000.0
    assert not hasattr(outcome, "total_intervention_amount")


# ──────────────────────────────────────────────────────────────────────────────
# 7–9: Prediction Evaluation Policy
# ──────────────────────────────────────────────────────────────────────────────

def test_no_future_prediction_linked(db):
    """7. A prediction created AFTER observed_event_time must never be linked."""
    user = _make_user(db, "I4C_ADMIN")
    complaint = _make_complaint(db)
    event_time = _utcnow()

    future_pred = Prediction(
        complaint_id=complaint.id, version_number=None,
        analysis_purpose="OPERATIONAL",
        predicted_window_start=event_time + dt.timedelta(minutes=5),
        predicted_window_end=event_time + dt.timedelta(hours=4),
        risk_score=0.85, risk_level="CRITICAL",
        created_at=event_time + dt.timedelta(minutes=5),
    )
    db.add(future_pred)
    db.commit()

    outcome = create_outcome(
        db=db, current_user=user, complaint_id=complaint.id,
        outcome_type="CONFIRMED_CASHOUT",
        source="OFFICER_MANUAL",
        observed_event_time=event_time,
    )
    # Future prediction must never be linked
    if outcome.linked_prediction_id:
        assert outcome.linked_prediction_id != future_pred.id


def test_historical_replay_prediction_excluded(db):
    """8. HISTORICAL_REPLAY predictions must never be linked."""
    user = _make_user(db, "I4C_ADMIN")
    complaint = _make_complaint(db)

    replay = Prediction(
        complaint_id=complaint.id, version_number=None,
        analysis_purpose="HISTORICAL_REPLAY",
        predicted_window_start=_utc(-3),
        predicted_window_end=_utc(-1),
        risk_score=0.75, risk_level="HIGH",
        created_at=_utc(-3),
    )
    db.add(replay)
    db.commit()

    event_time = _utcnow()
    outcome = create_outcome(
        db=db, current_user=user, complaint_id=complaint.id,
        outcome_type="NO_OBSERVED_CASHOUT",
        source="OFFICER_MANUAL",
        observed_event_time=event_time,
    )
    if outcome.linked_prediction_id:
        linked = db.query(Prediction).filter(Prediction.id == outcome.linked_prediction_id).first()
        assert linked.analysis_purpose == "OPERATIONAL"


def test_last_operational_before_event_selected(db):
    """9. When multiple OPERATIONAL predictions exist, the latest before event is chosen."""
    user = _make_user(db, "I4C_ADMIN")
    complaint = _make_complaint(db)
    event_time = _utcnow()

    older = Prediction(
        complaint_id=complaint.id, version_number=None,
        analysis_purpose="OPERATIONAL",
        predicted_window_start=_utc(-4), predicted_window_end=_utc(-2),
        risk_score=0.80, risk_level="HIGH", created_at=_utc(-4),
    )
    db.add(older)
    db.flush()
    newer = Prediction(
        complaint_id=complaint.id, version_number=None,
        analysis_purpose="OPERATIONAL",
        predicted_window_start=_utc(-2), predicted_window_end=event_time,
        risk_score=0.90, risk_level="CRITICAL", created_at=_utc(-2),
    )
    db.add(newer)
    db.commit()

    outcome = create_outcome(
        db=db, current_user=user, complaint_id=complaint.id,
        outcome_type="CONFIRMED_CASHOUT",
        source="OFFICER_MANUAL",
        observed_event_time=event_time,
        actual_lat=28.63, actual_lon=77.22,
    )
    assert outcome.linked_prediction_id == newer.id


# ──────────────────────────────────────────────────────────────────────────────
# 10–12: Correction Lineage
# ──────────────────────────────────────────────────────────────────────────────

def test_correction_creates_new_version(db):
    """10. Correcting an ACTIVE outcome creates version 2 and supersedes version 1."""
    user = _make_user(db, "I4C_ADMIN")
    complaint = _make_complaint(db)
    db.commit()

    original = create_outcome(
        db=db, current_user=user, complaint_id=complaint.id,
        outcome_type="UNKNOWN", source="OFFICER_MANUAL",
    )
    original_id = original.id
    assert original.version == 1

    corrected = correct_outcome(
        db=db, current_user=user, outcome_id=original_id,
        correction_reason="Confirmed via CCTV footage",
        outcome_type="CONFIRMED_CASHOUT",
        actual_location_name="Karol Bagh ATM",
    )
    assert corrected.version == 2
    assert corrected.corrects_outcome_id == original_id
    assert corrected.record_status == "ACTIVE"
    assert corrected.outcome_type == "CONFIRMED_CASHOUT"

    db.refresh(original)
    assert original.record_status == "SUPERSEDED"


def test_correction_of_superseded_record_rejected(db):
    """11. Correcting a SUPERSEDED record must raise HTTP 409."""
    user = _make_user(db, "I4C_ADMIN")
    complaint = _make_complaint(db)
    db.commit()

    v1 = create_outcome(
        db=db, current_user=user, complaint_id=complaint.id,
        outcome_type="UNKNOWN", source="OFFICER_MANUAL",
    )
    correct_outcome(
        db=db, current_user=user, outcome_id=v1.id,
        correction_reason="First correction — now confirmed",
        outcome_type="NO_OBSERVED_CASHOUT",
    )
    db.refresh(v1)
    assert v1.record_status == "SUPERSEDED"

    with pytest.raises(HTTPException) as exc:
        correct_outcome(
            db=db, current_user=user, outcome_id=v1.id,
            correction_reason="Trying to correct superseded record",
        )
    assert exc.value.status_code == 409


def test_correction_without_reason_rejected(db):
    """12. Correction with empty correction_reason must raise HTTP 400."""
    user = _make_user(db, "I4C_ADMIN")
    complaint = _make_complaint(db)
    db.commit()

    v1 = create_outcome(
        db=db, current_user=user, complaint_id=complaint.id,
        outcome_type="UNKNOWN", source="OFFICER_MANUAL",
    )

    with pytest.raises(HTTPException) as exc:
        correct_outcome(
            db=db, current_user=user, outcome_id=v1.id,
            correction_reason="",
        )
    assert exc.value.status_code == 400


# ──────────────────────────────────────────────────────────────────────────────
# 13–16: Denominator Accounting
# ──────────────────────────────────────────────────────────────────────────────

def test_unknown_excluded_from_measured_denominator(db):
    """13. UNKNOWN outcomes increment denominator_unknown, not denominator_measured."""
    user = _make_user(db, "I4C_ADMIN")
    complaint = _make_complaint(db)
    db.commit()

    before = get_outcome_metrics(db)
    create_outcome(db=db, current_user=user, complaint_id=complaint.id,
                   outcome_type="UNKNOWN", source="OFFICER_MANUAL")
    create_outcome(db=db, current_user=user, complaint_id=complaint.id,
                   outcome_type="UNKNOWN", source="OFFICER_MANUAL")
    db.commit()

    after = get_outcome_metrics(db)
    # Unknown count grew
    assert after["denominator_unknown"] >= before["denominator_unknown"] + 2
    # Measured did NOT grow due to these unknowns
    assert after["denominator_measured"] == before["denominator_measured"]


def test_synthetic_cohort_separate(db):
    """14. is_synthetic=True outcomes go into denominator_synthetic, not denominator_measured."""
    user = _make_user(db, "I4C_ADMIN")
    complaint = _make_complaint(db)
    db.commit()

    before = get_outcome_metrics(db)
    create_outcome(db=db, current_user=user, complaint_id=complaint.id,
                   outcome_type="CONFIRMED_CASHOUT", source="OFFICER_MANUAL", is_synthetic=True)
    create_outcome(db=db, current_user=user, complaint_id=complaint.id,
                   outcome_type="NO_OBSERVED_CASHOUT", source="OFFICER_MANUAL", is_synthetic=True)
    db.commit()

    after = get_outcome_metrics(db)
    assert after["denominator_synthetic"] >= before["denominator_synthetic"] + 2
    # Real denominator_measured must not change from synthetic outcomes
    assert after["denominator_measured"] == before["denominator_measured"]


def test_data_excluded_counted_separately(db):
    """15. DATA_EXCLUDED outcomes increment denominator_excluded."""
    user = _make_user(db, "I4C_ADMIN")
    complaint = _make_complaint(db)
    db.commit()

    before = get_outcome_metrics(db)
    create_outcome(
        db=db, current_user=user, complaint_id=complaint.id,
        outcome_type="DATA_EXCLUDED", source="OFFICER_MANUAL",
        is_excluded=True, exclusion_reason="Jurisdictional restriction",
    )
    db.commit()

    after = get_outcome_metrics(db)
    assert after["denominator_excluded"] >= before["denominator_excluded"] + 1


def test_metrics_returns_none_rates_when_no_cashouts(db):
    """16. If denominator_cashout=0, accuracy rates must be None (not a div/0 crash)."""
    metrics = get_outcome_metrics(db)
    if metrics["denominator_cashout"] == 0:
        assert metrics["rank1_accuracy_rate"] is None
        assert metrics["topk_accuracy_rate"] is None


# ──────────────────────────────────────────────────────────────────────────────
# 17–19: Financial Amounts
# ──────────────────────────────────────────────────────────────────────────────

def test_held_and_recovered_stored_separately(db):
    """17. verified_held and actual_recovered are independent DB columns."""
    user = _make_user(db, "I4C_ADMIN")
    complaint = _make_complaint(db)
    ba = _make_bank_action(db, complaint, held_amount=120000)
    db.commit()

    outcome = create_outcome(
        db=db, current_user=user, complaint_id=complaint.id,
        outcome_type="CONFIRMED_CASHOUT",
        source="OFFICER_MANUAL",
        observed_event_time=_utcnow(),
        linked_bank_action_id=ba.id,
        actual_recovered_amount_inr=40000,
        verified_released_amount_inr=20000,
    )
    assert float(outcome.verified_held_amount_inr) == 120000.0
    assert float(outcome.actual_recovered_amount_inr) == 40000.0
    assert float(outcome.verified_released_amount_inr) == 20000.0


def test_metrics_financial_note_present(db):
    """18. Metrics response includes a financial_note field."""
    metrics = get_outcome_metrics(db)
    assert "financial_note" in metrics
    note = metrics["financial_note"]
    assert isinstance(note, str) and len(note) > 20


def test_metrics_financials_reported_as_separate_keys(db):
    """19. Total financials are three distinct keys, never summed into one."""
    metrics = get_outcome_metrics(db)
    assert "total_verified_held_inr" in metrics
    assert "total_actual_recovered_inr" in metrics
    assert "total_verified_released_inr" in metrics
    assert "total_intervention_amount" not in metrics


# ──────────────────────────────────────────────────────────────────────────────
# 20–26: API / RBAC Tests
# ──────────────────────────────────────────────────────────────────────────────

def test_analyst_cannot_ingest_outcome(db, client):
    """20. ANALYST role gets 403 on POST /outcomes/complaints/{id}."""
    complaint = _make_complaint(db)
    db.commit()
    org = _make_org(db, org_type="I4C")
    analyst = _make_user(db, "ANALYST", org)
    db.commit()

    token = _token(analyst)
    res = client.post(
        f"/api/v1/outcomes/complaints/{complaint.id}",
        json={"outcome_type": "UNKNOWN", "source": "OFFICER_MANUAL"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_auditor_cannot_ingest_outcome(db, client):
    """21. AUDITOR role gets 403 on POST /outcomes/complaints/{id}."""
    complaint = _make_complaint(db)
    db.commit()
    org = _make_org(db, org_type="I4C")
    auditor = _make_user(db, "AUDITOR", org)
    db.commit()

    token = _token(auditor)
    res = client.post(
        f"/api/v1/outcomes/complaints/{complaint.id}",
        json={"outcome_type": "UNKNOWN", "source": "OFFICER_MANUAL"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_state_lea_can_ingest_outcome(db, client):
    """22. STATE_LEA can POST (201) when the complaint is in their jurisdiction."""
    org = _make_org(db, state="Delhi", org_type="LEA")
    lea = _make_user(db, "STATE_LEA", org)
    complaint = _make_complaint(db, org=org)
    db.commit()

    token = _token(lea)
    res = client.post(
        f"/api/v1/outcomes/complaints/{complaint.id}",
        json={"outcome_type": "UNKNOWN", "source": "OFFICER_MANUAL"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201


def test_analyst_can_read_metrics(db, client):
    """23. ANALYST can GET /outcomes/metrics (200)."""
    org = _make_org(db, org_type="I4C")
    analyst = _make_user(db, "ANALYST", org)
    db.commit()

    token = _token(analyst)
    res = client.get(
        "/api/v1/outcomes/metrics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "denominator_measured" in data
    assert "financial_note" in data
    assert "prediction_selection_policy" in data


def test_ingest_and_retrieve_outcome(db, client):
    """24. POST ingest → GET by ID returns same record."""
    org = _make_org(db, org_type="I4C")
    admin = _make_user(db, "I4C_ADMIN", org)
    complaint = _make_complaint(db)
    db.commit()

    token = _token(admin)
    res = client.post(
        f"/api/v1/outcomes/complaints/{complaint.id}",
        json={
            "outcome_type": "NO_OBSERVED_CASHOUT",
            "source": "OFFICER_MANUAL",
            "notes": "Window closed without any withdrawal observed.",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["outcome_type"] == "NO_OBSERVED_CASHOUT"
    assert data["record_status"] == "ACTIVE"
    assert data["prediction_selection_policy"] == "LAST_OPERATIONAL_BEFORE_EVENT"

    outcome_id = data["id"]
    res2 = client.get(f"/api/v1/outcomes/{outcome_id}",
                      headers={"Authorization": f"Bearer {token}"})
    assert res2.status_code == 200
    assert res2.json()["id"] == outcome_id


def test_list_outcomes_for_complaint(db, client):
    """25. GET /outcomes/complaints/{id} returns at least the outcomes created here."""
    org = _make_org(db, org_type="I4C")
    admin = _make_user(db, "I4C_ADMIN", org)
    complaint = _make_complaint(db)
    db.commit()

    token = _token(admin)
    for otype in ["CONFIRMED_CASHOUT", "UNKNOWN"]:
        client.post(
            f"/api/v1/outcomes/complaints/{complaint.id}",
            json={"outcome_type": otype, "source": "OFFICER_MANUAL"},
            headers={"Authorization": f"Bearer {token}"},
        )

    res = client.get(
        f"/api/v1/outcomes/complaints/{complaint.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    items = res.json()
    assert len(items) >= 2


def test_correct_outcome_via_api(db, client):
    """26. POST /outcomes/{id}/correct creates v2 ACTIVE, supersedes v1."""
    org = _make_org(db, org_type="I4C")
    admin = _make_user(db, "I4C_ADMIN", org)
    complaint = _make_complaint(db)
    db.commit()

    token = _token(admin)
    res = client.post(
        f"/api/v1/outcomes/complaints/{complaint.id}",
        json={"outcome_type": "UNKNOWN", "source": "OFFICER_MANUAL"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    outcome_id = res.json()["id"]

    res2 = client.post(
        f"/api/v1/outcomes/{outcome_id}/correct",
        json={
            "correction_reason": "Confirmed via official bank report received",
            "outcome_type": "CONFIRMED_CASHOUT",
            "actual_location_name": "Rajouri Garden Branch ATM",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res2.status_code == 201
    corrected = res2.json()
    assert corrected["version"] == 2
    assert corrected["outcome_type"] == "CONFIRMED_CASHOUT"
    assert corrected["corrects_outcome_id"] == outcome_id
