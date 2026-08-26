#!/usr/bin/env python3
"""Build the SOC/COE validation package (Phase 10 offline artifacts).

Derives SOC review sheets from the governed SOC Capability Crosswalk spine
(plus templates and curated enrichment detail joins) so the SOC/COE team can
review what is runtime-active, planned, metadata-only, unsupported, and safe
to demonstrate.

Phase 10 is validation and documentation, NOT runtime activation:
  - The crosswalk is the single authority for runtime_support_status,
    validation_status, tests_added, live_execution_skill, and row membership.
  - Detail-only fields are joined by use_case_id; missing joins emit null + a
    warning, never a fabricated value.
  - Review/approval fields (review_decision, *_review_notes) are left blank for
    SOC to fill. This generator never invents approval.

OFFLINE ONLY — must not import ``app.*`` and must not be wired into ``/chat``.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

CROSSWALK_PATH = REPO_ROOT / "docs" / "evals" / "soc_capability_crosswalk.json"
TEMPLATES_PATH = REPO_ROOT / "backend" / "app" / "spl" / "templates.json"
CONTENT_ENRICHMENT_PATH = REPO_ROOT / "backend" / "app" / "use_cases" / "content_enrichment.json"
OUTPUT_DIR = REPO_ROOT / "docs" / "validation"

SCHEMA_VERSION = "2026-06-08-phase10-v1"
MITRE_METADATA_ROLE = "metadata_not_evidence"

VALIDATION_NOT_ACTIVATION_NOTE = (
    "Validation/review artifact only. Phase 10 is documentation, not runtime "
    "activation. runtime_support_status and validation_status are authoritative "
    "from the SOC Capability Crosswalk; review_decision/*_review_notes are blank "
    "for SOC to complete."
)
MITRE_EVIDENCE_SOURCE = (
    "Runtime MITRE evidence status comes only from the planner MITRE branch "
    "(resolve_mitre_decision); registry/crosswalk candidates are "
    "metadata_not_evidence and never evidence_supported on their own."
)
SPL_VALIDATOR_EXPECTATION = (
    "Deterministic spl_validator is the final gate; candidate SPL is review-only "
    "with execution_enabled=false. No SPL execution and no MCP enablement."
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


def _rows(crosswalk: dict[str, Any], key: str) -> list[dict[str, Any]]:
    items = crosswalk.get(key) if isinstance(crosswalk, dict) else None
    if not isinstance(items, list):
        return []
    return [row for row in items if isinstance(row, dict)]


def _enrichment_index(enrichment: Any) -> dict[str, dict[str, Any]]:
    records = enrichment.get("records") if isinstance(enrichment, dict) else None
    if isinstance(records, dict):
        return {k: v for k, v in records.items() if isinstance(v, dict)}
    return {}


def _template_index(templates: Any) -> dict[str, dict[str, Any]]:
    items = templates.get("templates") if isinstance(templates, dict) else None
    if not isinstance(items, list):
        return {}
    return {t["template_id"]: t for t in items if isinstance(t, dict) and t.get("template_id")}


def _provenance_refs(github_reference_skills: Any) -> list[dict[str, Any]]:
    """Return audit pointers (repo/path/reuse) only — never SKILL.md content."""
    refs: list[dict[str, Any]] = []
    if not isinstance(github_reference_skills, list):
        return refs
    for ref in github_reference_skills:
        if isinstance(ref, dict):
            refs.append(
                {
                    "repo": ref.get("repo"),
                    "path": ref.get("path"),
                    "reuse_type": ref.get("reuse_type"),
                    "decision": ref.get("decision"),
                }
            )
        elif isinstance(ref, str):
            refs.append({"ref": ref})
    return refs


def _sheet(artifact: str, *, source_files: list[str], rows: list[dict[str, Any]],
           row_counts: dict[str, Any], warnings: list[str],
           extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "artifact": artifact,
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "export_kind": "validation_review_sheet",
        "usage_note": VALIDATION_NOT_ACTIVATION_NOTE,
        "source_files": source_files,
        "row_counts": row_counts,
        "rows": rows,
        "warnings": warnings,
    }
    if extra:
        payload.update(extra)
    return payload


# --------------------------------------------------------------------------- #
# Individual sheets
# --------------------------------------------------------------------------- #
def build_use_case_validation_sheet(uc_rows, enrich_idx, warnings) -> dict[str, Any]:
    rows = []
    for row in uc_rows:
        rows.append(
            {
                "use_case_id": row.get("use_case_id"),
                "catalog_present": row.get("catalog_present"),
                "runtime_support_status": row.get("runtime_support_status"),
                "validation_status": row.get("validation_status"),
                "tests_added": row.get("tests_added"),
                "live_execution_skill": row.get("live_execution_skill"),
                "spl_template_status": row.get("spl_template_status"),
                "enrichment_present": row.get("enrichment_present"),
                "rag_status": row.get("rag_status"),
                "review_decision": "",
                "notes": "",
            }
        )
    rows.sort(key=lambda r: (r["use_case_id"] is None, r["use_case_id"] or ""))
    return _sheet(
        "soc_validation_use_cases",
        source_files=["docs/evals/soc_capability_crosswalk.json"],
        rows=rows,
        row_counts={"use_cases": len(rows)},
        warnings=warnings,
    )


def build_spl_template_review_sheet(uc_rows, enrich_idx, template_idx, warnings) -> dict[str, Any]:
    rows = []
    for row in uc_rows:
        ucid = row.get("use_case_id")
        enrich = enrich_idx.get(ucid or "", {})
        allowed = enrich.get("allowed_spl_templates") or []
        template_id = row.get("spl_template_id")
        template_status = row.get("spl_template_status")
        # Crosswalk spl_template_status is the runtime availability/allowlist
        # authority; templates.json status is the template file's own state.
        # They mean different things, so surface both rather than reconcile.
        template_file_status = (
            template_idx[template_id].get("status")
            if template_id and template_id in template_idx
            else None
        )
        rows.append(
            {
                "use_case_id": ucid,
                "spl_template_id": template_id,
                "spl_template_status": template_status,
                "template_file_status": template_file_status,
                "allowed_spl_templates": allowed,
                "validator_expectation": SPL_VALIDATOR_EXPECTATION,
                "review_only": True,
                "no_execution": True,
                "review_notes": "",
            }
        )
    rows.sort(key=lambda r: (r["use_case_id"] is None, r["use_case_id"] or ""))
    return _sheet(
        "soc_validation_spl_templates",
        source_files=[
            "docs/evals/soc_capability_crosswalk.json",
            "backend/app/spl/templates.json",
            "backend/app/use_cases/content_enrichment.json",
        ],
        rows=rows,
        row_counts={"use_cases": len(rows)},
        warnings=warnings,
    )


def build_mitre_validation_sheet(uc_rows, warnings) -> dict[str, Any]:
    rows = []
    for row in uc_rows:
        rows.append(
            {
                "use_case_id": row.get("use_case_id"),
                "mitre_metadata_role": row.get("mitre_metadata_role") or MITRE_METADATA_ROLE,
                "mitre_candidates": row.get("mitre_candidates") or [],
                "mitre_blocked": row.get("mitre_blocked") or [],
                "evidence_status_source": MITRE_EVIDENCE_SOURCE,
                "soc_review_notes": "",
            }
        )
    rows.sort(key=lambda r: (r["use_case_id"] is None, r["use_case_id"] or ""))
    return _sheet(
        "soc_validation_mitre",
        source_files=["docs/evals/soc_capability_crosswalk.json"],
        rows=rows,
        row_counts={"use_cases": len(rows)},
        warnings=warnings,
        extra={"mitre_metadata_role": MITRE_METADATA_ROLE},
    )


def build_question_validation_sheet(q_rows, warnings) -> dict[str, Any]:
    rows = []
    for row in q_rows:
        rows.append(
            {
                "question_id": row.get("question_id"),
                "question": row.get("question"),
                "question_match_status": row.get("question_match_status"),
                "use_case_id": row.get("use_case_id"),
                "mapping_status": row.get("mapping_status"),
                "runtime_support_status": row.get("runtime_support_status"),
                "disposition": row.get("runtime_support_status"),
            }
        )
    rows.sort(key=lambda r: (r["question_id"] is None, r["question_id"] or ""))
    return _sheet(
        "soc_validation_questions",
        source_files=["docs/evals/soc_capability_crosswalk.json"],
        rows=rows,
        row_counts={"questions": len(rows)},
        warnings=warnings,
    )


def build_rag_sop_validation_sheet(uc_rows, enrich_idx, warnings) -> dict[str, Any]:
    rows = []
    for row in uc_rows:
        ucid = row.get("use_case_id")
        enrich = enrich_idx.get(ucid or "", {})
        runtime_status = row.get("runtime_support_status")
        sop_only = runtime_status == "sop_only"
        rows.append(
            {
                "use_case_id": ucid,
                "rag_status": row.get("rag_status"),
                "rag_doc_ids": enrich.get("rag_doc_ids") or [],
                "rag_collections": enrich.get("rag_collections") or [],
                "sop_only": sop_only,
                "no_spl_expectation": sop_only,
                "kb_no_match_behavior_review": "",
            }
        )
    rows.sort(key=lambda r: (r["use_case_id"] is None, r["use_case_id"] or ""))
    return _sheet(
        "soc_validation_rag_sop",
        source_files=[
            "docs/evals/soc_capability_crosswalk.json",
            "backend/app/use_cases/content_enrichment.json",
        ],
        rows=rows,
        row_counts={"use_cases": len(rows)},
        warnings=warnings,
    )


def _classify_cases(uc_rows, q_rows) -> dict[str, list[str]]:
    examples: dict[str, list[str]] = {c: [] for c in "ABCDEFGH"}
    for row in uc_rows:
        ucid = row.get("use_case_id")
        if not ucid:
            continue
        has_105 = row.get("question_id") is not None
        catalog = bool(row.get("catalog_present"))
        enrichment = bool(row.get("enrichment_present"))
        has_provenance = bool(row.get("github_reference_skills"))
        if catalog and enrichment and has_provenance:
            examples["E"].append(ucid)
        if has_105 and catalog and enrichment:
            examples["A"].append(ucid)
        elif has_105 and catalog and not enrichment:
            examples["B"].append(ucid)
        if catalog and not has_105:
            examples["D"].append(ucid)
        if enrichment and not catalog:
            examples["F"].append(ucid)
    for row in q_rows:
        if row.get("question_id") and not row.get("use_case_id"):
            examples["C"].append(row.get("question_id"))
    return {c: sorted(set(v))[:6] for c, v in examples.items()}


def build_combination_matrix_sheet(uc_rows, q_rows, warnings) -> dict[str, Any]:
    examples = _classify_cases(uc_rows, q_rows)
    cases = [
        ("A", "105 + catalog + enrichment", "Happy path; full branches if runtime_active and template allows."),
        ("B", "105 + catalog, no enrichment", "Runtime-supported but thinner; catalog SPL + registry MITRE, generic rules."),
        ("C", "105 only, no catalog", "No full runtime support; routing hint/eval only; RAG/generic/clarification."),
        ("D", "catalog only, no 105", "Valid for paraphrases; catalog authority; use_case_id activation."),
        ("E", "catalog + enrichment + provenance ref", "Best supported; curated enrichment drives evidence plan + contract; external-origin refs are provenance only."),
        ("F", "enrichment-only, no catalog", "metadata_only/planned; NO runtime activation; promote to catalog first."),
        ("G", "no 105/no catalog, SOC-related", "generic_soc_guidance or RAG-only; no fake use_case/SPL/MITRE evidence."),
        ("H", "unsafe / out-of-scope", "path_type=unsafe_blocked; HIL + blocked contract."),
    ]
    rows = [
        {
            "case": code,
            "condition": cond,
            "planner_runtime_behavior": behavior,
            "example_use_case_ids": examples.get(code, []),
            "review_note": "",
        }
        for code, cond, behavior in cases
    ]
    return _sheet(
        "soc_validation_combination_matrix",
        source_files=["docs/evals/soc_capability_crosswalk.json"],
        rows=rows,
        row_counts={"cases": len(rows)},
        warnings=warnings,
        extra={"csv_supported": False},
    )


def build_demo_scenario_sheet(uc_index, warnings) -> dict[str, Any]:
    def runtime_for(ucid: str | None) -> str:
        if not ucid:
            return "n/a"
        return uc_index.get(ucid, {}).get("runtime_support_status", "unmapped")

    scenarios = [
        ("Failed login spike", "Investigate a spike of failed logins for a user/source", "auth_failed_login_spike", "spl_review"),
        ("Successful login after failures", "Failed logins followed by a successful login from same user", "auth_success_after_failure", "hybrid_investigation"),
        ("DNS beaconing candidate", "Possible periodic DNS beaconing to a rare domain", "dns_beaconing_candidate", "spl_review_plus_rag"),
        ("Suspicious PowerShell", "Suspicious encoded PowerShell command on an endpoint", "edr_powershell_suspicious_command", "spl_review_plus_rag"),
        ("SOP-only query", "Show the SOP/runbook for brute-force handling (no SPL)", None, "rag_only"),
        ("MITRE-only without alert context", "Map this to MITRE (no alert/evidence provided)", None, "mitre_context_required"),
        ("Enrichment-only pilot", "Review phishing email headers (design-only pilot)", "email_phishing_header_review", "generic_soc_guidance"),
        ("Unsafe containment/execution request", "Contain/isolate the host or run the query now", None, "unsafe_blocked"),
    ]
    rows = []
    for name, prompt, ucid, expected_path in scenarios:
        runtime_status = runtime_for(ucid)
        # An enrichment-only / non-runtime_active pilot must not be demoed as live.
        runtime_active = runtime_status == "runtime_active"
        rows.append(
            {
                "scenario": name,
                "prompt_example": prompt,
                "target_use_case_id": ucid,
                "expected_path_type": expected_path,
                "runtime_support_status": runtime_status,
                "runtime_active": runtime_active,
                "demo_safe_as_live": runtime_active,
                "demo_safe_as_guidance_or_blocked": expected_path in {"rag_only", "mitre_context_required", "generic_soc_guidance", "unsafe_blocked"},
                "review_notes": "",
            }
        )
    return _sheet(
        "soc_validation_demo_scenarios",
        source_files=["docs/evals/soc_capability_crosswalk.json"],
        rows=rows,
        row_counts={"scenarios": len(rows)},
        warnings=warnings,
        extra={"csv_supported": False},
    )


def _readme(sheets: dict[str, dict[str, Any]]) -> str:
    lines = [
        "# SOC / COE Validation Package (Phase 10)",
        "",
        "Generated review sheets derived from the governed **SOC Capability "
        "Crosswalk** spine. **Validation and documentation only — not runtime "
        "activation.**",
        "",
        "- The crosswalk is authoritative for `runtime_support_status`, "
        "`validation_status`, `tests_added`, `live_execution_skill`, and row "
        "membership (105 questions / use-case rows).",
        "- Detail columns (SPL template status, enrichment, and RAG docs) are "
        "joined by `use_case_id`.",
        "- `review_decision` / `*_review_notes` are blank for SOC to complete. "
        "This generator never invents approval.",
        "- No `/chat` runtime behavior, flags, SPL execution, MCP enablement, or "
        "MITRE/SPL/composer logic is changed by this package.",
        "",
        "## Regenerate",
        "",
        "```bash",
        "python3 scripts/build_soc_validation_sheets.py",
        "python3 scripts/build_soc_validation_sheets.py --check   # CI staleness gate",
        "```",
        "",
        "## Artifacts",
        "",
        "| File | Knowledge export key | CSV |",
        "|------|----------------------|-----|",
    ]
    csv_map = {
        "use_case_validation_sheet.json": ("soc_validation_use_cases", "yes"),
        "spl_template_review_sheet.json": ("soc_validation_spl_templates", "yes"),
        "mitre_validation_sheet.json": ("soc_validation_mitre", "yes"),
        "question_validation_sheet.json": ("soc_validation_questions", "yes"),
        "rag_sop_validation_sheet.json": ("soc_validation_rag_sop", "yes"),
        "combination_matrix_sheet.json": ("soc_validation_combination_matrix", "no"),
        "demo_scenario_sheet.json": ("soc_validation_demo_scenarios", "no"),
    }
    for filename, (key, csv_ok) in csv_map.items():
        lines.append(f"| `{filename}` | `{key}` | {csv_ok} |")
    lines.extend(
        [
            "",
            "All seven sheets are exposed via `GET /knowledge/exports/{artifact}` "
            "using the keys above.",
            "Phase 11 demo/flag guidance: `docs/demo/flag_cutover_matrix.md`, "
            "`docs/demo/demo_scenarios_readiness.md`.",
            "",
            "## Combination cases A–H",
            "",
            "See `combination_matrix_sheet.json` for the planner runtime behavior "
            "per case (A happy-path → H unsafe_blocked).",
            "",
            "## Demo scenarios",
            "",
            "`demo_scenario_sheet.json` encodes `runtime_support_status` per "
            "scenario so a demo cannot overclaim. Only `runtime_active` use cases "
            "may be shown as live-supported; enrichment-only pilots "
            "(`email_phishing_header_review`) are design-only.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
FILE_MAP = {
    "use_case_validation_sheet.json": "soc_validation_use_cases",
    "spl_template_review_sheet.json": "soc_validation_spl_templates",
    "mitre_validation_sheet.json": "soc_validation_mitre",
    "question_validation_sheet.json": "soc_validation_questions",
    "rag_sop_validation_sheet.json": "soc_validation_rag_sop",
    "combination_matrix_sheet.json": "soc_validation_combination_matrix",
    "demo_scenario_sheet.json": "soc_validation_demo_scenarios",
}


def generate_sheets() -> tuple[dict[str, dict[str, Any]], str, list[str]]:
    warnings: list[str] = []
    crosswalk = _load_json(CROSSWALK_PATH, warnings) or {}
    templates = _load_json(TEMPLATES_PATH, warnings)
    enrichment = _load_json(CONTENT_ENRICHMENT_PATH, warnings)

    uc_rows = _rows(crosswalk, "use_case_rows")
    q_rows = _rows(crosswalk, "question_rows")
    enrich_idx = _enrichment_index(enrichment)
    template_idx = _template_index(templates)
    uc_index = {r.get("use_case_id"): r for r in uc_rows if r.get("use_case_id")}

    sheets = {
        "use_case_validation_sheet.json": build_use_case_validation_sheet(uc_rows, enrich_idx, []),
        "spl_template_review_sheet.json": build_spl_template_review_sheet(uc_rows, enrich_idx, template_idx, []),
        "mitre_validation_sheet.json": build_mitre_validation_sheet(uc_rows, []),
        "question_validation_sheet.json": build_question_validation_sheet(q_rows, []),
        "rag_sop_validation_sheet.json": build_rag_sop_validation_sheet(uc_rows, enrich_idx, []),
        "combination_matrix_sheet.json": build_combination_matrix_sheet(uc_rows, q_rows, []),
        "demo_scenario_sheet.json": build_demo_scenario_sheet(uc_index, []),
    }
    # Surface per-sheet warnings at the package level too.
    for sheet in sheets.values():
        warnings.extend(sheet.get("warnings") or [])
    readme = _readme(sheets)
    return sheets, readme, warnings


def _serialize(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _check_view(payload: dict[str, Any]) -> dict[str, Any]:
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
        help="Regenerate in memory and diff against on-disk artifacts; exit 1 if stale.",
    )
    args = parser.parse_args(argv)

    sheets, readme, warnings = generate_sheets()

    if args.check:
        _print_warnings(warnings)
        stale: list[str] = []
        for filename, payload in sheets.items():
            disk = OUTPUT_DIR / filename
            try:
                existing = json.loads(disk.read_text(encoding="utf-8"))
            except (FileNotFoundError, OSError, json.JSONDecodeError):
                stale.append(filename)
                continue
            if _check_view(existing) != _check_view(payload):
                stale.append(filename)
        readme_disk = OUTPUT_DIR / "README.md"
        if not readme_disk.is_file() or readme_disk.read_text(encoding="utf-8") != readme:
            stale.append("README.md")
        if stale:
            print(f"--check failed: stale validation artifacts: {', '.join(sorted(stale))}", file=sys.stderr)
            return 1
        print(f"--check ok: {len(sheets)} validation sheets match generated output.")
        return 0

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for filename, payload in sheets.items():
        (OUTPUT_DIR / filename).write_text(_serialize(payload), encoding="utf-8")
    (OUTPUT_DIR / "README.md").write_text(readme, encoding="utf-8")
    _print_warnings(warnings)
    print(f"wrote {len(sheets)} validation sheets + README to {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
