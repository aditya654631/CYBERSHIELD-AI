"""
CyberShield AI — Production-Safe Cloud Database Initialization Script
Step 17: Safe Cloud PostgreSQL Migration & Schema Setup

Usage:
    python backend/scripts/init_cloud_db.py [--db-url DATABASE_URL] [--seed-mode reference|demo|full|none]

Guarantees:
    - Zero data loss: Never drops tables or wipes existing rows
    - Zero ML retraining: Model artifacts remain frozen on the filesystem
    - Zero training regeneration in reference/demo mode
    - Fully idempotent: Safe to execute repeatedly on new or existing databases
    - Cloud URL normalization: Supports postgres://, postgresql://, and postgresql+psycopg://
"""

import os
import sys
import argparse
import logging
from typing import Dict, Any, List

# Ensure project root is in sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from alembic.config import Config
from alembic import command

from backend.app.config.settings import settings
from backend.app.models.db import Base
from backend.app.models.models import (
    Organization, User, LocationCluster, ATMLocation,
    Complaint, Account, ComplaintAccount, Transaction,
    Prediction, PredictionLocation, Alert, AuditLog
)
from database.seed.seed_data import (
    seed_auth_and_organizations,
    seed_delhi_geography,
    seed_demo_case_cmp1042,
    seed_delhi_operational_dataset
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("init_cloud_db")

EXPECTED_TABLES = [
    "organizations",
    "users",
    "location_clusters",
    "atm_locations",
    "complaints",
    "accounts",
    "complaint_accounts",
    "transactions",
    "withdrawals",
    "predictions",
    "prediction_locations",
    "alerts",
    "case_notes",
    "audit_logs",
    "alembic_version"
]


def normalize_url(url: str) -> str:
    """Normalizes database URL for psycopg v3 compatibility."""
    u = url.strip()
    if u.startswith("postgres://"):
        return u.replace("postgres://", "postgresql+psycopg://", 1)
    elif u.startswith("postgresql://") and not u.startswith("postgresql+"):
        return u.replace("postgresql://", "postgresql+psycopg://", 1)
    return u


def mask_url(url: str) -> str:
    """Masks credentials in database URL for safe logging."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.password:
            masked = url.replace(f":{parsed.password}@", ":********@")
            return masked
        return url
    except Exception:
        return "<sanitized-url>"


def run_cloud_init(db_url: str = None, seed_mode: str = "reference") -> Dict[str, Any]:
    target_url = normalize_url(db_url or settings.DATABASE_URL)
    masked_target = mask_url(target_url)

    logger.info("======================================================================")
    logger.info("CYBERSHIELD AI — CLOUD POSTGRESQL INITIALIZATION & MIGRATION")
    logger.info("======================================================================")
    logger.info(f"Target Database: {masked_target}")
    logger.info(f"Seed Mode: {seed_mode.upper()}")

    # 1. Connection Verification
    logger.info("[Step 1/5] Verifying live database connectivity...")
    engine = create_engine(
        target_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10
    )

    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            assert result == 1
        logger.info("Database connectivity check: SUCCESS (SELECT 1 returned 1)")
    except Exception as e:
        logger.error(f"Failed to connect to target database: {e}")
        raise

    # 2. Run Alembic Migrations
    logger.info("[Step 2/5] Applying Alembic schema migrations to head...")
    alembic_ini_path = os.path.join(BASE_DIR, "alembic.ini")
    alembic_cfg = Config(alembic_ini_path)
    alembic_cfg.set_main_option("sqlalchemy.url", target_url)
    
    command.upgrade(alembic_cfg, "head")
    logger.info("Alembic schema migrations applied successfully to HEAD.")

    # 3. Validate Schema Integrity
    logger.info("[Step 3/5] Validating table schema integrity...")
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    
    missing_tables = [t for t in EXPECTED_TABLES if t not in existing_tables]
    if missing_tables:
        err_msg = f"Schema validation failed. Missing tables: {missing_tables}"
        logger.error(err_msg)
        raise RuntimeError(err_msg)
    logger.info(f"All {len(EXPECTED_TABLES)} expected tables exist and verified.")

    # 4. Seed Data based on Seed Mode
    logger.info(f"[Step 4/5] Seeding data (Mode: {seed_mode})...")
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        if seed_mode in ("reference", "demo", "full"):
            logger.info(" - Seeding organizations and administrative user roles...")
            seed_auth_and_organizations(db)

            logger.info(" - Seeding 60 Delhi location clusters and 240 context ATMs...")
            clusters, atms = seed_delhi_geography(db)

        if seed_mode in ("demo", "full"):
            logger.info(" - Seeding CMP-1042 demonstration prototype case...")
            seed_demo_case_cmp1042(db)

        if seed_mode == "full":
            logger.info(" - Seeding full synthetic operational dataset...")
            seed_delhi_operational_dataset(db, clusters, atms)

        db.commit()
        logger.info("Data seeding phase complete.")
    except Exception as e:
        db.rollback()
        logger.error(f"Seeding failed: {e}")
        raise
    finally:
        db.close()

    # 5. Final Readiness Audit
    logger.info("[Step 5/5] Performing final database readiness audit...")
    db = Session()
    try:
        user_count = db.query(User).count()
        org_count = db.query(Organization).count()
        cluster_count = db.query(LocationCluster).count()
        atm_count = db.query(ATMLocation).count()
        complaint_count = db.query(Complaint).count()
        pred_count = db.query(Prediction).count()
        alert_count = db.query(Alert).count()

        logger.info("Final Database Summary:")
        logger.info(f" - Users: {user_count}")
        logger.info(f" - Organizations: {org_count}")
        logger.info(f" - Location Clusters (Delhi): {cluster_count}")
        logger.info(f" - ATM Context Nodes (Delhi): {atm_count}")
        logger.info(f" - Total Complaints: {complaint_count}")
        logger.info(f" - Persisted Predictions: {pred_count}")
        logger.info(f" - Persisted Alerts: {alert_count}")

        readiness_report = {
            "status": "READY",
            "target_database": masked_target,
            "seed_mode": seed_mode,
            "tables_verified": len(EXPECTED_TABLES),
            "users": user_count,
            "organizations": org_count,
            "clusters": cluster_count,
            "atms": atm_count,
            "complaints": complaint_count,
            "predictions": pred_count,
            "alerts": alert_count
        }
        logger.info("CLOUD POSTGRESQL INITIALIZATION: ALL CHECKS PASSED.")
        return readiness_report
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CyberShield AI Cloud Database Initialization")
    parser.add_argument("--db-url", type=str, default=None, help="Target PostgreSQL connection URL")
    parser.add_argument(
        "--seed-mode",
        type=str,
        choices=["reference", "demo", "full", "none"],
        default="reference",
        help="Seeding profile (default: reference)"
    )
    args = parser.parse_args()

    try:
        res = run_cloud_init(db_url=args.db_url, seed_mode=args.seed_mode)
        print("\nSUCCESS: Cloud database readiness verified.")
    except Exception as exc:
        print(f"\nERROR: Database initialization failed: {exc}", file=sys.stderr)
        sys.exit(1)
