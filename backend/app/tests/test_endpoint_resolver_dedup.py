from __future__ import annotations

from app.config import settings
from app.llm.clients.endpoint_resolver import build_failover_chat_client


def test_duplicate_local_and_instruct_urls_deduped(monkeypatch) -> None:
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
    assert len(client.chain) == 1
    assert client.chain[0][0] == "local_primary"
