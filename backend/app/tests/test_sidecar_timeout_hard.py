from __future__ import annotations

import time

import pytest

from app.llm.sidecar_governance import run_sidecar_llm_with_timeout

pytestmark = pytest.mark.l2_slow


def test_slow_provider_returns_within_budget() -> None:
    def slow_provider() -> str:
        time.sleep(5.0)
        return "done"

    started = time.monotonic()
    result = run_sidecar_llm_with_timeout(slow_provider, timeout_seconds=1.0)
    elapsed = time.monotonic() - started

    assert elapsed < 1.5
    assert result.timed_out is True
    assert result.raw_output is None


def test_fast_provider_passthrough() -> None:
    result = run_sidecar_llm_with_timeout(lambda: "ok", timeout_seconds=1.0)

    assert result.timed_out is False
    assert result.raw_output == "ok"


def test_provider_raises_is_timed_out_not_propagated() -> None:
    def failing_provider() -> str:
        raise RuntimeError("boom")

    result = run_sidecar_llm_with_timeout(failing_provider, timeout_seconds=1.0)

    assert result.timed_out is True
    assert result.raw_output is None
