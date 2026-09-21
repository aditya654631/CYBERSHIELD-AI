import datetime
import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, Numeric, UniqueConstraint, JSON, Index, event
)
from sqlalchemy.orm import relationship, synonym
from backend.app.models.db import Base

class Region(Base):
    __tablename__ = "regions"

    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    state = Column(String(100), nullable=False, index=True)
    catalog_version = Column(String(50), nullable=False)
    source = Column(String(255), nullable=False)
    license = Column(String(255), nullable=False)
    verification_time = Column(DateTime(timezone=True), nullable=True)
    center_lat = Column(Float, nullable=False)
    center_lon = Column(Float, nullable=False)
    bounds_min_lat = Column(Float, nullable=False)
    bounds_max_lat = Column(Float, nullable=False)
    bounds_min_lon = Column(Float, nullable=False)
    bounds_max_lon = Column(Float, nullable=False)
    cluster_radius_km = Column(Float, default=2.5)
    districts = Column(JSON, nullable=True)
    data_completeness_status = Column(String(50), default="COMPLETE")
    model_support_status = Column(String(50), default="UNSUPPORTED", index=True)
    supported_model_version = Column(String(100), nullable=True)
    is_synthetic = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=True)

    clusters = relationship("LocationCluster", back_populates="region")
    atms = relationship("ATMLocation", back_populates="region")
    complaints = relationship("Complaint", back_populates="region")
    catalogs = relationship("GeographyCatalog", back_populates="region", cascade="all, delete-orphan")

class GeographyCatalog(Base):
    __tablename__ = "geography_catalogs"

    id = Column(Integer, primary_key=True, index=True)
    catalog_id = Column(String(100), unique=True, index=True, nullable=False)
    region_id = Column(String(50), ForeignKey("regions.id", ondelete="CASCADE"), nullable=False, index=True)
    catalog_version = Column(String(50), nullable=False)
    source = Column(String(255), nullable=False)
    license = Column(String(255), nullable=False)
    provenance_notes = Column(Text, nullable=True)
    verification_time = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(50), default="ACTIVE", index=True)
    data_completeness_status = Column(String(50), default="COMPLETE")
    model_support_status = Column(String(50), default="UNSUPPORTED")
    supported_model_version = Column(String(100), nullable=True)
    total_clusters = Column(Integer, default=0)
    total_atms = Column(Integer, default=0)
    cluster_radius_km = Column(Float, default=2.5)
    catalog_payload = Column(JSON, nullable=True)
    imported_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    imported_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    region = relationship("Region", back_populates="catalogs")
    imported_by = relationship("User", foreign_keys=[imported_by_user_id])

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    org_type = Column(String(50), default="LEA")  # LEA, BANK, I4C
    state = Column(String(100), default="Delhi")
    district = Column(String(100), default="CENTRAL_NEW_DELHI")
    region_id = Column(String(50), ForeignKey("regions.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    users = relationship("User", back_populates="organization")
    owned_complaints = relationship("Complaint", foreign_keys="[Complaint.owner_organization_id]")
    bank_accounts = relationship("Account", foreign_keys="[Account.bank_organization_id]")
    bank_actions = relationship("BankAction", foreign_keys="[BankAction.bank_organization_id]")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), default="ANALYST")  # I4C_ADMIN, STATE_LEA, DISTRICT_LEA, BANK_OFFICER, ANALYST, AUDITOR
    badge_number = Column(String(50), default="CS-7701")
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    organization = relationship("Organization", back_populates="users")
    case_notes = relationship("CaseNote", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")
    transactions_created = relationship("Transaction", back_populates="created_by_user", foreign_keys="[Transaction.created_by_user_id]")

    @property
    def state(self):
        return self.organization.state if self.organization and self.organization.state else None

    @property
    def district(self):
        return self.organization.district if self.organization and self.organization.district else None

    @property
    def organization_name(self):
        return self.organization.name if self.organization else None

class LocationCluster(Base):
    __tablename__ = "location_clusters"

    id = Column(Integer, primary_key=True, index=True)
    cluster_name = Column(String(255), nullable=False)
    city = Column(String(100), nullable=False)
    district = Column(String(100), nullable=False)
    state = Column(String(100), default="Delhi")
    region_id = Column(String(50), ForeignKey("regions.id", ondelete="SET NULL"), nullable=True, index=True)
    center_lat = Column(Float, nullable=False)
    center_lon = Column(Float, nullable=False)
    radius_km = Column(Float, default=2.5)
    historical_fraud_count = Column(Integer, default=0)
    atm_count = Column(Integer, default=0)
    risk_score = Column(Float, default=0.5)

    region = relationship("Region", back_populates="clusters")
    atms = relationship("ATMLocation", back_populates="cluster")
    prediction_locations = relationship("PredictionLocation", back_populates="cluster")

class ATMLocation(Base):
    __tablename__ = "atm_locations"

    id = Column(Integer, primary_key=True, index=True)
    atm_code = Column(String(50), unique=True, index=True)
    bank_name = Column(String(100), nullable=False)
    address = Column(String(255), nullable=False)
    city = Column(String(100), nullable=False)
    district = Column(String(100), nullable=False)
    state = Column(String(100), default="Delhi")
    region_id = Column(String(50), ForeignKey("regions.id", ondelete="SET NULL"), nullable=True, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    cash_available = Column(Boolean, default=True)

    risk_rating = Column(String(20), default="MEDIUM")
    cluster_id = Column(Integer, ForeignKey("location_clusters.id"), nullable=True)

    region = relationship("Region", back_populates="atms")
    cluster = relationship("LocationCluster", back_populates="atms")

class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True)
    complaint_number = Column(String(50), unique=True, index=True, nullable=False)
    fraud_type = Column(String(100), nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    victim_name = Column(String(255), nullable=True)
    victim_phone = Column(String(50), nullable=True)
    victim_location = Column(String(255), nullable=False)
    state = Column(String(100), default="Delhi")
    district = Column(String(100), default="CENTRAL_NEW_DELHI")
    region_id = Column(String(50), ForeignKey("regions.id", ondelete="SET NULL"), nullable=True)
    payment_channel = Column(String(50), default="UPI")
    reported_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    incident_time = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    victim_lat = Column(Float, nullable=True)
    victim_lon = Column(Float, nullable=True)
    description = Column(Text, nullable=True)
    locality = Column(String(255), nullable=True)
    provenance_mode = Column(String(50), default="DIRECT_OFFICER_INPUT", nullable=True)
    risk_level = Column(String(20), default="MEDIUM")  # CRITICAL, HIGH, MEDIUM, LOW
    risk_score = Column(Float, nullable=True)
    prediction_status = Column(String(50), default="PENDING")  # PENDING, COMPLETED, IN_PROGRESS
    case_status = Column(String(50), default="ACTIVE", index=True)  # ACTIVE, UNDER_INVESTIGATION, ALERTED, RESOLVED
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    # Trusted server-side ownership. Historical rows remain NULL rather than receiving
    # guessed ownership during migration.
    owner_organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_complaints_state_district", "state", "district"),
        Index("ix_complaints_reported_at", "reported_at"),
        Index("ix_complaints_owner_organization_id", "owner_organization_id"),
        Index("ix_complaints_owner_user_id", "owner_user_id"),
        Index("ix_complaints_region_id", "region_id"),
    )

    # Synonyms for flexible compatibility with callers, ML pipelines, and test suites
    victim_latitude = synonym("victim_lat")
    victim_longitude = synonym("victim_lon")
    victim_state = synonym("state")
    complainant_name = synonym("victim_name")
    complainant_phone = synonym("victim_phone")
    incident_at = synonym("incident_time")
    status = synonym("case_status")

    region = relationship("Region", back_populates="complaints")
    transactions = relationship("Transaction", back_populates="complaint", cascade="all, delete-orphan")
    predictions = relationship("Prediction", back_populates="complaint", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="complaint", cascade="all, delete-orphan")
    case_notes = relationship("CaseNote", back_populates="complaint", cascade="all, delete-orphan")
    evidence_files = relationship("EvidenceFile", back_populates="complaint", cascade="all, delete-orphan")
    handoffs = relationship("CaseHandoff", back_populates="complaint", cascade="all, delete-orphan")
    outcome_observations = relationship("OutcomeObservation", back_populates="complaint", cascade="all, delete-orphan", foreign_keys="[OutcomeObservation.complaint_id]")
    accounts = relationship("Account", secondary="complaint_accounts", back_populates="complaints")
    withdrawals = relationship("Withdrawal", back_populates="complaint", cascade="all, delete-orphan")
    owner_organization = relationship("Organization", foreign_keys=[owner_organization_id], overlaps="owned_complaints")
    owner_user = relationship("User", foreign_keys=[owner_user_id])

class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    account_number = Column(String(100), unique=True, index=True, nullable=False)
    masked_account = Column(String(50), nullable=False)
    bank_name = Column(String(100), nullable=False)
    branch = Column(String(100), nullable=True)
    ifsc = Column(String(50), nullable=True)
    holder_name = Column(String(255), nullable=False)
    account_type = Column(String(50), default="SAVINGS")  # SAVINGS, CURRENT, WALLET
    state = Column(String(100), default="Delhi", nullable=True)
    district = Column(String(100), nullable=True)
    risk_score = Column(Float, default=None, nullable=True)
    is_mule = Column(Boolean, default=False)
    flag_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    # Once resolved by the server, this organization id is the authority for bank
    # visibility. bank_name remains presentation/provenance text only.
    bank_organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_accounts_bank_organization_id", "bank_organization_id"),
    )

    complaints = relationship("Complaint", secondary="complaint_accounts", back_populates="accounts")
    sent_transactions = relationship("Transaction", foreign_keys="[Transaction.sender_account_id]", back_populates="sender")
    received_transactions = relationship("Transaction", foreign_keys="[Transaction.receiver_account_id]", back_populates="receiver")
    bank_organization = relationship("Organization", foreign_keys=[bank_organization_id], overlaps="bank_accounts")

class ComplaintAccount(Base):
    __tablename__ = "complaint_accounts"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    association_type = Column(String(50), default="SUSPECT")  # VICTIM, SUSPECT, BENEFICIARY, INTERMEDIARY
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("complaint_id", "account_id", name="uq_complaint_account"),
    )

    complaint = relationship("Complaint", foreign_keys=[complaint_id], overlaps="accounts,complaints")
    account = relationship("Account", foreign_keys=[account_id], overlaps="accounts,complaints")

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    transaction_ref = Column(String(100), unique=True, index=True, nullable=False)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False, index=True)
    sender_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)
    receiver_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)
    amount = Column(Numeric(14, 2), nullable=False)
    payment_channel = Column(String(50), default="UPI")
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    received_at = Column(DateTime, nullable=True, index=True)
    source_system = Column(String(100), default="DIRECT_OFFICER_INPUT", nullable=True)
    dedup_key = Column(String(64), nullable=True, index=True)
    is_reversal = Column(Boolean, default=False, nullable=False)
    correction_of_ref = Column(String(100), nullable=True)
    hop_number = Column(Integer, default=1)
    status = Column(String(50), default="COMPLETED")
    analysis_status = Column(String(50), default="COMPLETED", nullable=True)
    prediction_id = Column(Integer, ForeignKey("predictions.id", ondelete="SET NULL"), nullable=True)
    suspicious_flag = Column(Boolean, default=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint("transaction_ref", name="uq_transactions_transaction_ref"),
        Index("ix_transactions_comp_hop", "complaint_id", "hop_number"),
        Index("ix_transactions_source_ref", "source_system", "transaction_ref"),
        Index("ix_transactions_created_by_user_id", "created_by_user_id"),
    )

    complaint = relationship("Complaint", back_populates="transactions")
    sender = relationship("Account", foreign_keys=[sender_account_id], back_populates="sent_transactions")
    receiver = relationship("Account", foreign_keys=[receiver_account_id], back_populates="received_transactions")
    created_by_user = relationship("User", foreign_keys=[created_by_user_id], back_populates="transactions_created")

    # Synonyms for seamless caller compatibility
    transaction_reference = synonym("transaction_ref")
    source_account_id = synonym("sender_account_id")
    destination_account_id = synonym("receiver_account_id")
    channel = synonym("payment_channel")

class Withdrawal(Base):
    __tablename__ = "withdrawals"

    id = Column(Integer, primary_key=True, index=True)
    withdrawal_ref = Column(String(100), unique=True, index=True, nullable=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id", ondelete="SET NULL"), nullable=True, index=True)
    atm_id = Column(Integer, ForeignKey("atm_locations.id"), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)
    amount = Column(Numeric(14, 2), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    success = Column(Boolean, default=True)
    camera_flagged = Column(Boolean, default=False)

    complaint = relationship("Complaint", back_populates="withdrawals")
    atm = relationship("ATMLocation", foreign_keys=[atm_id])
    account = relationship("Account", foreign_keys=[account_id])
class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    parent_prediction_id = Column(Integer, ForeignKey("predictions.id"), nullable=True)
    analysis_as_of = Column(DateTime, nullable=True)
    # Explicit persisted purpose: 'OPERATIONAL' or 'HISTORICAL_REPLAY'.
    # Replaces the "within 5 minutes of created_at" heuristic: a recent-cutoff historical replay
    # must never become operational merely because its cutoff is close to now.
    analysis_purpose = Column(String(50), nullable=True, default=None)
    input_fingerprint = Column(String(64), nullable=True, index=True)
    prediction_mode = Column(String(50), default="deterministic_demo")
    model_version = Column(String(50), default="demo-provider-v1")
    time_model_version = Column(String(100), nullable=True)
    predicted_minutes_to_cashout = Column(Float, nullable=True)
    result_metadata = Column(JSON, nullable=True)
    predicted_window_start = Column(DateTime, nullable=False)
    predicted_window_end = Column(DateTime, nullable=False)
    window_label = Column(String(100), default="Next 2–4 Hours")
    primary_cluster_id = Column(Integer, ForeignKey("location_clusters.id"), nullable=True)
    risk_score = Column(Float, default=0.85)
    risk_level = Column(String(50), default="CRITICAL")
    confidence_score = Column(Float, default=0.92)
    ml_score = Column(Float, default=0.88)
    graph_score = Column(Float, default=0.85)
    geo_score = Column(Float, default=0.84)
    temporal_score = Column(Float, default=0.80)
    intervention_priority = Column(Integer, default=94)
    why_explanation = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    __table_args__ = (
        UniqueConstraint("complaint_id", "version_number", name="uq_complaint_version_number"),
        Index("ix_predictions_comp_input_fp", "complaint_id", "input_fingerprint"),
        Index("ix_predictions_analysis_as_of", "analysis_as_of"),
    )

    complaint = relationship("Complaint", back_populates="predictions")
    locations = relationship("PredictionLocation", back_populates="prediction", cascade="all, delete-orphan")
    alerts = relationship("Alert", foreign_keys="[Alert.prediction_id]", back_populates="prediction")
    snapshot = relationship("PredictionSnapshot", back_populates="prediction", uselist=False, cascade="all, delete-orphan")
    parent_prediction = relationship("Prediction", remote_side=[id], backref="child_predictions")


@event.listens_for(Prediction, "before_insert")
def _prediction_before_insert(mapper, connection, target):
    if target.version_number is None:
        if target.complaint_id is not None:
            from sqlalchemy import select, func
            max_v = connection.execute(
                select(func.max(Prediction.__table__.c.version_number)).where(
                    Prediction.__table__.c.complaint_id == target.complaint_id
                )
            ).scalar()
            target.version_number = 1 if max_v is None else max_v + 1
        else:
            target.version_number = 1

class PredictionSnapshot(Base):
    """
    Phase 5: Immutable Inference Feature Snapshot for Faithful Explanations.
    Captures the exact ordered candidate feature matrix, schema version/hash,
    model/calibrator hashes, official candidate outputs, and provenance
    at the exact instant inference is executed. Never reconstructed dynamically.
    """
    __tablename__ = "prediction_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    prediction_id = Column(Integer, ForeignKey("predictions.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False, index=True)
    model_version = Column(String(100), nullable=False)
    feature_schema_version = Column(String(50), nullable=False)
    feature_schema_hash = Column(String(64), nullable=True)
    model_hash = Column(String(64), nullable=True)
    calibrator_hash = Column(String(64), nullable=True)
    snapshot_data = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    prediction = relationship("Prediction", back_populates="snapshot")
    complaint = relationship("Complaint")


@event.listens_for(PredictionSnapshot, "before_update")
def _prediction_snapshot_before_update(mapper, connection, target):
    raise ValueError("PredictionSnapshot is write-once and immutable; historical snapshot updates are strictly prohibited.")


class PredictionLocation(Base):
    __tablename__ = "prediction_locations"

    id = Column(Integer, primary_key=True, index=True)
    prediction_id = Column(Integer, ForeignKey("predictions.id"), nullable=False, index=True)
    cluster_id = Column(Integer, ForeignKey("location_clusters.id"), nullable=True, index=True)
    location_name = Column(String(255), nullable=False)
    rank = Column(Integer, nullable=False, index=True)
    probability = Column(Float, nullable=False)
    risk_level = Column(String(50), default="CRITICAL")
    distance_km = Column(Float, default=185.0)
    reasoning = Column(String(255), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint("prediction_id", "rank", name="uq_prediction_rank"),
    )

    prediction = relationship("Prediction", back_populates="locations")
    cluster = relationship("LocationCluster", back_populates="prediction_locations")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False, index=True)
    prediction_id = Column(Integer, ForeignKey("predictions.id"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    severity = Column(String(50), default="CRITICAL")  # CRITICAL, HIGH, MEDIUM, LOW
    location_name = Column(String(255), nullable=False)
    risk_score = Column(Float, default=0.87)
    expected_window = Column(String(100), default="Next 2–4 Hours")
    amount_at_risk = Column(Numeric(14, 2), default=125000.0)
    status = Column(String(50), default="NEW")  # NEW, DELIVERED, ACKNOWLEDGED, ACTION_INITIATED, EXPIRED, SUPERSEDED, RESOLVED
    acknowledged_by = Column(String(255), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    action_notes = Column(Text, nullable=True)
    superseded_by_prediction_id = Column(Integer, ForeignKey("predictions.id", ondelete="SET NULL"), nullable=True)
    superseded_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_alerts_comp_pred_status", "complaint_id", "prediction_id", "status"),
        Index("ix_alerts_expires_at", "expires_at"),
    )

    complaint = relationship("Complaint", back_populates="alerts")
    prediction = relationship("Prediction", foreign_keys=[prediction_id], back_populates="alerts")
    superseded_by_prediction = relationship("Prediction", foreign_keys=[superseded_by_prediction_id])
    outbox_events = relationship("NotificationOutbox", back_populates="alert", cascade="all, delete-orphan")


class NotificationOutbox(Base):
    """
    Phase 5: Persistent Transactional Notification Outbox.
    Ensures alert creation, acknowledgement, escalation, and supersession
    events commit atomically in the database and are durably dispatched to recipients.
    """
    __tablename__ = "notification_outbox"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)  # ALERT_CREATED, ALERT_ACKNOWLEDGED, ALERT_ESCALATED, ALERT_SUPERSEDED, ALERT_EXPIRED
    prediction_id = Column(Integer, ForeignKey("predictions.id", ondelete="SET NULL"), nullable=True, index=True)
    prediction_version = Column(Integer, nullable=True)
    channel = Column(String(50), default="DASHBOARD_WEBSOCKET", index=True)  # DASHBOARD_WEBSOCKET, API_POLL, SIMULATED_SMS, SIMULATED_EMAIL
    recipient_role = Column(String(50), nullable=True)
    recipient_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    recipient_organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    recipient_state = Column(String(100), nullable=True)
    recipient_district = Column(String(100), nullable=True)
    payload = Column(JSON, nullable=False)
    status = Column(String(50), default="QUEUED", index=True)  # QUEUED, PROCESSING, DELIVERED, FAILED, PERMANENT_FAILURE, ACKNOWLEDGED, ESCALATED, EXPIRED, SUPERSEDED, RESOLVED
    attempt_count = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=5, nullable=False)
    next_retry_at = Column(DateTime, nullable=True, index=True)
    last_attempt_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    worker_id = Column(String(100), nullable=True)
    locked_at = Column(DateTime, nullable=True)
    lease_expires_at = Column(DateTime, nullable=True, index=True)
    delivered_at = Column(DateTime, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(String(255), nullable=True)
    idempotency_key = Column(String(128), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    __table_args__ = (
        Index("ix_outbox_status_retry", "status", "next_retry_at"),
        Index("ix_outbox_lease", "status", "lease_expires_at"),
    )

    alert = relationship("Alert", back_populates="outbox_events")
    prediction = relationship("Prediction")
    recipient_user = relationship("User", foreign_keys=[recipient_user_id])
    recipient_organization = relationship("Organization", foreign_keys=[recipient_organization_id])


class CaseNote(Base):
    __tablename__ = "case_notes"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    note = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    complaint = relationship("Complaint", back_populates="case_notes")
    user = relationship("User", back_populates="case_notes")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    officer_name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)
    action = Column(String(100), nullable=False)  # LOGIN, CASE_VIEWED, PREDICTION_RUN, NETWORK_VIEWED, ALERT_CREATED, ALERT_ACKNOWLEDGED, ALERT_ESCALATED
    case_number = Column(String(100), nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(50), default="127.0.0.1")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_audit_logs_user_created_at", "user_id", "created_at"),
    )

    user = relationship("User", back_populates="audit_logs")

class BankAction(Base):
    __tablename__ = "bank_actions"

    id = Column(Integer, primary_key=True, index=True)
    action_reference = Column(String(100), unique=True, index=True, nullable=False)
    idempotency_key = Column(String(100), unique=True, index=True, nullable=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True, index=True)
    bank_name = Column(String(100), nullable=True)
    bank_organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    target_account_number = Column(String(100), nullable=True)
    target_ifsc = Column(String(20), nullable=True)
    action_type = Column(String(50), default="ATM_DISBURSEMENT_HOLD")  # ATM_DISBURSEMENT_HOLD, ACCOUNT_FREEZE, LIEN_HOLD, TRANSACTION_BLOCK
    status = Column(String(50), default="REQUESTED", index=True)  # REQUESTED, APPROVED, SENT, ACKNOWLEDGED, PARTIAL_HOLD, CONFIRMED_HOLD, COMPLETED, RELEASED, REJECTED, FAILED, CANCELLED
    environment = Column(String(50), default="SIMULATED", nullable=False, index=True)  # SIMULATED, SANDBOX, LIVE
    is_simulated = Column(Boolean, default=True, nullable=False)
    simulation_notes = Column(String(255), default="Simulated local action: External core-banking gateway not connected.")
    requested_amount = Column(Numeric(14, 2), nullable=True)
    held_amount = Column(Numeric(14, 2), default=0.0, nullable=False)
    currency = Column(String(10), default="INR", nullable=False)
    requested_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    actor_name = Column(String(255), nullable=True)
    actor_role = Column(String(50), nullable=True)
    action_notes = Column(Text, nullable=True)
    provider_reference_id = Column(String(100), nullable=True)
    failure_reason = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    release_reason = Column(Text, nullable=True)
    callback_evidence = Column(JSON, nullable=True)
    status_history = Column(JSON, nullable=True)
    requested_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    approved_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    held_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    released_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    __table_args__ = (
        Index("ix_bank_actions_comp_status", "complaint_id", "status"),
    )

    complaint = relationship("Complaint", foreign_keys=[complaint_id])
    alert = relationship("Alert", foreign_keys=[alert_id])
    account = relationship("Account", foreign_keys=[account_id])
    requested_by = relationship("User", foreign_keys=[requested_by_user_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_user_id])
    bank_organization = relationship("Organization", foreign_keys=[bank_organization_id], overlaps="bank_actions")


class EvidenceFile(Base):
    """
    Phase 6: Tamper-Evident Versioned Evidence Documentation.
    Preserves immutable cryptographic hashes, upload metadata, replacement lineage,
    and honest malware scanning state for case evidence files.
    """
    __tablename__ = "evidence_files"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False, index=True)
    source = Column(String(50), nullable=False, default="OFFICER_UPLOAD")  # OFFICER_UPLOAD, BANK_STATEMENT, CFCFRMS_EXPORT, VICTIM_SUBMISSION, ATM_CCTV, CDR_EXPORT
    uploader_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    uploader_role = Column(String(50), nullable=False)
    uploader_org_id = Column(Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    original_filename = Column(String(255), nullable=False)
    storage_key = Column(String(255), unique=True, nullable=False, index=True)
    mime_type = Column(String(100), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    sha256_hash = Column(String(64), nullable=False, index=True)
    version = Column(Integer, default=1, nullable=False)
    status = Column(String(50), default="ACTIVE", index=True)  # ACTIVE, SUPERSEDED, ARCHIVED, DELETED
    malware_scan_status = Column(String(50), default="PENDING_SCAN", nullable=False)  # PENDING_SCAN, QUARANTINED, FAILED_SCAN, UNSCANNED
    malware_scan_details = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    superseded_by_evidence_id = Column(Integer, ForeignKey("evidence_files.id", ondelete="SET NULL"), nullable=True)
    superseded_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    __table_args__ = (
        Index("ix_evidence_complaint_status", "complaint_id", "status"),
        Index("ix_evidence_sha256", "sha256_hash"),
    )

    complaint = relationship("Complaint", back_populates="evidence_files")
    uploader_user = relationship("User", foreign_keys=[uploader_user_id])
    uploader_org = relationship("Organization", foreign_keys=[uploader_org_id])
    superseded_by = relationship("EvidenceFile", remote_side=[id], foreign_keys=[superseded_by_evidence_id])


class CaseHandoff(Base):
    """
    Phase 7: Controlled Cross-Jurisdiction / Cross-State Handoff & Explicit Assignment.
    Enforces explicit, auditable handoffs between case-owning LEA and action-taking
    destination LEAs across state/district borders with scoped, time-bounded access.
    """
    __tablename__ = "case_handoffs"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False, index=True)
    prediction_id = Column(Integer, ForeignKey("predictions.id", ondelete="SET NULL"), nullable=True, index=True)
    prediction_version = Column(Integer, nullable=True)

    origin_organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    destination_organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    target_state = Column(String(100), nullable=False)
    target_district = Column(String(100), nullable=False)

    purpose = Column(String(100), nullable=False)  # PHYSICAL_SURVEILLANCE, ATM_INTERCEPTION, MULE_ARREST, EVIDENCE_COLLECTION, BANK_BRANCH_VISIT, LOCAL_INQUIRY
    evidence_scope = Column(String(50), default="METADATA_ONLY", nullable=False)  # METADATA_ONLY, SPECIFIC_EVIDENCE, ALL_EVIDENCE
    shared_evidence_ids = Column(JSON, nullable=True)  # List of integer evidence_files.id

    status = Column(String(50), default="REQUESTED", nullable=False, index=True)  # REQUESTED, ACCEPTED, REJECTED, IN_PROGRESS, COMPLETED, CANCELLED, EXPIRED

    initiator_user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    recipient_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    rejection_reason = Column(Text, nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    completed_notes = Column(Text, nullable=True)

    acknowledgement_deadline = Column(DateTime, nullable=False, index=True)
    accepted_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    __table_args__ = (
        Index("ix_case_handoffs_comp_status", "complaint_id", "status"),
        Index("ix_case_handoffs_dest_status", "destination_organization_id", "status"),
        Index("ix_case_handoffs_origin_status", "origin_organization_id", "status"),
        Index("ix_case_handoffs_deadline", "status", "acknowledgement_deadline"),
    )

    complaint = relationship("Complaint", back_populates="handoffs")
    prediction = relationship("Prediction")
    origin_organization = relationship("Organization", foreign_keys=[origin_organization_id])
    destination_organization = relationship("Organization", foreign_keys=[destination_organization_id])
    initiator_user = relationship("User", foreign_keys=[initiator_user_id])
    recipient_user = relationship("User", foreign_keys=[recipient_user_id])


class OutcomeObservation(Base):
    """
    Phase 9: Append-Only Correctable Outcome Observations.

    Records what actually happened after a fraud prediction — actual cashout events,
    confirmed holds, recoveries, or no observed cashout. Corrections create new records
    with incremented version numbers pointing back to the superseded record; original
    records are never deleted or overwritten.

    PREDICTION EVALUATION POLICY (pre-committed, never cherry-picked):
    linked_prediction_id is set to the LAST OPERATIONAL prediction created strictly
    before observed_event_time for the same complaint. If no such prediction exists,
    linked_prediction_id = NULL. This policy is stored in prediction_selection_policy
    and enforced by outcome_service.py at ingestion time.

    DENOMINATOR RULES (enforced in metrics queries and dashboard):
    - CONFIRMED_CASHOUT + NO_OBSERVED_CASHOUT contribute to success/failure denominators.
    - UNKNOWN outcomes are separately counted and excluded from success/failure.
    - Synthetic/demo outcomes tracked via is_synthetic flag; never mixed with real outcomes.
    - DATA_EXCLUDED outcomes are counted in excluded cohort; reason in exclusion_reason.
    - verified_held_amount_inr and actual_recovered_amount_inr are NEVER summed as
      "independently saved money" — they are recorded and reported separately.
    """
    __tablename__ = "outcome_observations"

    id = Column(Integer, primary_key=True, index=True)

    # --- Identity & Linkage ---
    complaint_id = Column(Integer, ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False, index=True)
    # Last OPERATIONAL prediction created strictly before observed_event_time (or NULL)
    linked_prediction_id = Column(Integer, ForeignKey("predictions.id", ondelete="SET NULL"), nullable=True, index=True)
    linked_prediction_version = Column(Integer, nullable=True)
    # Policy code recorded at ingestion time; must never be changed post-creation
    prediction_selection_policy = Column(String(100), nullable=False, default="LAST_OPERATIONAL_BEFORE_EVENT")
    linked_alert_id = Column(Integer, ForeignKey("alerts.id", ondelete="SET NULL"), nullable=True, index=True)
    linked_bank_action_id = Column(Integer, ForeignKey("bank_actions.id", ondelete="SET NULL"), nullable=True, index=True)

    # --- Outcome Classification ---
    # CONFIRMED_CASHOUT: cash-out observed at specific location/time
    # MULTIPLE_CASHOUT: multiple withdrawals observed (use cashout_events JSON)
    # NO_OBSERVED_CASHOUT: monitored window passed with no observed cash-out
    # UNKNOWN: outcome not determined / monitoring inconclusive
    # DATA_EXCLUDED: explicitly excluded from metrics (reason in exclusion_reason)
    outcome_type = Column(String(50), nullable=False, index=True)

    # --- Actual Event Fields (CONFIRMED_CASHOUT / MULTIPLE_CASHOUT) ---
    observed_event_time = Column(DateTime, nullable=True)
    actual_atm_id = Column(Integer, ForeignKey("atm_locations.id", ondelete="SET NULL"), nullable=True)
    actual_cluster_id = Column(Integer, ForeignKey("location_clusters.id", ondelete="SET NULL"), nullable=True)
    actual_lat = Column(Float, nullable=True)
    actual_lon = Column(Float, nullable=True)
    actual_location_name = Column(String(255), nullable=True)
    actual_withdrawal_amount_inr = Column(Numeric(14, 2), nullable=True)
    # Array of cashout events for MULTIPLE_CASHOUT: [{time, lat, lon, amount, atm_code}, ...]
    cashout_events = Column(JSON, nullable=True)

    # --- Financial Intervention Fields (recorded separately; never summed as one figure) ---
    # Verified hold amount — copied from bank_action.held_amount at observation time
    verified_held_amount_inr = Column(Numeric(14, 2), nullable=True)
    # Verified released amount — funds unfrozen post-investigation
    verified_released_amount_inr = Column(Numeric(14, 2), nullable=True)
    # Actual recovered amount — funds returned to victim / legally seized
    # NOT added to verified_held_amount_inr to avoid double-counting
    actual_recovered_amount_inr = Column(Numeric(14, 2), nullable=True)
    recovery_verified_by = Column(String(255), nullable=True)
    recovery_verified_at = Column(DateTime, nullable=True)

    # --- Derived Measurement Fields (computed at ingestion; immutable thereafter) ---
    # Rank of actual cashout cluster in linked_prediction's Top-K locations (1=top, NULL if not found)
    prediction_rank_matched = Column(Integer, nullable=True)
    # Haversine distance between rank-1 cluster centroid and actual cashout (km)
    distance_error_km = Column(Float, nullable=True)
    # Minutes from linked_prediction.created_at to observed_event_time
    prediction_lead_time_minutes = Column(Float, nullable=True)
    # Minutes from linked alert.created_at to observed_event_time
    alert_lead_time_minutes = Column(Float, nullable=True)
    # Minutes from alert.created_at to alert.acknowledged_at
    alert_acknowledgement_latency_minutes = Column(Float, nullable=True)
    # Minutes from bank_action.requested_at to bank_action.held_at
    bank_response_latency_minutes = Column(Float, nullable=True)

    # --- Cohort Labelling ---
    # Synthetic/demo outcomes; never mixed with real verified outcomes in metrics
    is_synthetic = Column(Boolean, default=False, nullable=False)
    is_excluded = Column(Boolean, default=False, nullable=False)
    exclusion_reason = Column(Text, nullable=True)
    # VERIFIED, UNVERIFIED, PENDING_VERIFICATION
    verification_status = Column(String(50), nullable=False, default="PENDING_VERIFICATION")

    # --- Provenance & Attribution ---
    # OFFICER_MANUAL, CFCFRMS_IMPORT, BANK_REPORT, COURT_RECORD, AUTOMATED_MONITORING
    source = Column(String(100), nullable=False)
    verifier_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    verifier_name = Column(String(255), nullable=True)
    verifier_role = Column(String(50), nullable=True)
    ingested_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=False, index=True)
    ingested_by_role = Column(String(50), nullable=False)
    # UTC timestamp: when record was entered into the system
    received_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)

    # --- Correction Lineage (append-only with version chain) ---
    version = Column(Integer, nullable=False, default=1)
    # If this record corrects a prior version, points to the superseded record's id
    corrects_outcome_id = Column(Integer, ForeignKey("outcome_observations.id", ondelete="SET NULL"), nullable=True)
    # ACTIVE (current) or SUPERSEDED (corrected by a newer version)
    record_status = Column(String(20), nullable=False, default="ACTIVE", index=True)
    correction_reason = Column(Text, nullable=True)

    # --- Notes / Timestamps ---
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    __table_args__ = (
        Index("ix_outcome_obs_comp_status", "complaint_id", "record_status", "outcome_type"),
        Index("ix_outcome_obs_received_at", "received_at"),
        Index("ix_outcome_obs_is_synthetic_status", "is_synthetic", "record_status"),
    )

    # Relationships
    complaint = relationship("Complaint", back_populates="outcome_observations", foreign_keys=[complaint_id])
    linked_prediction = relationship("Prediction", foreign_keys=[linked_prediction_id])
    linked_alert = relationship("Alert", foreign_keys=[linked_alert_id])
    linked_bank_action = relationship("BankAction", foreign_keys=[linked_bank_action_id])
    verifier_user = relationship("User", foreign_keys=[verifier_user_id])
    ingested_by_user = relationship("User", foreign_keys=[ingested_by_user_id])
    actual_atm = relationship("ATMLocation", foreign_keys=[actual_atm_id])
    actual_cluster = relationship("LocationCluster", foreign_keys=[actual_cluster_id])
    corrects_outcome = relationship("OutcomeObservation", remote_side=[id], foreign_keys=[corrects_outcome_id])


@event.listens_for(OutcomeObservation, "before_update")
def _outcome_before_update(mapper, connection, target):
    """Outcome observations are append-only; only limited fields may be updated after creation.
    Structural linkage fields (complaint_id, linked_prediction_id, prediction_selection_policy,
    outcome_type, observed_event_time, received_at) are frozen post-creation.
    Permitted updates: verification_status, notes, record_status (SUPERSEDED only), updated_at."""
    immutable_attrs = {
        "complaint_id", "linked_prediction_id", "linked_prediction_version",
        "prediction_selection_policy", "outcome_type", "observed_event_time",
        "ingested_by_user_id", "ingested_by_role", "received_at",
        "corrects_outcome_id", "version",
    }
    history = mapper.attrs
    for attr_name in immutable_attrs:
        attr = history.get(attr_name)
        if attr is not None:
            from sqlalchemy.orm.attributes import get_history
            h = get_history(target, attr_name)
            if h.deleted and h.deleted[0] is not None:
                raise ValueError(
                    f"OutcomeObservation.{attr_name} is immutable after creation. "
                    f"To correct, create a new record with corrects_outcome_id pointing to this record."
                )
