"""Artifact-safe writer for committed eval outputs under ``docs/evals/``.

Enforces plan item 35 guarantees at the writer — not via operator discipline:

1. Corpus completeness (120 rows; 105 base when ``include_105``)
2. Temp-first generation
3. Validate before replace
4. Atomic replacement
5. Refuse shrinkage vs an existing valid committed corpus
6. ``include_105=False`` cannot overwrite full-corpus artifacts
7. Fail closed (raise / non-zero) on incomplete corpus
8. Provenance metadata on every committed parity artifact
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
COMMITTED_EVALS_DIR = REPO_ROOT / "docs" / "evals"

EXPECTED_CORPUS_COUNT = 120
EXPECTED_BASE_105 = 105


class ArtifactWriteRefused(Exception):
    """A write to committed eval artifacts was refused."""


def commit_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
        ).stdout.strip()
    except Exception:  # noqa: BLE001 — provenance is best-effort
        return "unknown"


def is_committed_eval_path(path: Path) -> bool:
    resolved = path.resolve()
    committed = COMMITTED_EVALS_DIR.resolve()
    return resolved == committed or committed in resolved.parents


def corpus_is_complete(
    *,
    corpus_count: int,
    base_105_loaded: int,
    include_105: bool = True,
) -> bool:
    if corpus_count != EXPECTED_CORPUS_COUNT:
        return False
    if include_105 and base_105_loaded != EXPECTED_BASE_105:
        return False
    return True


def _read_existing_corpus_count(primary_json: Path) -> int | None:
    if not primary_json.is_file():
        return None
    try:
        payload = json.loads(primary_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    metadata = payload.get("metadata")
    if isinstance(metadata, dict) and metadata.get("corpus_count") is not None:
        return int(metadata["corpus_count"])
    summary = payload.get("summary")
    if isinstance(summary, dict):
        for key in ("total", "total_evaluated", "corpus_count"):
            if summary.get(key) is not None:
                return int(summary[key])
    rows = payload.get("rows")
    if isinstance(rows, list):
        return len(rows)
    return None


def refuse_partial_committed_write(
    *,
    target_paths: Mapping[str, Path],
    include_105: bool,
    corpus_count: int,
    base_105_loaded: int,
) -> None:
    """Rule 6 — reduced corpus cannot overwrite committed artifacts."""
    if not any(is_committed_eval_path(path) for path in target_paths.values()):
        return
    if not corpus_is_complete(
        corpus_count=corpus_count,
        base_105_loaded=base_105_loaded,
        include_105=include_105,
    ):
        raise ArtifactWriteRefused(
            f"refusing partial corpus write to committed eval artifacts: "
            f"corpus_count={corpus_count} base_105_loaded={base_105_loaded} include_105={include_105}"
        )


def write_artifact_safe(
    *,
    target_paths: Mapping[str, Path],
    write_fn: Callable[[Path], dict[str, Any]],
    validate_fn: Callable[[dict[str, Any]], list[str]],
    command: str,
    include_105: bool = True,
    corpus_count: int | None = None,
    base_105_loaded: int | None = None,
) -> dict[str, Any]:
    """Temp-first write with validation, shrinkage refusal, and atomic replace."""
    committed_targets = {name: path for name, path in target_paths.items() if is_committed_eval_path(path)}
    primary_json = committed_targets.get("json") or next(iter(target_paths.values()), None)

    if committed_targets:
        if corpus_count is None or base_105_loaded is None:
            raise ArtifactWriteRefused("corpus_count and base_105_loaded required for committed writes")
        refuse_partial_committed_write(
            target_paths=target_paths,
            include_105=include_105,
            corpus_count=corpus_count,
            base_105_loaded=base_105_loaded,
        )
        if primary_json is not None:
            existing = _read_existing_corpus_count(primary_json)
            if existing is not None and corpus_count < existing:
                raise ArtifactWriteRefused(
                    f"refusing corpus shrinkage: new={corpus_count} < committed={existing} "
                    f"({primary_json})"
                )

    for path in target_paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="ai-soc-eval-artifact-") as tmp:
        temp_dir = Path(tmp)
        metadata = write_fn(temp_dir)
        metadata["command"] = command
        metadata["commit_sha"] = commit_sha()
        metadata.setdefault("generated_at", metadata.get("generated_at"))

        failures = validate_fn(metadata)
        if failures:
            raise ArtifactWriteRefused("; ".join(failures))

        for name, final_path in target_paths.items():
            temp_path = temp_dir / name
            if not temp_path.is_file():
                raise ArtifactWriteRefused(f"missing temp artifact {name}: {temp_path}")
            final_path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(temp_path, final_path)

    return metadata


def attach_provenance(
    report: dict[str, Any],
    *,
    command: str,
    runtime_a: str | None = None,
    runtime_b: str | None = None,
) -> dict[str, Any]:
    """Ensure writer-enforced provenance fields are present on a report dict."""
    metadata = dict(report.get("metadata") or {})
    metadata["command"] = command
    metadata["commit_sha"] = commit_sha()
    if runtime_a is not None:
        metadata["runtime_a"] = runtime_a
    if runtime_b is not None:
        metadata["runtime_b"] = runtime_b
    report = dict(report)
    report["metadata"] = metadata
    return report
