"""S4 investigation polish — content consistency and agent adaptation."""

from __future__ import annotations

from app.demo.ec_turn import run_experience_center_turn
from app.demo.fixtures.s4.investigation_findings import S4_AFFECTED_ASSETS
from app.demo.fixtures.s4.pack import S4_SCENARIO_ID
from app.tests.test_s4_zero_day_no_playbook import _inv_steps


def _run_investigation_complete(session_id: str) -> dict:
    run_experience_center_turn(S4_SCENARIO_ID, session_id=session_id)
    run_experience_center_turn(
        S4_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="run_investigation",
        agent_payload={"selected_step_ids": [step["id"] for step in _inv_steps()]},
    )
    return run_experience_center_turn(
        S4_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="skip_investigation_vuln_scan",
    ).model_dump()


def test_complete_investigation_steps_have_findings() -> None:
    envelope = _run_investigation_complete("s4-findings")
    steps = envelope["ec_agent_workflow"]["investigation_results"]["steps"]
    for step in steps:
        if step.get("status") == "COMPLETE":
            finding = step.get("finding") or {}
            headline = finding.get("headline_finding") or ""
            assert headline and headline != "—"
            assert not headline.startswith("Skipped")


def test_investigation_metrics_consistent() -> None:
    envelope = _run_investigation_complete("s4-metrics")
    summary = envelope["ec_agent_workflow"]["investigation_summary"]
    assert summary["metrics"][0]["value"] == 12
    assert summary["metrics"][1]["value"] == 4
    assert summary["metrics"][2]["value"] == 2
    assert summary["metrics"][3]["value"] == 0


def test_agilus_patch_scope_all_affected_assets() -> None:
    session_id = "s4-agilus-scope"
    run_experience_center_turn(S4_SCENARIO_ID, session_id=session_id)
    run_experience_center_turn(
        S4_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="run_investigation",
        agent_payload={"selected_step_ids": [step["id"] for step in _inv_steps()]},
    )
    envelope = run_experience_center_turn(
        S4_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="approve_investigation_vuln_scan",
    ).model_dump()
    normalized = envelope["ec_agent_workflow"]["normalized_state"]
    assert normalized["patch_scope_asset_ids"] == list(S4_AFFECTED_ASSETS)


def test_remediation_plan_auto_visible_after_investigation() -> None:
    envelope = _run_investigation_complete("s4-auto-rem")
    assert envelope["ec_agent_lifecycle"] == "INVESTIGATION_COMPLETE"
    workflow = envelope["ec_agent_workflow"]
    assert workflow["remediation_offer"] is None
    assert not workflow["remediation_plan"]["visible"]
    assert workflow["phase"] == "investigation_complete"
    assert workflow.get("next_step_cta") is not None

    ready = run_experience_center_turn(
        S4_SCENARIO_ID,
        session_id="s4-auto-rem",
        follow_up_id="create_remediation_plan",
    ).model_dump()
    assert ready["ec_agent_lifecycle"] == "REMEDIATION_PLAN_READY"
    assert ready["ec_agent_workflow"]["remediation_plan"]["visible"] is True
    assert ready["ec_agent_workflow"]["phase"] == "remediation"
    submit = next(step for step in ready["ec_agent_workflow"]["remediation_plan"]["steps"] if step["id"] == "submit_patch")
    assert "EG-VPN-12.3.5-EMERG" in (submit.get("finding") or {}).get("headline_finding", "")
    assert "VPN-GW-08" in (submit.get("finding") or {}).get("affected_entities", [])


def test_remediation_plan_has_email_and_patch_scope() -> None:
    _run_investigation_complete("s4-rem-content")
    ready = run_experience_center_turn(
        S4_SCENARIO_ID,
        session_id="s4-rem-content",
        follow_up_id="create_remediation_plan",
    ).model_dump()
    workflow = ready["ec_agent_workflow"]
    assert workflow.get("remediation_summary")
    assert workflow.get("remediation_conclusion", {}).get("narrative_points")
    steps = workflow["remediation_results"]["steps"]
    notify = next(step for step in steps if step["id"] == "notify_stakeholders")
    assert notify["finding"]["details"]["email_draft"]["subject"]
    assert notify["status"] == "QUEUED"
    assert "after upstream" in notify["finding"]["headline_finding"].lower()
    mfa = next(step for step in steps if step["id"] == "enforce_mfa")
    assert mfa["execution_channel"] == "email_escalation"
    assert mfa["finding"]["details"]["email_draft"]["body"]
    assert mfa["finding"]["details"]["email_extra"]
    incident = next(step for step in steps if step["id"] == "create_incident")
    assert incident["finding"]["details"]["ticket_detail"]["ticket_id"] == "INC-48219"
    wan = next(step for step in steps if step["id"] == "restrict_wan")
    assert wan["execution_channel"] == "email_escalation"
    assert wan["finding"]["details"]["email_draft"]["subject"]
    patch = next(step for step in steps if step["id"] == "submit_patch")
    assert "VPN-GW-08" in patch["finding"]["affected_entities"]
    change = next(step for step in steps if step["id"] == "create_change")
    assert "CHG-29173" in change["finding"]["headline_finding"]


def test_agent_added_step_visible_with_finding() -> None:
    envelope = _run_investigation_complete("s4-agent-adapt")
    steps = envelope["ec_agent_workflow"]["investigation_results"]["steps"]
    added = next((step for step in steps if step.get("added_by_agent")), None)
    assert added is not None
    assert added["status"] == "COMPLETE"
    assert added["finding"]["headline_finding"]
    assert added["finding"].get("attention_state") == "ATTENTION"


def test_conclusion_uses_vulnerable_not_compromised_language() -> None:
    envelope = _run_investigation_complete("s4-conclusion")
    conclusion = envelope["ec_agent_workflow"]["investigation_conclusion"]
    headline = conclusion["headline"]
    assert "vulnerable" in headline
    assert "compromised" not in headline.lower()
    assert len(conclusion.get("narrative_points") or []) >= 3


def test_no_default_executive_summary() -> None:
    envelope = _run_investigation_complete("s4-no-exec")
    assert envelope["ec_agent_workflow"]["executive_summary"] == []
