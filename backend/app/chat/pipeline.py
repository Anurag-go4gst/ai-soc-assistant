from __future__ import annotations

import logging
import re
import time
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, TypedDict
from uuid import uuid4

from app.config import settings
from app.connectors.telemetry import get_telemetry_connector
from app.connectors.telemetry import metrics as _telemetry_metrics
from app.connectors.telemetry.log_context import current_trace_id, reset_trace_id, set_trace_id
from app.actions.capability_policy import action_capability_for
from app.chat.analyst_response_builder import (
    build_analyst_response_for_live,
    build_reference_source_playbook,
    merge_reference_message_with_llm_intro,
    reference_narration_seed,
    reference_one_sentence_lead,
    reference_summary_line,
)
from app.answer_guard.models import AnswerGuardStatus
from app.evidence.context_structurer import structure_context
from app.evidence.context_sufficiency import check_context_sufficiency
from app.evidence.source_evidence import (
    append_mcp_loop_source_evidence,
    build_provider_source_evidence,
    build_source_evidence,
)
from app.knowledge.rag_evidence_lineage import resolve_answer_readiness, resolve_response_evidence_origin
from app.knowledge.soc_kb_retriever import retrieve_soc_kb
from app.lineage.builder import build_investigation_lineage
from app.orchestration.broaden_orchestration import (
    finalize_broaden_orchestration,
    is_broaden_pending,
    maybe_build_broaden_decision,
    should_attempt_broaden,
)
from app.orchestration.human_review import human_review, no_human_review
from app.orchestration.spl_revision_hil import polish_spl_revision_human_review, resolve_spl_revision_hil_reason
from app.orchestration.mcp_execution_gate import evaluate_mcp_execution
from app.chat.per_step_hook_idempotency import HookIdempotencyContext, resolve_hook_idempotency_context
from app.orchestration.mcp_tool_selector import EXECUTION_ELIGIBLE_SKILLS
from app.orchestration.workflow_planner import plan_workflow
from app.query_understanding.soc_investigation_shape import detect_spl_artifact_request
from app.query_understanding.semantic_intent import build_semantic_intent_envelope
from app.query_understanding.parser import understand_query
from app.routing.routing_provenance import degraded_query_understanding_from_failover
from app.routing.operation_audit import build_operation_audit_record, operation_audit_human_review
from app.routing.llm_route_plan_candidate import skipped_reason_to_candidate_reason
from app.routing.route_plan_models import ROUTE_PLAN_GENERATOR_MODEL_FAMILY, ROUTE_PLAN_REASONING_MODEL_ALLOWED
from app.routing.route_plan_preflight import preflight_route_plan
from app.routing.route_plan_validator import validate_route_plan_candidate
from app.chat.deterministic_route_plan_builder import build_deterministic_route_plan_candidate
from app.routing.intent_operation_bridge_shadow import apply_intent_operation_bridge_to_shadow
from app.coverage.question_runtime_map_shadow import apply_question_runtime_map_to_shadow
from app.routing.precondition_evaluation_shadow import apply_precondition_evaluation_to_shadow
from app.routing.route_authority_compare import apply_route_authority_compare_to_shadow
from app.routing.route_authority_apply import project_compare_for_display
from app.routing.registry_route_authority import resolve_effective_routing_skill
from app.routing.route_adjudication import adjudicate_route as adjudicate_control_plane_route
from app.routing.llm_plan_validator import (
    build_advisory_plan_from_context,
    should_validate_llm_advisory_plan,
    validate_llm_advisory_plan,
)
from app.routing.supporter_registry import build_supporter_trace
from app.routing.use_case_registry_bridge import build_use_case_registry_bridge
from app.routing.template_match_shadow import apply_template_match_to_shadow
from app.synthesis.analyst_summary_llm_assist import apply_analyst_summary_shadow
from app.governance.trace_panels import build_governance_trace
from app.risk.severity_policy import (
    apply_analytics_severity_guard,
    apply_gate_severity_cap,
    decide_severity,
)
from app.safeguards.spl_validator import validate_spl
from app.safeguards.spl_slot_binding_validator import validate_spl_slot_bindings
from app.schemas.requests import ChatRequest
from app.schemas.responses import AnalystResponseEnvelope, PlaceholderResponse, SessionContextStatusEnvelope
from app.skills.selector import select_skill_chain
from app.spl.template_registry import QUERY_SHAPE_RAW_SEARCH, get_spl_template, template_summary
from app.splunk.capabilities import build_splunk_capability_profile
from app.chat.network_boundary_display import resolve_analyst_use_case_label
from app.chat.review_only_spl_renderer import apply_review_only_spl_render
from app.spl.spl_artifact_trace_projection import build_spl_artifact_handoff_summary
from app.spl.draft_preview import (
    DRAFT_PREVIEW_STATUS_MESSAGE,
    build_draft_preview,
    build_draft_preview_analyst_message,
    candidate_detection_families,
)
from app.llm.clients.local_chat_client import LocalChatError
from app.spl.llm_fallback import generate_llm_spl_fallback
from app.spl.llm_lineage_vigilance import classify_llm_spl_risk
from app.spl.llm_plan_compiler import generate_llm_spl_via_plan
from app.spl.review_only_spl_postprocessor import finalize_review_only_spl
from app.spl.spl_relevance_check import check_spl_relevance
from app.spl.mcp_loop_discovery import execute_loop_discovery_hop
from app.spl.mcp_source_discovery import run_mcp_source_discovery
from app.spl.saved_search_preference import (
    apply_saved_search_preference_to_spl,
    preference_from_discovery_context,
)
from app.spl.source_profile_resolver import extract_placeholder_slots
from app.spl.spl_source_resolve import build_spl_source_profile_review, resolve_spl_source_profile
from app.spl.t2_generation import generate_review_only_spl
from app.spl.t2_pre_parse import pre_parse_spl_tokens
from app.spl.runtime_source_profiles import resolve_profile_for_index
from app.splunk.spl_services import (
    explain_spl,
    generate_candidate_spl_with_provider,
    merge_post_validation_optimization,
    splunk_guidance,
)
from app.answer_guard.runner import run_answer_guard_lab
from app.llm.governed_context_package import build_governed_context_package_for_contract
from app.llm.guided_llm_budget import (
    build_guided_turn_budget,
    guided_turn_deadline_seconds,
    is_guided_investigation_route,
    should_skip_intent_advisor_for_guided,
)
from app.llm.turn_llm_budget import TurnLlmBudget
from app.llm.evidence_observer import (
    EVIDENCE_OBSERVER_ROLE,
    parse_evidence_observer_output,
    sanitize_rows_for_observer,
)
from app.llm.sidecar_clients import invoke_sidecar_role_with_metadata
from app.synthesis.composer_context_builders import (
    mcp_tool_hints_from_registry,
    skill_sections_from_enrichment,
    soc_kb_snippets_from_source_evidence,
)
from app.synthesis.composition_confidence import (
    composition_confidence,
    qualifies_for_weak_case_composition,
    should_attach_compose_hil,
)
from app.synthesis.governed_answer_composer import (
    GovernedComposerResult,
    build_composer_runtime_status,
    compose_governed_answer,
)
from app.synthesis.lab_runner import apply_synthesis_allowed_to_sufficiency, run_governed_synthesis_lab
from app.use_cases.content_enrichment import (
    get_guidance_only_enrichment_projection,
    get_runtime_curated_enrichment,
    llm_facing_curated_enrichment_projection,
)
from app.synthesis.models import SynthesisStatus
from app.synthesis.observation_grounding import ground_evidence_observations
from app.threat.mitre_decision import resolve_mitre_decision
from app.threat.mitre_kb import MitreMappingDecision, map_mitre_for_use_case
from app.use_cases.content_enrichment import enrichment_spl_governance, enrichment_spl_governance_for_runtime
from app.use_cases.models import UseCaseSelection
from app.use_cases.registry import match_use_cases
from app.use_cases.routing_authority import catalog_authority_row, sidecar_intent_is_t0
from app.chat.contracts.pipeline_dispatch import (
    McpDiscoveryContext,
    PipelineStage,
    build_pipeline_dispatch,
    build_plan_dispatch_trace_from_pipeline_dispatch,
    imperative_hook_schedule_from_state,
    next_stage_after,
    projected_flags_from_state,
)
from app.chat.contracts.run_contract import RouteContract
from app.chat.evidence_planner import plan_evidence, resolve_analyst_evidence_plan
from app.planner.executor import (
    DispatchHooks,
    annotate_step_statuses,
    execute_plan_dispatch,
    has_composed_plan,
)
from app.chat.contracts.answer_contract import build_answer_contract
from app.chat.contracts.investigation_plan import InvestigationPlan
from app.chat.contracts.llm_intent_advisory import LLMIntentAdvisory
from app.chat.answer_shape_router import (
    build_shaped_guidance,
    build_supply_chain_firmware_guidance,
    classify_answer_shape,
    is_supply_chain_firmware_query,
    plan_purposes_from_resource_plan,
    should_bypass_shape_router,
)
from app.chat.shape_advisor import apply_shape_advisory_promotion, generate_shape_advisory
from app.chat.final_answer_validator import validate_final_answer
from app.chat.guidance_summary_renderer import is_guidance_summary_path
from app.chat.negative_evidence_extractor import extract_negative_evidence
from app.llm.missing_evidence_reasoner import (
    MissingEvidenceReasonerResult,
    run_missing_evidence_reasoner,
)
from app.llm.mitre_risk_rationale import (
    MitreRiskRationaleResult,
    build_deterministic_mitre_rationale,
    build_deterministic_severity_rationale,
    run_mitre_risk_rationale,
)
from app.planner.plan_promotion_merge import apply_llm_primary_resource_plan, record_planner_sidecar
from app.planner.resource_plan import ResourcePlan
from app.planner.resource_plan_shadow import run_resource_plan_shadow
from app.connectors.mcp.mcp_tool_chronology import deterministic_default_chronology
from app.connectors.mcp.mcp_tool_planner import plan_tool_chronology
from app.chat.evidence_loop import (
    MAX_MCP_HOPS,
    ROUTE_DISCOVERY_HOP,
    assess_loop,
    assess_loop_with_recipe,
    apply_observer_next_hop_hint,
    build_data_silence_advisory,
    cve_requirements_present,
    initialize_loop,
    loop_initialized,
    record_execution_hop,
    record_hop,
    record_recipe_call,
)
from app.planner.recipe_registry import get_recipe, select_recipe_for_plan
from app.chat.guided_hunt_grounding import (
    T2_UNVERIFIED_BANNER,
    build_guided_hunt_grounding,
    guided_hunt_grounding_trace,
)
from app.cve.evidence_adapter import (
    append_cve_snapshot_source_evidence,
    resolve_vulnerability_source_status as resolve_cve_vulnerability_status,
    vulnerability_context_line,
)
from app.connectors.mcp.mcp_tool_plan_shadow import (
    mcp_tool_plan_llm_advisory_enabled,
    run_mcp_tool_plan_shadow,
)
from app.connectors.mcp.mcp_rbac import session_role_for_mcp_gate
from app.coverage.promotion_lifecycle import effective_promotion_status, can_skip_llm_for_t0
from app.coverage.question_runtime_map import question_runtime_entry
from app.coverage.row_authority import classify_runtime_row_authority, project_s3_authority_ready
from app.llm.sidecar_skip_policy import should_skip_sidecar
from app.llm.intent_advisor_scheduler import (
    build_intent_scheduling_trace,
    intent_advisor_hop_blocked,
    intent_advisor_provider_configured,
    intent_elapsed_before_call_ms,
    should_prioritize_intent_advisor,
)
from app.chat.query_signals import extract_query_signals
from app.chat.spl_authoring_intent import (
    is_universal_utility_spl_authoring,
    should_skip_intent_for_universal_utility_spl,
)
from app.catalogue.live_router_bind import apply_live_catalogue_bind
from app.chat.intent_classifier import build_query_to_intent
from app.chat.llm_intent_advisor import generate_llm_intent_advisory, intent_advisor_consumable
from app.llm.t2_advisory_latency_policy import (
    cap_turn_deadline_for_t2_advisory,
    enrich_intent_advisory_trace,
    should_bound_t2_intent_advisor,
    t2_intent_advisor_bound_seconds,
)
from app.use_cases.answer_packs import answer_pack_summary, reviewed_answer_pack
from app.spl.source_profile_bindings import build_source_profile_binding_slots
from app.spl.template_compatibility import check_template_compatibility
from app.spl.template_query_bindings import customize_template_spl_with_trace
from app.spl.slot_constraint_projection import (
    build_slot_constraint_projection,
    merge_evidence_plan_spl_drift,
    projection_from_bindings,
)
from app.spl.user_constraint_bindings import (
    SLOT_SOURCE_LLM,
    UserConstraintBindings,
    build_user_constraint_bindings,
)
from app.chat.mitre_branch import planner_mitre_branch_suppressed_decision, run_mitre_evidence_branch
from app.chat.hil_resolution import resolve_effective_hil_required
from app.chat.planning_decision import plan_path_and_tools
from app.chat.control_plane_trace import build_control_plane_trace
from app.chat.canonical_facts_spine import harvest_canonical_facts_from_state
from app.chat.canonical_db import planning_turn_scope
from app.synthesis.turn_timing import (
    RunKind,
    SynthesisPath,
    TurnOutcome,
    close_retrieval_spl_phase,
    finalize_turn_timing,
    record_synthesis_endpoint,
    synthesis_turn_timing_scope,
)
from app.chat.debug_summary import build_debug_summary
from app.chat.guided_discovery_promotion import build_guided_discovery_promotion_offer
from app.chat.guided_answer_contract import enhance_answer_contract_for_guided_hybrid
from app.chat.guided_handoff_trace import blocked_resources_wire, build_guided_handoff_trace
from app.chat.guided_hybrid_refinement import (
    MAX_GUIDED_INVESTIGATION_ROUNDS,
    apply_refinement_cap_warning,
    count_collected_guided_hops,
    refinement_cap_reached,
    should_run_refinement_pass,
)
from app.chat.guided_hybrid_dispatch import uses_guided_hybrid_dispatch_from_state
from app.chat.guided_hybrid_collection import collect_guided_hybrid_evidence
from app.chat.guided_investigation_plan_llm import propose_investigation_plan_llm
from app.chat.guided_investigation_synthesizer import (
    build_guided_llm_degraded_message,
    build_guided_llm_trace,
    resolve_guided_composer_timeout,
)
from app.chat.guided_step_sanitizer import filter_analyst_facing_steps
from app.chat.guided_investigation_planner import validate_investigation_plan
from app.chat.guided_capability_validator import validate_guided_resource_plan
from app.chat.guided_spl_review_gate import build_guided_spl_draft_preview_if_allowed
from app.chat.investigation_plan_builder import build_deterministic_investigation_plan
from app.chat.pipeline_visibility import build_pipeline_visibility
from app.chat.pipeline_state_v2 import project_chat_pipeline_state_v2
from app.chat.routing_skill_nodes import (
    graph_node_load_skill_enrichment,
    graph_node_resolve_planning_skill,
    graph_node_route_live_skill,
)
from app.chat.session_context import (
    SessionContextResolution,
    SessionPins,
    clear_session,
    persist_session_pins,
    pins_from_pipeline_state,
    resolve_session_context,
    use_case_from_session,
)
from app.chat.progress_context import (
    bind_progress_reporter,
    emit_mcp_status_from_execution,
    emit_stage,
    reset_progress_reporter,
)
from app.chat.progress_events import ProgressReporter

logger = logging.getLogger("ai_soc.telemetry")

_PARTIAL_SYNTHESIS_MESSAGE = (
    "Final LLM synthesis timed out; showing validated intermediate result."
)
OBSERVER_MAX_CALLS_PER_TURN = 1


def _routes_chat():
    """Lazy import so tests can monkeypatch symbols on app.api.routes_chat."""
    from app.api import routes_chat

    return routes_chat


class ChatPipelineState(TypedDict, total=False):
    request: ChatRequest
    trace_id: str
    query_understanding: Any
    selected_use_case: Any
    routed: dict[str, Any]
    route_plan_shadow: dict[str, Any]
    routing_skill_resolution: dict[str, Any]
    skill_selection: Any
    selected_skill_chain: Any
    disagreement: bool
    comparison: dict[str, Any]
    workflow_plan: dict[str, Any]
    candidate_spl: dict[str, Any] | None
    spl_validation: dict[str, Any] | None
    spl_draft_preview: dict[str, Any] | None
    llm_spl_candidate: dict[str, Any] | None
    spl_source_resolve: dict[str, Any] | None
    llm_derived_spl_artifact: dict[str, Any] | None
    execution: dict[str, Any]
    execution_reconciliation: dict[str, Any] | None
    human_review: dict[str, Any]
    source_evidence: list[dict[str, Any]]
    structured_context: dict[str, Any]
    context_sufficiency: dict[str, Any]
    spl_template: dict[str, object] | None
    mitre_mappings: list[Any]
    severity_decision: Any
    synthesis_status: Any
    answer_guard: Any
    action_capability: Any
    investigation_lineage: Any
    message: str
    note: str
    governance_trace: Any
    query_to_intent: dict[str, Any] | None
    llm_intent_advisory: LLMIntentAdvisory | None
    # LangGraph silently drops any state key not declared here (see executor
    # guide). shape_advisory was set by graph_node_query_understanding but
    # never declared — the LangGraph edge (LANGGRAPH_ORCHESTRATION_ENABLED=true,
    # the live default) dropped it every turn, so control_plane_trace.shape_advisory
    # read null in production even though the sidecar ran and item 21's tests
    # passed (tests call the node function directly, bypassing the graph edge).
    shape_advisory: dict[str, Any] | None
    intent_classification: dict[str, Any] | None
    evidence_plan: dict[str, Any] | None
    planning_decision: dict[str, Any] | None
    intent_dispatch: dict[str, Any] | None
    pipeline_dispatch: dict[str, Any] | None
    llm_spl_plan: dict[str, Any] | None
    route_adjudication: dict[str, Any] | None
    route_contract: dict[str, Any] | None
    run_contract: dict[str, Any] | None
    llm_plan_validation: dict[str, Any] | None
    mitre_decision: dict[str, Any] | None
    mitre_branch_result: dict[str, Any] | None
    answer_contract: dict[str, Any] | None
    soc_kb_retrieval: dict[str, Any] | None
    session_id: str | None
    session_pins: Any
    session_context_resolution: SessionContextResolution | None
    session_role: str | None
    effective_query: str | None
    llm_turn_budget: TurnLlmBudget | None
    # Stage 4B governed evidence-collection loop (canonical planning always on).
    mcp_chronology: list[str]
    mcp_cursor: int
    mcp_evidence: list[dict[str, Any]]
    mcp_hops_done: int
    mcp_requirements: dict[str, list[str]]
    mcp_required_produces: list[str]
    mcp_loop: dict[str, Any]
    mcp_loop_planner: dict[str, Any] | None
    evidence_observer_trace: dict[str, Any] | None
    reference_resolution: dict[str, Any] | None
    # O5c recipe-aware HUB path (item 3.1, 2026-07-03) — unset unless item 3.2's
    # selector chooses a recipe; the chronology-driven path above is unaffected.
    mcp_recipe_id: str | None
    mcp_recipe_pending_call_id: str | None
    mcp_call_records: list[dict[str, Any]]
    data_silence_advisory: dict[str, Any] | None
    # C1/C9 v2 additive visibility (packaging mirrors response; routed stays authority).
    live_execution_skill: str | None
    planning_or_analytic_skill: str | None
    skill_enrichment: dict[str, Any] | None
    spl_template_status: str | None
    mitre_evidence_status: dict[str, str] | None
    execution_decision: dict[str, Any] | None
    final_answer_validation: dict[str, Any] | None
    node_trace: list[dict[str, Any]]
    # Plan 5.2 — LangGraph drops undeclared keys; spine + dispatch/gate channels.
    canonical_facts: dict[str, Any] | None
    final_evidence_gate: dict[str, Any] | None
    plan_dispatch_trace: dict[str, Any] | None
    # Resource Planner hierarchy — append-only audit trail (item 4).
    decision_log: list[dict[str, Any]]
    # Item 5.4 — advisory grounding block assembled from the CanonicalFacts spine.
    grounding_block: dict[str, Any] | None
    # Canonical planning channels (T0–T4 cutover, plan 2026-07-24_2310). Written by
    # graph_node_lane_and_canonical_planning and read by later nodes — guided hybrid
    # dispatch/executor, planner/executor.py, session_context. ResourcePlannerGraphState
    # inherits this TypedDict, so an undeclared key here is dropped on the live RP graph
    # edge even though the imperative pipeline and node-level tests still see it.
    canonical_planning_input: dict[str, Any] | None
    canonical_planning_outcome: dict[str, Any] | None
    canonical_planning_failure: dict[str, Any] | None
    gap_resolution: dict[str, Any] | None
    known_completeness: dict[str, Any] | None
    processing_lane: str | None
    initial_tier: str | None
    resolved_tier: str | None
    handoff_resume: dict[str, Any] | None
    pending_handoff_id: str | None
    pending_handoff_version: int | None
    # Test harness only — allows legacy graph_node_evidence_planning on first entry
    # when canonical mode is authoritative (see graph_node_evidence_planning guard).
    legacy_langgraph_harness: bool
    response: PlaceholderResponse


_RP_DEGRADED_MESSAGE = (
    "The Resource Planner graph stopped before a response could be finalized. "
    "No SPL, MCP execution, or synthesis was performed."
)
_RP_DEGRADED_NOTE = (
    "Resource Planner graph did not produce a finalized answer; degraded facade only. "
    "Orchestration: resource_planner_hierarchy."
)


def build_rp_degraded_placeholder_response(
    request: ChatRequest,
    *,
    state: ChatPipelineState | None = None,
    session_role: str | None = None,
    entrypoint: str = "rp_fallback",
    reason: str = "response_missing",
) -> PlaceholderResponse:
    """Honest degraded card when RP graph completes without a finalized response.

    Item 12a: must not re-enter RP graph or run the legacy imperative pipeline.
    """
    trace_id = str((state or {}).get("trace_id") or current_trace_id() or uuid4())
    selected_skill = None
    routed = (state or {}).get("routed") if isinstance(state, dict) else None
    if isinstance(routed, dict):
        selected_skill = routed.get("skill")
    response = PlaceholderResponse(
        trace_id=trace_id,
        turn_id=str(uuid4()),
        message=_RP_DEGRADED_MESSAGE,
        note=_RP_DEGRADED_NOTE,
        user_query=request.message,
        selected_skill=selected_skill,
        response_mode="insufficient_evidence",
        answer_readiness="blocked",
        response_packaging_status="blocked_review_required",
        fallback_active=True,
        execution=None,
        candidate_spl=None,
        spl_validation=None,
        planning_decision={
            "path_type": "rp_degraded_facade",
            "execution_enabled": False,
            "hil_required": True,
            "degraded_reason": reason,
            "entrypoint": entrypoint,
        },
    )
    if isinstance(state, dict):
        from app.chat.control_plane_trace import patch_control_plane_trace_decision_log

        response = patch_control_plane_trace_decision_log(response, state)
    return response


def _benchmark_run_kind_override() -> RunKind | None:
    return benchmark_run_kind_override()


def build_live_chat_response(
    request: ChatRequest,
    *,
    progress: ProgressReporter | None = None,
    session_role: str | None = None,
    entrypoint: str = "chat",
) -> PlaceholderResponse:
    """Rollback orchestration when ``LANGGRAPH_ORCHESTRATION_ENABLED=false``.

    ``entrypoint=rp_fallback`` is the item-12a degraded facade only (no imperative
    re-run). Production ``/chat`` uses ``run_chat_via_resource_planner_graph``.
    """
    token = bind_progress_reporter(progress) if progress is not None else None

    try:
        run_kind = _benchmark_run_kind_override()
        with synthesis_turn_timing_scope(run_kind=run_kind):
            with planning_turn_scope():
                return _build_live_chat_response_inner(request, session_role=session_role, entrypoint=entrypoint)
    finally:
        if token is not None:
            reset_progress_reporter(token)
        reset_trace_id()


def _build_live_chat_response_inner(
    request: ChatRequest,
    *,
    session_role: str | None = None,
    entrypoint: str = "chat",
) -> PlaceholderResponse:
    if entrypoint.startswith("rp_"):
        # ``routes_chat`` is the sole orchestration selector. RP graph fallbacks
        # must stay on the degraded facade and never re-enter RP orchestration or
        # the legacy imperative pipeline (item 12a).
        from app.graph.resource_planner_graph import guard_rp_imperative_fallback

        guard_rp_imperative_fallback(entrypoint)
        if entrypoint == "rp_fallback":
            return build_rp_degraded_placeholder_response(
                request,
                session_role=session_role,
                entrypoint=entrypoint,
                reason="rp_fallback_facade",
            )
    started_at = datetime.now(UTC)
    state: ChatPipelineState | None = None
    try:
        state = _run_live_chat_pipeline(request, session_role=session_role)
    except Exception:
        # Record an honest error run so the debug surface can answer
        # "why no response" instead of showing nothing.
        if isinstance(state, dict):
            _persist_live_chat_error(state, started_at=started_at, session_role=session_role)
        raise
    response = state.get("response")
    if response is None:
        raise RuntimeError("chat pipeline did not produce a response")
    _persist_live_chat_telemetry(
        state, response, started_at=started_at, session_role=session_role, entrypoint=entrypoint
    )
    return response


def _run_live_chat_pipeline(
    request: ChatRequest,
    *,
    session_role: str | None = None,
) -> ChatPipelineState:
    emit_stage("queued")
    session_resolution = resolve_session_context(request)
    state: ChatPipelineState = {
        "request": request,
        "session_id": session_resolution.session_id,
        "session_pins": session_resolution.pins,
        "session_context_resolution": session_resolution,
        "session_role": session_role,
        "effective_query": session_resolution.effective_query,
        "handoff_resume": session_resolution.handoff_resume,
    }
    state = _timed_node(state, "init_routing", graph_node_init_routing)
    if settings.ai_soc_pipeline_split_routing_nodes_enabled:
        state = _timed_node(state, "route_live_skill", graph_node_route_live_skill)
        state = _timed_node(state, "resolve_planning_skill", graph_node_resolve_planning_skill)
        state = _timed_node(state, "load_skill_enrichment", graph_node_load_skill_enrichment)
    from app.chat.canonical_planning_orchestrator import run_canonical_planning

    state = _timed_node(state, "canonical_planning", run_canonical_planning)
    if not _uses_guided_hybrid_dispatch(state):
        state = _timed_node(state, "discovery_loop", _run_discovery_loop_imperative)
    state = _timed_node(state, "shadow_tail", graph_node_shadow_tail)
    if _session_spl_refine_active(state):
        state = _timed_node(
            state,
            "plan_dispatch_session_spl_refine",
            lambda s: _run_legacy_dispatch_fallback(s, dispatch_source="session_spl_refine"),
        )
    elif _uses_guided_hybrid_dispatch(state):
        state = _timed_node(state, "guided_hybrid_dispatch", _run_guided_hybrid_dispatch)
    elif has_composed_plan(state):
        state = _timed_node(state, "plan_dispatch", lambda s: execute_plan_dispatch(s, _dispatch_hooks()))
    else:
        from app.chat.canonical_mode import (
            build_canonical_failure_state,
            build_non_planned_dispatch_state,
        )
        from app.chat.canonical_outcome_read import OutcomeReadKind, read_canonical_planning_outcome

        read = read_canonical_planning_outcome(state)
        if read.kind == OutcomeReadKind.VALID and read.outcome is not None and read.outcome.status != "planned":
            status = read.outcome.status
            state = _timed_node(
                state,
                "plan_dispatch_skipped_non_planned",
                lambda s: build_non_planned_dispatch_state(s, status=status),
            )
        else:
            reason = "canonical_missing_resource_plan_at_dispatch"
            if read.kind == OutcomeReadKind.MALFORMED:
                reason = "canonical_invalid_outcome_at_dispatch"
            elif read.kind == OutcomeReadKind.ABSENT:
                reason = "canonical_missing_outcome_at_dispatch"
            state = _timed_node(
                state,
                "plan_dispatch_canonical_failure",
                lambda s, r=reason: build_canonical_failure_state(
                    s,
                    outcome="planning_failed",
                    reason=r,
                ),
            )
    if loop_initialized(state):
        state = _timed_node(state, "evidence_planning_loop", graph_node_evidence_planning)
    state = _timed_node(state, "context_finalize", graph_node_context_finalize)
    return state


def _timed_node(
    state: ChatPipelineState,
    node_name: str,
    fn: Any,
) -> ChatPipelineState:
    """Run a pipeline node, timing it and recording a durable node-timeline step.

    The trace spine is keyed on ``state['trace_id']`` (set by ``init_routing``);
    for the first node the id only exists on the returned state, so timing is
    recorded from the result. Telemetry never breaks the node flow.
    """
    started = time.monotonic()
    try:
        result = fn(state)
    except Exception:
        duration_ms = int((time.monotonic() - started) * 1000)
        _record_node_timing(state.get("trace_id"), node_name, "error", duration_ms)
        raise
    duration_ms = int((time.monotonic() - started) * 1000)
    trace_id = result.get("trace_id") if isinstance(result, dict) else None
    _record_node_timing(trace_id or state.get("trace_id"), node_name, "completed", duration_ms)
    return result


def _record_node_timing(
    trace_id: Any,
    node_name: str,
    status: str,
    duration_ms: int,
) -> None:
    if not trace_id:
        return
    try:
        _routes_chat().get_telemetry_connector().record_step(
            str(trace_id),
            f"node.{node_name}",
            status,
            duration_ms=duration_ms,
            node=True,
        )
    except Exception:  # noqa: BLE001 - telemetry must never break chat
        logger.warning("node_timing_persist_failed", exc_info=True)



def persist_chat_admission(trace_id: str, user: object, *, entrypoint: str = "chat") -> None:
    """Persist a running trace admission row before pipeline work (best-effort)."""
    try:
        session_role = user.get("role") if isinstance(user, dict) else None
        connector = _routes_chat().get_telemetry_connector()
        connector.start_trace(
            trace_id,
            entrypoint=entrypoint,
            status="running",
            started_at=datetime.now(UTC),
            user_id=session_role,
            metadata={"admission": True, "session_role": session_role},
        )
        connector.reap_stale_running_runs()
    except Exception:  # noqa: BLE001 - admission telemetry must never break chat
        logger.warning("chat_admission_record_failed trace_id=%s", trace_id, exc_info=True)


def finalize_chat_trace_from_state(
    state: ChatPipelineState,
    response: PlaceholderResponse,
    *,
    started_at: datetime,
    session_role: str | None,
    entrypoint: str = "chat",
) -> None:
    """Close the durable trace spine for LangGraph and stream parity paths."""
    _persist_live_chat_telemetry(
        state,
        response,
        started_at=started_at,
        session_role=session_role,
        entrypoint=entrypoint,
    )



def _resolve_trace_answer_mode(payload: dict[str, Any]) -> str | None:
    if not isinstance(payload, dict):
        return None
    sufficiency = payload.get("context_sufficiency")
    answer_mode = payload.get("answer_mode") or (
        sufficiency.get("answer_mode") if isinstance(sufficiency, dict) else None
    )
    if answer_mode:
        return str(answer_mode)
    evidence_plan = payload.get("evidence_plan")
    if isinstance(evidence_plan, dict) and evidence_plan.get("answer_mode"):
        return str(evidence_plan["answer_mode"])
    candidate_spl = payload.get("candidate_spl")
    spl_validation = payload.get("spl_validation")
    if _is_universal_spl_authoring_review(
        candidate_spl if isinstance(candidate_spl, dict) else None,
        spl_validation if isinstance(spl_validation, dict) else None,
    ):
        return "spl_utility_authoring"
    return None


def _strip_rag_from_workflow_plan(workflow_plan: dict[str, Any]) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    for step in workflow_plan.get("steps") or []:
        if not isinstance(step, dict):
            continue
        step_copy = dict(step)
        connectors = [
            str(item)
            for item in step_copy.get("required_connectors") or []
            if str(item) != "rag"
        ]
        step_copy["required_connectors"] = connectors
        steps.append(step_copy)
    required_connectors = sorted(
        {connector for step in steps for connector in step.get("required_connectors") or []}
    )
    return {
        **workflow_plan,
        "steps": steps,
        "required_connectors": required_connectors,
        "required_sources": [
            str(item)
            for item in workflow_plan.get("required_sources") or []
            if not str(item).startswith("rag:")
        ],
    }


def _persist_live_chat_telemetry(
    state: ChatPipelineState,
    response: PlaceholderResponse,
    *,
    started_at: datetime,
    session_role: str | None,
    entrypoint: str = "chat",
) -> None:
    """Phase 0/1: persist the durable trace spine + per-turn LLM-call ledger.

    Telemetry must never break the chat flow, so all work is wrapped here and the
    connector also fails closed internally. Only metadata is persisted — no raw
    prompts, completions, or events (redaction is applied by the connector).
    """
    try:
        telemetry = _routes_chat().get_telemetry_connector()
        trace_id = str(response.trace_id or state.get("trace_id") or "")
        if not trace_id:
            return
        payload = response.model_dump(mode="json")
        answer_mode = _resolve_trace_answer_mode(payload)
        run_status = "human_review" if payload.get("human_review") else "completed"
        telemetry.start_trace(
            trace_id,
            entrypoint=entrypoint,
            status="running",
            started_at=started_at,
            user_id=session_role,
            metadata={"session_role": session_role},
        )
        budget = state.get("llm_turn_budget")
        records = budget.records if isinstance(budget, TurnLlmBudget) else []
        for record in records:
            telemetry.record_llm_call(
                trace_id,
                kind=record.get("kind"),
                role=record.get("role"),
                provider_label=record.get("provider_label"),
                outcome=record.get("outcome"),
                latency_ms=record.get("latency_ms"),
                model=record.get("model"),
            )
            _count_llm_call(record)
        try:
            from app.chat.final_output_trace import build_final_output_trace

            final_output = build_final_output_trace(payload)
            telemetry.record_step(
                trace_id,
                "node.finalize_response",
                run_status,
                selected_skill=payload.get("selected_skill"),
                answer_mode=answer_mode,
                hil_required=bool(final_output.get("hil_required")) if final_output else None,
                message_preview=(final_output.get("message") or "")[:240] or None,
            )
        except Exception:  # noqa: BLE001 - telemetry must never break chat
            logger.warning("finalize_response_step_failed", exc_info=True)
        telemetry.end_trace(
            trace_id,
            status=run_status,
            metadata={
                "answer_mode": answer_mode,
                "selected_skill": payload.get("selected_skill"),
                "llm_call_count": len(records),
                "llm_live_calls": sum(1 for item in records if item.get("outcome") == "completed"),
            },
        )
        _telemetry_metrics.increment(
            "chat_turns_human_review" if run_status == "human_review" else "chat_turns_completed"
        )
    except Exception:  # noqa: BLE001 - telemetry must never break chat
        logger.warning("live_chat_telemetry_persist_failed", exc_info=True)


def _count_llm_call(record: dict[str, Any]) -> None:
    _telemetry_metrics.increment("llm_calls_total")
    outcome = str(record.get("outcome") or "")
    if outcome == "timed_out":
        _telemetry_metrics.increment("llm_calls_timed_out")
    if outcome in {"timed_out", "dropped", "blocked"}:
        _telemetry_metrics.increment("llm_calls_fallback")


def _persist_live_chat_error(
    state: ChatPipelineState,
    *,
    started_at: datetime,
    session_role: str | None,
) -> None:
    """Record an error run when the pipeline raised before producing a response."""
    try:
        trace_id = str(state.get("trace_id") or "")
        if not trace_id:
            return
        telemetry = _routes_chat().get_telemetry_connector()
        _telemetry_metrics.increment("chat_turns_error")
        telemetry.start_trace(
            trace_id,
            entrypoint="chat",
            status="error",
            started_at=started_at,
            user_id=session_role,
            metadata={"session_role": session_role},
        )
        telemetry.end_trace(trace_id, status="error", metadata={"error": True})
    except Exception:  # noqa: BLE001 - telemetry must never break chat
        logger.warning("live_chat_error_telemetry_persist_failed", exc_info=True)



def _compute_turn_deadline_for_state(query_understanding: Any, routed: dict[str, Any]) -> float:
    """P2-B dynamic turn deadline from query shape and routed skill."""
    from app.llm.hybrid_role_graph import compute_turn_deadline_seconds
    from app.use_cases.routing_authority import catalog_authority_row

    provenance = routed.get("routing_provenance") if isinstance(routed, dict) else {}
    match_path = provenance.get("deterministic_match_path") if isinstance(provenance, dict) else None
    if match_path is None and query_understanding is not None:
        match_path = getattr(query_understanding, "deterministic_match_path", None)
    selected_skill = str(routed.get("skill") or "knowledge_recall") if isinstance(routed, dict) else "knowledge_recall"
    soc_shaped = bool(getattr(query_understanding, "soc_investigation_shaped", False))
    use_case_ids = list(getattr(query_understanding, "mapped_use_case_ids", None) or [])
    catalog_row = catalog_authority_row(use_case_ids[0] if use_case_ids else None)
    registry_warnings = list(getattr(query_understanding, "registry_warnings", None) or [])
    base = compute_turn_deadline_seconds(
        match_path=match_path,
        selected_skill=selected_skill,
        soc_investigation_shaped=soc_shaped,
    )
    if (
        settings.ai_soc_guided_llm_enabled
        and is_guided_investigation_route(routed_skill=selected_skill)
    ):
        return guided_turn_deadline_seconds()
    return cap_turn_deadline_for_t2_advisory(
        match_path=match_path,
        catalog_row=catalog_row,
        registry_warnings=registry_warnings,
        selected_skill=selected_skill,
        base_deadline=base,
    )



def graph_node_init_routing(state: ChatPipelineState) -> ChatPipelineState:
    emit_stage("understanding_query")
    request = state["request"]
    query_text = state.get("effective_query") or request.message
    # Reuse the request-boundary trace seeded before dependencies execute. This
    # keeps success telemetry, protected exception diagnostics, and the sanitized
    # 500 envelope on one correlation id. Direct/in-process callers still receive
    # a fresh id.
    trace_id = current_trace_id()
    if not trace_id or trace_id == "-":
        trace_id = str(uuid4())
    set_trace_id(trace_id)
    qu_failed = False
    try:
        query_understanding = understand_query(query_text)
    except Exception:
        query_understanding = None
        qu_failed = True
    selected_use_case = _selected_use_case(query_text, query_signals=None)
    session_resolution = state.get("session_context_resolution")
    if isinstance(session_resolution, SessionContextResolution):
        if (
            session_resolution.apply_use_case_id
            and session_resolution.status.staleness == "fresh"
            and not session_resolution.status.clarification_required
        ):
            session_use_case = use_case_from_session(session_resolution.apply_use_case_id)
            if session_use_case is not None:
                selected_use_case = session_use_case
    rc = _routes_chat()
    routed = rc.route_skill(
        query_text,
        trace_id=trace_id,
        query_understanding=query_understanding,
        qu_failed=qu_failed,
    )
    if query_understanding is None:
        query_understanding = degraded_query_understanding_from_failover(
            request.message,
            routed.get("routing_provenance") or {},
        )
    route_plan_shadow = _route_plan_shadow_stage(
        query_text,
        deterministic_primary_skill=str(routed["skill"]),
        selected_use_case=selected_use_case,
        query_understanding=query_understanding,
    )
    routed_skill = str(routed.get("skill") or "")
    if is_guided_investigation_route(routed_skill=routed_skill) and settings.ai_soc_guided_llm_enabled:
        llm_budget = build_guided_turn_budget()
    else:
        llm_budget = TurnLlmBudget(
            deadline_seconds=_compute_turn_deadline_for_state(query_understanding, routed),
        )
    return {
        **state,
        "trace_id": trace_id,
        "query_understanding": query_understanding,
        "selected_use_case": selected_use_case,
        "routed": routed,
        "route_plan_shadow": route_plan_shadow,
        "llm_turn_budget": llm_budget,
    }


# Wall-clock cap for the advisory intent hop on a frozen-T0, review-only row
# (exact-105 / exact-105 + catalogue / catalogue t0_exact_authority) that was
# demoted only for answer-authority/enrichment reasons. The route is already
# deterministic and the advisor cannot supply the missing SPL binding, so a
# slow/timing-out call (q0.q046, ~100s) must fall back fast instead of consuming
# the full turn deadline. Failover is also suppressed for this hop (a second
# doomed retry would double the wall-clock), so the cap is the whole advisory
# budget for the turn. Kept inside the live 1-3s target.
_FROZEN_T0_INTENT_ADVISOR_BOUND_SECONDS = 2.0


def graph_node_query_to_intent(state: ChatPipelineState) -> ChatPipelineState:
    """Passive query-to-intent stage (does not change routing when flag is off)."""
    emit_stage("classifying_intent")
    request = state["request"]
    query_understanding = state.get("query_understanding")
    routed = state.get("routed") or {}
    routed_skill = str(routed.get("skill")) if routed.get("skill") else None
    query_text = state.get("effective_query") or request.message
    qu = state.get("query_understanding")
    candidate_mappings: dict[str, Any] = {}
    if qu is not None:
        candidate_mappings = {
            "match_path": getattr(qu, "deterministic_match_path", None),
            "question_ref": getattr(qu, "mapped_question_ref", None),
            "use_case_ids": list(getattr(qu, "mapped_use_case_ids", None) or []),
        }
    prior_budget = state.get("llm_turn_budget") or TurnLlmBudget()
    budget = TurnLlmBudget(
        max_sidecar_calls=prior_budget.max_sidecar_calls,
        max_narration_calls=prior_budget.max_narration_calls,
        deadline_seconds=prior_budget.deadline_seconds,
        sidecar_calls=prior_budget.sidecar_calls,
        narration_calls=prior_budget.narration_calls,
        records=list(prior_budget.records),
    )
    preliminary_signals = extract_query_signals(query_text, query_understanding)
    from app.query_understanding.soc_investigation_shape import detect_broad_hunt_guidance_request

    provider_configured = intent_advisor_provider_configured()
    primary_use_case_id = (candidate_mappings.get("use_case_ids") or [None])[0]
    preplan_lifecycle = _preplan_promotion_lifecycle_for_llm_skip(qu, primary_use_case_id)
    catalog_row = catalog_authority_row(primary_use_case_id)
    registry_warnings = (
        list(getattr(qu, "registry_warnings", None) or []) if qu is not None else None
    )
    skip_advisory, skip_reason = should_skip_sidecar(
        match_path=candidate_mappings.get("match_path"),
        registry_warnings=registry_warnings,
        catalog_row=catalog_row,
        promotion_lifecycle_summary=preplan_lifecycle,
    )
    # Frozen-T0 intent authority (exact-105, exact-105 + catalogue, or a catalogue
    # row with t0_exact_authority) whose route cannot change. When such a row is
    # demoted only for answer-authority/enrichment reasons (e.g.
    # row_authority_not_ready), should_skip_sidecar keeps the advisor on the live
    # path — and the intent advisor cannot supply the deterministic SPL binding a
    # review-only template row is missing. Rather than skip the advisory hop
    # outright (the weak-exact-105 row is still allowed to consult the LLM when it
    # is fast), sharply bound its wall-clock so a slow/timing-out call (q0.q046,
    # ~100s) falls back deterministically in a few seconds instead.
    bound_intent_advisor = not skip_advisory and sidecar_intent_is_t0(
        candidate_mappings.get("match_path"),
        catalog_row=catalog_row,
        registry_warnings=registry_warnings,
    )
    if detect_broad_hunt_guidance_request(query_text) or (
        routed_skill == "guided_investigation"
        and preliminary_signals.get("guidance_request")
    ):
        skip_advisory = True
        skip_reason = "guided_hunt_deterministic_routing"
    guided_skip, guided_skip_reason = should_skip_intent_advisor_for_guided(
        routed_skill=routed_skill,
        query_signals=preliminary_signals,
    )
    if guided_skip:
        skip_advisory = True
        skip_reason = guided_skip_reason or "guided_route_locked_skip_intent_advisor"
    if (
        not skip_advisory
        and _high_confidence_registry_match_t0(qu)
        and can_skip_llm_for_t0(preplan_lifecycle)
    ):
        skip_advisory = True
        skip_reason = "registry_backed_high_confidence_t0"
    intent_advisory_not_required_for_universal_utility_route = False
    intent_advisor_skip_reason: str | None = None
    budget_reallocated_to_spl_drafting = False
    utility_skip, utility_skip_reason = should_skip_intent_for_universal_utility_spl(
        query_text,
        preliminary_signals,
    )
    if utility_skip:
        skip_advisory = True
        skip_reason = utility_skip_reason
        intent_advisory_not_required_for_universal_utility_route = True
        intent_advisor_skip_reason = utility_skip_reason
        budget_reallocated_to_spl_drafting = True
    if (
        skip_advisory
        and skip_reason not in {
            "deterministic_exact_match_t0",
            "registry_backed_high_confidence_t0",
            "guided_hunt_deterministic_routing",
            "guided_route_locked_skip_intent_advisor",
        }
        and should_prioritize_intent_advisor(
        query_text,
        qu,
        candidate_mappings,
        preliminary_signals,
        )
    ):
        skip_advisory = False
        skip_reason = None
    if not skip_advisory:
        _consumable, _no_consumer_reason = intent_advisor_consumable(
            match_path=candidate_mappings.get("match_path"),
            signals=preliminary_signals if isinstance(preliminary_signals, dict) else None,
            query=query_text,
            t0_weak_row=bound_intent_advisor,
        )
        if not _consumable:
            skip_advisory = True
            skip_reason = _no_consumer_reason
    skip_policy = skip_reason
    bound_t2_intent_advisor, t2_bound_reason = should_bound_t2_intent_advisor(
        match_path=candidate_mappings.get("match_path"),
        catalog_row=catalog_row,
        registry_warnings=registry_warnings,
        skip_advisory=skip_advisory,
        preliminary_signals=preliminary_signals,
    )
    elapsed_before_call_ms = intent_elapsed_before_call_ms(budget)

    def _scheduling_trace(
        *,
        fallback_reason: str | None,
        route_after_skip: str | None = None,
        bound_reason: str | None = None,
        bound_timeout_seconds: float | None = None,
        dropped_reasons: list[str] | None = None,
        llm_called: bool = False,
        adjudication_status: str | None = None,
        proceeded_without_intent_wait: bool = False,
    ) -> dict[str, Any]:
        trace = build_intent_scheduling_trace(
            budget=budget,
            skip_policy=skip_policy,
            provider_configured=provider_configured,
            elapsed_before_call_ms=elapsed_before_call_ms,
            fallback_reason_if_skipped=fallback_reason,
            route_selected_after_skip=route_after_skip,
        )
        effective_bound = bound_timeout_seconds
        if bound_reason is not None and effective_bound is None:
            effective_bound = _FROZEN_T0_INTENT_ADVISOR_BOUND_SECONDS
        enriched = enrich_intent_advisory_trace(
            trace,
            bound_reason=bound_reason,
            bound_timeout_seconds=effective_bound,
            dropped_reasons=dropped_reasons,
            llm_called=llm_called,
            adjudication_status=adjudication_status,
        )
        enriched.update(
            {
                "deterministic_route_proceeded_without_waiting_for_intent": (
                    proceeded_without_intent_wait
                ),
                "intent_advisory_not_required_for_universal_utility_route": (
                    intent_advisory_not_required_for_universal_utility_route
                ),
                "intent_advisor_skip_reason": intent_advisor_skip_reason,
                "budget_reallocated_to_spl_drafting": budget_reallocated_to_spl_drafting,
            }
        )
        return enriched

    # Stage-1 dispatch decision — mirrors the deterministic skip outcome so flag-on
    # gating introduces no divergence; the only flag-on effect is the mode-specific
    # 2C prompt. Always recorded for observability; authoritative only when the
    # pipeline-dispatch flag is on.
    from app.chat.contracts.intent_dispatch import build_intent_dispatch

    intent_dispatch = build_intent_dispatch(
        skip_advisory=bool(skip_advisory),
        skip_reason=skip_reason,
        routed_skill=routed_skill,
        signals=preliminary_signals if isinstance(preliminary_signals, dict) else {},
        requires_clarification=bool(getattr(qu, "requires_clarification", False)),
    )
    state["intent_dispatch"] = intent_dispatch.model_dump()
    dispatch_v2_on = bool(getattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", False))
    _intent_prompt_mode = intent_dispatch.prompt_mode if dispatch_v2_on else None

    if skip_advisory:
        fallback = skip_reason or "deterministic_exact_match_t0"
        llm_advisory = LLMIntentAdvisory(
            dropped_reasons=[fallback],
            scheduling_trace=_scheduling_trace(
                fallback_reason=fallback,
                route_after_skip=routed_skill,
                proceeded_without_intent_wait=True,
            ),
        )
    elif (hop_block := intent_advisor_hop_blocked(budget)):
        llm_advisory = LLMIntentAdvisory(
            dropped_reasons=[hop_block],
            scheduling_trace=_scheduling_trace(
                fallback_reason=hop_block,
                route_after_skip=routed_skill,
                proceeded_without_intent_wait=True,
            ),
        )
    else:
        _intent_timeout = budget.capped_hop_timeout_seconds(role="intent_shadow_classifier")
        _bound_reason = None
        _bound_timeout_seconds: float | None = None
        if bound_intent_advisor:
            _bound_reason = "exact_template_bound_intent_advisor_bounded"
            _bound_timeout_seconds = _FROZEN_T0_INTENT_ADVISOR_BOUND_SECONDS
        elif bound_t2_intent_advisor:
            _bound_reason = t2_bound_reason
            _bound_timeout_seconds = t2_intent_advisor_bound_seconds()
        if _intent_timeout is not None and _bound_timeout_seconds is not None:
            # Frozen-T0 and T2 review-only rows: cap the advisory hop so a slow or
            # timing-out call falls back deterministically (advisory-only; route
            # authority stays deterministic).
            _intent_timeout = min(_intent_timeout, _bound_timeout_seconds)
        if _intent_timeout is None:
            llm_advisory = LLMIntentAdvisory(
                dropped_reasons=["insufficient_deadline_reserve"],
                scheduling_trace=_scheduling_trace(
                    fallback_reason="insufficient_deadline_reserve",
                    route_after_skip=routed_skill,
                    bound_reason=_bound_reason,
                    proceeded_without_intent_wait=True,
                ),
            )
        else:
            _t0 = time.monotonic()
            llm_advisory = generate_llm_intent_advisory(
                query_text,
                query_understanding=query_understanding,
                candidate_mappings=candidate_mappings,
                routed_skill=routed_skill,
                timeout_seconds=_intent_timeout,
                allow_failover=(not budget.time_budget_exhausted())
                and not bound_intent_advisor
                and not bound_t2_intent_advisor,
                prompt_mode=_intent_prompt_mode,
            )
            if llm_advisory.llm_called:
                outcome = "completed"
                if "llm_timed_out" in llm_advisory.dropped_reasons:
                    outcome = "timed_out"
                elif llm_advisory.dropped_reasons:
                    outcome = "dropped"
                budget.record_sidecar(
                    role="intent_shadow_classifier",
                    provider_label=llm_advisory.provider_label,
                    outcome=outcome,
                    latency_ms=int((time.monotonic() - _t0) * 1000),
                )
            llm_advisory = llm_advisory.model_copy(
                update={
                    "scheduling_trace": _scheduling_trace(
                        fallback_reason=(
                            llm_advisory.dropped_reasons[0]
                            if llm_advisory.dropped_reasons
                            else None
                        ),
                        route_after_skip=routed_skill,
                        bound_reason=_bound_reason,
                        bound_timeout_seconds=_bound_timeout_seconds,
                        dropped_reasons=llm_advisory.dropped_reasons,
                        llm_called=llm_advisory.llm_called,
                        adjudication_status=llm_advisory.adjudication_status,
                    ),
                }
            )
    deterministic_shape = classify_answer_shape(query_text).primary_shape
    if (shape_hop_block := budget.sidecar_hop_blocked(role="shape_advisor")):
        shape_advisory = {
            "role": "shape_advisor",
            "deterministic_shape": deterministic_shape,
            "skipped_reason": shape_hop_block,
            "used": False,
        }
        answer_shape_override = None
    else:
        _shape_started = time.monotonic()
        shape_result = generate_shape_advisory(
            query_text,
            deterministic_shape=deterministic_shape,
            timeout_seconds=min(10.0, budget.capped_hop_timeout_seconds(role="shape_advisor") or 10.0),
        )
        shape_result = apply_shape_advisory_promotion(query_text, shape_result)
        if shape_result.llm_called:
            budget.record_sidecar(
                role="shape_advisor",
                provider_label=shape_result.provider_label,
                outcome="timed_out" if shape_result.timed_out else "completed",
                latency_ms=int((time.monotonic() - _shape_started) * 1000),
            )
        shape_advisory = shape_result.to_trace()
        answer_shape_override = shape_result.promoted_shape if shape_result.used else None
        if answer_shape_override == "reference_taxonomy" and isinstance(routed, dict):
            routed = {
                **routed,
                "skill": "knowledge_recall",
                "tool_plan": [],
                "shape_advisory_promotion": "reference_taxonomy",
            }
            routed_skill = "knowledge_recall"

    if isinstance(routed, dict):
        _pre_use_case, routed, candidate_mappings = apply_live_catalogue_bind(
            query=query_text,
            query_understanding=query_understanding,
            selected_use_case=None,
            routed=routed,
            candidate_mappings=candidate_mappings,
        )

    result = build_query_to_intent(
        query=query_text,
        query_understanding=query_understanding,
        routed_skill=routed_skill,
        routing_provenance=routed.get("routing_provenance")
        if isinstance(routed.get("routing_provenance"), dict)
        else None,
        llm_intent_advisory=llm_advisory,
        answer_shape_override=answer_shape_override,
    )
    payload = result.model_dump()
    signals = payload.get("query_signals") if isinstance(payload.get("query_signals"), dict) else None
    if routed_skill == "guided_investigation":
        selected_use_case = None
    else:
        selected_use_case = _selected_use_case(query_text, query_signals=signals)
    selected_use_case, routed, candidate_mappings = apply_live_catalogue_bind(
        query=query_text,
        query_understanding=query_understanding,
        selected_use_case=selected_use_case,
        routed=routed if isinstance(routed, dict) else {},
        candidate_mappings=candidate_mappings,
    )
    payload = {
        **payload,
        "candidate_mappings": {
            **(payload.get("candidate_mappings") if isinstance(payload.get("candidate_mappings"), dict) else {}),
            **candidate_mappings,
        },
    }
    return {
        **state,
        "query_to_intent": payload,
        # Preserve the validated model at the node boundary.  The serialized copy
        # remains in query_to_intent for the wire/trace contract, while live
        # consumers receive the typed advisory and cannot silently lose fields.
        "llm_intent_advisory": result.llm_intent_advisory,
        "shape_advisory": shape_advisory,
        "routed": routed,
        "intent_classification": payload.get("intent_classification"),
        "selected_use_case": selected_use_case,
        "llm_turn_budget": budget,
    }


def _high_confidence_registry_match_t0(query_understanding: Any | None) -> bool:
    if query_understanding is None:
        return False
    match_path = str(getattr(query_understanding, "deterministic_match_path", "") or "")
    if match_path not in {"near_105_question", "semantic_105_question"}:
        return False
    if getattr(query_understanding, "registry_warnings", None):
        return False
    question_ref = getattr(query_understanding, "mapped_question_ref", None)
    if not isinstance(question_ref, str) or not question_ref.strip():
        return False
    score = getattr(query_understanding, "question_registry_match_score", None)
    return isinstance(score, (int, float)) and float(score) >= 0.95


def _preplan_promotion_lifecycle_for_llm_skip(
    query_understanding: Any | None,
    primary_use_case_id: Any,
) -> dict[str, Any] | None:
    """Read-only lifecycle projection for intent-advisor skip scheduling."""
    if query_understanding is None:
        return None
    question_ref = getattr(query_understanding, "mapped_question_ref", None)
    row_summary: dict[str, Any] | None = None
    if isinstance(question_ref, str) and question_ref.strip():
        entry = question_runtime_entry(question_ref.strip())
        if entry is not None:
            status, blockers = classify_runtime_row_authority(entry)
            row_summary = {
                "question_ref": str(entry.get("question_ref") or question_ref),
                "row_authority_status": status,
                "s3_authority_ready": project_s3_authority_ready(status),
                "promotion_status": entry.get("promotion_status"),
                "manifest_coverage_id": entry.get("manifest_coverage_id"),
                "blockers": blockers,
            }
    pack = reviewed_answer_pack(
        case_id=str(question_ref) if isinstance(question_ref, str) else None,
        use_case_id=str(primary_use_case_id) if primary_use_case_id else None,
    )
    pack_summary = answer_pack_summary(pack) if pack is not None else None
    lifecycle = effective_promotion_status(
        stored_promotion_status=(row_summary or {}).get("promotion_status") if row_summary else None,
        row_authority_summary=row_summary,
        answer_pack_summary=pack_summary,
    )
    if lifecycle["stored_promotion_status"] or lifecycle["demotion_reasons"] or pack_summary:
        return lifecycle
    return None


def _attach_pipeline_dispatch_if_enabled(
    state: ChatPipelineState,
    *,
    evidence_plan: dict[str, Any] | None,
    planning_decision: dict[str, Any] | None,
) -> ChatPipelineState:
    if not bool(getattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", False)):
        return state
    dispatch = build_pipeline_dispatch(
        evidence_plan=evidence_plan,
        route_contract=state.get("route_contract"),
        query_to_intent=state.get("query_to_intent"),
        intent_classification=state.get("intent_classification"),
        query_understanding=state.get("query_understanding"),
        routed=state.get("routed"),
        selected_use_case=state.get("selected_use_case"),
        planning_decision=planning_decision,
    )
    return {**state, "pipeline_dispatch": dispatch.model_dump(mode="json")}


def _active_recipe(state: ChatPipelineState) -> Any | None:
    """O5c: the recipe for this turn, if any.

    `mcp_recipe_id` is set by the item-3.2 selector on first entry into
    graph_node_evidence_planning for out_of_registry / near_105_question turns
    whose answer shape matches a recipe. Every other turn returns None here and
    falls through to the chronology behavior.
    """
    recipe_id = state.get("mcp_recipe_id")
    if not isinstance(recipe_id, str) or not recipe_id:
        return None
    return get_recipe(recipe_id)


def _observer_already_called(state: ChatPipelineState) -> bool:
    trace = state.get("evidence_observer_trace")
    if isinstance(trace, dict) and int(trace.get("invocation_count") or 0) >= OBSERVER_MAX_CALLS_PER_TURN:
        return True
    structured = state.get("structured_context")
    return bool(isinstance(structured, dict) and structured.get("llm_observations"))


def _rows_from_execution_for_observer(execution: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(execution, dict):
        return []
    raw = execution.get("raw_result")
    if isinstance(raw, dict) and isinstance(raw.get("rows"), list):
        return [row for row in raw["rows"] if isinstance(row, dict)]
    preview = execution.get("results_preview")
    if isinstance(preview, list):
        return [row for row in preview if isinstance(row, dict)]
    return []


def _rows_from_terminal_discovery_for_observer(state: ChatPipelineState, decision: Any) -> list[dict[str, Any]]:
    if getattr(decision, "route", None) == ROUTE_DISCOVERY_HOP:
        return []
    evidence = state.get("mcp_evidence")
    if not isinstance(evidence, list) or not evidence:
        return []
    latest = evidence[-1]
    if not isinstance(latest, dict):
        return []
    payload = latest.get("payload")
    if not isinstance(payload, dict):
        return []
    for key in ("preview_rows", "rows", "results_preview"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def _evidence_observer_prompt(state: ChatPipelineState, rows: list[dict[str, Any]]) -> tuple[str, dict[int, str], int]:
    request = state.get("request")
    query = str(state.get("effective_query") or getattr(request, "message", "") or "")
    facts = harvest_canonical_facts_from_state(state).model_dump(mode="json")
    sanitized = sanitize_rows_for_observer(rows)
    prompt = (
        "Analyst question:\n"
        f"{query}\n\n"
        "Canonical facts:\n"
        f"{facts}\n\n"
        "Numbered sanitized MCP rows:\n"
        f"{sanitized.prompt_text}\n"
    )
    return prompt, sanitized.row_text_by_index, sanitized.injection_withheld_count


def _persist_evidence_observer_trace(state: ChatPipelineState, trace: dict[str, Any]) -> None:
    trace_id = state.get("trace_id")
    if not isinstance(trace_id, str) or not trace_id:
        return
    safe_trace = dict(trace)
    try:
        telemetry = get_telemetry_connector()
        telemetry.record_llm_call(
            trace_id,
            role=EVIDENCE_OBSERVER_ROLE,
            event_type="evidence_observer",
            provider_label=safe_trace.get("provider_label"),
            latency_ms=safe_trace.get("latency_ms"),
            guard_status=safe_trace.get("guard_status"),
            grounded_n=safe_trace.get("grounded_n"),
            dropped_m=safe_trace.get("dropped_m"),
            skipped_reason=safe_trace.get("skipped_reason"),
            injection_withheld_row_count=safe_trace.get("injection_withheld_row_count"),
            hint_accepted=safe_trace.get("observer_hint_accepted"),
            hint_rejected=safe_trace.get("observer_hint_rejected"),
            hint_rejected_reason=safe_trace.get("observer_hint_rejected_reason"),
        )
        telemetry.merge_run_metadata(
            trace_id,
            {"control_plane_trace": {"evidence_observer": safe_trace}},
        )
    except Exception:  # noqa: BLE001 - telemetry must never break chat
        logger.warning("evidence_observer_telemetry_failed", exc_info=True)


def _state_with_evidence_observer_trace(
    state: ChatPipelineState,
    trace: dict[str, Any],
    *,
    budget: TurnLlmBudget | None = None,
    structured_context: dict[str, Any] | None = None,
) -> ChatPipelineState:
    _persist_evidence_observer_trace(state, trace)
    out: ChatPipelineState = {**state, "evidence_observer_trace": trace}
    if budget is not None:
        out["llm_turn_budget"] = budget
    if structured_context is not None:
        out["structured_context"] = structured_context
    return out


def _attach_evidence_observer(state: ChatPipelineState, *, rows: list[dict[str, Any]]) -> ChatPipelineState:
    if _observer_already_called(state) or not rows:
        return state
    trace: dict[str, Any] = {
        "role": EVIDENCE_OBSERVER_ROLE,
        "invocation_count": 0,
        "grounded_n": 0,
        "dropped_m": 0,
    }
    if not (
        settings.ai_soc_llm_final_synthesis_enabled
        and settings.ai_soc_llm_live_synthesis_enabled
    ):
        trace["skipped_reason"] = "live_synthesis_disabled"
        return _state_with_evidence_observer_trace(state, trace)

    budget = state.get("llm_turn_budget") or TurnLlmBudget()
    hop_block = budget.sidecar_hop_blocked(role=EVIDENCE_OBSERVER_ROLE)
    if hop_block:
        trace["skipped_reason"] = hop_block
        return _state_with_evidence_observer_trace(state, trace, budget=budget)
    timeout_seconds = budget.capped_hop_timeout_seconds(role=EVIDENCE_OBSERVER_ROLE)
    if timeout_seconds is None:
        trace["skipped_reason"] = "insufficient_deadline_reserve"
        return _state_with_evidence_observer_trace(state, trace, budget=budget)

    prompt, row_text_by_index, withheld_count = _evidence_observer_prompt(state, rows)
    trace["injection_withheld_row_count"] = withheld_count
    started = time.monotonic()
    invocation = invoke_sidecar_role_with_metadata(
        role=EVIDENCE_OBSERVER_ROLE,
        user_prompt=prompt,
        max_tokens=256,
        timeout_seconds=timeout_seconds,
        temperature=0.0,
        allow_failover=not budget.time_budget_exhausted(),
    )
    latency_ms = int((time.monotonic() - started) * 1000)
    trace.update(
        {
            "invocation_count": 1,
            "provider_label": invocation.answered_label,
            "latency_ms": latency_ms,
            "timed_out": invocation.timed_out,
        }
    )
    budget.record_sidecar(
        role=EVIDENCE_OBSERVER_ROLE,
        provider_label=invocation.answered_label,
        outcome="timed_out" if invocation.timed_out else "completed",
        latency_ms=latency_ms,
    )
    if not invocation.raw_output:
        trace["skipped_reason"] = "no_model_output"
        return _state_with_evidence_observer_trace(state, trace, budget=budget)

    parsed = parse_evidence_observer_output(invocation.raw_output)
    trace["parse_accepted"] = parsed.accepted
    if not parsed.accepted:
        trace["guard_status"] = "parse_failed"
        trace["warnings"] = list(parsed.warnings)
        trace["errors"] = list(parsed.errors)
        return _state_with_evidence_observer_trace(state, trace, budget=budget)

    grounded = ground_evidence_observations(
        parsed.governed_observations,
        row_text_by_index=row_text_by_index,
    )
    observations = [item.model_dump(mode="json") for item in grounded.grounded_observations]
    trace.update(
        {
            "guard_status": "grounded",
            "grounded_n": grounded.grounded_count,
            "dropped_m": grounded.dropped_count,
            "dropped_reasons": [
                {"reason": item.reason, "detail": item.detail}
                for item in grounded.dropped
            ],
            "next_hop_hint": parsed.next_hop_hint,
        }
    )
    structured = dict(state.get("structured_context") or {})
    if observations:
        structured["llm_observations"] = [
            *list(structured.get("llm_observations") or []),
            *observations,
        ]
    return _state_with_evidence_observer_trace(
        state,
        trace,
        budget=budget,
        structured_context=structured,
    )


def _graph_node_planning_decision_from_canonical(state: ChatPipelineState) -> ChatPipelineState:
    """Attach planning_decision when evidence_plan was produced by canonical final planner."""
    from app.chat.canonical_mode import build_canonical_failure_state, is_canonical_authoritative
    from app.chat.canonical_outcome_read import OutcomeReadKind, read_canonical_planning_outcome

    intent = state.get("intent_classification")
    evidence_payload = state.get("evidence_plan")

    read = read_canonical_planning_outcome(state)
    if read.kind != OutcomeReadKind.VALID or read.outcome is None:
        return build_canonical_failure_state(
            state,
            outcome="planning_failed",
            reason="canonical_invalid_outcome_for_planning_decision",
        )

    canonical_outcome = read.outcome
    if canonical_outcome.status != "planned" and isinstance(intent, dict):
        # A non-planned outcome has no EvidencePlan by contract, but the planning
        # decision must still be computed: ``path_type`` is what drives the unsafe /
        # clarification branches downstream. Treating a missing EvidencePlan as a
        # planning failure here silently downgraded blocked containment requests from
        # "unsafe_action_blocked" to "policy_checks_passed".
        planning = plan_path_and_tools(
            intent_classification=intent,
            evidence_plan=None,
            routed=state.get("routed"),
            query_understanding=state.get("query_understanding"),
            selected_use_case=state.get("selected_use_case"),
            llm_intent_advisory=state.get("llm_intent_advisory"),
        )
        return {**state, "planning_decision": planning.model_dump()}

    if not isinstance(intent, dict) or not isinstance(evidence_payload, dict):
        return build_canonical_failure_state(
            state,
            outcome="planning_failed",
            reason="canonical_missing_planning_artifacts",
        )
    if is_canonical_authoritative() and not evidence_payload.get("resource_plan"):
        return build_canonical_failure_state(
            state,
            outcome="planning_failed",
            reason="canonical_missing_resource_plan",
        )
    planning = plan_path_and_tools(
        intent_classification=intent,
        evidence_plan=evidence_payload,
        routed=state.get("routed"),
        query_understanding=state.get("query_understanding"),
        selected_use_case=state.get("selected_use_case"),
        llm_intent_advisory=state.get("llm_intent_advisory"),
    )
    planning_payload = planning.model_dump()
    route_adjudication_payload = _route_adjudication_with_final_plan_drift(
        state.get("route_adjudication"),
        evidence_payload,
    )
    next_state = {
        **state,
        "planning_decision": planning_payload,
        "route_adjudication": route_adjudication_payload,
    }
    return _attach_pipeline_dispatch_if_enabled(
        next_state,
        evidence_plan=evidence_payload,
        planning_decision=planning_payload,
    )


def graph_node_evidence_planning(state: ChatPipelineState) -> ChatPipelineState:
    from app.chat.canonical_mode import build_canonical_failure_state, is_canonical_authoritative

    if (
        is_canonical_authoritative()
        and not loop_initialized(state)
        and not state.get("legacy_langgraph_harness")
    ):
        return build_canonical_failure_state(
            state,
            outcome="planning_failed",
            reason="canonical_forbids_legacy_evidence_planning",
        )
    # Stage 4B: on loop re-entry (after an mcp_call discovery hop or the gated
    # execution hop) the HUB only re-assesses + routes — it must NOT re-emit
    # progress, re-route, or re-compose the plan (idempotency, plan bug #2).
    if loop_initialized(state):
        execution = state.get("execution") if "execution" in state else None
        recipe = _active_recipe(state)
        if recipe is not None:
            pending_call_id = state.get("mcp_recipe_pending_call_id")
            if isinstance(execution, dict) and isinstance(pending_call_id, str) and pending_call_id:
                state = {**state, **record_recipe_call(state, call_id=pending_call_id, execution=execution)}
            decision = assess_loop_with_recipe(state, recipe)
            next_state = {**state, "mcp_loop": decision.to_dict()}
            if decision.next_tool:
                next_state["mcp_recipe_pending_call_id"] = decision.next_tool
            return next_state
        observer_rows = _rows_from_execution_for_observer(execution if isinstance(execution, dict) else None)
        if isinstance(execution, dict):
            state = {**state, **record_execution_hop(state, execution)}
        decision = assess_loop(
            state,
            execution=execution,
            broaden_eligible=_loop_broaden_eligible(state),
        )
        if not observer_rows:
            observer_rows = _rows_from_terminal_discovery_for_observer(state, decision)
        state = _attach_evidence_observer(state, rows=observer_rows)
        hint_patch = apply_observer_next_hop_hint(state)
        if hint_patch:
            state = {**state, **hint_patch}
            if isinstance(state.get("evidence_observer_trace"), dict):
                _persist_evidence_observer_trace(state, state["evidence_observer_trace"])
            if hint_patch.get("mcp_chronology"):
                decision = assess_loop(
                    state,
                    execution=execution,
                    broaden_eligible=_loop_broaden_eligible(state),
                )
        next_state: ChatPipelineState = {**state, "mcp_loop": decision.to_dict()}
        if "data_silence" in decision.reason:
            next_state["data_silence_advisory"] = build_data_silence_advisory(state)
        return next_state
    emit_stage("planning_evidence")
    intent = state.get("intent_classification")
    if not isinstance(intent, dict):
        planning = plan_path_and_tools(
            intent_classification=None,
            evidence_plan=None,
            routed=state.get("routed"),
            query_understanding=state.get("query_understanding"),
            selected_use_case=state.get("selected_use_case"),
            llm_intent_advisory=state.get("llm_intent_advisory"),
        )
        planning_payload = planning.model_dump()
        next_state = {**state, "evidence_plan": None, "planning_decision": planning_payload}
        return _attach_pipeline_dispatch_if_enabled(
            next_state,
            evidence_plan=None,
            planning_decision=planning_payload,
        )
    _req_for_evidence = state.get("request")
    plan = plan_evidence(
        intent,
        query_to_intent=state.get("query_to_intent"),
        routed=state.get("routed"),
        query_understanding=state.get("query_understanding"),
        selected_use_case=state.get("selected_use_case"),
        user_query=getattr(_req_for_evidence, "message", None) if _req_for_evidence is not None else None,
    )
    evidence_payload = plan.model_dump()
    if isinstance(evidence_payload.get("resource_plan"), dict):
        floor_plan = ResourcePlan.model_validate(evidence_payload["resource_plan"])
        _match_path = getattr(state.get("query_understanding"), "deterministic_match_path", None)
        _budget = state.get("llm_turn_budget")
        _planner_started = time.monotonic()
        merged_plan, llm_planner_called = apply_llm_primary_resource_plan(
            floor_plan,
            query=str(getattr(_req_for_evidence, "message", "") or ""),
            match_path=str(_match_path) if _match_path is not None else None,
            action_mode=str(evidence_payload.get("action_mode") or "") or None,
            mcp_allowed=bool(evidence_payload.get("mcp_allowed")),
            budget=_budget if isinstance(_budget, TurnLlmBudget) else None,
        )
        evidence_payload["resource_plan"] = merged_plan.model_dump()
        if llm_planner_called and isinstance(_budget, TurnLlmBudget):
            record_planner_sidecar(_budget, started_at=_planner_started)
    evidence_payload["mcp_allowed_normalized"] = _mcp_allowed_decision_from_plan(evidence_payload)
    workflow_plan = state.get("workflow_plan")
    if (
        evidence_payload.get("answer_mode") == "spl_utility_authoring"
        and isinstance(workflow_plan, dict)
    ):
        state = {**state, "workflow_plan": _strip_rag_from_workflow_plan(workflow_plan)}
    route_adjudication_payload = _route_adjudication_with_final_plan_drift(
        state.get("route_adjudication"),
        evidence_payload,
    )
    planning = plan_path_and_tools(
        intent_classification=intent,
        evidence_plan=evidence_payload,
        routed=state.get("routed"),
        query_understanding=state.get("query_understanding"),
        selected_use_case=state.get("selected_use_case"),
        llm_intent_advisory=state.get("llm_intent_advisory"),
    )
    planning_payload = planning.model_dump()
    if not _mcp_evidence_loop_enabled(state, evidence_payload):
        next_state = {
            **state,
            "evidence_plan": evidence_payload,
            "planning_decision": planning_payload,
            "route_adjudication": route_adjudication_payload,
        }
        return _attach_pipeline_dispatch_if_enabled(
            next_state,
            evidence_plan=evidence_payload,
            planning_decision=planning_payload,
        )
    discovery_only = (
        evidence_payload.get("discovery_allowed") is True
        and evidence_payload.get("mcp_allowed") is not True
    )
    # O5c (item 3.4, 2026-07-03): select a governed recipe for this turn, if
    # any. This is the live-invocation step items 3.1-3.3 deliberately left
    # dormant — select_recipe_for_plan is a pure function; the recipe path
    # itself was already built and langgraph-verified in items 3.1-3.3.
    # Scoped to out-of-registry/near-105 paths ONLY (same _TRIGGER_MATCH_PATHS
    # set llm_plan_bridge.py already uses for the same reason) — this plan is
    # explicitly about out-of-catalogue resource planning; sweeping in-catalogue
    # traffic into the newer, less-proven recipe/O5c dispatch mechanism instead
    # of the established chronology path broke 5 pinned tests when tried
    # unscoped (same query text, same shape, previously chronology-routed).
    _resource_plan_for_shape = evidence_payload.get("resource_plan")
    # match_path must come from the just-composed plan's own provenance:
    # state["evidence_plan"]/["planning_decision"] are not set yet at this point
    # (they are still the local payloads), and routed.routing_provenance uses the
    # key "deterministic_match_path" — so _match_path_from_state(state) returned
    # None here on every first-entry turn and the recipe block never fired live.
    _recipe_match_path = None
    if isinstance(_resource_plan_for_shape, dict):
        _recipe_match_path = (_resource_plan_for_shape.get("provenance") or {}).get("match_path")
    _recipe_match_path = _recipe_match_path or _match_path_from_state(state)
    if isinstance(_resource_plan_for_shape, dict) and _recipe_match_path in {
        "out_of_registry",
        "near_105_question",
    }:
        _shape_query = state.get("effective_query") or state["request"].message
        _shape_result = classify_answer_shape(_shape_query, resource_plan=_resource_plan_for_shape)
        _selected_recipe_id = select_recipe_for_plan(
            resource_plan_purposes=plan_purposes_from_resource_plan(_resource_plan_for_shape),
            answer_shape=_shape_result.primary_shape,
            mcp_allowed=bool(evidence_payload.get("mcp_allowed")),
            discovery_allowed=bool(evidence_payload.get("discovery_allowed")),
        )
        if _selected_recipe_id:
            state = {**state, "mcp_recipe_id": _selected_recipe_id}
    # O5c (item 3.1): a recipe-driven turn skips chronology composition entirely
    # — the scheduler decides call order from the recipe, not a fixed sequence.
    active_recipe = _active_recipe(state)
    if active_recipe is not None:
        loop_init: dict[str, Any] = {"mcp_call_records": [], "mcp_hops_done": 0}
        loop_planner = {"source": "recipe", "recipe_id": active_recipe.recipe_id}
        first_decision = assess_loop_with_recipe(loop_init, active_recipe)
        next_state = {
            **state,
            "evidence_plan": evidence_payload,
            "planning_decision": planning_payload,
            "route_adjudication": route_adjudication_payload,
            **loop_init,
            "mcp_discovery_only": discovery_only,
            "mcp_loop_planner": loop_planner,
            "mcp_loop": first_decision.to_dict(),
        }
        if first_decision.next_tool:
            next_state["mcp_recipe_pending_call_id"] = first_decision.next_tool
        return _attach_pipeline_dispatch_if_enabled(
            next_state,
            evidence_plan=evidence_payload,
            planning_decision=planning_payload,
        )
    # Stage 4B: compose the reviewed discovery chronology once, so the HUB can
    # drive read-only mcp_call hops before the linear SPL/execution chain.
    chronology, loop_planner = _resolve_loop_chronology(state, spl_approved=False)
    loop_init = initialize_loop(
        chronology,
        required_produces=_loop_required_produces(evidence_payload),
    )
    loop_state = {**loop_init, "mcp_discovery_only": discovery_only}
    next_state = {
        **state,
        "evidence_plan": evidence_payload,
        "planning_decision": planning_payload,
        "route_adjudication": route_adjudication_payload,
        **loop_init,
        "mcp_discovery_only": discovery_only,
        "mcp_loop_planner": loop_planner,
        "mcp_loop": assess_loop(loop_state).to_dict(),
    }
    return _attach_pipeline_dispatch_if_enabled(
        next_state,
        evidence_plan=evidence_payload,
        planning_decision=planning_payload,
    )


# Narrow capability->tool mapping for the ONE discovery capability today's
# shipped recipes use. RecipeCall.resource_capability is a capability label,
# not a concrete MCP tool name; a general capability->tool resolver is out of
# scope for items 3.1-3.3 (recipes have no other discovery capability yet).
_RECIPE_DISCOVERY_CAPABILITY_TOOL = {"metadata_discovery": "splunk_get_indexes"}


def graph_node_mcp_call(state: ChatPipelineState) -> ChatPipelineState:
    """Stage 4B: run one read-only discovery hop, then return to the HUB.

    Execution stays globally gated — discovery hops are planned-only in the
    current air-gapped posture (no live MCP call), so the deliverable records the
    tool's declared `produces` as planned context. `splunk_run_query` is never
    run here; it stays in the gated execution node.
    """
    recipe = _active_recipe(state)
    if recipe is not None:
        decision = assess_loop_with_recipe(state, recipe)
        call_id = decision.next_tool
        if decision.route != ROUTE_DISCOVERY_HOP or not call_id:
            return state
        call = recipe.call_by_id(call_id)
        tool = _RECIPE_DISCOVERY_CAPABILITY_TOOL.get(call.resource_capability) if call is not None else None
        if not tool:
            return state
        hop = execute_loop_discovery_hop(
            tool,
            rbac_role=session_role_for_mcp_gate(state.get("session_role")),
            trace_id=state.get("trace_id"),
        )
        # "planned"/"collected" are both successful discovery outcomes (matches
        # the chronology path's own convention — discovery hops stay
        # planned-only while MCP execution is globally gated, which is not a
        # failure); anything else (e.g. blocked) is a real failure.
        hop_outcome = str(hop.get("outcome") or "")
        delivered = hop.get("delivered") or []
        hop_succeeded = hop_outcome in {"planned", "collected"} and bool(delivered)
        return {
            **state,
            **record_recipe_call(
                state,
                call_id=call_id,
                execution={
                    "status": "executed",
                    "result_count": 1 if hop_succeeded else 0,
                }
                if hop_succeeded
                else {"status": "blocked"},
            ),
        }
    decision = assess_loop(state)
    tool = decision.next_tool
    if decision.route != ROUTE_DISCOVERY_HOP or not tool or tool == "splunk_run_query":
        return state
    hop = execute_loop_discovery_hop(
        tool,
        rbac_role=session_role_for_mcp_gate(state.get("session_role")),
        trace_id=state.get("trace_id"),
    )
    return {
        **state,
        **record_hop(
            state,
            tool=tool,
            delivered=hop["delivered"],
            outcome=str(hop["outcome"]),
            payload=hop.get("payload") if isinstance(hop.get("payload"), dict) else {},
        ),
    }


def _loop_required_produces(evidence_payload: dict[str, Any] | None) -> list[str]:
    """Requirements the loop must satisfy: chronology produces plus any explicit
    evidence-plan needs (so unservable needs like CVE surface as honest gaps)."""
    needs: list[str] = []
    plan = evidence_payload if isinstance(evidence_payload, dict) else {}
    for key in ("missing_evidence", "evidence_needs", "required_produces", "missing_required_evidence"):
        value = plan.get(key)
        if isinstance(value, list):
            needs.extend(str(item) for item in value)
    needs.extend(_row_authority_loop_requirements(plan.get("row_authority_summary")))
    needs.extend(_source_profile_loop_requirements(plan.get("source_profile_binding_summary")))
    return list(dict.fromkeys(item for item in needs if str(item).strip()))


def _row_authority_loop_requirements(summary: Any) -> list[str]:
    if not isinstance(summary, dict):
        return []
    status = str(summary.get("row_authority_status") or "")
    by_status = {
        "exact_known_needs_lookup": "lookup_dependency",
        "exact_known_needs_detection_binding": "detection_binding",
        "exact_known_needs_context_binding": "context_binding",
        "exact_known_needs_clarification": "case_context",
    }
    requirement = by_status.get(status)
    if requirement:
        return [requirement]
    requirements: list[str] = []
    for blocker in summary.get("blockers") or []:
        blocker_text = str(blocker)
        if "lookup" in blocker_text:
            requirements.append("lookup_dependency")
        elif "detection" in blocker_text:
            requirements.append("detection_binding")
        elif "context" in blocker_text:
            requirements.append("context_binding")
        elif "clarification" in blocker_text:
            requirements.append("case_context")
    return list(dict.fromkeys(requirements))


def _source_profile_loop_requirements(summary: Any) -> list[str]:
    if not isinstance(summary, dict):
        return []
    missing = summary.get("source_profile_bindings_missing")
    if isinstance(missing, list) and missing:
        return ["source_profile"]
    return []


def _resolve_vulnerability_source_status(state: ChatPipelineState) -> dict[str, Any] | None:
    """Plan §3 A4: when the evidence plan needs CVE/vulnerability context, resolve
    the operator-vendored CVE snapshot read model into honest provenance.
    """
    return resolve_cve_vulnerability_status(
        required_produces=[str(item) for item in (state.get("mcp_required_produces") or [])],
        evidence_plan=state.get("evidence_plan") if isinstance(state.get("evidence_plan"), dict) else None,
    )


def _mcp_evidence_loop_enabled(state: ChatPipelineState, evidence_payload: dict[str, Any]) -> bool:
    mcp_allowed = _mcp_allowed_decision_from_plan(evidence_payload)["allowed"] is True
    discovery_allowed = evidence_payload.get("discovery_allowed") is True
    if not mcp_allowed and not discovery_allowed:
        return False
    provisional = {**state, "evidence_plan": evidence_payload}
    if _uses_guided_hybrid_dispatch(provisional):
        return False
    if discovery_allowed and not mcp_allowed:
        # Evidence loop for all tiers (2026-07 directive, item 2.2): guided_investigation
        # keeps its unconditional discovery-only admission; other families granted
        # discovery-only (e.g. spl_generation_only without a live-data ask, item 2.1)
        # are admitted too unless they are RAG-only shaped — discovery is read-only
        # and safe regardless of family, so the same exclusion applies as below.
        if evidence_payload.get("answer_mode") == "guided_investigation":
            return True
        return not _uses_rag_only_path(provisional)
    if _uses_rag_only_path(provisional):
        return False
    return True


def _mcp_allowed_decision_from_plan(evidence_plan: dict[str, Any] | None) -> dict[str, Any]:
    plan = evidence_plan if isinstance(evidence_plan, dict) else {}
    if plan.get("mcp_allowed") is True:
        return {
            "allowed": True,
            "source": "evidence_plan",
            "reason": "explicit_true",
        }
    if "mcp_allowed" not in plan:
        return {
            "allowed": False,
            "source": "evidence_plan_missing",
            "reason": "mcp_allowed_unset_fail_closed",
        }
    if plan.get("mcp_allowed") is None:
        return {
            "allowed": False,
            "source": "evidence_plan_null",
            "reason": "mcp_allowed_null_fail_closed",
        }
    return {
        "allowed": False,
        "source": "evidence_plan",
        "reason": "explicit_false",
    }


def _route_adjudication_with_final_plan_drift(
    route_adjudication: Any,
    evidence_payload: dict[str, Any] | None,
) -> Any:
    if not isinstance(route_adjudication, dict):
        return route_adjudication
    plan = evidence_payload if isinstance(evidence_payload, dict) else {}
    normalized = _mcp_allowed_decision_from_plan(plan)
    narrowed: list[str] = []
    if plan.get("needs_mcp") is True and normalized["allowed"] is not True:
        narrowed.append("mcp_execution")
    if plan.get("needs_spl") is True and plan.get("spl_allowed") is not True:
        narrowed.append("spl_generation")
    drift = {
        "status": "capability_narrowed" if narrowed else "aligned",
        "route_preserved": True,
        "selected_route": route_adjudication.get("final_route") or route_adjudication.get("route"),
        "route_family": _route_family(route_adjudication),
        "final_plan_family": _plan_family(plan),
        "capabilities_narrowed": narrowed,
        "mcp_allowed_normalized": normalized,
        "row_authority_status": (
            (plan.get("row_authority_summary") or {}).get("row_authority_status")
            if isinstance(plan.get("row_authority_summary"), dict)
            else None
        ),
    }
    updated = dict(route_adjudication)
    updated["final_evidence_plan_drift"] = drift
    return updated


def _route_family(route_adjudication: dict[str, Any]) -> str | None:
    route = route_adjudication.get("final_route") or route_adjudication.get("route")
    if route is None:
        return None
    return str(route)


def _plan_family(plan: dict[str, Any]) -> str:
    if plan.get("needs_spl"):
        return "spl_generation"
    if plan.get("needs_mcp"):
        return "live_investigation"
    if plan.get("needs_rag"):
        return "knowledge_recall"
    return str(plan.get("answer_mode") or "unknown")


def _resolve_loop_chronology(
    state: ChatPipelineState,
    *,
    spl_approved: bool,
) -> tuple[list[str], dict[str, Any] | None]:
    """Deterministic chronology on the live blocking path by default; the LLM
    planner is invoked only when the advisory flag is on. plan_tool_chronology
    makes a slow on-prem Instruct call — keeping it off the blocking /chat path
    by default is deliberate (PowerGrid latency incident). Either way the result
    is deterministically reviewed and the deterministic default always carries."""
    rbac_role = session_role_for_mcp_gate(state.get("session_role"))
    target_index = _target_index_from_spl_validation(state.get("spl_validation"))
    if not mcp_tool_plan_llm_advisory_enabled():
        return deterministic_default_chronology(spl_approved=spl_approved), {
            "decision_source": "deterministic_default",
            "dropped": [],
            "warnings": [],
            "planner": {"llm_called": False, "skipped_reason": "live_path_deterministic_only"},
        }
    request = state["request"]
    reviewed = plan_tool_chronology(
        request.message,
        target_index=target_index,
        spl_approved=spl_approved,
        rbac_role=rbac_role,
    )
    chronology = list(reviewed.get("approved_tools") or deterministic_default_chronology(spl_approved=spl_approved))
    planner_meta = reviewed.get("planner") if isinstance(reviewed.get("planner"), dict) else None
    return chronology, {
        "decision_source": reviewed.get("decision_source"),
        "dropped": reviewed.get("dropped"),
        "warnings": reviewed.get("warnings"),
        "planner": planner_meta,
    }


def _target_index_from_spl_validation(spl_validation: dict[str, Any] | None) -> str | None:
    if not isinstance(spl_validation, dict):
        return None
    normalized = str(spl_validation.get("normalized_spl") or "")
    match = re.search(r"\bindex\s*=\s*([^\s|]+)", normalized, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _run_discovery_loop_imperative(state: ChatPipelineState) -> ChatPipelineState:
    """Imperative twin: drain discovery hops before the linear chain when CP is on."""
    if not loop_initialized(state):
        return state
    hops = 0
    while hops < MAX_MCP_HOPS:
        route = (state.get("mcp_loop") or {}).get("route")
        if route != ROUTE_DISCOVERY_HOP:
            break
        state = graph_node_mcp_call(state)
        state = graph_node_evidence_planning(state)
        hops += 1
    return state


def graph_node_composed_dispatch(state: ChatPipelineState) -> ChatPipelineState:
    """WS0 composed-plan dispatch node for LangGraph."""
    return execute_plan_dispatch(state, _dispatch_hooks())


def _loop_broaden_eligible(state: ChatPipelineState) -> bool:
    execution = state.get("execution")
    if not isinstance(execution, dict):
        return False
    if execution.get("status") != "executed" or int(execution.get("result_count") or 0) != 0:
        return False
    return _mcp_allowed(state)


def _provisional_evidence_plan_for_adjudication(state: ChatPipelineState) -> dict[str, Any] | None:
    """Intent-only evidence plan for route adjudication tie-break (not final plan)."""
    intent = state.get("intent_classification")
    if not isinstance(intent, dict):
        return None
    plan = plan_evidence(
        intent,
        query_to_intent=state.get("query_to_intent"),
        routed=state.get("routed"),
        query_understanding=state.get("query_understanding"),
        selected_use_case=state.get("selected_use_case"),
    )
    return plan.model_dump()


def graph_node_route_resolution(state: ChatPipelineState) -> ChatPipelineState:
    emit_stage("route_adjudication")
    request = state["request"]
    routed = state["routed"]
    route_plan_shadow = state["route_plan_shadow"]
    apply_intent_operation_bridge_to_shadow(route_plan_shadow, legacy_intent=str(routed["skill"]))
    apply_route_authority_compare_to_shadow(
        route_plan_shadow,
        selected_skill=str(routed["skill"]),
        routing_comparison=routed.get("comparison"),
    )
    route_authority = _route_authority_payload(route_plan_shadow)
    primary_operation = _primary_operation_from_authority(route_plan_shadow, route_authority)
    routing_skill_resolution = resolve_effective_routing_skill(
        selected_skill=str(routed["skill"]),
        route_authority=route_authority,
        primary_operation=primary_operation,
    )
    route_plan_shadow["routing_skill_resolution"] = routing_skill_resolution
    route_plan_shadow["use_case_registry_bridge"] = build_use_case_registry_bridge(request.message)
    if isinstance(route_authority, dict):
        route_authority["legacy_intent_authority"] = routing_skill_resolution.get("legacy_intent_authority", True)
        route_authority["selected_skill_mirror_only"] = not bool(
            routing_skill_resolution.get("legacy_intent_authority", True)
        )
        route_plan_shadow["route_authority_compare"] = route_authority
    apply_question_runtime_map_to_shadow(route_plan_shadow)
    apply_precondition_evaluation_to_shadow(route_plan_shadow)
    if route_plan_shadow.get("candidate_available"):
        route_plan_shadow["supporter_trace"] = build_supporter_trace(
            _route_plan_for_supporters(route_plan_shadow),
            query=request.message,
            shadow=route_plan_shadow,
            runtime_invoked=True,
        )
    _apply_ood_llm_lab_metadata(route_plan_shadow, request.message)
    apply_analyst_summary_shadow(route_plan_shadow)
    comparison = routed.get("comparison", {})
    route_adjudication_payload: dict[str, Any] | None = None
    if isinstance(state.get("intent_classification"), dict):
        llm_advisory = comparison.get("llm_shadow") if isinstance(comparison, dict) else None
        adjudication = adjudicate_control_plane_route(
            deterministic_route=str(routed.get("skill") or "knowledge_recall"),
            llm_advisory=llm_advisory if isinstance(llm_advisory, dict) else None,
            route_plan_shadow=route_plan_shadow,
            evidence_plan=_provisional_evidence_plan_for_adjudication(state),
            intent_classification=state["intent_classification"],
            query_understanding=state.get("query_understanding"),
            message=request.message,
            query_to_intent=state.get("query_to_intent"),
        )
        route_adjudication_payload = adjudication.model_dump()
        routing_skill_resolution = {
            **routing_skill_resolution,
            "effective_skill": adjudication.final_route,
            "skill_resolution": "control_plane_route_adjudication",
            "legacy_intent_authority": False,
            "route_adjudication_authority_source": adjudication.authority_source,
        }
        # Keep the shadow copy in sync with the adjudicated authority; otherwise
        # governance/lineage panels read a stale legacy resolution that
        # contradicts RunContract (effective_skill / skill_resolution drift).
        route_plan_shadow["routing_skill_resolution"] = routing_skill_resolution
    return {
        **state,
        "route_plan_shadow": route_plan_shadow,
        "routing_skill_resolution": routing_skill_resolution,
        "route_adjudication": route_adjudication_payload,
        "comparison": comparison,
        "disagreement": not bool(comparison.get("match", False)),
    }


def graph_node_route_contract(state: ChatPipelineState) -> ChatPipelineState:
    from app.chat.run_contract_builder import build_route_contract  # circular: pipeline state

    route_contract = build_route_contract(state)
    routed = dict(state.get("routed") or {})
    routed["skill"] = route_contract.canonical_skill
    return {
        **state,
        "routed": routed,
        "route_contract": route_contract.model_dump(mode="json"),
    }


def graph_node_shadow_tail(state: ChatPipelineState) -> ChatPipelineState:
    routed = state["routed"]
    route_plan_shadow = state["route_plan_shadow"]
    comparison = routed.get("comparison", {})
    route_adjudication_payload = state.get("route_adjudication")
    llm_plan_validation_payload: dict[str, Any] | None = None
    skill_selection = select_skill_chain(
        routed=routed,
        selected_use_case=state.get("selected_use_case"),
    )
    if should_validate_llm_advisory_plan():
        advisory_plan = build_advisory_plan_from_context(
            comparison=comparison if isinstance(comparison, dict) else None,
            route_plan_shadow=route_plan_shadow,
        )
        q2i = state.get("query_to_intent")
        candidate_mappings = (
            q2i.get("candidate_mappings") if isinstance(q2i, dict) else None
        )
        llm_validation = validate_llm_advisory_plan(
            advisory_plan,
            evidence_plan=state.get("evidence_plan"),
            route_adjudication=route_adjudication_payload if isinstance(route_adjudication_payload, dict) else None,
            intent_classification=state.get("intent_classification"),
            candidate_mappings=candidate_mappings,
        )
        llm_plan_validation_payload = llm_validation.model_dump()
        route_plan_shadow["llm_plan_validation"] = llm_plan_validation_payload
    return {
        **state,
        "route_plan_shadow": route_plan_shadow,
        "llm_plan_validation": llm_plan_validation_payload,
        "skill_selection": skill_selection,
        "selected_skill_chain": skill_selection.selected_chain,
    }


def graph_node_shadow_enrichment(state: ChatPipelineState) -> ChatPipelineState:
    """Backward-compatible wrapper: route resolution → contract → shadow tail."""
    state = graph_node_route_resolution(state)
    state = graph_node_route_contract(state)
    return graph_node_shadow_tail(state)




def graph_node_ensure_workflow_plan(state: ChatPipelineState) -> ChatPipelineState:
    """Plan-only slice of workflow_spl when composed dispatch skips SPL generation."""
    if state.get("workflow_plan"):
        return state
    request = state["request"]
    routed = state["routed"]
    trace_id = state["trace_id"]
    effective_skill = _effective_routing_skill(state)
    workflow_plan = _routes_chat().plan_workflow(
        selected_skill=effective_skill,
        tool_plan=list(routed["tool_plan"]),
        query=request.message,
        trace_id=trace_id,
    )
    return {**state, "workflow_plan": workflow_plan}


def _dispatch_schedule_and_cursor(
    dispatch: dict[str, Any],
) -> tuple[list[PipelineStage], PipelineStage | None]:
    decision = dispatch.get("decision") or {}
    schedule = [
        PipelineStage(s)
        for s in (decision.get("stage_schedule") or [])
        if s in PipelineStage._value2member_map_
    ]
    runtime = dispatch.get("runtime_context") or {}
    cursor_raw = runtime.get("dispatch_cursor") if isinstance(runtime, dict) else None
    cursor = PipelineStage(cursor_raw) if cursor_raw in PipelineStage._value2member_map_ else None
    return schedule, cursor


def _record_dispatch_stage_skip(runtime: dict[str, Any], stage: PipelineStage, reason: str) -> dict[str, Any]:
    trace = dict(runtime.get("scheduling_trace") or {})
    skips = list(trace.get("skipped_stages") or [])
    skips.append({"stage": stage.value, "reason": reason})
    trace["skipped_stages"] = skips
    runtime["scheduling_trace"] = trace
    return runtime


def advance_dispatch_cursor(
    state: ChatPipelineState, stage: PipelineStage | str
) -> ChatPipelineState:
    """Advance dispatch cursor only when ``stage`` is the next scheduled stage.

    Sequential enforcement prevents skipping ``pre_spl_mcp_discovery`` when
    advancing ``workflow_spl``. Records ``cursor_path`` for audit parity.
    """
    if not bool(getattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", False)):
        return state
    dispatch = state.get("pipeline_dispatch")
    if not isinstance(dispatch, dict):
        return state
    stage_value = stage.value if isinstance(stage, PipelineStage) else str(stage)
    if stage_value not in PipelineStage._value2member_map_:
        return state
    schedule, cursor = _dispatch_schedule_and_cursor(dispatch)
    if not schedule:
        return state
    stage_enum = PipelineStage(stage_value)
    if stage_enum not in schedule:
        return state
    expected = next_stage_after(schedule, cursor)
    if expected is not stage_enum:
        return state
    runtime = dict(dispatch.get("runtime_context") or {})
    runtime["dispatch_cursor"] = stage_value
    trace = dict(runtime.get("scheduling_trace") or {})
    visited = list(trace.get("cursor_path") or [])
    if not visited or visited[-1] != stage_value:
        visited.append(stage_value)
    trace["cursor_path"] = visited
    runtime["scheduling_trace"] = trace
    return {**state, "pipeline_dispatch": {**dispatch, "runtime_context": runtime}}


def _defer_spl_postprocessor_inline() -> bool:
    """Dispatch v2: dedicated ``graph_node_spl_postprocessor`` owns the hook."""
    return bool(getattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", False))


def _postprocessor_family_from_candidate(candidate: dict[str, Any]) -> tuple[str, bool]:
    if candidate.get("template_id"):
        return "governed_template", False
    mode = str(candidate.get("generation_mode") or "")
    if mode == "t2_spl_native_review":
        t2 = candidate.get("t2_spl_native") if isinstance(candidate.get("t2_spl_native"), dict) else {}
        return str(t2.get("runtime_operation") or "t2_spl_native"), False
    if mode == "deterministic_lab_draft":
        return str(candidate.get("detection_family") or "lab_draft"), False
    if candidate.get("llm_fallback_used") or "llm" in mode:
        return str(candidate.get("detection_family") or "llm_spl_advisory"), True
    return str(candidate.get("detection_family") or mode or "spl_candidate"), False


def graph_node_spl_postprocessor(state: ChatPipelineState) -> ChatPipelineState:
    """Phase 6c — mandatory review-only SPL postprocessor (dedicated node when v2 on)."""
    emit_stage("spl_postprocessor")
    candidate = state.get("candidate_spl")
    if not isinstance(candidate, dict):
        return advance_dispatch_cursor(state, PipelineStage.spl_postprocessor)
    raw_spl = str(candidate.get("candidate_spl") or "").strip()
    if not raw_spl:
        return advance_dispatch_cursor(state, PipelineStage.spl_postprocessor)

    request = state["request"]
    query_text = state.get("effective_query") or request.message
    family, llm_gen = _postprocessor_family_from_candidate(candidate)
    dispatch = state.get("pipeline_dispatch") if isinstance(state.get("pipeline_dispatch"), dict) else {}
    decision = dispatch.get("decision") if isinstance(dispatch.get("decision"), dict) else {}
    slot_handoff = decision.get("slot_handoff") or candidate.get("user_constraint_bindings")
    mcp_ctx = ((dispatch.get("runtime_context") or {}).get("mcp_discovery_context"))

    postprocessor_context = None
    if str(candidate.get("generation_mode") or "") == "deterministic_lab_draft":
        from app.spl.utility_spl_authoring import build_utility_postprocessor_context

        postprocessor_context = build_utility_postprocessor_context(
            query_text,
            llm_generated=False,
            target_log_family=family or None,
            is_universal_spl=family == "universal_timestamp_spl",
        )

    postprocessed = finalize_review_only_spl(
        raw_spl,
        query=query_text,
        family=family,
        slot_handoff=slot_handoff,
        llm_generated=llm_gen,
        mcp_discovery_context=mcp_ctx,
        postprocessor_context=postprocessor_context,
    )
    final_spl = postprocessed.normalized_spl
    trace = dict(postprocessed.trace)
    updated_candidate = {
        **candidate,
        "candidate_spl": final_spl,
        "postprocessor_applied": bool(trace.get("postprocessor_applied")),
        "review_only_spl_postprocessor_trace": trace,
    }
    if postprocessed.warnings:
        updated_candidate["review_only_spl_postprocessor_warnings"] = list(postprocessed.warnings)

    spl_validation = state.get("spl_validation")
    updated_validation: dict[str, Any] | None = None
    if isinstance(spl_validation, dict):
        updated_validation = {
            **spl_validation,
            "review_only_spl_postprocessor_trace": trace,
        }
        if postprocessed.warnings:
            updated_validation["review_only_spl_postprocessor_warnings"] = list(postprocessed.warnings)
        # An approved (non-template) candidate carries a validated normalized_spl that
        # the MCP execution gate trusts. If the postprocessor MUTATED the SPL, the old
        # normalized_spl no longer matches what was validated — re-validate the
        # postprocessed SPL before trusting it, and fail closed if it no longer passes
        # so a mutated query can never reach the execution gate as "approved".
        if family != "governed_template" and spl_validation.get("normalized_spl"):
            if not bool(trace.get("postprocessor_applied")):
                updated_validation["normalized_spl"] = final_spl
            else:
                revalidation = validate_spl(final_spl)
                if revalidation.get("approved") and revalidation.get("normalized_spl"):
                    updated_validation["normalized_spl"] = revalidation.get("normalized_spl")
                    updated_validation["postprocessor_revalidated"] = True
                else:
                    updated_validation["approved"] = False
                    updated_validation["normalized_spl"] = None
                    updated_validation["postprocessor_revalidated"] = False
                    updated_validation["review_required_reason"] = "postprocessor_mutation_revalidation_failed"
                    reject = list(updated_validation.get("reject_reasons") or [])
                    if "postprocessor_mutation_revalidation_failed" not in reject:
                        reject.append("postprocessor_mutation_revalidation_failed")
                    updated_validation["reject_reasons"] = reject
                    updated_candidate["execution_eligible"] = False

    out: ChatPipelineState = {
        **state,
        "candidate_spl": updated_candidate,
    }
    if updated_validation is not None:
        out["spl_validation"] = updated_validation
    return advance_dispatch_cursor(out, PipelineStage.spl_postprocessor)


def dispatch_v2_route_after_shadow_tail(state: ChatPipelineState) -> str | None:
    """Cursor-driven shadow-tail routing when dispatch v2 is on (Phase 6 partial)."""
    if not bool(getattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", False)):
        return None
    dispatch = state.get("pipeline_dispatch")
    if not isinstance(dispatch, dict):
        return None
    schedule, cursor = _dispatch_schedule_and_cursor(dispatch)
    if not schedule:
        return None
    nxt = next_stage_after(schedule, cursor)
    if nxt is None:
        return None
    if nxt is PipelineStage.rag_early:
        plan = state.get("evidence_plan") if isinstance(state.get("evidence_plan"), dict) else {}
        return "rag_only" if plan.get("answer_mode") == "rag_only" else "rag_early"
    if nxt in {
        PipelineStage.pre_spl_mcp_discovery,
        PipelineStage.workflow_spl,
        PipelineStage.spl_postprocessor,
    }:
        return "workflow_spl"
    if nxt in {PipelineStage.spl_source_resolve, PipelineStage.mcp_execution}:
        return "spl_source_resolve"
    return None


def dispatch_v2_route_after_workflow_spl(state: ChatPipelineState) -> str | None:
    if not bool(getattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", False)):
        return None
    dispatch = state.get("pipeline_dispatch")
    if not isinstance(dispatch, dict):
        return None
    schedule, cursor = _dispatch_schedule_and_cursor(dispatch)
    nxt = next_stage_after(schedule, cursor)
    if nxt is PipelineStage.rag_early:
        return "rag_early"
    if nxt is PipelineStage.spl_postprocessor:
        return "spl_postprocessor"
    if nxt in {PipelineStage.spl_source_resolve, PipelineStage.mcp_execution}:
        return "spl_source_resolve"
    return None


def dispatch_v2_route_after_spl_postprocessor(state: ChatPipelineState) -> str | None:
    if not bool(getattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", False)):
        return None
    dispatch = state.get("pipeline_dispatch")
    if not isinstance(dispatch, dict):
        return None
    schedule, cursor = _dispatch_schedule_and_cursor(dispatch)
    nxt = next_stage_after(schedule, cursor)
    if nxt is PipelineStage.rag_early:
        return "rag_early"
    if nxt in {PipelineStage.spl_source_resolve, PipelineStage.mcp_execution}:
        return "spl_source_resolve"
    return None


def graph_node_pre_spl_mcp_discovery(state: ChatPipelineState) -> ChatPipelineState:
    """Read-only MCP source discovery before SPL generation (Phase 5).

    Runs only when dispatch v2 is on AND ``pre_spl_mcp_discovery`` is the next
    scheduled stage (cursor-driven). Discovery failures and disabled MCP are
    recorded as skipped stages, then the cursor advances so SPL generation can
    proceed without skipping ahead in ``cursor_path``.
    """
    if not bool(getattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", False)):
        return state
    dispatch = state.get("pipeline_dispatch")
    if not isinstance(dispatch, dict):
        return state

    flags = projected_flags_from_state(state)
    if flags is not None and not flags.get("run_pre_spl_mcp_discovery"):
        return state
    schedule, cursor = _dispatch_schedule_and_cursor(dispatch)
    if next_stage_after(schedule, cursor) is not PipelineStage.pre_spl_mcp_discovery:
        return state

    runtime = dict(dispatch.get("runtime_context") or {})
    if not bool(getattr(settings, "mcp_discovery_enabled", False)):
        runtime = _record_dispatch_stage_skip(runtime, PipelineStage.pre_spl_mcp_discovery, "mcp_discovery_disabled")
        state = {**state, "pipeline_dispatch": {**dispatch, "runtime_context": runtime}}
        return advance_dispatch_cursor(state, PipelineStage.pre_spl_mcp_discovery)

    handoff = (dispatch.get("decision") or {}).get("slot_handoff") or {}
    slots = handoff.get("normalized_slots") if isinstance(handoff, dict) else {}
    slots = slots if isinstance(slots, dict) else {}
    required = [k for k in ("index", "sourcetype") if not slots.get(k)]
    try:
        profile, trace = run_mcp_source_discovery(
            required_slots=required or None,
            include_knowledge_objects=True,
        )
    except Exception:  # noqa: BLE001 - discovery must never break the SPL path
        logger.warning("pre_spl_mcp_discovery_failed", exc_info=True)
        runtime = _record_dispatch_stage_skip(runtime, PipelineStage.pre_spl_mcp_discovery, "discovery_failed")
        state = {**state, "pipeline_dispatch": {**dispatch, "runtime_context": runtime}}
        return advance_dispatch_cursor(state, PipelineStage.pre_spl_mcp_discovery)

    indexes = [profile["index"]] if profile.get("index") else []
    sourcetypes = [profile["sourcetype"]] if profile.get("sourcetype") else []
    harvested_saved_searches: list[dict[str, str]] = []
    if isinstance(trace, dict):
        raw_saved = trace.get("saved_searches")
        if isinstance(raw_saved, list):
            harvested_saved_searches = [
                {"name": str(item.get("name") or ""), "description": str(item.get("description") or "")}
                for item in raw_saved
                if isinstance(item, dict) and str(item.get("name") or "").strip()
            ]
    discovery_ctx = McpDiscoveryContext(
        indexes=indexes,
        sourcetypes=sourcetypes,
        field_hints={k: str(v) for k, v in profile.items() if v},
        discovery_hops=[trace] if isinstance(trace, dict) else [],
        populated_at_stage="pre_spl_mcp_discovery",
        harvested_saved_searches=harvested_saved_searches,
    )
    runtime["mcp_discovery_context"] = discovery_ctx.model_dump(mode="json")
    runtime["mcp_phase"] = "pre_spl"
    state = {**state, "pipeline_dispatch": {**dispatch, "runtime_context": runtime}}
    return advance_dispatch_cursor(state, PipelineStage.pre_spl_mcp_discovery)


def _guard_query_to_intent_for_workflow_spl(state: ChatPipelineState) -> ChatPipelineState | None:
    """Fail closed when workflow SPL runs without a valid query_to_intent contract."""
    from app.chat.canonical_mode import build_canonical_failure_state
    from app.chat.canonical_query_to_intent_resume import query_to_intent_contract_error
    from app.chat.response_validation import emit_request_failed

    error = query_to_intent_contract_error(state.get("query_to_intent"))
    if not error:
        return None
    failed = build_canonical_failure_state(
        state,
        outcome="planning_failed",
        reason=error,
        detail="workflow_spl_missing_query_to_intent",
    )
    return emit_request_failed(failed, reason=error, error_category="planning")


def graph_node_workflow_spl(state: ChatPipelineState) -> ChatPipelineState:
    emit_stage("generating_spl")
    workflow_guard = _guard_query_to_intent_for_workflow_spl(state)
    if workflow_guard is not None:
        return workflow_guard
    # Phase 5: run pre-SPL MCP discovery inline when scheduled (flag-gated). The
    # dedicated conditional graph edge is wired in Phase 6; until then the node
    # invokes discovery here so the discovered context reaches the SPL compiler.
    state = graph_node_pre_spl_mcp_discovery(state)
    request = state["request"]
    routed = state["routed"]
    trace_id = state["trace_id"]
    session_resolution = state.get("session_context_resolution")
    if isinstance(session_resolution, SessionContextResolution) and session_resolution.spl_refine_from_session:
        effective_skill = (
            session_resolution.pins.last_selected_live_execution_skill
            if session_resolution.pins and session_resolution.pins.last_selected_live_execution_skill
            else "attack_discovery"
        )
    else:
        effective_skill = _effective_routing_skill(state)
    rc = _routes_chat()
    workflow_plan = rc.plan_workflow(
        selected_skill=effective_skill,
        tool_plan=list(routed["tool_plan"]),
        query=request.message,
        trace_id=trace_id,
    )
    query_text = state.get("effective_query") or request.message
    query_understanding = state.get("query_understanding")
    candidate_mapped_pattern = None
    if query_understanding is not None and getattr(
        query_understanding, "deterministic_match_path", None
    ) in (
        "exact_105_question",
        "exact_105_plus_use_case_catalog",
        "near_105_question",
        "semantic_105_question",
    ):
        candidate_mapped_pattern = getattr(query_understanding, "mapped_pattern_type", None)
    session_refined = _session_spl_refine_stage(
        state=state,
        trace_id=trace_id,
        skill=effective_skill,
        user_query=query_text,
    )
    if session_refined is not None:
        candidate_spl, spl_validation = session_refined
    else:
        _dispatch_flags = projected_flags_from_state(state)
        _slot_handoff = None
        _pd = state.get("pipeline_dispatch")
        if isinstance(_pd, dict):
            _dec = _pd.get("decision")
            if isinstance(_dec, dict) and isinstance(_dec.get("slot_handoff"), dict):
                _slot_handoff = _dec.get("slot_handoff")
        candidate_spl, spl_validation = _candidate_spl_stage(
            trace_id=trace_id,
            skill=effective_skill,
            user_query=query_text,
            spl_allowed=_spl_allowed(state),
            query_signals=_query_signals_from_state(state) or {},
            template_id=(
                state["selected_use_case"].default_spl_template
                if state.get("selected_use_case") is not None
                else None
            ),
            use_case_id=(
                state["selected_use_case"].use_case_id
                if state.get("selected_use_case") is not None
                else None
            ),
            slot_binding_enabled=True,
            mapped_pattern_type=candidate_mapped_pattern,
            llm_intent_advisory=state.get("llm_intent_advisory"),
            query_understanding=query_understanding,
            llm_turn_budget=state.get("llm_turn_budget"),
            mcp_discovery_context=(
                (state.get("pipeline_dispatch") or {}).get("runtime_context") or {}
            ).get("mcp_discovery_context"),
            slot_handoff=_slot_handoff,
            dispatch_flags=_dispatch_flags,
        )
    preference = preference_from_discovery_context(
        query=query_text,
        discovery_context=(
            (state.get("pipeline_dispatch") or {}).get("runtime_context") or {}
        ).get("mcp_discovery_context"),
        state=state,
    )
    if preference is not None:
        _dispatch = state.get("pipeline_dispatch")
        if isinstance(_dispatch, dict):
            _runtime = dict(_dispatch.get("runtime_context") or {})
            _ctx = dict(_runtime.get("mcp_discovery_context") or {})
            _ctx["saved_search_preference"] = preference.to_dict()
            _runtime["mcp_discovery_context"] = _ctx
            state = {**state, "pipeline_dispatch": {**_dispatch, "runtime_context": _runtime}}
        if preference.status == "primary_saved_search":
            candidate_spl, spl_validation = apply_saved_search_preference_to_spl(
                preference,
                candidate_spl=candidate_spl if isinstance(candidate_spl, dict) else None,
                spl_validation=spl_validation if isinstance(spl_validation, dict) else None,
            )
        elif preference.analyst_message and isinstance(candidate_spl, dict):
            candidate_spl = {
                **candidate_spl,
                "saved_search_advisory": preference.analyst_message,
                "harvested_saved_search_names": list(preference.advisory_names),
            }
    # Phase 4B: persist the LLM detection plan (if any) onto canonical state so
    # downstream nodes prefer it over re-parsing the query. Node-only persistence;
    # the compiler/fallback never write state.
    if isinstance(candidate_spl, dict) and candidate_spl.get("detection_plan"):
        state = persist_llm_spl_plan(state, candidate_spl.get("detection_plan"))
    # Phase 6: advance workflow_spl cursor; spl_postprocessor cursor advances in
    # graph_node_spl_postprocessor when dispatch v2 defers inline postprocessing.
    state = advance_dispatch_cursor(state, PipelineStage.workflow_spl)
    if not _defer_spl_postprocessor_inline():
        state = advance_dispatch_cursor(state, PipelineStage.spl_postprocessor)
    exact_105_pattern = candidate_mapped_pattern
    mapped_use_case_ids = (
        getattr(query_understanding, "mapped_use_case_ids", None) or []
        if query_understanding is not None
        else []
    )
    draft_use_case_id = mapped_use_case_ids[0] if mapped_use_case_ids else None
    llm_draft_advisory = (
        state["llm_intent_advisory"].model_dump()
        if isinstance(state.get("llm_intent_advisory"), LLMIntentAdvisory)
        else state.get("llm_intent_advisory")
    )
    spl_draft_preview = build_draft_preview(
        query_text,
        spl_validation=spl_validation if isinstance(spl_validation, dict) else None,
        unsafe_enforcement=bool((_query_signals_from_state(state) or {}).get("block_or_contain")),
        pattern_type=exact_105_pattern,
        use_case_id=draft_use_case_id,
        live_data_request=_live_data_request_from_state(state),
        llm_intent_advisory=llm_draft_advisory if isinstance(llm_draft_advisory, dict) else None,
        query_understanding=query_understanding,
    )
    llm_spl_candidate = _llm_spl_candidate_stage(
        skill=effective_skill,
        user_query=query_text,
        request_enabled=bool(request.llm_spl_draft_mode),
    )
    return {
        **state,
        "workflow_plan": workflow_plan,
        "candidate_spl": candidate_spl,
        "spl_validation": spl_validation,
        "spl_draft_preview": spl_draft_preview,
        "llm_spl_candidate": llm_spl_candidate,
    }


def graph_node_execution(state: ChatPipelineState) -> ChatPipelineState:
    emit_stage("checking_mcp")
    request = state["request"]
    session_pins = state.get("session_pins")
    pending_execution = None
    if isinstance(session_pins, SessionPins):
        pending_execution = session_pins.pending_execution_confirmation

    spl_validation = state.get("spl_validation")
    if getattr(request, "execution_review_action", None) == "update_spl" and getattr(request, "analyst_provided_spl", None):
        analyst_spl = str(request.analyst_provided_spl).strip()
        if analyst_spl:
            candidate = state.get("candidate_spl")
            resolve_result = resolve_spl_source_profile(
                analyst_spl,
                user_query=request.message,
                soc_kb_retrieval=state.get("soc_kb_retrieval"),
                session_slots=dict(getattr(session_pins, "source_profile_slots", None) or {}),
                template_id=str(candidate.get("template_id") or "") if isinstance(candidate, dict) else None,
            )
            if resolve_result.fully_resolved and isinstance(resolve_result.validation, dict):
                spl_validation = resolve_result.validation
                if isinstance(candidate, dict):
                    state = {
                        **state,
                        "candidate_spl": {**candidate, "candidate_spl": resolve_result.spl},
                        "spl_validation": spl_validation,
                    }
                else:
                    state = {**state, "spl_validation": spl_validation}

    # Item 2.3/2.4 derived-artifact wiring (respec'd 2026-07-03): only a non-blocked
    # llm_derived_spl_artifact may enter the gate, and only in place of — never in
    # addition to — the raw lab-tier spl_validation (which stays approved=false).
    # A high-risk derived artifact never reaches evaluate_mcp_execution at all.
    llm_lineage_auto_eligible = False
    derived_artifact = state.get("llm_derived_spl_artifact")
    if isinstance(derived_artifact, dict):
        if derived_artifact.get("blocked"):
            execution = {
                "status": "skipped",
                "execution_intent": "none",
                "selected_mcp_server": None,
                "selected_mcp_tool": None,
                "tool_selection_status": "blocked_by_llm_lineage_vigilance",
                "tool_selection_reason": derived_artifact.get("blocked_reason") or "llm_lineage_vigilance_blocked",
                "executed_spl": None,
                "result_count": 0,
                "results_preview": [],
                "block_reason": derived_artifact.get("blocked_reason") or "llm_lineage_vigilance_blocked",
                "duration_ms": 0,
                "evidence_source": "unavailable",
                "execution_status_label": "not_executed",
                "llm_lineage_risk_tier": derived_artifact.get("risk_tier"),
            }
            human_review_result = no_human_review()
            emit_mcp_status_from_execution(execution)
            return {**state, "spl_validation": spl_validation, "execution": execution, "human_review": human_review_result}
        if derived_artifact.get("normalized_spl"):
            spl_validation = {
                **(spl_validation or {}),
                "approved": True,
                "normalized_spl": derived_artifact["normalized_spl"],
                "reject_reasons": [],
                "execution_eligible": True,
                "llm_lineage_risk_tier": derived_artifact.get("risk_tier"),
                "llm_lineage_source": derived_artifact.get("producer_lineage"),
            }
            llm_lineage_auto_eligible = bool(derived_artifact.get("auto_eligible"))

    qu = state.get("query_understanding")
    mapped_use_case_ids = list(getattr(qu, "mapped_use_case_ids", None) or []) if qu is not None else []
    execution_intent = "spl_search"
    requested_mcp_tool = request.requested_mcp_tool
    candidate_spl = state.get("candidate_spl")
    if isinstance(candidate_spl, dict) and candidate_spl.get("generation_mode") == "saved_search_primary":
        execution_intent = "saved_search_execution"
        if not requested_mcp_tool:
            requested_mcp_tool = str(candidate_spl.get("planned_tool") or "splunk_run_saved_search")
    execution, human_review = _execution_stage(
        trace_id=state["trace_id"],
        selected_skill=_effective_routing_skill(state),
        workflow_plan=state["workflow_plan"],
        spl_validation=spl_validation,
        precondition_evaluation=state.get("route_plan_shadow", {}).get("precondition_evaluation"),
        requested_mcp_server=request.requested_mcp_server,
        requested_mcp_tool=requested_mcp_tool,
        execution_intent=execution_intent,
        llm_lineage_auto_eligible=llm_lineage_auto_eligible,
        mcp_allowed=_mcp_allowed(state),
        execution_review_action=getattr(request, "execution_review_action", None),
        analyst_provided_spl=getattr(request, "analyst_provided_spl", None),
        pending_execution=pending_execution,
        rbac_role=session_role_for_mcp_gate(state.get("session_role")),
        catalogue_match_path=getattr(qu, "deterministic_match_path", None) if qu is not None else None,
        catalogue_question_ref=getattr(qu, "mapped_question_ref", None) if qu is not None else None,
        catalogue_use_case_id=mapped_use_case_ids[0] if mapped_use_case_ids else None,
        data_silence_advisory=state.get("data_silence_advisory")
        if isinstance(state.get("data_silence_advisory"), dict)
        else None,
        hook_idempotency=resolve_hook_idempotency_context(state),
    )
    # O5c Step 2: the broaden confirm turn executed the approved broadened
    # search. Attach the two-call cross-turn envelope (empty primary + broadened
    # outcome) so lineage/evidence represent both logical calls, not just the
    # singular c2 execution.
    if (
        is_broaden_pending(pending_execution)
        and isinstance(execution, dict)
        and execution.get("status") == "executed"
    ):
        execution = {
            **execution,
            "mcp_orchestration": finalize_broaden_orchestration(
                trace_id=state["trace_id"],
                pending=pending_execution,
                broadened_execution=execution,
            ),
        }

    emit_mcp_status_from_execution(execution)
    # Source-profile clarification wins over the execution-stage HIL: a lab/draft
    # candidate whose index/sourcetype could not be resolved must surface the
    # "provide source profile" ask, not an execution-approval gate on an
    # unresolved placeholder SPL. (Governed templates never hit this — they carry
    # concrete sources, so source-resolve produces no missing slots.)
    prior_review = state.get("human_review")
    if (
        isinstance(prior_review, dict)
        and prior_review.get("required")
        and prior_review.get("review_type") == "spl_source_profile_clarification"
    ):
        return {**state, "execution": execution, "human_review": prior_review}

    # O5c: broaden-on-empty. When a primary search executed with zero rows and
    # the broaden recipe + LLM fallback are enabled, offer one bounded,
    # HIL-gated, LLM-proposed broadened retry. Default-off (both flags off) =>
    # this is skipped and the single-call result stands unchanged.
    if should_attempt_broaden(
        selected_skill=_effective_routing_skill(state),
        execution=execution,
        has_incoming_review_action=bool(getattr(request, "execution_review_action", None)),
    ):
        decision = maybe_build_broaden_decision(
            trace_id=state["trace_id"],
            user_query=state.get("effective_query") or request.message,
            execution=execution,
        )
        if decision is not None:
            execution = {
                **execution,
                "pending_execution_confirmation": decision.pending_execution_confirmation,
                "mcp_orchestration": decision.orchestration,
            }
            return {
                **state,
                "execution": execution,
                "human_review": decision.review,
                "mcp_orchestration": decision.orchestration,
            }

    return {**state, "execution": execution, "human_review": human_review}



def _live_data_request_from_state(state: ChatPipelineState) -> bool:
    signals = _query_signals_from_state(state) or {}
    return bool(signals.get("live_data_request"))


def _apply_effective_hil_to_state(
    state: ChatPipelineState,
    *,
    answer_contract: Any | None,
    execution_authorized: bool,
) -> ChatPipelineState:
    evidence_plan = state.get("evidence_plan") if isinstance(state.get("evidence_plan"), dict) else None
    intent = state.get("intent_classification") if isinstance(state.get("intent_classification"), dict) else {}
    effective_hil = resolve_effective_hil_required(
        evidence_plan=evidence_plan,
        answer_contract=answer_contract,
        human_review=state.get("human_review") if isinstance(state.get("human_review"), dict) else None,
        execution=state.get("execution") if isinstance(state.get("execution"), dict) else None,
        live_data_request=_live_data_request_from_state(state),
        execution_authorized=execution_authorized,
        intent_requires_hil=bool(intent.get("requires_hil")),
    )
    updated: ChatPipelineState = dict(state)
    planning = state.get("planning_decision")
    if isinstance(planning, dict):
        planning_copy = {**planning, "hil_required": effective_hil, "effective_hil_required": effective_hil}
        updated["planning_decision"] = planning_copy
    governance = state.get("governance_trace")
    if governance is not None:
        if isinstance(governance, dict):
            updated["governance_trace"] = {**governance, "effective_hil_required": effective_hil}
        else:
            updated["governance_trace"] = governance.model_copy(
                update={"effective_hil_required": effective_hil}
            )
    return updated

def graph_node_prepare_rag_only(state: ChatPipelineState) -> ChatPipelineState:
    request = state["request"]
    trace_id = state["trace_id"]
    planning = state.get("planning_decision")
    guided = isinstance(planning, dict) and planning.get("path_type") == "guided_investigation"
    selected_skill = "guided_investigation" if guided else "knowledge_recall"
    rc = _routes_chat()
    workflow_plan = rc.plan_workflow(
        selected_skill=selected_skill,
        tool_plan=(
            ["retrieve_approved_knowledge", "optional_review_only_spl", "no_mcp"]
            if guided
            else ["retrieve_approved_knowledge", "no_spl", "no_mcp"]
        ),
        query=request.message,
        trace_id=trace_id,
    )
    hybrid_dispatch_active = guided and uses_guided_hybrid_dispatch_from_state(state)
    spl_draft_preview = (
        None
        if hybrid_dispatch_active
        else build_draft_preview(
            state.get("effective_query") or request.message,
            unsafe_enforcement=bool((_query_signals_from_state(state) or {}).get("block_or_contain")),
            llm_intent_advisory=(
                state["llm_intent_advisory"].model_dump()
                if isinstance(state.get("llm_intent_advisory"), LLMIntentAdvisory)
                else state.get("llm_intent_advisory")
                if isinstance(state.get("llm_intent_advisory"), dict)
                else None
            ),
            query_understanding=state.get("query_understanding"),
        )
        if guided
        else None
    )
    execution, human_review = _execution_stage(
        trace_id=trace_id,
        selected_skill=selected_skill,
        workflow_plan=workflow_plan,
        spl_validation=None,
        precondition_evaluation=state.get("route_plan_shadow", {}).get("precondition_evaluation"),
        requested_mcp_server=request.requested_mcp_server,
        requested_mcp_tool=request.requested_mcp_tool,
        mcp_allowed=False,
    )
    emit_mcp_status_from_execution(execution)
    prepared = {
        **state,
        "workflow_plan": workflow_plan,
        "candidate_spl": None,
        "spl_validation": None,
        "spl_draft_preview": spl_draft_preview,
        "execution": execution,
        "human_review": human_review,
    }
    return _record_guided_resource_outcome(
        prepared,
        spl_draft_preview=spl_draft_preview,
        update_spl=True,
    )


def graph_node_rag_early(state: ChatPipelineState) -> ChatPipelineState:
    emit_stage("retrieving_knowledge")
    if not isinstance(state.get("workflow_plan"), dict):
        state = graph_node_prepare_rag_only(state)
    request = state["request"]
    query_text = state.get("effective_query") or request.message
    query_understanding = state.get("query_understanding")
    utility_signals = extract_query_signals(query_text, query_understanding)
    if is_universal_utility_spl_authoring(query_text, utility_signals):
        trace_id = str(state.get("trace_id") or "")
        if trace_id:
            try:
                _routes_chat().get_telemetry_connector().record_rag_retrieval(
                    trace_id,
                    collection=None,
                    status="skipped",
                    result_count=0,
                    evidence_origin="rag_skipped_for_spl_utility_authoring",
                )
            except Exception:  # noqa: BLE001 - telemetry must never break chat
                logger.warning("utility_spl_rag_skip_telemetry_failed", exc_info=True)
        return advance_dispatch_cursor(
            {**state, "soc_kb_retrieval": _utility_spl_rag_skipped_payload()},
            PipelineStage.rag_early,
        )
    workflow_plan = state["workflow_plan"]
    execution = state["execution"] if "execution" in state else {"block_reason": None}
    retrieval = retrieve_soc_kb(
        query=request.message,
        selected_skill=_context_selected_skill(state),
        workflow_stage="context",
        workflow_plan=workflow_plan,
        required_sources=list(workflow_plan.get("required_sources") or []),
        execution_block_reason=execution.get("block_reason"),
    )
    updated = {**state, "soc_kb_retrieval": retrieval}
    if _path_type(updated) == "guided_investigation" and _rag_no_match(retrieval):
        updated = _record_guided_resource_outcome(updated, rag_no_match=True)
    return advance_dispatch_cursor(updated, PipelineStage.rag_early)


def _utility_spl_rag_skipped_payload() -> dict[str, Any]:
    return {
        "retrieved_entries": [],
        "retrieval_status": "skipped",
        "ambiguity_status": "clear",
        "ambiguity_assist": None,
        "confidence": 0.0,
        "reasons": ["rag_skipped_for_spl_utility_authoring"],
        "warnings": [],
        "rag_skipped_for_spl_utility_authoring": True,
        "selected_collections": [],
        "collection_selection": {},
        "direct_to_llm": False,
        "llm_selection_enabled": False,
    }


def graph_node_spl_source_resolve(state: ChatPipelineState) -> ChatPipelineState:
    evidence_plan = state.get("evidence_plan")
    if isinstance(evidence_plan, dict) and evidence_plan.get("needs_spl") is False:
        return state
    candidate = state.get("candidate_spl")
    validation = state.get("spl_validation")
    if not isinstance(candidate, dict) or not isinstance(validation, dict):
        return state

    if candidate.get("detection_family") == "universal_timestamp_spl":
        post = candidate.get("review_only_spl_postprocessor_trace")
        post = post if isinstance(post, dict) else {}
        resolved_index = str(post.get("resolved_index") or "").strip()
        resolution_source = str(post.get("index_resolution_source") or "").strip()
        return {
            **state,
            "spl_source_resolve": {
                "skipped": True,
                "reason": "universal_spl_utility_placeholder_allowed",
                "placeholder_index": resolved_index == "<your_index>",
                "resolved_slots": {},
                "missing_slots": [],
                "tiers_used": [resolution_source] if resolution_source else [],
                "slot_sources": {},
                "fully_resolved": bool(resolved_index and resolved_index != "<your_index>"),
            },
        }

    spl = str(candidate.get("candidate_spl") or "").strip()
    if not spl or "<" not in spl:
        return state

    soc_kb_retrieval = state.get("soc_kb_retrieval") if isinstance(state.get("soc_kb_retrieval"), dict) else None
    if soc_kb_retrieval is None:
        request = state["request"]
        workflow_plan = state.get("workflow_plan") if isinstance(state.get("workflow_plan"), dict) else {}
        soc_kb_retrieval = retrieve_soc_kb(
            query=request.message,
            selected_skill=_context_selected_skill(state),
            workflow_stage="spl_source_resolve",
            workflow_plan=workflow_plan,
            required_sources=[str(item) for item in workflow_plan.get("required_sources") or []],
            execution_block_reason=None,
        )
        state = {**state, "soc_kb_retrieval": soc_kb_retrieval}

    session_pins = state.get("session_pins")
    session_slots: dict[str, str] = {}
    if isinstance(session_pins, SessionPins):
        session_slots = dict(session_pins.source_profile_slots or {})
    request = state["request"]
    if getattr(request, "source_profile_slots", None):
        session_slots.update({k: str(v) for k, v in request.source_profile_slots.items() if v})

    workflow_plan = state.get("workflow_plan") if isinstance(state.get("workflow_plan"), dict) else {}
    required_sources = [str(item) for item in workflow_plan.get("required_sources") or []]
    query_text = state.get("effective_query") or state["request"].message

    resolve_result = resolve_spl_source_profile(
        spl,
        user_query=query_text,
        soc_kb_retrieval=soc_kb_retrieval,
        session_slots=session_slots,
        required_sources=required_sources,
        template_id=str(candidate.get("template_id") or "") or None,
    )
    trace = {
        "resolved_slots": resolve_result.resolved_slots,
        "missing_slots": resolve_result.missing_slots,
        "tiers_used": resolve_result.tiers_used,
        "slot_sources": resolve_result.slot_sources,
        "mcp_discovery_trace": resolve_result.mcp_discovery_trace,
        "fully_resolved": resolve_result.fully_resolved,
    }
    updated: dict[str, Any] = {**state, "spl_source_resolve": trace}
    is_lab_tier = bool(candidate.get("lab_tier_exposure"))

    if resolve_result.fully_resolved and isinstance(resolve_result.validation, dict):
        # Lab-tier candidates (non-governed LLM/lab drafts) stay review-only: even
        # when placeholders fully resolve and validate, we never flip them to
        # execution_validated/approved. The analyst sees the substituted SPL for
        # review, but approved/normalized_spl stay false/null so the MCP gate cannot
        # run it. Governed candidates promote as before.
        if is_lab_tier:
            updated["candidate_spl"] = {
                **candidate,
                "candidate_spl": resolve_result.spl,
                "source_resolve_tiers": resolve_result.tiers_used,
            }
            updated["spl_validation"] = {
                **validation,
                "source_resolve_tiers": resolve_result.tiers_used,
            }
            # Item 2.3 (respec'd 2026-07-03): the raw lab-tier candidate above is
            # untouched — still review-only, execution_eligible stays false. A
            # SEPARATE derived artifact may become execution-eligible only after
            # passing the real validator (already true here: resolve_result.
            # validation.approved) AND harmful-SPL vigilance risk classification.
            # Never falls back to a lab draft on its own account — this branch
            # only runs when resolution already fully succeeded.
            vigilance = classify_llm_spl_risk(
                normalized_spl=resolve_result.validation.get("normalized_spl"),
                validator_result=resolve_result.validation,
                user_query=query_text,
            )
            updated["llm_derived_spl_artifact"] = {
                "normalized_spl": resolve_result.validation.get("normalized_spl") if not vigilance.blocked else None,
                "producer_lineage": "llm_plan_compiler",
                "source_resolve_tiers": resolve_result.tiers_used,
                **vigilance.to_trace_dict(),
            }
            return updated
        resolved_validation = {
            **validation,
            **resolve_result.validation,
            "lab_tier_exposure": False,
            "exposure_tier": "execution_validated",
            "source_resolve_tiers": resolve_result.tiers_used,
            "review_required_reason": None,
        }
        resolved_candidate = {
            **candidate,
            "candidate_spl": resolve_result.spl,
            "lab_tier_exposure": False,
            "exposure_tier": "execution_validated",
            "source_resolve_tiers": resolve_result.tiers_used,
        }
        updated["candidate_spl"] = resolved_candidate
        updated["spl_validation"] = resolved_validation
        return updated

    clarification_slots = list(resolve_result.missing_slots)
    if not clarification_slots and is_lab_tier and not resolve_result.fully_resolved:
        # Policy/COE may fill placeholders while validation still fails (e.g. sourcetype
        # not on allowlist). Lab-tier drafts must surface source-profile clarification,
        # not fall through to execution-stage spl_revision.
        clarification_slots = extract_placeholder_slots(spl)

    if clarification_slots:
        review = build_spl_source_profile_review(clarification_slots)
        existing_review = state.get("human_review")
        if isinstance(existing_review, dict) and existing_review.get("required"):
            review = {
                **existing_review,
                "review_type": review["review_type"],
                "reason": review["reason"],
                "safe_message_for_user": review["safe_message_for_user"],
                "allowed_actions": review["allowed_actions"],
            }
        updated["human_review"] = review
        updated_spl_validation = {
            **validation,
            "review_required_reason": "spl_source_profile_clarification",
            "source_profile_missing_slots": clarification_slots,
            "source_resolve_tiers": resolve_result.tiers_used,
        }
        updated["spl_validation"] = updated_spl_validation
    return updated


def _record_guided_resource_outcome(
    state: ChatPipelineState,
    *,
    spl_draft_preview: dict[str, Any] | None = None,
    update_spl: bool = False,
    rag_no_match: bool = False,
) -> ChatPipelineState:
    if _path_type(state) != "guided_investigation":
        return state

    no_match_limitation = (
        "No governed playbook matched this hunt; the checklist is general guidance and must be "
        "validated against local telemetry and policy."
    )

    def update_decisions(decisions: dict[str, Any]) -> dict[str, Any]:
        updated = dict(decisions)
        if update_spl and spl_draft_preview is not None:
            updated["spl"] = {
                **dict(updated.get("spl") or {}),
                "needed": True,
                "status": "planned_review_only",
                "detection_family": spl_draft_preview.get("detection_family"),
                "skip_reason": None,
            }
        elif update_spl and "spl" in updated:
            updated["spl"] = {
                **dict(updated.get("spl") or {}),
                "needed": False,
                "status": "skipped_no_deterministic_family_match",
            }
        if rag_no_match:
            updated["rag"] = {**dict(updated.get("rag") or {}), "match_status": "no_match"}
            limitations = list(updated.get("limitations") or [])
            if no_match_limitation not in limitations:
                limitations.append(no_match_limitation)
            updated["limitations"] = limitations
        return updated

    result: ChatPipelineState = dict(state)
    evidence_plan = state.get("evidence_plan")
    if isinstance(evidence_plan, dict):
        evidence_copy = dict(evidence_plan)
        resource_plan = dict(evidence_copy.get("resource_plan") or {})
        provenance = dict(resource_plan.get("provenance") or {})
        decisions = provenance.get("resource_decisions")
        if isinstance(decisions, dict):
            provenance["resource_decisions"] = update_decisions(decisions)
            resource_plan["provenance"] = provenance
            evidence_copy["resource_plan"] = resource_plan
            result["evidence_plan"] = evidence_copy

    planning = state.get("planning_decision")
    if isinstance(planning, dict) and isinstance(planning.get("resource_plan_summary"), dict):
        planning_copy = dict(planning)
        planning_copy["resource_plan_summary"] = update_decisions(planning["resource_plan_summary"])
        result["planning_decision"] = planning_copy
    return result


_ENV_HYGIENE_TOOLS_BY_QID = {
    "cisco.endpoint.044": "splunk_get_indexes",
    "cisco.endpoint.045": "splunk_get_index_info",
    "cisco.endpoint.046": "splunk_get_metadata",
    "cisco.endpoint.047": "splunk_get_knowledge_objects",
    "cisco.endpoint.048": "splunk_get_info",
}


def _environment_hygiene_envelope(state: ChatPipelineState) -> dict[str, Any] | None:
    qu = state.get("query_understanding")
    if getattr(qu, "mapped_pattern_type", None) != "environment_hygiene":
        return None
    question_ref = str(getattr(qu, "mapped_question_ref", "") or "")
    tool = _ENV_HYGIENE_TOOLS_BY_QID.get(question_ref, "splunk_get_indexes")
    preview: dict[str, Any] = {}
    trace: dict[str, Any] = {"planned_tool": tool}
    if tool in {"splunk_get_indexes", "splunk_get_metadata"} and settings.mcp_discovery_enabled:
        preview, trace = run_mcp_source_discovery(discovery_allowed=True)
    status = "planned"
    if preview:
        status = "collected_preview"
    elif not settings.mcp_discovery_enabled:
        status = "configured_unavailable"
    return {
        "status": status,
        "question_ref": question_ref or None,
        "pattern_type": "environment_hygiene",
        "needs_spl": False,
        "execution_enabled": False,
        "execution_eligible": False,
        "planned_tool": tool,
        "planned_tool_sequence": [tool],
        "preview": preview,
        "trace": trace,
        "governance": "read_only_metadata_discovery; no splunk_run_query; no live rows claimed unless collected",
        "limitations": [
            "Metadata discovery is read-only and scoped to the configured MCP service account.",
            "When MCP discovery is disabled or unavailable, this is a planned checklist rather than live Splunk state.",
        ],
    }


def _ensure_context_finalize_state(state: ChatPipelineState) -> ChatPipelineState:
    """Guarantee finalize prerequisites when LangGraph shortcuts skip execution/RAG hooks."""
    updated: ChatPipelineState = dict(state)
    if not isinstance(updated.get("execution"), dict):
        updated["execution"] = {
            "status": "skipped",
            "execution_intent": "none",
            "selected_mcp_server": None,
            "selected_mcp_tool": None,
            "tool_selection_status": "unavailable",
            "tool_selection_reason": "finalize_stage_default",
            "executed_spl": None,
            "result_count": 0,
            "results_preview": [],
            "block_reason": "finalize_stage_default",
            "duration_ms": 0,
            "evidence_source": "unavailable",
            "execution_status_label": "not_executed",
        }
    if not isinstance(updated.get("human_review"), dict):
        updated["human_review"] = no_human_review()
    if not isinstance(updated.get("workflow_plan"), dict):
        skill = str((updated.get("routed") or {}).get("skill") or "knowledge_recall")
        updated["workflow_plan"] = plan_workflow(
            selected_skill=skill,
            tool_plan=list((updated.get("routed") or {}).get("tool_plan") or []),
            query=str(getattr(updated.get("request"), "message", "") or updated.get("effective_query") or ""),
            trace_id=str(updated.get("trace_id") or "missing-trace"),
        )
    return updated


def graph_node_context_finalize(state: ChatPipelineState) -> ChatPipelineState:
    emit_stage("mapping_mitre")
    state = _ensure_context_finalize_state(state)
    request = state["request"]
    routed = state["routed"]
    trace_id = state["trace_id"]
    selected_use_case = state.get("selected_use_case")
    spl_validation = state.get("spl_validation")
    execution = state["execution"]
    route_contract_raw = state.get("route_contract")
    if isinstance(route_contract_raw, dict):
        route = RouteContract.model_validate(route_contract_raw)
    else:
        from app.chat.run_contract_builder import build_route_contract  # circular: pipeline state

        route = build_route_contract(state)
        state = {**state, "route_contract": route.model_dump(mode="json")}
    from app.chat.run_contract_builder import (  # circular: pipeline state
        build_final_evidence_gate,
        build_run_contract,
        enrich_run_contract_payload,
    )

    emit_stage("checking_sufficiency")
    source_evidence, structured_context, context_sufficiency = _context_stage(
        trace_id=trace_id,
        query=request.message,
        selected_skill=_context_selected_skill(state),
        workflow_plan=state["workflow_plan"],
        spl_validation=spl_validation,
        execution=execution,
        soc_kb_retrieval=state.get("soc_kb_retrieval"),
        evidence_plan=state.get("evidence_plan"),
        mcp_evidence=state.get("mcp_evidence"),
        reference_resolution=state.get("reference_resolution")
        if isinstance(state.get("reference_resolution"), dict)
        else None,
    )
    if not isinstance(state.get("soc_kb_retrieval"), dict):
        utility_signals = extract_query_signals(state.get("effective_query") or request.message)
        if is_universal_utility_spl_authoring(state.get("effective_query") or request.message, utility_signals):
            state = {**state, "soc_kb_retrieval": _utility_spl_rag_skipped_payload()}
    human_review = _attach_hil_soc_kb_guidance(state["human_review"], source_evidence)
    human_review = polish_spl_revision_human_review(
        human_review if isinstance(human_review, dict) else {},
        spl_validation=spl_validation if isinstance(spl_validation, dict) else None,
        candidate_spl=state.get("candidate_spl") if isinstance(state.get("candidate_spl"), dict) else None,
    )
    # FinalEvidenceGate: single cross-stream authority for evidence classification
    # and evidence-derived permissions. Computed once here, then projected by
    # RunContract and honored by MITRE/severity/renderer downstream.
    gate_state_input = {**state, "source_evidence": source_evidence}
    final_evidence_gate = build_final_evidence_gate(gate_state_input, route=route)
    gate_payload = final_evidence_gate.to_dict()
    structured_context["final_evidence_gate"] = gate_payload
    run_contract = build_run_contract(gate_state_input, route=route, gate=final_evidence_gate)
    state = {
        **state,
        "run_contract": enrich_run_contract_payload(run_contract.model_dump_canonical(), gate_state_input),
        "source_evidence": source_evidence,
        "structured_context": structured_context,
        "context_sufficiency": context_sufficiency,
        "final_evidence_gate": gate_payload,
    }
    from app.chat.canonical_facts_spine import attach_canonical_facts_to_state

    state = attach_canonical_facts_to_state(state)
    source_refs = [str(item.get("evidence_id")) for item in source_evidence]
    spl_template = template_summary(selected_use_case.default_spl_template if selected_use_case else None)
    if selected_use_case is not None:
        spl_template = _attach_spl_governance(
            spl_template,
            _runtime_spl_governance(selected_use_case.use_case_id)
            or enrichment_spl_governance(selected_use_case.use_case_id),
        )
    provenance = routed.get("routing_provenance") if isinstance(routed.get("routing_provenance"), dict) else {}
    mapped_refs = provenance.get("mapped_use_case_ids") if isinstance(provenance.get("mapped_use_case_ids"), list) else []
    use_case_id = selected_use_case.use_case_id if selected_use_case else (str(mapped_refs[0]) if mapped_refs else None)
    question_ref = provenance.get("mapped_question_ref") if isinstance(provenance.get("mapped_question_ref"), str) else None
    session_resolution = state.get("session_context_resolution")
    session_alert_context = bool(
        isinstance(session_resolution, SessionContextResolution) and session_resolution.session_alert_context
    )
    branch_mappings, branch_decision, mitre_branch = run_mitre_evidence_branch(
        query=state.get("effective_query") or request.message,
        question_ref=question_ref,
        use_case_id=_mitre_use_case_for_query(
            state.get("effective_query") or request.message,
            use_case_id,
            state.get("intent_classification"),
        ),
        source_refs=source_refs,
        intent_classification=state.get("intent_classification"),
        evidence_plan=state.get("evidence_plan"),
        planning_decision=state.get("planning_decision"),
        query_signals=_query_signals_from_state(state),
        source_evidence=source_evidence,
        structured_context=structured_context,
        alert_context_present=_mitre_alert_context_present(
            state.get("effective_query") or request.message,
            session_alert_context=session_alert_context,
        ),
        execution=execution,
    )
    if mitre_branch.ran:
        mitre_mappings, mitre_decision = branch_mappings, branch_decision
    elif (
        settings.ai_soc_planner_mitre_branch_enabled
        and mitre_branch.status == "not_applicable"
    ):
        mitre_mappings, mitre_decision = [], planner_mitre_branch_suppressed_decision(
            use_case_id=use_case_id,
            question_ref=question_ref,
            reason=str(mitre_branch.reason),
        )
    else:
        mitre_mappings, mitre_decision = _mitre_outputs_for_finalize(
            query=state.get("effective_query") or request.message,
            question_ref=question_ref,
            use_case_id=use_case_id,
            source_refs=source_refs,
            intent_classification=state.get("intent_classification"),
            evidence_plan=state.get("evidence_plan"),
            planning_decision=state.get("planning_decision"),
            query_signals=_query_signals_from_state(state),
            source_evidence=source_evidence,
            structured_context=structured_context,
            session_alert_context=session_alert_context,
            execution=execution,
            canonical_facts=state.get("canonical_facts"),
        )
    state = {
        **state,
        "mitre_decision": mitre_decision,
        "mitre_mappings": mitre_mappings,
    }
    state = attach_canonical_facts_to_state(state)
    # Item 5.3 (2026-07-03): record a best-effort CanonicalFacts snapshot +
    # LLM-plan-bridge promotion verdict at synthesis time into the trace spine.
    # Never allowed to break chat — telemetry failure degrades to a missing
    # trace event, never a broken response.
    try:
        from app.chat.canonical_facts_spine import synthesis_fact_summary
        from app.chat.contracts.canonical_facts import CanonicalFacts

        raw_facts = state.get("canonical_facts")
        if isinstance(raw_facts, dict):
            fact_summary = synthesis_fact_summary(CanonicalFacts.model_validate(raw_facts))
            evidence_plan_for_verdict = state.get("evidence_plan")
            resource_plan_for_verdict = (
                evidence_plan_for_verdict.get("resource_plan")
                if isinstance(evidence_plan_for_verdict, dict)
                else None
            )
            provenance_for_verdict = (
                resource_plan_for_verdict.get("provenance")
                if isinstance(resource_plan_for_verdict, dict)
                else None
            )
            promotion_verdict = (
                provenance_for_verdict.get("llm_bridge")
                if isinstance(provenance_for_verdict, dict)
                else None
            )
            _routes_chat().get_telemetry_connector().record_step(
                trace_id,
                "canonical_facts_snapshot",
                "recorded",
                fact_count=fact_summary.get("fact_count"),
                kinds=fact_summary.get("kinds"),
                promotion_verdict=promotion_verdict,
            )
    except Exception:  # noqa: BLE001 - telemetry must never break chat
        logger.warning("canonical_facts_snapshot_telemetry_failed", exc_info=True)
    # Item 5.4 (2026-07-03): wire the grounding assembler to the CanonicalFacts
    # spine so it quotes row-derived evidence with lineage when evidence was
    # executed, and states the gap honestly when it wasn't. Advisory context
    # only — deterministic facts remain overlay authority via existing
    # adapter/validators; this never influences execution_eligible or
    # severity/MITRE-status decisions.
    try:
        raw_facts_for_grounding = state.get("canonical_facts")
        if isinstance(raw_facts_for_grounding, dict):
            from app.chat.contracts.canonical_facts import CanonicalFacts
            from app.chat.grounding_assembler import assemble_grounding_from_facts
            from app.threat.attack_data_resolver import technique_resolver_from_settings

            grounding_block = assemble_grounding_from_facts(
                CanonicalFacts.model_validate(raw_facts_for_grounding),
                state.get("effective_query") or request.message,
                resolver=technique_resolver_from_settings(),
            )
            state = {**state, "grounding_block": grounding_block.to_dict()}
    except Exception:  # noqa: BLE001 - grounding is advisory, never breaks chat
        logger.warning("grounding_block_assembly_failed", exc_info=True)
    mitre_branch_payload = mitre_branch.model_dump()
    response_use_case = _response_use_case(state)
    severity_decision = decide_severity(
        response_use_case.use_case_id if response_use_case else None,
        structured_context,
        source_refs,
    )
    guard_signals = _query_signals_from_state(state) or {}
    guard_intent = (
        state.get("intent_classification")
        if isinstance(state.get("intent_classification"), dict)
        else {}
    )
    # The guard needs an explicit alert reference (ALT-style id, "for alert",
    # or pinned session alert), not the looser alert_context_present signal —
    # that regex also matches prose like "alert network events" and would let
    # the P3 default leak onto pure analytics questions.
    guard_query_text = state.get("effective_query") or request.message
    guard_alert_reference = bool(
        session_alert_context
        or re.search(r"\balt-\d{4}-\d+\b", guard_query_text, re.IGNORECASE)
        or re.search(r"\bfor alert\b", guard_query_text, re.IGNORECASE)
        or re.search(r"\balert[_\s]?id\b", guard_query_text, re.IGNORECASE)
    )
    severity_decision = apply_analytics_severity_guard(
        severity_decision,
        # Phase 2: any analytics/query-shaped or clarification answer without
        # alert evidence gets "Not assigned". Active use-case severity policies
        # still win inside the guard (default_no_policy check).
        analytics_query=bool(
            guard_signals.get("exact_105_analytics")
            or guard_signals.get("exact_105_hunt_spl")
            or guard_signals.get("analytics_aggregation")
            or guard_signals.get("live_data_request")
            or guard_intent.get("intent_family")
            in (
                "spl_generation_only",
                "live_investigation",
                "clarification_required",
                "guided_investigation",
            )
        ),
        alert_context_present=guard_alert_reference,
    )
    # FinalEvidenceGate authority: when the gate disallows a severity assessment,
    # cap the displayed severity to "Not assigned" BEFORE it feeds action
    # capability, lineage, governance trace, and the response payload — so every
    # surface honors the gate, not just the analyst card via AnswerContract.
    severity_decision = apply_gate_severity_cap(
        severity_decision,
        allow_severity_assessment=run_contract.allow_severity_assessment,
    )
    # A T1 SPL-native review-only draft is a pure SPL-artifact request: no
    # collected evidence and no alert context. Severity must not be assigned even
    # if a co-matched use-case (e.g. an IT-to-OT boundary row) carries a P-policy.
    if _is_t2_review_only(state.get("candidate_spl"), spl_validation):
        severity_decision = apply_gate_severity_cap(
            severity_decision,
            allow_severity_assessment=False,
        )
    action_capability = action_capability_for(
        response_use_case.use_case_id if response_use_case else None,
        severity_decision.severity_label,
        hil_required=run_contract.effective_hil_required,
    )
    emit_stage("generating_answer")
    _skip_registry_warnings, _skip_catalog_row = _composer_skip_registry_context(state)
    close_retrieval_spl_phase()
    synthesis_lab = run_governed_synthesis_lab(
        structured_context=structured_context,
        source_evidence=source_evidence,
        context_sufficiency=context_sufficiency,
        mitre_mappings=mitre_mappings,
        action_capability=action_capability,
        severity_label=severity_decision.severity_label,
        spl_validation=spl_validation,
        human_review=human_review,
        match_path=_match_path_from_state(state),
        promotion_lifecycle_summary=_promotion_lifecycle_for_composer_skip(state),
        registry_warnings=_skip_registry_warnings,
        catalog_row=_skip_catalog_row,
    )
    synthesis_status = synthesis_lab.status
    context_sufficiency = apply_synthesis_allowed_to_sufficiency(
        context_sufficiency,
        package=synthesis_lab.package,
    )
    emit_stage("validating_answer")
    answer_guard = run_answer_guard_lab(
        draft=synthesis_lab.draft,
        package=synthesis_lab.package,
        structured_context=structured_context,
        source_evidence=source_evidence,
        severity_label=severity_decision.severity_label,
        action_policy={
            "allowed_actions": list(action_capability.allowed_actions),
            "current_tier": action_capability.current_tier,
        },
    )
    analyst_summary_from_lab: str | None = None
    if synthesis_lab.analyst_summary and synthesis_status.status in {
        "completed",
        "partial_timeout",
        "degraded",
    }:
        if not answer_guard.enabled or answer_guard.guard_status == "passed":
            analyst_summary_from_lab = synthesis_lab.analyst_summary
        elif answer_guard.guard_status == "blocked":
            human_review = {
                **human_review,
                "required": True,
                "review_type": "answer_guard_blocked",
                "safe_message_for_user": (
                    "A governed draft answer was produced but blocked by Answer Guard. "
                    "Review the technical trace and evidence package."
                ),
            }
    route_plan_shadow = state["route_plan_shadow"]
    route_authority = _route_authority_payload(route_plan_shadow)
    primary_operation = _primary_operation_from_authority(route_plan_shadow, route_authority)
    coverage_id = _coverage_id_from_authority(route_authority)
    semantic_intent = build_semantic_intent_envelope(
        query_understanding=state["query_understanding"],
        routed=routed,
        route_plan_shadow=route_plan_shadow,
        route_authority=route_authority,
        primary_operation=primary_operation,
        coverage_id=coverage_id,
    )
    operation_audit = build_operation_audit_record(
        query=request.message,
        primary_operation=primary_operation,
        coverage_id=coverage_id,
        semantic_intent=semantic_intent,
        route_plan_shadow=route_plan_shadow,
        trace_id=trace_id,
    )
    if operation_audit is not None:
        route_plan_shadow["operation_audit"] = operation_audit
    # Raw shadow authority compare has now been consumed for routing/audit logic
    # above; re-project the displayed compare so governance/lineage panels never
    # claim the legacy route is authoritative once RunContract holds authority.
    _display_compare = route_plan_shadow.get("route_authority_compare")
    if isinstance(_display_compare, dict):
        route_plan_shadow["route_authority_compare"] = project_compare_for_display(
            _display_compare,
            authority_holder=run_contract.routing.authority_holder,
            canonical_skill=run_contract.routing.canonical_skill,
            legacy_skill=run_contract.routing.legacy_skill,
        )
    investigation_lineage = build_investigation_lineage(
        trace_id=trace_id,
        mode_source="live" if run_contract.execution_authorized else "review_only",
        query_understanding=state["query_understanding"],
        selected_use_case=response_use_case,
        selected_skill_chain=state["selected_skill_chain"],
        workflow_plan=state["workflow_plan"],
        spl_validation=spl_validation,
        execution=execution,
        source_evidence=source_evidence,
        structured_context=structured_context,
        context_sufficiency=context_sufficiency,
        route_plan_shadow=route_plan_shadow,
        spl_template=spl_template,
        mitre_mappings=mitre_mappings,
        severity_decision=severity_decision,
        synthesis_status=synthesis_status,
        answer_guard_status=answer_guard,
        action_capability=action_capability,
        collected_evidence_count=run_contract.collected_evidence_count,
        execution_authorized=run_contract.execution_authorized,
        allow_results_table=run_contract.allow_results_table,
        candidate_artifact_count=run_contract.source_evidence_summary.candidate_artifact_count,
    )

    planning_decision = state.get("planning_decision")
    path_type = planning_decision.get("path_type") if isinstance(planning_decision, dict) else None
    # LangGraph parity mode: planning_decision.path_type is "hybrid_investigation" even
    # when routing resolves to guided_investigation. Downstream guards use path_type to
    # gate guided-specific logic, so normalise to the canonical skill name here.
    if is_guided_investigation_route(routed_skill=_effective_routing_skill(state), path_type=path_type):
        path_type = "guided_investigation"
    qu = state.get("query_understanding")
    entities_payload: dict[str, Any] | None = None
    if qu is not None and hasattr(qu, "entities"):
        entities_payload = qu.entities.model_dump()
    elif isinstance(qu, dict) and isinstance(qu.get("entities"), dict):
        entities_payload = qu["entities"]
    match_path_for_t2 = _candidate_match_path(state)
    evidence_plan_for_shape = state.get("evidence_plan") if isinstance(state.get("evidence_plan"), dict) else {}
    resource_plan_for_shape = (
        evidence_plan_for_shape.get("resource_plan")
        if isinstance(evidence_plan_for_shape.get("resource_plan"), dict)
        else None
    )
    message = _chat_message(
        spl_validation,
        execution,
        analyst_summary_from_lab,
        evidence_plan=state.get("evidence_plan"),
        planning_decision=planning_decision,
        soc_kb_retrieval=state.get("soc_kb_retrieval"),
        user_query=request.message,
        entities=entities_payload,
        match_path=match_path_for_t2,
        intent_classification=state.get("intent_classification")
        if isinstance(state.get("intent_classification"), dict)
        else None,
        spl_draft_preview=state.get("spl_draft_preview")
        if isinstance(state.get("spl_draft_preview"), dict)
        else None,
        llm_intent_advisory=state.get("llm_intent_advisory"),
    )
    _intent_payload = state.get("intent_classification") if isinstance(state.get("intent_classification"), dict) else {}
    from app.synthesis.deterministic_prose_stitch import apply_deterministic_prose_enhancements

    message = apply_deterministic_prose_enhancements(
        message,
        user_query=request.message,
        intent_family=str(_intent_payload.get("intent_family") or "") or None,
        primary_intent=str(_intent_payload.get("primary_intent") or "") or None,
    )
    note = _chat_note(
        spl_validation,
        execution,
        evidence_plan=state.get("evidence_plan"),
        planning_decision=state.get("planning_decision"),
        soc_kb_retrieval=state.get("soc_kb_retrieval"),
    )
    if synthesis_status.status == "partial_timeout":
        message = _PARTIAL_SYNTHESIS_MESSAGE
        note = _PARTIAL_SYNTHESIS_MESSAGE
    candidate_spl = state.get("candidate_spl")
    spl_draft_preview = state.get("spl_draft_preview")
    llm_spl_candidate = state.get("llm_spl_candidate")
    environment_hygiene = _environment_hygiene_envelope(state)
    if environment_hygiene is not None:
        tool = str(environment_hygiene.get("planned_tool") or "splunk_get_indexes")
        message = (
            "Environment metadata hygiene is a read-only discovery path. "
            f"The governed next step is {tool}; SPL search generation and execution remain disabled."
        )
        note = "Metadata hygiene answer path selected; no candidate SPL or MCP search execution."
        spl_draft_preview = None
    if _session_stale_clarification_required(state):
        human_review = _session_stale_clarification_review()
        message = human_review["safe_message_for_user"]
        note = "Session context was stale or insufficient; clarification is required."
    elif _needs_mitre_clarification(
        request.message,
        candidate_spl,
        session_alert_context=session_alert_context,
        query_signals=_query_signals_from_state(state),
        intent_classification=state.get("intent_classification")
        if isinstance(state.get("intent_classification"), dict)
        else None,
    ):
        human_review = _mitre_clarification_review()
        message = (
            "I need alert context before mapping to MITRE ATT&CK. Share the alert title, "
            "detection rule, notable/event ID, or the SPL and a few sample fields."
        )
        note = "MITRE mapping requires grounded alert context; no SPL was generated."
    elif _is_t2_review_only(candidate_spl, spl_validation):
        # T1 SPL-native review-only draft: a renderable, non-executable SPL draft.
        # This is a review state, not a clarification — the analyst validates the
        # source profile/fields before any execution path. The review-only renderer
        # owns the visible message (the SPL is shown).
        human_review = _t2_review_only_review()
        note = "Review-only SPL draft produced; analyst validation required before any execution. Nothing was executed."
        if path_type == "guided_investigation" and isinstance(candidate_spl, dict):
            spl_text = str(candidate_spl.get("candidate_spl") or "").strip()
            if spl_text and spl_text not in message:
                spl_block = (
                    "Review-only SPL draft (not executed):\n"
                    f"```\n{spl_text}\n```"
                )
                message = f"{message.strip()}\n\n{spl_block}".strip()
    elif _is_universal_spl_authoring_review(candidate_spl, spl_validation):
        human_review = _universal_spl_authoring_review()
        note = (
            "Universal/template-free review-only SPL draft produced; analyst validation required "
            "before any execution. Nothing was executed."
        )
        if isinstance(candidate_spl, dict):
            spl_text = str(candidate_spl.get("candidate_spl") or "").strip()
            if spl_text:
                spl_block = (
                    "Review-only universal SPL draft (template-free, not executed):\n"
                    f"```\n{spl_text}\n```"
                )
                message = spl_block
    elif _is_spl_clarification_required(spl_validation):
        human_review = _spl_clarification_review(spl_validation)
        message = human_review["safe_message_for_user"]
        note = "No governed candidate SPL was produced; clarification is required before validation or execution."
    elif path_type == "unsafe_blocked":
        from app.chat.guidance_templates import build_spl_execution_refusal_guidance, is_explicit_run_spl_query

        signals_for_review = extract_query_signals(request.message)
        if is_explicit_run_spl_query(request.message) and not signals_for_review.get("block_or_contain"):
            from app.orchestration.human_review import human_review as build_human_review

            hil_review = build_human_review(
                "execution_approval",
                "explicit_run_spl_blocked",
                "soc_analyst",
                ["provide_investigation_guidance", "cancel"],
                build_spl_execution_refusal_guidance(),
            )
            human_review = hil_review
            message = hil_review["safe_message_for_user"]
            note = "Explicit SPL execution/results request blocked; HIL approval required."
        else:
            human_review = _unsafe_action_review()
            message = human_review["safe_message_for_user"]
            note = "Unsafe containment/enforcement request blocked; HIL approval required before any action."
    else:
        audit_review = operation_audit_human_review(operation_audit)
        if audit_review is not None:
            human_review = audit_review
            message = audit_review["safe_message_for_user"]
            note = "Novel operation proposals stop at audit/HIL; no MCP or SPL execution is authorized."

    from app.chat.explicit_run_spl_hil import apply_explicit_run_spl_hil_wiring

    human_review, execution = apply_explicit_run_spl_hil_wiring(
        user_query=request.message,
        path_type=path_type,
        human_review=human_review if isinstance(human_review, dict) else None,
        execution=execution if isinstance(execution, dict) else None,
    )

    if (
        spl_draft_preview
        and synthesis_status.status != "partial_timeout"
        and not _is_governed_spl_ready_for_response(spl_validation)
    ):
        shaped_non_hunt = (
            settings.ai_soc_t2_answer_shape_enabled
            and bool(request.message)
            and not should_bypass_shape_router(match_path_for_t2)
            and classify_answer_shape(
                request.message,
                entities=entities_payload,
                resource_plan=resource_plan_for_shape,
            ).primary_shape
            != "hunt"
        )
        draft_block = build_draft_preview_analyst_message(spl_draft_preview)
        if shaped_non_hunt:
            # Keep shaped guidance as the answer body; append draft when surfacing is off.
            if not settings.ai_soc_t2_answer_surfacing_enabled and draft_block not in message:
                message = f"{message}\n\n{draft_block}".strip()
        elif settings.ai_soc_t2_answer_surfacing_enabled:
            pass
        else:
            message = draft_block
        if isinstance(spl_draft_preview, dict) and spl_draft_preview.get("detection_family") == "universal_timestamp_spl":
            note = "Review-only universal SPL utility draft; no MCP execution was run."
        else:
            note = (
                "Governed template SPL was not produced. HIL/SOC review is required. "
                "No MCP execution was run."
            )
        if (
            not human_review.get("required")
            and human_review.get("review_type") != "spl_source_profile_clarification"
            and isinstance(spl_validation, dict)
            and spl_validation.get("approved") is False
        ):
            from app.orchestration.human_review import human_review as build_human_review

            human_review = build_human_review(
                "spl_revision",
                "lab_draft_preview_review_required",
                "soc_analyst",
                ["review_draft_spl", "confirm_source_profile", "cancel"],
                message,
            )

    evidence_origin = resolve_response_evidence_origin(
        source_evidence=source_evidence,
        soc_kb_retrieval=state.get("soc_kb_retrieval"),
        execution=execution,
    )
    answer_readiness = resolve_answer_readiness(
        evidence_origin=evidence_origin,
        context_sufficiency=context_sufficiency,
    )
    if evidence_origin:
        reasons = list(context_sufficiency.get("reasons") or [])
        label = f"evidence_origin:{evidence_origin}"
        if label not in reasons:
            reasons.append(label)
            context_sufficiency = {**context_sufficiency, "reasons": sorted(reasons)}

    comparison = state.get("comparison") or {}
    governance_trace = build_governance_trace(
        demo_mode=False,
        use_case_id=response_use_case.use_case_id if response_use_case else None,
        selected_skill=_effective_routing_skill(state),
        severity_decision=severity_decision,
        investigation_lineage=investigation_lineage,
        source_evidence=source_evidence,
        execution=execution,
        route_plan_shadow=route_plan_shadow,
        question_runtime_map=route_plan_shadow.get("question_runtime_map") if route_plan_shadow else None,
        precondition_evaluation=route_plan_shadow.get("precondition_evaluation") if route_plan_shadow else None,
        selected_use_case=response_use_case.model_dump() if response_use_case else None,
    )

    routing_skill_resolution = state.get("routing_skill_resolution") or route_plan_shadow.get(
        "routing_skill_resolution"
    )
    response_mode = _response_mode(context_sufficiency, human_review, spl_validation)
    synthesis_mode = _synthesis_mode(synthesis_status, analyst_summary_from_lab)
    use_case_label = None
    if response_use_case is not None:
        catalog_label = getattr(response_use_case, "display_name", None) or getattr(
            response_use_case, "use_case_id", None
        )
        use_case_label = resolve_analyst_use_case_label(
            use_case_id=getattr(response_use_case, "use_case_id", None),
            catalog_label=str(catalog_label) if catalog_label else None,
            user_query=request.message,
        )
    intent_classification = state.get("intent_classification")
    if intent_classification is None and isinstance(state.get("query_to_intent"), dict):
        intent_classification = state.get("query_to_intent", {}).get("intent_classification")
    resolved_use_case_id = (
        response_use_case.use_case_id if response_use_case is not None else use_case_id
    )
    from app.spl.draft_preview_customization import reconcile_evidence_plan_for_draft_preview

    evidence_plan_for_analyst = resolve_analyst_evidence_plan(
        state.get("evidence_plan"),
        use_case_id=resolved_use_case_id,
        intent_classification=intent_classification,
        query_to_intent=state.get("query_to_intent"),
        query_understanding=state.get("query_understanding"),
    )
    evidence_plan_for_analyst = reconcile_evidence_plan_for_draft_preview(
        evidence_plan_for_analyst,
        spl_draft_preview if isinstance(spl_draft_preview, dict) else None,
    )
    answer_contract = None
    hybrid_role_plan = None
    missing_evidence_reasoning_trace: dict[str, Any] | None = None
    llm_turn_budget_trace: dict[str, Any] | None = None
    guided_grounding_block = None
    contract_evidence_plan = evidence_plan_for_analyst
    # Contract is a read-model that drives the section-ordered analyst card; build it
    # for every classified answer so no path falls back to a one-paragraph bubble.
    if intent_classification or True or contract_evidence_plan:
        answer_contract = build_answer_contract(
            intent_classification=intent_classification,
            evidence_plan=contract_evidence_plan,
            mitre_decision=mitre_decision,
            severity_decision=severity_decision,
            spl_validation=spl_validation,
            execution=execution,
            human_review=human_review,
            mitre_mappings=mitre_mappings or [],
            mitre_branch_result=mitre_branch_payload,
            candidate_spl=candidate_spl if isinstance(candidate_spl, dict) else None,
            user_query=request.message,
            query_signals=_query_signals_from_state(state),
            use_case_id=resolved_use_case_id,
            match_path=_candidate_match_path(state),
            spl_draft_preview=spl_draft_preview if isinstance(spl_draft_preview, dict) else None,
            run_contract=run_contract,
            canonical_status=(
                (state.get("canonical_planning_outcome") or {}).get("status")
                if isinstance(state.get("canonical_planning_outcome"), dict)
                else None
            ),
        )
        if path_type == "guided_investigation" and _rag_no_match(state.get("soc_kb_retrieval")):
            limitations = list(answer_contract.limitations)
            no_match_limitation = (
                "No governed playbook matched this hunt; the checklist is general guidance and must be "
                "validated against local telemetry and policy."
            )
            if no_match_limitation not in limitations:
                limitations.append(no_match_limitation)
                answer_contract = answer_contract.model_copy(update={"limitations": limitations})
        if (
            path_type == "guided_investigation"
            and settings.ai_soc_guided_mcp_discovery_enabled
            and answer_contract is not None
        ):
            promotion_offer = build_guided_discovery_promotion_offer(
                state.get("mcp_evidence") if isinstance(state.get("mcp_evidence"), list) else None
            )
            if promotion_offer is not None:
                answer_contract = answer_contract.model_copy(update={"promotion_offer": promotion_offer})
        if (
            path_type == "guided_investigation"
            and settings.ai_soc_guided_hybrid_investigation_enabled
            and answer_contract is not None
        ):
            answer_contract = enhance_answer_contract_for_guided_hybrid(
                answer_contract,
                guided_handoff=state.get("guided_handoff_trace")
                if isinstance(state.get("guided_handoff_trace"), dict)
                else None,
                mcp_evidence=state.get("mcp_evidence")
                if isinstance(state.get("mcp_evidence"), list)
                else None,
                evidence_plan=contract_evidence_plan,
            )
        if path_type == "guided_investigation":
            guided_grounding_block = build_guided_hunt_grounding(
                query=request.message,
                answer_contract=answer_contract,
                soc_kb_retrieval=state.get("soc_kb_retrieval")
                if isinstance(state.get("soc_kb_retrieval"), dict)
                else None,
            )
            merged_limits = list(answer_contract.limitations)
            if T2_UNVERIFIED_BANNER not in merged_limits:
                merged_limits.append(T2_UNVERIFIED_BANNER)
                answer_contract = answer_contract.model_copy(update={"limitations": merged_limits})
        from app.chat.guidance_templates import should_skip_llm_composer as _skip_composer_fn

        _intent_family = ""
        if isinstance(intent_classification, dict):
            _intent_family = str(intent_classification.get("intent_family") or "")
        _registry_warnings, _catalog_row = _composer_skip_registry_context(state)
        _query_signals = _query_signals_from_state(state) or {}
        _skip_comp, _skip_comp_reason = _skip_composer_fn(
            query=request.message,
            path_type=path_type,
            intent_family=_intent_family or None,
            use_case_review_guidance=bool(_query_signals.get("use_case_review_guidance")),
            match_path=_match_path_from_state(state),
            promotion_lifecycle_summary=_promotion_lifecycle_for_composer_skip(state),
            registry_warnings=_registry_warnings,
            catalog_row=_catalog_row,
            selected_skill=_effective_routing_skill(state),
        )
        _draft_preview_active = isinstance(spl_draft_preview, dict) and bool(
            str(spl_draft_preview.get("draft_spl") or "").strip()
        )
        _llm_adv = state.get("llm_intent_advisory")
        _intent_skipped = bool(getattr(_llm_adv, "dropped_reasons", None)) if _llm_adv is not None else True
        _intent_skip = (
            (_llm_adv.dropped_reasons or [None])[0]
            if _llm_adv is not None and getattr(_llm_adv, "dropped_reasons", None)
            else None
        )
        from app.llm.hybrid_role_graph import build_hybrid_role_plan

        hybrid_role_plan = build_hybrid_role_plan(
            query=request.message,
            match_path=_candidate_match_path(state),
            selected_skill=_effective_routing_skill(state),
            answer_contract=answer_contract,
            path_type=path_type,
            intent_family=_intent_family or None,
            draft_preview_active=_draft_preview_active,
            skip_composer=_skip_comp,
            skip_composer_reason=_skip_comp_reason,
            intent_advisory_skipped=_intent_skipped,
            intent_skip_reason=_intent_skip,
            soc_investigation_shaped=bool(
                getattr(state.get("query_understanding"), "soc_investigation_shaped", False)
            ),
        )
        budget = state.get("llm_turn_budget") or TurnLlmBudget()
        if not hybrid_role_plan.role_enabled("missing_evidence_reasoner"):
            reasoner_result = MissingEvidenceReasonerResult(
                skipped_reason=hybrid_role_plan.skip_reason("missing_evidence_reasoner")
            )
        elif (hop_block := budget.sidecar_hop_blocked(role="missing_evidence_reasoner")):
            reasoner_result = MissingEvidenceReasonerResult(skipped_reason=hop_block)
        else:
            _reasoner_timeout = budget.capped_hop_timeout_seconds(role="missing_evidence_reasoner")
            if _reasoner_timeout is None:
                reasoner_result = MissingEvidenceReasonerResult(
                    skipped_reason="insufficient_deadline_reserve"
                )
            else:
                _t0 = time.monotonic()
                reasoner_result = run_missing_evidence_reasoner(
                    contract=answer_contract,
                    query=request.message,
                    resource_decisions=_resource_decision_labels(state),
                    timeout_seconds=_reasoner_timeout,
                    allow_failover=not budget.time_budget_exhausted(),
                )
                if reasoner_result.llm_called:
                    budget.record_sidecar(
                        role="missing_evidence_reasoner",
                        provider_label=reasoner_result.provider_label,
                        outcome="timed_out" if reasoner_result.timed_out else "completed",
                        latency_ms=int((time.monotonic() - _t0) * 1000),
                    )
        if reasoner_result.bullets:
            merged_limits = list(answer_contract.limitations)
            for bullet in reasoner_result.bullets:
                if bullet not in merged_limits:
                    merged_limits.append(bullet)
            answer_contract = answer_contract.model_copy(update={"limitations": merged_limits})
        missing_evidence_reasoning_trace = reasoner_result.to_trace_dict()
        llm_turn_budget_trace = budget.to_trace_dict()
        # Plan §3 A4b: surface the CVE snapshot status in the visible analyst card
        # (advisory; never a confirmed unpatched-CVE claim without join keys).
        _vuln_line = vulnerability_context_line(
            structured_context.get("vulnerability_source") if isinstance(structured_context, dict) else None
        )
        if _vuln_line:
            _limits = list(answer_contract.limitations)
            if _vuln_line not in _limits:
                _limits.append(_vuln_line)
                answer_contract = answer_contract.model_copy(update={"limitations": _limits})
    else:
        missing_evidence_reasoning_trace = None
        llm_turn_budget_trace = None
    answer_contract_payload = answer_contract.model_dump() if answer_contract is not None else None
    from app.chat.planning_telemetry import emit_request_completed
    from app.chat.response_validation import (
        emit_request_failed,
        emit_response_generated,
        emit_response_validated,
        validate_assembled_response,
        validate_final_response,
    )

    validation_outcome, validation_reasons = validate_final_response(state)
    state = emit_response_validated(state, ok=validation_outcome == "ok", reasons=validation_reasons)
    if validation_outcome != "ok":
        state = emit_request_failed(state, reason="response_validation_failed")
    analyst_response = build_analyst_response_for_live(
        user_query=request.message,
        message=message,
        analyst_summary=analyst_summary_from_lab,
        source_evidence=source_evidence,
        mitre_mappings=mitre_mappings or [],
        mitre_decision=mitre_decision,
        severity_label=severity_decision.severity_label,
        synthesis_draft=synthesis_lab.draft,
        human_review=human_review,
        selected_use_case_label=str(use_case_label) if use_case_label else None,
        candidate_spl=candidate_spl,
        spl_validation=spl_validation,
        execution=execution,
        intent_classification=intent_classification,
        evidence_plan=evidence_plan_for_analyst,
        severity_decision=severity_decision,
        answer_contract=answer_contract,
        spl_draft_preview=spl_draft_preview if isinstance(spl_draft_preview, dict) else None,
        llm_spl_candidate=llm_spl_candidate if isinstance(llm_spl_candidate, dict) else None,
    )
    if analyst_response is None:
        reference_facts_for_card = _reference_facts_for_card(structured_context)
        if reference_facts_for_card:
            reference_summary = _reference_lookup_summary(
                reference_facts_for_card,
                user_query=request.message,
                source_evidence=source_evidence,
            )
            reference_lead = reference_one_sentence_lead(
                reference_facts_for_card,
                user_query=request.message,
            )
            llm_intro = (
                str(analyst_summary_from_lab or "").strip()
                if synthesis_status.provider == "local_model"
                else None
            )
            message = merge_reference_message_with_llm_intro(
                reference_summary,
                llm_intro=llm_intro,
            )
            reference_actions = [
                "Use the cited offline reference rows as taxonomy context only.",
                "Do not treat taxonomy relevance as observed activity in local telemetry.",
                "Collect live evidence separately before claiming exploitation, severity, or confirmed technique use.",
            ]
            analyst_response = AnalystResponseEnvelope(
                finding_title="Reference taxonomy lookup",
                one_sentence_finding=(llm_intro or reference_lead)[:1200],
                direct_answer_summary=reference_summary[:4000],
                recommended_actions=reference_actions,
                analyst_checklist=reference_actions,
                investigation_steps=reference_actions,
                response_profile="knowledge_recall",
                execution_status=str(execution.get("status") or "skipped"),
                reference_facts=reference_facts_for_card[:10],
                retrieved_playbook=build_reference_source_playbook(
                    reference_facts_for_card[:10],
                    source_evidence=source_evidence,
                ),
            )
    if environment_hygiene is not None and analyst_response is not None:
        limitations = list(analyst_response.limitations or [])
        for item in environment_hygiene.get("limitations") or []:
            if str(item) not in limitations:
                limitations.append(str(item))
        checklist = list(analyst_response.analyst_checklist or [])
        planned_tool = str(environment_hygiene.get("planned_tool") or "splunk_get_indexes")
        planned_item = f"Review planned read-only metadata tool: {planned_tool}."
        if planned_item not in checklist:
            checklist.append(planned_item)
        analyst_response = analyst_response.model_copy(
            update={
                "direct_answer_summary": message,
                "environment_hygiene": environment_hygiene,
                "limitations": limitations,
                "analyst_checklist": checklist,
                "spl_status": "metadata_only_no_spl",
                "execution_status_label": "review_only_not_executed",
            }
        )
    mitre_risk_rationale_trace: dict[str, Any] | None = None
    resource_plan_shadow_trace: dict[str, Any] | None = None
    if answer_contract is not None and analyst_response is not None:
        budget = state.get("llm_turn_budget") or TurnLlmBudget()
        draft_preview_active = isinstance(spl_draft_preview, dict) and bool(
            str(spl_draft_preview.get("draft_spl") or "").strip()
        )
        if draft_preview_active:
            mitre_risk_rationale_trace = {
                "llm_called": False,
                "guard_status": "skipped",
                "fallback_used": True,
                "skipped_reason": "draft_spl_preview_active",
                "provider_label": None,
                "severity_rationale_present": bool(analyst_response.severity_rationale),
                "mitre_rationale_present": bool(analyst_response.foundation_sec_analysis),
                "adapter_warnings": [],
            }
        elif hybrid_role_plan is None or not hybrid_role_plan.role_enabled("mitre_reasoner"):
            rationale_result = MitreRiskRationaleResult(
                severity_rationale_prose=build_deterministic_severity_rationale(severity_decision),
                mitre_rationale_prose=build_deterministic_mitre_rationale(
                    contract=answer_contract,
                    mitre_branch_result=mitre_branch_payload if isinstance(mitre_branch_payload, dict) else None,
                ),
                guard_status="skipped",
                fallback_used=True,
                skipped_reason=(
                    hybrid_role_plan.skip_reason("mitre_reasoner")
                    if hybrid_role_plan is not None
                    else "hybrid_plan_unavailable"
                ),
            )
            mitre_risk_rationale_trace = rationale_result.to_trace_dict()
        else:
            rationale_result = run_mitre_risk_rationale(
                contract=answer_contract,
                query=request.message,
                severity_decision=severity_decision,
                mitre_decision=mitre_decision if isinstance(mitre_decision, dict) else None,
                mitre_branch_result=mitre_branch_payload if isinstance(mitre_branch_payload, dict) else None,
                budget_exhausted=budget.sidecar_hop_blocked(role="mitre_reasoner") is not None,
                budget=budget,  # per-internal-call accounting (mitre + risk = up to 2 slots)
            )
            mitre_risk_rationale_trace = rationale_result.to_trace_dict()
            rationale_updates: dict[str, Any] = {}
            if rationale_result.severity_rationale_prose:
                rationale_updates["severity_rationale"] = rationale_result.severity_rationale_prose
            if rationale_result.mitre_rationale_prose:
                rationale_updates["foundation_sec_analysis"] = rationale_result.mitre_rationale_prose
            if rationale_updates:
                analyst_response = analyst_response.model_copy(update=rationale_updates)
            if llm_turn_budget_trace is not None:
                llm_turn_budget_trace = budget.to_trace_dict()

        evidence_plan_payload = state.get("evidence_plan") if isinstance(state.get("evidence_plan"), dict) else None
        live_plan_source = None
        if isinstance(evidence_plan_payload, dict):
            live_resource_plan = evidence_plan_payload.get("resource_plan")
            if isinstance(live_resource_plan, dict):
                live_plan_source = live_resource_plan.get("plan_source")
        if draft_preview_active:
            resource_plan_shadow_trace = {"llm_called": False, "skipped_reason": "draft_spl_preview_active"}
        elif hybrid_role_plan is None or not hybrid_role_plan.role_enabled("route_plan_candidate_generator"):
            resource_plan_shadow_trace = {
                "llm_called": False,
                "skipped_reason": (
                    hybrid_role_plan.skip_reason("route_plan_candidate_generator")
                    if hybrid_role_plan is not None
                    else "hybrid_plan_unavailable"
                ),
            }
        elif (hop_block := budget.sidecar_hop_blocked(role="route_plan_candidate_generator")):
            resource_plan_shadow_trace = {"llm_called": False, "skipped_reason": hop_block}
        else:
            _inline_bridge = None
            if isinstance(evidence_plan_payload, dict):
                live_resource_plan = evidence_plan_payload.get("resource_plan")
                if isinstance(live_resource_plan, dict):
                    _inline_bridge = (live_resource_plan.get("provenance") or {}).get("llm_bridge")
            if _inline_bridge == "promoted":
                live_steps = (
                    (evidence_plan_payload.get("resource_plan") or {}).get("steps")
                    if isinstance(evidence_plan_payload, dict)
                    else None
                )
                resource_plan_shadow_trace = {
                    "shadow_only": True,
                    "promotion_blocked": False,
                    "llm_called": True,
                    "deterministic_plan_source": live_plan_source or "deterministic",
                    "skipped_reason": "promoted_inline",
                    "shadow_plan_source": (evidence_plan_payload or {}).get("resource_plan", {}).get("plan_source"),
                    "shadow_step_count": len(live_steps or []),
                    "shadow_provenance": (evidence_plan_payload or {}).get("resource_plan", {}).get("provenance"),
                    "live_plan_source_unchanged": False,
                }
            else:
                _t0 = time.monotonic()
                shadow_result = run_resource_plan_shadow(
                    query=request.message,
                    match_path=_match_path_from_state(state),
                    evidence_plan=evidence_plan_payload,
                )
                resource_plan_shadow_trace = shadow_result.to_trace_dict()
                if shadow_result.llm_called:
                    budget.record_sidecar(
                        role="route_plan_candidate_generator",
                        provider_label="local_or_failover",
                        outcome="completed",
                        latency_ms=int((time.monotonic() - _t0) * 1000),
                    )
                if isinstance(evidence_plan_payload, dict):
                    after_source = (evidence_plan_payload.get("resource_plan") or {}).get("plan_source")
                    if live_plan_source is not None:
                        resource_plan_shadow_trace["live_plan_source_unchanged"] = after_source == live_plan_source
        if llm_turn_budget_trace is not None:
            llm_turn_budget_trace = budget.to_trace_dict()
    composer_trace: dict[str, Any] = build_composer_runtime_status()
    from app.chat.guidance_templates import should_skip_llm_composer

    intent_family = ""
    if isinstance(state.get("intent_classification"), dict):
        intent_family = str(state["intent_classification"].get("intent_family") or "")
    _registry_warnings, _catalog_row = _composer_skip_registry_context(state)
    query_signals = _query_signals_from_state(state) or {}
    skip_composer, skip_reason = should_skip_llm_composer(
        query=request.message,
        path_type=path_type,
        intent_family=intent_family or None,
        use_case_review_guidance=bool(query_signals.get("use_case_review_guidance")),
        match_path=_match_path_from_state(state),
        promotion_lifecycle_summary=_promotion_lifecycle_for_composer_skip(state),
        registry_warnings=_registry_warnings,
        catalog_row=_catalog_row,
        selected_skill=_effective_routing_skill(state),
    )
    lab_already_narrated = synthesis_status.provider == "local_model"
    if lab_already_narrated:
        composer_trace = {
            **composer_trace,
            "llm_composer_skipped_reason": "synthesis_lab_already_narrated",
        }
    if (
        answer_contract is not None
        and analyst_response is not None
        and hybrid_role_plan is not None
        and hybrid_role_plan.role_enabled("governed_composer")
        and not skip_composer
        and not lab_already_narrated
    ):
        budget = state.get("llm_turn_budget") or TurnLlmBudget()
        # Do not start slow narration when its configured socket window cannot fit
        # inside the remaining turn budget. The deterministic envelope is complete.
        narration_reserve = budget.composer_reserve_seconds()
        if (hop_block := budget.narration_hop_blocked(reserve_seconds=narration_reserve)):
            composer_trace = {
                **composer_trace,
                "llm_composer_skipped_reason": hop_block,
            }
        else:
            composer_use_case_id = (
                response_use_case.use_case_id if response_use_case is not None else use_case_id
            )
            enrichment_context = get_runtime_curated_enrichment(composer_use_case_id)
            enrichment_projection = llm_facing_curated_enrichment_projection(enrichment_context)
            if enrichment_projection is None:
                enrichment_projection = get_guidance_only_enrichment_projection(composer_use_case_id)
            routed_payload = state.get("routed") if isinstance(state.get("routed"), dict) else {}
            intent_payload = (
                state.get("intent_classification")
                if isinstance(state.get("intent_classification"), dict)
                else {}
            )
            weak_case = qualifies_for_weak_case_composition(
                answer_contract,
                path_type=path_type,
                intent_family=intent_family or None,
                match_path=_match_path_from_state(state) or _candidate_match_path(state),
                router_confidence=(
                    float(routed_payload["confidence"])
                    if isinstance(routed_payload.get("confidence"), (int, float))
                    else None
                ),
                needs_clarification=bool(intent_payload.get("requires_clarification")),
            )
            soc_snippets = soc_kb_snippets_from_source_evidence(source_evidence)
            skill_sections = skill_sections_from_enrichment(enrichment_projection)
            context_package = None
            if weak_case:
                context_package = build_governed_context_package_for_contract(
                    query=request.message,
                    contract=answer_contract,
                    soc_kb_snippets=soc_snippets,
                    resource_decisions=_resource_decision_labels(state),
                    skill_sections=skill_sections,
                    mcp_tool_hints=mcp_tool_hints_from_registry(
                        mcp_allowed=bool(answer_contract.mcp_allowed),
                    ),
                    routed_skill=_context_selected_skill(state),
                    t2_grounding_block=(
                        guided_grounding_block.to_prompt_block() if guided_grounding_block else None
                    ),
                )
            _composer_timeout = resolve_guided_composer_timeout(budget)
            if _composer_timeout is None:
                # Budget drained between the narration gate and here: keep the complete
                # deterministic envelope rather than start an unbounded narration hop.
                composer_result = GovernedComposerResult(
                    envelope=analyst_response,
                    llm_composer_enabled=True,
                    llm_composer_used=False,
                    llm_guard_status="skipped",
                    llm_fallback_used=True,
                    llm_blocked_reason="insufficient_deadline_reserve",
                )
                composer_trace = {
                    **composer_trace,
                    "llm_composer_skipped_reason": "insufficient_deadline_reserve",
                }
            else:
                _reference_facts_for_compose = _reference_facts_for_card(structured_context)
                _reference_seed = (
                    reference_narration_seed(
                        _reference_facts_for_compose,
                        user_query=request.message,
                    )
                    if _reference_facts_for_compose
                    else None
                )
                _t0 = time.monotonic()
                composer_result = compose_governed_answer(
                    contract=answer_contract,
                    enrichment_projection=enrichment_projection,
                    fallback_envelope=analyst_response,
                    context_package=context_package,
                    path_type=path_type,
                    intent_family=intent_family or None,
                    timeout_seconds=_composer_timeout,
                    user_query=request.message or None,
                    selected_skill=_effective_routing_skill(state),
                    reference_narration_seed=_reference_seed,
                )
                composer_trace = {**composer_trace, **composer_result.trace_payload()}
                if composer_result.llm_composer_used:
                    latency_ms = int((time.monotonic() - _t0) * 1000)
                    budget.record_narration(
                        provider_label=composer_result.llm_provider_label,
                        outcome="completed",
                        latency_ms=latency_ms,
                    )
                    record_synthesis_endpoint(
                        latency_ms,
                        path=SynthesisPath.COMPOSER,
                        outcome=TurnOutcome.COMPLETED,
                        provider_label=composer_result.llm_provider_label,
                    )
                elif composer_result.llm_fallback_used:
                    latency_ms = int((time.monotonic() - _t0) * 1000)
                    blocked = str(composer_result.llm_blocked_reason or "")
                    outcome = (
                        TurnOutcome.TIMEOUT
                        if "timeout" in blocked.lower()
                        else TurnOutcome.FALLBACK
                    )
                    record_synthesis_endpoint(
                        latency_ms,
                        path=SynthesisPath.COMPOSER,
                        outcome=outcome,
                        timeout_applied=outcome is TurnOutcome.TIMEOUT,
                        fallback_used=True,
                        provider_label=composer_result.llm_provider_label,
                    )
            analyst_response = composer_result.envelope
            if composer_result.llm_composer_used and weak_case:
                confidence = composition_confidence(
                    contract=answer_contract,
                    path_type=path_type,
                    match_path=_match_path_from_state(state),
                    soc_kb_snippet_count=len(soc_snippets),
                    skill_section_count=len(skill_sections),
                )
                attach_hil, hil_reason = should_attach_compose_hil(
                    contract=answer_contract,
                    confidence=confidence,
                    resource_decisions=_resource_decision_labels(state),
                    evidence_plan=state.get("evidence_plan")
                    if isinstance(state.get("evidence_plan"), dict)
                    else None,
                )
                composer_trace["composition_confidence"] = confidence
                composer_trace["compose_hil_threshold"] = settings.ai_soc_llm_compose_hil_threshold
                if attach_hil:
                    composer_trace["compose_hil_attached"] = True
                    composer_trace["compose_hil_reason"] = hil_reason
                    answer_contract = answer_contract.model_copy(
                        update={"hil_status": "required", "human_review_required": True},
                    )
                    answer_contract_payload = answer_contract.model_dump()
                    from app.orchestration.human_review import human_review as build_human_review

                    human_review = build_human_review(
                        review_type="analyst_review_required",
                        reason=str(hil_reason),
                        reviewer_role="analyst",
                        allowed_actions=[
                            "review_composed_guidance",
                            "validate_against_local_telemetry",
                        ],
                        safe_message_for_user=(
                            "This composed out-of-catalog guidance requires analyst review "
                            "before any MCP search or enforcement action."
                        ),
                        required=True,
                    )
                    context_sufficiency = {
                        **context_sufficiency,
                        "status": "analyst_review_required",
                        "synthesis_readiness": False,
                    }
                    response_mode = _response_mode(context_sufficiency, human_review, spl_validation)
            if (
                spl_draft_preview
                and isinstance(spl_draft_preview, dict)
                and analyst_response is not None
                and not _is_universal_spl_authoring_review(
                    candidate_spl if isinstance(candidate_spl, dict) else None,
                    spl_validation if isinstance(spl_validation, dict) else None,
                )
            ):
                from app.chat.final_answer_readability import apply_draft_preview_readability

                analyst_response = apply_draft_preview_readability(analyst_response)
        if llm_turn_budget_trace is not None:
            llm_turn_budget_trace = budget.to_trace_dict()
    if path_type == "guided_investigation":
        guided_trace = build_guided_llm_trace(
            path_type=path_type,
            composer_trace=composer_trace,
        )
        llm_used = bool(composer_trace.get("llm_composer_used"))
        composer_trace = {
            **composer_trace,
            **guided_trace.to_dict(),
            "deterministic_guided_fallback": not llm_used,
            "guided_fallback_used": not llm_used,
        }
    elif answer_contract is not None and skip_composer and analyst_response is not None:
        composer_trace = {
            **composer_trace,
            "composer_attempted": False,
            "llm_composer_used": False,
            "llm_guard_status": "skipped",
            "llm_fallback_used": False,
            "llm_blocked_reason": skip_reason or "deterministic_guidance_only",
        }
    elif answer_contract is not None:
        composer_trace["composer_attempted"] = False
        composer_trace["composer_skipped_reason"] = (
            "analyst_response_unavailable"
            if analyst_response is None
            else "composer_not_eligible"
        )
    if _rag_no_match(state.get("soc_kb_retrieval")) and spl_validation is None:
        reference_facts_for_guidance = _reference_facts_for_card(structured_context)
        has_guidance = bool(
            reference_facts_for_guidance
            or (
                answer_contract is not None
                and (
                    answer_contract.analyst_checklist_safe
                    or answer_contract.investigation_steps
                    or answer_contract.limitations
                    or answer_contract.missing_evidence
                )
            )
        )
        from app.chat.rag_answer_surfacing import is_substantive_guidance_message

        if not has_guidance and not is_substantive_guidance_message(message):
            analyst_response = None
    if settings.ai_soc_t2_rag_surfacing_enabled:
        from app.chat.rag_answer_surfacing import apply_rag_answer_surfacing

        message, answer_contract, analyst_response, human_review = apply_rag_answer_surfacing(
            message=message,
            answer_contract=answer_contract,
            analyst_response=analyst_response,
            source_evidence=source_evidence,
            evidence_plan=state.get("evidence_plan") if isinstance(state.get("evidence_plan"), dict) else None,
            context_sufficiency=context_sufficiency if isinstance(context_sufficiency, dict) else None,
            user_query=request.message,
            human_review=human_review if isinstance(human_review, dict) else None,
            selected_skill=_effective_routing_skill(state),
        )
        if answer_contract is not None:
            answer_contract_payload = answer_contract.model_dump()
    if settings.ai_soc_t2_answer_surfacing_enabled:
        from app.chat.t2_answer_surfacing import apply_t2_answer_surfacing

        message, answer_contract, analyst_response = apply_t2_answer_surfacing(
            message=message,
            answer_contract=answer_contract,
            analyst_response=analyst_response,
            human_review=human_review if isinstance(human_review, dict) else None,
            candidate_spl=candidate_spl if isinstance(candidate_spl, dict) else None,
            spl_draft_preview=spl_draft_preview if isinstance(spl_draft_preview, dict) else None,
            spl_validation=spl_validation if isinstance(spl_validation, dict) else None,
            user_query=request.message,
            match_path=match_path_for_t2,
            resource_plan=resource_plan_for_shape,
        )
    if settings.ai_soc_t2_answer_surfacing_enabled:
        # WS-7b/7c: enrich a status-only stub with an asset-scoped checklist
        # (named entity) or a T1 objective headline (SPL artifact present). Runs
        # on in-catalogue rows too, so it is not happy-path-bypassed.
        from app.chat.entity_headline_surfacing import apply_entity_and_headline_surfacing

        message, analyst_response = apply_entity_and_headline_surfacing(
            message=message,
            answer_contract=answer_contract,
            analyst_response=analyst_response,
            spl_validation=spl_validation if isinstance(spl_validation, dict) else None,
            candidate_spl=candidate_spl if isinstance(candidate_spl, dict) else None,
            user_query=request.message,
        )
    reference_facts_for_card = _reference_facts_for_card(structured_context)
    if reference_facts_for_card:
        reference_summary = _reference_lookup_summary(
            reference_facts_for_card,
            user_query=request.message,
            source_evidence=source_evidence,
        )
        reference_lead = reference_one_sentence_lead(
            reference_facts_for_card,
            user_query=request.message,
        )
        llm_intro = None
        if synthesis_status.provider == "local_model":
            llm_intro = str(analyst_summary_from_lab or "").strip() or None
        elif isinstance(composer_trace, dict) and composer_trace.get("llm_composer_used"):
            llm_intro = (
                str(analyst_response.one_sentence_finding or analyst_response.direct_answer_summary or "").strip()
                or None
            )
        reference_actions = [
            "Use the cited offline reference rows as taxonomy context only.",
            "Do not treat taxonomy relevance as observed activity in local telemetry.",
            "Collect live evidence separately before claiming exploitation, severity, or confirmed technique use.",
        ]
        if analyst_response is None:
            analyst_response = AnalystResponseEnvelope(
                finding_title="Reference taxonomy lookup",
                response_profile="knowledge_recall",
                execution_status=str(execution.get("status") or "skipped"),
            )
        analyst_response = analyst_response.model_copy(
            update={
                "finding_title": "Reference taxonomy lookup",
                "one_sentence_finding": (llm_intro or reference_lead)[:1200],
                "direct_answer_summary": reference_summary[:4000],
                "recommended_actions": list(getattr(analyst_response, "recommended_actions", None) or reference_actions)
                or reference_actions,
                "analyst_checklist": list(getattr(analyst_response, "analyst_checklist", None) or reference_actions)
                or reference_actions,
                "investigation_steps": list(getattr(analyst_response, "investigation_steps", None) or reference_actions)
                or reference_actions,
                "response_profile": "knowledge_recall",
                "reference_facts": reference_facts_for_card[:10],
                "retrieved_playbook": build_reference_source_playbook(
                    reference_facts_for_card[:10],
                    source_evidence=source_evidence,
                ),
            }
        )
        message = merge_reference_message_with_llm_intro(
            reference_summary,
            llm_intro=llm_intro,
        )
    analyst_response = _collapse_card_summary_when_sections_own_details(
        analyst_response, path_type=path_type
    )
    analyst_response = _strip_priority_prefixes_when_severity_unassigned(analyst_response)
    message = _collapse_top_level_message_when_card_owns_sections(message, analyst_response)
    final_answer_validation = None
    guided_without_control_plane = (
        isinstance(state.get("planning_decision"), dict)
        and state["planning_decision"].get("path_type") == "guided_investigation"
    )
    utility_without_control_plane = _is_universal_spl_authoring_review(
        candidate_spl if isinstance(candidate_spl, dict) else None,
        spl_validation if isinstance(spl_validation, dict) else None,
    )
    if True or guided_without_control_plane or utility_without_control_plane:
        validation = validate_final_answer(
            analyst_response=analyst_response,
            answer_contract=answer_contract_payload,
            evidence_plan=state.get("evidence_plan"),
            mitre_decision=mitre_decision,
            human_review=human_review if isinstance(human_review, dict) else None,
            planning_decision=state.get("planning_decision"),
            routing_provenance=(state.get("routed") or {}).get("routing_provenance")
            if isinstance(state.get("routed"), dict)
            else None,
            visible_message=message,
        )
        final_answer_validation = validation.model_dump()
        if validation.guard_status == "blocked":
            # Fail closed: the answer contradicts the contract/deciders. Withhold
            # the rejected card server-side (do not rely on the client to hide it)
            # and route to analyst review rather than silently repairing the
            # upstream defect.
            analyst_response = None
            mitre_mappings = []
            human_review = {
                **(human_review or {}),
                "required": True,
                "safe_message_for_user": validation.blocked_reason
                or "Final-answer validation requires analyst review.",
            }
            context_sufficiency = {
                **context_sufficiency,
                "status": "analyst_review_required",
                "synthesis_readiness": False,
            }
            response_mode = _response_mode(context_sufficiency, human_review, spl_validation)

    execution_authorized = bool(
        isinstance(execution, dict)
        and str(execution.get("status") or "").lower()
        in {"executed", "executed_mock_evidence", "executed_live_evidence", "success"}
    )
    _intent_for_hil = intent_classification if isinstance(intent_classification, dict) else {}
    effective_hil_required = resolve_effective_hil_required(
        evidence_plan=state.get("evidence_plan") if isinstance(state.get("evidence_plan"), dict) else None,
        answer_contract=answer_contract,
        human_review=human_review if isinstance(human_review, dict) else None,
        execution=execution if isinstance(execution, dict) else None,
        live_data_request=_live_data_request_from_state(state),
        execution_authorized=execution_authorized,
        intent_requires_hil=bool(_intent_for_hil.get("requires_hil")),
    )
    if isinstance(state.get("planning_decision"), dict):
        state = {
            **state,
            "planning_decision": {
                **state["planning_decision"],
                "hil_required": effective_hil_required,
                "effective_hil_required": effective_hil_required,
            },
        }
    if governance_trace is not None:
        if isinstance(governance_trace, dict):
            governance_trace = {**governance_trace, "effective_hil_required": effective_hil_required}
        else:
            governance_trace = governance_trace.model_copy(
                update={"effective_hil_required": effective_hil_required}
            )
    if isinstance(human_review, dict):
        human_review = {**human_review, "effective_hil_required": effective_hil_required}

    # P1 steps 4–5: deterministic skill-contribution contract + investigation floor.
    # Records what the selected skill contributed to the finalized card (sections,
    # evidence keys, provenance, skip reason, survival) and guarantees an
    # investigation skill never returns a silent empty card.
    from app.chat.skill_contribution import (
        apply_evidence_summary_floor,
        apply_investigation_floor,
        apply_out_of_catalog_guidance_floor,
        build_skill_contribution,
        derive_boundary_class,
    )

    _routing_provenance = (
        (state.get("routed") or {}).get("routing_provenance")
        if isinstance(state.get("routed"), dict)
        else None
    )
    skill_contribution = build_skill_contribution(
        selected_skill=_effective_routing_skill(state),
        envelope=analyst_response,
        routing_provenance=_routing_provenance if isinstance(_routing_provenance, dict) else None,
        source_evidence=source_evidence,
        human_review=human_review if isinstance(human_review, dict) else None,
        boundary_class=derive_boundary_class(request.message),
    )
    analyst_response = apply_out_of_catalog_guidance_floor(
        envelope=analyst_response,
        contribution=skill_contribution,
        message=message,
        match_path=match_path_for_t2,
    )
    if analyst_response is not None:
        analyst_response = apply_investigation_floor(
            envelope=analyst_response, contribution=skill_contribution
        )
        # Item 5.5: scoped to out-of-registry/near-105 paths ONLY — the same
        # _TRIGGER_MATCH_PATHS-style set item 3.4 uses for the identical reason.
        # This plan is about out-of-catalogue answer quality; an unscoped floor
        # added a new "evidence_summary" section to in-catalogue (105/50) answer
        # contracts and broke the frozen contract-guard baseline (item 0.3) —
        # discovered via the full-suite run, fixed by scoping rather than
        # touching the baseline.
        if match_path_for_t2 in {"out_of_registry", "near_105_question"}:
            analyst_response = apply_evidence_summary_floor(
                envelope=analyst_response,
                contribution=skill_contribution,
                grounding_block=state.get("grounding_block")
                if isinstance(state.get("grounding_block"), dict)
                else None,
                requires_clarification=bool(
                    isinstance(intent_classification, dict)
                    and intent_classification.get("requires_clarification")
                ),
            )
    skill_contribution_record: dict[str, Any] = skill_contribution.to_dict()

    # WS0 T0.4 + SPL handoff: resolve final ResourcePlan step statuses and
    # planning-vs-final drift before control-plane trace assembly so trace and
    # response payloads agree on evidence_plan and run_contract.
    state = annotate_step_statuses({**state, "mitre_decision": mitre_decision})
    _handoff_candidate = state.get("candidate_spl") if isinstance(state.get("candidate_spl"), dict) else None
    _handoff_final_proj = (
        _handoff_candidate.get("slot_constraint_projection")
        if isinstance(_handoff_candidate, dict)
        else None
    )
    _handoff_evidence_plan = (
        state.get("evidence_plan") if isinstance(state.get("evidence_plan"), dict) else None
    )
    if isinstance(_handoff_final_proj, dict) and isinstance(_handoff_evidence_plan, dict):
        state = {
            **state,
            "evidence_plan": merge_evidence_plan_spl_drift(_handoff_evidence_plan, _handoff_final_proj),
        }
    _handoff_gate_state = {
        **state,
        "human_review": human_review,
        "source_evidence": source_evidence,
        "answer_contract": answer_contract_payload,
    }
    final_evidence_gate = build_final_evidence_gate(_handoff_gate_state, route=route)
    gate_payload = final_evidence_gate.to_dict()
    structured_context["final_evidence_gate"] = gate_payload
    run_contract = build_run_contract(_handoff_gate_state, route=route, gate=final_evidence_gate)
    state = {
        **state,
        "run_contract": enrich_run_contract_payload(run_contract.model_dump_canonical(), _handoff_gate_state),
        "final_evidence_gate": gate_payload,
    }
    if governance_trace is not None:
        final_hil = run_contract.effective_hil_required
        if isinstance(governance_trace, dict):
            governance_trace = {**governance_trace, "effective_hil_required": final_hil}
        else:
            governance_trace = governance_trace.model_copy(
                update={"effective_hil_required": final_hil}
            )

    visibility: dict[str, Any] = {}
    control_plane_trace = None
    if True:
        use_case_id_for_visibility = (
            response_use_case.use_case_id if response_use_case is not None else use_case_id
        )
        visibility = build_pipeline_visibility(
            state=state,
            selected_use_case_id=use_case_id_for_visibility,
            mitre_decision=mitre_decision,
            spl_validation=spl_validation if isinstance(spl_validation, dict) else None,
            candidate_spl=candidate_spl if isinstance(candidate_spl, dict) else None,
            execution=execution if isinstance(execution, dict) else None,
            human_review=human_review if isinstance(human_review, dict) else None,
            answer_guard=answer_guard.model_dump(),
            final_answer_validation=final_answer_validation,
            answer_contract=answer_contract_payload,
            severity_decision=severity_decision,
            session_context_resolution=session_resolution if isinstance(session_resolution, SessionContextResolution) else None,
        )
        state = {
            **state,
            **project_chat_pipeline_state_v2(
                state,
                visibility=visibility,
                final_answer_validation=final_answer_validation,
                execution=execution if isinstance(execution, dict) else None,
                human_review=human_review if isinstance(human_review, dict) else None,
                use_case_id=use_case_id_for_visibility,
            ),
        }
    if True or guided_without_control_plane or utility_without_control_plane:
        trace_state = {
            **state,
            "mitre_decision": mitre_decision,
            "mitre_branch_result": mitre_branch_payload,
            "answer_contract": answer_contract_payload,
            "final_answer_validation": final_answer_validation,
        }
        control_plane_trace = build_control_plane_trace(
            trace_state,
            source_evidence=source_evidence,
            context_sufficiency=context_sufficiency,
            synthesis_mode=synthesis_mode,
            answer_guard=answer_guard.model_dump(),
            node_trace=visibility.get("node_trace"),
        )
        control_plane_trace["llm_calls"] = visibility.get("llm_calls")
        control_plane_trace["llm_composer"] = composer_trace
        if missing_evidence_reasoning_trace is not None:
            control_plane_trace["missing_evidence_reasoning"] = missing_evidence_reasoning_trace
        if mitre_risk_rationale_trace is not None:
            control_plane_trace["mitre_risk_rationale"] = mitre_risk_rationale_trace
        plan_dispatch_trace = state.get("plan_dispatch_trace")
        if not isinstance(plan_dispatch_trace, dict) or not plan_dispatch_trace:
            plan_dispatch_trace = build_plan_dispatch_trace_from_pipeline_dispatch(state)
        if isinstance(plan_dispatch_trace, dict) and plan_dispatch_trace:
            control_plane_trace["plan_dispatch"] = plan_dispatch_trace
        guided_handoff_trace = state.get("guided_handoff_trace")
        if isinstance(guided_handoff_trace, dict) and guided_handoff_trace:
            control_plane_trace["guided_handoff"] = guided_handoff_trace
        if resource_plan_shadow_trace is not None:
            control_plane_trace["resource_plan_shadow"] = resource_plan_shadow_trace
        budget = state.get("llm_turn_budget") or TurnLlmBudget()
        tool_plan_reserve = max(1.0, float(settings.ai_soc_llm_timeout_seconds))
        allow_tool_plan_llm = (
            hybrid_role_plan is not None
            and hybrid_role_plan.role_enabled("mcp_tool_plan_shadow")
            and not draft_preview_active
            and budget.sidecar_hop_blocked(role="mcp_tool_plan_shadow") is None
            and budget.can_start_call(reserve_seconds=tool_plan_reserve)
        )
        mcp_tool_plan_shadow_trace = run_mcp_tool_plan_shadow(
            query=request.message,
            target_index=_target_index_from_validation(spl_validation),
            spl_approved=bool(isinstance(spl_validation, dict) and spl_validation.get("approved")),
            session_role=state.get("session_role"),
            needs_mcp=_mcp_tool_plan_needs_mcp(state, spl_validation),
            needs_spl=spl_validation is not None,
            allow_llm_advisory=allow_tool_plan_llm,
            llm_advisory_skip_reason=(
                "turn_budget_exhausted"
                if not draft_preview_active and not allow_tool_plan_llm
                else None
            ),
        )
        if mcp_tool_plan_shadow_trace is not None:
            control_plane_trace["mcp_tool_plan_shadow"] = mcp_tool_plan_shadow_trace
            planner_meta = mcp_tool_plan_shadow_trace.get("planner") or {}
            if planner_meta.get("llm_called"):
                budget.record_sidecar(
                    role="mcp_tool_plan_shadow",
                    provider_label=planner_meta.get("llm_label"),
                    outcome="completed" if not planner_meta.get("llm_error") else "dropped",
                )
        if llm_turn_budget_trace is not None:
            control_plane_trace["llm_turn_budget"] = budget.to_trace_dict()
        if hybrid_role_plan is not None:
            control_plane_trace["hybrid_role_graph"] = hybrid_role_plan.to_trace_dict()
        # Stage 4B: surface the governed evidence-loop so it is debuggable in
        # prod traces (chronology, bounded hop count, accumulated hops, verdict).
        if state.get("mcp_chronology") is not None:
            control_plane_trace["evidence_loop"] = {
                "chronology": list(state.get("mcp_chronology") or []),
                "hops_done": int(state.get("mcp_hops_done", 0)),
                "decision": state.get("mcp_loop"),
                "hops": state.get("mcp_evidence") or [],
                "planner": state.get("mcp_loop_planner"),
            }
        observer_trace = state.get("evidence_observer_trace")
        if isinstance(observer_trace, dict) and observer_trace:
            control_plane_trace["evidence_observer"] = observer_trace
        # Plan §3 A4: attach CVE snapshot provenance when the plan needs vulnerability context.
        vuln_source = _resolve_vulnerability_source_status(state)
        if vuln_source is not None:
            if isinstance(control_plane_trace.get("evidence_loop"), dict):
                control_plane_trace["evidence_loop"]["vulnerability_source"] = vuln_source
            else:
                control_plane_trace["vulnerability_source"] = vuln_source
        if path_type == "guided_investigation" and guided_grounding_block is not None:
            control_plane_trace["guided_hunt_grounding"] = guided_hunt_grounding_trace(
                guided_grounding_block
            )
        try:
            turn_timing = finalize_turn_timing()
            if turn_timing is not None:
                control_plane_trace["turn_timing"] = turn_timing
        except Exception:  # noqa: BLE001 — timing is best-effort only
            logger.warning("turn_timing_finalize_failed", exc_info=True)

    session_context_status = None
    if settings.ai_soc_session_context_enabled and isinstance(session_resolution, SessionContextResolution):
        session_context_status = SessionContextStatusEnvelope(**session_resolution.status.model_dump())

    partial_fallback = synthesis_status.status == "partial_timeout"
    answer_mode = (
        state.get("evidence_plan", {}).get("answer_mode")
        if isinstance(state.get("evidence_plan"), dict)
        else None
    )
    if not answer_mode and _is_universal_spl_authoring_review(
        candidate_spl if isinstance(candidate_spl, dict) else None,
        spl_validation if isinstance(spl_validation, dict) else None,
    ):
        answer_mode = "spl_utility_authoring"
    response_packaging_status = _response_packaging_status(
        synthesis_status=synthesis_status,
        composer_trace=composer_trace,
        human_review=human_review if isinstance(human_review, dict) else None,
        final_answer_validation=final_answer_validation,
        analyst_response=analyst_response,
    )
    # Review-only SPL drafts: one dedicated renderer owns the visible answer (fixed
    # section order + labels) and suppresses the generic title/review-type/investigation
    # producers. Presentation only — RunContract/HIL/MCP/source-evidence are unchanged.
    _spl_handoff = build_spl_artifact_handoff_summary(
        candidate_spl=candidate_spl if isinstance(candidate_spl, dict) else None,
        spl_validation=spl_validation if isinstance(spl_validation, dict) else None,
        spl_draft_preview=spl_draft_preview if isinstance(spl_draft_preview, dict) else None,
    )
    analyst_response, message = apply_review_only_spl_render(
        run_contract=run_contract,
        analyst_response=analyst_response,
        message=message,
        draft_preview=spl_draft_preview if isinstance(spl_draft_preview, dict) else None,
        candidate_spl=candidate_spl if isinstance(candidate_spl, dict) else None,
        spl_artifact_handoff=_spl_handoff,
        user_query=request.message,
        match_path=(
            (state.get("query_to_intent") or {}).get("candidate_mappings") or {}
        ).get("match_path")
        if isinstance(state.get("query_to_intent"), dict)
        else None,
    )
    from app.chat.answer_quality_enrichment import apply_answer_quality_enrichment

    from app.chat.guidance_summary_renderer import apply_guidance_summary_render

    message, analyst_response = apply_answer_quality_enrichment(
        message,
        analyst_response,
        user_query=request.message,
        evidence_plan=state.get("evidence_plan") if isinstance(state.get("evidence_plan"), dict) else None,
        path_type=path_type,
        answer_contract=answer_contract,
    )
    analyst_response, message = apply_guidance_summary_render(
        analyst_response,
        message,
        path_type=path_type,
        evidence_plan=state.get("evidence_plan") if isinstance(state.get("evidence_plan"), dict) else None,
        answer_contract=answer_contract,
        user_query=request.message,
        llm_composer_used=bool(composer_trace.get("llm_composer_used")),
    )
    if analyst_response is not None and path_type == "guided_investigation":
        filtered_steps = filter_analyst_facing_steps(list(analyst_response.investigation_steps or []))
        filtered_actions = filter_analyst_facing_steps(list(analyst_response.recommended_actions or []))
        filtered_checklist = filter_analyst_facing_steps(list(analyst_response.analyst_checklist or []))
        if (
            filtered_steps != list(analyst_response.investigation_steps or [])
            or filtered_actions != list(analyst_response.recommended_actions or [])
            or filtered_checklist != list(analyst_response.analyst_checklist or [])
        ):
            analyst_response = analyst_response.model_copy(
                update={
                    "investigation_steps": filtered_steps,
                    "recommended_actions": filtered_actions,
                    "analyst_checklist": filtered_checklist,
                }
            )
    if path_type == "guided_investigation" and composer_trace.get("guided_llm_degraded_fallback"):
        evidence_plan_payload = (
            state.get("evidence_plan") if isinstance(state.get("evidence_plan"), dict) else {}
        )
        checklist = list(evidence_plan_payload.get("checklist") or [])
        degraded_message = build_guided_llm_degraded_message(
            checklist=checklist,
            failure_reason=composer_trace.get("guided_llm_failure_reason"),
        )
        message = degraded_message
        if analyst_response is not None:
            filtered_steps = filter_analyst_facing_steps(
                list(analyst_response.investigation_steps or checklist)
            )
            analyst_response = analyst_response.model_copy(
                update={
                    "direct_answer_summary": degraded_message[:2000],
                    "one_sentence_finding": degraded_message[:500],
                    "investigation_steps": filtered_steps,
                    "recommended_actions": filtered_steps[:8],
                    "analyst_checklist": filtered_steps[:8],
                    "severity_label": None,
                    "review_notice": (
                        "Guided LLM planner unavailable — deterministic checklist only; "
                        "no live telemetry was queried."
                    ),
                }
            )
    from app.chat.coe_checklist_repair import repair_duplicate_soc_review_checklist

    analyst_response, message = repair_duplicate_soc_review_checklist(
        analyst_response, message, path_type=path_type
    )
    analyst_response = _collapse_card_summary_when_sections_own_details(
        analyst_response, path_type=path_type
    )
    analyst_response = _strip_priority_prefixes_when_severity_unassigned(analyst_response)
    message = _collapse_top_level_message_when_card_owns_sections(message, analyst_response)
    visible_spl_draft_preview = (
        None
        if _is_universal_spl_authoring_review(candidate_spl, spl_validation)
        else spl_draft_preview
    )
    action_capability = action_capability_for(
        response_use_case.use_case_id if response_use_case else None,
        severity_decision.severity_label,
        hil_required=run_contract.effective_hil_required,
    )
    proposed_actions: list[dict[str, Any]] | None = None
    try:
        from app.actions.live_action_proposals import attach_live_action_proposals

        gate_state_for_actions = {
            **state,
            "analyst_response": analyst_response.model_dump() if analyst_response is not None else None,
            "severity_decision": (
                severity_decision.model_dump()
                if hasattr(severity_decision, "model_dump")
                else severity_decision
            ),
            "message": message,
        }
        proposals = attach_live_action_proposals(gate_state_for_actions, trace_id=trace_id)
        proposed_actions = proposals or None
    except Exception:  # noqa: BLE001 - proposals are advisory, never break chat
        logger.warning("live_action_proposal_attach_failed", exc_info=True)
    response = PlaceholderResponse(
        trace_id=trace_id,
        user_query=request.message,
        fallback_active=True if partial_fallback else None,
        response_packaging_status=response_packaging_status,
        selected_skill=run_contract.routing.canonical_skill,
        primary_operation=primary_operation,
        coverage_id=coverage_id,
        route_authority=_route_authority_payload(route_plan_shadow),
        legacy_intent_authority=bool(
            (routing_skill_resolution or {}).get("legacy_intent_authority", True)
        ),
        routing_skill_resolution=routing_skill_resolution,
        evidence_origin=evidence_origin,
        answer_readiness=answer_readiness,
        semantic_intent=semantic_intent,
        operation_audit=operation_audit,
        tool_plan=list(routed["tool_plan"]),
        confidence=float(routed["confidence"]),
        routing_mode=settings.routing_mode,
        disagreement=bool(state.get("disagreement")),
        disagreement_reason=_disagreement_reason(comparison) if state.get("disagreement") else None,
        query_understanding=state.get("query_understanding"),
        selected_use_case=response_use_case,
        selected_skill_chain=state.get("selected_skill_chain"),
        skill_selection=state.get("skill_selection"),
        skill_contribution=skill_contribution_record,
        message=message,
        note=note,
        analyst_summary=(
            None
            if visible_spl_draft_preview and isinstance(visible_spl_draft_preview, dict)
            else analyst_summary_from_lab
        ),
        answer_mode=answer_mode,
        response_mode=response_mode,
        synthesis_mode=synthesis_mode,
        workflow_plan=(
            _strip_rag_from_workflow_plan(state["workflow_plan"])
            if answer_mode == "spl_utility_authoring" and isinstance(state.get("workflow_plan"), dict)
            else state["workflow_plan"]
        ),
        candidate_spl=candidate_spl,
        spl_validation=spl_validation,
        spl_draft_preview=visible_spl_draft_preview if isinstance(visible_spl_draft_preview, dict) else None,
        llm_spl_candidate=llm_spl_candidate if isinstance(llm_spl_candidate, dict) else None,
        execution=execution,
        human_review=human_review,
        source_evidence=source_evidence,
        structured_context=structured_context,
        context_sufficiency=context_sufficiency,
        route_plan_shadow=route_plan_shadow,
        spl_template=spl_template,
        mitre_mappings=mitre_mappings,
        severity_decision=severity_decision,
        investigation_lineage=investigation_lineage,
        synthesis_status=synthesis_status,
        answer_guard=answer_guard,
        action_capability=action_capability,
        proposed_actions=proposed_actions,
        governance_trace=governance_trace,
        query_to_intent=state.get("query_to_intent"),
        planning_decision=state.get("planning_decision"),
        llm_intent_advisory=(
            state["llm_intent_advisory"].model_dump()
            if isinstance(state.get("llm_intent_advisory"), LLMIntentAdvisory)
            else state.get("llm_intent_advisory")
        ),
        evidence_plan=state.get("evidence_plan"),
        route_adjudication=state.get("route_adjudication"),
        control_plane_trace=control_plane_trace,
        answer_contract=answer_contract_payload,
        final_answer_validation=final_answer_validation,
        mitre_decision=mitre_decision,
        analyst_response=analyst_response,
        environment_hygiene=environment_hygiene,
        mitre_evidence_status=visibility.get("mitre_evidence_status"),
        spl_template_status=visibility.get("spl_template_status"),
        node_trace=visibility.get("node_trace"),
        answer_guard_status=visibility.get("answer_guard_status"),
        final_answer_safety_status=visibility.get("final_answer_safety_status"),
        session_context_status=session_context_status,
        run_contract=state.get("run_contract"),
        canonical_facts=state.get("canonical_facts"),
        routing_contract=state.get("route_contract"),
    )
    response = _apply_coe_stop_condition_gate(response, query=request.message)
    if settings.ai_soc_session_context_enabled and state.get("session_id"):
        persist_session_pins(
            pins_from_pipeline_state(
                session_id=str(state["session_id"]),
                trace_id=trace_id,
                response=response,
                state=state,
            )
        )
    try:
        from app.quality.answer_scorecard import build_answer_scorecard
        from app.synthesis.narration_visibility import build_narration_visibility

        payload_view = response.model_dump()
        visibility = build_narration_visibility(payload_view)
        payload_view["narration_visibility"] = visibility
        response = response.model_copy(
            update={
                "narration_visibility": visibility,
                "answer_scorecard": build_answer_scorecard(payload_view),
            }
        )
    except Exception:
        # Scorecard is reporting only; it must never break an answer.
        pass
    assembly_outcome, assembly_reasons = validate_assembled_response(
        state,
        analyst_response=analyst_response,
        answer_contract=answer_contract_payload,
    )
    if assembly_outcome != "ok":
        state = emit_request_failed(state, reason="response_assembly_failed")
    else:
        state = emit_response_generated({**state, "response": response})
        state = emit_request_completed(state)
    return {
        **state,
        "context_sufficiency": response.context_sufficiency,
        "response": response,
        "mitre_decision": mitre_decision,
        "answer_contract": answer_contract_payload,
    }


_COE_STOP_CONDITION_IDS = frozenset(
    {
        "run_contract_missing",
        "live_backed_without_execution",
        "results_table_not_allowed",
        "priority_prefix_without_severity",
        "route_authority_holder_contradiction",
        "duplicate_spl_warning",
        "duplicate_soc_review_checklist",
    }
)


def _collapse_top_level_message_when_card_owns_sections(
    message: str,
    analyst_response: Any | None,
) -> str:
    if analyst_response is None:
        return message
    lowered = str(message or "").lower()
    if not (
        "lab-only draft spl preview" in lowered
        or "soc review checklist" in lowered
        or "draft spl (review-only" in lowered
    ):
        return message
    summary = str(getattr(analyst_response, "direct_answer_summary", "") or "").strip()
    if summary:
        return summary
    return "Review-only answer prepared; no live query was executed."


_PRIORITY_ACTION_PREFIX = re.compile(r"^P[1-4]\s*[—\-–:]\s*", re.IGNORECASE)


def _strip_priority_prefixes_when_severity_unassigned(analyst_response: Any | None) -> Any | None:
    """Drop P1/P2/P3/P4 action prefixes when incident severity is not assigned.

    COE stop condition: priority prefixes must not appear unless severity is actually
    assigned. Some answer paths emit P-prefixed actions without an assigned severity;
    normalize them here so the final answer is self-consistent rather than nulled.
    """
    if analyst_response is None:
        return None
    label = str(getattr(analyst_response, "severity_label", "") or "")
    severity_assigned = bool(label) and "not assigned" not in label.lower()
    if severity_assigned:
        return analyst_response
    updates: dict[str, Any] = {}
    for field in ("recommended_actions", "analyst_checklist", "investigation_steps"):
        items = getattr(analyst_response, field, None)
        if not isinstance(items, list) or not items:
            continue
        stripped = [
            _PRIORITY_ACTION_PREFIX.sub("", str(item)).strip() if isinstance(item, str) else item
            for item in items
        ]
        if stripped != list(items):
            updates[field] = stripped
    if not updates:
        return analyst_response
    return analyst_response.model_copy(update=updates)


def _collapse_card_summary_when_sections_own_details(
    analyst_response: Any | None,
    *,
    path_type: str | None = None,
) -> Any | None:
    if analyst_response is None:
        return None
    if is_guidance_summary_path(path_type):
        return analyst_response
    if str(getattr(analyst_response, "response_profile", "") or "") == "spl_only":
        return analyst_response
    summary = str(getattr(analyst_response, "direct_answer_summary", "") or "").strip()
    if not summary:
        return analyst_response
    if getattr(analyst_response, "reference_facts", None):
        return analyst_response
    lowered = summary.lower()
    owns_detail_sections = any(
        getattr(analyst_response, field, None)
        for field in (
            "recommended_actions",
            "analyst_checklist",
            "investigation_steps",
            "triage_checklist",
            "evidence_checklist",
            "spl_draft_preview",
            "draft_spl_code",
            "spl_code",
        )
    )
    if not owns_detail_sections:
        return analyst_response
    if not (
        "review steps:" in lowered
        or "soc review checklist" in lowered
        or "draft spl" in lowered
        or "\n-" in summary
    ):
        return analyst_response
    first_line = next((line.strip() for line in summary.splitlines() if line.strip()), "")
    if not first_line:
        first_line = "Review-only answer prepared; no live query was executed."
    return analyst_response.model_copy(update={"direct_answer_summary": first_line[:500]})


def _is_coe_stop_condition_violation(violation: str) -> bool:
    return violation in _COE_STOP_CONDITION_IDS or violation.startswith("run_contract_field_missing:")


def _apply_coe_stop_condition_gate(response: PlaceholderResponse, *, query: str) -> PlaceholderResponse:
    """Fail closed on COE stop-condition violations after RunContract packaging."""
    from app.chat.coe_checklist_repair import repair_duplicate_soc_review_checklist
    from app.evals.answer_efficacy_checks import evaluate_universal_efficacy

    repaired_response = response
    if response.analyst_response is not None or str(response.message or "").strip():
        analyst_response, message = repair_duplicate_soc_review_checklist(
            response.analyst_response,
            str(response.message or ""),
            path_type=(
                response.planning_decision.get("path_type")
                if isinstance(response.planning_decision, dict)
                else None
            ),
        )
        if analyst_response is not response.analyst_response or message != str(response.message or ""):
            repaired_response = response.model_copy(
                update={"analyst_response": analyst_response, "message": message}
            )

    payload = repaired_response.model_dump(mode="json")
    violations = [
        violation
        for violation in evaluate_universal_efficacy(query=query, payload=payload)
        if _is_coe_stop_condition_violation(violation)
    ]
    if not violations:
        return repaired_response

    first = violations[0]
    blocked_reason = f"COE stop-condition validation failed: {first}."
    final_validation = payload.get("final_answer_validation") if isinstance(payload.get("final_answer_validation"), dict) else {}
    prior_failed = final_validation.get("failed_checks") if isinstance(final_validation.get("failed_checks"), list) else []
    payload["final_answer_validation"] = {
        **final_validation,
        "enabled": True,
        "guard_status": "blocked",
        "failed_checks": sorted({str(item) for item in prior_failed + violations}),
        "blocked_reason": blocked_reason,
        "analyst_review_required": True,
        "reason": "COE stop-condition validation failed; routing to analyst review (fail closed).",
    }

    existing_review = payload.get("human_review") if isinstance(payload.get("human_review"), dict) else {}
    payload["human_review"] = {
        **existing_review,
        "required": True,
        "review_type": existing_review.get("review_type") or "answer_guard_blocked",
        "reason": existing_review.get("reason") or "coe_stop_condition_violation",
        "reviewer_role": existing_review.get("reviewer_role") or "soc_analyst",
        "allowed_actions": existing_review.get("allowed_actions") or ["review_renderer_output", "cancel"],
        "safe_message_for_user": blocked_reason,
    }
    context = payload.get("context_sufficiency") if isinstance(payload.get("context_sufficiency"), dict) else None
    if context is not None:
        payload["context_sufficiency"] = {
            **context,
            "status": "analyst_review_required",
            "synthesis_readiness": False,
        }
    payload["message"] = blocked_reason
    payload["note"] = "COE stop-condition validation failed; visible answer withheld for analyst review."
    payload["response_mode"] = "human_review"
    payload["analyst_response"] = None
    payload["mitre_mappings"] = []
    return PlaceholderResponse.model_validate(payload)


def _route_authority_payload(route_plan_shadow: dict[str, Any] | None) -> dict[str, object] | None:
    if not isinstance(route_plan_shadow, dict):
        return None
    compare = route_plan_shadow.get("route_authority_compare")
    if isinstance(compare, dict):
        return dict(compare)
    return None


def _primary_operation_from_authority(
    route_plan_shadow: dict[str, Any] | None,
    route_authority: dict[str, object] | None,
) -> str | None:
    if route_authority:
        for key in ("planning_primary_skill", "candidate_primary_skill", "route_plan_primary_skill_observed"):
            value = route_authority.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    if isinstance(route_plan_shadow, dict):
        value = route_plan_shadow.get("primary_skill")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _coverage_id_from_authority(route_authority: dict[str, object] | None) -> str | None:
    if not route_authority:
        return None
    value = route_authority.get("coverage_id_resolved") or route_authority.get("coverage_id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _evidence_plan(state: ChatPipelineState) -> dict[str, Any]:
    plan = state.get("evidence_plan")
    return plan if isinstance(plan, dict) else {}




def _composed_plan_missing_reason(state: ChatPipelineState) -> str:
    evidence_plan = state.get("evidence_plan")
    if not isinstance(evidence_plan, dict):
        return "evidence_plan_missing"
    resource_plan = evidence_plan.get("resource_plan")
    if not isinstance(resource_plan, dict):
        return "resource_plan_not_attached"
    if not resource_plan.get("steps"):
        return "resource_plan_empty"
    return "resource_plan_composition_failed"


_RUNTIME_PROFILE_CATALOGUE_TEMPLATES: dict[str, str] = {
    "scada_perf": "scada_perf_threshold_anomaly",
    "cisco_asa": "cisco_asa_ioc_lookup",
}


def _catalogue_template_dependencies_met(template_id: str) -> bool:
    """Live Splunk alignment for a catalogue template before execution.

    Verifies the template's index + referenced lookup CSVs exist on the search
    head via read-only MCP discovery. Returns False (degrade to token-SPL/HIL)
    when anything is missing or discovery is unavailable. Best-effort.
    """
    template = get_spl_template(template_id)
    if template is None:
        return False
    try:
        from app.spl.template_dependency_verifier import (
            required_lookups_for_template,
            verify_template_dependencies,
        )

        rules = getattr(template, "validation_rules", None) or {}
        required_indexes = [str(i) for i in (rules.get("allowed_indexes") or [])]
        required_lookups = required_lookups_for_template(getattr(template, "spl_text", "") or "")
        verification = verify_template_dependencies(
            required_indexes=required_indexes,
            required_lookups=required_lookups,
        )
        return bool(verification.verified)
    except Exception:  # noqa: BLE001 - alignment check must never break the SPL path
        logger.warning("catalogue_template_dependency_check_failed", exc_info=True)
        return False


def _run_legacy_dispatch_fallback(
    state: ChatPipelineState,
    *,
    dispatch_source: str,
    composed_plan_missing_reason: str | None = None,
) -> ChatPipelineState:
    """Dispatch stages when composed plan is absent; traced, never silent.

    When dispatch v2 is on and ``pipeline_dispatch`` is present, ``stage_schedule``
    is the sole routing authority (REV5-A). Otherwise legacy evidence_plan booleans.
    """
    trace: dict[str, Any] = {
        "dispatch_source": dispatch_source,
        "dispatch_schedule": [],
    }
    if composed_plan_missing_reason:
        trace["composed_plan_missing_reason"] = composed_plan_missing_reason
    projected = projected_flags_from_state(state)
    if projected is not None:
        trace["dispatch_authority"] = "pipeline_dispatch_v2"
        trace["projected_flags"] = projected
    state = {**state, "plan_dispatch_trace": trace}

    v2_hooks = imperative_hook_schedule_from_state(state)
    # An EMPTY hook list (e.g. mitre_finalize / cve_adapter-only schedules that map
    # to no imperative SPL/RAG hook) must fall through to the legacy branch, which
    # runs the knowledge/rag-only flow and sets state["execution"] for finalize.
    if v2_hooks:
        hook_nodes = {
            "prepare_rag_only": graph_node_prepare_rag_only,
            "rag_early": graph_node_rag_early,
            "workflow_spl": graph_node_workflow_spl,
            "spl_postprocessor": graph_node_spl_postprocessor,
            "spl_source_resolve": graph_node_spl_source_resolve,
            "reference_finalize": graph_node_reference_finalize,
            "execution": graph_node_execution,
        }
        ran_spl = False
        for hook_name in v2_hooks:
            node = hook_nodes.get(hook_name)
            if node is None:
                continue
            state = node(state)
            trace["dispatch_schedule"].append(hook_name)
            if hook_name == "workflow_spl":
                ran_spl = True
        # SPL/hybrid schedules omit ``mcp_execution`` from stage_schedule but still
        # need the execution gate stub (legacy path always ran execution after SPL).
        # Knowledge/MITRE/CVE schedules have no workflow_spl -> no workflow_plan, so
        # the execution gate (which requires state["workflow_plan"]) must NOT run.
        if ran_spl and "execution" not in state:
            state = graph_node_execution(state)
            trace["dispatch_schedule"].append("execution")
        return {**state, "plan_dispatch_trace": trace}

    if _uses_rag_only_path(state):
        state = graph_node_prepare_rag_only(state)
        trace["dispatch_schedule"].append("prepare_rag_only")
        state = graph_node_rag_early(state)
        trace["dispatch_schedule"].append("rag_early")
        return {**state, "plan_dispatch_trace": trace}
    state = graph_node_workflow_spl(state)
    trace["dispatch_schedule"].append("workflow_spl")
    if _uses_pre_mcp_rag(state):
        state = graph_node_rag_early(state)
        trace["dispatch_schedule"].append("rag_early")
    state = graph_node_spl_source_resolve(state)
    trace["dispatch_schedule"].append("spl_source_resolve")
    state = graph_node_execution(state)
    trace["dispatch_schedule"].append("execution")
    return {**state, "plan_dispatch_trace": trace}


def _dispatch_hooks() -> DispatchHooks:
    return DispatchHooks(
        uses_rag_only_path=_uses_rag_only_path,
        uses_pre_mcp_rag=_uses_pre_mcp_rag,
        prepare_rag_only=graph_node_prepare_rag_only,
        rag_early=graph_node_rag_early,
        spl_source_resolve=graph_node_spl_source_resolve,
        workflow_spl=graph_node_workflow_spl,
        spl_postprocessor=graph_node_spl_postprocessor,
        ensure_workflow_plan=graph_node_ensure_workflow_plan,
        reference_finalize=graph_node_reference_finalize,
        execution=graph_node_execution,
    )


def _session_spl_refine_active(state: ChatPipelineState) -> bool:
    resolution = state.get("session_context_resolution")
    return (
        isinstance(resolution, SessionContextResolution)
        and resolution.spl_refine_from_session
        and resolution.status.staleness == "fresh"
        and resolution.pins is not None
        and bool(resolution.pins.last_candidate_spl)
    )


def _uses_guided_hybrid_dispatch(state: ChatPipelineState) -> bool:
    return uses_guided_hybrid_dispatch_from_state(state)


def _run_guided_hybrid_dispatch(state: ChatPipelineState) -> ChatPipelineState:
    """Guided hybrid rail: execute only steps from the committed ResourcePlan."""
    from app.chat.guided_hybrid_executor import load_committed_guided_resource_plan

    from app.chat.contracts.evidence_plan import EvidencePlan

    request = state["request"]
    trace_id = state["trace_id"]
    query = state.get("effective_query") or request.message
    evidence_payload = dict(_evidence_plan(state))
    evidence = EvidencePlan.model_validate(evidence_payload)
    committed_resource, failure_state = load_committed_guided_resource_plan(state, evidence_payload)
    if failure_state is not None:
        return failure_state
    assert committed_resource is not None

    dispatch_steps = ["committed_resource_plan"]
    refinement_rounds: list[int] = []
    collection_state: ChatPipelineState = dict(state)
    validated_plan: InvestigationPlan | None = None
    pre_plan = None
    validation = None
    validated_resource: ResourcePlan | None = committed_resource
    llm_result = None
    refinement_round = 0

    while True:
        refinement_rounds.append(refinement_round)
        if refinement_round > 0:
            dispatch_steps.append("guided_refinement")

        baseline = build_deterministic_investigation_plan(
            query=query,
            soc_kb_retrieval=state.get("soc_kb_retrieval")
            if isinstance(state.get("soc_kb_retrieval"), dict)
            else None,
        ).model_copy(update={"refinement_round": refinement_round})
        if settings.ai_soc_guided_llm_enabled:
            from app.chat.guided_investigation_plan_llm import InvestigationPlanLlmResult

            llm_result = InvestigationPlanLlmResult(
                raw_llm=None,
                proposal=None,
                attempted=False,
                timed_out=False,
                provider_label=None,
                dropped_reasons=["guided_finalize_composer_reserved"],
            )
        else:
            llm_result = propose_investigation_plan_llm(query=query, baseline=baseline)
        if refinement_round == 0 and llm_result.attempted:
            dispatch_steps.append("guided_investigation_plan_llm")
        validated_plan = validate_investigation_plan(
            baseline,
            llm_result.proposal,
            llm_attempted=llm_result.attempted,
        )
        if refinement_round == 0:
            dispatch_steps.extend(
                [
                    "validator_a",
                    "compose_guided_resource_plan",
                    "validator_b",
                ]
            )
        pre_plan = validated_resource
        validation = validate_guided_resource_plan(evidence, validated_resource)
        validated_resource = validation.validated_resource_plan
        rc = _routes_chat()
        workflow_plan = rc.plan_workflow(
            selected_skill="guided_investigation",
            tool_plan=["retrieve_approved_knowledge", "optional_review_only_spl", "no_mcp"],
            query=request.message,
            trace_id=trace_id,
        )

        def _execute_guided_safe_catalog_spl(
            spl_validation: dict[str, Any],
        ) -> tuple[dict[str, Any], dict[str, Any]]:
            return _execution_stage(
                trace_id=trace_id,
                selected_skill="spl_generation",
                workflow_plan=workflow_plan,
                spl_validation=spl_validation,
                precondition_evaluation=state.get("route_plan_shadow", {}).get("precondition_evaluation"),
                requested_mcp_server=request.requested_mcp_server,
                requested_mcp_tool=request.requested_mcp_tool,
                mcp_allowed=True,
                rbac_role=state.get("session_role"),
            )

        collection_state, _ = collect_guided_hybrid_evidence(
            collection_state,
            validated_resource=validated_resource,
            execute_safe_catalog_spl=_execute_guided_safe_catalog_spl,
        )
        if any(
            step.purpose in {"mcp_discovery", "safe_catalog_query"}
            for step in validated_resource.steps
        ):
            if "guided_hybrid_collection" not in dispatch_steps:
                dispatch_steps.append("guided_hybrid_collection")

        if refinement_cap_reached(
            refinement_round=refinement_round,
            refinement_recommended=validated_plan.refinement_recommended,
        ):
            validated_plan = apply_refinement_cap_warning(validated_plan)
            break
        if not should_run_refinement_pass(
            refinement_round=refinement_round,
            refinement_recommended=validated_plan.refinement_recommended,
        ):
            break
        refinement_round += 1
        if refinement_round >= MAX_GUIDED_INVESTIGATION_ROUNDS:
            break

    dispatch_steps.append("rag_early")
    collected_count = count_collected_guided_hops(
        collection_state.get("mcp_evidence")
        if isinstance(collection_state.get("mcp_evidence"), list)
        else None
    )
    assert validated_plan is not None
    assert pre_plan is not None
    assert validation is not None
    assert validated_resource is not None
    assert llm_result is not None
    handoff_trace = build_guided_handoff_trace(
        investigation_plan_validated=validated_plan,
        resource_plan_pre_validation=pre_plan,
        resource_plan_validated=validated_resource,
        blocked_resources=blocked_resources_wire(validation),
        investigation_plan_raw_llm=llm_result.raw_llm,
        evidence_collected=collected_count,
        refinement_rounds=refinement_rounds,
    )

    if validated_plan.hypotheses:
        evidence_payload["checklist"] = list(validated_plan.hypotheses)
    if validated_plan.evidence_needed:
        evidence_payload["investigation_workflow"] = list(validated_plan.evidence_needed)
    spl_draft_preview = build_guided_spl_draft_preview_if_allowed(
        query=query,
        evidence_plan=evidence,
        investigation_plan=validated_plan,
        unsafe_enforcement=bool((_query_signals_from_state(state) or {}).get("block_or_contain")),
        llm_intent_advisory=(
            state["llm_intent_advisory"].model_dump()
            if isinstance(state.get("llm_intent_advisory"), LLMIntentAdvisory)
            else state.get("llm_intent_advisory")
            if isinstance(state.get("llm_intent_advisory"), dict)
            else None
        ),
        query_understanding=state.get("query_understanding"),
    )
    execution, human_review = _execution_stage(
        trace_id=trace_id,
        selected_skill="guided_investigation",
        workflow_plan=workflow_plan,
        spl_validation=None,
        precondition_evaluation=state.get("route_plan_shadow", {}).get("precondition_evaluation"),
        requested_mcp_server=request.requested_mcp_server,
        requested_mcp_tool=request.requested_mcp_tool,
        mcp_allowed=False,
    )
    emit_mcp_status_from_execution(execution)
    trace = {
        "dispatch_source": "guided_hybrid_dispatch",
        "dispatch_schedule": dispatch_steps,
    }
    updated: ChatPipelineState = {
        **collection_state,
        "evidence_plan": evidence_payload,
        "workflow_plan": workflow_plan,
        "candidate_spl": None,
        "spl_validation": None,
        "spl_draft_preview": spl_draft_preview,
        "execution": execution,
        "human_review": human_review,
        "guided_handoff_trace": handoff_trace,
        "plan_dispatch_trace": trace,
    }
    updated = _record_guided_resource_outcome(
        updated,
        spl_draft_preview=spl_draft_preview,
        update_spl=True,
    )
    return graph_node_rag_early(updated)


def _uses_rag_only_path(state: ChatPipelineState) -> bool:
    if _session_spl_refine_active(state):
        return False
    planning = state.get("planning_decision")
    path_type = planning.get("path_type") if isinstance(planning, dict) else None
    if path_type == "guided_investigation":
        return True
    answer_mode = _evidence_plan(state).get("answer_mode")
    return answer_mode in {"rag_only", "guided_investigation"} or path_type == "generic_soc_guidance"


def _uses_pre_mcp_rag(state: ChatPipelineState) -> bool:
    plan = _evidence_plan(state)
    return bool(plan.get("needs_rag")) and plan.get("rag_phase") == "pre_mcp"


def _path_type(state: ChatPipelineState) -> str | None:
    planning = state.get("planning_decision")
    if isinstance(planning, dict):
        value = planning.get("path_type")
        if isinstance(value, str) and value:
            return value
    return None


def _response_use_case(state: ChatPipelineState) -> UseCaseSelection | None:
    if _path_type(state) == "generic_soc_guidance":
        return None
    return state.get("selected_use_case")


def _rag_no_match(soc_kb_retrieval: dict[str, Any] | None) -> bool:
    if not isinstance(soc_kb_retrieval, dict):
        return False
    return str(soc_kb_retrieval.get("retrieval_status") or "") in {"no_match", "disabled", "failed"}


def _resource_decision_labels(state: ChatPipelineState) -> list[str]:
    """Non-sensitive resource-decision labels for sidecar context (keys only, no
    payloads). Returns [] when no resource plan provenance is present."""
    evidence_plan = state.get("evidence_plan")
    if not isinstance(evidence_plan, dict):
        return []
    provenance = (evidence_plan.get("resource_plan") or {}).get("provenance") or {}
    decisions = provenance.get("resource_decisions")
    if isinstance(decisions, dict):
        return [str(key) for key in decisions.keys()]
    if isinstance(decisions, list):
        return [str(item) for item in decisions if isinstance(item, (str, int))]
    return []


def _promotion_lifecycle_for_composer_skip(state: ChatPipelineState) -> dict[str, Any] | None:
    evidence_plan = state.get("evidence_plan")
    if isinstance(evidence_plan, dict):
        summary = evidence_plan.get("promotion_lifecycle_summary")
        if isinstance(summary, dict):
            return summary
    use_case_id = None
    q2i = state.get("query_to_intent") or {}
    if isinstance(q2i, dict):
        mappings = q2i.get("candidate_mappings") or {}
        if isinstance(mappings, dict):
            ids = mappings.get("use_case_ids") or []
            if ids:
                use_case_id = ids[0]
    return _preplan_promotion_lifecycle_for_llm_skip(state.get("query_understanding"), use_case_id)


def _composer_skip_registry_context(state: ChatPipelineState) -> tuple[list[str] | None, dict | None]:
    q2i = state.get("query_to_intent") or {}
    if not isinstance(q2i, dict):
        return None, None
    mappings = q2i.get("candidate_mappings") or {}
    if not isinstance(mappings, dict):
        return None, None
    warnings = mappings.get("registry_warnings")
    registry_warnings = [str(item) for item in warnings] if isinstance(warnings, list) else None
    catalog_row = mappings.get("catalog_row") if isinstance(mappings.get("catalog_row"), dict) else None
    return registry_warnings, catalog_row


def _match_path_from_state(state: ChatPipelineState) -> str | None:
    evidence_plan = state.get("evidence_plan")
    if isinstance(evidence_plan, dict):
        provenance = (evidence_plan.get("resource_plan") or {}).get("provenance") or {}
        match_path = provenance.get("match_path")
        if match_path:
            return str(match_path)
    planning = state.get("planning_decision")
    if isinstance(planning, dict):
        summary = planning.get("resource_plan_summary") or {}
        if isinstance(summary, dict) and summary.get("match_path"):
            return str(summary.get("match_path"))
    routed = state.get("routed") or {}
    provenance = routed.get("routing_provenance") or {}
    if isinstance(provenance, dict) and provenance.get("match_path"):
        return str(provenance.get("match_path"))
    return None


def _generic_soc_guidance_path(planning_decision: dict[str, Any] | None) -> bool:
    return isinstance(planning_decision, dict) and planning_decision.get("path_type") == "generic_soc_guidance"


def _spl_allowed(state: ChatPipelineState) -> bool:
    resolution = state.get("session_context_resolution")
    if (
        isinstance(resolution, SessionContextResolution)
        and resolution.spl_refine_from_session
        and resolution.status.staleness == "fresh"
        and resolution.pins is not None
        and resolution.pins.last_candidate_spl
    ):
        return True
    return bool(_evidence_plan(state).get("spl_allowed", True))


def _mcp_allowed(state: ChatPipelineState) -> bool:
    return _mcp_allowed_decision_from_plan(_evidence_plan(state))["allowed"] is True


def _context_selected_skill(state: ChatPipelineState) -> str:
    workflow_plan = state.get("workflow_plan")
    if isinstance(workflow_plan, dict):
        skill = workflow_plan.get("skill")
        if isinstance(skill, str) and skill.strip():
            return skill.strip()
    routed = state.get("routed") or {}
    return str(routed.get("skill") or _effective_routing_skill(state))


def _selected_use_case(query: str, *, query_signals: dict[str, Any] | None = None) -> UseCaseSelection | None:
    matches = match_use_cases(query, limit=5)
    if not matches:
        return None
    normalized = " ".join(query.lower().split())
    signals = query_signals or {}
    alert_context_present = bool(signals.get("alert_context_present"))
    if not alert_context_present:
        matches = [item for item in matches if item.use_case_id != "soc_map_alert_mitre"] or matches
    if signals.get("powershell_context"):
        preferred = next((item for item in matches if item.use_case_id == "edr_powershell_suspicious_command"), None)
        if preferred is not None:
            return preferred
    if signals.get("dns_beaconing"):
        preferred = next((item for item in matches if item.use_case_id == "dns_beaconing_candidate"), None)
        if preferred is not None:
            return preferred
    if signals.get("spl_suppressed"):
        preferred = next((item for item in matches if item.use_case_id == "soc_show_sop"), None)
        if preferred is not None:
            return preferred
    if signals.get("playbook_procedure") and not (
        signals.get("live_investigation_verbs") or signals.get("failed_login") or signals.get("time_window_24h")
    ):
        preferred = next((item for item in matches if item.use_case_id == "soc_show_sop"), None)
        if preferred is not None:
            return preferred
    from app.query_understanding.success_after_failure import detect_success_after_failure

    if detect_success_after_failure(normalized) or signals.get("success_after_failure"):
        preferred = next((item for item in matches if item.use_case_id == "auth_success_after_failure"), None)
        if preferred is not None:
            return preferred
    return matches[0]


def _mitre_outputs_for_finalize(
    *,
    query: str | None = None,
    question_ref: str | None,
    use_case_id: str | None,
    source_refs: list[str],
    intent_classification: dict[str, Any] | None,
    evidence_plan: dict[str, Any] | None,
    query_signals: dict[str, Any] | None = None,
    source_evidence: list[dict[str, Any]] | None = None,
    structured_context: dict[str, Any] | None = None,
    session_alert_context: bool = False,
    planning_decision: dict[str, Any] | None = None,
    execution: dict[str, Any] | None = None,
    canonical_facts: dict[str, Any] | None = None,
) -> tuple[list[Any], dict[str, Any] | None]:
    """MITRE mappings via Phase 7 evidence branch when control plane is active."""
    effective_use_case_id = _mitre_use_case_for_query(query or "", use_case_id, intent_classification)
    branch_mappings, branch_decision, branch = run_mitre_evidence_branch(
        query=query or "",
        question_ref=question_ref,
        use_case_id=effective_use_case_id,
        source_refs=source_refs,
        intent_classification=intent_classification,
        evidence_plan=evidence_plan,
        planning_decision=planning_decision,
        query_signals=query_signals,
        source_evidence=source_evidence,
        structured_context=structured_context,
        alert_context_present=_mitre_alert_context_present(query or "", session_alert_context=session_alert_context),
        execution=execution,
    )
    if branch.ran:
        return branch_mappings, branch_decision
    if settings.ai_soc_planner_mitre_branch_enabled and branch.status == "not_applicable":
        return [], planner_mitre_branch_suppressed_decision(
            use_case_id=effective_use_case_id,
            question_ref=question_ref,
            reason=str(branch.reason),
        )
    from app.chat.canonical_facts_spine import negative_evidence_from_facts
    from app.chat.contracts.canonical_facts import CanonicalFacts

    negative_evidence = None
    if isinstance(canonical_facts, dict):
        negative_evidence = negative_evidence_from_facts(CanonicalFacts.model_validate(canonical_facts))
    if negative_evidence is None:
        negative_evidence = extract_negative_evidence(
            query_signals=query_signals,
            source_evidence=source_evidence,
            structured_context=structured_context,
        )
    from app.chat.mitre_branch import _source_profile_missing

    decision = resolve_mitre_decision(
        question_ref=question_ref,
        use_case_id=effective_use_case_id,
        source_refs=source_refs,
        intent_classification=intent_classification,
        evidence_plan=evidence_plan,
        alert_context_present=_mitre_alert_context_present(query or "", session_alert_context=session_alert_context),
        negative_evidence=negative_evidence,
        use_case_review_guidance=bool((query_signals or {}).get("use_case_review_guidance")),
        source_evidence=source_evidence,
        execution=execution,
        source_profile_missing=_source_profile_missing(evidence_plan),
    )
    if not decision.answer_visible:
        return [], decision.model_dump()
    visible = [MitreMappingDecision(**item) for item in decision.techniques]
    return visible, decision.model_dump()


def _mitre_use_case_for_query(
    query: str,
    use_case_id: str | None,
    intent_classification: dict[str, Any] | None,
) -> str | None:
    normalized = " ".join(query.lower().split())
    success_after = _success_after_failure_context(normalized)
    if use_case_id == "auth_success_after_failure":
        return use_case_id
    if use_case_id and use_case_id not in {"soc_map_alert_mitre", "auth_failed_login_spike"}:
        if success_after and use_case_id == "auth_failed_login_spike":
            return "auth_success_after_failure"
        return use_case_id
    intent = intent_classification or {}
    intent_family = str(intent.get("intent_family") or "")
    if intent_family in {"mitre_mapping", "hybrid_alert_review"}:
        if success_after:
            return "auth_success_after_failure"
        if any(term in normalized for term in ("failed login", "failed-logins", "login failure", "failed authentication")):
            return "auth_failed_login_spike"
    if success_after:
        return "auth_success_after_failure"
    return use_case_id


def _success_after_failure_context(normalized: str) -> bool:
    from app.query_understanding.success_after_failure import detect_success_after_failure

    return detect_success_after_failure(normalized)


def _mitre_alert_context_present(query: str, *, session_alert_context: bool = False) -> bool:
    if session_alert_context:
        return True
    normalized = " ".join(query.lower().split())
    if re.search(r"\balt-\d{4}-\d+\b", normalized):
        return True
    if re.search(r"\bfor alert\b", normalized):
        return True
    if re.search(r"\balert\s+[a-z0-9][\w.-]+\b", normalized):
        return True
    if any(marker in normalized for marker in _ALERT_CONTEXT_MARKERS):
        return True
    if any(term in normalized for term in ("failed login", "failed-logins", "login failure", "failed authentication")):
        has_negation = any(
            term in normalized
            for term in (
                "no successful login",
                "no success",
                "no endpoint telemetry",
                "no endpoint evidence",
                "no evidence of credential dumping",
                "no credential dumping",
            )
        )
        if has_negation and any(term in normalized for term in ("external ip", "external ips", "source ip", "source ips")):
            return True
        if has_negation and "across" in normalized and any(term in normalized for term in ("accounts", "users", "hosts", "sources")):
            return True
    return False


_MITRE_INTENT_KEYWORDS = ("mitre", "att&ck", "attack technique", "map this alert", "map the alert")
# Markers that an alert/event was actually supplied, so mapping can proceed normally.
_ALERT_CONTEXT_MARKERS = ("index=", "sourcetype=", "rule:", "rule ", "alert:", "notable", "signature=", "event id", "eventid")


def _needs_mitre_clarification(
    query: str,
    candidate_spl: dict | None,
    *,
    session_alert_context: bool = False,
    query_signals: dict[str, Any] | None = None,
    intent_classification: dict[str, Any] | None = None,
) -> bool:
    """Conservative heuristic: a MITRE mapping ask with no alert context yet.

    False positives (asking for detail when context was present) are worse than
    false negatives, so any context marker, a generated SPL, or a long message
    routes through normal handling instead.
    """
    if isinstance(query_signals, dict) and query_signals.get("use_case_review_guidance"):
        return False
    if isinstance(query_signals, dict) and query_signals.get("mitre_evidence_threshold"):
        return False
    if isinstance(query_signals, dict) and query_signals.get("cross_skill_investigation"):
        return False
    if isinstance(query_signals, dict) and query_signals.get("cve_focus_investigation"):
        return False
    intent = intent_classification if isinstance(intent_classification, dict) else {}
    if str(intent.get("primary_intent") or "") == "cross_skill_investigation":
        return False
    if str(intent.get("intent_family") or "") in {
        "github_investigation",
        "cve_investigation",
        "alert_summary",
        "hybrid_alert_review",
        "mitre_explanation",
        "reference_knowledge",
    }:
        return False
    normalized = " ".join(query.lower().split())
    if normalized.startswith(("mitre focus:", "cve focus:", "github focus:", "cross-skill")):
        return False
    if not any(keyword in normalized for keyword in _MITRE_INTENT_KEYWORDS):
        return False
    if candidate_spl and candidate_spl.get("candidate_spl"):
        return False
    if len(normalized) > 160:
        return False
    if session_alert_context:
        return False
    return not any(marker in normalized for marker in _ALERT_CONTEXT_MARKERS)


def _mitre_clarification_review() -> dict:
    return human_review(
        "intent_clarification",
        "mitre_mapping_requires_alert_context",
        "soc_analyst",
        ["provide_alert_details", "cancel"],
        "To map to MITRE ATT&CK I need the alert context first: the alert title, detection rule, "
        "notable/event ID, or the SPL with a few sample fields. I will not generate SPL or guess "
        "techniques without grounding.",
    )


def _unsafe_action_review() -> dict:
    from app.chat.guidance_templates import build_unsafe_action_guidance

    return human_review(
        "execution_approval",
        "unsafe_action_blocked",
        "soc_analyst",
        ["provide_investigation_guidance", "cancel"],
        build_unsafe_action_guidance(),
    )


_SPL_GOVERNANCE_CLARIFICATION_REASONS = frozenset(
    {
        "spl_template_missing",
        "spl_template_not_allowed_by_enrichment",
        "spl_template_not_active",
        "spl_template_not_production_executable",
        "spl_template_sop_only_no_active_investigation_support",
        "spl_template_planned_no_free_spl_fallback",
        "spl_template_unavailable_no_free_spl_fallback",
        "spl_template_unknown_no_free_spl_fallback",
        "spl_template_governance_blocked",
        "runtime_spl_governance_not_allowed",
        "active_enrichment_without_allowed_template",
        "spl_template_active_source_profile_missing",
        "missing_index",
        "missing_sourcetype",
        "index_or_datamodel",
    }
)


def _spl_clarification_user_message(spl_validation: dict[str, Any] | None) -> str:
    reason = "spl_generation_requires_source_clarification"
    if isinstance(spl_validation, dict):
        reason = str(
            spl_validation.get("review_required_reason")
            or spl_validation.get("llm_fallback_reason")
            or spl_validation.get("candidate_provider_reason")
            or reason
        )
        reject_reasons = {str(item) for item in spl_validation.get("reject_reasons") or []}
        if "missing_index" in reject_reasons or "missing_sourcetype" in reject_reasons:
            reason = "spl_template_active_source_profile_missing"
        elif "index_or_datamodel" in reject_reasons:
            reason = "spl_template_active_source_profile_missing"
    messages = {
        "spl_template_active_source_profile_missing": (
            "Template active but source profile missing: index/sourcetype/key fields required."
        ),
        "spl_template_missing": (
            "Governed use case is active but no default SPL template was bound for this request."
        ),
        "spl_template_not_allowed_by_enrichment": (
            "The selected SPL template is not allowed for this governed use case."
        ),
        "runtime_spl_governance_not_allowed": (
            "SPL template governance is blocked until curated enrichment activation is complete for this use case."
        ),
        "active_enrichment_without_allowed_template": (
            "Curated enrichment is active but no allowed SPL template is configured for this use case."
        ),
        "spl_template_sop_only_no_active_investigation_support": (
            "This use case is SOP-only; active investigation SPL templates are not available."
        ),
        "spl_template_planned_no_free_spl_fallback": (
            "SPL template for this use case is planned but not yet active."
        ),
        "spl_template_unavailable_no_free_spl_fallback": (
            "No active governed SPL template is available for this use case."
        ),
    }
    if reason in messages:
        return messages[reason]
    if reason in _SPL_GOVERNANCE_CLARIFICATION_REASONS:
        return (
            "Governed SPL drafting is blocked for this request. "
            f"Reason: {reason.replace('_', ' ')}."
        )
    return (
        "I need a governed template match or supported source details before drafting SPL. "
        "Confirm the index, sourcetype, key fields, and time range for this request."
    )


def _is_t2_review_only(
    candidate_spl: dict[str, Any] | None,
    spl_validation: dict[str, Any] | None,
) -> bool:
    cs = candidate_spl if isinstance(candidate_spl, dict) else {}
    sv = spl_validation if isinstance(spl_validation, dict) else {}
    return (
        cs.get("generation_mode") == "t2_spl_native_review"
        or str(sv.get("review_required_reason") or "") == "t2_spl_native_review_only"
    )



def _is_universal_spl_authoring_review(
    candidate_spl: dict[str, Any] | None,
    spl_validation: dict[str, Any] | None,
) -> bool:
    cs = candidate_spl if isinstance(candidate_spl, dict) else {}
    sv = spl_validation if isinstance(spl_validation, dict) else {}
    if cs.get("detection_family") == "universal_timestamp_spl":
        return True
    return str(sv.get("review_required_reason") or "") == "universal_spl_authoring_review_only"


def _universal_spl_authoring_review() -> dict:
    return human_review(
        "spl_review_required",
        "universal_spl_authoring_review_only",
        "soc_analyst",
        ["review_draft_spl", "cancel"],
        "Universal/template-free review-only SPL draft. Splunk %w uses 0=Sunday and 6=Saturday "
        "for weekend filtering. Nothing was executed; validate before any future execution path.",
        required=True,
    )


def _t2_review_only_review() -> dict:
    return human_review(
        "spl_review_required",
        "t2_spl_native_review_only",
        "soc_analyst",
        ["review_draft_spl", "provide_source_profile", "cancel"],
        "A review-only SPL draft was generated. Validate the source profile and fields "
        "before any execution path. Nothing was executed.",
        required=True,
    )


def _spl_clarification_review(spl_validation: dict[str, Any] | None) -> dict:
    reason = "spl_generation_requires_source_clarification"
    if isinstance(spl_validation, dict):
        reason = str(
            spl_validation.get("review_required_reason")
            or spl_validation.get("llm_fallback_reason")
            or spl_validation.get("candidate_provider_reason")
            or reason
        )
    return human_review(
        "intent_clarification",
        reason,
        "soc_analyst",
        ["provide_source_profile", "enable_governed_llm_fallback", "add_catalog_template", "cancel"],
        _spl_clarification_user_message(spl_validation),
    )


def _disagreement_reason(comparison: dict) -> str:
    if comparison.get("skill_match") is False:
        return "skill_mismatch"
    if comparison.get("tool_plan_match") is False:
        return "tool_plan_mismatch"
    return "unknown_mismatch"


def _route_plan_shadow_stage(
    query: str,
    *,
    deterministic_primary_skill: str | None = None,
    selected_use_case: UseCaseSelection | None = None,
    query_understanding: Any | None = None,
) -> dict:
    shadow = _route_plan_shadow_base(model_role="instruct_candidate_only")
    preflight = preflight_route_plan(query)
    shadow["preflight_status"] = preflight.route_status.value if preflight.route_status else "passed"
    shadow["missing_slots"] = list(preflight.missing_slots)
    shadow["blocking_findings"] = list(preflight.blocking_findings)
    shadow["warnings"] = list(preflight.warnings)

    if preflight.is_blocked:
        shadow["route_status"] = preflight.route_status.value if preflight.route_status else None
        shadow["candidate_available"] = False
        shadow["candidate_reason"] = "deterministic_preflight_blocked"
        apply_template_match_to_shadow(shadow, normalized_route_plan=None)
        return shadow

    deterministic_candidate = None
    if True:
        deterministic_candidate = build_deterministic_route_plan_candidate(
            query=query,
            selected_use_case=selected_use_case,
            query_understanding=query_understanding,
        )

    if deterministic_candidate is not None:
        validation = validate_route_plan_candidate(deterministic_candidate)
        if validation.is_valid:
            normalized = validation.normalized_route_plan or {}
            shadow.update(
                {
                    "route_status": normalized.get("route_status"),
                    "primary_skill": normalized.get("primary_skill") or deterministic_candidate.get("primary_skill"),
                    "pattern_id": normalized.get("pattern_id") or deterministic_candidate.get("pattern_id"),
                    "candidate_available": True,
                    "candidate_reason": "deterministic_control_plane_route_plan",
                    "validation_result": {"is_valid": validation.is_valid},
                    "validation_findings": list(validation.validation_findings),
                    "blocking_findings": list(validation.blocking_findings),
                    "warnings": sorted(set(shadow["warnings"]) | set(validation.warnings)),
                    "normalized_plan_available": True,
                    "llm_candidate_route_plan_available": False,
                    "deterministic_route_plan_wins": True,
                    "model_role": "none",
                }
            )
            shadow["supporter_trace"] = build_supporter_trace(
                validation.normalized_route_plan,
                query=query,
                shadow=shadow,
                runtime_invoked=True,
            )
            apply_template_match_to_shadow(shadow, normalized_route_plan=validation.normalized_route_plan)
            parameters = normalized.get("parameters")
            if isinstance(parameters, dict):
                shadow["route_plan_parameters"] = dict(parameters)
            time_window = normalized.get("time_window")
            if isinstance(time_window, str) and time_window.strip():
                shadow["route_plan_time_window"] = time_window
            return shadow
        shadow["warnings"] = sorted(
            set(shadow["warnings"]) | {"deterministic_route_plan_validation_failed"} | set(validation.warnings)
        )

    llm_result = _routes_chat().generate_llm_route_plan_candidate(
        query,
        preflight=preflight,
        deterministic_primary_skill=deterministic_primary_skill,
    )
    llm_result.apply_to_shadow(shadow)

    candidate: dict | None = None
    candidate_reason: str | None = None
    validation = llm_result.validation

    if llm_result.llm_candidate_route_plan_available and llm_result.candidate is not None:
        candidate = llm_result.candidate
        candidate_reason = llm_result.candidate_reason or "llm_shadow_candidate"
        shadow["model_role"] = "instruct_candidate_only"
    else:
        hook_candidate = _routes_chat()._route_plan_shadow_candidate(query)
        if hook_candidate is not None:
            candidate = hook_candidate
            candidate_reason = "test_or_mock_candidate"
            validation = validate_route_plan_candidate(candidate)
        elif llm_result.llm_called:
            shadow["model_role"] = "instruct_candidate_only"
            candidate_reason = "llm_candidate_dropped"
        else:
            candidate_reason = skipped_reason_to_candidate_reason(llm_result.skipped_reason)
            shadow["model_role"] = (
                "none" if ROUTE_PLAN_GENERATOR_MODEL_FAMILY != "instruct" else "instruct_candidate_only"
            )

    if candidate is None:
        shadow["candidate_available"] = False
        shadow["candidate_reason"] = candidate_reason or "live_llm_routing_disabled"
        shadow["supporter_trace"] = build_supporter_trace(None)
        apply_template_match_to_shadow(shadow, normalized_route_plan=None)
        return shadow

    if validation is None:
        validation = validate_route_plan_candidate(candidate)
    normalized = validation.normalized_route_plan or {}
    shadow.update(
        {
            "route_status": normalized.get("route_status"),
            "primary_skill": normalized.get("primary_skill") or candidate.get("primary_skill"),
            "pattern_id": normalized.get("pattern_id") or candidate.get("pattern_id"),
            "candidate_available": True,
            "candidate_reason": candidate_reason,
            "validation_result": {"is_valid": validation.is_valid},
            "validation_findings": list(validation.validation_findings),
            "blocking_findings": list(validation.blocking_findings),
            "warnings": sorted(set(shadow["warnings"]) | set(validation.warnings)),
            "normalized_plan_available": bool(validation.normalized_route_plan and validation.is_valid),
        }
    )
    shadow["supporter_trace"] = build_supporter_trace(
        validation.normalized_route_plan or candidate,
        query=query,
        shadow=shadow,
        runtime_invoked=True,
    )
    validated_plan = validation.normalized_route_plan if validation.is_valid else None
    apply_template_match_to_shadow(shadow, normalized_route_plan=validated_plan)
    if validated_plan:
        parameters = validated_plan.get("parameters")
        if isinstance(parameters, dict):
            shadow["route_plan_parameters"] = dict(parameters)
        time_window = validated_plan.get("time_window")
        if isinstance(time_window, str) and time_window.strip():
            shadow["route_plan_time_window"] = time_window
    return shadow


def _route_plan_shadow_base(*, model_role: str) -> dict:
    return {
        "enabled": True,
        "mode": "dormant_shadow",
        "preflight_status": None,
        "route_status": None,
        "primary_skill": None,
        "pattern_id": None,
        "candidate_available": False,
        "candidate_reason": None,
        "validation_result": None,
        "validation_findings": [],
        "blocking_findings": [],
        "warnings": [],
        "missing_slots": [],
        "normalized_plan_available": False,
        "execution_authorized": False,
        "llm_called": False,
        "llm_role": None,
        "llm_model_family": None,
        "llm_candidate_route_plan_available": False,
        "llm_candidate_dropped_reasons": [],
        "deterministic_route_plan_wins": True,
        "disagreements": [],
        "analyst_summary_shadow_available": False,
        "analyst_summary_shadow_text": None,
        "analyst_summary_trace_bullets": [],
        "analyst_summary_dropped_reasons": [],
        "analyst_summary_shadow_source": None,
        "analyst_summary_narration_llm_called": False,
        "mcp_called": False,
        "spl_generated": False,
        "spl_executed": False,
        "model_role": model_role,
        "reasoning_model_used": ROUTE_PLAN_REASONING_MODEL_ALLOWED,
        "intent_operation_bridge": None,
        "route_authority_compare": None,
        "precondition_evaluation": None,
        "supporter_trace": None,
        "ood_llm_route_plan_lab": None,
        "operation_audit": None,
        "use_case_registry_bridge": None,
        "routing_skill_resolution": None,
    }


def _route_plan_for_supporters(route_plan_shadow: dict[str, Any]) -> dict[str, Any]:
    plan: dict[str, Any] = {}
    for key in ("primary_skill", "pattern_id", "route_status", "source_class", "evidence_needs"):
        value = route_plan_shadow.get(key)
        if value is not None:
            plan[key] = value
    parameters = route_plan_shadow.get("route_plan_parameters")
    if isinstance(parameters, dict):
        plan["parameters"] = dict(parameters)
    return plan


def _apply_ood_llm_lab_metadata(route_plan_shadow: dict[str, Any], query: str) -> None:
    """Annotate P6-add lab-primary OOD routing without granting execution authority."""
    if settings.routing_mode != "llm_primary_lab" or not settings.routing_lab_llm_primary_enabled:
        route_plan_shadow["ood_llm_route_plan_lab"] = {
            "enabled": False,
            "reason": "lab_primary_mode_disabled",
        }
        return
    if settings.ai_soc_environment_mode == "production":
        route_plan_shadow["ood_llm_route_plan_lab"] = {
            "enabled": False,
            "reason": "production_blocked",
        }
        return

    runtime_map = route_plan_shadow.get("question_runtime_map")
    registry_hit = bool(isinstance(runtime_map, dict) and runtime_map.get("map_entry_found") is True)
    route_plan_shadow["supporter_trace"] = build_supporter_trace(
        _route_plan_for_supporters(route_plan_shadow),
        query=query,
        shadow=route_plan_shadow,
        runtime_invoked=True,
    )
    route_plan_shadow["ood_llm_route_plan_lab"] = {
        "enabled": True,
        "registry_exact_match": registry_hit,
        "llm_primary_for_ood": not registry_hit,
        "candidate_source": route_plan_shadow.get("candidate_reason"),
        "validator_wins": True,
        "execution_authorized": False,
        "mcp_called": False,
    }


def _effective_routing_skill(state: ChatPipelineState) -> str:
    if True:
        adjudication = state.get("route_adjudication")
        if isinstance(adjudication, dict):
            final_route = adjudication.get("final_route")
            if isinstance(final_route, str) and final_route.strip():
                return final_route.strip()
    resolution = state.get("routing_skill_resolution")
    if isinstance(resolution, dict):
        skill = resolution.get("effective_skill")
        if isinstance(skill, str) and skill.strip():
            return skill.strip()
    routed = state.get("routed") or {}
    return str(routed.get("skill") or "knowledge_recall")



def _candidate_match_path(state: ChatPipelineState) -> str | None:
    routed = state.get("routed")
    if isinstance(routed, dict):
        provenance = routed.get("routing_provenance")
        if isinstance(provenance, dict):
            value = provenance.get("deterministic_match_path")
            if isinstance(value, str) and value:
                return value
    query_to_intent = state.get("query_to_intent")
    if isinstance(query_to_intent, dict):
        mappings = query_to_intent.get("candidate_mappings")
        if isinstance(mappings, dict):
            value = mappings.get("match_path")
            if isinstance(value, str) and value:
                return value
    return None

def _query_signals_from_state(state: ChatPipelineState) -> dict[str, Any] | None:
    q2i = state.get("query_to_intent")
    if not isinstance(q2i, dict):
        return None
    signals = q2i.get("query_signals")
    return signals if isinstance(signals, dict) else None


def _route_plan_shadow_candidate(query: str) -> dict | None:
    return None


def _session_stale_clarification_required(state: ChatPipelineState) -> bool:
    resolution = state.get("session_context_resolution")
    return isinstance(resolution, SessionContextResolution) and resolution.status.clarification_required


def _session_stale_clarification_review() -> dict[str, Any]:
    return human_review(
        "session_context_stale",
        "session_context_stale_or_missing",
        "soc_analyst",
        ["repeat_alert_context", "cancel"],
        "The prior investigation context is stale or missing. Repeat the alert context or start a fresh question.",
    )


def _session_spl_refine_stage(
    *,
    state: ChatPipelineState,
    trace_id: str,
    skill: str,
    user_query: str,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    resolution = state.get("session_context_resolution")
    if not isinstance(resolution, SessionContextResolution) or not resolution.spl_refine_from_session:
        return None
    if resolution.pins is None or not resolution.pins.last_candidate_spl:
        return None
    if not _spl_allowed(state):
        return None
    spl_text = resolution.pins.last_candidate_spl
    validation = validate_spl(spl_text)
    profile = build_splunk_capability_profile(required_saia_tool="saia_generate_spl")
    candidate_payload = {
        "trace_id": trace_id,
        "skill": skill,
        "user_query": user_query,
        "candidate_spl": spl_text,
        "generation_mode": "session_refine",
        "confidence": 0.72,
        "assumptions": ["session_context_refine"],
        "warnings": ["session_context_refine_revalidated"],
        "selected_candidate_spl_provider": "session_context",
        "reason": "session_context_refine",
        "validation_required": True,
        "execution_eligible": False,
        "spl_template_status": resolution.pins.last_spl_template_status,
    }
    validation_payload = {
        **validation,
        "selected_candidate_spl_provider": "session_context",
        "candidate_provider_reason": "session_context_refine",
        "spl_template_status": resolution.pins.last_spl_template_status,
        "template_production_executable": False,
    }
    if True:
        template_id = (
            state["selected_use_case"].default_spl_template
            if state.get("selected_use_case") is not None
            else None
        )
        validation_payload = validate_spl_slot_bindings(
            validation_payload,
            user_query=user_query,
            query_signals=_query_signals_from_state(state),
            template_id=template_id,
        )
    telemetry = _routes_chat().get_telemetry_connector()
    telemetry.record_spl_validation(
        trace_id,
        stage="spl_validation_result",
        approved=validation_payload["approved"],
        reject_reasons=validation_payload["reject_reasons"],
        warnings=validation_payload["warnings"],
        policy_version=validation_payload["policy_version"],
        optimization_steps=validation_payload.get("spl_optimization_steps"),
        optimization_rejected=validation_payload.get("spl_optimization_rejected"),
        optimization_reject_reason=validation_payload.get("spl_optimization_reject_reason"),
    )
    return candidate_payload, validation_payload


_FENCED_SPL_RE = re.compile(r"```(?:spl)?\s*(?P<spl>.*?)```", re.IGNORECASE | re.DOTALL)
_INLINE_SPL_RE = re.compile(r"\b(search\s+index\s*=.*)$", re.IGNORECASE | re.DOTALL)
_INLINE_SPL_TRAILER_RE = re.compile(
    r"\.\s+(?:validate|optimize|revalidate|simplify|rewrite|list|and\s+if|if\s+it|ask\s+me|do\s+not)\b",
    re.IGNORECASE,
)


def _extract_user_provided_spl(user_query: str) -> str | None:
    fenced = _FENCED_SPL_RE.search(user_query)
    if fenced:
        spl = fenced.group("spl").strip()
        return spl or None
    inline = _INLINE_SPL_RE.search(user_query)
    if not inline:
        return None
    spl = inline.group(1).strip().strip("`")
    trailer = _INLINE_SPL_TRAILER_RE.search(spl)
    if trailer:
        spl = spl[: trailer.start()].strip()
    return spl.strip().rstrip(".") or None


def _candidate_from_user_provided_spl(
    *,
    trace_id: str,
    skill: str,
    user_query: str,
    user_spl: str,
    telemetry: Any,
    profile: Any,
    spl_governance: dict[str, Any] | None,
    query_signals: dict[str, Any] | None,
    slot_binding_enabled: bool,
    template_id: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    postprocessor_trace: dict[str, Any] = {}
    postprocessor_warnings: list[str] = []
    final_spl = user_spl
    if not _defer_spl_postprocessor_inline():
        postprocessed = finalize_review_only_spl(
            user_spl,
            query=user_query,
            family="user_provided_spl",
            llm_generated=False,
        )
        final_spl = postprocessed.normalized_spl
        postprocessor_trace = dict(postprocessed.trace)
        postprocessor_warnings = list(postprocessed.warnings)
    validation = validate_spl(final_spl)
    optimization: dict[str, Any] = {
        "provider": "rule_based",
        "optimization_applied": False,
        "revalidation_status": None,
        "revalidation_approved": False,
    }
    if isinstance(query_signals, dict) and query_signals.get("optimize_spl"):
        final_spl, validation, optimization = merge_post_validation_optimization(
            final_spl,
            validation,
            profile=profile,
            user_query=user_query,
        )
    candidate_payload: dict[str, Any] = {
        "trace_id": trace_id,
        "skill": skill,
        "user_query": user_query,
        "candidate_spl": final_spl,
        "generation_mode": "user_provided_spl",
        "confidence": 0.9,
        "assumptions": ["user_provided_spl_reused_as_candidate"],
        "warnings": ["user_provided_spl_requires_validation_and_hil"],
        "selected_candidate_spl_provider": "user_provided_spl",
        "fallback_required": False,
        "candidate_spl_generated": True,
        "validation_required": True,
        "execution_eligible": False,
        "capability_profile": profile.model_dump(),
        "template_id": template_id,
        "postprocessor_applied": bool(postprocessor_trace.get("postprocessor_applied")),
        "review_only_spl_postprocessor_trace": postprocessor_trace,
    }
    if postprocessor_warnings:
        candidate_payload["review_only_spl_postprocessor_warnings"] = postprocessor_warnings
    validation_payload: dict[str, Any] = {
        "approved": validation["approved"],
        "normalized_spl": validation["normalized_spl"],
        "reject_reasons": validation["reject_reasons"],
        "warnings": validation["warnings"],
        "enforced_limits": validation["enforced_limits"],
        "policy_version": validation["policy_version"],
        "selected_candidate_spl_provider": "user_provided_spl",
        "candidate_provider_reason": "user_provided_spl",
        "saia_available": False,
        "fallback_required": False,
        "spl_explanation_provider": "rule_based",
        "spl_optimization_provider": optimization.get("provider") or "rule_based",
        "spl_guidance_provider": "rule_based",
        "optimization_applied": bool(optimization.get("optimization_applied")),
        "optimization_revalidation_status": optimization.get("revalidation_status"),
        "optimization_revalidation_approved": bool(optimization.get("revalidation_approved")),
        "spl_optimization_steps": optimization.get("simplification_steps") or [],
        "spl_optimization_rejected": bool(optimization.get("simplification_rejected")),
        "spl_optimization_reject_reason": optimization.get("simplification_reject_reason"),
        "capability_profile": profile.model_dump(),
        "template_id": template_id,
        "review_only_spl_postprocessor_trace": postprocessor_trace,
        "template_production_executable": False,
    }
    _merge_spl_governance(candidate_payload, validation_payload, spl_governance)
    _mark_spl_review_status(candidate_payload, validation_payload)
    if slot_binding_enabled:
        validation_payload = validate_spl_slot_bindings(
            validation_payload,
            user_query=user_query,
            query_signals=query_signals,
            template_id=template_id,
        )
        _mark_spl_review_status(candidate_payload, validation_payload)
    telemetry.record_spl_validation(
        trace_id,
        stage="spl_validation_result",
        approved=validation_payload["approved"],
        reject_reasons=validation_payload["reject_reasons"],
        warnings=validation_payload["warnings"],
        policy_version=validation_payload["policy_version"],
        optimization_steps=validation_payload.get("spl_optimization_steps"),
        optimization_rejected=validation_payload.get("spl_optimization_rejected"),
        optimization_reject_reason=validation_payload.get("spl_optimization_reject_reason"),
    )
    return candidate_payload, validation_payload




def _spl_user_constraint_bindings(
    user_query: str,
    *,
    llm_intent_advisory: LLMIntentAdvisory | dict[str, Any] | None = None,
    query_understanding: Any | None = None,
    template_id: str | None = None,
) -> UserConstraintBindings:
    template = get_spl_template(template_id) if template_id else None
    policy_indexes = None
    policy_sourcetypes = None
    if template is not None and isinstance(template.validation_rules, dict):
        raw_indexes = template.validation_rules.get("allowed_indexes")
        raw_sourcetypes = template.validation_rules.get("allowed_sourcetypes")
        if isinstance(raw_indexes, list) and raw_indexes:
            policy_indexes = tuple(str(item).lower() for item in raw_indexes)
        if isinstance(raw_sourcetypes, list) and raw_sourcetypes:
            policy_sourcetypes = tuple(str(item).lower() for item in raw_sourcetypes)
    source_profile_result = build_source_profile_binding_slots(
        user_query,
        template_id=template_id,
    )
    return build_user_constraint_bindings(
        user_query,
        llm_intent_advisory=llm_intent_advisory,
        query_understanding=query_understanding,
        extra_slots=source_profile_result.slots,
        source_profile_trace=source_profile_result.trace(),
        allowed_indexes=policy_indexes,
        allowed_sourcetypes=policy_sourcetypes,
    )

def persist_llm_spl_plan(
    state: ChatPipelineState, detection_plan: dict[str, Any] | None
) -> ChatPipelineState:
    """Persist the LLM-chosen detection plan onto canonical state (Phase 4B).

    Maps the redacted plan to ``LlmSplPlanSnapshot`` on ``state["llm_spl_plan"]``
    and, when present, ``pipeline_dispatch.runtime_context.llm_spl_plan`` so
    downstream nodes (source-resolve, MCP, MITRE, narration) prefer it over
    re-parsing the query. Advisory only — never execution authority.
    """
    if not isinstance(detection_plan, dict) or not detection_plan:
        return state
    from app.chat.contracts.pipeline_dispatch import LlmSplPlanSnapshot

    snapshot = LlmSplPlanSnapshot(
        index=detection_plan.get("index"),
        sourcetype=detection_plan.get("sourcetype"),
        data_domain=detection_plan.get("data_domain"),
        required_fields=[str(x) for x in (detection_plan.get("required_fields") or [])],
        filters=[str(x) for x in (detection_plan.get("filters") or [])],
        threshold=detection_plan.get("threshold") if isinstance(detection_plan.get("threshold"), dict) else None,
        detection_family=detection_plan.get("detection_family"),
        consumed_by=["spl_source_resolve", "mcp_execution", "mitre_finalize", "narration"],
    )
    snapshot_dump = snapshot.model_dump(mode="json")
    next_state: ChatPipelineState = {**state, "llm_spl_plan": snapshot_dump}
    dispatch = next_state.get("pipeline_dispatch")
    if isinstance(dispatch, dict):
        dispatch = dict(dispatch)
        runtime = dict(dispatch.get("runtime_context") or {})
        runtime["llm_spl_plan"] = snapshot_dump
        dispatch["runtime_context"] = runtime
        next_state["pipeline_dispatch"] = dispatch
    return next_state


def _candidate_spl_stage(
    trace_id: str,
    skill: str,
    user_query: str,
    *,
    spl_allowed: bool = True,
    query_signals: dict[str, Any] | None = None,
    template_id: str | None = None,
    use_case_id: str | None = None,
    slot_binding_enabled: bool = False,
    mapped_pattern_type: str | None = None,
    llm_intent_advisory: LLMIntentAdvisory | dict[str, Any] | None = None,
    query_understanding: Any | None = None,
    llm_turn_budget: Any | None = None,
    mcp_discovery_context: dict[str, Any] | None = None,
    slot_handoff: dict[str, Any] | None = None,
    dispatch_flags: dict[str, bool] | None = None,
) -> tuple[dict | None, dict | None]:
    if not spl_allowed:
        return None, None
    guided_spl_rescue = (
        skill == "guided_investigation"
        and _guided_investigation_spl_rescue_eligible(user_query)
    )
    if skill not in {"attack_discovery", "spl_generation"} and not guided_spl_rescue:
        return None, None

    signals = query_signals if isinstance(query_signals, dict) else {}
    if signals.get("explicit_spl_authoring"):
        telemetry = _routes_chat().get_telemetry_connector()
        profile = build_splunk_capability_profile(required_saia_tool="saia_generate_spl")
        spl_governance = _runtime_spl_governance(use_case_id)
        if is_universal_utility_spl_authoring(user_query, signals):
            from app.spl.utility_spl_authoring import candidate_from_universal_utility_authoring

            utility_draft = candidate_from_universal_utility_authoring(
                trace_id=trace_id,
                skill=skill,
                user_query=user_query,
                telemetry=telemetry,
                profile=profile,
                spl_governance=spl_governance,
                llm_intent_advisory=llm_intent_advisory,
                llm_turn_budget=llm_turn_budget,
            )
            if utility_draft is not None:
                return utility_draft
        # Phase 4.0: the unconditional lab-draft short-circuit for explicit SPL
        # authoring is removed when dispatch v2 is on, so authoring flows through
        # the template -> LLM plan-compiler -> lab-draft failover chain (LLM SPL no
        # longer bypassed). Flag-off keeps the legacy short-circuit byte-identical.
        if not bool(getattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", False)):
            authoring_draft = _candidate_from_lab_draft(
                trace_id=trace_id,
                skill=skill,
                user_query=user_query,
                telemetry=telemetry,
                profile=profile,
                spl_governance=spl_governance,
                pattern_type=mapped_pattern_type,
                use_case_id=use_case_id,
                llm_fallback_reason="explicit_spl_authoring_deterministic_draft",
                live_data_request=bool(signals.get("explicit_spl_authoring")),
                llm_intent_advisory=llm_intent_advisory,
            )
            if authoring_draft is not None:
                return authoring_draft

    telemetry = _routes_chat().get_telemetry_connector()
    profile = build_splunk_capability_profile(required_saia_tool="saia_generate_spl")
    spl_governance = _runtime_spl_governance(use_case_id)
    if signals.get("command_shaped_spl") or signals.get("run_spl") or signals.get("optimize_spl"):
        user_spl = _extract_user_provided_spl(user_query)
        if user_spl:
            return _candidate_from_user_provided_spl(
                trace_id=trace_id,
                skill=skill,
                user_query=user_query,
                user_spl=user_spl,
                telemetry=telemetry,
                profile=profile,
                spl_governance=spl_governance,
                query_signals=signals,
                slot_binding_enabled=slot_binding_enabled,
                template_id=template_id,
            )
    _dispatch_v2_on = bool(getattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", False))
    if guided_spl_rescue and not _dispatch_v2_on:
        t2_native_candidate = _candidate_from_t2_spl_native(
            trace_id=trace_id,
            skill=skill,
            user_query=user_query,
            telemetry=telemetry,
            profile=profile,
            spl_governance=spl_governance,
        )
        return t2_native_candidate if t2_native_candidate is not None else (None, None)
    template = get_spl_template(template_id)
    governance_block_reason = _spl_governance_block_reason(template_id, template, spl_governance)
    if governance_block_reason is not None:
        return _candidate_clarification(
            trace_id=trace_id,
            skill=skill,
            user_query=user_query,
            telemetry=telemetry,
            profile=profile,
            reason=governance_block_reason,
            spl_governance=spl_governance,
        )
    # Phase 7: retire the SCADA/Cisco T2-native early return when dispatch v2 is on
    # — those queries flow through the governed template -> LLM plan-compiler -> lab
    # draft failover chain (Phase 4) instead of short-circuiting to a runtime-profile
    # draft. runtime_source_profiles still supplies validator profiles downstream.
    # Promoting scada_perf/cisco_asa to enabled catalogue templates is deferred until
    # a live Splunk schema exists (Wave-3 posture: templates stay enabled=false until
    # physical lookups are confirmed; avoids eval-green/live-red sourcetype drift).
    runtime_profile = _t2_runtime_profile_for_query(user_query)
    if runtime_profile is not None and not _dispatch_v2_on:
        t2_early = _candidate_from_t2_spl_native(
            trace_id=trace_id,
            skill=skill,
            user_query=user_query,
            telemetry=telemetry,
            profile=profile,
            spl_governance=spl_governance,
        )
        if t2_early is not None:
            return t2_early

    user_bindings = _spl_user_constraint_bindings(
        user_query,
        llm_intent_advisory=llm_intent_advisory,
        query_understanding=query_understanding,
        template_id=template_id,
    )
    if runtime_profile is not None and _dispatch_v2_on:
        catalogue_template_id = _RUNTIME_PROFILE_CATALOGUE_TEMPLATES.get(
            getattr(runtime_profile, "source_profile_id", "") or ""
        )
        if catalogue_template_id:
            # Pre-execution Splunk server alignment: only when LIVE execution is
            # intended (MCP_GLOBAL_EXECUTION_ENABLED), confirm the template's index +
            # lookup CSVs exist on the search head via read-only discovery tools
            # (splunk_get_indexes / splunk_get_knowledge_objects). Unmapped or
            # unreachable -> drop to token-SPL + COE-HIL. Review-only posture
            # (execution off, the default) keeps the catalogue artifact unchanged.
            deps_ok = True
            if bool(getattr(settings, "mcp_global_execution_enabled", False)):
                deps_ok = _catalogue_template_dependencies_met(catalogue_template_id)
            if deps_ok:
                catalogue_candidate = _candidate_from_default_template(
                    trace_id=trace_id,
                    skill=skill,
                    user_query=user_query,
                    template_id=catalogue_template_id,
                    spl_governance=spl_governance,
                    telemetry=telemetry,
                    profile=profile,
                    slot_source=(
                        "llm"
                        if any(source == SLOT_SOURCE_LLM for source in user_bindings.slot_sources.values())
                        else "user"
                    ),
                    user_constraint_bindings=user_bindings,
                )
                if catalogue_candidate is not None:
                    return catalogue_candidate
            else:
                # Server alignment failed -> token-SPL degrade; source-resolve raises
                # the COE-HIL slot clarification for the analyst.
                token_degrade = _candidate_from_t2_spl_native(
                    trace_id=trace_id,
                    skill=skill,
                    user_query=user_query,
                    telemetry=telemetry,
                    profile=profile,
                    spl_governance=spl_governance,
                )
                if token_degrade is not None:
                    return token_degrade
    template_candidate = _candidate_from_default_template(
        trace_id=trace_id,
        skill=skill,
        user_query=user_query,
        template_id=template_id,
        spl_governance=spl_governance,
        telemetry=telemetry,
        profile=profile,
        slot_source=(
            "llm"
            if any(source == SLOT_SOURCE_LLM for source in user_bindings.slot_sources.values())
            else "user"
        ),
        user_constraint_bindings=user_bindings,
    )
    if template_candidate is not None:
        candidate_payload, validation_payload = template_candidate
        telemetry.record_step(
            trace_id,
            "candidate_spl_generated",
            "completed",
            skill=skill,
            generation_mode=candidate_payload["generation_mode"],
            confidence=candidate_payload["confidence"],
            warnings=candidate_payload["warnings"],
            selected_candidate_spl_provider=validation_payload["selected_candidate_spl_provider"],
            fallback_required=validation_payload["fallback_required"],
        )
        if slot_binding_enabled:
            validation_payload = validate_spl_slot_bindings(
                validation_payload,
                user_query=user_query,
                query_signals=query_signals,
                template_id=template_id,
            )
            _mark_spl_review_status(candidate_payload, validation_payload)
        telemetry.record_spl_validation(
            trace_id,
            stage="spl_validation_result",
            approved=validation_payload["approved"],
            reject_reasons=validation_payload["reject_reasons"],
            warnings=validation_payload["warnings"],
            policy_version=validation_payload["policy_version"],
        )
        return candidate_payload, validation_payload

    llm_failover_enabled = _should_use_llm_spl_failover(skill, dispatch_flags=dispatch_flags)
    # B02: when LLM failover is enabled, do not short-circuit planned/missing
    # template rows to clarification — let the LLM generate, then the relevance +
    # validation gates decide. Without failover, preserve the prior clarification.
    if (
        not llm_failover_enabled
        and spl_governance
        and spl_governance.get("spl_template_status")
        in {"planned", "unavailable", "missing", "unknown", "sop_only"}
    ):
        return _candidate_clarification(
            trace_id=trace_id,
            skill=skill,
            user_query=user_query,
            telemetry=telemetry,
            profile=profile,
            reason=str(spl_governance.get("governed_limitation") or "spl_template_unavailable_no_free_spl_fallback"),
            spl_governance=spl_governance,
        )

    # Catalogue/runtime-map matches already carry deterministic pattern authority.
    # If no governed template rendered and a lab draft family exists for that
    # mapped pattern, prefer the deterministic review-only draft over the slow
    # advisory LLM fallback. This keeps candidate SPL non-executable while
    # avoiding timeout-prone model calls for known Cisco catalogue paraphrases.
    # v2-off: prefer the deterministic catalogue/live-data lab draft over the slow
    # advisory LLM (latency optimization for known paraphrases). v2-on: dispatch
    # owns the schedule — when it scheduled the spl_plan_compiler hop, honor it by
    # falling through to _candidate_from_llm_fallback (which still degrades to the
    # lab draft internally if the LLM produces nothing), so the contract, persisted
    # plan, and LLM telemetry stay consistent with the dispatch decision.
    if mapped_pattern_type and not template_id and not _dispatch_v2_on:
        lab_draft_candidate = _candidate_from_lab_draft(
            trace_id=trace_id,
            skill=skill,
            user_query=user_query,
            telemetry=telemetry,
            profile=profile,
            spl_governance=spl_governance,
            pattern_type=mapped_pattern_type,
            use_case_id=use_case_id,
            llm_fallback_reason="deterministic_draft_preferred_for_catalog_pattern",
            llm_intent_advisory=llm_intent_advisory,
        )
        if lab_draft_candidate is not None:
            return lab_draft_candidate

    signals = query_signals if isinstance(query_signals, dict) else {}
    if signals.get("live_data_request") and not _dispatch_v2_on:
        from app.spl.draft_preview import has_strong_detection_family_match

        if has_strong_detection_family_match(user_query):
            live_data_draft = _candidate_from_lab_draft(
                trace_id=trace_id,
                skill=skill,
                user_query=user_query,
                telemetry=telemetry,
                profile=profile,
                spl_governance=spl_governance,
                pattern_type=mapped_pattern_type,
                use_case_id=use_case_id,
                live_data_request=True,
                llm_fallback_reason="deterministic_draft_preferred_for_live_data_family",
                llm_intent_advisory=llm_intent_advisory,
            )
            if live_data_draft is not None:
                return live_data_draft

    fallback_candidate = _candidate_from_llm_fallback(
        trace_id=trace_id,
        skill=skill,
        user_query=user_query,
        telemetry=telemetry,
        profile=profile,
        spl_governance=spl_governance,
        request_enabled=llm_failover_enabled,
        llm_turn_budget=llm_turn_budget,
        llm_context={
            "primary_skill": skill,
            "use_case_id": use_case_id,
            "pattern_type": (spl_governance or {}).get("pattern_type") or mapped_pattern_type,
            "required_sources": (spl_governance or {}).get("required_sources"),
            # Phase 4A: 2C advisory threaded into the plan compiler (input
            # preservation). The grounding block extracts entity_slots_candidate.
            # slot_handoff wired from canonical state in a later pass; the Phase 5
            # pre-SPL MCP discovery context is threaded here when present.
            "slot_handoff": slot_handoff,
            "mcp_discovery_context": mcp_discovery_context,
            "llm_intent_advisory": (
                llm_intent_advisory.model_dump()
                if isinstance(llm_intent_advisory, LLMIntentAdvisory)
                else llm_intent_advisory
            ),
            # R1: when keyword routing is ambiguous (>1 family matches), give the
            # LLM the candidate family list so it disambiguates rather than the
            # deterministic first-match silently winning.
            "candidate_families": (
                _ambiguous_families(user_query) if llm_failover_enabled else None
            ),
            # WS-F: governed deterministic grounding (detection families + MITRE/ATLAS
            # + AI-threat refs) so the T2 LLM SPL is anchored to in-repo references,
            # never invented. Advisory context only; the producer still validates output.
            "t2_grounding": (
                _build_t2_grounding_block(user_query) if llm_failover_enabled else None
            ),
        },
    )
    if fallback_candidate is not None:
        return fallback_candidate

    if True or settings.ai_soc_spl_template_governance_enabled:
        block_reason = _spl_governance_block_reason(template_id, template, spl_governance)
        if block_reason is None and spl_governance and not spl_governance.get("runtime_spl_governance_allowed", True):
            block_reason = str(
                spl_governance.get("governed_limitation") or "runtime_spl_governance_not_allowed"
            )
        if block_reason is None and settings.ai_soc_spl_template_governance_enabled:
            block_reason = "spl_template_missing" if not template_id else "spl_template_governance_blocked"
        return _candidate_clarification(
            trace_id=trace_id,
            skill=skill,
            user_query=user_query,
            telemetry=telemetry,
            profile=profile,
            reason=block_reason or "llm_spl_fallback_disabled",
            spl_governance=spl_governance,
        )

    candidate, provider_metadata = generate_candidate_spl_with_provider(trace_id=trace_id, skill=skill, user_query=user_query, profile=profile)
    candidate_payload = candidate.model_dump()
    candidate_payload.update(provider_metadata)
    telemetry.record_step(
        trace_id,
        "candidate_spl_generated",
        "completed",
        skill=skill,
        generation_mode=candidate.generation_mode,
        confidence=candidate.confidence,
        warnings=candidate.warnings,
        selected_candidate_spl_provider=provider_metadata["selected_candidate_spl_provider"],
        fallback_required=provider_metadata["fallback_required"],
    )

    validation = validate_spl(candidate.candidate_spl)
    explanation = explain_spl(candidate.candidate_spl, profile=profile)
    final_spl, validation, optimization = merge_post_validation_optimization(
        candidate.candidate_spl,
        validation,
        profile=profile,
        user_query=user_query,
    )
    candidate = replace(candidate, candidate_spl=final_spl)
    candidate_payload = candidate.model_dump()
    candidate_payload.update(provider_metadata)
    guidance = splunk_guidance(user_query, profile=profile)
    validation_payload = {
        "approved": validation["approved"],
        "normalized_spl": validation["normalized_spl"],
        "reject_reasons": validation["reject_reasons"],
        "warnings": validation["warnings"],
        "enforced_limits": validation["enforced_limits"],
        "policy_version": validation["policy_version"],
        "selected_candidate_spl_provider": provider_metadata["selected_candidate_spl_provider"],
        "candidate_provider_reason": provider_metadata["reason"],
        "saia_available": provider_metadata["saia_available"],
        "fallback_required": provider_metadata["fallback_required"],
        "spl_explanation_provider": explanation["provider"],
        "spl_optimization_provider": optimization["provider"],
        "spl_guidance_provider": guidance["provider"],
        "optimization_applied": optimization["optimization_applied"],
        "optimization_revalidation_status": optimization["revalidation_status"],
        "optimization_revalidation_approved": optimization["revalidation_approved"],
        "spl_optimization_steps": optimization.get("simplification_steps") or [],
        "spl_optimization_rejected": bool(optimization.get("simplification_rejected")),
        "spl_optimization_reject_reason": optimization.get("simplification_reject_reason"),
        "capability_profile": profile.model_dump(),
    }
    _merge_spl_governance(candidate_payload, validation_payload, spl_governance)
    _mark_spl_review_status(candidate_payload, validation_payload)
    if slot_binding_enabled:
        validation_payload = validate_spl_slot_bindings(
            validation_payload,
            user_query=user_query,
            query_signals=query_signals,
            template_id=template_id,
        )
        _mark_spl_review_status(candidate_payload, validation_payload)
    telemetry.record_spl_validation(
        trace_id,
        stage="spl_validation_result",
        approved=validation_payload["approved"],
        reject_reasons=validation_payload["reject_reasons"],
        warnings=validation_payload["warnings"],
        policy_version=validation_payload["policy_version"],
        optimization_steps=validation_payload.get("spl_optimization_steps"),
        optimization_rejected=validation_payload.get("spl_optimization_rejected"),
        optimization_reject_reason=validation_payload.get("spl_optimization_reject_reason"),
    )
    return candidate_payload, validation_payload


def _candidate_from_default_template(
    *,
    trace_id: str,
    skill: str,
    user_query: str,
    template_id: str | None,
    spl_governance: dict[str, Any] | None = None,
    telemetry: Any | None = None,
    profile: Any | None = None,
    extra_slots: dict[str, Any] | None = None,
    slot_source: str = "user",
    user_constraint_bindings: UserConstraintBindings | None = None,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    template = get_spl_template(template_id)
    if template is None or template.query_shape != QUERY_SHAPE_RAW_SEARCH or not template.spl_text:
        return None
    if template.status != "active":
        return None

    from app.spl.template_query_bindings import (
        customize_template_spl,
        validate_template_slots_for_render,
    )

    slot_outcome = validate_template_slots_for_render(
        template.template_id,
        user_query,
        extra_slots=extra_slots,
        slot_source=slot_source,
        user_constraint_bindings=user_constraint_bindings,
    )
    if not slot_outcome.valid:
        if telemetry is not None and profile is not None:
            clarification = _candidate_clarification(
                trace_id=trace_id,
                skill=skill,
                user_query=user_query,
                telemetry=telemetry,
                profile=profile,
                reason="slot_validation_failed",
                spl_governance=spl_governance,
            )
        else:
            clarification = _slot_validation_clarification(
                trace_id=trace_id,
                skill=skill,
                user_query=user_query,
                spl_governance=spl_governance,
            )
        candidate_payload, validation_payload = clarification
        validation_payload["reject_reasons"] = sorted(
            set(list(validation_payload.get("reject_reasons") or []) + slot_outcome.reject_reasons)
        )
        candidate_payload["candidate_spl"] = ""
        candidate_payload["generation_mode"] = "clarification_required"
        candidate_payload["warnings"] = sorted(
            set(list(candidate_payload.get("warnings") or []) + ["spl_slot_validation_failed"])
        )
        validation_payload["requires_mcp_identity_rbac_check"] = True
        validation_payload["mcp_execution_enabled"] = False
        candidate_payload["requires_mcp_identity_rbac_check"] = True
        candidate_payload["mcp_execution_enabled"] = False
        return candidate_payload, validation_payload

    from app.spl.spl_generation_safety import apply_spl_generation_safety

    bindings = user_constraint_bindings or _spl_user_constraint_bindings(
        user_query,
        template_id=template.template_id,
    )
    compatibility = check_template_compatibility(template.template_id, bindings, template=template)
    force_skeleton = compatibility.use_user_bound_skeleton
    if (
        force_skeleton
        and bool(getattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", False))
        and bool(getattr(settings, "ai_soc_llm_spl_fallback_enabled", False))
    ):
        llm_candidate = _candidate_from_llm_fallback(
            trace_id=trace_id,
            skill=skill,
            user_query=user_query,
            telemetry=telemetry,
            profile=profile,
            spl_governance=spl_governance,
            request_enabled=True,
            llm_context={
                "primary_skill": skill,
                "use_case_id": template_id,
                "pattern_type": (spl_governance or {}).get("pattern_type"),
                "template_incompatible_reasons": list(compatibility.incompatible_reasons or []),
                "slot_handoff": bindings.to_dict() if bindings is not None else None,
            },
        )
        if llm_candidate is not None:
            return llm_candidate
    rendered_spl, binding_trace = customize_template_spl_with_trace(
        template.template_id,
        template.spl_text,
        user_query,
        normalized_slots=slot_outcome.normalized_slots,
        user_constraint_bindings=bindings,
        force_user_skeleton=force_skeleton,
    )
    binding_trace["template_compatibility"] = compatibility.to_dict()
    # Env-Knowledge <stem> resolution happens once at template load
    # (load_spl_templates), so template.spl_text is already deployment-bound here.
    validation = validate_spl(rendered_spl, template_profile=template.validation_rules)
    profile = build_splunk_capability_profile(required_saia_tool="saia_generate_spl")
    final_spl, validation, optimization = merge_post_validation_optimization(
        rendered_spl,
        validation,
        profile=profile,
        user_query=user_query,
        template_profile=template.validation_rules,
    )
    postprocessor_trace: dict[str, Any] = {}
    if _defer_spl_postprocessor_inline():
        pass
    else:
        postprocessed = finalize_review_only_spl(
            final_spl,
            query=user_query,
            family="governed_template",
            slot_handoff=bindings.to_dict(),
            llm_generated=False,
        )
        postprocessor_trace = postprocessed.trace
        final_spl = postprocessed.normalized_spl
    candidate_payload = {
        "trace_id": trace_id,
        "skill": skill,
        "user_query": user_query,
        "candidate_spl": final_spl,
        "generation_mode": (
            "deterministic_user_bound_skeleton"
            if binding_trace.get("used_user_bound_skeleton")
            else "deterministic_template_render"
        ),
        "confidence": 0.93,
        "assumptions": [
            f"Governed raw-search SPL template selected from use-case catalog: {template.template_id}.",
            "Template output remains candidate SPL and requires validation/gated execution.",
        ],
        "warnings": [] if validation.get("approved") else ["template_spl_validation_failed"],
        "template_id": template.template_id,
        "user_constraint_bindings": bindings.to_dict(),
        "spl_binding_trace": binding_trace,
        "slot_constraint_projection": projection_from_bindings(
            bindings,
            built_at_stage="spl_generation",
        ).to_dict(),
        "postprocessor_applied": bool(postprocessor_trace.get("postprocessor_applied")),
        "review_only_spl_postprocessor_trace": postprocessor_trace,
    }
    validation_payload = {
        "approved": validation["approved"],
        "normalized_spl": validation["normalized_spl"],
        "reject_reasons": validation["reject_reasons"],
        "warnings": validation["warnings"],
        "enforced_limits": validation["enforced_limits"],
        "policy_version": validation["policy_version"],
        "selected_candidate_spl_provider": (
            "deterministic_user_bound_skeleton"
            if binding_trace.get("used_user_bound_skeleton")
            else "deterministic_template_render"
        ),
        "candidate_provider_reason": "use_case_catalog_default_raw_template",
        "saia_available": False,
        "fallback_required": False,
        "spl_explanation_provider": "rule_based",
        "spl_optimization_provider": optimization["provider"],
        "spl_guidance_provider": "scd_rag",
        "optimization_applied": optimization["optimization_applied"],
        "optimization_revalidation_status": optimization["revalidation_status"],
        "optimization_revalidation_approved": optimization["revalidation_approved"],
        "spl_optimization_steps": optimization.get("simplification_steps") or [],
        "spl_optimization_rejected": bool(optimization.get("simplification_rejected")),
        "spl_optimization_reject_reason": optimization.get("simplification_reject_reason"),
        "capability_profile": profile.model_dump(),
        "template_id": template.template_id,
        "review_only_spl_postprocessor_trace": postprocessor_trace,
    }
    _merge_spl_governance(
        candidate_payload,
        validation_payload,
        spl_governance or _template_spl_governance(template.template_id, template.status, template.is_production_executable()),
    )
    apply_spl_generation_safety(candidate_payload, validation_payload, spl=final_spl)
    _mark_spl_review_status(candidate_payload, validation_payload)
    return candidate_payload, validation_payload


def _slot_validation_clarification(
    *,
    trace_id: str,
    skill: str,
    user_query: str,
    spl_governance: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    profile = build_splunk_capability_profile(required_saia_tool="saia_generate_spl")
    validation = validate_spl("")
    reject_reasons = list(validation.get("reject_reasons") or [])
    if "slot_validation_failed" not in reject_reasons:
        reject_reasons.append("slot_validation_failed")
    candidate_payload = {
        "trace_id": trace_id,
        "skill": skill,
        "user_query": user_query,
        "candidate_spl": "",
        "generation_mode": "clarification_required",
        "confidence": 0.0,
        "assumptions": [
            "Template slot validation failed before SPL rendering.",
            "No candidate SPL was generated; analyst clarification is required.",
        ],
        "warnings": ["spl_slot_validation_failed"],
        "selected_candidate_spl_provider": "none",
        "fallback_required": True,
        "candidate_spl_generated": False,
        "validation_required": False,
        "execution_eligible": False,
        "capability_profile": profile.model_dump(),
        "template_id": None,
    }
    validation_payload = {
        "approved": False,
        "normalized_spl": None,
        "reject_reasons": reject_reasons,
        "warnings": list(validation.get("warnings") or []),
        "enforced_limits": validation.get("enforced_limits"),
        "policy_version": validation.get("policy_version"),
        "selected_candidate_spl_provider": "none",
        "candidate_provider_reason": "slot_validation_failed",
        "saia_available": False,
        "fallback_required": True,
        "spl_explanation_provider": "rule_based",
        "spl_optimization_provider": "rule_based",
        "spl_guidance_provider": "scd_rag",
        "optimization_applied": False,
        "optimization_revalidation_status": None,
        "optimization_revalidation_approved": False,
        "capability_profile": profile.model_dump(),
        "template_id": None,
    }
    _merge_spl_governance(candidate_payload, validation_payload, spl_governance)
    _mark_spl_review_status(candidate_payload, validation_payload, reason="slot_validation_failed")
    return candidate_payload, validation_payload


def _candidate_clarification(
    *,
    trace_id: str,
    skill: str,
    user_query: str,
    telemetry: Any,
    profile: Any,
    reason: str,
    spl_governance: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    validation = validate_spl("")
    reject_reasons = list(validation.get("reject_reasons") or [])
    if reason not in reject_reasons:
        reject_reasons.append(reason)
    candidate_payload = {
        "trace_id": trace_id,
        "skill": skill,
        "user_query": user_query,
        "candidate_spl": "",
        "generation_mode": "clarification_required",
        "confidence": 0.0,
        "assumptions": [
            _spl_clarification_user_message(
                {"review_required_reason": reason, "reject_reasons": [reason]}
            ),
            "No candidate SPL was generated; analyst clarification is required.",
        ],
        "warnings": ["spl_generation_requires_clarification"],
        "selected_candidate_spl_provider": "none",
        "fallback_required": True,
        "candidate_spl_generated": False,
        "validation_required": False,
        "execution_eligible": False,
        "capability_profile": profile.model_dump(),
        "template_id": None,
        "llm_supported": False,
        "llm_fallback_used": False,
        "llm_fallback_status": "clarification_required",
        "llm_fallback_reason": reason,
    }
    validation_payload = {
        "approved": False,
        "normalized_spl": None,
        "reject_reasons": reject_reasons,
        "warnings": list(validation.get("warnings") or []),
        "enforced_limits": validation.get("enforced_limits"),
        "policy_version": validation.get("policy_version"),
        "selected_candidate_spl_provider": "none",
        "candidate_provider_reason": reason,
        "saia_available": False,
        "fallback_required": True,
        "spl_explanation_provider": "rule_based",
        "spl_optimization_provider": "rule_based",
        "spl_guidance_provider": "scd_rag",
        "optimization_applied": False,
        "optimization_revalidation_status": None,
        "optimization_revalidation_approved": False,
        "capability_profile": profile.model_dump(),
        "template_id": None,
        "llm_supported": False,
        "llm_fallback_used": False,
        "llm_fallback_status": "clarification_required",
        "llm_fallback_reason": reason,
    }
    _merge_spl_governance(candidate_payload, validation_payload, spl_governance)
    _mark_spl_review_status(candidate_payload, validation_payload, reason=reason)
    telemetry.record_step(
        trace_id,
        "candidate_spl_generated",
        "completed",
        skill=skill,
        generation_mode=candidate_payload["generation_mode"],
        confidence=0.0,
        warnings=candidate_payload["warnings"],
        selected_candidate_spl_provider="none",
        fallback_required=True,
    )
    telemetry.record_spl_validation(
        trace_id,
        stage="spl_validation_result",
        approved=False,
        reject_reasons=reject_reasons,
        warnings=validation_payload["warnings"],
        policy_version=validation_payload["policy_version"],
    )
    return candidate_payload, validation_payload


def _gate_llm_spl_relevance(result: Any, user_query: str) -> Any:
    """Run the structural relevance gate on an LLM fallback result.

    An empty candidate (clarification/blocked/timeout) is not relevant; otherwise
    the SPL is structurally checked against the question's data source, metric, and
    entity. Returns the RelevanceResult."""
    spl = (getattr(result, "candidate_spl", "") or "").strip()
    return check_spl_relevance(user_query, spl or None)


def _ambiguous_families(user_query: str) -> list[str] | None:
    """Return the candidate family list only when routing is ambiguous (>1 match).

    Used as LLM disambiguation context (R1); None when routing is unambiguous so
    the prompt is not cluttered for the common single-match case."""
    families = candidate_detection_families(user_query)
    return families if len(families) > 1 else None


def _build_t2_grounding_block(user_query: str) -> str | None:
    """WS-F governed grounding for the T2 LLM SPL producer (advisory, never authority).

    Anchors the out-of-catalogue prompt to in-repo detection families + MITRE/ATLAS
    references so the LLM SPL is grounded, not invented. Best-effort: never breaks the
    SPL path."""
    try:
        from app.chat.grounding_assembler import assemble_grounding

        block = assemble_grounding(
            user_query,
            detection_families=candidate_detection_families(user_query, limit=4),
        )
        text = block.to_prompt_block()
        return text or None
    except Exception:
        return None


def _should_use_llm_spl_failover(
    skill: str,
    *,
    dispatch_flags: dict[str, bool] | None = None,
) -> bool:
    """LLM-primary failover when dispatch authorizes ``spl_plan_compiler`` (REV5-A).

    With dispatch v2 on, ``call_spl_llm`` from projected flags is required (fail
    closed when flags absent). Flag-off keeps legacy global-flag + skill gate.
    """
    if dispatch_flags is not None:
        return bool(dispatch_flags.get("call_spl_llm"))
    if bool(getattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", False)):
        return False
    if not settings.ai_soc_llm_spl_fallback_enabled:
        return False
    return skill in {"attack_discovery", "spl_generation"}


def _guided_investigation_spl_rescue_eligible(user_query: str) -> bool:
    """True when an out-of-registry guided turn still needs a review-only SPL draft.

    Guided investigation is review-only guidance by default, but explicit SPL-native
    asks (index-bound T2 profiles or SPL artifact phrasing) must still produce the
    deterministic draft instead of prose-only baselining/hunt guidance.
    """
    if detect_spl_artifact_request(user_query):
        return True
    return _t2_runtime_profile_for_query(user_query) is not None


def _t2_runtime_profile_for_query(user_query: str) -> Any | None:
    """Return the runtime source profile (scada_perf/cisco_asa) for the query."""
    from app.spl.runtime_source_profiles import resolve_runtime_profile_for_query

    return resolve_runtime_profile_for_query(user_query)


def _candidate_from_t2_spl_native(
    *,
    trace_id: str,
    skill: str,
    user_query: str,
    telemetry: Any,
    profile: Any,
    spl_governance: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """T1 SPL-native review-only candidate for runtime-source-profile queries.

    Deterministic pre-parse -> T2 shape -> repair -> review-only SPL.  The draft
    is always non-executable (approved=False, normalized_spl=None,
    execution_eligible=False).  Returns None when no runtime profile resolves so
    the existing degrade chain (lab draft / LLM fallback / clarification) runs.
    """
    runtime_profile = _t2_runtime_profile_for_query(user_query)
    if runtime_profile is None:
        return None

    artifact = generate_review_only_spl(user_query)
    slot_projection = build_slot_constraint_projection(
        user_query,
        built_at_stage="spl_generation",
    )

    # Unsafe candidate -> hard block, no renderable SPL.
    if artifact.blocked:
        candidate_payload, validation_payload = _candidate_clarification(
            trace_id=trace_id,
            skill=skill,
            user_query=user_query,
            telemetry=telemetry,
            profile=profile,
            reason="t2_unsafe_spl_blocked",
            spl_governance=spl_governance,
        )
        validation_payload["reject_reasons"] = sorted(
            set(list(validation_payload.get("reject_reasons") or []) + list(artifact.block_reasons))
        )
        return candidate_payload, validation_payload

    # No usable canonical SPL (operation unknown / unresolved fields) -> defer.
    if not artifact.renderable or not artifact.candidate_spl.strip():
        return None

    # Deferral 3: when dispatch v2 is on, author the SCADA/Cisco draft as
    # tenant-portable TOKEN SPL (placeholders + coalesce + analyst-guiding
    # fallback) instead of a hardcoded shape. It stays review-only (placeholders
    # are not allowlisted) and resolves per-environment through
    # graph_node_spl_source_resolve (query -> COE env KB -> MCP -> placeholder).
    # Flag-off keeps the existing shape draft byte-identical (cisco-50 eval).
    if bool(getattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", False)):
        from app.spl.tenant_token_spl import token_spl_for_validator_profile

        token_spl = token_spl_for_validator_profile(
            getattr(runtime_profile, "validator_profile", None)
        )
        if token_spl:
            artifact.candidate_spl = token_spl

    # Wire the runtime source profile into the validator so a known index
    # (scada_perf/cisco_asa) is not falsely rejected.  ``_profile_tuple`` only
    # honours list values, so these MUST be lists.
    template_profile: dict[str, Any] = {
        "allowed_indexes": list(runtime_profile.allowed_indexes),
        "allowed_commands": [
            "search", "fields", "eval", "bin", "stats", "eventstats", "streamstats",
            "where", "table", "sort", "rename", "dedup", "lookup", "coalesce", "head",
        ],
    }
    lookup_name = artifact.shape.get("lookup_name")
    if lookup_name:
        template_profile["allowed_lookups"] = [str(lookup_name)]
    validation = validate_spl(artifact.candidate_spl, template_profile=template_profile)

    # Review-only notes: deterministic shape/repair notes + honest validator
    # findings the analyst must resolve before any future execution path.
    validation_notes = list(artifact.validation_notes)
    for reason in validation.get("reject_reasons") or []:
        note = f"Validator (review): {reason}"
        if note not in validation_notes:
            validation_notes.append(note)

    shape = artifact.shape
    t2_block = {
        "runtime_operation": artifact.runtime_operation,
        "source_profile": artifact.source_profile,
        "entity_fields": list(shape.get("entity_fields") or []),
        "metric_fields": list(shape.get("metric_fields") or []),
        "baseline_window": shape.get("baseline_window"),
        "detection_window": shape.get("detection_window"),
        "lookup_name": shape.get("lookup_name"),
        "lookup_match_field": shape.get("lookup_match_field"),
        "log_match_field": shape.get("log_match_field"),
        "spl_candidate": artifact.candidate_spl,
        "validation_notes": validation_notes,
        "repairs": list(artifact.repairs),
        "execution_eligible": False,
        "review_required": True,
    }
    final_spl = artifact.candidate_spl
    postprocessor_trace: dict[str, Any] = {}
    if bool(getattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", False)) and not _defer_spl_postprocessor_inline():
        postprocessed = finalize_review_only_spl(
            artifact.candidate_spl,
            query=user_query,
            family=str(artifact.runtime_operation or "t2_spl_native"),
            llm_generated=False,
        )
        final_spl = postprocessed.normalized_spl
        postprocessor_trace = dict(postprocessed.trace)

    review_labels = {
        "governed": False,
        "catalog_approved": False,
        "execution_enabled": False,
        "execution_eligible": False,
        "review_required": True,
    }
    candidate_payload = {
        "trace_id": trace_id,
        "skill": skill,
        "user_query": user_query,
        "candidate_spl": final_spl,
        "generation_mode": "t2_spl_native_review",
        "confidence": 0.6,
        "assumptions": [
            *validation_notes,
            "T1 SPL-native review-only draft — not governed, not executed.",
            "Requires analyst validation before any MCP execution path.",
        ],
        "warnings": ["t2_spl_native_review_only"],
        "selected_candidate_spl_provider": "t2_spl_native",
        "fallback_required": False,
        "candidate_spl_generated": True,
        "validation_required": True,
        "capability_profile": profile.model_dump(),
        "template_id": None,
        "llm_supported": False,
        "llm_fallback_used": False,
        "llm_fallback_status": "t2_spl_native_review",
        "llm_fallback_reason": "t1_spl_native_runtime_profile",
        "exposure_tier": "review_candidate",
        "detection_family": None,
        "review_only_renderable": True,
        "t2_spl_native": t2_block,
        "slot_constraint_projection": slot_projection.to_dict(),
        **review_labels,
    }
    if postprocessor_trace:
        candidate_payload["postprocessor_applied"] = bool(
            postprocessor_trace.get("postprocessor_applied")
        )
        candidate_payload["review_only_spl_postprocessor_trace"] = postprocessor_trace
    t2_block["slot_constraint_projection"] = slot_projection.to_dict()
    validation_payload = {
        # Fail-closed: the analyst sees the draft, but approved/normalized_spl stay
        # false/null so the MCP execution gate can never run it.
        "approved": False,
        "normalized_spl": None,
        "reject_reasons": list(validation.get("reject_reasons") or []),
        "warnings": list(validation.get("warnings") or []),
        "enforced_limits": validation.get("enforced_limits") or {},
        "policy_version": validation.get("policy_version"),
        "selected_candidate_spl_provider": "t2_spl_native",
        "candidate_provider_reason": "t1_spl_native_runtime_profile",
        "saia_available": False,
        "fallback_required": False,
        "spl_explanation_provider": "rule_based",
        "spl_optimization_provider": "rule_based",
        "spl_guidance_provider": "scd_rag",
        "optimization_applied": False,
        "optimization_revalidation_status": None,
        "optimization_revalidation_approved": False,
        "capability_profile": profile.model_dump(),
        "template_id": None,
        "validation_notes": validation_notes,
        "t2_spl_native": t2_block,
        "review_only_spl_postprocessor_trace": postprocessor_trace,
        **review_labels,
    }
    _merge_spl_governance(candidate_payload, validation_payload, spl_governance)
    _mark_spl_review_status(candidate_payload, validation_payload, reason="t2_spl_native_review_only")
    telemetry.record_step(
        trace_id,
        "candidate_spl_generated",
        "completed",
        skill=skill,
        generation_mode=candidate_payload["generation_mode"],
        confidence=candidate_payload["confidence"],
        warnings=candidate_payload["warnings"],
        selected_candidate_spl_provider="t2_spl_native",
        fallback_required=False,
    )
    telemetry.record_spl_validation(
        trace_id,
        stage="spl_validation_result",
        approved=False,
        reject_reasons=validation_payload["reject_reasons"],
        warnings=validation_payload["warnings"],
        policy_version=validation_payload["policy_version"],
    )
    return candidate_payload, validation_payload


def _candidate_from_lab_draft(
    *,
    trace_id: str,
    skill: str,
    user_query: str,
    telemetry: Any,
    profile: Any,
    spl_governance: dict[str, Any] | None,
    pattern_type: str | None,
    use_case_id: str | None,
    llm_fallback_reason: str | None,
    live_data_request: bool = False,
    llm_intent_advisory: LLMIntentAdvisory | dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Deterministic lab-draft last resort for the LLM-failover degrade chain.

    Called only when the LLM advisory produced nothing exposable. Returns a
    review-only lab-tier candidate (placeholder index/sourcetype, approved=false,
    normalized_spl=null, execution disabled) so the analyst still gets an
    on-question draft. The lab-tier guard in graph_node_spl_source_resolve keeps it
    approved=false even if placeholders later resolve. Returns None when no draft
    family matches, preserving the prior clarification path.
    """
    draft = build_draft_preview(
        user_query,
        pattern_type=pattern_type,
        use_case_id=use_case_id,
        live_data_request=live_data_request,
        llm_intent_advisory=llm_intent_advisory,
        query_understanding=None,
    )
    draft_spl = (draft or {}).get("draft_spl")
    if not draft or not isinstance(draft_spl, str) or not draft_spl.strip():
        return None
    family = str(draft.get("detection_family") or "")
    from app.spl.utility_spl_authoring import build_utility_postprocessor_context

    context = build_utility_postprocessor_context(
        user_query,
        llm_generated=False,
        target_log_family=family or None,
        is_universal_spl=family == "universal_timestamp_spl",
    )
    postprocessor_trace: dict[str, Any] = {}
    postprocessor_warnings: list[str] = []
    if _defer_spl_postprocessor_inline():
        final_spl = draft_spl
    else:
        postprocessed = finalize_review_only_spl(
            draft_spl,
            query=user_query,
            family=family or "lab_draft",
            llm_generated=False,
            postprocessor_context=context,
        )
        final_spl = postprocessed.normalized_spl
        postprocessor_trace = dict(postprocessed.trace)
        postprocessor_warnings = list(postprocessed.warnings)

    lab_labels = {
        "governed": False,
        "catalog_approved": bool(draft.get("catalog_approved")),
        "execution_enabled": False,
        "execution_eligible": False,
        "review_required": True,
    }
    candidate_payload = {
        "trace_id": trace_id,
        "skill": skill,
        "user_query": user_query,
        "candidate_spl": final_spl,
        "generation_mode": "deterministic_lab_draft",
        "confidence": 0.5,
        "assumptions": list(draft.get("assumptions") or [])
        + (
            [
                "Deterministic lab SPL draft — not governed, not catalog-approved, not executable.",
            ]
            if draft.get("detection_family") == "universal_timestamp_spl"
            else [
                "Deterministic lab SPL draft — not governed, not catalog-approved, not executable.",
                "Placeholder index/sourcetype require a source profile before validation or execution.",
            ]
        ),
        "warnings": (
            ["review_only_universal_spl"]
            if draft.get("detection_family") == "universal_timestamp_spl"
            else ["lab_draft_requires_source_profile"]
        ),
        "selected_candidate_spl_provider": "deterministic_lab_draft",
        "fallback_required": True,
        "candidate_spl_generated": True,
        "validation_required": True,
        "capability_profile": profile.model_dump(),
        "template_id": None,
        "llm_supported": True,
        "llm_fallback_used": True,
        "llm_fallback_status": "lab_draft_fallback",
        "llm_fallback_reason": llm_fallback_reason,
        "exposure_tier": "lab_candidate",
        "lab_tier_exposure": True,
        "detection_family": draft.get("detection_family"),
        "postprocessor_applied": bool(postprocessor_trace.get("postprocessor_applied")),
        "review_only_spl_postprocessor_trace": postprocessor_trace,
        **lab_labels,
    }
    if postprocessor_warnings:
        candidate_payload["review_only_spl_postprocessor_warnings"] = postprocessor_warnings
    validation_payload = {
        # Fail-closed: the analyst sees the draft, but approved/normalized_spl stay
        # false/null so the MCP execution gate can never run a placeholder draft.
        "approved": False,
        "normalized_spl": None,
        "exposure_tier": "lab_candidate",
        "lab_tier_exposure": True,
        "reject_reasons": (
            ["universal_spl_authoring_review_only"]
            if draft.get("detection_family") == "universal_timestamp_spl"
            else list(draft.get("validator_reject_reasons") or ["lab_draft_source_profile_missing"])
        ),
        "review_required_reason": (
            "universal_spl_authoring_review_only"
            if draft.get("detection_family") == "universal_timestamp_spl"
            else None
        ),
        "warnings": (
            ["review_only_universal_spl"]
            if draft.get("detection_family") == "universal_timestamp_spl"
            else ["lab_draft_requires_source_profile"]
        ),
        "enforced_limits": validate_spl("").get("enforced_limits") or {},
        "policy_version": validate_spl("").get("policy_version"),
        "selected_candidate_spl_provider": "deterministic_lab_draft",
        "candidate_provider_reason": "llm_fallback_degraded_to_lab_draft",
        "saia_available": False,
        "fallback_required": True,
        "spl_explanation_provider": "rule_based",
        "spl_optimization_provider": "rule_based",
        "spl_guidance_provider": "scd_rag",
        "optimization_applied": False,
        "optimization_revalidation_status": None,
        "optimization_revalidation_approved": False,
        "capability_profile": profile.model_dump(),
        "template_id": None,
        "llm_supported": True,
        "llm_fallback_used": True,
        "llm_fallback_status": "lab_draft_fallback",
        "llm_fallback_reason": llm_fallback_reason,
        "review_only_spl_postprocessor_trace": postprocessor_trace,
        **lab_labels,
    }
    if postprocessor_warnings:
        validation_payload["review_only_spl_postprocessor_warnings"] = postprocessor_warnings
    _merge_spl_governance(candidate_payload, validation_payload, spl_governance)
    _mark_spl_review_status(candidate_payload, validation_payload)
    telemetry.record_step(
        trace_id,
        "candidate_spl_generated",
        "completed",
        skill=skill,
        generation_mode=candidate_payload["generation_mode"],
        confidence=candidate_payload["confidence"],
        warnings=candidate_payload["warnings"],
        selected_candidate_spl_provider="deterministic_lab_draft",
        fallback_required=True,
    )
    telemetry.record_spl_validation(
        trace_id,
        stage="spl_validation_result",
        approved=False,
        reject_reasons=validation_payload["reject_reasons"],
        warnings=validation_payload["warnings"],
        policy_version=validation_payload["policy_version"],
    )
    return candidate_payload, validation_payload


def _candidate_from_llm_fallback(
    **kwargs: Any,
) -> "SplCandidateStageResult | None":
    """Typed wrapper (Phase 4B): the LLM SPL fallback returns SplCandidateStageResult.

    The tuple-producing implementation is unchanged; this lifts its
    ``(candidate, validation)`` into the single return contract, pulling
    ``detection_plan`` / ``spl_plan_compiler_telemetry`` off the candidate so the
    workflow node can persist the plan without a tuple/dict smuggle. The result is
    tuple-unpackable, so existing ``candidate, validation = ...`` call sites and
    tests keep working unchanged.
    """
    from app.chat.contracts.spl_candidate import SplCandidateStageResult

    return SplCandidateStageResult.from_value(_candidate_from_llm_fallback_tuple(**kwargs))


def _candidate_from_llm_fallback_tuple(
    *,
    trace_id: str,
    skill: str,
    user_query: str,
    telemetry: Any,
    profile: Any,
    spl_governance: dict[str, Any] | None = None,
    request_enabled: bool = False,
    llm_context: dict[str, Any] | None = None,
    llm_turn_budget: "TurnLlmBudget | None" = None,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Governed LLM SPL advisory used only when no deterministic template matched.

    Returns None when the fallback is disabled, so behaviour is byte-identical to
    the prior Stage 3C stub path. When enabled, the LLM JSON is adapted through
    the role schema (execution eligibility forced false) and the proposed SPL is
    re-validated deterministically; a failed/unsupported result surfaces as a
    clarification (non-approved, non-executable), never an executable query.
    """
    if not request_enabled:
        return None
    # B02: with LLM failover enabled this pre-block is intentionally skipped so the
    # LLM can serve planned/missing template rows; the relevance + deterministic
    # validation gates below keep the output on-question and non-executable. Only
    # pre-block when failover is disabled.
    if (
        not settings.ai_soc_llm_spl_fallback_enabled
        and settings.ai_soc_spl_template_governance_enabled
        and spl_governance
    ):
        status = str(spl_governance.get("spl_template_status") or "unknown")
        allowed_templates = [str(item) for item in spl_governance.get("allowed_spl_templates") or []]
        if status != "active" or allowed_templates:
            return _candidate_clarification(
                trace_id=trace_id,
                skill=skill,
                user_query=user_query,
                telemetry=telemetry,
                profile=profile,
                reason=str(spl_governance.get("governed_limitation") or _spl_status_block_reason(status)),
                spl_governance=spl_governance,
            )
    if not settings.ai_soc_llm_spl_fallback_enabled:
        return None

    from app.query_understanding.soc_investigation_shape import detect_broad_hunt_guidance_request

    if detect_broad_hunt_guidance_request(user_query):
        lab_draft_candidate = _candidate_from_lab_draft(
            trace_id=trace_id,
            skill=skill,
            user_query=user_query,
            telemetry=telemetry,
            profile=profile,
            spl_governance=spl_governance,
            pattern_type=(llm_context or {}).get("pattern_type"),
            use_case_id=(llm_context or {}).get("use_case_id"),
            llm_fallback_reason="broad_hunt_guidance_deterministic_fallback",
            llm_intent_advisory=(llm_context or {}).get("llm_intent_advisory"),
        )
        if lab_draft_candidate is not None:
            return lab_draft_candidate
        return _candidate_clarification(
            trace_id=trace_id,
            skill=skill,
            user_query=user_query,
            telemetry=telemetry,
            profile=profile,
            reason="broad_hunt_guidance_no_llm_spl",
            spl_governance=spl_governance,
        )

    # LLM-primary with a relevance gate: generate, structurally check the SPL
    # answers the question, and regenerate once with the mismatch feedback before
    # accepting. A timeout/unavailable client returns a clarification result (no
    # raw output), which the gate treats as not-relevant and falls through.
    #
    # Plan-plus-compiler is the PRIMARY producer (proven reliable + repeatable on
    # the on-host 8B: 10/10 lab-tier in the seeded eval): the LLM emits a small
    # detection plan and deterministic code compiles SOC-STD-compliant SPL. Free-
    # form generation is the automatic fallback when the plan path yields no usable
    # SPL. Both flow through the same validation / quality / lab-tier gates.
    # Expected provider failures degrade to the deterministic path. Programming
    # errors (TypeError/signature drift, ValueError, etc.) intentionally propagate
    # to the sanitized P0-0 error envelope so they remain visible and diagnosable.
    # Phase 4A: thread the canonical slot handoff + MCP discovery context + 2C
    # advisory into the plan-compiler so the LLM plans against resolved context,
    # not just the raw query.
    _ctx = llm_context or {}
    _plan_t0 = time.monotonic()
    plan_compiler_used = False
    try:
        result = generate_llm_spl_via_plan(
            user_query=user_query,
            slot_handoff=_ctx.get("slot_handoff"),
            mcp_discovery_context=_ctx.get("mcp_discovery_context"),
            llm_intent_advisory=_ctx.get("llm_intent_advisory"),
        )
        plan_compiler_used = result is not None and bool(
            str(getattr(result, "candidate_spl", "") or "").strip()
        )
        if result is None or not str(getattr(result, "candidate_spl", "") or "").strip():
            result = generate_llm_spl_fallback(
                user_query=user_query, context=llm_context, correctness_mode=True
            )
    except LocalChatError as exc:
        try:
            telemetry.record_step(
                trace_id,
                "llm_spl_producer_failed",
                "failed",
                skill=skill,
                exception_type=type(exc).__name__,
            )
        except Exception:  # noqa: BLE001 - telemetry must never break chat
            logger.warning("llm_spl_producer_failed_telemetry_failed", exc_info=True)
        logger.warning(
            "llm_spl_producer_failed exc_type=%s trace_id=%s",
            type(exc).__name__,
            trace_id,
        )
        return None
    if result is None:
        return None
    # Phase 4D: dual telemetry for the spl_plan_compiler hop (previously only the
    # failure step was recorded). record_llm_call surfaces it in the control-plane
    # llm_calls list; budget.record_sidecar surfaces it in the turn budget records.
    if plan_compiler_used:
        _plan_latency_ms = int((time.monotonic() - _plan_t0) * 1000)
        _spl_compiler_telemetry = {
            "role": "spl_plan_compiler",
            "outcome": "completed",
            "latency_ms": _plan_latency_ms,
            "model": getattr(result, "model", None),
            "provider_label": getattr(result, "provider", "llm_spl_advisory"),
        }
        try:
            telemetry.record_llm_call(
                trace_id,
                kind="sidecar",
                role="spl_plan_compiler",
                provider_label=getattr(result, "provider", "llm_spl_advisory"),
                outcome="completed",
                latency_ms=_plan_latency_ms,
                model=getattr(result, "model", None),
            )
        except Exception:  # noqa: BLE001 - telemetry must never break chat
            logger.warning("spl_plan_compiler_telemetry_failed", exc_info=True)
        if llm_turn_budget is not None:
            try:
                llm_turn_budget.record_sidecar(
                    role="spl_plan_compiler",
                    provider_label=getattr(result, "provider", "llm_spl_advisory"),
                    outcome="completed",
                    latency_ms=_plan_latency_ms,
                    model=getattr(result, "model", None),
                )
            except Exception:  # noqa: BLE001 - telemetry must never break chat
                logger.warning("spl_plan_compiler_budget_record_failed", exc_info=True)
    else:
        _spl_compiler_telemetry = {}
    relevance = _gate_llm_spl_relevance(result, user_query)
    # Regenerate-once is OFF by default (ai_soc_llm_spl_failover_retry_enabled) to
    # keep one LLM call per failover turn — on slow on-prem hardware a second call
    # doubles the worst-case latency. The relevance gate still rejects bad SPL; the
    # deterministic draft remains the last resort.
    if (
        settings.ai_soc_llm_spl_failover_retry_enabled
        and not relevance.relevant
        and result.candidate_spl.strip()
    ):
        retry = generate_llm_spl_fallback(
            user_query=user_query,
            context=llm_context,
            correctness_mode=True,
            relevance_feedback=relevance.mismatches,
        )
        if retry is not None:
            retry_relevance = _gate_llm_spl_relevance(retry, user_query)
            # Keep the retry only if it improved relevance.
            if retry_relevance.relevant or not result.candidate_spl.strip():
                result = retry
                relevance = retry_relevance

    validation = result.validation
    approved = bool(result.approved)
    lab_tier = bool(getattr(result, "lab_tier", False))
    # R5 + lab-tier exposure: expose SPL when it is on-question AND either fully
    # execution-validated OR a placeholder-only lab candidate. Lab-tier is shown to
    # the analyst (review-only) but execution stays fail-closed below.
    expose_spl = bool(result.candidate_spl.strip()) and relevance.relevant and (approved or lab_tier)
    # Degrade chain last resort: when the LLM advisory produced nothing exposable
    # (client unavailable, off-question, or quality hard-fail), fall through to the
    # deterministic lab-draft family instead of dead-ending at clarification. The
    # draft is review-only lab-tier (approved=false, normalized_spl=null) so the MCP
    # execution gate still cannot run it.
    if not expose_spl:
        lab_draft_candidate = _candidate_from_lab_draft(
            trace_id=trace_id,
            skill=skill,
            user_query=user_query,
            telemetry=telemetry,
            profile=profile,
            spl_governance=spl_governance,
            pattern_type=(llm_context or {}).get("pattern_type"),
            use_case_id=(llm_context or {}).get("use_case_id"),
            llm_fallback_reason=result.clarification_reason,
            llm_intent_advisory=(llm_context or {}).get("llm_intent_advisory"),
        )
        if lab_draft_candidate is not None:
            return lab_draft_candidate
    reject_reasons = list(validation.get("reject_reasons") or [])
    if not relevance.relevant:
        for mismatch in relevance.mismatches:
            reason = f"relevance_{mismatch}"
            if reason not in reject_reasons:
                reject_reasons.append(reason)
    if result.clarification_reason and result.clarification_reason not in reject_reasons:
        reject_reasons = [*reject_reasons, result.clarification_reason]
    if result.hard_fail_count > 0 and result.quality_findings:
        for finding in result.quality_findings:
            if finding.get("severity") == "hard_fail":
                rule_id = str(finding.get("rule_id") or "quality")
                if rule_id not in reject_reasons:
                    reject_reasons.append(rule_id)

    if not expose_spl:
        # Diagnostic telemetry: preserve why an LLM SPL attempt was not exposed so
        # blocked/rejected drafts are debuggable in /debug. Redacted + best-effort;
        # never breaks the SPL path. The candidate SPL is lab-tier (placeholders, no
        # secrets) but still excerpted defensively.
        try:
            rejected_spl = str(getattr(result, "candidate_spl", "") or "")
            telemetry.record_step(
                trace_id,
                "llm_spl_rejected",
                "completed",
                skill=skill,
                generation_mode=getattr(result, "provider", "llm_spl_advisory"),
                relevant=relevance.relevant,
                quality_status=result.quality_status,
                hard_fail_count=result.hard_fail_count,
                reject_reasons=reject_reasons[:12],
                quality_findings=[
                    {"rule_id": str(f.get("rule_id")), "severity": str(f.get("severity"))}
                    for f in (result.quality_findings or [])
                ][:12],
                adapter_errors=list(result.adapter_errors or [])[:6],
                rejected_spl_excerpt=(rejected_spl[:280] + "…") if len(rejected_spl) > 280 else rejected_spl,
            )
        except Exception:  # noqa: BLE001 - telemetry must never break chat
            logger.warning("llm_spl_rejected_telemetry_failed", exc_info=True)

    # Phase 4C: the LLM SPL candidate must never bypass the review-only
    # postprocessor. Apply hygiene (index placeholders, time bound, command order)
    # to the exposed candidate and stamp the evaluated/applied + hash trace.
    postprocessor_trace_llm: dict[str, Any] = {}
    final_candidate_spl = result.candidate_spl if expose_spl else ""
    _dispatch_v2_on = bool(getattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", False))
    if (
        _dispatch_v2_on
        and expose_spl
        and final_candidate_spl.strip()
        and not _defer_spl_postprocessor_inline()
    ):
        pp = finalize_review_only_spl(
            final_candidate_spl,
            query=user_query,
            family=str(getattr(result, "detection_family", "") or "llm_spl_advisory"),
            slot_handoff=_ctx.get("slot_handoff"),
            llm_generated=True,
            mcp_discovery_context=_ctx.get("mcp_discovery_context"),
        )
        final_candidate_spl = pp.normalized_spl
        postprocessor_trace_llm = pp.trace
    llm_lab_labels = {
        "governed": False,
        "catalog_approved": False,
        "execution_enabled": False,
        "execution_eligible": False,
        "review_required": True,
    }
    candidate_payload = {
        "trace_id": trace_id,
        "skill": skill,
        "user_query": user_query,
        "candidate_spl": final_candidate_spl,
        # Phase 4B: redacted LLM detection plan, carried on the candidate so the
        # workflow node can persist it (persist_llm_spl_plan) for downstream nodes.
        "detection_plan": getattr(result, "detection_plan", None),
        "review_only_spl_postprocessor_trace": postprocessor_trace_llm,
        "review_only_spl_postprocessor_applied": bool(
            postprocessor_trace_llm.get("postprocessor_applied")
        ),
        "spl_plan_compiler_telemetry": _spl_compiler_telemetry,
        "generation_mode": "llm_spl_advisory_fallback",
        "confidence": 0.6 if expose_spl else 0.0,
        "assumptions": [
            *result.assumptions,
            "LLM lab SPL candidate — not governed, not catalog-approved, not executable.",
            "Output requires analyst review before any validation or execution gate.",
        ],
        "warnings": [] if expose_spl else ["llm_spl_fallback_requires_clarification"],
        "selected_candidate_spl_provider": "llm_spl_advisory_fallback",
        "fallback_required": True,
        "candidate_spl_generated": expose_spl,
        "validation_required": True,
        "capability_profile": profile.model_dump(),
        "template_id": None,
        "llm_supported": True,
        "llm_fallback_used": True,
        "llm_fallback_status": "candidate_ready" if expose_spl else "clarification_required",
        "llm_fallback_reason": result.clarification_reason,
        "llm_model": result.model,
        "llm_latency_ms": result.latency_ms,
        "exposure_tier": "lab_candidate" if lab_tier else (
            "execution_validated" if expose_spl else "not_exposed"
        ),
        "lab_tier_exposure": lab_tier,
        "quality_standard": result.quality_standard,
        "quality_status": result.quality_status,
        "quality_findings": list(result.quality_findings),
        **llm_lab_labels,
    }
    validation_payload = {
        # Execution validation is fail-closed for lab-tier: the analyst sees the
        # SPL, but approved/normalized_spl stay false/null so the MCP execution gate
        # (which requires both) can never run a placeholder lab candidate.
        "approved": False if lab_tier else expose_spl,
        "normalized_spl": None if lab_tier else (
            validation.get("normalized_spl") if expose_spl else None
        ),
        "exposure_tier": "lab_candidate" if lab_tier else (
            "execution_validated" if expose_spl else "not_exposed"
        ),
        "lab_tier_exposure": lab_tier,
        "reject_reasons": reject_reasons,
        "warnings": list(validation.get("warnings") or []),
        "enforced_limits": validation.get("enforced_limits"),
        "policy_version": validation.get("policy_version"),
        "selected_candidate_spl_provider": "llm_spl_advisory_fallback",
        "candidate_provider_reason": result.clarification_reason or "template_miss_llm_advisory_fallback",
        "saia_available": False,
        "fallback_required": True,
        "spl_explanation_provider": "rule_based",
        "spl_optimization_provider": "rule_based",
        "spl_guidance_provider": "scd_rag",
        "optimization_applied": False,
        "optimization_revalidation_status": None,
        "optimization_revalidation_approved": False,
        "capability_profile": profile.model_dump(),
        "template_id": None,
        "llm_supported": True,
        "llm_fallback_used": True,
        "llm_fallback_status": "candidate_ready" if expose_spl else "clarification_required",
        "llm_fallback_reason": result.clarification_reason,
        "llm_model": result.model,
        "llm_latency_ms": result.latency_ms,
        "quality_standard": result.quality_standard,
        "quality_status": result.quality_status,
        "quality_findings": list(result.quality_findings),
        "llm_fallback": {
            "provider": result.provider,
            "model": result.model,
            "latency_ms": result.latency_ms,
            "clarification_required": result.clarification_required,
            "clarification_reason": result.clarification_reason,
            "adapter_errors": list(result.adapter_errors),
            "quality_standard": result.quality_standard,
            "quality_status": result.quality_status,
            "quality_findings": list(result.quality_findings),
            "hard_fail_count": result.hard_fail_count,
        },
        **llm_lab_labels,
    }
    _merge_spl_governance(candidate_payload, validation_payload, spl_governance)
    _mark_spl_review_status(candidate_payload, validation_payload)
    telemetry.record_step(
        trace_id,
        "candidate_spl_generated",
        "completed",
        skill=skill,
        generation_mode=candidate_payload["generation_mode"],
        confidence=candidate_payload["confidence"],
        warnings=candidate_payload["warnings"],
        selected_candidate_spl_provider="llm_spl_advisory_fallback",
        fallback_required=True,
    )
    telemetry.record_spl_validation(
        trace_id,
        stage="spl_validation_result",
        # Record the runtime authority, not exposure. Lab-tier candidates are
        # exposed for review but approved=False (fail-closed); telemetry must not
        # say "approved" for SPL the execution gate blocks.
        approved=bool(validation_payload["approved"]),
        reject_reasons=reject_reasons,
        warnings=validation_payload["warnings"],
        policy_version=validation_payload["policy_version"],
    )
    return candidate_payload, validation_payload


def _llm_spl_candidate_stage(
    *,
    skill: str,
    user_query: str,
    request_enabled: bool,
) -> dict[str, Any] | None:
    """Separate lab-only LLM SPL candidate lane.

    This never populates governed candidate_spl or spl_validation. It exists
    only for side-by-side local/demo review when both the server flag and the
    request-level UI toggle are enabled.
    """
    if not request_enabled:
        return None
    if not settings.ai_soc_llm_spl_fallback_enabled:
        return None
    if skill not in {"attack_discovery", "spl_generation"}:
        return None

    result = generate_llm_spl_fallback(user_query=user_query)
    if result is None:
        return None

    validation = result.validation if isinstance(result.validation, dict) else validate_spl("")
    quality_findings = list(result.quality_findings)
    validation_findings = list(validation.get("reject_reasons") or [])
    status = result.status
    validator_status = "passed" if validation.get("approved") else "failed"
    if result.clarification_required and status == "candidate_generated":
        status = "needs_clarification"
    if result.hard_fail_count > 0:
        status = "blocked"
    if result.clarification_reason and result.clarification_reason not in validation_findings:
        validation_findings.append(result.clarification_reason)

    return {
        "llm_spl_candidate": result.candidate_spl if result.approved else "",
        "llm_spl_candidate_status": status,
        "llm_spl_confidence_score": result.confidence_score,
        "llm_spl_confidence_label": result.confidence_label,
        "detection_family": result.detection_family,
        "quality_status": result.quality_status,
        "validator_status": validator_status,
        "quality_findings": quality_findings,
        "validation_findings": validation_findings,
        "assumptions": list(result.assumptions),
        "required_fields": list(result.required_fields),
        "missing_details": list(result.missing_details),
        "clarifying_questions": list(result.clarifying_questions),
        "validation_notes": list(result.validation_notes),
        "soc_std_rules_applied": list(result.soc_std_rules_applied),
        "risk_notes": list(result.risk_notes),
        "execution_eligible": False,
        "governed": False,
        "catalog_approved": False,
        "execution_enabled": False,
        "review_required": True,
        "provider": result.provider,
        "model": result.model,
        "latency_ms": result.latency_ms,
    }


def _template_spl_governance(
    template_id: str | None,
    status: str | None,
    production_executable: bool | None,
) -> dict[str, Any]:
    return {
        "spl_template_status": status or "unavailable",
        "allowed_spl_templates": [template_id] if template_id else [],
        "template_production_executable": bool(production_executable),
        "governed_limitation": None if status == "active" else "spl_template_unavailable_no_free_spl_fallback",
        "evidence_requirements": [],
    }


def _runtime_spl_governance(use_case_id: str | None) -> dict[str, Any] | None:
    if settings.ai_soc_spl_template_governance_enabled:
        runtime_governance = enrichment_spl_governance_for_runtime(use_case_id)
        if runtime_governance is not None:
            return runtime_governance
        legacy_metadata = enrichment_spl_governance(use_case_id)
        if legacy_metadata is None:
            return None
        status = str(legacy_metadata.get("spl_template_status") or "unavailable")
        allowed_templates = [
            str(item) for item in legacy_metadata.get("allowed_spl_templates") or []
        ]
        # Curated-enrichment activation may be off while the catalogue still binds an
        # active governed template (weak-exact rows). Preserve allowed templates and
        # permit review-only template render; block enrichment context load only.
        catalog_template_render_allowed = status == "active" and bool(allowed_templates)
        governed_limitation = legacy_metadata.get("governed_limitation")
        if catalog_template_render_allowed:
            governed_limitation = None
        elif not governed_limitation:
            governed_limitation = _spl_status_block_reason(status)
        return {
            **legacy_metadata,
            "allowed_spl_templates": allowed_templates,
            "governed_limitation": governed_limitation,
            "planner_runtime_activation_allowed": False,
            "governed_enrichment_load_allowed": False,
            "runtime_spl_governance_allowed": catalog_template_render_allowed,
        }
    return enrichment_spl_governance(use_case_id)


def _spl_governance_block_reason(
    template_id: str | None,
    template: Any,
    governance: dict[str, Any] | None,
) -> str | None:
    if not settings.ai_soc_spl_template_governance_enabled or not governance:
        return None

    status = str(governance.get("spl_template_status") or "unknown")
    allowed_templates = {str(item) for item in governance.get("allowed_spl_templates") or []}
    if status == "active":
        if not governance.get("runtime_spl_governance_allowed", True):
            return str(governance.get("governed_limitation") or "runtime_spl_governance_not_allowed")
        if allowed_templates and not template_id:
            return "spl_template_missing"
        if template_id and allowed_templates and template_id not in allowed_templates:
            return "spl_template_not_allowed_by_enrichment"
        if template_id and template is None:
            return "spl_template_missing"
        if template_id and template is not None and getattr(template, "status", None) != "active":
            return "spl_template_not_active"
        if template_id and template is not None and not template.is_production_executable():
            return "spl_template_not_production_executable"
        return None
    if status == "sop_only":
        return "spl_template_sop_only_no_active_investigation_support"
    if status == "planned":
        return "spl_template_planned_no_free_spl_fallback"
    if status in {"unavailable", "missing", "unknown"}:
        return "spl_template_unavailable_no_free_spl_fallback"
    return "spl_template_unknown_no_free_spl_fallback"


def _spl_status_block_reason(status: str) -> str:
    if status == "sop_only":
        return "spl_template_sop_only_no_active_investigation_support"
    if status == "planned":
        return "spl_template_planned_no_free_spl_fallback"
    return "spl_template_unavailable_no_free_spl_fallback"


def _merge_spl_governance(
    candidate_payload: dict[str, Any],
    validation_payload: dict[str, Any],
    governance: dict[str, Any] | None,
) -> None:
    if not governance:
        return
    template_status = str(governance.get("spl_template_status") or "unavailable")
    allowed_templates = [str(item) for item in governance.get("allowed_spl_templates") or []]
    evidence_requirements = [str(item) for item in governance.get("evidence_requirements") or []]
    governed_limitation = governance.get("governed_limitation")
    production_executable = template_status == "active" and bool(allowed_templates)
    template_id = candidate_payload.get("template_id") or validation_payload.get("template_id")
    allowed_by_enrichment = bool(
        template_status == "active"
        and (
            not template_id
            or not allowed_templates
            or str(template_id) in set(allowed_templates)
        )
    )
    fields = {
        "spl_template_status": template_status,
        "allowed_spl_templates": allowed_templates,
        "allowed_by_enrichment": allowed_by_enrichment,
        "enrichment_evidence_requirements": evidence_requirements,
        "governed_limitation": str(governed_limitation) if governed_limitation else None,
        "template_production_executable": production_executable,
        "execution_enabled": False,
    }
    candidate_payload.update(fields)
    validation_payload.update(fields)
    if governed_limitation:
        warnings = list(validation_payload.get("warnings") or [])
        if str(governed_limitation) not in warnings:
            warnings.append(str(governed_limitation))
        validation_payload["warnings"] = warnings


def _mark_spl_review_status(
    candidate_payload: dict[str, Any],
    validation_payload: dict[str, Any],
    *,
    reason: str | None = None,
) -> None:
    approved = bool(validation_payload.get("approved"))
    if reason is None and not approved:
        reason = resolve_spl_revision_hil_reason(
            validation_payload,
            candidate_spl=candidate_payload,
        )
    if reason is None:
        reason = "candidate_spl_review_only"
    fields = {
        "validator_status": "approved" if approved else "blocked",
        "execution_enabled": False,
        "review_required": True,
        "review_required_reason": reason,
        "execution_eligible": False,
    }
    candidate_payload.update(fields)
    validation_payload.update(fields)


def _attach_spl_governance(
    spl_template: dict[str, object] | None,
    governance: dict[str, Any] | None,
) -> dict[str, object] | None:
    if spl_template is None and governance is None:
        return None
    payload: dict[str, object] = dict(spl_template or {})
    if governance:
        payload.update(
            {
                "spl_template_status": governance.get("spl_template_status"),
                "allowed_spl_templates": list(governance.get("allowed_spl_templates") or []),
                "enrichment_evidence_requirements": list(governance.get("evidence_requirements") or []),
                "governed_limitation": governance.get("governed_limitation"),
                "template_production_executable": (
                    governance.get("spl_template_status") == "active"
                    and bool(governance.get("allowed_spl_templates"))
                ),
            }
        )
    return payload


def _chat_message(
    spl_validation: dict | None,
    execution: dict | None = None,
    analyst_summary: str | None = None,
    evidence_plan: dict[str, Any] | None = None,
    planning_decision: dict[str, Any] | None = None,
    soc_kb_retrieval: dict[str, Any] | None = None,
    user_query: str | None = None,
    entities: dict[str, Any] | None = None,
    match_path: str | None = None,
    intent_classification: dict[str, Any] | None = None,
    spl_draft_preview: dict[str, Any] | None = None,
    llm_intent_advisory: LLMIntentAdvisory | dict[str, Any] | None = None,
) -> str:
    from app.chat.guidance_templates import (
        build_conceptual_mitre_guidance,
        build_investigation_triage_guidance,
        build_guided_investigation_guidance,
        build_mitre_evidence_threshold_guidance,
        build_policy_escalation_guidance,
        build_spl_execution_refusal_guidance,
        build_unsafe_action_guidance,
        is_policy_escalation_guidance_query,
        is_conceptual_mitre_confirm_query,
        is_explicit_run_spl_query,
        is_mitre_evidence_threshold_query,
        is_unsafe_blocked_path,
    )

    path_type = planning_decision.get("path_type") if isinstance(planning_decision, dict) else None
    resource_plan = None
    if isinstance(evidence_plan, dict):
        candidate_plan = evidence_plan.get("resource_plan")
        if isinstance(candidate_plan, dict):
            resource_plan = candidate_plan
    intent_family = ""
    primary_intent = ""
    if isinstance(intent_classification, dict):
        intent_family = str(intent_classification.get("intent_family") or "")
        primary_intent = str(intent_classification.get("primary_intent") or "")
    if primary_intent == "cross_skill_investigation" and user_query:
        from app.synthesis.deterministic_prose_stitch import build_cross_skill_investigation_message

        return build_cross_skill_investigation_message(user_query)
    if intent_family == "cve_investigation" and user_query:
        from app.chat.guidance_templates import build_cve_investigation_guidance

        return build_cve_investigation_guidance(user_query)
    if intent_family == "github_investigation" and user_query:
        from app.chat.guidance_templates import build_github_investigation_guidance

        return build_github_investigation_guidance(user_query)
    if user_query and is_mitre_evidence_threshold_query(user_query):
        return build_mitre_evidence_threshold_guidance(user_query)

    if intent_family == "alert_summary" and user_query:
        from app.chat.analyst_response_builder import build_alert_summary_message

        plan = evidence_plan if isinstance(evidence_plan, dict) else {}
        return build_alert_summary_message(
            user_query=user_query,
            evidence_plan=plan,
        )

    if is_unsafe_blocked_path(path_type) or (user_query and is_explicit_run_spl_query(user_query)):
        if user_query and is_explicit_run_spl_query(user_query):
            return build_spl_execution_refusal_guidance()
        return build_unsafe_action_guidance()
    # WS-0 is an out-of-registry answer-shape floor, not a guided-path-only
    # decoration.  Some T2 asks legitimately retain an SPL-review planning path;
    # they still need the deterministic regulatory/baseline/timeline/insider/OT
    # answer builder.  Exact/semantic catalogue paths remain byte-identical.
    if settings.ai_soc_t2_answer_shape_enabled and user_query:
        if not should_bypass_shape_router(match_path):
            from app.chat.query_signals import extract_query_signals
            from app.chat.network_boundary_display import is_firewall_boundary_query
            from app.spl.draft_preview import has_strong_detection_family_match

            live_data_signals = extract_query_signals(user_query)
            if (
                live_data_signals.get("live_data_request")
                and is_firewall_boundary_query(user_query)
                and has_strong_detection_family_match(user_query)
                and path_type in {"spl_review", "spl_review_plus_rag", "hybrid_investigation"}
            ):
                preview = (
                    spl_draft_preview
                    if isinstance(spl_draft_preview, dict)
                    else build_draft_preview(
                        user_query,
                        live_data_request=True,
                        llm_intent_advisory=(
                            llm_intent_advisory.model_dump()
                            if isinstance(llm_intent_advisory, LLMIntentAdvisory)
                            else llm_intent_advisory
                            if isinstance(llm_intent_advisory, dict)
                            else None
                        ),
                    )
                )
                if preview:
                    return build_draft_preview_analyst_message(preview)
            shape = classify_answer_shape(user_query, entities=entities, resource_plan=resource_plan)
            if shape.primary_shape != "hunt":
                return build_shaped_guidance(
                    user_query, entities=entities, match_path=match_path, resource_plan=resource_plan
                )
            if (
                str(match_path or "") == "out_of_registry"
                and path_type
                in {"guided_investigation", "hybrid_investigation", "spl_review", "spl_review_plus_rag"}
            ):
                return build_shaped_guidance(
                    user_query, entities=entities, match_path=match_path, resource_plan=resource_plan
                )
    if path_type == "guided_investigation" and user_query:
        # WS-0: route through the answer-shape router so non-hunt shapes
        # (IR/containment, regulatory, timeline, baselining, source-health,
        # insider/DLP, process-aware) get their shaped builders. The router
        # falls back to build_guided_investigation_guidance when the shape flag
        # is off or the match path is in-catalogue (happy-path bypass).
        return build_shaped_guidance(
            user_query, entities=entities, match_path=match_path, resource_plan=resource_plan
        )
    if user_query and is_policy_escalation_guidance_query(user_query):
        return build_policy_escalation_guidance(user_query)
    if user_query and is_mitre_evidence_threshold_query(user_query):
        return build_mitre_evidence_threshold_guidance(user_query)
    if settings.ai_soc_t2_answer_shape_enabled and user_query:
        # WS pk.009: supply-chain firmware/code-signing asks get judgment + substance
        # (cert provenance, vendor authorization, hash, rollout correlation), not the
        # conceptual-mitre judgment alone. Flag-gated; default posture unchanged.
        if is_supply_chain_firmware_query(user_query):
            return build_supply_chain_firmware_guidance(user_query)
    if user_query and is_conceptual_mitre_confirm_query(user_query):
        return build_conceptual_mitre_guidance(user_query)
    if user_query:
        from app.chat.query_signals import extract_query_signals

        triage_signals = extract_query_signals(user_query)
        if triage_signals.get("investigation_triage_guidance"):
            return build_investigation_triage_guidance(user_query)
    if spl_validation is None:
        if path_type in {"spl_review", "spl_review_plus_rag", "hybrid_investigation"}:
            return (
                "Governed SPL drafting is in review-only mode for this search request. "
                "Confirm index, sourcetype, key fields, and time range if a template is not yet bound."
            )
        if _rag_no_match(soc_kb_retrieval):
            return "No governed KB/SOP match was found for this request. I did not generate SPL, call MCP, or infer MITRE evidence."
        if _generic_soc_guidance_path(planning_decision):
            return "Generic SOC guidance path selected. Governed KB was checked when enabled; no catalog use case, SPL, MCP, or MITRE evidence claim was created."
        if isinstance(evidence_plan, dict) and evidence_plan.get("answer_mode") == "rag_only":
            if user_query and "checklist" in user_query.lower():
                return "Governed knowledge checklist path selected. SPL and MCP are skipped for this request."
            return "Governed knowledge path selected. SPL and MCP are skipped for this request."
        if user_query:
            from app.chat.query_signals import extract_query_signals

            signals = extract_query_signals(user_query)
            if signals.get("explicit_search_intent") or signals.get("explicit_log_search"):
                return (
                    "Review-only SPL/search path selected. A lab draft preview or governed template "
                    "may be shown when available; confirm index, sourcetype, fields, and time range. "
                    "No MCP execution was performed."
                )
            checklist = []
            if isinstance(evidence_plan, dict):
                checklist = list(evidence_plan.get("checklist") or evidence_plan.get("investigation_workflow") or [])
            if checklist:
                items = "\n".join(f"- {item}" for item in checklist[:6])
                return f"SOC investigation guidance:\n{items}"
        return (
            "Investigation planning is complete. Provide source profile details or run a review-only "
            "search when logs are required; no MCP execution was performed."
        )
    if _is_spl_clarification_required(spl_validation):
        return _spl_clarification_user_message(spl_validation)
    if spl_validation.get("approved") is True and (
        not execution or execution.get("status") != "executed"
    ):
        if spl_validation.get("llm_fallback_used") or (
            spl_validation.get("selected_candidate_spl_provider") == "llm_spl_advisory_fallback"
        ):
            return (
                "LLM lab SPL candidate — not governed, not approved, review required. "
                "It has passed deterministic validation and SOC-STD-SPL-001 quality lint "
                "but has not been executed."
            )
        return "Governed SPL draft ready. It has passed deterministic validation and has not been executed."
    if execution and execution.get("status") == "executed":
        if analyst_summary:
            return "Mock MCP execution complete. Live Foundation-Sec synthesis is disabled; deterministic lab summary was generated from governed evidence."
        return "Mock MCP execution complete. Final synthesis is disabled."
    return "SPL validation complete. MCP execution is disabled."


def _is_governed_spl_ready_for_response(spl_validation: dict[str, Any] | None) -> bool:
    if not isinstance(spl_validation, dict):
        return False
    return bool(spl_validation.get("approved") and spl_validation.get("normalized_spl"))


def _is_spl_clarification_required(spl_validation: dict[str, Any] | None) -> bool:
    if not isinstance(spl_validation, dict):
        return False
    # A T1 SPL-native review-only draft is a renderable review state, not a
    # clarification, even though it carries review-level findings (e.g. missing
    # sourcetype) that otherwise map to the clarification reason set.
    if str(spl_validation.get("review_required_reason") or "") in {
        "t2_spl_native_review_only",
        "universal_spl_authoring_review_only",
    }:
        return False
    if spl_validation.get("llm_fallback_status") == "clarification_required":
        return True
    review_reason = str(spl_validation.get("review_required_reason") or "")
    if review_reason in _SPL_GOVERNANCE_CLARIFICATION_REASONS:
        return True
    reasons = {str(item) for item in spl_validation.get("reject_reasons") or []}
    if reasons & _SPL_GOVERNANCE_CLARIFICATION_REASONS:
        return True
    return any(
        reason
        in {
            "llm_spl_fallback_disabled",
            "llm_spl_fallback_client_unavailable",
            "llm_spl_fallback_schema_invalid",
            "llm_spl_fallback_validation_failed",
            "llm_spl_fallback_unsupported_source",
        }
        for reason in reasons
    )


def _response_mode(
    context_sufficiency: dict[str, Any] | None,
    human_review: dict[str, Any] | None,
    spl_validation: dict[str, Any] | None,
) -> str:
    review = human_review if isinstance(human_review, dict) else {}
    if review.get("required") is True:
        review_type = str(review.get("review_type") or "")
        # The wired execute/edit/cancel confirmation for a ready, validated SPL.
        if review_type == "spl_execution_confirmation":
            return "execution_confirmation"
        # Review-only SPL draft (T1 SPL-native): renderable, non-executable.
        if review_type == "spl_review_required":
            return "review_required"
        if "clarification" in review_type:
            return "clarification_required"
        return "human_review_required"
    sufficiency = context_sufficiency if isinstance(context_sufficiency, dict) else {}
    if sufficiency.get("synthesis_readiness") is False and sufficiency.get("synthesis_allowed") is False:
        if spl_validation and spl_validation.get("approved") is False:
            return "candidate_spl_rejected"
        if sufficiency.get("status") in {"insufficient_evidence", "rag_no_match"}:
            return "insufficient_evidence"
    if spl_validation is None:
        return "deterministic_knowledge_or_routing"
    return "deterministic_investigation"


def _response_packaging_status(
    *,
    synthesis_status: SynthesisStatus | dict[str, Any] | None,
    composer_trace: dict[str, Any] | None,
    human_review: dict[str, Any] | None,
    final_answer_validation: dict[str, Any] | None,
    analyst_response: Any | None,
) -> str:
    """Small live-progress hint; never changes governance decisions."""
    if human_review and human_review.get("required"):
        return "blocked_review_required"
    if isinstance(final_answer_validation, dict) and final_answer_validation.get("guard_status") == "blocked":
        return "blocked_review_required"

    status = (
        synthesis_status.model_dump()
        if isinstance(synthesis_status, SynthesisStatus)
        else synthesis_status
        if isinstance(synthesis_status, dict)
        else {}
    )
    synthesis_state = str(status.get("status") or "")
    if synthesis_state == "partial_timeout":
        return "llm_timeout"
    if synthesis_state == "degraded":
        return "deterministic_fallback"
    if synthesis_state in {"disabled", "blocked"}:
        return "llm_skipped"

    composer = composer_trace if isinstance(composer_trace, dict) else {}
    if composer.get("llm_fallback_used"):
        return "deterministic_fallback"
    guard_status = str(composer.get("llm_guard_status") or "")
    if guard_status == "blocked":
        return "deterministic_fallback"
    if guard_status in {"disabled", "skipped"}:
        return "llm_skipped"
    if analyst_response is not None:
        return "answer_ready"
    return "packaging"


def _synthesis_mode(
    synthesis_status: SynthesisStatus | dict[str, Any] | None,
    analyst_summary: str | None,
) -> str:
    status = (
        synthesis_status.model_dump()
        if isinstance(synthesis_status, SynthesisStatus)
        else synthesis_status
        if isinstance(synthesis_status, dict)
        else {}
    )
    if analyst_summary and status.get("status") == "completed":
        return "deterministic_lab_summary"
    if status.get("enabled") is False:
        return "live_foundation_sec_disabled"
    if status.get("status") == "blocked":
        return "synthesis_blocked"
    return "deterministic_no_final_llm"


def _chat_note(
    spl_validation: dict | None,
    execution: dict | None = None,
    evidence_plan: dict[str, Any] | None = None,
    planning_decision: dict[str, Any] | None = None,
    soc_kb_retrieval: dict[str, Any] | None = None,
) -> str:
    rag_note = "Governed SOC KB retrieval may contribute source evidence when enabled."
    if not settings.soc_kb_retrieval_enabled:
        rag_note = "No RAG retrieval"
    if spl_validation is None:
        path_type = planning_decision.get("path_type") if isinstance(planning_decision, dict) else None
        if path_type in {"spl_review", "spl_review_plus_rag", "hybrid_investigation"}:
            return (
                "Review-only SPL/search path selected. SPL drafting may require source profile or template binding; "
                "no MCP execution, final synthesis, or Splunk telemetry write was run."
            )
        if _rag_no_match(soc_kb_retrieval):
            return "No governed KB/SOP match found. SPL and MCP were skipped; final synthesis remains disabled."
        if _generic_soc_guidance_path(planning_decision):
            return "Generic SOC guidance uses governed KB only when available and does not assign a runtime use_case_id. SPL, MCP, and final synthesis were skipped."
        if isinstance(evidence_plan, dict) and evidence_plan.get("answer_mode") == "rag_only":
            return "RAG-only evidence plan: SPL and MCP were skipped; final synthesis remains disabled."
        if not settings.soc_kb_retrieval_enabled:
            return "Routing and workflow planning only; SPL is not required at this stage. No MCP execution, RAG retrieval, or synthesis was run."
        return "Routing and workflow planning only; SPL is not required at this stage. Governed SOC KB retrieval may contribute source evidence when enabled. No MCP execution, final synthesis, or Splunk telemetry write was run."
    status = "approved" if spl_validation.get("approved") else "rejected"
    if execution and execution.get("status") == "executed":
        if not settings.soc_kb_retrieval_enabled:
            return f"Candidate SPL generated and {status}; mock MCP execution used normalized SPL only. No RAG retrieval, final synthesis, or Splunk telemetry write was run."
        return f"Candidate SPL generated and {status}; mock MCP execution used normalized SPL only. {rag_note} No final synthesis or Splunk telemetry write was run."
    if not settings.soc_kb_retrieval_enabled:
        return f"Candidate SPL generated and {status} by deterministic validation. No MCP execution, RAG retrieval, or synthesis was run."
    return f"Candidate SPL generated and {status} by deterministic validation. {rag_note} No MCP execution, final synthesis, or Splunk telemetry write was run."


def _execution_stage(
    *,
    trace_id: str,
    selected_skill: str,
    workflow_plan: dict,
    spl_validation: dict | None,
    precondition_evaluation: dict | None,
    requested_mcp_server: str | None,
    requested_mcp_tool: str | None,
    mcp_allowed: bool = True,
    execution_review_action: str | None = None,
    analyst_provided_spl: str | None = None,
    pending_execution: dict[str, Any] | None = None,
    rbac_role: str | None = None,
    llm_lineage_auto_eligible: bool = False,
    catalogue_match_path: str | None = None,
    catalogue_question_ref: str | None = None,
    catalogue_use_case_id: str | None = None,
    data_silence_advisory: dict[str, Any] | None = None,
    execution_intent: str = "spl_search",
    hook_idempotency: HookIdempotencyContext | None = None,
) -> tuple[dict, dict]:
    if spl_validation is None:
        return (
            {
                "status": "skipped",
                "execution_intent": "none",
                "selected_mcp_server": None,
                "selected_mcp_tool": None,
                "tool_selection_status": "unavailable",
                "tool_selection_reason": "spl_not_required_for_skill",
                "executed_spl": None,
                "result_count": 0,
                "results_preview": [],
                "block_reason": None,
                "duration_ms": 0,
            },
            no_human_review(),
        )
    if not mcp_allowed:
        return (
            {
                "status": "skipped",
                "execution_intent": "none",
                "selected_mcp_server": None,
                "selected_mcp_tool": None,
                "tool_selection_status": "blocked_by_evidence_plan",
                "tool_selection_reason": "mcp_not_allowed_by_evidence_plan",
                "executed_spl": None,
                "result_count": 0,
                "results_preview": [],
                "block_reason": "mcp_not_allowed_by_evidence_plan",
                "duration_ms": 0,
                "evidence_source": "unavailable",
                "execution_status_label": "not_executed",
            },
            no_human_review(),
        )
    return evaluate_mcp_execution(
        trace_id=trace_id,
        selected_skill=selected_skill,
        workflow_plan=workflow_plan,
        spl_validation=spl_validation,
        precondition_evaluation=precondition_evaluation,
        requested_mcp_server=requested_mcp_server,
        requested_mcp_tool=requested_mcp_tool,
        execution_review_action=execution_review_action,
        analyst_provided_spl=analyst_provided_spl,
        pending_execution=pending_execution,
        rbac_role=rbac_role,
        llm_lineage_auto_eligible=llm_lineage_auto_eligible,
        catalogue_match_path=catalogue_match_path,
        catalogue_question_ref=catalogue_question_ref,
        catalogue_use_case_id=catalogue_use_case_id,
        data_silence_advisory=data_silence_advisory,
        execution_intent=execution_intent,
        hook_idempotency=hook_idempotency,
    )


def _target_index_from_validation(spl_validation: dict | None) -> str | None:
    if not isinstance(spl_validation, dict):
        return None
    normalized = spl_validation.get("normalized_spl")
    if not isinstance(normalized, str):
        return None
    match = re.search(r"index=(\S+)", normalized)
    return match.group(1) if match else None


def _mcp_tool_plan_needs_mcp(state: ChatPipelineState, spl_validation: dict | None) -> bool:
    if spl_validation is None:
        return False
    if not _mcp_allowed(state):
        return False
    return _context_selected_skill(state) in EXECUTION_ELIGIBLE_SKILLS


def _reference_resolution_needed(evidence_plan: dict | None) -> bool:
    if not isinstance(evidence_plan, dict):
        return False
    if "reference_registry" in {str(item) for item in evidence_plan.get("required_sources") or []}:
        return True
    if "reference_dataset" in {str(item) for item in evidence_plan.get("required_evidence_keys") or []}:
        return True
    return "reference_taxonomy_lookup" in {str(item) for item in evidence_plan.get("reasons") or []}


# Reference dataset → knowledge-lane domain, for scoping keyword search when the
# validated bundle carries specialist ``reference_domains`` enrichments.
# RAG collection selection (``retrieve_soc_kb`` / ``select_rag_collections``) is
# intentionally unchanged — lane ``reference_domains`` do not narrow SOC-KB retrieval.
_REFERENCE_DATASET_DOMAINS: dict[str, str] = {
    "mitre_attack_enterprise": "mitre",
    "mitre_atlas": "atlas",
    "cve": "cve",
}


def _reference_dataset_allowed(dataset_id: str, reference_domains: list[str] | None) -> bool:
    """Keyword-search scope: unrestricted unless specific domains were merged."""
    if not reference_domains or "reference_lookup" in reference_domains:
        return True
    domain = _REFERENCE_DATASET_DOMAINS.get(dataset_id)
    return domain is None or domain in reference_domains


def _knowledge_reference_domains(evidence_plan: dict | None) -> list[str]:
    """Specialist ``reference_domains`` enrichments synced from the validated bundle."""
    if not isinstance(evidence_plan, dict):
        return []
    plan = evidence_plan.get("resource_plan")
    steps = plan.get("steps") if isinstance(plan, dict) else None
    domains: list[str] = []
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        if str(step.get("purpose") or "") not in {"knowledge_retrieval", "cve_lookup", "mitre_mapping"}:
            continue
        args = step.get("args_template")
        raw = args.get("reference_domains") if isinstance(args, dict) else None
        for item in raw or []:
            domain = str(item)
            if domain and domain not in domains:
                domains.append(domain)
    return domains


def _resolve_reference_knowledge(
    query: str,
    *,
    limit: int = 10,
    reference_domains: list[str] | None = None,
) -> dict[str, Any]:
    from app.planner.reference_registry import ReferenceFact, load_reference_registry

    registry = load_reference_registry()
    facts: list[ReferenceFact] = []
    ids_by_dataset = registry.extract_ids(query)
    for dataset_id, ids in ids_by_dataset.items():
        dataset = registry.by_id(dataset_id)
        if dataset is None:
            continue
        resolved = dataset.resolver.resolve_ids(ids)
        facts.extend(resolved)
        resolved_ids = {fact.reference_id.upper() for fact in resolved}
        for reference_id in ids:
            if reference_id.upper() in resolved_ids:
                continue
            facts.append(
                ReferenceFact(
                    reference_id=reference_id,
                    dataset_id=dataset_id,
                    name=reference_id,
                    description=f"{reference_id} was not found in the local {dataset_id} snapshot.",
                    citation=f"local {dataset_id} snapshot",
                    raw={"status": "not_found"},
                )
            )
    for dataset_id, dataset_facts in registry.search_keywords(query, limit=limit).items():
        if not _reference_dataset_allowed(dataset_id, reference_domains):
            continue
        facts.extend(dataset_facts)

    deduped: list[ReferenceFact] = []
    seen: set[tuple[str, str]] = set()
    for fact in facts:
        key = (fact.dataset_id, fact.reference_id.upper())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(fact)
        if len(deduped) >= limit:
            break
    return {
        "status": "resolved" if deduped else "not_found",
        "facts": [fact.to_dict() for fact in deduped],
        "ids_by_dataset": ids_by_dataset,
    }


def _append_reference_source_evidence(
    source_evidence: list[dict[str, Any]],
    *,
    trace_id: str,
    query: str,
    evidence_plan: dict | None,
    reference_resolution: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    if not _reference_resolution_needed(evidence_plan):
        return source_evidence, reference_resolution
    resolution = (
        reference_resolution
        if isinstance(reference_resolution, dict)
        else _resolve_reference_knowledge(
            query,
            reference_domains=_knowledge_reference_domains(evidence_plan),
        )
    )
    rows = [dict(item) for item in resolution.get("facts") or [] if isinstance(item, dict)]
    item = build_provider_source_evidence(
        trace_id=trace_id,
        source_type="reference_dataset",
        source_name="reference_registry",
        collection_status="collected" if rows else "skipped",
        query_or_request_summary="offline reference taxonomy lookup",
        result_count=len(rows),
        tool_name="reference_registry",
        preview_rows=rows,
        warnings=[] if rows else ["reference_not_found"],
        tool_category="reference_lookup",
        provider_used="reference_registry",
        provenance="operator_vendored_reference_dataset",
    )
    item["plan_step_ref"] = "reference"
    return [*source_evidence, item], resolution


def _reference_facts_for_card(structured_context: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(structured_context, dict):
        return []
    facts: list[dict[str, Any]] = []
    for item in structured_context.get("reference_facts") or []:
        if isinstance(item, dict):
            facts.append(dict(item))
        if len(facts) >= 10:
            break
    return facts


def _reference_lookup_summary(
    reference_facts: list[dict[str, Any]],
    *,
    user_query: str | None = None,
    source_evidence: list[dict[str, Any]] | None = None,
) -> str:
    return reference_summary_line(
        reference_facts,
        user_query=user_query,
        source_evidence=source_evidence,
    )


def graph_node_reference_finalize(state: ChatPipelineState) -> ChatPipelineState:
    emit_stage("reference_finalize")
    resolution = _resolve_reference_knowledge(
        str(state.get("effective_query") or state["request"].message),
        reference_domains=_knowledge_reference_domains(state.get("evidence_plan")),
    )
    updated = {**state, "reference_resolution": resolution}
    return advance_dispatch_cursor(updated, PipelineStage.reference_finalize)


def _context_stage(
    *,
    trace_id: str,
    query: str,
    selected_skill: str,
    workflow_plan: dict,
    spl_validation: dict | None,
    execution: dict,
    soc_kb_retrieval: dict | None = None,
    evidence_plan: dict | None = None,
    mcp_evidence: list[dict[str, Any]] | None = None,
    reference_resolution: dict[str, Any] | None = None,
) -> tuple[list[dict], dict, dict]:
    telemetry = _routes_chat().get_telemetry_connector()
    if soc_kb_retrieval is None:
        utility_signals = extract_query_signals(query)
        if is_universal_utility_spl_authoring(query, utility_signals):
            soc_kb_retrieval = _utility_spl_rag_skipped_payload()
            try:
                telemetry.record_rag_retrieval(
                    trace_id,
                    collection=None,
                    status="skipped",
                    result_count=0,
                    evidence_origin="rag_skipped_for_spl_utility_authoring",
                )
            except Exception:  # noqa: BLE001 - telemetry must never break chat
                logger.warning("utility_spl_rag_skip_telemetry_failed", exc_info=True)
        else:
            soc_kb_retrieval = retrieve_soc_kb(
                query=query,
                selected_skill=selected_skill,
                workflow_stage="context",
                workflow_plan=workflow_plan,
                required_sources=list(workflow_plan.get("required_sources") or []),
                execution_block_reason=execution.get("block_reason"),
            )
    source_evidence = build_source_evidence(
        trace_id=trace_id,
        query=query,
        selected_skill=selected_skill,
        spl_validation=spl_validation,
        execution=execution,
        soc_kb_retrieval=soc_kb_retrieval,
        include_skipped_mcp_placeholder=False,
    )
    source_evidence = append_mcp_loop_source_evidence(
        source_evidence,
        trace_id=trace_id,
        mcp_evidence=mcp_evidence,
    )
    source_evidence = append_cve_snapshot_source_evidence(
        source_evidence,
        trace_id=trace_id,
        evidence_plan=evidence_plan,
        query=query,
    )
    source_evidence, reference_resolution = _append_reference_source_evidence(
        source_evidence,
        trace_id=trace_id,
        query=query,
        evidence_plan=evidence_plan,
        reference_resolution=reference_resolution,
    )
    telemetry.record_step(
        trace_id,
        "source_evidence_created",
        "completed",
        evidence_count=len(source_evidence),
        collected_count=sum(1 for item in source_evidence if item["collection_status"] == "collected"),
    )
    structured_context = structure_context(
        query=query,
        trace_id=trace_id,
        selected_skill=selected_skill,
        workflow_plan=workflow_plan,
        spl_validation=spl_validation,
        execution=execution,
        source_evidence=source_evidence,
    )
    if reference_resolution is not None:
        structured_context["reference_resolution"] = reference_resolution
    telemetry.record_step(
        trace_id,
        "context_structured",
        "completed",
        context_quality=structured_context["context_quality"],
        fact_count=len(structured_context["structured_facts"]),
        synthesis_allowed=False,
    )
    context_sufficiency = check_context_sufficiency(structured_context, source_evidence)
    context_sufficiency = _apply_evidence_plan_sufficiency_reasons(
        context_sufficiency,
        evidence_plan=evidence_plan,
        soc_kb_retrieval=soc_kb_retrieval,
        source_evidence=source_evidence,
    )
    if isinstance(evidence_plan, dict) and evidence_plan.get("answer_mode"):
        context_sufficiency = {
            **context_sufficiency,
            "answer_mode": evidence_plan.get("answer_mode"),
        }
    telemetry.record_step(
        trace_id,
        "context_sufficiency_checked",
        "completed",
        sufficiency_status=context_sufficiency["status"],
        synthesis_allowed=False,
        synthesis_readiness=context_sufficiency["synthesis_readiness"],
        reasons=context_sufficiency["reasons"],
    )
    return source_evidence, structured_context, context_sufficiency


def _apply_evidence_plan_sufficiency_reasons(
    context_sufficiency: dict[str, Any],
    *,
    evidence_plan: dict | None,
    soc_kb_retrieval: dict | None,
    source_evidence: list[dict],
) -> dict[str, Any]:
    if not isinstance(evidence_plan, dict) or not evidence_plan.get("policy_context_required"):
        return context_sufficiency
    reasons = set(context_sufficiency.get("reasons") or [])
    reasons.add("policy_context_required")
    retrieved = soc_kb_retrieval if isinstance(soc_kb_retrieval, dict) else {}
    retrieval_status = str(retrieved.get("retrieval_status") or "")
    has_rag = any(item.get("source_type") == "rag" and item.get("collection_status") == "collected" for item in source_evidence)
    if retrieval_status in {"no_match", "disabled", "failed"} or not has_rag:
        reasons.add("rag_no_match")
    return {**context_sufficiency, "reasons": sorted(reasons)}


def _attach_hil_soc_kb_guidance(human_review: dict, source_evidence: list[dict]) -> dict:
    if not human_review.get("required"):
        return human_review
    if any(evidence.get("source_type") == "rag" and evidence.get("collection_status") == "ambiguous" for evidence in source_evidence):
        return {
            **human_review,
            "safe_message_for_user": "Knowledge retrieval is ambiguous and requires analyst review.",
        }
    sop_rows = []
    for evidence in source_evidence:
        if evidence.get("source_type") != "rag" or evidence.get("collection_status") != "collected":
            continue
        for row in evidence.get("preview_rows", []):
            if isinstance(row, dict) and row.get("document_type") in {"sop", "runbook", "escalation_matrix"}:
                sop_rows.append(row)
    if not sop_rows:
        return {
            **human_review,
            "safe_message_for_user": "Approved SOP guidance is unavailable for this scenario.",
        }
    row = sop_rows[0]
    actions = [str(item) for item in row.get("recommended_actions") or []]
    return {
        **human_review,
        "reviewer_role": str(row.get("reviewer_role") or human_review.get("reviewer_role")),
        "allowed_actions": actions or human_review.get("allowed_actions", []),
        "sop_reference": row.get("citation"),
        "sop_excerpt": row.get("source_excerpt"),
        "sop_action_hint": actions[0] if actions else None,
    }
