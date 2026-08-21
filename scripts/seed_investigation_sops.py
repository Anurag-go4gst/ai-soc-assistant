#!/usr/bin/env python3
"""Publish the curated investigation SOP seed (architecture P12).

Uses the existing ``KnowledgeRepository`` import draft/publish path — no new
ingestion pipeline, no direct RAG-to-LLM route. Idempotent: a document already
present at the same version is left alone.

    python3 scripts/seed_investigation_sops.py [--dry-run] [--approved-by coe.soc]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.knowledge.repository import get_knowledge_repository  # noqa: E402
from app.knowledge.seed.investigation_sop_seed import (  # noqa: E402
    SEED_DOCUMENTS,
    SEED_ENTRIES,
    seed_batch,
)
from app.knowledge.validation import validate_import_batch  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--approved-by", default="coe.soc")
    args = parser.parse_args()

    repository = get_knowledge_repository()
    existing = {str(doc.get("doc_id")) for doc in repository.list_documents()}
    documents = [doc for doc in SEED_DOCUMENTS if str(doc["doc_id"]) not in existing]
    if not documents:
        print("seed_already_present: nothing to do")
        return 0

    wanted = {str(doc["doc_id"]) for doc in documents}
    entries = [entry for entry in SEED_ENTRIES if str(entry["doc_id"]) in wanted]
    batch = seed_batch()

    validation = validate_import_batch(
        batch=batch,
        documents=documents,
        entries=entries,
        existing_documents=repository.list_documents(),
    )
    if validation.get("validation_errors"):
        print(f"validation_failed: {validation['validation_errors']}", file=sys.stderr)
        return 2
    if validation.get("validation_warnings"):
        print(f"warnings: {validation['validation_warnings']}")

    if args.dry_run:
        print(f"dry_run_ok: {len(documents)} documents, {len(entries)} entries")
        return 0

    repository.save_import_batch(batch, documents, entries)
    for document in documents:
        repository.publish_document(str(document["doc_id"]), approved_by=args.approved_by)
    print(f"published: {len(documents)} documents, {len(entries)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
