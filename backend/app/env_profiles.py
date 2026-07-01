"""Environment profile discovery and selection (COE vs development).

Profiles are committed under ``env/profiles/*.env.example``. The repo-root ``.env``
holds secrets and ``AI_SOC_ENV_PROFILE``. Docker Compose loads profile + secrets;
changing profile requires a backend container restart.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_PROFILE_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")


def _repo_root() -> Path:
    configured = os.getenv("AI_SOC_REPO_ROOT", "").strip()
    if configured:
        return Path(configured).resolve()
    # backend/app/env_profiles.py -> repo root
    return Path(__file__).resolve().parents[2]


def _env_base_dir() -> Path:
    override = os.getenv("AI_SOC_ENV_PROFILES_DIR", "").strip()
    if override:
        return Path(override).resolve()
    return _repo_root() / "env"


def profiles_dir() -> Path:
    return _env_base_dir() / "profiles"


def active_profile_path() -> Path:
    return _env_base_dir() / "active.profile"


def root_env_path() -> Path:
    return _repo_root() / ".env"


def manifest_path() -> Path:
    return profiles_dir() / "manifest.json"


@dataclass(frozen=True)
class EnvProfile:
    id: str
    label: str
    description: str
    example_file: str
    recommended_for: tuple[str, ...] = ()
    example_exists: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "example_file": self.example_file,
            "recommended_for": list(self.recommended_for),
            "example_exists": self.example_exists,
        }


def _load_manifest_document() -> dict[str, Any]:
    path = manifest_path()
    if not path.is_file():
        return {"version": 1, "profiles": []}
    return json.loads(path.read_text(encoding="utf-8"))


def list_profiles() -> list[EnvProfile]:
    document = _load_manifest_document()
    items: list[EnvProfile] = []
    for raw in document.get("profiles") or []:
        if not isinstance(raw, dict):
            continue
        profile_id = str(raw.get("id") or "").strip()
        if not profile_id:
            continue
        example_file = str(raw.get("example_file") or f"{profile_id}.env.example")
        example_path = profiles_dir() / example_file
        items.append(
            EnvProfile(
                id=profile_id,
                label=str(raw.get("label") or profile_id),
                description=str(raw.get("description") or ""),
                example_file=example_file,
                recommended_for=tuple(str(x) for x in (raw.get("recommended_for") or [])),
                example_exists=example_path.is_file(),
            )
        )
    return items


def profile_example_path(profile_id: str) -> Path:
    if not _PROFILE_ID_RE.match(profile_id):
        raise ValueError("invalid_profile_id")
    for profile in list_profiles():
        if profile.id == profile_id:
            return profiles_dir() / profile.example_file
    raise ValueError("unknown_profile")


def read_active_profile_id() -> str:
    from app.config import settings

    configured = (settings.ai_soc_env_profile or "").strip()
    if configured:
        return configured
    path = active_profile_path()
    if path.is_file():
        text = path.read_text(encoding="utf-8").strip().splitlines()
        if text and text[0].strip():
            return text[0].strip()
    return "coe"


def _upsert_env_profile_line(env_path: Path, profile_id: str) -> None:
    lines: list[str] = []
    if env_path.is_file():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    filtered = [line for line in lines if not line.startswith("AI_SOC_ENV_PROFILE=")]
    filtered.append(f"AI_SOC_ENV_PROFILE={profile_id}")
    env_path.write_text("\n".join(filtered).rstrip() + "\n", encoding="utf-8")


def select_profile(profile_id: str) -> dict[str, Any]:
    """Persist profile selection. Returns restart instructions (no hot reload)."""
    if not _PROFILE_ID_RE.match(profile_id):
        raise ValueError("invalid_profile_id")
    example = profile_example_path(profile_id)
    if not example.is_file():
        raise ValueError("profile_example_missing")

    active_path = active_profile_path()
    active_path.parent.mkdir(parents=True, exist_ok=True)
    active_path.write_text(profile_id + "\n", encoding="utf-8")

    root_env = root_env_path()
    root_env_updated = False
    root_env_error: str | None = None
    try:
        if not root_env.is_file() and (profiles_dir().parent / "secrets.example").is_file():
            root_env.write_text(
                (profiles_dir().parent / "secrets.example").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
        _upsert_env_profile_line(root_env, profile_id)
        root_env_updated = True
    except OSError as exc:
        root_env_error = str(exc)

    return {
        "profile_id": profile_id,
        "active_profile_file": str(active_path),
        "profile_example": str(example),
        "root_env_updated": root_env_updated,
        "root_env_path": str(root_env),
        "root_env_error": root_env_error,
        "restart_required": True,
        "restart_command": "docker compose up -d --force-recreate backend",
        "cli_command": f"./scripts/select_env_profile.sh {profile_id}",
    }


def build_env_profile_status() -> dict[str, Any]:
    active = read_active_profile_id()
    profiles = list_profiles()
    active_meta = next((p for p in profiles if p.id == active), None)
    example_path = profiles_dir() / (active_meta.example_file if active_meta else f"{active}.env.example")
    return {
        "active_profile_id": active,
        "active_profile": active_meta.to_dict() if active_meta else None,
        "profiles": [p.to_dict() for p in profiles],
        "profile_example_path": str(example_path),
        "profile_example_exists": example_path.is_file(),
        "active_profile_file": str(active_profile_path()),
        "root_env_path": str(root_env_path()),
        "reload_note": (
            "Environment variables load at container start. After changing profile, "
            "restart the backend: docker compose up -d --force-recreate backend"
        ),
    }
