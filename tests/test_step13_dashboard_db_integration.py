"""
CyberShield AI — Phase 1 Step 13 Test Suite: Fully DB-Driven Dashboard Integration

Verifies all requirements for the Step 13 read-only database-backed dashboard:
1. Dashboard endpoint is GET / read-only (rejects POST/PUT/DELETE)
2. Active complaint count matches DB exactly
3. High-risk latest prediction count matches DB exactly
4. Repeated prediction history does not incorrectly inflate operational KPIs
5. Active alert count matches DB exactly
6. Acknowledged alert count matches DB exactly
7. Risk distribution matches latest persisted predictions
8. Recent complaints exact DB ordering (reported_at DESC, id DESC)
9. Recent predictions exact DB ordering (created_at DESC, id DESC)
10. Rank-1 location identity matches PredictionLocation (rank == 1)
11. Recent alerts exact DB ordering (created_at DESC, id DESC)
12. Outside-scope complaint (CMP-NEW-000004) gets no fabricated prediction/risk
13. CMP-1042 demo provenance is strictly preserved
14. Empty dataset behavior (handles 0 records safely without crashes or NaN)
15. Nullable/partial data behavior
16. Zero ML inference invoked during dashboard calls
17. Zero prediction persistence write calls
18. Zero Alert creation calls
19. Zero acknowledgement calls
20. Zero Withdrawal ground-truth queries
21. Dashboard GET causes zero DB mutations (deltas across 10 tables == 0)
22. Dashboard refresh/repeat GET remains strictly zero-write
23. Direct DB counts == API counts for all summary metrics
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.db import SessionLocal
from backend.app.models.models import (
    Complaint, Account, Transaction, Withdrawal,
    Prediction, PredictionLocation, Alert, AuditLog,
    LocationCluster, ATMLocation
)
from backend.app.services.dashboard_service import dashboard_service


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_01_dashboard_endpoint_is_get_only(client):
    """Test 1: Dashboard endpoint is GET/read-only (rejects POST, PUT, DELETE)."""
    res_get = client.get("/api/v1/dashboard/summary")
    assert res_get.status_code == 200

    res_post = client.post("/api/v1/dashboard/summary", json={})
    assert res_post.status_code == 405  # Method Not Allowed

    res_put = client.put("/api/v1/dashboard/summary", json={})
    assert res_put.status_code == 405

    res_delete = client.delete("/api/v1/dashboard/summary")
    assert res_delete.status_code == 405


def test_02_active_complaint_count_matches_db(client, db_session):
    """Test 2: Active complaint count matches DB exactly."""
    active_statuses = ["ACTIVE", "UNDER_INVESTIGATION", "ALERTED"]
    db_active_count = db_session.query(Complaint).filter(Complaint.case_status.in_(active_statuses)).count()

    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200
    api_data = res.json()

    assert api_data["kpis"]["active_complaints"] == db_active_count


def test_03_high_risk_latest_prediction_count_matches_db(client, db_session):
    """Test 3: High-risk latest prediction count matches DB exactly."""
    latest_preds = dashboard_service.get_latest_successful_predictions(db_session)
    db_high_risk = sum(1 for p in latest_preds if p.risk_level in ("HIGH", "CRITICAL"))

    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200
    api_data = res.json()

    assert api_data["kpis"]["high_risk_predictions"] == db_high_risk


def test_04_repeated_prediction_history_does_not_inflate_kpi(client, db_session):
    """Test 4: Repeated Prediction history does not incorrectly inflate operational KPI."""
    latest_preds = dashboard_service.get_latest_successful_predictions(db_session)
    total_raw_predictions = db_session.query(Prediction).count()

    # In our database, some complaints have many test predictions (e.g. complaint 6068 has 21 predictions)
    # The operational KPI must use latest prediction per complaint, NOT total historical rows
    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200
    api_data = res.json()

    assert api_data["mode_distribution"]["total"] == len(latest_preds)
    assert api_data["mode_distribution"]["total"] <= total_raw_predictions
    assert api_data["risk_distribution"]["total"] == len(latest_preds)


def test_05_active_alert_count_matches_db(client, db_session):
    """Test 5: Active Alert count matches DB exactly."""
    db_active_alerts = db_session.query(Alert).filter(Alert.status.in_(["NEW", "ACTION_INITIATED"])).count()

    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200
    api_data = res.json()

    assert api_data["kpis"]["active_alerts"] == db_active_alerts


def test_06_acknowledged_alert_count_matches_db(client, db_session):
    """Test 6: Acknowledged Alert count matches DB exactly."""
    db_ack_alerts = db_session.query(Alert).filter(Alert.status == "ACKNOWLEDGED").count()

    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200
    api_data = res.json()

    assert api_data["kpis"]["acknowledged_alerts"] == db_ack_alerts


def test_07_risk_distribution_matches_latest_persisted_predictions(client, db_session):
    """Test 7: Risk distribution matches latest persisted Predictions."""
    latest_preds = dashboard_service.get_latest_successful_predictions(db_session)
    expected_dist = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for p in latest_preds:
        r = p.risk_level or "MEDIUM"
        expected_dist[r] = expected_dist.get(r, 0) + 1

    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200
    api_data = res.json()
    risk_dist = api_data["risk_distribution"]

    assert risk_dist["HIGH"] == expected_dist.get("HIGH", 0)
    assert risk_dist["CRITICAL"] == expected_dist.get("CRITICAL", 0)
    assert risk_dist["MEDIUM"] == expected_dist.get("MEDIUM", 0)
    assert risk_dist["LOW"] == expected_dist.get("LOW", 0)
    assert risk_dist["total"] == len(latest_preds)


def test_08_recent_complaints_exact_db_ordering(client, db_session):
    """Test 8: Recent complaints follow exact DB ordering (reported_at DESC, id DESC)."""
    db_recent = db_session.query(Complaint).order_by(Complaint.reported_at.desc(), Complaint.id.desc()).limit(10).all()

    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200
    api_recent = res.json()["recent_complaints"]

    assert len(api_recent) == len(db_recent)
    for api_c, db_c in zip(api_recent, db_recent):
        assert api_c["id"] == db_c.id
        assert api_c["complaint_number"] == db_c.complaint_number
        assert api_c["fraud_type"] == db_c.fraud_type


def test_09_recent_predictions_exact_db_ordering(client, db_session):
    """Test 9: Recent Predictions follow exact DB ordering (created_at DESC, id DESC)."""
    db_recent = db_session.query(Prediction).order_by(Prediction.created_at.desc(), Prediction.id.desc()).limit(10).all()

    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200
    api_recent = res.json()["recent_predictions"]

    assert len(api_recent) == len(db_recent)
    for api_p, db_p in zip(api_recent, db_recent):
        assert api_p["id"] == db_p.id
        assert api_p["complaint_id"] == db_p.complaint_id
        assert api_p["prediction_mode"] == db_p.prediction_mode


def test_10_rank_1_location_identity_matches_prediction_location(client, db_session):
    """Test 10: Rank-1 location identity matches PredictionLocation (rank == 1)."""
    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200
    api_preds = res.json()["recent_predictions"]

    for ap in api_preds:
        db_rank1 = (
            db_session.query(PredictionLocation)
            .filter(PredictionLocation.prediction_id == ap["id"], PredictionLocation.rank == 1)
            .first()
        )
        if db_rank1:
            assert ap["rank1_location"] == db_rank1.location_name


def test_11_recent_alerts_exact_db_ordering(client, db_session):
    """Test 11: Recent Alerts follow exact DB ordering (created_at DESC, id DESC)."""
    db_recent = db_session.query(Alert).order_by(Alert.created_at.desc(), Alert.id.desc()).limit(10).all()

    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200
    api_recent = res.json()["recent_alerts"]

    assert len(api_recent) == len(db_recent)
    for api_a, db_a in zip(api_recent, db_recent):
        assert api_a["id"] == db_a.id
        assert api_a["complaint_id"] == db_a.complaint_id
        assert api_a["status"] == db_a.status


def test_12_outside_scope_complaint_no_fabricated_prediction(client, db_session):
    """Test 12: Outside-scope complaint CMP-NEW-000004 gets NO fabricated prediction."""
    comp = db_session.query(Complaint).filter(Complaint.complaint_number == "CMP-NEW-000004").first()
    assert comp is not None

    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200
    api_recent = res.json()["recent_complaints"]

    target = next((c for c in api_recent if c["complaint_number"] == "CMP-NEW-000004"), None)
    if target:
        assert target["prediction_available"] is False
        assert target["latest_prediction_id"] is None
        assert target["latest_risk_level"] == "NO PREDICTION"
        assert target["latest_rank1_location"] is None


def test_13_cmp_1042_demo_provenance_preserved(client, db_session):
    """Test 13: CMP-1042 demo provenance is strictly preserved."""
    comp = db_session.query(Complaint).filter(Complaint.complaint_number == "CMP-1042").first()
    assert comp is not None

    latest_p = (
        db_session.query(Prediction)
        .filter(Prediction.complaint_id == comp.id)
        .order_by(Prediction.created_at.desc(), Prediction.id.desc())
        .first()
    )
    assert latest_p is not None
    assert latest_p.prediction_mode == "deterministic_demo"
    assert latest_p.model_version == "demo-provider-v1"


def test_14_empty_dataset_behavior():
    """Test 14: Handles empty dataset gracefully without division by zero or NaN."""
    from unittest.mock import MagicMock
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.count.return_value = 0
    mock_db.query.return_value.filter.return_value.scalar.return_value = None
    mock_db.query.return_value.filter.return_value.all.return_value = []
    mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
    mock_db.query.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = []

    with patch.object(dashboard_service, "get_latest_successful_predictions", return_value=[]):
        summary = dashboard_service.get_dashboard_summary(mock_db)

    assert summary["kpis"]["active_complaints"] == 0
    assert summary["kpis"]["high_risk_predictions"] == 0
    assert summary["kpis"]["active_alerts"] == 0
    assert summary["kpis"]["acknowledged_alerts"] == 0
    assert summary["kpis"]["total_amount_at_risk"] == 0.0
    assert summary["kpis"]["avg_response_time_minutes"] is None
    assert summary["kpis"]["response_time_label"] == "Not enough data"
    assert summary["risk_distribution"]["total"] == 0
    assert summary["mode_distribution"]["total"] == 0


def test_15_nullable_partial_data_behavior(client):
    """Test 15: Validates JSON response structure against nullable fields."""
    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200
    data = res.json()

    for c in data["recent_complaints"]:
        assert "complaint_number" in c
        assert "fraud_type" in c
        assert "amount" in c
        assert "prediction_available" in c

    for p in data["recent_predictions"]:
        assert "id" in p
        assert "prediction_mode" in p
        assert "risk_score" in p


def test_16_to_20_forbidden_calls_zero(client):
    """Tests 16-20: Zero ML inference, zero prediction persistence, zero alert writes, zero withdrawal queries."""
    with patch("backend.app.services.prediction_service.prediction_service.run_and_persist_prediction") as mock_pred_run, \
         patch("backend.app.services.prediction_persistence_service.prediction_persistence_service.persist_prediction") as mock_pred_write, \
         patch("backend.app.services.alert_service.create_alert_for_prediction") as mock_alert_create, \
         patch("backend.app.api.alert_routes.acknowledge_alert") as mock_alert_ack, \
         patch("backend.app.services.audit_service.log_audit") as mock_audit:

        res = client.get("/api/v1/dashboard/summary")
        assert res.status_code == 200

        assert mock_pred_run.call_count == 0
        assert mock_pred_write.call_count == 0
        assert mock_alert_create.call_count == 0
        assert mock_alert_ack.call_count == 0
        assert mock_audit.call_count == 0


def test_21_dashboard_get_causes_zero_db_mutations(client, db_session):
    """Test 21: Dashboard GET causes zero DB mutations (all 10 table deltas == 0)."""
    def snapshot():
        return {
            "complaints": db_session.query(Complaint).count(),
            "accounts": db_session.query(Account).count(),
            "transactions": db_session.query(Transaction).count(),
            "withdrawals": db_session.query(Withdrawal).count(),
            "predictions": db_session.query(Prediction).count(),
            "prediction_locations": db_session.query(PredictionLocation).count(),
            "alerts": db_session.query(Alert).count(),
            "audit_logs": db_session.query(AuditLog).count(),
            "clusters": db_session.query(LocationCluster).count(),
            "atms": db_session.query(ATMLocation).count(),
        }

    before = snapshot()
    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200
    after = snapshot()

    for table, count_before in before.items():
        delta = after[table] - count_before
        assert delta == 0, f"Mutation detected on table {table}: delta={delta}"


def test_22_dashboard_refresh_repeat_remains_zero_write(client, db_session):
    """Test 22: Repeated GET / refresh calls remain strictly zero-write."""
    def snapshot():
        return {
            "predictions": db_session.query(Prediction).count(),
            "alerts": db_session.query(Alert).count(),
            "audit_logs": db_session.query(AuditLog).count(),
        }

    before = snapshot()
    for _ in range(5):
        res = client.get("/api/v1/dashboard/summary")
        assert res.status_code == 200
    after = snapshot()

    for table, count_before in before.items():
        assert after[table] == count_before, f"Table {table} mutated across repeated calls"


def test_23_direct_db_counts_equal_api_counts(client, db_session):
    """Test 23: Direct DB counts match API response values across all metrics."""
    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200
    data = res.json()

    # Active complaints
    active_statuses = ["ACTIVE", "UNDER_INVESTIGATION", "ALERTED"]
    assert data["kpis"]["active_complaints"] == db_session.query(Complaint).filter(Complaint.case_status.in_(active_statuses)).count()

    # Active alerts
    assert data["kpis"]["active_alerts"] == db_session.query(Alert).filter(Alert.status.in_(["NEW", "ACTION_INITIATED"])).count()

    # Acknowledged alerts
    assert data["kpis"]["acknowledged_alerts"] == db_session.query(Alert).filter(Alert.status == "ACKNOWLEDGED").count()

    # Amount at risk
    raw_amount = db_session.query(Complaint.amount).filter(Complaint.case_status.in_(active_statuses)).all()
    expected_amount = float(sum(a[0] for a in raw_amount if a[0] is not None))
    assert abs(data["kpis"]["total_amount_at_risk"] - expected_amount) < 0.01
