"""Stage 3L: 105-question shadow eval harness (no network)."""

from __future__ import annotations

from pathlib import Path

from app.evals.stage3l_105_shadow_eval import run_105_shadow_eval

_REPO = Path(__file__).resolve().parents[3]
MAP_PATH = _REPO / "docs" / "stage3l_s6_105_question_operation_map.json"


def test_105_question_shadow_eval_passes_on_committed_map() -> None:
    summary = run_105_shadow_eval(MAP_PATH)
    assert summary.question_count == 105
    assert summary.overall_pass is True
    assert summary.buckets["promoted"]["total"] == 11
    assert summary.buckets["promoted"]["fail"] == 0
