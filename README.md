# Chess Auth Service

A standalone authentication microservice for a chess web application.

This service handles user registration, login, JWT-based authentication, refresh tokens, logout/session revocation, role-based authorization, password hashing, protected user identity lookup, database migrations, automated tests, and MySQL persistence.

The project is designed as a separate backend microservice that can later be connected to the main chess application or other services.

---

## Badges

Dev: [![CI Dev](https://github.com/shyrimon2000-tech/chess-auth-service/actions/workflows/ci.yml/badge.svg?branch=dev)](https://github.com/shyrimon2000-tech/chess-auth-service/actions)

Pull Request: [![CI PR](https://github.com/shyrimon2000-tech/chess-auth-service/actions/workflows/ci.yml/badge.svg?event=pull_request)](https://github.com/shyrimon2000-tech/chess-auth-service/actions)


---

## Features

- User registration
- User login
- JWT access token generation
- Refresh token generation
- Server-side logout through refresh token revocation
- Protected `/auth/me` endpoint
- Role-based access control with `user` and `admin` roles
- Admin-only protected endpoint
- Password hashing with bcrypt
- Refresh tokens stored as hashes
- MySQL database persistence
- SQLAlchemy ORM
- Alembic database migrations
- Automated tests with pytest
- Dockerized FastAPI application
- Docker Compose setup with MySQL
- Health check endpoint
- Basic account status support with `is_active`
- User activity tracking with `last_seen_at`

---

## Tech Stack

- Python 3.11
- FastAPI
- Uvicorn
- SQLAlchemy
- Alembic
- MySQL
- PyMySQL
- bcrypt
- python-jose
- Pydantic Settings
- tenacity
- pytest
- Docker
- Docker Compose

---

## Project Structure

```text
app/
├── routers/
│   └── auth.py
├── services/
│   ├── auth_service.py
│   └── auth_dependencies.py
├── repositories/
│   ├── user_repo.py
│   └── refresh_token_repo.py
├── config.py
├── database.py
├── main.py
├── models.py
└── schemas.py

alembic/
├── versions/
└── env.py

tests/
└── test_auth.py

e2e_tests/
├── chess_test1.py  — T1–T4:   complete resign game
├── chess_test2.py  — T5–T8:   disconnect and reconnect within 30 s
├── chess_test3.py  — T9–T12:  disconnect timeout, game abandoned
├── chess_test4.py  — T13–T16: resign flow, room cleanup
├── chess_test5.py  — T17–T20: quick join, matchmaking, spectator join
├── chess_test6.py  — T21–T23: auth flows (unauth redirect, bad credentials, logout)
├── chess_test7.py  — T24–T27: spectator joins active game
├── chess_test8.py  — T28–T31: board interaction, legal moves, turn guard
├── chess_test9.py  — T32–T34: return-to-game panel, direct navigation redirect
├── helpers.py      — registration helper, rate limit guard
├── cleanup.py      — test data teardown across all services
└── pytest-e2e.ini  — E2E pytest configuration
```

---

## API Endpoints

### Health Check

```http
GET /health
```

Response:

```json
{
  "status": "ok"
}
```

---

### Register User

```http
POST /auth/register
```

Creates a new user account.

Request body:

```json
{
  "username": "alex",
  "email": "alex@example.com",
  "password": "strong_password"
}
```

Response:

```json
{
  "id": 1,
  "username": "alex",
  "email": "alex@example.com",
  "role": "user",
  "is_active": true,
  "created_at": "2026-05-24T12:00:00",
  "last_seen_at": null
}
```

Notes:

- Passwords are never stored as plain text.
- The service stores only bcrypt password hashes.
- Duplicate email or username registration is rejected.
- New users are created with the default `user` role.

---

### Login

```http
POST /auth/login
```

Authenticates a user and returns both an access token and a refresh token.

Request body:

```json
{
  "email": "alex@example.com",
  "password": "strong_password"
}
```

Response:

```json
{
  "access_token": "jwt_access_token",
  "refresh_token": "random_refresh_token",
  "token_type": "bearer"
}
```

Notes:

- The password is verified against the stored bcrypt hash.
- On successful login, `last_seen_at` is updated.
- The service returns a signed JWT access token.
- The access token includes the user's ID in the `sub` claim and the user's role in the `role` claim.
- The service also returns a refresh token for session renewal.
- The raw refresh token is returned to the client only once.
- The database stores only a hash of the refresh token.

---

### Current User

```http
GET /auth/me
```

Returns the currently authenticated user.

Required header:

```http
Authorization: Bearer <access_token>
```

Response:

```json
{
  "id": 1,
  "username": "alex",
  "email": "alex@example.com",
  "role": "user",
  "is_active": true,
  "created_at": "2026-05-24T12:00:00",
  "last_seen_at": "2026-05-24T12:10:00"
}
```

Notes:

- The endpoint validates the JWT signature.
- The endpoint checks token expiration.
- The user ID is extracted from the JWT `sub` claim.
- The user is loaded from MySQL.
- Disabled users are rejected.

---

### Refresh Access Token

```http
POST /auth/refresh
```

Uses a valid refresh token to issue a new access token.

Request body:

```json
{
  "refresh_token": "random_refresh_token"
}
```

Response:

```json
{
  "access_token": "new_jwt_access_token",
  "refresh_token": "new_refresh_token",
  "token_type": "bearer"
}
```

Notes:

- The refresh token is checked against its stored hash.
- Revoked refresh tokens are rejected.
- Expired refresh tokens are rejected.
- Refresh tokens belonging to disabled users are rejected.
- The newly issued access token includes the user's ID in the `sub` claim and the user's current role in the `role` claim.
- The old refresh token is revoked and a new one is issued on every call (rotation). Using the old token again returns 401.

---

### Logout

```http
POST /auth/logout
```

Revokes the refresh token so it can no longer be used.

Request body:

```json
{
  "refresh_token": "random_refresh_token"
}
```

Response:

```json
{
  "message": "Successfully logged out"
}
```

Notes:

- Logout is handled server-side.
- The refresh token is marked as revoked in the database.
- After logout, the same refresh token can no longer be used with `/auth/refresh`.

---

### Admin-Only Endpoint

```http
GET /auth/admin-only
```

Requires a valid access token that belongs to a user with the `admin` role.

Required header:

```http
Authorization: Bearer <access_token>
```

Response for regular users:

```json
{
  "detail": "Admin privileges required"
}
```

Response status:

```text
403 Forbidden
```

Response for admin users:

```json
{
  "id": 1,
  "username": "alex",
  "email": "alex@example.com",
  "role": "admin",
  "is_active": true,
  "created_at": "2026-05-24T12:00:00",
  "last_seen_at": "2026-05-24T12:10:00"
}
```

Notes:

- This endpoint is used to validate role-based access control.
- Authentication is handled by the access token.
- Authorization is handled by checking `current_user.role == "admin"`.

---

## Authentication Flow

```text
Register
↓
Hash password with bcrypt
↓
Store user in MySQL with role = user
↓
Login
↓
Verify password
↓
Update last_seen_at
↓
Issue JWT access token with sub, role, and exp claims
↓
Issue refresh token
↓
Store refresh token hash in MySQL
↓
Client sends access token in Authorization header
↓
Protected endpoints validate access token
↓
Backend identifies the current user from JWT subject
↓
Backend reads the user's global role from the JWT role claim
↓
When access token expires, client sends refresh token
↓
Backend validates refresh token
↓
Backend issues new access token with updated role claim
↓
On logout, backend revokes refresh token

```

---

## Authorization Flow

The service supports basic role-based access control.

Current roles:

```text
user
admin
```

Default role:

```text
user
```

Regular protected endpoints require a valid authenticated user.

Admin-only endpoints require:

```text
current_user.role == "admin"
```

Authorization flow:

```text
Request with access token
↓
Validate JWT
↓
Load user from database
↓
Check account status
↓
Check user role
↓
Allow or reject request
```

Example:

```text
role = user  → /auth/admin-only returns 403
role = admin → /auth/admin-only returns 200
```

---

## JWT Design

The access token contains minimal identity and authorization data:

```json
{
  "sub": "1",
  "role": "user",
  "username": "alex",
  "exp": "expiration_time"
}
```

Fields:

- `sub` — user ID as a string
- `role` — user's authorization role (`user` or `admin`)
- `username` — username, included so other services can display the player name without a DB lookup
- `exp` — token expiration time

JWT payload is readable by the client, but it cannot be modified without invalidating the signature.

The access token is signed by the auth-service using `JWT_SECRET_KEY` and `JWT_ALGORITHM`.

Access tokens are short-lived and are used to access protected API endpoints.

Important:

- The frontend receives the access token after login.
- The frontend sends the access token to protected services using the `Authorization` header.
- Backend services must never trust `user_id` or `role` from request bodies.
- Backend services must extract `sub` and `role` only from a valid signed JWT.

Example authorization header:

```http
Authorization: Bearer <access_token>
```

The service uses these environment variables:

```text
JWT_SECRET_KEY
JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES
```

---

## Refresh Token Design

Refresh tokens are long-lived random tokens generated by the backend.

The raw refresh token is returned to the client after login.

The database does not store the raw refresh token. Instead, the service stores a SHA-256 hash of the refresh token.

Refresh tokens allow the client to request a new access token without asking the user to log in again.

Refresh tokens are rotated on every use — the old token is revoked and a new one is issued. Refresh tokens can also be explicitly revoked during logout.

Stored refresh token fields include:

```text
user_id
token_hash
created_at
expires_at
revoked_at
```

---

## Environment Variables

Create a `.env` file based on `.env.example`.

Example:

```env
# MySQL container settings
MYSQL_ROOT_PASSWORD=change-root-password
MYSQL_DATABASE=chess_auth_db
MYSQL_USER=chess_user
MYSQL_PASSWORD=change-user-password

# Application database connection
DATABASE_URL=mysql+pymysql://chess_user:change-user-password@auth-db:3306/chess_auth_db

# JWT settings
JWT_SECRET_KEY=change-this-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

Important:

- `.env` contains real secrets and must not be committed.
- `.env.example` is safe to commit as a template.
- `DATABASE_URL` uses `auth-db` as the MySQL host when running with Docker Compose.

---

## Run with Docker Compose

Build and start the service:

```bash
docker compose up --build
```

Run in detached mode:

```bash
docker compose up -d --build
```

The API will be available at:

```text
http://127.0.0.1:8000
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

Health check:

```text
http://127.0.0.1:8000/health
```

---

## Database Migrations

This project uses Alembic for database schema migrations.

The application does not create database tables automatically on startup. Database schema changes are managed through Alembic migrations.

Create a new migration:

```bash
docker compose exec auth-service alembic revision --autogenerate -m "migration message"
```

Apply migrations:

```bash
docker compose exec auth-service alembic upgrade head
```

Check current migration version:

```bash
docker compose exec auth-service alembic current
```

Show migration history:

```bash
docker compose exec auth-service alembic history
```

Current database tables:

```text
alembic_version
users
refresh_tokens
```

---

## Run Locally without Docker

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it.

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements-dev.txt
```

Run the service:

```bash
uvicorn app.main:app --reload
```

Open Swagger UI:

```text
http://127.0.0.1:8000/docs
```

Notes:

- `requirements.txt` contains production dependencies only.
- `requirements-dev.txt` includes `requirements.txt` and adds `pytest` and `httpx` for running tests.
- When running locally without Docker, make sure `DATABASE_URL` points to a MySQL host that is reachable from the local machine.

---

## Database

The service uses MySQL with two tables: `users` and `refresh_tokens`. Schema details are covered in the Database Model section of CLAUDE.md.

Current tables:

```text
alembic_version
users
refresh_tokens
```

---

## Docker Compose Architecture

```text
Browser / API client
        ↓
localhost:8000
        ↓
auth-service container
        ↓
Docker internal network
        ↓
auth-db MySQL container
```

The MySQL container is not exposed directly to the host by default.

The application connects to MySQL using the Docker Compose service name:

```text
auth-db:3306
```

---

## Automated Tests

The project includes automated tests for the authentication and authorization flow.

Run tests:

```bash
pytest -v
```

Current test coverage includes:

- user registration — returns correct fields, `last_seen_at` is null
- duplicate email rejected
- duplicate username rejected
- invalid email format rejected (422)
- login returns access token and refresh token
- `last_seen_at` updated on login
- wrong password rejected
- non-existent email rejected
- disabled account rejected at login
- `GET /auth/me` with valid token
- `GET /auth/me` without token rejected
- `GET /auth/me` with invalid token rejected
- `GET /auth/me` with disabled account rejected
- admin-only endpoint rejects regular user
- admin-only endpoint allows admin
- refresh returns new tokens with rotation
- old refresh token rejected after rotation
- invalid refresh token rejected
- expired refresh token rejected
- logout succeeds
- refresh after logout rejected
- double logout rejected
- invalid token on logout rejected

Example result:

```text
24 passed
```

---

## E2E Tests

The project includes a full end-to-end test suite using Playwright. The E2E tests run against the real stack — auth-service, chess-room-service, and chess-game-service — via Docker Compose.

34 tests across 9 modules cover the full gameplay lifecycle:

| Module | Tests | Scenario |
|---|---|---|
| chess_test1 | T1–T4 | Complete resign game |
| chess_test2 | T5–T8 | Disconnect and reconnect within 30 s |
| chess_test3 | T9–T12 | Disconnect timeout, game abandoned |
| chess_test4 | T13–T16 | Resign flow, room deleted after game over |
| chess_test5 | T17–T20 | Quick join creates room, explicit join, spectator |
| chess_test6 | T21–T23 | Unauthenticated redirect, bad credentials, logout |
| chess_test7 | T24–T27 | Spectator joins active game, board perspective |
| chess_test8 | T28–T31 | Legal move highlights, turn guard, move execution |
| chess_test9 | T32–T34 | Return-to-game panel, direct navigation redirect |

Build the combined env file and bring up the E2E stack:

```bash
cat .env.e2e e2e_versions.env > .env.combined
docker compose -f docker-compose.e2e.yml --env-file .env.combined up -d --wait
```

Run all E2E tests:

```bash
python -m pytest -c pytest-e2e.ini -v
```

Run a single module:

```bash
python -m pytest -c pytest-e2e.ini e2e_tests/chess_test2.py -v
```

---

## E2E Test Design Notes

This section documents non-obvious problems encountered while building the E2E suite and how each was resolved. Kept here so the same issues are not rediscovered.

### Problem 1: registration rate limit breaks fixture setup

**Symptom:** Fixtures that register two or three users would sometimes hang for 15–30 seconds in the middle of setup, or fail immediately when the rate limit was raised.

**Root cause:** The application enforces a rate limit of 5 registrations per minute per IP. The CI runner shares a single IP, so all test users across all modules count against the same bucket. After 5 registrations within 60 seconds, the next one returns 429. Without a client-side guard, the fixture would hit 429, raise an exception, and tear down without setting up the game.

**Solution:** `helpers.py` tracks registration timestamps in a local JSON file (`.reg_times.json`). Before each registration it counts how many occurred in the last 60 seconds. If the count is already 5, it sleeps until the oldest timestamp expires. The guard threshold (`_LIMIT = 5`) must match the server limit exactly — a higher value disables the guard and causes 429 failures in CI.

---

### Problem 2: test isolation — fixture teardown skipped on setup failure

**Symptom:** When a fixture failed mid-setup (e.g., room creation timed out), the `finally` block with `cleanup()` did not run. Leftover users, rooms, and games from the failed run polluted the next run.

**Root cause:** A bare `yield` in a pytest fixture does not guarantee teardown when the code before `yield` raises an exception.

**Solution:** All fixtures were rewritten using `try / finally`:

```python
try:
    reg(p1, P1)
    reg(p2, P2)
    # ... setup ...
    yield
finally:
    ctx1.close()
    ctx2.close()
    cleanup(SUFFIX)
```

`cleanup()` now always runs, even when setup raises.

---

### Problem 3: cleanup.py cannot reach room-service or game-service

**Symptom:** `cleanup()` reported 0 rooms and 0 games removed even though rows existed in the databases.

**Root cause:** `cleanup.py` runs `docker compose exec` to delete rows via the service containers. Without `--env-file .env.combined`, Docker Compose could not resolve service names in the E2E compose file and silently failed.

**Solution:** Every `docker compose exec` call in `cleanup.py` passes `--env-file .env.combined`:

```python
subprocess.run([
    'docker', 'compose', '--env-file', '.env.combined',
    '-f', 'docker-compose.e2e.yml', 'exec', '-T',
    service, 'python', '-c', code
], ...)
```

---

### Problem 4: `#create-room-info` panel race condition in CI

**Symptom:** Fixtures that waited for `p1.wait_for_selector('#create-room-info:not(.hidden)', timeout=30000)` consistently timed out in CI, even though the room was successfully created (later tests in the same module confirmed it).

**Root cause:** `rooms.html` polls `GET /rooms` every ~3 seconds. Locally, `POST /rooms` responds in ~50 ms — well within one polling interval. In CI the response takes 1–3 seconds. If the polling cycle fires between the click and the `POST /rooms` response, the JavaScript state machine transitions to "show room list" mode and the waiting panel is never displayed — even though the room exists on the backend.

**First fix:** Navigate `p1` to `rooms.html` explicitly with `p1.goto(BASE + '/rooms.html')` immediately before clicking the create button. This resets the polling timer to zero, giving the full 3-second interval for `POST /rooms` to respond before the next poll.

```python
p1.goto(BASE + '/rooms.html')
p1.wait_for_selector('#create-room-btn', state='visible', timeout=10000)
p1.click('#create-room-btn')
```

This fixed most modules but tests 2, 4, and 7 still failed. Those modules run after a completed game. The game-over event from the previous test triggers a room-list refresh on rooms.html at an unpredictable time, which re-hides the panel even after the `goto` reset.

**Final fix:** Stop relying on `p1`'s waiting panel entirely in fixture setup. Confirm room creation from `p2`'s side instead — `p2.goto(rooms.html)` and `p2.wait_for_selector('.join-btn')`. `p2` seeing the join button is a deterministic, race-free confirmation that the room exists.

```python
p1.click('#create-room-btn')

p2.goto(BASE + '/rooms.html')
p2.wait_for_selector('.join-btn', timeout=15000)
p2.click('.join-btn')
```

The `#create-room-info` panel itself is tested directly only in `T17` (quick-join creates room when none available), where the timing is controlled and isolated.

---

## CI/CD Pipeline

```text
lint ──┐
       ├──▶ test ──▶ docker-build ──▶ publish (semver tags only)
type ──┘
                           ↑
                     e2e (PRs to main + semver tags only)
```

| Job | Tool | Triggers |
|---|---|---|
| `lint` | ruff | every push / PR |
| `type-check` | mypy | every push / PR |
| `test` | pytest | every push / PR |
| `docker-build` | docker build | every push / PR |
| `e2e` | pytest + Playwright | PRs to main, semver tags |
| `publish` | docker push → GHCR | semver tags only, after e2e passes |

Publishing a new version:

```bash
git tag 1.3.0
git push origin 1.3.0
```

On success the image is pushed to:

```text
ghcr.io/shyrimon2000-tech/chess-auth-service:1.3.0
```

The GHCR package is private. Kubernetes clusters need an `imagePullSecret` with a GitHub PAT (`read:packages` scope) to pull the image.

Tag format is semver without `v` prefix: `1.2.0`, not `v1.2.0`.

---

## Service Ecosystem

chess-auth-service is one of three backend microservices for the chess application:

| Service | Role |
|---|---|
| **chess-auth-service** (this repo) | Issues JWT tokens, manages users |
| chess-room-service | Room lifecycle, matchmaking |
| chess-game-service | WebSocket gameplay, game results, disconnect logic |

Other services validate tokens **locally** using the shared `JWT_SECRET_KEY`. They never call auth-service over HTTP to validate a token.

What other services read from the JWT:

| Claim | Type | Used for |
|---|---|---|
| `sub` | string → cast to `int` | player ID stored in rooms and games |
| `role` | string | admin endpoint guard |
| `username` | string | display name without a DB lookup |

---

## Known Limitations

- There is no admin-promotion endpoint. To grant `admin` role to a user, update `users.role` directly in the database.

---

## Security Notes

Implemented:

- bcrypt password hashing
- JWT access tokens
- JWT access tokens include `sub`, `role`, and `exp` claims
- access token expiration
- access tokens can be validated locally by other backend services using the shared JWT secret
- refresh tokens
- refresh tokens stored as hashes
- refresh token rotation on every use
- server-side logout through refresh token revocation
- protected route dependency
- role-based access control
- admin-only dependency
- account status check with `is_active`
- secrets loaded from environment variables
- `.env` excluded from Git
- `.env.example` provided as a safe template
- non-root Docker container user
- internal Docker network for database access
- database schema changes managed with Alembic migrations
- rate limiting on `/register`, `/login`, `/refresh` via slowapi (5 req/min per IP)
- automated tests for authentication and authorization behavior
- CI pipeline with lint (ruff), type check (mypy), tests, and Docker build
- Docker image published to private GHCR on semver tags (`ghcr.io/shyrimon2000-tech/chess-auth-service:<version>`)

Planned improvements:

- admin user management endpoints
- Redis-backed session storage
- structured logging
- deploy to Kubernetes with ArgoCD
- production-grade secret management

---

## Development Status

The service is complete and production-ready as a microservice.

Implemented endpoints:

```text
GET  /health
POST /auth/register
POST /auth/login
GET  /auth/me
POST /auth/refresh
POST /auth/logout
GET  /auth/admin-only
```

Implemented infrastructure:

```text
Dockerfile
docker-compose.yml (auth-service + MySQL)
docker-compose.e2e.yml (full stack for E2E)
Alembic migrations
pytest unit test suite (24 tests)
Playwright E2E test suite (34 tests, full gameplay lifecycle)
CI/CD pipeline (lint, type-check, unit tests, Docker build, E2E gate, publish to GHCR)
```

Planned improvements:

- Admin user management endpoints (role promotion via API)
- Deploy to Kubernetes with ArgoCD
- Structured logging
- Production-grade secret management
