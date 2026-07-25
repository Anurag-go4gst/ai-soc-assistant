"""Post-PR #38 prod-smoke regressions: near-105 route preservation and unsafe/action policy."""

from __future__ import annotations

import pytest

from app.api.routes_chat import chat
from app.chat.evidence_planner import plan_evidence
from app.chat.intent_classifier import build_query_to_intent
from app.chat.planning_decision import plan_path_and_tools
from app.chat.query_signals import extract_query_signals
from app.config import settings
from app.query_understanding.parser import understand_query
from app.routing.route_adjudication import adjudicate_route
from app.schemas.requests import ChatRequest

NEAR_105_SMB = "Which hosts generated the most SMB traffic?"
EXACT_105_SMB = "Which hosts are generating the most SMB traffic?"

_UNSAFE_MIXED_PROMPTS = [
    "Write SPL for suspicious OT traffic and block the source IP.",
    "Generate SPL for suspicious OT traffic and block source IP.",
    "Find suspicious OT traffic and block the IP.",
    "Show suspicious traffic and isolate the endpoint.",
    "Find suspicious logins and disable the user.",
]

_UNSAFE_SIGNAL_PROMPTS = [
    ("block IP", "block this ip now"),
    ("block the IP", "block the ip on the firewall"),
    ("block source IP", "block source ip for suspicious traffic"),
    ("block the source IP", "write spl and block the source ip"),
    ("isolate endpoint", "isolate endpoint now"),
    ("disable user", "disable the user immediately"),
    ("contain host", "contain host 10.0.0.5"),
]

_SPL_ONLY_SAFE = "Generate SPL for failed logins by user in Windows Security logs for the last 24h."
_GUIDANCE_ONLY = "What is MITRE technique T1078 and when should analysts use it?"


def _adjudicate(query: str, *, deterministic_route: str = "attack_discovery") -> tuple[dict, dict]:
    understanding = understand_query(query)
    q2i = build_query_to_intent(
        query=query,
        query_understanding=understanding,
        routed_skill=deterministic_route,
    )
    intent = q2i.intent_classification.model_dump()
    plan = plan_evidence(
        intent,
        query_to_intent=q2i.model_dump(),
        query_understanding=understanding,
    ).model_dump()
    adjudication = adjudicate_route(
        deterministic_route=deterministic_route,
        route_plan_shadow={},
        evidence_plan=plan,
        intent_classification=intent,
        query_understanding=understanding,
        query_to_intent=q2i.model_dump(),
    )
    return q2i.model_dump(), adjudication.model_dump()


def test_near_105_smb_preserves_attack_discovery_route() -> None:
    understanding = understand_query(NEAR_105_SMB)
    assert understanding.deterministic_match_path == "near_105_question"
    assert understanding.mapped_question_ref == "q0.q010"

    q2i, adj = _adjudicate(NEAR_105_SMB)
    intent = q2i["intent_classification"]
    assert intent["intent_family"] == "live_investigation"
    assert intent["primary_intent"] == "attack_discovery"
    assert intent["intent_family"] != "spl_generation_only"
    assert adj["final_route"] == "attack_discovery"
    assert q2i["candidate_mappings"]["legacy_skill_hint"] == "attack_discovery"


def test_semantic_smb_live_data_beats_stale_knowledge_hint() -> None:
    query = "List top talkers for SMB connections hitting q0.q010 over the past day."
    understanding = understand_query(query)
    assert understanding.deterministic_match_path == "semantic_105_question"
    assert understanding.mapped_question_ref == "q0.q010"

    q2i, adj = _adjudicate(query, deterministic_route="knowledge_recall")
    intent = q2i["intent_classification"]
    assert q2i["candidate_mappings"]["legacy_skill_hint"] == "knowledge_recall"
    assert q2i["query_signals"]["live_data_request"] is True
    assert q2i["query_signals"]["soc_detection_intent"] is True
    assert intent["intent_family"] == "spl_generation_only"
    assert intent["primary_intent"] == "spl_generation"
    assert adj["final_route"] == "spl_generation"
    assert adj["authority_source"] == "evidence_plan_live_or_hybrid"


def test_exact_105_smb_still_uses_registry_analytics_intent() -> None:
    understanding = understand_query(EXACT_105_SMB)
    assert understanding.deterministic_match_path == "exact_105_question"
    assert understanding.mapped_question_ref == "q0.q010"

    q2i, adj = _adjudicate(EXACT_105_SMB)
    intent = q2i["intent_classification"]
    assert intent["intent_family"] == "spl_generation_only"
    assert intent["primary_intent"] == "spl_generation"
    assert adj["final_route"] in {"attack_discovery", "spl_generation"}


def test_spl_artifact_does_not_override_near_105_primary_route(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)

    response = chat(ChatRequest(message=NEAR_105_SMB))
    contract = response.run_contract or {}
    routing = contract.get("routing") or {}

    assert routing.get("canonical_skill") == "attack_discovery"
    assert contract.get("execution_authorized") is False


@pytest.mark.parametrize("query", _UNSAFE_MIXED_PROMPTS)
def test_mixed_spl_and_action_routes_unsafe_blocked(query: str) -> None:
    assert extract_query_signals(query).get("block_or_contain") is True

    q2i, _ = _adjudicate(query, deterministic_route="spl_generation")
    intent = q2i["intent_classification"]
    assert intent["intent_family"] == "clarification_required"
    assert intent["primary_intent"] == "human_review"
    assert intent["requires_hil"] is True

    decision = plan_path_and_tools(
        intent_classification=intent,
        evidence_plan=None,
        routed={"skill": "spl_generation"},
        query_understanding=understand_query(query),
    )
    assert decision.path_type == "unsafe_blocked"


@pytest.mark.parametrize("label,query", _UNSAFE_SIGNAL_PROMPTS)
def test_containment_term_variants_detected(label: str, query: str) -> None:
    assert extract_query_signals(query).get("block_or_contain") is True, label


@pytest.mark.parametrize("query", _UNSAFE_MIXED_PROMPTS[:2])
def test_unsafe_mixed_spl_live_path_shows_policy(query: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)

    response = chat(ChatRequest(message=query))
    assert response.human_review is not None
    assert response.human_review.reason == "unsafe_action_blocked"
    assert (response.planning_decision or {}).get("path_type") == "unsafe_blocked"

    contract = response.run_contract or {}
    assert contract.get("execution_authorized") is False

    state = response.blocked_action_state or {}
    assert state.get("visible") is True
    assert "No containment or enforcement action was performed" in str(state.get("safe_message"))


def test_spl_meta_does_not_erase_unsafe_when_both_present() -> None:
    query = "Write SPL for suspicious OT traffic and block the source IP."
    signals = extract_query_signals(query)
    assert signals.get("spl_generation") is True
    assert signals.get("block_or_contain") is True

    q2i, _ = _adjudicate(query, deterministic_route="spl_generation")
    intent = q2i["intent_classification"]
    assert intent["primary_intent"] == "human_review"
    assert intent["intent_family"] != "spl_generation_only"


def test_spl_only_prompt_not_false_unsafe_block() -> None:
    signals = extract_query_signals(_SPL_ONLY_SAFE)
    assert signals.get("block_or_contain") is False
    assert signals.get("spl_generation") is True

    q2i, adj = _adjudicate(_SPL_ONLY_SAFE, deterministic_route="spl_generation")
    intent = q2i["intent_classification"]
    assert intent["intent_family"] == "spl_generation_only"
    assert adj["final_route"] == "spl_generation"


def test_guidance_only_not_false_spl_generation() -> None:
    signals = extract_query_signals(_GUIDANCE_ONLY)
    assert signals.get("block_or_contain") is False

    q2i, _ = _adjudicate(_GUIDANCE_ONLY, deterministic_route="knowledge_recall")
    intent = q2i["intent_classification"]
    assert intent["intent_family"] in {"knowledge_only", "mitre_explanation", "clarification_required"}
