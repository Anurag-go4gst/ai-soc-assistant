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
from app.connectors.mcp.splunk_search_lifecycle import McpTransportError, run_search_lifecycle


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


def test_rows_from_mcp_result_tolerates_shapes() -> None:
    from app.connectors.mcp.splunk_mcp import _rows_from_mcp_result

    assert _rows_from_mcp_result({"rows": [{"a": 1}]}) == [{"a": 1}]
    assert _rows_from_mcp_result({"results": [{"b": 2}]}) == [{"b": 2}]
    assert _rows_from_mcp_result({"structuredContent": [{"c": 3}]}) == [{"c": 3}]
    assert _rows_from_mcp_result({"nothing": True}) == []
    assert _rows_from_mcp_result(None) == []


# --- streamable_http transport JSON-RPC wire (httpx mocked, no network) -------


class _FakeResponse:
    def __init__(self, status_code: int, body: dict):
        self.status_code = status_code
        self._body = body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http_{self.status_code}")

    def json(self):
        return self._body


class _FakeHttpxClient:
    """Captures construction kwargs + the last POST; returns a canned response."""

    last_instance = None

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.posts = []
        self.response = _FakeResponse(200, {"result": {"rows": [{"user": "alice"}]}})
        _FakeHttpxClient.last_instance = self

    def post(self, url, json=None):
        self.posts.append({"url": url, "json": json})
        return self.response


def _patch_httpx(monkeypatch, response: _FakeResponse | None = None):
    import httpx

    monkeypatch.setattr(httpx, "Client", _FakeHttpxClient)
    if response is not None:
        # set after construction in the test via last_instance
        pass


def test_transport_submit_posts_jsonrpc_tools_call(monkeypatch) -> None:
    from app.connectors.mcp.splunk_mcp import _StreamableHttpSearchTransport

    _patch_httpx(monkeypatch)
    t = _StreamableHttpSearchTransport("https://splunk.example.invalid", "tok", 30.0)
    job = t.submit({"search_query": "index=a", "_governance": {"x": 1}})
    client = _FakeHttpxClient.last_instance
    # Auth header + JSON-RPC tools/call with canonical tool name; _-prefixed args dropped.
    assert client.kwargs["headers"]["Authorization"] == "Bearer tok"
    post = client.posts[0]
    assert post["url"].endswith("/mcp")
    assert post["json"]["method"] == "tools/call"
    assert post["json"]["params"]["name"] == "splunk_run_query"
    assert post["json"]["params"]["arguments"] == {"search_query": "index=a"}
    # Inline model: rows captured at submit, fetch returns them.
    assert t.fetch(job)["rows"] == [{"user": "alice"}]


def test_transport_full_lifecycle_returns_ok(monkeypatch) -> None:
    from app.connectors.mcp.splunk_mcp import _StreamableHttpSearchTransport

    _patch_httpx(monkeypatch)
    t = _StreamableHttpSearchTransport("https://splunk.example.invalid", "tok", 30.0)
    out = run_search_lifecycle(t, {"search_query": "index=a"}, sleep=lambda _s: None,
                               max_polls=3, poll_interval_ms=0, job_timeout_ms=60000)
    assert out["status"] == "ok"
    assert out["rows"] == [{"user": "alice"}]


def test_transport_403_raises_permission_error(monkeypatch) -> None:
    from app.connectors.mcp.splunk_mcp import _StreamableHttpSearchTransport

    _patch_httpx(monkeypatch)
    t = _StreamableHttpSearchTransport("https://splunk.example.invalid", "tok", 30.0)
    _FakeHttpxClient.last_instance.response = _FakeResponse(403, {})
    with pytest.raises(McpTransportError) as excinfo:
        t.submit({"search_query": "index=a"})
    assert excinfo.value.error_type == "permission_denied"


def test_transport_parses_structured_content_shape(monkeypatch) -> None:
    from app.connectors.mcp.splunk_mcp import _StreamableHttpSearchTransport

    _patch_httpx(monkeypatch)
    t = _StreamableHttpSearchTransport("https://splunk.example.invalid", "tok", 30.0)
    _FakeHttpxClient.last_instance.response = _FakeResponse(
        200, {"result": {"structuredContent": [{"host": "app-01"}]}}
    )
    job = t.submit({"search_query": "index=a"})
    assert t.fetch(job)["rows"] == [{"host": "app-01"}]


# --- full gate live path (integration; injected transport, no network) --------

_APPROVED = {
    "approved": True,
    "normalized_spl": "search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now | stats count by user | head 100",
    "reject_reasons": [],
    "warnings": [],
    "enforced_limits": {"max_result_limit": 100},
    "policy_version": "spl-policy-v1",
}


class _FakeTelemetry:
    def record_mcp_execution(self, *a, **k):
        pass

    def record_step(self, *a, **k):
        pass


@pytest.fixture
def live_gate(monkeypatch):
    # registry status reads env; connector picker + gate read the settings singleton.
    monkeypatch.setenv("MCP_MODE", "registry")
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVERS", "splunk_soc")
    monkeypatch.setenv("MCP_DEFAULT_SERVER", "splunk_soc")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TYPE", "splunk")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_URL", "https://splunk-mcp.example.invalid/mcp")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_AUTH_MODE", "bearer")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_BEARER_TOKEN", "secret")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TOOL_ALLOWLIST", "splunk_run_query")
    for attr in ("mcp_mode",):
        monkeypatch.setattr(f"app.config.settings.{attr}", "registry")
    monkeypatch.setattr("app.config.settings.splunk_mcp_enabled", True)
    monkeypatch.setattr("app.config.settings.splunk_mcp_base_url", "https://splunk-mcp.example.invalid")
    monkeypatch.setattr("app.config.settings.splunk_mcp_token", "secret")
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    yield monkeypatch
    set_search_transport_factory(None)


def test_gate_live_run_uses_real_adapter_and_live_provenance(live_gate) -> None:
    from app.orchestration.mcp_execution_gate import evaluate_mcp_execution

    set_search_transport_factory(lambda: FakeTransport(["done"], rows=[{"user": "alice"}, {"user": "bob"}]))
    # Live registry runs always require per-call analyst confirmation (safety
    # hardening); supply it so this exercises the confirmed live-execution path.
    execution, review = evaluate_mcp_execution(
        trace_id="trace-live",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=_APPROVED,
        execution_review_action="confirm",
    )
    assert execution["status"] == "executed"
    assert execution["evidence_source"] == "live"  # bug #1 fix
    assert execution["execution_status_label"] == "executed"
    envelope = execution["splunk_result_envelope"]
    assert envelope["origin"] == "real_mcp"  # bug #2 fix — not mock_connector
    # Live success rode the pre-execution B4 gate; no mock-evidence HIL.
    assert review["review_type"] != "mock_evidence_review"


def test_health_reports_available_when_configured(live_gate) -> None:
    status = SplunkMcpConnector().health()
    assert status.available is True
    assert status.detail == "live_adapter_ready"


def test_gate_live_run_failed_outcome_is_not_executed(live_gate) -> None:
    from app.orchestration.mcp_execution_gate import evaluate_mcp_execution

    set_search_transport_factory(lambda: FakeTransport(["running", "failed"]))
    execution, review = evaluate_mcp_execution(
        trace_id="trace-live-fail",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=_APPROVED,
    )
    assert execution["status"] != "executed"
    assert execution["block_reason"]
    assert review["required"] is True
