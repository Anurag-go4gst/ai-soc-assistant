"""Deterministic MCP specialist — redacted committed-plan readiness audit.

The specialist reads only the committed Evidence/Resource Plan, the redacted
MCP registry status, and the deterministic resource registry.  It never runs
discovery, selects a tool, calls a connector, or decides execution authority.
Candidate names are capability disclosures for an existing plan step only.
"""

from __future__ import annotations

from typing import Any

from app.connectors.mcp.registry import McpRegistryStatus, load_mcp_registry_status
from app.planner.planner_hierarchy import McpSpecialistReport, SpecialistProposal
from app.planner.resource_registry import ResourceDescriptor, ResourceRegistry, load_resource_registry

_MCP_PURPOSES = frozenset({"mcp_execution", "mcp_discovery"})
_EXECUTION_CAPABILITIES = frozenset({"execute_validated_spl", "event_search"})
_DISCOVERY_CAPABILITIES = frozenset(
    {
        "metadata_discovery",
        "index_context",
        "source_context",
        "readiness_probe",
        "knowledge_object_discovery",
        "identity_lookup",
    }
)


def build_mcp_audit_report(
    *,
    evidence_plan: dict[str, Any] | None,
    registry_status: McpRegistryStatus | None = None,
    resource_registry: ResourceRegistry | None = None,
    delegation_id: str = "del:mcp",
) -> McpSpecialistReport:
    """Return bounded MCP readiness metadata for the committed plan."""
    plan = evidence_plan if isinstance(evidence_plan, dict) else {}
    registry = registry_status or load_mcp_registry_status()
    resources = resource_registry or load_resource_registry()
    steps = _mcp_steps(plan)
    execution_steps = [step for step in steps if step.get("purpose") == "mcp_execution"]
    discovery_steps = [step for step in steps if step.get("purpose") == "mcp_discovery"]

    plan_needs_mcp = bool(plan.get("needs_mcp") or steps)
    plan_mcp_allowed = bool(plan.get("mcp_allowed"))
    discovery_allowed = bool(plan.get("discovery_allowed"))
    configured_servers = [server for server in registry.servers if server.configured]
    available_servers = [server for server in configured_servers if server.available]
    candidate_server_ids = (
        sorted({server.name for server in available_servers})[:16]
        if plan_needs_mcp
        else []
    )

    safe_discovered = {
        name
        for server in available_servers
        for name in server.discovered_tools_safe_names
    }
    blocked_discovered = {
        name
        for server in registry.servers
        for name in server.blocked_tools_safe_names
    }
    candidate_tool_names: list[str] = []
    blocked_requested = False
    for step in steps:
        resource_id = str(step.get("resource_id") or "")
        descriptor = resources.by_id(resource_id)
        if descriptor is None or descriptor.kind != "mcp_tool":
            continue
        tool_name = descriptor.resource_id.rsplit(":", 1)[-1]
        if (
            descriptor.availability == "blocked"
            or tool_name in blocked_discovered
            or not _capability_allowed(str(step.get("purpose") or ""), descriptor)
        ):
            blocked_requested = True
            continue
        if tool_name in safe_discovered:
            candidate_tool_names.append(tool_name)
    candidate_tool_names = sorted(set(candidate_tool_names))[:16]

    blockers: list[str] = []
    warnings: list[str] = []
    if execution_steps and not plan_mcp_allowed:
        blockers.append("mcp_not_allowed_by_plan")
    if plan_needs_mcp and not available_servers:
        blockers.append("mcp_registry_unavailable")
    if plan_needs_mcp and steps and not candidate_tool_names:
        blockers.append("no_safe_mcp_tool_candidate")
    if plan_needs_mcp and not steps:
        blockers.append("mcp_step_missing")
    if execution_steps and not registry.global_execution_enabled:
        blockers.append("mcp_global_execution_disabled")
    if discovery_steps and not discovery_allowed:
        blockers.append("mcp_discovery_not_allowed")
    if blocked_requested:
        warnings.append("blocked_tools_excluded")

    execution_posture = _execution_posture(
        plan_needs_mcp=plan_needs_mcp,
        plan_mcp_allowed=plan_mcp_allowed,
        execution_steps=execution_steps,
        discovery_steps=discovery_steps,
        available_servers=available_servers,
        candidate_tool_names=candidate_tool_names,
    )
    proposals = _fill_blank_proposals(steps, candidate_tool_names)

    mode = str(registry.mode or "").lower()
    registry_mode = mode if mode in {"mock", "registry"} else "unavailable"
    return McpSpecialistReport(
        delegation_id=delegation_id,
        decision_reason=f"mcp_{execution_posture}",
        authority="proposed_validated" if proposals else "advisory",
        plan_needs_mcp=plan_needs_mcp,
        plan_mcp_allowed=plan_mcp_allowed,
        discovery_allowed=discovery_allowed,
        planned_hop_count=len(steps),
        hop_count=len(steps),
        registry_mode=registry_mode,
        global_execution_enabled=bool(registry.global_execution_enabled),
        configured_server_count=len(configured_servers),
        available_server_count=len(available_servers),
        candidate_server_ids=candidate_server_ids,
        candidate_tool_names=candidate_tool_names,
        execution_posture=execution_posture,
        requires_execution_gate=bool(execution_steps),
        blockers=blockers,
        warnings=warnings,
        proposals=proposals,
    )


def _mcp_steps(evidence_plan: dict[str, Any]) -> list[dict[str, Any]]:
    resource_plan = evidence_plan.get("resource_plan")
    raw_steps = resource_plan.get("steps") if isinstance(resource_plan, dict) else []
    return [
        step
        for step in raw_steps or []
        if isinstance(step, dict) and str(step.get("purpose") or "") in _MCP_PURPOSES
    ]


def _capability_allowed(purpose: str, descriptor: ResourceDescriptor) -> bool:
    capabilities = set(descriptor.capabilities)
    if purpose == "mcp_execution":
        return bool(capabilities & _EXECUTION_CAPABILITIES)
    if purpose == "mcp_discovery":
        return descriptor.read_only and bool(capabilities & _DISCOVERY_CAPABILITIES)
    return False


def _execution_posture(
    *,
    plan_needs_mcp: bool,
    plan_mcp_allowed: bool,
    execution_steps: list[dict[str, Any]],
    discovery_steps: list[dict[str, Any]],
    available_servers: list[Any],
    candidate_tool_names: list[str],
) -> str:
    if not plan_needs_mcp:
        return "not_needed"
    if execution_steps and not plan_mcp_allowed:
        return "blocked_by_plan"
    if not available_servers or not candidate_tool_names:
        return "unavailable"
    if execution_steps:
        return "gate_required"
    if discovery_steps:
        return "discovery_only"
    return "unavailable"


def _fill_blank_proposals(
    steps: list[dict[str, Any]],
    candidate_tool_names: list[str],
) -> list[SpecialistProposal]:
    if not candidate_tool_names:
        return []
    proposals: list[SpecialistProposal] = []
    for step in steps:
        args = step.get("args_template")
        args = args if isinstance(args, dict) else {}
        fill: dict[str, Any] = {}
        if not args.get("candidate_tool_names"):
            fill["candidate_tool_names"] = list(candidate_tool_names)
        if not args.get("execution_intent"):
            fill["execution_intent"] = (
                "spl_search"
                if step.get("purpose") == "mcp_execution"
                else "metadata_discovery"
            )
        if not fill:
            continue
        proposals.append(
            SpecialistProposal(
                proposal_id=f"mp:{step.get('step_id') or step.get('purpose')}",
                purpose=str(step.get("purpose") or ""),
                resource_id=str(step.get("resource_id") or ""),
                args_template=fill,
                rationale="fill blank MCP readiness metadata on committed plan step",
            )
        )
    return proposals[:16]
