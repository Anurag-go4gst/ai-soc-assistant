from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

_FIXTURE = Path(__file__).resolve().parents[1] / "intel" / "fixtures" / "ioc_registry.sample.json"


def test_ioc_registry_settings_routes_require_auth(monkeypatch) -> None:
    monkeypatch.setattr(settings, "app_auth_enabled", True)
    app.dependency_overrides.clear()
    client = TestClient(app)

    assert client.get("/settings/ioc-registry").status_code == 401
    assert client.put("/settings/ioc-registry", json={"registry": {}}).status_code == 401


def test_get_ioc_registry_settings_returns_hash_summary(monkeypatch) -> None:
    monkeypatch.setattr(settings, "app_auth_enabled", False)
    monkeypatch.setattr(settings, "ioc_registry_enabled", True)
    monkeypatch.setattr(settings, "ioc_registry_path", str(_FIXTURE))
    app.dependency_overrides.clear()
    client = TestClient(app)

    response = client.get("/settings/ioc-registry")
    assert response.status_code == 200
    payload = response.json()
    assert payload["hash_count"] >= 1
    assert payload["hashes"]
    assert payload["import_path_hint"]
    assert payload["read_only_hashes"] is True
