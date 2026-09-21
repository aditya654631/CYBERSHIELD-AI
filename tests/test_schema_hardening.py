import pytest
import datetime
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from sqlalchemy import inspect, Numeric, Float
from backend.app.models.db import SessionLocal, engine
from backend.app.models.models import (
    Base, Organization, User, LocationCluster, ATMLocation,
    Complaint, Account, ComplaintAccount, Transaction, Withdrawal,
    Prediction, PredictionLocation, Alert, CaseNote, AuditLog
)

def test_relationship_and_mapper_configuration():
    """Verify all required SQLAlchemy relationships load and navigate without mapper errors."""
    db = SessionLocal()
    try:
        # 1. Complaint -> Transactions & Predictions & Alerts
        cmp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-1042").first()
        assert cmp is not None
        assert len(cmp.transactions) >= 5
        assert len(cmp.predictions) >= 1
        assert len(cmp.alerts) >= 1

        # 2. Transaction -> Sender Account & Receiver Account
        tx = cmp.transactions[0]
        assert tx.sender is not None
        assert tx.receiver is not None
        assert tx.sender.account_number != tx.receiver.account_number

        # 3. Prediction -> Complaint & PredictionLocations
        pred = cmp.predictions[0]
        assert pred.complaint.id == cmp.id
        assert len(pred.locations) == 3

        # 4. PredictionLocation -> LocationCluster
        pred_loc = pred.locations[0]
        assert pred_loc.cluster is not None
        assert pred_loc.prediction.id == pred.id

        # 5. Alert -> Complaint & Prediction
        alert = cmp.alerts[0]
        assert alert.complaint.id == cmp.id
        if alert.prediction_id:
            assert alert.prediction is not None
            assert alert.prediction.id in [p.id for p in cmp.predictions]

        # 6. AuditLog -> User (nullable reference)
        user = db.query(User).first()
        assert user is not None
        test_audit = AuditLog(
            user_id=user.id,
            officer_name=user.full_name,
            role=user.role,
            action="SCHEMA_TEST_ACTION",
            details="Verifying AuditLog -> User relationship"
        )
        db.add(test_audit)
        db.flush()
        assert test_audit.user is not None
        assert test_audit.user.email == user.email
        db.rollback()

    finally:
        db.close()


def test_complaint_account_association_and_uniqueness():
    """Verify Complaint <-> Account association table and UNIQUE(complaint_id, account_id) constraint."""
    db = SessionLocal()
    try:
        cmp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-1042").first()
        assert cmp is not None
        existing_acc_ids = {ca.account_id for ca in db.query(ComplaintAccount).filter(ComplaintAccount.complaint_id == cmp.id).all()}
        acc = db.query(Account).filter(~Account.id.in_(existing_acc_ids)).first()
        assert acc is not None

        # Link account to complaint
        assoc = ComplaintAccount(
            complaint_id=cmp.id,
            account_id=acc.id,
            association_type="SUSPECT"
        )
        db.add(assoc)
        db.commit()

        # Verify navigation
        db.refresh(cmp)
        assert acc in cmp.accounts
        assert cmp in acc.complaints

        # Negative test: Duplicate (complaint_id, account_id) must raise IntegrityError
        dup_assoc = ComplaintAccount(
            complaint_id=cmp.id,
            account_id=acc.id,
            association_type="BENEFICIARY"
        )
        db.add(dup_assoc)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        # Clean up test association
        db.query(ComplaintAccount).filter(
            ComplaintAccount.complaint_id == cmp.id,
            ComplaintAccount.account_id == acc.id
        ).delete()
        db.commit()

    finally:
        db.close()


def test_unique_prediction_rank_constraint():
    """Verify UNIQUE(prediction_id, rank) database constraint on prediction_locations."""
    db = SessionLocal()
    try:
        pred = db.query(Prediction).first()
        assert pred is not None

        # Existing ranks are 1, 2, 3. Attempting to insert another location with rank=1 must fail.
        duplicate_rank_loc = PredictionLocation(
            prediction_id=pred.id,
            cluster_id=None,
            location_name="Illegal Duplicate Rank Zone",
            rank=1,
            probability=0.50,
            latitude=22.7,
            longitude=75.8
        )
        db.add(duplicate_rank_loc)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    finally:
        db.close()


def test_complaint_coordinates_nullable_no_fake_defaults():
    """Verify missing coordinates remain explicitly None with zero fake defaults."""
    db = SessionLocal()
    try:
        complaint = Complaint(
            complaint_number="CMP-TEST-NO-COORDS",
            fraud_type="UPI Phishing",
            amount=Decimal("45000.00"),
            victim_name="No Coords Citizen",
            victim_location="Unknown rural outpost",
            state="Madhya Pradesh",
            district="Bhopal",
            payment_channel="UPI"
        )
        db.add(complaint)
        db.commit()
        db.refresh(complaint)

        assert complaint.victim_lat is None
        assert complaint.victim_lon is None
        assert complaint.victim_latitude is None
        assert complaint.victim_longitude is None

        # Clean up test record
        db.delete(complaint)
        db.commit()

    finally:
        db.close()


def test_financial_amounts_numeric_and_ml_probabilities_float():
    """Verify monetary amounts use Numeric(14, 2) while ML probabilities remain Float."""
    insp = inspect(engine)

    # 1. Monetary fields MUST use Numeric / DECIMAL
    complaint_amount = [c for c in insp.get_columns("complaints") if c["name"] == "amount"][0]
    assert isinstance(complaint_amount["type"], Numeric)

    tx_amount = [c for c in insp.get_columns("transactions") if c["name"] == "amount"][0]
    assert isinstance(tx_amount["type"], Numeric)

    withdrawal_amount = [c for c in insp.get_columns("withdrawals") if c["name"] == "amount"][0]
    assert isinstance(withdrawal_amount["type"], Numeric)

    alert_amount = [c for c in insp.get_columns("alerts") if c["name"] == "amount_at_risk"][0]
    assert isinstance(alert_amount["type"], Numeric)

    # 2. ML Probability and score fields MUST remain Float
    pred_risk = [c for c in insp.get_columns("predictions") if c["name"] == "risk_score"][0]
    assert isinstance(pred_risk["type"], Float)

    pred_loc_prob = [c for c in insp.get_columns("prediction_locations") if c["name"] == "probability"][0]
    assert isinstance(pred_loc_prob["type"], Float)


def test_important_indexes_exist():
    """Verify important indexes exist on foreign keys, ranks, and status columns."""
    insp = inspect(engine)

    indexes_by_table = {
        table: [idx["name"] for idx in insp.get_indexes(table)]
        for table in insp.get_table_names()
    }

    # Verify key indexes exist
    assert any("complaint_id" in idx for idx in indexes_by_table.get("transactions", []))
    assert any("sender_account_id" in idx for idx in indexes_by_table.get("transactions", []))
    assert any("receiver_account_id" in idx for idx in indexes_by_table.get("transactions", []))
    assert any("timestamp" in idx for idx in indexes_by_table.get("transactions", []))
    assert any("case_status" in idx for idx in indexes_by_table.get("complaints", []))
    assert any("rank" in idx for idx in indexes_by_table.get("prediction_locations", []))
    assert any("prediction_id" in idx for idx in indexes_by_table.get("alerts", []))
    assert any("user_id" in idx for idx in indexes_by_table.get("audit_logs", []))
