from fastapi.testclient import TestClient

from app.main import app


def test_settings_status_root() -> None:
    client = TestClient(app)
    response = client.get("/settings/status")
    assert response.status_code == 200
    payload = response.json()
    for section in ("mcp", "rag", "llm", "routing", "safeguards", "observability"):
        assert section in payload, f"missing section: {section}"


def test_settings_status_api_prefix() -> None:
    client = TestClient(app)
    response = client.get("/api/settings/status")
    assert response.status_code == 200


def test_settings_status_does_not_leak_secrets() -> None:
    client = TestClient(app)
    response = client.get("/api/settings/status")
    text = response.text.lower()
    for forbidden in ("password", "secret", "token_value", "session_secret"):
        assert forbidden not in text, f"settings status leaked: {forbidden}"


def test_settings_status_uses_configured_booleans() -> None:
    client = TestClient(app)
    payload = client.get("/api/settings/status").json()
    assert isinstance(payload["mcp"]["base_url_configured"], bool)
    assert isinstance(payload["mcp"]["token_configured"], bool)
    assert isinstance(payload["llm"]["instruct_endpoint_configured"], bool)
