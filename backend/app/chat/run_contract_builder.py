"""Pure builders for RouteContract and RunContract from pipeline state."""

from __future__ import annotations

from typing import Any

from app.chat.contracts.run_contract import (
    AUTHORITY_HOLDER,
    RouteContract,
    RunContract,
    SourceEvidenceSummary,
    SplContractStatus,
)
from app.chat.hil_resolution import resolve_effective_hil_required
from app.evidence.source_evidence import build_candidate_artifact_refs
from app.chat.pipeline import ChatPipelineState
from app.chat.query_signals import is_guidance_request, is_live_data_request
from app.config import settings

_EXECUTION_AUTHORIZED_STATUSES = frozenset(
    {
        "executed",
        "executed_mock_evidence",
        "executed_live_evidence",
        "success",
    }
)
_LIVE_ANSWER_SKILLS = frozenset({"spl_generation", "attack_discovery"})
_IN_CATALOG_MATCH_PATHS = frozenset(
    {
        "exact_105_question",
        "exact_105_plus_use_case_catalog",
        "use_case_catalog",
    }
)
_POLICY_SEVERITY_FAMILIES = frozenset(
    {
        "hybrid_alert_review",
        "alert_summary",
        "live_investigation",
        "mitre_mapping",
        "spl_generation_only",
    }
)

_REVIEW_ONLY_SPL_PREVIEW = (
    "Review-only SPL draft — no live query was executed."
)
_REVIEW_ONLY_NO_TELEMETRY = (
    "Review-only response — no live telemetry was collected."
)


def build_route_contract(state: ChatPipelineState) -> RouteContract:
    """Project routing authority from pipeline state."""
    canonical_skill = _resolve_canonical_skill(state)
    routed = state.get("routed") if isinstance(state.get("routed"), dict) else {}
    routed_skill = str(routed.get("skill") or "").strip()
    legacy_skill = routed_skill if routed_skill and routed_skill != canonical_skill else None

    planning = state.get("planning_decision") if isinstance(state.get("planning_decision"), dict) else {}
    intent = state.get("intent_classification") if isinstance(state.get("intent_classification"), dict) else {}
    signals = _query_signals_from_state(state) or {}

    adjudication = state.get("route_adjudication") if isinstance(state.get("route_adjudication"), dict) else {}
    provenance = routed.get("routing_provenance") if isinstance(routed.get("routing_provenance"), dict) else {}
    adjudication_authority_source = adjudication.get("authority_source")
    if adjudication_authority_source is not None:
        adjudication_authority_source = str(adjudication_authority_source)
    route_source = adjudication_authority_source or (
        str(provenance.get("authority_source")) if provenance.get("authority_source") else None
    )

    return RouteContract(
        canonical_skill=canonical_skill,
        legacy_skill=legacy_skill,
        legacy_authoritative=False,
        authority_holder=AUTHORITY_HOLDER,
        path_type=str(planning.get("path_type") or "") or None,
        intent_family=str(intent.get("intent_family") or "") or None,
        live_data_request=is_live_data_request(signals),
        guidance_request=is_guidance_request(signals),
        route_source=route_source,
        adjudication_authority_source=adjudication_authority_source,
    )


def build_run_contract(
    state: ChatPipelineState,
    *,
    route: RouteContract,
) -> RunContract:
    """Project final-run contract; never infer MCP need from evidence_plan.needs_mcp alone."""
    signals = _query_signals_from_state(state) or {}
    live_data_request = is_live_data_request(signals)
    execution_needed = live_data_request and route.canonical_skill in _LIVE_ANSWER_SKILLS
    mcp_needed = execution_needed

    execution = state.get("execution") if isinstance(state.get("execution"), dict) else {}
    execution_status = str(execution.get("status") or "skipped")
    execution_authorized = execution_status.lower() in _EXECUTION_AUTHORIZED_STATUSES

    evidence_plan = state.get("evidence_plan") if isinstance(state.get("evidence_plan"), dict) else {}
    mcp_allowed = _resolve_mcp_allowed(state, evidence_plan)

    collected_evidence_count = _count_collected_evidence(state)
    source_evidence_available = collected_evidence_count > 0

    spl_validation = state.get("spl_validation") if isinstance(state.get("spl_validation"), dict) else None
    candidate_spl = state.get("candidate_spl") if isinstance(state.get("candidate_spl"), dict) else None
    spl_draft_preview = state.get("spl_draft_preview") if isinstance(state.get("spl_draft_preview"), dict) else None
    spl_allowed = bool(evidence_plan.get("spl_allowed"))

    spl_candidate_present = _spl_candidate_present(candidate_spl, spl_draft_preview)
    spl_candidate_renderable = _spl_candidate_renderable(
        spl_validation=spl_validation,
        candidate_spl=candidate_spl,
        spl_draft_preview=spl_draft_preview,
        spl_allowed=spl_allowed,
    )
    spl_validated = bool(isinstance(spl_validation, dict) and spl_validation.get("approved"))
    spl_normalized = bool(
        isinstance(spl_validation, dict) and bool(str(spl_validation.get("normalized_spl") or "").strip())
    )
    spl_status, spl_block_reason = _derive_spl_status(
        spl_validation=spl_validation,
        spl_draft_preview=spl_draft_preview,
        spl_allowed=spl_allowed,
        spl_candidate_present=spl_candidate_present,
    )

    intent = state.get("intent_classification") if isinstance(state.get("intent_classification"), dict) else {}
    answer_contract = state.get("answer_contract")
    human_review = state.get("human_review") if isinstance(state.get("human_review"), dict) else None

    effective_hil_required = resolve_effective_hil_required(
        evidence_plan=evidence_plan,
        answer_contract=answer_contract,
        human_review=human_review,
        execution=execution,
        live_data_request=live_data_request,
        execution_authorized=execution_authorized,
        intent_requires_hil=bool(intent.get("requires_hil")),
    )

    allow_live = execution_authorized and collected_evidence_count > 0
    allow_mitre = _allow_mitre_mapping(
        evidence_plan=evidence_plan,
        intent=intent,
        state=state,
        collected_evidence_count=collected_evidence_count,
    )
    allow_severity = _allow_severity_assessment(
        route=route,
        evidence_plan=evidence_plan,
        intent=intent,
        state=state,
        execution_authorized=execution_authorized,
        collected_evidence_count=collected_evidence_count,
    )

    source_evidence = state.get("source_evidence")
    evidence_count = len(source_evidence) if isinstance(source_evidence, list) else 0
    candidate_artifact_refs = build_candidate_artifact_refs(
        trace_id=str(state.get("trace_id") or "unknown"),
        spl_validation=spl_validation if isinstance(spl_validation, dict) else None,
        candidate_spl=candidate_spl if isinstance(candidate_spl, dict) else None,
    )

    return RunContract(
        execution_needed_for_answer=execution_needed,
        mcp_needed_for_live_answer=mcp_needed,
        execution_status=execution_status,
        execution_authorized=execution_authorized,
        mcp_allowed=mcp_allowed,
        collected_evidence_count=collected_evidence_count,
        source_evidence_available=source_evidence_available,
        effective_hil_required=effective_hil_required,
        allow_live_result_language=allow_live,
        allow_results_table=allow_live,
        allow_mitre_mapping=allow_mitre,
        allow_severity_assessment=allow_severity,
        spl_candidate_present=spl_candidate_present,
        spl_candidate_renderable=spl_candidate_renderable,
        spl_validated=spl_validated,
        spl_normalized=spl_normalized,
        spl_execution_eligible=False,
        spl_status=spl_status,
        spl_block_reason=spl_block_reason,
        routing=route,
        candidate_artifact_refs=candidate_artifact_refs,
        source_evidence_summary=SourceEvidenceSummary(
            status="collected" if source_evidence_available else "none",
            evidence_count=evidence_count,
            collected_evidence_count=collected_evidence_count,
            produced_answer_sections=[],
        ),
    )


def build_answer_preview(contract: RunContract) -> str:
    """Review-only preview strings when execution did not collect telemetry."""
    if contract.allow_live_result_language:
        return ""
    if contract.routing.canonical_skill == "spl_generation":
        return _REVIEW_ONLY_SPL_PREVIEW
    return _REVIEW_ONLY_NO_TELEMETRY


def _resolve_canonical_skill(state: ChatPipelineState) -> str:
    if settings.control_plane_enabled:
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
    routed = state.get("routed") if isinstance(state.get("routed"), dict) else {}
    return str(routed.get("skill") or "knowledge_recall")




def _resolve_mcp_allowed(state: ChatPipelineState, evidence_plan: dict[str, Any]) -> bool:
    """Align with pipeline _mcp_allowed: CP-off defaults permissive; plan gates when present."""
    if not settings.control_plane_enabled:
        return True
    if not evidence_plan:
        return True
    return bool(evidence_plan.get("mcp_allowed", True))

def _query_signals_from_state(state: ChatPipelineState) -> dict[str, Any] | None:
    q2i = state.get("query_to_intent")
    if not isinstance(q2i, dict):
        return None
    signals = q2i.get("query_signals")
    return signals if isinstance(signals, dict) else None


def _count_collected_evidence(state: ChatPipelineState) -> int:
    """Count collected rows from raw execution/RAG/MCP inputs, not packaged source_evidence."""
    count = 0

    soc_kb = state.get("soc_kb_retrieval")
    if isinstance(soc_kb, dict) and str(soc_kb.get("retrieval_status") or "") == "retrieved":
        count += 1

    execution = state.get("execution") if isinstance(state.get("execution"), dict) else {}
    exec_status = str(execution.get("status") or "")
    if exec_status == "executed":
        count += 1
        orchestration = execution.get("mcp_orchestration")
        if isinstance(orchestration, dict) and orchestration.get("recipe_id") == "broaden_scope_on_empty":
            calls = orchestration.get("calls")
            if isinstance(calls, list) and len(calls) >= 2:
                primary = calls[0]
                if isinstance(primary, dict) and primary.get("outcome") == "empty":
                    count += 1

    mcp_evidence = state.get("mcp_evidence")
    if isinstance(mcp_evidence, list):
        count += sum(
            1
            for item in mcp_evidence
            if isinstance(item, dict) and str(item.get("collection_status") or "") == "collected"
        )

    return count


def _spl_candidate_present(
    candidate_spl: dict[str, Any] | None,
    spl_draft_preview: dict[str, Any] | None,
) -> bool:
    if isinstance(candidate_spl, dict) and str(candidate_spl.get("candidate_spl") or "").strip():
        return True
    if isinstance(spl_draft_preview, dict) and str(spl_draft_preview.get("draft_spl") or "").strip():
        return True
    return False


def _spl_candidate_renderable(
    *,
    spl_validation: dict[str, Any] | None,
    candidate_spl: dict[str, Any] | None,
    spl_draft_preview: dict[str, Any] | None,
    spl_allowed: bool,
) -> bool:
    if not spl_allowed:
        return False
    if not _spl_candidate_present(candidate_spl, spl_draft_preview):
        return False
    reject_reasons = list((spl_validation or {}).get("reject_reasons") or [])
    if any(str(item).startswith("missing_binding:") for item in reject_reasons):
        return False
    if isinstance(candidate_spl, dict) and candidate_spl.get("generation_mode") == "clarification_required":
        return False
    if (
        isinstance(spl_draft_preview, dict)
        and spl_draft_preview.get("template_match_strength") == "strong"
        and str(spl_draft_preview.get("draft_spl") or "").strip()
    ):
        return True
    if isinstance(spl_validation, dict) and spl_validation.get("approved") and spl_validation.get("normalized_spl"):
        return True
    if isinstance(spl_draft_preview, dict) and str(spl_draft_preview.get("draft_spl") or "").strip():
        return True
    if isinstance(candidate_spl, dict) and str(candidate_spl.get("candidate_spl") or "").strip():
        return not reject_reasons
    return False


def _derive_spl_status(
    *,
    spl_validation: dict[str, Any] | None,
    spl_draft_preview: dict[str, Any] | None,
    spl_allowed: bool,
    spl_candidate_present: bool,
) -> tuple[SplContractStatus, str | None]:
    if not spl_allowed:
        return "not_required", None
    if isinstance(spl_validation, dict):
        reject_reasons = [str(item) for item in spl_validation.get("reject_reasons") or []]
        if any(item.startswith("missing_binding:") for item in reject_reasons):
            return "blocked", "missing_slot_binding"
        if spl_validation.get("approved") and spl_validation.get("normalized_spl"):
            return "ready_for_review", None
        if spl_validation.get("review_required"):
            return "review_required", None
        if reject_reasons:
            return "blocked", reject_reasons[0]
    if spl_candidate_present:
        return "review_required", None
    return "not_required", None


def _allow_mitre_mapping(
    *,
    evidence_plan: dict[str, Any],
    intent: dict[str, Any],
    state: ChatPipelineState,
    collected_evidence_count: int,
) -> bool:
    needs_mitre = bool(evidence_plan.get("needs_mitre"))
    if not needs_mitre:
        return False
    if collected_evidence_count > 0:
        return True
    return _policy_backed_in_catalog(state, intent)


def _allow_severity_assessment(
    *,
    route: RouteContract,
    evidence_plan: dict[str, Any],
    intent: dict[str, Any],
    state: ChatPipelineState,
    execution_authorized: bool,
    collected_evidence_count: int,
) -> bool:
    intent_family = route.intent_family or ""
    if _policy_backed_in_catalog(state, intent) and intent_family in _POLICY_SEVERITY_FAMILIES:
        return True
    if route.live_data_request and not execution_authorized and collected_evidence_count == 0:
        return False
    if intent_family == "spl_generation_only" and route.live_data_request and collected_evidence_count == 0:
        return False
    if collected_evidence_count > 0 or execution_authorized:
        return True
    return intent_family not in {"spl_generation_only", "guided_investigation", "knowledge_only"}


def _policy_backed_in_catalog(state: ChatPipelineState, intent: dict[str, Any]) -> bool:
    use_case_id = _resolve_use_case_id(state, intent)
    if use_case_id:
        return True
    match_path = str(intent.get("match_path") or "")
    if match_path in _IN_CATALOG_MATCH_PATHS:
        return True
    q2i = state.get("query_to_intent")
    if isinstance(q2i, dict):
        mappings = q2i.get("candidate_mappings")
        if isinstance(mappings, dict):
            mapping_path = str(mappings.get("match_path") or "")
            if mapping_path in _IN_CATALOG_MATCH_PATHS:
                return True
    return False


def _resolve_use_case_id(state: ChatPipelineState, intent: dict[str, Any]) -> str | None:
    evidence_plan = state.get("evidence_plan")
    if isinstance(evidence_plan, dict) and evidence_plan.get("use_case_id"):
        return str(evidence_plan["use_case_id"])
    if intent.get("use_case_id"):
        return str(intent["use_case_id"])
    selected = state.get("selected_use_case")
    if selected is not None and getattr(selected, "use_case_id", None):
        return str(selected.use_case_id)
    return None
