"""Clarification handoff resumption integration tests on PostgreSQL."""

from __future__ import annotations

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
from app.chat.canonical_db import reset_canonical_db_for_tests
from app.tests.integration.conftest import new_integration_handoff_id

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _postgres_runtime(postgres_integration_runtime: None) -> None:
    return None


def _save_pending(
    *,
    handoff_id: str,
    session_id: str,
    unresolved_fields: list[str] | None = None,
) -> None:
    save_clarification_handoff(
        handoff_id=handoff_id,
        handoff_version=1,
        canonical_planning_input={
            "routing": {"processing_lane": "known", "match_path": "out_of_registry"},
            "detail_state": {
                "field_values": {},
                "field_sources": {},
                "present_fields": [],
                "missing_fields": unresolved_fields or ["alert_id"],
            },
        },
        gap_resolution=None,
        unresolved_fields=unresolved_fields or ["alert_id"],
        clarification_reason="missing_alert_id",
        trace_id="int-trace",
        session_id=session_id,
        original_query="What happened with that alert?",
        original_skill="alert_summary",
        original_use_case_id="auth_failed_login_spike",
        original_answer_goal="live_investigation",
        initial_tier="T4",
        resolved_tier="T4",
    )


def test_postgres_resume_advances_version_once(postgres_migrated: str) -> None:
    handoff_id = new_integration_handoff_id("resume")
    session_id = "sess-pg-resume"
    _save_pending(handoff_id=handoff_id, session_id=session_id)
    result = resume_clarification_handoff(
        handoff_id=handoff_id,
        handoff_version=1,
        user_answer="ALT-PG-001",
        session_id=session_id,
    )
    assert result.record.handoff_version == 2
    assert result.idempotent_replay is False
    prior = get_handoff(handoff_id, 1)
    next_version = get_handoff(handoff_id, 2)
    assert prior is not None and prior.status == "resumed"
    assert next_version is not None and next_version.status == "in_progress"


def test_postgres_duplicate_answer_returns_existing_next_version(postgres_migrated: str) -> None:
    handoff_id = new_integration_handoff_id("dup")
    session_id = "sess-pg-dup"
    _save_pending(handoff_id=handoff_id, session_id=session_id)
    first = resume_clarification_handoff(
        handoff_id=handoff_id,
        handoff_version=1,
        user_answer="ALT-DUP",
        session_id=session_id,
    )
    second = resume_clarification_handoff(
        handoff_id=handoff_id,
        handoff_version=1,
        user_answer="ALT-DUP",
        session_id=session_id,
    )
    assert first.idempotent_replay is False
    assert second.idempotent_replay is True
    assert first.record.handoff_version == second.record.handoff_version == 2


def test_postgres_concurrent_resume_creates_single_next_version(postgres_migrated: str) -> None:
    handoff_id = new_integration_handoff_id("race")
    session_id = "sess-pg-race"
    _save_pending(handoff_id=handoff_id, session_id=session_id)

    def _resume() -> Any:
        return merge_clarification_answer(
            handoff_id=handoff_id,
            handoff_version=1,
            user_answer="ALT-RACE",
            session_id=session_id,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: _resume(), range(2)))

    versions = {result.record.handoff_version for result in results}
    assert versions == {2}
    assert sum(1 for result in results if result.idempotent_replay) == 1


def test_postgres_cross_process_restart_then_resume(postgres_migrated: str) -> None:
    handoff_id = new_integration_handoff_id("xproc")
    session_id = "sess-xproc"
    _save_pending(handoff_id=handoff_id, session_id=session_id)
    reset_canonical_db_for_tests()
    result = resume_clarification_handoff(
        handoff_id=handoff_id,
        handoff_version=1,
        user_answer="ALT-XPROC",
        session_id=session_id,
    )
    assert result.record.handoff_version == 2


def test_postgres_expired_handoff_cannot_resume(postgres_migrated: str) -> None:
    handoff_id = new_integration_handoff_id("expired")
    session_id = "sess-pg-expired"
    _save_pending(handoff_id=handoff_id, session_id=session_id)
    record = get_handoff(handoff_id, 1)
    assert record is not None
    expired = record.model_copy(update={"expires_at": datetime.now(UTC) - timedelta(minutes=1)})
    handoff_repo.save_handoff_record(expired, refresh_ttl=False)
    with pytest.raises(ClarificationResumeError, match="handoff_not_found|handoff_expired"):
        merge_clarification_answer(
            handoff_id=handoff_id,
            handoff_version=1,
            user_answer="ALT-EXPIRED",
            session_id=session_id,
        )


def test_postgres_completed_handoff_cannot_resume(postgres_migrated: str) -> None:
    handoff_id = new_integration_handoff_id("done")
    session_id = "sess-pg-done"
    _save_pending(handoff_id=handoff_id, session_id=session_id)
    record = get_handoff(handoff_id, 1)
    assert record is not None
    committed = record.model_copy(
        update={"status": "plan_committed", "committed_resource_plan_id": "rp:test"}
    )
    handoff_repo.save_handoff_record(committed, refresh_ttl=False)
    with pytest.raises(ClarificationResumeError, match="handoff_already_completed"):
        merge_clarification_answer(
            handoff_id=handoff_id,
            handoff_version=1,
            user_answer="ALT-DONE",
            session_id=session_id,
        )
