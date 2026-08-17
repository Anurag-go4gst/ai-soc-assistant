"""EC action restore and query autocomplete."""

from __future__ import annotations

from app.demo import ec_actions, ec_soar
from app.demo.ec_query_match import resolve_ec_query_fuzzy, score_query_match, suggest_ec_queries


def setup_function() -> None:
    ec_actions.clear_all_for_tests()
    ec_soar.clear_all_for_tests()


def test_restore_action_snapshot_allows_soar_execute_after_store_clear() -> None:
    fake = ec_soar.FakeSoarTransport()
    ec_soar.set_transport_for_tests(fake)
    prepared = ec_actions.prepare_action(
        kind="firewall_block",
        label="Prepare firewall block",
        session_id="s1-fw",
        scenario_id="s1_governed_splunk_investigation",
        extra={
            "indicator": "198.51.100.42",
            "soar": {"playbook": "ip_block", "indicator": "198.51.100.42", "action": "block", "reason": "test"},
        },
    )
    snapshot = prepared.model_dump()
    ec_actions.clear_all_for_tests()
    approved = ec_actions.approve_action(prepared.action_id, snapshot=snapshot)
    executed = ec_actions.execute_action(approved.action_id, snapshot=snapshot)
    assert executed.state == "EXECUTED"
    assert len(fake.submitted) == 1


def test_suggest_queries_fuzzy_not_exact_only() -> None:
    suggestions = suggest_ec_queries("suspicious ip communication")
    assert suggestions
    assert any("198.51.100.42" in row["question"] for row in suggestions)


def test_resolve_ec_query_fuzzy_variation() -> None:
    scenario_id, score = resolve_ec_query_fuzzy("find communication suspicious ip affected systems")
    assert scenario_id == "s1_governed_splunk_investigation"
    assert score >= 0.38


def test_score_query_match_token_overlap() -> None:
    assert score_query_match("why feature phone nps low", "Why is Feature Phone NPS lower?") > 0.35
