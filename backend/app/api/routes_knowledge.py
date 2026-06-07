from __future__ import annotations

import csv
import io
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.auth.session import require_auth
from app.config import settings
from app.coverage.question_runtime_map import list_question_runtime_entries, load_question_runtime_map
from app.knowledge.import_prompt import build_extraction_prompt
from app.knowledge.soc_kb_intake_template import build_soc_kb_intake_template, soc_kb_intake_contract
from app.knowledge.repository import get_knowledge_repository
from app.knowledge.soc_kb_retriever import retrieve_soc_kb
from app.knowledge.validation import llm_import_contract, parse_import_payload, validate_import_batch
from app.knowledge.mapping_exports import (
    MITRE_METADATA_ROLE,
    build_skill_coverage_export_payload,
    github_intake_csv_rows,
    load_github_intake_register,
    load_markdown_export,
    load_use_case_catalog_export_rows,
    skill_coverage_csv_rows,
    use_case_catalog_csv_row,
)

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


@router.get("/knowledge/exports/{artifact}")
def export_mapping_artifact(
    artifact: str,
    file_format: str = Query("json", pattern="^(json|csv)$"),
) -> Response:
    """Download governed mapping/catalog artifacts for analyst review."""
    normalized = artifact.strip().lower().replace("-", "_")
    csv_rows: list[dict[str, Any]] | None = None
    payload: dict[str, Any]
    filename: str

    if normalized in {"question_runtime_map", "105_questions", "questions"}:
        rows = list_question_runtime_entries()
        payload = {
            "artifact": "question_runtime_map",
            "export_kind": "legacy_base",
            "format_version": load_question_runtime_map().get("map_version"),
            "mitre_metadata_role": MITRE_METADATA_ROLE,
            "row_count": len(rows),
            "rows": rows,
        }
        csv_rows = [_question_export_row(row) for row in rows]
        filename = f"ai_soc_question_runtime_map_105.{file_format}"
    elif normalized in {"use_case_catalog", "use_cases", "catalog"}:
        rows = load_use_case_catalog_export_rows()
        payload = {
            "artifact": "use_case_catalog",
            "export_kind": "catalog_with_enrichment_join",
            "mitre_metadata_role": MITRE_METADATA_ROLE,
            "row_count": len(rows),
            "rows": rows,
        }
        csv_rows = [use_case_catalog_csv_row(row) for row in rows]
        filename = f"ai_soc_use_case_catalog.{file_format}"
    elif normalized in {"skill_coverage_matrix", "coverage_matrix", "105_coverage"}:
        payload = build_skill_coverage_export_payload()
        csv_rows = skill_coverage_csv_rows()
        filename = f"ai_soc_skill_coverage_matrix_105.{file_format}"
    elif normalized in {"github_skill_intake_register", "github_intake", "skill_intake_register"}:
        register = load_github_intake_register()
        records = register.get("records") or []
        payload = {
            "artifact": "github_skill_intake_register",
            "source_file": "docs/skills/github_skill_intake_register.json",
            "usage_rule": register.get("usage_rule"),
            "row_count": len(records) if isinstance(records, list) else 0,
            "records": records,
        }
        csv_rows = github_intake_csv_rows()
        filename = f"ai_soc_github_skill_intake_register.{file_format}"
    elif normalized in {"skill_enrichment_status_matrix", "enrichment_status_matrix"}:
        payload = load_markdown_export("docs/skills/skill_enrichment_status_matrix.md")
        filename = "ai_soc_skill_enrichment_status_matrix.json"
        if file_format == "csv":
            raise HTTPException(status_code=400, detail="markdown_artifact_json_only")
    elif normalized in {"rejected_github_skills", "rejected_skills"}:
        payload = load_markdown_export("docs/skills/rejected_github_skills.md")
        filename = "ai_soc_rejected_github_skills.json"
        if file_format == "csv":
            raise HTTPException(status_code=400, detail="markdown_artifact_json_only")
    elif normalized in {"pending_skill_enrichment_backlog", "pending_backlog", "skill_backlog"}:
        payload = load_markdown_export("docs/skills/pending_skill_enrichment_backlog.md")
        filename = "ai_soc_pending_skill_enrichment_backlog.json"
        if file_format == "csv":
            raise HTTPException(status_code=400, detail="markdown_artifact_json_only")
    else:
        raise HTTPException(status_code=404, detail="unknown_export_artifact")

    if file_format == "csv":
        if csv_rows is None:
            raise HTTPException(status_code=400, detail="csv_not_supported_for_artifact")
        return _csv_response(csv_rows, filename)
    return Response(
        content=json.dumps(payload, indent=2, sort_keys=True),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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


def _question_export_row(row: dict[str, Any]) -> dict[str, Any]:
    registry = row.get("mitre_registry") if isinstance(row.get("mitre_registry"), dict) else {}
    return {
        "question_number": row.get("question_number"),
        "question_ref": row.get("question_ref"),
        "question": row.get("question"),
        "pattern_type": row.get("pattern_type"),
        "legacy_router_intent_hint": row.get("legacy_router_intent_hint"),
        "proposed_primary_skill": row.get("proposed_primary_skill"),
        "proposed_operation_type": row.get("proposed_operation_type"),
        "dependency_class": row.get("dependency_class"),
        "route_blocked": row.get("route_blocked"),
        "promotion_status": row.get("promotion_status"),
        "manifest_coverage_id": row.get("manifest_coverage_id"),
        "authority_pilot_candidate": row.get("authority_pilot_candidate"),
        "s3_authority_ready": row.get("s3_authority_ready"),
        "skill_drift": row.get("skill_drift"),
        "mitre_permitted": _join(row.get("mitre_permitted")),
        "mitre_candidate": _join(row.get("mitre_candidate")),
        "mitre_blocked": _join(row.get("mitre_blocked")),
        "mitre_registry_permitted": _join(registry.get("permitted")),
        "mitre_registry_candidate": _join(registry.get("candidate")),
        "mitre_registry_blocked": _join(registry.get("blocked")),
        "mitre_requires_evidence": row.get("mitre_requires_evidence"),
        "mitre_requires_alert_context": row.get("mitre_requires_alert_context"),
        "mitre_visibility_policy": row.get("mitre_visibility_policy"),
        "mitre_blocked_rationale": _json_cell(registry.get("blocked_rationale")),
        "mitre_metadata_role": MITRE_METADATA_ROLE,
    }


def _csv_response(rows: list[dict[str, Any]], filename: str) -> Response:
    output = io.StringIO()
    fieldnames = list(rows[0].keys()) if rows else []
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _join(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return "" if value is None else str(value)


def _json_cell(value: Any) -> str:
    if value is None:
        return ""
    return json.dumps(value, sort_keys=True)
