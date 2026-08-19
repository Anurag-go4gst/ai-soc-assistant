"""A capability the user says they LACK must not bind as a request for it.

"We have no detection rule or SOAR playbook yet for VPN detection" bound
soc_show_sop at 0.91 on the single substring "playbook", which set
intent_family=sop_or_playbook and spl_allowed=False on a P1 zero-day exposure
question. The analyst was told "Governed SOP retrieved ... as requested".

The routing truth set could not see this defect when it was fixed (64/76 before
and after), so these are the direct regression pins.
"""

from __future__ import annotations

import pytest

from app.chat.query_signals import term_is_negated
from app.use_cases.registry import match_use_cases


@pytest.mark.parametrize(
    "query,term,expected",
    [
        ("we have no soar playbook yet for vpn detection", "playbook", True),
        ("there is no runbook for this technique", "runbook", True),
        ("we dont have a sop for this", "sop", True),
        ("we do not have a playbook", "playbook", True),
        ("without a playbook we cannot proceed", "playbook", True),
        # Not negation: the procedure exists and is being referenced.
        ("show me the playbook for phishing response", "playbook", False),
        ("the playbook says do not reboot the gateway", "playbook", False),
        ("what is the sop for ransomware containment", "sop", False),
    ],
)
def test_term_is_negated(query: str, term: str, expected: bool) -> None:
    assert term_is_negated(query, term) is expected


def test_negated_playbook_does_not_bind_a_procedure_use_case() -> None:
    """The originating defect, end to end through the catalogue matcher."""
    query = (
        "A critical zero-day affects our internet-facing VPN gateways. We have no "
        "detection rule or SOAR playbook yet for VPN detection. Determine whether we "
        "are exposed and what immediate controls we should apply."
    )
    assert [m.use_case_id for m in match_use_cases(query)] == []


def test_genuine_procedure_requests_still_bind() -> None:
    """Guard the other direction: the fix must not suppress real SOP asks."""
    for query in (
        "show me the sop for phishing response",
        "what is the playbook for ransomware containment",
    ):
        matches = match_use_cases(query)
        assert matches, query
        assert matches[0].use_case_id == "soc_show_sop", query
        assert matches[0].confidence >= 0.9, query


def test_negated_capability_with_procedure_ask_does_not_bind_but_still_routes_knowledge() -> None:
    """Discriminator (truth-set row rt.neg.004) — records a known imprecision.

    Here the capability is absent AND the ask IS to produce the procedure, so a
    procedure bind would arguably be right. The negation rule suppresses it
    anyway, because it keys on the negated term and cannot see that "write one
    for us" restores the request.

    That is acceptable today only because the answer is still correct: with no
    catalogue bind the query falls to the deterministic knowledge floor and
    routes to knowledge_recall, which is what rt.neg.004 requires. Route-level
    correctness is pinned there, not here.

    If a future change makes an unbound query route somewhere other than
    knowledge_recall, this imprecision becomes a real defect and the negation
    rule needs an "ask restores the request" clause.
    """
    matches = match_use_cases("We have no playbook for VPN zero-day response - write one for us.")
    assert [m.use_case_id for m in matches] == []
