"""Build action_tool payloads solely from CanonicalFacts + governed answer fields."""

from __future__ import annotations

from typing import Any, Mapping

from app.chat.contracts.canonical_facts import CanonicalFacts

CREATE_TICKET_TOOL = "action_tool:create_ticket"


def build_create_ticket_payload_from_state(state: Mapping[str, Any]) -> dict[str, Any] | None:
    """Derive a create_ticket payload from the fact spine — never prompts or RAG chunks."""
    raw_facts = state.get("canonical_facts")
    if not isinstance(raw_facts, dict):
        return None
    facts = CanonicalFacts.model_validate(raw_facts)

    source_refs: list[str] = []
    for fact in facts.facts_by_kind("executed_evidence"):
        evidence_id = fact.payload.get("evidence_id")
        if isinstance(evidence_id, str) and evidence_id.strip():
            source_refs.append(evidence_id.strip())
            continue
        mcp_record = fact.payload.get("mcp_record")
        if isinstance(mcp_record, dict):
            delivered = mcp_record.get("delivered")
            if isinstance(delivered, list):
                for item in delivered:
                    if isinstance(item, str) and item.strip():
                        source_refs.append(item.strip())

    analyst = state.get("analyst_response")
    summary = None
    if isinstance(analyst, dict):
        summary = analyst.get("one_sentence_finding") or analyst.get("direct_answer_summary")
    if not isinstance(summary, str) or not summary.strip():
        summary = state.get("message") if isinstance(state.get("message"), str) else None
    if not isinstance(summary, str) or not summary.strip():
        return None

    severity_label = "Medium"
    severity = state.get("severity_decision")
    if isinstance(severity, dict):
        label = severity.get("severity_label")
        if isinstance(label, str) and label.strip():
            severity_label = label.strip()
    elif hasattr(severity, "severity_label"):
        label = getattr(severity, "severity_label", None)
        if isinstance(label, str) and label.strip():
            severity_label = label.strip()

    # The spine can carry the same evidence fact via multiple harvest passes;
    # a ticket audit trail needs each ref once, in first-seen order.
    source_refs = list(dict.fromkeys(source_refs))
    if not source_refs:
        source_refs = ["no_executed_evidence_refs"]

    return {
        "summary": summary.strip()[:2000],
        "severity_label": severity_label,
        "source_refs": source_refs[:20],
    }
