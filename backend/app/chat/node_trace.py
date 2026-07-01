"""Formal per-node trace record schema (C9 / S2)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

GuardrailStatus = Literal["passed", "review_required", "blocked", "not_applicable"]


class NodeTraceRecord(BaseModel):
    """One lightweight trace row emitted by the packaging layer."""

    model_config = ConfigDict(extra="forbid")

    node_name: str
    input_summary: dict[str, Any] = Field(default_factory=dict)
    output_summary: dict[str, Any] = Field(default_factory=dict)
    decision_reason: str
    guardrail_status: GuardrailStatus
    human_review_required: bool = False
    limitations: list[str] = Field(default_factory=list)
    llm_call: dict[str, Any] | None = None

    @field_validator("node_name")
    @classmethod
    def _node_name_non_empty(cls, value: str) -> str:
        cleaned = str(value or "").strip()
        if not cleaned:
            raise ValueError("node_name must be non-empty")
        return cleaned


REQUIRED_NODE_TRACE_KEYS = frozenset(NodeTraceRecord.model_fields.keys())


def validate_node_trace_record(record: dict[str, Any]) -> NodeTraceRecord:
    """Validate a single node_trace row."""
    return NodeTraceRecord.model_validate(record)


def validate_node_trace(records: list[dict[str, Any]]) -> list[NodeTraceRecord]:
    """Validate an ordered node_trace list."""
    return [validate_node_trace_record(record) for record in records]


def node_trace_to_dicts(records: list[NodeTraceRecord]) -> list[dict[str, Any]]:
    return [record.model_dump() for record in records]
