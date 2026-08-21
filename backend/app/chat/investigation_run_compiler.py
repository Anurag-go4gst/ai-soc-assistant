"""P5 deterministic compiler and stop-on-gap observation seam.

The approved envelope is the authority boundary.  This module translates it
into the existing ResourcePlan/PhaseContract vocabulary; it never dispatches a
tool and deliberately has no PlanDelta dependency.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.contracts.investigation_envelope import ApprovedInvestigationEnvelope
from app.chat.contracts.investigation_plan import ValidatedInvestigationPlan
from app.chat.contracts.resolved_query import ResolvedQueryContract
from app.planner.phase_contract import PhaseContract
from app.planner.resource_plan import ResourcePlan


@dataclass(frozen=True)
class CompiledInvestigationRun:
    evidence_plan: EvidencePlan
    resource_plan: ResourcePlan
    phase_contract: PhaseContract


def _stable_plan_id(envelope: ApprovedInvestigationEnvelope, handoff_id: str) -> str:
    payload = json.dumps(envelope.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(f"{handoff_id}:{payload}".encode("utf-8")).hexdigest()[:16]
    return f"rp:investigation:{digest}"


def _is_search_capability(capability_id: str) -> bool:
    value = capability_id.lower()
    return value.startswith("mcp:") and any(
        marker in value for marker in ("run_query", "search_splunk", "run_splunk_query")
    )


def build_approved_investigation_evidence_plan(
    *,
    envelope: ApprovedInvestigationEnvelope,
    validated_plan: ValidatedInvestigationPlan,
    resolved_query_contract: ResolvedQueryContract,
    handoff_id: str,
    handoff_version: int,
    use_case_id: str | None = None,
) -> tuple[EvidencePlan, list[str]]:
    """Validate one immutable envelope and build its pre-composition EvidencePlan."""
    if envelope.envelope_version != handoff_version:
        raise ValueError("envelope_version_must_match_handoff_version")

    approved = set(envelope.allowed_read_only_capabilities)
    requested = {
        binding.capability_id
        for binding in validated_plan.capability_bindings
        if binding.availability == "available" and binding.access_mode == "read_only"
    }
    if not requested.issuperset(approved):
        raise ValueError("approved_capability_missing_from_validated_plan")

    search_capabilities = sorted(cap for cap in approved if _is_search_capability(cap))
    needs_mcp = bool(search_capabilities)
    needs_spl = needs_mcp
    required = list(dict.fromkeys(envelope.approved_evidence_categories))
    evidence = EvidencePlan(
        answer_mode="guided_investigation",
        rag_phase="pre_mcp" if needs_mcp else "rag_only",
        needs_rag=True,
        needs_spl=needs_spl,
        needs_mcp=needs_mcp,
        needs_mitre=False,
        spl_allowed=needs_spl,
        mcp_allowed=needs_mcp,
        mcp_available=needs_mcp,
        policy_context_required=False,
        policy_context_recommended=True,
        requires_hil=needs_mcp,
        action_mode="hil_required" if needs_mcp else "recommend_only",
        required_evidence_keys=required,
        missing_required_evidence=required,
        checklist=list(validated_plan.evidence_needed),
        investigation_workflow=list(validated_plan.dependencies),
        required_sources=list(validated_plan.candidate_sources),
        limitations=[
            "P5 stops on an evidence gap; it does not invent or schedule an extra search.",
            "All connector calls remain subject to validation, exact-call authorization, RBAC, HIL, and execution flags.",
        ],
        runtime_support_status="approved_envelope_compiled",
        use_case_id=use_case_id,
        discovery_allowed=False,
        investigation_planning_enabled=True,
        spl_review_allowed=False,
        safe_spl_execution_allowed=needs_mcp,
        freeform_spl_execution_allowed=False,
        mcp_action_allowed=False,
        reasons=[
            "immutable_approved_investigation_envelope",
            f"envelope_version:{envelope.envelope_version}",
        ],
    )
    return evidence, search_capabilities


def attach_investigation_observation(state: dict[str, Any]) -> dict[str, Any]:
    """Project operational progress and an honest P5 stop/sufficient verdict."""
    if not isinstance(state.get("approved_investigation_envelope"), dict):
        return state
    evidence_plan = state.get("evidence_plan") if isinstance(state.get("evidence_plan"), dict) else {}
    resource_plan = (
        evidence_plan.get("resource_plan")
        if isinstance(evidence_plan.get("resource_plan"), dict)
        else {}
    )
    execution = state.get("execution") if isinstance(state.get("execution"), dict) else {}
    source_evidence = [
        item for item in (state.get("source_evidence") or []) if isinstance(item, dict)
    ]
    progress: list[dict[str, Any]] = []
    for step in resource_plan.get("steps") or []:
        if not isinstance(step, dict):
            continue
        purpose = str(step.get("purpose") or "planned_step")
        status = str(step.get("status") or "planned")
        evidence_refs = [
            str(item.get("evidence_id") or item.get("source_id") or "")
            for item in source_evidence
            if item.get("evidence_id") or item.get("source_id")
        ][:20]
        summary = (
            "Governed evidence was collected for this step."
            if evidence_refs
            else "No matching governed evidence was found for this step."
        )
        if status not in {"executed", "fallback_taken", "completed"}:
            summary = "No governed evidence was produced by this step."
        progress.append(
            {
                "step_id": str(step.get("step_id") or ""),
                "purpose": purpose,
                "status": status,
                "source": str(step.get("resource_id") or ""),
                "evidence_summary": summary,
                "evidence_refs": evidence_refs,
                "failure": str(step.get("status_reason") or execution.get("block_reason") or "") or None,
            }
        )

    sufficiency = (
        state.get("evidence_sufficiency")
        if isinstance(state.get("evidence_sufficiency"), dict)
        else {}
    )
    status = str(sufficiency.get("status") or "INSUFFICIENT").upper()
    sufficient = status == "SUFFICIENT"
    missing = list(
        sufficiency.get("missing")
        or (state.get("evidence_state") or {}).get("missing")
        or evidence_plan.get("missing_required_evidence")
        or []
    )
    run_status = {
        "status": "sufficient" if sufficient else "incomplete",
        "stop_reason": None if sufficient else "missing_evidence_no_plan_delta_in_p5",
        "missing_evidence": [str(item) for item in missing],
        "next_action": "continue_to_outcome" if sufficient else "stop",
        "plan_delta_emitted": False,
    }
    return {
        **state,
        "investigation_progress": progress,
        "investigation_run_status": run_status,
    }
