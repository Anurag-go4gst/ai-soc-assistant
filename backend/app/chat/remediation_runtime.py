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
from app.chat.investigation_shaped import investigation_outcome_applicable
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


def remediation_plan_eligible(state: dict[str, Any]) -> bool:
    """Allow a plan only for completed evidence-backed suspicious outcomes.

    Positive authority reuses InvestigationOutcome fields only:
    ``investigation_status == completed`` and ``disposition == suspicious``.
    ``suspicious`` is derived from obtained evidence ∧ live-result language ∧
    high severity — not from LLM prose and not from skill name alone.

    Final-RQC product applicability and knowledge-only answer mode are defensive
    vetoes. User-conditional predicate truth is a separate gate and cannot make
    an ineligible outcome eligible for a remediation plan.
    """
    if not settings.ai_soc_remediation_planner_enabled:
        return False
    outcome = _as_dict(state.get("investigation_outcome"))
    # InvestigationOutcome V2 packages investigation_status only when the Final RQC
    # is investigation-shaped. Non-investigation products (SPL authoring, etc.) must
    # not receive a remediation CTA merely because an outcome dict is present.
    if not outcome.get("investigation_status"):
        return False
    status = str(outcome.get("investigation_status") or "")
    if status != "completed":
        return False
    if str(outcome.get("disposition") or "") != "suspicious":
        return False
    if not list(outcome.get("evidence_refs") or []):
        return False
    context = state.get("context_sufficiency")
    if isinstance(context, dict) and str(context.get("answer_mode") or "") == "knowledge_only_answer":
        return False
    if not investigation_outcome_applicable(
        resolved_query_contract=state.get("resolved_query_contract"),
        intent_classification=(
            state.get("intent_classification")
            if isinstance(state.get("intent_classification"), dict)
            else None
        ),
        query_understanding=state.get("query_understanding"),
        evidence_plan=state.get("evidence_plan")
        if isinstance(state.get("evidence_plan"), dict)
        else None,
        context_sufficiency=context if isinstance(context, dict) else None,
    ):
        return False
    return True


def remediation_offer_cta_eligible(state: dict[str, Any]) -> bool:
    """Whether to ask to create a plan; distinct from plan eligibility itself."""
    outcome = _as_dict(state.get("investigation_outcome"))
    return remediation_plan_eligible(state) and bool(outcome.get("remediation_offer_required"))


def resolve_requested_conditional_actions(state: dict[str, Any]) -> dict[str, Any]:
    """Advance Final-RQC requested actions through deterministic predicate truth only."""
    rqc = _as_dict(state.get("resolved_query_contract"))
    raw_actions = rqc.get("requested_conditional_actions")
    if not isinstance(raw_actions, list):
        return state
    changed = False
    actions: list[dict[str, Any]] = []
    for raw in raw_actions:
        if not isinstance(raw, dict):
            continue
        action = dict(raw)
        lifecycle = str(action.get("lifecycle_state") or "REQUESTED")
        predicate_id = action.get("predicate_id")
        if predicate_id and lifecycle == "REQUESTED":
            lifecycle = "PENDING_CONDITION"
        if lifecycle == "PENDING_CONDITION" and _predicate_satisfied(
            str(predicate_id or ""),
            state=state,
        ):
            lifecycle = "ELIGIBLE"
        if lifecycle != action.get("lifecycle_state"):
            action["lifecycle_state"] = lifecycle
            changed = True
        actions.append(action)
    if not changed:
        return state
    return {
        **state,
        "resolved_query_contract": {
            **rqc,
            "requested_conditional_actions": actions,
        },
    }


def _predicate_satisfied(predicate_id: str, *, state: dict[str, Any]) -> bool:
    """Closed predicate vocabulary; unknown or incomplete inputs fail closed."""
    if predicate_id != "account_compromise_confirmed":
        return False
    outcome = _as_dict(state.get("investigation_outcome"))
    if (
        str(outcome.get("investigation_status") or "") != "completed"
        or str(outcome.get("disposition") or "") != "suspicious"
        or not list(outcome.get("evidence_refs") or [])
    ):
        return False
    gate = _as_dict(state.get("final_evidence_gate"))
    if (
        gate.get("allow_environment_fact_claims") is not True
        or int(gate.get("environment_evidence_count") or 0) < 1
        or str(gate.get("source_evidence_status") or "") != "collected"
    ):
        return False
    evidence = _as_dict(state.get("evidence_state"))
    if predicate_id not in {str(item) for item in evidence.get("obtained") or []}:
        return False
    for item in evidence.get("items") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("key") or "") != predicate_id or str(item.get("status") or "") != "obtained":
            continue
        provenance = str(item.get("provenance") or "").lower()
        scope = item.get("scope") if isinstance(item.get("scope"), dict) else {}
        if "mock" in provenance or "simulat" in provenance or scope.get("simulated") is True:
            return False
        asserted_refs = {str(ref) for ref in scope.get("evidence_refs") or []}
        if (
            str(scope.get("predicate_id") or "") != predicate_id
            or scope.get("predicate_value") is not True
            or not asserted_refs.intersection(str(ref) for ref in outcome.get("evidence_refs") or [])
        ):
            return False
        return True
    return False


def _requested_action(state: dict[str, Any], action_kind: str) -> dict[str, Any] | None:
    rqc = _as_dict(state.get("resolved_query_contract"))
    for action in rqc.get("requested_conditional_actions") or []:
        if isinstance(action, dict) and str(action.get("action_kind") or "") == action_kind:
            return action
    return None


def maybe_attach_remediation_offer(
    state: dict[str, Any],
    *,
    turn_budget: Any | None = None,
    raw_output_provider: Any | None = None,
) -> dict[str, Any]:
    """Resolve requested actions and attach the governed remediation surface."""
    state = resolve_requested_conditional_actions(state)
    existing = _as_dict(state.get("remediation_approval"))
    if existing.get("status"):
        return state
    if not remediation_plan_eligible(state):
        return state
    if _requested_action(state, "remediation") is not None:
        if turn_budget is None and raw_output_provider is None:
            plan = build_deterministic_remediation_plan(
                investigation_outcome=_as_dict(state.get("investigation_outcome")),
                capability_snapshot=state.get("capability_snapshot"),
            )
            trace = {
                "role": "remediation_planner",
                "authority": "advisory",
                "attempted": False,
                "skipped_reason": "automatic_requested_plan_uses_deterministic_baseline",
                "plan_source": plan.plan_source,
                "execution_authorized": False,
            }
        else:
            plan, trace = build_validated_remediation_plan(
                investigation_outcome=_as_dict(state.get("investigation_outcome")),
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
    if not remediation_offer_cta_eligible(state):
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


def _load_pending_plan(state: dict[str, Any]) -> ValidatedRemediationPlan | None:
    """The plan the analyst is looking at, which may have been shown on a prior turn."""
    approval_raw = _as_dict(state.get("remediation_approval"))
    plan_raw = approval_raw.get("validated_plan")
    if isinstance(plan_raw, dict):
        return ValidatedRemediationPlan.model_validate(plan_raw)
    session_id = state.get("session_id")
    if not session_id:
        return None
    from app.chat.session_store import get_session_pins

    pins = get_session_pins(str(session_id))
    pending = getattr(pins, "pending_remediation_plan", None) if pins is not None else None
    if not isinstance(pending, dict):
        return None
    try:
        return ValidatedRemediationPlan.model_validate(pending)
    except Exception:  # noqa: BLE001 - a stale/incompatible pin is simply absent
        return None


"""Persistence note.

The shown plan is **not** written to session pins from here. ``pins_from_pipeline_state``
rebuilds the whole pin record at the end of every turn, so a write from this module is
overwritten before the next turn ever sees it. That builder reads
``state["remediation_approval"]`` and carries the plan forward, which keeps a single
writer and makes Approve bind to exactly what Create showed.
"""


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
    plan = _load_pending_plan(state)

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
