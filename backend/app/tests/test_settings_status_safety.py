"""Extra safety checks on /settings/status output."""

import json

from app.api.routes_settings import settings_status
from app.connectors.embeddings.local_embeddings import LocalEmbeddingsConnector
from app.connectors.llm.local_runtime import LocalRuntimeLlmConnector
from app.connectors.mcp.splunk_mcp import SplunkMcpConnector
from app.connectors.rag.local_vector import LocalVectorRagConnector


def test_status_does_not_contain_secret_patterns() -> None:
    text = json.dumps(settings_status()).lower()
    for forbidden in ("bearer ", "eyj", "-----begin", "sk-abc", "xoxb-", "api_key_value", "secret-token-value"):
        assert forbidden not in text, f"settings status leaked: {forbidden}"


def test_registry_status_redacts_dynamic_secrets(monkeypatch) -> None:
    monkeypatch.setenv("MCP_MODE", "registry")
    monkeypatch.setenv("MCP_SERVERS", "splunk_soc")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TYPE", "splunk")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_URL", "https://secret-user:secret-pass@example.invalid/mcp")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_AUTH_MODE", "bearer")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_BEARER_TOKEN", "secret-token-value")
    monkeypatch.setenv("LLM_PROVIDERS", "enterprise_gateway")
    monkeypatch.setenv("LLM_PROVIDER_ENTERPRISE_GATEWAY_ENABLED", "true")
    monkeypatch.setenv("LLM_PROVIDER_ENTERPRISE_GATEWAY_TYPE", "openai_compatible")
    monkeypatch.setenv("LLM_PROVIDER_ENTERPRISE_GATEWAY_BASE_URL", "https://llm.example.invalid/v1")
    monkeypatch.setenv("LLM_PROVIDER_ENTERPRISE_GATEWAY_AUTH_MODE", "api_key")
    monkeypatch.setenv("LLM_PROVIDER_ENTERPRISE_GATEWAY_API_KEY", "api_key_value")
    monkeypatch.setenv("LLM_PROVIDER_ENTERPRISE_GATEWAY_MODEL", "model")

    text = json.dumps(settings_status()).lower()

    for forbidden in ("secret-token-value", "api_key_value", "secret-user", "secret-pass"):
        assert forbidden not in text


def test_status_exposes_telemetry_write_failures_counter() -> None:
    payload = settings_status()
    assert "telemetry_write_failures" in payload["observability"]
    assert isinstance(payload["observability"]["telemetry_write_failures"], int)


def test_no_splunk_write_path_advertised() -> None:
    payload = settings_status()
    assert payload["telemetry"]["splunk_write_enabled"] is False
    assert payload["telemetry"]["sink"] == "db"


def test_placeholder_connectors_advertise_implemented_false_and_fallback() -> None:
    for connector in (
        SplunkMcpConnector(),
        LocalRuntimeLlmConnector(),
        LocalVectorRagConnector(),
        LocalEmbeddingsConnector(),
    ):
        status = connector.health()
        assert status.implemented is False, type(connector).__name__
        assert status.fallback == "mock", type(connector).__name__


def test_mock_connectors_remain_available() -> None:
    from app.connectors.embeddings.mock import MockEmbeddingsConnector
    from app.connectors.llm.mock import MockLlmConnector
    from app.connectors.mcp.mock import MockMcpConnector
    from app.connectors.rag.mock import MockRagConnector

    for connector in (
        MockMcpConnector(),
        MockRagConnector(),
        MockLlmConnector(),
        MockEmbeddingsConnector(),
    ):
        status = connector.health()
        assert status.available is True
        assert status.implemented is True  # mocks are fully implemented as mocks
