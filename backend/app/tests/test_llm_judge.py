"""WS5.2 — LLM judge is eval-only: skips cleanly, never changes verdicts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.evals.llm_judge import judge_report, judge_row


@dataclass
class _FakeResult:
    text: str


class _FakeClient:
    base_url = "http://fake:1/v1"
    model = "fake-judge"

    def __init__(self, text: str | None = None, exc: Exception | None = None) -> None:
        self._text = text
        self._exc = exc

    def generate(self, **kwargs: Any) -> _FakeResult:
        if self._exc is not None:
            raise self._exc
        return _FakeResult(text=self._text or "")


def _report() -> dict[str, Any]:
    return {
        "total": 2,
        "critical_count": 0,
        "counts": {"pass": 2, "review": 0, "fail": 0},
        "rows": [
            {"question_id": "oos.a", "question": "q1", "severity": "pass", "deterministic_verdict": "pass", "answer_excerpt": "x"},
            {"question_id": "oos.b", "question": "q2", "severity": "pass", "deterministic_verdict": "pass", "answer_excerpt": "y"},
        ],
    }


def test_llm_judge_skips_cleanly_when_unavailable() -> None:
    report = _report()
    summary = judge_report(report, client=_FakeClient(exc=RuntimeError("down")))
    assert summary["judge_enabled"] is True
    assert summary["status_counts"]["skipped"] == 2
    for row in report["rows"]:
        assert row["judge_status"] == "skipped"
        assert row["deterministic_verdict"] == "pass"
        assert row["final_eval_verdict"] == "pass"
    assert report["critical_count"] == 0


def test_llm_judge_unavailable_provider_marks_all_skipped(monkeypatch) -> None:
    import app.evals.llm_judge as judge

    monkeypatch.setattr(judge, "_judge_client", lambda: None)
    report = _report()
    summary = judge_report(report, client=None)
    assert summary["judge_enabled"] is False
    assert summary["judge_attempted"] is False
    assert all(row["judge_status"] == "skipped" for row in report["rows"])
    assert all(row["judge_reasons"] == ["judge_unavailable"] for row in report["rows"])


def test_llm_judge_does_not_change_runtime_verdict() -> None:
    report = _report()
    client = _FakeClient('{"judge_status": "fail", "judge_reasons": ["too generic"]}')
    summary = judge_report(report, client=client)
    assert summary["judge_used"] is True
    for row in report["rows"]:
        # Deterministic verdict and gate inputs untouched; only the
        # report-only roll-up reflects the judge opinion.
        assert row["deterministic_verdict"] == "pass"
        assert row["severity"] == "pass"
        assert row["final_eval_verdict"] == "fail"
    assert report["critical_count"] == 0
    assert report["counts"] == {"pass": 2, "review": 0, "fail": 0}


def test_judge_row_garbage_output_is_skipped() -> None:
    verdict = judge_row({"question": "q", "answer_excerpt": "a"}, _FakeClient("not json"))
    assert verdict["judge_status"] == "skipped"
    assert verdict["judge_reasons"] == ["judge_output_unusable"]
