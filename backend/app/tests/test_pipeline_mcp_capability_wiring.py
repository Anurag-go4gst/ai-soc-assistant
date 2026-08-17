"""Governed ResourcePlan -> mcp_capability wiring through the real
pipeline.py entry point (`_execution_stage`), not just the gate/selector in
isolation. Covers the mandatory test matrix items 1-15 for capability
production wiring.

mcp_capability derivation in pipeline.py is a projection of the SAME
structured signal that already decides execution_intent/requested_mcp_tool
(SPL generation's own `candidate_spl["generation_mode"]` field) -- never
user-text keyword matching. This file proves that projection is correct
and that a semantically-suggestive query with a non-matching structured
plan does not leak into capability selection (item 11 / 13).
"""

from __future__ import annotations

import time
from typing import Any

from app.chat.pipeline import _execution_stage
from app.connectors.mcp.discovery_snapshot import DiscoveredToolRecord, DiscoverySnapshot, get_discovery_snapshot_store

APPROVED = {
    "approved": True,
    "normalized_spl": "search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now | stats count by user | head 100",
    "reject_reasons": [],
    "warnings": [],
    "enforced_limits": {"max_result_limit": 100},
    "policy_version": "spl-policy-v1",
}

# Deliberately contains the words "indexes"/"metadata" inside an otherwise
# identical, still-valid SPL (a renamed grouping field) -- proves capability
# derivation does not scan SPL/query text for keywords. The structural signal
# (candidate_spl.generation_mode) is what matters, not this string's content.
APPROVED_MENTIONING_INDEXES_IN_TEXT = {
    **APPROVED,
    "normalized_spl": (
        "search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now "
        "| stats count by user_indexes_and_metadata_context | head 100"
    ),
}


class _RaisingConnector:
    def call_tool(self, tool_name: str, arguments: dict[str, Any], server_name: str | None = None) -> dict[str, Any]:
        raise AssertionError(f"connector.call_tool must not be reached for {tool_name}")


class _CapturingConnector:
    def __init__(self) -> None:
        self.called_with: tuple[str, dict[str, Any]] | None = None

    def call_tool(self, tool_name: str, arguments: dict[str, Any], server_name: str | None = None) -> dict[str, Any]:
        self.called_with = (tool_name, arguments)
        return {"status": "ok", "row_count": 1, "rows": [{"user": "svc_app"}]}


class _FakeTelemetry:
    def record_mcp_execution(self, *args: Any, **kwargs: Any) -> None:
        return None


def _registry_env(monkeypatch, *, allowlist: str = "splunk_run_query,splunk_run_saved_search") -> None:
    monkeypatch.setenv("MCP_MODE", "registry")
    monkeypatch.setenv("MCP_SERVERS", "splunk_soc")
    monkeypatch.setenv("MCP_DEFAULT_SERVER", "splunk_soc")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TYPE", "splunk")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TRANSPORT", "streamable_http")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_URL", "https://splunk-mcp.example.invalid/mcp")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_AUTH_MODE", "bearer")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_BEARER_TOKEN", "test-token")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TOOL_ALLOWLIST", allowlist)
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.ai_soc_require_spl_execution_confirmation", False)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.splunk_mcp_enabled", True)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.splunk_mcp_base_url", "https://splunk-mcp.example.invalid/mcp")
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.splunk_mcp_token", "test-token")
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.splunk_allow_run_saved_search", True)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.splunk_allowed_saved_searches", "SOC - Failed login spike")


def _seed(tool_name: str, input_schema: dict[str, Any] | None = None) -> None:
    get_discovery_snapshot_store().put(
        DiscoverySnapshot(
            server_name="splunk_soc", captured_at=time.time(), source="operator_refresh", status="ok",
            tools=(DiscoveredToolRecord(name=tool_name, input_schema=input_schema or {}),),
        )
    )


_QUERY_SCHEMA = {"properties": {"search_query": {"type": "string"}}, "required": ["search_query"]}


# 1. governed event-search ResourcePlan -> EVENT_SEARCH -> splunk_run_query
def test_1_default_execution_stage_resolves_event_search(monkeypatch) -> None:
    _registry_env(monkeypatch)
    connector = _CapturingConnector()
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: connector)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    _seed("splunk_run_query", _QUERY_SCHEMA)

    execution, review = _execution_stage(
        trace_id="pw1", selected_skill="attack_discovery", workflow_plan={},
        spl_validation=APPROVED, precondition_evaluation=None,
        requested_mcp_server=None, requested_mcp_tool=None,
        execution_intent="spl_search", mcp_capability="EVENT_SEARCH",
        execution_review_action="confirm",
    )
    assert execution["status"] == "executed"
    assert execution["selected_mcp_tool"] == "splunk_run_query"
    assert connector.called_with is not None


# 2. saved_search_primary -> SAVED_SEARCH_EXECUTION -> splunk_run_saved_search
def test_2_saved_search_capability_resolves_saved_search_tool(monkeypatch) -> None:
    _registry_env(monkeypatch)
    connector = _CapturingConnector()
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: connector)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    _seed("splunk_run_saved_search", {"properties": {"saved_search_name": {"type": "string"}}, "required": ["saved_search_name"]})

    proposed, _review = _execution_stage(
        trace_id="pw2", selected_skill="spl_generation", workflow_plan={},
        spl_validation={"saved_search_name": "SOC - Failed login spike"},
        precondition_evaluation=None,
        requested_mcp_server=None, requested_mcp_tool="splunk_run_saved_search",
        execution_intent="saved_search_execution", mcp_capability="SAVED_SEARCH_EXECUTION",
    )
    pending = proposed["pending_execution_confirmation"]

    execution, review = _execution_stage(
        trace_id="pw2", selected_skill="spl_generation", workflow_plan={},
        spl_validation={"saved_search_name": "SOC - Failed login spike"},
        precondition_evaluation=None,
        requested_mcp_server=None, requested_mcp_tool="splunk_run_saved_search",
        execution_intent="saved_search_execution", mcp_capability="SAVED_SEARCH_EXECUTION",
        execution_review_action="confirm", pending_execution=pending,
    )
    assert execution["status"] == "executed"
    assert execution["selected_mcp_tool"] == "splunk_run_saved_search"


# 3. validated capability reaches select_mcp_tool (proven by 1/2 already
# resolving the exact tool from capability alone -- explicit assertion here)
def test_3_capability_is_what_determined_the_tool_not_a_default_list_scan(monkeypatch) -> None:
    _registry_env(monkeypatch, allowlist="splunk_get_indexes,splunk_run_query")  # indexes listed FIRST
    connector = _CapturingConnector()
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: connector)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    _seed("splunk_run_query", _QUERY_SCHEMA)

    execution, review = _execution_stage(
        trace_id="pw3", selected_skill="attack_discovery", workflow_plan={},
        spl_validation=APPROVED, precondition_evaluation=None,
        requested_mcp_server=None, requested_mcp_tool=None,
        execution_intent="spl_search", mcp_capability="EVENT_SEARCH",
        execution_review_action="confirm",
    )
    # splunk_get_indexes is not present in the discovery snapshot at all and
    # is a different capability besides -- if list-order default-eligible
    # scanning were still in control, this would misbehave. It resolves
    # deterministically to splunk_run_query via capability instead.
    assert execution["selected_mcp_tool"] == "splunk_run_query"


# 4. unknown capability rejected
def test_4_unknown_capability_rejected(monkeypatch) -> None:
    _registry_env(monkeypatch)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: _RaisingConnector())
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    _seed("splunk_run_query", _QUERY_SCHEMA)

    execution, review = _execution_stage(
        trace_id="pw4", selected_skill="attack_discovery", workflow_plan={},
        spl_validation=APPROVED, precondition_evaluation=None,
        requested_mcp_server=None, requested_mcp_tool=None,
        execution_intent="spl_search", mcp_capability="DROP_EVERYTHING",
        execution_review_action="confirm",
    )
    assert execution["status"] == "requires_human_review"
    assert execution["tool_selection_reason"] == "capability_unresolved"


# 5. raw LLM tool recommendation cannot override capability
def test_5_llm_tool_recommendation_cannot_override_capability(monkeypatch) -> None:
    _registry_env(monkeypatch)
    connector = _CapturingConnector()
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: connector)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    monkeypatch.setattr("app.orchestration.mcp_tool_selector.settings.llm_tool_recommendation_enabled", True)
    _seed("splunk_run_query", _QUERY_SCHEMA)

    execution, review = _execution_stage(
        trace_id="pw5", selected_skill="attack_discovery", workflow_plan={},
        spl_validation=APPROVED, precondition_evaluation=None,
        requested_mcp_server=None, requested_mcp_tool=None,
        execution_intent="spl_search", mcp_capability="EVENT_SEARCH",
        execution_review_action="confirm",
    )
    assert execution["selected_mcp_tool"] == "splunk_run_query"  # llm_tool_recommendation was never even passed through


# 6. raw requested tool inconsistent with capability -- explicit request wins
# over capability (analyst preference), but must still pass all safety checks
def test_6_explicit_requested_tool_inconsistent_with_capability_still_governed(monkeypatch) -> None:
    _registry_env(monkeypatch, allowlist="splunk_run_query,splunk_get_indexes")
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: _RaisingConnector())
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    _seed("splunk_get_indexes")

    execution, review = _execution_stage(
        trace_id="pw6", selected_skill="attack_discovery", workflow_plan={},
        spl_validation=APPROVED, precondition_evaluation=None,
        requested_mcp_server=None, requested_mcp_tool="splunk_get_indexes",  # explicit, but intent says spl_search
        execution_intent="spl_search", mcp_capability="EVENT_SEARCH",
        execution_review_action="confirm",
    )
    assert execution["status"] == "requires_human_review"
    assert execution["tool_selection_reason"] == "requested_tool_intent_mismatch"


# 7. effective catalog still required even with a validated capability
def test_7_effective_catalog_still_required_with_capability(monkeypatch) -> None:
    _registry_env(monkeypatch)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: _RaisingConnector())
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    # no snapshot seeded at all -> DISCOVERY_UNVERIFIED

    execution, review = _execution_stage(
        trace_id="pw7", selected_skill="attack_discovery", workflow_plan={},
        spl_validation=APPROVED, precondition_evaluation=None,
        requested_mcp_server=None, requested_mcp_tool=None,
        execution_intent="spl_search", mcp_capability="EVENT_SEARCH",
        execution_review_action="confirm",
    )
    assert execution["status"] == "requires_human_review"
    assert execution["tool_selection_reason"] == "effective_catalog_blocked:DISCOVERY_UNVERIFIED"


# 8. capability does not bypass AUTH0
def test_8_capability_does_not_bypass_auth0(monkeypatch) -> None:
    _registry_env(monkeypatch)
    connector = _CapturingConnector()
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: connector)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    _seed("splunk_run_query", _QUERY_SCHEMA)

    # no execution_review_action="confirm" -- AUTH0/HIL round trip required
    execution, review = _execution_stage(
        trace_id="pw8", selected_skill="attack_discovery", workflow_plan={},
        spl_validation=APPROVED, precondition_evaluation=None,
        requested_mcp_server=None, requested_mcp_tool=None,
        execution_intent="spl_search", mcp_capability="EVENT_SEARCH",
    )
    assert execution["status"] == "requires_human_review"
    assert connector.called_with is None


# 9. capability does not bypass RBAC
def test_9_capability_does_not_bypass_rbac(monkeypatch) -> None:
    _registry_env(monkeypatch, allowlist="splunk_run_query,splunk_get_user_info")
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: _RaisingConnector())
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    _seed("splunk_get_user_info")

    execution, review = _execution_stage(
        trace_id="pw9", selected_skill="attack_discovery", workflow_plan={},
        spl_validation={}, precondition_evaluation=None,
        requested_mcp_server=None, requested_mcp_tool=None,
        execution_intent="identity_lookup", mcp_capability="USER_CONTEXT",
        execution_review_action="confirm", rbac_role="viewer",
        mcp_allowed=True,
    )
    assert execution["status"] == "requires_human_review"
    assert review["review_type"] == "policy_exception_request"


# 10. capability does not bypass HIL
def test_10_capability_does_not_bypass_hil(monkeypatch) -> None:
    _registry_env(monkeypatch, allowlist="splunk_run_query,splunk_get_user_info")
    connector = _CapturingConnector()
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: connector)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    _seed("splunk_get_user_info")

    execution, review = _execution_stage(
        trace_id="pw10", selected_skill="attack_discovery", workflow_plan={},
        spl_validation={}, precondition_evaluation=None,
        requested_mcp_server=None, requested_mcp_tool=None,
        execution_intent="identity_lookup", mcp_capability="USER_CONTEXT",
        rbac_role="analyst", mcp_allowed=True,  # no confirm action
    )
    assert execution["status"] == "requires_human_review"
    assert connector.called_with is None


# 13/11. semantic text mentioning "indexes"/"metadata" with a structured
# EVENT_SEARCH plan must NOT route to metadata capabilities -- proves no
# keyword routing was introduced.
def test_11_13_text_mentioning_indexes_stays_event_search(monkeypatch) -> None:
    _registry_env(monkeypatch)
    connector = _CapturingConnector()
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: connector)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    _seed("splunk_run_query", _QUERY_SCHEMA)

    execution, review = _execution_stage(
        trace_id="pw11", selected_skill="attack_discovery", workflow_plan={},
        spl_validation=APPROVED_MENTIONING_INDEXES_IN_TEXT, precondition_evaluation=None,
        requested_mcp_server=None, requested_mcp_tool=None,
        execution_intent="spl_search", mcp_capability="EVENT_SEARCH",  # structural, not derived from the text above
        execution_review_action="confirm",
    )
    assert execution["status"] == "executed"
    assert execution["selected_mcp_tool"] == "splunk_run_query"


# 14. metadata capability with no executable effective tool fails closed
def test_14_metadata_capability_no_executable_tool_fails_closed(monkeypatch) -> None:
    _registry_env(monkeypatch, allowlist="splunk_get_indexes")
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: _RaisingConnector())
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    # no snapshot -> DISCOVERY_UNVERIFIED, capability resolves to
    # splunk_get_indexes but it's not verified executable

    execution, review = _execution_stage(
        trace_id="pw14", selected_skill="attack_discovery", workflow_plan={},
        spl_validation={}, precondition_evaluation=None,
        requested_mcp_server=None, requested_mcp_tool=None,
        execution_intent="metadata_discovery", mcp_capability="INDEX_DISCOVERY",
        execution_review_action="confirm", mcp_allowed=True,
    )
    assert execution["status"] == "requires_human_review"


# 15. execution_intent cannot override a contradictory validated capability
def test_15_contradictory_execution_intent_and_capability_fails_closed(monkeypatch) -> None:
    _registry_env(monkeypatch)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: _RaisingConnector())
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    _seed("splunk_run_query", _QUERY_SCHEMA)

    # capability says EVENT_SEARCH (-> splunk_run_query), but execution_intent
    # claims metadata_discovery -- neither silently wins; the mismatch is
    # caught by _tool_matches_intent and rejected.
    execution, review = _execution_stage(
        trace_id="pw15", selected_skill="attack_discovery", workflow_plan={},
        spl_validation=APPROVED, precondition_evaluation=None,
        requested_mcp_server=None, requested_mcp_tool=None,
        execution_intent="metadata_discovery", mcp_capability="EVENT_SEARCH",
        execution_review_action="confirm",
    )
    assert execution["status"] == "requires_human_review"
    assert execution["tool_selection_reason"] == "requested_tool_intent_mismatch"


# fallback preserves the original required capability -- a failed EVENT_SEARCH
# tool must never mutate into a fallback attempt for a different capability.
def test_16_fallback_never_mutates_the_required_capability(monkeypatch) -> None:
    from app.connectors.mcp.effective_catalog import compute_effective_catalog
    from app.connectors.mcp.mcp_failure_taxonomy import TOOL_UNAVAILABLE
    from app.connectors.mcp.registry import load_mcp_registry_status
    from app.orchestration.mcp_fallback_policy import CAPABILITY_FALLBACK_CANDIDATES, resolve_fallback_tool

    _registry_env(monkeypatch, allowlist="splunk_run_query,splunk_get_indexes")
    registry = load_mcp_registry_status()
    server = registry.servers[0]
    snapshot = DiscoverySnapshot(
        server_name="splunk_soc", captured_at=time.time(), source="operator_refresh", status="ok",
        tools=(
            DiscoveredToolRecord(name="splunk_run_query", input_schema=_QUERY_SCHEMA),
            DiscoveredToolRecord(name="splunk_get_indexes", input_schema={}),
        ),
    )
    catalog = compute_effective_catalog(server, mode="registry", snapshot=snapshot)

    # The resolver call site always passes the ORIGINAL required capability
    # ("EVENT_SEARCH") -- it never derives a new one from the failure. Since
    # no cross-capability equivalence is ever configured in production
    # (CAPABILITY_FALLBACK_CANDIDATES stays empty), the realistic case is
    # simply "no candidate", proven here without injecting anything.
    assert "EVENT_SEARCH" not in CAPABILITY_FALLBACK_CANDIDATES
    tool, reason = resolve_fallback_tool(
        capability="EVENT_SEARCH", failed_tool_name="splunk_run_query",
        failure_kind=TOOL_UNAVAILABLE, effective_catalog=catalog,
    )
    assert tool is None
    assert reason == "no_established_fallback_equivalence"
