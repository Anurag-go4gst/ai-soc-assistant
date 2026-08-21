"""P10 remediation lifecycle seam: outcome -> offer -> plan -> Approve/Edit/Cancel.

Attaches the remediation offer and, once the analyst asks for one, a deterministic
``ValidatedRemediationPlan`` optionally narrowed by the advisory ``remediation_planner``
role. Nothing here executes: the approved envelope is the *input* to P11 connector
execution, never the authorization itself.

Three rules this module exists to enforce:

* no side effect before approval — ``execution_authorized`` is pinned false and no
  connector is imported here at all;
* the redundant-ask rule from P8 — if the Final RQC already requested contingent
  remediation, the offer is not repeated once the condition is satisfied;
* an unavailable connector yields a manual step, never a dropped step and never a
  claimed success.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.chat.contracts.remediation_plan import (
    ApprovedRemediationEnvelope,
    RemediationApprovalState,
    RemediationPlanEdits,
    RemediationPlanSummary,
    ValidatedRemediationPlan,
)
from app.chat.remediation_plan_builder import build_deterministic_remediation_plan
from app.chat.remediation_plan_validator import validate_remediation_plan
from app.config import settings

_MESSAGES: dict[str, str] = {
    "offered": "Investigation complete. Create a remediation plan?",
    "awaiting_approval": "Remediation plan ready. Review what changes, then Approve, Edit, or Cancel.",
    "edited_revalidated": "Edited remediation plan revalidated. Review it before approving.",
    "approved": "Remediation plan approved. Execution remains governed by the action gate and per-connector policy.",
    "cancelled": "Remediation cancelled. No connector was called and nothing was changed.",
    "declined": "No remediation plan created. The investigation result stands on its own.",
}


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    dump = getattr(value, "model_dump", None)
    payload = dump(mode="json") if callable(dump) else {}
    return dict(payload) if isinstance(payload, dict) else {}


def _fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_remediation_summary(plan: ValidatedRemediationPlan) -> RemediationPlanSummary:
    """Human-readable card. Manual steps are surfaced, not hidden."""
    executable = [step for step in plan.steps if step.execution_mode == "execute"]
    manual = [step for step in plan.steps if step.execution_mode == "manual_or_alternate"]
    return RemediationPlanSummary(
        what_will_change=[f"{step.description}" for step in executable[:16]]
        or ["No registered connector can perform this remediation automatically."],
        why_it_matters=plan.remediation_objective,
        what_stays_manual=[
            f"{step.description} ({step.unavailable_reason or 'no registered connector'})"
            for step in manual[:16]
        ],
        how_it_is_verified=[f"{step.step_id}: {step.verification}" for step in plan.steps[:16]],
    )


def _approval_state(
    *,
    status: str,
    plan: ValidatedRemediationPlan | None,
    envelope: ApprovedRemediationEnvelope | None = None,
    warnings: list[str] | None = None,
    handoff_id: str | None = None,
    handoff_version: int | None = None,
) -> RemediationApprovalState:
    if status == "offered":
        actions: list[str] = ["create", "decline"]
    elif status in {"awaiting_approval", "edited_revalidated"}:
        actions = ["approve", "edit", "cancel"]
    else:
        actions = []
    return RemediationApprovalState(
        status=status,  # type: ignore[arg-type]
        handoff_id=handoff_id,
        handoff_version=handoff_version,
        allowed_actions=actions,  # type: ignore[arg-type]
        plan_summary=build_remediation_summary(plan) if plan is not None else None,
        validated_plan=plan.model_dump(mode="json") if plan is not None else None,
        approved_envelope=envelope,
        safe_message=_MESSAGES[status],
        revalidation_warnings=list(warnings or []),
    )


def build_validated_remediation_plan(
    *,
    investigation_outcome: dict[str, Any],
    capability_snapshot: dict[str, Any] | None,
    turn_budget: Any | None = None,
    raw_output_provider: Any | None = None,
) -> tuple[ValidatedRemediationPlan, dict[str, Any]]:
    """Deterministic baseline, optionally narrowed by the advisory reasoning hop."""
    baseline = build_deterministic_remediation_plan(
        investigation_outcome=investigation_outcome,
        capability_snapshot=capability_snapshot,
    )
    if not settings.ai_soc_remediation_planner_enabled:
        trace = {
            "role": "remediation_planner",
            "authority": "advisory",
            "attempted": False,
            "skipped_reason": "remediation_planner_disabled",
        }
        return baseline, trace

    from app.chat.remediation_plan_reasoner import propose_remediation_plan

    result = propose_remediation_plan(
        baseline=baseline,
        raw_output_provider=raw_output_provider,
        turn_budget=turn_budget,
    )
    validated = validate_remediation_plan(
        baseline,
        result.proposal,
        llm_attempted=result.attempted,
    )
    trace = {
        **result.trace,
        "plan_source": validated.plan_source,
        "dropped_reasons": list(validated.dropped_reasons),
        "execution_authorized": False,
    }
    return validated, trace


def maybe_attach_remediation_offer(state: dict[str, Any]) -> dict[str, Any]:
    """Attach the P8 remediation offer as a P10 affordance. No plan is built yet."""
    if not settings.ai_soc_remediation_planner_enabled:
        return state
    outcome = _as_dict(state.get("investigation_outcome"))
    if not outcome.get("remediation_offer_required"):
        return state
    if str(outcome.get("investigation_status") or "") == "cancelled":
        return state
    approval = _approval_state(status="offered", plan=None)
    return {**state, "remediation_approval": approval.model_dump(mode="json")}


def _apply_edits(
    plan: ValidatedRemediationPlan,
    edits: RemediationPlanEdits,
) -> tuple[ValidatedRemediationPlan, list[str]]:
    warnings: list[str] = ["analyst_edit_revalidated"]
    removed = set(edits.removed_step_ids)
    steps = []
    for step in plan.steps:
        if step.step_id in removed:
            continue
        description = edits.step_descriptions.get(step.step_id)
        if description:
            steps.append(step.model_copy(update={"description": " ".join(description.split())[:500]}))
        else:
            steps.append(step)
    if removed and len(steps) == len(plan.steps):
        warnings.append("removed_step_ids_matched_nothing")
    unknown = set(edits.step_descriptions) - {step.step_id for step in plan.steps}
    if unknown:
        warnings.append("edit_referenced_unknown_step_ids")
    objective = edits.remediation_objective or plan.remediation_objective
    edited = plan.model_copy(
        update={
            "remediation_objective": " ".join(str(objective).split())[:500],
            "steps": steps,
            "manual_only_steps": [
                step.step_id for step in steps if step.execution_mode == "manual_or_alternate"
            ],
            "validation_warnings": list(dict.fromkeys([*plan.validation_warnings, *warnings])),
        }
    )
    return edited, warnings


def handle_remediation_review(
    state: dict[str, Any],
    *,
    action: str,
    edits: dict[str, Any] | None = None,
    turn_budget: Any | None = None,
    raw_output_provider: Any | None = None,
) -> dict[str, Any]:
    """Advance the remediation HIL. ``approve`` yields an envelope, never a call."""
    normalized = str(action or "").strip().lower()
    outcome = _as_dict(state.get("investigation_outcome"))
    approval_raw = _as_dict(state.get("remediation_approval"))
    plan_raw = approval_raw.get("validated_plan")
    plan = (
        ValidatedRemediationPlan.model_validate(plan_raw) if isinstance(plan_raw, dict) else None
    )

    if normalized == "decline":
        approval = _approval_state(status="declined", plan=None)
    elif normalized == "cancel":
        approval = _approval_state(status="cancelled", plan=plan)
    elif normalized == "create":
        plan, trace = build_validated_remediation_plan(
            investigation_outcome=outcome,
            capability_snapshot=state.get("capability_snapshot"),
            turn_budget=turn_budget,
            raw_output_provider=raw_output_provider,
        )
        approval = _approval_state(status="awaiting_approval", plan=plan)
        return {
            **state,
            "remediation_approval": approval.model_dump(mode="json"),
            "remediation_planning_trace": trace,
        }
    elif normalized == "edit":
        if plan is None:
            raise ValueError("remediation_plan_missing_for_edit")
        edited, warnings = _apply_edits(plan, RemediationPlanEdits.model_validate(edits or {}))
        approval = _approval_state(
            status="edited_revalidated",
            plan=edited,
            warnings=warnings,
        )
    elif normalized == "approve":
        if plan is None:
            raise ValueError("remediation_plan_missing_for_approval")
        prior_version = int(approval_raw.get("envelope_version") or 0)
        envelope = ApprovedRemediationEnvelope(
            envelope_version=max(1, prior_version + 1),
            remediation_objective=plan.remediation_objective,
            approved_steps=list(plan.steps),
            plan_fingerprint=_fingerprint(plan.model_dump(mode="json")),
            investigation_envelope_version=(
                int(_as_dict(state.get("approved_investigation_envelope")).get("envelope_version"))
                if _as_dict(state.get("approved_investigation_envelope")).get("envelope_version")
                else None
            ),
        )
        approval = _approval_state(status="approved", plan=plan, envelope=envelope)
        return {
            **state,
            "remediation_approval": approval.model_dump(mode="json"),
            "approved_remediation_envelope": envelope.model_dump(mode="json"),
        }
    else:
        raise ValueError("unsupported_remediation_review_action")

    return {**state, "remediation_approval": approval.model_dump(mode="json")}
