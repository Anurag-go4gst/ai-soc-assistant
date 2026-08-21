"""Bounded LLM InvestigationPlan propose for guided hybrid dispatch (REV4 batch 2 P9)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from app.chat.contracts.investigation_plan import InvestigationPlan
from app.llm.adapter.schemas import InvestigationPlanProposalPayload
from app.llm.adapter.output_preprocessor import INVESTIGATION_PLAN_SCHEMA, preprocess_llm_output
from app.llm.sidecar_clients import invoke_sidecar_role_with_metadata, sidecar_timeout_seconds
from app.llm.sidecar_governance import t4_circuit_status

INVESTIGATION_PLAN_ROLE = "investigation_planner"
_PROPOSE_TIMEOUT_SECONDS = 120.0

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
        # No case-specific capability vocabulary crosses the model boundary.
        "capability_requests": [],
    }
    if objective:
        proposal["investigation_objective"] = objective
    return proposal


def _build_user_prompt() -> str:
    return (
        "Propose a generic read-only SOC investigation-plan structure. No case data is supplied. "
        "Return only valid JSON matching the schema. No markdown, no explanation outside JSON, "
        "no hidden reasoning, no scratchpad, no planning text, and no <think> tags. Do not emit "
        "raw SPL, execution flags, severity, route changes, authorization, remediation actions, "
        "entities, targets, time scopes, environment metadata, source names, or tool names. "
        "capability_requests must be an empty list."
    )


def propose_investigation_plan_llm(
    *,
    query: str,
    baseline: InvestigationPlan,
    llm_raw_output_provider: Any | None = None,
) -> InvestigationPlanLlmResult:
    """Invoke bounded LLM propose; caller runs Validator A on the returned proposal."""
    user_prompt = _build_user_prompt()
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
        invocation = invoke_sidecar_role_with_metadata(
            role=INVESTIGATION_PLAN_ROLE,
            user_prompt=user_prompt,
            max_tokens=700,
            timeout_seconds=_PROPOSE_TIMEOUT_SECONDS,
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
