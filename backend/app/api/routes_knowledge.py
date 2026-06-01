from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.session import require_auth
from app.config import settings
from app.knowledge.import_prompt import build_extraction_prompt
from app.knowledge.soc_kb_intake_template import build_soc_kb_intake_template, soc_kb_intake_contract
from app.knowledge.repository import get_knowledge_repository
from app.knowledge.soc_kb_retriever import retrieve_soc_kb
from app.knowledge.validation import llm_import_contract, parse_import_payload, validate_import_batch

router = APIRouter(dependencies=[Depends(require_auth)])


@router.get("/knowledge/collections")
def list_collections() -> dict[str, Any]:
    repo = get_knowledge_repository()
    return {"collections": repo.list_collections(), "count": len(repo.list_collections())}


@router.get("/knowledge/documents")
def list_documents() -> dict[str, Any]:
    repo = get_knowledge_repository()
    docs = [_safe_document(doc) for doc in repo.list_documents()]
    return {"documents": docs, "count": len(docs)}


@router.get("/knowledge/documents/{doc_id}")
def get_document(doc_id: str) -> dict[str, Any]:
    repo = get_knowledge_repository()
    doc = repo.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="document_not_found")
    entries = [_safe_entry(entry) for entry in repo.list_entries() if entry.get("doc_id") == doc_id]
    return {"document": _safe_document(doc), "entries": entries}


@router.get("/knowledge/entries")
def list_entries(doc_id: str | None = None) -> dict[str, Any]:
    repo = get_knowledge_repository()
    entries = [_safe_entry(entry) for entry in repo.list_entries() if doc_id is None or entry.get("doc_id") == doc_id]
    return {"entries": entries, "count": len(entries)}


@router.get("/knowledge/import/contract")
def import_contract() -> dict[str, Any]:
    return llm_import_contract()


@router.get("/knowledge/intake/contract")
def intake_contract() -> dict[str, Any]:
    """P4-9: Full SOC-KB intake schema, approval metadata, and API map."""
    return soc_kb_intake_contract()


@router.get("/knowledge/import/prompt-template")
def import_prompt_template(
    collection_id: str | None = None,
    document_type: str | None = None,
    environment: str | None = None,
) -> dict[str, Any]:
    return build_soc_kb_intake_template(
        collection_id=collection_id,
        document_type=document_type,
        environment=environment,
    )


@router.post("/knowledge/import/validate")
def validate_import(payload: dict[str, Any]) -> dict[str, Any]:
    repo = get_knowledge_repository()
    batch, documents, entries = parse_import_payload(payload)
    result = validate_import_batch(batch=batch, documents=documents, entries=entries, existing_documents=repo.list_documents())
    return {"import_batch": batch, "documents": documents, "entries": entries, **result}


@router.post("/knowledge/import/save-draft")
def save_import_draft(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and persist an extracted batch as draft only — never publishes.

    Saved documents/entries stay draft/ready_for_review and do not affect runtime
    retrieval until a later explicit publish step.
    """
    repo = get_knowledge_repository()
    batch, documents, entries = parse_import_payload(payload)
    validation = validate_import_batch(batch=batch, documents=documents, entries=entries, existing_documents=repo.list_documents())
    if not validation["valid"]:
        raise HTTPException(status_code=400, detail=validation)
    batch = {**batch, **validation, "status": "ready_for_review"}
    saved = repo.save_import_batch(batch, documents, entries)
    return {"import_batch": saved, "validation": validation, "published": False, "drafts_affect_runtime": False}


@router.post("/knowledge/import/publish")
def publish_import(payload: dict[str, Any]) -> dict[str, Any]:
    repo = get_knowledge_repository()
    approved_by = str(payload.get("approved_by") or "admin")

    # Path A: publish already-saved drafts referenced by doc_ids (manual-edit loop).
    doc_ids = [str(doc_id) for doc_id in (payload.get("doc_ids") or []) if doc_id]
    if doc_ids:
        existing = repo.list_documents()
        existing_entries = repo.list_entries()
        targets = [doc for doc in existing if str(doc.get("doc_id")) in set(doc_ids)]
        if len(targets) != len(set(doc_ids)):
            raise HTTPException(status_code=404, detail="one_or_more_documents_not_found")
        target_entries = [entry for entry in existing_entries if entry.get("doc_id") in set(doc_ids)]
        validation = validate_import_batch(batch={}, documents=targets, entries=target_entries, existing_documents=existing)
        if not validation["valid"]:
            raise HTTPException(status_code=400, detail=validation)
        published_docs = [repo.publish_document(doc_id, approved_by=approved_by) for doc_id in doc_ids]
        return {"published_documents": [_safe_document(doc) for doc in published_docs], "validation": validation}

    # Path B: validate + save + publish a fresh payload in one shot.
    batch, documents, entries = parse_import_payload(payload)
    validation = validate_import_batch(batch=batch, documents=documents, entries=entries, existing_documents=repo.list_documents())
    if not validation["valid"]:
        raise HTTPException(status_code=400, detail=validation)
    batch = {**batch, **validation, "status": "ready_for_review"}
    saved = repo.save_import_batch(batch, documents, entries)
    published_docs = [repo.publish_document(str(doc["doc_id"]), approved_by=approved_by) for doc in documents]
    return {"import_batch": saved, "published_documents": [_safe_document(doc) for doc in published_docs], "validation": validation}


@router.post("/knowledge/documents/{doc_id}/retire")
def retire_document(doc_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    repo = get_knowledge_repository()
    try:
        doc = repo.retire_document(doc_id, retired_by=str((payload or {}).get("retired_by") or "admin"))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"document": _safe_document(doc)}


@router.get("/knowledge/retrieval/test")
def test_retrieval(
    query: str = Query(..., min_length=1),
    selected_skill: str = "attack_discovery",
    allowed_use: str | None = None,
    environment: str | None = None,
) -> dict[str, Any]:
    uses = [item.strip() for item in allowed_use.split(",") if item.strip()] if allowed_use else None
    result = retrieve_soc_kb(query=query, selected_skill=selected_skill, allowed_use=uses, environment=environment or settings.soc_kb_environment)
    return result


def _safe_document(doc: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "doc_id",
        "collection_id",
        "title",
        "document_type",
        "namespace",
        "domain",
        "environment",
        "version",
        "revision",
        "status",
        "approval_status",
        "lifecycle_stage",
        "allowed_use",
        "risk_level",
        "sensitivity",
        "checksum_sha256",
        "superseded_by_doc_id",
        "canonical_doc_id",
        "is_current_version",
        "effective_from",
        "effective_to",
        "import_batch_id",
        "validation_warnings",
    )
    return {key: doc.get(key) for key in keys}


def _safe_entry(entry: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "entry_id",
        "doc_id",
        "doc_version",
        "collection_id",
        "title",
        "section_id",
        "entry_type",
        "source_excerpt",
        "source_refs",
        "citation",
        "allowed_use",
        "reviewer_role",
        "recommended_actions",
        "risk_level",
        "sensitivity",
        "status",
        "approval_status",
        "import_batch_id",
    )
    return {key: entry.get(key) for key in keys}
