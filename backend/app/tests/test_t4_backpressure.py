"""Plan 8 REL0 — bounded T4 backpressure and storm suppression."""

from __future__ import annotations

import os
import threading
import time

from app.llm.sidecar_governance import (
    FAILURE_CIRCUIT_OPEN,
    FAILURE_SLOT_BUSY,
    NOTE_LLM_SLOT_BUSY,
    reset_t4_circuit,
    run_sidecar_llm_with_timeout,
    t4_circuit_status,
)


def test_busy_slot_sheds_without_queueing_a_second_call() -> None:
    started = threading.Event()
    release = threading.Event()
    second_ran = threading.Event()

    def _slow() -> str:
        started.set()
        release.wait(timeout=5.0)
        return "slow-done"

    def _second() -> str:
        second_ran.set()
        return "second"

    holder = threading.Thread(
        target=lambda: run_sidecar_llm_with_timeout(_slow, timeout_seconds=0.2),
        daemon=True,
    )
    holder.start()
    assert started.wait(timeout=2.0)
    busy = run_sidecar_llm_with_timeout(_second, timeout_seconds=1.0)
    assert busy.failure_kind == FAILURE_SLOT_BUSY
    assert NOTE_LLM_SLOT_BUSY in busy.notes
    assert second_ran.is_set() is False
    release.set()
    holder.join(timeout=3.0)


def test_open_circuit_suppresses_request_storm() -> None:
    os.environ["AI_SOC_T4_CIRCUIT_FAILURE_THRESHOLD"] = "1"
    reset_t4_circuit()

    def _fail() -> str:
        raise TimeoutError("slow")

    run_sidecar_llm_with_timeout(_fail, timeout_seconds=0.05)
    assert t4_circuit_status()["state"] == "OPEN"

    calls = {"n": 0}

    def _must_not_run() -> str:
        calls["n"] += 1
        return "no"

    results = [run_sidecar_llm_with_timeout(_must_not_run, timeout_seconds=1.0) for _ in range(20)]
    assert calls["n"] == 0
    assert all(row.failure_kind == FAILURE_CIRCUIT_OPEN for row in results)
    assert all(row.timed_out is False for row in results)


def test_slot_busy_does_not_open_the_circuit() -> None:
    reset_t4_circuit()
    started = threading.Event()
    release = threading.Event()

    def _slow() -> str:
        started.set()
        time.sleep(0.3)
        release.set()
        return "done"

    holder = threading.Thread(
        target=lambda: run_sidecar_llm_with_timeout(_slow, timeout_seconds=0.05),
        daemon=True,
    )
    holder.start()
    assert started.wait(timeout=2.0)
    busy = run_sidecar_llm_with_timeout(lambda: "x", timeout_seconds=1.0)
    assert busy.failure_kind == FAILURE_SLOT_BUSY
    assert t4_circuit_status()["state"] == "CLOSED"
    holder.join(timeout=3.0)
