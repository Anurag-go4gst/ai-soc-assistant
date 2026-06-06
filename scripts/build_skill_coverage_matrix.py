#!/usr/bin/env python3
"""Build the 105-question skill coverage matrix (master-control doc/eval artifact).

Slice S1a / work item B9 (+ BL-004 mapping layer) of the AI SOC master plan.
This is an OFFLINE, read-only generator. It MUST NOT import any ``app.*``
module and MUST NOT be importable by the runtime ``/chat`` path. It reads
JSON sources by explicit file path and emits a deterministic
``skill_coverage_matrix.json``:

  * ``backend/app/coverage/question_runtime_map_v1.json`` — the 105-question
    runtime map (one row per question; authoritative ``question_ref``,
    ``legacy_router_intent_hint``, ``proposed_primary_skill``, per-question
    ``mitre_registry`` ...).
  * ``backend/app/coverage/pattern_coverage_v1.json`` — the manifest of
    promoted/route-ready coverage rows; carries ``template_ref`` per
    ``question_ref``, used for deterministic question -> use_case derivation.
  * ``backend/app/use_cases/catalog.json`` — use cases + mitre_registry +
    ``default_spl_template`` (the equality key for derivation).
  * ``docs/skills/github_skill_intake_register.json`` — Track D GitHub intake
    decisions, keyed to internal use cases via ``internal_use_cases``.
  * ``docs/evals/question_use_case_map.json`` — BL-004 hand-curated
    ``question_ref -> use_case_id`` layer (precedence over auto-derivation).

Question -> use_case resolution (BL-004), in precedence order, never guessing
and never reconstructing the live router:
  1. ``curated_manual`` — an explicit entry in the curated map layer.
  2. ``mapped_from_existing_metadata`` — the manifest ``template_ref`` equals
     exactly one catalog ``default_spl_template`` (an explicit shared id, not
     routing logic).
  3. ``missing_authoritative_mapping`` — no defensible offline source; the
     row's ``use_case_id`` and use_case-gated columns
     (``github_reference_skill``, ``github_intake_decision``,
     ``evidence_requirements``) stay null, with a per-question warning.

Each row records ``mapping_status`` / ``mapping_source_file`` /
``mapping_confidence`` so the gap is auditable. Columns sourced directly from
the runtime entry (live/planning skill, mitre candidates, SPL template status)
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
MANIFEST_PATH = REPO_ROOT / "backend" / "app" / "coverage" / "pattern_coverage_v1.json"
CATALOG_PATH = REPO_ROOT / "backend" / "app" / "use_cases" / "catalog.json"
INTAKE_REGISTER_PATH = REPO_ROOT / "docs" / "skills" / "github_skill_intake_register.json"
CURATED_MAP_PATH = REPO_ROOT / "docs" / "evals" / "question_use_case_map.json"
OUTPUT_PATH = REPO_ROOT / "docs" / "evals" / "skill_coverage_matrix.json"

# Relative labels recorded in each row's ``mapping_source_file`` (stable across hosts).
_MANIFEST_SOURCE_LABEL = "backend/app/coverage/pattern_coverage_v1.json+backend/app/use_cases/catalog.json"
_CURATED_SOURCE_LABEL = "docs/evals/question_use_case_map.json"


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


def _index_manifest_template_by_question(manifest: Any, warnings: list[str]) -> dict[str, str]:
    """Return a ``question_ref -> template_ref`` index from the coverage manifest.

    Tolerates a missing/oddly-shaped manifest by returning an empty index and
    recording a warning rather than raising.
    """
    index: dict[str, str] = {}
    if not isinstance(manifest, dict):
        if manifest is not None:
            warnings.append("pattern_coverage_v1.json is not an object; manifest index empty")
        return index
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        warnings.append("pattern_coverage_v1.json missing an 'entries' list; manifest index empty")
        return index
    for record in entries:
        if not isinstance(record, dict):
            continue
        question_ref = record.get("question_ref")
        template_ref = record.get("template_ref")
        if isinstance(question_ref, str) and isinstance(template_ref, str) and template_ref:
            index[question_ref] = template_ref
    return index


def _index_template_to_use_case(catalog_index: dict[str, dict]) -> dict[str, list[str]]:
    """Return a ``default_spl_template -> [use_case_id]`` index from the catalog.

    Used to resolve a manifest ``template_ref`` to a use case only when the
    template maps to exactly one use case (otherwise the link is ambiguous and
    is not used).
    """
    index: dict[str, list[str]] = {}
    for use_case_id, record in catalog_index.items():
        template = record.get("default_spl_template")
        if isinstance(template, str) and template:
            index.setdefault(template, []).append(use_case_id)
    return index


def _load_curated_map(curated: Any, warnings: list[str]) -> dict[str, dict]:
    """Return a ``question_ref -> {use_case_id, mapping_confidence}`` curated index.

    Reads the hand-maintained BL-004 layer. Tolerates an absent/empty file
    (the common case today) by returning an empty index.
    """
    index: dict[str, dict] = {}
    if not isinstance(curated, dict):
        if curated is not None:
            warnings.append("question_use_case_map.json is not an object; curated layer ignored")
        return index
    mappings = curated.get("mappings")
    if not isinstance(mappings, dict):
        return index
    for question_ref, spec in mappings.items():
        if not isinstance(spec, dict):
            warnings.append(f"curated map: entry for {question_ref!r} is not an object; skipped")
            continue
        use_case_id = spec.get("use_case_id")
        if isinstance(use_case_id, str) and use_case_id:
            index[question_ref] = spec
        else:
            warnings.append(f"curated map: entry for {question_ref!r} has no use_case_id; skipped")
    return index


def _resolve_use_case_id(
    entry: dict,
    manifest_template_index: dict[str, str],
    template_to_use_case: dict[str, list[str]],
    curated_index: dict[str, dict],
) -> tuple[str | None, str, str | None, str | None]:
    """Resolve a deterministic ``use_case_id`` for a runtime-map question.

    Returns ``(use_case_id, mapping_status, mapping_source_file, mapping_confidence)``.
    Never guesses and never reconstructs the router. Precedence:
      1. curated manual entry -> ``curated_manual``
      2. manifest ``template_ref`` == exactly one catalog ``default_spl_template``
         -> ``mapped_from_existing_metadata``
      3. otherwise -> ``missing_authoritative_mapping`` (use_case_id None)
    """
    question_ref = entry.get("question_ref")

    curated = curated_index.get(question_ref) if isinstance(question_ref, str) else None
    if curated is not None:
        confidence = curated.get("mapping_confidence")
        confidence = confidence if isinstance(confidence, str) and confidence else "high"
        return curated["use_case_id"], "curated_manual", _CURATED_SOURCE_LABEL, confidence

    template_ref = manifest_template_index.get(question_ref) if isinstance(question_ref, str) else None
    if template_ref:
        use_case_ids = template_to_use_case.get(template_ref)
        if use_case_ids and len(use_case_ids) == 1:
            return use_case_ids[0], "mapped_from_existing_metadata", _MANIFEST_SOURCE_LABEL, "high"

    return None, "missing_authoritative_mapping", None, None


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
    # No use case: use the runtime entry's own authoritative per-question
    # registry candidate set (real signal for ~3/4 of rows), then the legacy
    # flat ``mitre_candidate`` field. Only the registry's ``candidate`` set is
    # used; ``permitted`` is deliberately excluded to avoid overclaiming.
    registry = entry.get("mitre_registry")
    if isinstance(registry, dict) and isinstance(registry.get("candidate"), list):
        registry_candidates = [tid for tid in registry["candidate"] if isinstance(tid, str)]
        if registry_candidates:
            return registry_candidates
    entry_candidates = entry.get("mitre_candidate")
    if isinstance(entry_candidates, list):
        return [tid for tid in entry_candidates if isinstance(tid, str)]
    return []


def _mitre_permitted_for(entry: dict) -> list[str]:
    """Return the runtime entry's registry-*permitted* MITRE techniques.

    In the question runtime map, ``mitre_registry.candidate`` is empty for every
    row; ``permitted`` carries the per-question MITRE signal (role
    ``metadata_not_evidence`` — registry-permitted, NOT evidence-confirmed and
    NOT a claim). Surfaced in its own column so coverage tracking sees it
    without conflating it with evidence-supported candidates.
    """
    registry = entry.get("mitre_registry")
    if isinstance(registry, dict) and isinstance(registry.get("permitted"), list):
        return [tid for tid in registry["permitted"] if isinstance(tid, str)]
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
    manifest_template_index: dict[str, str],
    template_to_use_case: dict[str, list[str]],
    curated_index: dict[str, dict],
    catalog_index: dict[str, dict],
    register_index: dict[str, list[dict]],
    warnings: list[str],
) -> list[dict]:
    """Build one coverage-matrix row per runtime-map question, sorted by question_id.

    Each row follows the D5/B8 column contract plus the BL-004 mapping-status
    columns. Use_case-gated fields are emitted as null (never guessed) when no
    defensible offline mapping exists, with a single per-question warning.
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

        use_case_id, mapping_status, mapping_source, mapping_confidence = _resolve_use_case_id(
            entry, manifest_template_index, template_to_use_case, curated_index
        )
        if use_case_id is None:
            warnings.append(
                f"{question_id}: {mapping_status}; use_case_id, github join, and "
                "evidence_requirements are null (curate via question_use_case_map.json)"
            )
        use_case = catalog_index.get(use_case_id) if use_case_id else None
        if use_case_id and use_case is None:
            warnings.append(
                f"{question_id}: mapped use_case_id '{use_case_id}' not found in catalog.json"
            )

        github_skills, github_decisions = _github_join(use_case_id, register_index)

        rows.append(
            {
                "question_id": question_id,
                "query": entry.get("question"),
                "use_case_id": use_case_id,
                "mapping_status": mapping_status,
                "mapping_source_file": mapping_source,
                "mapping_confidence": mapping_confidence,
                "live_execution_skill": entry.get("legacy_router_intent_hint"),
                "planning_or_analytic_skill": entry.get("proposed_primary_skill"),
                "github_reference_skill": github_skills,
                "github_intake_decision": github_decisions,
                "mitre_candidates": _mitre_candidates_for(entry, use_case),
                "mitre_permitted": _mitre_permitted_for(entry),
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
    manifest = _load_json(MANIFEST_PATH, warnings)
    catalog = _load_json(CATALOG_PATH, warnings)
    register = _load_json(INTAKE_REGISTER_PATH, warnings)
    curated = _load_json(CURATED_MAP_PATH, warnings)

    catalog_index = _index_catalog_by_use_case(catalog, warnings)
    register_index = _index_register_by_use_case(register, warnings)
    manifest_template_index = _index_manifest_template_by_question(manifest, warnings)
    template_to_use_case = _index_template_to_use_case(catalog_index)
    curated_index = _load_curated_map(curated, warnings)

    return build_rows(
        runtime_map,
        manifest_template_index,
        template_to_use_case,
        curated_index,
        catalog_index,
        register_index,
        warnings,
    )


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
