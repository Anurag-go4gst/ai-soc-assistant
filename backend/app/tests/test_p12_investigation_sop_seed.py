"""P12 — curated SOP seed publishes through the existing repository path only."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.knowledge.repository import JsonKnowledgeRepository, load_soc_kb_store
from app.knowledge.seed.investigation_sop_seed import (
    SEED_DOCUMENTS,
    SEED_ENTRIES,
    seed_batch,
)
from app.knowledge.validation import validate_import_batch


@pytest.fixture()
def repository(tmp_path: Path) -> JsonKnowledgeRepository:
    for name in ("collections", "documents", "entries", "batches"):
        (tmp_path / f"{name}.json").write_text("[]", encoding="utf-8")
    return JsonKnowledgeRepository(
        collections_path=str(tmp_path / "collections.json"),
        documents_path=str(tmp_path / "documents.json"),
        entries_path=str(tmp_path / "entries.json"),
        import_batches_path=str(tmp_path / "batches.json"),
    )


def test_seed_batch_validates_cleanly() -> None:
    result = validate_import_batch(
        batch=seed_batch(),
        documents=SEED_DOCUMENTS,
        entries=SEED_ENTRIES,
        existing_documents=[],
    )
    assert result["validation_errors"] == [], result["validation_errors"]
    assert result["valid"] is True


def test_every_runtime_entry_carries_an_excerpt_and_citation() -> None:
    for entry in SEED_ENTRIES:
        assert entry["source_excerpt"].strip()
        assert entry["citation"].strip()
        assert entry["source_refs"]


def test_every_entry_belongs_to_a_seeded_document() -> None:
    doc_ids = {doc["doc_id"] for doc in SEED_DOCUMENTS}
    assert {entry["doc_id"] for entry in SEED_ENTRIES} <= doc_ids


def test_drafts_are_not_runtime_eligible_until_published(
    repository: JsonKnowledgeRepository,
) -> None:
    drafts = [
        {**doc, "status": "ready_for_review", "approval_status": "draft", "is_current_version": False}
        for doc in SEED_DOCUMENTS
    ]
    draft_entries = [
        {**entry, "status": "draft", "approval_status": "draft"} for entry in SEED_ENTRIES
    ]
    repository.save_import_batch(seed_batch(), drafts, draft_entries)
    published = repository.get_published_entries()
    assert not [item for item in published if item.get("entry_id", "").startswith("coe-new-external")]


def test_published_seed_is_retrievable_as_source_evidence(
    repository: JsonKnowledgeRepository,
) -> None:
    repository.save_import_batch(seed_batch(), SEED_DOCUMENTS, SEED_ENTRIES)
    for document in SEED_DOCUMENTS:
        repository.publish_document(document["doc_id"], approved_by="coe.soc")
    store = load_soc_kb_store(repository)
    published_ids = {str(entry.get("entry_id")) for entry in store.entries}
    assert "coe-new-external-endpoint-triage" in published_ids
    assert "coe-zero-day-exposure-assessment" in published_ids


def test_seed_is_idempotent_on_repeat_import(repository: JsonKnowledgeRepository) -> None:
    repository.save_import_batch(seed_batch(), SEED_DOCUMENTS, SEED_ENTRIES)
    repository.save_import_batch(seed_batch(), SEED_DOCUMENTS, SEED_ENTRIES)
    doc_ids = [doc["doc_id"] for doc in repository.list_documents()]
    assert len(doc_ids) == len(set(doc_ids))


def test_seed_module_defines_no_new_ingestion_pipeline() -> None:
    source = Path(
        __file__
    ).resolve().parents[1] / "knowledge" / "seed" / "investigation_sop_seed.py"
    text = source.read_text(encoding="utf-8")
    for forbidden in ("embedding", "vector_store", "chunker", "openai", "llm"):
        assert forbidden not in text.lower().replace("no direct rag-to-llm path", "")


def test_seed_answer_constraints_forbid_unsupported_conclusions() -> None:
    zero_day = next(
        entry for entry in SEED_ENTRIES if entry["entry_id"] == "coe-zero-day-exposure-assessment"
    )
    joined = " ".join(zero_day["answer_constraints"]).lower()
    assert "inconclusive" in joined
    firewall = next(
        entry for entry in SEED_ENTRIES if entry["entry_id"] == "coe-firewall-block-preconditions"
    )
    assert any("receipt" in item.lower() for item in firewall["answer_constraints"])


def test_seed_payload_is_json_serializable() -> None:
    json.dumps({"batch": seed_batch(), "documents": SEED_DOCUMENTS, "entries": SEED_ENTRIES})
