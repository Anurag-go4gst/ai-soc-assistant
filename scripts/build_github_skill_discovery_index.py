#!/usr/bin/env python3
"""Build the GitHub skill discovery index (Phase 0B offline artifact).

Scans a local reference clone for skills/**/SKILL.md, extracts metadata only,
and merges intake-register decisions. Never copies raw SKILL.md bodies.
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
    DEFAULT_CLONE_ROOT,
    GITHUB_ACCEPTANCE_NOTE,
    duplicate_of_existing,
    extract_mitre_attack,
    extract_title,
    infer_domain_subdomain,
    infer_tags,
    intake_by_skill_id,
    likely_internal_domain,
    likely_soc_relevance,
    load_intake_register,
    parse_frontmatter,
    relative_skill_path,
    resolve_clone_root,
    scan_skill_files,
    skill_id_from_path,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = REPO_ROOT / "docs" / "skills" / "github_skill_discovery_index.json"
SCHEMA_VERSION = "2026-06-07-phase0b-v1"


def build_skill_row(
    skill_path: Path,
    clone_root: Path,
    intake_index: dict[str, dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    github_skill_id = skill_id_from_path(skill_path, clone_root)
    try:
        text = skill_path.read_text(encoding="utf-8")
    except OSError as exc:
        warnings.append(f"could not read {skill_path}: {exc}")
        return {
            "github_skill_id": github_skill_id,
            "path": relative_skill_path(skill_path, clone_root),
            "title": github_skill_id,
            "domain": None,
            "subdomain": None,
            "tags": [],
            "mitre_attack": [],
            "likely_soc_relevance": "unknown",
            "likely_internal_domain": "soc-operations",
            "review_status": "scan_error",
            "decision": None,
            "priority": None,
            "duplicate_of_existing": None,
            "notes": f"scan_error: {exc}",
        }

    # Metadata only — never persist body text.
    metadata = parse_frontmatter(text)
    domain, subdomain = infer_domain_subdomain(metadata, github_skill_id)
    intake = intake_index.get(github_skill_id)
    review_status = (
        intake.get("review_status") if intake else "discovered_unreviewed"
    )
    decision = intake.get("decision") if intake else None
    priority = intake.get("priority") if intake else None
    notes = intake.get("notes") if intake else None
    if intake and intake.get("decision") == "accept":
        notes = (
            (notes or "")
            + (" " if notes else "")
            + GITHUB_ACCEPTANCE_NOTE
        ).strip()

    return {
        "github_skill_id": github_skill_id,
        "path": relative_skill_path(skill_path, clone_root),
        "title": extract_title(text, github_skill_id),
        "domain": intake.get("domain") if intake and intake.get("domain") else domain,
        "subdomain": intake.get("subdomain") if intake and intake.get("subdomain") else subdomain,
        "tags": infer_tags(metadata, github_skill_id),
        "mitre_attack": extract_mitre_attack(metadata, text),
        "likely_soc_relevance": likely_soc_relevance(metadata, text),
        "likely_internal_domain": likely_internal_domain(metadata, github_skill_id),
        "review_status": review_status,
        "decision": decision,
        "priority": priority,
        "duplicate_of_existing": duplicate_of_existing(github_skill_id, intake_index),
        "notes": notes,
    }


def build_discovery_index(
    clone_root: Path,
    warnings: list[str],
) -> dict[str, Any]:
    register = load_intake_register(warnings)
    intake_index = intake_by_skill_id(register)
    skill_paths = scan_skill_files(clone_root)
    if not skill_paths:
        warnings.append(f"no SKILL.md files found under {clone_root}")

    skills = [
        build_skill_row(path, clone_root, intake_index, warnings)
        for path in skill_paths
    ]
    skills.sort(key=lambda row: row["github_skill_id"])

    discovered_ids = {row["github_skill_id"] for row in skills}
    for skill_id, record in sorted(intake_index.items()):
        if skill_id not in discovered_ids:
            warnings.append(
                f"intake register skill {skill_id!r} not found in clone scan; "
                "emitting register-only overlay row"
            )
            skills.append(
                {
                    "github_skill_id": skill_id,
                    "path": record.get("path"),
                    "title": skill_id.replace("-", " ").title(),
                    "domain": record.get("domain"),
                    "subdomain": record.get("subdomain"),
                    "tags": [],
                    "mitre_attack": list(record.get("mitre_from_github") or []),
                    "likely_soc_relevance": "high",
                    "likely_internal_domain": record.get("domain") or "soc-operations",
                    "review_status": record.get("review_status"),
                    "decision": record.get("decision"),
                    "priority": record.get("priority"),
                    "duplicate_of_existing": skill_id,
                    "notes": (record.get("notes") or "") + " register_only_overlay",
                }
            )
    skills.sort(key=lambda row: row["github_skill_id"])

    accepted = sum(1 for row in skills if row.get("decision") == "accept")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "clone_root_used": str(clone_root),
        "source_repo_name": register.get("repo") or "mukul975/Anthropic-Cybersecurity-Skills",
        "row_counts": {
            "skills": len(skills),
            "accepted_for_enrichment": accepted,
            "discovered_unreviewed": sum(
                1 for row in skills if row.get("review_status") == "discovered_unreviewed"
            ),
            "intake_register_records": len(intake_index),
        },
        "usage_note": GITHUB_ACCEPTANCE_NOTE,
        "skills": skills,
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
    parser.add_argument(
        "--fixture-root",
        type=Path,
        help="Use a temporary fixture clone root (required for tests).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Diff generated output against the committed artifact.",
    )
    args = parser.parse_args(argv)

    warnings: list[str] = []
    try:
        clone_root = resolve_clone_root(fixture_root=args.fixture_root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    payload = build_discovery_index(clone_root, warnings)
    rendered = _serialize(payload)

    if args.check:
        try:
            existing = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
            print(f"--check failed: {exc}", file=sys.stderr)
            return 1
        if _check_payload(existing) != _check_payload(payload):
            print(f"--check failed: {OUTPUT_PATH} is stale", file=sys.stderr)
            return 1
        print(f"--check ok: {OUTPUT_PATH} ({payload['row_counts']['skills']} skills)")
        return 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(rendered, encoding="utf-8")
    if warnings:
        print(f"warnings ({len(warnings)}):", file=sys.stderr)
        for line in warnings[:20]:
            print(f"  WARN: {line}", file=sys.stderr)
        if len(warnings) > 20:
            print(f"  ... {len(warnings) - 20} more", file=sys.stderr)
    print(
        f"wrote {OUTPUT_PATH} "
        f"({payload['row_counts']['skills']} skills, "
        f"{payload['row_counts']['accepted_for_enrichment']} accepted_for_enrichment)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
