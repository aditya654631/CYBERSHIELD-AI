import os
from typing import Optional, Union, List
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_ONLY_JWT_SECRET = "dev-insecure-jwt-secret-key-for-development-only-cybershield-2026"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="allow"
    )

    APP_NAME: str = "CyberShield AI"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # CORS Configuration
    CORS_ORIGINS: Union[str, List[str]] = "http://localhost:5173,http://127.0.0.1:5173"

    # JWT Authentication Configuration
    JWT_SECRET: Optional[str] = None
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Database Configuration (supports Neon PostgreSQL, standard PostgreSQL, and SQLite)
    DATABASE_URL: Optional[str] = "sqlite:///./cybershield.db"
    NEON_DATABASE_URL: Optional[str] = None
    NEON_HOST: Optional[str] = None
    NEON_USER: Optional[str] = None
    NEON_PASSWORD: Optional[str] = None
    NEON_DATABASE: Optional[str] = "neondb"
    NEON_SSLMODE: Optional[str] = "require"

    # ML Model Configuration
    ML_MODEL_DIR: str = "ml/models"
    USE_ML_FALLBACK: bool = True

    # Server Configuration
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    @model_validator(mode="after")
    def validate_jwt_secret(self) -> "Settings":
        is_prod = str(self.ENVIRONMENT).lower() in ("production", "prod")
        # Support JWT_SECRET with fallback to legacy SECRET_KEY if present in env
        secret = self.JWT_SECRET or os.getenv("SECRET_KEY")

        if is_prod:
            if not secret or secret == DEV_ONLY_JWT_SECRET or "CHANGE_THIS" in secret:
                raise ValueError(
                    "Production configuration error: JWT_SECRET must be set to a secure, non-default secret."
                )
            self.JWT_SECRET = secret
        else:
            self.JWT_SECRET = secret or DEV_ONLY_JWT_SECRET

        return self

    @model_validator(mode="after")
    def normalize_database_url(self) -> "Settings":
        """
        Normalizes cloud PostgreSQL connection URLs (especially Neon Serverless PostgreSQL)
        to psycopg v3 driver with SSL required.
        Supports NEON_DATABASE_URL, DATABASE_URL, or discrete NEON credentials (NEON_HOST, NEON_USER, etc.).
        """
        # Priority 1: Direct NEON_DATABASE_URL
        target_url = self.NEON_DATABASE_URL or self.DATABASE_URL

        # Priority 2: Construct from discrete Neon parameters if provided
        if (not target_url or target_url.startswith("sqlite")) and self.NEON_HOST and self.NEON_USER and self.NEON_PASSWORD:
            target_url = f"postgresql://{self.NEON_USER}:{self.NEON_PASSWORD}@{self.NEON_HOST}/{self.NEON_DATABASE or 'neondb'}?sslmode={self.NEON_SSLMODE or 'require'}"

        if target_url:
            db_u = target_url.strip()
            # Ensure modern psycopg driver prefix
            if db_u.startswith("postgres://"):
                db_u = db_u.replace("postgres://", "postgresql+psycopg://", 1)
            elif db_u.startswith("postgresql://") and not db_u.startswith("postgresql+"):
                db_u = db_u.replace("postgresql://", "postgresql+psycopg://", 1)

            # Ensure sslmode=require for Neon serverless endpoints
            if "neon.tech" in db_u and "sslmode" not in db_u:
                delimiter = "&" if "?" in db_u else "?"
                db_u = f"{db_u}{delimiter}sslmode=require"

            self.DATABASE_URL = db_u

        return self

    @model_validator(mode="after")
    def validate_cors_origins(self) -> "Settings":
        is_prod = str(self.ENVIRONMENT).lower() in ("production", "prod")
        origins = self.cors_origins_list
        if is_prod:
            if not origins or "*" in origins:
                raise ValueError(
                    "Production configuration error: CORS_ORIGINS must be set to explicit allowed origins and cannot contain wildcard '*' when allow_credentials=True."
                )
        return self

    @property
    def cors_origins_list(self) -> List[str]:
        """Parsed list of allowed CORS origins from CORS_ORIGINS environment variable."""
        val = self.CORS_ORIGINS
        if isinstance(val, list):
            origins = val
        elif isinstance(val, str):
            origins = [origin.strip() for origin in val.split(",") if origin.strip()]
        else:
            origins = []
        return [o.rstrip("/") for o in origins]

    @property
    def SECRET_KEY(self) -> str:
        """Backward compatibility alias for JWT_SECRET"""
        return self.JWT_SECRET or DEV_ONLY_JWT_SECRET

settings = Settings()

