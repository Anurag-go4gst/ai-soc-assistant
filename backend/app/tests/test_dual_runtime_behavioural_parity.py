"""Behavioural dual-runtime parity — imperative canonical flow vs RP bootstrap (9 scenarios)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.chat.canonical_outcome_read import OutcomeReadKind, read_canonical_planning_outcome
from app.config import settings
from app.graph.resource_planner_graph import _rp_dispatch_route, rp_node_bootstrap
from app.query_understanding.parser import understand_query
from app.routing.select_route_from_understanding import select_route_from_understanding
from app.tests.support.canonical_flow import run_canonical_flow

_SCENARIOS: list[tuple[str, dict[str, Any]]] = [
    (
        "t1_known_complete",
        {
            "query": (
                "Investigate failed login spike for user:alice host:APP-01 "
                "from 10.0.0.8 in the last 24 hours"
            ),
            "use_case_id": "auth_failed_login_spike",
        },
    ),
    (
        "t1_cve_knowledge",
        {"query": "What is CVE-2026-12345?", "use_case_id": None},
    ),
    (
        "t4_guided_hunt",
        {"query": "Investigate unusual DNS behaviour around finance users", "use_case_id": None},
    ),
    (
        "policy_unsafe_block",
        {"query": "Block IP 10.0.0.5 immediately", "use_case_id": None},
    ),
    (
        "clarification_vague",
        {"query": "What happened with that alert?", "use_case_id": None},
    ),
    (
        "mitre_without_context",
        {"query": "Explain MITRE technique T1059", "use_case_id": None},
    ),
    (
        "sop_playbook",
        {"query": "What is the SOP for ransomware response?", "use_case_id": None},
    ),
    (
        "explicit_spl_authoring",
        {
            "query": "Write SPL to find failed logins for user alice in the last 24 hours",
            "use_case_id": None,
        },
    ),
    (
        "alert_summary_style",
        {
            "query": "Summarize alert ALT-0891 hybrid login anomaly for host APP-02",
            "use_case_id": "manual.alt0891_hybrid",
        },
    ),
]


@pytest.fixture(autouse=True)
def _enable_canonical(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)
    monkeypatch.setattr(settings, "telemetry_mode", "none")


def _base_state(query: str, *, use_case_id: str | None = None) -> dict[str, Any]:
    qu = understand_query(query)
    route, prov = select_route_from_understanding(qu, query)
    state: dict[str, Any] = {
        "request": SimpleNamespace(message=query),
        "effective_query": query,
        "query_understanding": qu,
        "routed": {**route, "routing_provenance": prov},
        "trace_id": "beh-parity",
    }
    if use_case_id:
        state["selected_use_case"] = SimpleNamespace(use_case_id=use_case_id)
    return state


def _projection(state: dict[str, Any]) -> dict[str, Any]:
    read = read_canonical_planning_outcome(state)
    outcome_status = None
    if read.kind == OutcomeReadKind.VALID and read.outcome is not None:
        outcome_status = read.outcome.status
    ep = state.get("evidence_plan") if isinstance(state.get("evidence_plan"), dict) else None
    planning = state.get("planning_decision") if isinstance(state.get("planning_decision"), dict) else {}
    return {
        "outcome_status": outcome_status,
        "outcome_read_kind": read.kind.value,
        "processing_lane": state.get("processing_lane"),
        "resolved_tier": state.get("resolved_tier"),
        "intent_family": (state.get("intent_classification") or {}).get("intent_family"),
        "primary_skill": (state.get("routed") or {}).get("skill"),
        "has_evidence_plan": ep is not None,
        "has_resource_plan": bool((ep or {}).get("resource_plan")),
        "answer_mode": (ep or {}).get("answer_mode"),
        "path_type": planning.get("path_type"),
        "rp_dispatch_route": _rp_dispatch_route(state),
        "requires_clarification": bool((state.get("human_review") or {}).get("requires_clarification"))
        if isinstance(state.get("human_review"), dict)
        else None,
    }


@pytest.mark.parametrize("scenario_id,params", _SCENARIOS, ids=[s[0] for s in _SCENARIOS])
def test_imperative_and_rp_bootstrap_behavioural_parity(scenario_id: str, params: dict[str, Any]) -> None:
    query = str(params["query"])
    use_case_id = params.get("use_case_id")
    imperative = run_canonical_flow(
        query,
        use_case_id=use_case_id,
        trace_id=f"beh-{scenario_id}",
    ).state
    via_rp = rp_node_bootstrap(dict(_base_state(query, use_case_id=use_case_id)))
    assert _projection(imperative) == _projection(via_rp), scenario_id
