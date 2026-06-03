# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Collaboration Style

The user is learning backend development. Apply these principles in every session:

- When introducing a new concept, pattern, or tool — briefly flag it so it registers ("здесь мы используем X потому что..."). Don't over-explain, one sentence is enough.
- Proactively offer to go deeper on anything non-obvious ("хочешь объясню почему именно так?").
- Before applying any change, explain what it does and where it takes effect — let the user decide.
- Don't make decisions silently. State what you're about to do and why, even for small things.
- The user will ask to go deeper when they want — don't over-explain by default.

## What This Service Is

chess-auth-service is the authentication microservice for a real-time chess web application built with a microservice architecture.

This service is responsible for:

- User registration and login
- JWT access token issuance (short-lived, includes `sub` and `role` claims)
- Refresh token issuance, validation, and revocation
- Server-side logout
- Protected identity endpoint (`/auth/me`)
- Role-based access control (`user` / `admin`)
- Password hashing

This service is NOT responsible for:

- Room creation or matchmaking
- WebSocket gameplay or game state
- Game results or disconnect handling
- Spectator tracking
- Calling other services over HTTP to authorize users — other services validate tokens locally using the shared secret

## Service Ecosystem

| Service | Status | Role |
|---|---|---|
| chess-auth-service | **This repo** | Issues JWT tokens, manages users |
| chess-room-service | Implemented | Room lifecycle and matchmaking |
| chess-game-service | Planned | WebSocket gameplay, game results, disconnect logic |
| presence-service | Optional future split | Online user tracking |

The services are designed as separate Docker Compose projects today and will later be deployed to Kubernetes.

Other services validate tokens **locally** using the shared `JWT_SECRET_KEY`. They never call auth-service over HTTP to validate a token.

## Integration Contract with chess-room-service

chess-room-service validates tokens issued by this service without calling auth-service over HTTP. It decodes the JWT locally and constructs a minimal `CurrentUser(id: int, role: str)` object — it has no `users` table and does not know about `email`, `username`, or `is_active`.

**What room-service reads from the JWT:**

| Claim | Type | Used for |
|---|---|---|
| `sub` | string → cast to `int` | `CurrentUser.id`, stored as `white_player_id` / `black_player_id` in `rooms` |
| `role` | string | `CurrentUser.role`, checked against `"admin"` for admin endpoints |

**Breaking the contract:**
- If `sub` is missing or not castable to `int` → room-service returns 401
- If `role` is missing → room-service returns 401
- If `JWT_SECRET_KEY` or `JWT_ALGORITHM` differs between services → room-service returns 401 on every request

**Redis event bus (room-service → future game-service):**

When room-service transitions a room to `active` status, it publishes to the Redis channel `room_events`:

```json
{
  "event": "room_activated",
  "room_id": 1,
  "white_player_id": 42,
  "black_player_id": 7
}
```

The `white_player_id` and `black_player_id` values are the `sub` integers from auth-service JWTs. Future game-service will subscribe to this channel to start a game session.

## Architecture

This service follows a strict 3-layer pattern. Never skip or bypass layers.

```
routers → services → repositories → models
```

### Layer Responsibilities

**`app/routers/`** — HTTP layer only
- Parse request bodies and inject dependencies
- Call service functions
- Convert `ValueError` from services into `HTTPException`
- No business logic, no direct DB access

**`app/services/`** — Business logic
- Enforce registration rules (duplicate email/username)
- Own password hashing and verification
- Own JWT creation and decoding
- Own refresh token generation, hashing, validation, and revocation
- Raise `ValueError` with a message when a rule is violated

**`app/repositories/`** — Database queries only
- Translate service intent into SQLAlchemy queries
- No business rules, no HTTP concerns

**`app/models.py`** — SQLAlchemy ORM models (`User`, `RefreshToken`)

**`app/schemas.py`** — Pydantic schemas for request/response serialization

**`app/config.py`** — `pydantic-settings` singleton (`settings`) loaded from `.env`

**`app/database.py`** — Engine, session factory, `Base`, and `get_db` FastAPI dependency

## Database Model

### `users`

| Field | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `username` | String(50) | Unique |
| `email` | String(255) | Unique |
| `hashed_password` | String(255) | bcrypt hash — raw password is never stored |
| `role` | String(20) | `user` or `admin`, default `user` |
| `is_active` | Boolean | Account enabled/disabled |
| `created_at` | DateTime | UTC, server default |
| `last_seen_at` | DateTime nullable | Updated on each successful login |

### `refresh_tokens`

| Field | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `user_id` | Integer FK → users.id | |
| `token_hash` | String(255) | SHA-256 hash of the raw token |
| `created_at` | DateTime | UTC, server default |
| `expires_at` | DateTime | Set at creation |
| `revoked_at` | DateTime nullable | Set on logout |

Raw refresh tokens are never stored. Only the SHA-256 hash is persisted. The plain token is returned to the client once at login.

## Token Lifecycle

### Access token

```
Login
↓
Issue JWT: { sub: user_id, role: user.role, exp }
↓
Client sends Authorization: Bearer <token> to any service
↓
Service validates signature locally with shared JWT_SECRET_KEY
↓
Service extracts sub and role from token — no HTTP call to auth-service
```

Access tokens are short-lived (default 30 min). Role changes take effect when the next token is issued.

### Refresh token

```
Login → generate raw token → SHA-256 hash → store hash in DB → return raw token to client
                                                                         ↓
                                             POST /auth/refresh with raw token
                                                                         ↓
                                             hash → look up → validate → revoke old token → generate new token → store new hash
                                                                         ↓
                                             return new access token + new refresh token (old token is now dead)
                                                                         ↓
                                             POST /auth/logout with raw token → set revoked_at
```

Each call to `/auth/refresh` rotates the refresh token — the client must use the new token on the next refresh. Using the old token after rotation returns 401 "Refresh token has been revoked".

## Key Conventions

### Error Flow

Services raise `ValueError` with a plain message. Routers catch it and raise `HTTPException`.

```python
# service
raise ValueError("Email already registered")

# router
except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e))
```

### Auth Dependencies

- `get_current_user` — validates the JWT, loads the user from DB, rejects disabled accounts
- `get_current_admin_user` — wraps `get_current_user`, rejects if `role != "admin"`

Never trust `user_id` or `role` from request body or query params. Always read them from the decoded JWT via `get_current_user`.

### JWT Payload

```json
{ "sub": "1", "role": "user", "exp": 1234567890 }
```

`sub` is the user ID as a string. `role` is the user's current role at time of issuance.

## CI/CD Pipeline

Pipeline runs on every push to `main`/`dev` and on PRs:

```
lint ──┐
       ├──▶ test ──▶ docker-build ──▶ publish (semver tags only)
type ──┘
```

| Job | Tool | Runs on |
|---|---|---|
| `lint` | ruff | every push / PR |
| `type-check` | mypy | every push / PR |
| `test` | pytest | every push / PR |
| `docker-build` | docker build | every push / PR |
| `publish` | docker push → GHCR | semver tags only |

**Publishing a new version:**
```bash
git tag 1.3.0
git push origin 1.3.0
```

This triggers the full pipeline. On success, the image is pushed to:
```
ghcr.io/shyrimon2000-tech/chess-auth-service:1.3.0
```

The GHCR package is **private**. Kubernetes clusters need an `imagePullSecret` with a GitHub PAT (`read:packages` scope) to pull the image.

Tag format is semver without `v` prefix: `1.2.0`, not `v1.2.0`.

## Commands

**Run locally** (requires a reachable MySQL instance and a valid `.env`):
```bash
uvicorn app.main:app --reload
```

**Run with Docker Compose:**
```bash
docker compose up --build
```

Service is available at `http://localhost:8000`. The MySQL container is internal and does not expose port 3306 to the host.

**Apply Alembic migrations** (run inside the container when using Docker Compose):
```bash
docker compose exec auth-service alembic upgrade head
docker compose exec auth-service alembic revision --autogenerate -m "description"
docker compose exec auth-service alembic current
```

The app does not run migrations on startup. Migrations are a manual step.

**Run tests** (no database required — uses SQLite in-memory):
```bash
pytest -v
```

**Run a single test:**
```bash
pytest tests/test_auth.py::test_register_user_successfully -v
```

## Environment Setup

Copy `.env.example` to `.env` and fill in the values before running.

```bash
cp .env.example .env
```

| Variable | Notes |
|---|---|
| `DATABASE_URL` | Must use `auth-db` as hostname when running via Docker Compose |
| `JWT_SECRET_KEY` | Must match the value used in all other services that validate tokens |
| `JWT_ALGORITHM` | Must match across services — default `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Default 30 |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Default 7 |
| `MYSQL_*` | Used by the Docker Compose MySQL container |

`JWT_SECRET_KEY` and `JWT_ALGORITHM` are shared across services. If they differ, token validation in other services will fail with 401.

## Testing Notes

Tests use an in-memory SQLite database (via `StaticPool`) with the real `get_db` dependency overridden. No MySQL is needed to run tests. Each test calls `reset_database()` to drop and recreate all tables, so tests are fully isolated.

CI sets `DATABASE_URL=sqlite:///./test.db` and `JWT_SECRET_KEY=test-secret-key-for-ci-only` as env vars to satisfy `pydantic-settings` on import, even though the test file creates its own engine.

To test an admin flow, directly update the `User.role` via `TestingSessionLocal` before login — there is no admin-promotion endpoint yet.

After calling `/auth/refresh`, the returned `refresh_token` will be different from the one sent. Tests must not assert `data["refresh_token"] == original_token`.

## What To Avoid

**Layer violations**
- Do not put SQL queries in routers or services
- Do not put business logic in repositories
- Do not access the database from anywhere except the repository layer

**Auth**
- Do not trust `user_id` or `role` from request body or query params
- Do not call other services over HTTP to validate tokens — validate locally with the shared secret

**Token handling**
- Do not store raw refresh tokens — always store only the SHA-256 hash
- Do not return the same refresh token from `/auth/refresh` — rotation must always issue a new one
- Do not embed sensitive data in the JWT payload — only `sub`, `role`, `exp`

**Infrastructure**
- Do not run `alembic upgrade head` automatically on app startup
- Do not expose the MySQL container port to the host unnecessarily
- Do not use `Base.metadata.create_all()` in production — schema changes go through Alembic
