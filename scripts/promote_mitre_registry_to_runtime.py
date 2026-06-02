#!/usr/bin/env python3
"""Promote MITRE registry fields from COE DRAFT enrichment into runtime 105 + 42 JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.threat.mitre_registry_enrichment import (  # noqa: E402
    clear_mitre_enrichment_cache,
    load_mitre_enrichment_drafts,
    normalize_legacy_mitre_fields,
)
from app.threat.mitre_registry_schema import MitreRegistryMetadata  # noqa: E402

QUESTION_RUNTIME_PATH = REPO_ROOT / "backend/app/coverage/question_runtime_map_v1.json"
CATALOG_PATH = REPO_ROOT / "backend/app/use_cases/catalog.json"


def _registry_block_from_draft(draft_item: dict[str, Any], meta: MitreRegistryMetadata) -> dict[str, Any]:
    raw = draft_item.get("mitre_registry")
    block = dict(raw) if isinstance(raw, dict) else {}
    block["schema_version"] = meta.schema_version
    block["registry_role"] = meta.registry_role
    block["permitted"] = list(meta.mitre_permitted)
    block["candidate"] = list(meta.mitre_candidate)
    block["blocked"] = list(meta.mitre_blocked)
    block["requires_evidence"] = meta.mitre_requires_evidence
    block["requires_alert_context"] = meta.mitre_requires_alert_context
    block["answer_visibility_policy"] = meta.mitre_visibility_policy.value
    if meta.mapping_rationale:
        block["mapping_rationale"] = meta.mapping_rationale
    blocked_rationale = block.get("blocked_rationale")
    if isinstance(blocked_rationale, dict):
        block["blocked_rationale"] = blocked_rationale
    return block


def runtime_patch_for_draft_item(
    draft_item: dict[str, Any],
    *,
    question_ref: str | None,
    use_case_id: str | None,
) -> dict[str, Any]:
    meta = normalize_legacy_mitre_fields(
        draft_item,
        question_ref=question_ref,
        use_case_id=use_case_id,
    )
    registry = _registry_block_from_draft(draft_item, meta)
    patch: dict[str, Any] = {
        "mitre_registry": registry,
        "mitre_registry_schema_version": meta.schema_version,
        "mitre_requires_evidence": meta.mitre_requires_evidence,
        "mitre_requires_alert_context": meta.mitre_requires_alert_context,
        "mitre_visibility_policy": meta.mitre_visibility_policy.value,
    }
    if question_ref:
        patch["mitre_permitted"] = list(meta.mitre_permitted)
        patch["mitre_candidate"] = list(meta.mitre_candidate)
        patch["mitre_blocked"] = list(meta.mitre_blocked)
        overlap = draft_item.get("kb_references")
        if isinstance(overlap, dict):
            kb_overlap = overlap.get("mitre_runtime_kb_overlap")
            if isinstance(kb_overlap, list):
                patch["mitre_runtime_kb_overlap"] = [str(x).upper() for x in kb_overlap if x]
                patch["mitre_runtime_kb_match_count"] = len(patch["mitre_runtime_kb_overlap"])
    if use_case_id:
        patch["mitre_candidates"] = list(meta.mitre_candidate) or list(meta.mitre_permitted)
        if meta.mitre_permitted:
            patch["mitre_permitted"] = list(meta.mitre_permitted)
        patch["mitre_blocked"] = list(meta.mitre_blocked)
    return patch


def promote_questions(*, dry_run: bool) -> tuple[int, int, list[str]]:
    drafts = load_mitre_enrichment_drafts()
    payload = json.loads(QUESTION_RUNTIME_PATH.read_text(encoding="utf-8"))
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError("question_runtime_map_v1.json must contain entries[]")
    by_ref = {str(row["question_ref"]): row for row in entries if isinstance(row, dict) and row.get("question_ref")}
    updated = 0
    missing: list[str] = []
    for question_ref, draft_item in sorted(drafts["questions_by_id"].items()):
        entry = by_ref.get(question_ref)
        if entry is None:
            missing.append(question_ref)
            continue
        entry.update(runtime_patch_for_draft_item(draft_item, question_ref=question_ref, use_case_id=None))
        updated += 1
    if not dry_run:
        QUESTION_RUNTIME_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return updated, len(entries), missing


def promote_use_cases(*, dry_run: bool) -> tuple[int, int, list[str]]:
    drafts = load_mitre_enrichment_drafts()
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    use_cases = payload.get("use_cases")
    if not isinstance(use_cases, list):
        raise ValueError("catalog.json must contain use_cases[]")
    by_id = {str(row["use_case_id"]): row for row in use_cases if isinstance(row, dict) and row.get("use_case_id")}
    updated = 0
    missing: list[str] = []
    for use_case_id, draft_item in sorted(drafts["use_cases_by_id"].items()):
        row = by_id.get(use_case_id)
        if row is None:
            missing.append(use_case_id)
            continue
        row.update(runtime_patch_for_draft_item(draft_item, question_ref=None, use_case_id=use_case_id))
        updated += 1
    if not dry_run:
        CATALOG_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return updated, len(use_cases), missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report counts without writing JSON files")
    args = parser.parse_args()

    q_updated, q_total, q_missing = promote_questions(dry_run=args.dry_run)
    u_updated, u_total, u_missing = promote_use_cases(dry_run=args.dry_run)
    clear_mitre_enrichment_cache()

    mode = "dry-run" if args.dry_run else "written"
    print(f"MITRE registry promote ({mode}): questions {q_updated}/{q_total}, use_cases {u_updated}/{u_total}")
    if q_missing:
        print(f"warning: {len(q_missing)} draft question id(s) missing from runtime map: {q_missing[:5]}")
    if u_missing:
        print(f"warning: {len(u_missing)} draft use_case id(s) missing from catalog: {u_missing[:5]}")
    return 0 if not q_missing and not u_missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
