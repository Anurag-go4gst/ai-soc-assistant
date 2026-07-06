"""Phase 2.5 live-path flip — out-of-catalog / weak-case LLM composition."""

from __future__ import annotations

import pytest

from app.chat.contracts.answer_contract import AnswerContract, build_answer_contract
from app.config import settings
from app.llm.clients import ChatResult, LocalChatError
from app.llm.governed_context_package import build_governed_context_package_for_contract
from app.schemas.responses import AnalystResponseEnvelope
from app.synthesis.composition_confidence import (
    composition_confidence,
    qualifies_for_weak_case_composition,
    should_attach_compose_hil,
)
from app.synthesis.governed_answer_composer import (
    build_composer_prompt,
    compose_governed_answer,
    out_of_catalog_notice_preserved,
)


class _StubClient:
    def __init__(self, *, text: str = "", raises: bool = False) -> None:
        self._text = text
        self._raises = raises
        self.calls = 0
        self.last_prompt = ""

    def generate(self, *, system_prompt: str, user_prompt: str, max_tokens: int, temperature: float) -> ChatResult:
        self.calls += 1
        self.last_prompt = user_prompt
        if self._raises:
            raise LocalChatError("transport_error:Boom")
        return ChatResult(text=self._text, model="stub-model", latency_ms=8, usage={"total_tokens": 5})


def _enable_composer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_final_synthesis_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_live_synthesis_enabled", True)


def _guided_contract(**overrides) -> AnswerContract:
    payload = {
        "intent_classification": {
            "intent_family": "guided_investigation",
            "answer_goal": ["investigation_guidance"],
        },
        "evidence_plan": {
            "answer_mode": "guided_investigation",
            "spl_allowed": False,
            "mcp_allowed": False,
            "limitations": ["Do not claim compromise from this question alone."],
            "checklist": ["Validate scope and time window before escalation."],
        },
        "mitre_decision": {"answer_visible": False},
        "severity_decision": None,
        "spl_validation": None,
        "execution": {"status": "skipped", "block_reason": "mcp_not_allowed_by_evidence_plan"},
        "human_review": {"required": False},
    }
    payload.update(overrides)
    contract = build_answer_contract(**payload)
    return contract.model_copy(
        update={
            "out_of_catalog_notice": (
                "This question is outside the governed question catalog; validate against local telemetry and policy."
            ),
            "investigation_steps": ["Validate scope and time window."],
        }
    )


def _fallback_envelope() -> AnalystResponseEnvelope:
    return AnalystResponseEnvelope(
        response_profile="guided_investigation",
        direct_answer_summary="Guided investigation (review-only)\n\nHypotheses\n- Review east-west traffic.",
        severity_label=None,
    )


def test_qualifies_guided_and_out_of_catalog() -> None:
    contract = _guided_contract()
    assert qualifies_for_weak_case_composition(contract, path_type="guided_investigation")
    assert qualifies_for_weak_case_composition(
        AnswerContract(
            missing_evidence=[],
            hil_status="not_required",
            out_of_catalog_notice="Not a vetted catalog detection.",
        )
    )


def test_qualifies_reference_knowledge() -> None:
    contract = AnswerContract(
        missing_evidence=[],
        hil_status="not_required",
        answer_mode="rag_only",
        intent_family="reference_knowledge",
    )
    assert qualifies_for_weak_case_composition(contract, intent_family="reference_knowledge")


def test_weak_case_prompt_threads_context_package() -> None:
    contract = _guided_contract()
    pkg = build_governed_context_package_for_contract(
        query="odd OT chatter overnight",
        contract=contract,
        skill_sections=["guided_hunt: collect DNS and firewall context"],
        soc_kb_snippets=["Review periodicity and destination rarity together."],
    )
    prompt = build_composer_prompt(
        contract,
        None,
        context_package=pkg,
        weak_case_composition=True,
    )
    assert "GOVERNED CONTEXT" in prompt
    assert "out-of-catalog notice" in prompt.lower()
    assert "guided_hunt" in prompt
    assert "periodicity" in prompt


def test_out_of_catalog_composition_renders_notice_and_keeps_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_composer(monkeypatch)
    contract = _guided_contract()
    composed = (
        "Out-of-catalog: this is not a vetted catalog detection; validate against local telemetry and policy. "
        "Review east-west OT traffic, DNS, and firewall logs for the overnight window. "
        "Do not claim compromise from this question alone. Human review is required before any search execution."
    )
    client = _StubClient(text=composed)
    pkg = build_governed_context_package_for_contract(
        query="odd OT chatter",
        contract=contract,
        soc_kb_snippets=["Review periodicity and destination rarity together."],
    )

    result = compose_governed_answer(
        contract=contract,
        enrichment_projection=None,
        fallback_envelope=_fallback_envelope(),
        client=client,
        context_package=pkg,
        path_type="guided_investigation",
        intent_family="guided_investigation",
    )

    assert client.calls == 1
    assert result.llm_composer_used is True
    assert result.llm_guard_status == "passed"
    assert "not a vetted catalog detection" in result.envelope.direct_answer_summary.lower()
    assert result.envelope.severity_label is None
    assert contract.spl_status == "not_required"
    ok, _ = out_of_catalog_notice_preserved(result.envelope.direct_answer_summary, contract)
    assert ok


def test_low_confidence_attaches_compose_hil(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_compose_hil_threshold", 0.99)
    contract = _guided_contract()
    confidence = composition_confidence(
        contract=contract,
        path_type="guided_investigation",
        match_path="out_of_registry",
        soc_kb_snippet_count=0,
        skill_section_count=0,
    )
    attach, reason = should_attach_compose_hil(
        contract=contract,
        confidence=confidence,
        resource_decisions=[],
        evidence_plan={"resource_plan_summary": {"mcp": {"allowed": False}}},
    )
    assert confidence < 0.99
    assert attach is True
    assert reason == "composition_confidence_below_threshold"


def test_mcp_proposal_always_attaches_compose_hil() -> None:
    contract = AnswerContract(
        missing_evidence=[],
        hil_status="not_required",
        mcp_allowed=True,
    )
    attach, reason = should_attach_compose_hil(
        contract=contract,
        confidence=0.95,
        resource_decisions=[],
        evidence_plan=None,
    )
    assert attach is True
    assert reason == "proposed_mcp_search_review"


def test_guard_rejects_invented_source_and_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_composer(monkeypatch)
    contract = _guided_contract()
    bad = (
        "Out-of-catalog hunt: validate against local telemetry. "
        "Focus on source 203.0.113.99 and index=secret_logs for confirmation."
    )
    client = _StubClient(text=bad)
    fallback = _fallback_envelope()

    result = compose_governed_answer(
        contract=contract,
        enrichment_projection=None,
        fallback_envelope=fallback,
        client=client,
        path_type="guided_investigation",
        intent_family="guided_investigation",
    )

    assert result.llm_composer_used is False
    assert result.llm_fallback_used is True
    assert result.envelope.direct_answer_summary == fallback.direct_answer_summary
