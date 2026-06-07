#!/usr/bin/env python3
"""Build Phase 0B JSON factory artifacts from governed repo sources.

Generates:
  - docs/skills/proposed_use_cases_from_github.json
  - docs/skills/skill_enrichment_status_matrix.json
  - docs/skills/pending_skill_enrichment_backlog.json

No ``app.*`` imports. Proposed use cases are never runtime_active.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from github_skill_factory_lib import (
    ALLOWED_LIVE_SKILLS,
    CATALOG_PATH,
    ENRICHMENT_PATH,
    GITHUB_ACCEPTANCE_NOTE,
    MITRE_METADATA_ROLE,
    load_intake_register,
    load_json,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DISCOVERY_PATH = REPO_ROOT / "docs" / "skills" / "github_skill_discovery_index.json"
TRIAGE_PATH = REPO_ROOT / "docs" / "skills" / "github_skill_triage_scores.json"
PROPOSED_PATH = REPO_ROOT / "docs" / "skills" / "proposed_use_cases_from_github.json"
STATUS_MATRIX_PATH = REPO_ROOT / "docs" / "skills" / "skill_enrichment_status_matrix.json"
PENDING_PATH = REPO_ROOT / "docs" / "skills" / "pending_skill_enrichment_backlog.json"

SCHEMA_VERSION = "2026-06-07-phase0b-v1"


def _catalog_ids(catalog: dict[str, Any]) -> set[str]:
    return {
        str(item["use_case_id"])
        for item in catalog.get("use_cases") or []
        if isinstance(item, dict) and item.get("use_case_id")
    }


def _primary_github_skill(enrich: dict[str, Any]) -> str | None:
    refs = enrich.get("github_reference_skills") or []
    if not refs:
        return None
    first = refs[0]
    if isinstance(first, dict) and first.get("path"):
        path = str(first["path"])
        return path.split("/")[1] if path.startswith("skills/") else path
    return None


def build_proposed_use_cases(warnings: list[str]) -> dict[str, Any]:
    enrichment = load_json(ENRICHMENT_PATH, warnings) or {}
    catalog = load_json(CATALOG_PATH, warnings) or {}
    catalog_ids = _catalog_ids(catalog)
    records = enrichment.get("records") if isinstance(enrichment, dict) else {}
    proposed: list[dict[str, Any]] = []

    if not isinstance(records, dict):
        warnings.append("content_enrichment.json missing records object")
        records = {}

    for use_case_id, enrich in sorted(records.items()):
        if not isinstance(enrich, dict):
            continue
        if use_case_id in catalog_ids:
            continue
        live_skill = enrich.get("live_execution_skill")
        if live_skill not in ALLOWED_LIVE_SKILLS:
            live_skill = "knowledge_recall"
        proposed.append(
            {
                "proposed_use_case_id": use_case_id,
                "source_github_skill_id": _primary_github_skill(enrich),
                "proposed_display_name": use_case_id.replace("_", " "),
                "proposed_domain": enrich.get("domain"),
                "proposed_subdomain": enrich.get("subdomain"),
                "proposed_live_execution_skill": live_skill,
                "proposed_planning_skill": enrich.get("planning_or_analytic_skill"),
                "required_sources": enrich.get("required_sources") or [],
                "evidence_requirements": enrich.get("evidence_requirements") or [],
                "spl_template_need": enrich.get("spl_template_status") or "planned",
                "mitre_metadata": {
                    "role": MITRE_METADATA_ROLE,
                    "candidates": enrich.get("mitre_candidates") or [],
                },
                "rag_sop_need": bool(enrich.get("rag_doc_ids")),
                "safety_notes": "Derived from curated enrichment metadata only; not catalog-promoted.",
                "soc_approval_status": "needs_soc_review",
                "implementation_status": enrich.get("enrichment_status") or "content_added",
                "runtime_support_status": "metadata_only",
                "catalog_promotion_required": True,
                "github_acceptance_not_runtime_activation": True,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "usage_note": GITHUB_ACCEPTANCE_NOTE,
        "row_counts": {"proposed_use_cases": len(proposed)},
        "proposed_use_cases": proposed,
        "warnings": warnings,
    }


def build_enrichment_status_matrix(warnings: list[str]) -> dict[str, Any]:
    enrichment = load_json(ENRICHMENT_PATH, warnings) or {}
    register = load_intake_register(warnings)
    records = enrichment.get("records") if isinstance(enrichment, dict) else {}
    rows: list[dict[str, Any]] = []

    if not isinstance(records, dict):
        warnings.append("content_enrichment.json missing records object")
        records = {}

    for use_case_id, enrich in sorted(records.items()):
        if not isinstance(enrich, dict):
            continue
        github_refs = []
        for ref in enrich.get("github_reference_skills") or []:
            if isinstance(ref, dict) and ref.get("path"):
                github_refs.append(ref["path"].split("/")[1])
        impl = enrich.get("implementation_status")
        if not isinstance(impl, dict):
            impl = {}
        rows.append(
            {
                "internal_use_case": use_case_id,
                "github_reference_skills": github_refs,
                "live_skill": enrich.get("live_execution_skill"),
                "planning_skill": enrich.get("planning_or_analytic_skill"),
                "mitre_added": "metadata_only",
                "evidence_added": bool(enrich.get("evidence_requirements")),
                "spl_template": enrich.get("spl_template_status"),
                "workflow_added": bool(enrich.get("investigation_workflow")),
                "answer_rules": bool(enrich.get("answer_rules")),
                "rag_added": bool(enrich.get("rag_doc_ids")),
                "tests_added": enrich.get("test_status") == "tested",
                "status": "tests_added" if enrich.get("test_status") == "tested" else "content_added",
                "runtime_support_status": "planned",
                "github_acceptance_not_runtime_activation": True,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source_file": "backend/app/use_cases/content_enrichment.json",
        "intake_register_records": len(register.get("records") or []),
        "usage_note": GITHUB_ACCEPTANCE_NOTE,
        "row_counts": {"use_cases": len(rows)},
        "rows": rows,
        "warnings": warnings,
    }


def build_pending_backlog(warnings: list[str]) -> dict[str, Any]:
    discovery = load_json(DISCOVERY_PATH, warnings)
    triage = load_json(TRIAGE_PATH, warnings)
    register = load_intake_register(warnings)
    accepted_ids = {
        str(record["github_skill_id"])
        for record in register.get("records") or []
        if isinstance(record, dict)
        and record.get("decision") == "accept"
        and record.get("github_skill_id")
    }

    triage_by_id: dict[str, dict[str, Any]] = {}
    for row in (triage or {}).get("scores") or []:
        if isinstance(row, dict) and row.get("github_skill_id"):
            triage_by_id[str(row["github_skill_id"])] = row

    backlog: list[dict[str, Any]] = []
    for skill in (discovery or {}).get("skills") or []:
        if not isinstance(skill, dict):
            continue
        skill_id = str(skill.get("github_skill_id"))
        if skill_id in accepted_ids:
            continue
        triage_row = triage_by_id.get(skill_id, {})
        decision = triage_row.get("recommended_decision") or "defer"
        if decision in {"reject", "duplicate"}:
            continue
        backlog.append(
            {
                "backlog_id": f"BL-AUTO-{skill_id}",
                "github_skill_id": skill_id,
                "path": skill.get("path"),
                "title": skill.get("title"),
                "soc_domain": skill.get("likely_internal_domain"),
                "internal_use_case_candidate": None,
                "mitre_candidate": skill.get("mitre_attack") or [],
                "priority": triage_row.get("priority") or "P3",
                "dependency": "phase0b_discovery",
                "status": "review" if decision == "review" else "deferred",
                "recommended_decision": decision,
                "reason": triage_row.get("reason"),
            }
        )

    backlog.sort(key=lambda row: (row.get("priority") or "P9", row.get("github_skill_id") or ""))
    # Keep backlog bounded for analyst review surfaces.
    backlog = backlog[:100]

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source_files": [
            "docs/skills/github_skill_discovery_index.json",
            "docs/skills/github_skill_triage_scores.json",
            "docs/skills/github_skill_intake_register.json",
        ],
        "usage_note": "Advisory backlog only. Batch 2 skills are not implemented here.",
        "row_counts": {"backlog_items": len(backlog)},
        "backlog": backlog,
        "warnings": warnings,
    }


def _serialize(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _check_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    normalized["generated_at"] = "<generated>"
    return normalized


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    warnings: list[str] = []
    artifacts = {
        PROPOSED_PATH: build_proposed_use_cases(list(warnings)),
        STATUS_MATRIX_PATH: build_enrichment_status_matrix([]),
        PENDING_PATH: build_pending_backlog([]),
    }

    if args.check:
        for path, payload in artifacts.items():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
                print(f"--check failed for {path}: {exc}", file=sys.stderr)
                return 1
            if _check_payload(existing) != _check_payload(payload):
                print(f"--check failed: {path} is stale", file=sys.stderr)
                return 1
        print("--check ok: factory artifacts match generated output")
        return 0

    for path, payload in artifacts.items():
        path.write_text(_serialize(payload), encoding="utf-8")
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
