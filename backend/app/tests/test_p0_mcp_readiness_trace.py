"""P0 — mcp_tool_readiness_v2 trace from planned capability bindings."""

from __future__ import annotations

from app.chat.control_plane_trace import _mcp_tool_readiness_trace
from app.chat.planned_mcp_call import enrich_capability_binding
from app.chat.contracts.investigation_plan import InvestigationCapabilityBinding


def _binding_dict(*, with_spl: bool = False) -> dict:
    binding = InvestigationCapabilityBinding(
        capability_id="mcp:splunk_soc:splunk_run_query",
        capability_need="required",
        availability="available",
        access_mode="read_only",
    )
    enriched = enrich_capability_binding(
        binding,
        normalized_spl=(
            "search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now "
            "| stats count by user | head 100"
            if with_spl
            else None
        ),
        trace_id="p0-readiness",
    )
    return enriched.model_dump(mode="json")


def test_mcp_tool_readiness_v2_schema_and_playbook_purpose() -> None:
    state = {
        "investigation_approval": {
            "validated_plan": {
                "capability_bindings": [_binding_dict(with_spl=False)],
            }
        },
        "workflow_plan": {"required_sources": ["splunk"]},
    }
    trace = _mcp_tool_readiness_trace(state, execution={})
    assert trace["schema_version"] == "mcp_tool_readiness_v2"
    tool = trace["tools"][0]
    assert tool["purpose"]
    assert tool["purpose"] != "required"
    assert "unresolved_arguments" in tool
    assert tool["unresolved_arguments"]
    assert "planned_arguments" not in tool
    assert tool["authorization_status"] in {
        "not_requested",
        "pending_exact_call_grant",
        "blocked_unresolved_arguments",
    }
    for flag in ("planned", "attempted", "executed", "succeeded", "failed", "skipped"):
        assert flag in tool


def test_planned_arguments_omitted_when_absent_present_when_bound() -> None:
    unresolved_state = {
        "investigation_approval": {
            "validated_plan": {"capability_bindings": [_binding_dict(with_spl=False)]}
        },
        "workflow_plan": {},
    }
    unresolved_tool = _mcp_tool_readiness_trace(unresolved_state, execution={})["tools"][0]
    assert "planned_arguments" not in unresolved_tool

    bound_state = {
        "investigation_approval": {
            "validated_plan": {"capability_bindings": [_binding_dict(with_spl=True)]}
        },
        "workflow_plan": {},
    }
    execution = {
        "selected_mcp_server": "splunk_soc",
        "selected_mcp_tool": "splunk_run_query",
        "status": "ok",
        "execution_eligible": True,
        "call_grant": {"fingerprint": "abc", "canonical_arguments_hash": "def"},
    }
    bound_tool = _mcp_tool_readiness_trace(bound_state, execution=execution)["tools"][0]
    assert isinstance(bound_tool.get("planned_arguments"), dict)
    assert bound_tool["authorization_status"] == "granted"
    assert bound_tool["attempted"] is True
    assert bound_tool["executed"] is True
    assert bound_tool["succeeded"] is True
