"""WS4c/d — Splunk MCP contract + adapter readiness (planning only; no live I/O).

Produces planned/blocked/fixture tool-call records and validates result envelopes.
Real network execution remains gated behind MCP_GLOBAL_EXECUTION_ENABLED and COE S5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.config import settings
from app.connectors.mcp.registry import load_mcp_registry_status
from app.connectors.mcp.splunk_result_adapter import sanitize_result_envelope
from app.connectors.mcp.splunk_result_envelope import SplunkResultEnvelope
from app.connectors.mcp.splunk_result_fixture import envelope_from_fixture_payload

SPLUNK_MCP_SERVER = "splunk"
ALLOWED_READ_TOOL = "splunk_run_query"
ALLOWED_READ_TOOL_ALIASES = frozenset(
    {ALLOWED_READ_TOOL, "run_splunk_query", "search_splunk", "splunk.search"}
)
SPLUNK_DISCOVERY_TOOLS = (
    "splunk_get_indexes",
    "splunk_get_metadata",
    "splunk_get_index_info",
    "splunk_get_knowledge_objects",
)
DISALLOWED_MUTATING_TOOLS = frozenset(
    {
        "create_kvstore_collection",
        "delete_kvstore_collection",
        "outputlookup",
        "sendemail",
        "splunk.admin",
        "splunk.write",
    }
)

McpToolCallKind = Literal["planned_tool_call", "blocked_tool_call", "fixture_tool_call"]
McpFailureMode = Literal[
    "tool_unavailable",
    "connector_not_configured",
    "validation_failed",
    "execution_disabled",
    "timeout",
    "empty_result",
    "partial_result",
    "schema_mismatch",
    "permission_denied",
    "unsafe_action_blocked",
    "rag_only_skip",
    "source_profile_missing",
    "no_catalog_mapping",
    "hil_required",
]


@dataclass(frozen=True)
class SplunkSearchInputs:
    search_query: str
    earliest_time: str
    latest_time: str
    max_results: int
    correlation_id: str | None = None


@dataclass(frozen=True)
class McpToolCallRecord:
    kind: McpToolCallKind
    server: str
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    block_reason: str | None = None
    failure_mode: McpFailureMode | None = None
    policy_checks: tuple[str, ...] = ()
    notes: str | None = None


def build_splunk_search_inputs(
    *,
    normalized_spl: str,
    trace_id: str | None = None,
    earliest_time: str | None = None,
    latest_time: str | None = None,
    max_results: int | None = None,
) -> SplunkSearchInputs:
    cap = int(max_results if max_results is not None else settings.spl_max_result_limit)
    return SplunkSearchInputs(
        search_query=str(normalized_spl).strip(),
        earliest_time=str(earliest_time or settings.spl_default_earliest),
        latest_time=str(latest_time or settings.spl_default_latest),
        max_results=min(max(cap, 1), int(settings.spl_max_result_limit)),
        correlation_id=trace_id,
    )


def plan_splunk_search_call(
    *,
    trace_id: str,
    spl_validation: dict[str, Any] | None,
    evidence_plan: dict[str, Any] | None = None,
    path_type: str | None = None,
    intent_family: str | None = None,
    use_case_id: str | None = None,
    signals: dict[str, Any] | None = None,
    source_profile_missing: bool = False,
    llm_tool_recommendation: dict[str, Any] | None = None,
) -> McpToolCallRecord:
    """Deterministic MCP planning — never performs network I/O."""
    _ = llm_tool_recommendation  # advisory only; never authorizes
    plan = evidence_plan or {}
    sig = signals or {}

    if sig.get("block_or_contain") or sig.get("explicit_run_spl") or path_type == "unsafe_blocked":
        return _blocked(
            "unsafe_action_blocked",
            "Enforcement or direct SPL execution request — MCP search blocked.",
            policy_checks=("unsafe_or_explicit_run_spl",),
        )

    if plan.get("answer_mode") == "rag_only" or path_type == "rag_only" or intent_family in {
        "sop_or_playbook",
        "policy_knowledge",
        "knowledge_only",
    }:
        return _blocked(
            "rag_only_skip",
            "RAG-only path — no Splunk MCP tool planned.",
            policy_checks=("rag_only",),
        )

    if source_profile_missing or _source_profile_required_missing(plan, use_case_id):
        return _blocked(
            "source_profile_missing",
            "Active source profile required before Splunk MCP search can be planned.",
            policy_checks=("source_profile_required",),
        )

    if not plan.get("needs_mcp") and not plan.get("mcp_allowed"):
        return _blocked(
            "no_catalog_mapping",
            "Evidence plan does not authorize MCP for this question.",
            policy_checks=("mcp_not_in_plan",),
        )

    validation = spl_validation if isinstance(spl_validation, dict) else {}
    if not validation.get("approved") or not validation.get("normalized_spl"):
        return _blocked(
            "validation_failed",
            "Validated normalized SPL required before Splunk MCP search.",
            policy_checks=("approved_normalized_spl_only",),
        )

    registry = load_mcp_registry_status()
    if not registry.global_execution_enabled:
        inputs = build_splunk_search_inputs(
            normalized_spl=str(validation["normalized_spl"]),
            trace_id=trace_id,
        )
        return McpToolCallRecord(
            kind="planned_tool_call",
            server=SPLUNK_MCP_SERVER,
            tool_name=ALLOWED_READ_TOOL,
            arguments=_arguments_dict(inputs),
            block_reason="mcp_global_execution_disabled",
            failure_mode="execution_disabled",
            policy_checks=(
                "mcp_execution_gate",
                "global_and_server_execution_flags",
                "approved_normalized_spl_only",
            ),
            notes="Planned splunk_run_query; execution remains blocked until gates open (S5).",
        )

    if not registry.configured:
        return _blocked("connector_not_configured", "Splunk MCP connector is not configured.")

    return McpToolCallRecord(
        kind="planned_tool_call",
        server=SPLUNK_MCP_SERVER,
        tool_name=ALLOWED_READ_TOOL,
        arguments=_arguments_dict(
            build_splunk_search_inputs(
                normalized_spl=str(validation["normalized_spl"]),
                trace_id=trace_id,
            )
        ),
        policy_checks=("mcp_execution_gate", "hil_and_coe_approval"),
        notes="Execution flags enabled — still requires gate + HIL before live call (S5).",
    )


def plan_splunk_discovery_calls(
    *,
    target_index: str | None = None,
    include_knowledge_objects: bool = True,
) -> list[McpToolCallRecord]:
    """Build deterministic discovery records only; never call an MCP connector."""
    registry = load_mcp_registry_status()
    execution_disabled = not registry.global_execution_enabled
    tool_names = ["splunk_get_indexes", "splunk_get_metadata"]
    if target_index:
        tool_names.append("splunk_get_index_info")
    if include_knowledge_objects:
        tool_names.append("splunk_get_knowledge_objects")

    records: list[McpToolCallRecord] = []
    for tool_name in tool_names:
        arguments = {"index": target_index} if target_index and tool_name != "splunk_get_indexes" else {}
        records.append(
            McpToolCallRecord(
                kind="planned_tool_call",
                server=SPLUNK_MCP_SERVER,
                tool_name=tool_name,
                arguments=arguments,
                block_reason=(
                    "mcp_global_execution_disabled"
                    if execution_disabled
                    else "discovery_planning_only"
                ),
                failure_mode="execution_disabled" if execution_disabled else None,
                policy_checks=("read_only_discovery", "mcp_execution_gate"),
                notes="Planned discovery only; analyst may run this checklist manually.",
            )
        )
    return records


def fixture_splunk_search_call(
    *,
    trace_id: str,
    normalized_spl: str,
    fixture_payload: dict[str, Any],
) -> tuple[McpToolCallRecord, SplunkResultEnvelope]:
    """Test/fixture path only — bounded deterministic rows."""
    inputs = build_splunk_search_inputs(normalized_spl=normalized_spl, trace_id=trace_id)
    record = McpToolCallRecord(
        kind="fixture_tool_call",
        server=SPLUNK_MCP_SERVER,
        tool_name=ALLOWED_READ_TOOL,
        arguments=_arguments_dict(inputs),
        policy_checks=("fixture_only", "approved_normalized_spl_only"),
        notes="Fixture MCP result — not a live Splunk read.",
    )
    envelope = sanitize_result_envelope(
        envelope_from_fixture_payload(fixture_payload, trace_id=trace_id, normalized_spl=normalized_spl)
    )
    return record, envelope


def validate_mcp_result_envelope(envelope: SplunkResultEnvelope) -> dict[str, Any]:
    """Classify envelope for answer/sufficiency paths."""
    if envelope.status == "blocked":
        return {
            "valid": False,
            "failure_mode": "permission_denied",
            "review_required": True,
            "honest_answer": "Splunk search was blocked by policy.",
            "evidence_tier": "metadata_only",
        }
    if envelope.status == "error":
        return {
            "valid": False,
            "failure_mode": "schema_mismatch" if not envelope.schema_confirmed else "tool_unavailable",
            "review_required": True,
            "honest_answer": "Splunk search failed — analyst review required.",
            "evidence_tier": "metadata_only",
        }
    if envelope.status == "timeout":
        return {
            "valid": False,
            "failure_mode": "timeout",
            "review_required": True,
            "honest_answer": "Splunk search timed out — partial or incomplete results.",
            "evidence_tier": "metadata_only",
        }
    if envelope.status == "empty" or envelope.row_count == 0:
        return {
            "valid": True,
            "failure_mode": "empty_result",
            "review_required": False,
            "honest_answer": "No matching rows returned for the governed search window.",
            "evidence_tier": "source_grounded" if envelope.origin != "fixture" else "fixture",
            "negative_result": True,
        }
    if envelope.truncated:
        return {
            "valid": True,
            "failure_mode": "partial_result",
            "review_required": True,
            "honest_answer": "Partial Splunk results returned — review truncated preview.",
            "evidence_tier": "source_grounded",
        }
    if not envelope.schema_confirmed:
        return {
            "valid": True,
            "failure_mode": "schema_mismatch",
            "review_required": True,
            "honest_answer": "Results returned but schema is unconfirmed — MITRE stays capped.",
            "evidence_tier": "metadata_only",
        }
    return {
        "valid": True,
        "failure_mode": None,
        "review_required": False,
        "honest_answer": None,
        "evidence_tier": "source_grounded",
    }


def is_allowed_read_tool(tool_name: str) -> bool:
    if tool_name == "splunk_run_saved_search":
        return settings.splunk_allow_run_saved_search
    return tool_name in ALLOWED_READ_TOOL_ALIASES


def is_disallowed_tool(tool_name: str) -> bool:
    lowered = tool_name.lower()
    if tool_name in DISALLOWED_MUTATING_TOOLS:
        return True
    return any(token in lowered for token in ("kvstore", "delete", "write", "admin", "saia"))


def splunk_search_tool_arguments(
    *,
    normalized_spl: str,
    trace_id: str | None = None,
    earliest_time: str | None = None,
    latest_time: str | None = None,
    max_results: int | None = None,
) -> dict[str, Any]:
    inputs = build_splunk_search_inputs(
        normalized_spl=normalized_spl,
        trace_id=trace_id,
        earliest_time=earliest_time,
        latest_time=latest_time,
        max_results=max_results,
    )
    return _arguments_dict(inputs)


def _arguments_dict(inputs: SplunkSearchInputs) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "search_query": inputs.search_query,
        "earliest_time": inputs.earliest_time,
        "latest_time": inputs.latest_time,
        "max_results": inputs.max_results,
    }
    if inputs.correlation_id:
        payload["correlation_id"] = inputs.correlation_id
        payload["request_id"] = inputs.correlation_id
    return payload


def _blocked(
    failure_mode: McpFailureMode,
    message: str,
    *,
    policy_checks: tuple[str, ...] = (),
) -> McpToolCallRecord:
    return McpToolCallRecord(
        kind="blocked_tool_call",
        server=SPLUNK_MCP_SERVER,
        tool_name=ALLOWED_READ_TOOL,
        block_reason=message,
        failure_mode=failure_mode,
        policy_checks=policy_checks,
    )


def _source_profile_required_missing(plan: dict[str, Any], use_case_id: str | None) -> bool:
    required = [str(item) for item in plan.get("required_evidence_keys") or [] if item]
    if "active_source_profile" in required or "source_profile" in required:
        return True
    if use_case_id and plan.get("enrichment_driven") and not plan.get("source_profile_bound"):
        return bool(plan.get("spl_template_status") == "active_source_profile_missing")
    return False


def splunk_saved_search_tool_arguments(
    *,
    saved_search_name: str,
    saved_search_app: str = "search",
    trace_id: str | None = None,
    earliest_time: str | None = None,
    latest_time: str | None = None,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    args: dict[str, Any] = {
        "saved_search_name": str(saved_search_name).strip(),
        "app": str(saved_search_app or "search").strip() or "search",
        "earliest_time": str(earliest_time or settings.spl_default_earliest),
        "latest_time": str(latest_time or settings.spl_default_latest),
    }
    if parameters:
        args["parameters"] = dict(parameters)
    if trace_id:
        args["trace_id"] = trace_id
    return args
