from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.routers.auth import router as auth_router
from app.models import User


SQLALCHEMY_DATABASE_URL = "sqlite://"


engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def create_test_app():
    Base.metadata.create_all(bind=engine)

    test_app = FastAPI()
    test_app.include_router(auth_router)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    test_app.dependency_overrides[get_db] = override_get_db

    return test_app


def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


app = create_test_app()
client = TestClient(app)


def test_register_user_successfully():
    reset_database()

    response = client.post(
        "/auth/register",
        json={
            "username": "alex",
            "email": "alex@example.com",
            "password": "strong_password",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == 1
    assert data["username"] == "alex"
    assert data["email"] == "alex@example.com"
    assert data["is_active"] is True
    assert "hashed_password" not in data


def test_register_duplicate_email_fails():
    reset_database()

    client.post(
        "/auth/register",
        json={
            "username": "alex",
            "email": "alex@example.com",
            "password": "strong_password",
        },
    )

    response = client.post(
        "/auth/register",
        json={
            "username": "alex2",
            "email": "alex@example.com",
            "password": "another_password",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"


def test_login_successfully_returns_token():
    reset_database()

    client.post(
        "/auth/register",
        json={
            "username": "alex",
            "email": "alex@example.com",
            "password": "strong_password",
        },
    )

    response = client.post(
        "/auth/login",
        json={
            "email": "alex@example.com",
            "password": "strong_password",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_login_with_wrong_password_fails():
    reset_database()

    client.post(
        "/auth/register",
        json={
            "username": "alex",
            "email": "alex@example.com",
            "password": "strong_password",
        },
    )

    response = client.post(
        "/auth/login",
        json={
            "email": "alex@example.com",
            "password": "wrong_password",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_get_current_user_with_token():
    reset_database()

    client.post(
        "/auth/register",
        json={
            "username": "alex",
            "email": "alex@example.com",
            "password": "strong_password",
        },
    )

    login_response = client.post(
        "/auth/login",
        json={
            "email": "alex@example.com",
            "password": "strong_password",
        },
    )

    token = login_response.json()["access_token"]

    me_response = client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert me_response.status_code == 200

    data = me_response.json()

    assert data["id"] == 1
    assert data["username"] == "alex"
    assert data["email"] == "alex@example.com"
    assert data["is_active"] is True


def test_refresh_returns_new_access_token():
    reset_database()

    client.post(
        "/auth/register",
        json={
            "username": "alex",
            "email": "alex@example.com",
            "password": "strong_password",
        },
    )

    login_response = client.post(
        "/auth/login",
        json={
            "email": "alex@example.com",
            "password": "strong_password",
        },
    )

    refresh_token = login_response.json()["refresh_token"]

    refresh_response = client.post(
        "/auth/refresh",
        json={
            "refresh_token": refresh_token,
        },
    )

    assert refresh_response.status_code == 200

    data = refresh_response.json()

    assert "access_token" in data
    assert data["refresh_token"] == refresh_token
    assert data["token_type"] == "bearer"


def test_logout_revokes_refresh_token():
    reset_database()

    client.post(
        "/auth/register",
        json={
            "username": "alex",
            "email": "alex@example.com",
            "password": "strong_password",
        },
    )

    login_response = client.post(
        "/auth/login",
        json={
            "email": "alex@example.com",
            "password": "strong_password",
        },
    )

    refresh_token = login_response.json()["refresh_token"]

    logout_response = client.post(
        "/auth/logout",
        json={
            "refresh_token": refresh_token,
        },
    )

    assert logout_response.status_code == 200
    assert logout_response.json()["message"] == "Successfully logged out"


def test_refresh_after_logout_fails():
    reset_database()

    client.post(
        "/auth/register",
        json={
            "username": "alex",
            "email": "alex@example.com",
            "password": "strong_password",
        },
    )

    login_response = client.post(
        "/auth/login",
        json={
            "email": "alex@example.com",
            "password": "strong_password",
        },
    )

    refresh_token = login_response.json()["refresh_token"]

    client.post(
        "/auth/logout",
        json={
            "refresh_token": refresh_token,
        },
    )

    refresh_response = client.post(
        "/auth/refresh",
        json={
            "refresh_token": refresh_token,
        },
    )

    assert refresh_response.status_code == 401
    assert refresh_response.json()["detail"] == "Refresh token has been revoked"


def test_admin_only_endpoint_rejects_regular_user():
    reset_database()

    client.post(
        "/auth/register",
        json={
            "username": "alex",
            "email": "alex@example.com",
            "password": "strong_password",
        },
    )

    login_response = client.post(
        "/auth/login",
        json={
            "email": "alex@example.com",
            "password": "strong_password",
        },
    )

    token = login_response.json()["access_token"]

    response = client.get(
        "/auth/admin-only",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin privileges required"


def test_login_with_disabled_account_fails():
    reset_database()

    client.post(
        "/auth/register",
        json={
            "username": "alex",
            "email": "alex@example.com",
            "password": "strong_password",
        },
    )

    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == "alex@example.com").first()
    user.is_active = False
    db.commit()
    db.close()

    response = client.post(
        "/auth/login",
        json={
            "email": "alex@example.com",
            "password": "strong_password",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "User account is disabled"


def test_get_me_with_disabled_account_fails():
    reset_database()

    client.post(
        "/auth/register",
        json={
            "username": "alex",
            "email": "alex@example.com",
            "password": "strong_password",
        },
    )

    login_response = client.post(
        "/auth/login",
        json={
            "email": "alex@example.com",
            "password": "strong_password",
        },
    )

    token = login_response.json()["access_token"]

    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == "alex@example.com").first()
    user.is_active = False
    db.commit()
    db.close()

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "User account is disabled"


def test_admin_only_endpoint_allows_admin_user():
    reset_database()

    client.post(
        "/auth/register",
        json={
            "username": "alex",
            "email": "alex@example.com",
            "password": "strong_password",
        },
    )

    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == "alex@example.com").first()
    user.role = "admin"
    db.commit()
    db.close()

    login_response = client.post(
        "/auth/login",
        json={
            "email": "alex@example.com",
            "password": "strong_password",
        },
    )

    token = login_response.json()["access_token"]

    response = client.get(
        "/auth/admin-only",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["email"] == "alex@example.com"
    assert data["role"] == "admin"