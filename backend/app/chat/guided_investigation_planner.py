"""InvestigationPlan Validator (A) for guided hybrid investigation."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from app.chat.contracts.investigation_plan import InvestigationPlan
from app.planner.resource_registry import load_resource_registry
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
def _enabled_template_ids() -> frozenset[str]:
    return frozenset(
        template.template_id
        for template in load_spl_templates()
        if template.enabled
    )


def _coerce_proposal(proposal: InvestigationPlan | dict[str, Any] | None) -> dict[str, Any]:
    if proposal is None:
        return {}
    if isinstance(proposal, InvestigationPlan):
        return proposal.model_dump()
    return dict(proposal)


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
    known_templates = _enabled_template_ids()
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
    proposal: InvestigationPlan | dict[str, Any] | None = None,
    *,
    llm_attempted: bool = False,
) -> InvestigationPlan:
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

    return InvestigationPlan(
        investigation_objective=objective,
        hypotheses=_merge_unique(baseline.hypotheses, proposal_hypotheses),
        evidence_needed=_merge_unique(baseline.evidence_needed, proposal_evidence),
        data_categories=_merge_unique(baseline.data_categories, proposal_categories),
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
