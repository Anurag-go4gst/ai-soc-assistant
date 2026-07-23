"""E2E two-turn SPL human-in-the-loop contract on live ``/chat``.

Turn 1: governed candidate SPL is validated and normalized; analyst sees
``spl_execution_confirmation``; ``executed_spl`` stays null.

Turn 2: analyst ``confirm`` or ``update_spl`` → deterministic guardrails → mock MCP
executes only the approved normalized SPL (never raw ``candidate_spl`` alone).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from app.api.routes_chat import chat
from app.chat import pipeline as pl
from app.chat.session_store import clear_all_session_pins_for_tests
from app.config import settings
from app.safeguards.spl_validator import validate_spl
from app.schemas.requests import ChatRequest

QUERY = (
    "Show top users with failed login count in the last 24 hours "
    "and exclude service accounts"
)
BAD_ANALYST_SPL = "search index=* | delete"
GOOD_ANALYST_SPL = (
    "search index=pgcil_soc sourcetype=pgcil:auth earliest=-24h latest=now "
    "action=failure | stats count by user | head 100"
)


@pytest.fixture(autouse=True)
def _spl_hil_chat_runtime(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Mock MCP + confirmation on; skip shadow precondition blocks for this probe query."""
    monkeypatch.setenv("MCP_MODE", "mock")
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", "true")

    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_session_context_enabled", True)
    monkeypatch.setattr(settings, "mcp_global_execution_enabled", True)
    monkeypatch.setattr(settings, "mcp_server_mock_execution_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_require_spl_execution_confirmation", True)
    monkeypatch.setattr(settings, "ai_soc_catalogue_auto_execute_enabled", False)
    monkeypatch.setattr(settings, "langgraph_orchestration_enabled", False)
    monkeypatch.setattr(settings, "telemetry_mode", "none")
    monkeypatch.setattr(settings, "ai_soc_telemetry_sink", "none")
    monkeypatch.setattr(settings, "ai_soc_demo_or_lab_execution_mode", True)
    monkeypatch.setattr(settings, "ai_soc_allow_mock_execution_without_hil_in_demo", True)

    original = pl.apply_precondition_evaluation_to_shadow

    def _skip_precondition_block(shadow: dict[str, Any]) -> dict[str, Any]:
        payload = original(shadow)
        payload["evaluation_skipped"] = True
        shadow["precondition_evaluation"] = payload
        return payload

    monkeypatch.setattr(pl, "apply_precondition_evaluation_to_shadow", _skip_precondition_block)
    clear_all_session_pins_for_tests()
    yield
    clear_all_session_pins_for_tests()


def _turn1(message: str = QUERY) -> tuple[Any, str]:
    response = chat(ChatRequest(message=message))
    session_id = response.session_context_status.session_id if response.session_context_status else None
    assert session_id
    return response, session_id


def test_turn1_surfaces_normalized_spl_for_confirmation_not_execution() -> None:
    response, _session_id = _turn1()

    assert response.selected_skill == "attack_discovery"
    assert response.candidate_spl is not None
    assert response.candidate_spl.candidate_spl
    assert response.spl_validation is not None
    assert response.spl_validation.approved is True
    assert response.spl_validation.normalized_spl
    assert response.execution is not None
    assert response.execution.status == "requires_human_review"
    assert response.execution.executed_spl is None
    assert response.human_review is not None
    assert response.human_review.review_type == "spl_execution_confirmation"
    assert response.human_review.proposed_normalized_spl == response.spl_validation.normalized_spl
    assert "confirm_execution" in (response.human_review.allowed_actions or [])


def test_turn2_confirm_executes_normalized_spl_not_unvalidated_candidate() -> None:
    turn1, session_id = _turn1()
    normalized = turn1.spl_validation.normalized_spl
    assert normalized

    turn2 = chat(
        ChatRequest(
            message=QUERY,
            session_id=session_id,
            execution_review_action="confirm",
        )
    )

    assert turn2.execution is not None
    assert turn2.execution.status == "executed"
    assert turn2.execution.executed_spl == normalized
    assert turn2.human_review is not None
    assert turn2.human_review.required is False


def test_turn2_update_spl_invalid_blocked_by_guardrails() -> None:
    turn1, session_id = _turn1()

    turn2 = chat(
        ChatRequest(
            message=QUERY,
            session_id=session_id,
            execution_review_action="update_spl",
            analyst_provided_spl=BAD_ANALYST_SPL,
        )
    )

    assert turn2.execution is not None
    assert turn2.execution.status == "requires_human_review"
    assert turn2.execution.executed_spl is None
    assert turn2.human_review is not None
    assert turn2.human_review.review_type == "spl_revision"
    assert turn2.human_review.reason == "analyst_updated_spl_validation_failed"
    assert turn1.spl_validation.normalized_spl != BAD_ANALYST_SPL


def test_turn2_update_spl_valid_passes_guardrails_and_executes() -> None:
    turn1, session_id = _turn1()
    analyst_validation = validate_spl(GOOD_ANALYST_SPL)
    assert analyst_validation.get("approved") is True

    turn2 = chat(
        ChatRequest(
            message=QUERY,
            session_id=session_id,
            execution_review_action="update_spl",
            analyst_provided_spl=GOOD_ANALYST_SPL,
        )
    )

    assert turn2.execution is not None
    assert turn2.execution.status == "executed"
    assert turn2.execution.executed_spl == analyst_validation["normalized_spl"]
    assert turn2.execution.executed_spl != turn1.spl_validation.normalized_spl
