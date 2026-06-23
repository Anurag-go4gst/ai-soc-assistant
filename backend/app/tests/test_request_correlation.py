"""Client-known trace correlation: X-Request-ID -> trace_id -> X-Trace-ID.

The client mints a request id and sends it as ``X-Request-ID``; the server adopts
it (when a valid UUID) as the turn trace id, echoes it as ``X-Trace-ID`` on every
response (success and error), and persists an admission record so the trace is
queryable even if the client never receives the response (transport timeout).
"""

from __future__ import annotations

from uuid import UUID, uuid1, uuid4

import pytest
from fastapi.testclient import TestClient

from app.auth.session import require_auth
from app.connectors.telemetry.log_context import coerce_request_id
from app.main import app

_SECRET_MARKER = "TOP_SECRET_STACK_DETAIL_should_never_surface"


def _fake_user() -> dict[str, str]:
    return {"username": "analyst", "role": "soc_lead"}


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("app.config.settings.ai_soc_live_chat_ec_parity_enabled", False, raising=False)
    monkeypatch.setattr("app.config.settings.langgraph_orchestration_enabled", False, raising=False)
    monkeypatch.setattr("app.config.settings.telemetry_mode", "none", raising=False)
    monkeypatch.setattr("app.config.settings.ai_soc_telemetry_sink", "none", raising=False)
    monkeypatch.setattr("app.config.settings.ai_soc_llm_enabled", False, raising=False)
    monkeypatch.setattr("app.config.settings.ai_soc_llm_intent_advisor_enabled", False, raising=False)
    monkeypatch.setattr("app.config.settings.ai_soc_llm_live_synthesis_enabled", False, raising=False)
    monkeypatch.setattr("app.config.settings.ai_soc_llm_final_synthesis_enabled", False, raising=False)
    monkeypatch.setattr("app.config.settings.ai_soc_llm_spl_fallback_enabled", False, raising=False)
    app.dependency_overrides[require_auth] = _fake_user
    test_client = TestClient(app, raise_server_exceptions=False)
    try:
        yield test_client
    finally:
        app.dependency_overrides.pop(require_auth, None)


# ---- coerce_request_id unit ----------------------------------------------------


def test_coerce_accepts_valid_uuid() -> None:
    rid = str(uuid4())
    assert coerce_request_id(rid) == rid
    assert coerce_request_id(f"  {rid}  ") == rid


@pytest.mark.parametrize("bad", [None, "", "not-a-uuid", "../etc/passwd", "1; DROP TABLE"])
def test_coerce_rejects_invalid_and_mints_uuid(bad: str | None) -> None:
    out = coerce_request_id(bad)
    # Always a syntactically valid UUID — never the raw injected value.
    assert UUID(out)
    assert out != bad


@pytest.mark.parametrize("unsuitable", [str(UUID(int=0)), str(uuid1())])
def test_coerce_rejects_non_v4_uuid(unsuitable: str) -> None:
    out = coerce_request_id(unsuitable)
    assert UUID(out).version == 4
    assert out != unsuitable


# ---- success path --------------------------------------------------------------


def test_success_echoes_client_request_id(client: TestClient) -> None:
    rid = str(uuid4())
    response = client.post(
        "/chat",
        json={"message": "summarize the latest alert"},
        headers={"X-Request-ID": rid},
    )
    assert response.status_code == 200
    # Server adopted the client id and echoed it back.
    assert response.headers.get("X-Trace-ID") == rid
    # And the body's trace id is the same adopted id (pipeline adopted the contextvar).
    assert response.json().get("trace_id") == rid


def test_invalid_request_id_is_replaced_with_server_uuid(client: TestClient) -> None:
    response = client.post(
        "/chat",
        json={"message": "summarize the latest alert"},
        headers={"X-Request-ID": "not-a-uuid"},
    )
    assert response.status_code == 200
    echoed = response.headers.get("X-Trace-ID")
    assert echoed and UUID(echoed)  # valid server-minted uuid
    assert echoed != "not-a-uuid"


# ---- error path ----------------------------------------------------------------


def test_error_envelope_carries_client_request_id(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(*_args: object, **_kwargs: object):
        raise RuntimeError(_SECRET_MARKER)

    monkeypatch.setattr("app.api.routes_chat.build_live_chat_response", _boom)
    rid = str(uuid4())
    response = client.post(
        "/chat",
        json={"message": "summarize the latest alert"},
        headers={"X-Request-ID": rid},
    )
    assert response.status_code == 500
    # The error response is correlatable to the client-known id on both the header
    # and the JSON envelope, with no leaked exception text.
    assert response.headers.get("X-Trace-ID") == rid
    assert response.json().get("trace_id") == rid
    assert _SECRET_MARKER not in response.text
