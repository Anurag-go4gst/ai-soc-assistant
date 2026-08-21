"""InvestigationPlan Validator (A) for guided hybrid investigation."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from app.chat.contracts.investigation_plan import (
    InvestigationCapabilityBinding,
    InvestigationPlan,
    InvestigationPlanProposal,
    ValidatedInvestigationPlan,
)
from app.connectors.mcp.discovery import classify_mcp_tool
from app.planner.resource_registry import load_resource_registry
from app.spl.guided_safe_spl_catalog import guided_safe_template_ids
from app.spl.policy import load_spl_policy
from app.spl.template_registry import load_spl_templates

_RAW_SPL_MARKERS = re.compile(
    r"\b(?:index|sourcetype)\s*=\s*\S+|\|\s*(?:search|stats|head|where|table|eval)\b",
    re.IGNORECASE,
)
_FORBIDDEN_AUTHORITY_KEYS = frozenset(
    {
        "final_route",
        "execution_eligible",
        "mcp_allowed",
        "spl_execution_eligible",
        "freeform_spl_execution_eligible",
        "severity",
        "route",
        "selected_skill",
    }
)
_FORBIDDEN_TEXT_MARKERS = re.compile(
    r"\b("
    r"final_route|execution_eligible|mcp_allowed|spl_execution_eligible|"
    r"isolate|quarantine|block this|kill the|disable the account"
    r")\b",
    re.IGNORECASE,
)
_INDEX_OR_SOURCETYPE = re.compile(
    r"\b(?:index|sourcetype)\s*[=:]\s*([\w*_-]+)",
    re.IGNORECASE,
)


@lru_cache(maxsize=1)
def _metadata_tool_ids() -> frozenset[str]:
    registry = load_resource_registry()
    return frozenset(
        item.resource_id
        for item in registry.resources
        if item.kind == "mcp_tool"
        and str(item.resource_id).startswith("mcp_tool:splunk_get_")
        and item.availability != "blocked"
    )


@lru_cache(maxsize=1)
def _guided_safe_template_ids() -> frozenset[str]:
    return guided_safe_template_ids()


@lru_cache(maxsize=1)
def _enabled_template_ids() -> frozenset[str]:
    return frozenset(
        template.template_id
        for template in load_spl_templates()
        if template.enabled
    )


def _coerce_proposal(
    proposal: InvestigationPlanProposal | InvestigationPlan | dict[str, Any] | None,
) -> dict[str, Any]:
    if proposal is None:
        return {}
    if isinstance(proposal, InvestigationPlan):
        return proposal.model_dump()
    return dict(proposal)


def _snapshot_rows(snapshot: dict[str, Any] | Any | None) -> dict[str, dict[str, Any]]:
    if snapshot is None:
        return {}
    if not isinstance(snapshot, dict):
        dump = getattr(snapshot, "model_dump", None)
        snapshot = dump(mode="json") if callable(dump) else {}
    if not isinstance(snapshot, dict):
        return {}
    return {
        str(row.get("capability_id")): dict(row)
        for row in (snapshot.get("rows") or [])
        if isinstance(row, dict) and row.get("capability_id")
    }


def _capability_bindings(
    baseline: InvestigationPlan,
    requested_ids: Any,
    *,
    capability_snapshot: dict[str, Any] | Any | None,
    warnings: list[str],
) -> list[InvestigationCapabilityBinding]:
    bindings = list(baseline.capability_bindings)
    seen = {item.capability_id for item in bindings}
    rows = _snapshot_rows(capability_snapshot)
    if not isinstance(requested_ids, list):
        return bindings
    for raw in requested_ids:
        capability_id = str(raw or "").strip()
        if not capability_id or capability_id in seen:
            continue
        row = rows.get(capability_id)
        if row is None:
            warnings.append(f"dropped_unknown_capability:{capability_id}")
            continue
        if not capability_id.startswith("mcp:"):
            warnings.append(f"dropped_non_read_capability:{capability_id}")
            continue
        parts = capability_id.split(":", 2)
        tool_name = parts[2] if len(parts) == 3 else ""
        server_type = "splunk" if "splunk" in parts[1].lower() else "generic"
        if classify_mcp_tool(tool_name, server_type=server_type).blocked:
            warnings.append(f"dropped_blocked_capability:{capability_id}")
            continue
        need = str(row.get("capability_need") or "optional")
        availability = str(row.get("availability") or "unavailable")
        bindings.append(
            InvestigationCapabilityBinding(
                capability_id=capability_id,
                capability_need=need,  # type: ignore[arg-type]
                availability=availability,  # type: ignore[arg-type]
                access_mode="read_only" if availability == "available" else "manual_or_alternate",
            )
        )
        seen.add(capability_id)
    return bindings


def _contains_raw_spl(text: str) -> bool:
    normalized = str(text or "").strip()
    if not normalized:
        return False
    if _RAW_SPL_MARKERS.search(normalized):
        return True
    if "|" in normalized and any(
        token in normalized.lower()
        for token in (" stats ", " head ", " where ", " table ", " eval ")
    ):
        return True
    return False


def _invented_index_or_sourcetype(text: str) -> str | None:
    match = _INDEX_OR_SOURCETYPE.search(str(text or ""))
    if not match:
        return None
    token = match.group(1).lower()
    policy = load_spl_policy()
    allowed = {item.lower() for item in policy.allowed_indexes}
    allowed |= {item.lower() for item in policy.allowed_sourcetypes}
    if token in allowed or token == "<index>" or token.startswith("<"):
        return None
    return token


def _filter_string_items(
    values: Any,
    *,
    warnings: list[str],
    label: str,
    allow_registry_tools: bool = False,
    allow_templates: bool = False,
) -> list[str]:
    if not isinstance(values, list):
        return []
    kept: list[str] = []
    known_tools = _metadata_tool_ids()
    known_templates = _guided_safe_template_ids()
    for raw in values:
        item = str(raw or "").strip()
        if not item:
            continue
        if _contains_raw_spl(item) or _FORBIDDEN_TEXT_MARKERS.search(item):
            warnings.append(f"dropped_{label}_unsafe_text")
            continue
        invented = _invented_index_or_sourcetype(item)
        if invented:
            warnings.append(f"dropped_invented_index_or_sourcetype:{invented}")
            continue
        if allow_registry_tools and item not in known_tools:
            warnings.append(f"dropped_unknown_tool:{item}")
            continue
        if allow_templates and item not in known_templates:
            warnings.append(f"dropped_unknown_template:{item}")
            continue
        if item not in kept:
            kept.append(item)
    return kept


def _merge_unique(baseline_values: list[str], proposal_values: list[str]) -> list[str]:
    merged = list(baseline_values)
    for item in proposal_values:
        if item not in merged:
            merged.append(item)
    return merged


def validate_investigation_plan(
    baseline: InvestigationPlan,
    proposal: InvestigationPlanProposal | InvestigationPlan | dict[str, Any] | None = None,
    *,
    llm_attempted: bool = False,
    capability_snapshot: dict[str, Any] | Any | None = None,
) -> ValidatedInvestigationPlan:
    """Validate and merge an InvestigationPlan proposal; baseline wins on conflict."""
    warnings: list[str] = list(baseline.validation_warnings)
    proposal_data = _coerce_proposal(proposal)

    for key in _FORBIDDEN_AUTHORITY_KEYS:
        if key in proposal_data:
            warnings.append(f"dropped_forbidden_authority_field:{key}")

    proposal_hypotheses = _filter_string_items(
        proposal_data.get("hypotheses"),
        warnings=warnings,
        label="hypothesis",
    )
    proposal_evidence = _filter_string_items(
        proposal_data.get("evidence_needed"),
        warnings=warnings,
        label="evidence",
    )
    proposal_tools = _filter_string_items(
        proposal_data.get("read_only_tool_requests"),
        warnings=warnings,
        label="tool",
        allow_registry_tools=True,
    )
    proposal_templates = _filter_string_items(
        proposal_data.get("safe_spl_template_requests"),
        warnings=warnings,
        label="template",
        allow_templates=True,
    )
    proposal_constraints = _filter_string_items(
        proposal_data.get("environment_constraints"),
        warnings=warnings,
        label="constraint",
    )
    proposal_sources = _filter_string_items(
        proposal_data.get("candidate_sources"),
        warnings=warnings,
        label="candidate_source",
    )
    proposal_categories = _filter_string_items(
        proposal_data.get("data_categories"),
        warnings=warnings,
        label="data_category",
    )
    proposal_questions = _filter_string_items(
        proposal_data.get("clarification_questions"),
        warnings=warnings,
        label="clarification",
    )
    proposal_dependencies = _filter_string_items(
        proposal_data.get("dependencies"),
        warnings=warnings,
        label="dependency",
    )
    proposal_conditions = _filter_string_items(
        proposal_data.get("conditions"),
        warnings=warnings,
        label="condition",
    )
    proposal_success_criteria = _filter_string_items(
        proposal_data.get("success_criteria"),
        warnings=warnings,
        label="success_criterion",
    )
    capability_bindings = _capability_bindings(
        baseline,
        proposal_data.get("capability_requests"),
        capability_snapshot=capability_snapshot,
        warnings=warnings,
    )

    objective = baseline.investigation_objective
    proposed_objective = str(proposal_data.get("investigation_objective") or "").strip()
    if proposed_objective and proposed_objective != objective:
        if _contains_raw_spl(proposed_objective) or _FORBIDDEN_TEXT_MARKERS.search(proposed_objective):
            warnings.append("dropped_unsafe_investigation_objective")
        else:
            warnings.append("baseline_objective_retained")

    spl_review_reason = baseline.spl_review_reason
    proposed_reason = proposal_data.get("spl_review_reason")
    if isinstance(proposed_reason, str) and proposed_reason.strip():
        if _contains_raw_spl(proposed_reason):
            warnings.append("dropped_unsafe_spl_review_reason")
        elif not baseline.spl_review_reason:
            spl_review_reason = proposed_reason.strip()[:300]

    accepted_proposal = bool(proposal_data) and any(
        (
            proposal_hypotheses,
            proposal_evidence,
            proposal_tools,
            proposal_templates,
            proposal_constraints,
            proposal_sources,
            proposal_categories,
            proposal_questions,
            proposal_dependencies,
            proposal_conditions,
            proposal_success_criteria,
            len(capability_bindings) > len(baseline.capability_bindings),
        )
    )
    plan_source = baseline.plan_source
    if llm_attempted:
        plan_source = "llm_proposed_validated" if accepted_proposal else "llm_failed_baseline_only"
    elif proposal_data and accepted_proposal:
        plan_source = "llm_proposed_validated"

    llm_budget_used = baseline.llm_budget_used
    if llm_attempted:
        llm_budget_used = max(llm_budget_used, 1)

    spl_review_requested = baseline.spl_review_requested
    if llm_attempted and proposal_data.get("spl_review_requested") is True:
        spl_review_requested = True

    clarification_needed = baseline.clarification_needed
    if llm_attempted and proposal_data.get("clarification_needed") is True:
        clarification_needed = True

    refinement_recommended = baseline.refinement_recommended
    if llm_attempted and proposal_data.get("refinement_recommended") is True:
        refinement_recommended = True

    refinement_rationale = baseline.refinement_rationale
    proposed_rationale = proposal_data.get("refinement_rationale")
    if isinstance(proposed_rationale, str) and proposed_rationale.strip():
        if _contains_raw_spl(proposed_rationale):
            warnings.append("dropped_unsafe_refinement_rationale")
        else:
            refinement_rationale = proposed_rationale.strip()[:400]

    return ValidatedInvestigationPlan(
        investigation_objective=objective,
        hypotheses=_merge_unique(baseline.hypotheses, proposal_hypotheses),
        evidence_needed=_merge_unique(baseline.evidence_needed, proposal_evidence),
        data_categories=_merge_unique(baseline.data_categories, proposal_categories),
        dependencies=_merge_unique(baseline.dependencies, proposal_dependencies),
        conditions=_merge_unique(baseline.conditions, proposal_conditions),
        success_criteria=_merge_unique(baseline.success_criteria, proposal_success_criteria),
        capability_bindings=capability_bindings,
        authoritative_facts=list(baseline.authoritative_facts),
        rag_sufficient=baseline.rag_sufficient,
        env_kb_needed=baseline.env_kb_needed
        or (llm_attempted and bool(proposal_data.get("env_kb_needed"))),
        discovery_needed=baseline.discovery_needed
        or (llm_attempted and bool(proposal_data.get("discovery_needed"))),
        environment_constraints=_merge_unique(
            baseline.environment_constraints,
            proposal_constraints,
        ),
        candidate_sources=_merge_unique(baseline.candidate_sources, proposal_sources),
        read_only_tool_requests=_merge_unique(
            baseline.read_only_tool_requests,
            proposal_tools,
        ),
        safe_spl_template_requests=_merge_unique(
            baseline.safe_spl_template_requests,
            proposal_templates,
        ),
        spl_review_requested=spl_review_requested,
        spl_review_reason=spl_review_reason,
        clarification_needed=clarification_needed,
        clarification_questions=_merge_unique(
            baseline.clarification_questions,
            proposal_questions,
        ),
        refinement_recommended=refinement_recommended,
        refinement_rationale=refinement_rationale,
        blocked_capabilities=list(baseline.blocked_capabilities),
        human_review_required=True,
        plan_source=plan_source,
        validation_warnings=warnings,
        llm_budget_used=llm_budget_used,
        refinement_round=baseline.refinement_round,
    )
