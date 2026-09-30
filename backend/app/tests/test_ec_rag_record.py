"""R1 procedure answer: a chunk-level retrieval record that adds up, cited on every step.

Plan: plans/2026-09-29_1536_ec-r1-rag-procedure-question.md (items 1, 2, 4, 9).
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

import pytest

from app.config import Settings
from app.demo import ec_environment as E
from app.demo.ec_agent.rag_record import RagExclusion, answer_lines, check_rag_record
from app.demo.ec_query_match import resolve_ec_query_fuzzy
from app.demo.fixtures.specs import ALL_SPECS
from app.demo.fixtures.specs.r1_sop_answer import R1, RETRIEVAL
from app.tests.test_ec_cio_lifecycle_walk import configured_mail, walk_agent  # noqa: F401  (module fixture)

OLD_QUESTION = (
    "A privileged database admin account logged in successfully after repeated failed logins. What does our "
    "SOP require, and who do we need to escalate to?"
)
NEW_QUESTION = (
    "r.mehta from Finance reported a phishing email and says they clicked the link. What does our phishing "
    "procedure say we should do?"
)


def _check(record: Any, points: tuple[str, ...] | None = None) -> None:
    check_rag_record(record, points=answer_lines(record) if points is None else points, owner="test")


# --- the record must add up -------------------------------------------------------------------


def test_r1_record_is_consistent() -> None:
    _check(RETRIEVAL, points=R1.points)


def test_unknown_citation_is_rejected() -> None:
    bad = replace(RETRIEVAL, escalation=replace(RETRIEVAL.escalation, cites=("PH-99",)))
    with pytest.raises(ValueError, match="unknown chunk"):
        _check(bad)


def test_step_without_citation_is_rejected() -> None:
    bad = replace(RETRIEVAL, steps=(*RETRIEVAL.steps[:-1], replace(RETRIEVAL.steps[-1], cites=())))
    with pytest.raises(ValueError, match="no citation"):
        _check(bad)


def test_unsorted_rerank_is_rejected() -> None:
    chunks = list(RETRIEVAL.chunks)
    chunks[0], chunks[1] = chunks[1], chunks[0]
    with pytest.raises(ValueError, match="rerank"):
        _check(replace(RETRIEVAL, chunks=tuple(chunks)))


def test_answering_from_an_excluded_version_is_rejected() -> None:
    primary = RETRIEVAL.documents[0]
    exclusion = RagExclusion("superseded", 1, primary.doc_id, primary.version, "same version")
    with pytest.raises(ValueError, match="excluded document version"):
        _check(replace(RETRIEVAL, exclusions=(*RETRIEVAL.exclusions, exclusion)))


def test_citing_a_chunk_marked_not_used_is_rejected() -> None:
    bad = replace(RETRIEVAL, escalation=replace(RETRIEVAL.escalation, cites=("PH-02", "5.1")))
    with pytest.raises(ValueError, match="marked not used"):
        _check(bad)


def test_points_must_match_the_answer() -> None:
    with pytest.raises(ValueError, match="differ"):
        _check(RETRIEVAL, points=("something else",))


def test_index_names_the_configured_soc_kb_models() -> None:
    fields = Settings.model_fields
    assert RETRIEVAL.index.embedding_model == fields["soc_kb_vector_model"].default
    assert RETRIEVAL.index.reranker_model == fields["soc_kb_reranker_model"].default


# --- the R1 screen, end to end ----------------------------------------------------------------


@pytest.fixture(scope="module")
def r1_turns() -> list[tuple[str, dict[str, Any]]]:
    return walk_agent(R1.scenario_id)


def _response(turns: list[tuple[str, dict[str, Any]]], name: str) -> dict[str, Any]:
    return next(response for step, response in turns if step == name)


def test_question_names_the_user_and_needs_no_search() -> None:
    assert R1.question == NEW_QUESTION
    assert R1.legacy_phrasings == ()
    assert all(check.spl is None for check in R1.checks)
    assert all(action.spl is None for action in R1.actions)
    assert {action.verb for action in R1.actions} <= {"incident", "request", "email"}


def test_old_question_no_longer_resolves_to_r1() -> None:
    scenario_id, _ = resolve_ec_query_fuzzy(OLD_QUESTION)
    assert scenario_id != R1.scenario_id
    assert resolve_ec_query_fuzzy(NEW_QUESTION)[0] == R1.scenario_id


def test_no_section_sign_anywhere_in_r1(r1_turns) -> None:
    for step, response in r1_turns:
        assert "§" not in json.dumps(response, ensure_ascii=False), step


def test_answer_and_actions_arrive_together(r1_turns) -> None:
    plan = _response(r1_turns, "plan")["ec_agent_workflow"]
    assert "procedure_answer" not in plan and "rag_trace" not in plan
    response = _response(r1_turns, "run_investigation")
    assert response["ec_agent_lifecycle"] == "REMEDIATION_PLAN_READY"
    workflow = response["ec_agent_workflow"]
    assert workflow["remediation_offer"] is None
    assert [step["id"] for step in workflow["remediation_plan"]["steps"]] == [
        "open_incident", "reset_credentials", "purge_and_block", "issue_advisory", "email_user",
    ]


def test_procedure_screen(r1_turns) -> None:
    workflow = _response(r1_turns, "run_investigation")["ec_agent_workflow"]
    answer = workflow["procedure_answer"]
    assert len(answer["opening"].split(". ")) <= 3
    assert answer["documents"][0] == {
        "doc_id": E.SOP_PHISHING,
        "title": "Phishing response procedure",
        "version": "2026.3",
        "approved_on": "12 Mar 2026",
    }
    assert [phase["name"] for phase in answer["phases"]] == ["Contain", "Scope", "Record and notify"]
    steps = [step for phase in answer["phases"] for step in phase["steps"]]
    assert len(steps) == 8
    assert all(step["refs"] and all(ref["excerpt"] for ref in step["refs"]) for step in steps)
    isolate = next(step for step in steps if step["text"] == "Isolate the laptop")
    assert isolate["condition"] == "only if a file was downloaded or ran"
    assert answer["escalation"]["refs"][0]["ref"] == "PH-02"
    assert answer["assessment"]["incident_priority"] == "P3"
    trace = workflow["rag_trace"]
    assert (trace["funnel"]["kept"], trace["funnel"]["cited"], trace["excluded_total"]) == (11, 10, 5)
    assert trace["answer"]["sentences"] == []  # the answer lives on the procedure screen


def test_every_action_names_a_section_of_a_used_chunk() -> None:
    used = {f"{chunk.doc_id} {chunk.ref}" for chunk in RETRIEVAL.chunks if chunk.used}
    for action in R1.actions:
        assert any(ref in action.proposal for ref in used), action.id


def _sent_email(turns: list[tuple[str, dict[str, Any]]], action_id: str) -> dict[str, Any]:
    final = turns[-1][1]["ec_agent_workflow"]
    step = next(row for row in final["remediation_plan"]["steps"] if row["id"] == action_id)
    return step["finding"]["details"]["email_draft"]


def _step(turns: list[tuple[str, dict[str, Any]]], action_id: str) -> dict[str, Any]:
    final = turns[-1][1]["ec_agent_workflow"]
    return next(row for row in final["remediation_plan"]["steps"] if row["id"] == action_id)


def test_staff_advisory_is_a_request_to_internal_communications(r1_turns) -> None:
    ticket = _step(r1_turns, "issue_advisory")["finding"]["details"]["ticket"]
    assert ticket["number"] == E.TASK_R1_COMMS
    assert ticket["assignment_group"] == "Internal Communications"
    assert E.PHISH_URL in ticket["description"] and E.PHISH_SENDER in ticket["description"]
    assert f"SOC reference: {E.INCIDENT_R1}" in ticket["description"]
    assert E.PHISH_USER not in ticket["description"]  # an all-staff advisory never names the user
    assert all(action.email is None or action.id == "email_user" for action in R1.actions)


def test_user_is_asked_about_passwords_and_sensitive_information(r1_turns) -> None:
    step = RETRIEVAL.steps[-1]
    assert "shared sensitive information" in step.text
    body = _sent_email(r1_turns, "email_user")["body"]
    assert "sensitive information" in body and "password" in body


def test_after_approval_the_answer_stays_with_each_step_status(r1_turns) -> None:
    answer = r1_turns[-1][1]["ec_agent_workflow"]["procedure_answer"]
    status = {step["text"]: step["status"] for phase in answer["phases"] for step in phase["steps"]}
    assert status["Open an incident at policy priority — P3 for a click"] == "done"
    assert status["Reset the password and sign out all sessions within 4 hours"] == "requested"
    assert status["Remove the email from all mailboxes and block the sender"] == "requested"
    assert status["Warn staff with an advisory: sender, subject, do not click"] == "requested"
    assert status["Find everyone who received or opened the email"] == "pending"
    assert status["Check the laptop for anything that ran after the click"] == "pending"
    assert status["Isolate the laptop"] == "conditional"
    summary = answer["progress_summary"]
    assert "find other recipients" in summary["pending"] and "check the laptop" in summary["pending"]
    assert "incident" in summary["done"]


def test_answer_has_no_status_before_approval(r1_turns) -> None:
    answer = _response(r1_turns, "run_investigation")["ec_agent_workflow"]["procedure_answer"]
    assert answer["progress_summary"] is None
    assert all("status" not in step for phase in answer["phases"] for step in phase["steps"])


def test_knowledge_answer_uses_its_own_short_animations(r1_turns) -> None:
    plan = _response(r1_turns, "plan")["ec_execution_journey"]
    run = _response(r1_turns, "run_investigation")["ec_execution_journey"]
    assert plan["header"] == "Processing your request" and len(plan["stages"]) == 2
    assert run["header"] == "Searching the knowledge base" and len(run["stages"]) == 4


def test_user_email_carries_the_ticket_reference(r1_turns) -> None:
    email = _sent_email(r1_turns, "email_user")
    assert email["subject"].startswith(f"[{E.INCIDENT_R1}]")
    assert email["body"].startswith(f"Reference: {E.INCIDENT_R1}")


def test_r1_walk_reaches_awaiting_user_reply(r1_turns) -> None:
    final = r1_turns[-1][1]
    assert final["ec_agent_lifecycle"] == "COMPLETE"
    assert final["ec_agent_workflow"]["final_summary"]["title"] == "OPEN — AWAITING USER REPLY"


# --- no other scenario changes ----------------------------------------------------------------


@pytest.mark.parametrize("spec", [spec for spec in ALL_SPECS if spec.rag is None], ids=lambda spec: spec.scenario_id)
def test_non_rag_scenarios_emit_no_procedure_screen(spec) -> None:
    assert spec.propose_with_answer is False
    for _, response in walk_agent(spec.scenario_id):
        workflow = response.get("ec_agent_workflow") or {}
        assert "rag_trace" not in workflow and "procedure_answer" not in workflow


def test_a_skipped_action_shows_no_record() -> None:
    from app.demo.ec_agent.rag_record import build_procedure_answer

    progress = {"email_user": {"status": "SKIPPED", "email": {"to": "r.mehta", "subject": "draft", "body": "draft"}}}
    answer = build_procedure_answer(RETRIEVAL, assessment=None, progress=progress)
    step = answer["phases"][-1]["steps"][-1]
    assert (step["status"], step["status_label"]) == ("pending", "Not started")
    assert "email" not in step
    assert "ask the user" in answer["progress_summary"]["pending"]
