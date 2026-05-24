from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any

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
) -> list[dict[str, Any]]:
    if spl_validation is None:
        return [
            _evidence(
                trace_id=trace_id,
                source_type="manual",
                source_name="analyst_query",
                collection_status="skipped",
                query_or_request_summary=_summarize(query),
                result_count=0,
                warnings=["spl_not_required_for_skill"],
            )
        ]

    status = str(execution.get("status") or "skipped")
    rows = _safe_rows(execution.get("results_preview", []))
    fields = _fields_returned(rows)
    sensitivity_flags = _sensitivity_flags(rows, fields)
    raw_result_hash = _raw_hash(rows) if rows else None
    collection_status = _collection_status(status)
    warnings = []
    if execution.get("block_reason"):
        warnings.append(str(execution["block_reason"])[:VALUE_CAP])
    if spl_validation.get("warnings"):
        warnings.extend(str(item)[:VALUE_CAP] for item in spl_validation.get("warnings", []))

    return [
        _evidence(
            trace_id=trace_id,
            source_type="mcp",
            source_name=str(execution.get("selected_mcp_server") or "mcp_splunk"),
            tool_name=execution.get("selected_mcp_tool"),
            collection_status=collection_status,
            query_or_request_summary=_request_summary(selected_skill, query, execution),
            executed_spl=execution.get("executed_spl"),
            result_count=int(execution.get("result_count") or 0),
            fields_returned=fields,
            preview_rows=rows,
            raw_result_hash=raw_result_hash,
            raw_result_stored=False,
            time_range=_time_range(spl_validation.get("normalized_spl")),
            warnings=warnings,
            sensitivity_flags=sensitivity_flags,
        )
    ]


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
) -> dict[str, Any]:
    stable = f"{trace_id}:{source_type}:{source_name}:{tool_name or 'none'}:{collection_status}"
    return {
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
        "created_at": datetime.now(UTC).isoformat(),
    }


def _collection_status(execution_status: str) -> str:
    if execution_status == "executed":
        return "collected"
    if execution_status in {"blocked", "requires_human_review"}:
        return "blocked"
    if execution_status == "failed":
        return "failed"
    return "skipped"


def _request_summary(selected_skill: str, query: str, execution: dict[str, Any]) -> str:
    intent = execution.get("execution_intent") or "none"
    return _safe_text(f"{selected_skill}:{intent}:{query}", 300)


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
    return SENSITIVE_PATTERNS.sub("[redacted]", value).replace("\n", " ")[:max_len]


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
