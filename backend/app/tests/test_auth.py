from fastapi import HTTPException, Request, Response

from app.auth.routes_auth import LoginRequest, login, me
from app.auth.session import require_auth
from app.schemas.requests import ChatRequest
from app.api.routes_chat import chat
from app.config import settings


def _configure_auth(monkeypatch) -> None:
    monkeypatch.setattr(settings, "app_auth_enabled", True)
    monkeypatch.setattr(settings, "app_auth_user", "analyst")
    monkeypatch.setattr(settings, "app_auth_password", "test-password")
    monkeypatch.setattr(settings, "app_auth_session_secret", "test-session-secret")


def _request(cookie: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if cookie:
        headers.append((b"cookie", f"ai_soc_session={cookie}".encode("ascii")))
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers, "scheme": "http"})


def test_login_success(monkeypatch) -> None:
    _configure_auth(monkeypatch)
    response = Response()

    payload = login(LoginRequest(username="analyst", password="test-password"), _request(), response)

    assert payload.model_dump() == {"authenticated": True, "username": "analyst", "role": "demo_analyst"}
    assert "ai_soc_session" in response.headers.get("set-cookie", "")


def test_login_failure(monkeypatch) -> None:
    _configure_auth(monkeypatch)

    try:
        login(LoginRequest(username="analyst", password="wrong"), _request(), Response())
    except HTTPException as exc:
        assert exc.status_code == 401
        assert exc.detail == "Invalid credentials"
    else:
        raise AssertionError("expected invalid credentials")


def test_me_unauthenticated(monkeypatch) -> None:
    _configure_auth(monkeypatch)

    assert me(None).model_dump() == {"authenticated": False, "username": None, "role": None}


def test_chat_rejects_unauthenticated_request(monkeypatch) -> None:
    _configure_auth(monkeypatch)

    try:
        require_auth(None)
    except HTTPException as exc:
        assert exc.status_code == 401
        assert exc.detail == "Authentication required"
    else:
        raise AssertionError("expected authentication required")


def test_chat_allows_authenticated_request(monkeypatch) -> None:
    _configure_auth(monkeypatch)
    user = require_auth({"username": "analyst", "role": "demo_analyst"})
    monkeypatch.setattr("app.api.routes_chat.route_skill", _fake_route_skill)

    response = chat(ChatRequest(message="test"))

    assert response.note == "Routing only; no SPL generation, MCP execution, RAG retrieval, or synthesis was run."
    assert response.selected_skill == "knowledge_recall"


def _fake_route_skill(query: str, trace_id: str) -> dict:
    return {
        "skill": "knowledge_recall",
        "tool_plan": ["needs_clarification"],
        "confidence": 0.42,
        "comparison": {"match": True, "skill_match": True, "tool_plan_match": True},
    }
