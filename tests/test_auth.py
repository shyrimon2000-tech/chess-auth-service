import pytest
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import RefreshToken, User
from app.routers.auth import router as auth_router
from app.services.auth_service import hash_refresh_token

SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


test_app = FastAPI()
test_app.include_router(auth_router)
test_app.dependency_overrides[get_db] = override_get_db
client = TestClient(test_app)


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _register(username="alex", email="alex@example.com", password="strong_password"):
    return client.post("/auth/register", json={"username": username, "email": email, "password": password})


def _login(email="alex@example.com", password="strong_password"):
    return client.post("/auth/login", json={"email": email, "password": password})


# --- POST /auth/register ---

def test_register_returns_user():
    r = _register()
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == 1
    assert data["username"] == "alex"
    assert data["email"] == "alex@example.com"
    assert data["role"] == "user"
    assert data["is_active"] is True
    assert "hashed_password" not in data


def test_register_last_seen_at_is_null():
    r = _register()
    assert r.json()["last_seen_at"] is None


def test_register_duplicate_email_fails():
    _register()
    r = _register(username="alex2", email="alex@example.com")
    assert r.status_code == 400
    assert r.json()["detail"] == "Email already registered"


def test_register_duplicate_username_fails():
    _register()
    r = _register(username="alex", email="other@example.com")
    assert r.status_code == 400
    assert r.json()["detail"] == "Username already taken"


def test_register_invalid_email_returns_422():
    r = _register(email="not-an-email")
    assert r.status_code == 422


# --- POST /auth/login ---

def test_login_returns_tokens():
    _register()
    r = _login()
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_login_updates_last_seen_at():
    _register()
    _login()
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == "alex@example.com").first()
    db.close()
    assert user.last_seen_at is not None


def test_login_wrong_password_fails():
    _register()
    r = _login(password="wrong_password")
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid email or password"


def test_login_nonexistent_email_fails():
    r = _login(email="nobody@example.com")
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid email or password"


def test_login_disabled_account_fails():
    _register()
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == "alex@example.com").first()
    user.is_active = False
    db.commit()
    db.close()
    r = _login()
    assert r.status_code == 401
    assert r.json()["detail"] == "User account is disabled"


# --- GET /auth/me ---

def test_get_me_returns_current_user():
    _register()
    token = _login().json()["access_token"]
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == 1
    assert data["username"] == "alex"
    assert data["email"] == "alex@example.com"
    assert data["is_active"] is True


def test_get_me_without_token_returns_401():
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_get_me_invalid_token_returns_401():
    r = client.get("/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert r.status_code == 401


def test_get_me_disabled_account_returns_401():
    _register()
    token = _login().json()["access_token"]
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == "alex@example.com").first()
    user.is_active = False
    db.commit()
    db.close()
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    assert r.json()["detail"] == "User account is disabled"


# --- GET /auth/admin-only ---

def test_admin_only_rejects_regular_user():
    _register()
    token = _login().json()["access_token"]
    r = client.get("/auth/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
    assert r.json()["detail"] == "Admin privileges required"


def test_admin_only_allows_admin():
    _register()
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == "alex@example.com").first()
    user.role = "admin"
    db.commit()
    db.close()
    token = _login().json()["access_token"]
    r = client.get("/auth/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == "alex@example.com"
    assert data["role"] == "admin"


# --- POST /auth/refresh ---

def test_refresh_returns_new_tokens():
    _register()
    rt = _login().json()["refresh_token"]
    r = client.post("/auth/refresh", json={"refresh_token": rt})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["refresh_token"] != rt
    assert data["token_type"] == "bearer"


def test_refresh_rotates_token():
    _register()
    old_rt = _login().json()["refresh_token"]
    client.post("/auth/refresh", json={"refresh_token": old_rt})
    r = client.post("/auth/refresh", json={"refresh_token": old_rt})
    assert r.status_code == 401
    assert r.json()["detail"] == "Refresh token has been revoked"


def test_refresh_with_invalid_token_fails():
    r = client.post("/auth/refresh", json={"refresh_token": "totally-fake-token"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid refresh token"


def test_refresh_with_expired_token_fails():
    _register()
    rt = _login().json()["refresh_token"]
    token_hash = hash_refresh_token(rt)
    db = TestingSessionLocal()
    stored = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    stored.expires_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
    db.commit()
    db.close()
    r = client.post("/auth/refresh", json={"refresh_token": rt})
    assert r.status_code == 401
    assert r.json()["detail"] == "Refresh token has expired"


# --- POST /auth/logout ---

def test_logout_succeeds():
    _register()
    rt = _login().json()["refresh_token"]
    r = client.post("/auth/logout", json={"refresh_token": rt})
    assert r.status_code == 200
    assert r.json()["message"] == "Successfully logged out"


def test_refresh_after_logout_fails():
    _register()
    rt = _login().json()["refresh_token"]
    client.post("/auth/logout", json={"refresh_token": rt})
    r = client.post("/auth/refresh", json={"refresh_token": rt})
    assert r.status_code == 401
    assert r.json()["detail"] == "Refresh token has been revoked"


def test_logout_already_revoked_fails():
    _register()
    rt = _login().json()["refresh_token"]
    client.post("/auth/logout", json={"refresh_token": rt})
    r = client.post("/auth/logout", json={"refresh_token": rt})
    assert r.status_code == 401
    assert r.json()["detail"] == "Refresh token already revoked"


def test_logout_with_invalid_token_fails():
    r = client.post("/auth/logout", json={"refresh_token": "fake-token"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid refresh token"
