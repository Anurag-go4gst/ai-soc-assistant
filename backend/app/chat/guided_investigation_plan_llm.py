"""Bounded LLM InvestigationPlan propose for guided hybrid dispatch (REV4 batch 2 P9)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from app.chat.contracts.investigation_plan import InvestigationPlan
from app.llm.adapter.schemas import InvestigationPlanProposalPayload
from app.llm.adapter.output_preprocessor import INVESTIGATION_PLAN_SCHEMA, preprocess_llm_output
from app.llm.sidecar_clients import invoke_sidecar_role_with_metadata, sidecar_timeout_seconds
from app.llm.sidecar_governance import t4_circuit_status
from app.safeguards.trust_boundary import CONTROL_PREAMBLE, wrap_untrusted_source

INVESTIGATION_PLAN_ROLE = "investigation_planner"
_PROPOSE_TIMEOUT_SECONDS = 120.0
_PROPOSE_MAX_OUTPUT_TOKENS = 1200

INVESTIGATION_PLAN_PROPOSE_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "objectives": {"type": "array", "items": {"type": "string"}},
        "investigation_objective": {"type": "string"},
        "hypotheses": {"type": "array", "items": {"type": "string"}},
        "evidence_needed": {"type": "array", "items": {"type": "string"}},
        "data_categories": {"type": "array", "items": {"type": "string"}},
        "rag_sufficient": {"type": "boolean"},
        "env_kb_needed": {"type": "boolean"},
        "discovery_needed": {"type": "boolean"},
        "read_only_tools": {"type": "array", "items": {"type": "string"}},
        "safe_spl_templates": {"type": "array", "items": {"type": "string"}},
        "spl_review_requested": {"type": "boolean"},
        "clarification_needed": {"type": "boolean"},
        "clarification_questions": {"type": "array", "items": {"type": "string"}},
        "refinement_recommended": {"type": "boolean"},
        "rationale": {"type": "string"},
        "dependencies": {"type": "array", "items": {"type": "string"}},
        "conditions": {"type": "array", "items": {"type": "string"}},
        "success_criteria": {"type": "array", "items": {"type": "string"}},
        "capability_requests": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "hypotheses",
        "evidence_needed",
        "data_categories",
        "rag_sufficient",
        "env_kb_needed",
        "discovery_needed",
        "read_only_tools",
        "safe_spl_templates",
        "spl_review_requested",
        "clarification_needed",
        "clarification_questions",
        "refinement_recommended",
    ],
}


@dataclass(frozen=True)
class InvestigationPlanLlmResult:
    raw_llm: dict[str, Any] | None
    proposal: dict[str, Any] | None
    attempted: bool
    timed_out: bool
    provider_label: str | None
    dropped_reasons: list[str]
    latency_ms: int = 0
    circuit_state: str | None = None
    human_action_required: bool = False
    failure_kind: str | None = None


def _map_llm_payload_to_proposal(payload: dict[str, Any]) -> dict[str, Any]:
    objectives = payload.get("objectives")
    objective = None
    if isinstance(objectives, list) and objectives:
        objective = str(objectives[0] or "").strip() or None
    objective = str(payload.get("investigation_objective") or objective or "").strip() or None
    proposal: dict[str, Any] = {
        "hypotheses": payload.get("hypotheses") or [],
        "evidence_needed": payload.get("evidence_needed") or [],
        "data_categories": payload.get("data_categories") or [],
        "rag_sufficient": payload.get("rag_sufficient"),
        "env_kb_needed": payload.get("env_kb_needed"),
        "discovery_needed": payload.get("discovery_needed"),
        "read_only_tool_requests": payload.get("read_only_tools") or [],
        "safe_spl_template_requests": payload.get("safe_spl_templates") or [],
        "spl_review_requested": payload.get("spl_review_requested"),
        "clarification_needed": payload.get("clarification_needed"),
        "clarification_questions": payload.get("clarification_questions") or [],
        "refinement_recommended": payload.get("refinement_recommended"),
        "refinement_rationale": payload.get("rationale"),
        "dependencies": payload.get("dependencies") or [],
        "conditions": payload.get("conditions") or [],
        "success_criteria": payload.get("success_criteria") or [],
        # Advisory only: `_capability_bindings` drops anything not present in the
        # CapabilitySnapshot, not read-only, or classified blocked.
        "capability_requests": payload.get("capability_requests") or [],
    }
    if objective:
        proposal["investigation_objective"] = objective
    return proposal


_MAX_CONTEXT_ITEMS = 12


def _plan_context(baseline: InvestigationPlan, capability_ids: list[str]) -> dict[str, Any]:
    """Bounded, already-governed planning context for the reasoning role.

    Everything here is derived from the Final RQC and the deterministic baseline
    that DET has already committed. It is grounding, not authority: the proposal
    is still merged only through ``validate_investigation_plan``, which drops
    unsafe text, unknown capabilities and forbidden authority fields.
    """
    return {
        "investigation_objective": baseline.investigation_objective,
        "already_planned_hypotheses": list(baseline.hypotheses)[:_MAX_CONTEXT_ITEMS],
        "already_planned_evidence": list(baseline.evidence_needed)[:_MAX_CONTEXT_ITEMS],
        "data_categories": list(baseline.data_categories)[:_MAX_CONTEXT_ITEMS],
        "known_constraints": list(baseline.environment_constraints)[:_MAX_CONTEXT_ITEMS],
        "available_read_capability_ids": capability_ids[:_MAX_CONTEXT_ITEMS],
    }


def _build_user_prompt(
    *,
    query: str,
    baseline: InvestigationPlan,
    capability_ids: list[str],
) -> str:
    """Prompt the planner about THIS investigation, inside the trust boundary.

    A planner given no case data can only return generic SOC filler, which the
    validator then merges into the analyst-visible plan — an auth checklist on a
    DNS/firewall investigation. The query is labelled untrusted input (§2.8) and
    the model still receives no evidence rows, no credentials and no raw SPL.
    """
    context = json.dumps(_plan_context(baseline, capability_ids), separators=(",", ":"))
    return "\n".join(
        [
            CONTROL_PREAMBLE,
            "Propose read-only SOC investigation-plan fields for the request below. "
            "Extend the already-planned items; do not restate them and do not "
            "contradict them.",
            wrap_untrusted_source("user_query", query),
            f"PLANNING_CONTEXT: {context}",
            "Return only valid JSON matching the schema. No markdown, no explanation "
            "outside JSON, no hidden reasoning, no scratchpad, no planning text, and no "
            "<think> tags. Do not emit raw SPL, execution flags, severity, route changes, "
            "authorization, or remediation actions. read_only_tools and capability_requests "
            "may only contain ids from available_read_capability_ids; use an empty list when "
            "unsure. Every hypothesis and evidence item must be relevant to this request.",
            "ANSWER:",
        ]
    )


def _hop_timeout_seconds(turn_budget: Any | None) -> float | None:
    """Cap the planner hop to whatever wall time the turn has left.

    A reasoning endpoint that is merely slow must not be able to outlive the turn
    deadline; the deterministic baseline is always available, so an exhausted turn
    budget degrades instead of stalling ``/chat``. The optional-sidecar call quota
    is deliberately not consulted: the planner is a first-class investigation hop,
    not an advisory enrichment, so only wall clock bounds it.
    """
    if turn_budget is None:
        return _PROPOSE_TIMEOUT_SECONDS
    if turn_budget.time_budget_exhausted():
        return None
    capped = turn_budget.capped_hop_timeout_seconds(role=INVESTIGATION_PLAN_ROLE, min_seconds=1.0)
    if capped is None:
        return None
    return min(_PROPOSE_TIMEOUT_SECONDS, capped)


def propose_investigation_plan_llm(
    *,
    query: str,
    baseline: InvestigationPlan,
    llm_raw_output_provider: Any | None = None,
    turn_budget: Any | None = None,
    capability_ids: list[str] | None = None,
) -> InvestigationPlanLlmResult:
    """Invoke bounded LLM propose; caller runs Validator A on the returned proposal."""
    user_prompt = _build_user_prompt(
        query=query,
        baseline=baseline,
        capability_ids=list(capability_ids or []),
    )
    started = time.monotonic()
    circuit_state: str | None = None
    human_action_required = False
    failure_kind: str | None = None
    if llm_raw_output_provider is not None:
        raw_output = str(llm_raw_output_provider() or "")
        timed_out = False
        provider_label = "test_provider"
        attempted = True
        circuit_state = "test"
    else:
        hop_timeout = _hop_timeout_seconds(turn_budget)
        if hop_timeout is None:
            return InvestigationPlanLlmResult(
                raw_llm=None,
                proposal=None,
                attempted=False,
                timed_out=False,
                provider_label=None,
                dropped_reasons=["turn_budget_exhausted"],
                latency_ms=0,
                circuit_state=None,
            )
        invocation = invoke_sidecar_role_with_metadata(
            role=INVESTIGATION_PLAN_ROLE,
            user_prompt=user_prompt,
            # A case-grounded proposal is longer than the generic skeleton this
            # budget was sized for; at 700 the JSON object truncates mid-array and
            # the whole proposal is dropped as unparseable (measured).
            max_tokens=_PROPOSE_MAX_OUTPUT_TOKENS,
            timeout_seconds=hop_timeout,
            temperature=0.0,
            allow_failover=False,
        )
        raw_output = invocation.raw_output
        timed_out = invocation.timed_out
        provider_label = invocation.answered_label
        circuit_state = invocation.circuit_state
        human_action_required = invocation.human_action_required
        failure_kind = invocation.failure_kind
        attempted = raw_output is not None or timed_out or failure_kind is not None
        if not attempted:
            circuit_state = circuit_state or str(t4_circuit_status().get("state") or "")

    latency_ms = int((time.monotonic() - started) * 1000)

    if not attempted:
        return InvestigationPlanLlmResult(
            raw_llm=None,
            proposal=None,
            attempted=False,
            timed_out=False,
            provider_label=None,
            dropped_reasons=["llm_not_configured"],
            latency_ms=latency_ms,
            circuit_state=circuit_state,
            human_action_required=human_action_required,
            failure_kind=failure_kind,
        )

    if timed_out or not raw_output:
        return InvestigationPlanLlmResult(
            raw_llm=None,
            proposal=None,
            attempted=True,
            timed_out=timed_out,
            provider_label=provider_label,
            dropped_reasons=[
                "llm_timed_out" if timed_out else (failure_kind or "llm_empty_output")
            ],
            latency_ms=latency_ms,
            circuit_state=circuit_state,
            human_action_required=human_action_required,
            failure_kind=failure_kind,
        )

    pre = preprocess_llm_output(
        raw_output,
        INVESTIGATION_PLAN_SCHEMA,
        allow_retry=False,
        echo_of=None,
    )
    if pre.payload is None:
        return InvestigationPlanLlmResult(
            raw_llm=None,
            proposal=None,
            attempted=True,
            timed_out=False,
            provider_label=provider_label,
            dropped_reasons=["llm_json_parse_failed", pre.verdict, *pre.validation_errors],
            latency_ms=latency_ms,
            circuit_state=circuit_state,
            human_action_required=human_action_required,
            failure_kind=failure_kind,
        )

    payload = dict(pre.payload)
    normalized_payload = {
        key: payload.get(key)
        for key in InvestigationPlanProposalPayload.model_fields
        if key in payload
    }
    strict_payload = InvestigationPlanProposalPayload.model_validate(normalized_payload)
    payload.update(strict_payload.model_dump())
    proposal = _map_llm_payload_to_proposal(payload)
    trace_payload = {
        key: payload.get(key)
        for key in (
            "hypotheses",
            "evidence_needed",
            "data_categories",
            "discovery_needed",
            "read_only_tools",
            "safe_spl_templates",
            "spl_review_requested",
            "clarification_needed",
            "refinement_recommended",
            "dependencies",
            "conditions",
            "success_criteria",
        )
    }
    return InvestigationPlanLlmResult(
        raw_llm=trace_payload,
        proposal=proposal,
        attempted=True,
        timed_out=False,
        provider_label=provider_label,
        dropped_reasons=[],
        latency_ms=latency_ms,
        circuit_state=circuit_state,
        human_action_required=human_action_required,
        failure_kind=failure_kind,
    )


def sidecar_timeout_for_investigation_plan_role() -> float:
    return min(_PROPOSE_TIMEOUT_SECONDS, sidecar_timeout_seconds(INVESTIGATION_PLAN_ROLE))
