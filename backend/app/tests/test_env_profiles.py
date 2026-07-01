"""Tests for environment profile selection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.env_profiles import list_profiles, read_active_profile_id, select_profile


@pytest.fixture
def env_profiles_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    base = tmp_path / "env"
    profiles = base / "profiles"
    profiles.mkdir(parents=True)
    (profiles / "coe.env.example").write_text("AI_SOC_ENV_PROFILE=coe\nFOO=bar\n", encoding="utf-8")
    (profiles / "development.env.example").write_text(
        "AI_SOC_ENV_PROFILE=development\n", encoding="utf-8"
    )
    (profiles / "manifest.json").write_text(
        json.dumps(
            {
                "profiles": [
                    {"id": "coe", "label": "COE", "example_file": "coe.env.example"},
                    {"id": "development", "label": "Dev", "example_file": "development.env.example"},
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AI_SOC_ENV_PROFILES_DIR", str(base))
    monkeypatch.setenv("AI_SOC_REPO_ROOT", str(tmp_path))
    return base


def test_list_profiles(env_profiles_tree: Path) -> None:
    profiles = list_profiles()
    assert [p.id for p in profiles] == ["coe", "development"]
    assert profiles[0].example_exists is True


def test_select_profile_writes_active_file(env_profiles_tree: Path) -> None:
    result = select_profile("development")
    assert result["profile_id"] == "development"
    assert (env_profiles_tree / "active.profile").read_text(encoding="utf-8").strip() == "development"


def test_select_profile_rejects_unknown(env_profiles_tree: Path) -> None:
    with pytest.raises(ValueError, match="unknown_profile"):
        select_profile("missing")


def test_read_active_profile_id_from_active_file(
    env_profiles_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "ai_soc_env_profile", "")
    (env_profiles_tree / "active.profile").write_text("development\n", encoding="utf-8")
    assert read_active_profile_id() == "development"
