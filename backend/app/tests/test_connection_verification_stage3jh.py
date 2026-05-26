from __future__ import annotations

import json
from urllib.error import HTTPError, URLError

from app.api import routes_settings
from app.api.routes_settings import (
    LlmVerificationRequest,
    McpVerificationRequest,
    list_llm_models,
    test_llm_connection as run_llm_connection_test,
    test_mcp_connection as run_mcp_connection_test,
    validate_llm_settings,
    validate_mcp_settings,
)
from app.config import Settings


class _Response:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self.payload = payload
        self.status = status

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, _limit: int = -1) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_mcp_validate_returns_clear_failure_when_url_missing() -> None:
    result = validate_mcp_settings(McpVerificationRequest(auth_method="none", url=""))

    assert result["status"] == "Not connected"
    assert result["url_configured"] is False
    assert result["failure_reason"] == "MCP URL is missing or invalid."


def test_mcp_validate_returns_clear_failure_when_auth_required_but_missing() -> None:
    result = validate_mcp_settings(McpVerificationRequest(url="https://mcp.example.invalid", auth_method="bearer", bearer_token=""))

    assert result["status"] == "Not connected"
    assert result["authentication_configured"] is False
    assert result["failure_reason"] == "Authentication is required but credentials are not configured."


def test_mcp_test_connection_handles_unreachable_endpoint(monkeypatch) -> None:
    def fail(*_args: object, **_kwargs: object) -> object:
        raise URLError("dns_failed")

    monkeypatch.setattr(routes_settings, "urlopen", fail)

    result = run_mcp_connection_test(McpVerificationRequest(url="https://mcp.example.invalid", auth_method="none"))

    assert result["status"] == "Not connected"
    assert result["reachable"] is False
    assert "Cannot reach MCP endpoint" in result["failure_reason"]


def test_mcp_test_connection_handles_auth_failure(monkeypatch) -> None:
    def fail(*_args: object, **_kwargs: object) -> object:
        raise HTTPError("https://mcp.example.invalid", 401, "Unauthorized", {}, None)

    monkeypatch.setattr(routes_settings, "urlopen", fail)

    result = run_mcp_connection_test(McpVerificationRequest(url="https://mcp.example.invalid", auth_method="bearer", bearer_token="secret-token"))

    assert result["status"] == "Reachable but authentication failed"
    assert result["reachable"] is True
    assert result["authenticated"] is False
    assert "secret-token" not in json.dumps(result)


def test_mcp_test_connection_discovers_tools_without_execution(monkeypatch) -> None:
    methods: list[str] = []

    def fake_urlopen(request: object, **_kwargs: object) -> _Response:
        body = getattr(request, "data", b"") or b"{}"
        method = json.loads(body.decode("utf-8")).get("method")
        methods.append(method)
        if method == "initialize":
            return _Response({"jsonrpc": "2.0", "id": "ai-soc-verify-init", "result": {"serverInfo": {"name": "splunk"}}})
        return _Response(
            {
                "jsonrpc": "2.0",
                "id": "ai-soc-verify-tools",
                "result": {"tools": [{"name": "splunk_run_query"}, {"name": "saia_generate_spl"}]},
            }
        )

    monkeypatch.setattr(routes_settings, "urlopen", fake_urlopen)

    result = run_mcp_connection_test(McpVerificationRequest(url="https://mcp.example.invalid", auth_method="none"))

    assert methods == ["initialize", "tools/list"]
    assert result["status"] == "Connected"
    assert result["tools_discovered_count"] == 2
    assert result["execution_policy"] == "gated"


def test_mcp_result_returns_no_secrets(monkeypatch) -> None:
    def fake_urlopen(*_args: object, **_kwargs: object) -> _Response:
        return _Response({"result": {"tools": []}})

    monkeypatch.setattr(routes_settings, "urlopen", fake_urlopen)
    result = run_mcp_connection_test(McpVerificationRequest(url="https://mcp.example.invalid", auth_method="bearer", bearer_token="secret-token-3jh"))

    assert "secret-token-3jh" not in json.dumps(result)


def test_llm_validate_returns_clear_failure_when_url_model_key_missing() -> None:
    result = validate_llm_settings(LlmVerificationRequest(provider_type="openai_compatible", base_url="", api_key="", model="", allow_cloud=True))

    assert result["status"] == "Not connected"
    assert result["base_url_configured"] is False
    assert result["failure_reason"] == "LLM base URL is missing or invalid."


def test_llm_test_connection_handles_unreachable_endpoint(monkeypatch) -> None:
    def fail(*_args: object, **_kwargs: object) -> object:
        raise URLError("dns_failed")

    monkeypatch.setattr(routes_settings, "urlopen", fail)

    result = run_llm_connection_test(
        LlmVerificationRequest(provider_type="openai_compatible", base_url="https://llm.example.invalid/v1", api_key="secret-key", model="gpt-test", allow_cloud=True)
    )

    assert result["status"] == "Not connected"
    assert "Cannot reach LLM endpoint" in result["failure_reason"]
    assert "secret-key" not in json.dumps(result)


def test_llm_test_connection_handles_auth_failure(monkeypatch) -> None:
    def fail(*_args: object, **_kwargs: object) -> object:
        raise HTTPError("https://llm.example.invalid/v1/models", 401, "Unauthorized", {}, None)

    monkeypatch.setattr(routes_settings, "urlopen", fail)

    result = run_llm_connection_test(
        LlmVerificationRequest(provider_type="openai_compatible", base_url="https://llm.example.invalid/v1", api_key="secret-key", model="gpt-test", allow_cloud=True)
    )

    assert result["status"] == "Reachable but authentication failed"
    assert result["authenticated"] is False


def test_llm_test_connection_handles_model_not_found(monkeypatch) -> None:
    def fake_urlopen(*_args: object, **_kwargs: object) -> _Response:
        return _Response({"data": [{"id": "other-model"}]})

    monkeypatch.setattr(routes_settings, "urlopen", fake_urlopen)

    result = run_llm_connection_test(
        LlmVerificationRequest(provider_type="openai_compatible", base_url="https://llm.example.invalid/v1", api_key="secret-key", model="missing-model", allow_cloud=True)
    )

    assert result["status"] == "Model not found"
    assert result["model_available"] is False


def test_llm_test_connection_blocks_cloud_provider_when_airgap_enforced() -> None:
    result = run_llm_connection_test(
        LlmVerificationRequest(
            provider_type="openai_compatible",
            base_url="https://llm.example.invalid/v1",
            api_key="secret-key",
            model="gpt-test",
            allow_cloud=True,
            airgap_enforced=True,
        )
    )

    assert result["status"] == "Blocked by airgap policy"
    assert result["policy_allowed"] is False


def test_llm_list_models_names_only_and_no_secrets(monkeypatch) -> None:
    def fake_urlopen(*_args: object, **_kwargs: object) -> _Response:
        return _Response({"data": [{"id": "gpt-test", "owned_by": "vendor"}]})

    monkeypatch.setattr(routes_settings, "urlopen", fake_urlopen)

    result = list_llm_models(
        LlmVerificationRequest(provider_type="openai_compatible", base_url="https://llm.example.invalid/v1", api_key="secret-key-3jh", model="gpt-test", allow_cloud=True)
    )

    assert result["status"] == "Connected"
    assert result["models"] == ["gpt-test"]
    assert "secret-key-3jh" not in json.dumps(result)


def test_final_synthesis_and_answer_guard_remain_disabled_by_default() -> None:
    fresh = Settings(_env_file=None)

    assert fresh.ai_soc_llm_final_synthesis_enabled is False
    assert fresh.ai_soc_llm_answer_guard_enabled is False
