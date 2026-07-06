#!/usr/bin/env python3
"""Import ATLAS case-study and mitigation narratives into governed SOC-KB fixtures."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = REPO_ROOT / "docs" / "threat-intel" / "atlas" / "raw" / "atlas_nodes_2026_04.csv"
DOCS_PATH = REPO_ROOT / "backend" / "app" / "knowledge" / "fixtures" / "soc_kb_documents.json"
ENTRIES_PATH = REPO_ROOT / "backend" / "app" / "knowledge" / "fixtures" / "soc_kb_entries.json"
DOC_PREFIX = "atlas-"
FIXED_TIMESTAMP = "2026-07-06T00:00:00Z"


def _load_rows() -> list[dict[str, str]]:
    with CSV_PATH.open(encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _build_payload() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    documents: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    for row in _load_rows():
        entity = str(row.get("entity") or "").strip()
        if entity not in {"casestudy", "mitigation"}:
            continue
        node_id = str(row.get("id") or "").strip()
        name = str(row.get("name") or node_id).strip()
        description = str(row.get("description") or row.get("text") or "").strip()
        if not node_id or not description:
            continue
        doc_id = f"{DOC_PREFIX}{node_id.lower()}-v1"
        slug = node_id.lower().replace(".", "-")
        documents.append(
            {
                "doc_id": doc_id,
                "collection_id": "mitre_atlas",
                "title": f"MITRE ATLAS {entity}: {name}",
                "document_type": "other",
                "namespace": "threat-intel",
                "domain": "ai-security",
                "environment": "coe",
                "version": "1.0",
                "revision": "1",
                "status": "published",
                "approval_status": "coe_reviewed",
                "lifecycle_stage": "published",
                "allowed_use": ["hil_guidance", "synthesis_context"],
                "applies_to_skills": ["knowledge_recall", "guided_investigation", "attack_discovery"],
                "risk_level": "low",
                "sensitivity": "internal",
                "tags": sorted({"mitre_atlas", entity, "source:mitre_atlas", slug}),
                "owner": "ATLAS narrative importer",
                "uploaded_by": "atlas_narrative_importer",
                "reviewed_by": "anurag",
                "approved_by": "anurag",
                "created_at": FIXED_TIMESTAMP,
                "updated_at": FIXED_TIMESTAMP,
                "is_current_version": True,
            }
        )
        entries.append(
            {
                "entry_id": f"{DOC_PREFIX}{slug}-narrative",
                "doc_id": doc_id,
                "doc_version": "1.0",
                "collection_id": "mitre_atlas",
                "title": f"ATLAS {entity}: {name}",
                "section_id": node_id,
                "section_title": name,
                "entry_type": "reference",
                "source_excerpt": description[:900],
                "source_refs": [f"atlas_nodes_2026_04.csv#{node_id}"],
                "citation": f"MITRE ATLAS {node_id}",
                "retrieval_hints": [entity, "mitre atlas", name.lower(), node_id.lower()],
                "synonyms": [name, node_id],
                "positive_examples": [f"{entity} {name}"],
                "negative_examples": [],
                "tags": sorted({"mitre_atlas", entity, slug}),
                "allowed_use": ["hil_guidance", "synthesis_context"],
                "expected_skills": ["knowledge_recall", "guided_investigation"],
                "mitre_refs": [],
                "risk_level": "low",
                "sensitivity": "internal",
                "confidence_weight": 0.7,
                "status": "published",
                "approval_status": "coe_reviewed",
                "metadata": {
                    "source": "mitre_atlas",
                    "entity": entity,
                },
            }
        )
    return documents, entries


def _merge(fixtures_path: Path, prefix: str, new_rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    payload = json.loads(fixtures_path.read_text(encoding="utf-8"))
    kept: list[dict[str, Any]] = []
    tail: list[dict[str, Any]] = []
    for row in payload:
        if str(row.get(key) or "").startswith(prefix):
            continue
        if str(row.get(key) or "").startswith("skill-enrich-"):
            tail.append(row)
        else:
            kept.append(row)
    new_rows_sorted = sorted(new_rows, key=lambda row: str(row.get(key) or ""))
    return kept + new_rows_sorted + tail


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    documents, entries = _build_payload()
    merged_docs = _merge(DOCS_PATH, DOC_PREFIX, documents, "doc_id")
    merged_entries = _merge(ENTRIES_PATH, DOC_PREFIX, entries, "entry_id")
    rendered_docs = json.dumps(merged_docs, indent=1, ensure_ascii=False) + "\n"
    rendered_entries = json.dumps(merged_entries, indent=1, ensure_ascii=False) + "\n"
    if args.check:
        if (
            DOCS_PATH.read_text(encoding="utf-8") != rendered_docs
            or ENTRIES_PATH.read_text(encoding="utf-8") != rendered_entries
        ):
            print("ATLAS SOC-KB fixtures: drift detected", file=sys.stderr)
            return 1
        print("ATLAS SOC-KB fixtures: no drift")
        return 0
    DOCS_PATH.write_text(rendered_docs, encoding="utf-8")
    ENTRIES_PATH.write_text(rendered_entries, encoding="utf-8")
    print(f"Imported {len(documents)} ATLAS narrative docs and {len(entries)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
