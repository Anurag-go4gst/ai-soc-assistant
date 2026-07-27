"""Fail-closed canonical handoff persistence (plan item 18)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from app.chat import canonical_handoff_repository as handoff_repo
from app.chat.canonical_handoff_store import get_committed_resource_plan
from app.chat.contracts.canonical_planning_outcome import outcome_from_state
from app.chat.canonical_db import reset_canonical_db_for_tests
from app.chat.planning_telemetry import planning_events, reset_planning_telemetry_for_tests
from app.config import settings
from app.planner.executor import execute_plan_dispatch
from app.tests.support.canonical_flow import run_canonical_flow


@pytest.fixture()
def fail_closed_handoff_store() -> Any:
    handoff_repo.use_in_memory_store_for_tests(False)
    handoff_repo.clear_in_memory_store_for_tests()
    yield
    handoff_repo.clear_in_memory_store_for_tests()
    handoff_repo.use_in_memory_store_for_tests(True)


@pytest.fixture(autouse=True)
def _canonical_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_session_context_enabled", True)
    reset_planning_telemetry_for_tests()
    prior_in_memory = handoff_repo.in_memory_handoff_store_enabled()
    reset_canonical_db_for_tests()
    handoff_repo.clear_in_memory_store_for_tests()
    handoff_repo.use_in_memory_store_for_tests(True)
    monkeypatch.setattr(
        settings,
        "database_url",
        "postgresql://ai_soc:change-me@postgres:5432/ai_soc_assistant",
    )
    yield
    handoff_repo.clear_in_memory_store_for_tests()
    handoff_repo.use_in_memory_store_for_tests(prior_in_memory)
    reset_canonical_db_for_tests()


def _request_failed_emitted() -> bool:
    return any(event.get("event") == "request.failed" for event in planning_events())


def test_clarification_persist_fail_closed_when_db_unavailable(
    fail_closed_handoff_store: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(handoff_repo, "canonical_db_disabled", lambda: False)

    def _raise_on_write(fn: Any) -> Any:
        raise RuntimeError("connection refused")

    monkeypatch.setattr(handoff_repo, "run_in_canonical_unit_of_work", _raise_on_write)

    result = run_canonical_flow("What happened with that alert?")
    outcome = outcome_from_state(result.state)
    assert outcome is not None
    assert outcome.status == "persistence_failed"
    assert result.state.get("canonical_planning_failure", {}).get("outcome") == "persistence_failed"
    assert "evidence_plan" not in result.state
    assert _request_failed_emitted()


def test_handoff_resumption_fail_closed_when_db_unavailable(
    fail_closed_handoff_store: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handoff_repo.use_in_memory_store_for_tests(True)
    clarified = run_canonical_flow("What happened with that alert?")
    clarification = outcome_from_state(clarified.state)
    assert clarification is not None and clarification.clarification is not None

    handoff_repo.use_in_memory_store_for_tests(False)
    monkeypatch.setattr(
        handoff_repo,
        "load_handoff_record",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            handoff_repo.HandoffPersistenceError("handoff_load_failed", operation="handoff_load")
        ),
    )

    resumed = run_canonical_flow(
        "user:alice",
        handoff_resume={
            "handoff_id": clarification.clarification.handoff_id,
            "handoff_version": clarification.clarification.handoff_version,
            "user_answer": "user:alice",
        },
    )
    outcome = outcome_from_state(resumed.state)
    assert outcome is not None
    assert outcome.status == "persistence_failed"
    assert _request_failed_emitted()


def test_resource_plan_commit_fail_closed_blocks_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_save = handoff_repo.save_handoff_record

    def _fail_on_commit(record: Any, **kwargs: Any) -> Any:
        if record.status == "plan_committed":
            raise handoff_repo.HandoffPersistenceError(
                "handoff_commit_failed",
                operation="handoff_persist",
            )
        return original_save(record, **kwargs)

    monkeypatch.setattr("app.chat.canonical_handoff_store.save_handoff_record", _fail_on_commit)

    result = run_canonical_flow("What is CVE-2026-12345?")
    outcome = outcome_from_state(result.state)
    assert outcome is not None
    assert outcome.status == "persistence_failed"
    assert result.evidence_plan is None
    assert _request_failed_emitted()

    handoff_id = str((result.canonical_planning_input or {}).get("trace", {}).get("handoff_id") or "")
    handoff_version = int((result.canonical_planning_input or {}).get("trace", {}).get("handoff_version") or 0)
    if handoff_id and handoff_version:
        assert get_committed_resource_plan(handoff_id, handoff_version) is None

    from app.chat.pipeline import _dispatch_hooks

    dispatch = execute_plan_dispatch(
        {
            "evidence_plan": {
                "resource_plan": {
                    "steps": [],
                    "provenance": {"committed": True, "resource_plan_id": "rp:deadbeef"},
                }
            },
            "trace_id": "trace-failclosed",
        },
        hooks=_dispatch_hooks(),
    )
    assert dispatch.get("canonical_planning_failure") is not None
