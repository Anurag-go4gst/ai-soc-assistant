from __future__ import annotations

import json

import pytest

from app.api.routes_knowledge import (
    import_prompt_template,
    publish_import,
    save_import_draft,
)
from app.knowledge import ambiguity_assist as assist_module
from app.knowledge.ambiguity_assist import run_ambiguity_assist
from app.knowledge.hybrid import apply_rerank
from app.knowledge.import_prompt import build_extraction_prompt
from app.knowledge.repository import JsonKnowledgeRepository, get_knowledge_repository
from app.knowledge.soc_kb_retriever import retrieve_soc_kb, soc_kb_status_summary


def _repo(tmp_path) -> JsonKnowledgeRepository:
    source = JsonKnowledgeRepository().load_store()
    paths = {
        "collections": tmp_path / "collections.json",
        "documents": tmp_path / "documents.json",
        "entries": tmp_path / "entries.json",
        "batches": tmp_path / "batches.json",
    }
    paths["collections"].write_text(json.dumps(source.collections), encoding="utf-8")
    paths["documents"].write_text(json.dumps(source.documents), encoding="utf-8")
    paths["entries"].write_text(json.dumps(source.entries), encoding="utf-8")
    paths["batches"].write_text("[]", encoding="utf-8")
    return JsonKnowledgeRepository(
        collections_path=str(paths["collections"]),
        documents_path=str(paths["documents"]),
        entries_path=str(paths["entries"]),
        import_batches_path=str(paths["batches"]),
    )


def _point_repo_factory(monkeypatch, repo: JsonKnowledgeRepository) -> None:
    monkeypatch.setattr("app.api.routes_knowledge.get_knowledge_repository", lambda: repo)


def _draft_payload(*, risk_level: str = "medium", include_source_refs: bool = True) -> dict:
    doc = {
        "doc_id": "import-auth-sop-v9",
        "canonical_doc_id": "import-auth-sop",
        "collection_id": "soc_sop",
        "title": "Imported Auth SOP",
        "document_type": "sop",
        "environment": "coe",
        "version": "9.0",
        "status": "draft",
        "approval_status": "draft",
        "allowed_use": ["hil_guidance"],
        "risk_level": risk_level,
    }
    entry = {
        "entry_id": "import-auth-sop-v9-entry",
        "doc_id": "import-auth-sop-v9",
        "collection_id": "soc_sop",
        "title": "Imported escalation rule",
        "entry_type": "procedure",
        "source_excerpt": "Escalate repeated auth failures to tier 2.",
        "retrieval_hints": ["imported escalation rule unique marker"],
        "positive_examples": ["repeated auth failures escalation"],
        "allowed_use": ["hil_guidance"],
        "risk_level": risk_level,
        "status": "draft",
        "approval_status": "draft",
    }
    if include_source_refs:
        entry["source_refs"] = ["import.md#esc"]
    if risk_level in {"high", "critical"}:
        entry["positive_examples"] = ["repeated auth failures escalation"]
        entry["test_cases"] = [{"query": "repeated auth failures", "expected": "escalate tier 2"}]
    raw = {"documents": [doc], "entries": [entry]}
    return {"raw_json": json.dumps(raw), "source_file_name": "import.json", "generated_by": "llm_extraction", "checksum_sha256": "llm-extraction-placeholder"}


# 1 + 2: prompt template generated, says JSON-only and do-not-invent.
def test_extraction_prompt_says_json_only_and_do_not_invent() -> None:
    prompt = build_extraction_prompt(collection_id="soc_sop", document_type="sop", environment="coe")
    text = prompt["prompt"].lower()
    assert "valid json only" in text
    assert "do not invent" in text
    assert prompt["runtime_use"] is False
    assert prompt["drafts_affect_runtime"] is False
    assert "documents" in prompt["schema"] and "entries" in prompt["schema"]


def test_prompt_template_endpoint_returns_prompt() -> None:
    result = import_prompt_template(collection_id="soc_sop", document_type="sop", environment="coe")
    assert result["prompt"]
    assert result["generated_by"] == "llm_extraction"


# 3 + 4: uploaded JSON saved as draft only; draft not retrievable at runtime.
def test_save_draft_persists_draft_only_and_not_retrievable(tmp_path, monkeypatch) -> None:
    repo = _repo(tmp_path)
    _point_repo_factory(monkeypatch, repo)
    monkeypatch.setattr("app.knowledge.soc_kb_retriever.settings.soc_kb_retrieval_enabled", True)

    result = save_import_draft(_draft_payload())
    assert result["published"] is False
    assert result["drafts_affect_runtime"] is False

    saved_doc = repo.get_document("import-auth-sop-v9")
    assert saved_doc["status"] == "draft"
    assert saved_doc["approval_status"] == "draft"

    runtime = retrieve_soc_kb(query="imported escalation rule unique marker", selected_skill="attack_discovery", allowed_use=["hil_guidance"], repository=repo)
    assert "import-auth-sop-v9-entry" not in {item["entry_id"] for item in runtime["retrieved_entries"]}


# 5: validation catches missing source_refs for high-risk entries.
def test_validation_catches_missing_source_refs_high_risk(tmp_path, monkeypatch) -> None:
    repo = _repo(tmp_path)
    _point_repo_factory(monkeypatch, repo)
    with pytest.raises(Exception) as exc:
        save_import_draft(_draft_payload(risk_level="high", include_source_refs=False))
    detail = getattr(exc.value, "detail", {})
    assert "medium_high_critical_entries_require_source_refs" in detail.get("validation_errors", [])


# 6: publish makes valid current approved entry retrievable.
def test_publish_makes_entry_retrievable(tmp_path, monkeypatch) -> None:
    repo = _repo(tmp_path)
    _point_repo_factory(monkeypatch, repo)
    monkeypatch.setattr("app.knowledge.soc_kb_retriever.settings.soc_kb_retrieval_enabled", True)

    save_import_draft(_draft_payload())
    publish_import({"doc_ids": ["import-auth-sop-v9"], "approved_by": "coe.lead"})

    published = repo.get_document("import-auth-sop-v9")
    assert published["status"] == "published"
    assert published["is_current_version"] is True

    runtime = retrieve_soc_kb(query="imported escalation rule unique marker", selected_skill="attack_discovery", allowed_use=["hil_guidance"], repository=repo)
    assert "import-auth-sop-v9-entry" in {item["entry_id"] for item in runtime["retrieved_entries"]}


# 7: manual edit changes validation result.
def test_manual_edit_changes_validation(tmp_path, monkeypatch) -> None:
    repo = _repo(tmp_path)
    _point_repo_factory(monkeypatch, repo)
    bad = _draft_payload(risk_level="high", include_source_refs=False)
    with pytest.raises(Exception):
        save_import_draft(bad)
    # Manual edit: add the missing source_refs and required high-risk fields.
    fixed = _draft_payload(risk_level="high", include_source_refs=True)
    result = save_import_draft(fixed)
    assert result["published"] is False
    assert repo.get_document("import-auth-sop-v9") is not None


# 8: reranker disabled by default.
def test_reranker_disabled_by_default() -> None:
    status = soc_kb_status_summary()
    assert status["reranker_enabled"] is False


# 9: reranker cannot add candidates.
def test_reranker_cannot_add_candidates(monkeypatch) -> None:
    monkeypatch.setattr("app.knowledge.hybrid.settings.soc_kb_reranker_enabled", True)

    class InjectingReranker:
        def rerank(self, query, candidates):
            return [{"entry_id": "invented"}, *candidates]

    monkeypatch.setattr("app.knowledge.hybrid.reranker", lambda: InjectingReranker())
    candidates = [{"entry_id": "real-a", "confidence": 0.9}, {"entry_id": "real-b", "confidence": 0.8}]
    warnings: list[str] = []
    ranked = apply_rerank("q", candidates, warnings)
    assert "invented" not in {item["entry_id"] for item in ranked}
    assert "reranker_dropped_unknown_candidates" in warnings


# 10: reranker failure falls back safely.
def test_reranker_failure_falls_back(monkeypatch) -> None:
    monkeypatch.setattr("app.knowledge.hybrid.settings.soc_kb_reranker_enabled", True)

    class FailingReranker:
        def rerank(self, query, candidates):
            raise RuntimeError("boom")

    monkeypatch.setattr("app.knowledge.hybrid.reranker", lambda: FailingReranker())
    candidates = [{"entry_id": "real-a", "confidence": 0.9}]
    warnings: list[str] = []
    ranked = apply_rerank("q", candidates, warnings)
    assert [item["entry_id"] for item in ranked] == ["real-a"]
    assert any(w.startswith("reranker_failed_fallback_deterministic") for w in warnings)


# 11: ambiguity assist disabled by default.
def test_ambiguity_assist_disabled_by_default() -> None:
    out = run_ambiguity_assist(query="q", eligible_candidates=[{"entry_id": "a"}], retrieval_status="ambiguous")
    assert out is None
    status = soc_kb_status_summary()
    assert status["ambiguity_assist"]["enabled"] is False


# 12: ambiguity assist only sees eligible candidates.
def test_ambiguity_assist_sees_only_eligible(monkeypatch) -> None:
    monkeypatch.setattr("app.knowledge.ambiguity_assist.settings.soc_kb_llm_ambiguity_assist_enabled", True)
    monkeypatch.setattr("app.knowledge.ambiguity_assist.settings.soc_kb_llm_ambiguity_provider", "mock")
    monkeypatch.setattr(assist_module, "_resolve_assist_provider", lambda: ("mock", True))
    monkeypatch.setattr("app.knowledge.ambiguity_assist.settings.soc_kb_llm_ambiguity_max_candidates", 2)

    seen: dict = {}

    class SpyModel:
        def assess(self, payload):
            seen["candidates"] = payload["candidates"]
            return {"selected_entry_ids": [payload["candidates"][0]["entry_id"]], "ambiguity_reason": "ok", "needs_human_review": False, "confidence": 0.9}

    eligible = [{"entry_id": "a", "confidence": 0.9}, {"entry_id": "b", "confidence": 0.8}, {"entry_id": "c", "confidence": 0.7}]
    out = run_ambiguity_assist(query="q", eligible_candidates=eligible, retrieval_status="ambiguous", model=SpyModel())
    assert out["ran"] is True
    assert len(seen["candidates"]) == 2  # capped by max_candidates
    assert {c["entry_id"] for c in seen["candidates"]} == {"a", "b"}


# 13: ambiguity assist cannot invent entry IDs.
def test_ambiguity_assist_ignores_unknown_ids(monkeypatch) -> None:
    monkeypatch.setattr("app.knowledge.ambiguity_assist.settings.soc_kb_llm_ambiguity_assist_enabled", True)
    monkeypatch.setattr("app.knowledge.ambiguity_assist.settings.soc_kb_llm_ambiguity_provider", "mock")
    monkeypatch.setattr(assist_module, "_resolve_assist_provider", lambda: ("mock", True))

    class InventingModel:
        def assess(self, payload):
            return {"selected_entry_ids": ["a", "ghost-entry"], "ambiguity_reason": "x", "needs_human_review": False, "confidence": 0.9}

    eligible = [{"entry_id": "a", "confidence": 0.9}]
    out = run_ambiguity_assist(query="q", eligible_candidates=eligible, retrieval_status="ambiguous", model=InventingModel())
    assert out["selected_entry_ids"] == ["a"]
    assert "ambiguity_assist_ignored_unknown_entry_id" in out["warnings"]


def test_ambiguity_assist_provider_unavailable_defers_to_hil(monkeypatch) -> None:
    monkeypatch.setattr("app.knowledge.ambiguity_assist.settings.soc_kb_llm_ambiguity_assist_enabled", True)
    monkeypatch.setattr("app.knowledge.ambiguity_assist.settings.soc_kb_llm_ambiguity_provider", "ghost-provider")
    out = run_ambiguity_assist(query="q", eligible_candidates=[{"entry_id": "a"}], retrieval_status="ambiguous")
    assert out["ran"] is False
    assert out["needs_human_review"] is True
    assert "ambiguity_assist_provider_unavailable" in out["warnings"]


# 14 + 15: direct_to_llm remains false, no final synthesis added.
def test_no_direct_to_llm_and_no_final_synthesis(monkeypatch) -> None:
    monkeypatch.setattr("app.knowledge.soc_kb_retriever.settings.soc_kb_retrieval_enabled", True)
    result = retrieve_soc_kb(query="failed login spike brute force", selected_skill="attack_discovery")
    assert result["direct_to_llm"] is False
    status = soc_kb_status_summary()
    assert status["direct_to_llm"] is False
    assert status["final_synthesis_enabled"] is False


# 16: no Splunk telemetry write path exists in the knowledge layer.
def test_no_splunk_telemetry_write_in_knowledge_layer() -> None:
    import pathlib

    knowledge_dir = pathlib.Path(__file__).resolve().parents[1] / "knowledge"
    for path in knowledge_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        assert "splunk_run" not in text
        assert "write_telemetry_to_splunk" not in text
