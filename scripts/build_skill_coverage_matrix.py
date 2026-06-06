#!/usr/bin/env python3
"""Build the 105-question skill coverage matrix (master-control doc/eval artifact).

Slice S1a / work item B9 of the AI SOC master plan. This is an OFFLINE,
read-only generator. It MUST NOT import any ``app.*`` module and MUST NOT be
importable by the runtime ``/chat`` path. It reads three JSON sources by
explicit file path and emits a deterministic ``skill_coverage_matrix.json``:

  * ``backend/app/coverage/question_runtime_map_v1.json`` — the 105-question
    runtime map (one row per question; authoritative ``question_ref``,
    ``legacy_router_intent_hint``, ``proposed_primary_skill`` ...).
  * ``backend/app/use_cases/catalog.json`` — use cases + mitre_registry +
    templates (joined only when a deterministic ``use_case_id`` link exists).
  * ``docs/skills/github_skill_intake_register.json`` — Track D GitHub intake
    decisions, keyed to internal use cases via ``internal_use_cases``.

Known data gap (reported, not hidden): the repo carries NO precomputed,
non-router question -> use_case mapping. Resolving it at runtime is the
router's job, which lives under ``app.*`` and is out of bounds here. Per the
D5/B8 spec ("joined ... where a mapping exists, else null"), every row's
``use_case_id`` is therefore null, and the use-case-gated columns
(``github_reference_skill``, ``github_intake_decision``, ``evidence_requirements``)
are null with a per-question warning. Columns sourced directly from the
runtime entry (live/planning skill, mitre candidates, SPL template status)
carry real signal across all rows.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Repo root is two levels up from this file: <repo>/scripts/<this>.
REPO_ROOT = Path(__file__).resolve().parents[1]

RUNTIME_MAP_PATH = REPO_ROOT / "backend" / "app" / "coverage" / "question_runtime_map_v1.json"
CATALOG_PATH = REPO_ROOT / "backend" / "app" / "use_cases" / "catalog.json"
INTAKE_REGISTER_PATH = REPO_ROOT / "docs" / "skills" / "github_skill_intake_register.json"
OUTPUT_PATH = REPO_ROOT / "docs" / "evals" / "skill_coverage_matrix.json"


def _load_json(path: Path, warnings: list[str]) -> Any:
    """Load JSON from ``path``; on any read/parse failure append a warning and return None.

    Never raises on a missing or malformed source — the generator must still
    emit a structurally valid matrix (with nulls) so CI row-count checks hold.
    """
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        warnings.append(f"source file missing: {path}")
        return None
    except (json.JSONDecodeError, OSError) as exc:
        warnings.append(f"could not read source {path}: {exc}")
        return None


def _index_catalog_by_use_case(catalog: Any, warnings: list[str]) -> dict[str, dict]:
    """Return a ``use_case_id -> use_case record`` index from the catalog payload.

    Tolerates a missing/oddly-shaped catalog by returning an empty index and
    recording a warning rather than raising.
    """
    index: dict[str, dict] = {}
    if not isinstance(catalog, dict):
        if catalog is not None:
            warnings.append("catalog.json is not an object; use-case index empty")
        return index
    use_cases = catalog.get("use_cases")
    if not isinstance(use_cases, list):
        warnings.append("catalog.json missing a 'use_cases' list; use-case index empty")
        return index
    for record in use_cases:
        if not isinstance(record, dict):
            continue
        use_case_id = record.get("use_case_id")
        if isinstance(use_case_id, str) and use_case_id:
            index[use_case_id] = record
    return index


def _index_register_by_use_case(register: Any, warnings: list[str]) -> dict[str, list[dict]]:
    """Return a ``use_case_id -> [intake records]`` index from the intake register.

    The register links GitHub skills to internal use cases through each
    record's ``internal_use_cases`` list, so a single use case may carry
    several GitHub references.
    """
    index: dict[str, list[dict]] = {}
    if not isinstance(register, dict):
        if register is not None:
            warnings.append("intake register is not an object; github join index empty")
        return index
    records = register.get("records")
    if not isinstance(records, list):
        warnings.append("intake register missing a 'records' list; github join index empty")
        return index
    for record in records:
        if not isinstance(record, dict):
            continue
        for use_case_id in record.get("internal_use_cases") or []:
            if isinstance(use_case_id, str) and use_case_id:
                index.setdefault(use_case_id, []).append(record)
    return index


def _resolve_use_case_id(entry: dict) -> str | None:
    """Resolve a deterministic ``use_case_id`` for a runtime-map question, or None.

    No allowed source carries a precomputed, non-router question -> use_case
    key, and reconstructing the router is out of scope, so this always returns
    None today. It is isolated as a single seam so a future precomputed map can
    populate it without touching the rest of the generator.
    """
    return None


def _derive_spl_template_status(entry: dict) -> str:
    """Derive an SPL-template availability label from the runtime-map entry alone.

    Uses the entry's own promotion/readiness mirror (not a 4th source file):
      * ``in_manifest`` with a concrete ``manifest_readiness`` -> ``active``
      * ``in_manifest`` without readiness -> ``planned``
      * otherwise (``not_in_manifest`` etc.) -> ``unavailable``
    """
    promotion_status = entry.get("promotion_status")
    readiness = entry.get("manifest_readiness")
    if promotion_status == "in_manifest":
        return "active" if readiness else "planned"
    return "unavailable"


def _evidence_requirements_for(use_case: dict | None) -> dict | None:
    """Build an evidence-requirements block from a resolved catalog use case, or None.

    Requires a resolved ``use_case`` (entities + sources live only in the
    catalog). Returns None when the use case is unresolved, consistent with the
    use_case-gated null policy.
    """
    if not isinstance(use_case, dict):
        return None
    return {
        "required_entities": list(use_case.get("required_entities") or []),
        "optional_entities": list(use_case.get("optional_entities") or []),
        "required_sources": list(use_case.get("required_sources") or []),
        "optional_sources": list(use_case.get("optional_sources") or []),
    }


def _mitre_candidates_for(entry: dict, use_case: dict | None) -> list[str]:
    """Return MITRE candidate technique ids for a row.

    Prefers the resolved use-case ``mitre_registry`` candidates (per D5 spec);
    falls back to the runtime entry's own ``mitre_candidate`` so real
    per-question data is not discarded when the use case is unresolved.
    """
    if isinstance(use_case, dict):
        registry = use_case.get("mitre_registry")
        if isinstance(registry, dict) and isinstance(registry.get("candidate"), list):
            return [tid for tid in registry["candidate"] if isinstance(tid, str)]
        candidates = use_case.get("mitre_candidates")
        if isinstance(candidates, list):
            return [tid for tid in candidates if isinstance(tid, str)]
    entry_candidates = entry.get("mitre_candidate")
    if isinstance(entry_candidates, list):
        return [tid for tid in entry_candidates if isinstance(tid, str)]
    return []


def _github_join(
    use_case_id: str | None,
    register_index: dict[str, list[dict]],
) -> tuple[list[str] | None, list[str] | None]:
    """Join the intake register by ``use_case_id``.

    Returns ``(github_reference_skills, github_intake_decisions)`` as sorted
    lists, or ``(None, None)`` when there is no use case to join on or no
    matching register record.
    """
    if not use_case_id:
        return None, None
    records = register_index.get(use_case_id)
    if not records:
        return None, None
    skill_ids = sorted(
        {r["github_skill_id"] for r in records if isinstance(r.get("github_skill_id"), str)}
    )
    decisions = sorted(
        {r["decision"] for r in records if isinstance(r.get("decision"), str)}
    )
    return (skill_ids or None), (decisions or None)


def build_rows(
    runtime_map: Any,
    catalog_index: dict[str, dict],
    register_index: dict[str, list[dict]],
    warnings: list[str],
) -> list[dict]:
    """Build one coverage-matrix row per runtime-map question, sorted by question_id.

    Each row follows the D5/B8 column contract. Unresolvable, use_case-gated
    fields are emitted as null with a per-question warning rather than guessed.
    """
    rows: list[dict] = []
    if not isinstance(runtime_map, dict):
        warnings.append("runtime map is not an object; emitting zero rows")
        return rows
    entries = runtime_map.get("entries")
    if not isinstance(entries, list):
        warnings.append("runtime map missing an 'entries' list; emitting zero rows")
        return rows

    for entry in entries:
        if not isinstance(entry, dict):
            warnings.append("skipping non-object runtime entry")
            continue
        question_id = entry.get("question_ref")
        if not isinstance(question_id, str) or not question_id:
            warnings.append("skipping runtime entry with missing question_ref")
            continue

        use_case_id = _resolve_use_case_id(entry)
        if use_case_id is None:
            warnings.append(
                f"{question_id}: no deterministic use_case mapping in allowed sources; "
                "use_case_id, github join, and evidence_requirements are null"
            )
        use_case = catalog_index.get(use_case_id) if use_case_id else None
        if use_case_id and use_case is None:
            warnings.append(
                f"{question_id}: use_case_id '{use_case_id}' not found in catalog.json"
            )

        github_skills, github_decisions = _github_join(use_case_id, register_index)

        rows.append(
            {
                "question_id": question_id,
                "query": entry.get("question"),
                "use_case_id": use_case_id,
                "live_execution_skill": entry.get("legacy_router_intent_hint"),
                "planning_or_analytic_skill": entry.get("proposed_primary_skill"),
                "github_reference_skill": github_skills,
                "github_intake_decision": github_decisions,
                "mitre_candidates": _mitre_candidates_for(entry, use_case),
                "spl_template_status": _derive_spl_template_status(entry),
                "evidence_requirements": _evidence_requirements_for(use_case),
                "implementation_status": "not_started",
                "test_status": "unknown",
            }
        )

    rows.sort(key=lambda row: row["question_id"])
    return rows


def generate_matrix(warnings: list[str]) -> list[dict]:
    """Load all sources and return the full sorted coverage matrix (list of rows)."""
    runtime_map = _load_json(RUNTIME_MAP_PATH, warnings)
    catalog = _load_json(CATALOG_PATH, warnings)
    register = _load_json(INTAKE_REGISTER_PATH, warnings)

    catalog_index = _index_catalog_by_use_case(catalog, warnings)
    register_index = _index_register_by_use_case(register, warnings)
    return build_rows(runtime_map, catalog_index, register_index, warnings)


def _serialize(rows: list[dict]) -> str:
    """Serialize rows to stable JSON (sorted keys, indent=2, trailing newline)."""
    return json.dumps(rows, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _print_warnings(warnings: list[str]) -> None:
    """Print collected warnings to stderr (never silently swallowed)."""
    if not warnings:
        return
    print(f"warnings ({len(warnings)}):", file=sys.stderr)
    for line in warnings:
        print(f"  WARN: {line}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Default run writes the matrix; ``--check`` diffs without writing."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Regenerate in memory and diff against the on-disk file; exit 1 if they differ.",
    )
    args = parser.parse_args(argv)

    warnings: list[str] = []
    rows = generate_matrix(warnings)
    rendered = _serialize(rows)

    if args.check:
        try:
            existing = OUTPUT_PATH.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError) as exc:
            _print_warnings(warnings)
            print(f"--check failed: cannot read {OUTPUT_PATH}: {exc}", file=sys.stderr)
            return 1
        _print_warnings(warnings)
        if existing != rendered:
            print(
                f"--check failed: {OUTPUT_PATH} is stale; "
                "re-run the generator without --check to refresh it.",
                file=sys.stderr,
            )
            return 1
        print(f"--check ok: {OUTPUT_PATH} matches generated output ({len(rows)} rows).")
        return 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(rendered, encoding="utf-8")
    _print_warnings(warnings)
    print(f"wrote {OUTPUT_PATH} ({len(rows)} rows).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
