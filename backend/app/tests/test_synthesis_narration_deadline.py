"""Regression tests for monotonic synthesis narration deadline (E5 remediation)."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from app.actions.capability_policy import action_capability_for
from app.config import settings
from app.llm.clients import ChatResult, LocalChatError
from app.llm.clients.endpoint_resolver import resolve_local_primary_endpoint
from app.llm.clients.failover_client import FailoverChatClient
from app.synthesis.lab_runner import _narrate_with_progress_and_timeout, run_governed_synthesis_lab
from app.synthesis.live_narration import narrate_analyst_summary
from app.synthesis.models import build_governed_synthesis_package
from app.synthesis.narration_deadline import hop_timeout_seconds, release_narration_slot_for_tests
from app.tests.test_live_synthesis_narration import _run as run_live_narration_lab
from app.tests.test_p6_guarded_synthesis_lab import (
    _source_evidence,
    _structured_context,
    _sufficiency_ready,
)

pytestmark = pytest.mark.l2_slow

_TOLERANCE_S = 0.35
_EXECUTOR_TAIL_S = 2.5


@pytest.fixture(autouse=True)
def _drain_synthesis_executor_worker() -> None:
    yield
    time.sleep(_EXECUTOR_TAIL_S)
    release_narration_slot_for_tests()


class _HangingClient:
    """Blocks until the outer synthesis deadline fires."""

    timeout_seconds = 90
    base_url = "http://hang.invalid/v1"
    model = "hang"

    def generate(self, **kwargs: object) -> ChatResult:
        time.sleep(2.0)
        return ChatResult(text="late", model="hang", latency_ms=1)


class _SlowHopClient:
    """Simulates a blocking hop that exceeds its per-call socket budget."""

    def __init__(self, label: str, overrun_s: float = 0.15) -> None:
        self.label = label
        self.overrun_s = overrun_s
        self.timeout_seconds = 90
        self.base_url = f"http://{label}.invalid/v1"
        self.model = "slow"
        self.calls: list[tuple[str, float, int | None]] = []

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
        timeout_seconds: int | None = None,
        **kwargs: object,
    ) -> ChatResult:
        budget = timeout_seconds if timeout_seconds is not None else self.timeout_seconds
        self.calls.append((self.label, time.monotonic(), budget))
        time.sleep(max(0.05, budget + self.overrun_s))
        raise LocalChatError("url_error:timeout")


def _minimal_narration_inputs() -> tuple[object, dict, dict]:
    package = build_governed_synthesis_package(
        structured_context=_structured_context(),
        source_evidence=_source_evidence(),
        mitre_mappings=[],
        action_capability=action_capability_for("attack_discovery", "P2 - High"),
    )
    draft = {
        "analyst_summary": "Deterministic summary for timeout tests.",
        "execution_eligible": False,
        "draft_source": "deterministic_lab",
    }
    return package, draft, _structured_context()


def test_configured_timeout_not_floored_to_120_for_synthesis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")
    monkeypatch.setattr(settings, "ai_soc_llm_timeout_seconds", 90)
    monkeypatch.setattr(settings, "ai_soc_llm_local_base_url", "http://127.0.0.1:8081/v1")
    monkeypatch.setattr(settings, "ai_soc_llm_local_model", "test-model")
    endpoint = resolve_local_primary_endpoint(sidecar=False)
    assert endpoint is not None
    assert endpoint.timeout_seconds == 90
    sidecar = resolve_local_primary_endpoint(sidecar=True)
    assert sidecar is not None
    assert sidecar.timeout_seconds == 90


def test_hanging_primary_bounded_by_total_synthesis_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.synthesis.lab_runner.live_synthesis_timeout_seconds", lambda: 0.5)
    package, draft, structured = _minimal_narration_inputs()
    client = FailoverChatClient(chain=(("local_primary", _HangingClient()),))
    started = time.monotonic()
    narration, timed_out, elapsed_ms = _narrate_with_progress_and_timeout(
        package=package,
        deterministic_draft=draft,
        severity_label="P2 - High",
        client=client,
        structured_context=structured,
    )
    wall_s = time.monotonic() - started
    assert timed_out is True
    assert narration is None
    assert wall_s < 0.5 + _TOLERANCE_S
    assert elapsed_ms <= int((0.5 + _TOLERANCE_S) * 1000)


def test_failover_does_not_reset_full_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    primary = _SlowHopClient("primary", overrun_s=0.05)
    secondary = _SlowHopClient("secondary", overrun_s=0.05)
    client = FailoverChatClient(
        chain=(
            ("local_primary", primary),
            ("foundation_sec_instruct_fallback", secondary),
        )
    )
    deadline = time.monotonic() + 0.6
    started = time.monotonic()
    with pytest.raises(LocalChatError):
        client.generate(
            system_prompt="sys",
            user_prompt="user",
            max_tokens=32,
            temperature=0.0,
            deadline=deadline,
        )
    wall_s = time.monotonic() - started
    assert wall_s < 0.6 + _TOLERANCE_S
    assert len(primary.calls) == 1
    assert len(secondary.calls) == 0


def test_no_failover_after_deadline_exhausted() -> None:
    primary = MagicMock()
    primary.timeout_seconds = 90
    primary.generate.side_effect = LocalChatError("url_error:timeout")
    secondary = MagicMock()
    secondary.timeout_seconds = 90
    client = FailoverChatClient(
        chain=(
            ("local_primary", primary),
            ("foundation_sec_instruct_fallback", secondary),
        )
    )
    deadline = time.monotonic() - 0.01
    with pytest.raises(LocalChatError):
        client.generate(
            system_prompt="s",
            user_prompt="u",
            max_tokens=8,
            temperature=0.0,
            deadline=deadline,
        )
    primary.generate.assert_not_called()
    secondary.generate.assert_not_called()


def test_governed_fallback_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.synthesis.lab_runner.live_synthesis_timeout_seconds", lambda: 0.4)
    client = FailoverChatClient(chain=(("local_primary", _HangingClient()),))
    result = run_live_narration_lab(monkeypatch, live=True, client=client)
    assert result.status.status == "partial_timeout"
    assert result.status.provider == "deterministic_lab"
    assert result.analyst_summary
    assert result.draft["execution_eligible"] is False


def test_caller_returns_within_budget_tolerance(monkeypatch: pytest.MonkeyPatch) -> None:
    budget_s = 0.45
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


def test_no_delayed_endpoint_calls_after_response(monkeypatch: pytest.MonkeyPatch) -> None:
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
    return_mark = time.monotonic()
    time.sleep(0.2)
    assert len(secondary.calls) == 0


def test_successful_primary_path_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    client.timeout_seconds = 60
    client.generate.return_value = ChatResult(
        text="Governed analyst prose.",
        model="fast",
        latency_ms=12,
        usage={"total_tokens": 3},
    )
    result = run_live_narration_lab(monkeypatch, live=True, client=client)
    assert result.status.provider == "local_model"
    assert result.analyst_summary == "Governed analyst prose."
    client.generate.assert_called_once()


def test_successful_secondary_failover_unchanged() -> None:
    primary = MagicMock()
    primary.timeout_seconds = 60
    primary.generate.side_effect = LocalChatError("http_503")
    secondary = MagicMock()
    secondary.timeout_seconds = 60
    secondary.generate.return_value = ChatResult(
        text="Fallback prose.",
        model="instruct",
        latency_ms=8,
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
    assert result.text == "Fallback prose."
    assert result.answered_label == "foundation_sec_instruct_fallback"
    primary.generate.assert_called_once()
    secondary.generate.assert_called_once()


def test_timeout_never_sets_execution_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.synthesis.lab_runner.live_synthesis_timeout_seconds", lambda: 0.3)
    client = FailoverChatClient(chain=(("local_primary", _SlowHopClient("primary")),))
    result = run_live_narration_lab(monkeypatch, live=True, client=client)
    assert result.draft["execution_eligible"] is False


def test_slow_prompt_processing_scenario_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    """Large-prompt latency shape: slow primary, no secondary, total budget enforced."""
    monkeypatch.setattr("app.synthesis.lab_runner.live_synthesis_timeout_seconds", lambda: 0.55)
    primary = _SlowHopClient("primary", overrun_s=0.08)
    secondary = _SlowHopClient("secondary", overrun_s=0.08)
    client = FailoverChatClient(
        chain=(
            ("local_primary", primary),
            ("foundation_sec_instruct_fallback", secondary),
        )
    )
    package, draft, structured = _minimal_narration_inputs()
    started = time.monotonic()
    narration, timed_out, _ = _narrate_with_progress_and_timeout(
        package=package,
        deterministic_draft=draft,
        severity_label=None,
        client=client,
        structured_context=structured,
    )
    assert timed_out is True
    assert narration is None
    assert time.monotonic() - started < 0.55 + _TOLERANCE_S
    assert len(primary.calls) >= 1
    assert len(secondary.calls) == 0


def test_narrate_analyst_summary_passes_deadline_to_failover() -> None:
    client = MagicMock(spec=FailoverChatClient)
    client.generate.return_value = ChatResult(
        text="ok",
        model="m",
        latency_ms=1,
    )
    package, draft, structured = _minimal_narration_inputs()
    deadline = time.monotonic() + 10.0
    result = narrate_analyst_summary(
        package=package,
        deterministic_draft=draft,
        severity_label=None,
        client=client,
        structured_context=structured,
        deadline=deadline,
    )
    assert isinstance(result, object)
    assert client.generate.call_args.kwargs.get("deadline") == deadline


def test_hop_timeout_never_exceeds_configured_or_remaining() -> None:
    configured = 90
    deadline = time.monotonic() + 30.0
    capped = hop_timeout_seconds(configured, deadline)
    assert capped is not None
    assert capped <= 30.0
    assert capped <= configured


def test_failover_hops_receive_decreasing_budget_not_fresh_full_timeout() -> None:
    class _BudgetClient:
        def __init__(self, label: str, delay_s: float, fail: bool) -> None:
            self.label = label
            self.delay_s = delay_s
            self.fail = fail
            self.timeout_seconds = 90
            self.base_url = f"http://{label}.invalid/v1"
            self.model = "m"
            self.budgets: list[float | None] = []

        def generate(
            self,
            *,
            system_prompt: str,
            user_prompt: str,
            max_tokens: int,
            temperature: float,
            timeout_seconds: int | None = None,
            **kwargs: object,
        ) -> ChatResult:
            self.budgets.append(timeout_seconds)
            time.sleep(self.delay_s)
            if self.fail:
                raise LocalChatError("http_503")
            return ChatResult(text="ok", model="m", latency_ms=1)

    primary = _BudgetClient("primary", delay_s=0.12, fail=True)
    secondary = _BudgetClient("secondary", delay_s=0.02, fail=True)
    client = FailoverChatClient(
        chain=(
            ("local_primary", primary),
            ("foundation_sec_instruct_fallback", secondary),
        )
    )
    deadline = time.monotonic() + 0.4
    with pytest.raises(LocalChatError):
        client.generate(
            system_prompt="sys",
            user_prompt="user",
            max_tokens=16,
            temperature=0.0,
            deadline=deadline,
        )
    assert len(primary.budgets) == 1
    assert len(secondary.budgets) == 1
    assert primary.budgets[0] is not None
    assert secondary.budgets[0] is not None
    assert secondary.budgets[0] <= primary.budgets[0]


def test_lab_runner_deadline_uses_monotonic_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.synthesis.lab_runner.live_synthesis_timeout_seconds", lambda: 0.5)
    monotonic_calls: list[float] = []
    real_monotonic = time.monotonic

    def _spy_monotonic() -> float:
        value = real_monotonic()
        monotonic_calls.append(value)
        return value

    monkeypatch.setattr(time, "monotonic", _spy_monotonic)
    package, draft, structured = _minimal_narration_inputs()
    client = FailoverChatClient(chain=(("local_primary", _HangingClient()),))
    _narrate_with_progress_and_timeout(
        package=package,
        deterministic_draft=draft,
        severity_label=None,
        client=client,
        structured_context=structured,
    )
    assert len(monotonic_calls) >= 2
