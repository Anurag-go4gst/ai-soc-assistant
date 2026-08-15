"""Resolve lightweight session follow-ups from structured investigation pins."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from app.chat.session_store import SessionPins, delete_session_pins, get_session_pins, new_session_id, save_session_pins
from app.config import settings
from app.schemas.requests import ChatRequest
from app.schemas.responses import PlaceholderResponse
from app.use_cases.registry import get_use_case
from app.use_cases.models import UseCaseSelection

_FOLLOW_UP_MITRE = (
    "map to mitre",
    "map it to mitre",
    "now map it to mitre",
    "now map to mitre",
    "mitre mapping",
    "map this to mitre",
)
_FOLLOW_UP_SPL_REFINE = (
    "refine that spl",
    "refine the spl",
    "refine spl",
    "update that spl",
    "update spl",
)
_FOLLOW_UP_SAME_ALERT = ("same alert", "that alert", "for that alert")
_FOLLOW_UP_SHOW_EVIDENCE = ("show evidence", "show the evidence", "previous evidence")
_FOLLOW_UP_SEVERITY = ("what is the severity", "what's the severity", "severity?", "show severity")
# Bare "summarize" is NOT a follow-up marker: queries that carry their own
# subject ("summarize yesterday's helpdesk tickets") are standalone asks and
# must not HIL-block on missing session context (oos.near_miss.02 defect).
_FOLLOW_UP_SUMMARY = (
    "analyst summary",
    "give analyst summary",
    "give me a summary",
    "summarize it",
    "summarize this",
    "summarize that",
    "summarize the alert",
    "summarize the investigation",
    "summarize above",
)


class SessionContextStatus(BaseModel):
    session_id: str
    used_previous_context: bool = False
    context_source_trace_id: str | None = None
    staleness: str = "missing"  # fresh | stale | missing
    used_fields: list[str] = Field(default_factory=list)
    ignored_fields: list[str] = Field(default_factory=list)
    clarification_required: bool = False


class SessionContextResolution(BaseModel):
    session_id: str
    pins: SessionPins | None = None
    effective_query: str
    status: SessionContextStatus
    follow_up_kind: str | None = None
    apply_use_case_id: str | None = None
    spl_refine_from_session: bool = False
    session_alert_context: bool = False
    handoff_resume: dict[str, Any] | None = None


def resolve_session_context(request: ChatRequest) -> SessionContextResolution:
    session_id = (request.session_id or "").strip() or new_session_id()
    pins = get_session_pins(session_id) if settings.ai_soc_session_context_enabled else None
    message = request.message
    normalized = " ".join(message.lower().split())

    status = SessionContextStatus(session_id=session_id, staleness="missing")
    effective_query = message
    follow_up_kind: str | None = None
    apply_use_case_id: str | None = None
    spl_refine = False
    session_alert_context = False
    used_fields: list[str] = []
    ignored_fields: list[str] = []

    if not settings.ai_soc_session_context_enabled:
        return SessionContextResolution(
            session_id=session_id,
            pins=None,
            effective_query=effective_query,
            status=status,
        )

    if pins is None and request.session_id:
        status.staleness = "stale"
        status.clarification_required = _is_contextual_follow_up(normalized)
        status.ignored_fields = ["session_expired_or_missing"]
        return SessionContextResolution(
            session_id=session_id,
            pins=None,
            effective_query=effective_query,
            status=status,
            follow_up_kind=_follow_up_kind(normalized) if status.clarification_required else None,
        )

    if pins is None:
        return SessionContextResolution(
            session_id=session_id,
            pins=None,
            effective_query=effective_query,
            status=status,
        )

    handoff_resume: dict[str, Any] | None = None
    if pins.pending_handoff_id:
        from app.chat.canonical_handoff_store import get_handoff

        record = get_handoff(pins.pending_handoff_id, int(pins.pending_handoff_version or 1))
        if record is not None and record.normalized_status() == "awaiting_clarification":
            handoff_resume = {
                "handoff_id": pins.pending_handoff_id,
                "handoff_version": int(pins.pending_handoff_version or 1),
                "user_answer": message,
            }
            effective_query = str(record.original_query or message)
            status.used_previous_context = True
            status.staleness = "fresh"
            status.context_source_trace_id = pins.last_trace_id
            used_fields.append("pending_handoff")
            status.used_fields = sorted(set(used_fields))
            return SessionContextResolution(
                session_id=session_id,
                pins=pins,
                effective_query=effective_query,
                status=status,
                handoff_resume=handoff_resume,
            )

    status.staleness = "fresh"
    status.context_source_trace_id = pins.last_trace_id
    kind = _follow_up_kind(normalized)
    scope_delta = _generic_scope_delta(normalized)

    if not kind and scope_delta and (pins.last_rqc_redacted or pins.last_entities):
        status.used_previous_context = True
        status.used_fields = sorted(
            {
                field
                for field in (
                    "last_rqc_redacted" if pins.last_rqc_redacted else None,
                    "last_entities" if pins.last_entities else None,
                    "last_investigation_outcome_ref" if pins.last_investigation_outcome_ref else None,
                    "last_evidence_refs" if pins.last_evidence_refs else None,
                    "last_clarification_state" if pins.last_clarification_state else None,
                    "last_plan_identity" if pins.last_plan_identity else None,
                    "last_evidence_scope" if pins.last_evidence_scope else None,
                )
                if field
            }
        )
        return SessionContextResolution(
            session_id=session_id,
            pins=pins,
            effective_query=effective_query,
            status=status,
            follow_up_kind="scope_delta",
        )

    if not kind and not _message_has_own_alert_context(normalized):
        return SessionContextResolution(
            session_id=session_id,
            pins=pins,
            effective_query=effective_query,
            status=status,
        )

    follow_up_kind = kind
    status.used_previous_context = True

    if kind in {"mitre", "severity", "summary", "show_evidence", "same_alert", "spl_refine"}:
        if pins.last_alert_id and not _message_has_own_alert_context(normalized):
            effective_query = _session_augmented_query(message, pins, kind)
            session_alert_context = True
            used_fields.append("last_alert_id")
        elif kind != "spl_refine" and _requires_alert_context(kind):
            status.clarification_required = True
            status.used_previous_context = False
            ignored_fields.append("last_alert_id_missing")
            effective_query = message
            session_alert_context = False

    if pins.last_use_case_id and kind in {"mitre", "severity", "summary", "show_evidence", "same_alert", "spl_refine"}:
        apply_use_case_id = pins.last_use_case_id
        used_fields.append("last_use_case_id")
    elif _requires_use_case(kind):
        status.clarification_required = True
        ignored_fields.append("last_use_case_id_missing")

    if kind == "spl_refine":
        if pins.last_candidate_spl:
            spl_refine = True
            used_fields.append("last_candidate_spl")
        else:
            status.clarification_required = True
            ignored_fields.append("last_candidate_spl_missing")

    if kind == "show_evidence" and not pins.last_context_sufficiency:
        ignored_fields.append("last_context_sufficiency_missing")

    status.used_fields = sorted(set(used_fields))
    status.ignored_fields = sorted(set(ignored_fields))
    return SessionContextResolution(
        session_id=session_id,
        pins=pins,
        effective_query=effective_query,
        status=status,
        follow_up_kind=follow_up_kind,
        apply_use_case_id=apply_use_case_id,
        spl_refine_from_session=spl_refine,
        session_alert_context=session_alert_context,
    )


def use_case_from_session(use_case_id: str | None) -> UseCaseSelection | None:
    if not use_case_id:
        return None
    definition = get_use_case(use_case_id)
    if definition is None:
        return None
    return UseCaseSelection(
        use_case_id=definition.use_case_id,
        display_name=definition.display_name,
        category=definition.category,
        primary_skill=definition.primary_skill,
        confidence=0.7,
        matched_patterns=["session_context"],
        default_spl_template=definition.default_spl_template,
        output_template=definition.output_template,
        required_sources=definition.required_sources,
        optional_sources=definition.optional_sources,
        action_capability_tier=definition.action_capability_tier,
    )


def pins_from_pipeline_state(
    *,
    session_id: str,
    trace_id: str,
    response: PlaceholderResponse,
    state: dict[str, Any],
) -> SessionPins:
    selected = response.selected_use_case
    candidate = response.candidate_spl
    spl_validation = response.spl_validation
    execution = response.execution
    human_review = response.human_review
    mitre_decision = response.mitre_decision if isinstance(response.mitre_decision, dict) else None
    request = state.get("request")
    query_text = response.user_query or (request.message if isinstance(request, ChatRequest) else "")
    alert_id = _extract_alert_id(query_text)
    prior_pins = state.get("session_pins")
    source_profile_slots: dict[str, str] = {}
    if isinstance(prior_pins, SessionPins):
        source_profile_slots = dict(prior_pins.source_profile_slots or {})
    resolve_trace = state.get("spl_source_resolve")
    if isinstance(resolve_trace, dict):
        resolved = resolve_trace.get("resolved_slots")
        if isinstance(resolved, dict):
            source_profile_slots.update({str(k): str(v) for k, v in resolved.items() if v})

    if alert_id is None and isinstance(prior_pins, SessionPins):
        alert_id = prior_pins.last_alert_id

    spl_text = None
    if candidate is not None:
        spl_text = candidate.candidate_spl
    if spl_text is None and spl_validation is not None:
        spl_text = spl_validation.normalized_spl

    validation_status = None
    if spl_validation is not None:
        validation_status = "approved" if spl_validation.approved else "rejected"

    pending_execution_confirmation = None
    state_execution = state.get("execution")
    if isinstance(state_execution, dict):
        pending = state_execution.get("pending_execution_confirmation")
        if isinstance(pending, dict):
            pending_execution_confirmation = pending
        elif state_execution.get("status") == "executed":
            pending_execution_confirmation = None
    if isinstance(prior_pins, SessionPins) and pending_execution_confirmation is None:
        if human_review and isinstance(human_review, dict) and human_review.get("review_type") == "spl_execution_confirmation":
            pending_execution_confirmation = prior_pins.pending_execution_confirmation
    if human_review and isinstance(human_review, dict) and human_review.get("reason") == "analyst_rejected_execution":
        pending_execution_confirmation = None

    pending_handoff_id = state.get("pending_handoff_id") if isinstance(state.get("pending_handoff_id"), str) else None
    pending_handoff_version = state.get("pending_handoff_version")
    evidence_plan = state.get("evidence_plan") if isinstance(state.get("evidence_plan"), dict) else {}
    resource_plan = evidence_plan.get("resource_plan")
    if isinstance(resource_plan, dict) and (resource_plan.get("provenance") or {}).get("committed"):
        pending_handoff_id = None
        pending_handoff_version = None

    return SessionPins(
        session_id=session_id,
        last_trace_id=trace_id,
        last_alert_id=alert_id,
        last_use_case_id=selected.use_case_id if selected else None,
        last_selected_live_execution_skill=response.selected_skill,
        last_planning_or_analytic_skill=_planning_skill(state),
        last_entities=_entity_summary(state),
        source_profile_slots=source_profile_slots,
        last_candidate_spl=spl_text,
        last_spl_validation_status=validation_status,
        last_spl_template_status=response.spl_template_status,
        last_mitre_decision=mitre_decision,
        last_mitre_evidence_status=response.mitre_evidence_status,
        last_context_sufficiency=response.context_sufficiency.model_dump() if response.context_sufficiency else None,
        last_execution_status=execution.status if execution else None,
        last_human_review_status=_human_review_status(human_review),
        pending_execution_confirmation=pending_execution_confirmation,
        pending_handoff_id=pending_handoff_id,
        pending_handoff_version=pending_handoff_version,
        original_query=query_text if pending_handoff_id else (
            prior_pins.original_query if isinstance(prior_pins, SessionPins) else None
        ),
        last_rqc_redacted=_redact_rqc_for_session(state.get("resolved_query_contract")),
        last_investigation_outcome_ref=_outcome_ref_for_session(state.get("investigation_outcome")),
        last_evidence_refs=_evidence_refs_for_session(state),
        last_clarification_state=_clarification_state_for_session(state),
        last_plan_identity=_plan_identity_for_session(state, trace_id),
        last_evidence_scope=_evidence_scope_for_session(state),
        updated_at=datetime.now(UTC),
        expires_at=datetime.now(UTC),
    )


def persist_session_pins(pins: SessionPins) -> SessionPins:
    if not settings.ai_soc_session_context_enabled:
        return pins
    return save_session_pins(pins)


def clear_session(session_id: str | None) -> None:
    delete_session_pins(session_id)


def _follow_up_kind(normalized: str) -> str | None:
    if any(term in normalized for term in _FOLLOW_UP_MITRE):
        return "mitre"
    if any(term in normalized for term in _FOLLOW_UP_SPL_REFINE):
        return "spl_refine"
    if any(term in normalized for term in _FOLLOW_UP_SAME_ALERT):
        return "same_alert"
    if any(term in normalized for term in _FOLLOW_UP_SHOW_EVIDENCE):
        return "show_evidence"
    if any(term in normalized for term in _FOLLOW_UP_SEVERITY):
        return "severity"
    if any(term in normalized for term in _FOLLOW_UP_SUMMARY):
        return "summary"
    return None


def _is_contextual_follow_up(normalized: str) -> bool:
    return _follow_up_kind(normalized) is not None or any(
        term in normalized for term in ("same alert", "that spl", "previous", "last alert", "refine")
    )


def _requires_alert_context(kind: str) -> bool:
    return kind in {"mitre", "severity", "summary", "same_alert", "show_evidence"}


def _requires_use_case(kind: str) -> bool:
    return kind in {"mitre", "severity", "summary", "spl_refine", "show_evidence", "same_alert"}


def _message_has_own_alert_context(normalized: str) -> bool:
    return bool(
        re.search(r"\balt-\d{4}-\d+\b", normalized)
        or re.search(r"\bfor alert\b", normalized)
        or re.search(r"\balert\s+[a-z0-9][\w.-]+\b", normalized)
    )


def _extract_alert_id(message: str) -> str | None:
    normalized = " ".join(message.lower().split())
    match = re.search(r"\b(alt-\d{4}-\d+)\b", normalized)
    return match.group(1).upper() if match else None


def _planning_skill(state: dict[str, Any]) -> str | None:
    shadow = state.get("route_plan_shadow")
    if not isinstance(shadow, dict):
        return None
    compare = shadow.get("route_authority_compare")
    if isinstance(compare, dict):
        value = compare.get("planning_primary_skill")
        return str(value) if value else None
    return None


def _entity_summary(state: dict[str, Any]) -> dict[str, Any]:
    structured = state.get("structured_context")
    if not isinstance(structured, dict):
        return {}
    summary = structured.get("entity_summary")
    return dict(summary) if isinstance(summary, dict) else {}


def _session_augmented_query(message: str, pins: SessionPins, kind: str) -> str:
    parts = [message, f"(session context: alert {pins.last_alert_id})"]
    if pins.last_use_case_id == "auth_success_after_failure":
        parts.append(
            "failed logins followed by a successful login from the same user in the last hour"
        )
    elif pins.last_use_case_id == "auth_failed_login_spike":
        parts.append("failed login spike with no successful login")
    if kind == "spl_refine" and pins.last_candidate_spl:
        parts.append("refine the prior governed candidate SPL")
    return " ".join(parts)


def _human_review_status(human_review: Any) -> str | None:
    if human_review is None:
        return None
    required = getattr(human_review, "required", None)
    review_type = getattr(human_review, "review_type", None)
    if required:
        return str(review_type or "required")
    return "not_required"


_SCOPE_DELTA_PREFIXES = ("what about ", "how about ", "and for ", "also for ")


def _generic_scope_delta(normalized: str) -> str | None:
    """Shape-only follow-up delta. Not a catalogue of investigation phrases."""
    for prefix in _SCOPE_DELTA_PREFIXES:
        if normalized.startswith(prefix):
            remainder = normalized[len(prefix) :].strip(" ?.")
            return remainder or None
    return None


def _redact_rqc_for_session(rqc: Any) -> dict[str, Any] | None:
    if not isinstance(rqc, dict):
        return None
    caps = rqc.get("required_capabilities")
    if isinstance(caps, (set, frozenset)):
        caps = sorted(str(item) for item in caps)
    return {
        "intent_family": rqc.get("intent_family"),
        "answer_goal": rqc.get("answer_goal"),
        "evidence_requirements": list(rqc.get("evidence_requirements") or []),
        "required_capabilities": list(caps or []),
        "time_scope": rqc.get("time_scope"),
        "entities": rqc.get("entities") if isinstance(rqc.get("entities"), dict) else {},
        "clarification_required": bool(rqc.get("clarification_required")),
    }


def _outcome_ref_for_session(outcome: Any) -> dict[str, Any] | None:
    if not isinstance(outcome, dict):
        return None
    provenance = outcome.get("provenance") if isinstance(outcome.get("provenance"), dict) else {}
    return {
        "disposition": outcome.get("disposition"),
        "severity_label": outcome.get("severity_label"),
        "evidence_refs": list(outcome.get("evidence_refs") or []),
        "missing_evidence": list(outcome.get("missing_evidence") or []),
        "trace_id": provenance.get("trace_id"),
    }


def _evidence_refs_for_session(state: dict[str, Any]) -> list[str]:
    evidence = state.get("evidence_state") if isinstance(state.get("evidence_state"), dict) else {}
    refs = [str(item) for item in (evidence.get("obtained") or [])]
    outcome = state.get("investigation_outcome") if isinstance(state.get("investigation_outcome"), dict) else {}
    refs.extend(str(item) for item in (outcome.get("evidence_refs") or []))
    return sorted({item for item in refs if item})


def _clarification_state_for_session(state: dict[str, Any]) -> dict[str, Any] | None:
    rqc = state.get("resolved_query_contract") if isinstance(state.get("resolved_query_contract"), dict) else {}
    if not rqc:
        return None
    return {
        "clarification_required": bool(rqc.get("clarification_required")),
        "clarification_reason": rqc.get("clarification_reason"),
        "unresolved_fields": list(rqc.get("unresolved_fields") or []),
    }


def _plan_identity_for_session(state: dict[str, Any], trace_id: str) -> dict[str, Any]:
    evidence = state.get("evidence_plan") if isinstance(state.get("evidence_plan"), dict) else {}
    plan = evidence.get("resource_plan") if isinstance(evidence.get("resource_plan"), dict) else {}
    provenance = plan.get("provenance") if isinstance(plan.get("provenance"), dict) else {}
    return {
        "trace_id": trace_id,
        "resource_plan_id": provenance.get("resource_plan_id"),
        "handoff_id": provenance.get("handoff_id"),
    }


def _evidence_scope_for_session(state: dict[str, Any]) -> dict[str, Any] | None:
    rqc = state.get("resolved_query_contract") if isinstance(state.get("resolved_query_contract"), dict) else {}
    evidence = state.get("evidence_state") if isinstance(state.get("evidence_state"), dict) else {}
    if not rqc and not evidence:
        return None
    return {
        "time_scope": rqc.get("time_scope"),
        "entities": rqc.get("entities") if isinstance(rqc.get("entities"), dict) else {},
        "intent_family": rqc.get("intent_family"),
        "freshness": evidence.get("observed_at") or evidence.get("freshness"),
        "applicability": evidence.get("applicability"),
    }
