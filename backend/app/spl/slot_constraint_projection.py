"""Canonical slot + semantic constraint projection for T2 SPL handoff.

Wraps existing ``UserConstraintBindings`` and ``t2_constraints`` builders; does
not implement a third merge algorithm.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from app.chat.contracts.llm_intent_advisory import LLMIntentAdvisory
from app.query_understanding.models import QueryUnderstandingResult
from app.spl.source_profile_bindings import build_source_profile_binding_slots
from app.spl.user_constraint_bindings import (
    SLOT_SOURCE_DETERMINISTIC,
    SLOT_SOURCE_LLM,
    SLOT_SOURCE_SOURCE_PROFILE,
    SLOT_SOURCE_TEMPLATE_DEFAULT,
    SLOT_SOURCE_USER_EXPLICIT,
    UserConstraintBindings,
    build_user_constraint_bindings,
)

BuiltAtStage = Literal["evidence_planning", "spl_generation"]


@dataclass
class SlotConstraintProjection:
    projection_id: str
    built_at_stage: BuiltAtStage
    user_explicit_slots: dict[str, Any] = field(default_factory=dict)
    deterministic_slots: dict[str, Any] = field(default_factory=dict)
    llm_advisory_slots: dict[str, Any] = field(default_factory=dict)
    source_profile_defaults: dict[str, Any] = field(default_factory=dict)
    template_defaults: dict[str, Any] = field(default_factory=dict)
    normalized_slots: dict[str, str] = field(default_factory=dict)
    applied_defaults: dict[str, str] = field(default_factory=dict)
    dropped_profile_defaults: list[dict[str, Any]] = field(default_factory=list)
    semantic_constraints: list[dict[str, Any]] = field(default_factory=list)
    missing_constraints: list[str] = field(default_factory=list)
    unbound_constraints: list[dict[str, Any]] = field(default_factory=list)
    conflict_notes: list[dict[str, Any]] = field(default_factory=list)
    drift_from_planning_snapshot: bool = False
    drift_details: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "projection_id": self.projection_id,
            "built_at_stage": self.built_at_stage,
            "user_explicit_slots": dict(self.user_explicit_slots),
            "deterministic_slots": dict(self.deterministic_slots),
            "llm_advisory_slots": dict(self.llm_advisory_slots),
            "source_profile_defaults": dict(self.source_profile_defaults),
            "template_defaults": dict(self.template_defaults),
            "normalized_slots": dict(self.normalized_slots),
            "applied_defaults": dict(self.applied_defaults),
            "dropped_profile_defaults": list(self.dropped_profile_defaults),
            "semantic_constraints": list(self.semantic_constraints),
            "missing_constraints": list(self.missing_constraints),
            "unbound_constraints": list(self.unbound_constraints),
            "conflict_notes": list(self.conflict_notes),
            "drift_from_planning_snapshot": self.drift_from_planning_snapshot,
            "drift_details": list(self.drift_details),
        }


def build_slot_constraint_projection(
    user_query: str,
    *,
    built_at_stage: BuiltAtStage,
    llm_intent_advisory: LLMIntentAdvisory | dict[str, Any] | None = None,
    query_understanding: QueryUnderstandingResult | None = None,
    template_id: str | None = None,
    allowed_indexes: tuple[str, ...] | None = None,
    allowed_sourcetypes: tuple[str, ...] | None = None,
    planning_snapshot: dict[str, Any] | None = None,
    projection_id: str | None = None,
) -> SlotConstraintProjection:
    from app.spl.template_registry import get_spl_template

    template = get_spl_template(template_id) if template_id else None
    policy_indexes = allowed_indexes
    policy_sourcetypes = allowed_sourcetypes
    if template is not None and isinstance(template.validation_rules, dict):
        raw_indexes = template.validation_rules.get("allowed_indexes")
        raw_sourcetypes = template.validation_rules.get("allowed_sourcetypes")
        if policy_indexes is None and isinstance(raw_indexes, list) and raw_indexes:
            policy_indexes = tuple(str(item).lower() for item in raw_indexes)
        if policy_sourcetypes is None and isinstance(raw_sourcetypes, list) and raw_sourcetypes:
            policy_sourcetypes = tuple(str(item).lower() for item in raw_sourcetypes)

    source_profile = build_source_profile_binding_slots(user_query, template_id=template_id)
    bindings = build_user_constraint_bindings(
        user_query,
        llm_intent_advisory=llm_intent_advisory,
        query_understanding=query_understanding,
        extra_slots=source_profile.slots,
        source_profile_trace=source_profile.trace(),
        allowed_indexes=policy_indexes,
        allowed_sourcetypes=policy_sourcetypes,
    )
    return projection_from_bindings(
        bindings,
        built_at_stage=built_at_stage,
        source_profile_defaults=dict(source_profile.slots),
        planning_snapshot=planning_snapshot,
        projection_id=projection_id,
    )


def projection_from_bindings(
    bindings: UserConstraintBindings,
    *,
    built_at_stage: BuiltAtStage,
    source_profile_defaults: dict[str, Any] | None = None,
    planning_snapshot: dict[str, Any] | None = None,
    projection_id: str | None = None,
) -> SlotConstraintProjection:
    extracted = (bindings.debug_trace or {}).get("extracted_by_source") or {}
    user_explicit = dict(extracted.get(SLOT_SOURCE_USER_EXPLICIT) or {})
    deterministic = dict(extracted.get(SLOT_SOURCE_DETERMINISTIC) or {})
    llm_slots = dict(extracted.get(SLOT_SOURCE_LLM) or {})
    profile_defaults = dict(source_profile_defaults or extracted.get(SLOT_SOURCE_SOURCE_PROFILE) or {})
    template_defaults = dict(extracted.get(SLOT_SOURCE_TEMPLATE_DEFAULT) or {})

    dropped_profile, conflict_notes = _profile_drop_notes(bindings, profile_defaults)
    applied_defaults = _applied_profile_defaults(bindings, profile_defaults)
    display_unbound = _display_unbound_constraints(bindings, dropped_profile)

    projection = SlotConstraintProjection(
        projection_id=projection_id or str(uuid.uuid4()),
        built_at_stage=built_at_stage,
        user_explicit_slots=user_explicit,
        deterministic_slots=deterministic,
        llm_advisory_slots=llm_slots,
        source_profile_defaults=profile_defaults,
        template_defaults=template_defaults,
        normalized_slots=dict(bindings.normalized_slots),
        applied_defaults=applied_defaults,
        dropped_profile_defaults=dropped_profile,
        semantic_constraints=list(bindings.semantic_constraints),
        missing_constraints=list(bindings.missing_constraints),
        unbound_constraints=display_unbound,
        conflict_notes=conflict_notes,
    )
    drift, details = compare_planning_snapshot(projection, planning_snapshot)
    projection.drift_from_planning_snapshot = drift
    projection.drift_details = details
    return projection


def compare_planning_snapshot(
    projection: SlotConstraintProjection,
    planning_snapshot: dict[str, Any] | None,
) -> tuple[bool, list[str]]:
    if not isinstance(planning_snapshot, dict) or not planning_snapshot:
        return False, []
    details: list[str] = []
    plan_slots = dict(planning_snapshot.get("normalized_slots") or {})
    for key, value in projection.normalized_slots.items():
        if plan_slots.get(key) != value:
            details.append(f"normalized_slots.{key}")
    for key, value in plan_slots.items():
        if key not in projection.normalized_slots:
            details.append(f"missing_in_final.{key}")
    plan_constraints = planning_snapshot.get("semantic_constraints") or []
    final_types = {
        str(item.get("constraint_type"))
        for item in projection.semantic_constraints
        if isinstance(item, dict)
    }
    for item in plan_constraints:
        if not isinstance(item, dict):
            continue
        ctype = str(item.get("constraint_type") or "")
        if ctype and ctype not in final_types:
            details.append(f"semantic_constraint_missing.{ctype}")
    return bool(details), details


def _profile_drop_notes(
    bindings: UserConstraintBindings,
    profile_defaults: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    dropped: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    decisions = (bindings.debug_trace or {}).get("final_slot_precedence_decision") or []
    for row in decisions:
        if not isinstance(row, dict):
            continue
        if row.get("status") == "dropped" and row.get("source") == SLOT_SOURCE_SOURCE_PROFILE:
            dropped.append(
                {
                    "slot": row.get("slot"),
                    "value": row.get("value"),
                    "reason": "overridden_by_higher_precedence",
                    "overridden_by": bindings.slot_sources.get(str(row.get("slot") or "")),
                }
            )
    for conflict in (bindings.debug_trace or {}).get("slot_conflicts") or []:
        if isinstance(conflict, dict):
            conflicts.append(dict(conflict))
    for slot, value in profile_defaults.items():
        if slot in bindings.normalized_slots:
            continue
        if bindings.slot_sources.get(slot) == SLOT_SOURCE_USER_EXPLICIT:
            dropped.append(
                {
                    "slot": slot,
                    "value": value,
                    "reason": "user_explicit_wins",
                    "overridden_by": SLOT_SOURCE_USER_EXPLICIT,
                }
            )
    return dropped, conflicts


def _applied_profile_defaults(
    bindings: UserConstraintBindings,
    profile_defaults: dict[str, Any],
) -> dict[str, str]:
    applied: dict[str, str] = {}
    for slot, value in profile_defaults.items():
        if bindings.slot_sources.get(slot) == SLOT_SOURCE_SOURCE_PROFILE and slot in bindings.normalized_slots:
            applied[slot] = str(bindings.normalized_slots[slot])
    return applied


def _display_unbound_constraints(
    bindings: UserConstraintBindings,
    dropped_profile: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Omit profile defaults dropped by user explicit from blocking unbound list."""
    dropped_slots = {str(item.get("slot")) for item in dropped_profile if item.get("slot")}
    off_shift = next(
        (
            item
            for item in bindings.semantic_constraints
            if isinstance(item, dict) and item.get("constraint_type") == "off_shift_filter"
        ),
        None,
    )
    off_shift_value = off_shift.get("value") if isinstance(off_shift, dict) else None
    shift_hours_resolved = (
        isinstance(off_shift_value, dict)
        and off_shift_value.get("shift_start_hour") is not None
        and off_shift_value.get("shift_end_hour") is not None
    )
    implemented = {
        str(item.get("constraint_type"))
        for item in bindings.semantic_constraints
        if isinstance(item, dict) and item.get("status") == "implemented"
    }
    display: list[dict[str, Any]] = []
    for item in bindings.unbound_constraints:
        if not isinstance(item, dict):
            continue
        slot = str(item.get("slot") or "")
        if slot in dropped_slots and item.get("reason") != "missing_shift_hour_binding":
            continue
        if slot.startswith("normal_shift") and (
            "off_shift_filter" in implemented or shift_hours_resolved
        ):
            continue
        display.append(dict(item))
    return display


def merge_evidence_plan_spl_drift(
    evidence_plan: dict[str, Any],
    final_projection: dict[str, Any],
) -> dict[str, Any]:
    """Flag planning-vs-final SPL drift on the evidence plan handoff summary."""
    plan = dict(evidence_plan)
    planning_snapshot = plan.get("slot_constraint_projection_summary") or plan.get("normalized_slot_summary") or {}
    drift, details = compare_planning_snapshot(
        SlotConstraintProjection(
            projection_id=str(final_projection.get("projection_id") or "final"),
            built_at_stage="spl_generation",
            normalized_slots=dict(final_projection.get("normalized_slots") or {}),
            semantic_constraints=list(final_projection.get("semantic_constraints") or []),
        ),
        planning_snapshot if isinstance(planning_snapshot, dict) else None,
    )
    plan["handoff_drift_from_final_spl"] = drift
    plan["handoff_drift_details"] = details
    plan["final_spl_projection_summary"] = dict(final_projection)
    plan["slot_constraint_projection_summary"] = {
        **dict(plan.get("slot_constraint_projection_summary") or planning_snapshot),
        "planning_snapshot": True,
        "drift_from_final_spl": drift,
        "drift_details": details,
    }
    return plan
