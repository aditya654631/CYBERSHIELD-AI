import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
from jose import JWTError, jwt, ExpiredSignatureError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from backend.app.config.settings import settings
from backend.app.models.db import get_db
from backend.app.models.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def has_valid_role_organization_scope(user: User) -> bool:
    """Validate trusted database role/organization pairing before authorization."""
    org = getattr(user, "organization", None)
    role = (getattr(user, "role", None) or "").upper()
    if not org:
        return False
    org_type = (org.org_type or "").upper()
    expected = {
        "I4C_ADMIN": {"I4C"},
        "STATE_LEA": {"LEA"},
        "DISTRICT_LEA": {"LEA"},
        "BANK_OFFICER": {"BANK"},
        "ANALYST": {"I4C", "LEA"},
        "AUDITOR": {"I4C", "LEA"},
    }
    return role in expected and org_type in expected[role]


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain password against stored hash using constant-time comparison.
    Supports bcrypt and existing pbkdf2 hashes.
    Plaintext passwords are strictly rejected with zero fallback.
    """
    if not plain_password or not hashed_password:
        return False

    # 1. Bcrypt hashes ($2a$, $2b$, $2y$)
    if hashed_password.startswith(("$2a$", "$2b$", "$2y$")):
        try:
            return bcrypt.checkpw(
                plain_password.encode("utf-8"),
                hashed_password.encode("utf-8")
            )
        except Exception:
            return False

    # 2. Existing PBKDF2 hashes (pbkdf2:salt:hex)
    if hashed_password.startswith("pbkdf2:"):
        parts = hashed_password.split(":")
        if len(parts) == 3:
            _, salt, hashed = parts
            test_hash = hashlib.pbkdf2_hmac(
                "sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), 100000
            ).hex()
            return secrets.compare_digest(test_hash, hashed)

    # Reject plaintext and unknown formats
    return False


def get_password_hash(password: str) -> str:
    """Generates a secure bcrypt hash with 12 rounds of salting."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a signed JWT with expiration timestamp."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.ALGORITHM)
    return encoded_jwt


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """
    Validates JWT token and retrieves active user.
    Rejects missing, forged, expired, and inactive-user credentials.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is deactivated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not has_valid_role_organization_scope(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User role and organization scope are not configured for access",
        )

    return user


def verify_ws_token(token: Optional[str], db: Session) -> User:
    """
    Validates a JWT token supplied via WebSocket query parameter.
    Returns the authenticated active User, or raises HTTPException(401).
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="WebSocket connection requires an authenticated token parameter"
        )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if not email:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token claims")
    except ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="WebSocket token has expired")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid WebSocket token signature")

    user = db.query(User).filter(User.email == email).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    if not has_valid_role_organization_scope(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User scope is not configured")

    return user
