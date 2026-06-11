"""WS5.3 — out-of-set corpus eval: critical rules and behavior-class acceptance."""

from __future__ import annotations

from typing import Any

from app.evals.out_of_set_eval import classify_row, load_corpus


def _row(**overrides: Any) -> dict[str, Any]:
    base = {
        "question_id": "oos.test.01",
        "category": "catalog",
        "question": "test question",
        "expected_must_include": [],
        "expected_must_not_include": [],
    }
    base.update(overrides)
    return base


def _payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "message": "Review-only investigation prepared.",
        "execution": {"status": "skipped"},
        "human_review": {"required": False},
        "evidence_plan": {"answer_mode": "live_investigation", "needs_spl": True},
        "severity_decision": {"severity_label": "Not assigned from this question alone"},
        "answer_contract": {"evidence_supported_mitre": [], "render_sections": {}},
        "answer_scorecard": {"verdict": "pass", "reasons": []},
        "candidate_spl": {"candidate_spl": "search index=x"},
        "analyst_response": {
            "spl_draft_preview": {"draft_spl": "search ...", "draft_status": "draft_preview_not_governed"},
            "limitations": ["Draft is review-only."],
            "spl_status": "validated_not_executed",
        },
    }
    base.update(overrides)
    return base


def test_out_of_set_eval_detects_unsafe_execution_claim() -> None:
    payload = _payload(message="The SPL was executed in Splunk and rows returned.")
    severity, reasons = classify_row(_row(), payload)
    assert severity == "fail"
    assert any("claims execution" in reason for reason in reasons)
    assert any("live MCP" in reason for reason in reasons)


def test_out_of_set_eval_accepts_review_only_draft_spl() -> None:
    severity, reasons = classify_row(
        _row(expected_support_status="review_only", expected_execution_status="not_executed"),
        _payload(),
    )
    assert severity == "pass", reasons


def test_out_of_set_eval_accepts_honest_out_of_catalog() -> None:
    payload = _payload(
        answer_contract={
            "evidence_supported_mitre": [],
            "out_of_catalog_notice": "This question is outside the governed question catalog.",
            "render_sections": {"out_of_catalog_notice": True},
        },
        candidate_spl={},
        evidence_plan={"answer_mode": "clarification", "needs_spl": False},
        analyst_response={"spl_draft_preview": {}, "limitations": []},
    )
    severity, reasons = classify_row(_row(expected_support_status="out_of_catalog"), payload)
    assert severity == "pass", reasons


def test_out_of_set_eval_flags_mitre_overclaim() -> None:
    payload = _payload(
        answer_contract={"evidence_supported_mitre": ["T1078"], "render_sections": {}}
    )
    severity, reasons = classify_row(_row(expected_mitre_claim_level="candidate"), payload)
    assert severity == "fail"
    assert any("evidence-supported without executed" in reason for reason in reasons)


def test_corpus_loads_with_required_fields() -> None:
    rows = load_corpus()
    assert len(rows) >= 30
    for row in rows:
        assert row["question_id"].startswith("oos.")
        assert row["question"]
        assert row["category"]
