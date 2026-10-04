# NotifyHub - Backend Infrastructure

NotifyHub is a production-style notification infrastructure backend designed to handle user authentication, notification management, routing, and dispatching.

---

## 🚀 Technology Stack

- **Python**: 3.12+
- **Framework**: FastAPI
- **Database**: PostgreSQL
- **Message Broker**: RabbitMQ
- **Caching/Rate Limiting**: Redis
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
│   │   ├── deps.py              # Reusable authentication & service dependencies
│   │   └── v1/
│   │       ├── auth.py          # Authentication router (/api/v1/auth)
│   │       ├── health.py        # Health check router (/api/v1/health)
│   │       └── notifications.py # Notification management router (/api/v1/notifications)
│   ├── core/
│   │   ├── config.py            # Environment configuration settings (BaseSettings)
│   │   ├── database.py          # SQLAlchemy 2.0 engine & session setup
│   │   ├── security.py          # Password hashing (bcrypt) & JWT token utilities
│   │   ├── redis.py             # Redis async connection pool
│   │   └── rate_limiter.py      # Redis rate limiting dependency
│   ├── messaging/
│   │   ├── publisher.py         # RabbitMQ notification publisher & DLQ logic
│   │   └── rabbitmq.py          # RabbitMQ connection setup
│   ├── models/
│   │   ├── enums.py             # NotificationType, NotificationChannel, NotificationStatus enums
│   │   ├── user.py              # SQLAlchemy 2.0 User model (users table)
│   │   └── notification.py      # SQLAlchemy 2.0 Notification model (notifications table)
│   ├── schemas/
│   │   ├── auth.py              # Pydantic v2 Auth request/response validation
│   │   ├── user.py              # Pydantic v2 User schemas
│   │   └── notification.py      # Pydantic v2 Notification schemas & paginated responses
│   ├── services/
│   │   ├── auth_service.py      # Authentication business logic layer
│   │   ├── delivery_service.py  # Notification dispatch & error simulation logic
│   │   └── notification_service.py # Notification business logic layer
│   └── repositories/
│       ├── user_repository.py   # User persistence layer
│       └── notification_repository.py # Notification query & persistence layer
├── worker/
│   ├── __init__.py
│   └── notification_worker.py   # RabbitMQ async consumer and retry handler
├── alembic/
│   ├── env.py                   # Alembic environment runner
│   ├── script.py.mpy            # Alembic revision template
│   └── versions/
│       ├── 0001_create_users_table.py  # Initial migration script
│       └── 0002_create_notifications_table.py # Notification table & enum migration
├── tests/
│   ├── conftest.py              # Pytest fixtures and TestClient database overrides
│   ├── test_health.py           # Health endpoint tests
│   ├── test_auth.py             # Registration, login, & security tests
│   ├── test_notifications.py    # Core notification management endpoint tests
│   ├── test_rate_limiter.py     # Redis rate limiting tests
│   └── test_worker.py           # RabbitMQ background worker & retry logic tests
├── .env                         # Local environment variables
├── .env.example                 # Example environment variables template
├── .gitignore                   # Git ignore settings
├── alembic.ini                  # Alembic configuration file
├── Dockerfile                   # Multi-stage Docker image build specification
├── docker-compose.yml           # Docker Compose setup (PostgreSQL, RabbitMQ, Redis, FastAPI, Worker)
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
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest
RABBITMQ_QUEUE=notifications
RABBITMQ_DLQ=notifications.dlq
MAX_NOTIFICATION_RETRIES=3
REDIS_HOST=redis
REDIS_PORT=6379
```

---

### 2. Running with Docker Compose

Start the entire infrastructure (PostgreSQL, Redis, RabbitMQ, FastAPI Backend, Notification Worker):

```bash
docker compose up --build
```

The container setup automatically:
1. Starts **PostgreSQL** (`notifyhub_db`), **Redis** (`notifyhub_redis`), and **RabbitMQ** (`notifyhub_rabbitmq`) and waits for their respective health checks to pass.
2. Runs Alembic database migrations (`alembic upgrade head`) automatically before launching the API.
3. Starts the **FastAPI Server** (`notifyhub_api`) at `http://localhost:8000`.
4. Starts the **Background Worker** (`notifyhub_worker`) to asynchronously process notification deliveries.

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

To run the full pytest suite (covers authentication, health, notifications, rate limiting, and worker logic):

```bash
# Local virtual environment
.\.venv\Scripts\pytest -v
```

---

## 🔄 Notification Lifecycle

Each notification transitions through a structured status lifecycle:

```text
[ PENDING ] ──► [ PROCESSING ] ──► [ SENT ]
                        │
                        └──► [ FAILED ]
```

1. **`PENDING`**: Created and saved to the database. Initial default state.
2. **`PROCESSING`**: Picked up for dispatching/processing.
3. **`SENT`**: Successfully delivered to recipient channel (`sent_at` timestamp recorded).
4. **`FAILED`**: Delivery failed after retries (`retry_count` incremented).

---

## 🔐 Security & Tenant Isolation

All notification endpoints require a valid JWT Bearer token (`Authorization: Bearer <access_token>`).

- **Recipient Binding**: Clients cannot specify an arbitrary `user_id`. The recipient user ID is derived strictly from the authenticated JWT token payload.
- **Strict Isolation**: A user can never read, modify, or list notifications belonging to another user.
- **404 Masking**: Attempting to fetch or update another user's notification returns a `404 Not Found` response to avoid exposing resource existence.
- **Rate Limiting**: Notification creation is protected by an atomic Redis pipeline rate limiter, restricting users to 5 requests per minute per IP/user combo. Exceeding the limit results in a `429 Too Many Requests` response.

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

### 4. Create Notification
- **`POST /api/v1/notifications`** *(Requires Auth)*
- **Request Body**:
```json
{
  "type": "WELCOME",
  "channel": "IN_APP",
  "title": "Welcome to NotifyHub",
  "content": "Thank you for signing up for our service!",
  "idempotency_key": "unique-req-12345"
}
```
- **Response**: `201 Created`
```json
{
  "id": "a3b89012-e89b-12d3-a456-426614174000",
  "user_id": "f81d4fae-7dec-11d0-a765-00a0c91e6bf6",
  "type": "WELCOME",
  "channel": "IN_APP",
  "title": "Welcome to NotifyHub",
  "content": "Thank you for signing up for our service!",
  "status": "PENDING",
  "retry_count": 0,
  "idempotency_key": "unique-req-12345",
  "is_read": false,
  "created_at": "2026-10-03T11:15:00Z",
  "sent_at": null
}
```

---

### 5. List Authenticated User Notifications (Paginated)
- **`GET /api/v1/notifications`** *(Requires Auth)*
- **Query Parameters**:
  - `page`: integer >= 1 (default `1`)
  - `page_size`: integer 1-100 (default `20`)
- **Response**: `200 OK` (Newest notifications first)
```json
{
  "notifications": [
    {
      "id": "a3b89012-e89b-12d3-a456-426614174000",
      "user_id": "f81d4fae-7dec-11d0-a765-00a0c91e6bf6",
      "type": "WELCOME",
      "channel": "IN_APP",
      "title": "Welcome to NotifyHub",
      "content": "Thank you for signing up for our service!",
      "status": "PENDING",
      "retry_count": 0,
      "idempotency_key": "unique-req-12345",
      "is_read": false,
      "created_at": "2026-10-03T11:15:00Z",
      "sent_at": null
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1
}
```

---

### 6. Get Single Notification
- **`GET /api/v1/notifications/{notification_id}`** *(Requires Auth)*
- **Response**: `200 OK`
```json
{
  "id": "a3b89012-e89b-12d3-a456-426614174000",
  "user_id": "f81d4fae-7dec-11d0-a765-00a0c91e6bf6",
  "type": "WELCOME",
  "channel": "IN_APP",
  "title": "Welcome to NotifyHub",
  "content": "Thank you for signing up for our service!",
  "status": "PENDING",
  "retry_count": 0,
  "idempotency_key": "unique-req-12345",
  "is_read": false,
  "created_at": "2026-10-03T11:15:00Z",
  "sent_at": null
}
```

---

### 7. Mark IN_APP Notification as Read
- **`PATCH /api/v1/notifications/{notification_id}/read`** *(Requires Auth)*
- **Response**: `200 OK`
```json
{
  "id": "a3b89012-e89b-12d3-a456-426614174000",
  "user_id": "f81d4fae-7dec-11d0-a765-00a0c91e6bf6",
  "type": "WELCOME",
  "channel": "IN_APP",
  "title": "Welcome to NotifyHub",
  "content": "Thank you for signing up for our service!",
  "status": "PENDING",
  "retry_count": 0,
  "idempotency_key": "unique-req-12345",
  "is_read": true,
  "created_at": "2026-10-03T11:15:00Z",
  "sent_at": null
}
```
