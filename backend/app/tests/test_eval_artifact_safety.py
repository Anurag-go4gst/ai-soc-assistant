"""Artifact-safe writer guards for committed eval outputs (plan item 35)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.evals.artifact_safe_writer import (
    EXPECTED_BASE_105,
    EXPECTED_CORPUS_COUNT,
    ArtifactWriteRefused,
    is_committed_eval_path,
    refuse_partial_committed_write,
    write_artifact_safe,
)
from app.evals.production_runtime_parity import (
    RUNTIME_A,
    RUNTIME_B,
    validate_report,
    write_production_parity_committed_artifacts,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_langgraph_dual_parity_eval.py"
CLEAN_SCRIPT = REPO_ROOT / "scripts" / "run_soc_clean_answer_eval.py"


def _full_report() -> dict:
    return {
        "schema_version": "test",
        "metadata": {
            "runtime_a": RUNTIME_A,
            "runtime_b": RUNTIME_B,
            "corpus_count": EXPECTED_CORPUS_COUNT,
            "base_105_loaded": EXPECTED_BASE_105,
            "commit_sha": "abc123",
            "command": "test",
            "generated_at": "2026-07-25T00:00:00+00:00",
        },
        "summary": {"exact_match": 120, "approved_difference": 0, "critical_mismatch": 0},
        "rows": [{"row_id": f"row-{i}", "classification": "exact_match"} for i in range(EXPECTED_CORPUS_COUNT)],
    }


def test_committed_eval_path_detection() -> None:
    assert is_committed_eval_path(REPO_ROOT / "docs" / "evals" / "langgraph_dual_parity_report.json")
    assert not is_committed_eval_path(REPO_ROOT / "tmp" / "report.json")


def test_refuse_partial_committed_write() -> None:
    paths = {"json": REPO_ROOT / "docs" / "evals" / "test_report.json"}
    with pytest.raises(ArtifactWriteRefused):
        refuse_partial_committed_write(
            target_paths=paths,
            include_105=False,
            corpus_count=8,
            base_105_loaded=0,
        )


def test_write_artifact_safe_atomic_replace(tmp_path: Path) -> None:
    target = tmp_path / "report.json"
    target.write_text('{"rows": []}', encoding="utf-8")

    def _write(temp_dir: Path) -> dict:
        (temp_dir / "json").write_text(json.dumps(_full_report()), encoding="utf-8")
        return _full_report()["metadata"]

    metadata = write_artifact_safe(
        target_paths={"json": target},
        write_fn=_write,
        validate_fn=lambda _: [],
        command="pytest test_eval_artifact_safety",
        corpus_count=EXPECTED_CORPUS_COUNT,
        base_105_loaded=EXPECTED_BASE_105,
    )
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert len(payload["rows"]) == EXPECTED_CORPUS_COUNT
    assert metadata["command"] == "pytest test_eval_artifact_safety"


def test_write_artifact_safe_refuses_smaller_corpus_on_committed_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "langgraph_dual_parity_report.json"
    target.write_text(
        json.dumps({"metadata": {"corpus_count": 120}, "summary": {"total": 120}, "rows": [{}] * 120}),
        encoding="utf-8",
    )
    monkeypatch.setattr("app.evals.artifact_safe_writer.is_committed_eval_path", lambda _path: True)

    def _write(temp_dir: Path) -> dict:
        (temp_dir / "json").write_text(json.dumps({"rows": [{}] * 8}), encoding="utf-8")
        return {"corpus_count": 8, "base_105_loaded": 0}

    with pytest.raises(ArtifactWriteRefused):
        write_artifact_safe(
            target_paths={"json": target},
            write_fn=_write,
            validate_fn=lambda _: [],
            command="pytest",
            corpus_count=8,
            base_105_loaded=0,
        )


def test_validate_report_requires_provenance() -> None:
    report = _full_report()
    assert validate_report(report) == []
    report["metadata"].pop("commit_sha")
    assert any("commit_sha" in failure for failure in validate_report(report))


def test_dual_parity_cli_refuses_partial_committed_run() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--check",
            "--limit",
            "8",
            "--skip-105",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": "backend:.", "PATH": "/usr/bin:/bin"},
    )
    assert proc.returncode == 2
    assert "refusing partial run" in proc.stderr


def test_clean_answer_cli_refuses_partial_committed_run() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(CLEAN_SCRIPT),
            "--limit",
            "8",
            "--skip-105",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": "backend:.", "PATH": "/usr/bin:/bin"},
    )
    assert proc.returncode == 2
    assert "refusing partial run" in proc.stderr


def test_production_parity_committed_writer_validates_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    json_path = tmp_path / "langgraph_dual_parity_report.json"
    md_path = tmp_path / "langgraph_dual_parity_summary.md"
    monkeypatch.setattr("app.evals.artifact_safe_writer.is_committed_eval_path", lambda _path: True)
    report = _full_report()
    write_production_parity_committed_artifacts(
        report,
        json_path=json_path,
        markdown_path=md_path,
        command="pytest test_eval_artifact_safety",
    )
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["runtime_a"] == RUNTIME_A
    assert payload["metadata"]["runtime_b"] == RUNTIME_B
    assert payload["metadata"]["corpus_count"] == EXPECTED_CORPUS_COUNT
    assert payload["metadata"]["base_105_loaded"] == EXPECTED_BASE_105
    assert payload["metadata"]["commit_sha"]
    assert payload["metadata"]["command"]
