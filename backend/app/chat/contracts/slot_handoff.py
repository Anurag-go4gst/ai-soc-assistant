from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SlotHandoffSummary(BaseModel):
    """Planning-time snapshot of resolved slot bindings.

    Canonical handoff that downstream SPL/MCP stages MUST prefer over re-parsing
    the raw query. Coerced from the legacy dict-shaped
    ``EvidencePlan.normalized_slot_summary`` via
    :func:`slot_handoff_from_normalized_summary`.
    """

    schema_version: Literal["v1"] = "v1"
    normalized_slots: dict[str, str] = Field(default_factory=dict)
    slot_sources: dict[str, str] = Field(default_factory=dict)
    validation_status: dict[str, str] = Field(default_factory=dict)
    unbound_constraints: list[dict[str, Any]] = Field(default_factory=list)
    planning_snapshot: bool = True
    built_at_stage: str = "evidence_planning"


def _coerce_str_map(raw: Any) -> dict[str, str]:
    """Coerce a mapping into ``dict[str, str]``, dropping null values."""
    if not isinstance(raw, dict):
        return {}
    coerced: dict[str, str] = {}
    for key, value in raw.items():
        if value is None:
            continue
        coerced[str(key)] = str(value)
    return coerced


def slot_handoff_from_normalized_summary(raw: dict[str, Any] | None) -> SlotHandoffSummary:
    """Coerce legacy dict-shaped ``normalized_slot_summary`` into the contract.

    Tolerant of missing keys and non-string slot values so the builder never
    raises on a partially populated summary.
    """
    if not isinstance(raw, dict):
        return SlotHandoffSummary()
    unbound = raw.get("unbound_constraints")
    return SlotHandoffSummary(
        normalized_slots=_coerce_str_map(raw.get("normalized_slots")),
        slot_sources=_coerce_str_map(raw.get("slot_sources")),
        validation_status=_coerce_str_map(raw.get("validation_status")),
        unbound_constraints=[c for c in unbound if isinstance(c, dict)] if isinstance(unbound, list) else [],
        planning_snapshot=bool(raw.get("planning_snapshot", True)),
        built_at_stage=str(raw.get("built_at_stage") or "evidence_planning"),
    )
