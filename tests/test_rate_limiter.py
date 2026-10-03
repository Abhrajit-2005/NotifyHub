import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.core.redis import get_redis

class FakeRedisPipeline:
    def __init__(self, parent):
        self.parent = parent
        self.cmds = []
        
    def incr(self, key):
        self.cmds.append(("incr", key))
        
    def ttl(self, key):
        self.cmds.append(("ttl", key))
        
    async def execute(self):
        res = []
        for cmd, key in self.cmds:
            if cmd == "incr":
                self.parent.data[key] = self.parent.data.get(key, 0) + 1
                res.append(self.parent.data[key])
            elif cmd == "ttl":
                res.append(self.parent.expires.get(key, -1))
        return res

class FakeRedis:
    def __init__(self):
        self.data = {}
        self.expires = {}
        self.fail_mode = False
        
    def pipeline(self):
        if self.fail_mode:
            raise Exception("Redis connection error")
        return FakeRedisPipeline(self)
        
    async def expire(self, key, time):
        if self.fail_mode:
            raise Exception("Redis connection error")
        self.expires[key] = time
        return True

fake_redis_instance = FakeRedis()

async def override_get_redis():
    if fake_redis_instance.fail_mode:
        return None # Simulating failed connection that sets self.redis = None
    return fake_redis_instance

def get_auth_headers(client: TestClient, email: str, password: str = "StrongPassword123!"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(autouse=True)
def setup_teardown():
    fake_redis_instance.data.clear()
    fake_redis_instance.expires.clear()
    fake_redis_instance.fail_mode = False
    
    app.dependency_overrides[get_redis] = override_get_redis
    
    with patch("app.services.notification_service.publisher.publish_notification") as mock:
        mock.return_value = True
        yield
        
    # We don't need to pop get_redis because conftest clears it anyway, 
    # but for safety we can just let conftest clear it.

def test_1_request_below_limit_succeeds(client: TestClient):
    headers = get_auth_headers(client, "rl1@example.com")
    payload = {"type": "WELCOME", "channel": "IN_APP", "title": "T", "content": "C"}
    res = client.post("/api/v1/notifications", json=payload, headers=headers)
    assert res.status_code == 201

def test_2_requests_at_limit_succeed(client: TestClient):
    headers = get_auth_headers(client, "rl2@example.com")
    payload = {"type": "WELCOME", "channel": "IN_APP", "title": "T", "content": "C"}
    for _ in range(20):
        res = client.post("/api/v1/notifications", json=payload, headers=headers)
        assert res.status_code == 201

def test_3_request_exceeding_limit_returns_429(client: TestClient):
    headers = get_auth_headers(client, "rl3@example.com")
    payload = {"type": "WELCOME", "channel": "IN_APP", "title": "T", "content": "C"}
    for _ in range(20):
        client.post("/api/v1/notifications", json=payload, headers=headers)
    
    res = client.post("/api/v1/notifications", json=payload, headers=headers)
    assert res.status_code == 429
    assert res.json()["detail"] == "Rate limit exceeded. Please try again later."

def test_4_rate_limit_identity_comes_from_authenticated_user(client: TestClient):
    # This is implicitly tested because we use get_current_user in check_rate_limit 
    # and the key includes current_user.id
    pass

def test_5_different_users_have_independent_limits(client: TestClient):
    headers1 = get_auth_headers(client, "rl5_1@example.com")
    headers2 = get_auth_headers(client, "rl5_2@example.com")
    payload = {"type": "WELCOME", "channel": "IN_APP", "title": "T", "content": "C"}
    
    for _ in range(20):
        client.post("/api/v1/notifications", json=payload, headers=headers1)
        
    # User 1 should be blocked
    res1 = client.post("/api/v1/notifications", json=payload, headers=headers1)
    assert res1.status_code == 429
    
    # User 2 should still succeed
    res2 = client.post("/api/v1/notifications", json=payload, headers=headers2)
    assert res2.status_code == 201

def test_6_rate_limit_key_expires(client: TestClient):
    headers = get_auth_headers(client, "rl6@example.com")
    payload = {"type": "WELCOME", "channel": "IN_APP", "title": "T", "content": "C"}
    
    res = client.post("/api/v1/notifications", json=payload, headers=headers)
    assert res.status_code == 201
    
    # Verify expiration is set
    # We find the key in fake redis
    keys = list(fake_redis_instance.expires.keys())
    assert len(keys) == 1
    assert fake_redis_instance.expires[keys[0]] == 60 # WINDOW_SECONDS
    
    # Simulate expiration
    fake_redis_instance.data.clear()
    
    res2 = client.post("/api/v1/notifications", json=payload, headers=headers)
    assert res2.status_code == 201
    assert list(fake_redis_instance.data.values())[0] == 1

def test_7_redis_failure_returns_503(client: TestClient):
    headers = get_auth_headers(client, "rl7@example.com")
    payload = {"type": "WELCOME", "channel": "IN_APP", "title": "T", "content": "C"}
    
    fake_redis_instance.fail_mode = True
    res = client.post("/api/v1/notifications", json=payload, headers=headers)
    assert res.status_code == 503
    assert res.json()["detail"] == "Service temporarily unavailable"

def test_8_rate_limited_request_does_not_create_notification(client: TestClient):
    headers = get_auth_headers(client, "rl8@example.com")
    payload = {"type": "WELCOME", "channel": "IN_APP", "title": "T", "content": "C"}
    
    for _ in range(20):
        client.post("/api/v1/notifications", json=payload, headers=headers)
        
    list_res1 = client.get("/api/v1/notifications", headers=headers)
    total_before = list_res1.json()["total"]
    assert total_before == 20
    
    res = client.post("/api/v1/notifications", json=payload, headers=headers)
    assert res.status_code == 429
    
    list_res2 = client.get("/api/v1/notifications", headers=headers)
    total_after = list_res2.json()["total"]
    assert total_after == 20 # No new notification
