# NotifyHub - Phase 1 Backend Infrastructure

NotifyHub is a production-style notification infrastructure backend designed to handle authentication, notification routing, and dispatching. Phase 1 provides the foundational backend setup with user authentication, security features, database migrations, and containerization.

---

## 🚀 Technology Stack

- **Python**: 3.12+
- **Framework**: FastAPI
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy 2.x
- **Migrations**: Alembic
- **Validation**: Pydantic v2
- **Authentication**: JWT (JSON Web Tokens) with PyJWT
- **Security**: bcrypt password hashing
- **Containerization**: Docker & Docker Compose
- **Testing**: pytest & HTTPX

---

## 🏗️ Architecture & Project Structure

The project follows a clean layered architecture separating HTTP routing, business logic, data persistence, and database models.

```text
NotifyHub/
├── app/
│   ├── main.py                  # FastAPI application entry point & router mounting
│   ├── api/
│   │   ├── deps.py              # Reusable authentication & database dependencies
│   │   └── v1/
│   │       ├── auth.py          # Authentication router (/api/v1/auth)
│   │       └── health.py        # Health check router (/api/v1/health)
│   ├── core/
│   │   ├── config.py            # Environment configuration settings (BaseSettings)
│   │   ├── database.py          # SQLAlchemy 2.0 engine & session setup
│   │   └── security.py          # Password hashing (bcrypt) & JWT token utilities
│   ├── models/
│   │   └── user.py              # SQLAlchemy 2.0 User model (users table)
│   ├── schemas/
│   │   ├── auth.py              # Pydantic v2 Auth request/response validation
│   │   └── user.py              # Pydantic v2 User schemas
│   ├── services/
│   │   └── auth_service.py      # Authentication business logic layer
│   └── repositories/
│       └── user_repository.py   # Database query & persistence layer
├── alembic/
│   ├── env.py                   # Alembic environment runner
│   ├── script.py.mpy            # Alembic revision template
│   └── versions/
│       └── 0001_create_users_table.py  # Initial migration script
├── tests/
│   ├── conftest.py              # Pytest fixtures and TestClient database overrides
│   ├── test_health.py           # Health endpoint tests
│   └── test_auth.py             # Registration, login, & security tests
├── .env                         # Local environment variables
├── .env.example                 # Example environment variables template
├── .gitignore                   # Git ignore settings
├── alembic.ini                  # Alembic configuration file
├── Dockerfile                   # Multi-stage Docker image build specification
├── docker-compose.yml           # Docker Compose setup (PostgreSQL & FastAPI)
├── requirements.txt             # Python dependencies
└── README.md                    # Project documentation
```

---

## 🛠️ Getting Started

### 1. Environment Setup

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Default environment variables in `.env`:
```env
POSTGRES_SERVER=db
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=notifyhub
JWT_SECRET_KEY=your_secure_jwt_secret_key_change_in_production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

---

### 2. Running with Docker Compose

Start the PostgreSQL database and FastAPI backend services:

```bash
docker compose up --build
```

The container setup automatically:
1. Starts PostgreSQL database container (`notifyhub_db`) and waits for health check pass (`pg_isready`).
2. Runs Alembic database migrations (`alembic upgrade head`).
3. Starts the FastAPI server (`notifyhub_api`) at `http://localhost:8000`.

---

### 3. Running Database Migrations

To run migrations manually:

```bash
# Inside Docker container
docker compose exec api alembic upgrade head

# Local environment
alembic upgrade head
```

To create a new migration revision after modifying models:

```bash
alembic revision --autogenerate -m "describe_migration"
```

---

### 4. Running Tests

To run the pytest suite:

```bash
# Local environment with virtualenv
pytest

# Verbose test output
pytest -v
```

---

## 📡 API Endpoints

### 1. Health Check
- **`GET /health`** or **`GET /api/v1/health`**
- **Response**: `200 OK`
```json
{
  "status": "ok"
}
```

---

### 2. User Registration
- **`POST /api/v1/auth/register`**
- **Request Body**:
```json
{
  "email": "user@example.com",
  "password": "StrongPassword123!"
}
```
- **Response**: `201 Created`
```json
{
  "id": "f81d4fae-7dec-11d0-a765-00a0c91e6bf6",
  "email": "user@example.com",
  "is_active": true,
  "created_at": "2026-10-02T14:00:00Z",
  "updated_at": "2026-10-02T14:00:00Z"
}
```

---

### 3. User Login
- **`POST /api/v1/auth/login`**
- **Request Body**:
```json
{
  "email": "user@example.com",
  "password": "StrongPassword123!"
}
```
- **Response**: `200 OK`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

---

## 🔐 Reusable Authentication Dependency

The `get_current_user` dependency in `app/api/deps.py` provides simple, reusable authentication for future protected routes:

```python
from fastapi import Depends
from app.api.deps import get_current_user
from app.models.user import User

@router.get("/me")
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user
```
