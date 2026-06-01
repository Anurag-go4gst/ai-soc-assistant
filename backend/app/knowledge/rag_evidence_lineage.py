"""P4: Governed RAG evidence origin and approval metadata for trace/sufficiency."""

from __future__ import annotations

from typing import Any

from app.config import settings

EVIDENCE_ORIGIN_STUB_RAG = "stub_rag"
EVIDENCE_ORIGIN_LIVE_RAG = "live_rag"
EVIDENCE_ORIGIN_STUB_MCP = "stub_mcp"
EVIDENCE_ORIGIN_LIVE_MCP = "live_mcp"
EVIDENCE_ORIGIN_REGISTRY_ONLY = "registry_only"
EVIDENCE_ORIGIN_NONE = "none"

ANSWER_READINESS_SYSTEM_CHECK = "system_check_only"
ANSWER_READINESS_PRODUCTION = "production"
ANSWER_READINESS_INSUFFICIENT = "insufficient"
ANSWER_READINESS_BLOCKED = "blocked"


def classify_rag_evidence_origin(*, retrieval: dict[str, Any] | None) -> str:
    """Classify SOC-KB provenance for deck labels and sufficiency."""
    if not settings.soc_kb_retrieval_enabled:
        return EVIDENCE_ORIGIN_NONE
    if not isinstance(retrieval, dict):
        return EVIDENCE_ORIGIN_NONE
    status = str(retrieval.get("retrieval_status") or "")
    if status == "disabled":
        return EVIDENCE_ORIGIN_NONE
    if status in {"failed", "no_match", "ambiguous"} and not retrieval.get("retrieved_entries"):
        return EVIDENCE_ORIGIN_NONE
    if _is_fixture_or_mock_rag_backend():
        return EVIDENCE_ORIGIN_STUB_RAG
    return EVIDENCE_ORIGIN_LIVE_RAG


def classify_mcp_evidence_origin(*, execution: dict[str, Any] | None) -> str | None:
    if not isinstance(execution, dict):
        return None
    if execution.get("status") != "executed":
        return None
    if settings.mcp_mode == "mock" or not settings.mcp_global_execution_enabled:
        return EVIDENCE_ORIGIN_STUB_MCP
    return EVIDENCE_ORIGIN_LIVE_MCP


def resolve_response_evidence_origin(
    *,
    source_evidence: list[dict[str, Any]],
    soc_kb_retrieval: dict[str, Any] | None,
    execution: dict[str, Any] | None,
) -> str:
    """Pick the primary evidence_origin label for a live /chat response."""
    mcp_origin = classify_mcp_evidence_origin(execution=execution)
    if mcp_origin:
        return mcp_origin
    for item in source_evidence:
        if item.get("source_type") == "rag":
            envelope_origin = item.get("evidence_origin")
            if isinstance(envelope_origin, str) and envelope_origin.strip():
                return envelope_origin.strip()
    rag_origin = classify_rag_evidence_origin(retrieval=soc_kb_retrieval)
    collected = [item for item in source_evidence if item.get("collection_status") == "collected"]
    if any(item.get("source_type") == "rag" for item in collected):
        return rag_origin
    if rag_origin == EVIDENCE_ORIGIN_STUB_RAG:
        return EVIDENCE_ORIGIN_STUB_RAG
    if collected:
        return EVIDENCE_ORIGIN_REGISTRY_ONLY
    return EVIDENCE_ORIGIN_NONE


def resolve_answer_readiness(
    *,
    evidence_origin: str,
    context_sufficiency: dict[str, Any] | None,
) -> str:
    if isinstance(context_sufficiency, dict):
        mode = str(context_sufficiency.get("status") or "")
        if mode in {"blocked_by_policy", "insufficient_evidence"}:
            return ANSWER_READINESS_BLOCKED if mode == "blocked_by_policy" else ANSWER_READINESS_INSUFFICIENT
    if evidence_origin in {EVIDENCE_ORIGIN_STUB_RAG, EVIDENCE_ORIGIN_STUB_MCP, EVIDENCE_ORIGIN_NONE, EVIDENCE_ORIGIN_REGISTRY_ONLY}:
        return ANSWER_READINESS_SYSTEM_CHECK
    if evidence_origin == EVIDENCE_ORIGIN_LIVE_RAG:
        return ANSWER_READINESS_PRODUCTION
    if evidence_origin == EVIDENCE_ORIGIN_LIVE_MCP:
        return ANSWER_READINESS_PRODUCTION
    return ANSWER_READINESS_SYSTEM_CHECK


def build_rag_approval_summary(retrieval: dict[str, Any] | None) -> dict[str, Any]:
    """Summarize approval metadata for retrieved SOC-KB rows (trace only)."""
    if not isinstance(retrieval, dict):
        return {"enabled": False, "authority": "metadata_only"}
    entries = retrieval.get("retrieved_entries") or []
    approval_statuses = sorted(
        {str(item.get("approval_status")) for item in entries if item.get("approval_status")}
    )
    document_types = sorted(
        {str(item.get("document_type")) for item in entries if item.get("document_type")}
    )
    return {
        "enabled": True,
        "authority": "metadata_only",
        "evidence_origin": classify_rag_evidence_origin(retrieval=retrieval),
        "retrieval_status": retrieval.get("retrieval_status"),
        "entry_count": len(entries),
        "approval_statuses": approval_statuses,
        "document_types": document_types,
        "all_runtime_eligible": all(item.get("validation_status") == "runtime_eligible" for item in entries)
        if entries
        else False,
        "direct_to_llm": False,
        "repository_backend": settings.soc_kb_repository_backend,
        "rag_mode": settings.rag_mode,
    }


def _is_fixture_or_mock_rag_backend() -> bool:
    if str(settings.rag_mode or "").strip().lower() == "mock":
        return True
    backend = str(settings.soc_kb_repository_backend or "").strip().lower()
    return backend in {"json", "fixture", "fixtures"}
