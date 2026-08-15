"""Plan 8 E0A — EvidenceState derives missing/required keys from StructuredContext."""

from __future__ import annotations

from app.evidence.context_structurer import structure_context
from app.evidence.minimal_evidence_state import derive_minimal_evidence_state
from app.evidence.source_evidence import build_source_evidence
from app.tests.test_evidence_context import APPROVED_VALIDATION, EXECUTED, WORKFLOW


def test_structured_context_missing_evidence_projects_into_evidence_state() -> None:
    records = build_source_evidence(
        trace_id="trace-e0a-context",
        query="failed logins",
        selected_skill="attack_discovery",
        spl_validation=APPROVED_VALIDATION,
        execution=EXECUTED,
    )
    context = structure_context(
        query="failed logins",
        trace_id="trace-e0a-context",
        selected_skill="attack_discovery",
        workflow_plan=WORKFLOW,
        spl_validation=APPROVED_VALIDATION,
        execution=EXECUTED,
        source_evidence=records,
    )
    state = derive_minimal_evidence_state(
        source_evidence=records,
        structured_context=context,
        evidence_plan={"required_evidence_keys": list(context.get("missing_evidence") or [])},
    )
    dumped = state.model_dump_view()
    assert "structured_context" in dumped["provenance"]["derived_from"]
    assert "structured_facts" not in dumped
    for fact in context.get("structured_facts") or []:
        assert fact.get("statement") not in str(dumped)
    for key in context.get("missing_evidence") or []:
        assert key in state.required
        assert key in state.missing or key in state.obtained
    assert state.trust_class == "untrusted_evidence"
