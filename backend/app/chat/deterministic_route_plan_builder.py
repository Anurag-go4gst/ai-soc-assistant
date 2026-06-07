from __future__ import annotations

from hashlib import sha256
from typing import Any

from app.query_understanding.models import QueryUnderstandingResult
from app.routing.route_plan_models import MetricType, RouteStatus, RuntimeSkill, SortDirection
from app.spl.template_registry import SplTemplateDefinition, get_spl_template
from app.use_cases.models import UseCaseSelection


def build_deterministic_route_plan_candidate(
    *,
    query: str,
    selected_use_case: UseCaseSelection | None,
    query_understanding: QueryUnderstandingResult | None = None,
) -> dict[str, Any] | None:
    """Build a governed route-plan candidate from registry/catalog facts.

    This is intentionally narrow: it only emits a plan when the deterministic
    catalog selected a use case that has a concrete SPL template. It does not
    infer new detections or author arbitrary SPL from free text.
    """
    if selected_use_case is None or not selected_use_case.default_spl_template:
        return None

    template = get_spl_template(selected_use_case.default_spl_template)
    if template is None or not _template_can_drive_route_plan(template):
        return None

    time_window = _time_window(query_understanding, template)
    group_by = _group_by_field(template, selected_use_case)
    metric_field = _metric_field(template)
    limit = _result_limit(template)

    return {
        "route_plan_id": _route_plan_id(query, selected_use_case.use_case_id, template.template_id),
        "route_status": RouteStatus.ROUTE_READY.value,
        "primary_skill": RuntimeSkill.AGGREGATE_AND_RANK.value,
        "pattern_id": selected_use_case.use_case_id,
        "operation_type": "top_n",
        "domain": _domain(selected_use_case, template),
        "source_class": _source_class(selected_use_case, template),
        "entities": {},
        "time_window": time_window,
        "parameters": {
            "group_by": {"field": group_by},
            "metric": {"type": MetricType.COUNT.value, "field": metric_field},
            "sort": {"field": metric_field, "direction": SortDirection.DESC.value},
            "limit": limit,
            "template_id": template.template_id,
        },
        "evidence_needs": {
            "template_id": template.template_id,
            "query_shape": template.query_shape,
            "group_by": [group_by],
            "metric": {"type": MetricType.COUNT.value, "field": metric_field},
        },
        "missing_slots": [],
        "hard_preconditions": [
            "source_available",
            "template_available",
            "metric_defined",
            "grouping_field_defined",
        ],
        "post_enrichment": [],
        "model_advisory_metadata": {
            "candidate_source": "deterministic_control_plane",
            "use_case_id": selected_use_case.use_case_id,
            "template_id": template.template_id,
            "llm_authored": False,
        },
        "deterministic_validation": {
            "source": "use_case_catalog_default_template",
            "selected_use_case_id": selected_use_case.use_case_id,
            "template_id": template.template_id,
            "query_understanding_match_path": query_understanding.deterministic_match_path
            if query_understanding
            else None,
        },
    }


def _template_can_drive_route_plan(template: SplTemplateDefinition) -> bool:
    return bool(template.spl_text or template.render_pattern) and template.status == "active"


def _route_plan_id(query: str, use_case_id: str, template_id: str) -> str:
    digest = sha256(f"{use_case_id}:{template_id}:{query}".encode("utf-8")).hexdigest()[:12]
    return f"rp_det_{digest}"


def _time_window(
    query_understanding: QueryUnderstandingResult | None,
    template: SplTemplateDefinition,
) -> str:
    if query_understanding and query_understanding.entities.time_window:
        return query_understanding.entities.time_window
    if template.default_time_window:
        if "earliest=-60m" in template.default_time_window:
            return "last_1_hour"
        if "earliest=-24h" in template.default_time_window:
            return "last_24_hours"
    return "last_24_hours"


def _group_by_field(template: SplTemplateDefinition, selected_use_case: UseCaseSelection) -> str:
    if template.group_by_fields:
        return template.group_by_fields[0]
    if selected_use_case.use_case_id == "aws_security_group_modifications":
        return "userIdentity.arn"
    if "source_ip" in selected_use_case.optional_sources or "src" in template.returned_fields:
        return "src"
    if "user" in template.returned_fields:
        return "user"
    return template.returned_fields[0] if template.returned_fields else "user"


def _metric_field(template: SplTemplateDefinition) -> str:
    if template.metric_fields:
        return template.metric_fields[0]
    for candidate in ("change_count", "event_count", "failed_logins", "fail_count", "count"):
        if candidate in template.returned_fields:
            return candidate
    return "count"


def _result_limit(template: SplTemplateDefinition) -> int:
    max_rows = template.result_limits.get("max_rows") if isinstance(template.result_limits, dict) else None
    return int(max_rows) if isinstance(max_rows, int) else 100


def _domain(selected_use_case: UseCaseSelection, template: SplTemplateDefinition) -> str:
    category = selected_use_case.category.lower()
    if "cloud" in category or "aws" in category:
        return "cloud"
    if "auth" in category or "identity" in category:
        return "identity"
    return template.query_shape


def _source_class(selected_use_case: UseCaseSelection, template: SplTemplateDefinition) -> str:
    if selected_use_case.use_case_id.startswith("aws_"):
        return "aws_cloudtrail"
    rules = template.validation_rules if isinstance(template.validation_rules, dict) else {}
    sourcetypes = rules.get("allowed_sourcetypes")
    if isinstance(sourcetypes, list) and sourcetypes:
        return str(sourcetypes[0]).replace(":", "_")
    return selected_use_case.category.lower().replace(" / ", "_").replace(" ", "_")
