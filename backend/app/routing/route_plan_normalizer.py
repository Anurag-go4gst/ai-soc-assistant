from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.routing.route_plan_models import LookupStatus, RuntimeSkill


TIME_WINDOW_ALIASES = {
    "last 24 hours": "last_24_hours",
    "last_24_hour": "last_24_hours",
    "last_24_hours": "last_24_hours",
    "last hour": "last_1_hour",
    "last 1 hour": "last_1_hour",
    "last_1_hour": "last_1_hour",
    "today": "today",
}
ENRICHMENT_ALIASES = {
    "entity_context": RuntimeSkill.ENTITY_CONTEXT_LOOKUP.value,
    "entity_context_lookup": RuntimeSkill.ENTITY_CONTEXT_LOOKUP.value,
    "notable_risk": RuntimeSkill.NOTABLE_RISK_LOOKUP.value,
    "notable_risk_lookup": RuntimeSkill.NOTABLE_RISK_LOOKUP.value,
    "lookup_correlation": RuntimeSkill.LOOKUP_CORRELATION.value,
    "entity_timeline": RuntimeSkill.ENTITY_TIMELINE.value,
    "behavioral_detection_binding": RuntimeSkill.BEHAVIORAL_DETECTION_BINDING.value,
}


def normalize_route_plan_candidate(candidate: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str]]:
    plan = deepcopy(candidate)
    warnings: list[str] = []
    blocking_findings: list[str] = []

    _normalize_confidence(plan, warnings)
    _normalize_time_windows(plan)
    _normalize_parameter_exclusions(plan, warnings, blocking_findings)
    _normalize_post_enrichment(plan, warnings, blocking_findings)
    _remove_duplicate_primary_enrichments(plan, warnings)
    _remove_arbitrary_workflow_steps(plan, blocking_findings)

    return plan, warnings, blocking_findings


def _normalize_confidence(plan: dict[str, Any], warnings: list[str]) -> None:
    metadata = plan.get("model_advisory_metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    for key in ("confidence", "model_confidence", "self_reported_confidence"):
        if key in plan:
            metadata["model_self_reported_confidence"] = plan.pop(key)
            warnings.append("model_confidence_moved_to_advisory_metadata")
    if "confidence" in metadata:
        metadata["model_self_reported_confidence"] = metadata.pop("confidence")
        warnings.append("model_confidence_renamed_to_model_self_reported_confidence")
    plan["model_advisory_metadata"] = metadata


def _normalize_time_windows(plan: dict[str, Any]) -> None:
    if isinstance(plan.get("time_window"), str):
        plan["time_window"] = _normalize_time_window_value(plan["time_window"])
    parameters = plan.get("parameters")
    if isinstance(parameters, dict) and isinstance(parameters.get("time_window"), str):
        parameters["time_window"] = _normalize_time_window_value(parameters["time_window"])


def _normalize_time_window_value(value: str) -> str:
    normalized = " ".join(value.lower().strip().replace("-", " ").split())
    return TIME_WINDOW_ALIASES.get(normalized, value.strip().lower().replace(" ", "_"))


def _normalize_parameter_exclusions(plan: dict[str, Any], warnings: list[str], blocking_findings: list[str]) -> None:
    parameters = plan.setdefault("parameters", {})
    if not isinstance(parameters, dict):
        blocking_findings.append("parameters_must_be_object")
        return

    exclusions = parameters.get("exclusions")
    normalized_exclusions: list[dict[str, Any]] = []
    if isinstance(exclusions, list):
        for exclusion in exclusions:
            normalized = _normalize_exclusion(exclusion, plan)
            if normalized is None:
                blocking_findings.append("invalid_or_ambiguous_exclusion")
            else:
                normalized_exclusions.append(normalized)

    if "exclude_entities" in parameters:
        normalized = _normalize_legacy_exclude_entities(parameters.pop("exclude_entities"), plan)
        if normalized is None:
            blocking_findings.append("ambiguous_exclude_entities")
        else:
            normalized_exclusions.append(normalized)
            warnings.append("legacy_exclude_entities_normalized")

    if "lookup" in parameters:
        normalized = _normalize_legacy_lookup(parameters.pop("lookup"), plan)
        if normalized is None:
            blocking_findings.append("ambiguous_lookup_exclusion")
        else:
            normalized_exclusions.append(normalized)
            warnings.append("legacy_lookup_exclusion_normalized")

    if normalized_exclusions:
        parameters["exclusions"] = _dedupe_dicts(normalized_exclusions)


def _normalize_exclusion(exclusion: Any, plan: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(exclusion, dict):
        return None
    if exclusion.get("type") != "lookup":
        return None
    lookup_name = _clean_optional_str(exclusion.get("lookup_name") or exclusion.get("lookup_ref"))
    match_field = _clean_optional_str(exclusion.get("match_field")) or _infer_match_field(plan)
    lookup_status = _clean_optional_str(exclusion.get("lookup_status")) or LookupStatus.UNKNOWN.value
    if lookup_status not in {status.value for status in LookupStatus}:
        return None
    if not lookup_name or not match_field:
        return None
    return {
        "type": "lookup",
        "lookup_name": lookup_name,
        "lookup_status": lookup_status,
        "match_field": match_field,
    }


def _normalize_legacy_exclude_entities(value: Any, plan: dict[str, Any]) -> dict[str, Any] | None:
    lookup_name = _clean_optional_str(value)
    match_field = _infer_match_field(plan)
    if not lookup_name or not match_field:
        return None
    return {
        "type": "lookup",
        "lookup_name": lookup_name,
        "lookup_status": LookupStatus.APPROVED.value,
        "match_field": match_field,
    }


def _normalize_legacy_lookup(value: Any, plan: dict[str, Any]) -> dict[str, Any] | None:
    raw = _clean_optional_str(value)
    if not raw:
        return None
    lookup_status = LookupStatus.UNKNOWN.value
    lookup_name = raw
    for prefix, status in (("approved_", LookupStatus.APPROVED.value), ("unavailable_", LookupStatus.UNAVAILABLE.value)):
        if raw.startswith(prefix):
            lookup_status = status
            lookup_name = raw.removeprefix(prefix)
            break
    match_field = _infer_match_field(plan)
    if not lookup_name or not match_field:
        return None
    return {
        "type": "lookup",
        "lookup_name": lookup_name,
        "lookup_status": lookup_status,
        "match_field": match_field,
    }


def _normalize_post_enrichment(plan: dict[str, Any], warnings: list[str], blocking_findings: list[str]) -> None:
    post_enrichment = plan.get("post_enrichment")
    if post_enrichment in (None, ""):
        plan["post_enrichment"] = []
        return
    if not isinstance(post_enrichment, list):
        blocking_findings.append("post_enrichment_must_be_list")
        return

    normalized_items: list[dict[str, str]] = []
    for item in post_enrichment:
        if isinstance(item, dict):
            skill = _normalize_enrichment_skill(item.get("skill"))
            input_name = _clean_optional_str(item.get("input"))
            if not skill or not input_name:
                blocking_findings.append("invalid_structured_post_enrichment")
                continue
            normalized_items.append({"skill": skill, "input": input_name})
            continue
        if isinstance(item, str):
            skill = _normalize_enrichment_skill(item)
            input_name = _infer_post_enrichment_input(plan)
            if not skill or not input_name:
                blocking_findings.append("ambiguous_post_enrichment")
                continue
            normalized_items.append({"skill": skill, "input": input_name})
            warnings.append("post_enrichment_string_normalized")
            continue
        blocking_findings.append("invalid_post_enrichment_item")
    plan["post_enrichment"] = _dedupe_dicts(normalized_items)


def _remove_duplicate_primary_enrichments(plan: dict[str, Any], warnings: list[str]) -> None:
    parameters = plan.get("parameters")
    if not isinstance(parameters, dict):
        return
    primary_enrichments = parameters.get("enrichments")
    post_skills = {item.get("skill") for item in plan.get("post_enrichment", []) if isinstance(item, dict)}
    if not isinstance(primary_enrichments, list) or not post_skills:
        return
    retained = []
    removed = False
    for enrichment in primary_enrichments:
        normalized = _normalize_enrichment_skill(enrichment)
        if normalized in post_skills:
            removed = True
            continue
        retained.append(enrichment)
    if retained:
        parameters["enrichments"] = retained
    else:
        parameters.pop("enrichments", None)
    if removed:
        warnings.append("duplicate_primary_enrichment_removed")


def _remove_arbitrary_workflow_steps(plan: dict[str, Any], blocking_findings: list[str]) -> None:
    if "workflow_steps" in plan or "action_chain" in plan or "actions" in plan:
        blocking_findings.append("arbitrary_workflow_or_action_chain_rejected")


def _normalize_enrichment_skill(value: Any) -> str | None:
    raw = _clean_optional_str(value)
    if not raw:
        return None
    return ENRICHMENT_ALIASES.get(raw, raw)


def _infer_match_field(plan: dict[str, Any]) -> str | None:
    parameters = plan.get("parameters")
    if isinstance(parameters, dict):
        group_by = parameters.get("group_by")
        if isinstance(group_by, dict):
            field = _clean_optional_str(group_by.get("field"))
            if field:
                return field
    entities = plan.get("entities")
    if isinstance(entities, list) and len(entities) == 1:
        return _clean_optional_str(entities[0])
    return None


def _infer_post_enrichment_input(plan: dict[str, Any]) -> str | None:
    primary_skill = plan.get("primary_skill")
    if primary_skill == RuntimeSkill.AGGREGATE_AND_RANK.value:
        return "ranked_users" if _infer_match_field(plan) == "user" else "ranked_entities"
    if primary_skill == RuntimeSkill.MULTI_SIGNAL_CORRELATION.value:
        return "sub_results"
    if primary_skill in {RuntimeSkill.NOTABLE_RISK_LOOKUP.value, RuntimeSkill.ENTITY_TIMELINE.value}:
        return "entities"
    return None


def _clean_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _dedupe_dicts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[tuple[str, Any], ...]] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
        key = tuple(sorted(item.items()))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped
