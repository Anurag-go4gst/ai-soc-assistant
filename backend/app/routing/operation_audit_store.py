"""P2-audit: in-process audit log + repeat-pattern hints (trace/telemetry; no COE UI)."""

from __future__ import annotations

from collections import Counter
from threading import Lock
from typing import Any

from app.connectors.telemetry import get_telemetry_connector

_store_lock = Lock()
_audit_entries: list[dict[str, Any]] = []
_REPEAT_PROMOTION_THRESHOLD = 3


def record_operation_audit(
    audit_record: dict[str, object] | None,
    *,
    trace_id: str | None = None,
) -> dict[str, object] | None:
    if not audit_record or not audit_record.get("audit_required"):
        return None
    entry = {
        **dict(audit_record),
        "trace_id": trace_id,
        "repeat_pattern": _repeat_pattern_hint(audit_record.get("proposed_operation")),
    }
    with _store_lock:
        _audit_entries.append(entry)
        if len(_audit_entries) > 500:
            del _audit_entries[: len(_audit_entries) - 500]
    if trace_id:
        get_telemetry_connector().record_step(
            trace_id,
            "operation_audit_recorded",
            "completed",
            audit_sink=entry.get("audit_sink"),
            path_type=entry.get("path_type"),
            proposed_operation=entry.get("proposed_operation"),
            promotion_candidate=entry.get("promotion_candidate"),
            repeat_pattern=entry.get("repeat_pattern"),
        )
    return entry


def list_operation_audit_entries(*, limit: int = 50) -> list[dict[str, Any]]:
    with _store_lock:
        return list(_audit_entries[-limit:])


def export_coe_promotion_candidates(*, limit: int = 25) -> list[dict[str, Any]]:
    """Report-only export for COE review (P2-audit-2 repeat-pattern detector)."""
    with _store_lock:
        entries = list(_audit_entries)
    counter: Counter[str] = Counter()
    for entry in entries:
        op = entry.get("proposed_operation")
        if isinstance(op, str) and op.strip():
            counter[op.strip()] += 1
    candidates: list[dict[str, Any]] = []
    for operation, count in counter.most_common(limit):
        if count < _REPEAT_PROMOTION_THRESHOLD:
            continue
        candidates.append(
            {
                "proposed_operation": operation,
                "occurrence_count": count,
                "promotion_recommended": True,
                "review_status": "repeat_pattern_detected",
            }
        )
    return candidates


def clear_operation_audit_store_for_tests() -> None:
    with _store_lock:
        _audit_entries.clear()


def _repeat_pattern_hint(proposed_operation: object) -> dict[str, object] | None:
    if not isinstance(proposed_operation, str) or not proposed_operation.strip():
        return None
    op = proposed_operation.strip()
    with _store_lock:
        count = sum(
            1
            for entry in _audit_entries
            if str(entry.get("proposed_operation", "")).strip() == op
        )
    next_count = count + 1
    return {
        "operation": op,
        "prior_occurrences": count,
        "occurrence_count_after_record": next_count,
        "promotion_recommended": next_count >= _REPEAT_PROMOTION_THRESHOLD,
    }
