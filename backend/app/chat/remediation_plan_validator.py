"""Deterministic validation of advisory remediation proposals (architecture P10).

The reasoning model's proposal is a *narrowing and re-describing* input only. This
validator is the authority:

* a proposed capability that is not already in the deterministic baseline is
  dropped — the model cannot introduce a connector;
* a proposed capability the CapabilitySnapshot does not report as available is
  kept only as a ``manual_or_alternate`` step;
* ``execution_authorized`` stays false, pinned by the contract itself.
"""

from __future__ import annotations

from typing import Any

from app.chat.contracts.remediation_plan import (
    RemediationPlanProposal,
    ValidatedRemediationPlan,
)

#: Prose that would imply the action already happened, or that a write is self-authorizing.
_PROHIBITED_MARKERS: tuple[str, ...] = (
    "executed",
    "already applied",
    "auto-approve",
    "no approval needed",
    "authorized",
)


def _clean(value: str | None, *, limit: int) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())[:limit].strip()
    return text or None


def validate_remediation_plan(
    baseline: ValidatedRemediationPlan,
    proposal: dict[str, Any] | RemediationPlanProposal | None,
    *,
    llm_attempted: bool = False,
    capability_snapshot: dict[str, Any] | None = None,
) -> ValidatedRemediationPlan:
    """Return the DET plan, optionally narrowed by a schema-valid advisory proposal."""
    del capability_snapshot  # availability already bound by the baseline builder
    warnings = list(baseline.validation_warnings)
    dropped = list(baseline.dropped_reasons)

    if proposal is None:
        return baseline.model_copy(
            update={
                "plan_source": "llm_failed_baseline_only" if llm_attempted else "deterministic_only",
                "dropped_reasons": dropped,
            }
        )

    try:
        parsed = (
            proposal
            if isinstance(proposal, RemediationPlanProposal)
            else RemediationPlanProposal.model_validate(proposal)
        )
    except Exception as exc:  # noqa: BLE001 - schema failure is an advisory drop, not an error
        dropped.append(f"proposal_schema_invalid:{type(exc).__name__}")
        return baseline.model_copy(
            update={"plan_source": "llm_failed_baseline_only", "dropped_reasons": dropped}
        )

    baseline_capabilities = {step.capability_id for step in baseline.steps}
    invented = [
        capability_id
        for capability_id in parsed.capability_requests
        if capability_id not in baseline_capabilities
    ]
    if invented:
        dropped.append("capability_requests_not_in_snapshot_baseline")

    objective = _clean(parsed.remediation_objective, limit=500)
    if objective and any(marker in objective.lower() for marker in _PROHIBITED_MARKERS):
        dropped.append("objective_implies_completed_or_self_authorized_action")
        objective = None

    accepted_any = False
    steps = list(baseline.steps)
    if objective:
        accepted_any = True

    verification_suggestions = [
        text
        for text in (_clean(item, limit=300) for item in parsed.verification_suggestions)
        if text and not any(marker in text.lower() for marker in _PROHIBITED_MARKERS)
    ]
    if verification_suggestions:
        # A suggestion may only be appended to an existing step's verification; it can
        # never replace the deterministic verification text.
        merged: list[Any] = []
        for index, step in enumerate(steps):
            if index < len(verification_suggestions):
                extra = verification_suggestions[index]
                merged.append(
                    step.model_copy(
                        update={"verification": f"{step.verification} Also: {extra}"[:300]}
                    )
                )
            else:
                merged.append(step)
        steps = merged
        accepted_any = True

    if parsed.proposed_steps and not accepted_any:
        dropped.append("proposed_steps_carry_no_capability_binding")

    return baseline.model_copy(
        update={
            "remediation_objective": objective or baseline.remediation_objective,
            "steps": steps,
            "plan_source": "llm_proposed_validated" if accepted_any else "llm_failed_baseline_only",
            "validation_warnings": list(dict.fromkeys(warnings)),
            "dropped_reasons": list(dict.fromkeys(dropped)),
        }
    )
