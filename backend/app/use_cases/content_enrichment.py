from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.config import settings

CONTENT_ENRICHMENT_PATH = Path(__file__).with_name("content_enrichment.json")
CATALOG_PATH = Path(__file__).with_name("catalog.json")
CROSSWALK_PATH = Path(__file__).resolve().parents[3] / "docs" / "evals" / "soc_capability_crosswalk.json"

ALLOWED_LIVE_EXECUTION_SKILLS = frozenset(
    {"alert_summary", "spl_generation", "attack_discovery", "knowledge_recall"}
)


class UseCaseActivationDecision(BaseModel):
    use_case_id: str | None = None
    catalog_present: bool = False
    crosswalk_lookup_status: str = "not_found"
    runtime_support_status: str | None = None
    validation_status: str | None = None
    tests_added: bool = False
    spl_template_status: str | None = None
    live_execution_skill: str | None = None
    live_execution_skill_allowed: bool = False
    enrichment_present: bool = False
    enrichment_only: bool = False
    proposed_github_use_case: bool = False
    github_lifecycle_status: str | None = None
    github_accepted_for_enrichment_only: bool = False
    activation_lifecycle_stage: str = "not_cataloged"
    planner_runtime_activation_allowed: bool = False
    governed_enrichment_load_allowed: bool = False
    trace_metadata_allowed: bool = False
    reasons: list[str] = Field(default_factory=list)


class CuratedEnrichmentContext(BaseModel):
    use_case_id: str
    evidence_requirements: list[str] = Field(default_factory=list)
    investigation_workflow: list[str] = Field(default_factory=list)
    analyst_checklist: list[str] = Field(default_factory=list)
    answer_rules: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    not_claimed_defaults: list[str] = Field(default_factory=list)
    recommended_pivots: list[str] = Field(default_factory=list)
    required_sources: list[str] = Field(default_factory=list)
    optional_sources: list[str] = Field(default_factory=list)
    allowed_spl_templates: list[str] = Field(default_factory=list)
    spl_template_status: str = "unavailable"
    rag_doc_ids: list[str] = Field(default_factory=list)
    mitre_candidates: list[str] = Field(default_factory=list)
    planning_or_analytic_skill: str | None = None
    provenance_ref_ids: list[str] = Field(default_factory=list)
    activation_lifecycle_stage: str = "not_cataloged"
    runtime_support_status: str | None = None
    activation_decision: UseCaseActivationDecision


# Public alias for master-plan S3 (content_enrichment record model).
UseCaseContentEnrichment = CuratedEnrichmentContext


@lru_cache(maxsize=1)
def load_content_enrichment() -> dict[str, Any]:
    """Load curated enrichment metadata from the local app bundle only."""
    if not CONTENT_ENRICHMENT_PATH.exists():
        return {"records": {}}
    payload = json.loads(CONTENT_ENRICHMENT_PATH.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {"records": {}}


@lru_cache(maxsize=1)
def _load_catalog() -> dict[str, dict[str, Any]]:
    try:
        payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    rows = payload.get("use_cases") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return {}
    return {str(row.get("use_case_id")): row for row in rows if isinstance(row, dict) and row.get("use_case_id")}


@lru_cache(maxsize=1)
def _load_crosswalk() -> dict[str, Any]:
    try:
        payload = json.loads(CROSSWALK_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def content_enrichment_records() -> dict[str, dict[str, Any]]:
    records = load_content_enrichment().get("records")
    if not isinstance(records, dict):
        return {}
    return {str(key): value for key, value in records.items() if isinstance(value, dict)}


def get_content_enrichment(use_case_id: str | None) -> dict[str, Any] | None:
    if not use_case_id:
        return None
    records = content_enrichment_records()
    if use_case_id in records:
        return dict(records[use_case_id])
    for record in records.values():
        if record.get("use_case_id") == use_case_id or record.get("proposed_use_case_id") == use_case_id:
            return dict(record)
    return None


def resolve_use_case_activation(use_case_id: str | None) -> UseCaseActivationDecision:
    """Resolve whether curated enrichment can be treated as runtime active.

    GitHub acceptance and proposed-use-case rows are explicitly enrichment-only.
    This function reads local catalog/crosswalk metadata only; it does not load
    raw GitHub markdown, prompt text, RAG documents, SPL, or MCP state.
    """
    if not use_case_id:
        return UseCaseActivationDecision(reasons=["missing_use_case_id"])

    catalog_row = _load_catalog().get(use_case_id)
    enrichment = get_content_enrichment(use_case_id)
    crosswalk_row, lookup_status = _crosswalk_row(use_case_id)
    proposed_row = _proposed_use_case_row(use_case_id)

    catalog_present = bool(catalog_row)
    runtime_support_status = _first_str(
        (crosswalk_row or {}).get("runtime_support_status"),
        (proposed_row or {}).get("runtime_support_status"),
    )
    validation_status = _first_str((crosswalk_row or {}).get("validation_status"))
    tests_added = bool((crosswalk_row or {}).get("tests_added"))
    spl_template_status = _first_str(
        (crosswalk_row or {}).get("spl_template_status"),
        (enrichment or {}).get("spl_template_status"),
        (proposed_row or {}).get("spl_template_need"),
    )
    live_execution_skill = _first_str(
        (crosswalk_row or {}).get("live_execution_skill"),
        (catalog_row or {}).get("primary_skill"),
        (enrichment or {}).get("live_execution_skill"),
        (proposed_row or {}).get("proposed_live_execution_skill"),
    )
    live_execution_skill_allowed = bool(live_execution_skill in ALLOWED_LIVE_EXECUTION_SKILLS)
    proposed_github_use_case = bool(proposed_row or (enrichment and enrichment.get("proposed_use_case_id") == use_case_id))
    github_accepted_for_enrichment_only = _github_accepted_for_enrichment_only(enrichment)
    enrichment_present = bool(enrichment)
    enrichment_only = bool(
        enrichment_present
        and (
            not catalog_present
            or proposed_github_use_case
            or runtime_support_status in {"metadata_only", "unsupported"}
        )
    )

    reasons: list[str] = []
    if not catalog_present:
        reasons.append("catalog_not_present")
    if proposed_github_use_case:
        reasons.append("github_proposed_use_case_never_runtime_active_phase4")
    if github_accepted_for_enrichment_only:
        reasons.append("github_skill_acceptance_is_enrichment_only")
    if not live_execution_skill_allowed and live_execution_skill:
        reasons.append("live_execution_skill_not_allowed")
    if runtime_support_status == "planned":
        reasons.append("planned_allows_trace_metadata_only")
    if runtime_support_status in {"metadata_only", "unsupported"}:
        reasons.append("metadata_or_unsupported_not_runtime_active")

    planner_runtime_activation_allowed = bool(
        catalog_present
        and runtime_support_status == "runtime_active"
        and live_execution_skill_allowed
        and not proposed_github_use_case
        and not enrichment_only
    )
    governed_enrichment_load_allowed = bool(planner_runtime_activation_allowed and enrichment_present)
    trace_metadata_allowed = bool(catalog_present and runtime_support_status == "planned") or enrichment_only
    if planner_runtime_activation_allowed:
        lifecycle = "runtime_active"
        reasons.append("catalog_crosswalk_runtime_active")
    elif catalog_present and runtime_support_status == "planned":
        lifecycle = "planned_trace_metadata"
    elif enrichment_only:
        lifecycle = "enrichment_only"
    elif catalog_present:
        lifecycle = runtime_support_status or "catalog_metadata_only"
    else:
        lifecycle = "not_cataloged"

    return UseCaseActivationDecision(
        use_case_id=use_case_id,
        catalog_present=catalog_present,
        crosswalk_lookup_status=lookup_status,
        runtime_support_status=runtime_support_status,
        validation_status=validation_status,
        tests_added=tests_added,
        spl_template_status=spl_template_status,
        live_execution_skill=live_execution_skill,
        live_execution_skill_allowed=live_execution_skill_allowed,
        enrichment_present=enrichment_present,
        enrichment_only=enrichment_only,
        proposed_github_use_case=proposed_github_use_case,
        github_lifecycle_status=_github_lifecycle_status(enrichment),
        github_accepted_for_enrichment_only=github_accepted_for_enrichment_only,
        activation_lifecycle_stage=lifecycle,
        planner_runtime_activation_allowed=planner_runtime_activation_allowed,
        governed_enrichment_load_allowed=governed_enrichment_load_allowed,
        trace_metadata_allowed=trace_metadata_allowed,
        reasons=list(dict.fromkeys(reasons)),
    )


def runtime_enrichment_activation_allowed(use_case_id: str | None) -> bool:
    """Return True when curated enrichment may be used on runtime/evidence paths."""
    if not use_case_id:
        return False
    if not (
        settings.ai_soc_runtime_enrichment_enabled
        or settings.ai_soc_curated_enrichment_activation_enabled
    ):
        return False
    return resolve_use_case_activation(use_case_id).governed_enrichment_load_allowed


def load_skill_enrichment(use_case_id: str | None) -> UseCaseContentEnrichment | None:
    """Load curated enrichment for a use case when runtime enrichment is enabled."""
    return get_runtime_curated_enrichment(use_case_id)


def get_runtime_curated_enrichment(use_case_id: str | None) -> CuratedEnrichmentContext | None:
    """Runtime-safe curated enrichment loader (flag + activation gate)."""
    if not runtime_enrichment_activation_allowed(use_case_id):
        return None
    return load_curated_enrichment_context(use_case_id)


def load_curated_enrichment_context(use_case_id: str | None) -> CuratedEnrichmentContext | None:
    activation = resolve_use_case_activation(use_case_id)
    if not activation.governed_enrichment_load_allowed:
        return None
    record = get_content_enrichment(use_case_id)
    if record is None:
        return None
    catalog_row = _load_catalog().get(activation.use_case_id or "")
    context = _context_from_record(record, activation=activation, catalog_row=catalog_row)
    return context


def curated_enrichment_trace(use_case_id: str | None) -> dict[str, Any] | None:
    if not use_case_id:
        return None
    activation = resolve_use_case_activation(use_case_id)
    context = load_curated_enrichment_context(use_case_id)
    payload: dict[str, Any] = {
        "activation": activation.model_dump(),
        "context_loaded": context is not None,
    }
    if context is not None:
        payload["context_summary"] = {
            "use_case_id": context.use_case_id,
            "evidence_requirement_count": len(context.evidence_requirements),
            "investigation_workflow_count": len(context.investigation_workflow),
            "answer_rule_count": len(context.answer_rules),
            "limitation_count": len(context.limitations),
            "allowed_spl_templates": context.allowed_spl_templates,
            "spl_template_status": context.spl_template_status,
            "rag_doc_ids": context.rag_doc_ids,
            "mitre_candidates": context.mitre_candidates,
            "planning_or_analytic_skill": context.planning_or_analytic_skill,
        }
    return payload


def _scrub_guidance_projection_lists(record: dict[str, Any], field: str) -> list[str]:
    from app.chat.guidance_templates import scrub_blocked_context_text_list

    return scrub_blocked_context_text_list([str(item) for item in record.get(field) or [] if item])


def get_guidance_only_enrichment_projection(use_case_id: str | None) -> dict[str, Any] | None:
    """Project safe guidance fields when runtime activation is blocked.

    Must not enable SPL approval, MITRE evidence-supported status, severity
    escalation, execution, or runtime_active claims.
    """
    record = get_content_enrichment(use_case_id)
    if record is None:
        return None
    return {
        "use_case_id": str(record.get("use_case_id") or record.get("proposed_use_case_id") or use_case_id or ""),
        "evidence_requirements": _scrub_guidance_projection_lists(record, "evidence_requirements"),
        "investigation_workflow": _scrub_guidance_projection_lists(record, "investigation_workflow"),
        "analyst_checklist": _scrub_guidance_projection_lists(record, "analyst_checklist"),
        "answer_rules": _scrub_guidance_projection_lists(record, "answer_rules"),
        "limitations": _scrub_guidance_projection_lists(record, "limitations"),
        "not_claimed_defaults": [str(item) for item in record.get("not_claimed_defaults") or [] if item],
        "recommended_pivots": [str(item) for item in record.get("recommended_pivots") or [] if item],
        "required_sources": [str(item) for item in record.get("required_sources") or [] if item],
        "optional_sources": [str(item) for item in record.get("optional_sources") or [] if item],
        "allowed_spl_templates": [],
        "spl_template_status": "unavailable",
        "rag_doc_ids": [],
        "mitre_candidates_metadata_only": [str(item) for item in record.get("mitre_candidates") or [] if item],
        "planning_or_analytic_skill": record.get("planning_or_analytic_skill"),
        "activation_lifecycle_stage": "guidance_only_projection",
        "runtime_support_status": record.get("runtime_support_status"),
        "guidance_only": True,
    }


def llm_facing_curated_enrichment_projection(context: CuratedEnrichmentContext | None) -> dict[str, Any] | None:
    """Return a sanitized future composer payload.

    This intentionally excludes raw GitHub paths, raw skill-file contents, and
    internal provenance references. MITRE entries remain candidates only.
    """
    if context is None:
        return None
    return {
        "use_case_id": context.use_case_id,
        "evidence_requirements": list(context.evidence_requirements),
        "investigation_workflow": list(context.investigation_workflow),
        "analyst_checklist": list(context.analyst_checklist),
        "answer_rules": list(context.answer_rules),
        "limitations": list(context.limitations),
        "not_claimed_defaults": list(context.not_claimed_defaults),
        "recommended_pivots": list(context.recommended_pivots),
        "required_sources": list(context.required_sources),
        "optional_sources": list(context.optional_sources),
        "allowed_spl_templates": list(context.allowed_spl_templates),
        "spl_template_status": context.spl_template_status,
        "rag_doc_ids": list(context.rag_doc_ids),
        "mitre_candidates_metadata_only": list(context.mitre_candidates),
        "planning_or_analytic_skill": context.planning_or_analytic_skill,
        "activation_lifecycle_stage": context.activation_lifecycle_stage,
        "runtime_support_status": context.runtime_support_status,
    }


def enrichment_spl_governance_for_runtime(use_case_id: str | None) -> dict[str, Any] | None:
    """Runtime-safe SPL governance (flag + activation gate)."""
    if not runtime_enrichment_activation_allowed(use_case_id):
        return None
    return enrichment_spl_governance(use_case_id)


def enrichment_spl_governance(use_case_id: str | None) -> dict[str, Any] | None:
    record = get_content_enrichment(use_case_id)
    if record is None:
        return None
    activation = resolve_use_case_activation(use_case_id)
    status = str(record.get("spl_template_status") or "unavailable")
    allowed_templates = [str(item) for item in record.get("allowed_spl_templates") or []]
    evidence_requirements = [str(item) for item in record.get("evidence_requirements") or []]
    limitations = [str(item) for item in record.get("limitations") or []]
    return {
        "use_case_id": record.get("use_case_id") or record.get("proposed_use_case_id"),
        "use_case_status": record.get("use_case_status"),
        "spl_template_status": status,
        "allowed_spl_templates": allowed_templates,
        "evidence_requirements": evidence_requirements,
        "limitations": limitations,
        "governed_limitation": _spl_limitation(status, allowed_templates),
        "llm_fallback_allowed": False,
        "activation": activation.model_dump(),
        "planner_runtime_activation_allowed": activation.planner_runtime_activation_allowed,
        "governed_enrichment_load_allowed": activation.governed_enrichment_load_allowed,
    }


def _spl_limitation(status: str, allowed_templates: list[str]) -> str | None:
    if status == "active":
        if allowed_templates:
            return None
        return "active_enrichment_without_allowed_template"
    if status == "sop_only":
        return "spl_template_sop_only_no_active_investigation_support"
    if status == "planned":
        return "spl_template_planned_no_free_spl_fallback"
    return "spl_template_unavailable_no_free_spl_fallback"


def _context_from_record(
    record: dict[str, Any],
    *,
    activation: UseCaseActivationDecision,
    catalog_row: dict[str, Any] | None,
) -> CuratedEnrichmentContext:
    use_case_id = str(record.get("use_case_id") or record.get("proposed_use_case_id") or activation.use_case_id)
    return CuratedEnrichmentContext(
        use_case_id=use_case_id,
        evidence_requirements=_string_list(record.get("evidence_requirements")),
        investigation_workflow=_string_list(record.get("investigation_workflow")),
        analyst_checklist=_string_list(record.get("analyst_checklist")),
        answer_rules=_string_list(record.get("answer_rules")),
        limitations=_string_list(record.get("limitations")),
        not_claimed_defaults=_string_list(record.get("not_claimed_defaults")),
        recommended_pivots=_string_list(record.get("recommended_pivots")),
        required_sources=_string_list((catalog_row or {}).get("required_sources")),
        optional_sources=_string_list((catalog_row or {}).get("optional_sources")),
        allowed_spl_templates=_string_list(record.get("allowed_spl_templates")),
        spl_template_status=str(record.get("spl_template_status") or "unavailable"),
        rag_doc_ids=_string_list(record.get("rag_doc_ids")),
        mitre_candidates=_string_list(record.get("mitre_candidates")),
        planning_or_analytic_skill=_first_str(record.get("planning_or_analytic_skill")),
        provenance_ref_ids=_provenance_ref_ids(record),
        activation_lifecycle_stage=activation.activation_lifecycle_stage,
        runtime_support_status=activation.runtime_support_status,
        activation_decision=activation,
    )


def _crosswalk_row(use_case_id: str) -> tuple[dict[str, Any] | None, str]:
    crosswalk = _load_crosswalk()
    for row in crosswalk.get("use_case_rows") or []:
        if isinstance(row, dict) and row.get("use_case_id") == use_case_id:
            return row, "matched_use_case"
    for row in crosswalk.get("proposed_use_case_rows") or []:
        if isinstance(row, dict) and row.get("proposed_use_case_id") == use_case_id:
            return row, "matched_proposed_use_case"
    for row in crosswalk.get("question_rows") or []:
        if isinstance(row, dict) and row.get("use_case_id") == use_case_id:
            return row, "matched_question_use_case"
    return None, "not_found"


def _proposed_use_case_row(use_case_id: str) -> dict[str, Any] | None:
    crosswalk = _load_crosswalk()
    for row in crosswalk.get("proposed_use_case_rows") or []:
        if isinstance(row, dict) and row.get("proposed_use_case_id") == use_case_id:
            return row
    return None


def _github_accepted_for_enrichment_only(
    enrichment: dict[str, Any] | None,
) -> bool:
    for ref in (enrichment or {}).get("github_reference_skills") or []:
        if isinstance(ref, dict) and str(ref.get("decision") or "") == "accepted":
            return True
    return False


def _github_lifecycle_status(enrichment: dict[str, Any] | None) -> str | None:
    if _github_accepted_for_enrichment_only(enrichment):
        return "accepted_for_enrichment"
    refs = (enrichment or {}).get("github_reference_skills") or []
    if refs:
        return "provenance_only"
    return None


def _provenance_ref_ids(record: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for item in record.get("github_reference_skills") or []:
        if not isinstance(item, dict):
            continue
        repo = str(item.get("repo") or "")
        path = str(item.get("path") or "")
        if repo or path:
            refs.append(f"github_ref:{repo}:{path}")
    return refs


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _first_str(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value:
            return value
    return None
