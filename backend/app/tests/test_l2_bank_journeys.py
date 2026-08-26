"""L2 bank — P3 journey rows that are green today.

Scope discipline (workstream C, P3): this file adds *coverage*, never behaviour.
Every assertion below was probed against the runtime at `ae03a250` before it was
written, so a red test here means the product changed, not that the row was
aspirational.

Each test maps 1:1 to a row in ``app.tests.support.l2_bank_manifest`` and owns
exactly one invariant. ``test_l2_bank_manifest.py`` enforces that mapping in both
directions, so a test added here without a manifest row — or a row whose bound
test disappears — turns red.

Deliberately absent: assertions on ``control_plane_trace`` internals, diagnostic
ordering, timings, or any field whose contract P1/P2/P4 still own.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.chat.contracts.investigation_envelope import ApprovedInvestigationEnvelope
from app.chat.contracts.investigation_outcome import derive_investigation_outcome
from app.chat.contracts.plan_delta import PlanDeltaProposal
from app.chat.investigation_plan_delta import validate_plan_delta
from app.chat.remediation_runtime import handle_remediation_review, maybe_attach_remediation_offer
from app.config import settings
from app.knowledge import soc_kb_retriever

_SEARCH_CAPABILITY = "mcp:splunk:splunk_run_query"
_DELTA_SPL = (
    "search index=pgcil_soc sourcetype=pgcil:auth earliest=-24h latest=now user=alice "
    "| stats count by user | head 100"
)

_SOP_QUERY = "What is the SOP for investigating a failed login spike?"
_OUT_OF_DOMAIN_QUERY = "How do I calibrate the office espresso machine for oat milk?"


# ---------------------------------------------------------------------------
# RAG — L2.P3.01 / L2.P3.02 / L2.P3.03
# ---------------------------------------------------------------------------


@pytest.fixture
def _rag_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Smallest enabling set: the retriever's own flag, nothing else."""
    monkeypatch.setattr(soc_kb_retriever.settings, "soc_kb_retrieval_enabled", True)


def _retrieve(query: str) -> dict[str, Any]:
    return soc_kb_retriever.retrieve_soc_kb(
        query=query,
        selected_skill="knowledge_recall",
        workflow_stage="analysis",
    )


def test_l2_rag_sop_match_returns_governed_entries(_rag_enabled: None) -> None:
    """L2.P3.01 — a real SOP question retrieves governed entries with declared origin."""
    result = _retrieve(_SOP_QUERY)

    assert result["retrieval_status"] == "retrieved"
    assert len(result["retrieved_entries"]) >= 1
    assert result["confidence"] > 0.0
    # Every retrieved package declares where it came from; unattributed evidence is
    # the failure mode this row exists to catch.
    assert result["evidence_origin"] not in (None, "", "none")


def test_l2_rag_no_match_returns_nothing_and_says_so(_rag_enabled: None) -> None:
    """L2.P3.02 — out-of-domain retrieves nothing and invents no near-miss citation."""
    result = _retrieve(_OUT_OF_DOMAIN_QUERY)

    assert result["retrieval_status"] == "no_match"
    assert result["retrieved_entries"] == []
    assert result["confidence"] == 0.0
    assert result["evidence_origin"] == "none"


def test_l2_rag_disabled_by_default_is_declared_not_silent() -> None:
    """L2.P3.03 — the shipped default is 'disabled', which is not the same as 'no_match'.

    No monkeypatch: this asserts the posture a default-configured deployment has.
    """
    assert settings.soc_kb_retrieval_enabled is False

    result = _retrieve(_SOP_QUERY)

    assert result["retrieval_status"] == "disabled"
    assert "soc_kb_retrieval_disabled" in result["reasons"]
    assert result["retrieved_entries"] == []


# ---------------------------------------------------------------------------
# InvestigationOutcome — L2.P3.04 / L2.P3.05 / L2.P3.06
# ---------------------------------------------------------------------------


def test_l2_empty_evidence_outcome_invents_no_findings() -> None:
    """L2.P3.04 — zero evidence yields an incomplete outcome with nothing invented."""
    outcome = derive_investigation_outcome(outcome_v2_enabled=True)

    assert outcome.investigation_status == "incomplete"
    assert outcome.disposition == "inconclusive"
    assert outcome.findings == []
    assert outcome.evidence_refs == []


def test_l2_policy_block_is_status_not_security_disposition() -> None:
    """L2.P3.05 — 'blocked' is an investigation status; it is never a security verdict.

    architecture.md states this separation explicitly. The concrete hazard is an
    analyst reading a policy block as a finding about the environment.
    """
    outcome = derive_investigation_outcome(
        context_sufficiency={"status": "blocked_by_policy"},
        outcome_v2_enabled=True,
    )

    assert outcome.investigation_status == "blocked"
    assert outcome.disposition != "blocked"
    assert outcome.disposition in {"benign", "suspicious", "inconclusive"}


def test_l2_negative_evidence_yields_benign_disposition() -> None:
    """L2.P3.06 — 'we looked and it is not there' is not 'we could not tell'."""
    outcome = derive_investigation_outcome(
        canonical_facts={
            "facts": [
                {"kind": "negative_evidence", "statement": "no matching auth events in scope"}
            ]
        },
        evidence_state={"obtained": []},
        outcome_v2_enabled=True,
    )

    assert outcome.disposition == "benign"


# ---------------------------------------------------------------------------
# Plan delta bounds — L2.P3.07 / L2.P3.08
# ---------------------------------------------------------------------------


def _envelope() -> ApprovedInvestigationEnvelope:
    return ApprovedInvestigationEnvelope(
        envelope_version=2,
        objective="Investigate alice authentication activity",
        targets=["user:alice"],
        entities={"user": "alice"},
        time_scope="last 24 hours",
        approved_evidence_categories=["sessions"],
        allowed_read_only_capabilities=[_SEARCH_CAPABILITY],
        source_index_scope={"indexes": ["pgcil_soc"]},
    )


def _available_snapshot() -> dict[str, Any]:
    return {
        "rows": [
            {
                "capability_id": _SEARCH_CAPABILITY,
                "capability_need": "required",
                "availability": "available",
            }
        ]
    }


def _proposal(envelope: ApprovedInvestigationEnvelope, **overrides: Any) -> PlanDeltaProposal:
    payload: dict[str, Any] = {
        "envelope_version": 2,
        "objective": envelope.objective,
        "evidence_need": "authentication_correlation",
        "capability_id": _SEARCH_CAPABILITY,
        "access_mode": "read_only",
        "targets": envelope.targets,
        "entities": envelope.entities,
        "time_scope": envelope.time_scope,
        "source_index_scope": envelope.source_index_scope,
        "tool_arguments": {"query": _DELTA_SPL},
    }
    payload.update(overrides)
    return PlanDeltaProposal.model_validate(payload)


def test_l2_duplicate_plan_delta_is_refused_as_no_progress() -> None:
    """L2.P3.07 — repeating the same effective delta buys no round and no budget."""
    envelope = _envelope()
    snapshot = _available_snapshot()

    first = validate_plan_delta(
        _proposal(envelope),
        envelope=envelope,
        capability_snapshot=snapshot,
        missing_evidence=["authentication_correlation"],
        prior_revisions=[],
    )
    assert first.status == "accepted"
    assert first.validated_delta is not None

    duplicate = validate_plan_delta(
        _proposal(
            envelope,
            prior_revision_fingerprint=first.validated_delta.revision_fingerprint,
        ),
        envelope=envelope,
        capability_snapshot=snapshot,
        missing_evidence=["authentication_correlation"],
        prior_revisions=[first.validated_delta.model_dump(mode="json")],
    )

    assert duplicate.status == "no_progress"
    assert duplicate.reason == "duplicate_effective_plan_delta"
    assert duplicate.validated_delta is None


def test_l2_write_access_mode_is_not_an_investigation_delta() -> None:
    """L2.P3.08 — a write proposed as investigation work is routed out, not validated.

    Investigation is read-only. The correct behaviour is not a bare rejection but a
    referral to the remediation lane, which is what makes this distinct from the
    unavailable-capability rejection in L2.P0.07.
    """
    envelope = _envelope()

    decision = validate_plan_delta(
        _proposal(envelope, access_mode="write"),
        envelope=envelope,
        capability_snapshot=_available_snapshot(),
        missing_evidence=["authentication_correlation"],
        prior_revisions=[],
    )

    assert decision.status == "remediation_recommended"
    assert decision.reason == "writes_are_not_investigation_plan_delta"
    assert decision.validated_delta is None


# ---------------------------------------------------------------------------
# Remediation lifecycle — L2.P3.09 / L2.P3.10
# ---------------------------------------------------------------------------


@pytest.fixture
def _remediation_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_remediation_planner_enabled", True)


def _completed_outcome_state() -> dict[str, Any]:
    return {
        "investigation_outcome": {
            "investigation_status": "completed",
            "disposition": "suspicious",
            "remediation_offer_required": True,
            "evidence_refs": ["ev.auth"],
            "findings": ["repeated failed logins from 10.0.0.8"],
            "severity_label": "P2",
            "recommended_actions": ["block source ip"],
        }
    }


def test_l2_remediation_offer_then_decline_builds_no_plan(_remediation_enabled: None) -> None:
    """L2.P3.09 — the offer is an affordance; declining it leaves no plan behind."""
    offered = maybe_attach_remediation_offer(_completed_outcome_state())
    approval = offered["remediation_approval"]

    assert approval["status"] == "offered"
    assert approval["allowed_actions"] == ["create", "decline"]
    # Nothing is planned merely by being offered.
    assert approval["validated_plan"] is None

    declined = handle_remediation_review(offered, action="decline")
    declined_approval = declined["remediation_approval"]

    assert declined_approval["status"] == "declined"
    assert declined_approval["validated_plan"] is None
    assert "approved_remediation_envelope" not in declined


def test_l2_remediation_approval_yields_envelope_without_execution(
    _remediation_enabled: None,
) -> None:
    """L2.P3.10 — approval produces the envelope that P11 execution would *consume*.

    The envelope is the input to execution, never the authorization for it. This row
    is the load-bearing one for 'no unapproved write'.
    """
    offered = maybe_attach_remediation_offer(_completed_outcome_state())

    created = handle_remediation_review(offered, action="create")
    created_approval = created["remediation_approval"]
    plan = created_approval["validated_plan"] or {}

    assert created_approval["status"] == "awaiting_approval"
    assert created_approval["allowed_actions"] == ["approve", "edit", "cancel"]
    assert plan["execution_authorized"] is False
    assert plan["human_approval_required"] is True

    approved = handle_remediation_review(created, action="approve")
    approved_approval = approved["remediation_approval"]

    assert approved_approval["status"] == "approved"
    assert approved["approved_remediation_envelope"]["envelope_version"] == 1
    # Approval must not have executed, scheduled, or recorded any write.
    assert approved_approval["execution_result"] is None
    assert "remediation_execution" not in approved


def test_l2_remediation_cancel_calls_no_connector(_remediation_enabled: None) -> None:
    """L2.D.01 — Cancel after seeing the plan calls no connector and writes nothing."""
    offered = maybe_attach_remediation_offer(_completed_outcome_state())
    created = handle_remediation_review(offered, action="create")
    cancelled = handle_remediation_review(created, action="cancel")
    approval = cancelled["remediation_approval"]

    assert approval["status"] == "cancelled"
    assert "No connector was called" in approval["safe_message"]
    assert "approved_remediation_envelope" not in cancelled
    assert approval.get("execution_result") is None
    assert "remediation_execution" not in cancelled


def test_l2_remediation_planning_is_off_by_default() -> None:
    """L2.D.02 — a default deployment never surfaces a remediation CTA."""
    from app.config import settings as live_settings

    assert live_settings.ai_soc_remediation_planner_enabled is False
    offered = maybe_attach_remediation_offer(_completed_outcome_state())
    assert "remediation_approval" not in offered


def test_l2_remediation_edit_revalidates_before_approval(_remediation_enabled: None) -> None:
    """L2.D.03 — Edit revalidates; Approve is offered again and still executes nothing."""
    offered = maybe_attach_remediation_offer(_completed_outcome_state())
    offered = {
        **offered,
        "capability_snapshot": {
            "schema_version": "capability_snapshot_v1",
            "rows": [
                {
                    "capability_id": "firewall_block",
                    "capability_need": "recommended",
                    "availability": "available",
                }
            ],
        },
    }
    created = handle_remediation_review(offered, action="create")
    steps = list((created["remediation_approval"]["validated_plan"] or {}).get("steps") or [])
    assert steps, "create must produce a plan the analyst can edit"
    removed = str(steps[0]["step_id"])

    edited = handle_remediation_review(
        created,
        action="edit",
        edits={"removed_step_ids": [removed]},
    )
    approval = edited["remediation_approval"]
    remaining = [step["step_id"] for step in (approval["validated_plan"] or {}).get("steps") or []]

    assert approval["status"] == "edited_revalidated"
    assert approval["allowed_actions"] == ["approve", "edit", "cancel"]
    assert "analyst_edit_revalidated" in approval["revalidation_warnings"]
    assert removed not in remaining
    assert "approved_remediation_envelope" not in edited

    approved = handle_remediation_review(edited, action="approve")
    assert approved["remediation_approval"]["status"] == "approved"
    assert approved["remediation_approval"]["execution_result"] is None
    assert "remediation_execution" not in approved


# ---------------------------------------------------------------------------
# P1 contracts — L2.R.P1.01..06 (activated after rebase onto integrated P1)
# ---------------------------------------------------------------------------


def test_l2_llm_lifecycle_attempted_is_not_used() -> None:
    """L2.R.P1.01 — ATTEMPTED/RESPONSE_RECEIVED without ACCEPTED never reads as USED."""
    from app.spl.spl_provenance_trace import TRACE_LIFECYCLE_SCHEMA_VERSION, build_spl_llm_lifecycle

    lifecycle = build_spl_llm_lifecycle(
        candidate_spl={
            "generation_mode": "utility_llm_spl_draft",
            "candidate_spl": "search index=main | head 10",
            "utility_spl_draft_trace": {
                "llm_spl_draft_requested": True,
                "llm_spl_draft_completed": True,
                "llm_spl_draft_used": False,
            },
        },
        spl_validation={"approved": False, "normalized_spl": None},
        budget_records=[{"role": "utility_spl", "outcome": "completed"}],
    )
    assert lifecycle["schema_version"] == TRACE_LIFECYCLE_SCHEMA_VERSION
    assert "ATTEMPTED" in lifecycle["states"]
    assert "RESPONSE_RECEIVED" in lifecycle["states"]
    assert "USED" not in lifecycle["states"]
    assert lifecycle["used"] is False
    assert lifecycle["accepted"] is False


def test_l2_fallback_label_is_deterministic_fallback() -> None:
    """L2.R.P1.02 — one canonical fallback name on the provenance surface."""
    from app.spl.spl_provenance_trace import deterministic_fallback_used, spl_artifact_source

    candidate = {
        "generation_mode": "deterministic_lab_draft",
        "candidate_spl": "search index=main earliest=-24h | stats count",
        "utility_spl_draft_trace": {"llm_spl_draft_used": False},
    }
    assert spl_artifact_source(candidate) == "deterministic_fallback"
    assert deterministic_fallback_used(candidate) is True
    assert spl_artifact_source(candidate) != "live_llm"


def test_l2_artifact_review_is_not_execution_hil() -> None:
    """L2.R.P1.03 — reviewing a candidate SPL is not approving an execution."""
    from app.chat.control_plane_trace import build_control_plane_trace

    trace = build_control_plane_trace(
        {
            "candidate_spl": {"candidate_spl": "index=main | head 10"},
            "spl_validation": {"approved": False, "review_required_reason": "review_only"},
            "run_contract": {"effective_hil_required": False},
        }
    )
    oracle = trace["trace_oracle"]
    assert oracle["schema_version"] == "trace_oracle_v1"
    assert oracle["spl_artifact"]["artifact_present"] is True
    assert oracle["spl_artifact"]["artifact_review_required"] is True
    assert oracle["execution_review"]["execution_hil_required"] is False
    assert oracle["execution_review"]["decision_site"] == "run_contract"


def test_l2_pure_spl_authoring_projects_no_investigation_outcome() -> None:
    """L2.R.P1.04 — utility SPL authoring is not an investigation product."""
    from app.chat.contracts.investigation_outcome import derive_investigation_outcome
    from app.chat.investigation_shaped import investigation_outcome_applicable
    from app.chat.skill_intent_compatibility import CAPABILITY_SPL

    rqc = {
        "intent_family": "spl_generation_only",
        "answer_goal": "spl_artifact",
        "required_capabilities": [CAPABILITY_SPL],
        "understanding_source": "deterministic_qualification",
        "clarification_required": False,
        "ambiguity_state": "unambiguous",
        "normalized_goal": "author review-only SPL",
    }
    assert investigation_outcome_applicable(resolved_query_contract=rqc) is False
    payload = derive_investigation_outcome(
        evidence_sufficiency={"status": "BLOCKED", "missing": ["mcp_rows"], "next_action": "BLOCK"},
        context_sufficiency={"status": "INSUFFICIENT"},
        final_evidence_gate={"collected_evidence_refs": [], "allow_live_result_language": False},
        resolved_query_contract=rqc,
        outcome_v2_enabled=True,
    ).model_dump(mode="json")
    assert "investigation_status" not in payload
    assert payload["provenance"].get("investigation_outcome_applicable") is False


def test_l2_stable_oracle_excludes_diagnostics() -> None:
    """L2.R.P1.05 — versioned oracle is the only contract surface; diagnostics stay aside."""
    from app.chat.control_plane_trace import build_control_plane_trace

    trace = build_control_plane_trace(
        {
            "run_contract": {"effective_hil_required": False},
            "evidence_state": {
                "schema_version": "minimal_evidence_state_v2",
                "required": ["mcp"],
                "obtained": [],
                "missing": ["mcp"],
                "stale": [],
                "invalidated": [],
                "blocked": [],
                "empty": ["mcp"],
                "diagnostic": ["execution_status"],
            },
            "execution": {"status": "skipped", "latency_ms": 12},
        }
    )
    oracle = trace["trace_oracle"]
    assert oracle["schema_version"] == "trace_oracle_v1"
    assert oracle["run_shape_transition"]["schema_version"] == "run_shape_transition_v2"
    assert "diagnostic" not in oracle["evidence_state"]
    assert trace["evidence_state"]["diagnostic"] == ["execution_status"]
    assert "latency" not in str(oracle)


def test_l2_planned_evidence_is_not_obtained() -> None:
    """L2.R.P1.06 — planned/attempted collection never becomes SourceEvidence."""
    from app.evidence.minimal_evidence_state import derive_minimal_evidence_state

    state = derive_minimal_evidence_state(
        source_evidence=[
            {
                "evidence_id": "mcp-attempted",
                "source_type": "splunk_mcp",
                "source_name": "l2-bank",
                "collection_status": "attempted",
                "result_count": 0,
                "preview_rows": [],
            }
        ],
        evidence_plan={"needs_mcp": True, "mcp_allowed": True},
        canonical_facts={
            "facts": [
                {
                    "kind": "plan_step_outcome",
                    "payload": {"status": "attempted"},
                    "provenance": {"node": "resource_plan", "evidence_class": "plan"},
                }
            ]
        },
    )
    assert state.schema_version == "minimal_evidence_state_v2"
    assert state.obtained == []
    assert "mcp" in state.missing
    assert "plan_step_outcome" in state.diagnostic


# ---------------------------------------------------------------------------
# P2 contracts — L2.R.P2.01..03, .05, .06 (comparison remains PRODUCT_GAP)
# ---------------------------------------------------------------------------


def test_l2_rolling_window_is_preserved_through_compiler() -> None:
    """L2.R.P2.01 — rolling distinct-accounts window survives compile."""
    from app.spl.llm_plan_compiler import compile_intent_spec_to_spl
    from app.spl.spl_intent_spec import build_spl_intent_spec

    spec = build_spl_intent_spec(
        "one source IP attacking multiple distinct accounts over a rolling 10-minute window"
    )
    spl = compile_intent_spec_to_spl(spec)
    assert spec["analysis_shape"] == "rolling"
    assert spec["analytical_window"]["kind"] == "rolling"
    assert "streamstats time_window=10m" in spl
    assert "head 100" not in spl


def test_l2_hourly_trend_keeps_temporal_grain() -> None:
    """L2.R.P2.02 — hourly 24h trend is not collapsed to a single total."""
    from app.spl.llm_plan_compiler import compile_intent_spec_to_spl
    from app.spl.spl_intent_spec import build_spl_intent_spec

    spec = build_spl_intent_spec("hourly failed-login trend over the last 24 hours")
    spl = compile_intent_spec_to_spl(spec)
    assert spec["analysis_shape"] == "trend" or spec["temporal_grain"] == "1h"
    assert "timechart span=1h" in spl
    assert "earliest=-24h" in spl
    assert "head 100" not in spl


def test_l2_ordered_sequence_and_max_gap_are_preserved() -> None:
    """L2.R.P2.03 — password-change then login within 5m keeps order and gap."""
    from app.spl.llm_plan_compiler import compile_intent_spec_to_spl
    from app.spl.spl_intent_spec import build_spl_intent_spec

    spec = build_spl_intent_spec(
        "password change followed by successful login within 5 minutes"
    )
    spl = compile_intent_spec_to_spl(spec)
    assert spec["analysis_shape"] == "sequence"
    assert spec["ordered_sequence"] == ["password_change", "successful_login"]
    assert spec["sequence_max_gap"] == "5m"
    assert "password_change" in spl
    assert "successful_login" in spl


def test_l2_normalization_aliases_are_consumed_in_compiled_spl() -> None:
    """L2.R.P2.05 — declared aliases appear in compiled SPL, not just the spec."""
    from app.spl.llm_plan_compiler import compile_intent_spec_to_spl
    from app.spl.spl_intent_spec import build_spl_intent_spec

    spec = build_spl_intent_spec(
        "one source IP attacking multiple distinct accounts over a rolling 10-minute window"
    )
    spl = compile_intent_spec_to_spl(spec)
    aliases = {item["alias"] for item in spec["normalization_requirements"]}
    assert "src_ip_norm" in aliases
    assert "user_norm" in aliases
    assert "grouping" in spec["normalization_consumers"]
    assert "user_norm" in spl
    assert "src_ip_norm" in spl


def test_l2_analytical_shapes_are_not_arbitrarily_truncated() -> None:
    """L2.R.P2.06 — rolling/trend compiles without an invented head 100."""
    from app.spl.llm_plan_compiler import compile_intent_spec_to_spl
    from app.spl.spl_intent_spec import build_spl_intent_spec

    rolling = compile_intent_spec_to_spl(
        build_spl_intent_spec(
            "one source IP attacking multiple distinct accounts over a rolling 10-minute window"
        )
    )
    trend = compile_intent_spec_to_spl(
        build_spl_intent_spec("hourly failed-login trend over the last 24 hours")
    )
    assert "head 100" not in rolling
    assert "head 100" not in trend


# ---------------------------------------------------------------------------
# P4 contracts — L2.R.P4.01..04 (no live A/B claim)
# ---------------------------------------------------------------------------


def test_l2_prompt_provenance_is_deterministic() -> None:
    """L2.R.P4.01 — identical turns report identical prompt identity/hash."""
    from app.llm.policy.registry import contract_for
    from app.llm.policy.templates import assemble_prompt, stable_prefix_hash

    role = "investigation_planner"
    dynamic = {key: "turn-a" for key in contract_for(role).dynamic_context}
    first = assemble_prompt(role, dynamic)
    second = assemble_prompt(role, dynamic)
    provenance = first.provenance()
    assert provenance["prompt_template_id"]
    assert provenance["prompt_version"]
    assert provenance["prompt_hash"] == second.prompt_hash
    assert provenance["stable_prefix_hash"] == stable_prefix_hash(role)
    assert provenance["cache_policy_version"] == "prompt_cache_policy_v1"


def test_l2_blocked_reasoning_roles_stay_blocked() -> None:
    """L2.R.P4.02 — the seven blocked reasoners remain off the allowlist."""
    from app.llm.policy.role_inventory import blocked_role_ids
    from app.llm.sidecar_clients import _REASONING_ALLOWED_ROLES

    blocked = set(blocked_role_ids())
    required = {
        "mitre_reasoner",
        "missing_evidence_reasoner",
        "risk_rationale_reasoner",
        "plan_delta_reasoner",
        "pattern_reasoner",
        "evidence_reasoner",
        "hypothesis_reasoner",
    }
    assert required <= blocked
    assert not (required & set(_REASONING_ALLOWED_ROLES))


def test_l2_shape_advisor_stays_advisory() -> None:
    """L2.R.P4.03 — deterministic shape wins when the advisor disagrees."""
    from app.chat.shape_advisor import ShapeAdvisoryResult, apply_shape_advisory_promotion

    advisory = ShapeAdvisoryResult(
        suggested_shape="hunt",
        confidence=0.99,
        rationale="disagree",
        deterministic_shape="reference_taxonomy",
        llm_called=True,
    )
    result = apply_shape_advisory_promotion("Explain CVE-2024-3400.", advisory)
    assert result.used is False
    assert result.ignored_reason == "advisory_ignored_deterministic_match"
    assert result.promoted_shape is None
    assert result.deterministic_shape == "reference_taxonomy"


def test_l2_prompt_cache_metadata_is_not_authority() -> None:
    """L2.R.P4.04 — cache eligibility is metadata; session data cannot enter the prefix."""
    from app.llm.policy.registry import contract_for
    from app.llm.policy.templates import (
        CACHE_POLICY_VERSION,
        StablePrefixViolation,
        assemble_prompt,
        assert_prefix_is_cacheable,
    )

    contract = contract_for("investigation_planner")
    assert CACHE_POLICY_VERSION == "prompt_cache_policy_v1"
    assert contract.cache_eligible in {"ELIGIBLE", "INELIGIBLE_NO_STABLE_PREFIX"}
    assert_prefix_is_cacheable(
        '{"role_id":"investigation_planner"}',
        role_id="investigation_planner",
    )
    with pytest.raises(StablePrefixViolation):
        assemble_prompt("intent_shadow_classifier", {"session_id": "s-1"})
