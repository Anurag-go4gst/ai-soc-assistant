"""Plan 8 S0 — staged sufficiency adapter over existing deterministic checks."""

from __future__ import annotations

import inspect

from app.chat.contracts.staged_sufficiency import (
    StagedSufficiencyResult,
    derive_next_action,
    from_context_sufficiency,
    from_understanding_state,
)
from app.evidence.context_sufficiency import check_context_sufficiency


def _fact(refs: list[str] | None = None) -> dict:
    return {"fact_id": "f1", "statement": "source returned rows", "source_refs": refs if refs is not None else ["ev_1"]}


def _context(**overrides):
    base = {
        "context_quality": "partial",
        "missing_evidence": [],
        "structured_facts": [_fact()],
        "mitre_candidates": [],
        "mitre_grounding_refs": [],
        "environment_grounding_refs": [],
    }
    base.update(overrides)
    return base


def _evidence(source_type: str, *, status: str = "collected", sensitivity: list[str] | None = None) -> dict:
    return {"source_type": source_type, "collection_status": status, "sensitivity_flags": sensitivity or []}


def test_contract_fields_are_the_shared_vocabulary() -> None:
    result = StagedSufficiencyResult(
        stage="UNDERSTANDING",
        status="SUFFICIENT",
        required=["time_scope"],
        available=["time_scope"],
        missing=[],
        locked=["time_scope"],
        unresolved=[],
        reason_codes=[],
        next_action="CONTINUE",
    )
    assert result.stage == "UNDERSTANDING"
    assert result.status == "SUFFICIENT"
    assert result.next_action == "CONTINUE"
    dumped = result.model_dump()
    for key in (
        "stage",
        "status",
        "required",
        "available",
        "missing",
        "locked",
        "unresolved",
        "reason_codes",
        "next_action",
    ):
        assert key in dumped


def test_next_action_is_derived_not_caller_authority() -> None:
    result = StagedSufficiencyResult(
        stage="UNDERSTANDING",
        status="BLOCKED",
        reason_codes=["policy_blocked"],
        next_action="CONTINUE",
    )
    assert result.next_action == "BLOCK"


def test_understanding_unresolved_semantic_requests_t4() -> None:
    result = from_understanding_state(
        required=["semantic_goal"],
        available=[],
        missing=[],
        locked=["account_type"],
        unresolved=["semantic_goal"],
    )
    assert result.stage == "UNDERSTANDING"
    assert result.status == "PARTIAL"
    assert result.next_action == "CALL_T4"
    assert result.locked == ["account_type"]
    assert result.unresolved == ["semantic_goal"]


def test_understanding_clarification_does_not_call_t4() -> None:
    result = from_understanding_state(
        missing=["alert_id"],
        unresolved=["semantic_goal"],
        clarification_required=True,
    )
    assert result.next_action == "CLARIFY"
    assert result.status == "INSUFFICIENT"


def test_evidence_stage_never_calls_t4() -> None:
    envelope = check_context_sufficiency(_context(missing_evidence=["mcp:splunk"]), [_evidence("splunk_mcp")])
    projected = from_context_sufficiency(envelope)
    assert projected.stage == "EVIDENCE"
    assert projected.next_action != "CALL_T4"
    assert derive_next_action(stage="EVIDENCE", status="PARTIAL", unresolved=["x"]) == "CONTINUE"


def test_adapter_does_not_replace_context_sufficiency_modes() -> None:
    envelope = check_context_sufficiency(_context(), [_evidence("splunk_mcp")])
    assert envelope["status"] == "full_answer"
    assert envelope["synthesis_allowed"] is False
    projected = from_context_sufficiency(envelope)
    assert projected.status == "SUFFICIENT"
    assert projected.next_action == "CONTINUE"
    assert envelope["status"] == "full_answer"


def test_blocked_policy_projects_to_block() -> None:
    envelope = check_context_sufficiency(
        _context(),
        [_evidence("splunk_mcp", sensitivity=["sensitive_value_redacted"])],
    )
    projected = from_context_sufficiency(envelope)
    assert envelope["status"] == "blocked_by_policy"
    assert projected.status == "BLOCKED"
    assert projected.next_action == "BLOCK"


def test_insufficient_evidence_projects_to_degrade() -> None:
    envelope = check_context_sufficiency(_context(), [_evidence("splunk_mcp", status="blocked")])
    projected = from_context_sufficiency(envelope)
    assert envelope["status"] == "insufficient_evidence"
    assert projected.status == "INSUFFICIENT"
    assert projected.next_action == "DEGRADE"


def test_adapter_is_not_a_planner_or_router() -> None:
    source = inspect.getsource(StagedSufficiencyResult)
    assert "selected_skill" not in source
    assert "resource_plan" not in source
    assert "mcp" not in source.lower() or "execution" not in source.lower()
    dumped = from_understanding_state().model_dump()
    assert "selected_skill" not in dumped
    assert "execution_eligible" not in dumped
