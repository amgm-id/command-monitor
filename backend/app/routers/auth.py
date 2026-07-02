from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from app.utils.timezone import utc_now
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserLogin, Token, UserResponse
from app.utils.security import verify_password, create_access_token, get_current_user, get_client_ip
from app.services.audit_service import log_action
from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()


@router.post("/login", response_model=Token)
def login(credentials: UserLogin, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == credentials.username.lower()).first()

    if not user or not verify_password(credentials.password, user.password_hash):
        log_action(
            db, None, "LOGIN_FAILED",
            details={"username": credentials.username},
            ip_address=get_client_ip(request),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    user.last_login = utc_now()
    db.commit()

    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username, "role": user.role.value},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    log_action(db, user, "LOGIN_SUCCESS", ip_address=get_client_ip(request))

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post("/logout")
def logout(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    log_action(db, current_user, "LOGOUT", ip_address=get_client_ip(request))
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
