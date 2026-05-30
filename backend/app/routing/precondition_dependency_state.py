"""Stage 3L-S7.2: Registry-backed hard-precondition dependency snapshots.

Builds HardPreconditionDependencyState from closed-world registries and manifest
metadata only. No MCP/Splunk execution, no live LLM, not wired to /chat.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import Settings, settings as default_settings
from app.coverage.coverage_loader import coverage_for_id
from app.coverage.coverage_models import PatternCoverageEntry
from app.coverage.promotion_registry_snapshot import (
    PromotionRegistrySnapshot,
    evidence_contract_exists,
    load_promotion_registry_snapshot,
)
from app.detections.detection_binder import _resolve_registry_path as _detection_registry_path
from app.detections.detection_models import VettingStatus
from app.detections.detection_registry import load_detection_registry
from app.intel.ioc_lookup import (
    _resolve_registry_path as _ioc_registry_path,
    evaluate_registry_staleness,
)
from app.intel.ioc_models import StalenessStatus
from app.routing.precondition_evaluator import (
    HardPreconditionDependencyState,
    _plan_has_threshold_ref,
    _plan_has_time_window,
)
from app.routing.runtime_skill_catalog import get_skill_contract
from app.spl.template_matcher_llm_assist import APPROVED_SOURCE_CLASS_HINTS
from app.spl.template_registry import get_spl_template

# Enrichment-only primaries intentionally lack standalone fixtures (S3 / spine).
PRIMARY_FIXTURE_BLOCKED_SKILLS: frozenset[str] = frozenset(
    {"entity_context_lookup", "notable_risk_lookup"}
)

_CATALOG_REQUIRE_MAP: dict[str, str] = {
    "source_available": "require_source_class",
    "approved_lookup_available": "require_lookup",
    "vetted_detection_available": "require_detection",
    "vetted_sequence_detection_available": "require_detection",
    "threshold_or_baseline_policy_available": "require_threshold_policy",
}


def build_hard_precondition_dependency_state(
    route_plan: dict[str, Any] | None,
    coverage_entry: PatternCoverageEntry | dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> HardPreconditionDependencyState:
    """Derive explicit dependency readiness from registries + route plan + optional manifest row."""
    active_settings = settings or default_settings
    plan = route_plan if isinstance(route_plan, dict) else {}
    entry = _coerce_coverage_entry(coverage_entry)
    snapshot = load_promotion_registry_snapshot()

    primary_skill = _resolve_primary_skill(plan, entry)
    contract = get_skill_contract(primary_skill) or {}

    template_ref = _resolve_template_ref(plan, entry)
    evidence_ref = _resolve_evidence_contract_ref(plan, entry)
    lookup_ref = _resolve_lookup_ref(plan, entry)
    detection_ref = _resolve_detection_ref(plan, entry)
    detection_family = _resolve_detection_family(plan, entry)
    source_class = _resolve_source_class(plan, entry)

    require_flags = _derive_require_flags(
        plan,
        entry,
        contract,
        template_ref=template_ref,
        evidence_ref=evidence_ref,
        lookup_ref=lookup_ref,
        detection_ref=detection_ref,
        detection_family=detection_family,
        primary_skill=primary_skill,
    )

    template_available, template_sample_only = _resolve_template_state(template_ref, snapshot)
    evidence_available = _resolve_evidence_state(evidence_ref, snapshot)
    lookup_available, lookup_fresh = _resolve_lookup_state(
        lookup_ref,
        snapshot,
        active_settings,
    )
    detection_registered, detection_vetted = _resolve_detection_state(
        detection_ref,
        detection_family,
        snapshot,
        active_settings,
    )
    source_supported = _resolve_source_class_state(source_class)
    threshold_present = _resolve_threshold_policy_present(plan)
    if "time_window" in plan:
        time_window_present = _plan_has_time_window(plan)
    else:
        time_window_present = _manifest_shape_has_time_window(entry)
    primary_fixture_available = _resolve_primary_fixture_available(primary_skill)

    return HardPreconditionDependencyState(
        require_template=require_flags["require_template"],
        require_evidence_contract=require_flags["require_evidence_contract"],
        require_lookup=require_flags["require_lookup"],
        require_detection=require_flags["require_detection"],
        require_source_class=require_flags["require_source_class"],
        require_threshold_policy=require_flags["require_threshold_policy"],
        require_time_window=require_flags["require_time_window"],
        require_primary_fixture=require_flags["require_primary_fixture"],
        template_available=template_available,
        template_sample_only=template_sample_only,
        evidence_contract_available=evidence_available,
        lookup_available=lookup_available,
        lookup_fresh=lookup_fresh,
        detection_registered=detection_registered,
        detection_vetted=detection_vetted,
        source_class_supported=source_supported,
        threshold_policy_present=threshold_present,
        time_window_present=time_window_present,
        primary_fixture_available=primary_fixture_available,
    )


def build_hard_precondition_dependency_state_for_coverage(
    coverage_id: str,
    route_plan: dict[str, Any] | None = None,
    *,
    settings: Settings | None = None,
) -> HardPreconditionDependencyState:
    """Convenience: load manifest row by coverage_id and merge with route_plan."""
    entry = coverage_for_id(coverage_id)
    if entry is None:
        return build_hard_precondition_dependency_state(route_plan, None, settings)
    merged_plan = _merge_plan_with_coverage(route_plan, entry)
    return build_hard_precondition_dependency_state(merged_plan, entry, settings)


def _coerce_coverage_entry(
    coverage_entry: PatternCoverageEntry | dict[str, Any] | None,
) -> PatternCoverageEntry | None:
    if coverage_entry is None:
        return None
    if isinstance(coverage_entry, PatternCoverageEntry):
        return coverage_entry
    return PatternCoverageEntry.model_validate(coverage_entry)


def _merge_plan_with_coverage(
    route_plan: dict[str, Any] | None,
    entry: PatternCoverageEntry,
) -> dict[str, Any]:
    plan = dict(entry.route_plan_shape)
    if route_plan:
        plan.update(route_plan)
        if isinstance(route_plan.get("parameters"), dict):
            base_params = dict(plan.get("parameters") or {})
            base_params.update(route_plan["parameters"])
            plan["parameters"] = base_params
    if entry.template_ref and not plan.get("template_ref"):
        plan["template_ref"] = entry.template_ref
    if entry.evidence_contract_ref and not plan.get("evidence_contract_ref"):
        plan["evidence_contract_ref"] = entry.evidence_contract_ref
    plan.setdefault("coverage_id", entry.coverage_id)
    plan.setdefault("primary_skill", entry.primary_skill)
    return plan


def _resolve_primary_skill(
    plan: dict[str, Any],
    entry: PatternCoverageEntry | None,
) -> str:
    if plan.get("primary_skill"):
        return str(plan["primary_skill"])
    if entry is not None:
        return entry.primary_skill
    return ""


def _resolve_template_ref(plan: dict[str, Any], entry: PatternCoverageEntry | None) -> str | None:
    ref = plan.get("template_ref")
    if isinstance(ref, str) and ref.strip():
        return ref.strip()
    if entry and entry.template_ref:
        return entry.template_ref
    return None


def _resolve_evidence_contract_ref(
    plan: dict[str, Any],
    entry: PatternCoverageEntry | None,
) -> str | None:
    ref = plan.get("evidence_contract_ref")
    if isinstance(ref, str) and ref.strip():
        return ref.strip()
    if entry:
        return entry.evidence_contract_ref
    return None


def _resolve_lookup_ref(plan: dict[str, Any], entry: PatternCoverageEntry | None) -> str | None:
    parameters = plan.get("parameters")
    if isinstance(parameters, dict):
        ref = parameters.get("lookup_ref")
        if isinstance(ref, str) and ref.strip():
            return ref.strip()
    ref = plan.get("lookup_ref")
    if isinstance(ref, str) and ref.strip():
        return ref.strip()
    if entry and entry.lookup_ref:
        return entry.lookup_ref
    return None


def _resolve_detection_ref(plan: dict[str, Any], entry: PatternCoverageEntry | None) -> str | None:
    parameters = plan.get("parameters")
    if isinstance(parameters, dict):
        ref = parameters.get("detection_ref")
        if isinstance(ref, str) and ref.strip():
            return ref.strip()
    ref = plan.get("detection_ref")
    if isinstance(ref, str) and ref.strip():
        return ref.strip()
    if entry and entry.detection_ref:
        return entry.detection_ref
    return None


def _resolve_detection_family(plan: dict[str, Any], entry: PatternCoverageEntry | None) -> str | None:
    parameters = plan.get("parameters")
    if isinstance(parameters, dict):
        family = parameters.get("detection_family")
        if isinstance(family, str) and family.strip():
            return family.strip()
    family = plan.get("detection_family")
    if isinstance(family, str) and family.strip():
        return family.strip()
    if entry and entry.detection_family:
        return entry.detection_family
    return None


def _resolve_source_class(plan: dict[str, Any], entry: PatternCoverageEntry | None) -> str | None:
    if isinstance(plan.get("source_class"), str) and plan["source_class"].strip():
        return plan["source_class"].strip()
    shape = entry.route_plan_shape if entry else {}
    if isinstance(shape.get("source_class"), str) and shape["source_class"].strip():
        return shape["source_class"].strip()
    return None


def _derive_require_flags(
    plan: dict[str, Any],
    entry: PatternCoverageEntry | None,
    contract: dict[str, Any],
    *,
    template_ref: str | None,
    evidence_ref: str | None,
    lookup_ref: str | None,
    detection_ref: str | None,
    detection_family: str | None,
    primary_skill: str,
) -> dict[str, bool]:
    flags = {
        "require_template": False,
        "require_evidence_contract": False,
        "require_lookup": False,
        "require_detection": False,
        "require_source_class": False,
        "require_threshold_policy": False,
        "require_time_window": False,
        "require_primary_fixture": False,
    }

    for token in contract.get("hard_preconditions") or []:
        field_name = _CATALOG_REQUIRE_MAP.get(str(token))
        if field_name:
            flags[field_name] = True

    if template_ref or (entry and entry.template_ref):
        flags["require_template"] = True
    if evidence_ref:
        flags["require_evidence_contract"] = True
    if lookup_ref:
        flags["require_lookup"] = True
    if detection_ref or detection_family:
        flags["require_detection"] = True
    if _resolve_source_class(plan, entry):
        flags["require_source_class"] = True

    # S7.2: threshold precondition applies only when threshold_ref is explicit on the plan.
    flags["require_threshold_policy"] = _plan_has_threshold_ref(plan)

    clarification = set(entry.clarification_required if entry else [])
    required_slots = set(contract.get("required_slots") or [])
    flags["require_time_window"] = (
        "time_window" in required_slots or "time_window" in clarification
    )

    if primary_skill in PRIMARY_FIXTURE_BLOCKED_SKILLS:
        flags["require_primary_fixture"] = True

    return flags


def _resolve_template_state(
    template_ref: str | None,
    snapshot: PromotionRegistrySnapshot,
) -> tuple[bool, bool]:
    if not template_ref:
        return True, False
    if template_ref not in snapshot.template_refs:
        return False, False
    template = get_spl_template(template_ref)
    if template is None:
        return False, False
    return True, bool(template.sample_only)


def _resolve_evidence_state(
    evidence_ref: str | None,
    snapshot: PromotionRegistrySnapshot,
) -> bool:
    if not evidence_ref:
        return True
    return evidence_contract_exists(evidence_ref, snapshot)


def _resolve_lookup_state(
    lookup_ref: str | None,
    snapshot: PromotionRegistrySnapshot,
    active_settings: Settings,
) -> tuple[bool, bool]:
    if not lookup_ref:
        return True, True
    if not active_settings.ioc_registry_enabled:
        return False, False
    if lookup_ref not in snapshot.lookup_refs:
        return False, False
    staleness = evaluate_registry_staleness(_ioc_registry_path(active_settings.ioc_registry_path or None))
    fresh = staleness == StalenessStatus.FRESH
    return True, fresh


def _resolve_detection_state(
    detection_ref: str | None,
    detection_family: str | None,
    snapshot: PromotionRegistrySnapshot,
    active_settings: Settings,
) -> tuple[bool, bool]:
    if not detection_ref and not detection_family:
        return True, True
    if not active_settings.detection_registry_enabled:
        return False, False

    if detection_ref:
        registered = detection_ref in snapshot.detection_refs_all
        vetted = detection_ref in snapshot.detection_refs_bindable
        return registered, vetted

    registry = load_detection_registry(_detection_registry_path(active_settings.detection_registry_path or None))
    family_key = (detection_family or "").strip().lower()
    candidates = registry.by_family.get(family_key, [])
    if not candidates:
        return False, False
    approved = [record for record in candidates if record.vetting_status == VettingStatus.APPROVED]
    return True, bool(approved)


def _resolve_source_class_state(source_class: str | None) -> bool:
    if not source_class:
        return True
    return source_class in APPROVED_SOURCE_CLASS_HINTS


def _resolve_threshold_policy_present(plan: dict[str, Any]) -> bool:
    return _plan_has_threshold_ref(plan)


def _manifest_shape_has_time_window(entry: PatternCoverageEntry | None) -> bool:
    if entry is None:
        return False
    shape = entry.route_plan_shape
    tw = shape.get("time_window")
    if isinstance(tw, str) and tw.strip():
        return True
    parameters = shape.get("parameters")
    return isinstance(parameters, dict) and bool(parameters.get("time_window"))


def _resolve_primary_fixture_available(primary_skill: str) -> bool:
    if primary_skill not in PRIMARY_FIXTURE_BLOCKED_SKILLS:
        return True
    return False


__all__ = [
    "PRIMARY_FIXTURE_BLOCKED_SKILLS",
    "build_hard_precondition_dependency_state",
    "build_hard_precondition_dependency_state_for_coverage",
]
