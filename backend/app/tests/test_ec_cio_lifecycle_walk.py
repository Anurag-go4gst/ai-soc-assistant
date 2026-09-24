"""Walk every /scenarios catalog question end-to-end and hold it to the CIO bar.

Plan: plans/2026-09-24_1635_ec-cio-coherence-and-lifecycle.md (item A0.2).

Agent scenarios are driven with their **default** step selections (the first review pass
selected every step, which forced S7 onto Path B and skipped S4's Agilus HIL — a harness
artifact, not a product defect). Anything not yet fixed is ``xfail(strict=True)`` with the
plan item that fixes it, so each fix flips exactly one expectation.
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

AGENT_SCENARIOS = (S1, S2, S4, S7, R1)
LEGACY_LIFECYCLE_SCENARIOS = (S3, S5, S6, Q1)

# Words that describe the demo harness rather than the investigation.
DEMO_WORDS = re.compile(
    r"\bfixture\b|\bsimulated\b|Experience Center|Scenario: S\d|ZD-FIXTURE|\(if checked\)"
    r"|\bonboarded\b|non-executable|\blive (?:MCP|LLM)\b",
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
    lifecycles = [response.get("ec_agent_lifecycle") for _, response in agent_walks[scenario_id]]
    assert lifecycles[0] == "PLAN_READY"
    assert "INVESTIGATION_COMPLETE" in lifecycles
    assert "REMEDIATION_PLAN_READY" in lifecycles
    assert lifecycles[-1] == "COMPLETE"


@pytest.mark.parametrize("scenario_id", AGENT_SCENARIOS)
def test_agent_mode_emits_no_chips_before_completion(agent_walks, scenario_id):
    turns = agent_walks[scenario_id]
    for lifecycle in ("PLAN_READY", "INVESTIGATION_COMPLETE"):
        assert _turn(turns, lifecycle)["ec_followups"] == [], lifecycle


@pytest.mark.parametrize("scenario_id", AGENT_SCENARIOS)
def test_nothing_executes_before_plan_approval(agent_walks, scenario_id):
    assert _turn(agent_walks[scenario_id], "PLAN_READY")["ec_actions"] == []


def test_s4_default_plan_stops_for_agilus_approval(agent_walks):
    lifecycles = [response.get("ec_agent_lifecycle") for _, response in agent_walks[S4]]
    assert "INVESTIGATION_NEEDS_APPROVAL" in lifecycles


def test_s7_default_path_is_live_device_not_recycled_identity(agent_walks):
    conclusion = _turn(agent_walks[S7], "INVESTIGATION_COMPLETE")["ec_agent_workflow"]["investigation_conclusion"]
    assert "active" in conclusion["headline"].lower()
    assert "not an incident" not in conclusion["headline"].lower()


@pytest.mark.parametrize(
    "scenario_id",
    [pytest.param(sid, marks=pytest.mark.xfail(strict=True, reason="Release B: lifecycle adoption")) for sid in LEGACY_LIFECYCLE_SCENARIOS],
)
def test_legacy_scenario_is_on_agent_lifecycle(scenario_id):
    response = run_experience_center_turn(scenario_id, session_id=None).model_dump()
    assert response.get("ec_agent_lifecycle") == "PLAN_READY"


# ---------------------------------------------------------------- CIO content


@pytest.mark.parametrize("scenario_id", AGENT_SCENARIOS)
def test_every_plan_step_says_why(agent_walks, scenario_id):
    plan = _turn(agent_walks[scenario_id], "PLAN_READY")["ec_agent_workflow"]
    missing = [step["id"] for step in _steps(plan["investigation_plan"]) if not (step.get("rationale") and step.get("decides"))]
    assert missing == [], f"investigation steps without rationale/decides: {missing}"

    remediation = _turn(agent_walks[scenario_id], "REMEDIATION_PLAN_READY")["ec_agent_workflow"]
    rem_steps = _steps(remediation.get("remediation_results")) or _steps(remediation["remediation_plan"])
    missing = [
        step["id"]
        for step in rem_steps
        if not (step.get("rationale") and step.get("reversible") and step.get("approver"))
    ]
    assert missing == [], f"remediation steps without rationale/reversible/approver: {missing}"


@pytest.mark.parametrize("scenario_id", AGENT_SCENARIOS)
def test_executive_brief_at_outcome_and_close(agent_walks, scenario_id):
    for lifecycle in ("INVESTIGATION_COMPLETE", "COMPLETE"):
        brief = _turn(agent_walks[scenario_id], lifecycle)["ec_agent_workflow"].get("executive_brief") or {}
        assert brief.get("verdict"), lifecycle
        assert brief.get("decision_needed"), lifecycle
        assert brief.get("business_impact"), lifecycle


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
    assert any(tool["used"] for tool in workflow.get("tool_fabric") or [])


@pytest.mark.parametrize("scenario_id", AGENT_SCENARIOS)
def test_no_demo_words_in_analyst_visible_text(agent_walks, scenario_id):
    hits = [
        (where, DEMO_WORDS.search(text).group(0))
        for _, response in agent_walks[scenario_id]
        for where, text in _analyst_visible_text(response)
        if DEMO_WORDS.search(text)
    ]
    assert hits == []


# ---------------------------------------------------------------- storyline


def test_s1_q1_s3_share_one_incident_thread():
    ids = set()
    for scenario_id in (S1, Q1, S3):
        response = run_experience_center_turn(scenario_id, session_id=None).model_dump()
        thread = response.get("ec_story_thread") or (response.get("ec_agent_workflow") or {}).get("story_thread") or {}
        ids.add(thread.get("thread_id"))
    assert len(ids) == 1 and None not in ids


def test_s1_q1_s3_state_the_same_facts():
    """Same IP, jump host, account and incident id in every question of the thread."""
    blobs = {}
    for scenario_id in (S1, Q1, S3):
        response = run_experience_center_turn(scenario_id, session_id=None).model_dump()
        blobs[scenario_id] = str(response)
    for fact in ("198.51.100.42", "10.20.1.10", "svc_jump_ops", "INC-2026-89412"):
        missing = [scenario_id for scenario_id, blob in blobs.items() if fact not in blob]
        assert missing == [], (fact, missing)
    assert "FW-INC-2026-0615" not in "".join(blobs.values())


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
    thread = plan.get("ec_story_thread")
    if thread:
        assert "not investigated yet" in thread["verdict_so_far"].lower()


def test_q1_follow_up_findings_are_visible_and_grow():
    first = run_experience_center_turn(Q1, session_id=None).model_dump()
    session_id = first["ec_session_state"]["session_id"]
    assert not (first["analyst_response"] or {}).get("follow_up_findings")
    after = run_experience_center_turn(Q1, session_id=session_id, follow_up_id="check_identity").model_dump()
    findings = after["analyst_response"]["follow_up_findings"]
    assert len(findings) == 1 and "svc_jump_ops" in findings[0]
    assert "check_identity" not in [chip["follow_up_id"] for chip in after["ec_followups"]]
