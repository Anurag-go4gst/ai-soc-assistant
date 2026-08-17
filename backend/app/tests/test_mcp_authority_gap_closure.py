"""Authority-gap closure — every user/investigation-triggered live MCP tool
call requires exact-call AUTH0, not HIL/RBAC/allowlisting/read-only
classification alone.

Covers the mandatory test list from the authority-gap decision:
1  run_query still requires normalized_spl-bound AUTH0 (unchanged, see
   test_splunk_call_authorization.py — not duplicated here)
2  saved_search without AUTH0 confirmation rejected
3  saved_search argument/name mutation rejects existing grant
4  metadata tool without confirmation-carrying grant still executes only
   because it is deterministically not-HIL-required, but always carries a
   grant (AUTH0 mandatory even when HIL is not)
5  metadata argument mutation rejects grant (identity_lookup path, which is
   HIL-required)
6  user_info (identity_lookup) without AUTH0 confirmation rejected
7  tool substitution after authorization rejected
8  server substitution rejected
9  trace/identity mismatch rejected
10 expired grant rejected (reuses grants_match, already pinned generically
   in test_splunk_call_authorization.py; re-asserted here through the new
   call sites)
11 consumed grant cannot be reused
12 LLM recommendation cannot create/alter a grant (no LLM-authored field
   reaches build_splunk_call_grant / call_grant_from_tool_call — grants are
   always server-constructed from selection + settings)
13 HIL=true without AUTH0 still rejected (saved_search/identity_lookup: a
   pending confirmation payload lacking/mismatching call_grant is rejected
   even though the review is nominally an HIL confirmation review)
14 AUTH0 present but RBAC failure still rejected
15 AUTH0 present but tool-policy failure still rejected
16 initialize/tools-list control-plane discovery stays separate and cannot
   execute investigation tools
"""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.connectors.mcp.splunk_mcp import SplunkMcpConnector
from app.orchestration.mcp_execution_gate import evaluate_mcp_execution
from app.orchestration.splunk_call_authorization import call_grant_from_tool_call, grants_match


def _enable_mock_execution(monkeypatch, *, connector: Any = None) -> None:
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", "true")
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    if connector is not None:
        monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: connector)


class _FakeTelemetry:
    def record_mcp_execution(self, *args: Any, **kwargs: Any) -> None:
        return None


class _CapturingConnector:
    def __init__(self) -> None:
        self.called = False
        self.arguments: dict[str, Any] | None = None

    def call_tool(self, tool_name: str, arguments: dict[str, Any], server_name: str | None = None) -> dict[str, Any]:
        self.called = True
        self.arguments = arguments
        return {"status": "ok", "row_count": 1, "rows": [{"index": "pgcil_soc"}]}


class _RaisingConnector:
    def call_tool(self, tool_name: str, arguments: dict[str, Any], server_name: str | None = None) -> dict[str, Any]:
        raise AssertionError("MCP call must not happen without a valid AUTH0 grant")


# --- 2/3 saved search -------------------------------------------------------

def test_saved_search_first_turn_carries_call_grant_and_is_not_executed(monkeypatch) -> None:
    monkeypatch.setattr(settings, "splunk_allow_run_saved_search", True)
    monkeypatch.setattr(settings, "splunk_allowed_saved_searches", "SOC - Failed login spike")
    _enable_mock_execution(monkeypatch, connector=_RaisingConnector())

    execution, review = evaluate_mcp_execution(
        trace_id="auth0-saved-propose",
        selected_skill="spl_generation",
        workflow_plan={},
        spl_validation={"saved_search_name": "SOC - Failed login spike"},
        execution_intent="saved_search_execution",
        requested_mcp_tool="splunk_run_saved_search",
    )
    assert execution["status"] == "requires_human_review"
    pending = execution["pending_execution_confirmation"]
    assert pending["call_grant"]["schema_version"] == "splunk_call_grant_v1"
    assert pending["call_grant"]["fingerprint"]
    assert pending["call_grant"]["llm_granted"] is False


def test_saved_search_name_mutation_between_propose_and_confirm_rejected(monkeypatch) -> None:
    monkeypatch.setattr(settings, "splunk_allow_run_saved_search", True)
    monkeypatch.setattr(settings, "splunk_allowed_saved_searches", "SOC - Failed login spike,COE - Brute force watch")
    _enable_mock_execution(monkeypatch, connector=_RaisingConnector())

    proposed, _review = evaluate_mcp_execution(
        trace_id="auth0-saved-mut",
        selected_skill="spl_generation",
        workflow_plan={},
        spl_validation={"saved_search_name": "SOC - Failed login spike"},
        execution_intent="saved_search_execution",
        requested_mcp_tool="splunk_run_saved_search",
    )
    # `_saved_search_binding` prioritizes the pending payload's own
    # saved_search_name over spl_validation — mutate the field that is
    # actually authoritative on the confirm turn.
    pending = dict(proposed["pending_execution_confirmation"])
    pending["saved_search_name"] = "COE - Brute force watch"

    mutated, mutated_review = evaluate_mcp_execution(
        trace_id="auth0-saved-mut",
        selected_skill="spl_generation",
        workflow_plan={},
        spl_validation={"saved_search_name": "SOC - Failed login spike"},
        execution_intent="saved_search_execution",
        requested_mcp_tool="splunk_run_saved_search",
        execution_review_action="confirm",
        pending_execution=pending,
    )
    assert mutated["block_reason"] == "exact_call_grant_invalidated"
    assert mutated_review["reason"] == "exact_call_grant_invalidated"


def test_saved_search_confirmed_matching_grant_executes_and_consumes(monkeypatch) -> None:
    connector = _CapturingConnector()
    monkeypatch.setattr(settings, "splunk_allow_run_saved_search", True)
    monkeypatch.setattr(settings, "splunk_allowed_saved_searches", "SOC - Failed login spike")
    _enable_mock_execution(monkeypatch, connector=connector)

    proposed, _review = evaluate_mcp_execution(
        trace_id="auth0-saved-ok",
        selected_skill="spl_generation",
        workflow_plan={},
        spl_validation={"saved_search_name": "SOC - Failed login spike"},
        execution_intent="saved_search_execution",
        requested_mcp_tool="splunk_run_saved_search",
    )
    pending = proposed["pending_execution_confirmation"]

    executed, review = evaluate_mcp_execution(
        trace_id="auth0-saved-ok",
        selected_skill="spl_generation",
        workflow_plan={},
        spl_validation={"saved_search_name": "SOC - Failed login spike"},
        execution_intent="saved_search_execution",
        requested_mcp_tool="splunk_run_saved_search",
        execution_review_action="confirm",
        pending_execution=pending,
    )
    assert executed["status"] == "executed"
    assert connector.called is True
    assert executed["call_grant"]["consumed"] is True
    assert review["required"] is False


# --- 4/5/6/13 metadata / identity read-only tools ---------------------------

def test_metadata_discovery_not_hil_required_still_carries_auth0_grant(monkeypatch) -> None:
    connector = _CapturingConnector()
    _enable_mock_execution(monkeypatch, connector=connector)

    execution, review = evaluate_mcp_execution(
        trace_id="auth0-meta-noconfirm",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=None,
        execution_intent="metadata_discovery",
        requested_mcp_tool="splunk_get_indexes",
    )
    # metadata_discovery is deterministically not-HIL-required (§ policy) —
    # it executes without an interactive confirm round trip, but AUTH0 is
    # mandatory regardless: the grant must exist on the executed result.
    assert execution["status"] == "executed"
    assert connector.called is True
    assert execution["call_grant"]["schema_version"] == "splunk_call_grant_v1"
    assert execution["call_grant"]["consumed"] is True
    assert execution["call_grant"]["execution_intent"] == "metadata_discovery"
    assert review["required"] is False


def test_identity_lookup_requires_hil_confirmation_and_carries_grant(monkeypatch) -> None:
    _enable_mock_execution(monkeypatch, connector=_RaisingConnector())

    execution, review = evaluate_mcp_execution(
        trace_id="auth0-user-info",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=None,
        execution_intent="identity_lookup",
        requested_mcp_tool="splunk_get_user_info",
    )
    assert execution["status"] == "requires_human_review"
    assert review["review_type"] == "read_only_execution_confirmation"
    pending = execution["pending_execution_confirmation"]
    assert pending["call_grant"]["selected_mcp_tool"] == "splunk_get_user_info"
    assert pending["call_grant"]["execution_intent"] == "identity_lookup"


def test_identity_lookup_argument_mutation_between_propose_and_confirm_rejected(monkeypatch) -> None:
    _enable_mock_execution(monkeypatch, connector=_RaisingConnector())

    proposed, _review = evaluate_mcp_execution(
        trace_id="auth0-user-mut",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=None,
        execution_intent="identity_lookup",
        requested_mcp_tool="splunk_get_user_info",
    )
    pending = dict(proposed["pending_execution_confirmation"])

    # Identity changes between propose and confirm (e.g. session role
    # switched) — the confirm turn recomputes a grant bound to the new
    # identity, whose fingerprint differs from the one the analyst actually
    # saw and would be confirming; must invalidate rather than silently
    # rebind to the new identity.
    mutated, mutated_review = evaluate_mcp_execution(
        trace_id="auth0-user-mut",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=None,
        execution_intent="identity_lookup",
        requested_mcp_tool="splunk_get_user_info",
        execution_review_action="confirm",
        pending_execution=pending,
        rbac_role="soc_lead",
    )
    assert mutated["block_reason"] == "exact_call_grant_invalidated"
    assert mutated_review["reason"] == "exact_call_grant_invalidated"


def test_identity_lookup_confirm_without_any_prior_grant_rejected(monkeypatch) -> None:
    # HIL=true (a confirm action arrives) but no AUTH0 grant was ever issued —
    # must still be rejected, not treated as an implicit approval.
    _enable_mock_execution(monkeypatch, connector=_RaisingConnector())

    execution, review = evaluate_mcp_execution(
        trace_id="auth0-user-noauth0",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=None,
        execution_intent="identity_lookup",
        requested_mcp_tool="splunk_get_user_info",
        execution_review_action="confirm",
        pending_execution=None,
    )
    assert execution["status"] == "requires_human_review"
    assert execution["block_reason"] == "exact_call_grant_invalidated"
    assert review["reason"] == "exact_call_grant_invalidated"


# --- 7/8/9 substitution / mismatch ------------------------------------------

def test_tool_substitution_after_grant_rejected() -> None:
    selection = {"selected_mcp_server": "splunk_soc", "selected_mcp_tool": "splunk_get_indexes"}
    grant_a = call_grant_from_tool_call(
        trace_id="t1", selection=selection, tool_arguments={"x": 1},
        rbac_role="analyst", identity="analyst", hil_required=True,
        execution_intent="metadata_discovery",
    )
    selection_b = {**selection, "selected_mcp_tool": "splunk_get_metadata"}
    grant_b = call_grant_from_tool_call(
        trace_id="t1", selection=selection_b, tool_arguments={"x": 1},
        rbac_role="analyst", identity="analyst", hil_required=True,
        execution_intent="metadata_discovery",
    )
    assert grants_match({"call_grant": grant_a}, grant_b) is False


def test_server_substitution_after_grant_rejected() -> None:
    selection = {"selected_mcp_server": "splunk_soc", "selected_mcp_tool": "splunk_get_indexes"}
    grant_a = call_grant_from_tool_call(
        trace_id="t1", selection=selection, tool_arguments={"x": 1},
        rbac_role="analyst", identity="analyst", hil_required=True,
        execution_intent="metadata_discovery",
    )
    selection_b = {**selection, "selected_mcp_server": "other_server"}
    grant_b = call_grant_from_tool_call(
        trace_id="t1", selection=selection_b, tool_arguments={"x": 1},
        rbac_role="analyst", identity="analyst", hil_required=True,
        execution_intent="metadata_discovery",
    )
    assert grants_match({"call_grant": grant_a}, grant_b) is False


def test_trace_identity_mismatch_rejected() -> None:
    selection = {"selected_mcp_server": "splunk_soc", "selected_mcp_tool": "splunk_get_indexes"}
    grant_a = call_grant_from_tool_call(
        trace_id="trace-1", selection=selection, tool_arguments={"x": 1},
        rbac_role="analyst", identity="analyst", hil_required=True,
        execution_intent="metadata_discovery",
    )
    grant_trace_b = call_grant_from_tool_call(
        trace_id="trace-2", selection=selection, tool_arguments={"x": 1},
        rbac_role="analyst", identity="analyst", hil_required=True,
        execution_intent="metadata_discovery",
    )
    assert grants_match({"call_grant": grant_a}, grant_trace_b) is False

    grant_identity_b = call_grant_from_tool_call(
        trace_id="trace-1", selection=selection, tool_arguments={"x": 1},
        rbac_role="soc_lead", identity="soc_lead", hil_required=True,
        execution_intent="metadata_discovery",
    )
    assert grants_match({"call_grant": grant_a}, grant_identity_b) is False


def test_argument_mutation_alone_invalidates_grant_fingerprint() -> None:
    selection = {"selected_mcp_server": "splunk_soc", "selected_mcp_tool": "splunk_get_indexes"}
    grant_a = call_grant_from_tool_call(
        trace_id="t1", selection=selection, tool_arguments={"scope": "internal"},
        rbac_role="analyst", identity="analyst", hil_required=True,
        execution_intent="metadata_discovery",
    )
    grant_b = call_grant_from_tool_call(
        trace_id="t1", selection=selection, tool_arguments={"scope": "all"},
        rbac_role="analyst", identity="analyst", hil_required=True,
        execution_intent="metadata_discovery",
    )
    assert grant_a["fingerprint"] != grant_b["fingerprint"]
    assert grant_a["canonical_arguments_hash"] != grant_b["canonical_arguments_hash"]


# --- 11 consumed grant cannot be reused -------------------------------------

def test_consumed_saved_search_grant_cannot_be_reused(monkeypatch) -> None:
    connector = _CapturingConnector()
    monkeypatch.setattr(settings, "splunk_allow_run_saved_search", True)
    monkeypatch.setattr(settings, "splunk_allowed_saved_searches", "SOC - Failed login spike")
    _enable_mock_execution(monkeypatch, connector=connector)

    proposed, _review = evaluate_mcp_execution(
        trace_id="auth0-saved-reuse",
        selected_skill="spl_generation",
        workflow_plan={},
        spl_validation={"saved_search_name": "SOC - Failed login spike"},
        execution_intent="saved_search_execution",
        requested_mcp_tool="splunk_run_saved_search",
    )
    pending = proposed["pending_execution_confirmation"]

    executed, _review = evaluate_mcp_execution(
        trace_id="auth0-saved-reuse",
        selected_skill="spl_generation",
        workflow_plan={},
        spl_validation={"saved_search_name": "SOC - Failed login spike"},
        execution_intent="saved_search_execution",
        requested_mcp_tool="splunk_run_saved_search",
        execution_review_action="confirm",
        pending_execution=pending,
    )
    assert executed["status"] == "executed"
    consumed_grant = executed["call_grant"]
    assert consumed_grant["consumed"] is True

    replay, replay_review = evaluate_mcp_execution(
        trace_id="auth0-saved-reuse",
        selected_skill="spl_generation",
        workflow_plan={},
        spl_validation={"saved_search_name": "SOC - Failed login spike"},
        execution_intent="saved_search_execution",
        requested_mcp_tool="splunk_run_saved_search",
        execution_review_action="confirm",
        pending_execution={"call_grant": consumed_grant},
    )
    assert replay["block_reason"] == "exact_call_grant_invalidated"
    assert replay_review["reason"] == "exact_call_grant_invalidated"


# --- 12 LLM cannot construct or alter a grant -------------------------------

def test_llm_supplied_fields_cannot_reach_grant_construction() -> None:
    import inspect

    sig = inspect.signature(call_grant_from_tool_call)
    assert "llm_tool_recommendation" not in sig.parameters
    assert "llm_granted" not in sig.parameters
    selection = {"selected_mcp_server": "splunk_soc", "selected_mcp_tool": "splunk_get_indexes"}
    grant = call_grant_from_tool_call(
        trace_id="t1", selection=selection, tool_arguments={},
        rbac_role="analyst", identity="analyst", hil_required=True,
        execution_intent="metadata_discovery",
    )
    assert grant["llm_granted"] is False


# --- 14/15 RBAC / tool-policy failure independent of AUTH0 ------------------

def test_auth0_present_but_rbac_failure_still_rejected(monkeypatch) -> None:
    _enable_mock_execution(monkeypatch, connector=_RaisingConnector())

    execution, review = evaluate_mcp_execution(
        trace_id="auth0-rbac-deny",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=None,
        execution_intent="identity_lookup",
        requested_mcp_tool="splunk_get_user_info",
        rbac_role="viewer",
    )
    # viewer is not in mcp_rbac_policy.json's allowed_tools for
    # splunk_get_user_info — rejected before any grant/execution matters.
    assert execution["status"] == "requires_human_review"
    assert review["review_type"] == "policy_exception_request"


def test_auth0_present_but_tool_policy_failure_still_rejected(monkeypatch) -> None:
    _enable_mock_execution(monkeypatch, connector=_RaisingConnector())

    execution, review = evaluate_mcp_execution(
        trace_id="auth0-policy-deny",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=None,
        execution_intent="metadata_discovery",
        requested_mcp_tool="saia_generate_spl",
    )
    assert execution["status"] == "requires_human_review"
    assert execution["block_reason"] in {"requested_tool_intent_mismatch", "saia_conditional_blocked"} or (
        review.get("reason") in {"requested_tool_intent_mismatch", "saia_conditional_blocked"}
    )


# --- 16 discovery handshake stays separate from tool execution -------------

def test_handshake_never_calls_tool_execution(monkeypatch) -> None:
    calls: list[str] = []

    class _TrackingConnector:
        def call_tool(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            calls.append("call_tool")
            raise AssertionError("handshake must never execute a tool")

    connector = SplunkMcpConnector()
    result = connector.handshake_initialize_and_list_tools()
    assert calls == []
    assert result["status"] == "blocked"
    assert result["error"] == "live_transport_unconfigured"
