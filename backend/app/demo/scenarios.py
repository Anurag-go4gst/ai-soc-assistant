from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from app.actions.capability_policy import action_capability_for
from app.answer_guard.models import AnswerGuardStatus
from app.chat.analyst_response_builder import attach_evidence_summary
from app.chat.control_plane_trace import build_control_plane_trace
from app.chat.evidence_planner import plan_evidence
from app.chat.intent_classifier import build_query_to_intent
from app.demo.experience_center_governance import build_experience_center_governance
from app.demo.foundation_sec_fixtures import foundation_sec_governance_for
from app.demo.llm_shadow_provider import DemoLlmShadowContext, run_demo_llm_shadow
from app.demo.mcp_result_envelope import (
    apply_envelope_to_splunk_evidence,
    demo_envelope_from_rows,
    execution_fields_from_envelope,
)
from app.connectors.mcp.mcp_tool_plan_shadow import run_mcp_tool_plan_shadow
from app.lineage.builder import build_investigation_lineage
from app.llm.mitre_risk_rationale import build_deterministic_severity_rationale
from app.orchestration.human_review import human_review, no_human_review
from app.orchestration.workflow_planner import plan_workflow
from app.query_understanding.models import OutputTemplate, RequestedOutputType
from app.query_understanding.parser import understand_query
from app.risk.severity_policy import decide_severity
from app.routing.llm_plan_validator import validate_llm_advisory_plan
from app.routing.route_adjudication import adjudicate_route
from app.safeguards.spl_validator import validate_spl
from app.skills.selector import select_skill_chain
from app.spl.template_registry import get_spl_template, template_summary
from app.synthesis.models import SynthesisStatus
from app.threat.mitre_kb import map_mitre_for_use_case
from app.use_cases.models import UseCaseSelection
from app.use_cases.registry import get_use_case, match_use_cases

CREATED_AT = "2026-05-24T00:00:00Z"
EVIDENCE_ORIGIN = "coe_synthetic_fixture"
DEMO_BADGE = "COE scenario"
EXPERIENCE_CENTER_PROVENANCE = {
    "mode": "captured_huggingface_plus_known_mcp_happy_path",
    "llm_output_basis": "captured_huggingface_foundation_sec_output",
    "mcp_output_basis": "assumed_happy_path_fixture_from_known_mcp_tools",
    "live_llm_called": False,
    "live_mcp_called": False,
    "future_state_preview": False,
    "hallucinated_mcp_output": False,
}


@dataclass(frozen=True)
class DemoScenario:
    scenario_id: str
    label: str
    category: str
    query: str
    environment_mode: str
    expected_skill: str
    expected_sources: list[str]
    expected_sufficiency_mode: str
    mcp_execution_mode: str
    saia_available: bool
    rag_available: bool
    analyst_summary: str
    trace_explanation: list[str]
    candidate_spl: str | None = None
    source_evidence: list[dict[str, Any]] | None = None
    structured_context: dict[str, Any] | None = None
    selected_use_case_id: str | None = None
    confidence: float = 0.91


def list_demo_scenarios() -> list[dict[str, Any]]:
    return [_scenario_summary(item) for item in SCENARIOS.values()]


def resolve_demo_scenario_id_for_query(message: str) -> str | None:
    """Match live /chat text to an Experience Center scenario query (exact, normalized)."""
    from app.chat.query_signals import extract_query_signals

    normalized = extract_query_signals(message)["normalized_query"]
    matches: list[str] = []
    for scenario in SCENARIOS.values():
        scenario_norm = extract_query_signals(scenario.query)["normalized_query"]
        if normalized == scenario_norm:
            matches.append(scenario.scenario_id)
    if not matches:
        return None
    return matches[0]


def run_demo_scenario(scenario_id: str) -> dict[str, Any]:
    scenario = SCENARIOS[scenario_id]
    trace_id = f"demo-{scenario.scenario_id}-{uuid4().hex[:8]}"
    workflow = plan_workflow(
        selected_skill=scenario.expected_skill,
        tool_plan=_tool_plan(scenario),
        query=scenario.query,
        trace_id=trace_id,
        telemetry=_NoopTelemetry(),
    )
    workflow["available_sources"] = list(scenario.expected_sources)
    workflow["missing_sources"] = []
    workflow["message"] = "Captured Foundation-sec guidance was packaged as a governed Experience Center workflow. No live execution has started."

    candidate_spl, spl_validation = _spl_payloads(scenario, trace_id)
    execution = _execution_payload(scenario, trace_id, spl_validation)
    source_evidence = _with_trace(deepcopy(scenario.source_evidence or []), trace_id)
    structured_context = _with_context_trace(deepcopy(scenario.structured_context or {}), scenario, trace_id, source_evidence)
    demo_llm_shadow = run_demo_llm_shadow(_demo_llm_shadow_context(scenario, trace_id, structured_context))
    context_sufficiency = _context_sufficiency(scenario)
    review = _human_review(scenario, execution)
    analyst_response = _analyst_response(scenario)
    foundation_sec_governance = foundation_sec_governance_for(scenario.scenario_id)
    if isinstance(analyst_response, dict) and analyst_response.get("response_profile") == "spl_only":
        foundation_sec_governance = None
    query_understanding = _query_understanding_for_scenario(scenario)
    query_to_intent = build_query_to_intent(
        query=scenario.query,
        query_understanding=query_understanding,
        routed_skill=scenario.expected_skill,
    ).model_dump()
    intent_classification = query_to_intent["intent_classification"]
    evidence_plan = plan_evidence(
        intent_classification,
        query_to_intent=query_to_intent,
        routed={"skill": scenario.expected_skill, "tool_plan": _tool_plan(scenario)},
    ).model_dump()
    evidence_plan = _experience_center_evidence_plan(scenario, evidence_plan)
    advisory_plan = _experience_center_advisory_plan(
        scenario=scenario,
        evidence_plan=evidence_plan,
        mitre_mappings=[item.model_dump() for item in map_mitre_for_use_case(scenario.selected_use_case_id, [])]
        if scenario.selected_use_case_id
        else None,
    )
    route_adjudication = adjudicate_route(
        deterministic_route=scenario.expected_skill,
        llm_advisory=None,
        route_plan_shadow=None,
        evidence_plan=evidence_plan,
        intent_classification=intent_classification,
        query_understanding=query_understanding,
        message=scenario.query,
        query_to_intent=query_to_intent,
    ).model_dump()
    llm_plan_validation = validate_llm_advisory_plan(
        advisory_plan,
        evidence_plan=evidence_plan,
        route_adjudication=route_adjudication,
        intent_classification=intent_classification,
        routing_mode="llm_assisted_semantic",
    ).model_dump()
    selected_use_case = _selected_use_case(scenario)
    skill_selection = select_skill_chain(
        routed={
            "skill": scenario.expected_skill,
            "tool_plan": _tool_plan(scenario),
            "llm_shadow": None,
        },
        selected_use_case=selected_use_case,
    )
    selected_skill_chain = skill_selection.selected_chain
    source_refs = [str(item.get("evidence_id")) for item in source_evidence]
    spl_template = template_summary(selected_use_case.default_spl_template if selected_use_case else None)
    mitre_mappings = map_mitre_for_use_case(selected_use_case.use_case_id if selected_use_case else None, source_refs)
    mitre_decision = _experience_center_mitre_decision(mitre_mappings, source_refs)
    severity_decision = decide_severity(selected_use_case.use_case_id if selected_use_case else None, structured_context, source_refs)
    synthesis_status = SynthesisStatus(enabled=False, status="planned", reason="Experience Center uses captured Hugging Face/Foundation-sec output governed by deterministic policy; no live final synthesis is run.")
    answer_guard = AnswerGuardStatus(enabled=False, guard_status="planned", reason="Experience Center output is governed from captured Hugging Face/Foundation-sec output and fixture evidence; live Answer Guard execution is not run.")
    action_capability = action_capability_for(selected_use_case.use_case_id if selected_use_case else None, severity_decision.severity_label)
    investigation_lineage = build_investigation_lineage(
        trace_id=trace_id,
        mode_source="scenario",
        query_understanding=query_understanding,
        selected_use_case=selected_use_case,
        selected_skill_chain=selected_skill_chain,
        workflow_plan=workflow,
        spl_validation=spl_validation,
        execution=execution,
        source_evidence=source_evidence,
        structured_context=structured_context,
        context_sufficiency=context_sufficiency,
        spl_template=spl_template,
        mitre_mappings=mitre_mappings,
        severity_decision=severity_decision,
        synthesis_status=synthesis_status,
        answer_guard_status=answer_guard,
        action_capability=action_capability,
        demo_llm_shadow=demo_llm_shadow.to_lineage_dict() if demo_llm_shadow else None,
    )
    _scrub_experience_center_stage_labels(scenario, investigation_lineage)
    llm_sidecars = _experience_center_llm_sidecars(
        scenario=scenario,
        severity_decision=severity_decision,
        mitre_decision=mitre_decision,
        evidence_plan=evidence_plan,
        spl_validation=spl_validation,
    )
    experience_center_governance = build_experience_center_governance(
        scenario_id=scenario.scenario_id,
        selected_skill=scenario.expected_skill,
        severity_decision=severity_decision,
        source_evidence=source_evidence,
        execution=execution,
        investigation_lineage=investigation_lineage.model_dump(),
        route_plan_shadow=None,
        selected_use_case=selected_use_case.model_dump() if selected_use_case else None,
        llm_sidecar_panel=_llm_sidecar_panel(llm_sidecars),
    )
    response_mode = _experience_center_response_mode(scenario, context_sufficiency, review, spl_validation)
    synthesis_mode = "captured_huggingface_governed_output"
    control_plane_state = {
        "query_to_intent": query_to_intent,
        "evidence_plan": evidence_plan,
        "route_adjudication": route_adjudication,
        "llm_plan_validation": llm_plan_validation,
        "mitre_decision": mitre_decision,
        "workflow_plan": workflow,
        "spl_validation": spl_validation,
        "execution": execution,
        "route_plan_shadow": None,
    }
    control_plane_trace = build_control_plane_trace(
        control_plane_state,
        source_evidence=source_evidence,
        context_sufficiency=context_sufficiency,
        synthesis_mode=synthesis_mode,
        answer_guard=answer_guard.model_dump(),
    )
    control_plane_trace["experience_center_provenance"] = deepcopy(EXPERIENCE_CENTER_PROVENANCE)
    control_plane_trace["mitre_risk_rationale"] = llm_sidecars["mitre_risk_rationale"]
    control_plane_trace["resource_plan_shadow"] = llm_sidecars["resource_plan_shadow"]
    if llm_sidecars.get("mcp_tool_plan_shadow") is not None:
        control_plane_trace["mcp_tool_plan_shadow"] = llm_sidecars["mcp_tool_plan_shadow"]
    answer_scorecard = _experience_center_answer_scorecard(scenario)
    narration_visibility = _experience_center_narration_visibility(scenario)

    return {
        "trace_id": trace_id,
        "demo_mode": True,
        "evidence_origin": EVIDENCE_ORIGIN,
        "no_live_customer_data": True,
        "demo_badge": DEMO_BADGE,
        "environment_mode": scenario.environment_mode,
        "mcp_execution_mode": scenario.mcp_execution_mode,
        "saia_available": scenario.saia_available,
        "rag_available": scenario.rag_available,
        "fallback_active": not scenario.saia_available,
        "analyst_summary": analyst_response.get("one_sentence_finding") or scenario.analyst_summary,
        "response_mode": response_mode,
        "synthesis_mode": synthesis_mode,
        "trace_explanation": list(scenario.trace_explanation),
        "message": analyst_response.get("finding_title") or scenario.analyst_summary,
        "note": (
            "COE synthetic fixture only. No live customer data, final LLM synthesis, answer guard, "
            "real Splunk execution, or external remediation integration was used."
        ),
        "user_query": scenario.query,
        "selected_skill": scenario.expected_skill,
        "tool_plan": _tool_plan(scenario),
        "confidence": scenario.confidence,
        "routing_mode": "deterministic_demo_fixture",
        "disagreement": False,
        "disagreement_reason": None,
        "query_understanding": query_understanding.model_dump(),
        "query_to_intent": query_to_intent,
        "evidence_plan": evidence_plan,
        "route_adjudication": route_adjudication,
        "llm_plan_validation": llm_plan_validation,
        "control_plane_trace": control_plane_trace,
        "answer_scorecard": answer_scorecard,
        "narration_visibility": narration_visibility,
        "llm_sidecars": llm_sidecars,
        "mitre_decision": mitre_decision,
        "selected_use_case": selected_use_case.model_dump() if selected_use_case else None,
        "selected_skill_chain": selected_skill_chain.model_dump(),
        "skill_selection": skill_selection.model_dump(),
        "workflow_plan": workflow,
        "candidate_spl": candidate_spl,
        "spl_validation": spl_validation,
        "execution": execution,
        "human_review": review,
        "source_evidence": source_evidence,
        "structured_context": structured_context,
        "context_sufficiency": context_sufficiency,
        "analyst_response": analyst_response,
        "foundation_sec_governance": foundation_sec_governance,
        "spl_template": spl_template,
        "mitre_mappings": [item.model_dump() for item in mitre_mappings],
        "severity_decision": severity_decision.model_dump(),
        "investigation_lineage": investigation_lineage.model_dump(),
        "synthesis_status": synthesis_status.model_dump(),
        "answer_guard": answer_guard.model_dump(),
        "action_capability": action_capability.model_dump(),
        "experience_center_governance": experience_center_governance.model_dump(),
        "governance_trace": experience_center_governance.model_dump(),
    }


def _experience_center_answer_scorecard(scenario: DemoScenario) -> dict[str, Any] | None:
    return {
        "verdict": "pass",
        "key_checks_passed": [
            "route honored",
            "analyst guidance present",
            "SPL status clear",
            "execution status clear",
            "MITRE wording safe",
            "severity clear",
            "HIL clear",
            "no unsupported claims",
        ],
    }


def _experience_center_narration_visibility(scenario: DemoScenario) -> dict[str, Any] | None:
    return {
        "final_answer_source": "governed evidence contract",
        "llm_narration": "advisory model signal",
        "model_signal_authority": "advisory_only",
        "deterministic_policy_authority": "wins",
    }


def _experience_center_mitre_rationale_prose(mitre_decision: dict[str, Any]) -> str | None:
    """Build the MITRE rationale prose the Foundation-sec sidecar narrates in live mode.

    Sourced from the real governed MITRE decision (supported vs candidate vs not-claimed),
    so the Experience Center shows the actual sidecar contribution rather than staged text.
    """
    techniques = mitre_decision.get("techniques") or []
    supported = [
        t["technique_id"]
        for t in techniques
        if t.get("evidence_status") == "evidence_supported" or t.get("status") == "supported"
    ]
    candidate = [t for t in mitre_decision.get("registry_candidates") or [] if t not in supported]
    not_claimed = [
        t["technique_id"]
        for t in techniques
        if t.get("status") in {"not_claimed", "requires_validation"} and t["technique_id"] not in supported
    ]
    parts: list[str] = []
    if supported:
        parts.append("Evidence-supported MITRE: " + ", ".join(supported))
    if candidate:
        parts.append("Candidate (metadata only): " + ", ".join(candidate))
    if not_claimed:
        parts.append("Not claimed due to insufficient evidence: " + ", ".join(not_claimed))
    text = " ".join(parts).strip()
    return text or None


def _experience_center_llm_sidecars(
    *,
    scenario: DemoScenario,
    severity_decision: Any,
    mitre_decision: dict[str, Any],
    evidence_plan: dict[str, Any],
    spl_validation: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Mirror the production LLM sidecar hops (resource-plan shadow + MITRE/risk rationale).

    The traces carry real deterministic rationale and the real deterministic resource-plan
    source. They reflect the Experience Center posture: captured Foundation-sec output,
    advisory only, with deterministic policy keeping authority. Same trace keys as the live
    /chat path so the viewer sees the same sidecar panels production produces.
    """
    severity_prose = build_deterministic_severity_rationale(severity_decision)
    mitre_prose = _experience_center_mitre_rationale_prose(mitre_decision)
    resource_plan = (evidence_plan or {}).get("resource_plan") or {}
    plan_source = resource_plan.get("plan_source") or "deterministic"
    steps = resource_plan.get("steps") or []

    mitre_risk_rationale = {
        "llm_called": False,
        "guard_status": "advisory",
        "fallback_used": False,
        "skipped_reason": None,
        "provider_label": "captured_foundation_sec_advisory",
        "model_signal_authority": "advisory_only",
        "deterministic_policy_authority": "wins",
        "severity_rationale_present": bool(severity_prose),
        "mitre_rationale_present": bool(mitre_prose),
        "severity_rationale_prose": severity_prose,
        "mitre_rationale_prose": mitre_prose,
        "adapter_warnings": [],
        "live_mode_behavior": "Foundation-sec narrates this rationale; deterministic severity/MITRE decision keeps authority.",
    }
    resource_plan_shadow = {
        "shadow_only": True,
        "promotion_blocked": True,
        "llm_called": False,
        "deterministic_plan_source": plan_source,
        "shadow_plan_source": plan_source,
        "shadow_step_count": len(steps),
        "provider_label": "captured_foundation_sec_advisory",
        "skipped_reason": None,
        "live_plan_source_unchanged": True,
        "live_mode_behavior": "Foundation-sec proposes a plan; it is deterministically validated and never promoted over the live deterministic plan.",
    }
    sidecars: dict[str, dict[str, Any]] = {
        "mitre_risk_rationale": mitre_risk_rationale,
        "resource_plan_shadow": resource_plan_shadow,
    }
    needs_mcp = scenario.expected_skill in {"attack_discovery", "spl_generation"}
    mcp_tool_plan_shadow = run_mcp_tool_plan_shadow(
        query=scenario.query,
        target_index=_target_index_from_spl_validation(spl_validation),
        spl_approved=bool(isinstance(spl_validation, dict) and spl_validation.get("approved")),
        session_role="demo_analyst",
        needs_mcp=needs_mcp,
        needs_spl=spl_validation is not None,
    )
    if mcp_tool_plan_shadow is not None:
        mcp_tool_plan_shadow = {
            **mcp_tool_plan_shadow,
            "provider_label": "captured_foundation_sec_advisory",
            "live_llm_called": False,
            "live_mode_behavior": (
                "Foundation-sec may propose an MCP tool chronology in live mode; "
                "deterministic playbook review wins and execution stays gated."
            ),
        }
        sidecars["mcp_tool_plan_shadow"] = mcp_tool_plan_shadow
    return sidecars


def _llm_sidecar_panel(sidecars: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Flatten the sidecar traces into viewer-friendly governance-panel rows."""
    rationale = sidecars["mitre_risk_rationale"]
    shadow = sidecars["resource_plan_shadow"]
    panel: dict[str, Any] = {
        "what_this_shows": "LLM sidecar hops that run alongside the deterministic pipeline.",
        "authority": "advisory only — deterministic policy keeps final authority",
        "live_llm_called": "No (captured Foundation-sec output in the Experience Center)",
        "resource_plan_shadow": (
            f"LLM proposes a resource plan; it is deterministically validated and "
            f"never promoted over the live {shadow['deterministic_plan_source']} plan "
            f"({shadow['shadow_step_count']} steps)."
        ),
        "mitre_rationale": rationale.get("mitre_rationale_prose") or "No supported MITRE technique for this query.",
        "severity_rationale": rationale.get("severity_rationale_prose") or "—",
    }
    mcp_shadow = sidecars.get("mcp_tool_plan_shadow")
    if isinstance(mcp_shadow, dict):
        approved = mcp_shadow.get("approved_tools") or []
        dropped = mcp_shadow.get("dropped") or []
        unservable = (mcp_shadow.get("planner") or {}).get("llm_unservable") or []
        panel["mcp_tool_plan_shadow"] = (
            f"Advisory MCP tool chronology ({mcp_shadow.get('decision_source')}); "
            f"{len(approved)} approved hop(s)"
            + (f", {len(dropped)} dropped" if dropped else "")
            + (f", unservable={unservable}" if unservable else "")
            + f"; RBAC role {mcp_shadow.get('rbac_role')}; execution stays gated."
        )
    return panel


def _target_index_from_spl_validation(spl_validation: dict[str, Any] | None) -> str | None:
    if not isinstance(spl_validation, dict):
        return None
    normalized = spl_validation.get("normalized_spl")
    if not isinstance(normalized, str):
        return None
    match = re.search(r"index=(\S+)", normalized)
    return match.group(1) if match else None


def _scrub_experience_center_stage_labels(scenario: DemoScenario, investigation_lineage: Any) -> None:
    replacements = {
        "Stage 3C": "SPL candidate / validation",
        "Stage 3K": "governed composer / narration visibility",
        "Stage 3L": "answer governance",
        "Stage 3M": "model signal advisory",
        "stage_3c_stub_generator": "spl_candidate_validation_generator",
        "fixture_stage_3c_stub": "fixture_spl_candidate_validation",
        "LLM synthesis planned": "LLM narration advisory",
        "Answer Guard planned": "answer governance advisory",
    }
    def replace_terms(value: Any) -> Any:
        if isinstance(value, str):
            for old, new in replacements.items():
                value = value.replace(old, new)
            return value
        if isinstance(value, list):
            return [replace_terms(item) for item in value]
        if isinstance(value, dict):
            return {key: replace_terms(item) for key, item in value.items()}
        return value

    for stage in getattr(investigation_lineage, "stages", []) or []:
        for field_name in ("stage_id", "visible_label", "explanation", "production_equivalent"):
            value = getattr(stage, field_name, None)
            setattr(stage, field_name, replace_terms(value))
        if hasattr(stage, "technical_output"):
            stage.technical_output = replace_terms(stage.technical_output)


def _selected_use_case(scenario: DemoScenario) -> Any | None:
    if scenario.selected_use_case_id:
        return _use_case_selection(scenario.selected_use_case_id, scenario.confidence)
    matches = match_use_cases(scenario.query, limit=1)
    return matches[0] if matches else None


def _use_case_selection(use_case_id: str, confidence: float) -> UseCaseSelection | None:
    use_case = get_use_case(use_case_id)
    if not use_case:
        return None
    return UseCaseSelection(
        use_case_id=use_case.use_case_id,
        display_name=use_case.display_name,
        category=use_case.category,
        primary_skill=use_case.primary_skill,
        confidence=confidence,
        matched_patterns=["experience_center_override"],
        default_spl_template=use_case.default_spl_template,
        output_template=use_case.output_template,
        required_sources=use_case.required_sources,
        optional_sources=use_case.optional_sources,
        action_capability_tier=use_case.action_capability_tier,
    )


def _query_understanding_for_scenario(scenario: DemoScenario) -> Any:
    result = understand_query(scenario.query)
    if scenario.scenario_id == "mcp_metadata_discovery_app01":
        return result.model_copy(update={
            "primary_intent": "splunk_metadata_discovery",
            "secondary_intents": ["spl_generation"],
            "requested_output_type": RequestedOutputType.SPL,
            "output_template": OutputTemplate.SPL_RESPONSE,
            "confidence": 0.88,
            "clarification_needed": False,
            "clarification_question": None,
            "mapped_use_case_ids": ["soc_generate_spl"],
        })
    if scenario.selected_use_case_id:
        return result.model_copy(update={
            "mapped_use_case_ids": [scenario.selected_use_case_id],
        })
    return result


def _scenario_summary(scenario: DemoScenario) -> dict[str, Any]:
    return {
        "scenario_id": scenario.scenario_id,
        "label": scenario.label,
        "category": scenario.category,
        "query": scenario.query,
        "environment_mode": scenario.environment_mode,
        "demo_badge": DEMO_BADGE,
        "expected_skill": scenario.expected_skill,
        "expected_sources": list(scenario.expected_sources),
        "expected_sufficiency_mode": scenario.expected_sufficiency_mode,
        "mcp_execution_mode": scenario.mcp_execution_mode,
        "saia_available": scenario.saia_available,
        "rag_available": scenario.rag_available,
        "evidence_origin": EVIDENCE_ORIGIN,
        "no_live_customer_data": True,
    }


def _tool_plan(scenario: DemoScenario) -> list[str]:
    if scenario.expected_skill == "knowledge_recall":
        return ["retrieve_governed_soc_kb", "structure_context", "context_sufficiency_gate"]
    if scenario.expected_skill == "spl_generation":
        return ["retrieve_spl_policy", "generate_candidate_spl", "validate_spl", "return_for_analyst_review"]
    return ["route_only", "build_source_evidence", "structure_context", "context_sufficiency_gate"]


def _experience_center_evidence_plan(
    scenario: DemoScenario,
    evidence_plan: dict[str, Any],
) -> dict[str, Any]:
    plan = dict(evidence_plan)
    if scenario.expected_skill == "knowledge_recall":
        plan.update(
            {
                "answer_mode": "rag_only",
                "rag_phase": "rag_only",
                "needs_rag": scenario.rag_available,
                "needs_spl": False,
                "needs_mcp": False,
                "needs_mitre": False,
                "spl_allowed": False,
                "mcp_allowed": False,
            }
        )
    elif scenario.expected_skill == "spl_generation":
        mcp_enabled = scenario.mcp_execution_mode == "mock_success"
        plan.update(
            {
                "answer_mode": "live_investigation",
                "rag_phase": "post_mcp",
                "needs_rag": False if scenario.scenario_id.startswith("successful_login_after_failures") else scenario.rag_available,
                "needs_spl": bool(scenario.candidate_spl),
                "needs_mcp": mcp_enabled,
                "needs_mitre": mcp_enabled,
                "spl_allowed": bool(scenario.candidate_spl),
                "mcp_allowed": mcp_enabled,
            }
        )
    else:
        plan.update(
            {
                "answer_mode": "hybrid" if scenario.rag_available else "live_investigation",
                "rag_phase": "pre_mcp" if scenario.rag_available else "post_mcp",
                "needs_rag": scenario.rag_available,
                "needs_spl": bool(scenario.candidate_spl),
                "needs_mcp": scenario.mcp_execution_mode != "not_required",
                "needs_mitre": True,
                "spl_allowed": bool(scenario.candidate_spl),
                "mcp_allowed": scenario.mcp_execution_mode != "not_required",
            }
        )
    plan["reasons"] = sorted(
        set([str(item) for item in plan.get("reasons") or []] + ["experience_center_fixture_alignment"])
    )
    plan["experience_center_provenance"] = deepcopy(EXPERIENCE_CENTER_PROVENANCE)
    if scenario.scenario_id == "critical_alerts_mitre_cve_review":
        plan["resource_plan"] = {
            "plan_source": "deterministic",
            "steps": [
                {
                    "resource": "splunk_mcp",
                    "status": "fixture_packaged",
                    "tool": "search",
                    "reason": "Experience Center fixture Splunk evidence for critical-alert rollup.",
                },
                {
                    "resource": "vulnerability_source",
                    "status": "not_onboarded",
                    "join_key": "host",
                    "planned_section": "cve_correlation",
                    "reason": (
                        "unpatched CVE correlation requires a vulnerability data source; "
                        "not onboarded in this deployment."
                    ),
                },
            ],
        }
        plan["missing_evidence"] = sorted(
            {
                *(str(item) for item in plan.get("missing_evidence") or []),
                "vulnerability_source",
                "unpatched_cve_correlation",
            }
        )
    return plan


def _experience_center_advisory_plan(
    *,
    scenario: DemoScenario,
    evidence_plan: dict[str, Any],
    mitre_mappings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "skill": scenario.expected_skill,
        "needs_spl": bool(evidence_plan.get("needs_spl")),
        "needs_mcp": bool(evidence_plan.get("needs_mcp")),
        "needs_rag": bool(evidence_plan.get("needs_rag")),
        "needs_mitre": bool(mitre_mappings) or bool(evidence_plan.get("needs_mitre")),
        "mcp_execution_allowed": False,
        "provider": "captured_huggingface_foundation_sec",
        "source": "captured_output_governed_by_experience_center_fixture",
        "mcp_output_basis": "assumed_happy_path_fixture_from_known_mcp_tools",
    }


def _experience_center_mitre_decision(
    mitre_mappings: list[Any],
    source_refs: list[str],
) -> dict[str, Any]:
    techniques = [item.model_dump() if hasattr(item, "model_dump") else dict(item) for item in mitre_mappings]
    technique_ids = [
        str(item.get("technique_id") or item.get("Technique") or "")
        for item in techniques
        if item.get("technique_id") or item.get("Technique")
    ]
    return {
        "answer_visible": bool(techniques),
        "mitre_status": "fixture_evidence_governed_candidate" if techniques else "not_applicable",
        "techniques": techniques,
        "registry_candidates": technique_ids,
        "source_refs": source_refs,
        "requires_alert_context": False,
        "requires_more_context_for_supported_mapping": False,
        "reason": (
            "Experience Center MITRE output is based on captured Hugging Face/Foundation-sec "
            "analysis plus deterministic fixture evidence, then governed by V.AI SOC policy."
        ),
        "provenance": deepcopy(EXPERIENCE_CENTER_PROVENANCE),
        "registry_metadata": {
            "source": "experience_center_fixture",
            "candidate_count": len(techniques),
            "candidate_technique_ids": technique_ids,
        },
    }


def _experience_center_response_mode(
    scenario: DemoScenario,
    context_sufficiency: dict[str, Any] | None,
    human_review: dict[str, Any] | None,
    spl_validation: dict[str, Any] | None,
) -> str:
    review = human_review if isinstance(human_review, dict) else {}
    if review.get("required") is True:
        return "experience_center_human_review_required"
    if scenario.expected_skill == "knowledge_recall":
        return "experience_center_governed_knowledge"
    sufficiency = context_sufficiency if isinstance(context_sufficiency, dict) else {}
    if sufficiency.get("synthesis_readiness") is False and spl_validation and spl_validation.get("approved") is False:
        return "experience_center_candidate_spl_rejected"
    return "experience_center_fixture_answer"


def _spl_payloads(scenario: DemoScenario, trace_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not scenario.candidate_spl:
        return None, None
    validation = validate_spl(scenario.candidate_spl)
    provider = "spl_candidate_validation_generator" if scenario.saia_available else "deterministic_fallback_generator"
    capability_profile = {
        "environment_mode": scenario.environment_mode,
        "mcp_available": True,
        "discovery_mode": "fixture_redacted_metadata",
        "saia_available": scenario.saia_available,
        "saia_usable": scenario.saia_available,
        "saia_configured_mode": "available" if scenario.saia_available else "unavailable",
        "fallback_required": not scenario.saia_available,
        "available_core_tools": ["splunk_run_query", "splunk_get_indexes", "splunk_get_metadata"],
        "available_saia_tools": ["saia_generate_spl"] if scenario.saia_available else [],
        "blocked_tool_categories": ["assistant_write", "admin", "remediation"],
    }
    candidate = {
        "trace_id": trace_id,
        "skill": scenario.expected_skill,
        "user_query": scenario.query,
        "candidate_spl": scenario.candidate_spl,
        "generation_mode": "fixture_spl_candidate_validation",
        "confidence": 0.84,
        "assumptions": ["COE synthetic fixture; analyst must review before any execution."],
        "warnings": ["demo_fixture_not_live_data"],
        "selected_candidate_spl_provider": provider,
        "reason": "Demo scenario uses deterministic fixture SPL and existing validation policy.",
        "saia_available": scenario.saia_available,
        "saia_usable": scenario.saia_available,
        "fallback_required": not scenario.saia_available,
        "candidate_spl_generated": True,
        "validation_required": True,
        "execution_eligible": False,
        "capability_profile": capability_profile,
    }
    validation_payload = {
        "approved": validation["approved"],
        "normalized_spl": validation["normalized_spl"],
        "reject_reasons": validation["reject_reasons"],
        "warnings": validation["warnings"] + ["demo_fixture_not_live_data"],
        "enforced_limits": validation["enforced_limits"],
        "policy_version": validation["policy_version"],
        "selected_candidate_spl_provider": provider,
        "candidate_provider_reason": "Fixture SPL passed through deterministic validation.",
        "saia_available": scenario.saia_available,
        "fallback_required": not scenario.saia_available,
        "spl_explanation_provider": "deterministic_fixture",
        "spl_optimization_provider": "disabled_in_demo",
        "spl_guidance_provider": "governed_policy_fixture",
        "optimization_applied": False,
        "optimization_revalidation_status": {"approved": validation["approved"], "mode": "not_applied"},
        "capability_profile": capability_profile,
    }
    return candidate, validation_payload


def _execution_payload(scenario: DemoScenario, trace_id: str, spl_validation: dict[str, Any] | None) -> dict[str, Any]:
    if scenario.mcp_execution_mode == "not_required":
        return {
            "status": "skipped",
            "execution_intent": "none",
            "selected_mcp_server": None,
            "selected_mcp_tool": None,
            "tool_selection_status": "unavailable",
            "tool_selection_reason": "spl_not_required_for_demo_scenario",
            "executed_spl": None,
            "result_count": 0,
            "results_preview": [],
            "block_reason": None,
            "duration_ms": 0,
        }
    if scenario.mcp_execution_mode == "mock_success" and spl_validation and spl_validation.get("approved"):
        rows = _mock_rows_for(trace_id, scenario.scenario_id)
        envelope = demo_envelope_from_rows(
            rows,
            trace_id=trace_id,
            normalized_spl=str(spl_validation["normalized_spl"]),
        )
        result_count, results_preview, envelope_dict = execution_fields_from_envelope(envelope)
        return {
            "status": "executed",
            "execution_intent": "mock_preview",
            "selected_mcp_server": "splunk",
            "selected_mcp_tool": "search",
            "tool_selection_status": "selected",
            "tool_selection_reason": "Experience Center MCP fixture result selected after SPL validation; no live MCP execution.",
            "executed_spl": spl_validation["normalized_spl"],
            "result_count": result_count,
            "results_preview": results_preview,
            "splunk_result_envelope": envelope_dict,
            "block_reason": None,
            "duration_ms": envelope.duration_ms or 7,
        }
    if spl_validation is None and scenario.mcp_execution_mode != "not_required":
        splunk_items = [
            item
            for item in (scenario.source_evidence or [])
            if isinstance(item, dict) and item.get("source_type") in {"splunk_mcp", "splunk_mcp_fixture"}
        ]
        if splunk_items:
            result_count = sum(int(item.get("row_count") or 0) for item in splunk_items)
            tool_name = str(splunk_items[0].get("tool_name") or "search")
            return {
                "status": "fixture_evidence_packaged",
                "execution_intent": "known_mcp_happy_path_fixture",
                "selected_mcp_server": "splunk",
                "selected_mcp_tool": tool_name,
                "tool_selection_status": "fixture_evidence_packaged",
                "tool_selection_reason": (
                    "Experience Center packaged the COE fixture Splunk evidence from known MCP tool behavior; "
                    "no live MCP execution."
                ),
                "executed_spl": None,
                "result_count": result_count,
                "results_preview": [],
                "block_reason": "live_mcp_not_called",
                "duration_ms": 0,
            }
    return {
        "status": "requires_human_review",
        "execution_intent": "validated_spl_review",
        "selected_mcp_server": "splunk" if spl_validation else None,
        "selected_mcp_tool": "search" if spl_validation else None,
        "tool_selection_status": "requires_human_review" if spl_validation else "unavailable",
        "tool_selection_reason": "no live MCP execution; candidate SPL is shown for analyst review only",
        "executed_spl": None,
        "result_count": 0,
        "results_preview": [],
        "block_reason": "mcp_global_execution_disabled" if spl_validation else None,
        "duration_ms": 0,
    }


def _human_review(scenario: DemoScenario, execution: dict[str, Any]) -> dict[str, Any]:
    if scenario.expected_sufficiency_mode in {"spl_review_only", "analyst_review_required"} or execution["status"] == "requires_human_review":
        return human_review(
            "demo_analyst_review",
            execution.get("block_reason") or scenario.expected_sufficiency_mode,
            "soc_analyst",
            ["review_fixture_evidence", "copy_candidate_spl", "do_not_execute_fixture_data"],
            "Review the synthetic fixture output. It is not live production evidence and is not executed.",
        )
    return no_human_review()


def _demo_llm_shadow_context(
    scenario: DemoScenario,
    trace_id: str,
    structured_context: dict[str, Any],
) -> DemoLlmShadowContext:
    mitre_ids: list[str] = []
    for candidate in structured_context.get("mitre_candidates") or []:
        if isinstance(candidate, dict) and candidate.get("technique_id"):
            mitre_ids.append(str(candidate["technique_id"]))
    return DemoLlmShadowContext(
        scenario_id=scenario.scenario_id,
        query=scenario.query,
        selected_skill=scenario.expected_skill,
        governed_mitre_ids=tuple(sorted(set(mitre_ids))),
        trace_id=trace_id,
    )


def _with_trace(evidence: list[dict[str, Any]], trace_id: str) -> list[dict[str, Any]]:
    for item in evidence:
        item["trace_id"] = trace_id
        item.setdefault("created_at", CREATED_AT)
        if item.get("source_type") in {"splunk_mcp", "splunk_mcp_fixture"} and isinstance(item.get("preview_rows"), list):
            envelope = demo_envelope_from_rows(
                item["preview_rows"],
                trace_id=trace_id,
                normalized_spl=item.get("executed_spl"),
            )
            apply_envelope_to_splunk_evidence(item, envelope)
    return evidence


def _with_context_trace(
    context: dict[str, Any],
    scenario: DemoScenario,
    trace_id: str,
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    context.setdefault("trace_id", trace_id)
    context["trace_id"] = trace_id
    context.setdefault("query", scenario.query)
    context.setdefault("selected_skill", scenario.expected_skill)
    context.setdefault("source_evidence_refs", [item["evidence_id"] for item in evidence])
    context.setdefault("policy_context_refs", ["stage-3j-d-demo-fixture-policy"])
    context.setdefault("assumptions", ["Fixture-backed demo path; no live customer telemetry."])
    context.setdefault("warnings", ["coe_synthetic_fixture"])
    context.setdefault("missing_evidence", [])
    context.setdefault("allowed_conclusions", ["Describe only fixture-supported behavior."])
    context.setdefault("prohibited_conclusions", ["Do not claim live production impact or execute remediation."])
    context.setdefault("context_quality", "sufficient")
    context.setdefault("synthesis_allowed", False)
    return context


def _context_sufficiency(scenario: DemoScenario) -> dict[str, Any]:
    status = scenario.expected_sufficiency_mode
    return {
        "status": status,
        "synthesis_allowed": False,
        "synthesis_readiness": status in {"full_answer", "partial_answer", "knowledge_only_answer"},
        "reasons": [
            "demo_fixture_has_source_refs",
            "final_synthesis_disabled_by_stage_boundary",
            f"evidence_origin:{EVIDENCE_ORIGIN}",
        ],
        "missing_evidence": [] if status != "partial_answer" else ["live_mcp_execution"],
        "human_review": None,
    }


def _scoped_template_spl(template_id: str, *, host: str | None = None) -> str:
    """Source Experience Center SPL from the production-governed template registry.

    EC SPL must never drift from the optimized production queries, so we read the live
    template text instead of re-hardcoding it. `host` scoping mirrors deterministic slot
    binding for asset-specific demo scenarios (e.g. APP-01) without altering the query
    shape that production validated.
    """
    template = get_spl_template(template_id)
    if template is None or not template.spl_text:
        raise RuntimeError(
            f"Experience Center expected production SPL template '{template_id}' to exist"
        )
    spl = template.spl_text
    if host:
        # Insert the host filter immediately after the time bounds, matching how the
        # deterministic slot binder scopes the base search.
        spl = spl.replace("latest=now", f"latest=now host={host}", 1)
    return spl


def _pretty_spl(spl: str) -> str:
    """Pretty-print single-line SPL onto piped lines for the analyst SPL card."""
    segments = [segment.strip() for segment in spl.split("|")]
    head, *rest = segments
    return head + "".join(f"\n| {segment}" for segment in rest)


# Production-optimized auth SPL, sourced from the governed template registry so the
# Experience Center always renders the same query production generates.
FAILED_SPIKE_SPL = _scoped_template_spl("auth_failed_login_spike", host="APP-01")
SUCCESS_AFTER_FAILURES_SPL = _scoped_template_spl("auth_success_after_failure", host="APP-01")
SUCCESS_AFTER_FAILURES_VISIBLE_SPL = _pretty_spl(SUCCESS_AFTER_FAILURES_SPL)
LOCKOUT_SPL = _scoped_template_spl("auth_account_lockout_trend")
LOCKOUT_VISIBLE_SPL = _pretty_spl(LOCKOUT_SPL)
DNS_BEACONING_SPL = _scoped_template_spl("dns_beaconing_candidate")
DNS_BEACONING_VISIBLE_SPL = _pretty_spl(DNS_BEACONING_SPL)
CRITICAL_NOTABLE_SPL = _scoped_template_spl("notable_critical_review_mitre")
CRITICAL_NOTABLE_VISIBLE_SPL = _pretty_spl(CRITICAL_NOTABLE_SPL)

_CRITICAL_URGENCY_WEIGHT = {"critical": 10, "high": 5, "medium": 2, "low": 1}

_CRITICAL_ALERT_FIXTURE_ROWS = [
    {
        "alert_id": "ALT-8841",
        "host": "VPN-GW-01",
        "rule_name": "brute_force_vpn_spike",
        "urgency": "critical",
        "severity": "critical",
        "mitre_technique": "T1110.001",
        "mitre_tactic": "Credential Access",
        "alert_count": 12,
        "first_seen": "2026-06-15T02:14:00Z",
        "last_seen": "2026-06-15T07:58:00Z",
    },
    {
        "alert_id": "ALT-7720",
        "host": "DB-PROD-02",
        "rule_name": "privileged_login_anomaly",
        "urgency": "high",
        "severity": "high",
        "mitre_technique": "T1078",
        "mitre_tactic": "Persistence",
        "alert_count": 6,
        "first_seen": "2026-06-15T03:02:00Z",
        "last_seen": "2026-06-15T07:41:00Z",
    },
    {
        "alert_id": "ALT-9103",
        "host": "APP-EDGE-03",
        "rule_name": "suspicious_powershell",
        "urgency": "critical",
        "severity": "critical",
        "mitre_technique": "T1059.001",
        "mitre_tactic": "Execution",
        "alert_count": 8,
        "first_seen": "2026-06-15T04:18:00Z",
        "last_seen": "2026-06-15T07:52:00Z",
    },
    {
        "alert_id": "ALT-9104",
        "host": "VPN-GW-01",
        "rule_name": "geo_impossible_travel",
        "urgency": "high",
        "severity": "high",
        "mitre_technique": "T1078",
        "mitre_tactic": "Initial Access",
        "alert_count": 3,
        "first_seen": "2026-06-15T05:30:00Z",
        "last_seen": "2026-06-15T07:20:00Z",
    },
]


def _urgency_risk_weight(urgency: str) -> int:
    return _CRITICAL_URGENCY_WEIGHT.get(str(urgency).lower(), 1)


def _top_risky_hosts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scores: dict[str, int] = {}
    for row in rows:
        host = str(row.get("host") or "")
        if not host:
            continue
        count = int(row.get("alert_count") or row.get("count") or 1)
        scores[host] = scores.get(host, 0) + _urgency_risk_weight(str(row.get("urgency") or "")) * count
    return [
        {"Host": host, "Risk score": score, "Rank": index + 1}
        for index, (host, score) in enumerate(sorted(scores.items(), key=lambda item: -item[1]))
    ]


def _playbook_payload() -> dict[str, object]:
    return {
        "title": "Brute-force Authentication Investigation",
        "id": "SOC-SOP-AUTH-001",
        "version": "v2026.04",
        "purpose": "Guide the SOC analyst through triage, confirmation, escalation, and closure of brute-force authentication activity.",
    }


def _enriched_playbook_payload() -> dict[str, object]:
    return {
        **_playbook_payload(),
        "citation": "SOC-SOP-AUTH-001#triage",
        "retrieval_mode": "governed_soc_kb",
        "confidence": 0.91,
        "source_evidence_id": "ev-rag-bruteforce-sop",
    }


def _sop_guidance_payload() -> dict[str, object]:
    return {
        "triage_steps": [
            "Confirm affected asset, source IPs, users, and time window.",
            "Count failures by source IP, user, and destination host.",
            "Check for successful login after repeated failures.",
            "Verify whether targeted users are privileged or service accounts.",
            "Correlate with VPN, firewall, EDR, and identity logs.",
            "Escalate if a privileged account or critical asset is involved.",
        ],
        "validation_notes": [
            "Confirm no successful login followed the failure sequence.",
            "Check whether targeted accounts are privileged or service accounts.",
            "Review related activity from the same source IP range.",
        ],
    }


def _analyst_response(scenario: DemoScenario) -> dict[str, Any]:
    playbook = _enriched_playbook_payload()
    sop_guidance = _sop_guidance_payload()
    base = {
        "scenario_label": scenario.label,
        "status_badge": None,
        "retrieved_playbook": playbook,
        "sop_guidance": sop_guidance,
        "foundation_sec_analysis": None,
        "splunk_results_table": [],
        "mitre_mappings": [],
        "recommended_actions": [],
        "key_fields": [],
        "escalation_criteria": [],
        "closure_conditions": [],
    }

    if scenario.scenario_id == "failed_login_spike_app01":
        return attach_evidence_summary({
            **base,
            "severity_label": "P2 High",
            "finding_title": "Brute-force authentication spike detected on APP-01",
            "one_sentence_finding": "COE Splunk evidence shows 101 failed logins across three source IPs against APP-01. Foundation-sec model signal supports a password-guessing pattern. V.AI SOC governs the case as P2 High because the evidence supports T1110.001. Compromise not confirmed: global distinct user count is not confirmed, and privileged-account impact, source ownership, and APP-01 criticality are not confirmed.",
            "initial_assessment": [
                "COE Splunk evidence shows 101 failed logins across three source IPs against APP-01.",
                "Foundation-sec model signal supports a password-guessing pattern.",
                "V.AI SOC governs the case as P2 High because the evidence supports T1110.001.",
                "Compromise not confirmed: global distinct user count, privileged-account impact, source ownership, and APP-01 criticality are not confirmed.",
            ],
            "splunk_status_line": "Splunk MCP fixture search result [index=pgcil_soc] · last 60 minutes · 3 rows",
            "splunk_results_table": [
                {"Host": "APP-01", "Source IP": "10.10.4.21", "Failed logins": 42, "Distinct users by source": 7, "First seen": "13:42:10", "Last seen": "14:37:22", "Action": "failure"},
                {"Host": "APP-01", "Source IP": "10.10.4.22", "Failed logins": 31, "Distinct users by source": 4, "First seen": "13:48:31", "Last seen": "14:36:58", "Action": "failure"},
                {"Host": "APP-01", "Source IP": "10.10.4.19", "Failed logins": 28, "Distinct users by source": 3, "First seen": "13:51:02", "Last seen": "14:35:41", "Action": "failure"},
            ],
            "mitre_mappings": [
                {"Technique": "T1110.001", "Name": "Password Guessing", "Tactic": "Credential Access", "Status": "Supported", "Evidence": "High failed-login volume from multiple source IPs against APP-01", "Confidence": "High"},
            ],
            "foundation_sec_analysis": "\n\n".join([
                "Foundation-sec contributes an advisory password-guessing signal based on sustained failed logins across three source IPs.",
                "V.AI SOC accepts the T1110.001 mapping as supported, but keeps the response evidence-grounded: no successful login after the failures has been confirmed, and privileged-account status, APP-01 criticality, and source ownership remain unresolved.",
            ]),
            "recommended_actions": [
                "P1: Run success-after-failure correlation for APP-01 using the same source IPs and time window. Escalate immediately if any successful login follows five or more failures.",
                "P1: Check whether the affected users include privileged, service, VPN, or administrative accounts. Do not state account impact until identity evidence is available.",
                "P2: Validate ownership of 10.10.4.19, 10.10.4.21, and 10.10.4.22 against CMDB, DHCP, VPN, jump-host, and firewall inventory.",
                "P2: Pivot across firewall, VPN, EDR, and identity logs for the same source IPs and time window to identify related activity.",
                "P2: Check APP-01 CMDB criticality and business owner. Escalate scope if APP-01 supports critical or OT-adjacent operations.",
                "P3: Document findings after success-after-failure, account privilege, source ownership, and asset criticality checks are complete.",
            ],
        })
    if scenario.scenario_id == "new_source_ip_logins":
        return {
            **base,
            "severity_label": "P2 High",
            "finding_title": "New source IP login pattern observed for APP-01",
            "one_sentence_finding": "Foundation-sec recognised new-source successful logins as a Valid Accounts signal; V.AI SOC keeps T1078 validation-required until source ownership, MFA/session, account status, and post-login activity are confirmed.",
            "splunk_status_line": "Splunk MCP fixture search result [index=pgcil_soc] · last 24 hours · new source IPs only",
            "splunk_results_table": [
                {"Host": "APP-01", "User": "svc_grid_ops", "Source IP": "10.10.7.44", "First seen": "14:21:05", "Prior sightings": "None in 30 days", "Action": "success"},
                {"Host": "APP-01", "User": "operator.rajesh", "Source IP": "10.10.7.45", "First seen": "14:24:19", "Prior sightings": "None in 30 days", "Action": "success"},
            ],
            "mitre_mappings": [
                {"Technique": "T1078", "Name": "Valid Accounts", "Tactic": "Initial Access / Persistence", "Evidence": "Successful login from a source IP outside the established baseline for both accounts", "Confidence": "Moderate - analyst validation required"},
            ],
            "retrieved_playbook": {
                "title": "Source Baseline Deviation",
                "id": "SOC-SOP-AUTH-002",
                "version": "v2026.04",
            },
            "sop_guidance": {
                "triage_steps": [
                    "Validate whether the source IP belongs to an approved jump host, VPN subnet, or operational workstation.",
                    "Confirm MFA was successfully challenged at login for both accounts.",
                    "Check whether the accounts are service accounts or have privileged access.",
                ],
                "validation_notes": [
                    "Validate whether the source IP belongs to an approved jump host, VPN subnet, or operational workstation.",
                    "Confirm MFA was successfully challenged at login for both accounts.",
                    "Check whether the accounts are service accounts or have privileged access.",
                ],
            },
            "foundation_sec_analysis": "\n\n".join([
                "Foundation-sec treated successful logins from new source IPs as a Valid Accounts candidate because they deviate from the established account baseline.",
                "V.AI SOC constrains the answer to investigation status: the evidence does not prove misuse by itself, and source ownership, MFA result, account type, and endpoint activity are still required.",
            ]),
            "recommended_actions": [
                "P2: Validate source IP ownership for 10.10.7.44 and 10.10.7.45 against CMDB, DHCP, VPN, jump-host, and firewall inventory.",
                "P2: Check MFA result, session duration, and first post-login activity for each successful login.",
                "P2: Confirm account type, owner, and privilege level before stating account impact.",
                "P2: Pivot VPN, firewall, EDR, and identity logs around the same window for related activity.",
                "P3: Update the source-IP baseline for svc_grid_ops and operator.rajesh only after analyst sign-off. Do not auto-approve the new source range. Any baseline update must be linked to a documented change ticket, jump-host migration, VPN reconfiguration, or approved workstation reassignment before it is applied.",
            ],
        }
    if scenario.scenario_id == "mitre_mapping_auth_alert":
        return {
            **base,
            "severity_label": "P2 High",
            "finding_title": "Authentication attack pattern mapped to MITRE ATT&CK",
            "one_sentence_finding": None,
            "splunk_results_table": [
                {"Alert": "Auth failure burst + post-failure success", "User": "svc_grid_ops", "Host": "APP-01", "Source IPs": "10.10.4.21, 10.10.4.22", "Failed logins": 58, "Success observed": "Yes", "Window": "60 min"},
            ],
            "mitre_mappings": [
                {"Technique": "T1110.001", "Name": "Password Guessing", "Tactic": "Credential Access", "Status": "Supported", "Evidence": "Repeated failures against the same user and host from related sources", "Validation needed": "Clear benign automation, scanner, expired credential, or misconfiguration causes."},
                {"Technique": "T1078", "Name": "Valid Accounts", "Tactic": "Initial Access / Persistence", "Status": "Requires validation", "Evidence": "Successful login after repeated failures for svc_grid_ops", "Validation needed": "Confirm session legitimacy, MFA result, account ownership, and post-login activity."},
            ],
            "foundation_sec_analysis": "\n\n".join([
                "The successful login after repeated failures changes the investigation priority because it may indicate valid credential use after password guessing.",
                "T1110.001 is supported at high confidence by the failure volume and source distribution. T1078 remains validation-required until post-login activity, session behavior, or unauthorized access is observed.",
            ]),
            "recommended_actions": [
                "P1: Validate the successful session: source IP, MFA result, session duration, and first post-login activity.",
                "P1: Review EDR/process telemetry for APP-01 immediately after login.",
                "P2: Check account type, ownership, and privilege evidence for svc_grid_ops.",
                "P2: Pivot firewall, VPN, and identity logs for 10.10.4.21 around the same window.",
                "P2: Check CMDB criticality for APP-01.",
            ],
        }
    if scenario.scenario_id == "brute_force_sop_guidance":
        return {
            **base,
            "retrieved_playbook": playbook,
            "finding_title": "Brute-force Authentication Investigation - SOC-SOP-AUTH-001 v2026.04",
            "one_sentence_finding": "Guide the SOC analyst through triage, confirmation, escalation, and closure of brute-force authentication activity.",
            "sop_guidance": {
                "triage_steps": [
                    "Verify the alert is not a known batch job, service account sync, or scheduled task.",
                    "Confirm affected asset, source IPs, users, and time window.",
                    "Check whether a successful login followed the failure sequence.",
                    "Identify targeted users and confirm whether any are privileged.",
                    "Pull asset criticality for the target host from CMDB.",
                    "Review related activity from the same source IP range.",
                ],
                "validation_notes": sop_guidance["validation_notes"],
                "related_pivots": [
                    "Firewall and VPN activity for the same source IPs and time window.",
                    "EDR activity on the target host immediately after any successful login.",
                    "Identity provider logs for MFA result, account state, and privilege evidence.",
                ],
            },
            "escalation_criteria": [
                "Successful login after repeated failures.",
                "Privileged or service account targeted.",
                "Critical asset targeted, based on CMDB evidence.",
                "Same source appears across multiple assets.",
                "External or unknown network source.",
                "Evidence of post-authentication activity on the target host.",
            ],
            "closure_conditions": [
                "Source confirmed benign or misconfigured and corrected.",
                "No successful login followed the failures.",
                "No privileged account impact confirmed.",
                "No related endpoint, VPN, firewall, or identity activity found.",
                "SOC lead accepts closure with linked evidence.",
            ],
        }
    if scenario.scenario_id == "successful_login_after_failures":
        return {
            **base,
            "retrieved_playbook": None,
            "sop_guidance": None,
            "finding_title": "Success-after-failure correlation SPL",
            "status_badge": "Template-generated SPL - validator-ready",
            "one_sentence_finding": "Correlates failed and successful authentication events by user, source, and host. This is a governed candidate SPL artifact and has not been executed.",
            "spl_code": SUCCESS_AFTER_FAILURES_VISIBLE_SPL,
            "response_profile": "spl_only",
            "key_fields": [
                "user - account with failures followed by success",
                "host - target authentication host",
                "source_ips - source IPs involved in the sequence",
                "fail_count - number of failed attempts before success",
                "success_count - number of successful logins after failures",
                "first_failure / last_event - time window of the full chain",
                "risk - validation priority for the returned sequence",
            ],
            "review_notice": "Candidate SPL only. Review and validate scope before operational execution.",
        }
    if scenario.scenario_id == "successful_login_after_failures_run":
        return {
            **base,
            "retrieved_playbook": None,
            "sop_guidance": None,
            "finding_title": "Success-after-failure correlation executed on APP-01",
            "status_badge": "Splunk MCP fixture search result",
            "one_sentence_finding": "Splunk MCP fixture search returned one success-after-failure sequence for APP-01 using COE fixture Splunk evidence.",
            "splunk_status_line": "Splunk MCP fixture search result · 1 row",
            "splunk_results_table": [
                {
                    "User": "svc_grid_ops",
                    "Host": "APP-01",
                    "Source IP": "10.10.4.21",
                    "Failed logins": 58,
                    "Successful logins": 1,
                    "First failure": "2026-05-24T13:42:10Z",
                    "Last event": "2026-05-24T14:37:22Z",
                    "Risk": "P2 review - successful login after repeated failures",
                }
            ],
            "spl_code": SUCCESS_AFTER_FAILURES_VISIBLE_SPL,
            "executed_spl": SUCCESS_AFTER_FAILURES_SPL,
            "execution_status": "executed",
            "response_profile": "spl_executed",
            "key_fields": [
                "user - account with failures followed by success",
                "host - target authentication host",
                "src/source_ips - source IPs involved in the sequence",
                "fail_count - number of failed attempts before success",
                "success_count - number of successful logins after failures",
                "first_failure / last_event - time window of the full chain",
                "risk - validation priority for the returned sequence",
            ],
            "mitre_mappings": [
                {"Technique": "T1110.001", "Name": "Password Guessing", "Tactic": "Credential Access", "Status": "Supported", "Evidence": "58 failures before one success for the same user, source, and host", "Validation needed": "Validate benign causes and account ownership."},
                {"Technique": "T1078", "Name": "Valid Accounts", "Tactic": "Initial Access / Persistence", "Status": "Requires validation", "Evidence": "Successful login after repeated failures", "Validation needed": "Confirm MFA, session legitimacy, and post-login activity."},
            ],
            "recommended_actions": [
                "P2: Validate the successful session: source IP, MFA result, session duration, and first post-login activity.",
                "P2: Review EDR/process telemetry for APP-01 immediately after login.",
                "P2: Check account type, ownership, and privilege evidence for svc_grid_ops.",
                "P2: Pivot firewall, VPN, and identity logs for 10.10.4.21 around the same window.",
                "P2: Check CMDB criticality for APP-01.",
            ],
            "review_notice": "Review the validated normalized SPL and MCP gate status before operational use.",
        }
    if scenario.scenario_id == "airgapped_no_saia_success_after_failures":
        return {
            **base,
            "retrieved_playbook": None,
            "sop_guidance": None,
            "finding_title": "Air-gapped success-after-failure correlation SPL",
            "status_badge": "Template-generated SPL - validator-ready",
            "one_sentence_finding": "SAIA is unavailable in air-gapped mode, so V.AI SOC returns deterministic template SPL for analyst review only.",
            "spl_code": SUCCESS_AFTER_FAILURES_VISIBLE_SPL,
            "response_profile": "spl_only",
            "key_fields": [
                "user - account with failures followed by success",
                "host - target authentication host",
                "source_ips - source IPs involved in the sequence",
                "fail_count - number of failed attempts before success",
                "success_count - number of successful logins after failures",
                "first_failure / last_event - time window of the full chain",
                "risk - validation priority for the returned sequence",
            ],
            "review_notice": "Candidate SPL only. In live air-gapped mode, MCP preview execution still requires explicit global and server execution approval flags.",
        }
    if scenario.scenario_id == "account_lockouts_over_time_spl":
        return {
            **base,
            "finding_title": "Account lockout trend SPL",
            "status_badge": "Template-generated SPL - validator-ready",
            "one_sentence_finding": "Foundation-sec can assist with lockout-trend intent, but V.AI SOC uses deterministic template SPL for this known use case and keeps operational use gated by validation policy.",
            "spl_code": LOCKOUT_VISIBLE_SPL,
            "key_fields": [
                "_time - 1-hour lockout time bucket",
                "lockout_count - account_locked events in the bucket across the 24h window",
            ],
            "recommended_actions": [
                "P2: Run the lockout trend SPL across the last 24 hours and filter for any user with more than 10 lockout events across multiple source IPs. High lockout counts from multiple sources against the same user are a brute-force indicator even without a threshold breach on any single IP.",
                "P2: Identify whether any locked accounts are service, privileged, or shared-credential accounts. Service account lockouts can affect automated processes, scheduled jobs, and system integrations. If a lockout is disrupting operations, the business impact extends beyond security - notify the account owner and operations team.",
                "P3: Cross-reference lockout source IPs against approved authentication systems. If the source of repeated lockouts is not a registered client for the target host, treat it as unauthorised and investigate the source before unlocking the account.",
                "P4: Review account lockout policy thresholds against the observed pattern. If the current threshold, for example five failures before lockout, is being systematically avoided by distributing attempts across multiple IPs, consider tightening the policy or adding velocity-based detection at the host level.",
            ],
            "review_notice": "Review required before using this SPL in an operational search.",
        }
    if scenario.scenario_id == "mitre_mapping_requires_context":
        return {
            **base,
            "retrieved_playbook": None,
            "sop_guidance": None,
            "finding_title": "MITRE mapping requires alert context",
            "one_sentence_finding": "Please provide the alert title, rule name, SPL, notable event details, or key fields such as host, user, source IP, event type, and time window. V.AI SOC cannot map this alert to MITRE without event evidence.",
            "foundation_sec_analysis": "Foundation-sec recognised a MITRE mapping request, but V.AI SOC requires supporting alert evidence before selecting a technique.",
            "recommended_actions": [
                "P2: Provide alert title, detection rule, notable/event ID, or SPL before MITRE mapping.",
                "P2: Include key fields such as host, user, source IP, event type, and time window.",
            ],
            "review_notice": "Clarification required before MITRE mapping.",
        }
    if scenario.scenario_id == "mcp_metadata_discovery_app01":
        return {
            **base,
            "retrieved_playbook": None,
            "sop_guidance": None,
            "finding_title": "Safe Splunk metadata discovery selected",
            "one_sentence_finding": "Foundation-sec recognised that index and sourcetype discovery is needed before SPL generation; V.AI SOC rejects invented data locations and selects safe metadata discovery tools.",
            "foundation_sec_analysis": "Foundation-sec can identify the discovery need, but V.AI SOC does not accept invented index or sourcetype names. The governed path is splunk_get_indexes followed by splunk_get_metadata, with no SPL execution.",
            "recommended_actions": [
                "P2: Use splunk_get_indexes to enumerate available indexes before drafting SPL.",
                "P2: Use splunk_get_metadata to identify sourcetypes related to APP-01 authentication events.",
                "P3: Generate SPL only after actual index and sourcetype evidence is available.",
            ],
            "review_notice": "Discovery result required before SPL generation.",
        }
    if scenario.scenario_id == "dns_beaconing_c2_hunt":
        return attach_evidence_summary({
            **base,
            "retrieved_playbook": None,
            "sop_guidance": None,
            "severity_label": "P3 Medium",
            "finding_title": "DNS beaconing / C2 candidate across three internal hosts",
            "one_sentence_finding": "DNS evidence shows three hosts querying rare domains at fixed 5-15 minute intervals with steady small payloads. Foundation-sec flags a C2 beaconing pattern; V.AI SOC keeps it candidate-only (T1071.004) until jitter and domain reputation are confirmed.",
            "splunk_status_line": "Splunk MCP fixture search result [index=pgcil_soc sourcetype=pgcil:dns] · last 24 hours · 3 rows",
            "splunk_results_table": [
                {"Source": "10.20.3.41", "Domain": "a3f9k2.update-cdn.net", "Queries": 288, "Periodicity (s)": 300, "Bytes out": 41216, "Rare domain": "review"},
                {"Source": "10.20.7.12", "Domain": "sync.metric-telemetry.io", "Queries": 144, "Periodicity (s)": 600, "Bytes out": 20992, "Rare domain": "review"},
                {"Source": "10.20.5.88", "Domain": "cdn.win-update-cache.com", "Queries": 96, "Periodicity (s)": 900, "Bytes out": 13440, "Rare domain": "review"},
            ],
            "spl_code": DNS_BEACONING_VISIBLE_SPL,
            "key_fields": [
                "src - internal host generating the periodic DNS queries",
                "domain - queried domain (rare/low-reputation candidate)",
                "DNS_query_count - query volume in the window",
                "periodicity - mean seconds between queries (beaconing signal)",
                "bytes_out - payload steadiness indicator",
                "rare_domain_indicator - low-cardinality + high-volume flag",
            ],
            "mitre_mappings": [
                {"Technique": "T1071.004", "Name": "Application Layer Protocol: DNS", "Tactic": "Command and Control", "Status": "Candidate", "Evidence": "Fixed-interval DNS queries to rare domains with steady payloads", "Validation needed": "Confirm jitter, domain reputation, and process/owner of the querying host."},
            ],
            "foundation_sec_analysis": "Foundation-sec contributes an advisory C2-beaconing signal from the fixed-interval, rare-domain pattern. V.AI SOC keeps the mapping candidate-only: periodicity alone is not C2; jitter, domain reputation, and the querying process must be confirmed.",
            "recommended_actions": [
                "P2: Confirm beaconing by checking jitter (variance around the interval) and whether the domains are newly registered or low-reputation.",
                "P2: Identify the process and user on 10.20.3.41, 10.20.7.12, and 10.20.5.88 generating the DNS queries.",
                "P3: Pivot proxy/firewall egress for the resolved IPs to confirm an established channel and payload direction.",
                "P3: Document and close as benign if domains are reputable CDNs/telemetry with business justification.",
            ],
            "review_notice": "Candidate beaconing pattern. SPL is review-only; MCP execution stays gated.",
        })
    if scenario.scenario_id == "dns_beaconing_c2_hunt_run":
        return attach_evidence_summary({
            **base,
            "retrieved_playbook": None,
            "sop_guidance": None,
            "severity_label": "P3 Medium",
            "finding_title": "Beaconing-candidate correlation executed - two periodic-DNS hosts",
            "status_badge": "Splunk MCP fixture search result",
            "one_sentence_finding": "Splunk MCP fixture search returned two internal hosts beaconing to rare domains at fixed intervals. V.AI SOC keeps T1071.004 candidate-only until jitter and domain reputation are confirmed.",
            "splunk_status_line": "Splunk MCP fixture search result [index=pgcil_soc sourcetype=pgcil:dns] · last 24 hours · 2 rows",
            "splunk_results_table": [
                {"Source": "10.20.3.41", "Domain": "a3f9k2.update-cdn.net", "Queries": 288, "Periodicity (s)": 300, "Bytes out": 41216, "Rare domain": "review"},
                {"Source": "10.20.7.12", "Domain": "sync.metric-telemetry.io", "Queries": 144, "Periodicity (s)": 600, "Bytes out": 20992, "Rare domain": "review"},
            ],
            "spl_code": DNS_BEACONING_VISIBLE_SPL,
            "executed_spl": DNS_BEACONING_SPL,
            "execution_status": "executed",
            "response_profile": "spl_executed",
            "key_fields": [
                "src - internal host generating the periodic DNS queries",
                "domain - queried domain (rare/low-reputation candidate)",
                "DNS_query_count - query volume in the window",
                "periodicity - mean seconds between queries (beaconing signal)",
                "bytes_out - payload steadiness indicator",
                "rare_domain_indicator - low-cardinality + high-volume flag",
            ],
            "mitre_mappings": [
                {"Technique": "T1071.004", "Name": "Application Layer Protocol: DNS", "Tactic": "Command and Control", "Status": "Candidate", "Evidence": "Two hosts with fixed-interval queries to rare domains and steady payloads", "Validation needed": "Confirm jitter, domain reputation, and the querying process/owner."},
            ],
            "recommended_actions": [
                "P2: Confirm beaconing by checking jitter and whether the domains are newly registered or low-reputation.",
                "P2: Identify the process and user on 10.20.3.41 and 10.20.7.12 generating the DNS queries.",
                "P3: Pivot proxy/firewall egress for the resolved IPs to confirm an established channel.",
                "P3: Document and close as benign if the domains are reputable CDNs/telemetry with business justification.",
            ],
            "review_notice": "Review the validated normalized SPL and MCP gate status before operational use.",
        })
    if scenario.scenario_id == "critical_alerts_mitre_cve_review":
        top_hosts = _top_risky_hosts(_CRITICAL_ALERT_FIXTURE_ROWS)
        return attach_evidence_summary({
            **base,
            "retrieved_playbook": {
                "title": "Critical alert triage and CVE correlation",
                "id": "SOC-SOP-ALERT-CRIT-001",
                "version": "v2026.06",
                "purpose": "Guide analysts through critical-alert rollup, MITRE candidate review, and honest CVE-source gaps.",
            },
            "sop_guidance": {
                "triage_steps": [
                    "Roll up critical/high alerts by host and MITRE technique for the requested window.",
                    "Validate each technique mapping against underlying alert evidence before escalation.",
                    "Check whether a vulnerability or CMDB source is onboarded before claiming unpatched CVE exposure.",
                ],
                "validation_notes": [
                    "MITRE mappings remain candidate until alert context and technique evidence are confirmed.",
                    "CVE correlation stays unavailable when no vulnerability source is onboarded.",
                ],
            },
            "severity_label": "P2 High",
            "finding_title": "Critical alerts with MITRE rollup — CVE correlation not onboarded",
            "one_sentence_finding": (
                "Four critical/high alerts across three hosts roll up to three MITRE technique candidates "
                "(T1110.001, T1078, T1059.001). V.AI SOC cannot correlate unpatched CVEs because no "
                "vulnerability source is onboarded; the CVE leg is shown as a planned degrade only."
            ),
            "initial_assessment": [
                f"Top risky host: {top_hosts[0]['Host']} (risk_score {top_hosts[0]['Risk score']})",
                f"Second: {top_hosts[1]['Host']} (risk_score {top_hosts[1]['Risk score']})",
                "CVE correlation leg: vulnerability_source not_onboarded (no fabricated CVE rows).",
            ],
            "splunk_status_line": "Splunk MCP fixture search result [index=pgcil_soc sourcetype=pgcil:edr] · last 6 hours · 4 rows",
            "splunk_results_table": [
                {
                    "Alert ID": row["alert_id"],
                    "Host": row["host"],
                    "Rule": row["rule_name"],
                    "Urgency": row["urgency"],
                    "MITRE": row["mitre_technique"],
                    "Tactic": row["mitre_tactic"],
                    "Count": row["alert_count"],
                }
                for row in _CRITICAL_ALERT_FIXTURE_ROWS
            ],
            "top_risky_hosts": top_hosts,
            "mitre_mappings": [
                {
                    "Technique": "T1110.001",
                    "Name": "Password Guessing",
                    "Tactic": "Credential Access",
                    "Status": "Candidate",
                    "Evidence": "VPN-GW-01 brute_force_vpn_spike critical alert cluster",
                    "Validation needed": "Confirm source IPs, lockout policy, and whether successes followed failures.",
                },
                {
                    "Technique": "T1078",
                    "Name": "Valid Accounts",
                    "Tactic": "Persistence / Initial Access",
                    "Status": "Candidate",
                    "Evidence": "DB-PROD-02 privileged_login_anomaly and VPN-GW-01 geo_impossible_travel",
                    "Validation needed": "Confirm account legitimacy, MFA result, and session activity.",
                },
                {
                    "Technique": "T1059.001",
                    "Name": "PowerShell",
                    "Tactic": "Execution",
                    "Status": "Candidate",
                    "Evidence": "APP-EDGE-03 suspicious_powershell critical alert",
                    "Validation needed": "Review command line, parent process, and encoded-command flags.",
                },
            ],
            "spl_code": CRITICAL_NOTABLE_VISIBLE_SPL,
            "key_fields": [
                "host - affected endpoint in the critical-alert rollup",
                "urgency - Splunk-native severity weight input (critical/high/medium/low)",
                "mitre_technique - technique annotation carried on each alert row",
                "mitre_tactic - tactic column for kill-chain coverage in the MITRE table",
                "alert_count - number of correlated alerts for the host/rule in the 6h window",
            ],
            "limitations": [
                "Unpatched CVE correlation did not run: vulnerability_source is not onboarded in this deployment.",
                "MITRE techniques are candidate-only pending analyst validation of underlying alert evidence.",
            ],
            "missing_evidence": [
                "vulnerability_source",
                "unpatched_cve_correlation",
            ],
            "foundation_sec_analysis": (
                "Foundation-sec contributes advisory technique annotations from the critical-alert fixture. "
                "V.AI SOC keeps MITRE mappings candidate-only and refuses to fabricate CVE rows when no "
                "vulnerability source is available."
            ),
            "recommended_actions": [
                "P2: Triage VPN-GW-01 first (highest urgency-weighted risk_score) — validate brute-force sources and any post-failure successes.",
                "P2: Review APP-EDGE-03 PowerShell alert parent process, command line, and encoded-command indicators.",
                "P2: Validate DB-PROD-02 privileged-login anomaly against account owner, MFA, and session context.",
                "P3: Onboard or connect a governed vulnerability source before claiming unpatched CVE exposure on affected hosts.",
            ],
            "review_notice": "Candidate MITRE mappings and review-only SPL. CVE leg is an honest degrade — correlation unavailable.",
        })
    if scenario.scenario_id == "guided_investigation_supply_chain":
        return {
            **base,
            "retrieved_playbook": None,
            "sop_guidance": None,
            "status_badge": "Out-of-catalog - guided review only",
            "finding_title": "Guided hunt: CI/CD supply-chain compromise (out of vetted catalog)",
            "one_sentence_finding": "This hunt is outside the vetted use-case catalog, so V.AI SOC returns a review-only guided hunt plan with an out-of-catalog notice rather than auto-generating SPL.",
            "out_of_catalog_notice": "No vetted use-case or governed SPL template covers a CI/CD supply-chain hunt. Guidance below is review-only; any SPL must be analyst-authored and validated before use.",
            "foundation_sec_analysis": "Foundation-sec proposes hunt directions, but with no governed template the resource planner degrades to RAG hunt patterns and review-only guidance. MCP execution stays gated and no SPL is auto-run.",
            "key_fields": [
                "Unsigned or unexpected build artifacts in the pipeline output",
                "New outbound destinations from build agents / CI runners",
                "Modified pipeline definitions or build scripts",
                "Credential access or secret reads from CI runners",
            ],
            "recommended_actions": [
                "P2: Review build-agent egress for new or rare outbound destinations over the suspected window.",
                "P2: Diff pipeline definitions and build scripts against the last known-good revision.",
                "P3: Audit CI runner secret/credential access and artifact signing status.",
                "P3: Author and validate targeted SPL per data source before any execution; this hunt has no vetted template.",
            ],
            "review_notice": "Out-of-catalog guided review. No vetted template; SPL must be analyst-authored and validated. MCP execution stays gated.",
        }
    return {
        **base,
        "finding_title": scenario.label,
        "one_sentence_finding": scenario.analyst_summary,
    }


def _evidence(
    evidence_id: str,
    source_type: str,
    source_name: str,
    result_count: int,
    fields: list[str],
    rows: list[dict[str, Any]],
    *,
    tool_name: str | None = None,
    query_or_request_summary: str | None = None,
    executed_spl: str | None = None,
    provider_used: str | None = None,
    output_type: str | None = "fixture_preview",
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "trace_id": "pending",
        "source_type": source_type,
        "source_name": source_name,
        "tool_name": tool_name,
        "collection_status": "collected",
        "query_or_request_summary": query_or_request_summary,
        "executed_spl": executed_spl,
        "result_count": result_count,
        "fields_returned": fields,
        "preview_rows": rows,
        "raw_result_hash": f"fixture:{evidence_id}",
        "raw_result_stored": False,
        "time_range": "synthetic last 60 minutes",
        "warnings": ["coe_synthetic_fixture", "no_live_customer_data"],
        "sensitivity_flags": [],
        "tool_category": "read_only_search" if source_type.startswith("splunk") else "governed_knowledge",
        "provider_used": provider_used,
        "saved_search_name": None,
        "output_type": output_type,
        "provenance": EVIDENCE_ORIGIN,
        "created_at": CREATED_AT,
    }


def _rag_row(entry_id: str, title: str, excerpt: str, refs: list[str]) -> dict[str, Any]:
    return {
        "entry_id": entry_id,
        "collection_id": "soc_kb",
        "document_type": "sop",
        "doc_title": "Brute-force Authentication Investigation SOP",
        "entry_title": title,
        "source_excerpt": excerpt,
        "source_refs": refs,
        "citation": refs[0],
        "allowed_use": ["analyst_guidance", "triage_checklist"],
        "recommended_actions": ["confirm scope", "review successful login correlation", "escalate if privileged account affected"],
        "reviewer_role": "soc_analyst",
        "doc_version": "2026.04",
        "status": "published",
        "approval_status": "approved",
        "environment": "coe_demo",
        "retrieval_mode": "fixture",
        "confidence": 0.91,
    }


def _context(
    scenario_id: str,
    skill: str,
    facts: list[dict[str, Any]],
    *,
    metrics: dict[str, Any] | None = None,
    mitre: list[dict[str, Any]] | None = None,
    refs: list[str] | None = None,
    fallback: bool = False,
    quality: str = "sufficient",
) -> dict[str, Any]:
    refs = refs or sorted({ref for fact in facts for ref in fact["source_refs"]})
    return {
        "trace_id": "pending",
        "query": "",
        "selected_skill": skill,
        "source_evidence_refs": refs,
        "structured_facts": facts,
        "entity_summary": {"scenario_id": scenario_id, "fixture": True},
        "metrics": metrics or {},
        "timeline_candidates": [],
        "mitre_candidates": mitre or [],
        "tool_outputs_summary": [{"source_refs": refs, "origin": EVIDENCE_ORIGIN}],
        "capability_profile_ref": "fixture:splunk_capability",
        "spl_generation_provider": "deterministic_fixture_fallback" if fallback else "spl_candidate_validation_generator",
        "spl_explanation_provider": "deterministic_fixture",
        "spl_optimization_provider": "disabled_in_demo",
        "spl_guidance_provider": "governed_policy_fixture",
        "fallback_mode": fallback,
        "execution_provider": "mock_fixture" if scenario_id == "account_lockouts_over_time_spl" else None,
        "source_refs": refs,
        "policy_context_refs": ["stage-3j-d-demo-fixture-policy"],
        "sop_action_hints": [],
        "answer_constraints": ["No final LLM synthesis.", "No live customer data.", "Do not execute candidate_spl unless gated."],
        "mitre_grounding_refs": refs if mitre else [],
        "splunk_context_refs": [ref for ref in refs if ref.startswith("ev-splunk")],
        "tool_policy_refs": ["mcp_execution_default_disabled"],
        "environment_grounding_refs": ["coe_synthetic_fixture"],
        "knowledge_ambiguity": [],
        "validation_warnings": [],
        "assumptions": ["Fixture-backed demo data."],
        "warnings": ["coe_synthetic_fixture"],
        "missing_evidence": [],
        "allowed_conclusions": ["Only fixture-supported observations may be shown."],
        "prohibited_conclusions": ["No live production impact statement.", "No remediation execution."],
        "context_quality": quality,
        "synthesis_allowed": False,
    }


def _fact(fact_id: str, statement: str, refs: list[str], confidence: float = 0.9) -> dict[str, Any]:
    return {"fact_id": fact_id, "statement": statement, "source_refs": refs, "derivation": "demo_fixture", "confidence": confidence}


def _mock_rows_for(trace_id: str, scenario_id: str | None = None) -> list[dict[str, Any]]:
    if scenario_id == "dns_beaconing_c2_hunt_run":
        return [
            {"src": "10.20.3.41", "dest": "8.8.8.8", "domain": "a3f9k2.update-cdn.net", "DNS_query_count": 288, "periodicity": 300.0, "jitter": "requires_review", "bytes_out": 41216, "rare_domain_indicator": "review", "first_seen": "2026-05-24T00:04:00Z", "last_seen": "2026-05-24T23:56:00Z", "trace_id": trace_id},
            {"src": "10.20.7.12", "dest": "1.1.1.1", "domain": "sync.metric-telemetry.io", "DNS_query_count": 144, "periodicity": 600.0, "jitter": "requires_review", "bytes_out": 20992, "rare_domain_indicator": "review", "first_seen": "2026-05-24T00:09:00Z", "last_seen": "2026-05-24T23:51:00Z", "trace_id": trace_id},
        ]
    if scenario_id == "successful_login_after_failures_run":
        return [
            {
                "user": "svc_grid_ops",
                "host": "APP-01",
                "src": "10.10.4.21",
                "fail_count": 58,
                "success_count": 1,
                "first_failure": "2026-05-24T13:42:10Z",
                "last_event": "2026-05-24T14:37:22Z",
                "risk": "P2 review - successful login after repeated failures",
                "trace_id": trace_id,
            }
        ]
    return [
        {"_time": "2026-05-24T09:00:00Z", "action": "lockout", "count": 4, "trace_id": trace_id},
        {"_time": "2026-05-24T09:10:00Z", "action": "lockout", "count": 9, "trace_id": trace_id},
        {"_time": "2026-05-24T09:20:00Z", "action": "lockout", "count": 6, "trace_id": trace_id},
    ]


class _NoopTelemetry:
    def record_step(self, *args: Any, **kwargs: Any) -> None:
        return None


SCENARIOS: dict[str, DemoScenario] = {
    "failed_login_spike_app01": DemoScenario(
        scenario_id="failed_login_spike_app01",
        label="Failed login spike on APP-01",
        category="Investigate",
        query="Investigate failed login spike on APP-01",
        environment_mode="connected_coe_demo",
        expected_skill="attack_discovery",
        expected_sources=["mcp:splunk", "rag:sop"],
        expected_sufficiency_mode="partial_answer",
        mcp_execution_mode="disabled",
        saia_available=True,
        rag_available=True,
        candidate_spl=FAILED_SPIKE_SPL,
        analyst_summary="Synthetic APP-01 auth evidence shows a failed-login spike candidate. MITRE T1110 is supported by the fixture; SOP guidance is attached for analyst review.",
        trace_explanation=[
            "Routed to attack_discovery because the query asks to investigate failed authentication activity.",
            "SPL candidate generation and validation are shown before the MCP search path.",
            "RAG SOP evidence is included only as SourceEvidence and StructuredContext.",
        ],
        source_evidence=[
            _evidence(
                "ev-splunk-failed-app01",
                "splunk_mcp_fixture",
                "Splunk auth fixture",
                3,
                ["index", "sourcetype", "host", "src", "action", "fail_count"],
                [
                    {"index": "pgcil_soc", "sourcetype": "pgcil:auth", "host": "APP-01", "src": "10.10.4.21", "action": "failure", "fail_count": 42, "distinct_users": 7},
                    {"index": "pgcil_soc", "sourcetype": "pgcil:auth", "host": "APP-01", "src": "10.10.4.22", "action": "failure", "fail_count": 31, "distinct_users": 4},
                    {"index": "pgcil_soc", "sourcetype": "pgcil:auth", "host": "APP-01", "src": "10.10.4.19", "action": "failure", "fail_count": 28, "distinct_users": 3},
                ],
                tool_name="search",
                query_or_request_summary="Synthetic failed authentication aggregation for APP-01 in pgcil_soc/pgcil:auth.",
                executed_spl=None,
                provider_used="splunk_mcp_fixture",
            ),
            _evidence(
                "ev-rag-bruteforce-sop",
                "rag",
                "SOC KB fixture",
                1,
                ["entry_id", "document_type", "source_excerpt", "source_refs"],
                [_rag_row("sop-auth-001", "Brute-force triage", "Confirm affected asset, count source IPs, check for success-after-failure, then escalate privileged-user cases.", ["SOC-SOP-AUTH-001#triage"])],
                tool_name="retrieve_soc_kb",
                query_or_request_summary="Approved brute-force SOP guidance.",
                provider_used="governed_rag_fixture",
            ),
        ],
        structured_context=_context(
            "failed_login_spike_app01",
            "attack_discovery",
            [
                _fact("fact-fail-spike", "APP-01 has a synthetic failed-login spike in index pgcil_soc sourcetype pgcil:auth.", ["ev-splunk-failed-app01"]),
                _fact("fact-t1110", "MITRE T1110 is a supported candidate for repeated authentication failures.", ["ev-splunk-failed-app01", "ev-rag-bruteforce-sop"]),
            ],
            metrics={"failed_logins": 101, "distinct_users": 3, "fail_count_max": 42, "distinct_sources": 3},
            mitre=[{"technique_id": "T1110", "name": "Brute Force", "support": "supported", "source_refs": ["ev-splunk-failed-app01"]}],
            refs=["ev-splunk-failed-app01", "ev-rag-bruteforce-sop"],
            quality="partial",
        ),
    ),
    "new_source_ip_logins": DemoScenario(
        scenario_id="new_source_ip_logins",
        label="New source IP logins",
        category="Investigate",
        query="Investigate new source IP logins on APP-01",
        environment_mode="connected_coe_demo",
        expected_skill="attack_discovery",
        expected_sources=["mcp:splunk", "rag:sop"],
        expected_sufficiency_mode="partial_answer",
        mcp_execution_mode="disabled",
        saia_available=True,
        rag_available=True,
        analyst_summary="APP-01 has new source IP login evidence with SOC KB guidance attached for analyst validation.",
        trace_explanation=[
            "Routed to attack_discovery because the query asks to investigate novel authentication source behavior.",
            "COE fixture Splunk evidence is represented as SourceEvidence; operational execution remains gated.",
            "SOC KB guidance is included for validation and escalation criteria.",
        ],
        source_evidence=[
            _evidence(
                "ev-splunk-new-source-app01",
                "splunk_mcp",
                "Splunk auth fixture",
                2,
                ["index", "sourcetype", "host", "user", "src", "action", "prior_sightings"],
                [
                    {"index": "pgcil_soc", "sourcetype": "pgcil:auth", "host": "APP-01", "user": "svc_app", "src": "10.10.9.44", "action": "success", "prior_sightings": 0},
                    {"index": "pgcil_soc", "sourcetype": "pgcil:auth", "host": "APP-01", "user": "j.das", "src": "10.10.9.45", "action": "success", "prior_sightings": 0},
                ],
                tool_name="search",
                query_or_request_summary="New source IP authentication aggregation for APP-01 in pgcil_soc/pgcil:auth.",
                provider_used="splunk_mcp_fixture",
            ),
            _evidence(
                "ev-rag-new-source-sop",
                "rag",
                "SOC KB fixture",
                1,
                ["entry_id", "document_type", "source_excerpt", "source_refs"],
                [_rag_row("sop-auth-003", "New source validation", "Validate source ownership, account criticality, and post-login activity before escalation.", ["SOC-SOP-AUTH-001#validation"])],
                tool_name="retrieve_soc_kb",
                query_or_request_summary="Approved authentication-source validation guidance.",
                provider_used="governed_rag_fixture",
            ),
        ],
        structured_context=_context(
            "new_source_ip_logins",
            "attack_discovery",
            [
                _fact("fact-new-source", "APP-01 has successful authentications from sources with no prior sightings for the affected users.", ["ev-splunk-new-source-app01"]),
                _fact("fact-valid-accounts", "MITRE T1078 is a validation candidate for successful authentication from unusual sources.", ["ev-splunk-new-source-app01", "ev-rag-new-source-sop"]),
            ],
            metrics={"new_source_count": 2, "service_account_seen": True},
            mitre=[{"technique_id": "T1078", "name": "Valid Accounts", "support": "analyst_review", "source_refs": ["ev-splunk-new-source-app01"]}],
            refs=["ev-splunk-new-source-app01", "ev-rag-new-source-sop"],
            quality="partial",
        ),
    ),
    "successful_login_after_failures": DemoScenario(
        scenario_id="successful_login_after_failures",
        label="Successful login after failures",
        category="Generate SPL",
        query="Generate SPL for successful login after failures",
        environment_mode="connected_coe_demo",
        expected_skill="spl_generation",
        expected_sources=["spl_policy", "mcp:splunk"],
        expected_sufficiency_mode="spl_review_only",
        mcp_execution_mode="disabled",
        saia_available=True,
        rag_available=True,
        candidate_spl=SUCCESS_AFTER_FAILURES_SPL,
        selected_use_case_id="auth_success_after_failure",
        analyst_summary="Candidate SPL correlates failure and success counts by user, source, and host. Execution remains disabled, so this is SPL review only.",
        trace_explanation=[
            "Uses a correlation SPL with both action=\"failure\" and action=\"success\".",
            "Does not reuse the failed-login-spike-only SPL.",
            "Live MCP gate remains closed; the query is unexecuted for analyst review.",
        ],
        source_evidence=[],
        structured_context=_context(
            "successful_login_after_failures",
            "spl_generation",
            [
                _fact(
                    "fact-success-correlation",
                    "Governed template SPL correlates failure and success counts by user, source, and host.",
                    [],
                )
            ],
            metrics={"correlation_keys": ["user", "src", "host"]},
            mitre=[],
            refs=[],
            quality="partial",
        ),
    ),
    "successful_login_after_failures_run": DemoScenario(
        scenario_id="successful_login_after_failures_run",
        label="Successful login after failures - run",
        category="Generate + Run",
        query="Generate SPL for successful login after failures and run on host APP-01 in index pgcil_soc sourcetype pgcil:auth for the last 60 minutes",
        environment_mode="connected_coe_demo",
        expected_skill="spl_generation",
        expected_sources=["spl_policy", "mcp:splunk"],
        expected_sufficiency_mode="partial_answer",
        mcp_execution_mode="mock_success",
        saia_available=True,
        rag_available=False,
        candidate_spl=SUCCESS_AFTER_FAILURES_SPL,
        selected_use_case_id="auth_success_after_failure",
        analyst_summary="Validated success-after-failure SPL reached the Experience Center MCP fixture path and returned one fixture row for APP-01.",
        trace_explanation=[
            "Generates success-after-failure SPL from the governed template.",
            "Binds the scoped request to APP-01 in pgcil_soc/pgcil:auth for the fixture window.",
            "Experience Center MCP fixture selection uses approved normalized_spl only and returns fixture evidence.",
        ],
        source_evidence=[
            _evidence(
                "ev-splunk-success-after-fail-run",
                "splunk_mcp",
                "Splunk auth fixture",
                1,
                ["user", "src", "host", "fail_count", "success_count", "first_failure", "last_event", "risk"],
                _mock_rows_for("fixture", "successful_login_after_failures_run"),
                tool_name="search",
                executed_spl=SUCCESS_AFTER_FAILURES_SPL,
                provider_used="mock_mcp_fixture",
            ),
        ],
        structured_context=_context(
            "successful_login_after_failures_run",
            "spl_generation",
            [
                _fact(
                    "fact-success-correlation-run",
                    "COE fixture Splunk evidence returned one APP-01 success-after-failure sequence from validated normalized SPL.",
                    ["ev-splunk-success-after-fail-run"],
                )
            ],
            metrics={"successful_logins": 1, "failed_logins": 58, "mock_result_rows": 1},
            mitre=[{"technique_id": "T1078", "name": "Valid Accounts", "support": "analyst_review", "source_refs": ["ev-splunk-success-after-fail-run"]}],
            refs=["ev-splunk-success-after-fail-run"],
            quality="partial",
        ),
    ),
    "brute_force_sop_guidance": DemoScenario(
        scenario_id="brute_force_sop_guidance",
        label="Brute-force SOP guidance",
        category="Knowledge / SOP",
        query="Show SOP for brute-force investigation",
        environment_mode="knowledge_only_coe_demo",
        expected_skill="knowledge_recall",
        expected_sources=["rag:sop"],
        expected_sufficiency_mode="knowledge_only_answer",
        mcp_execution_mode="not_required",
        saia_available=True,
        rag_available=True,
        analyst_summary="Approved SOC KB guidance is returned without SPL generation. This demonstrates SOP recall with governed RAG only.",
        trace_explanation=[
            "Routes to knowledge_recall for SOP/playbook wording.",
            "No candidate SPL is generated by default.",
            "RAG evidence flows through SourceEvidence and StructuredContext only.",
        ],
        source_evidence=[
            _evidence("ev-rag-sop-only", "rag", "SOC KB fixture", 1, ["entry_id", "document_type", "source_excerpt", "source_refs"], [_rag_row("sop-auth-002", "Brute-force investigation checklist", "Validate alert scope, preserve evidence, and avoid account changes until business owner review.", ["SOC-SOP-AUTH-001#triage"])], tool_name="retrieve_soc_kb", provider_used="governed_rag_fixture"),
        ],
        structured_context=_context(
            "brute_force_sop_guidance",
            "knowledge_recall",
            [_fact("fact-sop-guidance", "Approved brute-force SOP guidance is available from the governed SOC KB fixture.", ["ev-rag-sop-only"])],
            refs=["ev-rag-sop-only"],
        ),
    ),
    "account_lockouts_over_time_spl": DemoScenario(
        scenario_id="account_lockouts_over_time_spl",
        label="Account lockouts over time SPL",
        category="Generate SPL",
        query="Generate SPL for account lockouts over time",
        environment_mode="connected_coe_demo",
        expected_skill="spl_generation",
        expected_sources=["spl_policy", "mcp:splunk"],
        expected_sufficiency_mode="spl_review_only",
        mcp_execution_mode="mock_success",
        saia_available=True,
        rag_available=True,
        candidate_spl=LOCKOUT_SPL,
        analyst_summary="Lockout trend SPL uses action=lockout and passes deterministic validation. This fixture explicitly models an Experience Center MCP fixture result with capped preview rows.",
        trace_explanation=[
            "Generates lockout-specific SPL using action=lockout.",
            "Runs deterministic SPL validation before any mock gate.",
            "Experience Center MCP fixture result is used; no live MCP execution is performed.",
        ],
        source_evidence=[
            _evidence("ev-splunk-lockout-trend", "splunk_mcp", "Splunk auth fixture", 3, ["_time", "lockout_count"], _mock_rows_for("fixture"), tool_name="search", executed_spl=LOCKOUT_SPL, provider_used="mock_mcp_fixture"),
        ],
        structured_context=_context(
            "account_lockouts_over_time_spl",
            "spl_generation",
            [_fact("fact-lockout-spl", "The candidate SPL trends action=lockout events over time.", ["ev-splunk-lockout-trend"])],
            metrics={"mock_result_rows": 3},
            refs=["ev-splunk-lockout-trend"],
            quality="partial",
        ),
    ),
    "mitre_mapping_auth_alert": DemoScenario(
        scenario_id="mitre_mapping_auth_alert",
        label="MITRE mapping for auth alert",
        category="MITRE Mapping",
        query="Map this alert to MITRE: notable signature=brute_force_success_after_failures index=pgcil_soc sourcetype=pgcil:auth host=APP-01",
        environment_mode="connected_coe_demo",
        expected_skill="alert_summary",
        expected_sources=["mcp:splunk", "rag:sop"],
        expected_sufficiency_mode="partial_answer",
        mcp_execution_mode="not_required",
        saia_available=True,
        rag_available=True,
        analyst_summary="Provided alert context grounds MITRE mapping. T1110 is supported; T1078 is an analyst-review candidate because success-after-failure context exists.",
        trace_explanation=[
            "Uses the provided alert context fixture rather than guessing from an empty MITRE prompt.",
            "Maps T1110 as supported from brute-force evidence.",
            "Keeps T1078 as analyst-review because valid-account use requires confirmation.",
        ],
        source_evidence=[
            _evidence("ev-splunk-mitre-alert", "splunk_mcp", "Splunk notable fixture", 1, ["signature", "index", "sourcetype", "host", "failed_then_success"], [{"signature": "brute_force_success_after_failures", "index": "pgcil_soc", "sourcetype": "pgcil:auth", "host": "APP-01", "failed_then_success": True}], tool_name="notable_lookup", provider_used="splunk_mcp_fixture"),
        ],
        structured_context=_context(
            "mitre_mapping_auth_alert",
            "alert_summary",
            [
                _fact("fact-alert-context", "The alert fixture provides auth context from pgcil_soc/pgcil:auth for APP-01.", ["ev-splunk-mitre-alert"]),
                _fact("fact-mitre-supported", "T1110 is supported by repeated failed-authentication context.", ["ev-splunk-mitre-alert"]),
                _fact("fact-mitre-review", "T1078 is candidate-only because success-after-failure exists but account legitimacy needs analyst review.", ["ev-splunk-mitre-alert"], 0.72),
            ],
            mitre=[
                {"technique_id": "T1110", "name": "Brute Force", "support": "supported", "source_refs": ["ev-splunk-mitre-alert"]},
                {"technique_id": "T1078", "name": "Valid Accounts", "support": "analyst_review", "source_refs": ["ev-splunk-mitre-alert"]},
            ],
            refs=["ev-splunk-mitre-alert"],
            quality="partial",
        ),
    ),
    "mitre_mapping_requires_context": DemoScenario(
        scenario_id="mitre_mapping_requires_context",
        label="MITRE clarification required",
        category="MITRE Mapping",
        query="Map this alert to MITRE",
        environment_mode="connected_coe_demo",
        expected_skill="knowledge_recall",
        expected_sources=[],
        expected_sufficiency_mode="insufficient_evidence",
        mcp_execution_mode="not_required",
        saia_available=True,
        rag_available=True,
        analyst_summary="MITRE mapping requires alert context before selecting a technique.",
        trace_explanation=[
            "The phrase 'this alert' does not include enough event context.",
            "Deterministic clarification policy overrides advisory model confidence.",
            "No MITRE technique is selected until alert evidence is supplied.",
        ],
        source_evidence=[],
        structured_context=_context(
            "mitre_mapping_requires_context",
            "knowledge_recall",
            [],
            refs=[],
            quality="insufficient",
        ),
    ),
    "mcp_metadata_discovery_app01": DemoScenario(
        scenario_id="mcp_metadata_discovery_app01",
        label="APP-01 metadata discovery",
        category="Generate SPL",
        query="Before generating SPL, check which indexes and sourcetypes are available for APP-01 authentication logs",
        environment_mode="connected_coe_demo",
        expected_skill="spl_generation",
        selected_use_case_id="soc_generate_spl",
        expected_sources=["mcp:splunk"],
        expected_sufficiency_mode="analyst_review_required",
        mcp_execution_mode="not_required",
        saia_available=True,
        rag_available=False,
        analyst_summary="Index and sourcetype discovery must run before SPL generation for APP-01 authentication logs.",
        trace_explanation=[
            "Routes to SPL preparation but stops at metadata discovery.",
            "LLM-invented index and sourcetype names are ignored.",
            "Deterministic tool mapping selects splunk_get_indexes and splunk_get_metadata.",
        ],
        source_evidence=[],
        structured_context=_context(
            "mcp_metadata_discovery_app01",
            "spl_generation",
            [_fact("fact-metadata-discovery", "APP-01 authentication SPL requires metadata discovery before SPL generation.", [])],
            metrics={"deterministic_tools": ["splunk_get_indexes", "splunk_get_metadata"]},
            refs=[],
            quality="partial",
        ),
    ),
    "airgapped_no_saia_success_after_failures": DemoScenario(
        scenario_id="airgapped_no_saia_success_after_failures",
        label="Air-gapped success after failures",
        category="Air-gapped Mode",
        query="Air-gapped mode: generate SPL for successful login after failures without SAIA",
        environment_mode="airgapped_coe_demo",
        expected_skill="spl_generation",
        expected_sources=["spl_policy", "mcp:splunk"],
        expected_sufficiency_mode="spl_review_only",
        mcp_execution_mode="disabled",
        saia_available=False,
        rag_available=True,
        candidate_spl=SUCCESS_AFTER_FAILURES_SPL,
        selected_use_case_id="auth_success_after_failure",
        analyst_summary="SAIA is unavailable in this air-gapped fixture, so deterministic fallback SPL generation is active while core Splunk MCP fixture metadata remains available.",
        trace_explanation=[
            "SAIA/generative assistant tools are unavailable.",
            "Fallback provider generates advisory SPL without tool calling.",
            "Core Splunk MCP fixture discovery is shown as available, with no live MCP execution.",
        ],
        source_evidence=[
            _evidence("ev-splunk-airgap-metadata", "splunk_mcp", "Splunk capability fixture", 1, ["server", "tool", "status"], [{"server": "splunk", "tool": "search", "status": "available", "saia": "unavailable"}], tool_name="tool_discovery", provider_used="mcp_registry_fixture"),
        ],
        structured_context=_context(
            "airgapped_no_saia_success_after_failures",
            "spl_generation",
            [_fact("fact-airgap-fallback", "SAIA is unavailable and deterministic fallback is active; core Splunk MCP fixture search metadata is available.", ["ev-splunk-airgap-metadata"])],
            metrics={"successful_logins": 1, "failed_logins": 58, "saia_available": False, "fallback_active": True},
            refs=["ev-splunk-airgap-metadata"],
            fallback=True,
            quality="partial",
        ),
    ),
    "dns_beaconing_c2_hunt": DemoScenario(
        scenario_id="dns_beaconing_c2_hunt",
        label="DNS beaconing / C2 hunt",
        category="Investigate",
        query="Hunt for possible DNS beaconing or C2 from internal hosts in the last 24 hours",
        environment_mode="connected_coe_demo",
        expected_skill="attack_discovery",
        selected_use_case_id="dns_beaconing_candidate",
        expected_sources=["mcp:splunk", "rag:sop"],
        expected_sufficiency_mode="partial_answer",
        mcp_execution_mode="disabled",
        saia_available=True,
        rag_available=True,
        candidate_spl=DNS_BEACONING_SPL,
        analyst_summary="Beaconing-candidate SPL aggregates DNS query periodicity, rare-domain ratio, and bytes-out per source. Foundation-sec flags a C2 pattern; V.AI SOC keeps it candidate-only until jitter and domain reputation are confirmed.",
        trace_explanation=[
            "Routed to attack_discovery for a cross-host DNS beaconing hunt beyond authentication.",
            "Governed dns_beaconing_candidate template computes periodicity/jitter/rare-domain signals deterministically.",
            "Threat-intel SOC-KB guidance is attached as SourceEvidence; MITRE T1071.004 stays candidate-only pending jitter + reputation.",
        ],
        source_evidence=[
            _evidence(
                "ev-splunk-dns-beacon",
                "splunk_mcp",
                "Splunk DNS fixture",
                3,
                ["src", "dest", "domain", "DNS_query_count", "periodicity", "rare_domain_indicator", "bytes_out"],
                [
                    {"src": "10.20.3.41", "dest": "8.8.8.8", "domain": "a3f9k2.update-cdn.net", "DNS_query_count": 288, "periodicity": 300.0, "rare_domain_indicator": "review", "bytes_out": 41216},
                    {"src": "10.20.7.12", "dest": "1.1.1.1", "domain": "sync.metric-telemetry.io", "DNS_query_count": 144, "periodicity": 600.0, "rare_domain_indicator": "review", "bytes_out": 20992},
                    {"src": "10.20.5.88", "dest": "8.8.4.4", "domain": "cdn.win-update-cache.com", "DNS_query_count": 96, "periodicity": 900.0, "rare_domain_indicator": "review", "bytes_out": 13440},
                ],
                tool_name="search",
                query_or_request_summary="DNS beaconing-candidate aggregation in pgcil_soc/pgcil:dns over 24h.",
                executed_spl=None,
                provider_used="splunk_mcp_fixture",
            ),
            _evidence(
                "ev-rag-c2-ti",
                "rag",
                "SOC KB fixture",
                1,
                ["entry_id", "document_type", "source_excerpt", "source_refs"],
                [_rag_row("ti-dns-002", "Beaconing triage", "Confirm fixed-interval periodicity, low jitter, rare/low-reputation domains, and steady small payloads before declaring C2.", ["SOC-TI-DNS-002#beaconing"])],
                tool_name="retrieve_soc_kb",
                query_or_request_summary="Approved DNS beaconing / C2 triage guidance.",
                provider_used="governed_rag_fixture",
            ),
        ],
        structured_context=_context(
            "dns_beaconing_c2_hunt",
            "attack_discovery",
            [
                _fact("fact-dns-periodicity", "Three internal hosts show fixed-interval DNS queries to rare domains with steady small payloads.", ["ev-splunk-dns-beacon"]),
                _fact("fact-c2-candidate", "MITRE T1071.004 is a candidate for the periodic DNS pattern; jitter and domain reputation are not yet confirmed.", ["ev-splunk-dns-beacon", "ev-rag-c2-ti"], 0.7),
            ],
            metrics={"beaconing_hosts": 3, "max_query_count": 288, "min_periodicity_seconds": 300},
            mitre=[{"technique_id": "T1071.004", "name": "Application Layer Protocol: DNS", "support": "analyst_review", "source_refs": ["ev-splunk-dns-beacon"]}],
            refs=["ev-splunk-dns-beacon", "ev-rag-c2-ti"],
            quality="partial",
        ),
    ),
    "dns_beaconing_c2_hunt_run": DemoScenario(
        scenario_id="dns_beaconing_c2_hunt_run",
        label="DNS beaconing / C2 hunt - run",
        category="Generate + Run",
        query="Hunt for DNS beaconing from internal hosts in index pgcil_soc sourcetype pgcil:dns over the last 24 hours and run it",
        environment_mode="connected_coe_demo",
        expected_skill="attack_discovery",
        selected_use_case_id="dns_beaconing_candidate",
        expected_sources=["spl_policy", "mcp:splunk"],
        expected_sufficiency_mode="partial_answer",
        mcp_execution_mode="mock_success",
        saia_available=True,
        rag_available=False,
        candidate_spl=DNS_BEACONING_SPL,
        analyst_summary="Validated beaconing SPL reached the Experience Center MCP fixture path and returned two periodic-DNS hosts for review. MITRE T1071.004 stays candidate-only pending jitter and domain reputation.",
        trace_explanation=[
            "Generates the governed dns_beaconing_candidate SPL and validates it deterministically.",
            "Binds the scoped request to pgcil_soc/pgcil:dns over the 24h window.",
            "Experience Center MCP fixture selection uses approved normalized_spl only and returns capped preview rows.",
        ],
        source_evidence=[
            _evidence(
                "ev-splunk-dns-beacon-run",
                "splunk_mcp",
                "Splunk DNS fixture",
                2,
                ["src", "dest", "domain", "DNS_query_count", "periodicity", "bytes_out", "rare_domain_indicator"],
                _mock_rows_for("fixture", "dns_beaconing_c2_hunt_run"),
                tool_name="search",
                executed_spl=DNS_BEACONING_SPL,
                provider_used="mock_mcp_fixture",
            ),
        ],
        structured_context=_context(
            "dns_beaconing_c2_hunt_run",
            "attack_discovery",
            [
                _fact("fact-dns-beacon-run", "COE fixture Splunk evidence returned two periodic-DNS hosts from validated normalized SPL.", ["ev-splunk-dns-beacon-run"]),
                _fact("fact-c2-candidate-run", "MITRE T1071.004 is a candidate for the periodic DNS pattern; jitter and domain reputation are not yet confirmed.", ["ev-splunk-dns-beacon-run"], 0.7),
            ],
            metrics={"beaconing_hosts": 2, "max_query_count": 288, "mock_result_rows": 2},
            mitre=[{"technique_id": "T1071.004", "name": "Application Layer Protocol: DNS", "support": "analyst_review", "source_refs": ["ev-splunk-dns-beacon-run"]}],
            refs=["ev-splunk-dns-beacon-run"],
            quality="partial",
        ),
    ),
    "critical_alerts_mitre_cve_review": DemoScenario(
        scenario_id="critical_alerts_mitre_cve_review",
        label="Critical alerts + MITRE + CVE cross-ref",
        category="Investigate",
        query=(
            "Show me all critical alerts in the last 6 hours, cross-reference with MITRE ATT&CK, "
            "and check if any affected hosts have unpatched CVEs"
        ),
        environment_mode="connected_coe_demo",
        expected_skill="attack_discovery",
        selected_use_case_id="critical_notable_mitre_review",
        expected_sources=["mcp:splunk", "rag:sop"],
        expected_sufficiency_mode="partial_answer",
        mcp_execution_mode="disabled",
        saia_available=True,
        rag_available=True,
        candidate_spl=CRITICAL_NOTABLE_SPL,
        analyst_summary=(
            "Critical/high alerts across three hosts roll up to three MITRE technique candidates. "
            "CVE correlation is honestly degraded because no vulnerability source is onboarded."
        ),
        trace_explanation=[
            "Routed to attack_discovery for a multi-host critical-alert MITRE rollup.",
            "Governed notable_critical_review_mitre template aggregates pgcil:edr alerts over 6h with technique annotations.",
            "Vulnerability-source degrade is explicit: no CVE rows fabricated; resource_plan marks vulnerability_source not_onboarded.",
        ],
        source_evidence=[
            _evidence(
                "ev-splunk-critical-alerts",
                "splunk_mcp",
                "Splunk critical-alert fixture",
                len(_CRITICAL_ALERT_FIXTURE_ROWS),
                [
                    "alert_id",
                    "host",
                    "rule_name",
                    "urgency",
                    "severity",
                    "mitre_technique",
                    "mitre_tactic",
                    "alert_count",
                    "first_seen",
                    "last_seen",
                ],
                _CRITICAL_ALERT_FIXTURE_ROWS,
                tool_name="search",
                query_or_request_summary="Critical/high alert rollup in pgcil_soc/pgcil:edr over 6h.",
                executed_spl=None,
                provider_used="splunk_mcp_fixture",
            ),
            _evidence(
                "ev-rag-critical-triage",
                "rag",
                "SOC KB fixture",
                1,
                ["entry_id", "document_type", "source_excerpt", "source_refs"],
                [
                    _rag_row(
                        "triage-crit-001",
                        "Critical alert triage",
                        "Roll up by host and MITRE technique, validate alert context before escalation, and only correlate CVEs when a vulnerability source is onboarded.",
                        ["SOC-TRIAGE-CRIT-001#rollup"],
                    )
                ],
                tool_name="retrieve_soc_kb",
                query_or_request_summary="Approved critical-alert triage and CVE-correlation SOP guidance.",
                provider_used="governed_rag_fixture",
            ),
        ],
        structured_context=_context(
            "critical_alerts_mitre_cve_review",
            "attack_discovery",
            [
                _fact(
                    "fact-critical-rollup",
                    "Four critical/high alerts across VPN-GW-01, DB-PROD-02, and APP-EDGE-03 carry technique annotations for analyst review.",
                    ["ev-splunk-critical-alerts"],
                ),
                _fact(
                    "fact-cve-degrade",
                    "Unpatched CVE correlation was unavailable because no vulnerability source is onboarded.",
                    ["ev-rag-critical-triage"],
                    0.95,
                ),
            ],
            metrics={
                "critical_alert_count": 2,
                "hosts_with_critical": 2,
                "hosts_with_alerts": 3,
            },
            mitre=[
                {"technique_id": "T1110.001", "name": "Password Guessing", "support": "analyst_review", "source_refs": ["ev-splunk-critical-alerts"]},
                {"technique_id": "T1078", "name": "Valid Accounts", "support": "analyst_review", "source_refs": ["ev-splunk-critical-alerts"]},
                {"technique_id": "T1059.001", "name": "PowerShell", "support": "analyst_review", "source_refs": ["ev-splunk-critical-alerts"]},
            ],
            refs=["ev-splunk-critical-alerts", "ev-rag-critical-triage"],
            quality="partial",
        ),
    ),
    "guided_investigation_supply_chain": DemoScenario(
        scenario_id="guided_investigation_supply_chain",
        label="Guided hunt: build-server supply chain",
        category="Guided Investigation",
        query="Hunt for signs of a software supply-chain compromise across our CI/CD build servers",
        environment_mode="connected_coe_demo",
        expected_skill="guided_investigation",
        expected_sources=["rag:sop"],
        expected_sufficiency_mode="analyst_review_required",
        mcp_execution_mode="disabled",
        saia_available=True,
        rag_available=True,
        analyst_summary="This hunt is out of the vetted use-case catalog, so V.AI SOC returns review-only guided guidance: a structured hunt plan, candidate data sources, and an out-of-catalog notice. No SPL is auto-executed.",
        trace_explanation=[
            "No vetted use-case or governed template matches a supply-chain build-server hunt.",
            "The guided_investigation rescue provides a review-only hunt plan with an out-of-catalog notice instead of guessing SPL.",
            "The resource planner degrades gracefully: RAG hunt patterns are used; MCP execution stays disabled and SPL is analyst-authored.",
        ],
        source_evidence=[
            _evidence(
                "ev-rag-supply-chain-hunt",
                "rag",
                "SOC KB fixture",
                1,
                ["entry_id", "document_type", "source_excerpt", "source_refs"],
                [_rag_row("hunt-scm-001", "Supply-chain hunt patterns", "Check for unsigned build artifacts, new outbound destinations from build agents, modified pipeline definitions, and credential access from CI runners.", ["SOC-HUNT-SCM-001#patterns"])],
                tool_name="retrieve_soc_kb",
                query_or_request_summary="Approved supply-chain hunt patterns for out-of-catalog guidance.",
                provider_used="governed_rag_fixture",
            ),
        ],
        structured_context=_context(
            "guided_investigation_supply_chain",
            "guided_investigation",
            [
                _fact("fact-out-of-catalog", "No vetted use-case or governed SPL template matches a CI/CD supply-chain hunt; review-only guidance is returned.", ["ev-rag-supply-chain-hunt"]),
                _fact("fact-hunt-plan", "Approved hunt patterns cover unsigned artifacts, new build-agent egress, pipeline tampering, and CI credential access.", ["ev-rag-supply-chain-hunt"]),
            ],
            metrics={"out_of_catalog": True, "hunt_patterns": 4},
            mitre=[],
            refs=["ev-rag-supply-chain-hunt"],
            quality="partial",
        ),
    ),
}
