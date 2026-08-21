"""Deterministic remediation baseline (architecture P10).

Builds a :class:`ValidatedRemediationPlan` skeleton from the governed
``InvestigationOutcome`` and the ``CapabilitySnapshot``. The reasoning model never
supplies the capability set — it may only re-describe or narrow what this builder
already found, through the validator.

Availability is honest in both directions: an action whose connector is not
registered stays in the plan as a ``manual_or_alternate`` step with a reason, so
the analyst sees what still needs doing by hand rather than a silently shorter
plan.
"""

from __future__ import annotations

from typing import Any

from app.actions.capability_policy import BLOCKED_EXECUTION_ACTIONS
from app.chat.contracts.remediation_plan import (
    RemediationStep,
    ValidatedRemediationPlan,
)

#: Deterministic verification text per known action kind. A capability with no
#: entry still gets a generic governed verification line — never an empty one.
_VERIFICATION_BY_CAPABILITY: dict[str, str] = {
    "email_send": "Confirm the send receipt and the recipient allowlist entry.",
    "firewall_block": "Re-query the firewall policy for the rule and confirm it is active.",
    "block_ip": "Re-query the blocking control for the indicator and confirm the deny rule.",
    "disable_user": "Confirm the account state is disabled in the identity source.",
    "isolate_endpoint": "Confirm the endpoint reports an isolated state in the EDR console.",
    "create_ticket": "Confirm the ticket exists and carries the investigation reference.",
    "containment": "Confirm each containment control reports the expected post-action state.",
    "close_incident": "Confirm the incident record state and the closing note.",
}

_GENERIC_VERIFICATION = "Confirm the post-action state through the owning system before closing."

#: Actions that change state irreversibly enough that rollback must be explicit.
_REVERSIBLE_CAPABILITIES: frozenset[str] = frozenset(
    {"block_ip", "firewall_block", "disable_user", "isolate_endpoint", "containment"}
)


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    dump = getattr(value, "model_dump", None)
    payload = dump(mode="json") if callable(dump) else {}
    return dict(payload) if isinstance(payload, dict) else {}


def _snapshot_availability(snapshot: dict[str, Any]) -> dict[str, str]:
    rows = snapshot.get("rows") if isinstance(snapshot, dict) else None
    availability: dict[str, str] = {}
    for row in rows or []:
        if isinstance(row, dict) and row.get("capability_id"):
            availability[str(row["capability_id"])] = str(row.get("availability") or "unavailable")
    return availability


def _objective(outcome: dict[str, Any]) -> str:
    disposition = str(outcome.get("disposition") or "inconclusive")
    severity = str(outcome.get("severity_label") or "").strip()
    suffix = f" ({severity})" if severity else ""
    if disposition == "suspicious":
        return f"Contain and remediate the confirmed suspicious activity{suffix}."
    if disposition == "benign":
        return f"Record the benign determination and close out residual risk{suffix}."
    return f"Reduce risk from the inconclusive investigation result{suffix}."


def _step(
    *,
    index: int,
    capability_id: str,
    availability: str,
    unavailable_reason: str | None,
) -> RemediationStep:
    executable = availability == "available" and capability_id not in BLOCKED_EXECUTION_ACTIONS
    return RemediationStep(
        step_id=f"rem.{index:02d}.{capability_id}",
        capability_id=capability_id,
        description=(
            f"Perform {capability_id.replace('_', ' ')} through the registered connector."
            if executable
            else f"Perform {capability_id.replace('_', ' ')} manually or through an alternate path."
        ),
        execution_mode="execute" if executable else "manual_or_alternate",
        availability="available" if availability == "available" else "unavailable",
        reversible=capability_id in _REVERSIBLE_CAPABILITIES,
        verification=_VERIFICATION_BY_CAPABILITY.get(capability_id, _GENERIC_VERIFICATION),
        unavailable_reason=unavailable_reason,
    )


def build_deterministic_remediation_plan(
    *,
    investigation_outcome: dict[str, Any] | Any,
    capability_snapshot: dict[str, Any] | Any | None = None,
) -> ValidatedRemediationPlan:
    """Project the governed outcome + snapshot onto a deterministic remediation plan."""
    outcome = _as_dict(investigation_outcome)
    snapshot = _as_dict(capability_snapshot)
    availability = _snapshot_availability(snapshot)
    eligibility = _as_dict(outcome.get("action_eligibility"))

    allowed = [str(item) for item in eligibility.get("allowed_actions") or []]
    unavailable = [str(item) for item in eligibility.get("unavailable_actions") or []]

    steps: list[RemediationStep] = []
    manual_only: list[str] = []
    warnings: list[str] = []
    seen: set[str] = set()

    for capability_id in allowed:
        if capability_id in seen:
            continue
        seen.add(capability_id)
        row_availability = availability.get(capability_id)
        if capability_id in BLOCKED_EXECUTION_ACTIONS:
            reason = "action_blocked_by_execution_policy"
        elif row_availability is None:
            reason = "capability_not_registered"
        elif row_availability != "available":
            reason = "capability_unavailable_in_snapshot"
        else:
            reason = None
        step = _step(
            index=len(steps) + 1,
            capability_id=capability_id,
            availability=row_availability or "unavailable",
            unavailable_reason=reason,
        )
        steps.append(step)
        if step.execution_mode == "manual_or_alternate":
            manual_only.append(step.step_id)

    for capability_id in unavailable:
        if capability_id in seen:
            continue
        seen.add(capability_id)
        step = _step(
            index=len(steps) + 1,
            capability_id=capability_id,
            availability="unavailable",
            unavailable_reason="capability_reported_unavailable_by_policy",
        )
        steps.append(step)
        manual_only.append(step.step_id)

    if not steps:
        warnings.append("no_registered_or_policy_eligible_remediation_capability")

    return ValidatedRemediationPlan(
        remediation_objective=_objective(outcome),
        steps=steps,
        manual_only_steps=manual_only,
        plan_source="deterministic_only",
        validation_warnings=warnings,
        derived_from_investigation_status=(
            str(outcome["investigation_status"]) if outcome.get("investigation_status") else None
        ),
        derived_from_disposition=(
            str(outcome["disposition"]) if outcome.get("disposition") else None
        ),
    )
