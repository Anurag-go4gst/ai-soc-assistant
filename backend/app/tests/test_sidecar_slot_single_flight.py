"""P2-A close: single-flight model-slot guard in run_sidecar_llm_with_timeout.

Gate: "no abandoned request keeps occupying the single model slot." On a single-slot
model a timed-out hop stays orphaned on the socket; a new hop must skip the slot rather
than pile a second concurrent request onto it and thrash.
"""

from __future__ import annotations

import threading
import time

from app.llm import sidecar_governance as sg
from app.llm.sidecar_governance import (
    FAILURE_PROVIDER_UNAVAILABLE,
    NOTE_LLM_PROVIDER_UNAVAILABLE,
    NOTE_LLM_ASSIST_TIMED_OUT,
    NOTE_LLM_SLOT_BUSY,
    run_sidecar_llm_with_timeout,
)


def test_free_slot_runs_provider() -> None:
    call = run_sidecar_llm_with_timeout(lambda: "ok", timeout_seconds=2.0)
    assert call.timed_out is False
    assert call.raw_output == "ok"
    assert call.notes == []


def test_busy_slot_skips_without_running_second_provider() -> None:
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

    holder: dict[str, object] = {}
    t = threading.Thread(
        target=lambda: holder.__setitem__(
            "result", run_sidecar_llm_with_timeout(_slow, timeout_seconds=0.2)
        )
    )
    t.start()
    assert started.wait(timeout=2.0)

    # Primary caller has timed out (0.2s) but the worker still holds the slot.
    time.sleep(0.4)
    busy = run_sidecar_llm_with_timeout(_second, timeout_seconds=1.0)
    assert busy.timed_out is False
    assert busy.raw_output is None
    assert busy.notes == [NOTE_LLM_SLOT_BUSY]
    assert second_ran.is_set() is False  # provider never ran — no pile-on

    # Free the orphan; the slot must become available again.
    release.set()
    t.join(timeout=5.0)
    primary = holder["result"]
    assert primary.timed_out is True
    assert primary.notes == [NOTE_LLM_ASSIST_TIMED_OUT]

    # Slot released after the orphan completed → next hop runs normally.
    deadline = time.time() + 3.0
    while time.time() < deadline:
        again = run_sidecar_llm_with_timeout(lambda: "free", timeout_seconds=1.0)
        if again.notes != [NOTE_LLM_SLOT_BUSY]:
            assert again.raw_output == "free"
            break
        time.sleep(0.05)
    else:
        raise AssertionError("slot never released after orphan completed")


def test_slot_released_on_provider_error() -> None:
    def _boom() -> str:
        raise RuntimeError("provider failed")

    err = run_sidecar_llm_with_timeout(_boom, timeout_seconds=1.0)
    # `timed_out` stays True so existing callers still degrade, but Plan 7 D1 made the
    # reported class truthful: a provider that raised did not run out of time.
    assert err.timed_out is True
    assert err.notes == [NOTE_LLM_PROVIDER_UNAVAILABLE]
    assert err.failure_kind == FAILURE_PROVIDER_UNAVAILABLE

    # Slot must be free immediately for the next hop.
    ok = run_sidecar_llm_with_timeout(lambda: "after-error", timeout_seconds=1.0)
    assert ok.raw_output == "after-error"
    assert ok.notes == []


def test_bounded_slot_wait_acquires_after_release() -> None:
    release = threading.Event()
    started = threading.Event()

    def _slow() -> str:
        started.set()
        release.wait(timeout=5.0)
        return "slow"

    t = threading.Thread(
        target=lambda: run_sidecar_llm_with_timeout(_slow, timeout_seconds=0.2)
    )
    t.start()
    assert started.wait(timeout=2.0)
    time.sleep(0.3)  # primary caller has given up; orphan still holds the slot

    # Release shortly; a bounded waiter should acquire once the slot frees.
    threading.Timer(0.3, release.set).start()
    waited = run_sidecar_llm_with_timeout(
        lambda: "waited", timeout_seconds=1.0, slot_wait_seconds=2.0
    )
    t.join(timeout=5.0)
    assert waited.raw_output == "waited"
    assert waited.notes == []


def test_single_slot_default() -> None:
    # The guard models one physical slot by default.
    assert sg._MODEL_SLOTS >= 1
