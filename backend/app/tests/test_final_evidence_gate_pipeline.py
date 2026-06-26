"""Pipeline/response-level regressions for the FinalEvidenceGate (plan Phase 5).

The pure A-H tests assert the gate in isolation. These run a real `/chat` turn
and assert the gate actually governs the exposed response surfaces — closing the
projection gaps the pure tests miss:

- the exposed ``structured_context.final_evidence_gate`` stays consistent with the
  final ``run_contract`` (no stale gate), and
- a gate-disallowed severity is not leaked into ``severity_decision`` or
  ``action_capability.reason`` even though the analyst card already hides it.
"""

from __future__ import annotations

import re

from app.api.routes_chat import chat
from app.evals.golden_answer_runner import _model_to_dict
from app.evals.sentinel_eval import sentinel_runtime
from app.risk.severity_policy import (
    ANALYTICS_SEVERITY_NOT_ASSIGNED_LABEL,
    SeverityDecision,
    apply_gate_severity_cap,
)
from app.schemas.requests import ChatRequest

OUT_OF_SET = "Strange OT chatter to a brand new external host overnight, anything to hunt?"
IN_REGISTRY_ANALYTICS = "Which hosts are generating the most SMB traffic?"

_GATE_MIRRORED_FIELDS = (
    "collected_evidence_count",
    "allow_severity_assessment",
    "allow_results_table",
    "allow_mitre_mapping",
    "allow_live_result_language",
    "effective_hil_required",
)


def _payload(question: str) -> dict:
    with sentinel_runtime():
        return _model_to_dict(chat(ChatRequest(message=question)))


def _gate(payload: dict) -> dict:
    return (payload.get("structured_context") or {}).get("final_evidence_gate") or {}


def _assert_gate_consistent_with_run_contract(payload: dict) -> None:
    gate = _gate(payload)
    run_contract = payload.get("run_contract") or {}
    assert gate, "final_evidence_gate missing from structured_context"
    assert run_contract, "run_contract missing from response"
    for field in _GATE_MIRRORED_FIELDS:
        assert gate[field] == run_contract[field], (
            f"gate.{field}={gate[field]} != run_contract.{field}={run_contract[field]} "
            "(stale gate vs final contract)"
        )


def test_guided_investigation_gate_governs_severity_and_is_not_stale() -> None:
    payload = _payload(OUT_OF_SET)
    _assert_gate_consistent_with_run_contract(payload)

    run_contract = payload.get("run_contract") or {}
    if not run_contract.get("allow_severity_assessment"):
        severity = payload.get("severity_decision") or {}
        label = str(severity.get("severity_label") or "")
        # No raw P1-P4 leaks into the exposed severity_decision.
        assert not re.match(r"^P[1-4]\b", label), f"disallowed severity leaked: {label!r}"
        # ...nor into the action-capability reason text.
        action = payload.get("action_capability") or {}
        assert not re.search(r"severity P[1-4]\b", str(action.get("reason") or ""))


def test_in_registry_analytics_gate_present_and_consistent() -> None:
    payload = _payload(IN_REGISTRY_ANALYTICS)
    _assert_gate_consistent_with_run_contract(payload)


def test_no_results_table_claim_when_gate_disallows() -> None:
    payload = _payload(OUT_OF_SET)
    run_contract = payload.get("run_contract") or {}
    # Review/guidance turn: no execution, so no results-table permission anywhere.
    assert run_contract.get("allow_results_table") is False
    assert _gate(payload)["allow_results_table"] is False


def test_apply_gate_severity_cap_unit() -> None:
    p3 = SeverityDecision(
        use_case_id=None,
        severity_label="P3 Medium",
        matched_rules=["default_no_policy"],
        recommended_priority="standard_triage",
        allowed_action_tier=1,
    )
    # Disallowed -> capped to the not-assigned sentinel.
    capped = apply_gate_severity_cap(p3, allow_severity_assessment=False)
    assert capped.severity_label == ANALYTICS_SEVERITY_NOT_ASSIGNED_LABEL
    assert capped.recommended_priority == "not_applicable"
    # Allowed -> unchanged.
    assert apply_gate_severity_cap(p3, allow_severity_assessment=True).severity_label == "P3 Medium"
    # Already a non-priority sentinel -> unchanged even when disallowed.
    sentinel = p3.model_copy(update={"severity_label": ANALYTICS_SEVERITY_NOT_ASSIGNED_LABEL})
    assert (
        apply_gate_severity_cap(sentinel, allow_severity_assessment=False).severity_label
        == ANALYTICS_SEVERITY_NOT_ASSIGNED_LABEL
    )
