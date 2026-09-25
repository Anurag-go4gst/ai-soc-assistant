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


_TEAM_MAILBOXES = ("FIREWALL_TEAM", "APPSEC_TEAM", "NETWORK_TEAM", "INCIDENT_OWNER", "OT_TEAM", "SOC_LEAD", "SOC_TIER2")


@pytest.fixture(scope="module", autouse=True)
def configured_mail():
    """Team mailboxes mapped and allowlisted; pytest uses the fake transport, so nothing leaves."""
    with pytest.MonkeyPatch.context() as patch:
        for team in _TEAM_MAILBOXES:
            patch.setenv(f"AI_SOC_EC_EMAIL_{team}", f"{team.lower()}@soc.test")
        patch.setenv("AI_SOC_EC_EMAIL_ALLOWLIST_DOMAINS", "soc.test")
        patch.setenv("AI_SOC_EC_EMAIL_TRANSPORT", "fake")
        yield


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


def _to_proposed_response(scenario_id: str) -> str:
    first = run_experience_center_turn(scenario_id, session_id=None).model_dump()
    session_id = first["ec_session_state"]["session_id"]
    for follow_up_id in ("run_investigation", "create_remediation_plan"):
        run_experience_center_turn(scenario_id, session_id=session_id, follow_up_id=follow_up_id)
    return session_id


def _approve(scenario_id: str, session_id: str, **payload) -> dict:
    return run_experience_center_turn(
        scenario_id, session_id=session_id, follow_up_id="run_remediation", agent_payload=payload
    ).model_dump()


S1_ID = "s1_governed_splunk_investigation"


def test_priority_control_offered_on_the_incident_before_approval() -> None:
    session_id = _to_proposed_response(S1_ID)
    plan = run_experience_center_turn(S1_ID, session_id=session_id, follow_up_id="update_remediation_plan").model_dump()
    incident = next(step for step in plan["ec_agent_workflow"]["remediation_plan"]["steps"] if step["id"] == "open_incident")
    control = incident["priority_control"]
    assert control["policy_priority"] == "P2" and control["selected"] == "P2"
    assert control["options"] == ["P1", "P2", "P3", "P4"]


def test_priority_change_without_reason_is_refused_and_nothing_runs() -> None:
    session_id = _to_proposed_response(S1_ID)
    after = _approve(S1_ID, session_id, priority_override={"priority": "P1", "reason": "  "})
    assert after["ec_agent_lifecycle"] == "REMEDIATION_PLAN_READY"
    assert "reason" in after["ec_agent_workflow"]["remediation_plan"]["error"].lower()
    assert after["ec_actions"] == []


def test_priority_override_with_reason_is_recorded_on_the_ticket() -> None:
    session_id = _to_proposed_response(S1_ID)
    after = _approve(S1_ID, session_id, priority_override={"priority": "P1", "reason": "Jump host is in scope of an active audit"})
    workflow = after["ec_agent_workflow"]
    final = workflow["final_summary"]
    assert final["assessment"]["incident_priority"] == "P1"
    assert final["assessment"]["priority_override"] == {"policy_priority": "P2", "reason": "Jump host is in scope of an active audit"}
    incident = next(row for row in final["actions"] if row["ticket"] and row["ticket"]["type"] == "Incident")
    assert incident["title"] == "Open a P1 incident"
    assert incident["ticket"]["priority"].startswith("P1 (analyst override of policy P2: Jump host")
    # The findings keep the policy priority; the override belongs to the ticket.
    assert workflow["investigation_conclusion"]["assessment"]["incident_priority"] == "P2"


def test_ticket_records_exist_only_after_execution() -> None:
    session_id = _to_proposed_response(S1_ID)
    before = run_experience_center_turn(S1_ID, session_id=session_id, follow_up_id="update_remediation_plan").model_dump()
    assert not [s for s in before["ec_agent_workflow"]["remediation_plan"]["steps"] if s["finding"]["details"].get("ticket")]
    final = _approve(S1_ID, session_id)["ec_agent_workflow"]["final_summary"]
    tickets = {row["ticket"]["number"]: row["ticket"] for row in final["actions"] if row["ticket"]}
    incident = tickets[E.INCIDENT_S1]
    assert incident["state"] == "New" and incident["assignment_group"] == "SOC Tier 2"
    assert E.TASK_S1_DETECTION in incident["related"]
    request = tickets[E.TASK_S1_DETECTION]
    assert request["assignment_group"] == "Detection Engineering"
    assert request["parent"] == E.INCIDENT_S1
    assert request["attachment"].startswith("search index=netfw")


def test_email_is_really_sent_with_cc_and_message_id() -> None:
    session_id = _to_proposed_response(S1_ID)
    final = _approve(S1_ID, session_id)["ec_agent_workflow"]["final_summary"]
    email = next(row for row in final["actions"] if row["email"])
    delivery = email["email_delivery"]
    assert delivery["sent"] is True
    assert delivery["to_address"] == "incident_owner@soc.test"
    assert delivery["cc_addresses"] == ["network_team@soc.test"]
    assert delivery["message_id"]
    assert E.INCIDENT_S1 in email["email"]["body"]


def test_unconfigured_email_is_reported_not_sent(monkeypatch) -> None:
    monkeypatch.delenv("AI_SOC_EC_EMAIL_INCIDENT_OWNER", raising=False)
    session_id = _to_proposed_response(S1_ID)
    after = _approve(S1_ID, session_id)
    assert after["ec_agent_lifecycle"] == "PARTIAL"
    final = after["ec_agent_workflow"]["final_summary"]
    email = next(row for row in final["actions"] if row["email"])
    assert email["status"] == "NOT_SENT" and email["status_label"] == "Not sent"
    assert email["result"] == "Not sent — outbound email is not configured"
    assert final["title"].startswith("PARTIALLY COMPLETE")
