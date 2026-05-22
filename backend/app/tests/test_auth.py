from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def _client_with_auth(monkeypatch) -> TestClient:
    monkeypatch.setattr(settings, "app_auth_enabled", True)
    monkeypatch.setattr(settings, "app_auth_user", "analyst")
    monkeypatch.setattr(settings, "app_auth_password", "test-password")
    monkeypatch.setattr(settings, "app_auth_session_secret", "test-session-secret")
    return TestClient(app)


def test_login_success(monkeypatch) -> None:
    client = _client_with_auth(monkeypatch)

    response = client.post("/api/auth/login", json={"username": "analyst", "password": "test-password"})

    assert response.status_code == 200
    assert response.json() == {"authenticated": True, "username": "analyst", "role": "demo_analyst"}
    assert "ai_soc_session" in response.cookies


def test_login_failure(monkeypatch) -> None:
    client = _client_with_auth(monkeypatch)

    response = client.post("/api/auth/login", json={"username": "analyst", "password": "wrong"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_me_unauthenticated(monkeypatch) -> None:
    client = _client_with_auth(monkeypatch)

    response = client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json() == {"authenticated": False, "username": None, "role": None}


def test_chat_rejects_unauthenticated_request(monkeypatch) -> None:
    client = _client_with_auth(monkeypatch)

    response = client.post("/api/chat", json={"message": "test"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"


def test_chat_allows_authenticated_request(monkeypatch) -> None:
    client = _client_with_auth(monkeypatch)
    login = client.post("/api/auth/login", json={"username": "analyst", "password": "test-password"})
    assert login.status_code == 200

    response = client.post("/api/chat", json={"message": "test"})

    assert response.status_code == 200
    assert response.json()["note"] == "LangGraph orchestration is not implemented yet."
