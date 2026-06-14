from __future__ import annotations

from time import perf_counter
from typing import Any

from app.connectors.mcp import get_mcp_connector
from app.connectors.mcp.registry import load_mcp_registry_status
from app.connectors.mcp.splunk_result_adapter import adapt_mcp_search_payload, execution_preview_from_envelope
from app.config import settings
from app.connectors.mcp.splunk_mcp_readiness import splunk_search_tool_arguments
from app.connectors.telemetry import get_telemetry_connector
from app.orchestration.execution_confirmation import (
    build_execution_confirmation_review,
    resolve_execution_spl,
)
from app.orchestration.human_review import human_review, no_human_review
from app.orchestration.mcp_tool_selector import EXECUTION_ELIGIBLE_SKILLS, select_mcp_tool

RESULT_PREVIEW_CAP = 5


def _mock_success_requires_hil() -> bool:
    """Whether a successful mock execution must surface an analyst-review gate.

    A valid SPL and a successful mock run never imply autonomous execution. HIL
    is required by default; it is relaxed ONLY when the deployment is explicitly
    flagged as demo/lab AND the without-HIL allowance is enabled — two
    independent axes, so enabling a demo cannot silently disable HIL elsewhere.
    """
    relax = (
        settings.ai_soc_demo_or_lab_execution_mode
        and settings.ai_soc_allow_mock_execution_without_hil_in_demo
    )
    return settings.ai_soc_require_hil_for_mock_execution and not relax


def evaluate_mcp_execution(
    *,
    trace_id: str,
    selected_skill: str,
    workflow_plan: dict[str, Any],
    spl_validation: dict[str, Any] | None,
    precondition_evaluation: dict[str, Any] | None = None,
    requested_mcp_server: str | None = None,
    requested_mcp_tool: str | None = None,
    llm_tool_recommendation: dict[str, Any] | None = None,
    execution_review_action: str | None = None,
    analyst_provided_spl: str | None = None,
    pending_execution: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    telemetry = get_telemetry_connector()
    precondition_block_reason = _precondition_block_reason(precondition_evaluation)
    if precondition_block_reason:
        selection = {
            "execution_intent": "spl_search",
            "selected_mcp_server": None,
            "selected_mcp_tool": None,
            "tool_selection_status": "blocked_by_precondition_eval",
            "tool_selection_reason": precondition_block_reason,
        }
        review = _review(
            "precondition_review",
            precondition_block_reason,
            "soc_lead",
            ["fix_preconditions", "reject_execution"],
        )
        execution = _blocked_execution(selection, "requires_human_review", precondition_block_reason)
        execution["precondition_evaluation"] = precondition_evaluation
        telemetry.record_mcp_execution(
            trace_id,
            event_type="mcp_execution_blocked",
            reason=precondition_block_reason,
        )
        return execution, review

    registry = load_mcp_registry_status()
    _record_discovery(telemetry, trace_id, registry)

    selection = select_mcp_tool(
        trace_id=trace_id,
        selected_skill=selected_skill,
        workflow_plan=workflow_plan,
        execution_intent="spl_search",
        spl_validation=spl_validation,
        user_requested_mcp_server=requested_mcp_server,
        user_requested_mcp_tool=requested_mcp_tool,
        llm_tool_recommendation=llm_tool_recommendation,
        registry=registry,
    )
    telemetry.record_mcp_execution(trace_id, event_type="mcp_tool_selection", **_selection_event(selection))

    if selection["tool_selection_status"] != "selected":
        review = selection.get("human_review") or _review("tool_selection_review", selection["tool_selection_reason"])
        execution = _blocked_execution(selection, "requires_human_review", selection["tool_selection_reason"])
        telemetry.record_mcp_execution(trace_id, event_type="mcp_execution_blocked", reason=selection["tool_selection_reason"])
        telemetry.record_mcp_execution(trace_id, event_type="mcp_execution_requires_human_review", reason=selection["tool_selection_reason"])
        return execution, review

    review = _gate_review(
        selected_skill=selected_skill,
        spl_validation=spl_validation,
        selected_mcp_server=str(selection["selected_mcp_server"]),
        selected_mcp_tool=str(selection["selected_mcp_tool"]),
        registry=registry,
    )
    if review["required"]:
        execution = _blocked_execution(selection, "requires_human_review", review["reason"])
        telemetry.record_mcp_execution(trace_id, event_type="mcp_execution_blocked", reason=review["reason"])
        telemetry.record_mcp_execution(trace_id, event_type="mcp_execution_requires_human_review", reason=review["reason"])
        return execution, review

    execution_validation, confirmation_review = resolve_execution_spl(
        spl_validation=spl_validation or {},
        execution_review_action=execution_review_action,
        analyst_provided_spl=analyst_provided_spl,
        pending_execution=pending_execution,
    )
    if confirmation_review is not None:
        execution = _blocked_execution(selection, "requires_human_review", confirmation_review["reason"])
        telemetry.record_mcp_execution(trace_id, event_type="mcp_execution_requires_human_review", reason=confirmation_review["reason"])
        return execution, confirmation_review
    if execution_validation is None:
        normalized_spl = str(spl_validation["normalized_spl"])
        review = build_execution_confirmation_review(
            normalized_spl=normalized_spl,
            selected_mcp_tool=str(selection["selected_mcp_tool"]),
            selected_mcp_server=str(selection["selected_mcp_server"]),
        )
        execution = _blocked_execution(selection, "requires_human_review", review["reason"])
        execution["pending_execution_confirmation"] = {
            "normalized_spl": normalized_spl,
            "selected_mcp_server": selection["selected_mcp_server"],
            "selected_mcp_tool": selection["selected_mcp_tool"],
            "trace_id": trace_id,
            "selected_skill": selected_skill,
        }
        telemetry.record_mcp_execution(trace_id, event_type="mcp_execution_requires_human_review", reason=review["reason"])
        return execution, review

    normalized_spl = str(execution_validation["normalized_spl"])
    tool_arguments = splunk_search_tool_arguments(normalized_spl=normalized_spl, trace_id=trace_id)
    started = perf_counter()
    telemetry.record_mcp_execution(
        trace_id,
        event_type="mcp_execution_started",
        selected_mcp_server=selection["selected_mcp_server"],
        selected_mcp_tool=selection["selected_mcp_tool"],
    )
    try:
        result = get_mcp_connector().call_tool(
            str(selection["selected_mcp_tool"]),
            tool_arguments,
            server_name=str(selection["selected_mcp_server"]),
        )
    except NotImplementedError:
        review = _review("admin_action_required", "real_mcp_adapter_not_implemented", "platform_admin", ["configure_connector", "reject_execution"])
        execution = _blocked_execution(selection, "requires_human_review", review["reason"])
        telemetry.record_mcp_execution(trace_id, event_type="mcp_execution_failed", reason=review["reason"])
        return execution, review
    except Exception as exc:  # noqa: BLE001 - execution gate must fail closed.
        review = _review("admin_action_required", "mcp_execution_failed", "platform_admin", ["configure_connector", "reject_execution"])
        execution = _blocked_execution(selection, "failed", f"mcp_execution_failed:{type(exc).__name__}")
        telemetry.record_mcp_execution(trace_id, event_type="mcp_execution_failed", reason=type(exc).__name__)
        return execution, review

    duration_ms = int((perf_counter() - started) * 1000)
    # A.10 honest outcomes: a live job can fail / time out / be denied / return a
    # bad envelope. Empty (status ok, 0 rows) is NOT a failure — it falls through
    # to the executed/negative-result path below.
    result_status = str(result.get("status") or "ok").strip().lower()
    if result_status not in {"ok", "completed", "success"}:
        outcome_review, exec_status = _classify_failed_call(result_status, result)
        execution = _blocked_execution(selection, exec_status, str(result.get("error") or result_status))
        telemetry.record_mcp_execution(trace_id, event_type="mcp_execution_failed", reason=result_status)
        return execution, outcome_review
    # _gate_review guarantees the registry success path is reached only when a
    # live Splunk endpoint is configured, so registry == a real run. Use the
    # real adapter and live provenance; mock keeps mock provenance.
    live_run = registry.mode == "registry"
    envelope = adapt_mcp_search_payload(
        result,
        mcp_mode="splunk_mcp" if live_run else registry.mode,
        trace_id=trace_id,
        normalized_spl=normalized_spl,
        duration_ms=duration_ms,
    )
    result_count, results_preview = execution_preview_from_envelope(
        envelope,
        preview_cap=RESULT_PREVIEW_CAP,
    )
    execution = {
        "status": "executed",
        "execution_intent": "spl_search",
        "selected_mcp_server": selection["selected_mcp_server"],
        "selected_mcp_tool": selection["selected_mcp_tool"],
        "tool_selection_status": selection["tool_selection_status"],
        "tool_selection_reason": selection["tool_selection_reason"],
        "executed_spl": normalized_spl,
        "result_count": result_count,
        "results_preview": results_preview,
        "splunk_result_envelope": envelope.to_dict(),
        "block_reason": None,
        "duration_ms": duration_ms,
        "evidence_source": "live" if live_run else "mock",
        "execution_status_label": "executed" if live_run else None,
    }
    telemetry.record_mcp_execution(trace_id, event_type="mcp_execution_completed", result_count=execution["result_count"], duration_ms=duration_ms)
    if live_run:
        # Live search already passed the per-call confirmation gate (B4) before
        # it ran; the real results are reviewed in the analyst answer, not via a
        # mock-evidence gate.
        review = no_human_review()
        review["safe_message_for_user"] = "Live Splunk search executed; results are reviewed in the analyst answer."
        return execution, review

    requires_hil = _mock_success_requires_hil()
    execution["execution_status_label"] = "review_required" if requires_hil else "mock_executed"
    if requires_hil:
        review = human_review(
            "mock_evidence_review",
            "mock_execution_requires_analyst_review",
            "analyst",
            ["review_mock_evidence", "approve_mock_evidence", "reject_execution"],
            "Mock evidence was generated and must be reviewed by an analyst before it informs any decision.",
        )
        telemetry.record_mcp_execution(
            trace_id,
            event_type="mcp_execution_requires_human_review",
            reason="mock_execution_requires_analyst_review",
        )
        return execution, review
    review = no_human_review()
    review["safe_message_for_user"] = "Mock execution completed in demo/lab mode; results are synthetic, not live evidence."
    return execution, review


def _record_discovery(telemetry: Any, trace_id: str, registry: Any) -> None:
    telemetry.record_mcp_execution(trace_id, event_type="mcp_tool_discovery_started")
    try:
        telemetry.record_mcp_execution(
            trace_id,
            event_type="mcp_tool_discovery_completed",
            server_count=len(registry.servers),
            discovered_tools_count=sum(server.discovered_tools_count for server in registry.servers),
            blocked_tools_count=sum(server.blocked_tools_count for server in registry.servers),
        )
    except Exception as exc:  # noqa: BLE001
        telemetry.record_mcp_execution(trace_id, event_type="mcp_tool_discovery_failed", reason=type(exc).__name__)


def _precondition_block_reason(precondition_evaluation: dict[str, Any] | None) -> str | None:
    if not isinstance(precondition_evaluation, dict):
        return None
    if precondition_evaluation.get("evaluation_skipped") is True:
        return None
    failed = precondition_evaluation.get("preconditions_failed")
    if isinstance(failed, list) and failed:
        return "precondition_eval_failed"
    route_status = precondition_evaluation.get("route_status")
    if isinstance(route_status, str) and route_status not in {"route_ready", "ready"}:
        return "precondition_eval_failed"
    return None


def _gate_review(
    *,
    selected_skill: str,
    spl_validation: dict[str, Any] | None,
    selected_mcp_server: str,
    selected_mcp_tool: str,
    registry: Any,
) -> dict[str, Any]:
    if selected_skill not in EXECUTION_ELIGIBLE_SKILLS:
        return _review("tool_selection_review", "skill_not_execution_eligible")
    if not spl_validation or spl_validation.get("approved") is not True:
        return _review("spl_revision", "spl_validation_failed", "analyst", ["regenerate_spl", "edit_spl", "reject_execution"])
    if spl_validation.get("normalized_spl") is None:
        return _review("spl_revision", "normalized_spl_null", "analyst", ["regenerate_spl", "edit_spl", "reject_execution"])
    if not registry.global_execution_enabled:
        return _review("execution_approval", "mcp_global_execution_disabled", "soc_lead", ["approve_execution_after_policy_check", "reject_execution"])
    server = next((item for item in registry.servers if item.name == selected_mcp_server), None)
    if server is None:
        return _review("connector_configuration", "mcp_server_unavailable", "platform_admin", ["configure_connector", "reject_execution"])
    if not server.execution_enabled:
        return _review("execution_approval", "mcp_server_execution_disabled", "soc_lead", ["approve_execution_after_policy_check", "reject_execution"])
    if not server.available:
        return _review("connector_configuration", "mcp_server_unavailable", "platform_admin", ["configure_connector", "reject_execution"])
    tool = next((item for item in server.discovered_tools if item.get("name") == selected_mcp_tool), None)
    if tool is None:
        return _review("tool_selection_review", "selected_tool_not_found")
    if tool.get("blocked"):
        return _review("policy_exception_request", tool.get("blocked_reason") or "selected_tool_blocked", "security_admin", ["request_policy_exception", "reject_execution"])
    if selected_mcp_tool == "splunk_run_saved_search" and not getattr(server, "search_execution_allowed", False):
        return _review("execution_approval", "saved_search_execution_disabled", "soc_lead", ["approve_execution_after_policy_check", "reject_execution"])
    if tool.get("capability") != "spl_search":
        return _review("tool_selection_review", "selected_tool_not_spl_search")
    if registry.mode not in {"mock", "registry"}:
        return _review("admin_action_required", "real_mcp_adapter_not_implemented", "platform_admin", ["configure_connector", "reject_execution"])
    # Live (registry) search needs a configured Splunk MCP endpoint + token. The
    # adapter is implemented (Step 3); "schema_confirmed" is operator doc
    # sign-off, not a runtime flag. Until URL/token are set, fail closed.
    if registry.mode == "registry" and not (
        settings.splunk_mcp_enabled and settings.splunk_mcp_base_url.strip() and settings.splunk_mcp_token.strip()
    ):
        return _review("connector_configuration", "splunk_mcp_not_configured", "platform_admin", ["configure_connector", "reject_execution"])
    return no_human_review()


def _classify_failed_call(result_status: str, result: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Map a non-ok live call payload to (review, execution_status)."""
    if result_status in {"denied", "permission_denied", "blocked", "forbidden"}:
        return (
            _review("policy_exception_request", str(result.get("error") or "permission_denied"), "security_admin", ["request_policy_exception", "reject_execution"]),
            "blocked",
        )
    if result_status == "timeout":
        return (
            _review("admin_action_required", "mcp_search_timed_out", "platform_admin", ["configure_connector", "reject_execution"]),
            "failed",
        )
    if result_status == "schema_invalid":
        return (
            _review("admin_action_required", "mcp_result_schema_invalid", "platform_admin", ["configure_connector", "reject_execution"]),
            "failed",
        )
    return (
        _review("admin_action_required", "mcp_execution_failed", "platform_admin", ["configure_connector", "reject_execution"]),
        "failed",
    )


def _blocked_execution(selection: dict[str, Any], status: str, reason: str) -> dict[str, Any]:
    return {
        "status": status,
        "execution_intent": selection["execution_intent"],
        "selected_mcp_server": selection.get("selected_mcp_server"),
        "selected_mcp_tool": selection.get("selected_mcp_tool"),
        "tool_selection_status": selection["tool_selection_status"],
        "tool_selection_reason": selection["tool_selection_reason"],
        "executed_spl": None,
        "result_count": 0,
        "results_preview": [],
        "block_reason": reason,
        "duration_ms": 0,
        "evidence_source": "unavailable",
        "execution_status_label": "not_executed",
    }


def _review(
    review_type: str,
    reason: str,
    reviewer_role: str = "soc_lead",
    allowed_actions: list[str] | None = None,
) -> dict[str, Any]:
    return human_review(
        review_type,
        reason,
        reviewer_role,
        allowed_actions or ["choose_different_mcp_tool", "reject_execution"],
        "Execution cannot safely proceed until this item is reviewed.",
    )


def _selection_event(selection: dict[str, Any]) -> dict[str, Any]:
    return {
        "selected_mcp_server": selection.get("selected_mcp_server"),
        "selected_mcp_tool": selection.get("selected_mcp_tool"),
        "execution_intent": selection.get("execution_intent"),
        "tool_selection_status": selection.get("tool_selection_status"),
        "tool_selection_reason": selection.get("tool_selection_reason"),
        "blocked_reason": selection.get("blocked_reason"),
    }
