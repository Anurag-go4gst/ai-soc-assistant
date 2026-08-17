"""MCP discovery snapshot storage.

Holds what a real `initialize`/`tools/list` handshake actually returned for a
server, so `registry.py` can compute an EFFECTIVE_APPROVED_CATALOG that is
`SERVER_DISCOVERED ∩ LOCAL_APPROVED_ALLOWLIST` instead of treating the
allowlist as if it were discovery.

Snapshot content is UNTRUSTED discovery metadata — it is never itself
authorization. `TOOL_ALLOWLIST` and `classify_mcp_tool()` remain the sole
local policy authority; this module only records what the server said.

Storage: process-runtime cache (module-level, thread-safe), populated only
by explicit startup/operator discovery -- never per-request, never
implicitly. A Postgres-backed store following the existing
`app/connectors/telemetry/db.py` (asyncpg + `app/db/migrations/`) pattern is
the natural next step for cross-restart durability (schema already added at
`app/db/migrations/0007_mcp_discovery_snapshot.sql`) but is not implemented
here -- this session had no reachable live Postgres to prove an asyncpg
write path against, and an unproven DB writer must not be claimed as done.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any

# Fields we accept from a raw tool descriptor (see splunk_mcp.py's
# `_tool_descriptors_from_list_result`). Never accept or store anything
# resembling a credential/token -- descriptions are already redacted at
# parse time, but we redact again defensively here since this is the
# storage boundary.
_SECRET_TOKEN_MARKERS = ("bearer ", "authorization:", "token=", "secret=", "api_key=", "apikey=")


@dataclass(frozen=True)
class DiscoveredToolRecord:
    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    input_schema_malformed: bool = False
    annotations: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DiscoverySnapshot:
    server_name: str
    captured_at: float
    source: str  # "startup" | "operator_refresh"
    status: str  # "ok" | "failed"
    tools: tuple[DiscoveredToolRecord, ...] = ()
    error_reason: str | None = None

    @property
    def age_seconds(self) -> float:
        return max(0.0, time.time() - self.captured_at)

    def tool_by_name(self, name: str) -> DiscoveredToolRecord | None:
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None

    def to_safe_dict(self) -> dict[str, Any]:
        """Operator-visible projection. No secrets, no raw evidence."""
        return {
            "server_name": self.server_name,
            "captured_at": self.captured_at,
            "age_seconds": self.age_seconds,
            "source": self.source,
            "status": self.status,
            "error_reason": self.error_reason,
            "tool_count": len(self.tools),
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema_malformed": tool.input_schema_malformed,
                    "has_input_schema": bool(tool.input_schema),
                    "annotations": tool.annotations,
                }
                for tool in self.tools
            ],
        }


def _redact_description(value: str) -> str:
    lowered = value.lower()
    if any(marker in lowered for marker in _SECRET_TOKEN_MARKERS):
        return "[redacted: description contained a credential-like pattern]"
    return value


def build_snapshot_from_handshake(
    *,
    server_name: str,
    handshake_result: dict[str, Any],
    source: str,
    now: float | None = None,
) -> DiscoverySnapshot:
    """Build a snapshot from `SplunkMcpConnector.handshake_initialize_and_list_tools()`
    output. Never raises -- a malformed/blocked handshake becomes a
    `status="failed"` snapshot, not an exception, so discovery refresh can
    never crash a caller."""
    captured_at = float(now if now is not None else time.time())
    if not isinstance(handshake_result, dict) or handshake_result.get("status") != "ok":
        error_reason = handshake_result.get("error") if isinstance(handshake_result, dict) else None
        return DiscoverySnapshot(
            server_name=server_name,
            captured_at=captured_at,
            source=source,
            status="failed",
            tools=(),
            error_reason=str(error_reason or "handshake_not_ok"),
        )
    raw_descriptors = handshake_result.get("tool_descriptors")
    tools: list[DiscoveredToolRecord] = []
    if isinstance(raw_descriptors, list):
        for item in raw_descriptors:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            tools.append(
                DiscoveredToolRecord(
                    name=str(item["name"]),
                    description=_redact_description(str(item.get("description") or "")),
                    input_schema=item.get("input_schema") if isinstance(item.get("input_schema"), dict) else {},
                    input_schema_malformed=bool(item.get("input_schema_malformed")),
                    annotations=item.get("annotations") if isinstance(item.get("annotations"), dict) else {},
                )
            )
    return DiscoverySnapshot(
        server_name=server_name,
        captured_at=captured_at,
        source=source,
        status="ok",
        tools=tuple(tools),
        error_reason=None,
    )


class InMemoryDiscoverySnapshotStore:
    """Process-runtime cache. Thread-safe. No implicit refresh -- callers
    (a startup hook or an explicit operator-refresh action) decide when a
    new snapshot is captured; nothing here calls the network."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._snapshots: dict[str, DiscoverySnapshot] = {}

    def put(self, snapshot: DiscoverySnapshot) -> None:
        with self._lock:
            self._snapshots[snapshot.server_name] = snapshot

    def get(self, server_name: str) -> DiscoverySnapshot | None:
        with self._lock:
            return self._snapshots.get(server_name)

    def all(self) -> dict[str, DiscoverySnapshot]:
        with self._lock:
            return dict(self._snapshots)

    def clear(self) -> None:
        with self._lock:
            self._snapshots.clear()


_STORE = InMemoryDiscoverySnapshotStore()


def get_discovery_snapshot_store() -> InMemoryDiscoverySnapshotStore:
    """Single process-wide store. Swappable in tests via
    `discovery_snapshot._STORE` or by constructing an isolated
    `InMemoryDiscoverySnapshotStore()` and passing it explicitly."""
    return _STORE


def snapshot_to_json(snapshot: DiscoverySnapshot) -> str:
    return json.dumps(snapshot.to_safe_dict(), sort_keys=True)
