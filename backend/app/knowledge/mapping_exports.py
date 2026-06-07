"""Read-only Knowledge mapping export builders (no runtime routing changes)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.use_cases.content_enrichment import content_enrichment_records

MITRE_METADATA_ROLE = "metadata_not_evidence"

_REPO_ROOT_CANDIDATES = (
    Path(__file__).resolve().parents[3],
    Path("/workspace"),
)

_SKILL_COVERAGE_PATH = "docs/evals/skill_coverage_matrix.json"
_SOC_CAPABILITY_CROSSWALK_PATH = "docs/evals/soc_capability_crosswalk.json"
_GITHUB_INTAKE_PATH = "docs/skills/github_skill_intake_register.json"
_DISCOVERY_INDEX_PATH = "docs/skills/github_skill_discovery_index.json"
_TRIAGE_SCORES_PATH = "docs/skills/github_skill_triage_scores.json"
_PROPOSED_USE_CASES_PATH = "docs/skills/proposed_use_cases_from_github.json"
_ENRICHMENT_STATUS_JSON = "docs/skills/skill_enrichment_status_matrix.json"
_PENDING_BACKLOG_JSON = "docs/skills/pending_skill_enrichment_backlog.json"
_ENRICHMENT_STATUS_MD = "docs/skills/skill_enrichment_status_matrix.md"
_REJECTED_SKILLS_MD = "docs/skills/rejected_github_skills.md"
_PENDING_BACKLOG_MD = "docs/skills/pending_skill_enrichment_backlog.md"
_CATALOG_PATH = "backend/app/use_cases/catalog.json"

GITHUB_ACCEPTANCE_NOTE = (
    "GitHub decision=accept means accepted_for_enrichment only — not runtime_active "
    "and not a live execution skill."
)


def repo_root() -> Path:
    for base in _REPO_ROOT_CANDIDATES:
        if (base / _SKILL_COVERAGE_PATH).is_file():
            return base
    return _REPO_ROOT_CANDIDATES[0]


def load_skill_coverage_matrix_rows() -> list[dict[str, Any]]:
    path = repo_root() / _SKILL_COVERAGE_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        rows = payload.get("rows")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def build_skill_coverage_export_payload() -> dict[str, Any]:
    rows = load_skill_coverage_matrix_rows()
    return {
        "artifact": "skill_coverage_matrix",
        "source_file": _SKILL_COVERAGE_PATH,
        "mitre_metadata_role": MITRE_METADATA_ROLE,
        "row_count": len(rows),
        "rows": rows,
    }


def load_soc_capability_crosswalk() -> dict[str, Any]:
    path = repo_root() / _SOC_CAPABILITY_CROSSWALK_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def build_soc_capability_crosswalk_export_payload() -> dict[str, Any]:
    crosswalk = load_soc_capability_crosswalk()
    row_counts = crosswalk.get("row_counts") if isinstance(crosswalk.get("row_counts"), dict) else {}
    return {
        "artifact": "soc_capability_crosswalk",
        "source_file": _SOC_CAPABILITY_CROSSWALK_PATH,
        "schema_version": crosswalk.get("schema_version"),
        "generated_at": crosswalk.get("generated_at"),
        "mitre_metadata_role": crosswalk.get("mitre_metadata_role", MITRE_METADATA_ROLE),
        "allowed_live_execution_skills": crosswalk.get("allowed_live_execution_skills") or [],
        "row_counts": row_counts,
        "factory_visibility": crosswalk.get("factory_visibility") or {},
        "question_rows": crosswalk.get("question_rows") or [],
        "use_case_rows": crosswalk.get("use_case_rows") or [],
        "github_skill_rows": crosswalk.get("github_skill_rows") or [],
        "proposed_use_case_rows": crosswalk.get("proposed_use_case_rows") or [],
        "warnings": crosswalk.get("warnings") or [],
    }


def soc_capability_crosswalk_csv_rows() -> list[dict[str, Any]]:
    crosswalk = load_soc_capability_crosswalk()
    rows: list[dict[str, Any]] = []
    for kind, items in (
        ("question", crosswalk.get("question_rows") or []),
        ("use_case", crosswalk.get("use_case_rows") or []),
        ("github_skill", crosswalk.get("github_skill_rows") or []),
    ):
        for item in items:
            if isinstance(item, dict):
                rows.append({"row_kind": kind, **_soc_capability_crosswalk_csv_row(item)})
    return rows


def _soc_capability_crosswalk_csv_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "question_id": row.get("question_id"),
        "question": row.get("question"),
        "question_match_status": row.get("question_match_status"),
        "use_case_id": row.get("use_case_id"),
        "catalog_present": row.get("catalog_present"),
        "enrichment_present": row.get("enrichment_present"),
        "mapping_status": row.get("mapping_status"),
        "mapping_confidence": row.get("mapping_confidence"),
        "live_execution_skill": row.get("live_execution_skill"),
        "planning_or_analytic_skill": row.get("planning_or_analytic_skill"),
        "github_reference_skills": _join(row.get("github_reference_skills")),
        "github_reuse_type": _join(row.get("github_reuse_type")),
        "spl_template_id": row.get("spl_template_id"),
        "spl_template_status": row.get("spl_template_status"),
        "mitre_metadata_role": row.get("mitre_metadata_role") or MITRE_METADATA_ROLE,
        "mitre_candidates": _join(row.get("mitre_candidates")),
        "mitre_blocked": _join(row.get("mitre_blocked")),
        "evidence_requirements": _json_cell(row.get("evidence_requirements")),
        "investigation_workflow_status": row.get("investigation_workflow_status"),
        "answer_rules_status": row.get("answer_rules_status"),
        "rag_status": row.get("rag_status"),
        "runtime_support_status": row.get("runtime_support_status"),
        "validation_status": row.get("validation_status"),
        "tests_added": row.get("tests_added"),
        "github_skill_id": row.get("github_skill_id"),
        "decision": row.get("decision"),
        "mapping_state": row.get("mapping_state"),
        "runtime_skill": row.get("runtime_skill"),
    }


def skill_coverage_csv_rows() -> list[dict[str, Any]]:
    return [_skill_coverage_export_row(row) for row in load_skill_coverage_matrix_rows()]


def _skill_coverage_export_row(row: dict[str, Any]) -> dict[str, Any]:
    github_refs = row.get("github_reference_skills") or row.get("github_reference_skill")
    intake = row.get("github_intake_decision")
    evidence = row.get("evidence_requirements") or row.get("enrichment_evidence_requirements")
    return {
        "question_id": row.get("question_id"),
        "query": row.get("query"),
        "live_execution_skill": row.get("live_execution_skill"),
        "planning_or_analytic_skill": row.get("planning_or_analytic_skill"),
        "use_case_id": row.get("use_case_id"),
        "mapping_status": row.get("mapping_status"),
        "mapping_confidence": row.get("mapping_confidence"),
        "spl_template_status": row.get("spl_template_status"),
        "github_reference_skills": _join(github_refs),
        "github_intake_decision": _join(intake),
        "enrichment_status": row.get("enrichment_status"),
        "evidence_requirements": _join(evidence),
        "implementation_status": row.get("implementation_status"),
        "test_status": row.get("test_status"),
        "mitre_permitted": _join(row.get("mitre_permitted")),
        "mitre_metadata_role": MITRE_METADATA_ROLE,
    }


def load_github_intake_register() -> dict[str, Any]:
    path = repo_root() / _GITHUB_INTAKE_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {"records": []}


def _load_json_artifact(path_suffix: str) -> dict[str, Any]:
    path = repo_root() / path_suffix
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def load_github_skill_discovery_index() -> dict[str, Any]:
    return _load_json_artifact(_DISCOVERY_INDEX_PATH)


def build_github_skill_discovery_export_payload() -> dict[str, Any]:
    payload = load_github_skill_discovery_index()
    row_counts = payload.get("row_counts") if isinstance(payload.get("row_counts"), dict) else {}
    return {
        "artifact": "github_skill_discovery_index",
        "source_file": _DISCOVERY_INDEX_PATH,
        "schema_version": payload.get("schema_version"),
        "generated_at": payload.get("generated_at"),
        "clone_root_used": payload.get("clone_root_used"),
        "source_repo_name": payload.get("source_repo_name"),
        "usage_note": payload.get("usage_note") or GITHUB_ACCEPTANCE_NOTE,
        "row_counts": row_counts,
        "skills": payload.get("skills") or [],
        "warnings": payload.get("warnings") or [],
    }


def github_skill_discovery_csv_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for skill in load_github_skill_discovery_index().get("skills") or []:
        if not isinstance(skill, dict):
            continue
        rows.append(
            {
                "github_skill_id": skill.get("github_skill_id"),
                "path": skill.get("path"),
                "title": skill.get("title"),
                "domain": skill.get("domain"),
                "subdomain": skill.get("subdomain"),
                "tags": _join(skill.get("tags")),
                "mitre_attack": _join(skill.get("mitre_attack")),
                "likely_soc_relevance": skill.get("likely_soc_relevance"),
                "likely_internal_domain": skill.get("likely_internal_domain"),
                "review_status": skill.get("review_status"),
                "decision": skill.get("decision"),
                "priority": skill.get("priority"),
                "duplicate_of_existing": skill.get("duplicate_of_existing"),
            }
        )
    return rows


def load_github_skill_triage_scores() -> dict[str, Any]:
    return _load_json_artifact(_TRIAGE_SCORES_PATH)


def build_github_skill_triage_export_payload() -> dict[str, Any]:
    payload = load_github_skill_triage_scores()
    return {
        "artifact": "github_skill_triage_scores",
        "source_file": _TRIAGE_SCORES_PATH,
        "schema_version": payload.get("schema_version"),
        "generated_at": payload.get("generated_at"),
        "scoring_model_version": payload.get("scoring_model_version"),
        "usage_note": payload.get("usage_note") or GITHUB_ACCEPTANCE_NOTE,
        "row_counts": payload.get("row_counts") or {},
        "scores": payload.get("scores") or [],
        "warnings": payload.get("warnings") or [],
    }


def github_skill_triage_csv_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for score in load_github_skill_triage_scores().get("scores") or []:
        if not isinstance(score, dict):
            continue
        rows.append(
            {
                "github_skill_id": score.get("github_skill_id"),
                "path": score.get("path"),
                "soc_relevance": score.get("soc_relevance"),
                "defensive_usefulness": score.get("defensive_usefulness"),
                "mapped_mitre_value": score.get("mapped_mitre_value"),
                "splunk_log_detection_relevance": score.get("splunk_log_detection_relevance"),
                "enterprise_demo_value": score.get("enterprise_demo_value"),
                "evidence_model_availability": score.get("evidence_model_availability"),
                "safety_risk": score.get("safety_risk"),
                "overlap_with_existing_skill": score.get("overlap_with_existing_skill"),
                "implementation_complexity": score.get("implementation_complexity"),
                "data_source_availability": score.get("data_source_availability"),
                "recommended_decision": score.get("recommended_decision"),
                "priority": score.get("priority"),
                "reason": score.get("reason"),
            }
        )
    return rows


def load_proposed_use_cases_from_github() -> dict[str, Any]:
    return _load_json_artifact(_PROPOSED_USE_CASES_PATH)


def build_proposed_use_cases_export_payload() -> dict[str, Any]:
    payload = load_proposed_use_cases_from_github()
    return {
        "artifact": "proposed_use_cases_from_github",
        "source_file": _PROPOSED_USE_CASES_PATH,
        "schema_version": payload.get("schema_version"),
        "generated_at": payload.get("generated_at"),
        "usage_note": payload.get("usage_note") or GITHUB_ACCEPTANCE_NOTE,
        "row_counts": payload.get("row_counts") or {},
        "proposed_use_cases": payload.get("proposed_use_cases") or [],
        "warnings": payload.get("warnings") or [],
    }


def proposed_use_cases_csv_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in load_proposed_use_cases_from_github().get("proposed_use_cases") or []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "proposed_use_case_id": item.get("proposed_use_case_id"),
                "source_github_skill_id": item.get("source_github_skill_id"),
                "proposed_display_name": item.get("proposed_display_name"),
                "proposed_domain": item.get("proposed_domain"),
                "proposed_subdomain": item.get("proposed_subdomain"),
                "proposed_live_execution_skill": item.get("proposed_live_execution_skill"),
                "proposed_planning_skill": item.get("proposed_planning_skill"),
                "spl_template_need": item.get("spl_template_need"),
                "soc_approval_status": item.get("soc_approval_status"),
                "implementation_status": item.get("implementation_status"),
                "runtime_support_status": item.get("runtime_support_status"),
            }
        )
    return rows


def load_skill_enrichment_status_matrix() -> dict[str, Any]:
    json_path = repo_root() / _ENRICHMENT_STATUS_JSON
    if json_path.is_file():
        return _load_json_artifact(_ENRICHMENT_STATUS_JSON)
    return load_markdown_export(_ENRICHMENT_STATUS_MD)


def build_skill_enrichment_status_export_payload() -> dict[str, Any]:
    payload = load_skill_enrichment_status_matrix()
    if payload.get("format") == "markdown":
        return {
            **payload,
            "export_kind": "markdown_backed",
            "usage_note": "Markdown-backed export; regenerate skill_enrichment_status_matrix.json for JSON-backed view.",
        }
    return {
        "artifact": "skill_enrichment_status_matrix",
        "source_file": _ENRICHMENT_STATUS_JSON,
        "export_kind": "json_backed",
        "schema_version": payload.get("schema_version"),
        "generated_at": payload.get("generated_at"),
        "usage_note": payload.get("usage_note") or GITHUB_ACCEPTANCE_NOTE,
        "row_counts": payload.get("row_counts") or {},
        "rows": payload.get("rows") or [],
        "warnings": payload.get("warnings") or [],
    }


def skill_enrichment_status_csv_rows() -> list[dict[str, Any]]:
    payload = load_skill_enrichment_status_matrix()
    if payload.get("format") == "markdown":
        return []
    rows: list[dict[str, Any]] = []
    for item in payload.get("rows") or []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "internal_use_case": item.get("internal_use_case"),
                "github_reference_skills": _join(item.get("github_reference_skills")),
                "live_skill": item.get("live_skill"),
                "planning_skill": item.get("planning_skill"),
                "spl_template": item.get("spl_template"),
                "tests_added": item.get("tests_added"),
                "status": item.get("status"),
                "runtime_support_status": item.get("runtime_support_status"),
            }
        )
    return rows


def load_pending_skill_enrichment_backlog() -> dict[str, Any]:
    json_path = repo_root() / _PENDING_BACKLOG_JSON
    if json_path.is_file():
        return _load_json_artifact(_PENDING_BACKLOG_JSON)
    return load_markdown_export(_PENDING_BACKLOG_MD)


def build_pending_backlog_export_payload() -> dict[str, Any]:
    payload = load_pending_skill_enrichment_backlog()
    if payload.get("format") == "markdown":
        return {
            **payload,
            "export_kind": "markdown_backed",
            "usage_note": "Markdown-backed export; regenerate pending_skill_enrichment_backlog.json for JSON-backed view.",
        }
    return {
        "artifact": "pending_skill_enrichment_backlog",
        "source_file": _PENDING_BACKLOG_JSON,
        "export_kind": "json_backed",
        "schema_version": payload.get("schema_version"),
        "generated_at": payload.get("generated_at"),
        "usage_note": payload.get("usage_note") or "Advisory backlog only; not runtime activation.",
        "row_counts": payload.get("row_counts") or {},
        "backlog": payload.get("backlog") or [],
        "warnings": payload.get("warnings") or [],
    }


def pending_backlog_csv_rows() -> list[dict[str, Any]]:
    payload = load_pending_skill_enrichment_backlog()
    if payload.get("format") == "markdown":
        return []
    rows: list[dict[str, Any]] = []
    for item in payload.get("backlog") or []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "backlog_id": item.get("backlog_id"),
                "github_skill_id": item.get("github_skill_id"),
                "title": item.get("title"),
                "soc_domain": item.get("soc_domain"),
                "priority": item.get("priority"),
                "status": item.get("status"),
                "recommended_decision": item.get("recommended_decision"),
                "reason": item.get("reason"),
            }
        )
    return rows


def github_intake_csv_rows() -> list[dict[str, Any]]:
    register = load_github_intake_register()
    rows: list[dict[str, Any]] = []
    for record in register.get("records") or []:
        if not isinstance(record, dict):
            continue
        impl = record.get("implementation_status") if isinstance(record.get("implementation_status"), dict) else {}
        safety = record.get("safety_review") if isinstance(record.get("safety_review"), dict) else {}
        rows.append(
            {
                "github_skill_id": record.get("github_skill_id"),
                "path": record.get("path"),
                "decision": record.get("decision"),
                "review_status": record.get("review_status"),
                "domain": record.get("domain"),
                "subdomain": record.get("subdomain"),
                "internal_use_cases": _join(record.get("internal_use_cases")),
                "mapped_live_execution_skill": record.get("mapped_live_execution_skill"),
                "mapped_planning_or_analytic_skill": record.get("mapped_planning_or_analytic_skill"),
                "reuse_type": record.get("reuse_type"),
                "mitre_from_github": _join(record.get("mitre_from_github")),
                "content_enrichment_added": impl.get("content_enrichment_added"),
                "tests_added": impl.get("tests_added"),
                "defensive_only": safety.get("defensive_only"),
                "no_runtime_markdown_loading": safety.get("no_runtime_markdown_loading"),
                "priority": record.get("priority"),
                "reviewed_date": record.get("reviewed_date"),
            }
        )
    return rows


def load_markdown_export(path_suffix: str) -> dict[str, Any]:
    path = repo_root() / path_suffix
    content = path.read_text(encoding="utf-8")
    artifact = Path(path_suffix).stem
    return {
        "artifact": artifact,
        "source_file": path_suffix,
        "format": "markdown",
        "content": content,
    }


def load_use_case_catalog_export_rows() -> list[dict[str, Any]]:
    catalog_path = repo_root() / _CATALOG_PATH
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog_by_id: dict[str, dict[str, Any]] = {}
    for item in payload.get("use_cases") or []:
        if isinstance(item, dict) and item.get("use_case_id"):
            catalog_by_id[str(item["use_case_id"])] = dict(item)

    enrichment = content_enrichment_records()
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    for use_case_id, catalog_row in sorted(catalog_by_id.items()):
        row = dict(catalog_row)
        _merge_enrichment_export_fields(row, enrichment.get(use_case_id))
        row["catalog_present"] = True
        rows.append(row)
        seen.add(use_case_id)

    for use_case_id, enrich in sorted(enrichment.items()):
        if use_case_id in seen:
            continue
        row: dict[str, Any] = {
            "use_case_id": use_case_id,
            "display_name": enrich.get("use_case_id"),
            "category": enrich.get("domain"),
            "primary_skill": enrich.get("live_execution_skill"),
            "catalog_present": False,
        }
        _merge_enrichment_export_fields(row, enrich)
        rows.append(row)

    return rows


def _merge_enrichment_export_fields(row: dict[str, Any], enrich: dict[str, Any] | None) -> None:
    if enrich is None:
        row.setdefault("enrichment_present", False)
        return
    row["enrichment_present"] = True
    row["domain"] = enrich.get("domain")
    row["subdomain"] = enrich.get("subdomain")
    row["use_case_status"] = enrich.get("use_case_status")
    row["github_reference_skills"] = enrich.get("github_reference_skills") or []
    row["evidence_requirements"] = enrich.get("evidence_requirements") or []
    row["investigation_workflow"] = enrich.get("investigation_workflow") or []
    row["analyst_checklist"] = enrich.get("analyst_checklist") or []
    row["answer_rules"] = enrich.get("answer_rules") or []
    row["limitations"] = enrich.get("limitations") or []
    row["allowed_spl_templates"] = enrich.get("allowed_spl_templates") or []
    row["spl_template_status"] = enrich.get("spl_template_status")
    row["enrichment_status"] = enrich.get("enrichment_status")
    row["enrichment_implementation_status"] = _enrichment_implementation_status(enrich)


def _enrichment_implementation_status(enrich: dict[str, Any]) -> str:
    github_refs = enrich.get("github_reference_skills") or []
    if not github_refs:
        return "not_started"
    first = github_refs[0] if isinstance(github_refs[0], dict) else {}
    return str(first.get("implementation_status") or enrich.get("enrichment_status") or "content_added")


def use_case_catalog_csv_row(row: dict[str, Any]) -> dict[str, Any]:
    registry = row.get("mitre_registry") if isinstance(row.get("mitre_registry"), dict) else {}
    github_refs = row.get("github_reference_skills") or []
    github_paths = [
        ref.get("path") if isinstance(ref, dict) else str(ref)
        for ref in github_refs
    ]
    return {
        "use_case_id": row.get("use_case_id"),
        "display_name": row.get("display_name"),
        "category": row.get("category"),
        "catalog_present": row.get("catalog_present"),
        "primary_skill": row.get("primary_skill"),
        "secondary_skills": _join(row.get("secondary_skills")),
        "default_spl_template": row.get("default_spl_template"),
        "domain": row.get("domain"),
        "subdomain": row.get("subdomain"),
        "use_case_status": row.get("use_case_status"),
        "github_reference_skills": _join(github_paths),
        "evidence_requirements": _join(row.get("evidence_requirements")),
        "investigation_workflow": _join(row.get("investigation_workflow")),
        "analyst_checklist": _join(row.get("analyst_checklist")),
        "answer_rules": _join(row.get("answer_rules")),
        "limitations": _join(row.get("limitations")),
        "allowed_spl_templates": _join(row.get("allowed_spl_templates")),
        "spl_template_status": row.get("spl_template_status"),
        "enrichment_status": row.get("enrichment_status"),
        "enrichment_implementation_status": row.get("enrichment_implementation_status"),
        "enrichment_present": row.get("enrichment_present"),
        "mitre_candidates": _join(row.get("mitre_candidates")),
        "mitre_registry_permitted": _join(registry.get("permitted")),
        "mitre_registry_candidate": _join(registry.get("candidate")),
        "mitre_registry_blocked": _join(registry.get("blocked")),
        "mitre_requires_evidence": row.get("mitre_requires_evidence"),
        "mitre_requires_alert_context": row.get("mitre_requires_alert_context"),
        "mitre_visibility_policy": row.get("mitre_visibility_policy"),
        "mitre_metadata_role": MITRE_METADATA_ROLE,
        "mitre_blocked_rationale": _json_cell(registry.get("blocked_rationale")),
        "severity_policy": _json_cell(row.get("severity_policy")),
        "action_capability_tier": row.get("action_capability_tier"),
        "output_template": row.get("output_template"),
    }


def _join(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return "" if value is None else str(value)


def _json_cell(value: Any) -> str:
    if value is None:
        return ""
    return json.dumps(value, sort_keys=True)
