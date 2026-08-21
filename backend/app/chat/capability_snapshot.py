"""CapabilitySnapshot — need × availability planning vocabulary (architecture P1).

Deterministic join of registries / MCP discovery ∩ allowlist / global tool
classification. Planning only — never execution authorization.

Axes (only these two on planner rows):

    capability_need: required | recommended | optional
    availability:    available | unavailable

``availability=available`` means registered + discovered (verified tools/list) +
allowlisted + valid classification. It does **not** encode RBAC, AUTH0, HIL,
envelope, PhaseContract, or ``MCP_GLOBAL_EXECUTION_ENABLED``.

``SERVER_ONLY_NOT_APPROVED`` tools are operator-only and never appear as planner
rows. There is no ``executable`` field on this contract.
"""

from __future__ import annotations

from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.actions import email_adapter
from app.actions.remediation_execution import ADAPTERS
from app.chat.skill_intent_compatibility import CAPABILITY_MCP, CAPABILITY_SPL
from app.connectors.mcp.discovery import classify_mcp_tool
from app.connectors.mcp.effective_catalog import (
    EffectiveCatalogResult,
    EffectiveToolEntry,
    compute_effective_catalog,
)
from app.connectors.mcp.discovery_snapshot import DiscoverySnapshot

SCHEMA_VERSION = "capability_snapshot_v1"

CapabilityNeed = Literal["required", "recommended", "optional"]
Availability = Literal["available", "unavailable"]

#: Drift statuses that count as planning-time "present and approved".
_AVAILABLE_DRIFT: frozenset[str] = frozenset({"APPROVED_AND_PRESENT"})

#: Well-known non-MCP planning kinds (writes / coordination). Availability follows
#: explicit registration hooks — never Experience Center fixtures.
KNOWN_ACTION_KINDS: tuple[str, ...] = (
    "firewall_block",
    "email_send",
)


class CapabilityRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability_id: str = Field(min_length=1)
    capability_need: CapabilityNeed
    availability: Availability


class CapabilitySnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    rows: list[CapabilityRow] = Field(default_factory=list)

    @model_validator(mode="after")
    def _no_executable_and_unique_ids(self) -> CapabilitySnapshot:
        # Belt-and-braces: forbid any accidental executable-like payload if a
        # future caller bypasses CapabilityRow typing.
        raw = self.model_dump()
        if "executable" in raw:
            raise ValueError("CapabilitySnapshot must not carry executable")
        ids = [row.capability_id for row in self.rows]
        if len(ids) != len(set(ids)):
            raise ValueError("CapabilitySnapshot capability_id values must be unique")
        return self

    def row_for(self, capability_id: str) -> CapabilityRow | None:
        for row in self.rows:
            if row.capability_id == capability_id:
                return row
        return None


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        payload = dump(mode="json")
        return payload if isinstance(payload, dict) else {}
    return {}


def _capability_set(raw: Any) -> frozenset[str]:
    if raw is None:
        return frozenset()
    if isinstance(raw, (set, frozenset, list, tuple)):
        return frozenset(str(item) for item in raw)
    return frozenset()


def mcp_tool_capability_id(server_name: str, tool_name: str) -> str:
    return f"mcp:{server_name}:{tool_name}"


def action_capability_id(kind: str) -> str:
    return f"action:{kind}"


def _availability_from_entry(entry: EffectiveToolEntry) -> Availability:
    """Map effective-catalog drift to planning availability.

    Unlike ``entry.executable``, mock-mode short-circuits do **not** make a tool
    available without verified discovery — P1 treats DISCOVERY_UNVERIFIED as
    unavailable even when execution flags / mock mode would allow gate paths.
    """
    if entry.blocked or entry.drift_status == "UNSAFE_OR_BLOCKED":
        return "unavailable"
    if entry.drift_status in _AVAILABLE_DRIFT and entry.server_present is True:
        return "available"
    # Mock path marks APPROVED_AND_PRESENT with server_present=None and no snapshot.
    # That is discovery-unverified for planning purposes.
    if entry.drift_status == "APPROVED_AND_PRESENT" and entry.server_present is True:
        return "available"
    return "unavailable"


def _need_for_mcp_tool(
    *,
    tool_name: str,
    required_caps: frozenset[str],
    intent_family: str,
) -> CapabilityNeed:
    splunk_search = tool_name in {"splunk_run_query", "run_splunk_query", "splunk_run_saved_search"}
    if splunk_search and (CAPABILITY_SPL in required_caps or CAPABILITY_MCP in required_caps):
        return "required"
    if splunk_search and intent_family in {
        "guided_investigation",
        "live_investigation",
        "hybrid_investigation",
        "hybrid_investigation_plus_policy",
    }:
        return "required"
    if tool_name.startswith("splunk_get_") or tool_name in {"get_splunk_metadata"}:
        return "optional"
    return "recommended"


def _project_mcp_rows(
    *,
    catalogs: Mapping[str, EffectiveCatalogResult],
    required_caps: frozenset[str],
    intent_family: str,
) -> list[CapabilityRow]:
    rows: list[CapabilityRow] = []
    for server_name, catalog in catalogs.items():
        for entry in catalog.effective_approved_catalog:
            # Re-check global classification — blocked tools stay unavailable.
            classified = classify_mcp_tool(entry.name, server_type="splunk" if "splunk" in server_name.lower() else "generic")
            availability = _availability_from_entry(entry)
            if classified.blocked:
                availability = "unavailable"
            rows.append(
                CapabilityRow(
                    capability_id=mcp_tool_capability_id(server_name, entry.name),
                    capability_need=_need_for_mcp_tool(
                        tool_name=entry.name,
                        required_caps=required_caps,
                        intent_family=intent_family,
                    ),
                    availability=availability,
                )
            )
        # SERVER_ONLY_NOT_APPROVED deliberately omitted from planner vocabulary.
    return rows


def _project_action_rows(
    *,
    registered_action_kinds: Mapping[str, bool] | None,
) -> list[CapabilityRow]:
    """Action kinds: need is recommended/optional; availability from registration only."""
    registered = registered_action_kinds or {}
    rows: list[CapabilityRow] = []
    for kind in KNOWN_ACTION_KINDS:
        need: CapabilityNeed = "recommended" if kind == "firewall_block" else "optional"
        available = bool(registered.get(kind))
        rows.append(
            CapabilityRow(
                capability_id=action_capability_id(kind),
                capability_need=need,
                availability="available" if available else "unavailable",
            )
        )
    return rows


def build_capability_snapshot(
    *,
    resolved_query_contract: dict[str, Any] | Any | None,
    mcp_catalogs: Mapping[str, EffectiveCatalogResult] | None = None,
    registered_action_kinds: Mapping[str, bool] | None = None,
) -> CapabilitySnapshot:
    """Pure builder — injectable catalogs for tests; no LLM; no RBAC join."""
    rqc = _as_dict(resolved_query_contract)
    required_caps = _capability_set(rqc.get("required_capabilities"))
    intent_family = str(rqc.get("intent_family") or "").strip()

    rows: list[CapabilityRow] = []
    if mcp_catalogs:
        rows.extend(
            _project_mcp_rows(
                catalogs=mcp_catalogs,
                required_caps=required_caps,
                intent_family=intent_family,
            )
        )
    rows.extend(_project_action_rows(registered_action_kinds=registered_action_kinds))

    # Stable order for determinism.
    rows.sort(key=lambda row: row.capability_id)
    return CapabilitySnapshot(rows=rows)


def load_live_mcp_catalogs() -> dict[str, EffectiveCatalogResult]:
    """Read current registry + in-memory discovery snapshots (may be unverified)."""
    from app.connectors.mcp.discovery_snapshot import get_discovery_snapshot_store
    from app.connectors.mcp.registry import load_mcp_registry_status

    registry = load_mcp_registry_status()
    store = get_discovery_snapshot_store()
    catalogs: dict[str, EffectiveCatalogResult] = {}
    for server in registry.servers:
        snapshot: DiscoverySnapshot | None = store.get(server.name)
        catalogs[server.name] = compute_effective_catalog(
            server,
            mode=registry.mode,
            snapshot=snapshot,
        )
    return catalogs


def production_registered_action_kinds() -> dict[str, bool]:
    """Production registration map — email becomes true only when a /chat adapter exists.

    P11 owns the production email adapter. Until then email_send stays unavailable
    for planning (manual/alternate path), independent of EC demo transport.
    """
    return {
        "firewall_block": False,
        "email_send": bool(
            "email_send" in ADAPTERS
            and email_adapter.configured()
            and email_adapter.default_recipient()
        ),
    }


def maybe_attach_capability_snapshot(
    state: dict[str, Any],
    *,
    resolved_query_contract: dict[str, Any] | Any | None,
    mcp_catalogs: Mapping[str, EffectiveCatalogResult] | None = None,
    registered_action_kinds: Mapping[str, bool] | None = None,
) -> dict[str, Any]:
    """Flag-gated attachment after Final RQC. Flag-off leaves state unchanged."""
    from app.config import settings

    if not settings.ai_soc_capability_snapshot_enabled:
        return state
    catalogs = mcp_catalogs if mcp_catalogs is not None else load_live_mcp_catalogs()
    actions = (
        registered_action_kinds
        if registered_action_kinds is not None
        else production_registered_action_kinds()
    )
    snapshot = build_capability_snapshot(
        resolved_query_contract=resolved_query_contract,
        mcp_catalogs=catalogs,
        registered_action_kinds=actions,
    )
    return {**state, "capability_snapshot": snapshot.model_dump(mode="json")}
