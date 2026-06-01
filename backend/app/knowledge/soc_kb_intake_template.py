"""P4-9: SOC RAG content intake template and approval metadata contract."""

from __future__ import annotations

from typing import Any

from app.knowledge.import_prompt import KB_JSON_SCHEMA_SKELETON, build_extraction_prompt
from app.knowledge.validation import (
    RUNTIME_APPROVAL_STATUSES,
    RUNTIME_STATUSES,
    SUPPORTED_ALLOWED_USE,
    SUPPORTED_DOCUMENT_TYPES,
    llm_import_contract,
    validate_import_batch,
)


def soc_kb_intake_contract() -> dict[str, Any]:
    """Machine-readable intake contract for COE/admin importers."""
    return {
        "schema_version": "p4_soc_kb_intake_v1",
        "runtime_use": False,
        "direct_rag_to_llm": False,
        "drafts_affect_runtime": False,
        "human_review_required": True,
        "supported_document_types": sorted(SUPPORTED_DOCUMENT_TYPES),
        "supported_allowed_use": sorted(SUPPORTED_ALLOWED_USE),
        "runtime_statuses": sorted(RUNTIME_STATUSES),
        "runtime_approval_statuses": sorted(RUNTIME_APPROVAL_STATUSES),
        "json_schema_skeleton": KB_JSON_SCHEMA_SKELETON,
        "llm_import": llm_import_contract(),
        "api_surfaces": [
            "GET /api/knowledge/import/contract",
            "GET /api/knowledge/import/prompt-template",
            "POST /api/knowledge/import/validate",
            "POST /api/knowledge/import/save-draft",
            "POST /api/knowledge/import/publish",
        ],
    }


def build_soc_kb_intake_template(
    *,
    collection_id: str | None = None,
    document_type: str | None = None,
    environment: str | None = None,
) -> dict[str, Any]:
    """Return offline extraction prompt + schema for governed SOC-KB intake."""
    prompt = build_extraction_prompt(
        collection_id=collection_id,
        document_type=document_type,
        environment=environment,
    )
    return {
        **soc_kb_intake_contract(),
        **prompt,
        "validate_import_batch": "use app.knowledge.validation.validate_import_batch",
    }
