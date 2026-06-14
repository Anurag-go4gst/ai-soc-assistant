"""Phase 2 (#4): Experience Center isolation — demo fixtures never call a live provider.

The demo (`coe_synthetic_fixture`) early-return in ``routes_chat`` must produce its
answer from ``run_demo_scenario`` without entering the live pipeline. This test makes
the live sidecar/composer entry points raise, then proves a demo scenario still
resolves and renders.
"""

from __future__ import annotations

import pytest

from app.demo.scenarios import resolve_demo_scenario_id_for_query, run_demo_scenario


def _first_demo_query() -> str:
    from app.demo.scenarios import SCENARIOS

    for scenario in SCENARIOS.values():
        if getattr(scenario, "query", None):
            return str(scenario.query)
    return ""


def test_demo_scenario_renders_without_live_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    # Any attempt to build/invoke a live LLM client must blow up if reached.
    import app.llm.sidecar_clients as sidecar_clients
    import app.llm.clients.endpoint_resolver as resolver

    def _boom(*_args, **_kwargs):
        raise AssertionError("EC path must not call a live provider")

    monkeypatch.setattr(sidecar_clients, "invoke_sidecar_role", _boom)
    monkeypatch.setattr(resolver, "build_synthesis_client_from_settings", _boom)
    monkeypatch.setattr(resolver, "build_failover_chat_client", _boom)

    query = _first_demo_query()
    if not query:
        pytest.skip("no demo scenario query available in this build")

    scenario_id = resolve_demo_scenario_id_for_query(query)
    assert scenario_id, "expected a demo scenario to match its own trigger query"
    payload = run_demo_scenario(scenario_id)
    assert isinstance(payload, dict)
    # Fixture provenance, not a live run.
    serialized = str(payload).lower()
    assert "coe_synthetic_fixture" in serialized or payload.get("note") or payload.get("message")
