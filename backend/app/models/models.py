import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, Enum
)
from sqlalchemy.orm import relationship
from backend.app.models.db import Base

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    org_type = Column(String(50), default="LEA")  # LEA, BANK, I4C
    state = Column(String(100), default="Madhya Pradesh")
    district = Column(String(100), default="Bhopal")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    users = relationship("User", back_populates="organization")

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

class LocationCluster(Base):
    __tablename__ = "location_clusters"

    id = Column(Integer, primary_key=True, index=True)
    cluster_name = Column(String(255), nullable=False)
    city = Column(String(100), nullable=False)
    district = Column(String(100), nullable=False)
    state = Column(String(100), default="Madhya Pradesh")
    center_lat = Column(Float, nullable=False)
    center_lon = Column(Float, nullable=False)
    radius_km = Column(Float, default=2.5)
    historical_fraud_count = Column(Integer, default=0)
    atm_count = Column(Integer, default=0)
    risk_score = Column(Float, default=0.5)

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
    state = Column(String(100), default="Madhya Pradesh")
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    cash_available = Column(Boolean, default=True)
    risk_rating = Column(String(20), default="MEDIUM")
    cluster_id = Column(Integer, ForeignKey("location_clusters.id"), nullable=True)

    cluster = relationship("LocationCluster", back_populates="atms")

class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True)
    complaint_number = Column(String(50), unique=True, index=True, nullable=False)
    fraud_type = Column(String(100), nullable=False)
    amount = Column(Float, nullable=False)
    victim_name = Column(String(255), nullable=True)
    victim_phone = Column(String(50), nullable=True)
    victim_location = Column(String(255), nullable=False)
    state = Column(String(100), default="Madhya Pradesh")
    district = Column(String(100), default="Bhopal")
    payment_channel = Column(String(50), default="UPI")
    reported_at = Column(DateTime, default=datetime.datetime.utcnow)
    incident_time = Column(DateTime, default=datetime.datetime.utcnow)
    risk_level = Column(String(20), default="MEDIUM")  # CRITICAL, HIGH, MEDIUM, LOW
    risk_score = Column(Float, default=0.5)
    prediction_status = Column(String(50), default="PENDING")  # PENDING, COMPLETED, IN_PROGRESS
    case_status = Column(String(50), default="ACTIVE")  # ACTIVE, UNDER_INVESTIGATION, ALERTED, RESOLVED
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    transactions = relationship("Transaction", back_populates="complaint")
    predictions = relationship("Prediction", back_populates="complaint")
    alerts = relationship("Alert", back_populates="complaint")
    case_notes = relationship("CaseNote", back_populates="complaint")

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
    risk_score = Column(Float, default=0.1)
    is_mule = Column(Boolean, default=False)
    flag_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    transaction_ref = Column(String(100), unique=True, index=True, nullable=False)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False)
    sender_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    receiver_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    amount = Column(Float, nullable=False)
    payment_channel = Column(String(50), default="UPI")
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    hop_number = Column(Integer, default=1)
    status = Column(String(50), default="COMPLETED")
    suspicious_flag = Column(Boolean, default=True)

    complaint = relationship("Complaint", back_populates="transactions")
    sender = relationship("Account", foreign_keys=[sender_account_id])
    receiver = relationship("Account", foreign_keys=[receiver_account_id])

class Withdrawal(Base):
    __tablename__ = "withdrawals"

    id = Column(Integer, primary_key=True, index=True)
    atm_id = Column(Integer, ForeignKey("atm_locations.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    amount = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    success = Column(Boolean, default=True)
    camera_flagged = Column(Boolean, default=False)

class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False)
    prediction_mode = Column(String(50), default="deterministic_demo")
    model_version = Column(String(50), default="demo-provider-v1")
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
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    complaint = relationship("Complaint", back_populates="predictions")
    locations = relationship("PredictionLocation", back_populates="prediction", cascade="all, delete-orphan")

class PredictionLocation(Base):
    __tablename__ = "prediction_locations"

    id = Column(Integer, primary_key=True, index=True)
    prediction_id = Column(Integer, ForeignKey("predictions.id"), nullable=False)
    cluster_id = Column(Integer, ForeignKey("location_clusters.id"), nullable=True)
    location_name = Column(String(255), nullable=False)
    rank = Column(Integer, nullable=False)
    probability = Column(Float, nullable=False)
    risk_level = Column(String(50), default="CRITICAL")
    distance_km = Column(Float, default=185.0)
    reasoning = Column(String(255), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    prediction = relationship("Prediction", back_populates="locations")
    cluster = relationship("LocationCluster", back_populates="prediction_locations")

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False)
    prediction_id = Column(Integer, ForeignKey("predictions.id"), nullable=True)
    title = Column(String(255), nullable=False)
    severity = Column(String(50), default="CRITICAL")  # CRITICAL, HIGH, MEDIUM, LOW
    location_name = Column(String(255), nullable=False)
    risk_score = Column(Float, default=0.87)
    expected_window = Column(String(100), default="Next 2–4 Hours")
    amount_at_risk = Column(Float, default=125000.0)
    status = Column(String(50), default="NEW")  # NEW, ACKNOWLEDGED, ACTION_INITIATED, RESOLVED
    acknowledged_by = Column(String(255), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    action_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    complaint = relationship("Complaint", back_populates="alerts")

class CaseNote(Base):
    __tablename__ = "case_notes"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    note = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    complaint = relationship("Complaint", back_populates="case_notes")
    user = relationship("User", back_populates="case_notes")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True)
    officer_name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)
    action = Column(String(100), nullable=False)  # LOGIN, CASE_VIEWED, PREDICTION_RUN, NETWORK_VIEWED, ALERT_CREATED, ALERT_ACKNOWLEDGED, ALERT_ESCALATED
    case_number = Column(String(100), nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(50), default="127.0.0.1")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
