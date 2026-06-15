from __future__ import annotations

from app.api.routes_chat import _context_stage
from app.evidence.source_evidence import append_mcp_loop_source_evidence, mcp_loop_source_evidence

APPROVED_VALIDATION = {
    "approved": True,
    "normalized_spl": "search index=pgcil_soc earliest=-15m latest=now | stats count | head 10",
    "reject_reasons": [],
    "warnings": [],
    "policy_version": "spl-policy-v1",
}

EXECUTION_SKIPPED = {
    "status": "skipped",
    "block_reason": "mcp_execution_globally_disabled",
    "selected_mcp_server": "splunk_soc",
    "selected_mcp_tool": "splunk_run_query",
}

MCP_EVIDENCE = [
    {
        "tool": "splunk_get_info",
        "delivered": ["server_version", "readiness"],
        "outcome": "planned",
        "payload": {"read_only": True},
    },
    {
        "tool": "splunk_get_indexes",
        "delivered": ["index_list"],
        "outcome": "planned",
        "payload": {"read_only": True},
    },
]


def test_mcp_loop_source_evidence_maps_planned_hops() -> None:
    items = mcp_loop_source_evidence("trace-1", MCP_EVIDENCE)
    assert len(items) == 2
    assert items[0]["source_type"] == "mcp_discovery"
    assert items[0]["collection_status"] == "planned"
    assert items[0]["tool_name"] == "splunk_get_info"
    assert items[0]["plan_step_ref"] == "mcp"
    assert "discovery_hop_planned_only" in items[0]["warnings"]
    assert items[0]["preview_rows"][0]["produce_key"] == "server_version"
    assert items[0]["evidence_id"] != items[1]["evidence_id"]


def test_mcp_loop_skips_run_query_hop_rows() -> None:
    items = mcp_loop_source_evidence(
        "trace-2",
        [{"tool": "splunk_run_query", "delivered": ["events"], "outcome": "collected"}],
    )
    assert items == []


def test_context_stage_merges_mcp_evidence_into_source_evidence() -> None:
    evidence, context, _sufficiency = _context_stage(
        trace_id="trace-3",
        query="show failed admin logins",
        selected_skill="spl_generation",
        workflow_plan={"required_sources": ["mcp:splunk"]},
        spl_validation=APPROVED_VALIDATION,
        execution=EXECUTION_SKIPPED,
        mcp_evidence=MCP_EVIDENCE,
    )
    discovery = [item for item in evidence if item.get("source_type") == "mcp_discovery"]
    assert len(discovery) == 2
    discovery_ids = {item["evidence_id"] for item in discovery}
    assert discovery_ids.issubset(set(context["source_evidence_refs"]))
    summaries = context["tool_outputs_summary"]
    assert any(item["source_type"] == "mcp_discovery" for item in summaries)


def test_append_mcp_loop_is_noop_when_empty() -> None:
    base = [{"evidence_id": "ev_base", "source_type": "splunk_mcp"}]
    merged = append_mcp_loop_source_evidence(base, trace_id="trace-4", mcp_evidence=None)
    assert merged is base
