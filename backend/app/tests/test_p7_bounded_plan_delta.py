"""P7 bounded, append-only PlanDelta on the existing Resource Planner hub."""

from __future__ import annotations

import inspect

from app.chat.contracts.investigation_envelope import ApprovedInvestigationEnvelope
from app.chat.contracts.plan_delta import PlanDeltaProposal
from app.chat.investigation_plan_delta import attach_plan_delta_decision, validate_plan_delta
from app.chat.investigation_plan_delta_reasoner import propose_plan_delta
from app.config import settings
from app.graph import resource_planner_graph as rp
from app.orchestration.splunk_call_authorization import call_grant_from_tool_call


CAPABILITY = "mcp:splunk:splunk_run_query"


def _envelope() -> ApprovedInvestigationEnvelope:
    return ApprovedInvestigationEnvelope(
        envelope_version=2,
        objective="Investigate alice authentication activity",
        targets=["user:alice"],
        entities={"user": "alice"},
        time_scope="last 24 hours",
        approved_evidence_categories=["sessions", "authentication_correlation"],
        allowed_read_only_capabilities=[CAPABILITY],
        source_index_scope={"indexes": ["auth"]},
    )


def _snapshot(source: str = "deterministic_qualification") -> dict:
    return {
        "understanding_source": source,
        "rows": [{"capability_id": CAPABILITY, "capability_need": "required", "availability": "available"}],
    }


def _proposal(**updates: object) -> PlanDeltaProposal:
    payload = {
        "envelope_version": 2,
        "objective": "Investigate alice authentication activity",
        "evidence_need": "authentication_correlation",
        "capability_id": CAPABILITY,
        "access_mode": "read_only",
        "targets": ["user:alice"],
        "entities": {"user": "alice"},
        "time_scope": "last 24 hours",
        "source_index_scope": {"indexes": ["auth"]},
        "tool_arguments": {"correlate": "sessions_to_auth", "earliest": "-24h"},
        "hypothesis": "Allowed sessions may follow the denied burst.",
        "evidence_refs": ["evidence:sessions"],
    }
    payload.update(updates)
    return PlanDeltaProposal.model_validate(payload)


def _validate(proposal: PlanDeltaProposal, revisions: list[dict] | None = None, source: str = "deterministic_qualification"):
    return validate_plan_delta(
        proposal,
        envelope=_envelope(),
        capability_snapshot=_snapshot(source),
        missing_evidence=["authentication_correlation"],
        prior_revisions=revisions or [],
    )


def test_scenario_a_gap_accepts_one_bounded_read_only_delta(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_investigation_planner_enabled", True)
    state = attach_plan_delta_decision(
        {
            "approved_investigation_envelope": _envelope().model_dump(mode="json"),
            "capability_snapshot": _snapshot(),
            "investigation_run_status": {"status": "incomplete", "missing_evidence": ["authentication_correlation"]},
            "evidence_state": {"present": ["sessions"], "missing": ["authentication_correlation"]},
            "source_evidence": [{"evidence_id": "evidence:sessions", "source_type": "mcp"}],
            "plan_delta_proposal": _proposal().model_dump(mode="json"),
        }
    )
    assert state["plan_delta_decision"]["status"] == "accepted"
    assert state["plan_delta_execution_request"]["exact_call_authorization_required"] is True
    assert state["plan_delta_execution_request"]["execution_authorized"] is False
    assert state["investigation_run_status"]["next_action"] == "execute_bounded_read_only_step"
    assert state["source_evidence"] == [{"evidence_id": "evidence:sessions", "source_type": "mcp"}]


def test_reasoning_role_is_advisory_and_scope_is_bound_deterministically() -> None:
    raw = '{"evidence_need":"authentication_correlation","capability_id":"mcp:splunk:splunk_run_query","access_mode":"read_only","tool_arguments":{"correlate":"sessions_to_auth"}}'
    result = propose_plan_delta(
        envelope=_envelope(),
        missing_evidence=["authentication_correlation"],
        raw_output_provider=lambda: raw,
    )
    assert result.proposal is not None
    assert result.proposal["objective"] == _envelope().objective
    assert result.proposal["entities"] == {"user": "alice"}
    assert result.trace["authority"] == "advisory"


def test_accepted_delta_routes_back_to_existing_composed_dispatch(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_investigation_planner_enabled", True)
    state = rp.rp_node_plan_delta_reasoner(
        {
            "approved_investigation_envelope": _envelope().model_dump(mode="json"),
            "capability_snapshot": _snapshot(),
            "investigation_run_status": {"status": "incomplete", "missing_evidence": ["authentication_correlation"]},
            "evidence_state": {"missing": ["authentication_correlation"]},
            "plan_delta_proposal": _proposal().model_dump(mode="json"),
        }
    )
    assert rp._rp_after_plan_delta(state) == "composed_dispatch"
    assert ("plan_delta_reasoner", "composed_dispatch") in rp.resource_planner_graph_edges()


def test_scope_widening_requires_hil_and_write_becomes_remediation() -> None:
    widened = _validate(_proposal(targets=["user:alice", "user:bob"]))
    assert widened.status == "hil_required"
    write = _validate(_proposal(access_mode="write"))
    assert write.status == "remediation_recommended"
    assert write.validated_delta is None


def test_duplicate_delta_no_progress_and_budget_stop() -> None:
    accepted = _validate(_proposal())
    assert accepted.validated_delta is not None
    first = accepted.validated_delta.model_dump(mode="json")
    duplicate = _validate(
        _proposal(prior_revision_fingerprint=first["revision_fingerprint"]),
        [first],
    )
    assert duplicate.status == "no_progress"
    exhausted = _validate(
        _proposal(prior_revision_fingerprint=first["revision_fingerprint"], tool_arguments={"new": True}),
        [first] * 4,
    )
    assert exhausted.status == "budget_exhausted"


def test_unavailable_capability_rejected_and_t1_t4_policy_equivalent() -> None:
    unavailable = _snapshot()
    unavailable["rows"][0]["availability"] = "unavailable"
    rejected = validate_plan_delta(
        _proposal(), envelope=_envelope(), capability_snapshot=unavailable,
        missing_evidence=["authentication_correlation"], prior_revisions=[]
    )
    assert rejected.reason == "capability_not_available_on_snapshot"
    assert _validate(_proposal(), source="deterministic_qualification").model_dump() == _validate(
        _proposal(), source="semantic_t4"
    ).model_dump()


def test_changed_delta_arguments_require_a_distinct_exact_call_grant() -> None:
    selection = {"selected_mcp_server": "splunk", "selected_mcp_tool": "splunk_run_query"}
    a = call_grant_from_tool_call(
        trace_id="p7", selection=selection, tool_arguments={"query": "sessions"},
        execution_intent="spl_search", hil_required=False,
    )
    b = call_grant_from_tool_call(
        trace_id="p7", selection=selection, tool_arguments={"query": "auth_correlation"},
        execution_intent="spl_search", hil_required=False,
    )
    assert a["fingerprint"] != b["fingerprint"]


def test_flag_off_is_p5_honest_stop_and_no_second_executor_loop(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_investigation_planner_enabled", False)
    state = attach_plan_delta_decision({"approved_investigation_envelope": _envelope().model_dump(mode="json")})
    assert state["plan_delta_decision"]["status"] == "disabled"
    source = inspect.getsource(rp)
    assert "while " not in inspect.getsource(rp.rp_node_plan_delta_reasoner)
    assert "_run_guided_hybrid_dispatch" not in inspect.getsource(rp.rp_node_plan_delta_reasoner)
    assert "plan_delta_reasoner" in source
