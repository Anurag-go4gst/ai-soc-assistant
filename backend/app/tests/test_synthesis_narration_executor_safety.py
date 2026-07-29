"""Fast deterministic tests for synthesis narration executor admission and safety."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

import pytest

from app.llm.clients import ChatResult, LocalChatError
from app.llm.clients.failover_client import FailoverChatClient
from app.synthesis.lab_runner import _narrate_with_progress_and_timeout, run_governed_synthesis_lab
from app.synthesis.narration_deadline import (
    release_narration_slot_for_tests,
    try_submit_narration,
)
from app.tests.test_live_synthesis_narration import _run as run_live_narration_lab
from app.tests.test_synthesis_narration_deadline import (
    _EXECUTOR_TAIL_S,
    _HangingClient,
    _SlowHopClient,
    _TOLERANCE_S,
    _minimal_narration_inputs,
)

_CALL_COUNTER = 0


@pytest.fixture(autouse=True)
def _drain_executor() -> None:
    yield
    time.sleep(_EXECUTOR_TAIL_S)
    release_narration_slot_for_tests()


def test_saturated_submit_returns_none_without_endpoint_call() -> None:
    """While the slot is held, new narration must not queue or call an endpoint."""
    calls: list[str] = []

    def _hold_and_call() -> None:
        calls.append("start")
        time.sleep(0.35)
        calls.append("end")

    holder = threading.Thread(target=lambda: try_submit_narration(_hold_and_call), daemon=True)
    holder.start()
    time.sleep(0.05)

    def _would_call() -> str:
        calls.append("endpoint")
        return "late"

    future = try_submit_narration(_would_call)
    assert future is None
    assert "endpoint" not in calls

    holder.join(timeout=2.0)
    time.sleep(0.1)
    assert calls.count("endpoint") == 0


def test_saturation_returns_governed_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.synthesis.lab_runner.live_synthesis_timeout_seconds", lambda: 1.0)

    def _long_hold() -> None:
        time.sleep(0.5)

    holder = threading.Thread(
        target=lambda: try_submit_narration(_long_hold),
        daemon=True,
    )
    holder.start()
    time.sleep(0.05)

    client = FailoverChatClient(chain=(("local_primary", _HangingClient()),))
    package, draft, structured = _minimal_narration_inputs()
    narration, timed_out, _ = _narrate_with_progress_and_timeout(
        package=package,
        deterministic_draft=draft,
        severity_label=None,
        client=client,
        structured_context=structured,
    )
    assert narration is None
    assert timed_out is True
    holder.join(timeout=2.0)


def test_running_request_expires_within_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    budget_s = 0.4
    monkeypatch.setattr("app.synthesis.lab_runner.live_synthesis_timeout_seconds", lambda: budget_s)
    client = FailoverChatClient(chain=(("local_primary", _SlowHopClient("primary")),))
    package, draft, structured = _minimal_narration_inputs()
    started = time.monotonic()
    _narrate_with_progress_and_timeout(
        package=package,
        deterministic_draft=draft,
        severity_label=None,
        client=client,
        structured_context=structured,
    )
    assert time.monotonic() - started < budget_s + _TOLERANCE_S


def test_running_completion_cannot_start_secondary_failover(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.synthesis.lab_runner.live_synthesis_timeout_seconds", lambda: 0.35)
    secondary = _SlowHopClient("secondary")
    client = FailoverChatClient(
        chain=(
            ("local_primary", _SlowHopClient("primary")),
            ("foundation_sec_instruct_fallback", secondary),
        )
    )
    package, draft, structured = _minimal_narration_inputs()
    _narrate_with_progress_and_timeout(
        package=package,
        deterministic_draft=draft,
        severity_label=None,
        client=client,
        structured_context=structured,
    )
    time.sleep(0.2)
    assert len(secondary.calls) == 0


def test_repeated_timeouts_do_not_accumulate_pending_work(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.synthesis.lab_runner.live_synthesis_timeout_seconds", lambda: 0.25)
    client = FailoverChatClient(chain=(("local_primary", _HangingClient()),))
    package, draft, structured = _minimal_narration_inputs()
    for _ in range(5):
        _narrate_with_progress_and_timeout(
            package=package,
            deterministic_draft=draft,
            severity_label=None,
            client=client,
            structured_context=structured,
        )
    time.sleep(_EXECUTOR_TAIL_S)


def test_late_worker_cannot_mutate_finalized_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.synthesis.lab_runner.live_synthesis_timeout_seconds", lambda: 0.3)
    late_client = MagicMock()
    late_client.timeout_seconds = 90
    late_client.generate.return_value = ChatResult(
        text="Late model prose that must not surface.",
        model="late",
        latency_ms=1,
    )

    def _slow_then_late(**kwargs: object) -> ChatResult:
        time.sleep(0.55)
        return late_client.generate(**kwargs)

    slow = MagicMock()
    slow.timeout_seconds = 90
    slow.generate.side_effect = _slow_then_late
    client = FailoverChatClient(chain=(("local_primary", slow),))

    result = run_live_narration_lab(monkeypatch, live=True, client=client)
    assert result.status.status == "partial_timeout"
    assert result.analyst_summary != "Late model prose that must not surface."
    assert result.draft["execution_eligible"] is False
    time.sleep(0.4)
    assert result.analyst_summary != "Late model prose that must not surface."


def test_successful_primary_path_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    client.timeout_seconds = 60
    client.generate.return_value = ChatResult(
        text="Primary success prose.",
        model="fast",
        latency_ms=5,
    )
    result = run_live_narration_lab(monkeypatch, live=True, client=client)
    assert result.status.provider == "local_model"
    assert result.analyst_summary == "Primary success prose."


def test_successful_secondary_failover_still_works() -> None:
    primary = MagicMock()
    primary.timeout_seconds = 60
    primary.generate.side_effect = LocalChatError("http_503")
    secondary = MagicMock()
    secondary.timeout_seconds = 60
    secondary.generate.return_value = ChatResult(
        text="Secondary success prose.",
        model="instruct",
        latency_ms=6,
        answered_label="foundation_sec_instruct_fallback",
    )
    client = FailoverChatClient(
        chain=(
            ("local_primary", primary),
            ("foundation_sec_instruct_fallback", secondary),
        )
    )
    result = client.generate(
        system_prompt="s",
        user_prompt="u",
        max_tokens=16,
        temperature=0.0,
    )
    assert result.text == "Secondary success prose."
    assert result.answered_label == "foundation_sec_instruct_fallback"
