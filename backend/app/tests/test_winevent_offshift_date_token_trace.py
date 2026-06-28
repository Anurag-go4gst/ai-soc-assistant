"""Regression: Winevent off-shift date/time tokens must not bind as a host.

A query like "... outside business hours on 6/22" previously bound the date
fragment "6" as a host, poisoning the generated SPL with a spurious
`dest_host_norm="6"` filter (would match nothing). The off-shift hour extraction
and wineventlog binding must remain intact while the date token is dropped.
"""

from __future__ import annotations

import pytest

from app.chat.pipeline import build_live_chat_response
from app.config import settings
from app.schemas.requests import ChatRequest
from app.spl.spl_slot_binding_validator import extract_natural_language_slots

_WINEVENT_DATE = "Show Event 4624 logons outside business hours on 6/22"


@pytest.fixture(autouse=True)
def _flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "legacy_selected_skill_authority_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_spl_template_governance_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_spl_fallback_enabled", False)


def _winevent_spl() -> str:
    payload = build_live_chat_response(ChatRequest(message=_WINEVENT_DATE)).model_dump(mode="json")
    cs = payload.get("candidate_spl") or {}
    return str(cs.get("candidate_spl") or "") if isinstance(cs, dict) else str(cs or "")


@pytest.mark.parametrize(
    "query",
    [
        "Show Event 4624 logons outside business hours on 6/22",
        "logons on 06-22 review",
        "logons outside 06:00-22:00",
        "Event 4624 on 22",
    ],
)
def test_date_or_time_token_does_not_bind_host(query: str) -> None:
    assert "host" not in extract_natural_language_slots(query)


@pytest.mark.parametrize(
    "query,expected",
    [
        ("logons on dc01", "dc01"),
        ("failed logins on web-prod-01", "web-prod-01"),
    ],
)
def test_real_hostname_still_binds(query: str, expected: str) -> None:
    assert extract_natural_language_slots(query).get("host") == expected


def test_winevent_offshift_spl_has_no_spurious_host_clause() -> None:
    spl = _winevent_spl()
    assert 'dest_host_norm="6"' not in spl
    assert 'dest_host_norm="06-22"' not in spl


def test_winevent_offshift_spl_preserves_index_event_and_hour_filter() -> None:
    spl = _winevent_spl()
    assert "index=wineventlog" in spl
    assert "4624" in spl
    assert "login_hour < 6" in spl and "login_hour >= 22" in spl


def test_winevent_offshift_remains_review_only_no_execution() -> None:
    payload = build_live_chat_response(ChatRequest(message=_WINEVENT_DATE)).model_dump(mode="json")
    contract = payload.get("run_contract") or {}
    assert contract.get("execution_authorized") is False
    assert payload.get("workflow_plan", {}).get("execution_enabled") is False
