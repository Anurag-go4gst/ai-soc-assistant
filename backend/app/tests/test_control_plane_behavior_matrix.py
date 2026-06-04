"""Commit 5 — general SOC reasoning behavior matrix.

A broad, tactic-spanning matrix that asserts *contracts* (answer mode, gates,
no over-claim, validator never self-blocks a governed answer) rather than
brittle counts or exact strings. The point is generality: the same governed
rules hold for auth, DNS/DGA, phishing, malware, network, exfiltration, and
lateral-movement inputs — without a per-question fix.

Does not enable live MCP and never executes candidate_spl.
"""

from __future__ import annotations

import pytest

from app.api.routes_chat import chat
from app.schemas.requests import ChatRequest


@pytest.fixture(autouse=True)
def _enable_control_plane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.control_plane_enabled", True)
    monkeypatch.setattr("app.config.settings.spl_allowed_sourcetypes", "pgcil:auth,aws:cloudtrail")


# (query, category) — categories drive the extra per-row checks below.
MATRIX: list[tuple[str, str]] = [
    # policy / RAG-only
    ("What is the escalation policy for repeated failed login alerts?", "policy"),
    ("When should repeated failed login alerts be escalated?", "policy"),
    ("What is the SOP for brute-force investigation?", "policy"),
    ("What is the playbook for phishing response?", "policy"),
    ("What is a DGA domain?", "knowledge"),
    ("Explain what credential dumping means", "knowledge"),
    # live investigation
    ("Find accounts failing login in the last 24 hours", "live"),
    ("Show top users with failed login count in the last 24 hours and exclude service accounts", "live"),
    ("Investigate repeated failed logins in the last 24 hours", "live"),
    ("List source IPs with the most failed authentications today", "live"),
    # hybrid (investigation + guidance / policy)
    ("Find accounts failing login in the last 24 hours, exclude service accounts, and tell me what analyst action I should take", "hybrid"),
    ("Investigate DGA alerts and give me the playbook next steps", "hybrid"),
    ("Review alert ALT-2024-0891: repeated failed logins followed by a successful login, map to MITRE and assess severity", "hybrid"),
    # MITRE mapping / explanation
    ("Map 148 failed logins across 12 accounts from external IPs to MITRE", "mitre"),
    ("Map this alert to MITRE", "mitre_clarify"),
    ("Explain MITRE technique T1110", "mitre_explain"),
    # SPL-only
    ("Generate SPL for the top failed-login users in the last 24 hours", "spl_only"),
    ("Generate SPL for failed logins, review only, do not execute", "spl_only"),
    ("Write a query for failed authentications grouped by user", "spl_only"),
    # negative evidence — auth
    ("148 failed logins across 12 accounts from external IPs, no successful login, no endpoint telemetry, no evidence of credential dumping — map to MITRE", "neg_auth"),
    ("Repeated failed logins with no successful login observed — what MITRE applies?", "neg_auth"),
    # negative evidence — non-auth (the generalization)
    ("Suspected data exfiltration but no outbound transfer was observed — what can we conclude?", "neg_general"),
    ("Possible DGA beaconing detected, but no command execution was seen", "neg_general"),
    ("Phishing email reported, no endpoint telemetry available", "neg_general"),
    ("Lateral movement suspected but no remote service authentication observed", "neg_general"),
    ("Malware alert raised with no credential dumping evidence", "neg_general"),
    ("Network anomaly flagged with no outbound transfer and no command execution", "neg_general"),
    # MCP unavailable / execution requested
    ("Run a live search for failed logins in the last 24 hours now", "mcp_unavailable"),
    ("Execute SPL to find failed logins and pull the results", "mcp_unavailable"),
    # additional knowledge / procedural
    ("Explain the investigation steps for DGA detection", "knowledge"),
    ("What are the steps to investigate a brute-force alert?", "policy"),
    ("Describe how to triage a suspicious login alert", "knowledge"),
]


def _visible_mitre_ids(response) -> set[str]:
    ar = response.analyst_response
    rows = getattr(ar, "mitre_mappings", None) if ar is not None else None
    out: set[str] = set()
    for row in rows or []:
        if isinstance(row, dict) and (row.get("Technique") or row.get("technique_id")):
            out.add(str(row.get("Technique") or row.get("technique_id")))
    return out


def _not_claimed_ids(response) -> set[str]:
    contract = response.answer_contract or {}
    return {str(item) for item in contract.get("not_claimed_technique_ids") or []}


@pytest.mark.parametrize("query,category", MATRIX, ids=[f"{c}:{q[:40]}" for q, c in MATRIX])
def test_behavior_matrix_universal_governance(query: str, category: str) -> None:
    """Invariants that must hold for every governed answer, every tactic."""
    response = chat(ChatRequest(message=query))

    # The control plane always projects a contract and runs the validator.
    assert response.answer_contract is not None, query
    assert response.control_plane_trace is not None, query
    assert response.final_answer_validation is not None, query

    # Validation either passes, or fails closed. Failing closed is a valid
    # governed outcome (e.g. an incomplete answer), but it MUST route to analyst
    # review — never be shown as-is.
    fav = response.final_answer_validation
    if fav["guard_status"] == "blocked":
        assert fav["analyst_review_required"] is True, (query, fav)
        assert response.human_review is not None and response.human_review.required, query
    else:
        assert fav["guard_status"] in {"passed", "skipped"}, (query, fav)

    visible = _visible_mitre_ids(response)
    # No over-claim: a not-claimed / blocked technique never appears as a positive mapping.
    assert visible.isdisjoint(_not_claimed_ids(response)), (query, visible)

    # MITRE is only shown when the decision made it answer-visible.
    if visible:
        assert response.answer_contract["mitre_answer_visible"] is True, query


@pytest.mark.parametrize("query,category", [(q, c) for q, c in MATRIX], ids=[f"{c}:{q[:40]}" for q, c in MATRIX])
def test_behavior_matrix_category_contracts(query: str, category: str) -> None:
    """Per-category gate checks sourced from the contract / evidence plan."""
    response = chat(ChatRequest(message=query))
    contract = response.answer_contract or {}
    ar = response.analyst_response

    if category in {"policy", "knowledge"}:
        # Policy/knowledge answers must not present an executable artifact path
        # or answer-visible MITRE.
        assert contract.get("mitre_answer_visible") is not True, query
        if ar is not None:
            assert not getattr(ar, "spl_code", None), query

    if category == "spl_only":
        # SPL generation must not silently execute or require MCP.
        assert contract.get("execution_status") in {None, "skipped", "requires_human_review", "not_executed"}, (
            query,
            contract.get("execution_status"),
        )

    if category in {"neg_auth", "neg_general"}:
        # Negative-evidence inputs stay governed: any answer-visible technique is
        # backed by the decision (no over-claim), and absence is handled without
        # an unrouted self-inconsistent answer.
        fav = response.final_answer_validation
        assert fav["guard_status"] in {"passed", "skipped"} or fav["analyst_review_required"] is True, query

    if category == "mcp_unavailable":
        # Execution is never live; either skipped/gated or routed to review.
        assert contract.get("execution_status") != "executed", query
