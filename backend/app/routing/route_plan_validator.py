from __future__ import annotations

import re
from typing import Any

from app.routing.route_plan_models import (
    LookupStatus,
    MetricType,
    RoutePlanValidationResult,
    RouteStatus,
    RuntimeSkill,
    SortDirection,
    route_status_values,
    runtime_skill_values,
)
from app.routing.route_plan_normalizer import normalize_route_plan_candidate
from app.routing.runtime_skill_catalog import get_skill_contract


GROUPING_ONLY_DESCRIPTORS = {"user", "host", "src_ip", "dest_ip", "source_ip", "destination_ip", "entity", "account"}
METRIC_EXPRESSION_MARKERS = ("count(", "dc(", "sum(", "avg(", "stats ", " by ", " as ", "|")
REGISTRY_REF_PATTERN = re.compile(r"^[a-z][a-z0-9._-]{2,}$")


def validate_route_plan_candidate(candidate: dict[str, Any]) -> RoutePlanValidationResult:
    plan, warnings, normalization_blocks = normalize_route_plan_candidate(candidate)
    validation_findings: list[str] = []
    blocking_findings: list[str] = list(normalization_blocks)

    _validate_required_top_level(plan, blocking_findings)
    _validate_route_status(plan, blocking_findings)
    _validate_primary_skill(plan, blocking_findings)
    _validate_operation_type(plan, blocking_findings)
    _validate_confidence_advisory_only(plan, validation_findings, blocking_findings, warnings)
    _validate_skill_slots(plan, blocking_findings)
    _validate_skill_parameter_shapes(plan, blocking_findings)
    _validate_aggregate_parameters(plan, blocking_findings)
    _validate_exclusions(plan, blocking_findings)
    _validate_post_enrichment(plan, blocking_findings)
    _validate_composition(plan, blocking_findings)

    if blocking_findings:
        if any(
            "composition" in finding or "sub_invocations" in finding or "post_enrichment_not_allowed" in finding
            for finding in blocking_findings
        ):
            plan["route_status"] = RouteStatus.BLOCKED_INVALID_COMPOSITION.value
        else:
            plan["route_status"] = RouteStatus.BLOCKED_INVALID_PARAMETERS.value

    is_valid = not blocking_findings and plan.get("route_status") == RouteStatus.ROUTE_READY.value
    return RoutePlanValidationResult(
        is_valid=is_valid,
        normalized_route_plan=plan if is_valid or plan else None,
        validation_findings=validation_findings,
        blocking_findings=sorted(set(blocking_findings)),
        warnings=sorted(set(warnings)),
    )


def _validate_required_top_level(plan: dict[str, Any], blocking_findings: list[str]) -> None:
    required = {
        "route_plan_id",
        "route_status",
        "primary_skill",
        "pattern_id",
        "operation_type",
        "domain",
        "source_class",
        "entities",
        "time_window",
        "parameters",
        "missing_slots",
        "hard_preconditions",
        "model_advisory_metadata",
        "deterministic_validation",
    }
    for field in sorted(required):
        if field not in plan:
            blocking_findings.append(f"missing_required_field:{field}")


def _validate_route_status(plan: dict[str, Any], blocking_findings: list[str]) -> None:
    route_status = plan.get("route_status")
    if route_status not in route_status_values():
        blocking_findings.append("invalid_route_status")


def _validate_operation_type(plan: dict[str, Any], blocking_findings: list[str]) -> None:
    if plan.get("route_status") != RouteStatus.ROUTE_READY.value:
        return
    primary_skill = plan.get("primary_skill")
    operation_type = plan.get("operation_type")
    if not isinstance(primary_skill, str) or not primary_skill:
        return
    if not isinstance(operation_type, str) or not str(operation_type).strip():
        blocking_findings.append("route_ready_requires_operation_type")
        return
    contract = get_skill_contract(primary_skill)
    if not contract:
        return
    allowed = contract.get("allowed_operation_types") or []
    if operation_type not in allowed:
        blocking_findings.append(f"operation_type_not_allowed_for_skill:{primary_skill}:{operation_type}")


def _validate_primary_skill(plan: dict[str, Any], blocking_findings: list[str]) -> None:
    primary_skill = plan.get("primary_skill")
    if isinstance(primary_skill, list):
        blocking_findings.append("primary_skill_must_be_exactly_one")
        return
    if plan.get("route_status") == RouteStatus.ROUTE_READY.value and not primary_skill:
        blocking_findings.append("route_ready_requires_primary_skill")
    if primary_skill and primary_skill not in runtime_skill_values():
        blocking_findings.append(f"unknown_primary_skill:{primary_skill}")


def _validate_confidence_advisory_only(
    plan: dict[str, Any],
    validation_findings: list[str],
    blocking_findings: list[str],
    warnings: list[str],
) -> None:
    metadata = plan.get("model_advisory_metadata")
    if isinstance(metadata, dict) and "model_self_reported_confidence" in metadata:
        validation_findings.append("model_self_reported_confidence_ignored_for_validation")
        warnings.append("model_self_reported_confidence_is_advisory_only")
    text = " ".join(str(value).lower() for value in plan.values() if isinstance(value, (str, int, float, bool)))
    if "confidence" in text and "justification" in text:
        blocking_findings.append("confidence_must_not_be_used_as_justification")


def _validate_skill_slots(plan: dict[str, Any], blocking_findings: list[str]) -> None:
    primary_skill = plan.get("primary_skill")
    if not isinstance(primary_skill, str):
        return
    contract = get_skill_contract(primary_skill)
    if not contract:
        return
    parameters = plan.get("parameters") if isinstance(plan.get("parameters"), dict) else {}
    for slot in contract["required_slots"]:
        if slot == "sub_invocations":
            if not plan.get("sub_invocations"):
                blocking_findings.append("missing_required_slot:sub_invocations")
            continue
        if slot in {"group_by", "metric", "threshold_ref", "lookup_ref", "match_field", "detection_ref"}:
            if not parameters.get(slot):
                blocking_findings.append(f"missing_required_slot:{slot}")
            continue
        if not plan.get(slot) and not parameters.get(slot):
            blocking_findings.append(f"missing_required_slot:{slot}")


def _validate_skill_parameter_shapes(plan: dict[str, Any], blocking_findings: list[str]) -> None:
    primary_skill = plan.get("primary_skill")
    if not isinstance(primary_skill, str):
        return
    parameters = plan.get("parameters")
    if not isinstance(parameters, dict):
        return
    if primary_skill == RuntimeSkill.AGGREGATE_AND_RANK.value:
        return
    if primary_skill == RuntimeSkill.THRESHOLD_ANOMALY.value:
        _validate_threshold_parameters(parameters, blocking_findings)
    elif primary_skill == RuntimeSkill.LOOKUP_CORRELATION.value:
        _validate_lookup_parameters(parameters, blocking_findings)
    elif primary_skill in {
        RuntimeSkill.SEQUENCE_DETECTION.value,
        RuntimeSkill.BEHAVIORAL_DETECTION_BINDING.value,
    }:
        _validate_detection_ref_parameter(parameters, blocking_findings)
    elif primary_skill == RuntimeSkill.MULTI_SIGNAL_CORRELATION.value:
        return


def _validate_threshold_parameters(parameters: dict[str, Any], blocking_findings: list[str]) -> None:
    metric = parameters.get("metric")
    if metric is not None and isinstance(metric, dict):
        metric_type = metric.get("type")
        if metric_type not in {item.value for item in MetricType}:
            blocking_findings.append("invalid_metric_type")
    _validate_registry_ref_slot(parameters.get("threshold_ref"), "threshold_ref", blocking_findings)


def _validate_lookup_parameters(parameters: dict[str, Any], blocking_findings: list[str]) -> None:
    _validate_registry_ref_slot(parameters.get("lookup_ref"), "lookup_ref", blocking_findings)
    match_field = parameters.get("match_field")
    if match_field is not None:
        _validate_plain_field_name(match_field, "match_field", blocking_findings)


def _validate_detection_ref_parameter(parameters: dict[str, Any], blocking_findings: list[str]) -> None:
    _validate_registry_ref_slot(parameters.get("detection_ref"), "detection_ref", blocking_findings)


def _validate_registry_ref_slot(value: Any, slot_name: str, blocking_findings: list[str]) -> None:
    if value is None:
        return
    if isinstance(value, dict):
        ref = value.get("ref") or value.get("policy_id") or value.get("detection_id") or value.get("lookup_name")
        if isinstance(ref, str) and ref.strip():
            if REGISTRY_REF_PATTERN.match(ref.strip()):
                return
        blocking_findings.append(f"invalid_{slot_name}_structure")
        return
    if isinstance(value, str) and REGISTRY_REF_PATTERN.match(value.strip()):
        return
    blocking_findings.append(f"invalid_{slot_name}_structure")


def _validate_plain_field_name(value: Any, slot_name: str, blocking_findings: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        blocking_findings.append(f"invalid_{slot_name}_structure")
        return
    if _looks_like_metric_expression(value):
        blocking_findings.append(f"invalid_{slot_name}_structure")


def _validate_aggregate_parameters(plan: dict[str, Any], blocking_findings: list[str]) -> None:
    if plan.get("primary_skill") != RuntimeSkill.AGGREGATE_AND_RANK.value:
        return
    parameters = plan.get("parameters")
    if not isinstance(parameters, dict):
        blocking_findings.append("parameters_must_be_object")
        return
    group_by = parameters.get("group_by")
    metric = parameters.get("metric")
    if not isinstance(group_by, dict):
        blocking_findings.append("aggregate_and_rank_requires_group_by")
    if not isinstance(metric, dict):
        blocking_findings.append("aggregate_and_rank_requires_metric")
        return
    if isinstance(group_by, dict):
        group_field = str(group_by.get("field", "")).strip()
        if not group_field:
            blocking_findings.append("group_by_field_required")
        if _looks_like_metric_expression(group_field):
            blocking_findings.append("group_by_field_must_not_be_metric_expression")
    metric_type = metric.get("type")
    metric_field = str(metric.get("field", "")).strip()
    if metric_type not in {item.value for item in MetricType}:
        blocking_findings.append("invalid_metric_type")
    if not metric_field:
        blocking_findings.append("metric_field_required")
    if metric_type != MetricType.COUNT.value and metric_field in GROUPING_ONLY_DESCRIPTORS:
        blocking_findings.append("metric_field_must_not_be_grouping_only_descriptor")
    sort = parameters.get("sort")
    if sort is not None:
        if not isinstance(sort, dict):
            blocking_findings.append("sort_must_be_object")
        elif sort.get("direction") not in {item.value for item in SortDirection}:
            blocking_findings.append("invalid_sort_direction")


def _validate_exclusions(plan: dict[str, Any], blocking_findings: list[str]) -> None:
    parameters = plan.get("parameters")
    if not isinstance(parameters, dict):
        return
    exclusions = parameters.get("exclusions", [])
    if not isinstance(exclusions, list):
        blocking_findings.append("exclusions_must_be_list")
        return
    for exclusion in exclusions:
        if not isinstance(exclusion, dict):
            blocking_findings.append("exclusion_must_be_object")
            continue
        if exclusion.get("type") != "lookup":
            blocking_findings.append("exclusion_type_must_be_lookup")
        if not exclusion.get("lookup_name"):
            blocking_findings.append("exclusion_lookup_name_required")
        if exclusion.get("lookup_status") not in {status.value for status in LookupStatus}:
            blocking_findings.append("invalid_exclusion_lookup_status")
        if not exclusion.get("match_field"):
            blocking_findings.append("exclusion_match_field_required")


def _validate_post_enrichment(plan: dict[str, Any], blocking_findings: list[str]) -> None:
    post_enrichment = plan.get("post_enrichment", [])
    if not isinstance(post_enrichment, list):
        blocking_findings.append("post_enrichment_must_be_list")
        return
    for item in post_enrichment:
        if not isinstance(item, dict):
            blocking_findings.append("post_enrichment_item_must_be_structured")
            continue
        skill = item.get("skill")
        if skill not in runtime_skill_values():
            blocking_findings.append(f"unknown_post_enrichment_skill:{skill}")
        if not item.get("input"):
            blocking_findings.append("post_enrichment_input_required")


def _validate_composition(plan: dict[str, Any], blocking_findings: list[str]) -> None:
    primary_skill = plan.get("primary_skill")
    if not isinstance(primary_skill, str):
        return
    contract = get_skill_contract(primary_skill)
    if not contract:
        return
    post_enrichment = plan.get("post_enrichment", [])
    if isinstance(post_enrichment, list):
        allowed = set(contract["allowed_post_enrichments"])
        for item in post_enrichment:
            if isinstance(item, dict) and item.get("skill") not in allowed:
                blocking_findings.append(f"post_enrichment_not_allowed:{primary_skill}->{item.get('skill')}")
    sub_invocations = plan.get("sub_invocations", [])
    if sub_invocations in (None, ""):
        return
    if not isinstance(sub_invocations, list):
        blocking_findings.append("sub_invocations_must_be_list")
        return
    allows_sub = contract.get("allows_sub_invocations")
    if sub_invocations and not allows_sub:
        blocking_findings.append(f"sub_invocations_not_allowed_for_skill:{primary_skill}")
    elif sub_invocations and allows_sub is not True:
        blocking_findings.append("sub_invocations_allowed_flag_missing_in_contract")
    if primary_skill == RuntimeSkill.MULTI_SIGNAL_CORRELATION.value:
        _validate_multi_signal_sub_invocations(sub_invocations, blocking_findings)


def _validate_multi_signal_sub_invocations(sub_invocations: list[Any], blocking_findings: list[str]) -> None:
    for sub_invocation in sub_invocations:
        if not isinstance(sub_invocation, dict):
            blocking_findings.append("sub_invocation_must_be_object")
            continue
        skill = sub_invocation.get("primary_skill") or sub_invocation.get("skill")
        if skill not in runtime_skill_values():
            blocking_findings.append(f"unknown_sub_invocation_skill:{skill}")
        if skill == RuntimeSkill.MULTI_SIGNAL_CORRELATION.value:
            blocking_findings.append("nested_multi_signal_correlation_rejected")
        if sub_invocation.get("sub_invocations"):
            blocking_findings.append("nested_sub_invocations_rejected")
        if "workflow_steps" in sub_invocation or "action_chain" in sub_invocation or "actions" in sub_invocation:
            blocking_findings.append("sub_invocation_action_chain_rejected")


def _looks_like_metric_expression(value: str) -> bool:
    normalized = value.lower()
    return any(marker in normalized for marker in METRIC_EXPRESSION_MARKERS) or bool(re.search(r"\w+\(.+\)", normalized))
