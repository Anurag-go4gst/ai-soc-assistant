from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

SUPPORTED_ALLOWED_USE = {
    "routing",
    "spl_generation",
    "validation",
    "hil_guidance",
    "synthesis_context",
    "mitre_grounding",
    "asset_context",
    "tool_selection",
    "environment_grounding",
}
SUPPORTED_DOCUMENT_TYPES = {
    "sop",
    "playbook",
    "splunk_context_document",
    "detection_engineering_note",
    "mitre_enterprise_reference",
    "mitre_ics_reference",
    "escalation_matrix",
    "asset_policy",
    "mcp_tool_policy",
    "customer_context",
    "runbook",
    "other",
}
RUNTIME_STATUSES = {"active", "published"}
RUNTIME_APPROVAL_STATUSES = {"coe_reviewed", "pgcil_approved"}


def parse_import_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    candidate: Any = payload
    if "raw_json" in payload and isinstance(payload["raw_json"], str):
        candidate = json.loads(payload["raw_json"])
    elif "llm_extracted_kb_json" in payload and isinstance(payload["llm_extracted_kb_json"], str):
        candidate = json.loads(payload["llm_extracted_kb_json"])
    elif "uploaded_document_text" in payload and payload.get("documents") is None:
        candidate = {
            "import_batch": {
                "source_file_name": payload.get("source_file_name") or "pasted_document.txt",
                "source_type": "text",
                "target_collection_id": payload.get("target_collection_id"),
                "environment": payload.get("environment"),
                "generated_by": "llm_extraction",
                "status": "uploaded",
                "source_document_ref": "pasted_text",
            },
            "documents": [],
            "entries": [],
        }
    batch = dict(candidate.get("import_batch") or candidate.get("batch") or {})
    batch.setdefault("source_file_name", payload.get("source_file_name"))
    batch.setdefault("source_type", payload.get("source_type") or "json")
    batch.setdefault("target_collection_id", payload.get("target_collection_id"))
    batch.setdefault("environment", payload.get("environment"))
    batch.setdefault("imported_by", payload.get("imported_by"))
    batch.setdefault("generated_by", payload.get("generated_by") or ("llm_extraction" if payload.get("llm_extracted_kb_json") else "manual_json"))
    batch.setdefault("source_document_ref", payload.get("source_document_ref"))
    batch.setdefault("checksum_sha256", payload.get("checksum_sha256"))
    return batch, list(candidate.get("documents") or []), list(candidate.get("entries") or [])


def validate_import_batch(
    *,
    batch: dict[str, Any],
    documents: list[dict[str, Any]],
    entries: list[dict[str, Any]],
    existing_documents: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    existing_documents = existing_documents or []
    doc_ids = {doc.get("doc_id") for doc in documents}
    if not documents:
        errors.append("documents_required")
    for doc in documents:
        _validate_document(doc, documents, existing_documents, errors, warnings)
    for entry in entries:
        _validate_entry(entry, doc_ids, errors, warnings)
    if batch.get("source_file_name") and not batch.get("checksum_sha256"):
        errors.append("checksum_sha256_required_when_source_file_exists")
    if batch.get("generated_by") == "llm_extraction":
        warnings.append("llm_extraction_is_draft_only_until_human_publish")
    return {
        "valid": not errors,
        "status": "ready_for_review" if not errors else "validation_failed",
        "validation_errors": sorted(set(errors)),
        "validation_warnings": sorted(set(warnings)),
        "document_count": len(documents),
        "entry_count": len(entries),
    }


def llm_import_contract() -> dict[str, Any]:
    return {
        "runtime_use": False,
        "conversion_scope": "offline_admin_only",
        "extraction_prompt_template": (
            "Extract only source-grounded SOC KB documents and entries. Preserve source excerpts and refs. "
            "Mark all proposed documents and entries as draft/ready_for_review."
        ),
        "human_review_required": True,
        "drafts_affect_runtime": False,
        "llm_can_retrieve_sources": False,
        "llm_can_invent_entries": False,
    }


def _validate_document(
    doc: dict[str, Any],
    batch_docs: list[dict[str, Any]],
    existing_docs: list[dict[str, Any]],
    errors: list[str],
    warnings: list[str],
) -> None:
    for field in ("collection_id", "doc_id", "title", "document_type", "version", "status", "approval_status", "allowed_use", "environment"):
        if not doc.get(field):
            errors.append(f"document.{field}_required")
    if doc.get("document_type") and doc.get("document_type") not in SUPPORTED_DOCUMENT_TYPES:
        errors.append("unsupported_document_type")
    unsupported_uses = set(doc.get("allowed_use") or []) - SUPPORTED_ALLOWED_USE
    if unsupported_uses:
        errors.append("unsupported_allowed_use")
    if doc.get("approval_status") in {"draft", "rejected"} and doc.get("status") in RUNTIME_STATUSES:
        errors.append("no_runtime_eligibility_for_draft_or_rejected_approval")
    if _expired(doc):
        errors.append("expired_documents_cannot_be_published")
    if doc.get("superseded_by_doc_id") and bool(doc.get("is_current_version", False)):
        errors.append("superseded_documents_cannot_be_current")
    canonical = doc.get("canonical_doc_id") or doc.get("doc_id")
    current_docs = [
        item
        for item in [*existing_docs, *batch_docs]
        if (item.get("canonical_doc_id") or item.get("doc_id")) == canonical and bool(item.get("is_current_version", False)) and not item.get("superseded_by_doc_id")
        and item.get("status") in RUNTIME_STATUSES
        and item.get("approval_status") in RUNTIME_APPROVAL_STATUSES
    ]
    if len({item.get("doc_id") for item in current_docs}) > 1:
        errors.append("duplicate_current_version_for_canonical_doc_id")
    if doc.get("status") in {"uploaded", "parsed", "ready_for_review"}:
        warnings.append("pre_publish_documents_do_not_affect_runtime")


def _validate_entry(entry: dict[str, Any], doc_ids: set[Any], errors: list[str], warnings: list[str]) -> None:
    for field in ("entry_id", "doc_id", "collection_id", "title", "entry_type", "allowed_use", "status", "approval_status"):
        if not entry.get(field):
            errors.append(f"entry.{field}_required")
    if entry.get("doc_id") not in doc_ids:
        errors.append("entry_doc_id_missing_from_batch")
    unsupported_uses = set(entry.get("allowed_use") or []) - SUPPORTED_ALLOWED_USE
    if unsupported_uses:
        errors.append("unsupported_allowed_use")
    if entry.get("status") in RUNTIME_STATUSES and not entry.get("source_excerpt"):
        errors.append("runtime_entries_require_source_excerpt")
    risk = str(entry.get("risk_level") or "low")
    if risk in {"medium", "high", "critical"} and not entry.get("source_refs"):
        errors.append("medium_high_critical_entries_require_source_refs")
    if risk in {"high", "critical"}:
        if not entry.get("positive_examples"):
            errors.append("high_critical_entries_require_positive_examples")
        if not entry.get("test_cases"):
            errors.append("high_critical_entries_require_test_cases")
    if entry.get("approval_status") in {"draft", "rejected"} and entry.get("status") in RUNTIME_STATUSES:
        errors.append("no_runtime_eligibility_for_draft_or_rejected_approval")
    if entry.get("status") in {"uploaded", "parsed", "ready_for_review"}:
        warnings.append("pre_publish_entries_do_not_affect_runtime")


def _expired(doc: dict[str, Any]) -> bool:
    effective_to = doc.get("effective_to")
    if not effective_to:
        return False
    return datetime.fromisoformat(str(effective_to).replace("Z", "+00:00")) < datetime.now(UTC)
