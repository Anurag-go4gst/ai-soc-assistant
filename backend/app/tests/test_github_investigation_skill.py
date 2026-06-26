"""Track C: GitHub investigation intent, evidence contract, and review-only governance."""

from __future__ import annotations

import re

import pytest

from app.chat.evidence_planner import plan_evidence
from app.chat.guidance_templates import build_github_investigation_guidance
from app.chat.intent_classifier import build_query_to_intent
from app.chat.pipeline import build_live_chat_response
from app.chat.query_signals import is_github_investigation_query
from app.config import settings
from app.query_understanding.parser import understand_query
from app.routing.route_adjudication import adjudicate_route
from app.schemas.requests import ChatRequest

PAT_WORKFLOW_QUERY = (
    "GitHub focus: summarize how to investigate if a leaked PAT was used to push "
    "unauthorized CI workflow changes in the last 24h."
)
WORKFLOW_TAMPER_QUERY = (
    "Investigate whether a GitHub Actions workflow file was modified to exfiltrate "
    "secrets after a repo.push from an unknown actor."
)
COMMIT_PROVENANCE_QUERY = (
    "How should we validate commit SHA provenance and audit log events when a PAT "
    "appears in oauth_access records for our GitHub org?"
)

_GITHUB_EVIDENCE_PATTERNS = (
    re.compile(r"actor|username", re.I),
    re.compile(r"pat|token", re.I),
    re.compile(r"commit", re.I),
    re.compile(r"workflow", re.I),
    re.compile(r"audit\s*log|repo\.push|workflow_dispatch|oauth", re.I),
)


def _github_evidence_field_count(text: str) -> int:
    return sum(1 for pattern in _GITHUB_EVIDENCE_PATTERNS if pattern.search(text))


def _intent_and_adjudication(query: str, *, deterministic_route: str = "guided_investigation"):
    understanding = understand_query(query)
    qti = build_query_to_intent(query=query, query_understanding=understanding)
    intent = qti.intent_classification
    plan = plan_evidence(
        intent_classification=intent,
        query_to_intent=qti.model_dump(),
        query_understanding=understanding,
        routed={"skill": deterministic_route},
    )
    adjudication = adjudicate_route(
        deterministic_route=deterministic_route,
        evidence_plan=plan,
        intent_classification=intent,
        query_understanding=understanding,
        query_to_intent=qti.model_dump(),
        message=query,
    )
    return intent, adjudication, plan


@pytest.mark.parametrize(
    "query",
    [PAT_WORKFLOW_QUERY, WORKFLOW_TAMPER_QUERY, COMMIT_PROVENANCE_QUERY],
)
def test_github_queries_detected(query: str) -> None:
    assert is_github_investigation_query(query) is True


def test_github_intent_not_alert_summary_for_pat_probe() -> None:
    intent, adjudication, plan = _intent_and_adjudication(PAT_WORKFLOW_QUERY)
    assert intent.intent_family == "github_investigation"
    assert intent.requires_clarification is False
    assert adjudication.final_route == "guided_investigation"
    assert plan.spl_allowed is False
    assert plan.needs_spl is False


def test_github_guidance_has_three_plus_native_evidence_fields() -> None:
    body = build_github_investigation_guidance(PAT_WORKFLOW_QUERY)
    assert _github_evidence_field_count(body) >= 3
    assert "not eligible for execution" in body.lower() or "mcp execution was performed" in body.lower()


@pytest.mark.parametrize("query", [PAT_WORKFLOW_QUERY, WORKFLOW_TAMPER_QUERY, COMMIT_PROVENANCE_QUERY])
def test_github_evidence_checklist_in_plan(query: str) -> None:
    _, _, plan = _intent_and_adjudication(query)
    joined = " ".join(list(plan.checklist or []) + list(plan.investigation_workflow or []))
    assert _github_evidence_field_count(joined) >= 3


def test_github_live_pipeline_returns_guidance_card(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_t2_answer_shape_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_t2_rag_surfacing_enabled", True)
    response = build_live_chat_response(ChatRequest(message=PAT_WORKFLOW_QUERY))
    assert response.analyst_response is not None
    blob = (response.message or "") + (response.analyst_response.direct_answer_summary or "")
    assert "github" in blob.lower()
    assert _github_evidence_field_count(blob) >= 3
    assert "not eligible for execution" in blob.lower() or "mcp execution was performed" in blob.lower()
