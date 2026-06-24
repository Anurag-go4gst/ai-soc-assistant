from __future__ import annotations

import pytest

from app.api.routes_chat import chat
from app.demo.scenarios import resolve_demo_scenario_id_for_query
from app.schemas.requests import ChatRequest


def test_resolve_demo_scenario_exact_query_match() -> None:
    query = "Generate SPL for successful login after failures"
    assert resolve_demo_scenario_id_for_query(query) == "successful_login_after_failures"


def test_resolve_demo_scenario_returns_none_for_unknown_query() -> None:
    assert resolve_demo_scenario_id_for_query("show me something random") is None


def test_live_chat_ec_parity_returns_demo_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.routes_chat.settings.ai_soc_live_chat_ec_parity_enabled", True)
    query = "Generate SPL for successful login after failures"
    response = chat(ChatRequest(message=query))
    assert response.demo_mode is True
    assert response.analyst_response is not None
    assert response.analyst_response.response_profile == "spl_only"
    assert response.foundation_sec_governance is None


def test_live_chat_ec_parity_off_uses_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.routes_chat.settings.ai_soc_live_chat_ec_parity_enabled", False)
    query = "Generate SPL for successful login after failures"
    response = chat(ChatRequest(message=query))
    assert response.demo_mode is False
