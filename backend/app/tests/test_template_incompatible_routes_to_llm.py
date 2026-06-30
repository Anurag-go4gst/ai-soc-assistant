"""Template-incompatible queries route to the LLM compiler, not the legacy skeleton.

Root cause fixed: when a governed template matched but was incompatible with the
user's explicit constraints (use_user_bound_skeleton=True), the legacy
deterministic skeleton produced non-SOC-STD SPL (index=*, eval/table, no agg) and
bypassed the scheduled spl_plan_compiler hop. With dispatch v2 + LLM SPL on, the
incompatible case must route to _candidate_from_llm_fallback instead.
"""

from __future__ import annotations

import pytest

from app.chat import pipeline as p
from app.chat.contracts.spl_candidate import SplCandidateStageResult


def test_force_skeleton_routes_to_llm_when_v2_and_llm_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(p.settings, "ai_soc_pipeline_dispatch_v2_enabled", True)
    monkeypatch.setattr(p.settings, "ai_soc_llm_spl_fallback_enabled", True)

    class _Compat:
        use_user_bound_skeleton = True
        incompatible_reasons = ["drops_explicit_event_code:4625"]

        def to_dict(self):
            return {"compatible": False, "use_user_bound_skeleton": True}

    monkeypatch.setattr(p, "check_template_compatibility", lambda *a, **k: _Compat())

    class _SlotOK:
        valid = True
        normalized_slots: dict = {}
        reject_reasons: list = []

    monkeypatch.setattr(
        "app.spl.template_query_bindings.validate_template_slots_for_render",
        lambda *a, **k: _SlotOK(),
    )

    sentinel = SplCandidateStageResult(
        candidate_payload={"candidate_spl": "search index=<auth_index> | stats count by user", "generation_mode": "llm_spl_advisory_fallback"},
        validation_payload={"approved": False},
    )
    called = {"n": 0}

    def _fake_llm(**kwargs):
        called["n"] += 1
        # The incompatible reasons must be threaded into the LLM context.
        assert "template_incompatible_reasons" in (kwargs.get("llm_context") or {})
        return sentinel

    monkeypatch.setattr(p, "_candidate_from_llm_fallback", _fake_llm)

    result = p._candidate_from_default_template(
        trace_id="t",
        skill="spl_generation",
        user_query="Which users have excessive failed logins across Windows hosts in the last hour",
        template_id="auth_failed_login_spike",
    )
    assert called["n"] == 1, "incompatible template must route to the LLM fallback"
    candidate, _validation = result  # tuple-unpackable
    assert candidate["generation_mode"] == "llm_spl_advisory_fallback"


def test_force_skeleton_keeps_legacy_when_flags_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """v2 off -> legacy skeleton path unchanged (no LLM route, byte-identical)."""
    monkeypatch.setattr(p.settings, "ai_soc_pipeline_dispatch_v2_enabled", False)

    class _Compat:
        use_user_bound_skeleton = True
        incompatible_reasons = []

        def to_dict(self):
            return {"compatible": False}

    monkeypatch.setattr(p, "check_template_compatibility", lambda *a, **k: _Compat())

    def _must_not_call(**kwargs):
        raise AssertionError("LLM fallback must not run when v2 is off")

    monkeypatch.setattr(p, "_candidate_from_llm_fallback", _must_not_call)
    # Should not raise (LLM route skipped); returns the legacy skeleton path.
    result = p._candidate_from_default_template(
        trace_id="t",
        skill="spl_generation",
        user_query="Which users have excessive failed logins",
        template_id="auth_failed_login_spike",
    )
    assert result is not None
