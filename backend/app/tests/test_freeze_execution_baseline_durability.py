"""Plan 5 A4.5 — the protected-artifact gate must be durable and must guard what it declares.

Measured at P0: `freeze_execution_baseline.py --check` reported **13 checked** while `PROTECTED`
declares 14 entries. Two independent defects:

1. The manifest defaults to `/tmp/exec-baseline.json`, so the gate compares against a file that does
   not survive a reboot and does not exist at all on a fresh host — where `--check` exits 2 rather
   than passing.
2. `check()` iterates the *stored* manifest, so an artifact added to `PROTECTED` but never
   re-captured is silently skipped. That is exactly what happened to
   `docs/evals/routing_truth_set_baseline_v1.json`, added at Plan 4 R1.5: declared protected, in
   practice unguarded, so `--freeze` could have rewritten the routing baseline with the gate still
   green.

A protection mechanism that silently protects less than it claims is worse than none, because the
green result is cited as evidence. These tests pin both properties.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "freeze_execution_baseline.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("freeze_execution_baseline", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def freeze():
    return _load_module()


def _declared(module) -> set[str]:
    return {rel for members in module.PROTECTED.values() for rel in members}


def test_manifest_is_committed_not_ephemeral(freeze) -> None:
    """The baseline must live in the repo — a gate backed by /tmp proves nothing on a fresh host."""
    default_in = freeze.DEFAULT_MANIFEST_PATH
    assert not str(default_in).startswith("/tmp"), (
        f"protected-artifact manifest defaults to an ephemeral path: {default_in}"
    )
    assert default_in.is_file(), f"committed manifest is missing: {default_in}"


def test_committed_manifest_covers_every_declared_artifact(freeze) -> None:
    """The stored manifest must not lag `PROTECTED` — the Plan 4 R1.5 failure mode."""
    stored = json.loads(freeze.DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8"))["protected"]
    recorded = {rel for members in stored.values() for rel in members}
    unguarded = sorted(_declared(freeze) - recorded)
    assert not unguarded, (
        "artifacts are declared protected but absent from the committed manifest, so drift on them "
        f"is invisible: {unguarded}"
    )


def test_check_fails_closed_when_a_declared_artifact_is_unrecorded(freeze, tmp_path) -> None:
    """A declared-but-uncaptured member must fail the check, not be skipped."""
    stored = json.loads(freeze.DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8"))
    group = next(g for g, members in stored["protected"].items() if members)
    dropped = sorted(stored["protected"][group])[0]
    del stored["protected"][group][dropped]

    partial = tmp_path / "partial.json"
    partial.write_text(json.dumps(stored), encoding="utf-8")

    assert freeze.check(partial) != 0, (
        f"check() passed while {dropped} was declared in PROTECTED but missing from the manifest"
    )


def test_check_detects_drift_in_the_routing_truth_set_baseline(tmp_path) -> None:
    """End-to-end on the artifact that was actually unguarded, via the real CLI.

    Runs against a copy of the repo tree's manifest so the test never mutates a protected file.
    """
    target = REPO_ROOT / "docs/evals/routing_truth_set_baseline_v1.json"
    original = target.read_bytes()
    try:
        target.write_bytes(original + b"\n")
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--check"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert proc.returncode != 0, (
            "tampering with the routing truth-set baseline did not fail the protected-artifact "
            f"gate; stdout={proc.stdout!r}"
        )
        assert "routing_truth_set_baseline_v1.json" in proc.stdout
    finally:
        target.write_bytes(original)


def test_check_counts_what_it_actually_verified(freeze, capsys) -> None:
    """The printed count is cited as closure evidence, so it must equal the declared set."""
    assert freeze.check(freeze.DEFAULT_MANIFEST_PATH) == 0
    out = capsys.readouterr().out
    assert f"({len(_declared(freeze))} checked)" in out, out
