"""
CyberShield AI — Pytest Isolation & Configuration Fixtures

Enforces:
1. Complete isolation from operational and production databases.
2. Production guardrails: aborts or redirects if production database detected.
3. Automatic creation of isolated temporary test database.
4. Dependency override for FastAPI get_db.
5. Opt-in execution for live infrastructure tests via --run-live.
"""

import os
import sys
import tempfile
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Ensure root is on path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Force test environment before application imports
os.environ["ENVIRONMENT"] = "test"
os.environ["AUTO_SEED_DEMO_DATA"] = "false"

from backend.app.config.settings import settings
import backend.app.models.db as db_mod
from backend.app.models.db import Base, get_db
from backend.app.models import models
from backend.app.main import app
from backend.app.auth.security import get_password_hash

# Guardrail: Override database url for test session
db_url = str(settings.DATABASE_URL).lower()
if any(k in db_url for k in ["neon.tech", "prod", "railway.app"]) and os.environ.get("FORCE_LIVE_DB") != "1":
    settings.DATABASE_URL = "sqlite:///:memory:"

# Create temporary database file for test session at conftest import time
_temp_dir = tempfile.mkdtemp(prefix="cybershield_test_")
_test_db_path = os.path.join(_temp_dir, "isolated_test.db")
test_engine = create_engine(
    f"sqlite:///{_test_db_path}",
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Intercept engine and SessionLocal immediately so any test file importing them gets test_engine
_original_session_local = db_mod.SessionLocal
_original_engine = db_mod.engine
db_mod.SessionLocal = TestingSessionLocal
db_mod.engine = test_engine

# Initialize schema
Base.metadata.create_all(bind=test_engine)


def pytest_addoption(parser):
    parser.addoption(
        "--run-live",
        action="store_true",
        default=False,
        help="Run live cloud / infrastructure integration tests"
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-live"):
        skip_live = pytest.mark.skip(reason="Live infrastructure tests require --run-live option")
        for item in items:
            if "live" in item.keywords:
                item.add_marker(skip_live)


@pytest.fixture(scope="session", autouse=True)
def guardrail_and_isolate_test_db():
    """
    Session-wide fixture that intercepts any attempt to touch production or operational databases.
    Mounts an isolated temporary SQLite database and overrides FastAPI get_db.
    """
    # Seed baseline reference data (Organizations, Users, ATMLocations, LocationClusters)
    db = TestingSessionLocal()
    try:
        # Organizations
        if not db.query(models.Organization).first():
            i4c_org = models.Organization(id=1, name="I4C National Command", org_type="I4C", state="Delhi", district="CENTRAL_NEW_DELHI")
            mp_state_lea = models.Organization(id=2, name="Madhya Pradesh State Cyber Police Headquarters", org_type="LEA", state="Madhya Pradesh", district="Bhopal")
            indore_lea = models.Organization(id=3, name="Indore District Cyber Cell", org_type="LEA", state="Madhya Pradesh", district="Indore")
            sbi_bank = models.Organization(id=4, name="State Bank of India - Fraud Risk Management Unit", org_type="BANK", state="Maharashtra", district="Mumbai")
            mha_audit = models.Organization(id=5, name="Ministry of Home Affairs Oversight & Compliance", org_type="I4C", state="Delhi", district="CENTRAL_NEW_DELHI")
            db.add_all([i4c_org, mp_state_lea, indore_lea, sbi_bank, mha_audit])
            db.flush()

        # Users
        if not db.query(models.User).filter_by(id=1).first():
            org_1 = db.query(models.Organization).filter_by(id=1).first()
            org_2 = db.query(models.Organization).filter_by(id=2).first()
            org_3 = db.query(models.Organization).filter_by(id=3).first()
            org_4 = db.query(models.Organization).filter_by(id=4).first()
            org_5 = db.query(models.Organization).filter_by(id=5).first()
            users = [
                models.User(
                    id=1, email="admin@cybershield.gov.in", hashed_password=get_password_hash("CyberAdmin@2026"),
                    full_name="Dr. Vikramaditya Sen", role="I4C_ADMIN", badge_number="I4C-DIR-001", organization_id=org_1.id if org_1 else None, is_active=True
                ),
                models.User(
                    id=2, email="state.lea@mp.police.gov.in", hashed_password=get_password_hash("StateLea@2026"),
                    full_name="SP Anand Shekhawat, IPS", role="STATE_LEA", badge_number="MP-CYBER-09", organization_id=org_2.id if org_2 else None, is_active=True
                ),
                models.User(
                    id=3, email="district.lea@indore.police.gov.in", hashed_password=get_password_hash("IndoreLea@2026"),
                    full_name="Inspector Rajesh Verma", role="DISTRICT_LEA", badge_number="IND-CY-441", organization_id=org_3.id if org_3 else None, is_active=True
                ),
                models.User(
                    id=4, email="officer@sbi.co.in", hashed_password=get_password_hash("BankOfficer@2026"),
                    full_name="Sunita Deshmukh", role="BANK_OFFICER", badge_number="SBI-FRMU-88", organization_id=org_4.id if org_4 else None, is_active=True
                ),
                models.User(
                    id=5, email="analyst@cybershield.gov.in", hashed_password=get_password_hash("Analyst@2026"),
                    full_name="Pooja Kulkarni", role="ANALYST", badge_number="CS-AN-102", organization_id=org_1.id if org_1 else None, is_active=True
                ),
                models.User(
                    id=6, email="auditor@mha.gov.in", hashed_password=get_password_hash("Auditor@2026"),
                    full_name="Col. Sanjeev Nair (Retd.)", role="AUDITOR", badge_number="MHA-AUD-07", organization_id=org_5.id if org_5 else None, is_active=True
                ),
                models.User(
                    id=7, email="officer@delhipolice.gov.in", hashed_password=get_password_hash("officer123"),
                    full_name="ACP Vikramaditya Singh", role="DISTRICT_LEA", badge_number="DL-CY-9901", organization_id=org_1.id if org_1 else None, is_active=True
                ),
                models.User(
                    id=8, email="inactive.officer@cybershield.gov.in", hashed_password=get_password_hash("Password@2026"),
                    full_name="Suspended Officer", role="DISTRICT_LEA", badge_number="SUSP-01", organization_id=org_1.id if org_1 else None, is_active=False
                ),
            ]
            db.add_all(users)
            db.flush()

        # Baseline Complaint for test scenarios
        if not db.query(models.Complaint).filter_by(id=1).first():
            base_complaint = models.Complaint(
                id=1,
                complaint_number="CMP-DELHI-001",
                fraud_type="UPI Fraud",
                amount=50000.0,
                victim_location="Connaught Place, Delhi",
                state="Delhi",
                district="Central Delhi",
                case_status="REGISTERED"
            )
            db.add(base_complaint)
            db.flush()

        if not db.query(models.Account).filter_by(id=1).first():
            sbi_account = models.Account(
                id=1,
                account_number="SBIN0001234567",
                masked_account="SBIN••••4567",
                bank_name="State Bank of India",
                ifsc="SBIN0001234",
                holder_name="Mule Beneficiary",
                account_type="SAVINGS",
                state="Delhi",
                district="Central Delhi"
            )
            db.add(sbi_account)
            db.flush()

            complaint_account = models.ComplaintAccount(
                complaint_id=1,
                account_id=sbi_account.id,
                association_type="BENEFICIARY"
            )
            db.add(complaint_account)
            db.flush()

        # Baseline clusters and ATMs for test scenarios
        if not db.query(models.LocationCluster).filter_by(id=1).first():
            from database.seed.delhi_geography import DELHI_CLUSTERS_DATA
            clusters = [
                models.LocationCluster(
                    id=i + 1,
                    cluster_name=c["name"],
                    city="Delhi",
                    district=c["zone"],
                    state="Delhi",
                    center_lat=c["lat"],
                    center_lon=c["lon"],
                    radius_km=c["radius"],
                    historical_fraud_count=c["fraud_count"] * 10,
                    atm_count=4,
                    risk_score=c["risk"]
                )
                for i, c in enumerate(DELHI_CLUSTERS_DATA)
            ]
            db.add_all(clusters)
            db.flush()

        if not db.query(models.ATMLocation).filter_by(id=1).first():
            atm_1 = models.ATMLocation(
                id=1,
                atm_code="ATM-DL-0001",
                bank_name="SBI",
                address="Inner Circle, Connaught Place",
                city="Delhi",
                district="Central Delhi",
                state="Delhi",
                latitude=28.6320,
                longitude=77.2170,
                cash_available=True,
                risk_rating="HIGH",
                cluster_id=1
            )
            atm_2 = models.ATMLocation(
                id=2,
                atm_code="ATM-DL-0002",
                bank_name="HDFC",
                address="Pusa Road, Karol Bagh",
                city="Delhi",
                district="Central Delhi",
                state="Delhi",
                latitude=28.6520,
                longitude=77.1910,
                cash_available=True,
                risk_rating="HIGH",
                cluster_id=2
            )
            atm_3 = models.ATMLocation(
                id=3,
                atm_code="ATM-DL-0003",
                bank_name="ICICI",
                address="Central Market, Lajpat Nagar",
                city="Delhi",
                district="South Delhi",
                state="Delhi",
                latitude=28.5680,
                longitude=77.2435,
                cash_available=True,
                risk_rating="MEDIUM",
                cluster_id=3
            )
            atm_4 = models.ATMLocation(
                id=4,
                atm_code="ATM-DL-0004",
                bank_name="Axis",
                address="Commercial Complex, Nehru Place",
                city="Delhi",
                district="South East Delhi",
                state="Delhi",
                latitude=28.5498,
                longitude=77.2540,
                cash_available=True,
                risk_rating="HIGH",
                cluster_id=4
            )
            db.add_all([atm_1, atm_2, atm_3, atm_4])
            db.flush()
        db.commit()
    finally:
        db.close()

    # Override FastAPI dependency
    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    yield TestingSessionLocal

    # Teardown
    db_mod.SessionLocal = _original_session_local
    db_mod.engine = _original_engine
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()
    try:
        if os.path.exists(_test_db_path):
            os.remove(_test_db_path)
        os.rmdir(_temp_dir)
    except Exception:
        pass


@pytest.fixture
def db_session(guardrail_and_isolate_test_db):
    """Provides an isolated session to individual tests."""
    session = guardrail_and_isolate_test_db()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(guardrail_and_isolate_test_db):
    """Provides a TestClient wired to the isolated database."""
    with TestClient(app) as c:
        yield c
