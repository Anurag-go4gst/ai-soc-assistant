import json

import pytest
from fastapi import HTTPException, Request, Response

from app.auth.routes_auth import LoginRequest, login, me
from app.auth.session import require_auth
from app.auth.user_registry import reload_users_for_tests
from app.schemas.requests import ChatRequest
from app.api.routes_chat import chat
from app.config import settings


@pytest.fixture(autouse=True)
def _reset_user_registry():
    """Auth is registry-backed; drop the cached document after each test so a
    seeded temp registry never leaks into other suites."""
    yield
    reload_users_for_tests()


def _configure_auth(monkeypatch, tmp_path) -> None:
    # ``authenticate`` reads the user registry, not env creds (env only seeds a
    # bootstrap registry when none exists). Point the registry at a temp file
    # holding the credentials this suite logs in with.
    users_file = tmp_path / "users.json"
    users_file.write_text(
        json.dumps(
            {
                "users": [
                    {
                        "username": "analyst",
                        "password": "test-password",
                        "role": "demo_analyst",
                        "debug_access": False,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "app_auth_users_path", str(users_file))
    reload_users_for_tests()
    monkeypatch.setattr(settings, "app_auth_enabled", True)
    monkeypatch.setattr(settings, "app_auth_user", "analyst")
    monkeypatch.setattr(settings, "app_auth_password", "test-password")
    monkeypatch.setattr(settings, "app_auth_session_secret", "test-session-secret")


def _request(cookie: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if cookie:
        headers.append((b"cookie", f"ai_soc_session={cookie}".encode("ascii")))
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers, "scheme": "http"})


def test_login_success(monkeypatch, tmp_path) -> None:
    _configure_auth(monkeypatch, tmp_path)
    response = Response()

    payload = login(LoginRequest(username="analyst", password="test-password"), _request(), response)

    assert payload.model_dump() == {
        "authenticated": True,
        "username": "analyst",
        "role": "demo_analyst",
        "debug_access": False,
    }
    assert "ai_soc_session" in response.headers.get("set-cookie", "")


def test_login_failure(monkeypatch, tmp_path) -> None:
    _configure_auth(monkeypatch, tmp_path)

    try:
        login(LoginRequest(username="analyst", password="wrong"), _request(), Response())
    except HTTPException as exc:
        assert exc.status_code == 401
        assert exc.detail == "Invalid credentials"
    else:
        raise AssertionError("expected invalid credentials")


def test_me_unauthenticated(monkeypatch, tmp_path) -> None:
    _configure_auth(monkeypatch, tmp_path)

    assert me(None).model_dump() == {
        "authenticated": False,
        "username": None,
        "role": None,
        "debug_access": None,
    }


def test_chat_rejects_unauthenticated_request(monkeypatch, tmp_path) -> None:
    _configure_auth(monkeypatch, tmp_path)

    try:
        require_auth(None)
    except HTTPException as exc:
        assert exc.status_code == 401
        assert exc.detail == "Authentication required"
    else:
        raise AssertionError("expected authentication required")


def test_chat_allows_authenticated_request(monkeypatch, tmp_path) -> None:
    _configure_auth(monkeypatch, tmp_path)
    user = require_auth({"username": "analyst", "role": "demo_analyst"})
    monkeypatch.setattr("app.api.routes_chat.route_skill", _fake_route_skill)
    monkeypatch.setattr("app.api.routes_chat.plan_workflow", _fake_plan_workflow)
    monkeypatch.setattr("app.api.routes_chat.get_telemetry_connector", lambda: _FakeTelemetry())

    response = chat(ChatRequest(message="test"))

    assert response.note == (
        "Routing and workflow planning only; SPL is not required at this stage. "
        "No MCP execution, RAG retrieval, or synthesis was run."
    )
    assert response.selected_skill == "knowledge_recall"


def _fake_route_skill(query: str, trace_id: str, **kwargs) -> dict:
    return {
        "skill": "knowledge_recall",
        "tool_plan": ["needs_clarification"],
        "confidence": 0.42,
        "comparison": {"match": True, "skill_match": True, "tool_plan_match": True},
    }


def _fake_plan_workflow(selected_skill: str, tool_plan: list[str], query: str, trace_id: str) -> dict:
    return {
        "trace_id": trace_id,
        "skill": selected_skill,
        "tool_plan": tool_plan,
        "status": "not_started",
        "execution_enabled": False,
        "steps": [
            {
                "order": 1,
                "name": "test workflow plan",
                "status": "not_started",
                "required_connectors": [],
                "safety_gates": ["no_execution"],
            }
        ],
        "required_connectors": [],
        "safety_gates": ["no_execution"],
        "message": "Workflow plan created. No SPL/MCP/RAG execution has started.",
    }


class _FakeTelemetry:
    def record_step(self, trace_id: str, step_name: str, status: str, **fields: object) -> None:
        return None

    def start_trace(self, trace_id: str | None = None, **fields: object):
        from app.connectors.telemetry.base import TraceHandle

        return TraceHandle(trace_id=trace_id or "fake")

    def end_trace(self, trace_id: str, status: str = "completed", **fields: object) -> None:
        return None

    def merge_run_metadata(self, trace_id: str, metadata: dict) -> None:
        return None

    def record_llm_call(self, trace_id: str, **fields: object) -> None:
        return None

    def record_rag_retrieval(self, trace_id: str, **fields: object) -> None:
        return None
