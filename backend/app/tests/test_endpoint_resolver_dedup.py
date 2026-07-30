from __future__ import annotations

from app.config import settings
from app.llm.clients.endpoint_resolver import build_failover_chat_client


def test_same_url_model_different_config_identity_retained(monkeypatch) -> None:
    """local_primary and instruct fallback may share URL+model but stay distinct candidates."""
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")
    monkeypatch.setattr(settings, "ai_soc_llm_local_base_url", "http://host.docker.internal:8081/v1")
    monkeypatch.setattr(settings, "ai_soc_llm_local_model", "instruct-model")
    monkeypatch.setattr(
        settings,
        "ai_soc_llm_foundation_sec_instruct_base_url",
        "http://host.docker.internal:8081/v1",
    )
    monkeypatch.setattr(settings, "ai_soc_llm_foundation_sec_instruct_model", "instruct-model")

    client = build_failover_chat_client(sidecar=True)
    assert client is not None
    assert len(client.chain) == 2
    labels = [label for label, _ in client.chain]
    assert labels == ["local_primary", "foundation_sec_instruct_fallback"]


def test_proven_equivalent_endpoint_omitted_from_chain(monkeypatch) -> None:
    """Chain build drops only provably equivalent candidates (full fingerprint match)."""
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")
    monkeypatch.setattr(settings, "ai_soc_llm_qwen_primary_enabled", True)
    shared_url = "http://host.docker.internal:8081/v1"
    shared_model = "shared-model"
    monkeypatch.setattr(settings, "ai_soc_llm_qwen_base_url", shared_url)
    monkeypatch.setattr(settings, "ai_soc_llm_qwen_model", shared_model)
    monkeypatch.setattr(settings, "ai_soc_llm_qwen_api_key", "")
    monkeypatch.setattr(settings, "ai_soc_llm_local_base_url", shared_url)
    monkeypatch.setattr(settings, "ai_soc_llm_local_model", shared_model)
    monkeypatch.setattr(settings, "ai_soc_llm_foundation_sec_instruct_base_url", "")
    monkeypatch.setattr(settings, "ai_soc_llm_foundation_sec_instruct_model", "")

    client = build_failover_chat_client(sidecar=False)
    assert client is not None
    labels = [label for label, _ in client.chain]
    assert labels == ["qwen_primary", "local_primary"]
