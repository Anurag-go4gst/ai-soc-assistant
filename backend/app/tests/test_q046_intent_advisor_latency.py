"""q0.q046 frozen-T0 template-bound rows bound the intent advisor (latency closure).

q0.q046 ("Which users have excessive failed logins?") is an exact-105 +
catalogue match (``exact_105_plus_use_case_catalog``) bound to the
``auth_failed_login_spike`` review-only template. Its intent authority is frozen
T0, but a row-authority/enrichment demotion (``row_authority_not_ready``) keeps
the intent advisor on the live path. The advisor is advisory-only here (it cannot
change the deterministic route, nor supply the deterministic SPL binding the
template is missing), so its wall-clock is sharply bounded: a slow/timing-out
call (~100s on the on-host 8B) must fall back deterministically in a few seconds
while the review-only answer contract is preserved unchanged.

The advisory hop is still *scheduled* (the weak-exact-105 row may consult the LLM
when it is fast) — see ``test_intent_advisor_t0_skip`` for the unchanged
skip-vs-run scheduling invariants.
"""

from __future__ import annotations

import pytest

from app.chat.contracts.llm_intent_advisory import LLMIntentAdvisory
from app.chat.pipeline import (
    _FROZEN_T0_INTENT_ADVISOR_BOUND_SECONDS,
    build_live_chat_response,
    graph_node_query_to_intent,
)
from app.config import settings
from app.query_understanding.parser import understand_query
from app.schemas.requests import ChatRequest

_Q046 = "Which users have excessive failed logins?"
_Q010 = "Which hosts are generating the most SMB traffic?"
_BROAD_GUIDED_HUNT = (
    "Hunt for CI/CD supply-chain compromise indicators across our environment"
)


@pytest.fixture(autouse=True)
def _flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "legacy_selected_skill_authority_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_llm_intent_advisor_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")
    monkeypatch.setattr(settings, "ai_soc_llm_final_synthesis_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_live_synthesis_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_spl_template_governance_enabled", True)


def _payload(question: str) -> dict:
    return build_live_chat_response(ChatRequest(message=question)).model_dump(mode="json")


def _hil(payload: dict) -> dict:
    return payload.get("human_review") or {}


def test_q046_intent_advisor_hop_is_sharply_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    """The advisory hop runs but with a capped wall-clock and a clear trace reason."""
    captured: dict[str, float | None] = {}

    def _fake_advisor(*_args, timeout_seconds=None, **_kwargs):
        captured["timeout_seconds"] = timeout_seconds
        # Simulate a fast advisory result so the hop is genuinely invoked.
        return LLMIntentAdvisory(llm_called=True, dropped_reasons=["test_advisory_called"])

    monkeypatch.setattr("app.chat.pipeline.generate_llm_intent_advisory", _fake_advisor)

    qu = understand_query(_Q046)
    assert qu.deterministic_match_path == "exact_105_plus_use_case_catalog"
    state = graph_node_query_to_intent(
        {
            "request": ChatRequest(message=_Q046),
            "effective_query": _Q046,
            "query_understanding": qu,
            "routed": {"skill": "attack_discovery"},
        }
    )
    advisory = state.get("llm_intent_advisory")
    # Hop was scheduled (not skipped) and bounded to the frozen-T0 cap.
    assert advisory.llm_called is True
    assert captured["timeout_seconds"] is not None
    assert captured["timeout_seconds"] <= _FROZEN_T0_INTENT_ADVISOR_BOUND_SECONDS
    trace = advisory.scheduling_trace or {}
    assert trace.get("intent_advisor_bound_reason") == "exact_template_bound_intent_advisor_bounded"


def test_q046_contract_preserved_under_bound() -> None:
    hil = _hil(_payload(_Q046))
    assert hil.get("review_type") == "spl_revision"
    assert hil.get("reason") == "template_review_required"
    # Execution stays disabled — bounding the advisor never authorizes execution.
    assert _payload(_Q046)["workflow_plan"]["execution_enabled"] is False


def test_q046_validator_details_remain_visible() -> None:
    payload = _payload(_Q046)
    blob = repr(payload.get("control_plane_trace") or {}) + repr(payload.get("human_review") or {})
    # The deterministic SPL validator finding must not be hidden by the bound.
    assert "missing_binding:group_by_user" in blob


def test_q010_smb_review_path_not_regressed() -> None:
    hil = _hil(_payload(_Q010))
    assert hil.get("review_type") == "spl_revision"
    assert hil.get("reason") != "not_in_manifest"
    assert _payload(_Q010)["workflow_plan"]["execution_enabled"] is False


def test_broad_guided_hunt_pr53_still_skips_and_routes_guided() -> None:
    payload = _payload(_BROAD_GUIDED_HUNT)
    advisory = (payload.get("control_plane_trace") or {}).get("llm_advisory_trace") or {}
    assert payload["workflow_plan"]["skill"] == "guided_investigation"
    assert advisory["llm_called"] is False
    assert "guided_hunt_deterministic_routing" in advisory["llm_dropped_reasons"]
    assert payload["workflow_plan"]["execution_enabled"] is False
