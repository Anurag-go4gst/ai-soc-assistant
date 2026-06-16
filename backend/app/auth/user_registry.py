"""Multi-user auth registry with per-user debug_access profile preference."""

from __future__ import annotations

import hmac
import json
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

from app.config import settings

_STORE_LOCK = Lock()
_CACHE: dict[str, Any] | None = None


@dataclass(frozen=True)
class AuthUser:
    username: str
    role: str
    debug_access: bool


def _users_path() -> Path:
    configured = settings.app_auth_users_path.strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parent / "users.json"


def _example_path() -> Path:
    return Path(__file__).resolve().parent / "users.example.json"


def _default_debug_access_for_role(role: str) -> bool:
    return role.strip().lower() in {"soc_lead", "platform_admin", "security_admin"}


def _bootstrap_users() -> dict[str, Any]:
    example = _example_path()
    if example.is_file():
        return json.loads(example.read_text(encoding="utf-8"))
    role = settings.app_auth_role.strip() or "demo_analyst"
    return {
        "users": [
            {
                "username": settings.app_auth_user,
                "password": settings.app_auth_password,
                "role": role,
                "debug_access": _default_debug_access_for_role(role),
            }
        ]
    }


def _load_document() -> dict[str, Any]:
    global _CACHE
    path = _users_path()
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_bootstrap_users(), indent=2) + "\n", encoding="utf-8")
    with path.open(encoding="utf-8") as handle:
        document = json.load(handle)
    if not isinstance(document.get("users"), list):
        raise ValueError("invalid_users_registry")
    _CACHE = document
    return document


def _document_unlocked() -> dict[str, Any]:
    global _CACHE
    if _CACHE is None:
        return _load_document()
    return _CACHE


def _document() -> dict[str, Any]:
    with _STORE_LOCK:
        return _document_unlocked()


def _persist(document: dict[str, Any]) -> None:
    global _CACHE
    path = _users_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    _CACHE = document


def reload_users_for_tests() -> None:
    global _CACHE
    with _STORE_LOCK:
        _CACHE = None


def list_public_users() -> list[dict[str, Any]]:
    return [
        {
            "username": user.username,
            "role": user.role,
            "debug_access": user.debug_access,
        }
        for user in _all_users()
    ]


def _all_users() -> list[AuthUser]:
    users: list[AuthUser] = []
    for raw in _document().get("users", []):
        if not isinstance(raw, dict):
            continue
        username = str(raw.get("username") or "").strip()
        if not username:
            continue
        role = str(raw.get("role") or "analyst")
        users.append(
            AuthUser(
                username=username,
                role=role,
                debug_access=bool(raw.get("debug_access", _default_debug_access_for_role(role))),
            )
        )
    return users


def _raw_user_record(username: str) -> dict[str, Any] | None:
    for raw in _document().get("users", []):
        if isinstance(raw, dict) and str(raw.get("username") or "").strip() == username:
            return raw
    return None


def get_user(username: str) -> AuthUser | None:
    normalized = username.strip()
    for user in _all_users():
        if user.username == normalized:
            return user
    return None


def authenticate(username: str, password: str) -> AuthUser | None:
    uname = username.strip()
    record = _raw_user_record(uname)
    if record is not None:
        stored_password = str(record.get("password") or "")
        if not hmac.compare_digest(password, stored_password):
            return None
        return get_user(uname)
    # Backward-compat: the registry has no such user. Fall back to the legacy
    # single-user env credentials (APP_AUTH_USER / APP_AUTH_PASSWORD) so old
    # env-only deployments keep working after the multi-user migration.
    return _authenticate_env_fallback(uname, password)


def _authenticate_env_fallback(username: str, password: str) -> AuthUser | None:
    env_user = settings.app_auth_user.strip()
    env_password = settings.app_auth_password
    if not env_user or not env_password:
        return None
    if not hmac.compare_digest(username, env_user):
        return None
    if not hmac.compare_digest(password, env_password):
        return None
    role = settings.app_auth_role.strip() or "demo_analyst"
    return AuthUser(
        username=env_user,
        role=role,
        debug_access=_default_debug_access_for_role(role),
    )


def user_has_debug_access(username: str) -> bool:
    user = get_user(username)
    if user is None:
        return False
    return user.debug_access


def set_debug_access(username: str, *, enabled: bool) -> AuthUser:
    normalized = username.strip()
    with _STORE_LOCK:
        document = json.loads(json.dumps(_document_unlocked()))
        users = document.get("users")
        if not isinstance(users, list):
            raise ValueError("invalid_users_registry")
        updated = False
        for raw in users:
            if not isinstance(raw, dict):
                continue
            if str(raw.get("username") or "").strip() == normalized:
                raw["debug_access"] = bool(enabled)
                updated = True
                break
        if not updated:
            raise KeyError("user_not_found")
        _persist(document)
    user = get_user(normalized)
    if user is None:
        raise KeyError("user_not_found")
    return user


def session_user_from_token_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    username = str(payload.get("username") or "").strip()
    user = get_user(username)
    if user is None:
        return None
    return {
        "username": user.username,
        "role": user.role,
        "debug_access": user.debug_access,
    }
