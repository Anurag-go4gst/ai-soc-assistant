"""Execution idempotency for committed ResourcePlan steps (plan item 20)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from app.chat.canonical_execution_idempotency import (
    AcquireOutcome,
    acquire_execution_step,
    build_idempotency_key,
    build_downstream_idempotency_key,
    clear_in_memory_store_for_tests,
    complete_execution_step,
    fail_execution_step,
    operation_contract_for_step,
    inspect_execution_step,
    run_idempotent_execution_step,
    use_in_memory_store_for_tests,
)


@pytest.fixture(autouse=True)
def _idempotency_memory() -> None:
    use_in_memory_store_for_tests(True)
    clear_in_memory_store_for_tests()
    yield
    clear_in_memory_store_for_tests()


def _key(*, handoff_version: int = 1) -> dict[str, str | int]:
    return {
        "resource_plan_id": "rp:test",
        "handoff_id": "h-1",
        "handoff_version": handoff_version,
        "step_id": "s1",
        "operation": "mcp_discovery:mcp_tool:foo",
    }


def test_duplicate_dispatch_returns_stored_result() -> None:
    params = _key()
    calls = {"count": 0}

    def _first() -> dict:
        calls["count"] += 1
        return {"value": 1}

    def _second() -> dict:
        calls["count"] += 1
        return {"value": 99}

    first = run_idempotent_execution_step(
        **params,
        side_effecting=True,
        lease_owner="worker-a",
        execute=_first,
    )
    assert first[0] == AcquireOutcome.EXECUTE
    second = run_idempotent_execution_step(
        **params,
        side_effecting=True,
        lease_owner="worker-b",
        execute=_second,
    )
    assert second[0] == AcquireOutcome.REPLAY
    assert second[1] == {"value": 1}
    assert calls["count"] == 1


def test_concurrent_dispatch_two_workers_second_gets_in_progress() -> None:
    params = _key()
    barrier = __import__("threading").Barrier(2)

    def _worker_a() -> AcquireOutcome:
        acquired = acquire_execution_step(**params, lease_owner="worker-a", side_effecting=True)
        barrier.wait(timeout=2)
        return acquired.outcome

    def _worker_b() -> AcquireOutcome:
        barrier.wait(timeout=2)
        acquired = acquire_execution_step(**params, lease_owner="worker-b", side_effecting=True)
        return acquired.outcome

    with ThreadPoolExecutor(max_workers=2) as pool:
        future_a = pool.submit(_worker_a)
        future_b = pool.submit(_worker_b)
        outcomes = {future_a.result(timeout=5), future_b.result(timeout=5)}

    assert outcomes == {AcquireOutcome.EXECUTE, AcquireOutcome.IN_PROGRESS}


def test_concurrent_run_invokes_at_most_one_worker() -> None:
    params = _key()
    calls = {"count": 0}

    def _execute() -> dict:
        calls["count"] += 1
        return {"ok": True}

    with ThreadPoolExecutor(max_workers=2) as pool:
        future_a = pool.submit(
            run_idempotent_execution_step,
            **params,
            side_effecting=True,
            lease_owner="worker-a",
            execute=_execute,
        )
        future_b = pool.submit(
            run_idempotent_execution_step,
            **params,
            side_effecting=True,
            lease_owner="worker-b",
            execute=_execute,
        )
        outcomes = {future_a.result(timeout=5)[0], future_b.result(timeout=5)[0]}

    assert AcquireOutcome.EXECUTE in outcomes
    assert calls["count"] == 1


def test_worker_crash_after_running_stale_lease_recovery() -> None:
    params = _key()
    key = build_idempotency_key(
        resource_plan_id=str(params["resource_plan_id"]),
        handoff_id=str(params["handoff_id"]),
        handoff_version=int(params["handoff_version"]),
        step_id=str(params["step_id"]),
        operation=str(params["operation"]),
    )
    acquired = acquire_execution_step(**params, lease_owner="crashed-worker", side_effecting=True)
    assert acquired.outcome == AcquireOutcome.EXECUTE
    fail_execution_step(idempotency_key=key, result={"error": "crash"}, retryable=True)
    record = inspect_execution_step(
        resource_plan_id=str(params["resource_plan_id"]),
        step_id=str(params["step_id"]),
        operation=str(params["operation"]),
        handoff_id=str(params["handoff_id"]),
        handoff_version=int(params["handoff_version"]),
    )
    assert record is not None
    from app.chat import canonical_execution_idempotency as store

    stale = record.model_copy(
        update={
            "status": "running",
            "lease_owner": "crashed-worker",
            "lease_expires_at": datetime.now(UTC) - timedelta(seconds=5),
        }
    )
    store._TEST_STORE[key] = stale.model_dump(mode="json")

    recovered = acquire_execution_step(
        **params,
        lease_owner="worker-b",
        side_effecting=True,
        operation_contract="side_effecting_without_stable_idempotency",
    )
    assert recovered.outcome == AcquireOutcome.REQUIRES_RECONCILIATION
    assert recovered.stored_result["reason"] == "execution_outcome_uncertain"


def test_stale_read_only_lease_reacquires_for_retry() -> None:
    params = _key()
    key = build_idempotency_key(
        resource_plan_id=str(params["resource_plan_id"]),
        handoff_id=str(params["handoff_id"]),
        handoff_version=int(params["handoff_version"]),
        step_id=str(params["step_id"]),
        operation=str(params["operation"]),
    )
    acquire_execution_step(
        **params,
        lease_owner="worker-a",
        side_effecting=False,
        operation_contract="read_only_retryable",
    )
    from app.chat import canonical_execution_idempotency as store

    record = store._TEST_STORE[key]
    record["lease_expires_at"] = datetime.now(UTC) - timedelta(seconds=5)
    store._TEST_STORE[key] = record

    recovered = acquire_execution_step(
        **params,
        lease_owner="worker-b",
        side_effecting=False,
        operation_contract="read_only_retryable",
    )
    assert recovered.outcome == AcquireOutcome.EXECUTE


def test_stale_non_idempotent_side_effect_requires_reconciliation_zero_invocation() -> None:
    params = _key()
    key = build_idempotency_key(
        resource_plan_id=str(params["resource_plan_id"]),
        handoff_id=str(params["handoff_id"]),
        handoff_version=int(params["handoff_version"]),
        step_id=str(params["step_id"]),
        operation=str(params["operation"]),
    )
    acquire_execution_step(
        **params,
        lease_owner="worker-a",
        side_effecting=True,
        operation_contract="side_effecting_without_stable_idempotency",
    )
    from app.chat import canonical_execution_idempotency as store

    record = store._TEST_STORE[key]
    record["lease_expires_at"] = datetime.now(UTC) - timedelta(seconds=5)
    store._TEST_STORE[key] = record
    calls = {"count": 0}

    outcome, stored = run_idempotent_execution_step(
        **params,
        side_effecting=True,
        operation_contract="side_effecting_without_stable_idempotency",
        lease_owner="worker-b",
        execute=lambda: calls.__setitem__("count", calls["count"] + 1) or {"should": "not run"},
    )

    assert outcome == AcquireOutcome.REQUIRES_RECONCILIATION
    assert stored["reason"] == "execution_outcome_uncertain"
    assert calls["count"] == 0


def test_stale_idempotent_side_effect_reuses_propagated_stable_key() -> None:
    params = _key()
    expected_downstream_key = build_downstream_idempotency_key(
        resource_plan_id=str(params["resource_plan_id"]),
        handoff_id=str(params["handoff_id"]),
        handoff_version=int(params["handoff_version"]),
        step_id=str(params["step_id"]),
        operation=str(params["operation"]),
    )
    first_seen: list[str] = []

    def _first(*, downstream_idempotency_key: str) -> dict:
        first_seen.append(downstream_idempotency_key)
        raise RuntimeError("worker died after downstream submit")

    with pytest.raises(RuntimeError):
        run_idempotent_execution_step(
            **params,
            side_effecting=True,
            operation_contract="side_effecting_with_stable_idempotency",
            lease_owner="worker-a",
            execute=_first,
        )
    key = build_idempotency_key(
        resource_plan_id=str(params["resource_plan_id"]),
        handoff_id=str(params["handoff_id"]),
        handoff_version=int(params["handoff_version"]),
        step_id=str(params["step_id"]),
        operation=str(params["operation"]),
    )
    from app.chat import canonical_execution_idempotency as store

    stale = store._TEST_STORE[key]
    stale["status"] = "running"
    stale["lease_expires_at"] = datetime.now(UTC) - timedelta(seconds=5)
    store._TEST_STORE[key] = stale
    second_seen: list[str] = []

    def _second(*, downstream_idempotency_key: str) -> dict:
        second_seen.append(downstream_idempotency_key)
        return {"ok": True, "downstream_idempotency_key": downstream_idempotency_key}

    outcome, result = run_idempotent_execution_step(
        **params,
        side_effecting=True,
        operation_contract="side_effecting_with_stable_idempotency",
        lease_owner="worker-b",
        execute=_second,
    )

    assert outcome == AcquireOutcome.EXECUTE
    assert first_seen == [expected_downstream_key]
    assert second_seen == [expected_downstream_key]
    assert result["downstream_idempotency_key"] == expected_downstream_key


def test_replay_after_completion() -> None:
    params = _key()
    run_idempotent_execution_step(
        **params,
        side_effecting=True,
        lease_owner="worker-a",
        execute=lambda: {"status": "done"},
    )
    replay = acquire_execution_step(**params, lease_owner="worker-b", side_effecting=True)
    assert replay.outcome == AcquireOutcome.REPLAY
    assert replay.stored_result == {"status": "done"}


def test_retryable_read_only_failure_allows_retry() -> None:
    params = _key()
    key = build_idempotency_key(
        resource_plan_id=str(params["resource_plan_id"]),
        handoff_id=str(params["handoff_id"]),
        handoff_version=int(params["handoff_version"]),
        step_id=str(params["step_id"]),
        operation=str(params["operation"]),
    )
    acquire_execution_step(**params, lease_owner="worker-a", side_effecting=False)
    fail_execution_step(idempotency_key=key, result={"error": "transient"}, retryable=True)
    retry = acquire_execution_step(**params, lease_owner="worker-b", side_effecting=False)
    assert retry.outcome == AcquireOutcome.EXECUTE


def test_side_effecting_step_timeout_marks_uncertain_and_blocks_replay_execute() -> None:
    params = _key()
    key = build_idempotency_key(
        resource_plan_id=str(params["resource_plan_id"]),
        handoff_id=str(params["handoff_id"]),
        handoff_version=int(params["handoff_version"]),
        step_id=str(params["step_id"]),
        operation=str(params["operation"]),
    )
    acquire_execution_step(**params, lease_owner="worker-a", side_effecting=True)
    fail_execution_step(
        idempotency_key=key,
        result={"error": "timeout"},
        retryable=False,
        uncertain=True,
    )
    replay = acquire_execution_step(**params, lease_owner="worker-b", side_effecting=True)
    assert replay.outcome == AcquireOutcome.REQUIRES_RECONCILIATION
    assert replay.stored_result["error"] == "timeout"
    assert replay.stored_result["reason"] == "execution_outcome_uncertain"


def test_same_plan_different_step_ids_independent_keys() -> None:
    base = _key()
    other = {**base, "step_id": "s2"}
    run_idempotent_execution_step(
        **base,
        side_effecting=True,
        lease_owner="worker-a",
        execute=lambda: {"step": "s1"},
    )
    second = run_idempotent_execution_step(
        **other,
        side_effecting=True,
        lease_owner="worker-a",
        execute=lambda: {"step": "s2"},
    )
    assert second[0] == AcquireOutcome.EXECUTE
    assert second[1] == {"step": "s2"}


def test_mismatched_handoff_version_distinct_keys() -> None:
    v1 = _key(handoff_version=1)
    v2 = _key(handoff_version=2)
    run_idempotent_execution_step(
        **v1,
        side_effecting=True,
        lease_owner="worker-a",
        execute=lambda: {"version": 1},
    )
    second = run_idempotent_execution_step(
        **v2,
        side_effecting=True,
        lease_owner="worker-a",
        execute=lambda: {"version": 2},
    )
    assert second[0] == AcquireOutcome.EXECUTE
    assert second[1] == {"version": 2}


def test_complete_marks_terminal_status() -> None:
    params = _key()
    acquired = acquire_execution_step(**params, lease_owner="worker-a", side_effecting=True)
    assert acquired.record is not None
    complete_execution_step(idempotency_key=acquired.record.idempotency_key, result={"ok": True})
    record = inspect_execution_step(
        resource_plan_id=str(params["resource_plan_id"]),
        step_id=str(params["step_id"]),
        operation=str(params["operation"]),
        handoff_id=str(params["handoff_id"]),
        handoff_version=int(params["handoff_version"]),
    )
    assert record is not None and record.status == "completed"


def test_purpose_label_cannot_override_explicit_operation_contract() -> None:
    step = {
        "purpose": "mcp_discovery",
        "resource_id": "mcp_tool:splunk_get_metadata",
        "operation_contract": "side_effecting_without_stable_idempotency",
    }
    assert operation_contract_for_step(step) == "side_effecting_without_stable_idempotency"


def test_unknown_mcp_execution_contract_defaults_to_non_replay_side_effect() -> None:
    step = {"purpose": "mcp_execution", "resource_id": "mcp_tool:unknown_admin_write"}
    assert operation_contract_for_step(step) == "side_effecting_without_stable_idempotency"


def test_known_read_only_mcp_execution_contract_is_retryable() -> None:
    step = {"purpose": "mcp_execution", "resource_id": "mcp_tool:splunk_run_query"}
    assert operation_contract_for_step(step) == "read_only_retryable"
