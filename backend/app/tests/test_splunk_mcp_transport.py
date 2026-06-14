"""Step 3 — Splunk search async lifecycle + connector wiring.

Injected transport (no live server): proves submit → bounded poll → fetch maps
to honest outcomes (ok/empty/timeout/denied/failed/schema_invalid) and that the
connector drives the lifecycle once per call with alias normalization.
"""

from __future__ import annotations

import pytest

from app.connectors.mcp.splunk_mcp import (
    SplunkMcpConnector,
    set_search_transport_factory,
)
from app.connectors.mcp.splunk_search_lifecycle import run_search_lifecycle


class FakeTransport:
    """Scripted submit/poll/fetch. `states` drives the poll sequence."""

    def __init__(self, states, rows=None, submit_exc=None, poll_exc=None):
        self.states = list(states)
        self.rows = rows if rows is not None else [{"user": "alice"}]
        self.submit_exc = submit_exc
        self.poll_exc = poll_exc
        self.submits = 0
        self.polls = 0

    def submit(self, arguments):
        self.submits += 1
        if self.submit_exc:
            raise self.submit_exc
        return "job-1"

    def poll(self, job_id):
        if self.poll_exc:
            raise self.poll_exc
        self.polls += 1
        return {"state": self.states.pop(0) if self.states else "running"}

    def fetch(self, job_id):
        return {"rows": self.rows}


_BOUNDS = dict(max_polls=5, poll_interval_ms=0, job_timeout_ms=60000)


def _run(transport):
    return run_search_lifecycle(transport, {"search_query": "index=a"}, sleep=lambda _s: None, **_BOUNDS)


def test_running_then_done_returns_rows() -> None:
    out = _run(FakeTransport(["running", "done"], rows=[{"user": "alice"}, {"user": "bob"}]))
    assert out["status"] == "ok"
    assert len(out["rows"]) == 2
    assert out["job"]["state"] == "completed"


def test_done_with_no_rows_is_ok_empty() -> None:
    out = _run(FakeTransport(["done"], rows=[]))
    assert out["status"] == "ok"
    assert out["rows"] == []  # honest negative, not a failure


def test_failed_state_is_failed() -> None:
    out = _run(FakeTransport(["running", "failed"]))
    assert out["status"] == "failed"


def test_denied_state_is_denied() -> None:
    out = _run(FakeTransport(["forbidden"]))
    assert out["status"] == "denied"


def test_unknown_state_is_schema_invalid() -> None:
    out = _run(FakeTransport(["weird_state"]))
    assert out["status"] == "schema_invalid"


def test_submit_permission_error_is_denied() -> None:
    out = _run(FakeTransport([], submit_exc=PermissionError("nope")))
    assert out["status"] == "denied"


def test_submit_transport_error_is_failed() -> None:
    out = _run(FakeTransport([], submit_exc=RuntimeError("conn refused")))
    assert out["status"] == "failed"
    assert out["rows"] == []


def test_max_polls_exceeded_is_timeout() -> None:
    # Never reaches a terminal state within max_polls.
    out = run_search_lifecycle(
        FakeTransport(["running"] * 10),
        {"search_query": "index=a"},
        sleep=lambda _s: None,
        max_polls=3,
        poll_interval_ms=0,
        job_timeout_ms=60000,
    )
    assert out["status"] == "timeout"


def test_wall_clock_timeout(monkeypatch) -> None:
    clock = {"t": 0.0}

    def fake_monotonic():
        clock["t"] += 100.0  # each call jumps 100s
        return clock["t"]

    out = run_search_lifecycle(
        FakeTransport(["running", "running", "done"]),
        {"search_query": "index=a"},
        sleep=lambda _s: None,
        monotonic=fake_monotonic,
        max_polls=5,
        poll_interval_ms=2000,
        job_timeout_ms=120000,
    )
    assert out["status"] == "timeout"


# --- connector wiring ---------------------------------------------------------


@pytest.fixture
def live_registry(monkeypatch):
    monkeypatch.setenv("MCP_MODE", "registry")
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("SPLUNK_MCP_ENABLED", "true")
    monkeypatch.setenv("SPLUNK_MCP_BASE_URL", "https://splunk-mcp.example.invalid")
    monkeypatch.setenv("SPLUNK_MCP_TOKEN", "secret")
    yield
    set_search_transport_factory(None)


def test_connector_drives_lifecycle_via_injected_transport(live_registry) -> None:
    transport = FakeTransport(["done"], rows=[{"user": "alice"}])
    set_search_transport_factory(lambda: transport)
    out = SplunkMcpConnector().call_tool("splunk_run_query", {"search_query": "index=a"})
    assert out["status"] == "ok"
    assert transport.submits == 1  # one logical call


def test_connector_normalizes_search_alias(live_registry) -> None:
    transport = FakeTransport(["done"], rows=[])
    set_search_transport_factory(lambda: transport)
    # contract alias -> canonical splunk_run_query
    out = SplunkMcpConnector().call_tool("search_splunk", {"search_query": "index=a"})
    assert out["status"] == "ok"


def test_connector_blocks_when_transport_unconfigured(live_registry) -> None:
    set_search_transport_factory(lambda: None)
    out = SplunkMcpConnector().call_tool("splunk_run_query", {"search_query": "index=a"})
    assert out["status"] == "blocked"
    assert out["error"] == "live_transport_unconfigured"
