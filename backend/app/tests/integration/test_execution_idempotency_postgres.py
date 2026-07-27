"""Execution idempotency integration tests on PostgreSQL."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from app.chat.canonical_execution_idempotency import (
    AcquireOutcome,
    acquire_execution_step,
    run_idempotent_execution_step,
)
from app.tests.integration.conftest import new_integration_handoff_id

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _postgres_runtime(postgres_integration_runtime: None) -> None:
    return None


def _params(*, handoff_id: str) -> dict[str, str | int]:
    return {
        "resource_plan_id": "rp:int-exec",
        "handoff_id": handoff_id,
        "handoff_version": 1,
        "step_id": "s1",
        "operation": "mcp_discovery:mcp_tool:foo",
    }


def test_postgres_duplicate_dispatch_replays_stored_result(postgres_migrated: str) -> None:
    handoff_id = new_integration_handoff_id("exec-dup")
    params = _params(handoff_id=handoff_id)
    calls = {"count": 0}

    def _execute() -> dict[str, int]:
        calls["count"] += 1
        return {"value": 42}

    first = run_idempotent_execution_step(
        **params,
        side_effecting=True,
        lease_owner="worker-a",
        execute=_execute,
    )
    second = run_idempotent_execution_step(
        **params,
        side_effecting=True,
        lease_owner="worker-b",
        execute=_execute,
    )
    assert first[0] == AcquireOutcome.EXECUTE
    assert second[0] == AcquireOutcome.REPLAY
    assert second[1] == {"value": 42}
    assert calls["count"] == 1


def test_postgres_concurrent_acquire_single_executor(postgres_migrated: str) -> None:
    handoff_id = new_integration_handoff_id("exec-race")
    params = _params(handoff_id=handoff_id)
    calls = {"count": 0}

    def _execute() -> dict[str, bool]:
        calls["count"] += 1
        return {"ok": True}

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                run_idempotent_execution_step,
                **params,
                side_effecting=True,
                lease_owner=f"worker-{index}",
                execute=_execute,
            )
            for index in range(2)
        ]
        outcomes = {future.result(timeout=10)[0] for future in futures}

    assert AcquireOutcome.EXECUTE in outcomes
    assert calls["count"] == 1


def test_postgres_concurrent_acquire_reports_in_progress(postgres_migrated: str) -> None:
    handoff_id = new_integration_handoff_id("exec-lock")
    params = _params(handoff_id=handoff_id)
    barrier = __import__("threading").Barrier(2)

    def _worker_a() -> AcquireOutcome:
        acquired = acquire_execution_step(**params, lease_owner="worker-a", side_effecting=True)
        barrier.wait(timeout=5)
        return acquired.outcome

    def _worker_b() -> AcquireOutcome:
        barrier.wait(timeout=5)
        acquired = acquire_execution_step(**params, lease_owner="worker-b", side_effecting=True)
        return acquired.outcome

    with ThreadPoolExecutor(max_workers=2) as pool:
        future_a = pool.submit(_worker_a)
        future_b = pool.submit(_worker_b)
        outcomes = {future_a.result(timeout=10), future_b.result(timeout=10)}

    assert outcomes == {AcquireOutcome.EXECUTE, AcquireOutcome.IN_PROGRESS}
