from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def test_asset_registry_settings_routes_require_auth(monkeypatch) -> None:
    monkeypatch.setattr(settings, "app_auth_enabled", True)
    app.dependency_overrides.clear()
    client = TestClient(app)

    assert client.get("/settings/asset-registry").status_code == 401
    assert client.put("/settings/asset-registry", json={"assets": []}).status_code == 401
    assert client.post("/settings/asset-registry/import", content="[]").status_code == 401
    assert client.get("/settings/asset-registry/export").status_code == 401


def test_source_profile_settings_routes_require_auth(monkeypatch) -> None:
    monkeypatch.setattr(settings, "app_auth_enabled", True)
    app.dependency_overrides.clear()
    client = TestClient(app)

    assert client.get("/settings/source-profiles").status_code == 401
    assert client.put("/settings/source-profiles", json={"values": {}}).status_code == 401

