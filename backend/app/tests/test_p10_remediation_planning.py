"""P10 — remediation proposal + Approve/Edit/Cancel, with no side effect before approval."""

from __future__ import annotations

import json

import pytest

from app.chat.contracts.remediation_plan import (
    ApprovedRemediationEnvelope,
    RemediationPlanProposal,
    ValidatedRemediationPlan,
)
from app.chat.remediation_plan_builder import build_deterministic_remediation_plan
from app.chat.remediation_plan_reasoner import propose_remediation_plan
from app.chat.remediation_plan_validator import validate_remediation_plan
from app.chat.remediation_runtime import (
    build_validated_remediation_plan,
    handle_remediation_review,
    maybe_attach_remediation_offer,
)
from app.config import settings
from app.llm.turn_llm_budget import TurnLlmBudget


@pytest.fixture(autouse=True)
def _enable_p10(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "ai_soc_remediation_planner_enabled", True)


def _snapshot(**availability: str) -> dict:
    return {
        "schema_version": "capability_snapshot_v1",
        "rows": [
            {"capability_id": key, "capability_need": "recommended", "availability": value}
            for key, value in availability.items()
        ],
    }


def _outcome(**overrides) -> dict:
    payload = {
        "schema_version": "investigation_outcome_v2",
        "investigation_status": "completed",
        "disposition": "suspicious",
        "severity_label": "P2",
        "remediation_offer_required": True,
        "action_eligibility": {
            "allowed_actions": ["email_send"],
            "unavailable_actions": ["firewall_block"],
            "hil_required": True,
            "current_tier": 1,
        },
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------- deterministic baseline


def test_available_capability_becomes_executable_step() -> None:
    plan = build_deterministic_remediation_plan(
        investigation_outcome=_outcome(),
        capability_snapshot=_snapshot(email_send="available"),
    )
    step = next(item for item in plan.steps if item.capability_id == "email_send")
    assert step.execution_mode == "execute"
    assert step.availability == "available"
    assert step.verification


def test_unavailable_capability_stays_as_manual_step_not_dropped() -> None:
    plan = build_deterministic_remediation_plan(
        investigation_outcome=_outcome(),
        capability_snapshot=_snapshot(email_send="available"),
    )
    firewall = next(item for item in plan.steps if item.capability_id == "firewall_block")
    assert firewall.execution_mode == "manual_or_alternate"
    assert firewall.availability == "unavailable"
    assert firewall.unavailable_reason
    assert firewall.step_id in plan.manual_only_steps


def test_unregistered_connector_is_not_executable_even_when_action_allowed() -> None:
    """Agilius/SOAR absent means manual path, never a silent success."""
    plan = build_deterministic_remediation_plan(
        investigation_outcome=_outcome(
            action_eligibility={"allowed_actions": ["agilius_patch_submit"], "unavailable_actions": []}
        ),
        capability_snapshot=_snapshot(),
    )
    step = plan.steps[0]
    assert step.execution_mode == "manual_or_alternate"
    assert step.unavailable_reason == "capability_not_registered"


def test_plan_never_carries_execution_authorization() -> None:
    plan = build_deterministic_remediation_plan(
        investigation_outcome=_outcome(),
        capability_snapshot=_snapshot(email_send="available"),
    )
    assert plan.execution_authorized is False
    assert plan.human_approval_required is True
    with pytest.raises(Exception):
        ValidatedRemediationPlan.model_validate(
            {**plan.model_dump(mode="json"), "execution_authorized": True}
        )


# ---------------------------------------------------------------- advisory validation


def test_model_cannot_introduce_a_capability_not_in_the_baseline() -> None:
    baseline = build_deterministic_remediation_plan(
        investigation_outcome=_outcome(),
        capability_snapshot=_snapshot(email_send="available"),
    )
    validated = validate_remediation_plan(
        baseline,
        RemediationPlanProposal(capability_requests=["isolate_endpoint", "wipe_disk"]),
        llm_attempted=True,
    )
    assert {step.capability_id for step in validated.steps} == {"email_send", "firewall_block"}
    assert "capability_requests_not_in_snapshot_baseline" in validated.dropped_reasons


def test_model_cannot_claim_the_action_already_ran() -> None:
    baseline = build_deterministic_remediation_plan(
        investigation_outcome=_outcome(),
        capability_snapshot=_snapshot(email_send="available"),
    )
    validated = validate_remediation_plan(
        baseline,
        RemediationPlanProposal(remediation_objective="Block executed and already applied."),
        llm_attempted=True,
    )
    assert validated.remediation_objective == baseline.remediation_objective
    assert "objective_implies_completed_or_self_authorized_action" in validated.dropped_reasons


def test_unreachable_reasoner_falls_back_to_deterministic_baseline() -> None:
    baseline = build_deterministic_remediation_plan(
        investigation_outcome=_outcome(),
        capability_snapshot=_snapshot(email_send="available"),
    )
    validated = validate_remediation_plan(baseline, None, llm_attempted=True)
    assert validated.plan_source == "llm_failed_baseline_only"
    assert validated.steps == baseline.steps


def test_reasoner_hop_is_bounded_by_turn_budget() -> None:
    baseline = build_deterministic_remediation_plan(
        investigation_outcome=_outcome(),
        capability_snapshot=_snapshot(email_send="available"),
    )
    exhausted = TurnLlmBudget(deadline_seconds=0.0001)
    result = propose_remediation_plan(baseline=baseline, turn_budget=exhausted)
    assert result.attempted is False
    assert result.trace["skipped_reason"] == "turn_budget_exhausted"


def test_reasoner_prompt_carries_no_case_data() -> None:
    baseline = build_deterministic_remediation_plan(
        investigation_outcome=_outcome(),
        capability_snapshot=_snapshot(email_send="available"),
    )
    captured: dict[str, str] = {}

    def _provider() -> str:
        return json.dumps({"remediation_objective": "Notify the owning team."})

    result = propose_remediation_plan(baseline=baseline, raw_output_provider=_provider)
    assert result.proposal == {"remediation_objective": "Notify the owning team."}
    assert captured == {}
    assert result.trace["authority"] == "advisory"


# ---------------------------------------------------------------- HIL lifecycle


def test_offer_is_attached_when_outcome_requires_it() -> None:
    state = maybe_attach_remediation_offer({"investigation_outcome": _outcome()})
    approval = state["remediation_approval"]
    assert approval["status"] == "offered"
    assert approval["allowed_actions"] == ["create", "decline"]
    assert approval["validated_plan"] is None


def test_offer_is_skipped_when_rqc_already_requested_remediation() -> None:
    """P8 sets remediation_offer_required=False; P10 must not re-ask."""
    state = maybe_attach_remediation_offer(
        {"investigation_outcome": _outcome(remediation_offer_required=False)}
    )
    assert "remediation_approval" not in state


def test_offer_is_skipped_for_cancelled_investigation() -> None:
    state = maybe_attach_remediation_offer(
        {"investigation_outcome": _outcome(investigation_status="cancelled")}
    )
    assert "remediation_approval" not in state


def test_create_then_approve_produces_envelope_and_no_execution() -> None:
    state = {
        "investigation_outcome": _outcome(),
        "capability_snapshot": _snapshot(email_send="available"),
        "approved_investigation_envelope": {"envelope_version": 2},
    }
    created = handle_remediation_review(state, action="create")
    assert created["remediation_approval"]["status"] == "awaiting_approval"
    assert created["remediation_approval"]["allowed_actions"] == ["approve", "edit", "cancel"]
    assert "approved_remediation_envelope" not in created

    approved = handle_remediation_review(created, action="approve")
    envelope = ApprovedRemediationEnvelope.model_validate(
        approved["approved_remediation_envelope"]
    )
    assert envelope.envelope_version >= 1
    assert envelope.plan_fingerprint
    assert envelope.investigation_envelope_version == 2
    assert envelope.executable_capability_ids() == ["email_send"]


def test_cancel_leaves_no_envelope() -> None:
    state = {
        "investigation_outcome": _outcome(),
        "capability_snapshot": _snapshot(email_send="available"),
    }
    created = handle_remediation_review(state, action="create")
    cancelled = handle_remediation_review(created, action="cancel")
    assert cancelled["remediation_approval"]["status"] == "cancelled"
    assert "approved_remediation_envelope" not in cancelled


def test_decline_records_no_plan() -> None:
    declined = handle_remediation_review(
        {"investigation_outcome": _outcome()}, action="decline"
    )
    assert declined["remediation_approval"]["status"] == "declined"
    assert declined["remediation_approval"]["validated_plan"] is None


def test_edit_revalidates_and_cannot_invent_a_step() -> None:
    state = {
        "investigation_outcome": _outcome(),
        "capability_snapshot": _snapshot(email_send="available"),
    }
    created = handle_remediation_review(state, action="create")
    step_ids = [step["step_id"] for step in created["remediation_approval"]["validated_plan"]["steps"]]
    edited = handle_remediation_review(
        created,
        action="edit",
        edits={
            "removed_step_ids": [step_ids[0]],
            "step_descriptions": {"rem.99.invented": "do something else"},
        },
    )
    approval = edited["remediation_approval"]
    assert approval["status"] == "edited_revalidated"
    remaining = [step["step_id"] for step in approval["validated_plan"]["steps"]]
    assert step_ids[0] not in remaining
    assert "rem.99.invented" not in remaining
    assert "edit_referenced_unknown_step_ids" in approval["revalidation_warnings"]


def test_approve_without_a_plan_is_refused() -> None:
    with pytest.raises(ValueError, match="remediation_plan_missing_for_approval"):
        handle_remediation_review({"investigation_outcome": _outcome()}, action="approve")


def test_unsupported_action_is_refused() -> None:
    with pytest.raises(ValueError, match="unsupported_remediation_review_action"):
        handle_remediation_review({"investigation_outcome": _outcome()}, action="execute")


def test_flag_off_produces_no_remediation_surface(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_remediation_planner_enabled", False)
    state = maybe_attach_remediation_offer({"investigation_outcome": _outcome()})
    assert "remediation_approval" not in state
    plan, trace = build_validated_remediation_plan(
        investigation_outcome=_outcome(),
        capability_snapshot=_snapshot(email_send="available"),
    )
    assert trace["skipped_reason"] == "remediation_planner_disabled"
    assert plan.plan_source == "deterministic_only"


def test_no_connector_module_is_imported_by_the_planning_path() -> None:
    """Planning must not be able to reach a transport, even accidentally."""
    import app.chat.remediation_runtime as runtime
    import app.chat.remediation_plan_builder as builder

    for module in (runtime, builder):
        source = module.__doc__ or ""
        assert "smtp" not in source.lower()
    assert not hasattr(runtime, "send_email")
    assert not hasattr(builder, "send_email")


# ------------------------------------------- defects found by live COE probing


def test_tier1_answer_affordances_never_become_remediation_steps() -> None:
    """Live probe produced steps like "Perform summarize manually".

    ``ActionCapability.allowed_actions`` at tier 1 is an answer-affordance vocabulary,
    not a set of estate-changing actions. Those must not enter a remediation plan.
    """
    plan = build_deterministic_remediation_plan(
        investigation_outcome=_outcome(
            action_eligibility={
                "allowed_actions": [
                    "summarize",
                    "explain",
                    "show_sop",
                    "generate_spl",
                    "draft_investigation_note",
                ],
                "unavailable_actions": ["run_saved_search", "block_ip"],
            }
        ),
        capability_snapshot=_snapshot(),
    )
    capability_ids = {step.capability_id for step in plan.steps}
    for affordance in (
        "summarize",
        "explain",
        "show_sop",
        "generate_spl",
        "draft_investigation_note",
        "run_saved_search",
    ):
        assert affordance not in capability_ids
    assert "block_ip" in capability_ids
    assert any(reason.startswith("answer_affordance_is_not_remediation") for reason in plan.dropped_reasons)


def test_unonboarded_connector_is_kept_as_a_manual_step() -> None:
    """An unknown identifier is a future connector, not an affordance — keep it visible."""
    plan = build_deterministic_remediation_plan(
        investigation_outcome=_outcome(
            action_eligibility={"allowed_actions": ["agilus_submit_patch"], "unavailable_actions": []}
        ),
        capability_snapshot=_snapshot(),
    )
    step = next(item for item in plan.steps if item.capability_id == "agilus_submit_patch")
    assert step.execution_mode == "manual_or_alternate"


def test_available_write_capability_enters_the_plan_without_a_tier1_mention() -> None:
    """A registered, available connector is a real option even if tier 1 never lists it."""
    plan = build_deterministic_remediation_plan(
        investigation_outcome=_outcome(
            action_eligibility={"allowed_actions": ["summarize"], "unavailable_actions": []}
        ),
        capability_snapshot=_snapshot(email_send="available"),
    )
    step = next(item for item in plan.steps if item.capability_id == "email_send")
    assert step.execution_mode == "execute"


def test_approve_binds_to_the_plan_shown_on_an_earlier_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Create and Approve arrive on separate /chat turns; state does not carry the plan."""
    from app.chat.session_store import (
        SessionPins,
        clear_all_session_pins_for_tests,
        get_session_pins,
        save_session_pins,
    )

    clear_all_session_pins_for_tests()
    session_id = "session-remediation-1"
    save_session_pins(SessionPins(session_id=session_id))

    create_state = {
        "session_id": session_id,
        "investigation_outcome": _outcome(),
        "capability_snapshot": _snapshot(email_send="available"),
    }
    created = handle_remediation_review(create_state, action="create")
    shown = [step["step_id"] for step in created["remediation_approval"]["validated_plan"]["steps"]]
    assert shown

    pins = get_session_pins(session_id)
    assert pins is not None and pins.pending_remediation_plan is not None

    # A later turn: fresh state, same session, no approval payload carried over.
    approve_state = {
        "session_id": session_id,
        "investigation_outcome": _outcome(),
        "capability_snapshot": _snapshot(email_send="available"),
    }
    approved = handle_remediation_review(approve_state, action="approve")
    envelope = approved["approved_remediation_envelope"]
    assert [step["step_id"] for step in envelope["approved_steps"]] == shown
    assert get_session_pins(session_id).pending_remediation_plan is None
