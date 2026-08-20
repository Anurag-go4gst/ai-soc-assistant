"""A capability the user says they LACK must not bind as a request for it.

"We have no detection rule or SOAR playbook yet for VPN detection" bound
soc_show_sop at 0.91 on the single substring "playbook", which set
intent_family=sop_or_playbook and spl_allowed=False on a P1 zero-day exposure
question. The analyst was told "Governed SOP retrieved ... as requested".

The routing truth set could not see this defect when it was fixed (64/76 before
and after), so these are the direct regression pins.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.chat.query_signals import term_is_negated
from app.use_cases.registry import get_use_case, load_use_case_catalog, match_use_cases

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TRUTH_SET = _REPO_ROOT / "docs" / "evals" / "routing_truth_set_v1.json"
_QUESTION_105 = _REPO_ROOT / "backend" / "app" / "evals" / "golden_answers" / "question_105_golden.jsonl"


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
        # Ranking is coverage_score (item 3), not the retired 0.62+0.05*n
        # formula that used to pin this at >= 0.9. A one-word SOP hit is a
        # real bind; do not require the old additive confidence.


def test_sop_ask_outranks_hunt_terms_named_in_the_procedure() -> None:
    """The procedure is the ask; 'brute force' is which SOP, not a hunt bind."""
    matches = match_use_cases("Which SOP covers brute force authentication?")
    assert matches
    assert matches[0].use_case_id == "soc_show_sop"


def test_close_margin_escalates_rather_than_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    """Item 4: a two-candidate bind inside the too-close band is not committed."""
    from app.use_cases import registry as use_case_registry

    query = "vpn login failures"
    committed = match_use_cases(query)
    assert committed, "clear enough under the production 0.10 band"
    assert committed[0].bind_margin is not None
    monkeypatch.setattr(use_case_registry, "_BIND_MARGIN_TOO_CLOSE", 0.20)
    assert match_use_cases(query) == []
    # Uncontested SOP and a clear MFA-vs-generic gap still bind at production.
    monkeypatch.setattr(use_case_registry, "_BIND_MARGIN_TOO_CLOSE", 0.10)
    assert match_use_cases("Show me the SOP for phishing response.")[0].use_case_id == "soc_show_sop"
    assert (
        match_use_cases("Find MFA failures for privileged users in the last 24 hours.")[0].use_case_id
        == "auth_mfa_failure_spike"
    )


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


def test_mitre_ask_without_alert_context_does_not_bind_a_hunt() -> None:
    """rt.know.002 — coverage ranking must not steal a mapping ask into failed-logins.

    The user names failed logins as the only fact they have, and explicitly
    denies alert/log context. Hunt coverage is higher; mapping is the ask.
    """
    query = (
        "What MITRE technique is this? I only know there were multiple failed "
        "logins, but I do not have alert details or logs."
    )
    matches = match_use_cases(query, limit=3)
    assert matches
    assert matches[0].use_case_id == "soc_map_alert_mitre"
    assert matches[0].primary_skill == "mitre_mapping"


def test_unnegated_playbook_with_exposure_ask_does_not_bind_sop() -> None:
    """Item 5: live-investigation phrasing vetoes soc_show_sop even when playbook is present."""
    query = (
        "We have a SOAR playbook. Determine whether we are exposed and what "
        "immediate controls we should apply."
    )
    assert [m.use_case_id for m in match_use_cases(query)] == []


def test_requires_signals_bang_forbids_when_signal_present() -> None:
    """Item 5 mechanism: `!live_data_request` drops a SOP bind that `find` would otherwise keep."""
    sop = get_use_case("soc_show_sop")
    assert sop is not None
    original = list(sop.requires_signals)
    sop.requires_signals = ["!live_data_request"]
    try:
        assert match_use_cases("Show me the SOP for phishing response.")
        assert match_use_cases("Show me the SOP for phishing response.")[0].use_case_id == "soc_show_sop"
        assert match_use_cases("find the SOP for phishing response") == []
    finally:
        sop.requires_signals = original


def test_absent_exclusion_and_requires_are_noop_except_soc_show_sop() -> None:
    """Schema addition is backward compatible: only soc_show_sop is populated."""
    for use_case in load_use_case_catalog():
        if use_case.use_case_id == "soc_show_sop":
            assert use_case.exclusion_patterns
            assert use_case.requires_signals == []
            continue
        assert use_case.exclusion_patterns == []
        assert use_case.requires_signals == []


def test_non_sop_binds_byte_identical_when_soc_show_sop_metadata_cleared() -> None:
    """Every use case without the new fields produces a byte-identical bind."""
    queries: list[tuple[str, str]] = []
    truth = json.loads(_TRUTH_SET.read_text(encoding="utf-8"))
    for row in truth["rows"]:
        queries.append((row["row_id"], row["query"]))
    with _QUESTION_105.open(encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            queries.append((payload["case_id"], payload["query"]))

    production = {row_id: [m.use_case_id for m in match_use_cases(query)] for row_id, query in queries}
    sop = get_use_case("soc_show_sop")
    assert sop is not None
    original_excl = list(sop.exclusion_patterns)
    original_req = list(sop.requires_signals)
    sop.exclusion_patterns = []
    sop.requires_signals = []
    try:
        cleared = {row_id: [m.use_case_id for m in match_use_cases(query)] for row_id, query in queries}
    finally:
        sop.exclusion_patterns = original_excl
        sop.requires_signals = original_req

    for row_id, ids in production.items():
        if "soc_show_sop" in ids or "soc_show_sop" in cleared[row_id]:
            continue
        assert ids == cleared[row_id], row_id


def test_display_name_alone_does_not_authorize_a_t2_bind() -> None:
    """LOOP 1: display_name is documentation, not a match term."""
    from app.use_cases.registry import get_use_case as _get

    aws = _get("aws_console_success_logins_by_user")
    assert aws is not None
    assert match_use_cases(aws.display_name) == []
    generate = _get("soc_generate_spl")
    assert generate is not None
    assert match_use_cases(generate.display_name) == []


def test_example_query_that_contains_an_intent_pattern_still_binds() -> None:
    """LOOP 1: example text still binds when it contains a real intent_pattern."""
    matches = match_use_cases("Investigate failed login spike on APP-01")
    assert matches
    assert matches[0].use_case_id == "auth_failed_login_spike"
    assert "failed login" in [p.lower() for p in matches[0].matched_patterns]
