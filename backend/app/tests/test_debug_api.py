from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.auth import user_registry
from app.config import settings
from app.main import app


@pytest.fixture
def users_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "users.json"
    path.write_text(
        json.dumps(
            {
                "users": [
                    {"username": "analyst", "password": "pass-a", "role": "analyst", "debug_access": True},
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "app_auth_users_path", str(path))
    user_registry.reload_users_for_tests()
    return path


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_debug_api_disabled_returns_404(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_debug_api_enabled", False)
    monkeypatch.setattr(settings, "app_auth_enabled", False)
    response = client.get("/api/debug/traces")
    assert response.status_code == 404


def test_debug_api_forbidden_without_profile_access(
    users_file: Path,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    users_file.write_text(
        json.dumps(
            {
                "users": [
                    {"username": "analyst", "password": "pass-a", "role": "analyst", "debug_access": False},
                ]
            }
        ),
        encoding="utf-8",
    )
    user_registry.reload_users_for_tests()
    monkeypatch.setattr(settings, "ai_soc_debug_api_enabled", True)
    monkeypatch.setattr(settings, "app_auth_enabled", True)
    client.post("/api/auth/login", json={"username": "analyst", "password": "pass-a"})
    response = client.get("/api/debug/traces")
    assert response.status_code == 403


def test_debug_api_lists_traces_when_profile_allows(
    users_file: Path,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_debug_api_enabled", True)
    monkeypatch.setattr(settings, "app_auth_enabled", True)
    client.post("/api/auth/login", json={"username": "analyst", "password": "pass-a"})
    monkeypatch.setattr(
        "app.api.routes_debug.list_trace_runs",
        lambda **kwargs: [{"trace_id": "trace-1", "status": "completed"}],
    )
    response = client.get("/api/debug/traces")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1


def test_debug_readiness_shape(users_file: Path, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_debug_api_enabled", True)
    monkeypatch.setattr(settings, "app_auth_enabled", True)
    client.post("/api/auth/login", json={"username": "analyst", "password": "pass-a"})
    response = client.get("/api/debug/readiness")
    assert response.status_code == 200
    payload = response.json()
    assert "telemetry" in payload
    assert payload["debug_api_enabled"] is True


def test_debug_trace_bundle_not_found(users_file: Path, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_debug_api_enabled", True)
    monkeypatch.setattr(settings, "app_auth_enabled", True)
    client.post("/api/auth/login", json={"username": "analyst", "password": "pass-a"})
    monkeypatch.setattr("app.api.routes_debug.fetch_trace_bundle", lambda trace_id, **kwargs: None)
    response = client.get("/api/debug/traces/missing/bundle")
    assert response.status_code == 404


def test_debug_trace_id_validation(users_file: Path, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_debug_api_enabled", True)
    monkeypatch.setattr(settings, "app_auth_enabled", True)
    client.post("/api/auth/login", json={"username": "analyst", "password": "pass-a"})
    response = client.get("/api/debug/traces/bad%20trace")
    assert response.status_code == 400
    assert response.json()["detail"] == "invalid_trace_id"


def test_debug_bundle_and_timeline_use_event_limits(
    users_file: Path,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_debug_api_enabled", True)
    monkeypatch.setattr(settings, "app_auth_enabled", True)
    client.post("/api/auth/login", json={"username": "analyst", "password": "pass-a"})

    calls: list[tuple[str, int | None]] = []

    def _fake_timeline(trace_id: str, *, max_events: int | None = None) -> dict[str, Any]:
        calls.append(("timeline", max_events))
        return {"run": {"trace_id": trace_id}, "events": [], "event_count": 0}

    def _fake_bundle(trace_id: str, *, max_events: int | None = None) -> dict[str, Any]:
        calls.append(("bundle", max_events))
        return {"trace_id": trace_id, "run": {"trace_id": trace_id}, "timeline": []}

    monkeypatch.setattr("app.api.routes_debug.fetch_trace_timeline", _fake_timeline)
    monkeypatch.setattr("app.api.routes_debug.fetch_trace_bundle", _fake_bundle)

    timeline_response = client.get("/api/debug/traces/trace-1")
    bundle_response = client.get("/api/debug/traces/trace-1/bundle")

    assert timeline_response.status_code == 200
    assert bundle_response.status_code == 200
    assert ("timeline", 500) in calls
    assert ("bundle", 200) in calls
