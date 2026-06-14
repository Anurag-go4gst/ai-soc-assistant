from __future__ import annotations

from app.config import settings
from app.llm.clients.endpoint_resolver import build_failover_chat_client


def test_qwen_not_in_chain_when_flag_off(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_qwen_primary_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_llm_qwen_base_url", "http://10.52.1.13:8000/v1")
    monkeypatch.setattr(settings, "ai_soc_llm_qwen_model", "./qwen72b")
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")
    monkeypatch.setattr(settings, "ai_soc_llm_local_base_url", "http://host.docker.internal:8081/v1")
    monkeypatch.setattr(settings, "ai_soc_llm_local_model", "instruct-model")

    client = build_failover_chat_client(sidecar=True)
    assert client is not None
    labels = [label for label, _ in client.chain]
    assert "qwen_primary" not in labels
    assert labels[0] == "local_primary"


def test_qwen_prepended_when_flag_on(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_qwen_primary_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_qwen_base_url", "http://10.52.1.13:8000/v1")
    monkeypatch.setattr(settings, "ai_soc_llm_qwen_model", "./qwen72b")
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")
    monkeypatch.setattr(settings, "ai_soc_llm_local_base_url", "http://host.docker.internal:8081/v1")
    monkeypatch.setattr(settings, "ai_soc_llm_local_model", "instruct-model")

    client = build_failover_chat_client(sidecar=True)
    assert client is not None
    labels = [label for label, _ in client.chain]
    assert labels[0] == "qwen_primary"
    assert "local_primary" in labels
