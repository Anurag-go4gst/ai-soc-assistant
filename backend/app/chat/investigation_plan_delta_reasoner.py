"""Bounded advisory PlanDelta reasoning role; deterministic validation is separate."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.chat.contracts.investigation_envelope import ApprovedInvestigationEnvelope
from app.chat.contracts.plan_delta import PlanDeltaProposal
from app.chat.hypothesis_assessment import (
    assessments_from_payload,
    ledger_for_prompt,
    validate_advisory_assessments,
)
from app.evidence.governed_reasoning_context import project_source_evidence_for_reasoning
from app.llm.adapter.json_extractor import extract_first_json_object
from app.llm.sidecar_clients import invoke_sidecar_role_with_metadata


PLAN_DELTA_ROLE = "plan_delta_reasoner"
_DELTA_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class PlanDeltaReasonerResult:
    proposal: dict[str, Any] | None
    trace: dict[str, Any]
    hypothesis_assessments: dict[str, Any] | None = None


def _delta_hop_timeout_seconds(turn_budget: Any | None) -> float | None:
    """Cap the PlanDelta hop to the turn's remaining wall time (None = skip)."""
    if turn_budget is None:
        return _DELTA_TIMEOUT_SECONDS
    if turn_budget.time_budget_exhausted():
        return None
    capped = turn_budget.capped_hop_timeout_seconds(role=PLAN_DELTA_ROLE, min_seconds=1.0)
    if capped is None:
        return None
    return min(_DELTA_TIMEOUT_SECONDS, capped)


def _prompt_entity_value(value: Any) -> str | None:
    if isinstance(value, (list, tuple)):
        value = next((item for item in value if str(item).strip()), None)
    text = str(value).strip() if value is not None else ""
    return text[:80] if text else None


def build_plan_delta_reasoner_prompt(
    *,
    envelope: ApprovedInvestigationEnvelope,
    missing_evidence: list[str],
    source_evidence: list[dict[str, Any]] | None = None,
    hypotheses: list[str] | None = None,
    prior_assessments: dict[str, Any] | None = None,
) -> str:
    """Bounded PlanDelta prompt: missing categories, hypotheses, admitted SourceEvidence."""
    projected = project_source_evidence_for_reasoning(source_evidence)
    return json.dumps(
        {
            "missing_evidence_categories": missing_evidence[:16],
            "allowed_read_only_capabilities": envelope.allowed_read_only_capabilities[:32],
            "envelope_version": envelope.envelope_version,
            "entities": {
                str(key)[:40]: flattened
                for key, value in list(envelope.entities.items())[:16]
                if (flattened := _prompt_entity_value(value))
            },
            "time_scope": envelope.time_scope,
            "source_index_scope": {
                str(key)[:40]: [str(item)[:80] for item in (values or [])[:8]]
                for key, values in list(envelope.source_index_scope.items())[:8]
            },
            "current_hypotheses": ledger_for_prompt(list(hypotheses or []), prior_assessments),
            "admitted_environment_evidence": projected["admitted_environment_evidence"],
            "rag_guidance": projected["rag_guidance"],
            "failed_tool_observations": projected["failed_tool_observations"],
            "instruction": (
                "Return one JSON PlanDelta proposal AND hypothesis_assessments. Reason over "
                "admitted environment evidence, current_hypotheses, and missing categories. "
                "Assess each hypothesis as supported, unconfirmed, or weakened using only "
                "admitted environment evidence_id values; RAG, user claims, and failed tools "
                "cannot support or weaken; absence of evidence is not contradiction. Choose "
                "evidence_need from missing_evidence_categories that most reduces remaining "
                "material uncertainty AFTER those assessments. Failed tool observations are "
                "not negative findings. Read-only only. A Splunk search must place candidate "
                "SPL in tool_arguments.query; it remains non-authoritative until deterministic "
                "validation and exact-call authorization. No writes, authorization, or hidden "
                "reasoning."
            ),
        },
        sort_keys=True,
    )


def _assessments_from_raw(
    *,
    payload: dict[str, Any] | None,
    hypotheses: list[str] | None,
    source_evidence: list[dict[str, Any]] | None,
    prior_assessments: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not hypotheses:
        return None
    return validate_advisory_assessments(
        hypotheses=hypotheses,
        advisory=assessments_from_payload(payload),
        source_evidence=source_evidence,
        prior=prior_assessments,
    )


def propose_plan_delta(
    *,
    envelope: ApprovedInvestigationEnvelope,
    missing_evidence: list[str],
    prior_revision_fingerprint: str | None = None,
    raw_output_provider: Any | None = None,
    turn_budget: Any | None = None,
    source_evidence: list[dict[str, Any]] | None = None,
    hypotheses: list[str] | None = None,
    prior_assessments: dict[str, Any] | None = None,
) -> PlanDeltaReasonerResult:
    """Send bounded vocabulary plus admitted SourceEvidence summaries, never raw rows."""
    prompt = build_plan_delta_reasoner_prompt(
        envelope=envelope,
        missing_evidence=missing_evidence,
        source_evidence=source_evidence,
        hypotheses=hypotheses,
        prior_assessments=prior_assessments,
    )
    projected = project_source_evidence_for_reasoning(source_evidence)
    context_meta = {
        "admitted_environment_evidence_count": len(projected["admitted_environment_evidence"]),
        "rag_guidance_count": len(projected["rag_guidance"]),
        "raw_rows_sent": False,
    }
    if raw_output_provider is not None:
        raw = str(raw_output_provider() or "")
        trace = {
            "role": "plan_delta_reasoner",
            "provider": "test_provider",
            "authority": "advisory",
            "attempted": True,
            **context_meta,
        }
    else:
        hop_timeout = _delta_hop_timeout_seconds(turn_budget)
        if hop_timeout is None:
            return PlanDeltaReasonerResult(
                proposal=None,
                trace={
                    "role": PLAN_DELTA_ROLE,
                    "provider": None,
                    "authority": "advisory",
                    "attempted": False,
                    "skipped_reason": "turn_budget_exhausted",
                    "accepted": False,
                },
                hypothesis_assessments=_assessments_from_raw(
                    payload=None,
                    hypotheses=hypotheses,
                    source_evidence=source_evidence,
                    prior_assessments=prior_assessments,
                ),
            )
        invocation = invoke_sidecar_role_with_metadata(
            role=PLAN_DELTA_ROLE,
            user_prompt=prompt,
            max_tokens=700,
            timeout_seconds=hop_timeout,
            temperature=0.0,
            allow_failover=False,
        )
        raw = str(invocation.raw_output or "")
        trace = {
            "role": "plan_delta_reasoner",
            "provider": invocation.answered_label,
            "authority": "advisory",
            # The hop WAS attempted: control reached the sidecar invocation.
            # Deriving this from the output conflated "no call" with "call that
            # returned nothing", and hid a real LLM hop from turn accounting.
            "attempted": True,
            "empty_output": not raw,
            "timed_out": invocation.timed_out,
            "failure_kind": invocation.failure_kind,
            **context_meta,
        }
    extraction = extract_first_json_object(raw)
    assessments = _assessments_from_raw(
        payload=extraction.payload,
        hypotheses=hypotheses,
        source_evidence=source_evidence,
        prior_assessments=prior_assessments,
    )
    if extraction.payload is None:
        return PlanDeltaReasonerResult(
            proposal=None,
            trace={**trace, "accepted": False},
            hypothesis_assessments=assessments,
        )
    try:
        payload = dict(extraction.payload)
        payload.pop("hypothesis_assessments", None)
        bound = {
            **payload,
            "envelope_version": envelope.envelope_version,
            "prior_revision_fingerprint": prior_revision_fingerprint,
            "objective": envelope.objective,
            "targets": list(envelope.targets),
            "entities": dict(envelope.entities),
            "time_scope": envelope.time_scope,
            "source_index_scope": dict(envelope.source_index_scope),
        }
        proposal = PlanDeltaProposal.model_validate(bound).model_dump(mode="json")
    except Exception:
        return PlanDeltaReasonerResult(
            proposal=None,
            trace={**trace, "accepted": False},
            hypothesis_assessments=assessments,
        )
    return PlanDeltaReasonerResult(
        proposal=proposal,
        trace={**trace, "accepted": True},
        hypothesis_assessments=assessments,
    )
