# Chess Auth Service

A standalone authentication service for a chess web application.

This service handles user registration, login, JWT-based authentication, password hashing, protected user identity lookup, and MySQL persistence.

The project is designed as a separate backend service that can later be connected to the main chess application or other microservices.

---

## Features

- User registration
- User login
- JWT access token generation
- Protected `/auth/me` endpoint
- Password hashing with bcrypt
- MySQL database persistence
- SQLAlchemy ORM
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
- MySQL
- PyMySQL
- bcrypt
- python-jose
- Pydantic Settings
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
│   └── user_repo.py
├── config.py
├── database.py
├── main.py
├── models.py
└── schemas.py
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
  "is_active": true,
  "created_at": "2026-05-20T02:04:38",
  "last_seen_at": null
}
```

Notes:

- Passwords are never stored as plain text.
- The service stores only bcrypt password hashes.
- Duplicate email or username registration is rejected.

---

### Login

```http
POST /auth/login
```

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
  "access_token": "JWT_TOKEN",
  "token_type": "bearer"
}
```

Notes:

- The password is verified against the stored bcrypt hash.
- On successful login, `last_seen_at` is updated.
- The service returns a signed JWT access token.

---

### Current User

```http
GET /auth/me
```

Required header:

```http
Authorization: Bearer JWT_TOKEN
```

Response:

```json
{
  "id": 1,
  "username": "alex",
  "email": "alex@example.com",
  "is_active": true,
  "created_at": "2026-05-20T02:04:38",
  "last_seen_at": "2026-05-20T02:35:10"
}
```

Notes:

- The endpoint validates the JWT signature.
- The endpoint checks token expiration.
- The user ID is extracted from the JWT `sub` claim.
- The user is loaded from MySQL.
- Disabled users are rejected.

---

## Authentication Flow

```text
Register
↓
Hash password with bcrypt
↓
Store user in MySQL
↓
Login
↓
Verify password
↓
Update last_seen_at
↓
Issue JWT access token
↓
Client sends token in Authorization header
↓
Protected endpoints validate token
↓
Backend identifies current user from JWT subject
```

---

## JWT Design

The access token contains minimal identity data:

```json
{
  "sub": "1",
  "exp": "expiration_time"
}
```

`sub` stores the user ID.

JWT payload is readable by the client, but it cannot be modified without invalidating the signature.

The service uses these environment variables:

```text
JWT_SECRET_KEY
JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES
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
pip install -r requirements.txt
```

Run the service:

```bash
uvicorn app.main:app --reload
```

Open Swagger UI:

```text
http://127.0.0.1:8000/docs
```

---

## Database

The service uses MySQL.

Current `users` table:

```text
id
username
email
hashed_password
is_active
created_at
last_seen_at
```

Field meanings:

| Field | Description |
|---|---|
| `id` | Internal user ID |
| `username` | Unique username |
| `email` | Unique email address |
| `hashed_password` | bcrypt password hash |
| `is_active` | Account enabled/disabled status |
| `created_at` | User creation timestamp |
| `last_seen_at` | Last successful login timestamp |

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

## Security Notes

Implemented:

- bcrypt password hashing
- JWT access tokens
- token expiration
- protected route dependency
- account status check with `is_active`
- secrets loaded from environment variables
- non-root Docker container user
- internal Docker network for database access

Planned improvements:

- Alembic database migrations
- automated tests
- refresh tokens
- logout/session revocation
- Redis-backed token/session storage
- roles and permissions
- rate limiting
- structured logging
- CI/CD pipeline
- production-grade secret management

---

## Development Status

Current status:

```text
Working local and Docker-based auth service skeleton.
```

Implemented endpoints:

```text
GET  /health
POST /auth/register
POST /auth/login
GET  /auth/me
```

Next planned steps:

1. Add automated tests
2. Add Alembic migrations
3. Add refresh token flow
4. Add logout/session revocation
5. Add roles and permissions
6. Connect auth-service to the main chess application