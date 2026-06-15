from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any

from app.knowledge.soc_kb_retriever import soc_kb_source_evidence
from app.safeguards.evidence_sanitizer import redact_secret_values
from app.safeguards.mcp_result_safeguard import scan_mcp_preview_rows

SOURCE_PREVIEW_CAP = 5
FIELD_CAP = 40
VALUE_CAP = 240
SENSITIVE_PATTERNS = re.compile(r"(password|passwd|secret|token|api[_-]?key|credential|authorization)", re.IGNORECASE)


def build_source_evidence(
    *,
    trace_id: str,
    query: str,
    selected_skill: str,
    spl_validation: dict[str, Any] | None,
    execution: dict[str, Any],
    soc_kb_retrieval: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    if soc_kb_retrieval is not None and soc_kb_retrieval.get("retrieval_status") != "disabled":
        kb_item = soc_kb_source_evidence(trace_id, query, soc_kb_retrieval)
        kb_item.setdefault("plan_step_ref", "rag")
        evidence.append(kb_item)
    if spl_validation and str(spl_validation.get("selected_candidate_spl_provider") or "").startswith("saia_"):
        evidence.append(
            _evidence(
                trace_id=trace_id,
                source_type="splunk_mcp_saia",
                source_name="splunk_ai_assistant",
                tool_name=str(spl_validation.get("selected_candidate_spl_provider")),
                collection_status="collected",
                query_or_request_summary=_summarize(query),
                result_count=1,
                warnings=["saia_output_candidate_only_validation_required"],
                output_type="candidate_spl",
                provider_used=spl_validation.get("selected_candidate_spl_provider"),
                provenance="splunk_ai_assistant_candidate_provider",
            )
        )

    if spl_validation is None:
        evidence.append(
            _evidence(
                trace_id=trace_id,
                source_type="manual",
                source_name="analyst_query",
                collection_status="skipped",
                query_or_request_summary=_summarize(query),
                result_count=0,
                warnings=["spl_not_required_for_skill"],
            )
        )
        return evidence

    status = str(execution.get("status") or "skipped")
    rows, fields, envelope_warnings = _preview_from_execution(execution)
    rows, injection_flags, injection_warnings = scan_mcp_preview_rows(rows)
    sensitivity_flags = sorted(set(_sensitivity_flags(rows, fields) + injection_flags))
    if injection_warnings:
        envelope_warnings = [*envelope_warnings, *injection_warnings]
    raw_result_hash = _raw_hash(rows) if rows else None
    collection_status = _collection_status(status)
    warnings: list[str] = list(envelope_warnings)
    if execution.get("block_reason"):
        warnings.append(str(execution["block_reason"])[:VALUE_CAP])
    if spl_validation.get("warnings"):
        warnings.extend(str(item)[:VALUE_CAP] for item in spl_validation.get("warnings", []))
    result_count = int(execution.get("result_count") or 0)
    if status == "executed" and result_count == 0:
        warnings.append("execution_completed_zero_rows")

    evidence.append(
        _evidence(
            trace_id=trace_id,
            source_type="splunk_mcp",
            source_name=str(execution.get("selected_mcp_server") or "mcp_splunk"),
            tool_name=execution.get("selected_mcp_tool"),
            collection_status=collection_status,
            query_or_request_summary=_request_summary(selected_skill, query, execution),
            executed_spl=execution.get("executed_spl"),
            result_count=result_count,
            execution_outcome="negative_result" if status == "executed" and result_count == 0 else None,
            fields_returned=fields,
            preview_rows=rows,
            raw_result_hash=raw_result_hash,
            raw_result_stored=False,
            time_range=_time_range(spl_validation.get("normalized_spl")),
            warnings=warnings,
            sensitivity_flags=sensitivity_flags,
            tool_category=_tool_category(execution.get("selected_mcp_tool")),
            provider_used="splunk_run_query" if execution.get("executed_spl") else None,
            saved_search_name=execution.get("saved_search_name"),
            provenance="ai_soc_validated_execution_gate",
        )
    )

    # O5c Step 2: per-call evidence. On a completed broaden turn the singular
    # `execution` above is the broadened (c2) search; emit a separate honest
    # negative-result item for the empty primary (c1) so sufficiency sees both
    # logical calls rather than only the broadened one.
    _append_broaden_primary_evidence(evidence, trace_id, query, selected_skill, execution)
    return evidence


def _append_broaden_primary_evidence(
    evidence: list[dict[str, Any]],
    trace_id: str,
    query: str,
    selected_skill: str,
    execution: dict[str, Any],
) -> None:
    orchestration = execution.get("mcp_orchestration")
    if not isinstance(orchestration, dict) or orchestration.get("recipe_id") != "broaden_scope_on_empty":
        return
    calls = orchestration.get("calls")
    if not isinstance(calls, list) or len(calls) < 2:
        return
    primary = calls[0]
    if not isinstance(primary, dict) or primary.get("outcome") != "empty":
        return
    primary_spl = str(primary.get("result_envelope_ref") or "") or None
    item = _evidence(
        trace_id=trace_id,
        source_type="splunk_mcp",
        source_name=str(execution.get("selected_mcp_server") or "mcp_splunk"),
        tool_name=execution.get("selected_mcp_tool"),
        collection_status="collected",
        query_or_request_summary=_request_summary(selected_skill, query, execution),
        executed_spl=primary_spl,
        result_count=0,
        execution_outcome="negative_result",
        warnings=["execution_completed_zero_rows", "broaden_primary_call"],
        tool_category=_tool_category(execution.get("selected_mcp_tool")),
        provider_used="splunk_run_query" if primary_spl else None,
        provenance="ai_soc_validated_execution_gate",
    )
    # The broadened (c2) item above shares source/tool/status with this primary
    # (c1) item, so disambiguate the id and link it to the c1 plan step.
    item["evidence_id"] = f"{item['evidence_id']}_c1"
    item["plan_step_ref"] = "c1_primary_search"
    evidence.append(item)


def build_provider_source_evidence(
    *,
    trace_id: str,
    source_type: str,
    source_name: str,
    collection_status: str,
    query_or_request_summary: str | None,
    result_count: int,
    tool_name: str | None = None,
    preview_rows: list[dict[str, Any]] | None = None,
    warnings: list[str] | None = None,
    tool_category: str | None = None,
    provider_used: str | None = None,
    provenance: str | None = None,
) -> dict[str, Any]:
    rows = _safe_rows(preview_rows or [])
    return _evidence(
        trace_id=trace_id,
        source_type=source_type,
        source_name=source_name,
        tool_name=tool_name,
        collection_status=collection_status,
        query_or_request_summary=_safe_text(query_or_request_summary or "", 300) if query_or_request_summary else None,
        result_count=result_count,
        fields_returned=_fields_returned(rows),
        preview_rows=rows,
        raw_result_hash=_raw_hash(rows) if rows else None,
        raw_result_stored=False,
        warnings=warnings or [],
        sensitivity_flags=_sensitivity_flags(rows, _fields_returned(rows)),
        tool_category=tool_category,
        provider_used=provider_used,
        provenance=provenance,
    )


def _evidence(
    *,
    trace_id: str,
    source_type: str,
    source_name: str,
    collection_status: str,
    query_or_request_summary: str | None,
    result_count: int,
    tool_name: str | None = None,
    executed_spl: str | None = None,
    fields_returned: list[str] | None = None,
    preview_rows: list[dict[str, Any]] | None = None,
    raw_result_hash: str | None = None,
    raw_result_stored: bool = False,
    time_range: str | None = None,
    warnings: list[str] | None = None,
    sensitivity_flags: list[str] | None = None,
    tool_category: str | None = None,
    provider_used: str | None = None,
    saved_search_name: str | None = None,
    output_type: str | None = None,
    provenance: str | None = None,
    execution_outcome: str | None = None,
) -> dict[str, Any]:
    stable = f"{trace_id}:{source_type}:{source_name}:{tool_name or 'none'}:{collection_status}"
    payload: dict[str, Any] = {
        "evidence_id": f"ev_{hashlib.sha256(stable.encode('utf-8')).hexdigest()[:16]}",
        "trace_id": trace_id,
        "source_type": source_type,
        "source_name": _safe_text(source_name, 120),
        "tool_name": _safe_text(tool_name, 120) if tool_name else None,
        "collection_status": collection_status,
        "query_or_request_summary": query_or_request_summary,
        "executed_spl": executed_spl,
        "result_count": result_count,
        "fields_returned": fields_returned or [],
        "preview_rows": preview_rows or [],
        "raw_result_hash": raw_result_hash,
        "raw_result_stored": raw_result_stored,
        "time_range": time_range,
        "warnings": warnings or [],
        "sensitivity_flags": sensitivity_flags or [],
        "tool_category": tool_category,
        "provider_used": provider_used,
        "saved_search_name": saved_search_name,
        "output_type": output_type,
        "provenance": provenance,
        "created_at": datetime.now(UTC).isoformat(),
    }
    if execution_outcome:
        payload["execution_outcome"] = execution_outcome
    # WS0 T0.4: link evidence back to the composed plan step that produced it.
    # Step ids are fixed by the deterministic composer ("rag"/"spl"/"mcp").
    step_ref = _PLAN_STEP_REF_BY_SOURCE_TYPE.get(source_type)
    if step_ref is not None:
        payload["plan_step_ref"] = step_ref
    return payload


_PLAN_STEP_REF_BY_SOURCE_TYPE = {
    "splunk_mcp": "mcp",
    "splunk_mcp_saia": "spl",
    "mcp_discovery": "mcp",
    "rag": "rag",
}


def mcp_loop_source_evidence(
    trace_id: str,
    mcp_evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Stage 4B phase 6: map accumulated loop hops into governed source_evidence."""
    items: list[dict[str, Any]] = []
    for index, hop in enumerate(mcp_evidence):
        if not isinstance(hop, dict):
            continue
        tool = str(hop.get("tool") or "unknown_mcp_tool")
        if tool == "splunk_run_query":
            # The gated execution node owns run_query evidence; skip duplicate hop rows.
            continue
        outcome = str(hop.get("outcome") or "unknown")
        delivered = [str(item) for item in (hop.get("delivered") or [])]
        payload = hop.get("payload") if isinstance(hop.get("payload"), dict) else {}
        payload_rows = payload.get("preview_rows")
        if isinstance(payload_rows, list) and payload_rows:
            rows = _safe_rows([dict(row) for row in payload_rows if isinstance(row, dict)])
        else:
            rows = _mcp_hop_preview_rows(tool=tool, delivered=delivered, outcome=outcome)
        warnings: list[str] = []
        if outcome == "planned":
            warnings.append("discovery_hop_planned_only")
        if payload.get("read_only"):
            warnings.append("read_only_discovery_hop")
        collection_status = _mcp_hop_collection_status(outcome)
        items.append(
            _evidence(
                trace_id=trace_id,
                source_type="mcp_discovery",
                source_name=tool,
                tool_name=tool,
                collection_status=collection_status,
                query_or_request_summary=_safe_text(
                    f"discovery_hop:{tool}:delivered={','.join(delivered) or 'none'}",
                    300,
                ),
                result_count=len(delivered) if delivered else 0,
                fields_returned=_fields_returned(rows),
                preview_rows=rows,
                warnings=warnings,
                tool_category="discovery",
                provenance="stage_4b_evidence_loop",
                execution_outcome=outcome if outcome != "collected" else None,
            )
        )
        # Distinct evidence_id per hop even when the same tool repeats.
        items[-1]["evidence_id"] = _mcp_hop_evidence_id(trace_id, tool, index, outcome)
    return items


def append_mcp_loop_source_evidence(
    evidence: list[dict[str, Any]],
    *,
    trace_id: str,
    mcp_evidence: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    if not mcp_evidence:
        return evidence
    loop_items = mcp_loop_source_evidence(trace_id, mcp_evidence)
    if not loop_items:
        return evidence
    return [*evidence, *loop_items]


def _mcp_hop_collection_status(outcome: str) -> str:
    if outcome == "collected":
        return "collected"
    if outcome == "planned":
        return "planned"
    if outcome in {"blocked", "requires_human_review"}:
        return "blocked"
    if outcome == "failed":
        return "failed"
    return "skipped"


def _mcp_hop_preview_rows(*, tool: str, delivered: list[str], outcome: str) -> list[dict[str, Any]]:
    if delivered:
        return [
            {
                "produce_key": produce,
                "discovery_status": outcome,
                "tool": tool,
                "derivation": "stage_4b_evidence_loop",
            }
            for produce in delivered[:SOURCE_PREVIEW_CAP]
        ]
    return [
        {
            "tool": tool,
            "discovery_status": outcome,
            "derivation": "stage_4b_evidence_loop",
        }
    ]


def _mcp_hop_evidence_id(trace_id: str, tool: str, index: int, outcome: str) -> str:
    stable = f"{trace_id}:mcp_discovery:{tool}:{index}:{outcome}"
    return f"ev_{hashlib.sha256(stable.encode('utf-8')).hexdigest()[:16]}"


def _collection_status(execution_status: str) -> str:
    if execution_status == "executed":
        return "collected"
    if execution_status in {"blocked", "requires_human_review"}:
        return "blocked"
    if execution_status == "failed":
        return "failed"
    return "skipped"


def _tool_category(tool_name: Any) -> str | None:
    tool = str(tool_name or "")
    if tool in {"splunk_run_query", "run_splunk_query"}:
        return "execution"
    if tool == "splunk_run_saved_search":
        return "saved_search_execution"
    return None


def _request_summary(selected_skill: str, query: str, execution: dict[str, Any]) -> str:
    intent = execution.get("execution_intent") or "none"
    return _safe_text(f"{selected_skill}:{intent}:{query}", 300)


def _preview_from_execution(
    execution: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Prefer SplunkResultEnvelope on execution; fall back to legacy results_preview."""
    envelope_data = execution.get("splunk_result_envelope")
    if isinstance(envelope_data, dict):
        raw_rows = envelope_data.get("rows")
        # Live executed-search rows arrive on the envelope; route them through
        # _safe_rows so secret values are redacted like the legacy preview path
        # (the envelope path must not bypass the sanitizer).
        rows = _safe_rows(raw_rows if isinstance(raw_rows, list) else [])
        fields = _fields_returned(rows)
        envelope_warnings = [
            str(item)[:VALUE_CAP]
            for item in envelope_data.get("warnings", [])
            if item is not None
        ]
        if envelope_data.get("schema_confirmed") is False:
            reason = envelope_data.get("schema_confirmed_reason")
            if reason:
                envelope_warnings.append(f"schema_unconfirmed:{reason}"[:VALUE_CAP])
        return rows, fields, envelope_warnings
    rows = _safe_rows(execution.get("results_preview", []))
    return rows, _fields_returned(rows), []


def _safe_rows(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    safe_rows: list[dict[str, Any]] = []
    for row in rows[:SOURCE_PREVIEW_CAP]:
        if not isinstance(row, dict):
            continue
        safe_rows.append({_safe_text(str(key), 80): _safe_value(value) for key, value in row.items()})
    return safe_rows


def _safe_value(value: Any) -> Any:
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _safe_text(str(value), VALUE_CAP)


def _safe_text(value: str, max_len: int) -> str:
    masked = redact_secret_values(SENSITIVE_PATTERNS.sub("[redacted]", value))
    return masked.replace("\n", " ")[:max_len]


def _summarize(query: str) -> str:
    return _safe_text(query, 300)


def _fields_returned(rows: list[dict[str, Any]]) -> list[str]:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    return fields[:FIELD_CAP]


def _sensitivity_flags(rows: list[dict[str, Any]], fields: list[str]) -> list[str]:
    flags = []
    if any(SENSITIVE_PATTERNS.search(field) for field in fields):
        flags.append("sensitive_field_name_redacted")
    serialized = json.dumps(rows, default=str)
    if SENSITIVE_PATTERNS.search(serialized):
        flags.append("sensitive_value_redacted")
    return sorted(set(flags))


def _raw_hash(rows: list[dict[str, Any]]) -> str:
    serialized = json.dumps(rows, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


def _time_range(spl: Any) -> str | None:
    if not spl:
        return None
    text = str(spl)
    earliest = _match(r"\bearliest=([^\s|]+)", text)
    latest = _match(r"\blatest=([^\s|]+)", text)
    if earliest or latest:
        return f"earliest={earliest or 'unknown'} latest={latest or 'unknown'}"
    return None


def _match(pattern: str, text: str) -> str | None:
    matched = re.search(pattern, text)
    return matched.group(1) if matched else None
