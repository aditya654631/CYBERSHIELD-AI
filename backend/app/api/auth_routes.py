from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.models.db import get_db
from backend.app.models.models import User
from backend.app.schemas.schemas import LoginRequest, Token, UserResponse
from backend.app.auth.security import verify_password, create_access_token, get_current_user
from backend.app.services.audit_service import log_audit

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=Token)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid officer credentials or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.email, "role": user.role})

    # Log audit
    log_audit(
        db=db,
        user_id=user.id,
        officer_name=user.full_name,
        role=user.role,
        action="LOGIN",
        details=f"Successful officer login from {user.role}"
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
            "organization_name": user.organization.name if user.organization else "National Cybercrime Coordination Centre (I4C)"
        }
    }

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
