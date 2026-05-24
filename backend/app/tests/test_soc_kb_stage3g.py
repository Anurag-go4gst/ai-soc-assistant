from __future__ import annotations

import json
from copy import deepcopy

from app.api.routes_knowledge import test_retrieval as knowledge_retrieval_endpoint
from app.knowledge.hybrid import apply_rerank
from app.knowledge.rag_collection_selector import select_rag_collections
from app.knowledge.repository import JsonKnowledgeRepository, load_soc_kb_store
from app.knowledge.soc_kb_retriever import retrieve_soc_kb
from app.knowledge.validation import validate_import_batch


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


def _draft_doc(version: str = "2.0") -> dict:
    return {
        "doc_id": f"coe-auth-sop-v{version}",
        "collection_id": "soc_sop",
        "title": "COE Sample Auth SOP New Version",
        "document_type": "sop",
        "namespace": "auth",
        "domain": "identity",
        "environment": "coe",
        "version": version,
        "status": "draft",
        "approval_status": "draft",
        "allowed_use": ["hil_guidance"],
        "risk_level": "medium",
        "canonical_doc_id": "coe-auth-sop",
        "is_current_version": False,
        "effective_from": "2026-04-03T00:00:00Z",
    }


def _draft_entry(doc_id: str) -> dict:
    return {
        "entry_id": f"{doc_id}-entry",
        "doc_id": doc_id,
        "doc_version": "2.0",
        "collection_id": "soc_sop",
        "title": "New Auth SOP Entry",
        "entry_type": "procedure",
        "source_excerpt": "Approved sample guidance after publish.",
        "source_refs": ["new.md#AUTH"],
        "retrieval_hints": ["approved sample guidance after publish"],
        "positive_examples": ["failed login spike"],
        "allowed_use": ["hil_guidance"],
        "risk_level": "medium",
        "status": "draft",
        "approval_status": "draft",
    }


def test_repository_abstraction_and_collection_selector(monkeypatch) -> None:
    monkeypatch.setattr("app.knowledge.soc_kb_retriever.settings.soc_kb_retrieval_enabled", True)
    repo = JsonKnowledgeRepository()
    store = load_soc_kb_store(repo)
    assert len(store.collections) >= 8
    assert len(store.documents) >= 10
    assert len(store.entries) >= 13

    selected = select_rag_collections(
        query="failed login attack discovery needs review",
        selected_skill="attack_discovery",
        workflow_stage="context",
        workflow_plan={"required_sources": ["rag:sop"]},
        required_sources=["rag:sop"],
        environment="coe",
        allowed_use=["hil_guidance", "mitre_grounding", "environment_grounding", "synthesis_context"],
        human_review={"required": True},
        execution_block_reason="mcp_global_execution_disabled",
        repository=repo,
    )
    assert {"soc_sop", "mitre_enterprise", "splunk_context", "escalation_matrix"}.issubset(set(selected["selected_collections"]))

    spl = select_rag_collections(
        query="generate SPL failed auth by user",
        selected_skill="spl_generation",
        workflow_stage="spl_generation",
        workflow_plan={},
        required_sources=[],
        environment="coe",
        allowed_use=["spl_generation", "validation", "tool_selection"],
        repository=repo,
    )
    assert {"detection_notes", "splunk_context", "mcp_tool_policy"}.issubset(set(spl["selected_collections"]))


def test_import_validation_lifecycle_publish_supersedes_and_runtime_filters(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.knowledge.soc_kb_retriever.settings.soc_kb_retrieval_enabled", True)
    repo = _repo(tmp_path)
    doc = _draft_doc()
    entry = _draft_entry(doc["doc_id"])
    batch = {
        "source_file_name": "new_auth_sop.json",
        "checksum_sha256": "checksum",
        "target_collection_id": "soc_sop",
        "environment": "coe",
        "generated_by": "llm_extraction",
    }
    validation = validate_import_batch(batch=batch, documents=[doc], entries=[entry], existing_documents=repo.list_documents())
    assert validation["valid"] is True
    saved = repo.save_import_batch({**batch, **validation}, [doc], [entry])
    assert saved["status"] == "ready_for_review"

    draft_result = retrieve_soc_kb(query="approved sample guidance after publish", selected_skill="attack_discovery", allowed_use=["hil_guidance"], repository=repo)
    assert entry["entry_id"] not in {item["entry_id"] for item in draft_result["retrieved_entries"]}

    published = repo.publish_document(doc["doc_id"], approved_by="coe.lead")
    assert published["is_current_version"] is True
    old = repo.get_document("coe-auth-sop-v1")
    assert old and old["is_current_version"] is False
    assert old["superseded_by_doc_id"] == doc["doc_id"]

    runtime = retrieve_soc_kb(query="approved sample guidance after publish", selected_skill="attack_discovery", allowed_use=["hil_guidance"], repository=repo)
    assert entry["entry_id"] in {item["entry_id"] for item in runtime["retrieved_entries"]}

    retired = repo.retire_document(doc["doc_id"])
    assert retired["status"] == "retired"
    after_retire = retrieve_soc_kb(query="approved sample guidance after publish", selected_skill="attack_discovery", allowed_use=["hil_guidance"], repository=repo)
    assert entry["entry_id"] not in {item["entry_id"] for item in after_retire["retrieved_entries"]}


def test_validation_catches_missing_fields_and_high_risk_source_requirements() -> None:
    bad_doc = {"doc_id": "bad", "document_type": "unsupported", "status": "published", "approval_status": "draft", "allowed_use": ["bad_use"]}
    bad_entry = {"entry_id": "bad-entry", "doc_id": "bad", "collection_id": "soc_sop", "title": "Bad", "entry_type": "procedure", "allowed_use": ["hil_guidance"], "status": "published", "approval_status": "coe_reviewed", "risk_level": "high"}
    result = validate_import_batch(batch={"source_file_name": "bad.json"}, documents=[bad_doc], entries=[bad_entry])
    assert result["valid"] is False
    assert "document.collection_id_required" in result["validation_errors"]
    assert "unsupported_document_type" in result["validation_errors"]
    assert "unsupported_allowed_use" in result["validation_errors"]
    assert "runtime_entries_require_source_excerpt" in result["validation_errors"]
    assert "high_critical_entries_require_test_cases" in result["validation_errors"]


def test_hybrid_vector_graph_and_reranker_cannot_add_unapproved_candidates(monkeypatch) -> None:
    monkeypatch.setattr("app.knowledge.soc_kb_retriever.settings.soc_kb_retrieval_enabled", True)
    monkeypatch.setattr("app.knowledge.soc_kb_retriever.settings.soc_kb_retrieval_mode", "hybrid")
    monkeypatch.setattr("app.knowledge.hybrid.settings.soc_kb_retrieval_mode", "hybrid")
    monkeypatch.setattr("app.knowledge.hybrid.settings.soc_kb_vector_backend", "mock")
    monkeypatch.setattr("app.knowledge.soc_kb_retriever.settings.soc_kb_graph_expansion_enabled", True)
    result = retrieve_soc_kb(query="failed login spl generation", selected_skill="spl_generation", allowed_use=["spl_generation", "validation"], max_results=5)
    assert result["retrieval_mode"] == "hybrid"
    assert result["vector_backend"] == "mock"
    assert not any(item["approval_status"] == "draft" for item in result["retrieved_entries"])
    assert not any(item["status"] == "draft" for item in result["retrieved_entries"])

    candidates = deepcopy(result["retrieved_entries"])
    monkeypatch.setattr("app.knowledge.hybrid.settings.soc_kb_reranker_enabled", True)

    class InjectingReranker:
        def rerank(self, query, candidates):
            return [{"entry_id": "invented-candidate"}, *candidates]

    monkeypatch.setattr("app.knowledge.hybrid.reranker", lambda: InjectingReranker())
    reranked = apply_rerank("failed login", candidates)
    assert "invented-candidate" not in {item["entry_id"] for item in reranked}


def test_ambiguity_metadata_source_evidence_and_admin_endpoint(monkeypatch) -> None:
    monkeypatch.setattr("app.knowledge.soc_kb_retriever.settings.soc_kb_retrieval_enabled", True)
    result = retrieve_soc_kb(query="auth failed login brute force T1110", selected_skill="attack_discovery", max_results=3)
    assert result["retrieval_status"] in {"retrieved", "ambiguous"}
    assert result["llm_ambiguity_assist_enabled"] is False
    if result["retrieved_entries"]:
        row = result["retrieved_entries"][0]
        assert "retrieval_stage_scores" in row
        assert row["is_current_version"] is True

    payload = knowledge_retrieval_endpoint(query="failed login spike brute force")
    assert "retrieved_entries" in payload
    assert payload["direct_to_llm"] is False
