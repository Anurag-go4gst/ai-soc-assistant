"""EFFECTIVE_MCP_TOOL_CATALOG = SERVER_DISCOVERED ∩ LOCAL_APPROVED_ALLOWLIST ∩
DETERMINISTIC_TOOL_POLICY.

Closes the gap where `registry.py::McpServerStatus.discovered_tools` was
built entirely from `.env` TOOL_ALLOWLIST and never reconciled against what
the server actually advertised (`docs/evals/mcp_tool_discovery_selection_
audit_2026-08-17.md`, finding P0).

Two distinct, always-both-computed views (never conflated):

- `server_discovered_catalog` — everything the last discovery snapshot
  actually returned, including tools not in the local allowlist
  (SERVER_ONLY_NOT_APPROVED). Operator visibility only; the resolver never
  reads this to select a tool.
- `effective_approved_catalog` — only names from the local
  TOOL_ALLOWLIST, each tagged with a drift status and an `executable`
  bit. This is the only view `mcp_tool_selector.py` may read.

Local `TOOL_ALLOWLIST` / `classify_mcp_tool()` remain sole authorization
policy. The server cannot authorize itself — a tool being present and
schema-compatible on the server is necessary but never sufficient; it must
also already be in the local allowlist and pass local safety
classification.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Literal

from app.connectors.mcp.discovery_snapshot import DiscoverySnapshot, DiscoveredToolRecord
from app.connectors.mcp.mcp_rbac import canonical_mcp_tool_name
from app.connectors.mcp.registry import McpRegistryStatus, McpServerStatus

DriftStatus = Literal[
    "DISCOVERY_UNVERIFIED",
    "APPROVED_AND_PRESENT",
    "APPROVED_BUT_MISSING",
    "SERVER_ONLY_NOT_APPROVED",
    "SCHEMA_MISMATCH",
    "SCHEMA_UNKNOWN",
    "UNSAFE_OR_BLOCKED",
    "DISCOVERY_STALE",
    "DISCOVERY_FAILED",
]

SchemaStatus = Literal["SCHEMA_COMPATIBLE", "SCHEMA_INCOMPATIBLE", "SCHEMA_UNKNOWN"]

# Local policy constant, not an activation flag: how old a snapshot may be
# before live COE execution treats it as untrustworthy. Refresh lifecycle
# stays operator-triggered (explicit startup/refresh action) per the
# discovery-refresh policy; this only bounds how long a stale answer may
# gate real execution.
DISCOVERY_STALE_THRESHOLD_SECONDS = 24 * 60 * 60


@dataclass(frozen=True)
class LocalToolContract:
    """What we actually require to call a tool. Absence of a required
    parameter from `no_required_params=True` is a deliberate, explicit local
    statement that this tool legitimately takes no required arguments — not
    an assumption. Tools with no implemented connector call path yet (see
    audit finding: 4 discovery tools raise NotImplementedError,
    splunk_get_user_info/splunk_get_info are not connector-allowlisted) get
    `no_required_params=True` here because we do not invent argument names
    for contracts we have not implemented — this makes schema comparison a
    no-op for them until a real implementation defines real requirements."""

    required_params: tuple[str, ...] = ()
    param_types: dict[str, str] = field(default_factory=dict)
    no_required_params: bool = False


# Only the two tools with an implemented, argument-passing execution path
# (splunk_search_tool_arguments / splunk_saved_search_tool_arguments) get a
# real contract. Everything else is explicitly "no required params" per the
# no-invented-arguments rule above.
LOCAL_TOOL_CONTRACTS: dict[str, LocalToolContract] = {
    "splunk_run_query": LocalToolContract(required_params=("search_query",), param_types={"search_query": "string"}),
    "splunk_run_saved_search": LocalToolContract(required_params=("saved_search_name",), param_types={"saved_search_name": "string"}),
    "splunk_get_info": LocalToolContract(no_required_params=True),
    "splunk_get_indexes": LocalToolContract(no_required_params=True),
    "splunk_get_index_info": LocalToolContract(no_required_params=True),
    "splunk_get_metadata": LocalToolContract(no_required_params=True),
    "splunk_get_user_info": LocalToolContract(no_required_params=True),
    "splunk_get_knowledge_objects": LocalToolContract(no_required_params=True),
}

_DANGEROUS_NEW_PARAM_MARKERS = ("write", "delete", "admin", "remediate", "contain", "isolate", "modify", "execute_write")


def compare_schema(
    tool_name: str,
    *,
    server_input_schema: dict[str, Any],
    server_input_schema_malformed: bool,
) -> SchemaStatus:
    """Deterministic comparison against a LOCAL expected contract — never a
    raw JSON-equality check, never trusting server descriptions as policy."""
    if server_input_schema_malformed:
        return "SCHEMA_INCOMPATIBLE"
    contract = LOCAL_TOOL_CONTRACTS.get(canonical_mcp_tool_name(tool_name))
    if contract is None:
        return "SCHEMA_UNKNOWN"  # no local contract defined for this tool at all
    if not server_input_schema:
        return "SCHEMA_COMPATIBLE" if contract.no_required_params else "SCHEMA_UNKNOWN"
    properties = server_input_schema.get("properties")
    properties = properties if isinstance(properties, dict) else {}
    required = server_input_schema.get("required")
    required = required if isinstance(required, list) else []
    for param in contract.required_params:
        if param not in properties:
            return "SCHEMA_INCOMPATIBLE"  # expected required property missing
        prop = properties.get(param)
        actual_type = prop.get("type") if isinstance(prop, dict) else None
        expected_type = contract.param_types.get(param)
        if expected_type and actual_type and expected_type != actual_type:
            return "SCHEMA_INCOMPATIBLE"  # incompatible parameter type
    for req_name in required:
        req_name_str = str(req_name).lower()
        if str(req_name) not in contract.required_params and any(marker in req_name_str for marker in _DANGEROUS_NEW_PARAM_MARKERS):
            return "SCHEMA_INCOMPATIBLE"  # execution-sensitive new required parameter
    return "SCHEMA_COMPATIBLE"


def schema_fingerprint(server_input_schema: dict[str, Any]) -> str:
    """Normalized hash for operator drift diagnostics only — never a policy input."""
    return hashlib.sha256(json.dumps(server_input_schema or {}, sort_keys=True).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EffectiveToolEntry:
    name: str
    capability: str
    blocked: bool
    drift_status: DriftStatus
    executable: bool
    schema_status: SchemaStatus | None
    schema_fingerprint: str | None
    server_present: bool | None  # None = discovery never verified


@dataclass(frozen=True)
class ServerOnlyToolEntry:
    name: str
    description: str
    schema_fingerprint: str


@dataclass(frozen=True)
class EffectiveCatalogResult:
    server_name: str
    mode: str
    effective_approved_catalog: tuple[EffectiveToolEntry, ...]
    server_discovered_catalog: tuple[ServerOnlyToolEntry, ...]  # SERVER_ONLY_NOT_APPROVED names only
    discovery_status: str  # "unverified" | "ok" | "failed" | "stale"
    discovery_age_seconds: float | None

    def entry_for(self, tool_name: str) -> EffectiveToolEntry | None:
        for entry in self.effective_approved_catalog:
            if entry.name == tool_name:
                return entry
        return None

    def is_executable(self, tool_name: str) -> bool:
        entry = self.entry_for(tool_name)
        return bool(entry and entry.executable)


def compute_effective_catalog(
    server: McpServerStatus,
    *,
    mode: str,
    snapshot: DiscoverySnapshot | None,
    now: float | None = None,
) -> EffectiveCatalogResult:
    """Pure function: registry server status (local policy) + a discovery
    snapshot (untrusted server-reported state) -> both catalog views."""
    now_ts = float(now if now is not None else time.time())

    discovery_status = "unverified"
    stale = False
    if snapshot is not None:
        if snapshot.status == "failed":
            discovery_status = "failed"
        elif (now_ts - snapshot.captured_at) > DISCOVERY_STALE_THRESHOLD_SECONDS:
            discovery_status = "stale"
            stale = True
        else:
            discovery_status = "ok"

    entries: list[EffectiveToolEntry] = []
    for tool in server.discovered_tools:  # local allowlist, classified — unchanged authority source
        name = str(tool.get("name") or "")
        blocked = bool(tool.get("blocked"))
        capability = str(tool.get("capability") or "unknown")
        safe_classification = not blocked

        server_record: DiscoveredToolRecord | None = snapshot.tool_by_name(name) if snapshot is not None else None
        server_present = (server_record is not None) if (snapshot is not None and snapshot.status == "ok") else None

        schema_status: SchemaStatus | None = None
        fingerprint: str | None = None
        if server_record is not None:
            schema_status = compare_schema(
                name,
                server_input_schema=server_record.input_schema,
                server_input_schema_malformed=server_record.input_schema_malformed,
            )
            fingerprint = schema_fingerprint(server_record.input_schema)

        if not safe_classification:
            drift_status: DriftStatus = "UNSAFE_OR_BLOCKED"
            executable = False
        elif mode != "registry":
            # Mock/development compatibility: unchanged legacy behavior.
            # Does not weaken the live-COE rule below.
            drift_status = "APPROVED_AND_PRESENT"
            executable = True
        elif snapshot is None:
            drift_status = "DISCOVERY_UNVERIFIED"
            executable = False
        elif snapshot.status == "failed":
            drift_status = "DISCOVERY_FAILED"
            executable = False
        elif stale:
            drift_status = "DISCOVERY_STALE"
            executable = False
        elif server_record is None:
            drift_status = "APPROVED_BUT_MISSING"
            executable = False
        elif schema_status == "SCHEMA_INCOMPATIBLE":
            drift_status = "SCHEMA_MISMATCH"
            executable = False
        elif schema_status == "SCHEMA_UNKNOWN":
            drift_status = "SCHEMA_UNKNOWN"
            executable = False
        else:
            drift_status = "APPROVED_AND_PRESENT"
            executable = True

        entries.append(
            EffectiveToolEntry(
                name=name,
                capability=capability,
                blocked=blocked,
                drift_status=drift_status,
                executable=executable,
                schema_status=schema_status,
                schema_fingerprint=fingerprint,
                server_present=server_present,
            )
        )

    approved_names = {str(tool.get("name") or "") for tool in server.discovered_tools}
    server_only: list[ServerOnlyToolEntry] = []
    if snapshot is not None and snapshot.status == "ok":
        for record in snapshot.tools:
            if record.name in approved_names:
                continue
            server_only.append(
                ServerOnlyToolEntry(
                    name=record.name,
                    description=record.description,
                    schema_fingerprint=schema_fingerprint(record.input_schema),
                )
            )

    return EffectiveCatalogResult(
        server_name=server.name,
        mode=mode,
        effective_approved_catalog=tuple(entries),
        server_discovered_catalog=tuple(server_only),
        discovery_status=discovery_status,
        discovery_age_seconds=snapshot.age_seconds if snapshot is not None else None,
    )


def compute_effective_catalog_for_registry(
    registry: McpRegistryStatus,
    *,
    snapshot_store: Any,
    now: float | None = None,
) -> dict[str, EffectiveCatalogResult]:
    """Convenience: one result per server in the registry."""
    results: dict[str, EffectiveCatalogResult] = {}
    for server in registry.servers:
        snapshot = snapshot_store.get(server.name)
        results[server.name] = compute_effective_catalog(server, mode=registry.mode, snapshot=snapshot, now=now)
    return results
