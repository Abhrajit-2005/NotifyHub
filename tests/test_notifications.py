import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

@pytest.fixture(autouse=True)
def mock_publisher():
    with patch("app.services.notification_service.publisher.publish_notification") as mock:
        mock.return_value = True
        yield mock

def get_auth_headers(client: TestClient, email: str, password: str = "StrongPassword123!"):

    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_1_authenticated_user_can_create_notification(client: TestClient):
    headers = get_auth_headers(client, "user1@example.com")
    payload = {
        "type": "WELCOME",
        "channel": "IN_APP",
        "title": "Welcome to NotifyHub",
        "content": "Thank you for signing up!"
    }
    response = client.post("/api/v1/notifications", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "WELCOME"
    assert data["channel"] == "IN_APP"
    assert data["title"] == "Welcome to NotifyHub"
    assert data["content"] == "Thank you for signing up!"
    assert data["status"] == "PENDING"
    assert data["is_read"] is False

def test_2_unauthenticated_user_cannot_create_notification(client: TestClient):
    payload = {
        "type": "WELCOME",
        "channel": "IN_APP",
        "title": "Welcome to NotifyHub",
        "content": "Thank you for signing up!"
    }
    response = client.post("/api/v1/notifications", json=payload)
    assert response.status_code == 401

def test_3_user_can_retrieve_own_notifications(client: TestClient):
    headers = get_auth_headers(client, "user3@example.com")
    create_res = client.post("/api/v1/notifications", json={
        "type": "GENERAL",
        "channel": "EMAIL",
        "title": "System Update",
        "content": "System will be down for maintenance."
    }, headers=headers)
    notif_id = create_res.json()["id"]

    get_res = client.get(f"/api/v1/notifications/{notif_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == notif_id

    list_res = client.get("/api/v1/notifications", headers=headers)
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 1
    assert any(n["id"] == notif_id for n in list_data["notifications"])

def test_4_user_cannot_retrieve_another_users_notification(client: TestClient):
    headers_user_a = get_auth_headers(client, "usera@example.com")
    headers_user_b = get_auth_headers(client, "userb@example.com")

    create_res = client.post("/api/v1/notifications", json={
        "type": "SECURITY_ALERT",
        "channel": "EMAIL",
        "title": "New Login",
        "content": "New login detected from unknown IP."
    }, headers=headers_user_a)
    notif_id = create_res.json()["id"]

    get_res = client.get(f"/api/v1/notifications/{notif_id}", headers=headers_user_b)
    assert get_res.status_code == 404
    assert get_res.json()["detail"] == "Notification not found"

def test_5_pagination_works(client: TestClient):
    headers = get_auth_headers(client, "user_pagination@example.com")

    for i in range(5):
        client.post("/api/v1/notifications", json={
            "type": "GENERAL",
            "channel": "IN_APP",
            "title": f"Notification {i+1}",
            "content": f"Content {i+1}"
        }, headers=headers)

    res_p1 = client.get("/api/v1/notifications?page=1&page_size=2", headers=headers)
    assert res_p1.status_code == 200
    data_p1 = res_p1.json()
    assert data_p1["page"] == 1
    assert data_p1["page_size"] == 2
    assert data_p1["total"] == 5
    assert len(data_p1["notifications"]) == 2

    res_p2 = client.get("/api/v1/notifications?page=2&page_size=2", headers=headers)
    assert res_p2.status_code == 200
    data_p2 = res_p2.json()
    assert data_p2["page"] == 2
    assert len(data_p2["notifications"]) == 2

    ids_p1 = {n["id"] for n in data_p1["notifications"]}
    ids_p2 = {n["id"] for n in data_p2["notifications"]}
    assert ids_p1.isdisjoint(ids_p2)

def test_6_user_can_mark_own_in_app_notification_as_read(client: TestClient):
    headers = get_auth_headers(client, "user_read@example.com")
    create_res = client.post("/api/v1/notifications", json={
        "type": "ORDER_CONFIRMED",
        "channel": "IN_APP",
        "title": "Order #1234",
        "content": "Your order has been confirmed!"
    }, headers=headers)
    notif_id = create_res.json()["id"]
    assert create_res.json()["is_read"] is False

    read_res = client.patch(f"/api/v1/notifications/{notif_id}/read", headers=headers)
    assert read_res.status_code == 200
    assert read_res.json()["is_read"] is True

def test_7_user_cannot_mark_another_users_notification_as_read(client: TestClient):
    headers_owner = get_auth_headers(client, "owner@example.com")
    headers_attacker = get_auth_headers(client, "attacker@example.com")

    create_res = client.post("/api/v1/notifications", json={
        "type": "PASSWORD_RESET",
        "channel": "IN_APP",
        "title": "Reset Password",
        "content": "Click link to reset password."
    }, headers=headers_owner)
    notif_id = create_res.json()["id"]

    read_res = client.patch(f"/api/v1/notifications/{notif_id}/read", headers=headers_attacker)
    assert read_res.status_code == 404
    assert read_res.json()["detail"] == "Notification not found"

def test_8_notification_defaults_to_pending(client: TestClient):
    headers = get_auth_headers(client, "user_pending@example.com")
    create_res = client.post("/api/v1/notifications", json={
        "type": "GENERAL",
        "channel": "EMAIL",
        "title": "Default Status Test",
        "content": "Testing default status value"
    }, headers=headers)
    assert create_res.status_code == 201
    assert create_res.json()["status"] == "PENDING"
    assert create_res.json()["retry_count"] == 0

def test_9_user_id_taken_from_authentication(client: TestClient):
    headers = get_auth_headers(client, "user_jwt@example.com")
    payload = {
        "type": "WELCOME",
        "channel": "EMAIL",
        "title": "JWT User ID check",
        "content": "Testing user_id binding"
    }
    create_res = client.post("/api/v1/notifications", json=payload, headers=headers)
    assert create_res.status_code == 201
    data = create_res.json()
    assert "user_id" in data
    assert data["user_id"] is not None
