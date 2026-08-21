"""P1 — CapabilitySnapshot need × availability projection."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.chat.capability_snapshot import (
    CapabilityRow,
    CapabilitySnapshot,
    action_capability_id,
    build_capability_snapshot,
    maybe_attach_capability_snapshot,
    mcp_tool_capability_id,
)
from app.chat.skill_intent_compatibility import CAPABILITY_MCP, CAPABILITY_SPL
from app.config import settings
from app.connectors.mcp.effective_catalog import EffectiveCatalogResult, EffectiveToolEntry


def _entry(
    name: str,
    *,
    drift: str,
    blocked: bool = False,
    server_present: bool | None = True,
    executable: bool = False,
) -> EffectiveToolEntry:
    return EffectiveToolEntry(
        name=name,
        capability="spl_search" if "run_query" in name else "metadata_lookup",
        blocked=blocked,
        drift_status=drift,  # type: ignore[arg-type]
        executable=executable,
        schema_status="SCHEMA_COMPATIBLE",
        schema_fingerprint=None,
        server_present=server_present,
    )


def _catalog(server: str, *entries: EffectiveToolEntry, discovery_status: str = "ok") -> dict[str, EffectiveCatalogResult]:
    return {
        server: EffectiveCatalogResult(
            server_name=server,
            mode="registry",
            effective_approved_catalog=tuple(entries),
            server_discovered_catalog=(),
            discovery_status=discovery_status,
            discovery_age_seconds=1.0,
        )
    }


def test_firewall_block_recommended_unavailable_is_valid() -> None:
    snap = build_capability_snapshot(
        resolved_query_contract={"intent_family": "live_investigation", "required_capabilities": []},
        mcp_catalogs={},
        registered_action_kinds={"firewall_block": False, "email_send": False},
    )
    row = snap.row_for(action_capability_id("firewall_block"))
    assert row is not None
    assert row.capability_need == "recommended"
    assert row.availability == "unavailable"


def test_required_available_does_not_authorize_mcp() -> None:
    catalogs = _catalog(
        "splunk_soc",
        _entry("splunk_run_query", drift="APPROVED_AND_PRESENT", server_present=True, executable=True),
    )
    snap = build_capability_snapshot(
        resolved_query_contract={
            "intent_family": "live_investigation",
            "required_capabilities": [CAPABILITY_SPL, CAPABILITY_MCP],
        },
        mcp_catalogs=catalogs,
        registered_action_kinds={},
    )
    row = snap.row_for(mcp_tool_capability_id("splunk_soc", "splunk_run_query"))
    assert row is not None
    assert row.capability_need == "required"
    assert row.availability == "available"
    # Snapshot is vocabulary only — no executable / auth fields.
    dumped = snap.model_dump()
    assert "executable" not in dumped
    assert all("executable" not in row.model_dump() for row in snap.rows)


def test_same_snapshot_for_two_rbac_roles() -> None:
    catalogs = _catalog(
        "splunk_soc",
        _entry("splunk_run_query", drift="APPROVED_AND_PRESENT", server_present=True),
    )
    rqc = {"intent_family": "guided_investigation", "required_capabilities": [CAPABILITY_MCP]}
    a = build_capability_snapshot(resolved_query_contract=rqc, mcp_catalogs=catalogs, registered_action_kinds={})
    b = build_capability_snapshot(resolved_query_contract=rqc, mcp_catalogs=catalogs, registered_action_kinds={})
    # RBAC is not an input — identical RQC + catalogs ⇒ identical snapshot.
    assert a.model_dump() == b.model_dump()


def test_snapshot_identical_for_t13_vs_t4_same_rqc() -> None:
    catalogs = _catalog(
        "splunk_soc",
        _entry("splunk_run_query", drift="APPROVED_AND_PRESENT", server_present=True),
    )
    rqc_t13 = {
        "intent_family": "live_investigation",
        "required_capabilities": [CAPABILITY_SPL],
        "understanding_source": "deterministic_qualification",
    }
    rqc_t4 = {
        **rqc_t13,
        "understanding_source": "semantic_t4",
        "provenance": {"t4": True},
    }
    a = build_capability_snapshot(resolved_query_contract=rqc_t13, mcp_catalogs=catalogs, registered_action_kinds={})
    b = build_capability_snapshot(resolved_query_contract=rqc_t4, mcp_catalogs=catalogs, registered_action_kinds={})
    assert a.rows == b.rows


def test_discovery_unverified_splunk_not_available() -> None:
    catalogs = _catalog(
        "splunk_soc",
        _entry("splunk_run_query", drift="DISCOVERY_UNVERIFIED", server_present=None),
        discovery_status="unverified",
    )
    snap = build_capability_snapshot(
        resolved_query_contract={"intent_family": "live_investigation", "required_capabilities": [CAPABILITY_MCP]},
        mcp_catalogs=catalogs,
        registered_action_kinds={},
    )
    row = snap.row_for(mcp_tool_capability_id("splunk_soc", "splunk_run_query"))
    assert row is not None
    assert row.availability == "unavailable"


def test_execution_off_verified_allowlisted_tool_is_available() -> None:
    # Execution flags are not inputs to the builder — verified + allowlisted ⇒ available.
    catalogs = _catalog(
        "splunk_soc",
        _entry("splunk_run_query", drift="APPROVED_AND_PRESENT", server_present=True, executable=False),
    )
    snap = build_capability_snapshot(
        resolved_query_contract={"intent_family": "live_investigation", "required_capabilities": [CAPABILITY_MCP]},
        mcp_catalogs=catalogs,
        registered_action_kinds={},
    )
    row = snap.row_for(mcp_tool_capability_id("splunk_soc", "splunk_run_query"))
    assert row is not None
    assert row.availability == "available"


def test_injected_extra_mcp_server_appears_without_planner_edits() -> None:
    catalogs = {
        **_catalog("splunk_soc", _entry("splunk_run_query", drift="APPROVED_AND_PRESENT", server_present=True)),
        **_catalog(
            "agilius",
            _entry("agilius_list_patches", drift="APPROVED_AND_PRESENT", server_present=True),
        ),
    }
    snap = build_capability_snapshot(
        resolved_query_contract={"intent_family": "guided_investigation", "required_capabilities": []},
        mcp_catalogs=catalogs,
        registered_action_kinds={},
    )
    assert snap.row_for(mcp_tool_capability_id("agilius", "agilius_list_patches")) is not None


def test_schema_has_no_executable_field() -> None:
    assert "executable" not in CapabilitySnapshot.model_fields
    assert "executable" not in CapabilityRow.model_fields
    with pytest.raises(ValidationError):
        CapabilityRow.model_validate(
            {
                "capability_id": "action:firewall_block",
                "capability_need": "recommended",
                "availability": "unavailable",
                "executable": True,
            }
        )


def test_needs_splunk_projects_required_without_grant() -> None:
    catalogs = _catalog(
        "splunk_soc",
        _entry("splunk_run_query", drift="DISCOVERY_UNVERIFIED", server_present=None),
    )
    snap = build_capability_snapshot(
        resolved_query_contract={
            "intent_family": "live_investigation",
            "required_capabilities": [CAPABILITY_SPL, CAPABILITY_MCP],
        },
        mcp_catalogs=catalogs,
        registered_action_kinds={},
    )
    row = snap.row_for(mcp_tool_capability_id("splunk_soc", "splunk_run_query"))
    assert row is not None
    assert row.capability_need == "required"
    assert row.availability == "unavailable"  # need ≠ grant


def test_flag_off_does_not_attach(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_capability_snapshot_enabled", False)
    state = maybe_attach_capability_snapshot(
        {"resolved_query_contract": {}},
        resolved_query_contract={"intent_family": "knowledge_recall"},
        mcp_catalogs={},
        registered_action_kinds={},
    )
    assert "capability_snapshot" not in state


def test_flag_on_attaches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_capability_snapshot_enabled", True)
    state = maybe_attach_capability_snapshot(
        {},
        resolved_query_contract={"intent_family": "knowledge_recall"},
        mcp_catalogs={},
        registered_action_kinds={"firewall_block": False, "email_send": False},
    )
    assert isinstance(state.get("capability_snapshot"), dict)
    assert state["capability_snapshot"]["schema_version"] == "capability_snapshot_v1"
