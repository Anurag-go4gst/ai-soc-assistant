"""Spec engine and shared environment: the rules every Experience Center scenario inherits."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.demo import ec_environment as E
from app.demo.ec_agent.spec_engine import registered_spec_ids, spec_for, validated_spl
from app.demo.ec_email import LOGICAL_TEAMS
from app.demo.ec_query_match import resolve_ec_query_fuzzy
from app.demo.ec_turn import run_experience_center_turn
from app.demo.fixtures.specs import ALL_SPECS
from app.demo.scenarios import SCENARIOS, list_demo_scenarios
from app.safeguards.spl_validator import validate_spl

SPEC_IDS = [spec.scenario_id for spec in ALL_SPECS]


def _walk(scenario_id: str) -> dict[str, dict]:
    first = run_experience_center_turn(scenario_id, session_id=None).model_dump()
    session_id = first["ec_session_state"]["session_id"]
    turns = {"plan": first}
    for follow_up_id in ("run_investigation", "create_remediation_plan", "run_remediation"):
        turns[follow_up_id] = run_experience_center_turn(
            scenario_id, session_id=session_id, follow_up_id=follow_up_id
        ).model_dump()
    return turns


def test_all_ten_scenarios_are_specs() -> None:
    assert set(SPEC_IDS) == set(registered_spec_ids())
    assert len(SPEC_IDS) == 10


@pytest.mark.parametrize("scenario_id", SPEC_IDS)
def test_every_search_passes_the_real_validator(scenario_id: str) -> None:
    spec = spec_for(scenario_id)
    steps = [*spec.checks, *([spec.added_check] if spec.added_check else []), *spec.actions]
    for step in steps:
        if step.spl:
            result = validate_spl(step.spl, template_profile=spec.spl_profile)
            assert result["approved"], (step.id, result["reject_reasons"])
            assert "pgcil" not in step.spl
            assert validated_spl(spec, step.spl) == result["normalized_spl"]


@pytest.mark.parametrize("scenario_id", [sid for sid in SPEC_IDS if any(c.spl for c in spec_for(sid).checks)])
def test_governance_trace_reports_the_validated_search_never_the_candidate(scenario_id: str) -> None:
    turns = _walk(scenario_id)
    assert turns["plan"].get("execution") is None or not turns["plan"]["execution"].get("executed_spl")
    after = turns["run_investigation"]
    assert after["candidate_spl"]["execution_eligible"] is False
    assert after["spl_validation"]["execution_eligible"] is False
    assert after["execution"]["candidate_spl_not_executed"] is True
    assert after["execution"]["executed_spl"] == after["spl_validation"]["normalized_spl"]


@pytest.mark.parametrize(
    ("tier", "evidence", "priority"),
    [
        (0, "confirmed_compromise", "P1"),
        (1, "exploitation_confirmed", "P1"),
        (0, "unexplained_access", "P2"),
        (1, "exposure", "P2"),
        (1, "unauthorized_change", "P2"),
        (1, "attempted_misuse", "P3"),
        (2, "unexplained_access", "P3"),
        (2, "confirmed_compromise", "P3"),
        (0, "benign", "P4"),
    ],
)
def test_priority_policy_is_deterministic(tier: int, evidence: str, priority: str) -> None:
    result = E.incident_priority(asset_tier=tier, evidence_state=evidence)
    assert result["priority"] == priority
    assert result["rule"].startswith("SOC-POL-PRIO-01 rule ")


def test_unknown_evidence_state_fails_closed() -> None:
    with pytest.raises(ValueError):
        E.incident_priority(asset_tier=0, evidence_state="watch_fired")


def test_time_tokens_render_against_now() -> None:
    now = datetime(2026, 9, 25, 10, 0, tzinfo=timezone.utc)
    assert E.render_time_tokens("{D-9}", now=now) == "16 Sep"
    assert E.render_time_tokens("{D-9 03:12}", now=now) == "16 Sep 03:12"
    assert E.render_time_tokens("{D14}", now=now) == "9 Oct"
    assert E.render_time_tokens("{W30}", now=now) == "26 Aug – 25 Sep"


def test_s1_evidence_sits_inside_the_30_day_window() -> None:
    """The dates the S1 findings cite must fall inside the window the question asks about."""
    spec = spec_for("s1_governed_splunk_investigation")
    text = " ".join(" ".join([check.result, *check.evidence]) for check in spec.checks)
    import re

    offsets = [int(value) for value in re.findall(r"\{D(-\d+)", text)]
    assert offsets and min(offsets) >= -30 and max(offsets) <= 0


@pytest.mark.parametrize("scenario_id", SPEC_IDS)
def test_emails_go_to_allowlisted_team_mailboxes(scenario_id: str) -> None:
    for action in spec_for(scenario_id).actions:
        if action.email is not None:
            assert action.email.mailbox in LOGICAL_TEAMS


def test_s6_reuses_the_open_incident_and_opens_no_new_one() -> None:
    spec = spec_for("s6_investigation_continuity")
    assert spec.existing_incident == E.INCIDENT_S6_EXISTING
    assert not [action for action in spec.actions if action.verb == "incident"]
    final = _walk(spec.scenario_id)["run_remediation"]["ec_agent_workflow"]["final_summary"]
    assert any(E.INCIDENT_S6_EXISTING in (row["result"] or "") for row in final["actions"])


def test_s2_blocked_attempts_are_not_called_a_breach() -> None:
    conclusion = _walk("s2_ai_prompt_injection")["run_investigation"]["ec_agent_workflow"]["investigation_conclusion"]
    assert "breach" not in conclusion["headline"].lower()
    assert conclusion["assessment"]["incident_priority"] == "P3"


def test_s7_opens_no_incident_before_the_evidence() -> None:
    turns = _walk("s7_conflicting_ot_evidence")
    for stage in ("plan", "run_investigation", "create_remediation_plan"):
        assert turns[stage]["ec_actions"] == [], stage


def test_legacy_phrasings_still_resolve() -> None:
    for spec in ALL_SPECS:
        for phrase in spec.legacy_phrasings:
            assert resolve_ec_query_fuzzy(phrase)[0] == spec.scenario_id, phrase


def test_chatpanel_picker_keeps_the_q1_q2_legacy_entries() -> None:
    picker = {row["scenario_id"]: row for row in list_demo_scenarios()}
    for scenario_id in ("firewall_deny_coordinated_attack", "firewall_baseline_template_spl"):
        assert scenario_id in picker
        assert SCENARIOS[scenario_id].category == "Coordinated Firewall Incident"
    assert SCENARIOS["firewall_baseline_template_spl"].candidate_spl


@pytest.mark.parametrize("scenario_id", SPEC_IDS)
def test_spec_text_has_no_sample_or_harness_wording(scenario_id: str) -> None:
    import re
    from dataclasses import asdict

    blob = str(asdict(spec_for(scenario_id)))
    visible = blob.replace(str(spec_for(scenario_id).legacy_phrasings), "")
    assert not re.search(r"\bdemo\b|pgcil|Northwind|198\.51\.100|\bfixture\b|\bsimulated\b", visible, re.IGNORECASE)
