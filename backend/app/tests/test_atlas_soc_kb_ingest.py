"""SOC-KB retrieval for imported ATLAS narratives (plan item 8)."""

from __future__ import annotations

from app.knowledge.soc_kb_retriever import retrieve_soc_kb


def test_atlas_case_study_narrative_retrievable_when_kb_enabled(monkeypatch) -> None:
    monkeypatch.setattr("app.config.settings.soc_kb_retrieval_enabled", True)
    result = retrieve_soc_kb(
        query="Data Exfiltration via an MCP Server used by Cursor",
        selected_skill="knowledge_recall",
        collection_ids=["mitre_atlas"],
    )
    entries = result.get("retrieved_entries") or []
    assert any(str(item.get("entry_id") or "").startswith("atlas-") for item in entries)
