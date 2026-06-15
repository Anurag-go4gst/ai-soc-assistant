from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import settings
from app.spl import source_profile_store as store


@pytest.fixture
def temp_store_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "source_profile_map.json"
    monkeypatch.setattr(settings, "ai_soc_source_profile_store_path", str(path))
    return path


def test_save_and_load_persisted_profile(temp_store_path: Path) -> None:
    document = store.save_persisted_source_profile(
        {"auth_index": "pgcil_soc", "auth_sourcetype": "pgcil:auth"},
        updated_by="test",
    )
    assert document["values"]["auth_index"] == "pgcil_soc"
    assert store.load_persisted_source_profile()["auth_sourcetype"] == "pgcil:auth"
    loaded = json.loads(temp_store_path.read_text(encoding="utf-8"))
    assert loaded["updated_by"] == "test"


def test_merge_mcp_discovery_overwrites_coe_values(temp_store_path: Path) -> None:
    store.save_persisted_source_profile({"auth_index": "legacy_index"}, updated_by="coe_ui")
    document = store.merge_mcp_discovery_into_store({"auth_index": "pgcil_soc"}, overwrite=True)
    assert document["values"]["auth_index"] == "pgcil_soc"
    assert document["field_sources"]["auth_index"] == "mcp_discovery"
