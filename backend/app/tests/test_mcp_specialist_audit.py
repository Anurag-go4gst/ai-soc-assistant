"""Deterministic, redacted MCP specialist plan-readiness audit."""

from __future__ import annotations

from app.connectors.mcp.registry import McpRegistryStatus, McpServerStatus
from app.planner.mcp_specialist import build_mcp_audit_report
from app.planner.planner_hierarchy import apply_specialist_reports, work_bundle_from_resource_plan
from app.planner.resource_plan import PlanStep, ResourcePlan
from app.planner.resource_registry import ResourceDescriptor, ResourceRegistry


def _server(
    *,
    available: bool = True,
    safe_tools: list[str] | None = None,
    blocked_tools: list[str] | None = None,
) -> McpServerStatus:
    safe_tools = safe_tools or ["splunk_run_query", "splunk_get_indexes"]
    blocked_tools = blocked_tools or ["create_kvstore_collection"]
    return McpServerStatus(
        name="splunk-primary",
        type="splunk",
        enabled=True,
        implemented=True,
        configured=True,
        available=available,
        transport="streamable_http",
        url_configured=True,
        command_configured=False,
        auth_mode="bearer",
        auth_configured=True,
        execution_enabled=False,
        discovered_tools_count=len(safe_tools),
        discovered_tools_safe_names=safe_tools,
        discovered_tools=[],
        blocked_tools_count=len(blocked_tools),
        blocked_tools_safe_names=blocked_tools,
        last_error="must_not_escape:token=secret-value",
        search_execution_allowed=False,
        saia_spl_generation_allowed=False,
        knowledge_object_discovery_allowed=True,
        list_tools_allowed=True,
    )


def _registry(*, available: bool = True) -> McpRegistryStatus:
    return McpRegistryStatus(
        mode="registry",
        default_server="splunk-primary",
        global_execution_enabled=False,
        servers=[_server(available=available)],
    )


def _resources() -> ResourceRegistry:
    return ResourceRegistry(
        schema_version=2,
        resources=[
            ResourceDescriptor(
                resource_id="mcp_tool:splunk_run_query",
                kind="mcp_tool",
                capabilities=["execute_validated_spl", "event_search"],
                availability="fixture_only",
                onboarding_status="fixture_tested",
                read_only=False,
            ),
            ResourceDescriptor(
                resource_id="mcp_tool:splunk_get_indexes",
                kind="mcp_tool",
                capabilities=["metadata_discovery", "index_context"],
                availability="fixture_only",
                onboarding_status="fixture_tested",
                read_only=True,
            ),
            ResourceDescriptor(
                resource_id="mcp_tool:create_kvstore_collection",
                kind="mcp_tool",
                capabilities=["kvstore_mutation"],
                availability="blocked",
                onboarding_status="declared",
                read_only=False,
            ),
        ],
    )


def _evidence_plan(
    *,
    purpose: str | None,
    resource_id: str = "mcp_tool:splunk_run_query",
    mcp_allowed: bool = False,
    discovery_allowed: bool = False,
    args_template: dict | None = None,
) -> dict:
    steps = []
    if purpose:
        steps.append(
            {
                "step_id": "mcp",
                "resource_id": resource_id,
                "purpose": purpose,
                "args_template": args_template or {},
                "policy_checks": ["mcp_execution_gate"],
                "status": "blocked_policy" if not mcp_allowed else "planned",
            }
        )
    return {
        "needs_mcp": bool(purpose),
        "mcp_allowed": mcp_allowed,
        "discovery_allowed": discovery_allowed,
        "resource_plan": {"plan_source": "deterministic", "steps": steps},
        "mcp_discovery_result": {"candidate_tool_names": ["attacker_supplied_tool"]},
    }


def test_not_needed_report_is_empty_and_bounded() -> None:
    report = build_mcp_audit_report(
        evidence_plan=_evidence_plan(purpose=None),
        registry_status=_registry(),
        resource_registry=_resources(),
    )

    assert report.execution_posture == "not_needed"
    assert report.planned_hop_count == report.hop_count == 0
    assert report.candidate_server_ids == []
    assert report.candidate_tool_names == []
    assert report.proposals == []


def test_discovery_only_report_uses_committed_metadata_step() -> None:
    report = build_mcp_audit_report(
        evidence_plan=_evidence_plan(
            purpose="mcp_discovery",
            resource_id="mcp_tool:splunk_get_indexes",
            discovery_allowed=True,
        ),
        registry_status=_registry(),
        resource_registry=_resources(),
    )

    assert report.execution_posture == "discovery_only"
    assert report.planned_hop_count == 1
    assert report.requires_execution_gate is False
    assert report.candidate_tool_names == ["splunk_get_indexes"]
    assert report.proposals[0].args_template == {
        "candidate_tool_names": ["splunk_get_indexes"],
        "execution_intent": "metadata_discovery",
    }


def test_genuine_execution_hop_is_preserved_and_gate_required() -> None:
    report = build_mcp_audit_report(
        evidence_plan=_evidence_plan(purpose="mcp_execution", mcp_allowed=True),
        registry_status=_registry(),
        resource_registry=_resources(),
    )

    assert report.plan_needs_mcp is True
    assert report.plan_mcp_allowed is True
    assert report.planned_hop_count == report.hop_count == 1
    assert report.execution_posture == "gate_required"
    assert report.requires_execution_gate is True
    assert report.candidate_tool_names == ["splunk_run_query"]
    assert "mcp_global_execution_disabled" in report.blockers
    assert "attacker_supplied_tool" not in report.candidate_tool_names


def test_plan_block_and_unavailable_postures_are_distinct() -> None:
    blocked = build_mcp_audit_report(
        evidence_plan=_evidence_plan(purpose="mcp_execution", mcp_allowed=False),
        registry_status=_registry(),
        resource_registry=_resources(),
    )
    unavailable = build_mcp_audit_report(
        evidence_plan=_evidence_plan(purpose="mcp_execution", mcp_allowed=True),
        registry_status=_registry(available=False),
        resource_registry=_resources(),
    )

    assert blocked.execution_posture == "blocked_by_plan"
    assert blocked.planned_hop_count == 1
    assert blocked.requires_execution_gate is True
    assert "mcp_not_allowed_by_plan" in blocked.blockers
    assert unavailable.execution_posture == "unavailable"
    assert "mcp_registry_unavailable" in unavailable.blockers


def test_blocked_tool_is_never_a_candidate() -> None:
    report = build_mcp_audit_report(
        evidence_plan=_evidence_plan(
            purpose="mcp_execution",
            resource_id="mcp_tool:create_kvstore_collection",
            mcp_allowed=True,
        ),
        registry_status=_registry(),
        resource_registry=_resources(),
    )

    assert report.candidate_tool_names == []
    assert "no_safe_mcp_tool_candidate" in report.blockers
    assert "blocked_tools_excluded" in report.warnings


def test_report_is_redacted_and_builder_performs_no_live_io(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.planner.mcp_specialist.load_mcp_registry_status",
        lambda: (_ for _ in ()).throw(AssertionError("registry loader called")),
    )
    monkeypatch.setattr(
        "app.planner.mcp_specialist.load_resource_registry",
        lambda: (_ for _ in ()).throw(AssertionError("resource loader called")),
    )

    report = build_mcp_audit_report(
        evidence_plan=_evidence_plan(purpose="mcp_execution", mcp_allowed=True),
        registry_status=_registry(),
        resource_registry=_resources(),
    )
    payload = report.model_dump_json()

    assert "secret-value" not in payload
    assert "bearer" not in payload
    assert "streamable_http" not in payload
    assert "url" not in payload
    assert "candidate_spl" not in payload
    assert "normalized_spl" not in payload


def test_fill_blank_proposal_merges_without_relaxing_block() -> None:
    evidence = _evidence_plan(purpose="mcp_execution", mcp_allowed=False)
    plan = ResourcePlan(
        plan_source="deterministic",
        steps=[PlanStep.model_validate(evidence["resource_plan"]["steps"][0])],
    )
    bundle = work_bundle_from_resource_plan(plan, bundle_id="bundle:mcp")
    report = build_mcp_audit_report(
        evidence_plan=evidence,
        registry_status=_registry(),
        resource_registry=_resources(),
    )

    merged = apply_specialist_reports(bundle, [report])
    task = merged.tasks[0]
    assert task.args_template == {
        "candidate_tool_names": ["splunk_run_query"],
        "execution_intent": "spl_search",
    }
    assert task.status == "blocked_policy"
    assert task.policy_checks == ["mcp_execution_gate"]
