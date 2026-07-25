"""Clarification handoff resumption integration tests (plan item 19).

Postgres concurrency cases are extended in item 24 under ``app/tests/integration/``.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.chat import canonical_handoff_repository as handoff_repo
from app.chat.canonical_handoff_resumption import (
    ClarificationResumeError,
    merge_clarification_answer,
    resume_clarification_handoff,
)
from app.chat.canonical_handoff_store import get_handoff, save_clarification_handoff
from app.chat.contracts.canonical_planning_outcome import outcome_from_state
from app.config import settings
from app.tests.support.canonical_flow import run_canonical_flow


@pytest.fixture(autouse=True)
def _canonical_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_session_context_enabled", True)


def _save_pending_clarification(
    *,
    handoff_id: str = "cpi:clarify-test",
    handoff_version: int = 1,
    session_id: str = "sess-clarify",
    unresolved_fields: list[str] | None = None,
) -> None:
    save_clarification_handoff(
        handoff_id=handoff_id,
        handoff_version=handoff_version,
        canonical_planning_input={
            "routing": {"processing_lane": "known", "match_path": "out_of_registry"},
            "detail_state": {"field_values": {}, "field_sources": {}, "present_fields": [], "missing_fields": unresolved_fields or ["alert_id"]},
        },
        gap_resolution=None,
        unresolved_fields=unresolved_fields or ["alert_id"],
        clarification_reason="missing_alert_id",
        trace_id="trace-clarify",
        session_id=session_id,
        original_query="What happened with that alert?",
        original_skill="alert_summary",
        original_use_case_id="auth_failed_login_spike",
        original_answer_goal="live_investigation",
        initial_tier="T4",
        resolved_tier="T4",
    )


def test_resume_advances_version_and_plans() -> None:
    first = run_canonical_flow("What happened with that alert?", session_id="sess-resume-1")
    clarification = outcome_from_state(first.state)
    assert clarification is not None and clarification.clarification is not None

    resumed = run_canonical_flow(
        "ALT-2024-0891",
        session_id="sess-resume-1",
        handoff_resume={
            "handoff_id": clarification.clarification.handoff_id,
            "handoff_version": clarification.clarification.handoff_version,
            "user_answer": "ALT-2024-0891",
        },
    )
    outcome = outcome_from_state(resumed.state)
    assert outcome is not None and outcome.status == "planned"

    prior = get_handoff(clarification.clarification.handoff_id, clarification.clarification.handoff_version)
    next_version = get_handoff(clarification.clarification.handoff_id, clarification.clarification.handoff_version + 1)
    assert prior is not None and prior.status == "resumed"
    assert next_version is not None and next_version.handoff_version == clarification.clarification.handoff_version + 1


def test_resume_preserves_original_metadata() -> None:
    _save_pending_clarification(handoff_id="cpi:preserve", session_id="sess-preserve")
    prior = get_handoff("cpi:preserve", 1)
    assert prior is not None
    result = resume_clarification_handoff(
        handoff_id="cpi:preserve",
        handoff_version=1,
        user_answer="ALT-PRESERVE",
        session_id="sess-preserve",
    )
    assert result.record.original_skill == prior.original_skill
    assert result.record.original_answer_goal == prior.original_answer_goal
    assert result.record.original_use_case_id == prior.original_use_case_id


def test_duplicate_answer_returns_existing_next_version() -> None:
    _save_pending_clarification(handoff_id="cpi:dup", session_id="sess-dup")
    first = resume_clarification_handoff(
        handoff_id="cpi:dup",
        handoff_version=1,
        user_answer="ALT-1",
        session_id="sess-dup",
    )
    second = resume_clarification_handoff(
        handoff_id="cpi:dup",
        handoff_version=1,
        user_answer="ALT-1",
        session_id="sess-dup",
    )
    assert first.idempotent_replay is False
    assert second.idempotent_replay is True
    assert first.record.handoff_version == second.record.handoff_version == 2
    assert len({first.record.model_dump_json(), second.record.model_dump_json()}) == 1


def test_session_mismatch_rejected() -> None:
    _save_pending_clarification(handoff_id="cpi:session", session_id="sess-owner")
    with pytest.raises(ClarificationResumeError, match="session_ownership_mismatch"):
        merge_clarification_answer(
            handoff_id="cpi:session",
            handoff_version=1,
            user_answer="ALT-2",
            session_id="sess-other",
        )


def test_expired_handoff_cannot_resume() -> None:
    _save_pending_clarification(handoff_id="cpi:expired", session_id="sess-expired")
    record = get_handoff("cpi:expired", 1)
    assert record is not None
    expired = record.model_copy(update={"expires_at": datetime.now(UTC) - timedelta(minutes=1)})
    handoff_repo.test_store_write("cpi:expired", 1, expired)
    with pytest.raises(ClarificationResumeError, match="handoff_expired"):
        merge_clarification_answer(
            handoff_id="cpi:expired",
            handoff_version=1,
            user_answer="ALT-3",
            session_id="sess-expired",
        )


def test_completed_handoff_cannot_resume() -> None:
    _save_pending_clarification(handoff_id="cpi:done", session_id="sess-done")
    record = get_handoff("cpi:done", 1)
    assert record is not None
    committed = record.model_copy(update={"status": "plan_committed", "committed_resource_plan_id": "rp:test"})
    handoff_repo.test_store_write("cpi:done", 1, committed)
    with pytest.raises(ClarificationResumeError, match="handoff_already_completed"):
        merge_clarification_answer(
            handoff_id="cpi:done",
            handoff_version=1,
            user_answer="ALT-4",
            session_id="sess-done",
        )


def test_concurrent_resume_creates_single_next_version() -> None:
    _save_pending_clarification(handoff_id="cpi:race", session_id="sess-race")

    def _resume() -> Any:
        return merge_clarification_answer(
            handoff_id="cpi:race",
            handoff_version=1,
            user_answer="ALT-RACE",
            session_id="sess-race",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: _resume(), range(2)))

    versions = {result.record.handoff_version for result in results}
    assert versions == {2}
    replay_count = sum(1 for result in results if result.idempotent_replay)
    assert replay_count == 1
    assert get_handoff("cpi:race", 2) is not None


@pytest.mark.integration
def test_postgres_resume_round_trip() -> None:
    database_url = (os.environ.get("DATABASE_URL") or settings.database_url or "").strip()
    if not database_url or "change-me@postgres" in database_url:
        pytest.skip("PostgreSQL not configured for integration resume test")

    handoff_repo.use_in_memory_store_for_tests(False)
    try:
        _save_pending_clarification(handoff_id="cpi:pg", session_id="sess-pg")
        result = resume_clarification_handoff(
            handoff_id="cpi:pg",
            handoff_version=1,
            user_answer="ALT-PG",
            session_id="sess-pg",
        )
        assert result.record.handoff_version == 2
        assert get_handoff("cpi:pg", 1) is not None
    finally:
        handoff_repo.clear_in_memory_store_for_tests()
        handoff_repo.use_in_memory_store_for_tests(True)
