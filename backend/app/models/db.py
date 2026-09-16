import os
from datetime import datetime, timezone
from time import perf_counter
from typing import Dict, Any
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.app.config.settings import settings

db_url = settings.DATABASE_URL
engine_kwargs: Dict[str, Any] = {"echo": False}

# Detect engine backend using SQLAlchemy URL utilities
is_sqlite = db_url.startswith("sqlite")

if is_sqlite:
    # SQLite requires check_same_thread=False for multithreading; do not pass to PostgreSQL
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # Sensible connection resilience for PostgreSQL (verifies connections before checkout)
    engine_kwargs["pool_pre_ping"] = True
    # Production cloud connection pooling options with environment variable overrides
    engine_kwargs["pool_size"] = int(os.getenv("DB_POOL_SIZE", "10"))
    engine_kwargs["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    default_recycle = "300" if "neon.tech" in db_url else "1800"
    engine_kwargs["pool_recycle"] = int(os.getenv("DB_POOL_RECYCLE", default_recycle))
    engine_kwargs["pool_timeout"] = int(os.getenv("DB_POOL_TIMEOUT", "30"))

engine = create_engine(
    db_url,
    **engine_kwargs
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_database_engine_type() -> str:
    """
    Safely identifies whether the configured database engine is 'sqlite', 'postgresql', etc.
    Uses SQLAlchemy's URL backend inspection without parsing credentials manually.
    """
    try:
        return engine.url.get_backend_name()
    except Exception:
        return "sqlite" if settings.DATABASE_URL.startswith("sqlite") else "postgresql"

def check_database_connection() -> Dict[str, Any]:
    """
    Executes a lightweight query (SELECT 1) to verify active database connectivity.
    Guarantees no credentials, passwords, or connection strings are leaked in return values or errors.
    """
    engine_type = get_database_engine_type()
    checked_at = datetime.now(timezone.utc).isoformat()
    started_at = perf_counter()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {
            "status": "connected",
            "engine": engine_type,
            "latency_ms": round((perf_counter() - started_at) * 1000, 2),
            "timestamp": checked_at,
        }
    except Exception as exc:
        # Sanitize error to avoid leaking DB host, credentials, or connection details
        return {
            "status": "unavailable",
            "engine": engine_type,
            "latency_ms": None,
            "timestamp": checked_at,
            "error": f"Database connection failed: {exc.__class__.__name__}",
        }
