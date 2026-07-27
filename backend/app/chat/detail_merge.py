"""Deterministic merge for DetailTool outputs with provenance precedence."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.chat.contracts.gap_resolution import FieldConflict, FieldProvenance
from app.chat.contracts.knowledge_recall import KnowledgeRecallResult

_PRECEDENCE = {
    "user": 5,
    "live_telemetry": 4,
    "knowledge_recall": 3,
    "catalogue_default": 2,
    "detail_tool": 2,
    "model_inference": 1,
}


def _precedence(source: str) -> int:
    return _PRECEDENCE.get(source, 0)


def merge_field_values(
    existing: dict[str, FieldProvenance],
    incoming: dict[str, FieldProvenance],
) -> tuple[dict[str, FieldProvenance], list[FieldConflict]]:
    merged = dict(existing)
    conflicts: list[FieldConflict] = []
    for key, new_prov in incoming.items():
        old = merged.get(key)
        if old is None:
            merged[key] = new_prov
            continue
        if old.value == new_prov.value:
            continue
        if _precedence(new_prov.source) > _precedence(old.source):
            conflicts.append(
                FieldConflict(
                    field=key,
                    existing_value=old.value,
                    new_value=new_prov.value,
                    existing_source=old.source,
                    new_source=new_prov.source,
                    resolution_status="accepted_new",
                )
            )
            merged[key] = new_prov
        else:
            conflicts.append(
                FieldConflict(
                    field=key,
                    existing_value=old.value,
                    new_value=new_prov.value,
                    existing_source=old.source,
                    new_source=new_prov.source,
                    resolution_status="kept_existing",
                )
            )
    return merged, conflicts


def merge_knowledge_recall(
    result: KnowledgeRecallResult,
    *,
    known: dict[str, FieldProvenance],
) -> tuple[dict[str, FieldProvenance], list[FieldConflict], list[str]]:
    incoming: dict[str, FieldProvenance] = {}
    now = datetime.now(UTC).isoformat()
    for fact in result.facts:
        if fact.reference_id:
            incoming[fact.reference_id] = FieldProvenance(
                value=fact.text,
                source="knowledge_recall",
                confidence=result.confidence,
                timestamp=now,
                tool_call_id=result.tool_call_id,
            )
    merged, conflicts = merge_field_values(known, incoming)
    limitations = list(result.limitations)
    if result.status == "error":
        limitations.append("knowledge_recall_failed")
    return merged, conflicts, limitations
