"""Transport correlation/retry contracts for the reusable live efficacy runner."""

from __future__ import annotations

from typing import Any

from scripts import run_live_efficacy_100 as runner


class _Client:
    def __init__(self, *, post_status: int = 0, run_status: str = "completed") -> None:
        self.timeout = 170.0
        self.post_status = post_status
        self.run_status = run_status
        self.post_ids: list[str] = []
        self.get_timeouts: list[float | None] = []

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> tuple[int, Any, dict[str, str]]:
        if method == "POST":
            self.post_ids.append(str((extra_headers or {}).get("X-Request-ID")))
            return self.post_status, {"detail": "transport"}, {}
        self.get_timeouts.append(timeout)
        return 200, {"run": {"status": self.run_status}}, {}


def _question() -> dict[str, str]:
    return {"id": "eff.test", "category": "soc_detection", "question": "test"}


def test_transport_timeout_makes_one_http_attempt_then_polls() -> None:
    client = _Client(post_status=0, run_status="completed")

    result = runner._post_chat(
        client,
        _question(),
        1,
        trace_poll_seconds=0,
        trace_poll_interval=0.1,
    )

    assert len(client.post_ids) == 1
    assert result["transport_attempts"] == 1
    assert result["server_outcome"]["status"] == "completed_after_disconnect"
    assert client.get_timeouts == [5.0]


def test_running_trace_becomes_bounded_nonterminal_outcome() -> None:
    client = _Client(post_status=0, run_status="running")

    result = runner._post_chat(
        client,
        _question(),
        1,
        trace_poll_seconds=0,
        trace_poll_interval=0.1,
    )

    assert result["server_outcome"]["status"] == "still_running_after_poll_limit"
    assert result["server_outcome"]["poll_exhausted"] is True


def test_resilience_retry_uses_distinct_trace_and_retry_link() -> None:
    client = _Client(post_status=200)
    first = runner._post_chat(client, _question(), 1)
    second = runner._post_chat(
        client,
        _question(),
        2,
        retry_of=first["request_id"],
    )

    assert first["request_id"] != second["request_id"]
    assert second["retry_of"] == first["request_id"]
    assert client.post_ids == [first["request_id"], second["request_id"]]


def test_summary_reliability_uses_first_attempt_not_recovery() -> None:
    row = {
        "id": "eff.test",
        "category": "soc_detection",
        "http_status": 0,
        "wall_latency_ms": 170_000,
        "failure_class": "transport",
        "error_code": None,
        "quality": {"score": 0, "issues": [], "selected_skill": None},
        "telemetry": {"available": True},
        "retried": True,
        "recovery_attempt": {"http_status": 200},
    }

    summary = runner._summarize([row], [])

    assert summary["http_success"] == 0
    assert summary["resilience"] == {
        "retry_attempted": 1,
        "retry_recovered_to_http_200": 1,
    }
