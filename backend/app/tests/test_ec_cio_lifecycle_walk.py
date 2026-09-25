"""Walk every /scenarios catalog question end-to-end and hold it to the SOC realism bar.

Plan: plans/2026-09-24_1635_ec-cio-coherence-and-lifecycle.md (A0.2; realism revamp R-items).

All ten questions run on the shared spec engine and are driven with their **default** step
selections: plan → run → proposed response → approve → execution and verification.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from app.demo.ec_agent.tool_catalog import resolve_tool_id
from app.demo.ec_turn import run_experience_center_turn

S1 = "s1_governed_splunk_investigation"
S2 = "s2_ai_prompt_injection"
S3 = "s3_firewall_team_coordination"
S4 = "s4_zero_day_no_playbook"
S5 = "s5_cisco_hardening_remediation"
S6 = "s6_investigation_continuity"
S7 = "s7_conflicting_ot_evidence"
Q1 = "firewall_deny_coordinated_attack"
Q2 = "firewall_baseline_template_spl"
R1 = "r1_rag_privileged_success_after_failure"

AGENT_SCENARIOS = (S1, S2, S3, S4, S5, S6, S7, R1, Q1, Q2)

# Words that describe the demo harness rather than the investigation.
DEMO_WORDS = re.compile(
    r"\bfixture\b|\bsimulated\b|Experience Center|Scenario: S\d|ZD-FIXTURE|\(if checked\)"
    r"|\bonboarded\b|non-executable|\blive (?:MCP|LLM)\b|\bdemo\b|pgcil|Northwind|198\.51\.100",
    re.IGNORECASE,
)


def _steps(container: Any) -> list[dict[str, Any]]:
    if isinstance(container, dict):
        return [step for step in container.get("steps") or [] if isinstance(step, dict)]
    return []


def _default_ids(workflow: dict[str, Any], key: str) -> list[str]:
    return [step["id"] for step in _steps(workflow.get(key)) if step.get("default_selected", step.get("selected"))]


def walk_agent(scenario_id: str) -> list[tuple[str, dict[str, Any]]]:
    """Plan → run (defaults) → HIL approve if asked → remediation plan → approve (defaults)."""
    turns: list[tuple[str, dict[str, Any]]] = []
    response = run_experience_center_turn(scenario_id, session_id=None).model_dump()
    session_id = response["ec_session_state"]["session_id"]
    turns.append(("plan", response))

    def step(follow_up_id: str, payload: dict[str, Any] | None = None) -> None:
        nonlocal response
        response = run_experience_center_turn(
            scenario_id, session_id=session_id, follow_up_id=follow_up_id, agent_payload=payload
        ).model_dump()
        turns.append((follow_up_id, response))

    step("run_investigation", {"selected_step_ids": _default_ids(response["ec_agent_workflow"], "investigation_plan")})
    if response.get("ec_agent_lifecycle") == "INVESTIGATION_NEEDS_APPROVAL":
        hil = response["ec_agent_workflow"].get("hil_prompt") or {}
        step(hil.get("approve_follow_up_id") or "approve_investigation_vuln_scan")
    step("create_remediation_plan")
    step("run_remediation", {"selected_step_ids": _default_ids(response["ec_agent_workflow"], "remediation_plan")})
    return turns


def _turn(turns: list[tuple[str, dict[str, Any]]], lifecycle: str) -> dict[str, Any]:
    for _, response in turns:
        if response.get("ec_agent_lifecycle") == lifecycle:
            return response
    raise AssertionError(f"lifecycle {lifecycle} never reached: {[r.get('ec_agent_lifecycle') for _, r in turns]}")


def _emails(obj: Any, found: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(obj, dict):
        if "subject" in obj and ("body" in obj or "body_text" in obj):
            if obj.get("subject") not in [item.get("subject") for item in found]:
                found.append(obj)
        for value in obj.values():
            _emails(value, found)
    elif isinstance(obj, list):
        for value in obj:
            _emails(value, found)
    return found


def _analyst_visible_text(response: dict[str, Any]) -> list[tuple[str, str]]:
    """Text a viewer reads on the page (not the transparency drawer)."""
    out: list[tuple[str, str]] = []
    workflow = response.get("ec_agent_workflow") or {}
    for key in ("opening_narrative",):
        if workflow.get(key):
            out.append((key, str(workflow[key])))
    for line in (workflow.get("brief") or {}).get("what_i_know") or []:
        out.append(("brief", str(line)))
    for container in ("investigation_plan", "remediation_plan", "investigation_results", "remediation_results"):
        for item in _steps(workflow.get(container)):
            for field in ("title", "summary", "rationale"):
                if item.get(field):
                    out.append((f"{container}.{item['id']}.{field}", str(item[field])))
            if item.get("result"):
                out.append((f"{container}.{item['id']}.result", str(item["result"])))
            finding = item.get("finding") or {}
            headline = finding.get("headline_finding")
            if headline:
                out.append((f"{container}.{item['id']}.finding", str(headline)))
            for line in finding.get("key_evidence") or []:
                out.append((f"{container}.{item['id']}.key_evidence", str(line)))
            if finding.get("caveat"):
                out.append((f"{container}.{item['id']}.caveat", str(finding["caveat"])))
    conclusion = workflow.get("investigation_conclusion") or {}
    for point in [conclusion.get("headline"), *(conclusion.get("narrative_points") or [])]:
        if point:
            out.append(("conclusion", str(point)))
    for key in ("remediation_conclusion",):
        block = workflow.get(key) or {}
        for point in [block.get("headline"), *(block.get("narrative_points") or [])]:
            if point:
                out.append((key, str(point)))
    for row in workflow.get("verification") or []:
        out.append(("verification", f"{row.get('item')} {row.get('detail')}"))
    for line in workflow.get("executive_summary") or []:
        out.append(("executive_summary", str(line)))
    for key in ("investigation_summary", "remediation_summary"):
        for metric in (workflow.get(key) or {}).get("metrics") or []:
            out.append((key, f"{metric.get('label')} {metric.get('value')}"))
    final = workflow.get("final_summary") or {}
    for point in [final.get("headline"), final.get("risk_note"), *(final.get("completed") or []), *(final.get("in_progress") or [])]:
        if point:
            out.append(("final_summary", str(point)))
    for index, email in enumerate(_emails(response, [])):
        out.append((f"email[{index}].subject", str(email.get("subject") or "")))
        out.append((f"email[{index}].body", str(email.get("body") or email.get("body_text") or "")))
    return out


@pytest.fixture(scope="module")
def agent_walks() -> dict[str, list[tuple[str, dict[str, Any]]]]:
    return {scenario_id: walk_agent(scenario_id) for scenario_id in AGENT_SCENARIOS}


# ---------------------------------------------------------------- lifecycle


@pytest.mark.parametrize("scenario_id", AGENT_SCENARIOS)
def test_agent_scenario_reaches_complete_with_default_plan(agent_walks, scenario_id):
    assert _turn(agent_walks[scenario_id], "COMPLETE")


@pytest.mark.parametrize("scenario_id", AGENT_SCENARIOS)
def test_agent_mode_emits_no_chips_before_completion(agent_walks, scenario_id):
    for name, response in agent_walks[scenario_id]:
        assert response["ec_followups"] == [], name


@pytest.mark.parametrize("scenario_id", AGENT_SCENARIOS)
def test_nothing_executes_before_plan_approval(agent_walks, scenario_id):
    for lifecycle in ("PLAN_READY", "INVESTIGATION_COMPLETE", "REMEDIATION_PLAN_READY"):
        assert _turn(agent_walks[scenario_id], lifecycle)["ec_actions"] == [], lifecycle


@pytest.mark.parametrize("scenario_id", AGENT_SCENARIOS)
def test_plan_is_short(agent_walks, scenario_id):
    plan = _turn(agent_walks[scenario_id], "PLAN_READY")["ec_agent_workflow"]
    checks = [step for step in _steps(plan["investigation_plan"]) if step.get("selected")]
    assert 2 <= len(checks) <= 3, [step["id"] for step in checks]
    actions = _steps(_turn(agent_walks[scenario_id], "REMEDIATION_PLAN_READY")["ec_agent_workflow"]["remediation_plan"])
    assert 1 <= len(actions) <= 5


@pytest.mark.parametrize("scenario_id", AGENT_SCENARIOS)
def test_every_step_says_what_it_does_and_which_tool(agent_walks, scenario_id):
    plan = _turn(agent_walks[scenario_id], "PLAN_READY")["ec_agent_workflow"]
    missing = [step["id"] for step in _steps(plan["investigation_plan"]) if not (step.get("summary") and step.get("tools"))]
    assert missing == []
    remediation = _turn(agent_walks[scenario_id], "REMEDIATION_PLAN_READY")["ec_agent_workflow"]
    missing = [step["id"] for step in _steps(remediation["remediation_plan"]) if not (step.get("summary") and step.get("tools"))]
    assert missing == []


@pytest.mark.parametrize("scenario_id", AGENT_SCENARIOS)
def test_actions_are_pending_until_approved(agent_walks, scenario_id):
    proposed = _steps(_turn(agent_walks[scenario_id], "REMEDIATION_PLAN_READY")["ec_agent_workflow"]["remediation_plan"])
    assert {step["status"] for step in proposed} == {"PROPOSED"}
    assert {step["status_label"] for step in proposed} == {"Pending approval"}
    assert all(step["result"] is None for step in proposed)
    done = _steps(_turn(agent_walks[scenario_id], "COMPLETE")["ec_agent_workflow"]["remediation_plan"])
    assert all(step["status"] in {"EXECUTED", "VERIFIED", "REQUESTED", "SCHEDULED", "AWAITING_REPLY"} for step in done)


_BEFORE_EXECUTION = re.compile(
    r"watch is live|watch live|incident opened|email sent|change completed|\bopened \(P\d\)", re.IGNORECASE
)


@pytest.mark.parametrize("scenario_id", AGENT_SCENARIOS)
def test_no_ticket_id_or_done_claim_before_execution(agent_walks, scenario_id):
    from app.demo.ec_agent.spec_engine import spec_for

    spec = spec_for(scenario_id)
    created = {action.ticket_id for action in spec.actions if action.ticket_id}
    for lifecycle in ("PLAN_READY", "INVESTIGATION_COMPLETE", "REMEDIATION_PLAN_READY"):
        text = str(_turn(agent_walks[scenario_id], lifecycle)["ec_agent_workflow"])
        assert [ticket for ticket in created if ticket in text] == [], lifecycle
        assert not _BEFORE_EXECUTION.search(text), lifecycle


@pytest.mark.parametrize("scenario_id", AGENT_SCENARIOS)
def test_final_state_is_not_closed_while_work_is_pending(agent_walks, scenario_id):
    final = _turn(agent_walks[scenario_id], "COMPLETE")["ec_agent_workflow"]["final_summary"]
    assert final["title"] and "COMPLETE" not in final["title"].upper().split(" — ")[0]
    if final["in_progress"]:
        assert not final["title"].upper().startswith(("CLOSED", "RESOLVED"))


def test_s4_uses_agilus_for_versions_and_the_approved_workaround(agent_walks):
    complete = _turn(agent_walks[S4], "COMPLETE")["ec_agent_workflow"]
    checks = {step["id"]: step for step in complete["investigation_results"]["steps"]}
    assert checks["affected_versions"]["tool_ids"] == ["agilus_mcp"]
    workaround = next(step for step in complete["remediation_plan"]["steps"] if step["id"] == "apply_workaround")
    assert workaround["tool_ids"] == ["agilus_mcp"] and workaround["status"] == "VERIFIED"


def test_s7_finds_a_live_device_not_a_recycled_identity(agent_walks):
    conclusion = _turn(agent_walks[S7], "INVESTIGATION_COMPLETE")["ec_agent_workflow"]["investigation_conclusion"]
    assert "still live" in conclusion["headline"].lower()
    assert "not an incident" not in conclusion["headline"].lower()


@pytest.mark.parametrize("scenario_id", AGENT_SCENARIOS)
def test_every_scenario_is_on_agent_lifecycle(scenario_id):
    response = run_experience_center_turn(scenario_id, session_id=None).model_dump()
    assert response.get("ec_agent_lifecycle") == "PLAN_READY"


# ---------------------------------------------------------------- findings


@pytest.mark.parametrize("scenario_id", [sid for sid in AGENT_SCENARIOS if sid != Q2])
def test_priority_and_threat_are_separate_and_policy_based(agent_walks, scenario_id):
    conclusion = _turn(agent_walks[scenario_id], "INVESTIGATION_COMPLETE")["ec_agent_workflow"]["investigation_conclusion"]
    assessment = conclusion["assessment"]
    assert assessment["incident_priority"] in {"P1", "P2", "P3", "P4"}
    assert assessment["priority_rule"].startswith("SOC-POL-PRIO-01 rule ")
    assert assessment["threat_assessment"] in {"Confirmed", "Suspected", "Unconfirmed", "Benign", "Insufficient evidence"}


@pytest.mark.parametrize("scenario_id", (S1, S2, S4, S5, S6, S7, Q1))
def test_the_agent_adds_a_check_when_evidence_asks_for_it(agent_walks, scenario_id):
    results = _turn(agent_walks[scenario_id], "INVESTIGATION_COMPLETE")["ec_agent_workflow"]["investigation_results"]["steps"]
    assert [step["id"] for step in results if step.get("added_by_agent")], scenario_id


def test_no_check_is_added_when_its_trigger_did_not_run():
    first = run_experience_center_turn(S1, session_id=None).model_dump()
    session_id = first["ec_session_state"]["session_id"]
    after = run_experience_center_turn(
        S1, session_id=session_id, follow_up_id="run_investigation", agent_payload={"selected_step_ids": ["who_owns_ip", "sop"]}
    ).model_dump()
    assert not [step for step in after["ec_agent_workflow"]["investigation_results"]["steps"] if step.get("added_by_agent")]


@pytest.mark.parametrize("scenario_id", AGENT_SCENARIOS)
def test_every_tool_resolves_to_the_catalog(agent_walks, scenario_id):
    workflow = _turn(agent_walks[scenario_id], "REMEDIATION_PLAN_READY")["ec_agent_workflow"]
    unknown = sorted(
        {
            label
            for container in ("investigation_plan", "remediation_plan")
            for step in _steps(workflow.get(container))
            for label in step.get("tools") or []
            if resolve_tool_id(label) is None
        }
    )
    assert unknown == []
    used = {tool["tool_id"] for tool in workflow.get("tool_fabric") or [] if tool["used"]}
    assert used and used <= {"splunk_mcp", "agilus_mcp", "soc_kb", "itsm", "email", "spl_validator"}


@pytest.mark.parametrize("scenario_id", AGENT_SCENARIOS)
def test_no_demo_words_in_analyst_visible_text(agent_walks, scenario_id):
    hits = [
        (where, DEMO_WORDS.search(text).group(0))
        for _, response in agent_walks[scenario_id]
        for where, text in _analyst_visible_text(response)
        if DEMO_WORDS.search(text)
    ]
    assert hits == []


@pytest.mark.parametrize("scenario_id", AGENT_SCENARIOS)
def test_dates_are_rendered(agent_walks, scenario_id):
    for name, response in agent_walks[scenario_id]:
        assert not re.search(r"\{D-?\d+|\{W\d+|\{incident\}|\{ticket:", str(response)), name


# ---------------------------------------------------------------- storyline


def test_s1_q1_s3_state_the_same_facts(agent_walks):
    """Same IP, jump host, account and incident in every question of the jump-host thread."""
    blobs = {sid: str(_turn(agent_walks[sid], "COMPLETE")) for sid in (S1, Q1, S3)}
    for fact in ("45.xx.xx.42", "JMP-ADM-01", "INC0048213"):
        missing = [scenario_id for scenario_id, blob in blobs.items() if fact not in blob]
        assert missing == [], (fact, missing)
    assert all("svc_netops" in blobs[sid] for sid in (Q1, S3))
    assert all("ACL-PARTNER-0147" in blobs[sid] for sid in (S1, S3))


def test_no_scripted_story_thread():
    for scenario_id in (S1, Q1, S3):
        assert run_experience_center_turn(scenario_id, session_id=None).model_dump().get("ec_story_thread") is None


def test_monitoring_hit_does_not_auto_block(agent_walks):
    final = _turn(agent_walks[Q1], "COMPLETE")["ec_agent_workflow"]
    assert not [step for step in final["remediation_plan"]["steps"] if "block" in step["id"] and step["status"] != "AWAITING_REPLY"]
    assert any("approval" in item.lower() for item in final["final_summary"]["deferred"])


# ---------------------------------------------------------------- plan stage (visual walkthrough F1/F2)

_VERDICT_WORDS = re.compile(r"not confirmed|confirmed|blocked|contained|malicious use|breach", re.IGNORECASE)
_EXECUTION_WORDS = re.compile(r"executing|executed|no alert|polling|search returned|validated", re.IGNORECASE)


@pytest.mark.parametrize("scenario_id", AGENT_SCENARIOS)
def test_plan_stage_states_no_verdict_and_runs_nothing(agent_walks, scenario_id):
    plan = _turn(agent_walks[scenario_id], "PLAN_READY")
    title = (plan.get("analyst_response") or {}).get("finding_title") or ""
    assert not _VERDICT_WORDS.search(title), title
    journey = plan.get("ec_execution_journey") or {}
    text = " ".join(
        f"{stage.get('title', '')} {' '.join(stage.get('activity') or [])}" for stage in journey.get("stages") or []
    )
    assert not _EXECUTION_WORDS.search(text), text
