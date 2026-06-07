"""Stage 3K-Q1C deterministic route-plan → SPL template matcher (library only).

Dry-run matching against the Q1B template registry. Does not render SPL, call MCP,
or wire into ``/chat`` (Q1E). Authoritative for template selection; LLM hints are
applied only via ``template_matcher_llm_assist``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Sequence

from app.safeguards.spl_validator import APPROVED_DATAMODELS, DATAMODEL_ALIASES
from app.spl.template_registry import (
    QUERY_SHAPE_FROM_DATAMODEL,
    QUERY_SHAPE_RAW_SEARCH,
    QUERY_SHAPE_TSTATS_DATAMODEL,
    SplTemplateDefinition,
    load_spl_templates,
)

MISMATCH_UNKNOWN_DATAMODEL = "unknown_datamodel"
MISMATCH_CANNOT_RESOLVE_DATAMODEL = "cannot_resolve_datamodel"
MISMATCH_DATAMODEL_MISMATCH = "datamodel_mismatch"
MISMATCH_UNSUPPORTED_GROUP_BY = "unsupported_group_by"
MISMATCH_UNSUPPORTED_METRIC = "unsupported_metric"
MISMATCH_NO_TEMPLATE_FOR_SKILL = "no_template_for_skill"
MISMATCH_TIME_WINDOW = "time_window_not_satisfiable"
MISMATCH_RESULT_LIMIT = "result_limit_not_satisfiable"
MISMATCH_VALIDATOR_PROFILE = "validator_profile_mismatch"
MISMATCH_AMBIGUOUS = "ambiguous_match"

VALID_MISMATCH_REASONS = frozenset(
    {
        MISMATCH_UNKNOWN_DATAMODEL,
        MISMATCH_CANNOT_RESOLVE_DATAMODEL,
        MISMATCH_DATAMODEL_MISMATCH,
        MISMATCH_UNSUPPORTED_GROUP_BY,
        MISMATCH_UNSUPPORTED_METRIC,
        MISMATCH_NO_TEMPLATE_FOR_SKILL,
        MISMATCH_TIME_WINDOW,
        MISMATCH_RESULT_LIMIT,
        MISMATCH_VALIDATOR_PROFILE,
        MISMATCH_AMBIGUOUS,
    }
)

SKILL_AGGREGATION_SHAPES: dict[str, tuple[str, ...]] = {
    "aggregate_and_rank": ("ranked_entities",),
    "threshold_anomaly": ("ranked_entities", "non_aggregate"),
    "metadata_discovery": ("non_aggregate",),
    "entity_timeline": ("timechart",),
}

OPERATION_TYPE_AGGREGATION: dict[str, str] = {
    "top_n": "ranked_entities",
    "rank": "ranked_entities",
    "threshold": "ranked_entities",
    "field_discovery": "non_aggregate",
    "correlate_signals": "non_aggregate",
}

SOURCE_CLASS_TO_DATAMODEL: dict[str, str] = {
    "okta_authentication_logs": "Authentication",
    "windows_security": "Authentication",
    "identity_authentication": "Authentication",
    "active_directory": "Authentication",
    "network_traffic": "Network_Traffic",
    "firewall_logs": "Network_Traffic",
    "dns_logs": "Network_Resolution",
    "network_resolution": "Network_Resolution",
}

CIM_QUERY_SHAPES = frozenset({QUERY_SHAPE_TSTATS_DATAMODEL, QUERY_SHAPE_FROM_DATAMODEL})


@dataclass
class TemplateCandidateScore:
    template_id: str
    match_score: float
    match_reasons: list[str] = field(default_factory=list)
    mismatch_reasons: list[str] = field(default_factory=list)
    production_executable: bool = False
    sample_only: bool = False
    validator_profile: str | None = None
    datamodel: str | None = None


@dataclass
class TemplateMatchResult:
    matched_template_id: str | None
    matched: bool
    match_score: float
    match_reasons: list[str] = field(default_factory=list)
    mismatch_reasons: list[str] = field(default_factory=list)
    candidate_template_ids: list[str] = field(default_factory=list)
    production_executable: bool = False
    sample_only: bool = False
    validator_profile: str | None = None
    datamodel: str | None = None
    execution_authorized: bool = False
    disagreements: list[dict[str, Any]] = field(default_factory=list)
    template_match_llm_hints: dict[str, Any] | None = None
    llm_assist_timed_out: bool = False
    llm_assist_enabled: bool = False
    coe_synthetic_fixture: bool = True
    captured_live_run: bool = False
    production_execution: bool = False

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class _RoutePlanMatchContext:
    template_id: str | None
    runtime_skill: str
    operation_type: str | None
    source_class: str | None
    datamodel: str | None
    dataset: str | None
    group_by_fields: frozenset[str]
    metric_type: str | None
    metric_field: str | None
    time_window: str | None
    limit: int | None
    summariesonly: bool | None
    validator_profile: str | None
    expected_aggregation_shapes: tuple[str, ...]
    resolved_aggregation_shape: str | None


def match_route_plan_to_template(
    normalized_route_plan: dict[str, Any],
    *,
    include_disabled: bool = True,
    templates: Sequence[SplTemplateDefinition] | None = None,
) -> TemplateMatchResult:
    """Match a validated normalized route plan to the best SPL template candidate."""
    catalog = list(templates) if templates is not None else load_spl_templates()
    if not include_disabled:
        catalog = [item for item in catalog if item.is_production_executable()]
    ctx = _extract_match_context(normalized_route_plan)
    candidates = dry_run_matches(normalized_route_plan, include_disabled=include_disabled, templates=catalog)
    viable = [item for item in candidates if not item.mismatch_reasons and item.match_score > 0]
    if not viable:
        mismatch = _collect_no_match_reasons(ctx, catalog, candidates)
        return TemplateMatchResult(
            matched_template_id=None,
            matched=False,
            match_score=0.0,
            mismatch_reasons=mismatch,
            candidate_template_ids=[item.template_id for item in candidates if item.template_id],
            production_executable=False,
            datamodel=ctx.datamodel,
        )

    ranked = sorted(viable, key=lambda item: _template_rank_key(item, catalog), reverse=True)
    top = ranked[0]
    if len(ranked) > 1 and _substantive_rank_key(top, catalog) == _substantive_rank_key(ranked[1], catalog):
        return TemplateMatchResult(
            matched_template_id=None,
            matched=False,
            match_score=0.0,
            mismatch_reasons=[MISMATCH_AMBIGUOUS],
            candidate_template_ids=[item.template_id for item in ranked],
            production_executable=False,
            datamodel=ctx.datamodel,
        )

    template = _template_by_id(catalog, top.template_id)
    return TemplateMatchResult(
        matched_template_id=top.template_id,
        matched=True,
        match_score=top.match_score,
        match_reasons=top.match_reasons,
        mismatch_reasons=[],
        candidate_template_ids=[item.template_id for item in ranked],
        production_executable=template.is_production_executable() if template else False,
        sample_only=bool(template.sample_only) if template else False,
        validator_profile=template.validator_profile if template else None,
        datamodel=ctx.datamodel,
    )


def dry_run_matches(
    normalized_route_plan: dict[str, Any],
    *,
    include_disabled: bool = True,
    templates: Sequence[SplTemplateDefinition] | None = None,
) -> list[TemplateCandidateScore]:
    """Return scored template candidates for inspection (Q1E lineage)."""
    catalog = list(templates) if templates is not None else load_spl_templates()
    if not include_disabled:
        catalog = [item for item in catalog if item.is_production_executable()]
    ctx = _extract_match_context(normalized_route_plan)
    global_mismatch = _collect_global_mismatches(ctx, catalog)
    if global_mismatch:
        return [
            TemplateCandidateScore(
                template_id=template.template_id,
                match_score=0.0,
                mismatch_reasons=list(global_mismatch),
                production_executable=template.is_production_executable(),
                sample_only=template.sample_only,
                validator_profile=template.validator_profile,
                datamodel=template.datamodel,
            )
            for template in _templates_for_context(ctx, catalog)
        ] or [
            TemplateCandidateScore(
                template_id="",
                match_score=0.0,
                mismatch_reasons=list(global_mismatch),
            )
        ]

    scored: list[TemplateCandidateScore] = []
    for template in _templates_for_context(ctx, catalog):
        score, reasons, mismatches = _score_template(template, ctx)
        scored.append(
            TemplateCandidateScore(
                template_id=template.template_id,
                match_score=score,
                match_reasons=reasons,
                mismatch_reasons=mismatches,
                production_executable=template.is_production_executable(),
                sample_only=template.sample_only,
                validator_profile=template.validator_profile,
                datamodel=template.datamodel,
            )
        )
    return sorted(scored, key=lambda item: (item.match_score, item.template_id), reverse=True)


def _extract_match_context(plan: dict[str, Any]) -> _RoutePlanMatchContext:
    runtime_skill = str(plan.get("primary_skill") or plan.get("runtime_skill") or "")
    operation_type = str(plan.get("operation_type") or "") or None
    source_class = str(plan.get("source_class") or "") or None
    evidence = plan.get("evidence_needs") if isinstance(plan.get("evidence_needs"), dict) else {}
    parameters = plan.get("parameters") if isinstance(plan.get("parameters"), dict) else {}

    datamodel = _resolve_datamodel(evidence, source_class)
    dataset = evidence.get("dataset") if isinstance(evidence.get("dataset"), str) else None

    group_by_fields = _resolve_group_by_fields(evidence, parameters)
    metric = parameters.get("metric") if isinstance(parameters.get("metric"), dict) else {}
    if not metric and isinstance(evidence.get("metric"), dict):
        metric = evidence["metric"]
    metric_type = str(metric.get("type")) if metric.get("type") else None
    metric_field = str(metric.get("field")) if metric.get("field") else None

    time_window = _resolve_time_window(plan, parameters)
    limit = _resolve_limit(parameters)
    summariesonly = evidence.get("summariesonly") if "summariesonly" in evidence else None
    validator_profile = evidence.get("validator_profile") if isinstance(evidence.get("validator_profile"), str) else None

    expected_shapes = SKILL_AGGREGATION_SHAPES.get(runtime_skill, ())
    resolved_shape = OPERATION_TYPE_AGGREGATION.get(operation_type or "", None)
    if not resolved_shape and expected_shapes:
        resolved_shape = expected_shapes[0]

    return _RoutePlanMatchContext(
        template_id=evidence.get("template_id") if isinstance(evidence.get("template_id"), str) else None,
        runtime_skill=runtime_skill,
        operation_type=operation_type,
        source_class=source_class,
        datamodel=datamodel,
        dataset=dataset,
        group_by_fields=group_by_fields,
        metric_type=metric_type,
        metric_field=metric_field,
        time_window=time_window,
        limit=limit,
        summariesonly=summariesonly if isinstance(summariesonly, bool) else None,
        validator_profile=validator_profile,
        expected_aggregation_shapes=expected_shapes,
        resolved_aggregation_shape=resolved_shape,
    )


def _resolve_datamodel(evidence: dict[str, Any], source_class: str | None) -> str | None:
    raw = evidence.get("datamodel")
    if isinstance(raw, str) and raw.strip():
        normalized = DATAMODEL_ALIASES.get(raw.strip().lower(), raw.strip())
        return normalized if normalized in APPROVED_DATAMODELS else raw.strip()
    if source_class:
        return SOURCE_CLASS_TO_DATAMODEL.get(source_class.strip().lower()) or SOURCE_CLASS_TO_DATAMODEL.get(source_class)
    return None


def _resolve_group_by_fields(evidence: dict[str, Any], parameters: dict[str, Any]) -> frozenset[str]:
    fields: set[str] = set()
    group_by = parameters.get("group_by")
    if isinstance(group_by, dict) and group_by.get("field"):
        fields.add(str(group_by["field"]))
    raw_list = evidence.get("group_by")
    if isinstance(raw_list, list):
        fields.update(str(item) for item in raw_list if item)
    return frozenset(fields)


def _resolve_time_window(plan: dict[str, Any], parameters: dict[str, Any]) -> str | None:
    if isinstance(parameters.get("time_window"), str):
        return parameters["time_window"]
    if isinstance(plan.get("time_window"), str):
        return plan["time_window"]
    return None


def _resolve_limit(parameters: dict[str, Any]) -> int | None:
    limit = parameters.get("limit")
    if isinstance(limit, int):
        return limit
    if isinstance(limit, str) and limit.isdigit():
        return int(limit)
    return None


def _needs_resolved_datamodel(ctx: _RoutePlanMatchContext) -> bool:
    return ctx.runtime_skill in SKILL_AGGREGATION_SHAPES and ctx.runtime_skill != "entity_timeline"


def _collect_global_mismatches(ctx: _RoutePlanMatchContext, catalog: Sequence[SplTemplateDefinition]) -> list[str]:
    mismatches: list[str] = []
    if not ctx.runtime_skill:
        mismatches.append(MISMATCH_NO_TEMPLATE_FOR_SKILL)
        return mismatches
    if ctx.runtime_skill not in SKILL_AGGREGATION_SHAPES:
        mismatches.append(MISMATCH_NO_TEMPLATE_FOR_SKILL)
        return mismatches
    if ctx.runtime_skill == "entity_timeline":
        mismatches.append(MISMATCH_NO_TEMPLATE_FOR_SKILL)
        return mismatches
    if not ctx.expected_aggregation_shapes:
        mismatches.append(MISMATCH_NO_TEMPLATE_FOR_SKILL)
        return mismatches
    if not ctx.datamodel and _needs_resolved_datamodel(ctx) and not _raw_templates_for_context(ctx, catalog):
        mismatches.append(MISMATCH_CANNOT_RESOLVE_DATAMODEL)
    if ctx.datamodel and ctx.datamodel not in APPROVED_DATAMODELS:
        mismatches.append(MISMATCH_UNKNOWN_DATAMODEL)
        return mismatches
    if ctx.runtime_skill in {"aggregate_and_rank", "threshold_anomaly"} and not ctx.group_by_fields:
        mismatches.append(MISMATCH_UNSUPPORTED_GROUP_BY)
    if ctx.datamodel and not (_cim_templates_for_context(ctx, catalog) or _raw_templates_for_context(ctx, catalog)):
        mismatches.append(MISMATCH_NO_TEMPLATE_FOR_SKILL)
    return mismatches


def _collect_no_match_reasons(
    ctx: _RoutePlanMatchContext,
    catalog: Sequence[SplTemplateDefinition],
    candidates: list[TemplateCandidateScore],
) -> list[str]:
    mismatch = _collect_global_mismatches(ctx, catalog)
    if not mismatch:
        mismatch = sorted(
            {
                reason
                for item in candidates
                for reason in item.mismatch_reasons
                if reason in VALID_MISMATCH_REASONS
            }
        )
    if not mismatch:
        if _needs_resolved_datamodel(ctx) and not ctx.datamodel:
            mismatch = [MISMATCH_CANNOT_RESOLVE_DATAMODEL]
        else:
            mismatch = [MISMATCH_NO_TEMPLATE_FOR_SKILL]
    return mismatch


def _cim_templates_for_context(
    ctx: _RoutePlanMatchContext,
    catalog: Sequence[SplTemplateDefinition],
) -> list[SplTemplateDefinition]:
    if not ctx.datamodel:
        return []
    return [
        template
        for template in catalog
        if template.query_shape in CIM_QUERY_SHAPES and template.datamodel == ctx.datamodel
    ]


def _templates_for_context(
    ctx: _RoutePlanMatchContext,
    catalog: Sequence[SplTemplateDefinition],
) -> list[SplTemplateDefinition]:
    raw = _raw_templates_for_context(ctx, catalog)
    cim = _cim_templates_for_context(ctx, catalog)
    by_id: dict[str, SplTemplateDefinition] = {}
    for template in [*raw, *cim]:
        by_id[template.template_id] = template
    return list(by_id.values())


def _raw_templates_for_context(
    ctx: _RoutePlanMatchContext,
    catalog: Sequence[SplTemplateDefinition],
) -> list[SplTemplateDefinition]:
    return [
        template
        for template in catalog
        if template.query_shape == QUERY_SHAPE_RAW_SEARCH
        and (
            (ctx.template_id and template.template_id == ctx.template_id)
            or (ctx.template_id and template.use_case_id == ctx.template_id)
        )
    ]


def _score_template(
    template: SplTemplateDefinition,
    ctx: _RoutePlanMatchContext,
) -> tuple[float, list[str], list[str]]:
    reasons: list[str] = []
    mismatches: list[str] = []

    if template.query_shape == QUERY_SHAPE_RAW_SEARCH:
        if ctx.template_id and template.template_id == ctx.template_id:
            reasons.extend(["explicit_template_id_match", "raw_search_template"])
            if template.is_production_executable():
                reasons.append("production_executable_preferred")
            return 0.96 if template.is_production_executable() else 0.76, reasons, mismatches
        mismatches.append(MISMATCH_NO_TEMPLATE_FOR_SKILL)
        return 0.0, reasons, mismatches

    if ctx.runtime_skill not in SKILL_AGGREGATION_SHAPES:
        mismatches.append(MISMATCH_NO_TEMPLATE_FOR_SKILL)
        return 0.0, reasons, mismatches

    allowed_shapes = SKILL_AGGREGATION_SHAPES[ctx.runtime_skill]
    if template.aggregation_shape not in allowed_shapes:
        mismatches.append(MISMATCH_NO_TEMPLATE_FOR_SKILL)
        return 0.0, reasons, mismatches

    if ctx.datamodel and template.datamodel and template.datamodel != ctx.datamodel:
        mismatches.append(MISMATCH_DATAMODEL_MISMATCH)
        return 0.0, reasons, mismatches

    if ctx.dataset and template.dataset and template.dataset != ctx.dataset:
        mismatches.append(MISMATCH_NO_TEMPLATE_FOR_SKILL)
        return 0.0, reasons, mismatches

    if ctx.runtime_skill in {"aggregate_and_rank", "threshold_anomaly"}:
        if frozenset(template.group_by_fields) != ctx.group_by_fields:
            mismatches.append(MISMATCH_UNSUPPORTED_GROUP_BY)
            return 0.0, reasons, mismatches
        reasons.append("group_by_fields_set_equal")

    if not _metric_matches(template, ctx):
        mismatches.append(MISMATCH_UNSUPPORTED_METRIC)
        return 0.0, reasons, mismatches
    reasons.append("metric_compatible")

    if template.time_bound_required and not ctx.time_window:
        mismatches.append(MISMATCH_TIME_WINDOW)
        return 0.0, reasons, mismatches
    if template.result_limit_required and ctx.limit is None:
        mismatches.append(MISMATCH_RESULT_LIMIT)
        return 0.0, reasons, mismatches

    if ctx.summariesonly is not None and template.summariesonly_required != ctx.summariesonly:
        mismatches.append(MISMATCH_NO_TEMPLATE_FOR_SKILL)
        return 0.0, reasons, mismatches

    if ctx.validator_profile and template.validator_profile != ctx.validator_profile:
        mismatches.append(MISMATCH_VALIDATOR_PROFILE)
        return 0.0, reasons, mismatches

    if template.datamodel == ctx.datamodel:
        reasons.append("exact_datamodel_match")
    if ctx.resolved_aggregation_shape and template.aggregation_shape == ctx.resolved_aggregation_shape:
        reasons.append("exact_aggregation_shape_match")
    if template.is_production_executable():
        reasons.append("production_executable_preferred")
    elif template.sample_only:
        reasons.append("sample_only_dry_run_match")

    score = 0.4
    if "exact_datamodel_match" in reasons:
        score += 0.25
    if "exact_aggregation_shape_match" in reasons:
        score += 0.15
    if "group_by_fields_set_equal" in reasons:
        score += 0.1
    if "metric_compatible" in reasons:
        score += 0.1
    return min(score, 1.0), reasons, mismatches


def _metric_matches(template: SplTemplateDefinition, ctx: _RoutePlanMatchContext) -> bool:
    if not ctx.metric_type:
        return bool(template.allowed_metrics or template.metric_fields)
    if template.allowed_metrics and ctx.metric_type not in template.allowed_metrics:
        return False
    if not ctx.metric_field:
        return True
    if ctx.metric_field in template.metric_fields:
        return True
    if ctx.metric_field in template.group_by_fields:
        return True
    if ctx.metric_field in template.cim_fields:
        return True
    if ctx.metric_type == "count" and "count" in template.metric_fields:
        return True
    return False


def _substantive_rank_key(item: TemplateCandidateScore, catalog: Sequence[SplTemplateDefinition]) -> tuple[Any, ...]:
    template = _template_by_id(catalog, item.template_id)
    cim_size = len(template.cim_fields) if template else 999
    return (
        item.match_score,
        1 if template and template.datamodel else 0,
        1 if template and template.is_production_executable() else 0,
        -cim_size,
    )


def _template_rank_key(item: TemplateCandidateScore, catalog: Sequence[SplTemplateDefinition]) -> tuple[Any, ...]:
    return _substantive_rank_key(item, catalog) + (item.template_id,)


def _template_by_id(catalog: Sequence[SplTemplateDefinition], template_id: str) -> SplTemplateDefinition | None:
    return next((item for item in catalog if item.template_id == template_id), None)
