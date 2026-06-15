from __future__ import annotations

from typing import Any, Callable

from app.config import settings
from app.connectors.mcp.base import ConnectorStatus, KnowledgeObjectRequest
from app.connectors.mcp.discovery import McpToolDescriptor
from app.connectors.mcp.registry import load_mcp_registry_status
from app.connectors.mcp.splunk_mcp_readiness import (
    ALLOWED_READ_TOOL,
    SPLUNK_DISCOVERY_TOOLS,
    is_allowed_read_tool,
    is_disallowed_tool,
    plan_splunk_search_call,
)
from app.connectors.mcp.splunk_search_lifecycle import SearchTransport, run_search_lifecycle

# Canonical search tool (splunk_* surface). Contract/registry aliases normalize
# to this name at the live boundary (Go-live decision A.13 #4).
_CANONICAL_SEARCH_TOOL = "splunk_run_query"
_SEARCH_TOOL_ALIASES = {"splunk_run_query", "search_splunk", "splunk.search", "run_splunk_query"}

# Injectable transport factory — tests provide a fake; production builds the
# streamable_http transport from settings. Returns None when not configured
# (credential-pending, not code-pending).
SearchTransportFactory = Callable[[], "SearchTransport | None"]
_search_transport_factory: SearchTransportFactory | None = None


def set_search_transport_factory(factory: SearchTransportFactory | None) -> None:
    """Override the live search transport (test seam)."""
    global _search_transport_factory
    _search_transport_factory = factory


class SplunkMcpConnector:
    mode = "splunk_mcp"

    def health(self) -> ConnectorStatus:
        configured = bool(
            settings.splunk_mcp_enabled
            and settings.splunk_mcp_base_url.strip()
            and settings.splunk_mcp_token.strip()
        )
        registry = load_mcp_registry_status()
        if not registry.global_execution_enabled:
            return ConnectorStatus(
                mode=self.mode, configured=configured, available=False,
                detail="execution_disabled", implemented=True, fallback="mock",
            )
        if not configured:
            return ConnectorStatus(
                mode=self.mode, configured=False, available=False,
                detail="credentials_missing", implemented=True, fallback="mock",
            )
        # Adapter implemented + endpoint configured + execution enabled. Schema is
        # confirmed by the operator after staging smoke (doc-level), not here.
        return ConnectorStatus(
            mode=self.mode, configured=True, available=True,
            detail="live_adapter_ready", implemented=True, fallback="mock",
        )

    def list_tools(self, server_name: str | None = None) -> list[McpToolDescriptor]:
        return []

    def plan_search(
        self,
        *,
        trace_id: str,
        spl_validation: dict[str, Any] | None,
        evidence_plan: dict[str, Any] | None = None,
        path_type: str | None = None,
        signals: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Readiness-only planning surface — no network I/O."""
        record = plan_splunk_search_call(
            trace_id=trace_id,
            spl_validation=spl_validation,
            evidence_plan=evidence_plan,
            path_type=path_type,
            signals=signals,
        )
        return {
            "kind": record.kind,
            "server": record.server,
            "tool_name": record.tool_name,
            "arguments": dict(record.arguments),
            "block_reason": record.block_reason,
            "failure_mode": record.failure_mode,
            "policy_checks": list(record.policy_checks),
        }

    def call_tool(self, tool_name: str, arguments: dict[str, Any], server_name: str | None = None) -> dict[str, Any]:
        canonical = _CANONICAL_SEARCH_TOOL if tool_name in _SEARCH_TOOL_ALIASES else tool_name
        if is_disallowed_tool(canonical):
            return {"status": "blocked", "error": "tool_not_allowlisted", "tool_name": tool_name}
        is_discovery = canonical in SPLUNK_DISCOVERY_TOOLS
        if not is_discovery and not is_allowed_read_tool(canonical):
            return {"status": "blocked", "error": "tool_not_allowlisted", "tool_name": tool_name}
        if is_discovery:
            governance = arguments.get("_governance") if isinstance(arguments.get("_governance"), dict) else {}
            if not settings.mcp_discovery_enabled and governance.get("discovery_allowed") is not True:
                return {"status": "blocked", "error": "mcp_discovery_disabled", "tool_name": tool_name}
            # Discovery auto-execution is a separate decision (O4); not in v1.
            raise NotImplementedError("Splunk MCP live discovery execution is out of v1 scope (O4).")
        registry = load_mcp_registry_status()
        if not registry.global_execution_enabled:
            return {
                "status": "blocked",
                "error": "mcp_global_execution_disabled",
                "tool_name": canonical,
            }
        # Live search: drive the async job lifecycle inside the connector. The
        # gate calls this once; submit/poll/fetch is one logical investigation
        # call (A.3). Transport is built from settings (or injected in tests).
        transport = self._search_transport()
        if transport is None:
            return {
                "status": "blocked",
                "error": "live_transport_unconfigured",
                "tool_name": canonical,
            }
        return run_search_lifecycle(
            transport,
            arguments,
            max_polls=settings.mcp_max_polls_per_call,
            poll_interval_ms=settings.mcp_search_poll_interval_ms,
            job_timeout_ms=settings.mcp_search_job_timeout_ms,
        )

    def _search_transport(self) -> "SearchTransport | None":
        if _search_transport_factory is not None:
            return _search_transport_factory()
        return build_live_search_transport()

    def execute_validated_spl(
        self,
        *,
        server_name: str,
        tool_name: str,
        normalized_spl: str,
        trace_id: str,
        policy_context: dict[str, Any],
    ) -> dict[str, Any]:
        plan = self.plan_search(
            trace_id=trace_id,
            spl_validation={"approved": True, "normalized_spl": normalized_spl},
            evidence_plan={"needs_mcp": True, "mcp_allowed": True},
        )
        if plan.get("kind") != "planned_tool_call" or plan.get("failure_mode") == "execution_disabled":
            return {
                "status": "blocked",
                "error": plan.get("block_reason") or "mcp_execution_disabled",
                "planned_tool": plan,
            }
        # Live execution flows through call_tool (which drives the async search
        # lifecycle). The execution gate calls call_tool directly; this method is
        # a thin convenience that shares the same governed path.
        return self.call_tool(
            tool_name or _CANONICAL_SEARCH_TOOL,
            {"search_query": normalized_spl, "trace_id": trace_id},
            server_name=server_name,
        )

    def discover_knowledge_objects(self, request: KnowledgeObjectRequest) -> dict[str, Any]:
        return {"status": "not_implemented", "objects": []}


class _StreamableHttpSearchTransport:
    """Live search transport over MCP streamable_http (bearer auth).

    Most Splunk MCP servers run `splunk_run_query` server-side and return rows in
    one `tools/call`; we model that as an inline lifecycle (submit captures the
    result, poll reports done, fetch returns rows). If a deployment exposes a
    submit/poll/fetch job protocol instead, only this class changes — the gate,
    lifecycle bounds, and envelope mapping stay the same (credential drop-in).

    NOTE: the exact JSON-RPC framing is verified at first live connect
    (contract checklist). Until a base URL + token are configured this class is
    never constructed (factory returns None).
    """

    def __init__(self, base_url: str, token: str, timeout_seconds: float) -> None:
        import httpx  # lazy: optional dependency, only needed for live runs

        self._url = base_url.rstrip("/") + "/mcp"
        self._client = httpx.Client(
            timeout=timeout_seconds,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        self._inline: dict[str, dict[str, Any]] = {}

    def submit(self, arguments: dict[str, Any]) -> str:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": _CANONICAL_SEARCH_TOOL,
                "arguments": {k: v for k, v in arguments.items() if not k.startswith("_")},
            },
        }
        response = self._client.post(self._url, json=payload)
        if response.status_code in (401, 403):
            raise PermissionError("splunk_mcp_forbidden")
        response.raise_for_status()
        body = response.json()
        result = body.get("result") if isinstance(body, dict) else None
        rows = _rows_from_mcp_result(result)
        job_id = "inline-1"
        self._inline[job_id] = {"rows": rows}
        return job_id

    def poll(self, job_id: str) -> dict[str, Any]:
        # Inline model: the result was already captured at submit.
        return {"state": "done" if job_id in self._inline else "failed"}

    def fetch(self, job_id: str) -> dict[str, Any]:
        return self._inline.get(job_id, {"rows": []})


def _rows_from_mcp_result(result: Any) -> list[dict[str, Any]]:
    """Extract row dicts from a tools/call result, tolerating common shapes."""
    if isinstance(result, dict):
        for key in ("rows", "results", "records"):
            value = result.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
        content = result.get("structuredContent") or result.get("content")
        if isinstance(content, list):
            return [row for row in content if isinstance(row, dict)]
    return []


def build_live_search_transport() -> "SearchTransport | None":
    base_url = settings.splunk_mcp_base_url.strip()
    token = settings.splunk_mcp_token.strip()
    if not base_url or not token:
        return None
    try:
        return _StreamableHttpSearchTransport(
            base_url=base_url,
            token=token,
            timeout_seconds=settings.mcp_search_job_timeout_ms / 1000.0,
        )
    except Exception:  # noqa: BLE001 — missing httpx / bad config => fail closed.
        return None
