"""Contract tests for the protected-artifact manifest gate."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "freeze_execution_baseline.py"


@pytest.fixture()
def guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    spec = importlib.util.spec_from_file_location(
        "freeze_execution_baseline_under_test", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    protected = {
        "eval_baselines": ("baseline.txt",),
        "published_doc_mirrors": (
            "docs/details.html",
            "public/details.html",
            "dist/details.html",
        ),
    }
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "PROTECTED", protected)
    monkeypatch.setattr(module, "MIRROR_GROUPS", ("published_doc_mirrors",))

    (tmp_path / "baseline.txt").write_text("frozen\n", encoding="utf-8")
    for relative in protected["published_doc_mirrors"]:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("published\n", encoding="utf-8")
    return module


def test_capture_then_check_is_clean(guard: Any, tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"

    assert guard.capture(manifest) == 0
    assert guard.check(manifest) == 0


def test_check_fails_on_protected_drift(guard: Any, tmp_path: Path, capsys) -> None:
    manifest = tmp_path / "manifest.json"
    assert guard.capture(manifest) == 0
    (tmp_path / "baseline.txt").write_text("drifted\n", encoding="utf-8")

    assert guard.check(manifest) == 1
    output = capsys.readouterr().out
    assert "PROTECTED ARTIFACT DRIFT" in output
    assert "[eval_baselines] baseline.txt" in output


def test_check_fails_when_published_mirrors_diverge(
    guard: Any, tmp_path: Path, capsys
) -> None:
    manifest = tmp_path / "manifest.json"
    assert guard.capture(manifest) == 0
    (tmp_path / "public/details.html").write_text("torn\n", encoding="utf-8")

    assert guard.check(manifest) == 1
    assert "copies are not byte-identical" in capsys.readouterr().out


def test_ignore_escape_hatch_is_not_supported(
    guard: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["freeze_execution_baseline.py", "--check", "--ignore", "eval_baselines"],
    )

    with pytest.raises(SystemExit) as exc:
        guard.main()

    assert exc.value.code == 2
