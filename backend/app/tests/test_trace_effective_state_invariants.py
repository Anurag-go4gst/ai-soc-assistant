"""Trace-consistency invariants for the debug bundle.

The bundle is a diagnostic source of truth, so a projection that contradicts the
run is a defect even when no analyst-visible behaviour changes. These are generic
invariants over synthetic payloads plus a bounded replay of the reference trace
`8791eeb8-6814-4c0a-86d6-6bb69e9813f2` (P2 review-only SPL authoring).

Nothing here asserts runtime behaviour; see
``test_trace_effective_state_backward_compatibility.py`` for the legacy-consumer pins.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.chat.debug_summary import build_debug_summary
from app.chat.trace_effective_state import build_effective_state_projection

_FIXTURE = Path(__file__).parent / "fixtures" / "trace_consistency" / "p2_review_only_spl_payload.json"


def _p2_payload() -> dict[str, Any]:
    return json.loads(_FIXTURE.read_text())


@pytest.fixture()
def p2_effective_state() -> dict[str, Any]:
    return build_effective_state_projection(_p2_payload())


def _review_only_payload(**overrides: Any) -> dict[str, Any]:
    """Minimal synthetic review-only SPL authoring payload."""
    payload: dict[str, Any] = {
        "answer_mode": "spl_utility_authoring",
        "candidate_spl": {
            "candidate_spl": "search index=<your_index> | stats count",
            "utility_spl_draft_trace": {
                "analyst_synthesis_source": "DETERMINISTIC_SYNTHESIS_FALLBACK",
                "analyst_synthesis": {"summary": "x"},
                "semantic_fidelity_final": {"passed": True, "losses": []},
                "final_raw_spl_source": "deterministic_compiler",
            },
            "review_only_spl_postprocessor_trace": {
                "placeholder_used": True,
                "resolved_index": "<your_index>",
                "postprocessor_applied": True,
            },
        },
        "spl_validation": {"approved": False, "reject_reasons": ["review_only_spl_authoring"]},
        "execution": {"status": "skipped"},
        "human_review": {
            "required": True,
            "review_type": "spl_source_profile_clarification",
            "reason": "source_profile_slots_missing",
        },
        "run_contract": {"execution_needed_for_answer": False, "spl_candidate_present": True},
        "control_plane_trace": {
            "evidence_plan": {
                "needs_spl": True,
                "needs_rag": False,
                "source_profile_binding_summary": {
                    "source_profile_bindings_missing": [],
                    "source_profile_bindings_applied": [
                        {"slot": "index", "value": "pgcil_soc", "source": "coe_store"},
                    ],
                },
            },
            "query_to_intent": {"query_signals": {"review_only_spl": True}},
            "mcp_execution": {"status": "skipped", "result_count": 0},
            "spl_artifact_handoff_summary": {"review_only": True, "artifact_present": True},
        },
    }
    payload.update(overrides)
    return payload


# --- Invariant 1 ------------------------------------------------------------


def test_skipped_execution_never_reports_obtained_executed_evidence(
    p2_effective_state: dict[str, Any],
) -> None:
    """Execution skipped with zero rows cannot yield obtained executed evidence."""
    execution = p2_effective_state["execution"]
    evidence = p2_effective_state["evidence"]
    assert execution["mcp_status"] == "skipped"
    assert execution["result_count"] == 0
    assert evidence["executed_evidence"]["status"] != "obtained"
    assert evidence["live_execution_evidence_available"] is False


def test_knowledge_record_is_not_projected_as_executed_evidence() -> None:
    """A governed RAG record must not satisfy the executed-evidence key.

    CanonicalFacts uses one `executed_evidence` kind for every SourceEvidence
    record; only execution provenance may claim the EvidenceState key.
    """
    from app.evidence.minimal_evidence_state import derive_minimal_evidence_state

    state = derive_minimal_evidence_state(
        canonical_facts={
            "facts": [
                {
                    "kind": "executed_evidence",
                    "payload": {"row_count": 5, "row_summary": [{"doc_id": "kb1"}]},
                    "provenance": {"node": "source_evidence", "evidence_class": "rag"},
                }
            ]
        },
        execution={"status": "skipped"},
    )
    assert "executed_evidence" not in state.obtained
    assert "source_evidence" in state.obtained


def test_mcp_search_record_still_claims_executed_evidence() -> None:
    """The rename must not hide genuine execution provenance."""
    from app.evidence.minimal_evidence_state import derive_minimal_evidence_state

    state = derive_minimal_evidence_state(
        canonical_facts={
            "facts": [
                {
                    "kind": "executed_evidence",
                    "payload": {"row_count": 3, "row_summary": [{"user": "a"}]},
                    "provenance": {"node": "mcp_execution", "evidence_class": "mcp_search"},
                }
            ]
        },
        execution={"status": "completed"},
    )
    assert "executed_evidence" in state.obtained


# --- Invariant 2 ------------------------------------------------------------


def test_resolved_bindings_never_leave_source_profile_slots_missing_as_final_reason(
    p2_effective_state: dict[str, Any],
) -> None:
    assert p2_effective_state["source_profile"]["bindings_missing"] == []
    assert p2_effective_state["hil"]["final_hil_reason"] != "source_profile_slots_missing"
    assert p2_effective_state["hil"]["current_turn_hil_reason"] != "source_profile_slots_missing"


def test_genuinely_missing_binding_is_not_suppressed() -> None:
    """The supersede rule must not swallow a real missing binding."""
    payload = _review_only_payload()
    binding = payload["control_plane_trace"]["evidence_plan"]["source_profile_binding_summary"]
    binding["source_profile_bindings_missing"] = ["index"]
    binding["source_profile_bindings_applied"] = []
    state = build_effective_state_projection(payload)
    assert state["hil"]["current_turn_hil_required"] is True
    assert state["hil"]["current_turn_hil_reason"] == "source_profile_slots_missing"
    assert state["hil"]["superseded_by_final_resolution"] is False


def test_non_source_profile_review_is_never_superseded() -> None:
    """Any other HIL kind passes through untouched."""
    payload = _review_only_payload()
    payload["human_review"] = {
        "required": True,
        "review_type": "intent_clarification",
        "reason": "ambiguous_request",
    }
    state = build_effective_state_projection(payload)
    assert state["hil"]["current_turn_hil_required"] is True
    assert state["hil"]["current_turn_hil_reason"] == "ambiguous_request"
    assert state["hil"]["superseded_by_final_resolution"] is False


# --- Invariant 3 ------------------------------------------------------------


def test_review_only_do_not_execute_turn_is_not_blocked_for_hil(
    p2_effective_state: dict[str, Any],
) -> None:
    assert p2_effective_state["answer_mode"] == "spl_utility_authoring"
    assert p2_effective_state["explicit_do_not_execute"] is True
    assert p2_effective_state["hil"]["current_turn_hil_required"] is False
    # The deferred execution requirement survives.
    assert p2_effective_state["hil"]["execution_hil_required"] is True
    assert p2_effective_state["status"]["execution_approval_required_if_requested"] is True


def test_explicit_execution_request_is_not_treated_as_do_not_execute() -> None:
    payload = _review_only_payload()
    payload["control_plane_trace"]["query_to_intent"]["query_signals"]["run_execution"] = True
    state = build_effective_state_projection(payload)
    assert state["explicit_do_not_execute"] is False
    assert state["hil"]["current_turn_hil_required"] is True


# --- Invariant 4 ------------------------------------------------------------


def test_rendered_spl_reports_an_available_artifact(p2_effective_state: dict[str, Any]) -> None:
    assert p2_effective_state["spl_authoring"]["spl_artifact_available"] is True
    assert p2_effective_state["evidence"]["spl_artifact"]["status"] == "obtained"
    assert p2_effective_state["evidence"]["artifact_evidence_available"] is True


def test_spl_key_gap_is_labelled_as_an_execution_result() -> None:
    """`spl` in the raw missing list means executed SPL result, and says so."""
    summary = build_debug_summary(payload=_p2_payload())
    items = {item["key"]: item for item in summary["evidence_state"]["items"]}
    assert items["spl"]["status"] == "missing"
    assert items["spl"]["applicability"] == "executed_spl_result"
    assert summary["effective_state"]["evidence"]["spl_execution_result"]["status"] == "not_applicable"


# --- Invariant 5 ------------------------------------------------------------


def test_absent_normalized_spl_forbids_execution_eligibility(
    p2_effective_state: dict[str, Any],
) -> None:
    validation = p2_effective_state["validation"]
    assert validation["normalized_spl_available"] is False
    assert validation["execution_eligible"] is False
    assert validation["approved"] is False
    assert p2_effective_state["execution"]["execution_eligible"] is False


@pytest.mark.parametrize("normalized", [None, "", False])
def test_execution_eligible_requires_normalized_spl(normalized: Any) -> None:
    payload = _review_only_payload()
    payload["spl_validation"] = {"approved": False, "normalized_spl": normalized, "execution_eligible": False}
    state = build_effective_state_projection(payload)
    assert state["validation"]["normalized_spl_available"] is False
    assert state["execution"]["execution_eligible"] is False


# --- Invariants 6 and 7 -----------------------------------------------------


def test_llm_synthesis_source_requires_a_synthesis_call() -> None:
    payload = _review_only_payload()
    trace = payload["candidate_spl"]["utility_spl_draft_trace"]
    trace["analyst_synthesis_source"] = "LLM_SYNTHESIS"
    trace["analyst_synthesis_llm_attempted"] = True
    trace["analyst_synthesis_latency_ms"] = 812
    state = build_effective_state_projection(payload)
    assert state["synthesis"]["synthesis_source"] == "LLM_SYNTHESIS"
    assert state["synthesis"]["llm_call_attempted"] is True
    assert state["synthesis"]["synthesis_latency_ms"] == 812
    assert state["llm"]["llm_used_for_synthesis"] is True
    assert state["llm"]["llm_contributed_to_final_output"] is True


def test_deterministic_synthesis_makes_no_llm_contribution_claim(
    p2_effective_state: dict[str, Any],
) -> None:
    synthesis = p2_effective_state["synthesis"]
    assert synthesis["synthesis_source"] == "DETERMINISTIC_SYNTHESIS_FALLBACK"
    assert synthesis["synthesis_status"] == "deterministic_fallback_used"
    assert p2_effective_state["llm"]["llm_used_for_synthesis"] is False
    assert p2_effective_state["llm"]["llm_contributed_to_final_output"] is False
    assert p2_effective_state["llm"]["legacy_llm_used"] is False


def test_synthesis_provenance_is_always_recoverable(p2_effective_state: dict[str, Any]) -> None:
    """The bundle must never leave the analyst prose unattributed."""
    synthesis = p2_effective_state["synthesis"]
    assert synthesis["synthesis_source"] in {
        "LLM_SYNTHESIS",
        "DETERMINISTIC_SYNTHESIS_FALLBACK",
    }
    assert synthesis["synthesis_attempted"] is True
    assert synthesis["synthesis_grounding_status"]
    # Composer silence must not be mistaken for "no synthesis happened".
    assert synthesis["composer_attempted"] is False


# --- Invariant 8 ------------------------------------------------------------


def test_deterministic_final_spl_never_credits_a_rejected_llm_candidate(
    p2_effective_state: dict[str, Any],
) -> None:
    authoring = p2_effective_state["spl_authoring"]
    lifecycle = p2_effective_state["llm_spl_candidate_lifecycle"]
    assert authoring["final_raw_spl_source"] == "deterministic_compiler"
    assert lifecycle["used"] is False
    assert p2_effective_state["llm"]["llm_used_for_spl_authoring"] is False
    assert p2_effective_state["validation"]["final_spl_source"] == "deterministic_compiler"


def test_candidate_lifecycle_reports_an_ordered_stop_point(
    p2_effective_state: dict[str, Any],
) -> None:
    """A dropped candidate must say where it stopped, not just that it dropped."""
    lifecycle = p2_effective_state["llm_spl_candidate_lifecycle"]
    assert lifecycle["requested"] is True
    assert lifecycle["failure_stage"] == "provider"
    assert lifecycle["transport_completed"] is False
    for step in ("parsed", "schema_valid", "quality_passed", "fidelity_passed"):
        assert lifecycle[step] == "not_reached", step


def test_candidate_lifecycle_marks_steps_reached_before_a_later_failure() -> None:
    payload = _review_only_payload()
    payload["candidate_spl"]["utility_spl_draft_trace"].update(
        {"llm_spl_draft_requested": True, "authoring_failure_stage": "draft_quality"}
    )
    lifecycle = build_effective_state_projection(payload)["llm_spl_candidate_lifecycle"]
    assert lifecycle["transport_completed"] is True
    assert lifecycle["parsed"] is True
    assert lifecycle["schema_valid"] is True
    assert lifecycle["quality_passed"] is False
    assert lifecycle["fidelity_passed"] == "not_reached"


# --- Invariant 9 ------------------------------------------------------------


def test_unplanned_retrieval_is_classified_as_enrichment_not_runtime_rag(
    p2_effective_state: dict[str, Any],
) -> None:
    rag = p2_effective_state["rag"]
    assert rag["planned_needs_rag"] is False
    assert rag["retrieval_status"] == "retrieved"
    assert rag["runtime_rag_used"] is False
    assert rag["enrichment_lookup_used"] is True
    assert rag["retrieval_workflow_stage"] == "spl_source_resolve"
    assert rag["enrichment_purpose"] == "source_profile_hint"


def test_planned_rag_retrieval_is_reported_as_runtime_rag() -> None:
    payload = _review_only_payload()
    payload["control_plane_trace"]["evidence_plan"]["needs_rag"] = True
    payload["control_plane_trace"]["rag_trace"] = {"retrieval_status": "retrieved"}
    rag = build_effective_state_projection(payload)["rag"]
    assert rag["runtime_rag_used"] is True
    assert rag["enrichment_lookup_used"] is False


# --- Invariant 10 -----------------------------------------------------------


def test_superseded_stage_reason_is_retained_as_history_not_as_final_state(
    p2_effective_state: dict[str, Any],
) -> None:
    """History is preserved; only the final summary fields must be current."""
    hil = p2_effective_state["hil"]
    assert hil["initial_hil_candidate_reason"] == "source_profile_slots_missing"
    assert hil["initial_hil_candidate_stage"] == "spl_source_resolve"
    assert hil["superseded_by"] == "source_profile_binding_summary"
    assert hil["final_hil_reason"] is None


def test_source_profile_separates_resolution_from_review_draft_exposure(
    p2_effective_state: dict[str, Any],
) -> None:
    """Issue 2: a resolved binding and a displayed placeholder must both be legible."""
    slots = p2_effective_state["source_profile"]["slots"]
    assert slots["index"]["resolved"] is True
    assert slots["index"]["resolved_value"] == "pgcil_soc"
    assert slots["index"]["resolution_source"] == "coe_store"
    assert slots["index"]["exposed_in_review_draft"] is False
    assert slots["index"]["display_value"] == "<your_index>"
    assert slots["index"]["withholding_reason"] == "review_only_placeholder_policy"
    assert slots["sourcetype"]["exposed_in_review_draft"] is True
    assert slots["sourcetype"]["display_value"] == "pgcil:auth"
    assert slots["sourcetype"]["withholding_reason"] is None


def test_review_draft_binding_a_different_value_is_not_called_withholding() -> None:
    """P1: the draft used a user-explicit index, which is not placeholder policy.

    Labelling every unexposed binding "review_only_placeholder_policy" would put a
    fresh false statement into the bundle -- the exact class of defect this work
    exists to remove.
    """
    payload = _review_only_payload()
    payload["candidate_spl"]["candidate_spl"] = "search index=wineventlog sourcetype=pgcil:auth | stats count"
    payload["candidate_spl"]["review_only_spl_postprocessor_trace"] = {"placeholder_used": False}
    slots = build_effective_state_projection(payload)["source_profile"]["slots"]
    assert slots["index"]["resolved_value"] == "pgcil_soc"
    assert slots["index"]["exposed_in_review_draft"] is False
    assert slots["index"]["display_value"] == "wineventlog"
    assert slots["index"]["withholding_reason"] == "draft_uses_different_value"


def test_unbound_placeholders_are_reported_even_when_no_binding_is_missing() -> None:
    """P4: `bindings_missing == []` must not read as "the draft is ready to run"."""
    payload = _review_only_payload()
    payload["candidate_spl"]["candidate_spl"] = "search index=<your_index> sourcetype=<dns_sourcetype> | stats count"
    binding = payload["control_plane_trace"]["evidence_plan"]["source_profile_binding_summary"]
    binding["source_profile_bindings_applied"] = []
    source_profile = build_effective_state_projection(payload)["source_profile"]
    assert source_profile["bindings_missing"] == []
    assert source_profile["unbound_placeholders_in_review_draft"] == ["<dns_sourcetype>", "<your_index>"]
    assert source_profile["review_draft_fully_bound"] is False


def test_p2_placeholder_substitution_is_still_labelled_as_policy(
    p2_effective_state: dict[str, Any],
) -> None:
    source_profile = p2_effective_state["source_profile"]
    assert source_profile["slots_resolved_but_withheld_from_review_draft"] == ["index"]
    assert source_profile["unbound_placeholders_in_review_draft"] == []
    assert source_profile["review_draft_fully_bound"] is False


def test_validation_separates_authoring_from_execution_promotion(
    p2_effective_state: dict[str, Any],
) -> None:
    """Issue 7: the compiler SPL was not the thing the validator refused."""
    validation = p2_effective_state["validation"]
    assert validation["authoring_fidelity_status"] == "passed"
    assert validation["candidate_spl_validation_status"] == "withheld_review_only"
    assert validation["execution_validation_status"] == "not_applicable_review_only"
    assert validation["final_spl_rejected_by_validator"] is False
    assert validation["legacy_validator_status"] == "rejected"


def test_investigation_plan_metadata_is_marked_non_runtime(
    p2_effective_state: dict[str, Any],
) -> None:
    """Issue 10: DNS legs and MITRE candidates were never runtime inputs here."""
    classification = p2_effective_state["evidence_plan_classification"]
    assert classification["runtime_required"]["spl"] is True
    assert classification["runtime_required"]["mcp"] is False
    assert classification["runtime_required"]["mitre"] is False
    assert "evidence_legs" in classification["planning_metadata_only"]
    assert "mitre_candidates_metadata_only" in classification["planning_metadata_only"]
    assert classification["runtime_required_flag"] is False


def test_source_evidence_availability_is_split_by_kind(
    p2_effective_state: dict[str, Any],
) -> None:
    """Issue 11: a knowledge record must not read as live telemetry."""
    evidence = p2_effective_state["evidence"]
    assert evidence["legacy_source_evidence_available"] is True
    assert evidence["knowledge_evidence_available"] is True
    assert evidence["artifact_evidence_available"] is True
    assert evidence["live_execution_evidence_available"] is False


def test_projection_never_raises_on_degenerate_payloads() -> None:
    for payload in (None, {}, {"control_plane_trace": "not-a-dict"}, {"candidate_spl": []}):
        assert isinstance(build_effective_state_projection(payload), dict)  # type: ignore[arg-type]
