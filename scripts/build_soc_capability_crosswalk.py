#!/usr/bin/env python3
"""Build the SOC Capability Crosswalk spine (Phase 0 offline artifact).

Connects 105 question/runtime rows, 49 use-case catalog/export rows, 4 allowed
live execution skills, and 7 accepted GitHub-derived enrichments into a single
governed mapping document for SOC review and Knowledge exports.

OFFLINE ONLY — must not import ``app.*`` and must not be wired into ``/chat``.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

RUNTIME_MAP_PATH = REPO_ROOT / "backend" / "app" / "coverage" / "question_runtime_map_v1.json"
CATALOG_PATH = REPO_ROOT / "backend" / "app" / "use_cases" / "catalog.json"
CONTENT_ENRICHMENT_PATH = REPO_ROOT / "backend" / "app" / "use_cases" / "content_enrichment.json"
INTAKE_REGISTER_PATH = REPO_ROOT / "docs" / "skills" / "github_skill_intake_register.json"
DISCOVERY_INDEX_PATH = REPO_ROOT / "docs" / "skills" / "github_skill_discovery_index.json"
TRIAGE_SCORES_PATH = REPO_ROOT / "docs" / "skills" / "github_skill_triage_scores.json"
PROPOSED_USE_CASES_PATH = REPO_ROOT / "docs" / "skills" / "proposed_use_cases_from_github.json"
SPL_TEMPLATES_PATH = REPO_ROOT / "backend" / "app" / "spl" / "templates.json"
MATRIX_GENERATOR_PATH = REPO_ROOT / "scripts" / "build_skill_coverage_matrix.py"
OUTPUT_PATH = REPO_ROOT / "docs" / "evals" / "soc_capability_crosswalk.json"

SCHEMA_VERSION = "2026-06-07-phase0b-v1"
MITRE_METADATA_ROLE = "metadata_not_evidence"

ALLOWED_LIVE_SKILLS = frozenset(
    {"alert_summary", "spl_generation", "attack_discovery", "knowledge_recall"}
)

CATALOG_SKILL_COLLAPSE: dict[str, str] = {
    "action_planning": "knowledge_recall",
    "investigation_notes": "knowledge_recall",
    "mitre_mapping": "knowledge_recall",
    "ticket_drafting": "knowledge_recall",
}

GITHUB_NOT_RUNTIME_NOTE = (
    "GitHub-derived skills are provenance/enrichment reference only; "
    "never runtime skills and never loaded as raw SKILL.md into prompts or RAG."
)

GITHUB_ACCEPTANCE_NOTE = (
    "GitHub decision=accept means accepted_for_enrichment only — not runtime_active "
    "and not a live execution skill."
)


def _load_json(path: Path, warnings: list[str]) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        warnings.append(f"source file missing: {path}")
        return None
    except (json.JSONDecodeError, OSError) as exc:
        warnings.append(f"could not read source {path}: {exc}")
        return None


def _load_matrix_generator():
    spec = importlib.util.spec_from_file_location(
        "build_skill_coverage_matrix", MATRIX_GENERATOR_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load matrix generator from {MATRIX_GENERATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _index_catalog(catalog: Any, warnings: list[str]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    if not isinstance(catalog, dict):
        if catalog is not None:
            warnings.append("catalog.json is not an object")
        return index
    for record in catalog.get("use_cases") or []:
        if isinstance(record, dict) and record.get("use_case_id"):
            index[str(record["use_case_id"])] = record
    return index


def _index_enrichment(enrichment: Any, warnings: list[str]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    if not isinstance(enrichment, dict):
        if enrichment is not None:
            warnings.append("content_enrichment.json is not an object")
        return index
    records = enrichment.get("records")
    if not isinstance(records, dict):
        warnings.append("content_enrichment.json missing records object")
        return index
    for key, record in records.items():
        if isinstance(record, dict):
            use_case_id = record.get("use_case_id") or record.get("proposed_use_case_id") or key
            if isinstance(use_case_id, str) and use_case_id:
                index[use_case_id] = record
    return index


def _index_templates(templates: Any, warnings: list[str]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    if not isinstance(templates, dict):
        return index
    for record in templates.get("templates") or []:
        if isinstance(record, dict) and record.get("template_id"):
            index[str(record["template_id"])] = record
    return index


def _index_intake_by_use_case(register: Any, warnings: list[str]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    if not isinstance(register, dict):
        return index
    for record in register.get("records") or []:
        if not isinstance(record, dict):
            continue
        for use_case_id in record.get("internal_use_cases") or []:
            if isinstance(use_case_id, str) and use_case_id:
                index.setdefault(use_case_id, []).append(record)
    return index


def _collapse_live_skill(primary: str | None) -> str | None:
    if not isinstance(primary, str) or not primary:
        return None
    if primary in ALLOWED_LIVE_SKILLS:
        return primary
    return CATALOG_SKILL_COLLAPSE.get(primary)


def _github_reference_paths(enrichment: dict[str, Any] | None) -> list[str]:
    if not enrichment:
        return []
    refs = enrichment.get("github_reference_skills") or []
    paths: list[str] = []
    for ref in refs:
        if isinstance(ref, dict) and isinstance(ref.get("path"), str) and ref["path"]:
            paths.append(ref["path"])
    return sorted(set(paths))


def _github_reuse_types(enrichment: dict[str, Any] | None) -> list[str]:
    if not enrichment:
        return []
    reuse = enrichment.get("reuse_types")
    if isinstance(reuse, list):
        return sorted({str(item) for item in reuse if item})
    refs = enrichment.get("github_reference_skills") or []
    types = {
        str(ref.get("reuse_type"))
        for ref in refs
        if isinstance(ref, dict) and ref.get("reuse_type")
    }
    return sorted(types)


def _mitre_blocked(catalog: dict[str, Any] | None, enrichment: dict[str, Any] | None) -> list[str]:
    registry = catalog.get("mitre_registry") if isinstance(catalog, dict) else None
    if isinstance(registry, dict) and isinstance(registry.get("blocked"), list):
        blocked = [tid for tid in registry["blocked"] if isinstance(tid, str)]
        if blocked:
            return blocked
    if enrichment and isinstance(enrichment.get("not_claimed_defaults"), list):
        return [tid for tid in enrichment["not_claimed_defaults"] if isinstance(tid, str)]
    return []


def _mitre_candidates(
    matrix_row: dict[str, Any] | None,
    catalog: dict[str, Any] | None,
    enrichment: dict[str, Any] | None,
) -> list[str]:
    if enrichment and isinstance(enrichment.get("mitre_candidates"), list):
        candidates = [tid for tid in enrichment["mitre_candidates"] if isinstance(tid, str)]
        if candidates:
            return candidates
    if isinstance(catalog, dict):
        registry = catalog.get("mitre_registry")
        if isinstance(registry, dict) and isinstance(registry.get("candidate"), list):
            candidates = [tid for tid in registry["candidate"] if isinstance(tid, str)]
            if candidates:
                return candidates
        flat = catalog.get("mitre_candidates")
        if isinstance(flat, list):
            return [tid for tid in flat if isinstance(tid, str)]
    if matrix_row and isinstance(matrix_row.get("mitre_candidates"), list):
        return [tid for tid in matrix_row["mitre_candidates"] if isinstance(tid, str)]
    return []


def _spl_template_id(
    catalog: dict[str, Any] | None,
    enrichment: dict[str, Any] | None,
) -> str | None:
    if isinstance(catalog, dict):
        default = catalog.get("default_spl_template")
        if isinstance(default, str) and default:
            return default
    if enrichment:
        allowed = enrichment.get("allowed_spl_templates") or []
        if isinstance(allowed, list):
            for template_id in allowed:
                if isinstance(template_id, str) and template_id:
                    return template_id
    return None


def _workflow_status(enrichment: dict[str, Any] | None, field: str) -> str:
    if not enrichment:
        return "missing"
    value = enrichment.get(field)
    if isinstance(value, list) and value:
        return "present"
    return "missing"


def _rag_status(enrichment: dict[str, Any] | None) -> str:
    if not enrichment:
        return "missing"
    rag_docs = enrichment.get("rag_doc_ids") or enrichment.get("rag_collections")
    if isinstance(rag_docs, list) and rag_docs:
        return "configured"
    if enrichment.get("enrichment_status"):
        return "planned"
    return "missing"


def _derive_tests_added(
    enrichment: dict[str, Any] | None,
    intake_records: list[dict[str, Any]],
) -> bool:
    if enrichment and enrichment.get("test_status") == "tested":
        return True
    for record in intake_records:
        impl = record.get("implementation_status")
        if isinstance(impl, dict) and impl.get("tests_added") is True:
            return True
    return False


def _derive_validation_status(
    enrichment: dict[str, Any] | None,
    tests_added: bool,
) -> str:
    if isinstance(enrichment, dict):
        explicit = enrichment.get("validation_status")
        if explicit in {"soc_approved", "tests_added", "blocked", "needs_soc_review"}:
            return str(explicit)
    if tests_added:
        return "tests_added"
    return "needs_soc_review"


def _no_runtime_markdown_loading(
    enrichment: dict[str, Any] | None,
    intake_records: list[dict[str, Any]],
) -> bool:
    if enrichment:
        safety = enrichment.get("safety_review")
        if isinstance(safety, dict) and safety.get("no_runtime_markdown_loading") is False:
            return False
    for record in intake_records:
        safety = record.get("safety_review")
        if isinstance(safety, dict) and safety.get("no_runtime_markdown_loading") is False:
            return False
    return True


def _derive_runtime_support_status(
    *,
    catalog_present: bool,
    enrichment_present: bool,
    validation_status: str,
    tests_added: bool,
    live_execution_skill: str | None,
    spl_template_status: str | None,
    no_runtime_markdown_loading: bool,
    route_blocked: bool | None = None,
) -> str:
    if route_blocked is True:
        return "unsupported"
    if not catalog_present and enrichment_present:
        return "metadata_only"
    if (
        catalog_present
        and validation_status in {"soc_approved", "tests_added"}
        and tests_added
        and live_execution_skill in ALLOWED_LIVE_SKILLS
        and spl_template_status in {"active", "sop_only"}
        and no_runtime_markdown_loading
    ):
        return "runtime_active"
    if live_execution_skill == "knowledge_recall" and spl_template_status == "sop_only":
        return "sop_only"
    if catalog_present or enrichment_present:
        return "planned"
    return "metadata_only"


def _question_match_status(mapping_status: str | None, mapping_confidence: str | None) -> str:
    if mapping_status == "missing_authoritative_mapping":
        return "unmapped"
    if mapping_confidence == "medium":
        return "near"
    if mapping_status in {"curated_manual", "mapped_from_existing_metadata"}:
        return "exact"
    return "unmapped"


def _build_common_row_fields(
    *,
    use_case_id: str | None,
    catalog: dict[str, Any] | None,
    enrichment: dict[str, Any] | None,
    intake_records: list[dict[str, Any]],
    matrix_row: dict[str, Any] | None,
    live_execution_skill: str | None,
    planning_or_analytic_skill: str | None,
    mapping_status: str | None,
    mapping_confidence: str | None,
    spl_template_status: str | None,
    route_blocked: bool | None = None,
) -> dict[str, Any]:
    catalog_present = catalog is not None
    enrichment_present = enrichment is not None
    tests_added = _derive_tests_added(enrichment, intake_records)
    validation_status = _derive_validation_status(enrichment, tests_added)
    no_runtime_md = _no_runtime_markdown_loading(enrichment, intake_records)
    mitre_candidates = _mitre_candidates(matrix_row, catalog, enrichment)
    runtime_status = _derive_runtime_support_status(
        catalog_present=catalog_present,
        enrichment_present=enrichment_present,
        validation_status=validation_status,
        tests_added=tests_added,
        live_execution_skill=live_execution_skill,
        spl_template_status=spl_template_status,
        no_runtime_markdown_loading=no_runtime_md,
        route_blocked=route_blocked,
    )
    return {
        "use_case_id": use_case_id,
        "catalog_present": catalog_present,
        "enrichment_present": enrichment_present,
        "mapping_status": mapping_status,
        "mapping_confidence": mapping_confidence,
        "live_execution_skill": live_execution_skill,
        "planning_or_analytic_skill": planning_or_analytic_skill,
        "github_reference_skills": _github_reference_paths(enrichment),
        "github_reuse_type": _github_reuse_types(enrichment),
        "spl_template_id": _spl_template_id(catalog, enrichment),
        "spl_template_status": spl_template_status,
        "mitre_metadata_role": MITRE_METADATA_ROLE if mitre_candidates else None,
        "mitre_candidates": mitre_candidates,
        "mitre_blocked": _mitre_blocked(catalog, enrichment),
        "evidence_requirements": (
            enrichment.get("evidence_requirements")
            if enrichment
            else (
                {
                    "required_entities": list(catalog.get("required_entities") or []),
                    "optional_entities": list(catalog.get("optional_entities") or []),
                    "required_sources": list(catalog.get("required_sources") or []),
                    "optional_sources": list(catalog.get("optional_sources") or []),
                }
                if catalog
                else None
            )
        ),
        "investigation_workflow_status": _workflow_status(enrichment, "investigation_workflow"),
        "answer_rules_status": _workflow_status(enrichment, "answer_rules"),
        "rag_status": _rag_status(enrichment),
        "runtime_support_status": runtime_status,
        "validation_status": validation_status,
        "tests_added": tests_added,
    }


def _build_question_rows(
    matrix_rows: list[dict[str, Any]],
    runtime_map: dict[str, Any],
    catalog_index: dict[str, dict[str, Any]],
    enrichment_index: dict[str, dict[str, Any]],
    intake_by_use_case: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    runtime_by_ref: dict[str, dict[str, Any]] = {}
    for entry in runtime_map.get("entries") or []:
        if isinstance(entry, dict) and entry.get("question_ref"):
            runtime_by_ref[str(entry["question_ref"])] = entry

    rows: list[dict[str, Any]] = []
    for matrix_row in matrix_rows:
        question_id = matrix_row["question_id"]
        use_case_id = matrix_row.get("use_case_id")
        catalog = catalog_index.get(use_case_id) if use_case_id else None
        enrichment = enrichment_index.get(use_case_id) if use_case_id else None
        intake_records = intake_by_use_case.get(use_case_id or "", [])
        runtime_entry = runtime_by_ref.get(question_id, {})
        live_skill = matrix_row.get("live_execution_skill")
        if live_skill not in ALLOWED_LIVE_SKILLS:
            live_skill = _collapse_live_skill(
                (enrichment or {}).get("live_execution_skill")
                or (catalog or {}).get("primary_skill")
            )
        planning_skill = matrix_row.get("planning_or_analytic_skill") or (
            (enrichment or {}).get("planning_or_analytic_skill")
            or (catalog or {}).get("secondary_skills", [None])[0]
            if isinstance((catalog or {}).get("secondary_skills"), list)
            else None
        )
        spl_status = matrix_row.get("spl_template_status")
        if enrichment and enrichment.get("spl_template_status"):
            spl_status = enrichment.get("spl_template_status")
        common = _build_common_row_fields(
            use_case_id=use_case_id,
            catalog=catalog,
            enrichment=enrichment,
            intake_records=intake_records,
            matrix_row=matrix_row,
            live_execution_skill=live_skill,
            planning_or_analytic_skill=planning_skill,
            mapping_status=matrix_row.get("mapping_status"),
            mapping_confidence=matrix_row.get("mapping_confidence"),
            spl_template_status=spl_status,
            route_blocked=runtime_entry.get("route_blocked"),
        )
        rows.append(
            {
                "question_id": question_id,
                "question": matrix_row.get("query"),
                "question_match_status": _question_match_status(
                    matrix_row.get("mapping_status"), matrix_row.get("mapping_confidence")
                ),
                **common,
            }
        )
    rows.sort(key=lambda row: row["question_id"])
    return rows


def _build_use_case_rows(
    catalog_index: dict[str, dict[str, Any]],
    enrichment_index: dict[str, dict[str, Any]],
    intake_by_use_case: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    for use_case_id, catalog in sorted(catalog_index.items()):
        enrichment = enrichment_index.get(use_case_id)
        intake_records = intake_by_use_case.get(use_case_id, [])
        live_skill = _collapse_live_skill(
            (enrichment or {}).get("live_execution_skill") or catalog.get("primary_skill")
        )
        planning_skill = (enrichment or {}).get("planning_or_analytic_skill")
        if not planning_skill and isinstance(catalog.get("secondary_skills"), list):
            planning_skill = catalog["secondary_skills"][0] if catalog["secondary_skills"] else None
        spl_status = (enrichment or {}).get("spl_template_status") or "unavailable"
        common = _build_common_row_fields(
            use_case_id=use_case_id,
            catalog=catalog,
            enrichment=enrichment,
            intake_records=intake_records,
            matrix_row=None,
            live_execution_skill=live_skill,
            planning_or_analytic_skill=planning_skill,
            mapping_status="catalog_export_row",
            mapping_confidence="high",
            spl_template_status=spl_status,
        )
        rows.append(
            {
                "question_id": None,
                "question": None,
                "question_match_status": "n/a_use_case_only",
                **common,
            }
        )
        seen.add(use_case_id)

    for use_case_id, enrichment in sorted(enrichment_index.items()):
        if use_case_id in seen:
            continue
        intake_records = intake_by_use_case.get(use_case_id, [])
        common = _build_common_row_fields(
            use_case_id=use_case_id,
            catalog=None,
            enrichment=enrichment,
            intake_records=intake_records,
            matrix_row=None,
            live_execution_skill=_collapse_live_skill(enrichment.get("live_execution_skill")),
            planning_or_analytic_skill=enrichment.get("planning_or_analytic_skill"),
            mapping_status="enrichment_only_export_row",
            mapping_confidence="high",
            spl_template_status=enrichment.get("spl_template_status"),
        )
        rows.append(
            {
                "question_id": None,
                "question": None,
                "question_match_status": "n/a_use_case_only",
                **common,
            }
        )

    rows.sort(key=lambda row: str(row.get("use_case_id")))
    return rows


def _index_discovery(discovery: Any) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    if not isinstance(discovery, dict):
        return index
    for row in discovery.get("skills") or []:
        if isinstance(row, dict) and row.get("github_skill_id"):
            index[str(row["github_skill_id"])] = row
    return index


def _index_triage(triage: Any) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    if not isinstance(triage, dict):
        return index
    for row in triage.get("scores") or []:
        if isinstance(row, dict) and row.get("github_skill_id"):
            index[str(row["github_skill_id"])] = row
    return index


def _index_proposed_by_github_skill(proposed: Any) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    if not isinstance(proposed, dict):
        return index
    for row in proposed.get("proposed_use_cases") or []:
        if not isinstance(row, dict):
            continue
        skill_id = row.get("source_github_skill_id")
        proposed_id = row.get("proposed_use_case_id")
        if isinstance(skill_id, str) and isinstance(proposed_id, str):
            index.setdefault(skill_id, []).append(proposed_id)
    return index


def _build_github_skill_rows(
    register: dict[str, Any],
    enrichment_index: dict[str, dict[str, Any]],
    discovery_index: dict[str, dict[str, Any]],
    triage_index: dict[str, dict[str, Any]],
    proposed_by_skill: dict[str, list[str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in register.get("records") or []:
        if not isinstance(record, dict):
            continue
        github_skill_id = record.get("github_skill_id")
        internal_use_cases = [
            uc for uc in (record.get("internal_use_cases") or []) if isinstance(uc, str) and uc
        ]
        mapped_use_case_id = internal_use_cases[0] if len(internal_use_cases) == 1 else None
        mapping_state = (
            "mapped"
            if internal_use_cases
            else ("deferred" if record.get("decision") == "defer" else "rejected")
        )
        enrichment = enrichment_index.get(mapped_use_case_id) if mapped_use_case_id else None
        impl = record.get("implementation_status") if isinstance(record.get("implementation_status"), dict) else {}
        safety = record.get("safety_review") if isinstance(record.get("safety_review"), dict) else {}
        discovery = discovery_index.get(str(github_skill_id)) if github_skill_id else None
        triage = triage_index.get(str(github_skill_id)) if github_skill_id else None
        proposed_ids = proposed_by_skill.get(str(github_skill_id), [])
        rows.append(
            {
                "github_skill_id": github_skill_id,
                "decision": record.get("decision"),
                "review_status": record.get("review_status"),
                "acceptance_means": (
                    "accepted_for_enrichment_only"
                    if record.get("decision") == "accept"
                    else None
                ),
                "mapping_state": mapping_state,
                "mapped_use_case_id": mapped_use_case_id,
                "mapped_use_case_ids": internal_use_cases,
                "proposed_use_case_ids": proposed_ids,
                "runtime_skill": False,
                "runtime_support_status": "metadata_only",
                "validation_status": (
                    "tests_added" if impl.get("tests_added") else "needs_soc_review"
                ),
                "tests_added": bool(impl.get("tests_added")),
                "evidence_requirements_added": bool(impl.get("evidence_requirements_added")),
                "content_enrichment_added": bool(impl.get("content_enrichment_added")),
                "github_reuse_type": record.get("reuse_type"),
                "no_runtime_markdown_loading": safety.get("no_runtime_markdown_loading", True),
                "usage_note": GITHUB_NOT_RUNTIME_NOTE,
                "acceptance_not_runtime_activation": GITHUB_ACCEPTANCE_NOTE,
                "factory_visibility": {
                    "discovery_present": discovery is not None,
                    "discovery_review_status": discovery.get("review_status") if discovery else None,
                    "triage_recommended_decision": triage.get("recommended_decision") if triage else None,
                    "triage_priority": triage.get("priority") if triage else None,
                    "triage_soc_relevance": triage.get("soc_relevance") if triage else None,
                    "proposed_use_case_ids": proposed_ids,
                },
                "enrichment_linkage": {
                    "use_case_id": mapped_use_case_id,
                    "enrichment_present": enrichment is not None,
                    "github_reference_paths": _github_reference_paths(enrichment),
                },
            }
        )
    rows.sort(key=lambda row: str(row.get("github_skill_id")))
    return rows


def generate_crosswalk(warnings: list[str]) -> dict[str, Any]:
    matrix_mod = _load_matrix_generator()
    matrix_rows = matrix_mod.generate_matrix(warnings)

    runtime_map = _load_json(RUNTIME_MAP_PATH, warnings) or {}
    catalog = _load_json(CATALOG_PATH, warnings)
    enrichment = _load_json(CONTENT_ENRICHMENT_PATH, warnings)
    register = _load_json(INTAKE_REGISTER_PATH, warnings) or {}
    discovery = _load_json(DISCOVERY_INDEX_PATH, warnings)
    triage = _load_json(TRIAGE_SCORES_PATH, warnings)
    proposed = _load_json(PROPOSED_USE_CASES_PATH, warnings)
    if discovery is None:
        warnings.append("Phase 0B discovery index missing; github factory_visibility will be partial")
    if triage is None:
        warnings.append("Phase 0B triage scores missing; github factory_visibility will be partial")

    catalog_index = _index_catalog(catalog, warnings)
    enrichment_index = _index_enrichment(enrichment, warnings)
    intake_by_use_case = _index_intake_by_use_case(register, warnings)
    discovery_index = _index_discovery(discovery)
    triage_index = _index_triage(triage)
    proposed_by_skill = _index_proposed_by_github_skill(proposed)

    question_rows = _build_question_rows(
        matrix_rows, runtime_map, catalog_index, enrichment_index, intake_by_use_case
    )
    use_case_rows = _build_use_case_rows(catalog_index, enrichment_index, intake_by_use_case)
    github_skill_rows = _build_github_skill_rows(
        register,
        enrichment_index,
        discovery_index,
        triage_index,
        proposed_by_skill,
    )
    proposed_use_case_rows = proposed.get("proposed_use_cases") if isinstance(proposed, dict) else []

    expected_questions = 105
    expected_use_cases = 49
    expected_github = 7
    if len(question_rows) != expected_questions:
        warnings.append(
            f"question row count drift: expected {expected_questions}, got {len(question_rows)}"
        )
    if len(use_case_rows) != expected_use_cases:
        warnings.append(
            f"use_case row count drift: expected {expected_use_cases} "
            f"(46 catalog + 3 enrichment-only), got {len(use_case_rows)}"
        )
    if len(github_skill_rows) != expected_github:
        warnings.append(
            f"github_skill row count drift: expected {expected_github}, got {len(github_skill_rows)}"
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "mitre_metadata_role": MITRE_METADATA_ROLE,
        "allowed_live_execution_skills": sorted(ALLOWED_LIVE_SKILLS),
        "row_counts": {
            "question_rows": len(question_rows),
            "use_case_rows": len(use_case_rows),
            "github_skill_rows": len(github_skill_rows),
            "proposed_use_case_rows": len(proposed_use_case_rows or []),
            "catalog_use_cases": len(catalog_index),
            "enrichment_records": len(enrichment_index),
            "enrichment_only_use_cases": len(enrichment_index) - len(
                set(enrichment_index) & set(catalog_index)
            ),
            "discovery_skills": len(discovery_index),
            "triage_scores": len(triage_index),
        },
        "factory_visibility": {
            "discovery_index_present": discovery is not None,
            "triage_scores_present": triage is not None,
            "proposed_use_cases_present": proposed is not None,
            "github_acceptance_not_runtime_activation": GITHUB_ACCEPTANCE_NOTE,
        },
        "question_rows": question_rows,
        "use_case_rows": use_case_rows,
        "github_skill_rows": github_skill_rows,
        "proposed_use_case_rows": proposed_use_case_rows or [],
        "warnings": warnings,
    }


def _serialize(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _check_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a stable view for ``--check`` diffs (ignore generation timestamp)."""
    normalized = dict(payload)
    normalized["generated_at"] = "<generated>"
    return normalized


def _print_warnings(warnings: list[str]) -> None:
    if not warnings:
        return
    print(f"warnings ({len(warnings)}):", file=sys.stderr)
    for line in warnings:
        print(f"  WARN: {line}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Regenerate in memory and diff against on-disk artifact; exit 1 if stale.",
    )
    args = parser.parse_args(argv)

    warnings: list[str] = []
    payload = generate_crosswalk(warnings)
    rendered = _serialize(payload)

    if args.check:
        try:
            existing = OUTPUT_PATH.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError) as exc:
            _print_warnings(warnings)
            print(f"--check failed: cannot read {OUTPUT_PATH}: {exc}", file=sys.stderr)
            return 1
        _print_warnings(warnings)
        existing_payload = json.loads(existing)
        if _check_payload(existing_payload) != _check_payload(payload):
            print(
                f"--check failed: {OUTPUT_PATH} is stale; "
                "re-run without --check to refresh.",
                file=sys.stderr,
            )
            return 1
        print(
            f"--check ok: {OUTPUT_PATH} matches generated output "
            f"({payload['row_counts']['question_rows']} question rows)."
        )
        return 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(rendered, encoding="utf-8")
    _print_warnings(warnings)
    print(
        f"wrote {OUTPUT_PATH} "
        f"(questions={payload['row_counts']['question_rows']}, "
        f"use_cases={payload['row_counts']['use_case_rows']}, "
        f"github={payload['row_counts']['github_skill_rows']})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
