"""G1 — Experience Center backend isolation."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from app.demo.ec_turn import run_experience_center_turn
from app.demo.fixtures.registry import FLAGSHIP_SCENARIO_IDS
from app.demo.scenarios import run_demo_scenario
from app.schemas.responses import PlaceholderResponse

REPO = Path(__file__).resolve().parents[3]


def test_g1_no_new_production_import_of_app_demo() -> None:
    known_preexisting = {
        "backend/app/api/routes_chat.py",
        "backend/app/api/routes_chat_stream.py",
    }
    offenders: list[str] = []
    for folder in (
        REPO / "backend/app/chat/pipeline.py",
        REPO / "backend/app/graph",
        REPO / "backend/app/planner",
        REPO / "backend/app/routing",
        REPO / "backend/app/api/routes_chat.py",
        REPO / "backend/app/api/routes_chat_stream.py",
        REPO / "backend/app/api/routes_actions.py",
    ):
        paths = [folder] if folder.is_file() else sorted(folder.rglob("*.py"))
        for path in paths:
            text = path.read_text(encoding="utf-8")
            if "from app.demo" in text or "import app.demo" in text:
                rel = str(path.relative_to(REPO))
                if rel not in known_preexisting:
                    offenders.append(rel)
    assert not offenders


def test_g1_flagships_do_not_call_live_connectors_or_actions() -> None:
    demo = REPO / "backend/app/demo"
    for path in demo.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "from app.api.routes_actions" not in text
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {"call_tool", "evaluate_mcp_execution"}


def test_g1_placeholder_response_unchanged_and_legacy_helper() -> None:
    from subprocess import run

    result = run(
        ["git", "diff", "--name-only", "--", "backend/app/schemas/responses.py"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.stdout.strip() == ""
    payload = run_demo_scenario("s2_ai_prompt_injection")
    assert PlaceholderResponse(**payload).demo_mode is True


def test_g1_demo_http_envelope_is_experience_center_response() -> None:
    envelope = run_experience_center_turn("s1_governed_splunk_investigation", session_id="g1")
    dumped = envelope.model_dump()
    assert dumped["production_side_effect"] is False
    assert dumped["ec_provenance"]["live_llm_called"] is False
    assert dumped["ec_provenance"]["live_mcp_called"] is False
    for scenario_id in FLAGSHIP_SCENARIO_IDS:
        item = run_experience_center_turn(scenario_id, session_id=f"g1-{scenario_id}")
        dumped = item.model_dump()
        assert dumped.get("production_side_effect") is False
        assert dumped["ec_provenance"].get("live_llm_called") is False
        assert dumped["ec_provenance"].get("live_mcp_called") is False


def test_g1_ec_actions_module_has_no_production_session() -> None:
    from app.demo import ec_actions

    source = inspect.getsource(ec_actions)
    assert "routes_actions" not in source
    assert "SessionLocal" not in source
    assert "ai_trace_runs" not in source
