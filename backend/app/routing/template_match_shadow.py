"""Stage 3K-Q1E deterministic template match + render shadow (no LLM sidecars).

Uses ``match_route_plan_to_template`` and ``render_template`` only — never
``template_matcher_llm_assist`` or ``template_renderer_llm_assist``.
"""

from __future__ import annotations

import hashlib
from typing import Any

from app.config import settings
from app.spl.template_matcher import match_route_plan_to_template
from app.spl.template_registry import get_spl_template
from app.spl.template_renderer import render_template

SKIP_NO_VALIDATED_ROUTE_PLAN = "no_validated_route_plan"
SKIP_ROUTING_SHADOW_DISABLED = "routing_shadow_disabled"

TEMPLATE_MATCH_STATUS_MATCHED = "matched"
TEMPLATE_MATCH_STATUS_NO_MATCH = "no_match"
TEMPLATE_MATCH_STATUS_RENDER_REJECTED = "render_rejected"
TEMPLATE_MATCH_STATUS_VALIDATOR_REJECTED = "validator_rejected"


def apply_template_match_to_shadow(
    shadow: dict[str, Any],
    *,
    normalized_route_plan: dict[str, Any] | None,
) -> None:
    """Populate Q1E template-match fields on ``route_plan_shadow`` (in-place)."""
    _set_template_match_defaults(shadow)

    if not settings.routing_llm_shadow_enabled:
        shadow["template_match_skip_reason"] = SKIP_ROUTING_SHADOW_DISABLED
        return

    if not normalized_route_plan or not shadow.get("normalized_plan_available"):
        shadow["template_match_skip_reason"] = SKIP_NO_VALIDATED_ROUTE_PLAN
        return

    shadow["template_match_attempted"] = True
    shadow["coe_synthetic_fixture"] = True
    shadow["captured_live_run"] = False
    shadow["production_execution"] = False

    match = match_route_plan_to_template(normalized_route_plan)
    shadow["matched_template_id"] = match.matched_template_id
    shadow["template_match_score"] = match.match_score if match.matched else 0.0
    shadow["template_match_reasons"] = list(match.match_reasons)
    shadow["template_mismatch_reasons"] = list(match.mismatch_reasons)
    shadow["candidate_template_ids"] = list(match.candidate_template_ids)
    shadow["template_production_executable"] = match.production_executable
    shadow["template_sample_only"] = match.sample_only
    shadow["template_validator_profile"] = match.validator_profile

    if not match.matched or not match.matched_template_id:
        shadow["template_match_shadow_status"] = TEMPLATE_MATCH_STATUS_NO_MATCH
        shadow["rendered_spl_available"] = False
        shadow["rendered_spl_validator_approved"] = False
        shadow["rendered_spl_execution_eligible"] = False
        return

    template = get_spl_template(match.matched_template_id)
    if template is None:
        shadow["template_match_shadow_status"] = TEMPLATE_MATCH_STATUS_NO_MATCH
        shadow["template_mismatch_reasons"] = sorted(
            set(shadow["template_mismatch_reasons"]) | {"template_not_found"}
        )
        shadow["rendered_spl_available"] = False
        shadow["rendered_spl_validator_approved"] = False
        shadow["rendered_spl_execution_eligible"] = False
        return

    if template.evidence_output_contract is not None:
        shadow["evidence_output_contract"] = template.evidence_output_contract.model_dump()

    bound_params, route_window = _bound_params_from_route_plan(normalized_route_plan)
    render_result = render_template(template, bound_params, route_window=route_window)

    shadow["rendered_spl_execution_eligible"] = False
    shadow["rendered_spl_validator_approved"] = bool(render_result.validator_approved)
    shadow["rendered_spl_available"] = bool(
        render_result.render_ok and render_result.rendered_spl
    )

    if render_result.rendered_spl:
        shadow["rendered_spl_sha256"] = hashlib.sha256(
            render_result.rendered_spl.encode("utf-8")
        ).hexdigest()

    if not render_result.render_ok:
        shadow["template_match_shadow_status"] = TEMPLATE_MATCH_STATUS_RENDER_REJECTED
        return

    if not render_result.validator_approved:
        shadow["template_match_shadow_status"] = TEMPLATE_MATCH_STATUS_VALIDATOR_REJECTED
        return

    shadow["template_match_shadow_status"] = TEMPLATE_MATCH_STATUS_MATCHED
    if render_result.validator_profile:
        shadow["template_validator_profile"] = render_result.validator_profile


def _set_template_match_defaults(shadow: dict[str, Any]) -> None:
    shadow.setdefault("template_match_attempted", False)
    shadow.setdefault("template_match_skip_reason", None)
    shadow.setdefault("template_match_shadow_status", None)
    shadow.setdefault("matched_template_id", None)
    shadow.setdefault("template_match_score", None)
    shadow.setdefault("template_match_reasons", [])
    shadow.setdefault("template_mismatch_reasons", [])
    shadow.setdefault("candidate_template_ids", [])
    shadow.setdefault("template_production_executable", False)
    shadow.setdefault("template_sample_only", False)
    shadow.setdefault("template_validator_profile", None)
    shadow.setdefault("rendered_spl_available", False)
    shadow.setdefault("rendered_spl_validator_approved", False)
    shadow.setdefault("rendered_spl_execution_eligible", False)
    shadow.setdefault("rendered_spl_sha256", None)
    shadow.setdefault("evidence_output_contract", None)
    shadow.setdefault("coe_synthetic_fixture", True)
    shadow.setdefault("captured_live_run", False)
    shadow.setdefault("production_execution", False)


def _bound_params_from_route_plan(plan: dict[str, Any]) -> tuple[dict[str, Any], Any]:
    parameters = plan.get("parameters") if isinstance(plan.get("parameters"), dict) else {}
    bound: dict[str, Any] = {}
    limit = parameters.get("limit")
    if isinstance(limit, int):
        bound["result_limit"] = limit
    elif isinstance(limit, str) and limit.isdigit():
        bound["result_limit"] = int(limit)

    route_window = parameters.get("time_window") or plan.get("time_window")
    return bound, route_window
