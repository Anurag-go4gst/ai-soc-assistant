"""Render and gate guided safe-catalog SPL before mediated MCP dispatch."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.spl.guided_safe_spl_catalog import (
    get_guided_safe_catalog_entry,
    load_guided_safe_spl_catalog,
)
from app.spl.template_registry import get_spl_template
from app.spl.template_renderer import render_template


@dataclass(frozen=True)
class GuidedSafeSplDispatchPlan:
    template_id: str | None
    ready: bool
    outcome: str
    reason: str | None = None
    spl_validation: dict[str, Any] | None = None
    delivered: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)


def build_guided_safe_spl_dispatch_plan(template_id: str | None) -> GuidedSafeSplDispatchPlan:
    """Return a validated SPL dispatch plan, or a fail-closed trace plan.

    The catalog is intentionally visible while COE unsigned, but execution stays
    inert until the top-level catalog signature is explicitly true.
    """
    payload: dict[str, Any] = {
        "template_id": template_id,
        "provenance": "guided_safe_catalog",
        "read_only": True,
    }
    catalog = load_guided_safe_spl_catalog()
    payload["catalog_version"] = catalog.version
    payload["coe_signed"] = bool(catalog.coe_signed)
    if catalog.coe_signed is not True:
        return GuidedSafeSplDispatchPlan(
            template_id=template_id,
            ready=False,
            outcome="planned",
            reason="guided_safe_catalog_unsigned",
            delivered=["template_bound_query"],
            payload=payload,
        )

    if not template_id:
        return GuidedSafeSplDispatchPlan(
            template_id=template_id,
            ready=False,
            outcome="blocked",
            reason="missing_template_id",
            payload=payload,
        )
    entry = get_guided_safe_catalog_entry(template_id)
    if entry is None:
        return GuidedSafeSplDispatchPlan(
            template_id=template_id,
            ready=False,
            outcome="blocked",
            reason="catalog_template_not_allowlisted",
            payload=payload,
        )

    template = get_spl_template(template_id)
    if template is None or template.enabled is not True:
        return GuidedSafeSplDispatchPlan(
            template_id=template_id,
            ready=False,
            outcome="blocked",
            reason="catalog_template_not_enabled",
            payload=payload,
        )

    render = render_template(template, {})
    payload.update(
        {
            "render_ok": render.render_ok,
            "validator_approved": render.validator_approved,
            "validator_profile": render.validator_profile,
            "max_rows": entry.max_rows,
            "max_lookback_hours": entry.max_lookback_hours,
        }
    )
    if not render.render_ok or not render.validation_result:
        payload["render_errors"] = list(render.render_errors)
        return GuidedSafeSplDispatchPlan(
            template_id=template_id,
            ready=False,
            outcome="blocked",
            reason="guided_safe_template_validation_failed",
            payload=payload,
        )

    validation = dict(render.validation_result)
    validation.update(
        {
            "template_id": template_id,
            "selected_candidate_spl_provider": "guided_safe_catalog",
            "candidate_provider_reason": "guided_safe_catalog_allowlisted_template",
        }
    )
    return GuidedSafeSplDispatchPlan(
        template_id=template_id,
        ready=True,
        outcome="requires_human_review",
        spl_validation=validation,
        delivered=["template_bound_query"],
        payload=payload,
    )
