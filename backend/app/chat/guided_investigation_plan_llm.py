"""Bounded LLM InvestigationPlan propose for guided hybrid dispatch (REV4 batch 2 P9)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.chat.contracts.investigation_plan import InvestigationPlan
from app.llm.adapter.output_preprocessor import INVESTIGATION_PLAN_SCHEMA, preprocess_llm_output
from app.llm.sidecar_clients import invoke_sidecar_role, sidecar_timeout_seconds

INVESTIGATION_PLAN_ROLE = "guided_investigation_plan_proposer"
_PROPOSE_TIMEOUT_SECONDS = 15.0

INVESTIGATION_PLAN_PROPOSE_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "objectives": {"type": "array", "items": {"type": "string"}},
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


def _map_llm_payload_to_proposal(payload: dict[str, Any]) -> dict[str, Any]:
    objectives = payload.get("objectives")
    objective = None
    if isinstance(objectives, list) and objectives:
        objective = str(objectives[0] or "").strip() or None
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
    }
    if objective:
        proposal["investigation_objective"] = objective
    return proposal


def _build_user_prompt(*, query: str, baseline: InvestigationPlan) -> str:
    baseline_dump = baseline.model_dump()
    return (
        "Propose additional investigation-plan fields for an out-of-registry guided hunt. "
        "Return only valid JSON matching the schema. No markdown, no explanation outside JSON, "
        "no hidden reasoning, no scratchpad, no planning text, and no <think> tags. Do not emit "
        "raw SPL, execution flags, severity, route changes, or remediation actions. Use registry "
        "tool IDs for read_only_tools only.\n"
        f"QUERY: {query}\n"
        f"DETERMINISTIC_BASELINE:\n{json.dumps(baseline_dump, ensure_ascii=False)}"
    )


def propose_investigation_plan_llm(
    *,
    query: str,
    baseline: InvestigationPlan,
    llm_raw_output_provider: Any | None = None,
) -> InvestigationPlanLlmResult:
    """Invoke bounded LLM propose; caller runs Validator A on the returned proposal."""
    user_prompt = _build_user_prompt(query=query, baseline=baseline)
    if llm_raw_output_provider is not None:
        raw_output = str(llm_raw_output_provider() or "")
        timed_out = False
        provider_label = "test_provider"
        attempted = True
    else:
        raw_output, timed_out, provider_label = invoke_sidecar_role(
            role=INVESTIGATION_PLAN_ROLE,
            user_prompt=user_prompt,
            max_tokens=700,
            timeout_seconds=_PROPOSE_TIMEOUT_SECONDS,
            temperature=0.0,
            allow_failover=True,
        )
        attempted = raw_output is not None or timed_out

    if not attempted:
        return InvestigationPlanLlmResult(
            raw_llm=None,
            proposal=None,
            attempted=False,
            timed_out=False,
            provider_label=None,
            dropped_reasons=["llm_not_configured"],
        )

    if timed_out or not raw_output:
        return InvestigationPlanLlmResult(
            raw_llm=None,
            proposal=None,
            attempted=True,
            timed_out=timed_out,
            provider_label=provider_label,
            dropped_reasons=["llm_timed_out" if timed_out else "llm_empty_output"],
        )

    pre = preprocess_llm_output(
        raw_output,
        INVESTIGATION_PLAN_SCHEMA,
        allow_retry=False,
        echo_of=query,
    )
    if pre.payload is None:
        return InvestigationPlanLlmResult(
            raw_llm=None,
            proposal=None,
            attempted=True,
            timed_out=False,
            provider_label=provider_label,
            dropped_reasons=["llm_json_parse_failed", pre.verdict, *pre.validation_errors],
        )

    payload = dict(pre.payload)
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
        )
    }
    return InvestigationPlanLlmResult(
        raw_llm=trace_payload,
        proposal=proposal,
        attempted=True,
        timed_out=False,
        provider_label=provider_label,
        dropped_reasons=[],
    )


def sidecar_timeout_for_investigation_plan_role() -> float:
    return min(_PROPOSE_TIMEOUT_SECONDS, sidecar_timeout_seconds(INVESTIGATION_PLAN_ROLE))
