"""P0-0 / P0-A — fail-closed error envelopes for /chat.

Two layers are exercised:

* The route-level catch in ``app.api.routes_chat.chat`` logs the failure with the
  correlatable ``trace_id`` and re-raises — a real defect is never masked as a 200
  stub (which would inflate the reliability denominator). A genuine producer/LLM
  failure instead degrades to a complete deterministic 200 answer inside the
  pipeline, not here.
* The app-level ``Exception`` handler in ``app.main`` — any unhandled exception
  (escaping the route body or a FastAPI dependency) returns an HTTP 500 JSON
  envelope with a ``trace_id`` and ``error_code`` and never leaks the exception
  message or a stack frame.

The live-LLM guard conftest still applies; nothing here reaches a real model.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth.session import require_auth
from app.main import app


_SECRET_MARKER = "TOP_SECRET_STACK_DETAIL_should_never_surface"


def _fake_user() -> dict[str, str]:
    return {"username": "analyst", "role": "demo_analyst"}


@pytest.fixture()
def client() -> TestClient:
    # raise_server_exceptions=False lets the registered app-level handler produce
    # the JSON 500 response instead of the TestClient re-raising the exception.
    app.dependency_overrides[require_auth] = _fake_user
    test_client = TestClient(app, raise_server_exceptions=False)
    try:
        yield test_client
    finally:
        app.dependency_overrides.pop(require_auth, None)


def test_route_level_pipeline_failure_returns_sanitized_500(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(*args: object, **kwargs: object):
        raise RuntimeError(_SECRET_MARKER)

    # Patch the pipeline entry the route calls so the failure happens inside the
    # route body. The route logs with a correlatable trace_id and re-raises; the
    # app-level handler must return an honest sanitized 500 (never a masked 200).
    monkeypatch.setattr("app.api.routes_chat.build_live_chat_response", _boom)
    monkeypatch.setattr(
        "app.config.settings.ai_soc_live_chat_ec_parity_enabled", False, raising=False
    )
    monkeypatch.setattr(
        "app.config.settings.langgraph_orchestration_enabled", False, raising=False
    )

    response = client.post("/chat", json={"message": "summarize the latest alert"})

    assert response.status_code == 500
    body = response.json()
    assert body["trace_id"]
    assert body["error_code"] == "internal_error"
    # No leakage of the raised exception's message text or a stack frame.
    assert _SECRET_MARKER not in response.text
    assert "Traceback" not in response.text


def test_app_level_handler_returns_500_with_trace_id(
    client: TestClient,
) -> None:
    def _raise_in_dependency() -> dict[str, str]:
        raise RuntimeError(_SECRET_MARKER)

    # An exception inside the dependency escapes the route body entirely and must
    # be caught by the app-level backstop handler.
    app.dependency_overrides[require_auth] = _raise_in_dependency
    try:
        response = client.post("/chat", json={"message": "summarize the latest alert"})
    finally:
        app.dependency_overrides[require_auth] = _fake_user

    assert response.status_code == 500
    body = response.json()
    assert body["trace_id"]
    assert body["error_code"] == "internal_error"
    assert body["message"] == "An internal error occurred."
    # Sanitized: never the exception message or a traceback frame.
    assert _SECRET_MARKER not in response.text
    assert "Traceback" not in response.text
    assert ".py" not in body.get("message", "")


def test_error_envelope_trace_matches_protected_diagnostic(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    class _Telemetry:
        def start_trace(self, trace_id: str, **_fields: object) -> None:
            captured["start_trace_id"] = trace_id

        def record_step(
            self, trace_id: str, step_name: str, status: str, **fields: object
        ) -> None:
            captured.update(
                trace_id=trace_id,
                step_name=step_name,
                status=status,
                exception_type=fields.get("exception_type"),
            )

        def end_trace(self, trace_id: str, **_fields: object) -> None:
            captured["end_trace_id"] = trace_id

    def _boom(*_args: object, **_kwargs: object):
        raise RuntimeError(_SECRET_MARKER)

    monkeypatch.setattr("app.main.get_telemetry_connector", lambda: _Telemetry())
    monkeypatch.setattr("app.api.routes_chat.build_live_chat_response", _boom)
    monkeypatch.setattr(
        "app.config.settings.ai_soc_live_chat_ec_parity_enabled", False, raising=False
    )
    monkeypatch.setattr(
        "app.config.settings.langgraph_orchestration_enabled", False, raising=False
    )

    response = client.post("/chat", json={"message": "summarize the latest alert"})

    assert response.status_code == 500
    assert response.json()["trace_id"] == captured["trace_id"]
    assert captured["start_trace_id"] == captured["trace_id"] == captured["end_trace_id"]
    assert captured["step_name"] == "unhandled_exception"
    assert captured["exception_type"] == "RuntimeError"
