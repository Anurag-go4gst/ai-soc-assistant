"""P0 — httpx-mocked Splunk MCP streamable HTTP transport contract (no network)."""

from __future__ import annotations

import pytest

from app.connectors.mcp.mcp_endpoint import normalize_mcp_endpoint_url
from app.connectors.mcp.splunk_search_lifecycle import McpTransportError, run_search_lifecycle


class _FakeResponse:
    def __init__(self, status_code: int, body: dict | None = None):
        self.status_code = status_code
        self._body = body or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http_{self.status_code}")

    def json(self):
        return self._body


class _FakeHttpxClient:
    last_instance = None

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.posts: list[dict] = []
        self.response = _FakeResponse(200, {"result": {"rows": [{"user": "alice"}]}})
        _FakeHttpxClient.last_instance = self

    def post(self, url, json=None):
        self.posts.append({"url": url, "json": json})
        return self.response


def _patch_httpx(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    monkeypatch.setattr(httpx, "Client", _FakeHttpxClient)


def test_endpoint_normalizes_to_mcp_path() -> None:
    assert normalize_mcp_endpoint_url("https://splunk.example.invalid").endswith("/mcp")


def test_transport_posts_bearer_jsonrpc_tools_call(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.connectors.mcp.splunk_mcp import _StreamableHttpSearchTransport

    _patch_httpx(monkeypatch)
    transport = _StreamableHttpSearchTransport("https://splunk.example.invalid", "tok", 30.0)
    job = transport.submit({"search_query": "index=a", "_governance": {"x": 1}})
    client = _FakeHttpxClient.last_instance
    assert client.kwargs["headers"]["Authorization"] == "Bearer tok"
    post = client.posts[0]
    assert post["url"].endswith("/mcp")
    assert post["json"]["method"] == "tools/call"
    assert post["json"]["params"]["name"] == "splunk_run_query"
    assert post["json"]["params"]["arguments"] == {"search_query": "index=a"}
    assert transport.fetch(job)["rows"] == [{"user": "alice"}]


def test_transport_lifecycle_ok_with_mocked_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.connectors.mcp.splunk_mcp import _StreamableHttpSearchTransport

    _patch_httpx(monkeypatch)
    transport = _StreamableHttpSearchTransport("https://splunk.example.invalid", "tok", 30.0)
    out = run_search_lifecycle(
        transport,
        {"search_query": "index=a"},
        sleep=lambda _s: None,
        max_polls=3,
        poll_interval_ms=0,
        job_timeout_ms=60000,
    )
    assert out["status"] == "ok"
    assert out["rows"] == [{"user": "alice"}]


@pytest.mark.parametrize("status_code,error_type", [(401, "auth_failed"), (403, "permission_denied")])
def test_transport_auth_errors_raise(monkeypatch: pytest.MonkeyPatch, status_code: int, error_type: str) -> None:
    from app.connectors.mcp.splunk_mcp import _StreamableHttpSearchTransport

    _patch_httpx(monkeypatch)
    transport = _StreamableHttpSearchTransport("https://splunk.example.invalid", "tok", 30.0)
    _FakeHttpxClient.last_instance.response = _FakeResponse(status_code, {})
    with pytest.raises(McpTransportError) as excinfo:
        transport.submit({"search_query": "index=a"})
    assert excinfo.value.error_type == error_type


def test_transport_timeout_maps_to_failed_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.connectors.mcp.splunk_mcp import _StreamableHttpSearchTransport

    _patch_httpx(monkeypatch)

    class _TimeoutClient(_FakeHttpxClient):
        def post(self, url, json=None):
            raise TimeoutError("connect timed out")

    import httpx

    monkeypatch.setattr(httpx, "Client", _TimeoutClient)
    transport = _StreamableHttpSearchTransport("https://splunk.example.invalid", "tok", 30.0)
    with pytest.raises(McpTransportError):
        transport.submit({"search_query": "index=a"})


def test_transport_malformed_result_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.connectors.mcp.splunk_mcp import _StreamableHttpSearchTransport

    _patch_httpx(monkeypatch)
    transport = _StreamableHttpSearchTransport("https://splunk.example.invalid", "tok", 30.0)
    _FakeHttpxClient.last_instance.response = _FakeResponse(200, ["not", "a", "dict"])
    with pytest.raises(McpTransportError) as excinfo:
        transport.submit({"search_query": "index=a"})
    assert excinfo.value.error_type == "malformed_result"
