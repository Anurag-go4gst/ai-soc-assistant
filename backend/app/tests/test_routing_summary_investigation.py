"""Track A: live-path routing for alert_summary and guided_investigation intents."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.chat.evidence_planner import plan_evidence
from app.chat.intent_classifier import build_query_to_intent
from app.config import settings
from app.query_understanding.parser import understand_query
from app.routing.route_adjudication import adjudicate_route

_env = Path(__file__).resolve().parents[2] / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())

@pytest.fixture(autouse=True)
def _enable_track_a_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_t2_answer_shape_enabled", True)


_GUIDED_PROBE = (
    "Build a guided investigation for contractor VPN, OT bastion login, "
    "and relay parameter change within 3 hours."
)
_SUMMARY_OUT_OF_REGISTRY = (
    "Give a concise analyst summary: engineering workstation accessed OT jump host "
    "and changed two RTU parameters after-hours."
)
_SUMMARY_IN_CATALOG = (
    "Summarize for shift handoff: failed PLC admin login burst, one success, "
    "then relay logic export in 22 minutes."
)


def _intent_and_adjudication(query: str, *, deterministic_route: str = "knowledge_recall"):
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


def test_guided_probe_classifies_as_guided_not_clarification() -> None:
    intent, adjudication, plan = _intent_and_adjudication(_GUIDED_PROBE, deterministic_route="guided_investigation")
    assert intent.intent_family == "guided_investigation"
    assert intent.requires_clarification is False
    assert adjudication.final_route == "guided_investigation"
    assert plan.answer_mode == "guided_investigation"
    assert plan.needs_spl is False
    assert plan.spl_allowed is False


def test_summary_out_of_registry_classifies_as_alert_summary() -> None:
    intent, adjudication, plan = _intent_and_adjudication(_SUMMARY_OUT_OF_REGISTRY, deterministic_route="spl_generation")
    assert intent.intent_family == "alert_summary"
    assert intent.primary_intent == "alert_summary"
    assert intent.requested_output_type == "SUMMARY"
    assert intent.requires_clarification is False
    assert adjudication.final_route == "alert_summary"
    assert plan.needs_spl is False


def test_summary_in_catalog_classifies_as_alert_summary_not_attack_discovery() -> None:
    intent, adjudication, plan = _intent_and_adjudication(_SUMMARY_IN_CATALOG, deterministic_route="attack_discovery")
    assert intent.intent_family == "alert_summary"
    assert intent.requires_clarification is False
    assert adjudication.final_route == "alert_summary"
    assert plan.needs_spl is False


@pytest.mark.parametrize(
    "query",
    [
        "Provide guided triage when SCADA polling is normal but syslog from two RTUs stopped.",
        "Provide investigation branches for relay config hash mismatch after emergency maintenance.",
    ],
)
def test_explicit_guided_phrasing_not_clarification(query: str) -> None:
    intent, adjudication, _ = _intent_and_adjudication(query, deterministic_route="guided_investigation")
    assert intent.intent_family == "guided_investigation"
    assert intent.requires_clarification is False
    assert adjudication.final_route == "guided_investigation"


def test_clarification_sentinel_still_clarifies() -> None:
    intent, adjudication, _ = _intent_and_adjudication("Check if this alert is serious.")
    assert intent.intent_family == "clarification_required"
    assert intent.requires_clarification is True
    assert adjudication.final_route == "knowledge_recall"
