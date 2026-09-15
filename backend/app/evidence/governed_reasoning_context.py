"""Project already-admitted SourceEvidence into bounded LLM reasoning context.

This is not a second evidence model. Authority remains SourceEvidence admission;
this module only renders a redacted summary that reasoning hops may read.

Callers pass the projected strings into ``GovernedContextPackage`` — the package
still never reaches into SourceEvidence payloads itself.
"""

from __future__ import annotations

from typing import Any

from app.evidence.source_evidence import FIELD_CAP, SOURCE_PREVIEW_CAP, VALUE_CAP
from app.safeguards.evidence_sanitizer import redact_secret_values, sanitize_mapping

ENVIRONMENT_SOURCE_TYPES = frozenset({"splunk_mcp", "mcp_discovery"})
RAG_SOURCE_TYPES = frozenset({"rag", "soc_kb", "knowledge"})
USER_CLAIM_SOURCE_TYPES = frozenset({"manual"})
ADMITTED_STATUSES = frozenset({"collected"})
FAILED_STATUSES = frozenset({"failed", "error", "blocked", "unavailable"})
_PREVIEW_ROW_CAP = min(3, SOURCE_PREVIEW_CAP)
_FIELD_NAME_CAP = min(8, FIELD_CAP)


def project_source_evidence_for_reasoning(
    source_evidence: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Return bounded, already-admitted summaries suitable for a reasoning hop.

    Failed tool calls are observations of failure, not negative environment
    findings. User claims never appear as admitted evidence. RAG is a distinct
    list from environment telemetry.
    """
    admitted_environment: list[str] = []
    rag_guidance: list[str] = []
    failed_observations: list[str] = []
    excluded_user_claims = 0
    for item in source_evidence or []:
        if not isinstance(item, dict):
            continue
        source_type = str(item.get("source_type") or "")
        status = str(item.get("collection_status") or "")
        if source_type in USER_CLAIM_SOURCE_TYPES:
            excluded_user_claims += 1
            continue
        if status in FAILED_STATUSES:
            failed_observations.append(_failed_observation(item))
            continue
        if status not in ADMITTED_STATUSES:
            continue
        summary = _admitted_summary(item)
        if source_type in RAG_SOURCE_TYPES or str(item.get("plan_step_ref") or "") == "rag":
            rag_guidance.append(summary)
            continue
        if source_type in ENVIRONMENT_SOURCE_TYPES:
            admitted_environment.append(summary)
    return {
        "admitted_environment_evidence": admitted_environment[:16],
        "rag_guidance": rag_guidance[:8],
        "failed_tool_observations": failed_observations[:8],
        "excluded_user_claim_count": excluded_user_claims,
    }


def _admitted_summary(item: dict[str, Any]) -> str:
    evidence_id = redact_secret_values(str(item.get("evidence_id") or "unknown"))[:48]
    source_type = redact_secret_values(str(item.get("source_type") or "unknown"))[:40]
    result_count = int(item.get("result_count") or 0)
    fields = [
        redact_secret_values(str(name))[:40]
        for name in (item.get("fields_returned") or [])[:_FIELD_NAME_CAP]
        if name
    ]
    preview = _bounded_preview(item.get("preview_rows"))
    query_summary = redact_secret_values(str(item.get("query_or_request_summary") or ""))[:120]
    parts = [
        f"evidence_id={evidence_id}",
        f"source_type={source_type}",
        "trust_class=environment" if source_type in ENVIRONMENT_SOURCE_TYPES else "trust_class=rag_guidance",
        f"collection_status={item.get('collection_status')}",
        f"result_count={result_count}",
    ]
    if fields:
        parts.append("fields=" + ",".join(fields))
    if query_summary:
        parts.append(f"request={query_summary}")
    if preview:
        parts.append("preview=" + preview)
    return "; ".join(parts)[:VALUE_CAP * 4]


def _bounded_preview(rows: Any) -> str:
    if not isinstance(rows, list):
        return ""
    chunks: list[str] = []
    for row in rows[:_PREVIEW_ROW_CAP]:
        if not isinstance(row, dict):
            continue
        cleaned = sanitize_mapping(row)
        cells: list[str] = []
        for key, value in list(cleaned.items())[:_FIELD_NAME_CAP]:
            if str(key).lower() in {"executed_spl", "query", "spl"}:
                continue
            cells.append(f"{redact_secret_values(str(key))[:40]}={redact_secret_values(str(value))[:VALUE_CAP]}")
        if cells:
            chunks.append(",".join(cells))
    return " | ".join(chunks)[:VALUE_CAP * 3]


def _failed_observation(item: dict[str, Any]) -> str:
    tool = redact_secret_values(str(item.get("tool_name") or item.get("source_name") or "unknown"))[:80]
    status = redact_secret_values(str(item.get("collection_status") or "failed"))[:40]
    return f"tool={tool}; status={status}; not_negative_evidence=true"
