from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from backend.app.models.db import get_db
from backend.app.models.models import User
from backend.app.schemas.schemas import LoginRequest, Token, UserResponse
from backend.app.auth.security import verify_password, create_access_token, get_current_user
from backend.app.auth.rate_limiter import login_rate_limiter
from backend.app.services.audit_service import log_audit

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=Token)
def login(request: LoginRequest, req: Request, db: Session = Depends(get_db)):
    # 1. Check rate limit
    login_rate_limiter.check_rate_limit(req, request.email)

    user = db.query(User).filter(User.email == request.email).first()
    if not user or not verify_password(request.password, user.hashed_password):
        login_rate_limiter.record_failure(req, request.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid officer credentials or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Inactive user verification
    if not user.is_active:
        login_rate_limiter.record_failure(req, request.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is deactivated. Contact system administrator.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Successful login: clear rate limit counters
    login_rate_limiter.record_success(req, request.email)

    access_token = create_access_token(data={"sub": user.email, "role": user.role})

    # Log audit without sensitive data
    log_audit(
        db=db,
        user_id=user.id,
        officer_name=user.full_name,
        role=user.role,
        action="LOGIN",
        details=f"Successful officer login for {user.email} ({user.role})"
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "badge_number": user.badge_number,
            "organization_name": user.organization.name if user.organization else "National Cybercrime Coordination Centre (I4C)",
            "state": user.state,
            "district": user.district
        }
    }


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
