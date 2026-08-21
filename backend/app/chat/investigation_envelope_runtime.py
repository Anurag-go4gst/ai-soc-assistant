"""P4 deterministic Run/Edit/Cancel handling for investigation plans."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg

from app.chat.canonical_db import run_in_canonical_unit_of_work
from app.chat.canonical_handoff_models import CanonicalHandoffRecord
from app.chat.canonical_handoff_repository import (
    fetch_handoff_record,
    handoff_record_from_row,
    in_memory_handoff_store_enabled,
    load_pending_for_update,
    memory_handoff_lock,
    persist_handoff_record,
    test_store_read,
    test_store_write,
)
from app.chat.canonical_handoff_store import commit_resource_plan, get_handoff, save_handoff
from app.chat.contracts.canonical_planning_outcome import awaiting_investigation_plan_outcome, planned_outcome
from app.chat.contracts.investigation_envelope import (
    ApprovedInvestigationEnvelope,
    InvestigationApprovalState,
    InvestigationPlanEdits,
    InvestigationPlanSummary,
)
from app.chat.contracts.investigation_plan import InvestigationPlan, ValidatedInvestigationPlan
from app.chat.guided_investigation_planner import validate_investigation_plan
from app.config import settings

_HIL_KEY = "investigation_hil"
_DECISION_KEY = "investigation_decision"


class InvestigationEnvelopeError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class _AdvanceResult:
    record: CanonicalHandoffRecord
    idempotent_replay: bool = False


def _fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    dump = getattr(value, "model_dump", None)
    payload = dump(mode="json") if callable(dump) else {}
    return dict(payload) if isinstance(payload, dict) else {}


def _targets(entities: dict[str, Any]) -> list[str]:
    targets: list[str] = []
    for key, raw in sorted(entities.items()):
        values = raw if isinstance(raw, list) else [raw]
        for value in values:
            text = str(value or "").strip()
            if text:
                targets.append(f"{key}:{text}")
    return targets[:64]


def _source_index_scope(rqc: dict[str, Any]) -> dict[str, list[str]]:
    scope: dict[str, list[str]] = {}
    provenance = _as_dict(rqc.get("provenance"))
    for key in ("indexes", "sourcetypes", "sources"):
        raw = rqc.get(key, provenance.get(key))
        values = raw if isinstance(raw, list) else [raw] if raw else []
        normalized = [str(value).strip() for value in values if str(value or "").strip()]
        if normalized:
            scope[key] = list(dict.fromkeys(normalized))[:32]
    return scope


def build_plan_summary(
    plan: ValidatedInvestigationPlan,
    rqc: dict[str, Any],
) -> InvestigationPlanSummary:
    entities = _as_dict(rqc.get("entities"))
    scope = [f"Target: {item}" for item in _targets(entities)]
    if rqc.get("time_scope"):
        scope.append(f"Time: {str(rqc['time_scope'])[:240]}")
    resources = [
        (
            f"{binding.capability_id} — {binding.capability_need}, "
            f"{binding.availability}, {binding.access_mode}"
        )
        for binding in plan.capability_bindings[:16]
    ]
    resources.extend(f"Source: {source}" for source in plan.candidate_sources[:8])
    return InvestigationPlanSummary(
        what_will_be_checked=list(plan.evidence_needed[:10])
        or ["Collect governed evidence or record an explicit evidence gap."],
        why_it_matters=plan.investigation_objective,
        scope_and_time=scope or ["Scope is bound to the approved Final RQC."],
        resources_and_capabilities=resources
        or ["Governed knowledge and registered read-only capabilities only."],
    )


def _approval_state(
    *,
    status: str,
    handoff_id: str,
    handoff_version: int,
    plan: ValidatedInvestigationPlan,
    rqc: dict[str, Any],
    envelope: ApprovedInvestigationEnvelope | None = None,
    warnings: list[str] | None = None,
) -> InvestigationApprovalState:
    messages = {
        "awaiting_approval": "Investigation plan ready. Review the scope, then Run, Edit, or Cancel.",
        "edited_revalidated": "Edited investigation plan revalidated. Review it before running.",
        "approved": "Investigation plan approved as an immutable read-only envelope. Any execution remains governed by the Resource Planner and its policy gates.",
        "cancelled": "Investigation cancelled. No ResourcePlan was compiled and no tool was executed.",
        "replanning_required": "The requested edit changes material scope. Re-enter query resolution before approval.",
    }
    actions = ["run", "edit", "cancel"] if status in {"awaiting_approval", "edited_revalidated"} else []
    return InvestigationApprovalState(
        status=status,  # type: ignore[arg-type]
        handoff_id=handoff_id,
        handoff_version=handoff_version,
        allowed_actions=actions,  # type: ignore[arg-type]
        plan_summary=build_plan_summary(plan, rqc),
        validated_plan=plan.model_dump(mode="json"),
        approved_envelope=envelope,
        safe_message=messages[status],
        revalidation_warnings=list(warnings or []),
    )


def _persist_initial_plan(
    state: dict[str, Any],
    *,
    plan: ValidatedInvestigationPlan,
    rqc: dict[str, Any],
    snapshot: dict[str, Any],
) -> None:
    handoff_id = str(state.get("handoff_id") or "")
    version = int(state.get("handoff_version") or 0)
    if not handoff_id or version < 1:
        raise InvestigationEnvelopeError("investigation_handoff_identity_missing")
    record = get_handoff(handoff_id, version)
    if record is None or record.normalized_status() != "awaiting_investigation_plan":
        raise InvestigationEnvelopeError("investigation_handoff_not_pending")
    canonical = dict(record.canonical_planning_input or {})
    canonical[_HIL_KEY] = {
        "validated_investigation_plan": plan.model_dump(mode="json"),
        "capability_snapshot": snapshot,
        "resolved_query_contract": rqc,
        "intent_classification": _as_dict(state.get("intent_classification")),
        "routed": _as_dict(state.get("routed")),
        "plan_fingerprint": _fingerprint(plan.model_dump(mode="json")),
    }
    save_handoff(record.model_copy(update={"canonical_planning_input": canonical}))


def maybe_attach_investigation_approval(state: dict[str, Any]) -> dict[str, Any]:
    """Attach and persist the readable P4 plan on the existing P0 wait-state."""
    if not settings.ai_soc_investigation_plan_before_resource_plan_enabled:
        return state
    raw_plan = state.get("validated_investigation_plan")
    if not isinstance(raw_plan, dict):
        return state
    plan = ValidatedInvestigationPlan.model_validate(raw_plan)
    rqc = _as_dict(state.get("resolved_query_contract"))
    snapshot = _as_dict(state.get("capability_snapshot"))
    _persist_initial_plan(state, plan=plan, rqc=rqc, snapshot=snapshot)
    approval = _approval_state(
        status="awaiting_approval",
        handoff_id=str(state["handoff_id"]),
        handoff_version=int(state["handoff_version"]),
        plan=plan,
        rqc=rqc,
    )
    return {**state, "investigation_approval": approval.model_dump(mode="json")}


def _material_scope_changed(
    edits: InvestigationPlanEdits,
    *,
    plan: ValidatedInvestigationPlan,
    rqc: dict[str, Any],
) -> bool:
    if edits.investigation_objective is not None:
        if " ".join(edits.investigation_objective.split()) != " ".join(plan.investigation_objective.split()):
            return True
    if edits.entities is not None and edits.entities != _as_dict(rqc.get("entities")):
        return True
    if edits.time_scope is not None and edits.time_scope.strip() != str(rqc.get("time_scope") or "").strip():
        return True
    return False


def _revalidate_edit(
    edits: InvestigationPlanEdits,
    *,
    plan: ValidatedInvestigationPlan,
    snapshot: dict[str, Any],
) -> ValidatedInvestigationPlan:
    proposal = {
        key: value
        for key, value in edits.model_dump().items()
        if value is not None and key not in {"entities", "time_scope"}
    }
    validated = validate_investigation_plan(
        InvestigationPlan.model_validate(plan.model_dump()),
        proposal,
        llm_attempted=False,
        capability_snapshot=snapshot,
    )
    return validated.model_copy(
        update={
            "plan_source": plan.plan_source,
            "validation_warnings": list(
                dict.fromkeys([*validated.validation_warnings, "analyst_edit_revalidated"])
            ),
        }
    )


def _build_envelope(
    *,
    version: int,
    plan: ValidatedInvestigationPlan,
    rqc: dict[str, Any],
) -> ApprovedInvestigationEnvelope:
    entities = _as_dict(rqc.get("entities"))
    capabilities = [
        binding.capability_id
        for binding in plan.capability_bindings
        if binding.availability == "available" and binding.access_mode == "read_only"
    ]
    return ApprovedInvestigationEnvelope(
        envelope_version=version,
        objective=plan.investigation_objective,
        targets=_targets(entities),
        entities=entities,
        time_scope=str(rqc.get("time_scope")) if rqc.get("time_scope") else None,
        approved_evidence_categories=list(plan.data_categories),
        allowed_read_only_capabilities=capabilities,
        source_index_scope=_source_index_scope(rqc),
    )


def _successor_for_action(
    pending: CanonicalHandoffRecord,
    *,
    action: str,
    edits_raw: dict[str, Any] | None,
) -> CanonicalHandoffRecord:
    canonical = dict(pending.canonical_planning_input or {})
    hil = _as_dict(canonical.get(_HIL_KEY))
    raw_plan = hil.get("validated_investigation_plan")
    if not isinstance(raw_plan, dict):
        raise InvestigationEnvelopeError("validated_investigation_plan_missing")
    plan = ValidatedInvestigationPlan.model_validate(raw_plan)
    rqc = _as_dict(hil.get("resolved_query_contract") or canonical.get("resolved_query_contract"))
    snapshot = _as_dict(hil.get("capability_snapshot"))
    next_version = pending.handoff_version + 1
    decision: dict[str, Any] = {"requested_action": action, "prior_version": pending.handoff_version}
    status = "awaiting_investigation_plan"
    envelope: ApprovedInvestigationEnvelope | None = None
    approval_status = "awaiting_approval"
    warnings: list[str] = []

    if action == "run":
        envelope = _build_envelope(version=next_version, plan=plan, rqc=rqc)
        status = "investigation_approved"
        approval_status = "approved"
        canonical["approved_investigation_envelope"] = envelope.model_dump(mode="json")
    elif action == "cancel":
        status = "investigation_cancelled"
        approval_status = "cancelled"
        canonical.pop("approved_investigation_envelope", None)
    elif action == "edit":
        edits = InvestigationPlanEdits.model_validate(edits_raw or {})
        if _material_scope_changed(edits, plan=plan, rqc=rqc):
            status = "awaiting_clarification"
            approval_status = "replanning_required"
            warnings.append("material_scope_change_requires_new_rqc")
        else:
            plan = _revalidate_edit(edits, plan=plan, snapshot=snapshot)
            approval_status = "edited_revalidated"
            hil["validated_investigation_plan"] = plan.model_dump(mode="json")
            hil["plan_fingerprint"] = _fingerprint(plan.model_dump(mode="json"))
            canonical[_HIL_KEY] = hil
            canonical.pop("approved_investigation_envelope", None)
    else:
        raise InvestigationEnvelopeError("unsupported_investigation_review_action")

    approval = _approval_state(
        status=approval_status,
        handoff_id=pending.handoff_id,
        handoff_version=next_version,
        plan=plan,
        rqc=rqc,
        envelope=envelope,
        warnings=warnings,
    )
    decision.update(
        {
            "status": approval_status,
            "plan_fingerprint": hil.get("plan_fingerprint"),
            "approval": approval.model_dump(mode="json"),
        }
    )
    canonical[_DECISION_KEY] = decision
    now = datetime.now(UTC)
    return pending.model_copy(
        update={
            "handoff_version": next_version,
            "status": status,
            "canonical_planning_input": canonical,
            "committed_resource_plan_id": None,
            "committed_resource_plan": None,
            "committed_evidence_plan": None,
            "created_at": now,
            "updated_at": now,
            "expires_at": now + timedelta(minutes=max(5, settings.ai_soc_handoff_store_ttl_minutes)),
        }
    )


def _validate_pending(
    pending: CanonicalHandoffRecord | None,
    *,
    session_id: str | None,
) -> CanonicalHandoffRecord:
    if pending is None:
        raise InvestigationEnvelopeError("investigation_handoff_not_found")
    if pending.is_expired():
        raise InvestigationEnvelopeError("investigation_handoff_expired")
    if pending.normalized_status() != "awaiting_investigation_plan":
        raise InvestigationEnvelopeError("investigation_handoff_not_pending")
    if session_id and pending.session_id and session_id != pending.session_id:
        raise InvestigationEnvelopeError("session_ownership_mismatch")
    return pending


def _existing_successor_result(
    pending: CanonicalHandoffRecord,
    existing: CanonicalHandoffRecord,
    *,
    action: str,
) -> _AdvanceResult:
    decision = _as_dict((existing.canonical_planning_input or {}).get(_DECISION_KEY))
    if decision.get("requested_action") != action:
        raise InvestigationEnvelopeError("investigation_handoff_already_decided")
    return _AdvanceResult(record=existing, idempotent_replay=True)


def _advance_memory(
    *,
    handoff_id: str,
    handoff_version: int,
    action: str,
    edits: dict[str, Any] | None,
    session_id: str | None,
) -> _AdvanceResult:
    with memory_handoff_lock(handoff_id):
        pending_raw = test_store_read(handoff_id, handoff_version)
        existing = test_store_read(handoff_id, handoff_version + 1)
        if existing is not None:
            if pending_raw is None:
                raise InvestigationEnvelopeError("investigation_handoff_not_found")
            if session_id and pending_raw.session_id and session_id != pending_raw.session_id:
                raise InvestigationEnvelopeError("session_ownership_mismatch")
            return _existing_successor_result(pending_raw, existing, action=action)
        pending = _validate_pending(pending_raw, session_id=session_id)
        successor = _successor_for_action(pending, action=action, edits_raw=edits)
        test_store_write(
            handoff_id,
            handoff_version,
            pending.model_copy(update={"status": "resumed", "updated_at": datetime.now(UTC)}),
        )
        test_store_write(handoff_id, successor.handoff_version, successor)
        return _AdvanceResult(record=successor)


async def _advance_db(
    conn: asyncpg.Connection,
    *,
    handoff_id: str,
    handoff_version: int,
    action: str,
    edits: dict[str, Any] | None,
    session_id: str | None,
) -> _AdvanceResult:
    pending_raw = await load_pending_for_update(conn, handoff_id, handoff_version)
    existing_row = await fetch_handoff_record(conn, handoff_id, handoff_version + 1)
    if existing_row is not None:
        if pending_raw is None:
            raise InvestigationEnvelopeError("investigation_handoff_not_found")
        if session_id and pending_raw.session_id and session_id != pending_raw.session_id:
            raise InvestigationEnvelopeError("session_ownership_mismatch")
        return _existing_successor_result(
            pending_raw,
            handoff_record_from_row(existing_row),
            action=action,
        )
    pending = _validate_pending(pending_raw, session_id=session_id)
    successor = _successor_for_action(pending, action=action, edits_raw=edits)
    await persist_handoff_record(
        conn,
        pending.model_copy(update={"status": "resumed", "updated_at": datetime.now(UTC)}),
    )
    await persist_handoff_record(conn, successor)
    return _AdvanceResult(record=successor)


def _advance_review(
    *,
    handoff_id: str,
    handoff_version: int,
    action: str,
    edits: dict[str, Any] | None,
    session_id: str | None,
) -> _AdvanceResult:
    if in_memory_handoff_store_enabled():
        return _advance_memory(
            handoff_id=handoff_id,
            handoff_version=handoff_version,
            action=action,
            edits=edits,
            session_id=session_id,
        )

    async def _txn(conn: asyncpg.Connection | None) -> _AdvanceResult:
        if conn is None:
            raise InvestigationEnvelopeError("canonical_handoff_db_unavailable")
        return await _advance_db(
            conn,
            handoff_id=handoff_id,
            handoff_version=handoff_version,
            action=action,
            edits=edits,
            session_id=session_id,
        )

    return run_in_canonical_unit_of_work(_txn)


def maybe_handle_investigation_review(state: dict[str, Any]) -> dict[str, Any] | None:
    """Handle an explicitly version-bound investigation decision before replanning."""
    if not settings.ai_soc_investigation_plan_before_resource_plan_enabled:
        return None
    request = state.get("request")
    action = str(getattr(request, "investigation_review_action", "") or "").strip().lower()
    if not action:
        return None
    result = _advance_review(
        handoff_id=str(getattr(request, "investigation_handoff_id")),
        handoff_version=int(getattr(request, "investigation_handoff_version")),
        action=action,
        edits=getattr(request, "investigation_plan_edits", None),
        session_id=str(state.get("session_id")) if state.get("session_id") else None,
    )
    record = result.record
    canonical = dict(record.canonical_planning_input or {})
    hil = _as_dict(canonical.get(_HIL_KEY))
    rqc = _as_dict(hil.get("resolved_query_contract") or canonical.get("resolved_query_contract"))
    approval_raw = _as_dict(_as_dict(canonical.get(_DECISION_KEY)).get("approval"))
    approval = InvestigationApprovalState.model_validate(approval_raw)
    routing = _as_dict(canonical.get("routing"))
    skill = str(routing.get("primary_skill") or record.original_skill or "guided_investigation")
    routed = _as_dict(hil.get("routed")) or dict(state.get("routed") or {})
    routed.update({"skill": skill, "confidence": 1.0, "tool_plan": []})
    intent = _as_dict(hil.get("intent_classification"))
    if not intent:
        answer_goal = str(routing.get("answer_goal") or rqc.get("answer_goal") or "live_results")
        intent = {
            "primary_intent": skill,
            "intent_family": str(routing.get("intent_family") or rqc.get("intent_family") or "live_investigation"),
            "query_type": "ask_for_live_results",
            "answer_goal": [answer_goal],
            "answer_goal_primary": answer_goal,
            "confidence": 1.0,
            "confidence_band": "high",
            "requires_clarification": False,
            "requires_hil": True,
            "action_mode": "hil_required",
            "reason": "investigation_envelope_review_resume",
        }
    intent["requires_clarification"] = approval.status == "replanning_required"
    intent["requires_hil"] = True
    outcome = awaiting_investigation_plan_outcome(canonical_input=canonical)
    next_state = {
        **state,
        "routed": routed,
        "intent_classification": intent,
        "resolved_query_contract": rqc,
        "canonical_planning_input": canonical,
        "canonical_planning_outcome": outcome.model_dump(mode="json"),
        "capability_snapshot": _as_dict(hil.get("capability_snapshot")),
        "validated_investigation_plan": approval.validated_plan,
        "investigation_approval": approval.model_dump(mode="json"),
        "approved_investigation_envelope": (
            approval.approved_envelope.model_dump(mode="json")
            if approval.approved_envelope is not None
            else None
        ),
        "handoff_id": record.handoff_id,
        "handoff_version": record.handoff_version,
        "pending_handoff_id": record.handoff_id,
        "pending_handoff_version": record.handoff_version,
        "investigation_approval_action_handled": True,
    }
    for key in ("evidence_plan", "execution", "mcp_evidence"):
        next_state.pop(key, None)
    if (
        action == "run"
        and approval.approved_envelope is not None
        and settings.ai_soc_resource_plan_execution_enabled
    ):
        from app.chat.contracts.resolved_query import ResolvedQueryContract
        from app.chat.investigation_run_compiler import compile_approved_investigation

        compiled = compile_approved_investigation(
            envelope=approval.approved_envelope,
            validated_plan=ValidatedInvestigationPlan.model_validate(approval.validated_plan),
            resolved_query_contract=ResolvedQueryContract.model_validate(rqc),
            handoff_id=record.handoff_id,
            handoff_version=record.handoff_version,
            use_case_id=record.original_use_case_id,
        )
        evidence_payload = compiled.evidence_plan.model_dump(mode="json")
        resource_payload = compiled.resource_plan.model_dump(mode="json")
        commit_resource_plan(
            handoff_id=record.handoff_id,
            handoff_version=record.handoff_version,
            resource_plan_id=str(compiled.resource_plan.provenance["resource_plan_id"]),
            resource_plan=resource_payload,
            evidence_plan=evidence_payload,
        )
        outcome = planned_outcome(
            canonical_input=canonical,
            evidence_plan=evidence_payload,
            resource_plan=resource_payload,
        )
        next_state = {
            **next_state,
            "canonical_planning_outcome": outcome.model_dump(mode="json"),
            "evidence_plan": evidence_payload,
            "investigation_phase_contract": compiled.phase_contract.trace_payload(),
        }
    return next_state
