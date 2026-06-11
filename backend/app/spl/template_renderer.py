"""Stage 3K-Q1D deterministic SPL template renderer (library only).

Pure render + Q1A validation. Raw templates render from approved static SPL;
CIM/datamodel templates render from parameterized patterns. No MCP calls.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from app.safeguards.spl_validator import validate_spl
from app.spl.policy import load_spl_policy
from app.spl.spl_slot_binding_validator import _valid_ip, validate_render_bindings
from app.spl.template_registry import (
    QUERY_SHAPE_FROM_DATAMODEL,
    QUERY_SHAPE_RAW_SEARCH,
    QUERY_SHAPE_TSTATS_DATAMODEL,
    SplTemplateDefinition,
)

RENDER_NOT_SUPPORTED = "q1d_renderer_not_supported_for_query_shape"
RENDER_MISSING_PATTERN = "missing_render_pattern"
RENDER_UNKNOWN_PLACEHOLDER = "unknown_placeholder"
RENDER_UNDECLARED_BINDING = "undeclared_binding"
RENDER_BINDING_REGEX_FAILED = "binding_regex_failed"
RENDER_MISSING_TIME_WINDOW = "missing_time_window"
RENDER_UNSUBSTITUTED_PLACEHOLDER = "unsubstituted_placeholder"
RENDER_VALIDATION_FAILED = "validation_failed"

SYSTEM_BINDINGS = frozenset({"earliest", "latest", "result_limit"})
PLACEHOLDER_PATTERN = re.compile(r"\{([a-z_][a-z0-9_]*)\}", re.IGNORECASE)

ROUTE_WINDOW_ALIASES: dict[str, tuple[str, str]] = {
    "last_24_hours": ("earliest=-24h", "latest=now"),
    "last_1_hour": ("earliest=-1h", "latest=now"),
    "today": ("earliest=-24h", "latest=now"),
}

SPL_IN_VALUE_PATTERN = re.compile(
    r"\||\bsearch\b|\btstats\b|\bfrom\s+datamodel\b|\bstats\b|\bwhere\b.*\bindex=",
    re.IGNORECASE,
)


@dataclass
class RenderResult:
    rendered_spl: str | None
    render_ok: bool
    bound_parameters: dict[str, Any] = field(default_factory=dict)
    validation_result: dict[str, Any] | None = None
    validator_approved: bool = False
    validator_profile: str | None = None
    execution_eligible: bool = False
    render_warnings: list[str] = field(default_factory=list)
    render_errors: list[str] = field(default_factory=list)
    template_id: str | None = None
    sample_only: bool = False
    production_executable: bool = False
    disagreements: list[dict[str, Any]] = field(default_factory=list)
    parameter_extraction_llm: dict[str, Any] | None = None
    llm_assist_timed_out: bool = False
    llm_assist_enabled: bool = False
    coe_synthetic_fixture: bool = True
    captured_live_run: bool = False
    production_execution: bool = False

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def render_template(
    template: SplTemplateDefinition,
    bound_params: dict[str, Any] | None = None,
    *,
    route_window: Any = None,
) -> RenderResult:
    """Render SPL from a governed template and validate with Q1A."""
    bound_params = dict(bound_params or {})
    errors: list[str] = []
    warnings: list[str] = []

    if template.query_shape == QUERY_SHAPE_RAW_SEARCH:
        if not template.spl_text:
            errors.append(RENDER_MISSING_PATTERN)
            return _failure(template, errors, warnings, bound_params)
        validation = validate_spl(template.spl_text, load_spl_policy())
        approved = bool(validation.get("approved"))
        if not approved:
            errors.append(RENDER_VALIDATION_FAILED)
            errors.extend(str(item) for item in validation.get("reject_reasons", []))
        return RenderResult(
            rendered_spl=template.spl_text if approved else None,
            render_ok=approved and not errors,
            bound_parameters=bound_params,
            validation_result=validation,
            validator_approved=approved,
            validator_profile=validation.get("validation_profile") or template.validator_profile,
            execution_eligible=False,
            render_warnings=warnings,
            render_errors=errors,
            template_id=template.template_id,
            sample_only=template.sample_only,
            production_executable=template.is_production_executable(),
        )

    if template.query_shape not in {QUERY_SHAPE_TSTATS_DATAMODEL, QUERY_SHAPE_FROM_DATAMODEL}:
        errors.append(RENDER_NOT_SUPPORTED)
        return _failure(template, errors, warnings, bound_params)

    if not template.render_pattern:
        errors.append(RENDER_MISSING_PATTERN)
        return _failure(template, errors, warnings, bound_params)

    placeholders = _extract_placeholders(template.render_pattern)
    allowed_keys = _allowed_binding_keys(template)
    unknown_placeholders = sorted(placeholders - allowed_keys)
    if unknown_placeholders:
        errors.append(RENDER_UNKNOWN_PLACEHOLDER)
        errors.extend(f"unknown_placeholder:{name}" for name in unknown_placeholders)
        return _failure(template, errors, warnings, bound_params)

    undeclared = sorted(set(bound_params) - allowed_keys)
    if undeclared:
        errors.append(RENDER_UNDECLARED_BINDING)
        errors.extend(f"undeclared_binding:{name}" for name in undeclared)
        return _failure(template, errors, warnings, bound_params)

    bindings, bind_errors = _build_bindings(template, bound_params, route_window=route_window)
    errors.extend(bind_errors)
    if errors:
        return _failure(template, errors, warnings, bindings)

    regex_errors = validate_render_bindings(bindings, template=template, policy=load_spl_policy())
    if regex_errors:
        errors.append(RENDER_BINDING_REGEX_FAILED)
        errors.extend(regex_errors)
        return _failure(template, errors, warnings, bindings)

    rendered = _substitute(template.render_pattern, bindings, placeholders)
    if "{" in rendered or "}" in rendered:
        errors.append(RENDER_UNSUBSTITUTED_PLACEHOLDER)
        return _failure(template, errors, warnings, bindings)

    validation = validate_spl(rendered, load_spl_policy())
    approved = bool(validation.get("approved"))
    if not approved:
        errors.append(RENDER_VALIDATION_FAILED)
        errors.extend(str(item) for item in validation.get("reject_reasons", []))

    return RenderResult(
        rendered_spl=rendered if approved else None,
        render_ok=approved and not errors,
        bound_parameters=bindings,
        validation_result=validation,
        validator_approved=approved,
        validator_profile=validation.get("validation_profile") or template.validator_profile,
        execution_eligible=False,
        render_warnings=warnings,
        render_errors=errors,
        template_id=template.template_id,
        sample_only=template.sample_only,
        production_executable=template.is_production_executable(),
    )


def _allowed_binding_keys(template: SplTemplateDefinition) -> set[str]:
    return (
        set(template.required_parameters)
        | set(template.optional_parameters)
        | set(SYSTEM_BINDINGS)
    )


def _extract_placeholders(pattern: str) -> set[str]:
    return {match.group(1) for match in PLACEHOLDER_PATTERN.finditer(pattern)}


def _build_bindings(
    template: SplTemplateDefinition,
    bound_params: dict[str, Any],
    *,
    route_window: Any,
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    bindings: dict[str, Any] = dict(bound_params)

    earliest, latest = _resolve_time_window(route_window, template.default_time_window)
    placeholders = _extract_placeholders(template.render_pattern or "")
    if earliest and latest:
        bindings["earliest"] = earliest
        bindings["latest"] = latest
    needed_time = {"earliest", "latest"} & placeholders
    if needed_time and not (bindings.get("earliest") and bindings.get("latest")):
        errors.append(RENDER_MISSING_TIME_WINDOW)

    max_rows = template.result_limits.get("max_rows") if isinstance(template.result_limits, dict) else None
    if "result_limit" not in bindings and max_rows is not None:
        bindings["result_limit"] = int(max_rows)
    elif "result_limit" in bindings:
        bindings["result_limit"] = int(bindings["result_limit"])

    required = set(template.required_parameters) | ({"earliest", "latest", "result_limit"} & _extract_placeholders(template.render_pattern or ""))
    for key in sorted(required):
        if key not in bindings:
            errors.append(f"missing_binding:{key}")

    return bindings, errors


def _resolve_time_window(route_window: Any, default_time_window: str | None) -> tuple[str | None, str | None]:
    if isinstance(route_window, dict):
        earliest = route_window.get("earliest")
        latest = route_window.get("latest")
        if isinstance(earliest, str) and isinstance(latest, str):
            return earliest.strip(), latest.strip()

    if isinstance(route_window, str):
        alias = ROUTE_WINDOW_ALIASES.get(route_window.strip().lower().replace(" ", "_"))
        if alias:
            return alias

    if default_time_window:
        tokens = default_time_window.split()
        earliest = next((token for token in tokens if token.startswith("earliest=")), None)
        latest = next((token for token in tokens if token.startswith("latest=")), None)
        if earliest and latest:
            return earliest, latest

    return None, None


def _substitute(pattern: str, bindings: dict[str, Any], placeholders: set[str]) -> str:
    rendered = pattern
    for key in placeholders:
        if key not in bindings:
            continue
        rendered = rendered.replace(f"{{{key}}}", str(bindings[key]))
    return re.sub(r"\s+", " ", rendered).strip()


def _failure(
    template: SplTemplateDefinition,
    errors: list[str],
    warnings: list[str],
    bindings: dict[str, Any],
) -> RenderResult:
    return RenderResult(
        rendered_spl=None,
        render_ok=False,
        bound_parameters=bindings,
        validation_result=None,
        validator_approved=False,
        validator_profile=template.validator_profile,
        execution_eligible=False,
        render_warnings=warnings,
        render_errors=sorted(set(errors)),
        template_id=template.template_id,
        sample_only=template.sample_only,
        production_executable=template.is_production_executable(),
    )
