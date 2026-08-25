"""S5 — one-repair bound, repair payload, and shape-aware SPL prompts."""

from __future__ import annotations

import json
from typing import Any

from app.spl.llm_fallback import spl_advisory_prompts
from app.spl.spl_intent_spec import build_spl_intent_spec
from app.spl.utility_spl_authoring import (
    MAX_SPL_LLM_REPAIRS,
    attempt_bounded_utility_spl_llm_draft,
    candidate_from_universal_utility_authoring,
)
from app.config import settings


class _Telemetry:
    def record_step(self, *args: Any, **kwargs: Any) -> None:
        return None

    def record_spl_validation(self, *args: Any, **kwargs: Any) -> None:
        return None


def _payload(spl: str) -> str:
    return json.dumps(
        {
            "status": "candidate_generated",
            "confidence_score": 0.7,
            "confidence_label": "medium",
            "detection_family": "lab_draft",
            "candidate_spl": spl,
            "assumptions": ["Review-only lab draft"],
            "required_fields": ["src_ip"],
            "missing_details": [],
            "clarifying_questions": [],
            "validation_notes": [],
            "soc_std_rules_applied": [],
            "risk_notes": [],
            "execution_eligible": False,
            "governed": False,
            "catalog_approved": False,
        }
    )


def test_more_than_one_repair_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_utility_spl_draft_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")
    result, trace = attempt_bounded_utility_spl_llm_draft(
        "hourly failed-login trend over the last 24 hours",
        llm_raw_output_provider=lambda: _payload("search index=auth | head 100"),
        context={"repair_attempt_count": 2},
        repair_attempt=True,
    )
    assert result is None
    assert trace["llm_spl_draft_dropped_reason"] == "more_than_one_repair"
    assert MAX_SPL_LLM_REPAIRS == 1


def test_authoring_calls_llm_at_most_twice(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")
    monkeypatch.setattr(settings, "ai_soc_llm_utility_spl_draft_enabled", True)
    monkeypatch.setattr("app.spl.utility_spl_authoring.load_persisted_source_profile", lambda: {})
    monkeypatch.setattr(
        "app.spl.utility_spl_authoring.load_persisted_source_profile_document",
        lambda: {"values": {}, "field_sources": {}},
    )
    unfaithful = (
        "search index=pgcil_soc sourcetype=WinEventLog:Security earliest=-24h latest=now "
        "| table _time user | head 100"
    )
    calls = {"n": 0}

    def provider() -> str:
        calls["n"] += 1
        return _payload(unfaithful)

    profile = __import__(
        "app.splunk.capabilities", fromlist=["build_splunk_capability_profile"]
    ).build_splunk_capability_profile(required_saia_tool="saia_generate_spl")
    candidate, validation = candidate_from_universal_utility_authoring(
        trace_id="s5-repair-bound",
        skill="spl_generation",
        user_query="hourly failed-login trend over the last 24 hours",
        telemetry=_Telemetry(),
        profile=profile,
        spl_governance=None,
        llm_raw_output_provider=provider,
    )
    assert candidate is not None
    assert calls["n"] == 2
    trace = candidate.get("utility_spl_draft_trace") or {}
    assert trace.get("repair_attempt_count") == 1
    assert candidate.get("candidate_spl") == ""
    assert candidate.get("spl_authoring_unavailable") is True
    assert "semantic_fidelity_unresolved" in (validation.get("reject_reasons") or [])


def test_repair_prompt_receives_prior_candidate_and_contract() -> None:
    spec = build_spl_intent_spec("hourly failed-login trend over the last 24 hours")
    _system, user = spl_advisory_prompts(
        "hourly failed-login trend over the last 24 hours",
        utility_authoring=True,
        context={
            "semantic_analyst_intent": spec,
            "semantic_analyst_intent_text": "Immutable semantic SPL contract",
            "previous_rejected_candidate": "search index=auth | head 100",
            "deterministic_losses": ["time_series_shape_missing", "arbitrary_head_100"],
            "repair_scope": "syntax_and_declared_semantic_losses_only",
            "do_not_reinterpret_request": True,
        },
        relevance_feedback=["semantic_loss:time_series_shape_missing"],
    )
    assert "Previous rejected candidate_spl:" in user
    assert "search index=auth | head 100" in user
    assert "time_series_shape_missing" in user
    assert "Do NOT reinterpret the user request" in user
    assert "syntax_and_declared_semantic_losses_only" in user


def test_trend_prompt_does_not_force_head_100_or_alert_template() -> None:
    spec = build_spl_intent_spec("hourly failed-login trend over the last 24 hours")
    system, _user = spl_advisory_prompts(
        "hourly failed-login trend over the last 24 hours",
        utility_authoring=True,
        context={"semantic_analyst_intent": spec},
    )
    assert "do NOT add `head 100` arbitrarily" in system or "do NOT end with `head 100`" in system
    assert "Windows Account Lockout / Event 4740" not in system
    assert "Privileged Group Changes / Active Directory" not in system
    assert "timechart" in system.lower()
    assert "Do not invent count/severity thresholds" in system
    assert "ALWAYS end with `head 100`" not in system
    assert "| head 100" not in system
