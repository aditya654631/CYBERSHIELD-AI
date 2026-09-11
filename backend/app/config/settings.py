import os
from typing import Optional
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

    # JWT Authentication Configuration
    JWT_SECRET: Optional[str] = None
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Database Configuration (supports SQLite for local dev and PostgreSQL for production)
    DATABASE_URL: str = "sqlite:///./cybershield.db"

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
        """Normalizes cloud PostgreSQL connection URLs (e.g. postgres:// or standard postgresql://) to psycopg v3 driver."""
        if self.DATABASE_URL:
            db_u = self.DATABASE_URL.strip()
            if db_u.startswith("postgres://"):
                self.DATABASE_URL = db_u.replace("postgres://", "postgresql+psycopg://", 1)
            elif db_u.startswith("postgresql://") and not db_u.startswith("postgresql+"):
                self.DATABASE_URL = db_u.replace("postgresql://", "postgresql+psycopg://", 1)
        return self

    @property
    def SECRET_KEY(self) -> str:
        """Backward compatibility alias for JWT_SECRET"""
        return self.JWT_SECRET or DEV_ONLY_JWT_SECRET

settings = Settings()

