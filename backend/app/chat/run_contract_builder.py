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
from app.evidence.final_evidence_gate import (
    GatedEvidenceState,
    apply_final_evidence_gate,
)
from app.evidence.source_evidence import build_candidate_artifact_refs
from app.chat.pipeline import ChatPipelineState
from app.chat.query_signals import is_guidance_request, is_live_data_request
from app.config import settings
from app.planner.executor import mcp_composed_block_reason, normalize_mcp_posture_status

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
# Severity / MITRE intent-family policy now lives in the FinalEvidenceGate
# (app/evidence/final_evidence_gate.py), the single authority that
# build_run_contract projects from.

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


def build_final_evidence_gate(
    state: ChatPipelineState,
    *,
    route: RouteContract,
) -> GatedEvidenceState:
    """Compute the single cross-stream FinalEvidenceGate from pipeline state.

    This is the one authority for evidence classification + evidence-derived
    permissions (collected count, results-table/live-language permission, MITRE
    and severity permission, HIL). ``build_run_contract`` and the finalize node
    project from the returned state instead of re-deriving any of it.
    """
    signals = _query_signals_from_state(state) or {}
    live_data_request = is_live_data_request(signals)

    execution = state.get("execution") if isinstance(state.get("execution"), dict) else {}
    execution_status = str(execution.get("status") or "skipped")
    execution_authorized = execution_status.lower() in _EXECUTION_AUTHORIZED_STATUSES

    evidence_plan = state.get("evidence_plan") if isinstance(state.get("evidence_plan"), dict) else {}
    intent = state.get("intent_classification") if isinstance(state.get("intent_classification"), dict) else {}
    answer_contract = state.get("answer_contract")
    human_review = state.get("human_review") if isinstance(state.get("human_review"), dict) else None
    source_evidence = state.get("source_evidence") if isinstance(state.get("source_evidence"), list) else []
    spl_validation = state.get("spl_validation") if isinstance(state.get("spl_validation"), dict) else None
    candidate_spl = state.get("candidate_spl") if isinstance(state.get("candidate_spl"), dict) else None
    spl_draft_preview = state.get("spl_draft_preview") if isinstance(state.get("spl_draft_preview"), dict) else None

    effective_hil_required = resolve_effective_hil_required(
        evidence_plan=evidence_plan,
        answer_contract=answer_contract,
        human_review=human_review,
        execution=execution,
        live_data_request=live_data_request,
        execution_authorized=execution_authorized,
        intent_requires_hil=bool(intent.get("requires_hil")),
    )

    # The gate reads intent_family from the intent dict; the canonical family
    # lives on the RouteContract, so align them before calling the gate.
    gate_intent = dict(intent)
    if route.intent_family:
        gate_intent["intent_family"] = route.intent_family

    return apply_final_evidence_gate(
        source_evidence=source_evidence,
        execution=execution,
        soc_kb_retrieval=state.get("soc_kb_retrieval"),
        mcp_evidence=state.get("mcp_evidence"),
        evidence_plan=evidence_plan,
        intent=gate_intent,
        spl_validation=spl_validation,
        candidate_spl=candidate_spl,
        spl_draft_preview=spl_draft_preview,
        route_live_data_request=live_data_request,
        execution_authorized=execution_authorized,
        effective_hil_required=effective_hil_required,
        policy_backed=_policy_backed_in_catalog(state, intent),
    )



def _is_spl_utility_authoring(state: ChatPipelineState, evidence_plan: dict[str, Any]) -> bool:
    if evidence_plan.get("answer_mode") == "spl_utility_authoring":
        return True
    candidate = state.get("candidate_spl") if isinstance(state.get("candidate_spl"), dict) else {}
    if candidate.get("detection_family") == "universal_timestamp_spl":
        return True
    spl_validation = state.get("spl_validation") if isinstance(state.get("spl_validation"), dict) else {}
    return str(spl_validation.get("review_required_reason") or "") == "universal_spl_authoring_review_only"


def build_run_contract(
    state: ChatPipelineState,
    *,
    route: RouteContract,
    gate: GatedEvidenceState | None = None,
) -> RunContract:
    """Project final-run contract; never infer MCP need from evidence_plan.needs_mcp alone.

    ``gate`` is the FinalEvidenceGate authority. When omitted (direct unit-test
    callers) it is computed here so behavior is identical; the finalize node
    passes the already-computed gate to keep a single source of truth.
    """
    if gate is None:
        gate = build_final_evidence_gate(state, route=route)
    evidence_plan = state.get("evidence_plan") if isinstance(state.get("evidence_plan"), dict) else {}
    utility_spl_authoring = _is_spl_utility_authoring(state, evidence_plan)
    signals = _query_signals_from_state(state) or {}
    live_data_request = is_live_data_request(signals)
    if utility_spl_authoring:
        execution_needed = False
        mcp_needed = False
    else:
        execution_needed = live_data_request and route.canonical_skill in _LIVE_ANSWER_SKILLS
        mcp_needed = execution_needed

    execution = state.get("execution") if isinstance(state.get("execution"), dict) else {}
    execution_status = str(execution.get("status") or "skipped")
    execution_authorized = execution_status.lower() in _EXECUTION_AUTHORIZED_STATUSES

    mcp_allowed = _resolve_mcp_allowed(state, evidence_plan, execution_authorized=execution_authorized)

    collected_evidence_count = gate.collected_evidence_count
    source_evidence_available = collected_evidence_count > 0

    spl_validation = state.get("spl_validation") if isinstance(state.get("spl_validation"), dict) else None
    candidate_spl = state.get("candidate_spl") if isinstance(state.get("candidate_spl"), dict) else None
    spl_draft_preview = state.get("spl_draft_preview") if isinstance(state.get("spl_draft_preview"), dict) else None
    # Mirror the pipeline's _spl_allowed authority: with the control plane off
    # there is no evidence_plan node, so SPL is allowed (a candidate that exists
    # was already permitted upstream).  With CP on, honour the evidence plan.
    spl_allowed = bool(evidence_plan.get("spl_allowed")) if True else True

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

    # Evidence-derived authority is projected from the gate, not re-decided here.
    effective_hil_required = gate.effective_hil_required
    allow_live = gate.allow_live_result_language
    allow_mitre = gate.allow_mitre_mapping
    allow_severity = gate.allow_severity_assessment

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
            status=(
                "collected"
                if source_evidence_available
                else ("metadata_only" if evidence_count > 0 else "none")
            ),
            source_evidence_available=source_evidence_available,
            evidence_count=evidence_count,
            collected_evidence_count=collected_evidence_count,
            review_artifact_count=max(evidence_count - collected_evidence_count, 0),
            candidate_artifact_count=len(candidate_artifact_refs),
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
    routed = state.get("routed") if isinstance(state.get("routed"), dict) else {}
    return str(routed.get("skill") or "knowledge_recall")




def _resolve_mcp_allowed(
    state: ChatPipelineState,
    evidence_plan: dict[str, Any],
    *,
    execution_authorized: bool = False,
) -> bool:
    """Audit projection of MCP authorization for this turn.

    This is a post-execution read-model, not the execution gate. With the control
    plane off (or no evidence plan), there is no permissive plan to report, so the
    audit value is explicit: MCP is "allowed" only when execution was actually
    authorized this turn. A review-only / blocked answer reports explicit False
    rather than the permissive gate-bypass True.
    """
    if not evidence_plan:
        return bool(execution_authorized)
    spl_validation = state.get("spl_validation") if isinstance(state, dict) else None
    if isinstance(spl_validation, dict) and spl_validation.get("approved") is not True:
        return False
    return evidence_plan.get("mcp_allowed") is True

def _query_signals_from_state(state: ChatPipelineState) -> dict[str, Any] | None:
    q2i = state.get("query_to_intent")
    if not isinstance(q2i, dict):
        return None
    signals = q2i.get("query_signals")
    return signals if isinstance(signals, dict) else None


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
    # T1 SPL-native review-only draft: render the safe, non-executable SPL even
    # though it carries review-level validator findings (e.g. missing sourcetype).
    # Execution is hard-blocked elsewhere (approved=false, normalized_spl=null),
    # so showing the draft is safe and is the point of the review-only path.
    if (
        isinstance(candidate_spl, dict)
        and candidate_spl.get("generation_mode") == "t2_spl_native_review"
        and candidate_spl.get("review_only_renderable")
        and str(candidate_spl.get("candidate_spl") or "").strip()
    ):
        return True
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


def _normalize_mcp_posture_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    normalized["status"] = normalize_mcp_posture_status(str(payload.get("status") or "planned"))
    normalized["execution_authorized"] = bool(payload.get("execution_authorized"))
    return normalized


def project_mcp_posture(state: ChatPipelineState) -> dict[str, Any] | None:
    """Project MCP posture from composed ResourcePlan + execution evaluation."""
    evidence_plan = state.get("evidence_plan") if isinstance(state.get("evidence_plan"), dict) else {}
    resource_plan = evidence_plan.get("resource_plan") if isinstance(evidence_plan.get("resource_plan"), dict) else {}
    steps = resource_plan.get("steps") if isinstance(resource_plan.get("steps"), list) else []
    mcp_step = next(
        (step for step in steps if isinstance(step, dict) and step.get("purpose") == "mcp_execution"),
        None,
    )
    execution = state.get("execution") if isinstance(state.get("execution"), dict) else {}
    if mcp_step is None and not execution:
        return None
    metadata = mcp_step.get("mcp_step_metadata") if isinstance(mcp_step, dict) else None
    if isinstance(metadata, dict) and metadata:
        return _normalize_mcp_posture_payload(metadata)
    if isinstance(mcp_step, dict):
        composed_reason = mcp_composed_block_reason(mcp_step)
        if composed_reason is not None:
            posture_status = str(mcp_step.get("status") or "blocked_policy")
            primary_reason = composed_reason
            execution_authorized = False
        else:
            posture_status = str(mcp_step.get("status") or execution.get("status") or "planned")
            primary_reason = str(
                mcp_step.get("status_reason") or execution.get("block_reason") or "not_run"
            )
            execution_authorized = str(execution.get("status") or "") == "executed"
        return _normalize_mcp_posture_payload(
            {
                "status": posture_status,
                "primary_reason": primary_reason,
                "secondary_reasons": [str(item) for item in mcp_step.get("policy_checks") or []],
                "selected_tool": execution.get("selected_mcp_tool"),
                "execution_authorized": execution_authorized,
            }
        )
    return _normalize_mcp_posture_payload(
        {
            "status": str(execution.get("status") or "skipped"),
            "primary_reason": str(execution.get("block_reason") or execution.get("status") or "no_mcp_step"),
            "secondary_reasons": [],
            "selected_tool": execution.get("selected_mcp_tool"),
            "execution_authorized": str(execution.get("status") or "") == "executed",
        }
    )


def enrich_run_contract_payload(payload: dict[str, Any], state: ChatPipelineState) -> dict[str, Any]:
    posture = project_mcp_posture(state)
    if posture is not None:
        payload = dict(payload)
        payload["mcp_posture"] = posture
    return payload
