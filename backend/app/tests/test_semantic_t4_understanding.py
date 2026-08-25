"""Plan 5 B4 — bounded T4 semantic understanding, default-off, fail-closed merge."""

from __future__ import annotations

import ast
import json
import time
from pathlib import Path

import pytest

from app.chat.contracts.resolved_query import ResolvedQueryContract
from app.chat.resolved_query_builder import build_resolved_query_contract
from app.chat.semantic_t4_understanding import (
    SEMANTIC_T4_TIMEOUT_SECONDS,
    maybe_enrich_t4_semantic,
)
from app.config import Settings, settings
from app.query_understanding.parser import understand_query


def _t4_contract() -> ResolvedQueryContract:
    from app.tests.support.t4_abstain import force_t4_abstain

    query = "Hunt for CI/CD supply-chain compromise indicators across our environment"
    qu = understand_query(query)
    return force_t4_abstain(
        build_resolved_query_contract(
            query=query,
            query_understanding=qu,
            qualification_tier="T4",
            qualification_source="out_of_registry",
        )
    )


def _t1_contract() -> ResolvedQueryContract:
    query = "What incident or alert network events are high or critical right now?"
    qu = understand_query(query)
    return build_resolved_query_contract(
        query=query,
        query_understanding=qu,
        qualification_tier="T1",
        qualification_source="exact_105_question",
    )


def _json_provider(payload: dict) -> object:
    def _provider(_query: str, _contract: ResolvedQueryContract) -> str:
        return json.dumps(payload)

    return _provider


def test_flag_name_and_default() -> None:
    assert Settings().ai_soc_t4_semantic_understanding_enabled is False
    assert "ai_soc_t4_semantic_understanding_enabled" in Settings.model_fields
    assert Settings().ai_soc_t4_semantic_understanding_timeout_seconds == SEMANTIC_T4_TIMEOUT_SECONDS


def test_config_declares_the_flag_default_false() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "config.py").read_text(encoding="utf-8")
    assert "ai_soc_t4_semantic_understanding_enabled: bool = False" in text
    assert "ai_soc_t4_semantic_understanding_timeout_seconds: float = 2.0" in text


def test_t1_never_invokes_semantic_when_flag_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_enabled", True)
    calls: list[str] = []

    def _provider(query: str, _contract: ResolvedQueryContract) -> str:
        calls.append(query)
        return json.dumps({"normalized_goal": "should not apply"})

    original = _t1_contract()
    enriched = maybe_enrich_t4_semantic(original, query="x", raw_output_provider=_provider)
    assert calls == []
    assert enriched.model_dump() == original.model_dump()
    assert enriched.understanding_source == "deterministic_qualification"


@pytest.mark.parametrize("tier,source", [("T2", "use_case_catalog"), ("T3", "near_105_question")])
def test_t2_t3_never_invoke_semantic_when_flag_on(
    monkeypatch: pytest.MonkeyPatch, tier: str, source: str
) -> None:
    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_enabled", True)
    calls: list[int] = []

    def _provider(_query: str, _contract: ResolvedQueryContract) -> str:
        calls.append(1)
        return "{}"

    contract = ResolvedQueryContract(
        normalized_goal="catalogue row",
        intent_family="hybrid_alert_review",
        answer_goal="live_results",
        ambiguity_state="unambiguous",
        qualification_tier=tier,  # type: ignore[arg-type]
        qualification_source=source,
        confidence=0.8,
    )
    maybe_enrich_t4_semantic(contract, query="x", raw_output_provider=_provider)
    assert calls == []


def test_flag_off_does_not_invoke_on_t4(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_enabled", False)
    calls: list[int] = []

    def _provider(_query: str, _contract: ResolvedQueryContract) -> str:
        calls.append(1)
        return json.dumps({"normalized_goal": "mutated"})

    # Complete T4-lane contract (ACCEPT / no semantic_referent ownership).
    query = "Hunt for CI/CD supply-chain compromise indicators across our environment"
    original = build_resolved_query_contract(
        query=query,
        query_understanding=understand_query(query),
        qualification_tier="T4",
        qualification_source="out_of_registry",
    )
    enriched = maybe_enrich_t4_semantic(original, query="hunt", raw_output_provider=_provider)
    assert calls == []
    assert enriched.model_dump() == original.model_dump()


def test_t4_invokes_only_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_enabled", True)
    original = _t4_contract()
    enriched = maybe_enrich_t4_semantic(
        original,
        query="hunt",
        raw_output_provider=_json_provider({"normalized_goal": "supply-chain hunt"}),
    )
    assert enriched.normalized_goal == "supply-chain hunt"
    assert enriched.understanding_source == "semantic_t4"
    assert enriched.provenance["field_sources"]["normalized_goal"] == "semantic_t4"
    assert enriched.provenance["semantic_t4"]["invoked"] is True


def test_timeout_returns_deterministic_contract_within_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_timeout_seconds", 0.15)

    def _hang(_query: str, _contract: ResolvedQueryContract) -> str:
        time.sleep(2.0)
        return json.dumps({"normalized_goal": "too late"})

    original = _t4_contract()
    started = time.monotonic()
    enriched = maybe_enrich_t4_semantic(original, query="hunt", raw_output_provider=_hang)
    elapsed = time.monotonic() - started
    assert elapsed < 0.8
    assert enriched.normalized_goal == original.normalized_goal
    assert enriched.understanding_source == "deterministic_qualification"
    assert enriched.provenance["semantic_t4"]["timed_out"] is True
    assert enriched.provenance["semantic_t4"]["invoked"] is True


def test_model_cannot_set_a_skill(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_enabled", True)
    original = _t4_contract()
    enriched = maybe_enrich_t4_semantic(
        original,
        query="hunt",
        raw_output_provider=_json_provider({"skill": "spl_generation", "normalized_goal": "x"}),
    )
    dumped = enriched.model_dump()
    assert "skill" not in dumped
    assert enriched.normalized_goal == original.normalized_goal
    # Plan 7 C3: an authority-bearing key is reported as such rather than as a
    # generic schema failure. The whole hop is still rejected — a chatty model may
    # lose unknown *non-authority* keys, but never smuggles a route through.
    assert "authority_key_present" in enriched.provenance["semantic_t4"]["rejected_reasons"]


def test_model_cannot_remove_clarification(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_enabled", True)
    original = ResolvedQueryContract(
        normalized_goal="run this now",
        intent_family="clarification_required",
        answer_goal="clarification",
        ambiguity_state="clarification_required",
        clarification_required=True,
        clarification_reason="unsafe_run_spl",
        prohibited_capabilities=["spl", "mcp"],
        qualification_tier="T4",
        qualification_source="out_of_registry",
        confidence=0.2,
    )
    enriched = maybe_enrich_t4_semantic(
        original,
        query="run this",
        raw_output_provider=_json_provider(
            {
                "clarification_required": False,
                "ambiguity_state": "unambiguous",
                "intent_family": "live_investigation",
                "required_capabilities": ["spl", "mcp"],
                "prohibited_capabilities": [],
            }
        ),
    )
    assert enriched.clarification_required is True
    assert enriched.clarification_reason == "unsafe_run_spl"
    assert enriched.ambiguity_state == "clarification_required"
    assert enriched.intent_family == "clarification_required"
    assert enriched.prohibited_capabilities == frozenset({"spl", "mcp"})
    assert enriched.required_capabilities == frozenset()


def test_model_cannot_reduce_required_capabilities(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_enabled", True)
    original = ResolvedQueryContract(
        normalized_goal="hunt lateral movement",
        intent_family="live_investigation",
        answer_goal="live_results",
        ambiguity_state="unambiguous",
        required_capabilities=["spl", "mcp"],
        qualification_tier="T4",
        qualification_source="out_of_registry",
        confidence=0.4,
    )
    enriched = maybe_enrich_t4_semantic(
        original,
        query="hunt",
        raw_output_provider=_json_provider(
            {
                "intent_family": "knowledge_only",
                "required_capabilities": [],
                "prohibited_capabilities": ["spl", "mcp"],
            }
        ),
    )
    assert enriched.required_capabilities == frozenset({"spl", "mcp"})
    assert enriched.intent_family == "live_investigation"


def test_proposed_additional_capabilities_rejected_without_family_requirement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.tests.support.t4_abstain import force_t4_abstain

    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_enabled", True)
    original = force_t4_abstain(
        ResolvedQueryContract(
            normalized_goal="what is our vacation policy",
            intent_family="knowledge_only",
            answer_goal="policy_citation",
            ambiguity_state="unambiguous",
            prohibited_capabilities=["spl", "mcp"],
            qualification_tier="T4",
            qualification_source="out_of_registry",
            confidence=0.5,
        )
    )
    enriched = maybe_enrich_t4_semantic(
        original,
        query="policy",
        raw_output_provider=_json_provider({"required_capabilities": ["spl", "mcp"]}),
    )
    assert enriched.required_capabilities == frozenset()
    assert enriched.prohibited_capabilities == frozenset({"spl", "mcp"})
    assert "capability_widening_rejected" in enriched.provenance["semantic_t4"]["rejected_reasons"]


def test_malformed_output_rejected_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_enabled", True)
    original = _t4_contract()
    enriched = maybe_enrich_t4_semantic(
        original,
        query="hunt",
        raw_output_provider=lambda _q, _c: "not-json {{{",
    )
    assert enriched.normalized_goal == original.normalized_goal
    assert "schema_invalid" in enriched.provenance["semantic_t4"]["rejected_reasons"]


def test_module_has_no_mcp_or_spl_execution_path() -> None:
    source = (Path(__file__).resolve().parents[1] / "chat" / "semantic_t4_understanding.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    forbidden = (
        "app.orchestration.mcp_execution_gate",
        "app.connectors.mcp",
        "app.mcp",
        "app.safeguards.spl_validator",
        "app.spl.llm_plan_compiler",
        "app.llm.sidecar_clients",
    )
    for name in imported:
        assert name not in forbidden
        assert not name.startswith("app.connectors.mcp")
        assert not name.startswith("app.orchestration.mcp")
