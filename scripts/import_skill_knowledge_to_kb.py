#!/usr/bin/env python3
"""Import curated skill-enrichment knowledge into the governed SOC-KB (T2.2).

Generates one SOP document + sectioned entries per record in
backend/app/use_cases/content_enrichment.json and merges them into the
SOC-KB fixtures (documents/entries). Deterministic and idempotent: existing
`skill-enrich-*` rows are replaced wholesale; `--check` exits 1 on drift.

Provenance policy: GitHub/internal origin is recorded as clean tags
(`source:github_skill_intake` / `source:internal_curated`) — never URLs or
SKILL.md paths, so generated content can never trip the answer composer's
provenance-marker guard. Full provenance stays in docs/skills/*.

Usage:
  PYTHONPATH=backend:. python3 scripts/import_skill_knowledge_to_kb.py          # write
  PYTHONPATH=backend:. python3 scripts/import_skill_knowledge_to_kb.py --check  # drift gate
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
ENRICHMENT_PATH = REPO_ROOT / "backend" / "app" / "use_cases" / "content_enrichment.json"
DOCS_PATH = REPO_ROOT / "backend" / "app" / "knowledge" / "fixtures" / "soc_kb_documents.json"
ENTRIES_PATH = REPO_ROOT / "backend" / "app" / "knowledge" / "fixtures" / "soc_kb_entries.json"

DOC_PREFIX = "skill-enrich-"
FIXED_TIMESTAMP = "2026-06-11T00:00:00Z"
FORBIDDEN_MARKERS = ("skill.md", "github.com", "/skills/", "github_ref:")


def _doc_for(record: dict[str, Any]) -> dict[str, Any]:
    use_case = record["use_case_id"]
    origin = "source:github_skill_intake" if record.get("github_reference_skills") else "source:internal_curated"
    return {
        "doc_id": f"{DOC_PREFIX}{use_case}-v1",
        "collection_id": "soc_sop",
        "title": f"Skill enrichment guidance: {use_case.replace('_', ' ')}",
        "document_type": "sop",
        "namespace": str(record.get("subdomain") or record.get("domain") or "soc"),
        "domain": str(record.get("domain") or "soc"),
        "environment": "coe",
        "version": "1.0",
        "revision": "1",
        "status": "published",
        "approval_status": "coe_reviewed",
        "lifecycle_stage": "published",
        "allowed_use": ["hil_guidance", "synthesis_context"],
        "applies_to_skills": sorted(
            {str(record.get("live_execution_skill") or "attack_discovery"), "knowledge_recall"}
        ),
        "risk_level": "medium",
        "sensitivity": "internal",
        "tags": sorted({*map(str, record.get("tags") or []), use_case, origin}),
        "owner": "SOC skill enrichment",
        "uploaded_by": "skill_enrichment_importer",
        "reviewed_by": "anurag",
        "approved_by": "anurag",
        "created_at": FIXED_TIMESTAMP,
        "updated_at": FIXED_TIMESTAMP,
        "is_current_version": True,
    }


def _entries_for(record: dict[str, Any]) -> list[dict[str, Any]]:
    use_case = record["use_case_id"]
    doc_id = f"{DOC_PREFIX}{use_case}-v1"
    phrase = use_case.replace("_", " ")
    tag_phrases = [str(tag).replace("_", " ") for tag in record.get("tags") or []]
    hints = sorted({*tag_phrases, phrase} - {"splunk"})
    synonyms = sorted({phrase, *tag_phrases})
    # Knowledge-channel content: scoped away from attack_discovery so live
    # investigations keep preferring COE SOPs and splunk-context entries
    # (wrong-skill penalty handles the ranking).
    expected_skills = ["alert_summary", "knowledge_recall"]
    citation_base = f"Skill enrichment {use_case} v1"
    sections: list[tuple[str, str, str, list[str]]] = []
    if record.get("analyst_checklist"):
        sections.append(("CHECKLIST", "Analyst checklist", "procedure", record["analyst_checklist"]))
    if record.get("investigation_workflow"):
        sections.append(("WORKFLOW", "Investigation workflow", "procedure", record["investigation_workflow"]))
    if record.get("limitations"):
        sections.append(("LIMITS", "Limitations and non-claims", "constraint", record["limitations"]))
    if record.get("answer_rules"):
        sections.append(("RULES", "Answer rules", "rule", record["answer_rules"]))

    entries = []
    for section_id, section_title, entry_type, items in sections:
        entries.append(
            {
                "entry_id": f"{DOC_PREFIX}{use_case}-{section_id.lower()}",
                "doc_id": doc_id,
                "doc_version": "1.0",
                "collection_id": "soc_sop",
                "title": f"{section_title}: {use_case.replace('_', ' ')}",
                "section_id": f"{use_case.upper()}-{section_id}",
                "section_title": section_title,
                "entry_type": entry_type,
                "source_excerpt": " ".join(str(item) for item in items)[:900],
                "source_refs": [f"content_enrichment.json#{use_case}.{section_id.lower()}"],
                "citation": f"{citation_base} {section_id}",
                "retrieval_hints": hints,
                "synonyms": synonyms,
                "positive_examples": [str(items[0])[:200]] if items else [],
                "negative_examples": [],
                "tags": sorted({*tag_phrases, phrase}),
                "allowed_use": ["hil_guidance", "synthesis_context"],
                "expected_skills": expected_skills,
                # mitre ids stay in excerpt text only — a mitre_refs field outbids the
                # COE SOP entries on technique-id queries (metadata, not evidence).
                "mitre_refs": [],
                "risk_level": "medium",
                "sensitivity": "internal",
                # Supplementary tier: curated COE SOPs outrank skill-enrichment
                # guidance on shared topics (prevents retrieval ambiguity ties).
                "confidence_weight": 0.6,
                "status": "published",
                "approval_status": "coe_reviewed",
            }
        )
    return entries


def build_payloads() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records = json.loads(ENRICHMENT_PATH.read_text(encoding="utf-8"))["records"]
    docs, entries = [], []
    for use_case in sorted(records):
        record = {**records[use_case], "use_case_id": records[use_case].get("use_case_id") or use_case}
        if not record.get("analyst_checklist") and not record.get("investigation_workflow"):
            continue
        docs.append(_doc_for(record))
        entries.extend(_entries_for(record))
    serialized = json.dumps([docs, entries]).lower()
    for marker in FORBIDDEN_MARKERS:
        if marker in serialized:
            raise SystemExit(f"generated KB content contains forbidden marker {marker!r}")
    return docs, entries


def _merge(existing: list[dict[str, Any]], generated: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    kept = [item for item in existing if not str(item.get(key, "")).startswith(DOC_PREFIX)]
    return kept + generated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    docs, entries = build_payloads()
    current_docs = json.loads(DOCS_PATH.read_text(encoding="utf-8"))
    current_entries = json.loads(ENTRIES_PATH.read_text(encoding="utf-8"))
    merged_docs = _merge(current_docs, docs, "doc_id")
    merged_entries = _merge(current_entries, entries, "entry_id")

    rendered_docs = json.dumps(merged_docs, indent=1, ensure_ascii=False) + "\n"
    rendered_entries = json.dumps(merged_entries, indent=1, ensure_ascii=False) + "\n"

    if args.check:
        if (
            DOCS_PATH.read_text(encoding="utf-8") != rendered_docs
            or ENTRIES_PATH.read_text(encoding="utf-8") != rendered_entries
        ):
            print("RESULT: FAIL (skill knowledge KB fixtures drifted)")
            return 1
        print(f"RESULT: PASS ({len(docs)} docs, {len(entries)} entries, no drift)")
        return 0

    DOCS_PATH.write_text(rendered_docs, encoding="utf-8")
    ENTRIES_PATH.write_text(rendered_entries, encoding="utf-8")
    print(f"RESULT: PASS (wrote {len(docs)} docs, {len(entries)} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
