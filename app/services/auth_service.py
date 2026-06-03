from datetime import datetime, timedelta, timezone

import secrets
import hashlib

import bcrypt
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings

from app.repositories.user_repo import (
    get_user_by_id,
    get_user_by_email,
    get_user_by_username,
    create_user,
    update_user_last_seen
)
from app.schemas import UserCreate, UserLogin

from app.repositories.refresh_token_repo import (
    create_refresh_token,
    get_refresh_token_by_hash,
    revoke_refresh_token
)

def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password_bytes, salt)
    return hashed_password.decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        password.encode("utf-8"),
        hashed_password.encode("utf-8")
    )


def create_access_token(data: dict) -> str:
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    to_encode.update({"exp": expire})

    token = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )

    return token


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )

        return payload

    except JWTError:
        raise ValueError("Invalid or expired token")


def register_user(db: Session, user_data: UserCreate):
    existing_email = get_user_by_email(db, user_data.email)
    if existing_email:
        raise ValueError("Email already registered")

    existing_username = get_user_by_username(db, user_data.username)
    if existing_username:
        raise ValueError("Username already taken")

    hashed_password = hash_password(user_data.password)

    user = create_user(
        db=db,
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password
    )

    return user


def login_user(db: Session, login_data: UserLogin):
    user = get_user_by_email(db, login_data.email)

    if not user:
        raise ValueError("Invalid email or password")

    if not verify_password(login_data.password, user.hashed_password):
        raise ValueError("Invalid email or password")

    if not user.is_active:
        raise ValueError("User account is disabled")

    update_user_last_seen(db, user)

    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "role": user.role,
        }
    )

    refresh_token = create_refresh_token_for_user(db, user.id)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token
    }


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def hash_refresh_token(refresh_token: str) -> str:
    return hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()


def create_refresh_token_for_user(db: Session, user_id: int) -> str:
    refresh_token = generate_refresh_token()
    token_hash = hash_refresh_token(refresh_token)

    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )

    create_refresh_token(
        db=db,
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at
    )

    return refresh_token


def refresh_access_token(db: Session, refresh_token: str):
    token_hash = hash_refresh_token(refresh_token)

    stored_token = get_refresh_token_by_hash(db, token_hash)

    if not stored_token:
        raise ValueError("Invalid refresh token")

    if stored_token.revoked_at is not None:
        raise ValueError("Refresh token has been revoked")

    expires_at = stored_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise ValueError("Refresh token has expired")

    user = get_user_by_id(db, stored_token.user_id)

    if not user:
        raise ValueError("User not found")

    if not user.is_active:
        raise ValueError("User account is disabled")

    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "role": user.role,
        }
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token
    }


def logout_user(db: Session, refresh_token: str):
    token_hash = hash_refresh_token(refresh_token)

    stored_token = get_refresh_token_by_hash(db, token_hash)

    if not stored_token:
        raise ValueError("Invalid refresh token")

    if stored_token.revoked_at is not None:
        raise ValueError("Refresh token already revoked")

    revoke_refresh_token(db, stored_token)

    return {
        "message": "Successfully logged out"
    }