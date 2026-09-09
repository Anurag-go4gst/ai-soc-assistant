"""Controlled SOC lifecycle: external MCP + /chat RP path + P11 recording write."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from app.actions import email_adapter
from app.actions.email_adapter import RecordingEmailTransport
from app.chat.canonical_handoff_store import clear_all_handoffs_for_tests
from app.chat.session_store import clear_all_session_pins_for_tests
from app.config import settings
from app.connectors.mcp.discovery_snapshot import build_snapshot_from_handshake, get_discovery_snapshot_store
from app.connectors.mcp.splunk_mcp import SplunkMcpConnector
from app.graph.resource_planner_graph import run_chat_via_resource_planner_graph
from app.llm.sidecar_clients import SidecarInvocationResult
from app.schemas.requests import ChatRequest
from app.spl.source_profile_resolver import _explicit_profile_map

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from tools.controlled_mcp_server.server import ControlledMcpServer  # noqa: E402

LIFECYCLE_QUERY = (
    "An analyst reports that WINWORD.EXE spawned powershell.exe on workstation WS-14; "
    "minutes later a new scheduled task appeared and the same host contacted an unfamiliar "
    "external address. Investigate whether these events are related, correlate them by host, "
    "user, and time, and if the task is suspicious check persistence and subsequent activity. "
    "Give a conclusion and recommended next action, including notifying the SOC mailbox if "
    "evidence supports it."
)

DO_NOT_EXECUTE_QUERY = (
    LIFECYCLE_QUERY + " Recommend containment but do not execute any remediation."
)
_SOURCE_PROFILE_SLOTS = {
    "auth_index": "pgcil_soc",
    "windows_index": "pgcil_soc",
    "network_index": "pgcil_soc",
    "dns_index": "pgcil_soc",
    "endpoint_index": "pgcil_soc",
    "firewall_index": "pgcil_soc",
    "vpn_index": "pgcil_soc",
    "sysmon_index": "pgcil_soc",
    "notable_index": "pgcil_soc",
    "auth_sourcetype": "pgcil:auth",
    "windows_security_sourcetype": "WinEventLog:Security",
    "endpoint_process_sourcetype": "pgcil:edr",
    "network_traffic_sourcetype": "pgcil:network",
    "dns_sourcetype": "pgcil:dns",
    "firewall_sourcetype": "pgcil:firewall",
    "vpn_sourcetype": "pgcil:vpn",
}
_SEARCH_ALLOWLIST = (
    "splunk_run_query,splunk_get_info,splunk_get_indexes,splunk_get_index_info,"
    "splunk_get_metadata,splunk_get_user_info,splunk_get_knowledge_objects"
)

_HIL_FLAGS = {
    "ai_soc_curated_enrichment_activation_enabled": True,
    "ai_soc_investigation_plan_before_resource_plan_enabled": True,
    "ai_soc_capability_snapshot_enabled": True,
    "ai_soc_guided_composable_planning_enabled": True,
    "ai_soc_investigation_planner_enabled": False,
    "ai_soc_session_context_enabled": True,
    "ai_soc_resource_plan_execution_enabled": True,
    "langgraph_orchestration_enabled": True,
    "ai_soc_plan_delta_enabled": True,
    "ai_soc_investigation_outcome_v2_enabled": True,
    "ai_soc_remediation_planner_enabled": True,
}


def _arm_mcp(monkeypatch: pytest.MonkeyPatch, server: ControlledMcpServer) -> None:
    monkeypatch.setenv("MCP_MODE", "registry")
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", "false")
    monkeypatch.setenv("MCP_SERVERS", "splunk_soc")
    monkeypatch.setenv("MCP_DEFAULT_SERVER", "splunk_soc")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TYPE", "splunk")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TRANSPORT", "streamable_http")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_URL", server.base_url)
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_AUTH_MODE", "bearer")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_BEARER_TOKEN", server.token)
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TOOL_ALLOWLIST", _SEARCH_ALLOWLIST)
    monkeypatch.setattr(settings, "mcp_mode", "registry")
    monkeypatch.setattr(settings, "splunk_mcp_enabled", True)
    monkeypatch.setattr(settings, "splunk_mcp_base_url", server.base_url)
    monkeypatch.setattr(settings, "splunk_mcp_token", server.token)
    monkeypatch.setattr(settings, "mcp_global_execution_enabled", True)
    monkeypatch.setattr(settings, "mcp_discovery_enabled", True)
    monkeypatch.setattr(settings, "spl_allowed_indexes", "pgcil_soc")
    monkeypatch.setattr(
        settings,
        "spl_allowed_sourcetypes",
        "pgcil:auth,aws:cloudtrail,pgcil:edr,pgcil:dns,cisco:firepower,pgcil:sysmon",
    )
    monkeypatch.setenv("SPL_ALLOWED_INDEXES", "pgcil_soc")
    monkeypatch.setenv(
        "SPL_ALLOWED_SOURCETYPES",
        "pgcil:auth,aws:cloudtrail,pgcil:edr,pgcil:dns,cisco:firepower,pgcil:sysmon",
    )
    source_profile = json.dumps(_SOURCE_PROFILE_SLOTS)
    monkeypatch.setenv("AI_SOC_SOURCE_PROFILE_MAP", source_profile)
    monkeypatch.setattr(settings, "ai_soc_source_profile_map", source_profile)
    _explicit_profile_map.cache_clear()


def _arm_hil(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in _HIL_FLAGS.items():
        monkeypatch.setattr(settings, name, value)


def _discover(server: ControlledMcpServer) -> None:
    handshake = SplunkMcpConnector().handshake_initialize_and_list_tools()
    snapshot = build_snapshot_from_handshake(
        server_name="splunk_soc",
        handshake_result=handshake,
        source="operator_refresh",
    )
    assert snapshot.status == "ok", handshake
    get_discovery_snapshot_store().put(snapshot)


def _stub_reasoners(monkeypatch: pytest.MonkeyPatch, captured: dict) -> None:
    def fake_invoke(*, role: str, user_prompt: str, **_kwargs):
        if role == "plan_delta_reasoner":
            captured["plan_delta_prompt"] = user_prompt
            payload: dict = {}
            try:
                payload = json.loads(user_prompt)
            except json.JSONDecodeError:
                payload = {}
            skip = {"rag", "spl", "approved_sop_guidance", "rag:sop"}
            missing = [
                str(item)
                for item in (payload.get("missing_evidence_categories") or [])
                if str(item) and str(item) not in skip
            ]
            caps = [str(item) for item in (payload.get("allowed_read_only_capabilities") or [])]
            search_cap = next(
                (item for item in caps if "run_query" in item or "search_splunk" in item),
                caps[0] if caps else "",
            )
            admitted = payload.get("admitted_environment_evidence") or []
            captured.setdefault("plan_delta_attempts", []).append(
                {
                    "admitted_count": len(admitted if isinstance(admitted, list) else []),
                    "missing": list(missing),
                    "raw_missing": payload.get("missing_evidence_categories"),
                }
            )
            if not search_cap or not missing or not admitted:
                return SidecarInvocationResult(
                    raw_output=None,
                    timed_out=False,
                    answered_label="test_provider",
                )
            entities = payload.get("entities") if isinstance(payload.get("entities"), dict) else {}
            host_raw = entities.get("host") or entities.get("hostname") or "WS-14"
            if isinstance(host_raw, list):
                host_raw = host_raw[0] if host_raw else "WS-14"
            host = str(host_raw).strip() or "WS-14"
            indexes = ((payload.get("source_index_scope") or {}).get("indexes") or ["pgcil_soc"])
            index = str(indexes[0] if indexes else "pgcil_soc")
            delta_spl = (
                f'search index={index} sourcetype=pgcil:edr earliest=-24h latest=now host="{host}" '
                f"| stats count as event_count values(dest) as dest values(action) as action by host,user "
                f"| sort -event_count | head 100"
            )
            return SidecarInvocationResult(
                raw_output=json.dumps(
                    {
                        "evidence_need": missing[0],
                        "capability_id": search_cap,
                        "access_mode": "read_only",
                        "tool_arguments": {"query": delta_spl},
                    }
                ),
                timed_out=False,
                answered_label="test_provider",
            )
        if role == "remediation_planner":
            captured["remediation_prompt"] = user_prompt
            return SidecarInvocationResult(
                raw_output=None,
                timed_out=False,
                answered_label="test_provider",
            )
        return SidecarInvocationResult(raw_output=None, timed_out=False, answered_label=None)

    monkeypatch.setattr(
        "app.chat.investigation_plan_delta_reasoner.invoke_sidecar_role_with_metadata",
        fake_invoke,
    )
    monkeypatch.setattr(
        "app.chat.remediation_plan_reasoner.invoke_sidecar_role_with_metadata",
        fake_invoke,
    )


def _chat(message: str, **kwargs):
    return run_chat_via_resource_planner_graph(ChatRequest(message=message, **kwargs))


def _session_id(response) -> str | None:
    return response.session_context_status.session_id if response.session_context_status else None


def _confirm_execution_if_needed(response, query: str, *, max_rounds: int = 4):
    """Registry-mode searches still use the existing per-call confirmation HIL."""
    current = response
    for _ in range(max_rounds):
        execution = current.execution
        human = current.human_review
        status = execution.status if execution is not None else None
        if status != "requires_human_review":
            return current
        actions = list((human.allowed_actions if human is not None else None) or [])
        reason = str((human.reason if human is not None else "") or "")
        review_type = str((human.review_type if human is not None else "") or "")
        if (
            "confirm_execution" in actions
            or "analyst_confirmation_required" in reason
            or review_type == "spl_execution_confirmation"
        ):
            current = _chat(
                query,
                session_id=_session_id(current),
                execution_review_action="confirm",
                source_profile_slots=dict(_SOURCE_PROFILE_SLOTS),
            )
            continue
        return current
    return current


def _approve_investigation(first, query: str):
    approval = first.investigation_approval or {}
    second = _chat(
        query,
        session_id=_session_id(first),
        investigation_review_action="run",
        investigation_handoff_id=str(approval["handoff_id"]),
        investigation_handoff_version=int(approval["handoff_version"]),
        source_profile_slots=dict(_SOURCE_PROFILE_SLOTS),
    )
    return _confirm_execution_if_needed(second, query)


@pytest.fixture()
def recording(monkeypatch: pytest.MonkeyPatch) -> RecordingEmailTransport:
    transport = RecordingEmailTransport()
    email_adapter.set_transport_for_tests(transport)
    monkeypatch.setattr(settings, "ai_soc_action_email_enabled", True)
    monkeypatch.setenv("AI_SOC_ACTION_EMAIL_ALLOWLIST", "soc@example.com")
    monkeypatch.setenv("AI_SOC_ACTION_EMAIL_FROM", "ai-soc@example.com")
    monkeypatch.setenv("AI_SOC_ACTION_EMAIL_SMTP_HOST", "smtp.example.com")
    yield transport
    email_adapter.set_transport_for_tests(None)


@pytest.fixture(autouse=True)
def _reset_stores() -> None:
    clear_all_handoffs_for_tests()
    clear_all_session_pins_for_tests()
    yield
    clear_all_handoffs_for_tests()
    clear_all_session_pins_for_tests()


def test_controlled_full_lifecycle_read_reason_delta_outcome_p11(
    monkeypatch: pytest.MonkeyPatch,
    recording: RecordingEmailTransport,
) -> None:
    server = ControlledMcpServer(mode="full")
    server.start()
    captured: dict = {}
    try:
        _arm_mcp(monkeypatch, server)
        _arm_hil(monkeypatch)
        _discover(server)
        _stub_reasoners(monkeypatch, captured)

        first = _chat(LIFECYCLE_QUERY)
        approval = first.investigation_approval or {}
        assert approval.get("status") in {"awaiting_approval", "edited_revalidated"}, approval
        envelope = (approval.get("approved_envelope") or approval.get("validated_plan") or {})
        assert envelope or approval.get("handoff_id")
        plan_blob = json.dumps(approval.get("validated_plan") or first.validated_investigation_plan or {}).lower()
        visible = f"{plan_blob} {first.message or ''}".lower()
        assert "process" in visible or "script" in visible or "powershell" in visible or "scheduled" in visible

        second = _approve_investigation(first, LIFECYCLE_QUERY)
        payload = second.model_dump(mode="json")
        execution = payload.get("execution") or {}
        source = payload.get("source_evidence") or []
        collected = [
            item
            for item in source
            if isinstance(item, dict) and item.get("collection_status") == "collected"
            and item.get("source_type") in {"splunk_mcp", "mcp_discovery"}
        ]
        snapshot = payload.get("capability_snapshot") or first.model_dump(mode="json").get("capability_snapshot") or {}
        rows = snapshot.get("rows") if isinstance(snapshot, dict) else []
        envelope_caps = (
            (payload.get("approved_investigation_envelope") or {}).get("allowed_read_only_capabilities")
            or ((first.investigation_approval or {}).get("validated_plan") or {}).get("capability_bindings")
            or []
        )
        ep = payload.get("evidence_plan") or {}
        diag = {
            "exec_status": execution.get("status"),
            "block_reason": execution.get("block_reason"),
            "tool_reason": execution.get("tool_selection_reason"),
            "hr_reason": (payload.get("human_review") or {}).get("reason"),
            "hr_type": (payload.get("human_review") or {}).get("review_type"),
            "needs_mcp": ep.get("needs_mcp"),
            "mcp_allowed": ep.get("mcp_allowed"),
            "mcp_available": ep.get("mcp_available"),
            "spl_approved": (payload.get("spl_validation") or {}).get("approved"),
            "run_status": payload.get("investigation_run_status"),
            "source_types": [item.get("source_type") for item in source],
            "search_calls": server.search_calls,
            "inv2": (payload.get("investigation_approval") or {}).get("status"),
            "snapshot_ids": [
                row.get("capability_id") for row in rows if isinstance(row, dict)
            ][:8],
            "envelope_caps": envelope_caps if isinstance(envelope_caps, list) else envelope_caps,
            "plan_delta": (payload.get("plan_delta_decision") or {}).get("status"),
            "plan_delta_reason": (payload.get("plan_delta_decision") or {}).get("reason"),
            "missing_slots": (payload.get("spl_source_resolve") or {}).get("missing_slots"),
            "candidate": ((payload.get("candidate_spl") or {}).get("candidate_spl") or "")[:280],
            "reject": (payload.get("spl_validation") or {}).get("reject_reasons"),
            "skill": payload.get("selected_skill") or second.selected_skill,
            "spl_allowed": ep.get("spl_allowed"),
            "needs_spl": ep.get("needs_spl"),
            "cand_type": type(payload.get("candidate_spl")).__name__,
            "steps": [
                {
                    "id": step.get("step_id"),
                    "purpose": step.get("purpose"),
                    "status": step.get("status"),
                    "reason": step.get("status_reason"),
                    "resource": step.get("resource_id"),
                }
                for step in ((ep.get("resource_plan") or {}).get("steps") or [])
                if isinstance(step, dict)
            ],
            "pdt": payload.get("plan_dispatch_trace")
            or ((payload.get("control_plane_trace") or {}).get("plan_dispatch_trace")),
            "cpo": (
                (payload.get("canonical_planning_outcome") or {}).get("status")
                if isinstance(payload.get("canonical_planning_outcome"), dict)
                else None
            ),
            "nodes": [
                record.get("node")
                for record in ((payload.get("control_plane_trace") or {}).get("decision_log") or [])
                if isinstance(record, dict)
            ][:40],
            "path_type": (payload.get("planning_decision") or {}).get("path_type")
            if isinstance(payload.get("planning_decision"), dict)
            else None,
        }
        assert execution.get("status") == "executed" or collected, json.dumps(diag, default=str)[:4000]
        assert collected, source
        assert all(item.get("source_type") != "manual" or item.get("collection_status") != "collected" for item in collected)
        env_preview = json.dumps(collected)
        assert "powershell.exe" in env_preview or "WINWORD" in env_preview or "WS-14" in env_preview

        prompt = captured.get("plan_delta_prompt") or ""
        assert prompt, "PlanDelta reasoner must run after READ #1"
        assert "admitted_environment_evidence" in prompt
        prompt_payload = json.loads(prompt)
        admitted = prompt_payload.get("admitted_environment_evidence") or []
        assert admitted, prompt
        admitted_blob = " ".join(str(item) for item in admitted)
        assert "powershell.exe" in admitted_blob or "WS-14" in admitted_blob
        assert "rag_guidance" in prompt
        assert "compromised" not in prompt.lower() or "trust_class=environment" in prompt

        assert server.search_calls >= 2, json.dumps({"search_calls": server.search_calls, "run_status": payload.get("investigation_run_status")}, default=str)
        evidence_blob = json.dumps(source)
        assert "198.51.100.88" in evidence_blob or "scheduled_task_created" in evidence_blob
        assert len(collected) >= 2 or any(
            isinstance(item, dict) and item.get("result_count", 0) > 0
            for item in collected[1:]
        )

        outcome = payload.get("investigation_outcome") or {}
        assert outcome.get("investigation_status") == "completed", outcome
        assert outcome.get("disposition") == "suspicious", outcome
        missing = [str(item) for item in (outcome.get("missing_evidence") or [])]
        assert "rag" not in missing
        assert "spl" not in missing
        assert "approved_sop_guidance" not in missing
        assert "rag:sop" not in missing
        if collected:
            # User claims must not be the only evidence_refs.
            refs = list(outcome.get("evidence_refs") or [])
            assert refs
            assert all("analyst said" not in str(ref).lower() for ref in refs)

        visible = f"{payload.get('message') or ''} {payload.get('analyst_summary') or ''}"
        ar = payload.get("analyst_response") or {}
        if isinstance(ar, dict):
            visible = f"{visible} {ar.get('one_sentence_finding') or ''} {ar.get('direct_answer_summary') or ''}"
        visible_l = visible.lower()
        assert visible.strip(), "completed investigation must produce an analyst narrative"
        assert "generic guided" not in visible_l
        assert "powershell" in visible_l or "process" in visible_l
        assert "scheduled" in visible_l or "task" in visible_l or "persist" in visible_l
        assert "198.51.100.88" in visible or "dest" in visible_l
        assert "suspicious" in visible_l or outcome.get("disposition") == "suspicious"
        extra_after = [
            item
            for item in (captured.get("plan_delta_attempts") or [])
            if set(item.get("missing") or []).issubset({"rag", "spl", "approved_sop_guidance", "rag:sop"})
        ]
        assert extra_after == []

        rem = payload.get("remediation_approval") or {}
        assert rem.get("status") in {
            "offered",
            "awaiting_approval",
            "edited_revalidated",
            "approved",
        }, {"remediation_approval": rem, "outcome": outcome, "eligible_fields": {
            "status": outcome.get("investigation_status"),
            "disposition": outcome.get("disposition"),
            "evidence_refs": outcome.get("evidence_refs"),
            "remediation_offer_required": outcome.get("remediation_offer_required"),
        }}
        session_id = second.session_context_status.session_id if second.session_context_status else None
        if rem.get("status") == "offered":
            created = _chat(
                LIFECYCLE_QUERY,
                session_id=session_id,
                remediation_review_action="create",
            )
            rem = created.model_dump(mode="json").get("remediation_approval") or {}
            session_id = created.session_context_status.session_id if created.session_context_status else session_id
        if rem.get("status") in {"awaiting_approval", "edited_revalidated"}:
            approved = _chat(
                LIFECYCLE_QUERY,
                session_id=session_id,
                remediation_review_action="approve",
            )
            approved_payload = approved.model_dump(mode="json")
            envelope = (approved_payload.get("remediation_approval") or {}).get("approved_envelope") or {}
            assert envelope.get("envelope_version") or envelope.get("plan_fingerprint")
            action_ev = approved_payload.get("remediation_execution") or approved_payload.get("action_evidence") or {}
            assert recording.sent, {
                "remediation_execution": action_ev,
                "remediation_approval": approved_payload.get("remediation_approval"),
            }
            assert len(recording.sent) == 1
            replay = _chat(
                LIFECYCLE_QUERY,
                session_id=session_id,
                remediation_review_action="approve",
            )
            assert len(recording.sent) == 1
            replay_exec = replay.model_dump(mode="json").get("remediation_execution") or {}
            assert replay_exec.get("idempotent") or replay_exec.get("duplicate") or len(recording.sent) == 1
            receipt = action_ev if isinstance(action_ev, dict) else {}
            assert receipt.get("verified") not in {True, "verified"}
        production = Path(__file__).resolve().parents[1]
        production_py = "\n".join(
            path.read_text()
            for path in production.rglob("*.py")
            if "tests" not in path.parts
        )
        assert "if test_query" not in production_py
        assert "if golden_test" not in production_py
        assert "if localhost_mock" not in production_py
    finally:
        server.stop()


def test_insufficient_fixture_does_not_invent_correlation(monkeypatch: pytest.MonkeyPatch) -> None:
    server = ControlledMcpServer(mode="insufficient")
    server.start()
    captured: dict = {}
    try:
        _arm_mcp(monkeypatch, server)
        _arm_hil(monkeypatch)
        _discover(server)
        _stub_reasoners(monkeypatch, captured)
        first = _chat(LIFECYCLE_QUERY)
        if not first.investigation_approval:
            pytest.skip("investigation HIL did not arm for this query")
        second = _approve_investigation(first, LIFECYCLE_QUERY)
        payload = second.model_dump(mode="json")
        blob = json.dumps(payload.get("source_evidence") or [])
        assert "198.51.100.88" not in blob
        rem = payload.get("remediation_execution") or {}
        assert rem in ({}, None) or not rem.get("executed_any")
    finally:
        server.stop()


def test_recommend_but_do_not_execute_zero_write(
    monkeypatch: pytest.MonkeyPatch,
    recording: RecordingEmailTransport,
) -> None:
    server = ControlledMcpServer(mode="full")
    server.start()
    captured: dict = {}
    try:
        _arm_mcp(monkeypatch, server)
        _arm_hil(monkeypatch)
        _discover(server)
        _stub_reasoners(monkeypatch, captured)
        first = _chat(DO_NOT_EXECUTE_QUERY)
        if first.investigation_approval:
            second = _approve_investigation(first, DO_NOT_EXECUTE_QUERY)
        else:
            second = first
        assert recording.sent == []
        rem = second.model_dump(mode="json").get("remediation_execution") or {}
        assert rem in ({}, None) or not rem.get("executed_any")
    finally:
        server.stop()


def test_source_unavailable_is_honest(monkeypatch: pytest.MonkeyPatch) -> None:
    _arm_hil(monkeypatch)
    monkeypatch.setenv("MCP_MODE", "registry")
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "false")
    monkeypatch.setattr(settings, "mcp_mode", "registry")
    monkeypatch.setattr(settings, "mcp_global_execution_enabled", False)
    monkeypatch.setattr(settings, "splunk_mcp_enabled", False)
    first = _chat(LIFECYCLE_QUERY)
    assert first.investigation_approval is not None
    second = _approve_investigation(first, LIFECYCLE_QUERY)
    payload = second.model_dump(mode="json")
    execution = payload.get("execution") or {}
    assert execution.get("status") != "executed"
    collected = [
        item
        for item in (payload.get("source_evidence") or [])
        if isinstance(item, dict)
        and item.get("source_type") == "splunk_mcp"
        and item.get("collection_status") == "collected"
        and (item.get("preview_rows") or item.get("result_count"))
    ]
    assert collected == []
    visible = f"{second.message or ''} {second.note or ''}".lower()
    assert "unavailable" in visible or "disabled" in visible or execution.get("block_reason")


def test_edit_investigation_revalidates_without_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    server = ControlledMcpServer(mode="full")
    server.start()
    captured: dict = {}
    try:
        _arm_mcp(monkeypatch, server)
        _arm_hil(monkeypatch)
        _discover(server)
        _stub_reasoners(monkeypatch, captured)
        first = _chat(LIFECYCLE_QUERY)
        approval = first.investigation_approval or {}
        assert approval.get("status") in {"awaiting_approval", "edited_revalidated"}
        edited = _chat(
            LIFECYCLE_QUERY,
            session_id=_session_id(first),
            investigation_review_action="edit",
            investigation_handoff_id=str(approval["handoff_id"]),
            investigation_handoff_version=int(approval["handoff_version"]),
            investigation_plan_edits={
                "evidence_needed": ["process execution correlation on the reported workstation"]
            },
        )
        edited_approval = edited.investigation_approval or {}
        assert edited_approval.get("status") == "edited_revalidated"
        assert int(edited_approval.get("handoff_version") or 0) > int(approval["handoff_version"])
        assert edited.approved_investigation_envelope is None
        assert (edited.model_dump(mode="json").get("execution") or {}).get("status") != "executed"
        assert server.search_calls == 0
    finally:
        server.stop()


def test_cancel_investigation_zero_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    _arm_hil(monkeypatch)
    first = _chat(LIFECYCLE_QUERY)
    approval = first.investigation_approval
    assert approval is not None
    cancelled = _chat(
        LIFECYCLE_QUERY,
        session_id=_session_id(first),
        investigation_review_action="cancel",
        investigation_handoff_id=str(approval["handoff_id"]),
        investigation_handoff_version=int(approval["handoff_version"]),
    )
    payload = cancelled.model_dump(mode="json")
    assert (payload.get("execution") or {}).get("status") != "executed"
    assert (payload.get("remediation_execution") or {}).get("executed_any") in {None, False}
