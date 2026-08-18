from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.auth import user_registry
from app.config import settings
from app.connectors.mcp.discovery_snapshot import get_discovery_snapshot_store
from app.main import app


@pytest.fixture(autouse=True)
def _clear_discovery_store():
    get_discovery_snapshot_store().clear()
    yield
    get_discovery_snapshot_store().clear()


@pytest.fixture
def users_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "users.json"
    path.write_text(
        json.dumps({"users": [{"username": "analyst", "password": "pass-a", "role": "analyst", "debug_access": True}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "app_auth_users_path", str(path))
    user_registry.reload_users_for_tests()
    return path


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_mcp_catalog_disabled_returns_404(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_debug_api_enabled", False)
    monkeypatch.setattr(settings, "app_auth_enabled", False)
    response = client.get("/api/debug/mcp/catalog")
    assert response.status_code == 404


def test_mcp_catalog_requires_debug_access(users_file: Path, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    users_file.write_text(
        json.dumps({"users": [{"username": "analyst", "password": "pass-a", "role": "analyst", "debug_access": False}]}),
        encoding="utf-8",
    )
    user_registry.reload_users_for_tests()
    monkeypatch.setattr(settings, "ai_soc_debug_api_enabled", True)
    monkeypatch.setattr(settings, "app_auth_enabled", True)
    client.post("/api/auth/login", json={"username": "analyst", "password": "pass-a"})
    response = client.get("/api/debug/mcp/catalog")
    assert response.status_code == 403


def test_mcp_catalog_returns_dual_views_no_secrets(users_file: Path, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_debug_api_enabled", True)
    monkeypatch.setattr(settings, "app_auth_enabled", True)
    monkeypatch.delenv("MCP_MODE", raising=False)  # mock mode -- deterministic, no live network
    client.post("/api/auth/login", json={"username": "analyst", "password": "pass-a"})

    response = client.get("/api/debug/mcp/catalog")
    assert response.status_code == 200
    payload = response.json()
    assert payload["servers"]
    server = payload["servers"][0]
    assert "effective_approved_catalog" in server
    assert "server_discovered_catalog" in server
    body_text = json.dumps(payload)
    assert "bearer_token" not in body_text.lower()
    assert "test-token" not in body_text


def test_mcp_discovery_refresh_unconfigured_server_fails_safely_not_mocked(
    users_file: Path, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "ai_soc_debug_api_enabled", True)
    monkeypatch.setattr(settings, "app_auth_enabled", True)
    monkeypatch.delenv("MCP_MODE", raising=False)  # mock registry -> server name "mock"
    client.post("/api/auth/login", json={"username": "analyst", "password": "pass-a"})

    response = client.post("/api/debug/mcp/discovery/refresh", params={"server_name": "mock"})
    assert response.status_code == 200
    payload = response.json()
    # No base_url/token configured in this test -> connector refuses to
    # fabricate a live result; snapshot is honestly "failed", never "ok".
    assert payload["status"] == "failed"
    assert payload["error_reason"] == "live_transport_unconfigured"


def test_mcp_discovery_refresh_unknown_server_404(users_file: Path, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_debug_api_enabled", True)
    monkeypatch.setattr(settings, "app_auth_enabled", True)
    monkeypatch.delenv("MCP_MODE", raising=False)
    client.post("/api/auth/login", json={"username": "analyst", "password": "pass-a"})

    response = client.post("/api/debug/mcp/discovery/refresh", params={"server_name": "not_a_real_server"})
    assert response.status_code == 404


def test_mcp_discovery_refresh_populates_store_reflected_in_catalog(
    users_file: Path, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "ai_soc_debug_api_enabled", True)
    monkeypatch.setattr(settings, "app_auth_enabled", True)
    monkeypatch.delenv("MCP_MODE", raising=False)
    client.post("/api/auth/login", json={"username": "analyst", "password": "pass-a"})

    refresh = client.post("/api/debug/mcp/discovery/refresh", params={"server_name": "mock"})
    assert refresh.status_code == 200

    catalog = client.get("/api/debug/mcp/catalog").json()
    server = next(s for s in catalog["servers"] if s["server_name"] == "mock")
    assert server["discovery_status"] == "failed"  # unconfigured transport -> honest failure, not fabricated
