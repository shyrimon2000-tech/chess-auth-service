from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import UserCreate, UserLogin, UserResponse, TokenResponse, RefreshTokenRequest, LogoutRequest, MessageResponse
from app.services.auth_service import register_user, login_user, refresh_access_token, logout_user
from app.models import User
from app.services.auth_dependencies import get_current_user, get_current_admin_user

router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)


@router.post("/register", response_model=UserResponse)
def register(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    try:
        return register_user(db, user_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=TokenResponse)
def login(
    login_data: UserLogin,
    db: Session = Depends(get_db)
):
    try:
        tokens = login_user(db, login_data)
        return tokens
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: User = Depends(get_current_user)
):
    return current_user


@router.get("/admin-only", response_model=UserResponse)
def admin_only(
    current_user: User = Depends(get_current_admin_user)
):
    return current_user


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    try:
        tokens = refresh_access_token(db, refresh_data.refresh_token)
        return tokens
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/logout", response_model=MessageResponse)
def logout(
    logout_data: LogoutRequest,
    db: Session = Depends(get_db)
):
    try:
        return logout_user(db, logout_data.refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))