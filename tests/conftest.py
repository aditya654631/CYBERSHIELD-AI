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
from fastapi.testclient import TestClient

# Ensure root is on path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Force test environment before application imports
os.environ["ENVIRONMENT"] = "test"
os.environ["AUTO_SEED_DEMO_DATA"] = "false"
# Set the temporary URL before importing any application module. main.py keeps
# import-time references to engine/SessionLocal; replacing db_mod afterwards
# leaves those references connected to a different database.
_temp_dir = tempfile.mkdtemp(prefix="cybershield_test_")
_test_db_path = os.path.join(_temp_dir, "isolated_test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_test_db_path}"

from backend.app.config.settings import settings
import backend.app.models.db as db_mod
from backend.app.models.db import Base, get_db
from backend.app.models import models
import datetime
from backend.app.main import app
from backend.app.auth.security import get_password_hash, create_access_token

test_engine = db_mod.engine
TestingSessionLocal = db_mod.SessionLocal
assert str(settings.DATABASE_URL) == os.environ["DATABASE_URL"]
assert str(test_engine.url) == os.environ["DATABASE_URL"]


def _isolated_get_db():
    """FastAPI dependency bound to this test session's isolated SQLite DB."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

# All imports now point to the same temporary test database.
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


@pytest.fixture(autouse=True)
def reset_rate_limiter_fixture():
    """Reset rate limiter state before and after each test to prevent cross-test contamination."""
    from backend.app.auth.rate_limiter import login_rate_limiter
    login_rate_limiter.reset()
    yield
    login_rate_limiter.reset()


@pytest.fixture(autouse=True)
def restore_isolated_fastapi_db_override(guardrail_and_isolate_test_db):
    """Prevent one test's dependency_overrides.clear() from leaking into another."""
    app.dependency_overrides[get_db] = _isolated_get_db
    yield
    app.dependency_overrides[get_db] = _isolated_get_db


_legacy_seeded_modules = {
    "test_prediction_explainability_lime",
    "test_step9_prediction_flow",
    "test_step10_prediction_persistence",
    "test_step11_gis_persistence_integration",
    "test_step12_prediction_alert_integration",
    "test_step13_dashboard_db_integration",
    "test_step14_auth_audit",
    "test_synthetic_seed",
    "test_transaction_scenario_linking",
}
_legacy_dataset_seeded = False


@pytest.fixture(autouse=True)
def seed_legacy_integration_dataset_when_required(request, guardrail_and_isolate_test_db):
    """Load synthetic fixtures only for tests that explicitly require the full corpus.

    This remains inside the temporary SQLite test database. Most tests use the
    small baseline fixture and avoid the 3,000-case/50,000-transfer seed cost.
    """
    global _legacy_dataset_seeded
    if request.module.__name__.rsplit(".", 1)[-1] not in _legacy_seeded_modules:
        return
    if _legacy_dataset_seeded:
        return
    from database.seed.seed_data import seed_delhi_operational_dataset

    with TestingSessionLocal() as db:
        clusters = db.query(models.LocationCluster).filter_by(state="Delhi").order_by(models.LocationCluster.id).all()
        atms = db.query(models.ATMLocation).filter(
            models.ATMLocation.atm_code.like("ATM-DL-%")
        ).order_by(models.ATMLocation.id).all()
        assert len(clusters) == 60 and len(atms) == 240
        seed_delhi_operational_dataset(db, clusters, atms)
        db.commit()
    _legacy_dataset_seeded = True


@pytest.fixture(scope="session", autouse=True)
def guardrail_and_isolate_test_db():
    """
    Session-wide fixture that intercepts any attempt to touch production or operational databases.
    Mounts an isolated temporary SQLite database and overrides FastAPI get_db.
    """
    # Seed baseline reference data (Organizations, Users, ATMLocations, LocationClusters)
    db = TestingSessionLocal()
    try:
        # Seed Geography Regions & Catalogs first to satisfy foreign key constraints (Phase 12)
        from backend.app.services.geography_catalog_service import ensure_default_regions_and_catalogs
        ensure_default_regions_and_catalogs(db)

        # Organizations
        if not db.query(models.Organization).first():
            i4c_org = models.Organization(id=1, name="I4C National Command", org_type="I4C", state="Delhi", district="CENTRAL_NEW_DELHI")
            mp_state_lea = models.Organization(id=2, name="Madhya Pradesh State Cyber Police Headquarters", org_type="LEA", state="Madhya Pradesh", district="Bhopal")
            indore_lea = models.Organization(id=3, name="Indore District Cyber Cell", org_type="LEA", state="Madhya Pradesh", district="Indore")
            sbi_bank = models.Organization(id=4, name="State Bank of India - Fraud Risk Management Unit", org_type="BANK", state="Maharashtra", district="Mumbai")
            mha_audit = models.Organization(id=5, name="Ministry of Home Affairs Oversight & Compliance", org_type="I4C", state="Delhi", district="CENTRAL_NEW_DELHI")
            delhi_lea = models.Organization(id=6, name="Delhi Central Cyber Cell", org_type="LEA", state="Delhi", district="CENTRAL_NEW_DELHI")
            delhi_nct = models.Organization(id=10, name="Delhi Cyber Crime Unit (NCT)", org_type="LEA", state="Delhi", district="ALL", region_id="delhi")
            south_delhi = models.Organization(id=11, name="District Cyber Cell (South Delhi)", org_type="LEA", state="Delhi", district="SOUTH", region_id="delhi")
            db.add_all([i4c_org, mp_state_lea, indore_lea, sbi_bank, mha_audit, delhi_lea, delhi_nct, south_delhi])
            db.flush()

        # Users
        if not db.query(models.User).filter_by(id=1).first():
            org_1 = db.query(models.Organization).filter_by(id=1).first()
            org_2 = db.query(models.Organization).filter_by(id=2).first()
            org_3 = db.query(models.Organization).filter_by(id=3).first()
            org_4 = db.query(models.Organization).filter_by(id=4).first()
            org_5 = db.query(models.Organization).filter_by(id=5).first()
            org_10 = db.query(models.Organization).filter_by(id=10).first()
            org_11 = db.query(models.Organization).filter_by(id=11).first()
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
                    full_name="ACP Vikramaditya Singh", role="DISTRICT_LEA", badge_number="DL-CY-9901", organization_id=6, is_active=True
                ),
                models.User(
                    id=8, email="inactive.officer@cybershield.gov.in", hashed_password=get_password_hash("Password@2026"),
                    full_name="Suspended Officer", role="DISTRICT_LEA", badge_number="SUSP-01", organization_id=6, is_active=False
                ),
                models.User(
                    id=12, email="state.lea@delhi.cyber.gov.in", hashed_password=get_password_hash("StateLea@2026"),
                    full_name="DCP Rajesh Kumar, IPS", role="STATE_LEA", badge_number="DL-CY-NCT01", organization_id=org_10.id if org_10 else None, is_active=True
                ),
                models.User(
                    id=13, email="district.lea@southdelhi.cyber.gov.in", hashed_password=get_password_hash("DistrictLea@2026"),
                    full_name="Inspector Amit Sharma", role="DISTRICT_LEA", badge_number="DL-CY-SD01", organization_id=org_11.id if org_11 else None, is_active=True
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
                bank_organization_id=4,
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

        # Seed complete synthetic operational database (idempotent)
        from database.seed.seed_data import seed_database
        seed_database(db)

        # Seed canonical test complaints CMP-NEW-000002, CMP-NEW-000003, CMP-NEW-000004
        if not db.query(models.Complaint).filter_by(complaint_number="CMP-NEW-000002").first():
            sc_1261 = db.query(models.Complaint).filter_by(complaint_number="CMP-DL-1261").first()
            c2 = models.Complaint(
                complaint_number="CMP-NEW-000002",
                fraud_type="UPI Fraud",
                amount=50000.0,
                victim_location="Connaught Place, Delhi",
                state="Delhi",
                district="Central Delhi",
                payment_channel="UPI",
                provenance_mode="LINKED_SYNTHETIC_SCENARIO",
                description="[SCENARIO:CMP-DL-1261|STATUS:LINKED|SCORE:95.0|REASON:Tier 1: Same Zone, Fraud Type, Channel, Amount Band]\nLinked operational scenario test complaint",
                case_status="REGISTERED",
                reported_at=datetime.datetime.now(datetime.timezone.utc)
            )
            db.add(c2)
            db.flush()
            if sc_1261:
                for ca in db.query(models.ComplaintAccount).filter_by(complaint_id=sc_1261.id).all():
                    db.add(models.ComplaintAccount(complaint_id=c2.id, account_id=ca.account_id, association_type=ca.association_type))

        if not db.query(models.Complaint).filter_by(complaint_number="CMP-NEW-000003").first():
            sc_1095 = db.query(models.Complaint).filter_by(complaint_number="CMP-DL-1095").first()
            c3 = models.Complaint(
                complaint_number="CMP-NEW-000003",
                fraud_type="UPI Fraud",
                amount=75000.0,
                victim_location="Karol Bagh, Delhi",
                state="Delhi",
                district="Central Delhi",
                payment_channel="UPI",
                provenance_mode="LINKED_SYNTHETIC_SCENARIO",
                description="[SCENARIO:CMP-DL-1095|STATUS:LINKED|SCORE:95.0|REASON:Tier 1: Same Zone, Fraud Type, Channel, Amount Band]\nLinked operational scenario test complaint",
                case_status="REGISTERED",
                reported_at=datetime.datetime.now(datetime.timezone.utc)
            )
            db.add(c3)
            db.flush()
            if sc_1095:
                for ca in db.query(models.ComplaintAccount).filter_by(complaint_id=sc_1095.id).all():
                    db.add(models.ComplaintAccount(complaint_id=c3.id, account_id=ca.account_id, association_type=ca.association_type))

        if not db.query(models.Complaint).filter_by(complaint_number="CMP-NEW-000004").first():
            c4 = models.Complaint(
                complaint_number="CMP-NEW-000004",
                fraud_type="Investment Scam",
                amount=125000.0,
                victim_location="MP Nagar, Bhopal",
                state="Madhya Pradesh",
                district="Bhopal",
                payment_channel="Net Banking",
                provenance_mode="OUTSIDE_OPERATIONAL_SCOPE",
                description="Outside pilot scope test complaint",
                case_status="REGISTERED",
                reported_at=datetime.datetime.now(datetime.timezone.utc)
            )
            db.add(c4)
            db.flush()

        db.commit()
    finally:
        db.close()

    # Override FastAPI dependency
    app.dependency_overrides[get_db] = _isolated_get_db

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
def db(db_session):
    """Alias for db_session fixture."""
    return db_session


@pytest.fixture
def client(guardrail_and_isolate_test_db):
    """Provides an unauthenticated TestClient wired to the isolated database."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_client(guardrail_and_isolate_test_db):
    """Provides an authenticated TestClient with I4C_ADMIN privileges."""
    with TestClient(app) as c:
        token = create_access_token({"sub": "admin@cybershield.gov.in", "role": "I4C_ADMIN"})
        c.headers.update({"Authorization": f"Bearer {token}"})
        yield c


@pytest.fixture
def admin_headers(guardrail_and_isolate_test_db):
    """Provides standard I4C_ADMIN bearer authorization headers."""
    token = create_access_token({"sub": "admin@cybershield.gov.in", "role": "I4C_ADMIN"})
    return {"Authorization": f"Bearer {token}"}
