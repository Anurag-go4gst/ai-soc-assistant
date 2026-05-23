import json

from app.api.routes_settings import settings_status


def test_settings_status_root() -> None:
    payload = settings_status()
    for section in ("mcp", "rag", "llm", "embeddings", "telemetry", "routing", "safeguards", "observability"):
        assert section in payload, f"missing section: {section}"


def test_settings_status_api_prefix() -> None:
    assert settings_status()["mcp"]["mode"] == "mock"


def test_settings_status_does_not_leak_secrets() -> None:
    text = json.dumps(settings_status()).lower()
    for forbidden in ("example-secret-value", "session_secret", "token_value"):
        assert forbidden not in text, f"settings status leaked: {forbidden}"


def test_settings_status_uses_configured_booleans() -> None:
    payload = settings_status()
    assert isinstance(payload["mcp"]["base_url_configured"], bool)
    assert isinstance(payload["mcp"]["token_configured"], bool)
    assert isinstance(payload["mcp"]["global_execution_enabled"], bool)
    assert isinstance(payload["mcp"]["servers"][0]["url_configured"], bool)
    assert isinstance(payload["llm"]["instruct_endpoint_configured"], bool)
    assert isinstance(payload["llm"]["providers"][0]["api_key_configured"], bool)


def test_default_connector_modes_and_no_splunk_write() -> None:
    payload = settings_status()
    assert payload["mcp"]["mode"] == "mock"
    assert payload["mcp"]["global_execution_enabled"] is False
    assert payload["mcp"]["servers"][0]["execution_enabled"] is False
    assert payload["rag"]["mode"] == "mock"
    assert payload["llm"]["mode"] == "mock"
    assert payload["llm"]["health_canary_enabled"] is False
    assert payload["llm"]["providers"][0]["supports_tool_calling"] is False
    assert payload["embeddings"]["mode"] == "mock"
    assert payload["telemetry"]["sink"] == "db"
    assert payload["telemetry"]["database_telemetry_enabled"] is True
    assert payload["telemetry"]["splunk_write_enabled"] is False
    assert payload["routing"]["workflow_planner_enabled"] is True
    assert payload["routing"]["workflow_planner_execution_enabled"] is False
    assert payload["routing"]["workflow_plan_logging_enabled"] is True
