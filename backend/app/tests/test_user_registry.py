from __future__ import annotations

import json
from pathlib import Path

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
                    {"username": "analyst", "password": "pass-a", "role": "analyst", "debug_access": False},
                    {"username": "coe_lead", "password": "pass-l", "role": "soc_lead", "debug_access": True},
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


def test_authenticate_known_user(users_file: Path) -> None:
    user = user_registry.authenticate("analyst", "pass-a")
    assert user is not None
    assert user.username == "analyst"
    assert user.debug_access is False


def test_env_fallback_authenticates_user_absent_from_registry(
    users_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Backward-compat: legacy env-only deployments (no matching registry user)
    # still authenticate via APP_AUTH_USER / APP_AUTH_PASSWORD.
    monkeypatch.setattr(settings, "app_auth_user", "legacy")
    monkeypatch.setattr(settings, "app_auth_password", "legacy-pass")
    monkeypatch.setattr(settings, "app_auth_role", "soc_lead")

    user = user_registry.authenticate("legacy", "legacy-pass")
    assert user is not None
    assert user.username == "legacy"
    assert user.role == "soc_lead"
    assert user.debug_access is True  # role-default for soc_lead


def test_env_fallback_rejects_wrong_password(
    users_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "app_auth_user", "legacy")
    monkeypatch.setattr(settings, "app_auth_password", "legacy-pass")
    assert user_registry.authenticate("legacy", "wrong") is None


def test_registry_user_takes_precedence_over_env(
    users_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A username present in the registry must validate against the registry
    # password, never silently fall through to env creds.
    monkeypatch.setattr(settings, "app_auth_user", "analyst")
    monkeypatch.setattr(settings, "app_auth_password", "env-pass")
    assert user_registry.authenticate("analyst", "env-pass") is None
    assert user_registry.authenticate("analyst", "pass-a") is not None


def test_authenticate_reloads_registry_after_external_file_update(users_file: Path) -> None:
    assert user_registry.authenticate("analyst", "pass-a") is not None

    document = json.loads(users_file.read_text(encoding="utf-8"))
    document["users"][0]["password"] = "new-external-pass"
    users_file.write_text(json.dumps(document), encoding="utf-8")

    assert user_registry.authenticate("analyst", "new-external-pass") is not None
    assert user_registry.authenticate("analyst", "pass-a") is None


def test_set_debug_access_persists(users_file: Path) -> None:
    updated = user_registry.set_debug_access("analyst", enabled=True)
    assert updated.debug_access is True
    reloaded = user_registry.get_user("analyst")
    assert reloaded is not None
    assert reloaded.debug_access is True


def test_profile_toggle_via_api(users_file: Path, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_auth_enabled", True)
    login = client.post("/api/auth/login", json={"username": "analyst", "password": "pass-a"})
    assert login.status_code == 200
    assert login.json()["debug_access"] is False

    patch = client.patch("/api/auth/profile", json={"debug_access": True})
    assert patch.status_code == 200
    assert patch.json()["debug_access"] is True

    me = client.get("/api/auth/me")
    assert me.json()["debug_access"] is True


def test_debug_api_uses_profile_flag(users_file: Path, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_auth_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_debug_api_enabled", True)
    client.post("/api/auth/login", json={"username": "analyst", "password": "pass-a"})
    denied = client.get("/api/debug/traces")
    assert denied.status_code == 403

    client.patch("/api/auth/profile", json={"debug_access": True})
    monkeypatch.setattr(
        "app.api.routes_debug.list_trace_runs",
        lambda **kwargs: [],
    )
    allowed = client.get("/api/debug/traces")
    assert allowed.status_code == 200


def test_env_fallback_session_payload_resolves_without_registry_row(monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulate env fallback login token payload when users.json has no matching user.
    monkeypatch.setattr(settings, "app_auth_users_path", "")
    monkeypatch.setattr(settings, "app_auth_user", "legacy-user")
    monkeypatch.setattr(settings, "app_auth_role", "soc_lead")
    user_registry.reload_users_for_tests()

    resolved = user_registry.session_user_from_token_payload(
        {"username": "legacy-user", "role": "soc_lead"},
    )

    assert resolved is not None
    assert resolved["username"] == "legacy-user"
    assert resolved["role"] == "soc_lead"
    assert resolved["debug_access"] is True


def test_upsert_user_creates_and_authenticates(users_file: Path) -> None:
    created = user_registry.upsert_user(
        "jane@velocis.in", password="s3cret", role="analyst"
    )
    assert created.username == "jane@velocis.in"
    assert created.role == "analyst"
    assert created.debug_access is False  # analyst role default
    assert user_registry.authenticate("jane@velocis.in", "s3cret") is not None
    # Persisted to the registry file.
    document = json.loads(users_file.read_text(encoding="utf-8"))
    assert any(u["username"] == "jane@velocis.in" for u in document["users"])


def test_upsert_user_updates_existing_and_role_default_debug(users_file: Path) -> None:
    # soc_lead role defaults debug_access true when not specified.
    user = user_registry.upsert_user("analyst", password="newpass", role="soc_lead")
    assert user.role == "soc_lead"
    assert user.debug_access is True
    assert user_registry.authenticate("analyst", "newpass") is not None
    assert user_registry.authenticate("analyst", "pass-a") is None  # old password replaced


def test_upsert_user_explicit_debug_overrides_role_default(users_file: Path) -> None:
    user = user_registry.upsert_user(
        "lead@velocis.in", password="p", role="soc_lead", debug_access=False
    )
    assert user.debug_access is False


def test_upsert_user_rejects_empty(users_file: Path) -> None:
    with pytest.raises(ValueError):
        user_registry.upsert_user("  ", password="p")
    with pytest.raises(ValueError):
        user_registry.upsert_user("x@y.z", password="")


def test_delete_user_lifecycle(users_file: Path) -> None:
    assert user_registry.delete_user("analyst") is True
    assert user_registry.get_user("analyst") is None
    assert user_registry.delete_user("analyst") is False  # already gone
