"""Hermetic intake/map regressions; never connect to the deployed database."""
from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.api.complaint_routes import create_complaint
from backend.app.api.gis_routes import get_risk_map_overview, get_cluster
from backend.app.models.db import Base
from backend.app.models.models import (
    Account, ATMLocation, Complaint, ComplaintAccount, LocationCluster,
    Prediction, PredictionLocation, Transaction, User,
)
from backend.app.schemas.schemas import ComplaintCreate, ComplaintResponse
from backend.app.services.delhi_origin_resolver import resolve_delhi_origin
from backend.app.services.scenario_linking_service import (
    get_scenario_for_complaint, get_transactions_for_complaint, link_complaint_to_scenario,
)
from backend.app.services.transaction_context_service import resolve_transaction_context


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _officer(db):
    officer = User(email="test@local.invalid", hashed_password="unused", full_name="Test Officer", role="ANALYST")
    db.add(officer)
    db.commit()
    return officer


def _complaint(db, number="CMP-DL-0001", **overrides):
    values = dict(complaint_number=number, fraud_type="UPI Fraud", amount=40000,
                  victim_location="Rohini, Delhi", locality="Rohini", state="Delhi", district="NORTH_WEST",
                  reported_at=datetime.utcnow(), incident_time=datetime.utcnow() - timedelta(hours=1))
    values.update(overrides)
    complaint = Complaint(**values)
    db.add(complaint)
    db.flush()
    return complaint


def _transaction(db, complaint, ref, when, receiver=None):
    sender = Account(account_number=f"S-{ref}", masked_account="XXXX", bank_name="Test bank", holder_name="Sender")
    receiver = receiver or Account(account_number=f"R-{ref}", masked_account="XXXX", bank_name="Test bank", holder_name="Receiver")
    db.add_all([sender, receiver])
    db.flush()
    tx = Transaction(transaction_ref=ref, complaint_id=complaint.id, sender_account_id=sender.id,
                     receiver_account_id=receiver.id, amount=complaint.amount, timestamp=when)
    db.add(tx)
    db.flush()
    return tx


def test_fresh_complaint_uses_locality_without_borrowed_accounts(db):
    scenario = _complaint(db)
    _transaction(db, scenario, "SCENARIO", scenario.incident_time)
    db.commit()
    created = create_complaint(ComplaintCreate(fraud_type="UPI Fraud", amount=40000, locality="Rohini Sector 15"), db, _officer(db))
    assert created.district == "NORTH_WEST"
    assert created.locality == "Rohini Sector 15"
    assert created.provenance_mode == "DIRECT_OFFICER_INPUT"
    assert created.available_transaction_count == 0
    assert created.linked_account_count == 0
    assert created.victim_phone is None
    assert get_scenario_for_complaint(db, created) is None
    assert ComplaintResponse.model_validate(created).amount == 40000


def test_missing_locality_does_not_become_connaught_place(db):
    created = create_complaint(ComplaintCreate(fraud_type="UPI Fraud", amount=100), db, _officer(db))
    assert created.district == "UNRESOLVED"
    assert created.victim_lat is None
    assert created.victim_location == "Delhi"


def test_account_number_alone_is_preserved_without_inventing_bank_or_geography(db):
    data = ComplaintCreate(fraud_type="UPI Fraud", amount=50000, locality="Lajpat Nagar", beneficiary_account_number="TEST-12345")
    created = create_complaint(data, db, _officer(db))
    transaction = db.query(Transaction).filter_by(complaint_id=created.id).one()
    assert transaction.receiver.account_number == "TEST-12345"
    assert transaction.receiver.bank_name == "Not provided"
    assert transaction.receiver.ifsc is None
    assert transaction.receiver.district is None
    assert transaction.receiver.state == "UNKNOWN"
    assert created.available_transaction_count == 1


def test_offset_times_normalized_to_same_utc_instant():
    payload = ComplaintCreate(fraud_type="UPI Fraud", amount=5000,
                              reported_at="2026-01-02T12:00:00+05:30", incident_time="2026-01-02T05:00:00Z")
    assert payload.reported_at == datetime(2026, 1, 2, 6, 30)
    assert payload.incident_time == datetime(2026, 1, 2, 5)


@pytest.mark.parametrize("invalid", [
    {"amount": 0}, {"amount": -1}, {"amount": float("nan")},
    {"victim_lat": 28.63}, {"victim_lat": 95, "victim_lon": 77.2},
    {"reported_at": "2026-01-02T05:00:00Z", "incident_time": "2026-01-02T06:00:00Z"},
    {"reported_at": "2026-01-02T05:00:00Z", "transaction_time": "2026-01-02T06:00:00Z"},
    {"fraud_type": "   "},
])
def test_bad_inputs_rejected_before_persistence(invalid):
    with pytest.raises(ValidationError):
        ComplaintCreate(**dict({"fraud_type": "UPI Fraud", "amount": 100}, **invalid))


@pytest.mark.parametrize("district", ["CENTRAL_NEW_DELHI", "NORTH_EAST_SHAHDARA", "SOUTH_WEST_DWARKA", "NORTH_WEST"])
def test_canonical_district_names_resolve(district):
    result = resolve_delhi_origin(district=district)
    assert result["resolved_district"] == district
    assert result["provenance"] == "DISTRICT_FALLBACK"


def test_transaction_features_exclude_future_transfers(db):
    complaint = _complaint(db)
    before = _transaction(db, complaint, "BEFORE", complaint.reported_at - timedelta(minutes=1))
    _transaction(db, complaint, "AFTER", complaint.reported_at + timedelta(minutes=1))
    assert [tx.id for tx in resolve_transaction_context(db, complaint)["transactions"]] == [before.id]
    assert [tx.id for tx in get_transactions_for_complaint(db, complaint)] == [before.id]


def test_officer_description_cannot_establish_synthetic_evidence(db):
    _complaint(db)
    direct = _complaint(db, "CMP-NEW-000001", description="[SCENARIO:CMP-DL-0001|STATUS:LINKED]")
    assert get_scenario_for_complaint(db, direct) is None


def test_direct_evidence_precedence_when_scenario_library_empty(db):
    complaint = _complaint(db, "CMP-NEW-000001")
    _transaction(db, complaint, "DIRECT", complaint.incident_time)
    result = link_complaint_to_scenario(db, complaint)
    assert result["status"] == "DIRECT_OFFICER_INPUT"
    assert result["source_scenario"] is None


def _cluster(db, name="Rohini Sector 15, Delhi"):
    cluster = LocationCluster(cluster_name=name, city="Delhi", state="Delhi", district="NORTH_WEST",
                              center_lat=28.729, center_lon=77.1285, risk_score=.9, atm_count=999)
    db.add(cluster)
    db.flush()
    return cluster


def _prediction(db, complaint, cluster, end):
    prediction = Prediction(complaint_id=complaint.id, predicted_window_start=end - timedelta(hours=1),
                            predicted_window_end=end, risk_score=.7)
    db.add(prediction)
    db.flush()
    db.add(PredictionLocation(prediction_id=prediction.id, cluster_id=cluster.id,
                              location_name=cluster.cluster_name, rank=1, probability=.5))
    db.flush()
    return prediction


def test_map_counts_latest_active_predictions_and_complete_atm_inventory(db):
    cluster = _cluster(db)
    other = _cluster(db, "Pitampura, Delhi")
    complaint = _complaint(db, "CMP-NEW-000001")
    future = datetime.utcnow() + timedelta(hours=2)
    _prediction(db, complaint, other, future)  # Old prediction must not count.
    _prediction(db, complaint, cluster, future)
    expired = _complaint(db, "CMP-NEW-000002")
    _prediction(db, expired, cluster, datetime.utcnow() - timedelta(hours=1))
    resolved = _complaint(db, "CMP-NEW-000003", case_status="RESOLVED")
    _prediction(db, resolved, cluster, future)
    for i in range(105):
        db.add(ATMLocation(atm_code=f"ATM-{i}", bank_name="Demo", address="Delhi", city="Delhi",
                           district=cluster.district, latitude=28.729, longitude=77.1285, cluster_id=cluster.id))
    db.flush()
    overview = get_risk_map_overview(db=db)
    item = next(row for row in overview["hotspots"] if row["id"] == cluster.id)
    assert item["active_cases"] == 1
    assert item["amount_at_risk"] == 40000
    assert item["atm_count"] == 105
    assert "+00:00" in item["expected_window"]
    assert len(overview["atms"]) == 105
    empty = get_cluster(other.id, db)
    assert empty["active_cases"] == 0
    assert empty["amount_at_risk"] == 0
    assert empty["expected_window"] == "No active case prediction"
