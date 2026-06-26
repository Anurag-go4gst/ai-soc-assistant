"""Governed LLM T2 producer: grounding wiring + governed (validated) output.

The producer never emits raw free-form SPL: output passes the deterministic SPL
validator + SOC-STD quality lint and execution is forced off (review-only lab tier).
WS-F grounding is injected as advisory prompt context.
"""
from __future__ import annotations

import json

import pytest

from app.chat.pipeline import _build_t2_grounding_block
from app.spl.llm_fallback import generate_llm_spl_fallback


def test_grounding_block_is_built_for_novel_query():
    g = _build_t2_grounding_block("Detect possible kerberoasting against domain controllers")
    assert g and "GROUNDING CONTEXT" in g


def test_grounding_reaches_producer_prompt():
    captured = {}

    def _provider() -> str:
        # The producer builds the user prompt before calling the model; capture it.
        return json.dumps({"status": "needs_clarification", "candidate_spl": "",
                           "assumptions": ["x"], "required_fields": ["y"]})

    # Inspect the prompt via the user-prompt builder directly.
    from app.spl.llm_fallback import _user_prompt

    prompt = _user_prompt("Detect kerberoasting", context={"t2_grounding": "GROUNDING CONTEXT: families=[kerberoasting]"})
    assert "Deterministic grounding" in prompt
    assert "GROUNDING CONTEXT" in prompt


@pytest.fixture()
def _llm_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.ai_soc_llm_spl_fallback_enabled", True)
    monkeypatch.setattr("app.config.settings.ai_soc_llm_enabled", True)
    monkeypatch.setattr("app.config.settings.ai_soc_llm_mode", "local")


def test_producer_output_is_governed_review_only(_llm_on: None):
    # A well-formed, SOC-STD-compliant lab SPL with placeholder index/sourcetype is
    # exposed as a review-only lab-tier candidate: never executable.
    spl = (
        "search index=<windows_index> sourcetype=<windows_security_sourcetype> EventCode=4769 "
        "| eval account_norm=lower(coalesce(Account_Name, user, \"unknown\")) "
        "| stats count as ticket_count earliest(_time) as first_seen_epoch latest(_time) as last_seen_epoch by account_norm "
        "| eval first_seen=strftime(first_seen_epoch, \"%Y-%m-%d %H:%M:%S\") "
        "| eval last_seen=strftime(last_seen_epoch, \"%Y-%m-%d %H:%M:%S\") "
        "| fields - first_seen_epoch last_seen_epoch | sort - ticket_count | head 100"
    )
    payload = json.dumps({
        "status": "candidate_generated", "confidence_score": 0.6, "confidence_label": "medium",
        "detection_family": "kerberoasting", "candidate_spl": spl,
        "assumptions": ["Kerberos service-ticket logs onboarded"], "required_fields": ["EventCode"],
        "missing_details": [], "clarifying_questions": [], "validation_notes": [],
        "soc_std_rules_applied": [], "risk_notes": [],
        "execution_eligible": False, "governed": False, "catalog_approved": False,
    })
    r = generate_llm_spl_fallback(user_query="Detect kerberoasting", llm_raw_output_provider=lambda: payload)
    assert r is not None
    if r.lab_tier:
        # Governed exposure: validator keeps it non-executable.
        assert r.validation.get("approved") is False
        assert r.validation.get("normalized_spl") is None
    else:
        # Otherwise it must be blocked/clarification — never an approved executable.
        assert r.validation.get("normalized_spl") is None


def test_disabled_llm_returns_clarification_not_free_form():
    # With the fallback flag off, the producer never emits SPL (no free-form leak).
    r = generate_llm_spl_fallback(user_query="Detect kerberoasting")
    assert r is not None
    assert r.clarification_required is True
    assert not r.candidate_spl
