"""Bounded advisory ``remediation_planner`` role (architecture P10).

Sends only planning vocabulary — capability identifiers already present in the
deterministic baseline, plus the governed disposition. No raw evidence, entities,
tool output, SPL, or hidden reasoning crosses this boundary, and the returned
proposal is advisory: :mod:`app.chat.remediation_plan_validator` decides.

Like the P3/P7 hops, this one is bounded by the turn wall clock so an absent or
very slow reasoning endpoint degrades to the deterministic baseline instead of
stalling ``/chat``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from app.chat.contracts.remediation_plan import ValidatedRemediationPlan
from app.llm.adapter.json_extractor import extract_first_json_object
from app.llm.sidecar_clients import invoke_sidecar_role_with_metadata

REMEDIATION_PLAN_ROLE = "remediation_planner"
_REMEDIATION_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class RemediationReasonerResult:
    proposal: dict[str, Any] | None
    attempted: bool = False
    trace: dict[str, Any] = field(default_factory=dict)


def _hop_timeout_seconds(turn_budget: Any | None) -> float | None:
    if turn_budget is None:
        return _REMEDIATION_TIMEOUT_SECONDS
    if turn_budget.time_budget_exhausted():
        return None
    capped = turn_budget.capped_hop_timeout_seconds(role=REMEDIATION_PLAN_ROLE, min_seconds=1.0)
    if capped is None:
        return None
    return min(_REMEDIATION_TIMEOUT_SECONDS, capped)


def _build_prompt(baseline: ValidatedRemediationPlan) -> str:
    return json.dumps(
        {
            "disposition": baseline.derived_from_disposition,
            "investigation_status": baseline.derived_from_investigation_status,
            "available_capability_ids": [
                step.capability_id for step in baseline.steps if step.execution_mode == "execute"
            ],
            "manual_capability_ids": [
                step.capability_id
                for step in baseline.steps
                if step.execution_mode == "manual_or_alternate"
            ],
            "instruction": (
                "Return one JSON RemediationPlanProposal. You may only re-describe or "
                "narrow the supplied capabilities; never introduce a new one, never claim "
                "an action ran, and never assert authorization. No hidden reasoning."
            ),
        },
        sort_keys=True,
    )


def propose_remediation_plan(
    *,
    baseline: ValidatedRemediationPlan,
    raw_output_provider: Any | None = None,
    turn_budget: Any | None = None,
) -> RemediationReasonerResult:
    """Invoke the bounded remediation reasoning hop; the caller runs DET validation."""
    if raw_output_provider is not None:
        raw = str(raw_output_provider() or "")
        trace: dict[str, Any] = {
            "role": REMEDIATION_PLAN_ROLE,
            "authority": "advisory",
            "provider": "test_provider",
            "attempted": True,
        }
    else:
        hop_timeout = _hop_timeout_seconds(turn_budget)
        if hop_timeout is None:
            return RemediationReasonerResult(
                proposal=None,
                attempted=False,
                trace={
                    "role": REMEDIATION_PLAN_ROLE,
                    "authority": "advisory",
                    "provider": None,
                    "attempted": False,
                    "skipped_reason": "turn_budget_exhausted",
                },
            )
        invocation = invoke_sidecar_role_with_metadata(
            role=REMEDIATION_PLAN_ROLE,
            user_prompt=_build_prompt(baseline),
            max_tokens=600,
            timeout_seconds=hop_timeout,
            temperature=0.0,
            allow_failover=False,
        )
        raw = str(invocation.raw_output or "")
        trace = {
            "role": REMEDIATION_PLAN_ROLE,
            "authority": "advisory",
            "provider": invocation.answered_label,
            "attempted": bool(raw or invocation.timed_out or invocation.failure_kind),
            "timed_out": invocation.timed_out,
            "failure_kind": invocation.failure_kind,
            "latency_ms": invocation.latency_ms,
            "circuit_state": invocation.circuit_state,
            "case_data_sent_to_model": False,
        }

    extraction = extract_first_json_object(raw)
    if extraction.payload is None:
        return RemediationReasonerResult(
            proposal=None,
            attempted=bool(trace.get("attempted")),
            trace={**trace, "accepted": False},
        )
    return RemediationReasonerResult(
        proposal=dict(extraction.payload),
        attempted=True,
        trace={**trace, "accepted": True},
    )
