"""Plan 5 B5 — live capability enforcement, default-off, fail-closed, never widens."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.chat.contracts.resolved_query import ResolvedQueryContract
from app.chat.evidence_planner import plan_evidence
from app.chat.intent_classifier import build_query_to_intent
from app.chat.skill_intent_compatibility import (
    CAPABILITY_MCP,
    CAPABILITY_SPL,
    enforce_route_capabilities,
    resolve_capability_compatibility,
    skill_contract_for,
)
from app.config import Settings, settings
from app.query_understanding.parser import understand_query
from app.routing.route_adjudication import adjudicate_route

_POLICY = "What is the escalation policy for repeated failed login alerts?"
_SUMMARY = (
    "Give a concise analyst summary: engineering workstation accessed OT jump host "
    "and changed two RTU parameters after-hours."
)
_CONFIG_PY = Path(__file__).resolve().parents[1] / "config.py"


def _adjudicate(
    query: str,
    *,
    deterministic_route: str,
    contract: ResolvedQueryContract | None = None,
) -> dict:
    qu = understand_query(query)
    q2i = build_query_to_intent(query=query, query_understanding=qu)
    intent = q2i.intent_classification.model_dump()
    evidence = plan_evidence(
        intent,
        query_to_intent=q2i.model_dump(),
        query_understanding=qu,
    ).model_dump()
    result = adjudicate_route(
        deterministic_route=deterministic_route,
        route_plan_shadow={},
        evidence_plan=evidence,
        intent_classification=intent,
        query_understanding=qu,
        message=query,
        query_to_intent=q2i.model_dump(),
        resolved_query_contract=contract,
    )
    return result.model_dump()


def test_enforcement_flag_defaults_off() -> None:
    assert Settings().ai_soc_live_capability_enforcement_enabled is False
    text = _CONFIG_PY.read_text(encoding="utf-8")
    assert "ai_soc_live_capability_enforcement_enabled: bool = False" in text


def _hunt_contract_over_summary() -> ResolvedQueryContract:
    return ResolvedQueryContract(
        normalized_goal=_SUMMARY,
        intent_family="spl_generation_only",
        answer_goal="spl_artifact",
        ambiguity_state="unambiguous",
        required_capabilities=frozenset({CAPABILITY_SPL}),
        prohibited_capabilities=frozenset(),
        qualification_tier="T4",
        qualification_source="out_of_registry",
        confidence=0.8,
    )


def test_flag_off_does_not_change_contradicting_route(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_live_capability_enforcement_enabled", False)
    off = _adjudicate(
        _SUMMARY,
        deterministic_route="alert_summary",
        contract=_hunt_contract_over_summary(),
    )
    assert off["capability_enforcement"] is None
    assert off["final_route"] == "alert_summary"
    assert off["authority_source"] != "capability_enforcement_veto"


def test_flag_on_vetoes_skill_that_denies_required_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_live_capability_enforcement_enabled", True)
    on = _adjudicate(
        _SUMMARY,
        deterministic_route="alert_summary",
        contract=_hunt_contract_over_summary(),
    )
    assert on["final_route"] == "knowledge_recall"
    assert on["authority_source"] == "capability_enforcement_veto"
    assert on["capability_enforcement"] == "veto"
    assert CAPABILITY_SPL in on["capability_denied"]


def test_never_promotes_to_satisfy_required_caps() -> None:
    route, resolution, status = enforce_route_capabilities(
        final_route="knowledge_recall",
        intent_family="live_investigation",
        required_capabilities=frozenset({CAPABILITY_SPL, CAPABILITY_MCP}),
    )
    assert route == "knowledge_recall"
    assert status == "unsatisfied"
    assert CAPABILITY_SPL in resolution.denied_capabilities
    assert route != "attack_discovery"
    assert route != "spl_generation"


def test_compatible_skill_is_unchanged() -> None:
    route, resolution, status = enforce_route_capabilities(
        final_route="attack_discovery",
        intent_family="live_investigation",
        required_capabilities=frozenset({CAPABILITY_SPL, CAPABILITY_MCP}),
    )
    assert route == "attack_discovery"
    assert status == "compatible"
    assert not resolution.denied_capabilities


def test_flag_on_without_contract_does_not_invent_a_route(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_live_capability_enforcement_enabled", True)
    result = _adjudicate(_POLICY, deterministic_route="knowledge_recall", contract=None)
    assert result["final_route"] == "knowledge_recall"
    assert result["capability_enforcement"] == "no_contract"


def test_malformed_contract_fail_closed_keeps_route(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_live_capability_enforcement_enabled", True)
    result = _adjudicate(
        _POLICY,
        deterministic_route="knowledge_recall",
        contract={"intent_family": "not-a-valid-contract"},  # type: ignore[arg-type]
    )
    assert result["final_route"] == "knowledge_recall"
    assert result["capability_enforcement"] == "unresolved_contract"


def test_does_not_remove_clarification_requirement(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_live_capability_enforcement_enabled", True)
    contract = ResolvedQueryContract(
        normalized_goal="Block this IP immediately",
        intent_family="clarification_required",
        answer_goal="clarification",
        ambiguity_state="clarification_required",
        clarification_required=True,
        clarification_reason="unsafe_action",
        required_capabilities=frozenset(),
        prohibited_capabilities=frozenset({CAPABILITY_SPL, CAPABILITY_MCP}),
        qualification_tier="T4",
        qualification_source="out_of_registry",
        confidence=0.9,
    )
    result = _adjudicate(
        "Block this IP immediately and run SPL against all indexes",
        deterministic_route="knowledge_recall",
        contract=contract,
    )
    assert contract.clarification_required is True
    assert result["capability_enforcement"] in {"compatible", "unsatisfied"}
    assert result["final_route"] == "knowledge_recall"


def test_cannot_reduce_deterministic_required_capabilities() -> None:
    """Enforcement unions contract.required with family required; it never drops them."""
    _, resolution, _ = enforce_route_capabilities(
        final_route="knowledge_recall",
        intent_family="spl_generation_only",
        required_capabilities=frozenset(),
    )
    assert CAPABILITY_SPL in resolution.required_capabilities


def test_reuses_resolve_capability_compatibility_not_a_second_table() -> None:
    via_enforce = enforce_route_capabilities(
        final_route="guided_investigation",
        intent_family="spl_generation_only",
    )[1]
    via_resolve = resolve_capability_compatibility(
        routed_skill="guided_investigation",
        intent_family="spl_generation_only",
        skill_contract=skill_contract_for("guided_investigation"),
    )
    assert via_enforce.status == via_resolve.status
    assert via_enforce.denied_capabilities == via_resolve.denied_capabilities
    assert via_enforce.granted_capabilities == via_resolve.granted_capabilities


def test_additional_required_caps_accepted_only_if_skill_already_grants_them() -> None:
    """Widening is not automatic: extra required caps still go through the skill contract."""
    route, _, status = enforce_route_capabilities(
        final_route="knowledge_recall",
        intent_family="knowledge_only",
        required_capabilities=frozenset({CAPABILITY_SPL}),
    )
    assert route == "knowledge_recall"
    assert status == "unsatisfied"

    route_ok, _, status_ok = enforce_route_capabilities(
        final_route="attack_discovery",
        intent_family="knowledge_only",
        required_capabilities=frozenset({CAPABILITY_SPL}),
    )
    assert route_ok == "attack_discovery"
    assert status_ok == "compatible"
