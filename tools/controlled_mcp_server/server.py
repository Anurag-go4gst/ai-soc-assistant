"""Local external MCP test server — fixture telemetry only.

Speaks the same JSON-RPC streamable HTTP contract the SOC live Splunk
transport already uses (`initialize`, `tools/list`, `tools/call`). The SOC
product discovers it through the normal registry path. This process owns the
deterministic rows; production code must not branch on test queries.
"""

from __future__ import annotations

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

PROTOCOL_VERSION = "2024-11-05"
DEFAULT_TOKEN = "controlled-mcp-token"

PROCESS_ROWS = [
    {
        "host": "WS-14",
        "user": "jdoe",
        "parent_process": "WINWORD.EXE",
        "process": "powershell.exe",
        "cmdline": "powershell.exe -NoProfile -EncodedCommand <redacted>",
        "_time": "2026-09-07T12:01:04Z",
    }
]
PERSISTENCE_ROWS = [
    {
        "host": "WS-14",
        "user": "jdoe",
        "action": "scheduled_task_created",
        "task_name": "OfficeUpdateCheck",
        "task_exec": "powershell.exe",
        "_time": "2026-09-07T12:04:18Z",
    }
]
NETWORK_ROWS = [
    {
        "host": "WS-14",
        "user": "jdoe",
        "src": "10.4.2.11",
        "dest": "198.51.100.88",
        "dest_port": 443,
        "bytes": 184320,
        "_time": "2026-09-07T12:05:02Z",
    }
]

#: Hypothesis-revision fixture. READ #1 returns a SIGNED, well-known administrative
#: binary -- process identity alone therefore weakens "malware binary" -- but carries
#: one suspicious contextual clue (a service account running it out of hours from an
#: unexpected parent). READ #2 supplies the lineage/session/destination context that
#: separates legitimate administration from abuse of a legitimate tool. The expected
#: conclusion is deliberately NOT encoded here; only telemetry is.
ADMIN_TOOL_FIRST_READ_ROWS = [
    {
        "host": "SRV-APP-03",
        "user": "svc_backup",
        "parent_process": "wscript.exe",
        "process": "psexec.exe",
        "signature_status": "signed",
        "signer": "Microsoft Corporation",
        "product_name": "PsExec Sysinternals",
        "cmdline": "psexec.exe -s cmd.exe",
        "_time": "2026-09-08T02:47:11Z",
    }
]
ADMIN_TOOL_SECOND_READ_ROWS = [
    {
        "host": "SRV-APP-03",
        "user": "svc_backup",
        "logon_type": "3",
        "src": "10.9.4.51",
        "dest": "203.0.113.77",
        "dest_port": 443,
        "bytes": 940112,
        "_time": "2026-09-08T02:49:36Z",
    },
    {
        "host": "SRV-APP-03",
        "user": "svc_backup",
        "action": "scheduled_task_created",
        "task_name": "BackupHealthCheck",
        "task_exec": "psexec.exe",
        "_time": "2026-09-08T02:51:02Z",
    },
]

TOOLS = [
    {
        "name": "splunk_run_query",
        "description": "Run validator-approved bounded SPL search.",
        "inputSchema": {
            "type": "object",
            "properties": {"search_query": {"type": "string"}, "query": {"type": "string"}},
            "required": ["search_query"],
        },
    },
    {
        "name": "splunk_get_info",
        "description": "Return Splunk server identity metadata.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "splunk_get_indexes",
        "description": "List available indexes.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "splunk_get_metadata",
        "description": "List sourcetypes.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "splunk_get_knowledge_objects",
        "description": "List knowledge objects.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


class FixtureState:
    def __init__(self, *, token: str, mode: str) -> None:
        self.token = token
        self.mode = mode
        self.search_calls = 0
        self.lock = threading.Lock()


class ControlledMcpHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def do_POST(self) -> None:  # noqa: N802
        state: FixtureState = self.server.fixture_state  # type: ignore[attr-defined]
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        auth = self.headers.get("Authorization") or ""
        if auth != f"Bearer {state.token}":
            self._send(401, {"jsonrpc": "2.0", "id": None, "error": {"code": -32001, "message": "unauthorized"}})
            return
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send(400, {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
            return
        rpc_id = payload.get("id")
        method = str(payload.get("method") or "")
        if method == "initialize":
            result = {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "controlled-mcp", "version": "1.0"},
            }
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
            result = self._call_tool(state, params)
        elif method in {"notifications/initialized", "initialized"}:
            self._send(200, {"jsonrpc": "2.0", "id": rpc_id, "result": {}})
            return
        else:
            self._send(
                200,
                {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": -32601, "message": f"unknown tool {method}"}},
            )
            return
        self._send(200, {"jsonrpc": "2.0", "id": rpc_id, "result": result})

    def _call_tool(self, state: FixtureState, params: dict[str, Any]) -> dict[str, Any]:
        name = str(params.get("name") or "")
        arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        if name == "splunk_get_info":
            return {"rows": [{"server_name": "controlled-mcp", "server_version": "9.1.0"}]}
        if name == "splunk_get_indexes":
            return {"rows": [{"index": "pgcil_soc"}]}
        if name == "splunk_get_metadata":
            return {"rows": [{"sourcetype": "pgcil:edr"}, {"sourcetype": "pgcil:sysmon"}, {"sourcetype": "pgcil:proxy"}]}
        if name == "splunk_get_knowledge_objects":
            return {"objects": []}
        if name not in {"splunk_run_query", "run_splunk_query", "search_splunk"}:
            return {"error": "unknown tool", "rows": []}
        with state.lock:
            state.search_calls += 1
            call_no = state.search_calls
        if state.mode == "admin_tool_revision":
            rows = (
                list(ADMIN_TOOL_FIRST_READ_ROWS)
                if call_no == 1
                else list(ADMIN_TOOL_SECOND_READ_ROWS)
            )
        elif state.mode == "insufficient":
            rows = list(PROCESS_ROWS)
        elif call_no == 1:
            rows = list(PROCESS_ROWS)
        else:
            rows = list(PERSISTENCE_ROWS) + list(NETWORK_ROWS)
        query = str(arguments.get("search_query") or arguments.get("query") or "")
        return {"rows": rows, "query_hash": str(abs(hash(query)))[:12]}

    def _send(self, status: int, body: dict[str, Any]) -> None:
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


class ControlledMcpServer:
    def __init__(self, *, host: str = "127.0.0.1", port: int = 0, token: str = DEFAULT_TOKEN, mode: str = "full"):
        self._httpd = ThreadingHTTPServer((host, port), ControlledMcpHandler)
        self._httpd.fixture_state = FixtureState(token=token, mode=mode)  # type: ignore[attr-defined]
        self._thread: threading.Thread | None = None
        self.token = token
        self.mode = mode

    @property
    def port(self) -> int:
        return int(self._httpd.server_address[1])

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def search_calls(self) -> int:
        return int(self._httpd.fixture_state.search_calls)  # type: ignore[attr-defined]

    def start(self) -> str:
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return self.base_url

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Controlled external MCP test server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18081)
    parser.add_argument("--token", default=DEFAULT_TOKEN)
    parser.add_argument("--mode", choices=("full", "insufficient", "admin_tool_revision"), default="full")
    args = parser.parse_args()
    server = ControlledMcpServer(host=args.host, port=args.port, token=args.token, mode=args.mode)
    print(f"controlled-mcp listening on {server.start()}/mcp mode={args.mode}", flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        server.stop()


if __name__ == "__main__":
    main()
