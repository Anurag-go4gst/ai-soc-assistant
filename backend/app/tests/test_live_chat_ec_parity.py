from __future__ import annotations

from pathlib import Path

from app.demo.scenarios import resolve_demo_scenario_id_for_query


def test_resolve_demo_scenario_exact_query_match() -> None:
    query = "Generate SPL for successful login after failures"
    assert resolve_demo_scenario_id_for_query(query) == "successful_login_after_failures"


def test_resolve_demo_scenario_returns_none_for_unknown_query() -> None:
    assert resolve_demo_scenario_id_for_query("show me something random") is None


def test_production_chat_routes_never_import_or_dispatch_demo_scenarios() -> None:
    api_root = Path(__file__).resolve().parents[1] / "api"
    for filename in ("routes_chat.py", "routes_chat_stream.py"):
        source = (api_root / filename).read_text(encoding="utf-8")
        assert "from app.demo" not in source
        assert "run_demo_scenario" not in source
        assert "resolve_demo_scenario_id_for_query" not in source
