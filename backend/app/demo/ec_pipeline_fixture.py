"""Synthetic pipeline-dispatch v2 + run_contract surfaces for Experience Center."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.chat.contracts.intent_dispatch import IntentPromptMode, build_intent_dispatch
from app.chat.contracts.pipeline_dispatch import (
    PipelineDispatchState,
    PipelineStage,
    build_plan_dispatch_trace_from_pipeline_dispatch,
    project_dispatch_flags,
)
from app.chat.pipeline_dispatch_builder import build_pipeline_dispatch
from app.chat.run_contract_builder import build_final_evidence_gate, build_route_contract, build_run_contract
from app.demo.ec_mcp_lifecycle_fixture import (
    build_mcp_discovery_context,
    build_mcp_console_lines,
    build_discovery_hops,
)
from app.demo.scenarios import DemoScenario
from app.spl.review_only_spl_postprocessor import finalize_review_only_spl


def build_ec_intent_dispatch(
    *,
    scenario: DemoScenario,
    query_understanding: Any,
    requires_clarification: bool = False,
) -> dict[str, Any]:
    signals = {}
    if hasattr(query_understanding, "model_dump"):
        qu = query_understanding.model_dump()
        signals = {
            "explicit_spl_authoring": qu.get("requested_output_type") == "spl",
            "ambiguous_investigation": bool(qu.get("clarification_needed")),
        }
    if scenario.scenario_id == "mitre_mapping_requires_context" or requires_clarification:
        decision = build_intent_dispatch(
            skip_advisory=False,
            routed_skill=scenario.expected_skill,
            signals=signals,
            requires_clarification=True,
        )
        return decision.model_dump()
    decision = build_intent_dispatch(
        skip_advisory=True,
        skip_reason="deterministic_exact_match_t0",
        routed_skill=scenario.expected_skill,
        signals=signals,
        requires_clarification=False,
    )
    return decision.model_dump()


def build_ec_pipeline_dispatch(
    *,
    scenario: DemoScenario,
    evidence_plan: dict[str, Any],
    route_adjudication: dict[str, Any],
    query_to_intent: dict[str, Any],
    query_understanding: Any,
    selected_use_case: Any,
) -> dict[str, Any]:
    dispatch = build_pipeline_dispatch(
        evidence_plan=evidence_plan,
        route_adjudication=route_adjudication,
        query_to_intent=query_to_intent,
        intent_classification=query_to_intent.get("intent_classification"),
        query_understanding=query_understanding,
        routed={"skill": scenario.expected_skill, "tool_plan": []},
        selected_use_case=selected_use_case,
    )
    payload = dispatch.model_dump(mode="json")
  # EC always projects discovery context when schedule includes pre_spl_mcp_discovery.
    decision = dispatch.decision
    stages = set(decision.stage_schedule)
    discovery_only = scenario.scenario_id == "splunk_env_asa_ti_readiness"
    include_search = scenario.mcp_execution_mode == "mock_success" or scenario.scenario_id in {
        "firewall_deny_coordinated_attack",
        "network_blast_radius_attacker_ip",
    }
    if PipelineStage.pre_spl_mcp_discovery in stages or discovery_only or include_search:
        runtime = payload.setdefault("runtime_context", {})
        runtime["mcp_discovery_context"] = build_mcp_discovery_context(
            discovery_only=discovery_only,
            include_search=include_search and not discovery_only,
        )
        runtime["mcp_phase"] = "pre_spl" if discovery_only else ("post_spl" if include_search else "none")
    return payload


def build_ec_plan_dispatch(pipeline_dispatch: dict[str, Any]) -> dict[str, Any]:
    from app.chat.contracts.pipeline_dispatch import PipelineDispatchContract

    raw_decision = (pipeline_dispatch or {}).get("decision") or {}
    try:
        decision = PipelineDispatchContract.model_validate(raw_decision)
    except Exception:
        decision = PipelineDispatchContract()
    schedule = [stage.value if hasattr(stage, "value") else str(stage) for stage in decision.stage_schedule]
    projected = project_dispatch_flags(decision)
    # Use live builder shape when possible; EC does not require the v2 env flag.
    hooks_schedule: list[str] = []
    for stage in decision.stage_schedule:
        name = stage.value if hasattr(stage, "value") else str(stage)
        if name == "rag_early":
            hooks_schedule.extend(["prepare_rag_only", "rag_early"])
        elif name == "workflow_spl" and "workflow_spl" not in hooks_schedule:
            hooks_schedule.append("workflow_spl")
        elif name == "spl_postprocessor" and "spl_postprocessor" not in hooks_schedule:
            hooks_schedule.append("spl_postprocessor")
        elif name == "spl_source_resolve" and "spl_source_resolve" not in hooks_schedule:
            hooks_schedule.append("spl_source_resolve")
        elif name == "mcp_execution" and "execution" not in hooks_schedule:
            hooks_schedule.append("execution")
    if "workflow_spl" in hooks_schedule and "execution" not in hooks_schedule:
        hooks_schedule.append("execution")
    return {
        "dispatch_source": "ec_fixture_projection",
        "dispatch_schedule": hooks_schedule,
        "dispatch_authority": "pipeline_dispatch_v2",
        "projected_flags": projected,
    }


def build_ec_spl_postprocessor_trace(
    *,
    scenario: DemoScenario,
    candidate_spl: str | None,
    pipeline_dispatch: dict[str, Any],
) -> dict[str, Any] | None:
    if not candidate_spl:
        return None
    mcp_ctx = ((pipeline_dispatch or {}).get("runtime_context") or {}).get("mcp_discovery_context")
    result = finalize_review_only_spl(
        candidate_spl,
        query=scenario.query,
        family="governed_template",
        mcp_discovery_context=mcp_ctx,
    )
    trace = dict(result.trace)
    trace.setdefault("no_op_reason", "governed_template_byte_identity")
    return trace


def build_ec_run_contract(
    *,
    trace_id: str,
    scenario: DemoScenario,
    query_to_intent: dict[str, Any],
    evidence_plan: dict[str, Any],
    route_adjudication: dict[str, Any],
    source_evidence: list[dict[str, Any]],
    spl_validation: dict[str, Any] | None,
    candidate_spl: dict[str, Any] | None,
    execution: dict[str, Any],
    query_understanding: Any,
) -> dict[str, Any]:
    state: dict[str, Any] = {
        "trace_id": trace_id,
        "routed": {"skill": scenario.expected_skill, "tool_plan": []},
        "intent_classification": query_to_intent.get("intent_classification"),
        "evidence_plan": evidence_plan,
        "route_adjudication": route_adjudication,
        "source_evidence": source_evidence,
        "spl_validation": spl_validation,
        "candidate_spl": candidate_spl,
        "execution": execution,
        "query_understanding": query_understanding.model_dump() if hasattr(query_understanding, "model_dump") else query_understanding,
        "request": type("R", (), {"message": scenario.query})(),
    }
    route = build_route_contract(state)
    gate = build_final_evidence_gate(state, route=route)
    contract = build_run_contract(state, route=route, gate=gate)
    return contract.model_dump(mode="json")


def enrich_investigation_lineage(
    lineage: dict[str, Any],
    *,
    pipeline_dispatch: dict[str, Any],
    plan_dispatch: dict[str, Any],
    intent_dispatch: dict[str, Any],
) -> dict[str, Any]:
    enriched = deepcopy(lineage)
    enriched["intent_dispatch"] = intent_dispatch
    enriched["plan_dispatch"] = plan_dispatch
    enriched["pipeline_dispatch_summary"] = {
        "request_mode": ((pipeline_dispatch or {}).get("decision") or {}).get("request_mode"),
        "stage_schedule": ((pipeline_dispatch or {}).get("decision") or {}).get("stage_schedule"),
    }
    return enriched


def build_ec_visual_lanes(
    *,
    scenario: DemoScenario,
    pipeline_dispatch: dict[str, Any],
    analyst_response: dict[str, Any],
) -> dict[str, Any] | None:
    from app.demo.ec_firewall_incident import visual_lanes_for_scenario

    return visual_lanes_for_scenario(scenario, pipeline_dispatch, analyst_response)


def attach_ec_dispatch_surfaces(
    response: dict[str, Any],
    *,
    scenario: DemoScenario,
    query_understanding: Any,
    query_to_intent: dict[str, Any],
    evidence_plan: dict[str, Any],
    route_adjudication: dict[str, Any],
    selected_use_case: Any,
    spl_validation: dict[str, Any] | None,
    candidate_spl: str | None,
    source_evidence: list[dict[str, Any]],
    execution: dict[str, Any],
    investigation_lineage: dict[str, Any],
    analyst_response: dict[str, Any],
) -> dict[str, Any]:
    intent_dispatch = build_ec_intent_dispatch(
        scenario=scenario,
        query_understanding=query_understanding,
        requires_clarification=scenario.scenario_id == "mitre_mapping_requires_context",
    )
    pipeline_dispatch = build_ec_pipeline_dispatch(
        scenario=scenario,
        evidence_plan=evidence_plan,
        route_adjudication=route_adjudication,
        query_to_intent=query_to_intent,
        query_understanding=query_understanding,
        selected_use_case=selected_use_case,
    )
    plan_dispatch = build_ec_plan_dispatch(pipeline_dispatch)
    postprocessor = build_ec_spl_postprocessor_trace(
        scenario=scenario,
        candidate_spl=candidate_spl,
        pipeline_dispatch=pipeline_dispatch,
    )
    if postprocessor and isinstance(response.get("candidate_spl"), dict):
        response["candidate_spl"]["review_only_spl_postprocessor_trace"] = postprocessor
    elif postprocessor and candidate_spl:
        response["candidate_spl"] = {
            "candidate_spl": candidate_spl,
            "review_only_spl_postprocessor_trace": postprocessor,
        }

    trace_id = str(response.get("trace_id") or "demo")
    run_contract = build_ec_run_contract(
        trace_id=trace_id,
        scenario=scenario,
        query_to_intent=query_to_intent,
        evidence_plan=evidence_plan,
        route_adjudication=route_adjudication,
        source_evidence=source_evidence,
        spl_validation=spl_validation,
        candidate_spl=response.get("candidate_spl") if isinstance(response.get("candidate_spl"), dict) else None,
        execution=execution,
        query_understanding=query_understanding,
    )

    control_plane = dict(response.get("control_plane_trace") or {})
    control_plane["intent_dispatch"] = intent_dispatch
    control_plane["pipeline_dispatch"] = pipeline_dispatch
    control_plane["plan_dispatch"] = plan_dispatch

    tools_called = (
        ((pipeline_dispatch.get("runtime_context") or {}).get("mcp_discovery_context") or {}).get("tools_called")
        or []
    )
    if tools_called:
        control_plane["mcp_tools_called"] = tools_called

    visual_lanes = build_ec_visual_lanes(
        scenario=scenario,
        pipeline_dispatch=pipeline_dispatch,
        analyst_response=analyst_response if isinstance(analyst_response, dict) else {},
    )

    from app.demo.ec_mcp_lifecycle_fixture import build_ec_stage_latencies

    enriched_lineage = enrich_investigation_lineage(
        investigation_lineage,
        pipeline_dispatch=pipeline_dispatch,
        plan_dispatch=plan_dispatch,
        intent_dispatch=intent_dispatch,
    )

    updated = dict(response)
    updated["control_plane_trace"] = control_plane
    updated["intent_dispatch"] = intent_dispatch
    updated["pipeline_dispatch"] = pipeline_dispatch
    updated["plan_dispatch"] = plan_dispatch
    updated["run_contract"] = run_contract
    updated["route_authority"] = (run_contract.get("routing") or {})
    updated["investigation_lineage"] = enriched_lineage
    updated["ec_stage_latencies"] = build_ec_stage_latencies(scenario.scenario_id)
    if visual_lanes:
        updated["ec_visual_lanes"] = visual_lanes
    updated["ec_provenance"] = {
        **(updated.get("ec_provenance") or {}),
        "mcp_label": "Splunk MCP search" if execution.get("status") == "executed" else "Splunk MCP readiness",
        "dispatch_authority": "pipeline_dispatch_v2",
    }
    return updated
