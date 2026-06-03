"""P5-6 report-first: build mitre_permitted[] per 105+ registry row."""

from __future__ import annotations

import re
from typing import Any

from registries import REPO_ROOT

_MITRE_ID_RE = re.compile(r"\bT\d{4}(?:\.\d{3})?\b", re.IGNORECASE)
_TAXONOMY_TABLE_ROW = re.compile(r"^\|\s*(\d+)\s*\|(.+)\|\s*$", re.MULTILINE)
# Index within match.group(2).split("|") — column suggested_MITRE_candidates (after #).
_MITRE_COLUMN_INDEX = 10


def parse_mitre_ids_from_cell(cell: str) -> list[str]:
    """Extract ATT&CK technique IDs from a taxonomy table cell."""
    normalized = cell.strip()
    if not normalized:
        return []
    seen: set[str] = set()
    ordered: list[str] = []
    for match in _MITRE_ID_RE.finditer(normalized):
        tid = match.group(0).upper()
        if tid not in seen:
            seen.add(tid)
            ordered.append(tid)
    return ordered


def load_taxonomy_mitre_by_ref(taxonomy_path: Any | None = None) -> dict[str, list[str]]:
    from pathlib import Path

    from taxonomy_lookup import TAXONOMY_PATH

    path = Path(taxonomy_path) if taxonomy_path is not None else TAXONOMY_PATH
    content = path.read_text(encoding="utf-8")
    by_ref: dict[str, list[str]] = {}
    for match in _TAXONOMY_TABLE_ROW.finditer(content):
        number = int(match.group(1))
        cells = [part.strip() for part in match.group(2).split("|")]
        if len(cells) <= _MITRE_COLUMN_INDEX:
            continue
        ref = f"q0.q{number:03d}"
        by_ref[ref] = parse_mitre_ids_from_cell(cells[_MITRE_COLUMN_INDEX])
    return by_ref


def _runtime_kb_technique_ids() -> frozenset[str]:
    import json
    from pathlib import Path

    kb_path = REPO_ROOT / "backend" / "app" / "threat" / "mitre_attack_subset.json"
    payload = json.loads(kb_path.read_text(encoding="utf-8"))
    return frozenset(
        str(item.get("technique_id", "")).upper()
        for item in (payload.get("techniques") or [])
        if item.get("technique_id")
    )


def build_mitre_permitted_for_row(
    *,
    question_ref: str,
    taxonomy_mitre: list[str],
    use_case_mitre: list[str] | None = None,
) -> dict[str, Any]:
    """Merge taxonomy + optional use-case MITRE; tag KB overlap (report-first)."""
    kb_ids = _runtime_kb_technique_ids()
    merged: list[str] = []
    seen: set[str] = set()
    sources: list[str] = []

    for tid in taxonomy_mitre:
        if tid not in seen:
            seen.add(tid)
            merged.append(tid)
    if taxonomy_mitre:
        sources.append("taxonomy_suggested_MITRE_candidates")

    for tid in use_case_mitre or []:
        upper = tid.upper()
        if upper not in seen:
            seen.add(upper)
            merged.append(upper)
    if use_case_mitre:
        sources.append("use_case_catalog_mitre_candidates")

    in_kb = [tid for tid in merged if tid in kb_ids]
    return {
        "mitre_permitted": merged,
        "mitre_permitted_sources": sources,
        "mitre_runtime_kb_overlap": in_kb,
        "mitre_runtime_kb_match_count": len(in_kb),
    }


def use_case_mitre_for_question_ref(question_ref: str) -> list[str]:
    """Best-effort catalog MITRE via manifest / use-case keyword overlap (author-time)."""
    import json
    from pathlib import Path

    manifest_path = REPO_ROOT / "backend" / "app" / "coverage" / "pattern_coverage_v1.json"
    catalog_path = REPO_ROOT / "backend" / "app" / "use_cases" / "catalog.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    use_cases_by_id = {str(u["use_case_id"]): u for u in catalog.get("use_cases", [])}

    for entry in manifest.get("entries", []):
        if str(entry.get("question_ref", "")).lower() != question_ref.lower():
            continue
        uc_id = entry.get("use_case_id") or entry.get("linked_use_case_id")
        if isinstance(uc_id, str) and uc_id in use_cases_by_id:
            raw = use_cases_by_id[uc_id].get("mitre_candidates") or []
            return [str(item).upper() for item in raw if item]
    return []
