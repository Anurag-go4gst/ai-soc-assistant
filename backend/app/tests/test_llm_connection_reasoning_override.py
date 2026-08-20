"""Operator LLM endpoint switching (VPS <-> COE) via the connection override store.

The Settings UI writes this override; it must repoint both the primary endpoint
(Ask LLM + every governed role) and the Foundation-Sec reasoning hop, so a switch
cannot strand a dead endpoint in the failover chain.
"""

from __future__ import annotations

import pytest

from app.config import settings
from app.llm import connection_store
from app.llm.clients.endpoint_resolver import build_failover_chat_client


@pytest.fixture
def isolated_store(tmp_path, monkeypatch, isolated_llm_connection_store_apply):
    """Store path + a clean endpoint baseline.

    ``isolated_llm_connection_store_apply`` restores the globals that
    ``apply_to_settings`` writes without being asked to (enabled / active model /
    default provider), which monkeypatch alone would not cover.
    """
    monkeypatch.setattr(
        settings, "ai_soc_llm_connection_store_path", str(tmp_path / "llm_connection.json")
    )
    monkeypatch.setattr(settings, "ai_soc_llm_qwen_primary_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_llm_foundation_sec_instruct_base_url", "")
    monkeypatch.setattr(settings, "ai_soc_llm_foundation_sec_instruct_model", "")
    monkeypatch.setattr(settings, "ai_soc_llm_foundation_sec_reasoning_base_url", "")
    monkeypatch.setattr(settings, "ai_soc_llm_foundation_sec_reasoning_model", "")
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")
    monkeypatch.setattr(settings, "ai_soc_llm_local_base_url", "")
    monkeypatch.setattr(settings, "ai_soc_llm_local_model", "")
    monkeypatch.setattr(settings, "ai_soc_llm_local_api_key", "")
    return tmp_path


def _chain(role: str | None) -> list[tuple[str, str, str]]:
    client = build_failover_chat_client(role=role, sidecar=False)
    if client is None:
        return []
    return [(label, c.base_url, c.model) for label, c in client.chain]


def _save_coe(**overrides):
    kwargs = {
        "enabled": True,
        "mode": "local",
        "base_url": "http://10.52.1.13:8004/v1",
        "model": "foundation-sec-instruct",
        "api_key": None,
        "timeout_seconds": 120,
        "updated_by": "test",
        "reasoning_base_url": "http://10.52.1.13:8003/v1",
        "reasoning_model": "foundation-sec-reasoning",
    }
    kwargs.update(overrides)
    return connection_store.save_connection(**kwargs)


def test_coe_preset_repoints_primary_and_reasoning_hop(isolated_store):
    _save_coe()

    assert _chain(None) == [
        ("local_primary", "http://10.52.1.13:8004/v1", "foundation-sec-instruct")
    ]
    assert _chain("mitre_reasoner") == [
        ("foundation_sec_reasoning", "http://10.52.1.13:8003/v1", "foundation-sec-reasoning"),
        ("local_primary", "http://10.52.1.13:8004/v1", "foundation-sec-instruct"),
    ]


def test_switch_back_to_vps_drops_the_reasoning_hop(isolated_store):
    _save_coe()
    # VPS preset carries no reasoning endpoint — the hop must go away, not linger
    # pointing at an unreachable COE address (each dead hop costs a full timeout).
    _save_coe(
        base_url="http://host.docker.internal:8081/v1",
        model="foundation-sec-1.1-8b-instruct-q8_0.gguf",
        reasoning_base_url="",
        reasoning_model="",
    )

    expected = [
        (
            "local_primary",
            "http://host.docker.internal:8081/v1",
            "foundation-sec-1.1-8b-instruct-q8_0.gguf",
        )
    ]
    assert _chain(None) == expected
    assert _chain("mitre_reasoner") == expected


def test_effective_connection_exposes_reasoning_and_never_the_key(isolated_store):
    _save_coe(api_key="super-secret-token")
    effective = connection_store.effective_connection()

    assert effective["reasoning_base_url"] == "http://10.52.1.13:8003/v1"
    assert effective["reasoning_model"] == "foundation-sec-reasoning"
    assert effective["api_key_configured"] is True
    assert "api_key" not in effective
    assert "super-secret-token" not in str(effective)


def test_legacy_document_without_reasoning_keys_leaves_env_untouched(isolated_store, monkeypatch):
    _save_coe(reasoning_base_url="", reasoning_model="")
    # Simulate an override written before reasoning support existed.
    import json
    from pathlib import Path

    path = Path(settings.ai_soc_llm_connection_store_path)
    document = json.loads(path.read_text(encoding="utf-8"))
    document.pop("reasoning_base_url")
    document.pop("reasoning_model")
    path.write_text(json.dumps(document), encoding="utf-8")

    monkeypatch.setattr(
        settings, "ai_soc_llm_foundation_sec_reasoning_base_url", "http://env-value:9/v1"
    )
    monkeypatch.setattr(settings, "ai_soc_llm_foundation_sec_reasoning_model", "env-model")
    connection_store.apply_to_settings()

    assert settings.ai_soc_llm_foundation_sec_reasoning_base_url == "http://env-value:9/v1"


def test_presets_cover_vps_and_coe_and_carry_no_secret():
    ids = {preset["id"] for preset in connection_store.CONNECTION_PRESETS}
    assert ids == {"vps_dev", "coe_lan"}
    coe = next(p for p in connection_store.CONNECTION_PRESETS if p["id"] == "coe_lan")
    assert coe["base_url"] == "http://10.52.1.13:8004/v1"
    assert coe["reasoning_base_url"] == "http://10.52.1.13:8003/v1"
    for preset in connection_store.CONNECTION_PRESETS:
        assert "api_key" not in preset
