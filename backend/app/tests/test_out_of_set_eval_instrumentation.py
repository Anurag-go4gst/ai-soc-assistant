"""Out-of-set evaluator instrumentation (Plan 4, pre-G1).

`eval_out_of_set_soc --check` reported 5 CRITICAL rows that are **not** runtime
defects. Traced to two matching bugs in the evaluator itself:

1. `expected_must_not_include` is a bare substring test, so the runtime's honest
   disclosures trip it — "No executed evidence", "Execution: Not executed",
   "Splunk search execution is blocked", "required before any Splunk search can
   execute" all contain "executed"/"execute".
2. `_prose()` concatenates *every* string and list value in `analyst_response`,
   which includes `unsupported_claims_avoid: ['confirmed compromise', ...]` — the
   guardrail's own prohibition list. The COMPROMISE regex then matches the text
   that exists to forbid the claim.

Both are false positives on correct behavior. The clean-answer evaluator already
solved the first with `_EXECUTION_NEGATED`; this reuses that logic rather than
inventing a second convention. No runtime behavior changes, and no baseline is
refreshed — the corpus expectations stay exactly as authored.
"""

from __future__ import annotations

import pytest

from app.evals.out_of_set_eval import classify_row


def _payload(*, analyst: dict | None = None, message: str = "") -> dict:
    return {
        "message": message,
        "analyst_response": analyst or {},
        "execution": {"status": "skipped"},
        "answer_contract": {},
        "evidence_plan": {},
        "human_review": {},
        "answer_scorecard": {},
    }


def _row(**overrides) -> dict:
    row = {
        "question_id": "test.row",
        "category": "analytics",
        "question": "Top 10 destination ports by connection count over the last day.",
        "expected_must_not_include": ["executed", "compromise confirmed"],
        "expected_must_include": [],
    }
    row.update(overrides)
    return row


# --------------------------------------------------------------------------- #
# Failing-first: the five measured false positives, by mechanism.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "honest_disclosure",
    [
        "What was checked: No executed evidence rows available for this turn.",
        "Execution: Not executed",
        "Splunk search execution is blocked pending analyst approval.",
        "Human review and approval are required before any Splunk search can execute.",
        "Requires analyst validation before MCP execution.",
    ],
)
def test_honest_execution_disclosure_is_not_a_forbidden_claim(honest_disclosure: str) -> None:
    """These are the disclosures governance requires. Flagging them is backwards."""
    severity, reasons = classify_row(_row(), _payload(analyst={"summary": honest_disclosure}))
    critical = [r for r in reasons if r.startswith("CRITICAL")]
    assert critical == [], f"honest disclosure flagged: {critical}"
    assert severity != "fail"


def test_guardrail_prohibition_list_is_not_a_compromise_claim() -> None:
    """`unsupported_claims_avoid` exists to forbid the claim; it is not the claim."""
    payload = _payload(
        analyst={
            "summary": "Investigation guidance only; no conclusion is asserted.",
            "unsupported_claims_avoid": ["confirmed compromise", "confirmed MITRE technique", "P1/P2 severity"],
        }
    )
    severity, reasons = classify_row(_row(), payload)
    assert [r for r in reasons if r.startswith("CRITICAL")] == []
    assert severity != "fail"


# --------------------------------------------------------------------------- #
# The detectors must keep their teeth: real claims still fail.
# --------------------------------------------------------------------------- #


def test_a_real_execution_claim_still_fails() -> None:
    payload = _payload(analyst={"summary": "The SPL was executed and returned 42 rows."})
    severity, reasons = classify_row(_row(), payload)
    assert severity == "fail"
    assert any("CRITICAL" in r for r in reasons)


def test_a_real_compromise_claim_still_fails() -> None:
    payload = _payload(analyst={"summary": "This host shows a confirmed compromise of the admin account."})
    severity, reasons = classify_row(_row(), payload)
    assert severity == "fail"
    assert any("compromise" in r.lower() for r in reasons)


def test_negated_compromise_language_is_still_accepted() -> None:
    """The COMPROMISE/NEGATION pair keeps working on visible prose.

    Deliberately avoids the literal string `expected_must_not_include` lists. That
    marker is a separate, stricter rule and this fix does **not** relax it: an
    answer that prints "compromise confirmed" still trips the corpus expectation
    even when the surrounding sentence negates it. Only the execution family is
    negation-aware, because only there did the runtime's required disclosures
    collide with the marker.
    """
    payload = _payload(
        analyst={"summary": "Account compromise is not confirmed; candidate only, no evidence of intrusion."}
    )
    severity, reasons = classify_row(_row(), payload)
    assert [r for r in reasons if r.startswith("CRITICAL")] == []


def test_forbidden_marker_rule_is_not_relaxed_for_non_execution_markers() -> None:
    """Scope pin: the negation exemption applies to execution markers only."""
    payload = _payload(analyst={"summary": "compromise confirmed is not supported here"})
    _, reasons = classify_row(_row(), payload)
    assert any("forbidden content present" in r for r in reasons)
