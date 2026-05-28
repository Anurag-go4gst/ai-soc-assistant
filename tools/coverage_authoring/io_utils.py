"""Draft file I/O with path guards."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.coverage.coverage_models import PatternCoverageEntry

from draft_schema import CoverageDraftDocument
from deterministic import slugify
from registries import DRAFTS_DIR, MANIFEST_PATH


def ensure_drafts_dir() -> Path:
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    return DRAFTS_DIR


def draft_output_path(question: str, *, drafts_dir: Path | None = None) -> Path:
    base = drafts_dir or ensure_drafts_dir()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return base / f"draft_{timestamp}_{slugify(question)}.json"


def resolve_draft_path(path: Path) -> Path:
    resolved = path.resolve()
    drafts_root = ensure_drafts_dir().resolve()
    if drafts_root not in resolved.parents and resolved != drafts_root:
        raise ValueError(f"Draft path must be under {drafts_root}")
    return resolved


def assert_not_manifest_path(path: Path) -> None:
    if path.resolve() == MANIFEST_PATH.resolve():
        raise ValueError("Refusing to write the committed runtime manifest from Q4A")


def write_draft_document(document: CoverageDraftDocument, path: Path) -> Path:
    target = resolve_draft_path(path)
    assert_not_manifest_path(target)
    payload = document.to_json_dict()
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return target


def load_draft_document(path: Path) -> CoverageDraftDocument:
    resolved = path.resolve()
    data = json.loads(resolved.read_text(encoding="utf-8"))
    entry_data = data.get("entry", data)
    entry = PatternCoverageEntry.model_validate(entry_data)
    header = {k: data[k] for k in (
        "draft_only",
        "generated_by",
        "requires_human_review",
        "promoted_to_manifest",
        "generated_at",
        "validation_warnings",
        "validation_errors",
    ) if k in data}
    return CoverageDraftDocument(entry=entry, **header)


def load_entry_json(path: Path) -> PatternCoverageEntry:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "entry" in data:
        data = data["entry"]
    return PatternCoverageEntry.model_validate(data)
