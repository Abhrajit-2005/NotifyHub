from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.user import User

def test_successful_registration(client: TestClient):
    payload = {
        "email": "newuser@example.com",
        "password": "StrongPassword123!"
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert "id" in data
    assert data["is_active"] is True
    assert "password" not in data
    assert "password_hash" not in data

def test_duplicate_registration(client: TestClient):
    payload = {
        "email": "user@example.com",
        "password": "StrongPassword123!"
    }
    # First registration
    res1 = client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    # Duplicate registration attempt
    res2 = client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 400
    assert res2.json()["detail"] == "Email already registered"

def test_successful_login(client: TestClient):
    register_payload = {
        "email": "loginuser@example.com",
        "password": "StrongPassword123!"
    }
    client.post("/api/v1/auth/register", json=register_payload)

    login_payload = {
        "email": "loginuser@example.com",
        "password": "StrongPassword123!"
    }
    response = client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_invalid_login_wrong_password(client: TestClient):
    register_payload = {
        "email": "user@example.com",
        "password": "StrongPassword123!"
    }
    client.post("/api/v1/auth/register", json=register_payload)

    login_payload = {
        "email": "user@example.com",
        "password": "WrongPassword123!"
    }
    response = client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"

def test_invalid_login_nonexistent_email(client: TestClient):
    login_payload = {
        "email": "nonexistent@example.com",
        "password": "StrongPassword123!"
    }
    response = client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"

def test_password_is_not_stored_as_plaintext(client: TestClient, db: Session):
    plain_password = "StrongPassword123!"
    payload = {
        "email": "secureuser@example.com",
        "password": plain_password
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201

    db_user = db.query(User).filter_by(email="secureuser@example.com").first()
    assert db_user is not None
    assert db_user.password_hash != plain_password
    assert plain_password not in db_user.password_hash
    assert db_user.password_hash.startswith("$2b$") or db_user.password_hash.startswith("$2a$")
