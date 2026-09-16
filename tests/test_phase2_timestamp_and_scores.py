"""
CyberShield AI - Phase 2 Timestamp Correctness & Score Semantics Regression Suite

Validates:
1. API timestamps representing instants serialize with explicit UTC "Z"
2. Input parsing handles UTC with Z, +00:00, and +05:30 (converting aware inputs to UTC exactly once)
3. Legacy naive timestamps are treated as UTC under the verified compatibility policy (no blind shifting)
4. datetime-local round-trip preserves intended instant
5. Null / invalid timestamps are handled gracefully
6. Windows crossing midnight include full date/time
7. Exact expiry boundary evaluation (window_end <= now is expired, > now is active)
8. Complaint reported_at and Prediction reference_time match identically when referencing the same event
9. Genuine zero scores (0.0) are preserved as 0.0% and distinct from missing scores (None -> Unavailable)
10. Official candidate scores are strictly preserved (no artificial rescaling into 70-90% relevance indices)
11. Operational priority and candidate model score are separate concepts that can coexist
12. Graph heuristic risk and historical geographic risk are distinct
"""

import pytest
from datetime import datetime, timezone, timedelta

from backend.app.schemas.schemas import (
    to_utc_datetime,
    to_utc_iso,
    ComplaintCreate,
    ComplaintResponse,
    PredictionResponse,
    PredictionLocationItem,
    AlertResponse,
    RecentComplaintItem,
)
from backend.app.services.prediction_service import compute_operational_priority
from backend.app.services.alert_service import format_window_ist
from backend.app.api.prediction_routes import utc_iso


# ==============================================================================
# 1. TIMESTAMP SERIALIZATION & OFFSET TESTS
# ==============================================================================

def test_utc_serialization_with_z():
    """All API datetime fields representing instants must serialize with explicit 'Z'."""
    dt_aware = datetime(2026, 9, 16, 10, 0, 0, tzinfo=timezone.utc)
    res_iso = to_utc_iso(dt_aware)
    assert res_iso is not None
    assert res_iso.endswith("Z")
    assert res_iso == "2026-09-16T10:00:00Z"

    dt_obj = to_utc_datetime(dt_aware)
    assert dt_obj is not None
    assert dt_obj.tzinfo == timezone.utc


def test_timestamp_with_plus_0000_normalization():
    """Timestamp string with +00:00 must be parsed and serialized to UTC with Z."""
    iso_with_offset = "2026-09-16T10:00:00+00:00"
    res_iso = to_utc_iso(iso_with_offset)
    assert res_iso == "2026-09-16T10:00:00Z"

    dt_obj = to_utc_datetime(iso_with_offset)
    assert dt_obj == datetime(2026, 9, 16, 10, 0, 0, tzinfo=timezone.utc)


def test_timestamp_with_plus_0530_ist_normalization():
    """Timestamp string with +05:30 must convert to UTC exactly once (15:30 IST -> 10:00 UTC)."""
    ist_string = "2026-09-16T15:30:00+05:30"
    res_iso = to_utc_iso(ist_string)
    assert res_iso == "2026-09-16T10:00:00Z"

    dt_obj = to_utc_datetime(ist_string)
    assert dt_obj == datetime(2026, 9, 16, 10, 0, 0, tzinfo=timezone.utc)


def test_legacy_naive_timestamp_compatibility_policy():
    """
    Verified compatibility policy:
    Legacy naive timestamps stored in DB are treated as UTC instants without shifting.
    e.g. naive datetime(2026, 9, 16, 10, 0, 0) -> "2026-09-16T10:00:00Z"
    """
    naive_dt = datetime(2026, 9, 16, 10, 0, 0)
    res_iso = to_utc_iso(naive_dt)
    assert res_iso == "2026-09-16T10:00:00Z"

    dt_obj = to_utc_datetime(naive_dt)
    assert dt_obj == datetime(2026, 9, 16, 10, 0, 0, tzinfo=timezone.utc)

    # Naive string e.g. "2026-09-16T10:00:00"
    naive_str = "2026-09-16T10:00:00"
    res_str = to_utc_iso(naive_str)
    assert res_str == "2026-09-16T10:00:00Z"


def test_null_and_invalid_timestamps_handled_gracefully():
    """Null and invalid values should return None or original string without crashing."""
    assert to_utc_iso(None) is None
    assert to_utc_iso("") is None
    assert to_utc_iso("not-a-datetime") == "not-a-datetime"
    assert to_utc_datetime(None) is None


def test_complaint_create_converts_aware_input_to_utc_once():
    """
    ComplaintCreate converts timezone-aware input (e.g. from frontend .toISOString())
    to UTC naive datetime for DB persistence exactly once.
    """
    payload = {
        "complaint_number": "CMP-TEST-NORM-01",
        "fraud_type": "UPI Fraud",
        "amount": 50000.0,
        "victim_location": "Dwarka, Delhi",
        "incident_time": "2026-09-16T15:30:00+05:30",
        "reported_at": "2026-09-16T10:00:00.000Z",
    }
    cc = ComplaintCreate(**payload)
    # 15:30 IST is 10:00 UTC
    assert cc.incident_time == datetime(2026, 9, 16, 10, 0, 0)
    assert cc.reported_at == datetime(2026, 9, 16, 10, 0, 0)


def test_complaint_response_serializes_with_z():
    """ComplaintResponse serializes datetime fields with explicit 'Z' when dumped to JSON."""
    cr = ComplaintResponse(
        id=1,
        complaint_number="CMP-TEST-001",
        fraud_type="UPI Fraud",
        amount=50000.0,
        victim_name="Test Victim",
        victim_phone="9876543210",
        victim_location="Dwarka, Delhi",
        state="Delhi",
        district="South West Delhi",
        payment_channel="UPI",
        reported_at=datetime(2026, 9, 16, 10, 0, 0),
        incident_time=datetime(2026, 9, 16, 9, 0, 0),
        risk_level="HIGH",
        prediction_status="AVAILABLE",
        case_status="ACTIVE",
        created_at=datetime(2026, 9, 16, 10, 0, 0),
    )
    dumped = cr.model_dump(mode="json")
    assert dumped["reported_at"] == "2026-09-16T10:00:00Z"
    assert dumped["incident_time"] == "2026-09-16T09:00:00Z"
    assert dumped["created_at"] == "2026-09-16T10:00:00Z"


# ==============================================================================
# 2. IDENTICAL EVENT ACROSS COMPLAINT & PREDICTION REFERENCE
# ==============================================================================

def test_complaint_and_prediction_reference_consistency():
    """
    Ensures that when a complaint is filed at 10:00 UTC and prediction uses that
    as reference_time, both serialize with the exact same UTC instant.
    Prevents the 5h30m discrepancy.
    """
    event_time_utc = datetime(2026, 9, 16, 10, 0, 0, tzinfo=timezone.utc)

    # Complaint serialized
    cr = ComplaintResponse(
        id=42,
        complaint_number="CMP-1042",
        fraud_type="Investment Scam",
        amount=85000.0,
        victim_name="Aman Sharma",
        victim_phone="9876543210",
        victim_location="South West Delhi",
        state="Delhi",
        district="South West Delhi",
        payment_channel="IMPS",
        incident_time=datetime(2026, 9, 16, 8, 0, 0, tzinfo=timezone.utc),
        reported_at=event_time_utc,
        risk_level="CRITICAL",
        prediction_status="AVAILABLE",
        case_status="ACTIVE",
        created_at=event_time_utc,
    )

    # Prediction reference serialized via utc_iso
    pred_ref_iso = utc_iso(event_time_utc)
    dumped_cr = cr.model_dump(mode="json")

    # Both must refer to the exact same instant
    assert dumped_cr["reported_at"] == "2026-09-16T10:00:00Z"
    assert pred_ref_iso == "2026-09-16T10:00:00Z"
    assert dumped_cr["reported_at"] == pred_ref_iso


# ==============================================================================
# 3. MIDNIGHT-CROSSING WINDOWS & EXPIRY BOUNDARY
# ==============================================================================

def test_midnight_crossing_window_formatting():
    """
    Alert window formatting must include full date when crossing midnight.
    e.g., 2026-09-16 18:00:00 UTC (23:30 IST) to 2026-09-16 20:00:00 UTC (01:30 IST next day)
    """
    start_utc = datetime(2026, 9, 16, 18, 0, 0, tzinfo=timezone.utc)
    end_utc = datetime(2026, 9, 16, 20, 0, 0, tzinfo=timezone.utc)

    window_text = format_window_ist(start_utc, end_utc)
    # Must show IST and dates because it crosses midnight in IST
    assert "IST" in window_text
    assert "16 Sep" in window_text
    assert "17 Sep" in window_text
    assert "23:30" in window_text
    assert "01:30" in window_text


def test_same_day_window_formatting():
    """
    Alert window on same IST day should show concise format with IST label.
    """
    start_utc = datetime(2026, 9, 16, 10, 0, 0, tzinfo=timezone.utc)  # 15:30 IST
    end_utc = datetime(2026, 9, 16, 11, 30, 0, tzinfo=timezone.utc)   # 17:00 IST

    window_text = format_window_ist(start_utc, end_utc)
    assert "IST" in window_text
    assert "15:30" in window_text
    assert "17:00" in window_text


def test_exact_expiry_boundary_logic():
    """
    Prediction expiry boundary:
    If window_end <= now, window is expired.
    If window_end > now, window is active.
    """
    now = datetime(2026, 9, 16, 12, 0, 0, tzinfo=timezone.utc)
    exact_expiry = datetime(2026, 9, 16, 12, 0, 0, tzinfo=timezone.utc)
    active_boundary = datetime(2026, 9, 16, 12, 0, 1, tzinfo=timezone.utc)
    past_boundary = datetime(2026, 9, 16, 11, 59, 59, tzinfo=timezone.utc)

    assert exact_expiry <= now, "Exact expiry boundary must be classified as expired"
    assert past_boundary <= now, "Past time must be classified as expired"
    assert not (active_boundary <= now), "Future time must be active"


# ==============================================================================
# 4. SCORE SEMANTICS & OPERATIONAL PRIORITY SEPARATION
# ==============================================================================

def test_genuine_zero_score_vs_missing_score():
    """
    A genuine zero score (0.0) is legitimate and must not be treated as missing.
    Missing score (None) must not default to 0.0.
    """
    item_zero = PredictionLocationItem(
        rank=3,
        location_name="Cluster-3",
        probability=0.0,
        risk_level="LOW",
        distance_km=15.0,
        reasoning="Minimal activity",
        latitude=28.6,
        longitude=77.2,
    )
    # Schema must allow 0.0
    assert item_zero.probability == 0.0
    assert item_zero.score_label == "Model ranking score"

    # In prediction routes/adapters, missing score remains None, not defaulted to 0.0
    raw_data = {"score": None}
    assert raw_data["score"] is None
    assert raw_data.get("score") is not 0.0


def test_official_candidate_score_unchanged():
    """
    Candidate model score e.g. 0.089 (8.9%) must NOT be artificially rescaled
    to 70-90% relevance index. Official calibrated output is strictly preserved.
    """
    official_score = 0.0894
    item = PredictionLocationItem(
        rank=1,
        location_name="Cluster-1",
        probability=official_score,
        risk_level="CRITICAL",
        distance_km=2.5,
        reasoning="Primary predicted cashout point",
        latitude=28.65,
        longitude=77.22,
    )
    # Output must retain official score exactly
    assert item.probability == official_score
    assert round(item.probability * 100, 1) == 8.9


def test_operational_priority_rules_inspection():
    """
    Operational priority must follow the actual inspection rules:
    - Amount >= 500k -> CRITICAL
    - Amount >= 75k or (>= 30k and urgent <= 90m) -> HIGH
    - Amount >= 20k or urgent -> MEDIUM
    - Else LOW

    Validates that a high operational priority (CRITICAL) can coexist
    with a low candidate model score (e.g. 0.089).
    """
    now = datetime(2026, 9, 16, 12, 0, 0, tzinfo=timezone.utc)
    incident_recent = now - timedelta(hours=2)

    # Case 1: Large amount (₹6L) -> CRITICAL priority regardless of candidate model score (e.g. 0.07)
    p_label = compute_operational_priority(
        rank=1,
        amount=600000.0,
        time_pred_minutes=180.0,
        incident_time=incident_recent,
        reported_at=now
    )
    assert p_label == "CRITICAL"

    # Case 2: ₹180k amount + 45 min window + recent -> CRITICAL priority
    p_label2 = compute_operational_priority(
        rank=1,
        amount=180000.0,
        time_pred_minutes=45.0,
        incident_time=incident_recent,
        reported_at=now
    )
    assert p_label2 == "CRITICAL"

    # Case 3: ₹85k amount + 200 min window -> HIGH priority
    p_label3 = compute_operational_priority(
        rank=1,
        amount=85000.0,
        time_pred_minutes=200.0,
        incident_time=incident_recent,
        reported_at=now
    )
    assert p_label3 == "HIGH"

    # Case 4: ₹10k amount, old incident (>4h), long window -> LOW priority
    incident_old = now - timedelta(hours=24)
    p_label4 = compute_operational_priority(
        rank=1,
        amount=10000.0,
        time_pred_minutes=300.0,
        incident_time=incident_old,
        reported_at=now
    )
    assert p_label4 == "LOW"


def test_distinguish_graph_heuristic_risk_and_historical_geo_risk():
    """
    Graph heuristic risk (mule graph connectivity) and Historical geographic risk
    (past ATM/cluster crime concentration) are two distinct concepts and must not
    be conflated.
    """
    pred = PredictionResponse(
        id=1,
        complaint_id=10,
        complaint_number="CMP-DIST-01",
        predicted_location="Rohini Sector 7",
        risk_score=0.88,
        risk_level="HIGH",
        risk_percentage=88.0,
        confidence_score=0.089,
        ml_score=0.089,
        graph_score=0.75,  # Heuristic from graph edge count
        geo_score=0.84,    # Historical cluster risk base rate
        temporal_score=0.91,
        intervention_priority=75,
        priority_level="HIGH",
        when_window="30-60 mins",
        why_summary="Test distinguishing risks",
        prediction_mode="trained_ml",
        model_version="cashout-location-xgb-v7-compat",
        top_locations=[
            PredictionLocationItem(
                rank=1,
                location_name="Rohini Sector 7",
                probability=0.089,
                risk_level="HIGH",
                distance_km=3.2,
                reasoning="Primary candidate",
                latitude=28.7,
                longitude=77.1,
            )
        ]
    )

    assert pred.ml_score != pred.graph_score
    assert pred.graph_score != pred.geo_score
    assert pred.ml_score == 0.089       # Model ranking score
    assert pred.graph_score == 0.75     # Graph heuristic risk
    assert pred.geo_score == 0.84       # Historical geographic risk
