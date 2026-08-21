"""P13 — end-to-end investigation acceptance: scenarios A-E, negatives, parity, UX.

Deterministic and mocked. This is the regression gate; the live COE probe
(``scripts/probe_investigation_lifecycle.py``) is complementary evidence, not a
substitute — a 300s-per-query live probe cannot gate a suite.

The assertions here are the §7 negative list and the §6 scenarios expressed as
behaviour: what the architecture must refuse, not what a model happens to say.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.chat.capability_snapshot import CapabilitySnapshot
from app.chat.contracts.investigation_envelope import ApprovedInvestigationEnvelope
from app.chat.contracts.investigation_outcome import derive_investigation_outcome
from app.chat.contracts.remediation_plan import ValidatedRemediationPlan
from app.chat.guided_investigation_plan_llm import (
    INVESTIGATION_PLAN_ROLE,
    propose_investigation_plan_llm,
)
from app.chat.investigation_plan_builder import build_deterministic_investigation_plan
from app.chat.investigation_shaped import (
    INVESTIGATION_INTENT_FAMILIES,
    is_investigation_shaped_final_rqc,
)
from app.chat.remediation_plan_builder import build_deterministic_remediation_plan
from app.chat.remediation_runtime import handle_remediation_review
from app.config import settings
from app.llm.sidecar_clients import _REASONING_ALLOWED_ROLES
from app.llm.turn_llm_budget import TurnLlmBudget

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _snapshot(**availability: str) -> dict:
    return {
        "schema_version": "capability_snapshot_v1",
        "rows": [
            {"capability_id": key, "capability_need": "required", "availability": value}
            for key, value in availability.items()
        ],
    }


def _outcome_payload(**overrides) -> dict:
    payload = {
        "schema_version": "investigation_outcome_v2",
        "investigation_status": "completed",
        "disposition": "inconclusive",
        "remediation_offer_required": True,
        "action_eligibility": {
            "allowed_actions": ["email_send", "firewall_block"],
            "unavailable_actions": [],
        },
    }
    payload.update(overrides)
    return payload


# =====================================================================  scenarios A-E


def test_scenario_a_new_ip_plan_binds_only_snapshot_capabilities() -> None:
    """A: a plan may want Splunk, but only snapshot rows may be bound."""
    plan = build_deterministic_investigation_plan(
        query="Check 198.51.100.42 over the last 30 days and determine if it is malicious.",
        entities={"src_ip": "198.51.100.42"},
        resolved_query_contract={"intent_family": "live_investigation"},
        capability_snapshot=_snapshot(splunk_search="available"),
    )
    bound = {binding.capability_id for binding in plan.capability_bindings}
    assert bound <= {"splunk_search"}


def test_scenario_b_ssh_pattern_alone_is_never_confirmed_compromise() -> None:
    """B: 25 failures then a success is a pattern, not a determination."""
    outcome = derive_investigation_outcome(
        evidence_sufficiency={"status": "INSUFFICIENT", "missing": ["authentication_correlation"]},
        canonical_facts={"facts": []},
        structured_context={},
        severity_label="P2",
        outcome_v2_enabled=True,
    )
    assert outcome.disposition == "inconclusive"
    assert outcome.investigation_status != "completed"


def test_scenario_c_zero_day_missing_patch_connector_is_manual_not_executed() -> None:
    """C: no Agilius/patch connector means a manual change step, never a claim."""
    plan = build_deterministic_remediation_plan(
        investigation_outcome=_outcome_payload(
            action_eligibility={"allowed_actions": ["agilus_submit_patch"], "unavailable_actions": []}
        ),
        capability_snapshot=_snapshot(),
    )
    step = plan.steps[0]
    assert step.execution_mode == "manual_or_alternate"
    assert step.unavailable_reason == "capability_not_registered"
    assert plan.execution_authorized is False


def test_scenario_d_tool_failure_does_not_silently_become_rag_only() -> None:
    """D: an unavailable tool is an honest gap row, not a quiet knowledge dump."""
    plan = build_deterministic_investigation_plan(
        query="Hunt for lateral movement across the OT network.",
        entities=None,
        resolved_query_contract={"intent_family": "guided_investigation"},
        capability_snapshot=_snapshot(splunk_search="unavailable"),
    )
    unavailable = [
        binding for binding in plan.capability_bindings if binding.availability == "unavailable"
    ]
    assert unavailable, "an unavailable required capability must remain visible in the plan"
    assert all(binding.access_mode != "read_only" for binding in unavailable)


def test_scenario_e_missing_firewall_connector_shows_manual_path() -> None:
    """E: firewall recommended but absent -> manual governed workflow."""
    plan = build_deterministic_remediation_plan(
        investigation_outcome=_outcome_payload(
            action_eligibility={"allowed_actions": [], "unavailable_actions": ["firewall_block"]}
        ),
        capability_snapshot=_snapshot(),
    )
    step = next(item for item in plan.steps if item.capability_id == "firewall_block")
    assert step.execution_mode == "manual_or_alternate"
    assert step.step_id in plan.manual_only_steps


# =====================================================  §7 authority / security negatives


def test_capability_snapshot_is_not_execution_authorization() -> None:
    snapshot = CapabilitySnapshot.model_validate(_snapshot(splunk_search="available"))
    payload = snapshot.model_dump()
    assert "executable" not in payload
    assert "auth" not in str(payload).lower()


def test_snapshot_carries_no_rbac_axis() -> None:
    """RBAC is a later gate; it must not be encoded as capability absence."""
    row = CapabilitySnapshot.model_validate(_snapshot(splunk_search="available")).rows[0]
    assert set(row.model_dump()) == {"capability_id", "capability_need", "availability"}


def test_t4_cannot_become_the_investigation_planner() -> None:
    assert _REASONING_ALLOWED_ROLES == frozenset({INVESTIGATION_PLAN_ROLE})
    assert "t4_semantic" not in _REASONING_ALLOWED_ROLES


def test_llm_cannot_grant_a_capability() -> None:
    plan = build_deterministic_investigation_plan(
        query="investigate",
        entities=None,
        resolved_query_contract={},
        capability_snapshot=_snapshot(splunk_search="available"),
    )
    from app.chat.guided_investigation_planner import validate_investigation_plan

    validated = validate_investigation_plan(
        plan,
        {"capability_requests": ["firewall_block", "agilus_submit_patch"]},
        llm_attempted=True,
        capability_snapshot=_snapshot(splunk_search="available"),
    )
    bound = {binding.capability_id for binding in validated.capability_bindings}
    assert "firewall_block" not in bound
    assert "agilus_submit_patch" not in bound


def test_remediation_cannot_execute_before_approval() -> None:
    from app.actions.remediation_execution import execute_approved_remediation

    plan = build_deterministic_remediation_plan(
        investigation_outcome=_outcome_payload(),
        capability_snapshot=_snapshot(email_send="available"),
    )
    assert plan.execution_authorized is False
    with pytest.raises(Exception):
        execute_approved_remediation(approved_envelope=plan.model_dump(mode="json"))


def test_remediation_execution_cannot_diverge_from_approved_plan_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.actions.remediation_execution import execute_approved_remediation

    monkeypatch.setattr(settings, "ai_soc_remediation_planner_enabled", True)
    state = {
        "investigation_outcome": _outcome_payload(),
        "capability_snapshot": _snapshot(email_send="available"),
    }
    created = handle_remediation_review(state, action="create")
    approved = handle_remediation_review(created, action="approve")
    result = execute_approved_remediation(
        approved_envelope=approved["approved_remediation_envelope"],
        current_plan_fingerprint="a-different-plan",
    )
    assert result.refused_reason == "approved_plan_superseded"
    assert result.receipts == []


def test_investigation_plan_delta_cannot_send_email() -> None:
    source = (_BACKEND_ROOT / "app" / "chat" / "investigation_plan_delta.py").read_text(
        encoding="utf-8"
    )
    for forbidden in ("email_adapter", "send_remediation_email", "remediation_execution"):
        assert forbidden not in source


def test_production_chat_does_not_import_ec_demo_action_fixtures() -> None:
    completed = subprocess.run(
        [
            "grep",
            "-rnE",
            r"from app\.demo(\.| import).*(ec_email|ec_soar|ec_agent)",
            str(_BACKEND_ROOT / "app" / "chat"),
            str(_BACKEND_ROOT / "app" / "planner"),
            str(_BACKEND_ROOT / "app" / "actions"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.stdout.strip() == "", completed.stdout


def test_static_catalog_correction_is_not_flag_reversible() -> None:
    """P2's catalog row is permanent; only runtime scheduling rides the flag."""
    catalog = (_BACKEND_ROOT / "app" / "skills" / "catalog.json").read_text(encoding="utf-8")
    import json

    rows = json.loads(catalog)
    entries = rows if isinstance(rows, list) else rows.get("skills") or []
    guided = next(
        (row for row in entries if row.get("skill") == "guided_investigation"
         or row.get("skill_id") == "guided_investigation"
         or row.get("name") == "guided_investigation"),
        None,
    )
    assert guided is not None, "guided_investigation row must exist"
    assert "mcp_execution" not in (guided.get("blocked_tools") or [])


def test_reasoning_hops_cannot_outlive_the_turn() -> None:
    """No investigation reasoning hop may stall /chat past the turn deadline."""
    from app.chat.investigation_plan_delta_reasoner import _delta_hop_timeout_seconds
    from app.chat.guided_investigation_plan_llm import _hop_timeout_seconds
    from app.chat.remediation_plan_reasoner import _hop_timeout_seconds as _remediation_timeout

    budget = TurnLlmBudget(deadline_seconds=10.0)
    for resolver in (_hop_timeout_seconds, _delta_hop_timeout_seconds, _remediation_timeout):
        capped = resolver(budget)
        assert capped is None or capped <= 10.0


def test_exhausted_budget_degrades_to_baseline_not_an_error() -> None:
    baseline = build_deterministic_investigation_plan(
        query="investigate",
        entities=None,
        resolved_query_contract={},
        capability_snapshot=_snapshot(splunk_search="available"),
    )
    result = propose_investigation_plan_llm(
        query="investigate",
        baseline=baseline,
        turn_budget=TurnLlmBudget(deadline_seconds=0.0001),
    )
    assert result.attempted is False
    assert "turn_budget_exhausted" in result.dropped_reasons


# =====================================================  T1 vs T4 convergence (§8)


@pytest.mark.parametrize(
    "rqc",
    [
        {"intent_family": "live_investigation", "understanding_source": "deterministic"},
        {"intent_family": "live_investigation", "understanding_source": "semantic_t4"},
    ],
)
def test_t1_and_t4_take_the_same_investigation_runtime(rqc: dict) -> None:
    assert is_investigation_shaped_final_rqc(resolved_query_contract=rqc) is True


def test_equivalent_rqcs_produce_equivalent_plans_regardless_of_understanding_arm() -> None:
    snapshot = _snapshot(splunk_search="available")
    arms = [
        {"intent_family": "live_investigation", "understanding_source": "deterministic",
         "entities": {"src_ip": "198.51.100.42"}},
        {"intent_family": "live_investigation", "understanding_source": "semantic_t4",
         "entities": {"src_ip": "198.51.100.42"}},
    ]
    plans = [
        build_deterministic_investigation_plan(
            query="Check 198.51.100.42 over the last 30 days.",
            entities=arm["entities"],
            resolved_query_contract=arm,
            capability_snapshot=snapshot,
        )
        for arm in arms
    ]
    assert plans[0].investigation_objective == plans[1].investigation_objective
    assert plans[0].evidence_needed == plans[1].evidence_needed
    assert [b.model_dump() for b in plans[0].capability_bindings] == [
        b.model_dump() for b in plans[1].capability_bindings
    ]


def test_every_investigation_family_reaches_the_wait_state() -> None:
    for family in INVESTIGATION_INTENT_FAMILIES:
        assert is_investigation_shaped_final_rqc(
            resolved_query_contract={"intent_family": family}
        ) is True


def test_pure_knowledge_recall_is_not_investigation_shaped() -> None:
    assert is_investigation_shaped_final_rqc(
        resolved_query_contract={"intent_family": "knowledge_recall", "answer_goal": "definition"}
    ) is False


# =====================================================  UX / presentation (§ production UX)


def _observed_progress(step_status: str, *, source_evidence: list | None = None) -> list[dict]:
    from app.chat.investigation_run_compiler import attach_investigation_observation

    state = attach_investigation_observation(
        {
            "approved_investigation_envelope": {"envelope_version": 2},
            "evidence_plan": {
                "resource_plan": {
                    "steps": [
                        {
                            "step_id": "step-1",
                            "purpose": "collect_authentication_evidence",
                            "status": step_status,
                            "resource_id": "splunk_search",
                        }
                    ]
                }
            },
            "source_evidence": source_evidence or [],
        }
    )
    return state["investigation_progress"]


def test_progress_payload_exposes_no_chain_of_thought() -> None:
    """Operational steps only — never model reasoning, scratchpad, or prompts."""
    progress = _observed_progress("executed", source_evidence=[{"evidence_id": "ev-1"}])
    serialized = str(progress).lower()
    for forbidden in ("<think>", "scratchpad", "prompt", "chain_of_thought", "rationale"):
        assert forbidden not in serialized


def test_completed_empty_step_never_renders_a_blank_finding() -> None:
    """An executed step with no evidence must say so, not emit 'Finding: -'."""
    for status in ("executed", "completed", "planned"):
        entry = _observed_progress(status)[0]
        assert entry["evidence_summary"].strip()
        assert entry["evidence_summary"].strip() != "-"
        assert "finding: -" not in entry["evidence_summary"].lower()


def test_progress_does_not_claim_evidence_it_did_not_collect() -> None:
    entry = _observed_progress("executed")[0]
    assert entry["evidence_refs"] == []
    assert "no matching governed evidence" in entry["evidence_summary"].lower()


def test_remediation_summary_names_manual_steps_instead_of_hiding_them() -> None:
    from app.chat.remediation_runtime import build_remediation_summary

    plan = build_deterministic_remediation_plan(
        investigation_outcome=_outcome_payload(),
        capability_snapshot=_snapshot(email_send="available"),
    )
    summary = build_remediation_summary(plan)
    assert summary.what_stays_manual, "an unavailable connector must be visible to the analyst"
    assert summary.how_it_is_verified


def test_cancelled_investigation_offers_no_remediation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_remediation_planner_enabled", True)
    from app.chat.remediation_runtime import maybe_attach_remediation_offer

    state = maybe_attach_remediation_offer(
        {"investigation_outcome": _outcome_payload(investigation_status="cancelled")}
    )
    assert "remediation_approval" not in state


# =====================================================  follow-up / envelope integrity


def test_follow_up_cannot_silently_widen_an_approved_envelope() -> None:
    envelope = ApprovedInvestigationEnvelope(
        envelope_version=2,
        objective="scope ssh logins",
        targets=["host:jump-01"],
        entities={"host": "jump-01"},
        time_scope="last_30_days",
        allowed_read_only_capabilities=["splunk_search"],
    )
    with pytest.raises(Exception):
        envelope.allowed_read_only_capabilities.append("firewall_block")  # type: ignore[union-attr]
        ApprovedInvestigationEnvelope.model_validate(
            {**envelope.model_dump(mode="json"), "envelope_version": 2, "extra_scope": True}
        )


def test_envelope_forbids_write_capabilities() -> None:
    with pytest.raises(Exception):
        ApprovedInvestigationEnvelope(
            envelope_version=1,
            objective="scope",
            allowed_read_only_capabilities=["firewall_block_write"],
        )


# =====================================================  flag-off identity


def test_flag_off_produces_no_investigation_or_remediation_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_investigation_plan_before_resource_plan_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_investigation_planner_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_remediation_planner_enabled", False)
    from app.chat.investigation_plan_runtime import maybe_attach_validated_investigation_plan
    from app.chat.remediation_runtime import maybe_attach_remediation_offer

    state = {"resolved_query_contract": {}, "capability_snapshot": {}}
    assert maybe_attach_validated_investigation_plan(dict(state)) == state
    assert "remediation_approval" not in maybe_attach_remediation_offer(
        {"investigation_outcome": _outcome_payload()}
    )


def test_flag_off_investigation_shape_gate_is_the_only_activation_seam(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P4/P7 ride the P0 wait-state; no separate envelope or PlanDelta flag exists."""
    assert not hasattr(settings, "ai_soc_investigation_envelope_enabled")
    assert not hasattr(settings, "ai_soc_plan_delta_enabled")


def test_no_infrastructure_readiness_flags_were_introduced() -> None:
    """Availability is represented by config + snapshot + health, never by a flag."""
    for forbidden in (
        "ai_soc_reasoning_ready",
        "ai_soc_splunk_live",
        "ai_soc_model_available",
        "ai_soc_mcp_available",
    ):
        assert not hasattr(settings, forbidden)


# =====================================================  EC behavioral parity checklist


def test_experience_center_behavioral_parity_surfaces_exist() -> None:
    """Behaviour parity, not fixture parity: each lifecycle affordance must exist."""
    from app.chat import remediation_runtime
    from app.chat import investigation_envelope_runtime

    assert hasattr(investigation_envelope_runtime, "maybe_attach_investigation_approval")
    assert hasattr(investigation_envelope_runtime, "maybe_handle_investigation_review")
    assert hasattr(remediation_runtime, "maybe_attach_remediation_offer")
    assert hasattr(remediation_runtime, "handle_remediation_review")
    assert hasattr(remediation_runtime, "build_remediation_summary")


def test_remediation_plan_contract_pins_no_execution_field() -> None:
    fields = ValidatedRemediationPlan.model_fields
    assert fields["execution_authorized"].default is False
    assert fields["human_approval_required"].default is True


# =====================================================  governed refusal, not a crash


@pytest.mark.parametrize(
    "reason",
    [
        "session_ownership_mismatch",
        "investigation_handoff_not_found",
        "investigation_handoff_expired",
        "investigation_handoff_already_decided",
        "investigation_handoff_not_pending",
    ],
)
def test_stale_or_foreign_investigation_decision_is_a_409_not_a_500(reason: str) -> None:
    """Fail-closed must not mean crash: /chat stays healthy and says what to do."""
    from fastapi.testclient import TestClient

    from app.chat.investigation_envelope_runtime import InvestigationEnvelopeError
    from app.main import app

    if not any(
        getattr(route, "path", "") == "/__test_investigation_refusal" for route in app.routes
    ):

        @app.get("/__test_investigation_refusal")
        def _raise(reason: str) -> None:  # pragma: no cover - raised for the client below
            raise InvestigationEnvelopeError(reason)

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/__test_investigation_refusal", params={"reason": reason})
    assert response.status_code == 409
    body = response.json()
    assert body["error_code"] == "investigation_decision_not_applicable"
    assert body["reason"] == reason
    assert "Traceback" not in response.text
    assert body["message"]
