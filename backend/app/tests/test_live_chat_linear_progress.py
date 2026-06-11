from __future__ import annotations

from pathlib import Path

import pytest

from app.api.routes_chat import chat
from app.chat.pipeline import _response_packaging_status
from app.schemas.requests import ChatRequest
from app.synthesis.models import SynthesisStatus

REPO_ROOT = Path(__file__).resolve().parents[3]
PROGRESS_TS = REPO_ROOT / "frontend/src/lib/investigationProgress.ts"
TRACE_PANEL_TSX = REPO_ROOT / "frontend/src/components/Stage3DTracePanel.tsx"
CHAT_PANEL_TSX = REPO_ROOT / "frontend/src/components/ChatPanel.tsx"


@pytest.fixture(autouse=True)
def _live_chat_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.control_plane_enabled", True)
    monkeypatch.setattr("app.config.settings.ai_soc_live_chat_ec_parity_enabled", False)
    monkeypatch.setattr("app.config.settings.langgraph_orchestration_enabled", False)
    monkeypatch.setattr("app.config.settings.mcp_global_execution_enabled", False)
    monkeypatch.setattr("app.config.settings.telemetry_mode", "none")
    monkeypatch.setattr("app.config.settings.ai_soc_telemetry_sink", "none")


def test_live_chat_linear_progress_shows_all_generic_stages() -> None:
    source = PROGRESS_TS.read_text(encoding="utf-8")
    live_block = source.split("const LIVE_LINEAR_STEPS", 1)[1].split("const LIVE_OPTIONAL_STEP_IDS", 1)[0]

    for label in (
        "Understanding query",
        "Selecting route",
        "Planning workflow",
        "Preparing SPL / evidence path",
        "Checking MCP gate",
        "Retrieving SOC knowledge",
        "Mapping MITRE / severity",
        "Applying LLM / answer governance",
        "Packaging analyst answer",
    ):
        assert label in live_block


def test_live_chat_progress_does_not_claim_mcp_connection_when_disabled() -> None:
    source = PROGRESS_TS.read_text(encoding="utf-8")
    live_block = source.split("const LIVE_LINEAR_STEPS", 1)[1].split("const LIVE_OPTIONAL_STEP_IDS", 1)[0]

    assert "Checking MCP gate" in live_block
    assert "Connecting Splunk MCP" not in live_block
    response = chat(ChatRequest(message="Show SOP for brute-force investigation"))
    assert response.execution is not None
    assert response.execution.status != "executed"


def test_live_chat_progress_does_not_show_ec_fixture_rows() -> None:
    source = TRACE_PANEL_TSX.read_text(encoding="utf-8")
    live_function = source.split("function liveEvidenceRowsFor", 1)[1].split("function RoutePlanShadowDemoCallout", 1)[0]

    assert "if (!trace.demo_mode)" in source
    assert "3 rows returned" not in live_function
    assert "COE synthetic" not in live_function
    assert "No fixture evidence is displayed in live chat" in live_function


def test_live_chat_loader_shows_when_answer_not_ready_after_stages() -> None:
    progress_source = PROGRESS_TS.read_text(encoding="utf-8")
    chat_source = CHAT_PANEL_TSX.read_text(encoding="utf-8")

    assert "Final analyst answer is being packaged" in progress_source
    assert "packaging" in chat_source


def test_live_chat_llm_unavailable_shows_deterministic_fallback() -> None:
    assert (
        _response_packaging_status(
            synthesis_status=SynthesisStatus(enabled=True, status="degraded", reason="LLM HTTP 503"),
            composer_trace={},
            human_review=None,
            final_answer_validation=None,
            analyst_response=object(),
        )
        == "deterministic_fallback"
    )
    chat_source = CHAT_PANEL_TSX.read_text(encoding="utf-8")
    assert "Using governed deterministic answer while LLM narration is unavailable" in chat_source


def test_unsafe_request_progress_ends_in_blocked_review_required() -> None:
    response = chat(ChatRequest(message="Block the source IP and disable this user immediately."))

    assert response.human_review is not None
    assert response.human_review.required is True
    assert response.response_packaging_status == "blocked_review_required"


def test_draft_spl_request_progress_shows_prepare_spl_not_execute_spl() -> None:
    source = PROGRESS_TS.read_text(encoding="utf-8")
    live_block = source.split("const LIVE_LINEAR_STEPS", 1)[1].split("const LIVE_OPTIONAL_STEP_IDS", 1)[0]

    assert "Preparing SPL / evidence path" in live_block
    assert "Running SPL" not in live_block
    assert "Executing SPL" not in live_block
