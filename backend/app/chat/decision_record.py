"""DecisionRecord emission for planner hierarchy audit trail."""

from __future__ import annotations

from typing import Any

from app.connectors.telemetry.redaction import is_secret_key
from app.planner.planner_hierarchy import DecisionRecord, new_decision_record_id
from app.safeguards.evidence_sanitizer import REDACTED, sanitize_value

State = dict[str, Any]

_REQUIRED_FIELDS = ("node", "authority", "decision_reason", "inputs_ref", "outputs_ref")


def _sanitize_refs(refs: list[str]) -> list[str]:
    cleaned: list[str] = []
    for ref in refs:
        text = str(ref or "").strip()
        if not text:
            continue
        if is_secret_key(text):
            cleaned.append(REDACTED)
            continue
        cleaned.append(str(sanitize_value(text)))
    return cleaned


def emit_decision_record(state: State, record: DecisionRecord | dict[str, Any]) -> State:
    """Append a sanitized ``DecisionRecord`` to ``state["decision_log"]``."""
    payload = record.model_dump() if isinstance(record, DecisionRecord) else dict(record)
    for field in _REQUIRED_FIELDS:
        if field not in payload or payload[field] in (None, ""):
            raise ValueError(f"decision record missing required field: {field}")

    sanitized = DecisionRecord(
        record_id=str(payload.get("record_id") or new_decision_record_id()),
        node=str(payload["node"]),
        authority=str(payload["authority"]),
        decision_reason=str(payload["decision_reason"]),
        inputs_ref=_sanitize_refs(list(payload.get("inputs_ref") or [])),
        outputs_ref=_sanitize_refs(list(payload.get("outputs_ref") or [])),
    )

    log = [dict(item) for item in state.get("decision_log") or [] if isinstance(item, dict)]
    log.append(sanitized.model_dump())
    return {**state, "decision_log": log}


def wrap_graph_node(
    node_id: str,
    node_fn: Any,
    *,
    authority: str = "deterministic",
    decision_reason: str | None = None,
    inputs_ref: list[str] | None = None,
    outputs_ref: list[str] | None = None,
) -> Any:
    """Wrap a LangGraph node so each hop appends a ``DecisionRecord``."""

    def wrapped(state: State) -> State:
        result = node_fn(state)
        return emit_decision_record(
            result,
            DecisionRecord(
                record_id=new_decision_record_id(),
                node=node_id,
                authority=authority,
                decision_reason=decision_reason or f"{node_id}_completed",
                inputs_ref=inputs_ref or ["state"],
                outputs_ref=outputs_ref or ["state"],
            ),
        )

    wrapped.__name__ = getattr(node_fn, "__name__", node_id)
    return wrapped


def decision_log_for_trace(state: State) -> list[dict[str, Any]]:
    """Return a copy of ``decision_log`` suitable for control-plane trace packaging."""
    raw = state.get("decision_log")
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, dict)]
