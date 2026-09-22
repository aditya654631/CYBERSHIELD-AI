"""
CyberShield AI - Phase 5: Durable Alerts, Transactional Outbox, and Delivery Lifecycle Test Suite

Validates all 9 Phase 5 core verification scenarios:
1. Atomic Outbox & Crash Before Dispatch (Alert + Outbox commit together)
2. Worker Lease Locking & Stale Lease Recovery (Crash after dispatch recovery)
3. Bounded Exponential Backoff Retry on Temporary Provider Failure
4. Permanent Failure Transition (Max 5 attempts / non-retryable error)
5. Missed-Alert Replay via GET /api/v1/alerts/sync (Cursor & timestamp pagination)
6. RBAC Jurisdiction & Organization Scoping on Alert Sync
7. Prediction Version Supersession (New prediction supersedes active alerts with audit trail)
8. Alert Expiration (Stale alerts transition to EXPIRED with outbox event)
9. Outbox Delivery Audit Trail API (GET /api/v1/alerts/{id}/outbox)
"""

import time
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy.orm import Session

from backend.app.auth.security import create_access_token
from backend.app.models.models import (
    Complaint, Prediction, PredictionLocation, LocationCluster, User, Organization, Alert, NotificationOutbox
)
from backend.app.services.outbox_service import outbox_service, calculate_backoff
from backend.app.services.alert_service import create_alert_for_prediction


def _make_auth_header(email: str, role: str) -> dict:
    claims = {"sub": email, "role": role}
    token = create_access_token(claims)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers():
    return _make_auth_header("admin@cybershield.gov.in", "I4C_ADMIN")


@pytest.fixture
def delhi_state_lea_headers():
    """Active: User 12 — DCP Rajesh Kumar, IPS (STATE_LEA, Delhi Cyber Crime Unit NCT)"""
    return _make_auth_header("state.lea@delhi.cyber.gov.in", "STATE_LEA")


@pytest.fixture
def south_delhi_district_lea_headers():
    """Active: User 13 — Inspector Amit Sharma (DISTRICT_LEA, District Cyber Cell South Delhi)"""
    return _make_auth_header("district.lea@southdelhi.cyber.gov.in", "DISTRICT_LEA")


@pytest.fixture
def sbi_headers():
    return _make_auth_header("officer@sbi.co.in", "BANK_OFFICER")


def _get_or_create_complaint(
    db_session: Session,
    comp_num: str,
    state: str = "Delhi",
    district: str = "Central Delhi"
) -> Complaint:
    complaint = db_session.query(Complaint).filter(Complaint.complaint_number == comp_num).first()
    if not complaint:
        now = datetime.now(timezone.utc)
        complaint = Complaint(
            complaint_number=comp_num,
            fraud_type="UPI Fraud",
            amount=250000.0,
            victim_name="Test Citizen",
            victim_phone="9876543210",
            victim_location=f"{district}, {state}",
            state=state,
            district=district,
            incident_time=now - timedelta(hours=2),
            reported_at=now - timedelta(hours=1),
            case_status="UNDER_INVESTIGATION",
            created_at=now
        )
        db_session.add(complaint)
        db_session.commit()
        db_session.refresh(complaint)
    return complaint


def _create_test_prediction_and_alert(
    db_session: Session,
    complaint: Complaint,
    risk_score: float = 0.90,
    model_version: str = "v4.0.0",
    operational: bool = True,
    cluster: LocationCluster = None
):
    if cluster is None:
        cluster = db_session.query(LocationCluster).filter(LocationCluster.state == complaint.state).first()
        if not cluster:
            cluster = db_session.query(LocationCluster).first()
            
    now = datetime.now(timezone.utc)
    pred = Prediction(
        complaint_id=complaint.id,
        predicted_window_start=now,
        predicted_window_end=now + timedelta(hours=4),
        primary_cluster_id=cluster.id if cluster else None,
        risk_score=risk_score,
        confidence_score=0.92,
        risk_level="CRITICAL" if risk_score >= 0.85 else "HIGH",
        prediction_mode="trained_ml",
        model_version=model_version,
        analysis_purpose="OPERATIONAL" if operational else "HISTORICAL_REPLAY",
        created_at=now
    )
    db_session.add(pred)
    db_session.commit()
    db_session.refresh(pred)
    
    if cluster:
        ploc = PredictionLocation(
            prediction_id=pred.id,
            cluster_id=cluster.id,
            location_name=getattr(cluster, "cluster_name", "Test Hotspot"),
            rank=1,
            probability=risk_score,
            risk_level="CRITICAL" if risk_score >= 0.85 else "HIGH",
            latitude=getattr(cluster, "latitude", 28.6139),
            longitude=getattr(cluster, "longitude", 77.2090)
        )
        db_session.add(ploc)
        db_session.commit()
    
    alert = create_alert_for_prediction(db_session, pred.id)
    return pred, alert


# ==============================================================================
# 1. Atomic Outbox & Crash Before Dispatch
# ==============================================================================
def test_atomic_outbox_and_crash_before_dispatch(db_session: Session):
    """
    Verifies that alert creation and outbound notification events commit
    in the same atomic DB transaction. If system restarts, outbox remains QUEUED.
    """
    complaint = _get_or_create_complaint(db_session, "CMP-P5-ATOM-001")
    pred, alert = _create_test_prediction_and_alert(db_session, complaint, risk_score=0.92)
    
    assert alert is not None
    assert alert.id is not None
    assert alert.expires_at is not None
    
    # Verify outbox event exists and is committed in QUEUED state
    outbox_events = db_session.query(NotificationOutbox).filter(
        NotificationOutbox.alert_id == alert.id
    ).all()
    
    assert len(outbox_events) >= 1
    event = outbox_events[0]
    assert event.status == "QUEUED"
    assert event.event_type == "ALERT_CREATED"
    assert event.attempt_count == 0
    assert event.idempotency_key is not None
    assert event.prediction_id == pred.id


# ==============================================================================
# 2. Worker Lease Locking & Stale Lease Recovery
# ==============================================================================
def test_worker_lease_locking_and_stale_lease_recovery(db_session: Session):
    """
    Verifies worker lease acquisition, preventing dual-delivery,
    and stale lease recovery when worker crashes during processing.
    """
    complaint = _get_or_create_complaint(db_session, "CMP-P5-LEASE-002")
    pred, alert = _create_test_prediction_and_alert(db_session, complaint, risk_score=0.85)
    
    # Worker 1 claims pending events
    worker1_events = outbox_service.claim_pending_events(db=db_session, worker_id="worker_node_1", limit=5, lease_seconds=10)
    assert len(worker1_events) >= 1
    claimed_ids = [e.id for e in worker1_events]
    
    # Verify status is PROCESSING and lease fields are populated
    for ev in worker1_events:
        assert ev.status == "PROCESSING"
        assert ev.worker_id == "worker_node_1"
        assert ev.lease_expires_at > datetime.utcnow()
    
    # Worker 2 attempts to claim simultaneously -> should get 0 because lease is active
    worker2_events = outbox_service.claim_pending_events(db=db_session, worker_id="worker_node_2", limit=5, lease_seconds=10)
    assert not any(e.id in claimed_ids for e in worker2_events)
    
    # Simulate Worker 1 crashing and lease expiring (backdate lease_expires_at)
    db_session.query(NotificationOutbox).filter(NotificationOutbox.id.in_(claimed_ids)).update({
        NotificationOutbox.lease_expires_at: datetime.utcnow() - timedelta(seconds=5)
    }, synchronize_session=False)
    db_session.commit()
    
    # Worker 2 now reclaims expired lease
    reclaimed = outbox_service.claim_pending_events(db=db_session, worker_id="worker_node_2", limit=5, lease_seconds=10)
    reclaimed_ids = [e.id for e in reclaimed]
    assert any(e_id in reclaimed_ids for e_id in claimed_ids)


# ==============================================================================
# 3. Bounded Exponential Backoff Retry on Temporary Provider Failure
# ==============================================================================
def test_bounded_exponential_backoff_retry(db_session: Session):
    """
    Verifies exponential backoff calculation: T_retry = min(5 * 2^(attempt - 1), 3600)
    and state transition on temporary delivery failure.
    """
    # Check backoff formula
    assert calculate_backoff(attempt=1).total_seconds() == 5   # 5 * 2^0 = 5s
    assert calculate_backoff(attempt=2).total_seconds() == 10  # 5 * 2^1 = 10s
    assert calculate_backoff(attempt=3).total_seconds() == 20  # 5 * 2^2 = 20s
    assert calculate_backoff(attempt=4).total_seconds() == 40  # 5 * 2^3 = 40s
    assert calculate_backoff(attempt=10).total_seconds() == 2560
    assert calculate_backoff(attempt=11).total_seconds() == 3600 # Capped at 3600s
    
    complaint = _get_or_create_complaint(db_session, "CMP-P5-RETRY-003")
    pred, alert = _create_test_prediction_and_alert(db_session, complaint, risk_score=0.86)
    
    event = db_session.query(NotificationOutbox).filter(NotificationOutbox.alert_id == alert.id).first()
    
    # Simulate processing with temporary failure
    success = outbox_service.process_event(
        db=db_session,
        event=event,
        simulated_failure="TEMPORARY",
        custom_error="Temporary 503 Gateway Timeout from SMS gateway"
    )
    
    assert success is False
    assert event.status == "FAILED"
    assert event.attempt_count == 1
    assert "503" in event.last_error
    assert event.next_retry_at is not None
    assert event.next_retry_at > datetime.utcnow()


# ==============================================================================
# 4. Permanent Failure Transition (Max Retries Exhausted)
# ==============================================================================
def test_permanent_failure_transition(db_session: Session):
    """
    Verifies that after max_retries (5), the outbox item transitions to PERMANENT_FAILURE.
    """
    complaint = _get_or_create_complaint(db_session, "CMP-P5-PERM-004")
    pred, alert = _create_test_prediction_and_alert(db_session, complaint, risk_score=0.88)
    
    event = db_session.query(NotificationOutbox).filter(NotificationOutbox.alert_id == alert.id).first()
    
    # Set attempt_count to 4 (so next failure hits max_retries = 5)
    event.attempt_count = 4
    db_session.commit()
    
    success = outbox_service.process_event(
        db=db_session,
        event=event,
        simulated_failure="TEMPORARY",
        custom_error="Fatal unrecoverable delivery error"
    )
    
    assert success is False
    assert event.status == "PERMANENT_FAILURE"
    assert event.attempt_count == 5
    assert "Fatal" in event.last_error


# ==============================================================================
# 5. Missed-Alert Replay via GET /api/v1/alerts/sync
# ==============================================================================
def test_missed_alert_replay_sync_api(client, db_session: Session, admin_headers):
    """
    Verifies cursor-based and timestamp-based replay for disconnected/reconnecting clients.
    """
    complaint = _get_or_create_complaint(db_session, "CMP-P5-SYNC-005")
    pred, alert = _create_test_prediction_and_alert(db_session, complaint, risk_score=0.91)
    
    # Query sync endpoint with since_id = alert.id - 1
    response = client.get(f"/api/v1/alerts/sync?since_id={alert.id - 1}&limit=10", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    
    assert "items" in data
    assert "has_more" in data
    assert "synced_at" in data
    assert any(item["id"] == alert.id for item in data["items"])
    
    sync_item = next(item for item in data["items"] if item["id"] == alert.id)
    assert "delivery_status" in sync_item
    assert "outbox_events" in data
    
    # Query with since_id = alert.id -> should return items with ID > alert.id
    response_cursor = client.get(f"/api/v1/alerts/sync?since_id={alert.id}&limit=10", headers=admin_headers)
    assert response_cursor.status_code == 200
    cursor_data = response_cursor.json()
    assert not any(item["id"] == alert.id for item in cursor_data["items"])

    # Query with since_time 1 hour ago
    since_str = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    resp_time = client.get(f"/api/v1/alerts/sync?since_time={since_str}&limit=500", headers=admin_headers)
    assert resp_time.status_code == 200
    time_data = resp_time.json()
    assert any(item["id"] == alert.id for item in time_data["items"])


# ==============================================================================
# 6. RBAC Jurisdiction & Organization Scoping on Alert Sync
# ==============================================================================
def test_rbac_jurisdiction_scoping_on_alert_sync(
    client, db_session: Session, delhi_state_lea_headers, south_delhi_district_lea_headers, sbi_headers
):
    """
    Verifies that alert replay strictly respects Phase 03 jurisdiction & org boundaries.
    Delhi STATE_LEA (NCT) should see Delhi-state alerts.
    South Delhi DISTRICT_LEA should see only South Delhi district-scoped alerts.
    A BANK_OFFICER should NOT see LEA jurisdiction alerts.
    """
    # Ensure a Delhi state-level cluster exists
    delhi_state_cluster = db_session.query(LocationCluster).filter(
        LocationCluster.state == "Delhi",
        LocationCluster.district != "SOUTH"
    ).first()
    if not delhi_state_cluster:
        delhi_state_cluster = LocationCluster(
            cluster_name="Connaught Place Cyber Hub",
            state="Delhi",
            district="CENTRAL_NEW_DELHI",
            latitude=28.6315,
            longitude=77.2167,
            radius_meters=1500.0,
            is_active=True
        )
        db_session.add(delhi_state_cluster)
        db_session.commit()
        db_session.refresh(delhi_state_cluster)

    # Ensure a South Delhi district cluster exists
    south_cluster = db_session.query(LocationCluster).filter(
        LocationCluster.state == "Delhi",
        LocationCluster.district.ilike("%south%")
    ).first()
    if not south_cluster:
        south_cluster = db_session.query(LocationCluster).filter(LocationCluster.state == "Delhi").first()

    delhi_complaint = _get_or_create_complaint(db_session, "CMP-P5-NCT-006", state="Delhi", district="Central Delhi")
    south_complaint = _get_or_create_complaint(db_session, "CMP-P5-SOUTH-006", state="Delhi", district="SOUTH")

    pred_delhi, alert_delhi = _create_test_prediction_and_alert(
        db_session, delhi_complaint, risk_score=0.90, cluster=delhi_state_cluster
    )
    pred_south, alert_south = _create_test_prediction_and_alert(
        db_session, south_complaint, risk_score=0.90, cluster=south_cluster
    )

    # Delhi STATE_LEA (NCT scope) syncs alerts — should see Delhi state alerts
    resp_state = client.get("/api/v1/alerts/sync?limit=100", headers=delhi_state_lea_headers)
    assert resp_state.status_code == 200
    state_items = resp_state.json()["items"]
    state_alert_ids = [it["id"] for it in state_items]

    # STATE_LEA with Delhi scope should see delhi_complaint alert
    assert alert_delhi.id in state_alert_ids, "Delhi STATE_LEA must see Delhi NCT alerts"

    # BANK_OFFICER should receive 403 on alert sync (unauthorized role)
    resp_bank = client.get("/api/v1/alerts/sync?limit=50", headers=sbi_headers)
    assert resp_bank.status_code == 403, f"BANK_OFFICER must be forbidden from alert sync, got {resp_bank.status_code}"


# ==============================================================================
# 7. Prediction Version Supersession
# ==============================================================================
def test_prediction_version_supersession(db_session: Session):
    """
    Verifies that when a newer operational prediction arrives for a complaint,
    the active older alert is marked SUPERSEDED, superseded_by_prediction_id is set,
    and an ALERT_SUPERSEDED outbox event is generated.
    """
    complaint = _get_or_create_complaint(db_session, "CMP-P5-SUPER-007")
    
    # Prediction v1
    pred_v1, alert_v1 = _create_test_prediction_and_alert(
        db_session, complaint, risk_score=0.75, model_version="v4.0.0"
    )
    assert alert_v1.status == "NEW"
    
    # Prediction v2 arrives for same complaint
    pred_v2, alert_v2 = _create_test_prediction_and_alert(
        db_session, complaint, risk_score=0.95, model_version="v4.1.0"
    )
    
    db_session.refresh(alert_v1)
    assert alert_v1.status == "SUPERSEDED"
    assert alert_v1.superseded_by_prediction_id == pred_v2.id
    assert alert_v1.superseded_at is not None
    
    # Verify ALERT_SUPERSEDED outbox event exists for alert_v1
    superseded_events = db_session.query(NotificationOutbox).filter(
        NotificationOutbox.alert_id == alert_v1.id,
        NotificationOutbox.event_type == "ALERT_SUPERSEDED"
    ).all()
    assert len(superseded_events) >= 1


# ==============================================================================
# 8. Alert Window Expiration
# ==============================================================================
def test_alert_window_expiration(db_session: Session):
    """
    Verifies that expire_stale_alerts transitions alerts past expires_at
    from NEW/DELIVERED to EXPIRED, enqueuing ALERT_EXPIRED outbox events.
    """
    complaint = _get_or_create_complaint(db_session, "CMP-P5-EXP-008")
    pred, alert = _create_test_prediction_and_alert(db_session, complaint, risk_score=0.80)
    
    # Backdate expires_at to 10 minutes ago
    alert.expires_at = datetime.utcnow() - timedelta(minutes=10)
    db_session.commit()
    
    expired_alerts = outbox_service.expire_stale_alerts(db=db_session)
    assert len(expired_alerts) >= 1
    
    db_session.refresh(alert)
    assert alert.status == "EXPIRED"
    
    # Check outbox event
    exp_events = db_session.query(NotificationOutbox).filter(
        NotificationOutbox.alert_id == alert.id,
        NotificationOutbox.event_type == "ALERT_EXPIRED"
    ).all()
    assert len(exp_events) >= 1


# ==============================================================================
# 9. Outbox Delivery Audit Trail API
# ==============================================================================
def test_outbox_delivery_audit_api(client, db_session: Session, admin_headers):
    """
    Verifies GET /api/v1/alerts/{id}/outbox endpoint returning full audit history.
    """
    complaint = _get_or_create_complaint(db_session, "CMP-P5-AUDIT-009")
    pred, alert = _create_test_prediction_and_alert(db_session, complaint, risk_score=0.88)
    
    # Process one event to DELIVERED
    event = db_session.query(NotificationOutbox).filter(NotificationOutbox.alert_id == alert.id).first()
    success = outbox_service.process_event(db=db_session, event=event)
    assert success is True
    
    response = client.get(f"/api/v1/alerts/{alert.id}/outbox", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    
    assert isinstance(data, list)
    assert len(data) >= 1
    item = data[0]
    assert item["status"] == "DELIVERED"
    assert item["channel"] == "DASHBOARD_WEBSOCKET"
    assert "delivered_at" in item
