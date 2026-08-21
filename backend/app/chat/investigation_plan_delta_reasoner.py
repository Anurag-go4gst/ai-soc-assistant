"""Bounded advisory PlanDelta reasoning role; deterministic validation is separate."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.chat.contracts.investigation_envelope import ApprovedInvestigationEnvelope
from app.chat.contracts.plan_delta import PlanDeltaProposal
from app.llm.adapter.json_extractor import extract_first_json_object
from app.llm.sidecar_clients import invoke_sidecar_role_with_metadata


PLAN_DELTA_ROLE = "plan_delta_reasoner"
_DELTA_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class PlanDeltaReasonerResult:
    proposal: dict[str, Any] | None
    trace: dict[str, Any]


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


def propose_plan_delta(
    *,
    envelope: ApprovedInvestigationEnvelope,
    missing_evidence: list[str],
    prior_revision_fingerprint: str | None = None,
    raw_output_provider: Any | None = None,
    turn_budget: Any | None = None,
) -> PlanDeltaReasonerResult:
    """Send only bounded vocabulary, never raw evidence, entities, or tool output."""
    prompt = json.dumps(
        {
            "missing_evidence_categories": missing_evidence[:16],
            "allowed_read_only_capabilities": envelope.allowed_read_only_capabilities[:32],
            "envelope_version": envelope.envelope_version,
            "instruction": (
                "Return one JSON PlanDelta proposal. Read-only only. A Splunk search must place "
                "candidate SPL in tool_arguments.query; it remains non-authoritative until deterministic "
                "validation and exact-call authorization. No writes, authorization, or hidden reasoning."
            ),
        },
        sort_keys=True,
    )
    if raw_output_provider is not None:
        raw = str(raw_output_provider() or "")
        trace = {"role": "plan_delta_reasoner", "provider": "test_provider", "authority": "advisory", "attempted": True}
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
            "attempted": bool(raw or invocation.timed_out or invocation.failure_kind),
            "timed_out": invocation.timed_out,
            "failure_kind": invocation.failure_kind,
        }
    extraction = extract_first_json_object(raw)
    if extraction.payload is None:
        return PlanDeltaReasonerResult(proposal=None, trace={**trace, "accepted": False})
    try:
        bound = {
            **extraction.payload,
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
        return PlanDeltaReasonerResult(proposal=None, trace={**trace, "accepted": False})
    return PlanDeltaReasonerResult(proposal=proposal, trace={**trace, "accepted": True})
