"""CLI contract for scripts/audit_reference_probes.py.

The probe script is used as a verification gate (C0, G1). A gate that rewrites
its own baseline cannot fail, so the property under test is not only "does it
detect drift" but "does it leave the baseline byte-identical while doing so".

These tests import the script as a module and stub the probe runner, so they
never execute the real pipeline — the ten live probes take minutes and are
covered by the gate itself, not by this unit test.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

from app.config import settings

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "audit_reference_probes.py"

_OFFLINE_ENV_KEYS: tuple[str, ...] = (
    "AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED",
    "AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED",
    "AI_SOC_LLM_EVIDENCE_OBSERVER_ENABLED",
    "AI_SOC_LLM_SPL_FALLBACK_ENABLED",
    "AI_SOC_LLM_UTILITY_SPL_DRAFT_ENABLED",
    "MCP_GLOBAL_EXECUTION_ENABLED",
)

_OFFLINE_SETTING_NAMES: tuple[str, ...] = (
    "ai_soc_llm_enabled",
    "ai_soc_llm_intent_advisor_enabled",
    "ai_soc_llm_spl_fallback_enabled",
    "ai_soc_llm_utility_spl_draft_enabled",
    "ai_soc_llm_final_synthesis_enabled",
    "ai_soc_llm_live_synthesis_enabled",
    "mcp_global_execution_enabled",
)


def _load_script_module() -> Any:
    """Import by path without leaking the CLI's offline posture into pytest."""
    original_env = {key: os.environ.get(key) for key in _OFFLINE_ENV_KEYS}
    original_settings = {
        name: getattr(settings, name)
        for name in _OFFLINE_SETTING_NAMES
        if hasattr(settings, name)
    }
    spec = importlib.util.spec_from_file_location("audit_reference_probes_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        for name, value in original_settings.items():
            setattr(settings, name, value)
    return module


@pytest.fixture(scope="module")
def script() -> Any:
    return _load_script_module()


def _row(probe_id: str, **overrides: Any) -> dict[str, Any]:
    row = {
        "id": probe_id,
        "kind": "positive",
        "query": f"query for {probe_id}",
        "selected_skill": "knowledge_recall",
        "answer_mode": "rag_only",
        "request_mode": "reference_knowledge",
        "stage_schedule": ["rag_early", "reference_finalize"],
        "primary_shape": "reference_taxonomy",
        "human_review_type": None,
        "has_mitre_panel": False,
        "has_reference_panel": True,
    }
    row.update(overrides)
    return row


def _write_baseline(script: Any, path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(script._render(rows), encoding="utf-8")


@pytest.fixture()
def harness(script: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point the script at a temp baseline and a stubbed probe runner."""
    baseline = tmp_path / "reference_knowledge_baseline.md"
    monkeypatch.setattr(script, "OUT", baseline)

    state: dict[str, Any] = {"rows": [_row("P1"), _row("N1", kind="negative")]}
    _write_baseline(script, baseline, state["rows"])

    monkeypatch.setattr(script, "_run_probes", lambda: [dict(r) for r in state["rows"]])
    return script, baseline, state


def _run(script: Any, monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> int:
    monkeypatch.setattr(sys, "argv", ["audit_reference_probes.py", *argv])
    return script.main()


def test_check_passes_and_leaves_baseline_byte_identical(harness, monkeypatch, capsys):
    script, baseline, _ = harness
    before = baseline.read_bytes()

    assert _run(script, monkeypatch, ["--check"]) == 0

    assert baseline.read_bytes() == before, "a passing check must not rewrite the baseline"
    assert "all probes match the frozen baseline" in capsys.readouterr().out


def test_default_mode_is_check_and_is_non_mutating(harness, monkeypatch):
    script, baseline, _ = harness
    before = baseline.read_bytes()

    assert _run(script, monkeypatch, []) == 0

    assert baseline.read_bytes() == before, "the default invocation must not mutate the baseline"


def test_drift_exits_non_zero_without_rewriting_the_baseline(harness, monkeypatch, capsys):
    script, baseline, state = harness
    before = baseline.read_bytes()
    # Regression shape this gate exists to catch: a reference answer turning into
    # a live investigation.
    state["rows"] = [
        _row("P1", answer_mode="live_investigation", primary_shape="hunt"),
        _row("N1", kind="negative"),
    ]

    assert _run(script, monkeypatch, ["--check"]) == 1

    assert baseline.read_bytes() == before, "drift must never be absorbed into the baseline"
    out = capsys.readouterr()
    assert "DRIFT" in out.out
    assert "answer_mode" in out.out and "live_investigation" in out.out
    assert "P1" in out.out


def test_missing_and_extra_probes_are_drift(harness, monkeypatch, capsys):
    script, baseline, state = harness
    state["rows"] = [_row("P1")]  # N1 disappeared

    assert _run(script, monkeypatch, ["--check"]) == 1
    assert "N1" in capsys.readouterr().out


def test_errored_probe_is_drift_not_a_pass(harness, monkeypatch, capsys):
    script, baseline, state = harness
    state["rows"] = [_row("P1", error="row_timeout:20s"), _row("N1", kind="negative")]

    assert _run(script, monkeypatch, ["--check"]) == 1
    assert "row_timeout" in capsys.readouterr().out


def test_out_writes_scratch_report_and_leaves_baseline_untouched(harness, monkeypatch, tmp_path):
    script, baseline, _ = harness
    before = baseline.read_bytes()
    scratch = tmp_path / "scratch" / "probes.md"

    assert _run(script, monkeypatch, ["--out", str(scratch)]) == 0

    assert scratch.exists() and scratch.read_text(encoding="utf-8").strip()
    assert baseline.read_bytes() == before, "--out must not touch the frozen baseline"


def test_out_with_check_still_reports_drift(harness, monkeypatch, tmp_path):
    script, baseline, state = harness
    scratch = tmp_path / "probes.md"
    state["rows"] = [_row("P1", selected_skill="spl_generation"), _row("N1", kind="negative")]

    assert _run(script, monkeypatch, ["--out", str(scratch), "--check"]) == 1
    assert scratch.exists()


def test_update_baseline_is_the_only_mutating_path(harness, monkeypatch):
    script, baseline, state = harness
    before = baseline.read_bytes()
    state["rows"] = [_row("P1", answer_mode="live_investigation"), _row("N1", kind="negative")]

    assert _run(script, monkeypatch, ["--update-baseline"]) == 0

    assert baseline.read_bytes() != before
    # and the refreshed baseline now matches, proving the write was complete
    assert _run(script, monkeypatch, ["--check"]) == 0


def test_check_and_update_baseline_are_mutually_exclusive(harness, monkeypatch):
    script, _, _ = harness
    with pytest.raises(SystemExit):
        _run(script, monkeypatch, ["--check", "--update-baseline"])


def test_unparseable_baseline_is_a_usage_error_not_a_pass(harness, monkeypatch):
    script, baseline, _ = harness
    baseline.write_text("# no json block here\n", encoding="utf-8")

    assert _run(script, monkeypatch, ["--check"]) == 2


def test_timestamp_only_difference_is_not_drift(harness, monkeypatch):
    """The rendered baseline embeds a Generated: timestamp; it must be ignored."""
    script, baseline, state = harness
    original = baseline.read_text(encoding="utf-8")
    baseline.write_text(
        original.replace("Generated: ", "Generated: 1999-01-01 00:00 UTC — was "), encoding="utf-8"
    )

    assert _run(script, monkeypatch, ["--check"]) == 0
