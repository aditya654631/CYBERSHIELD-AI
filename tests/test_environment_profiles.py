"""
CyberShield AI — Environment Profile & Production Invariant Verification Tests
"""

import pytest
from pydantic import ValidationError
from backend.app.config.settings import Settings, DEV_ONLY_JWT_SECRET

VALID_PROD_SECRET = "super-secret-key-production-cybershield-security-test-32chars"
VALID_PROD_DB = "postgresql+psycopg://cybershield:strongpass@prod-db.internal:5432/cybershield"
VALID_PROD_CORS = "https://cybershield.gov.in,https://cybershield-ai.vercel.app"

def test_production_rejects_sqlite():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET=VALID_PROD_SECRET,
            DATABASE_URL="sqlite:///./cybershield.db",
            ALLOW_DEMO_LOGIN=False,
            AUTO_SEED_DEMO_DATA=False,
            CORS_ORIGINS=VALID_PROD_CORS
        )
    assert "PostgreSQL is required in production" in str(exc_info.value)

def test_production_rejects_default_jwt_secret():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET=DEV_ONLY_JWT_SECRET,
            DATABASE_URL=VALID_PROD_DB,
            ALLOW_DEMO_LOGIN=False,
            AUTO_SEED_DEMO_DATA=False,
            CORS_ORIGINS=VALID_PROD_CORS
        )
    assert "JWT_SECRET must be set to a secure, non-default secret" in str(exc_info.value)

def test_production_rejects_wildcard_cors():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET=VALID_PROD_SECRET,
            DATABASE_URL=VALID_PROD_DB,
            ALLOW_DEMO_LOGIN=False,
            AUTO_SEED_DEMO_DATA=False,
            CORS_ORIGINS="*"
        )
    assert "cannot contain wildcard '*'" in str(exc_info.value)

def test_production_rejects_allow_demo_login():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET=VALID_PROD_SECRET,
            DATABASE_URL=VALID_PROD_DB,
            ALLOW_DEMO_LOGIN=True,
            AUTO_SEED_DEMO_DATA=False,
            CORS_ORIGINS=VALID_PROD_CORS
        )
    assert "ALLOW_DEMO_LOGIN must be disabled" in str(exc_info.value)

def test_production_rejects_auto_seed_demo_data():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET=VALID_PROD_SECRET,
            DATABASE_URL=VALID_PROD_DB,
            ALLOW_DEMO_LOGIN=False,
            AUTO_SEED_DEMO_DATA=True,
            CORS_ORIGINS=VALID_PROD_CORS
        )
    assert "AUTO_SEED_DEMO_DATA must be disabled" in str(exc_info.value)

def test_production_accepts_valid_configuration():
    s = Settings(
        ENVIRONMENT="production",
        JWT_SECRET=VALID_PROD_SECRET,
        DATABASE_URL=VALID_PROD_DB,
        ALLOW_DEMO_LOGIN=False,
        AUTO_SEED_DEMO_DATA=False,
        CORS_ORIGINS=VALID_PROD_CORS
    )
    assert s.ENVIRONMENT == "production"
    assert s.DATABASE_URL == VALID_PROD_DB
    assert s.ALLOW_DEMO_LOGIN is False
    assert s.AUTO_SEED_DEMO_DATA is False

def test_development_allows_sqlite_and_conveniences():
    s = Settings(
        ENVIRONMENT="development",
        DATABASE_URL="sqlite:///./cybershield.db",
        ALLOW_DEMO_LOGIN=True,
        AUTO_SEED_DEMO_DATA=False
    )
    assert s.ENVIRONMENT == "development"
    assert s.DATABASE_URL.startswith("sqlite")
    assert s.ALLOW_DEMO_LOGIN is True
