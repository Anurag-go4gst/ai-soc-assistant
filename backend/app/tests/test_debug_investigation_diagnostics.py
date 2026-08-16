"""Failing-first COE investigation diagnostics on debug_summary / bundle.

Pins EvidenceState, InvestigationOutcome, AUTH0, T4 circuit, and MCP status
projections on the existing explainability surface — not a parallel trace.
"""

from __future__ import annotations

import json
from typing import Any

from app.chat.debug_summary import build_debug_summary, redact_resolved_query
from app.connectors.telemetry.redaction import minimize
from app.orchestration.splunk_call_authorization import build_splunk_call_grant
from app.tests.test_debug_summary import _scada_like_payload


BEARER = "Bearer FAKESECRET_u3v4w5x6y7z8a9b0c1d2"
TOKEN_FILE = "splunk-mcp-token.txt contents: super-secret-file"
PROVIDER_KEY = "sk-live-provider-credential-do-not-leak"
GRANT_SPL = "search index=secrets sourcetype=auth0:log | table user password"


def _grant() -> dict[str, Any]:
    return build_splunk_call_grant(
        trace_id="diag-1",
        identity="analyst",
        selected_mcp_server="splunk",
        selected_mcp_tool="splunk_run_query",
        normalized_spl=GRANT_SPL,
        mcp_endpoint="https://splunk.example/mcp",
        rbac_role="analyst",
        now=1_700_000_000.0,
    )


def _diagnostic_payload() -> dict[str, Any]:
    payload = _scada_like_payload()
    grant = _grant()
    payload["execution"] = {
        "status": "skipped",
        "block_reason": "requires_human_review",
        "evidence_source": "unavailable",
        "selected_mcp_server": "splunk",
        "selected_mcp_tool": "splunk_run_query",
        "result_count": 0,
        "call_grant_consumed": False,
        "results_preview": [{"user": "alice", "password": "hunter2", "note": BEARER}],
        "splunk_mcp_token": BEARER,
        "pending_execution_confirmation": {
            "normalized_spl": GRANT_SPL,
            "token_file": TOKEN_FILE,
            "call_grant": grant,
        },
    }
    payload["run_contract"]["mcp_allowed"] = False
    payload["evidence_state"] = {
        "schema_version": "minimal_evidence_state_v1",
        "required": ["mcp", "user"],
        "obtained": ["user"],
        "missing": ["mcp"],
        "stale": [],
        "invalidated": [],
        "blocked": ["mcp"],
        "provenance": {"derived_from": ["source_evidence"], "raw_evidence_duplicated": False},
        "scope": {"entities": {"user": "alice", "host": "ot-1"}},
        "items": [
            {
                "key": "user",
                "status": "obtained",
                "trust_class": "untrusted_evidence",
                "provenance": "source_evidence",
                "scope": {"entities": {"user": "alice"}},
                "preview_rows": [{"raw": "should-not-surface"}],
            },
            {
                "key": "mcp",
                "status": "blocked",
                "trust_class": "trusted_control_authority",
                "provenance": "evidence_plan",
            },
        ],
        "preview_rows": [{"secret": PROVIDER_KEY}],
    }
    payload["investigation_outcome"] = {
        "schema_version": "investigation_outcome_v1",
        "disposition": "inconclusive",
        "severity_label": "P3",
        "findings": ["Failed logons clustered on one host"],
        "evidence_refs": ["src-1"],
        "missing_evidence": ["mcp"],
        "llm_proposal_accepted": False,
        "recommended_actions": ["investigate"],
        "policy_eligibility": {
            "synthesis_allowed": False,
            "human_review_required": True,
            "evidence_sufficiency": "PARTIAL",
            "next_action": "collect_missing_evidence",
        },
        "preview_rows": [{"row": "raw-mcp-hit"}],
    }
    payload["resolved_query_contract"] = {
        "qualification_tier": "T4",
        "intent_family": "guided_investigation",
        "answer_goal": "procedural_steps",
        "ambiguity_state": "unambiguous",
        "understanding_source": "deterministic_qualification",
        "qualification_source": "deterministic",
        "entities": {"host": "ot-1"},
        "provenance": {
            "semantic_t4": {
                "invoked": False,
                "accepted": False,
                "timed_out": False,
                "failure_kind": "circuit_open",
                "circuit_state": "OPEN",
                "human_action_required": True,
                "elapsed_ms": 12,
                "rejected_reasons": ["circuit_open"],
                "notes": [
                    "t4_circuit_open",
                    "human_action_required_model_restart",
                    PROVIDER_KEY,
                ],
                "prompt": "system prompt with " + PROVIDER_KEY,
            }
        },
    }
    payload["source_evidence"] = [
        {
            "evidence_id": "src-1",
            "preview_rows": [{"password": "hunter2", "Authorization": BEARER}],
            "api_key": PROVIDER_KEY,
        }
    ]
    return payload


def test_debug_summary_includes_evidence_state_keys_not_rows() -> None:
    summary = build_debug_summary(payload=_diagnostic_payload())
    evidence = summary["evidence_state"]
    assert evidence["required"] == ["mcp", "user"]
    assert evidence["obtained"] == ["user"]
    assert evidence["missing"] == ["mcp"]
    assert evidence["blocked"] == ["mcp"]
    assert "preview_rows" not in evidence
    assert "alice" not in json.dumps(evidence)
    keys = {item["key"] for item in evidence["items"]}
    assert keys == {"user", "mcp"}
    for item in evidence["items"]:
        assert "preview_rows" not in item
        assert "scope" not in item or "entities" not in (item.get("scope") or {})


def test_debug_summary_includes_investigation_outcome_projection() -> None:
    summary = build_debug_summary(payload=_diagnostic_payload())
    outcome = summary["investigation_outcome"]
    assert outcome["disposition"] == "inconclusive"
    assert outcome["severity_label"] == "P3"
    assert outcome["missing_evidence"] == ["mcp"]
    assert outcome["evidence_refs"] == ["src-1"]
    assert outcome["llm_proposal_accepted"] is False
    assert outcome["policy_eligibility"]["synthesis_allowed"] is False
    assert "preview_rows" not in outcome
    dumped = json.dumps(outcome)
    assert "raw-mcp-hit" not in dumped


def test_debug_summary_includes_auth0_fingerprint_not_grant_material() -> None:
    payload = _diagnostic_payload()
    expected_fp = payload["execution"]["pending_execution_confirmation"]["call_grant"]["fingerprint"]
    summary = build_debug_summary(payload=payload)
    auth0 = summary["auth0"]
    assert auth0["present"] is True
    assert auth0["fingerprint"] == expected_fp
    assert auth0["llm_granted"] is False
    assert auth0["consumed"] is False
    assert auth0["hil_required"] is True
    assert auth0["selected_mcp_tool"] == "splunk_run_query"
    dumped = json.dumps(auth0)
    assert GRANT_SPL not in dumped
    assert "normalized_spl" not in dumped
    assert "mcp_endpoint" not in dumped
    assert "analyst" not in dumped
    assert TOKEN_FILE not in dumped
    assert BEARER not in dumped


def test_debug_summary_includes_t4_circuit_first_class() -> None:
    summary = build_debug_summary(payload=_diagnostic_payload())
    circuit = summary["t4_circuit"]
    assert circuit["circuit_state"] == "OPEN"
    assert circuit["human_action_required"] is True
    assert circuit["failure_kind"] == "circuit_open"
    t4 = summary["resolved_query"]["semantic_t4"]
    assert t4["circuit_state"] == "OPEN"
    assert t4["human_action_required"] is True
    assert "t4_circuit_open" in t4["notes"]
    assert "human_action_required_model_restart" in t4["notes"]
    assert PROVIDER_KEY not in json.dumps(t4)


def test_debug_summary_mcp_status_omits_rows_and_tokens() -> None:
    summary = build_debug_summary(payload=_diagnostic_payload())
    mcp = summary["mcp"]
    assert mcp["status"] == "skipped"
    assert mcp["block_reason"] == "requires_human_review"
    assert mcp["evidence_source"] == "unavailable"
    assert mcp["selected_mcp_tool"] == "splunk_run_query"
    assert mcp["result_count"] == 0
    assert mcp["call_grant_consumed"] is False
    dumped = json.dumps(mcp)
    assert "results_preview" not in dumped
    assert "alice" not in dumped
    assert BEARER not in dumped
    assert "splunk_mcp_token" not in dumped


def test_redact_resolved_query_preserves_circuit_across_second_pass() -> None:
    once = redact_resolved_query(_diagnostic_payload()["resolved_query_contract"])
    twice = redact_resolved_query(once)
    assert twice["semantic_t4"]["circuit_state"] == "OPEN"
    assert twice["semantic_t4"]["human_action_required"] is True


def test_debug_summary_and_minimize_drop_secrets_and_raw_rows() -> None:
    summary = build_debug_summary(payload=_diagnostic_payload())
    blob = json.dumps(minimize(summary))
    assert BEARER not in blob
    assert TOKEN_FILE not in blob
    assert PROVIDER_KEY not in blob
    assert GRANT_SPL not in blob
    assert "hunter2" not in blob
    assert "preview_rows" not in blob
    assert "sk-live-provider" not in blob


def test_trace_bundle_explainability_carries_investigation_diagnostics() -> None:
    summary = build_debug_summary(payload=_diagnostic_payload())
    from app.connectors.telemetry.read_store import fetch_trace_bundle

    def _timeline(trace_id: str, *, max_events: int | None = None) -> dict[str, Any]:
        return {
            "run": {"trace_id": trace_id, "metadata": {"debug_summary": summary, "turn_id": "turn-1"}},
            "events": [],
            "event_count": 0,
        }

    import app.connectors.telemetry.read_store as read_store

    original = read_store.fetch_trace_timeline
    read_store.fetch_trace_timeline = _timeline  # type: ignore[method-assign]
    try:
        bundle = fetch_trace_bundle("diag-1")
    finally:
        read_store.fetch_trace_timeline = original  # type: ignore[method-assign]
    assert bundle is not None
    ds = bundle["explainability"]["debug_summary"]
    assert ds["evidence_state"]["missing"] == ["mcp"]
    assert ds["investigation_outcome"]["disposition"] == "inconclusive"
    assert ds["auth0"]["fingerprint"]
    assert ds["t4_circuit"]["circuit_state"] == "OPEN"
    assert ds["mcp"]["evidence_source"] == "unavailable"
    assert bundle["turn_id"] == "turn-1"


def test_control_plane_trace_projects_auth0_and_evidence_state() -> None:
    from app.chat.control_plane_trace import build_control_plane_trace

    grant = _grant()
    trace = build_control_plane_trace(
        {
            "evidence_state": {
                "required": ["mcp"],
                "obtained": [],
                "missing": ["mcp"],
                "blocked": ["mcp"],
                "items": [{"key": "mcp", "status": "blocked", "preview_rows": [{"x": 1}]}],
                "scope": {"entities": {"user": "alice"}},
            },
            "investigation_outcome": {
                "disposition": "blocked",
                "missing_evidence": ["mcp"],
                "preview_rows": [{"raw": "nope"}],
            },
            "execution": {
                "status": "skipped",
                "block_reason": "requires_human_review",
                "evidence_source": "unavailable",
                "selected_mcp_tool": "splunk_run_query",
                "result_count": 0,
                "pending_execution_confirmation": {
                    "normalized_spl": GRANT_SPL,
                    "call_grant": grant,
                },
            },
        }
    )
    mcp = trace["mcp_execution"]
    assert mcp["auth0"]["fingerprint"] == grant["fingerprint"]
    assert GRANT_SPL not in json.dumps(mcp)
    evidence = trace["evidence_state"]
    assert evidence["missing"] == ["mcp"]
    assert "alice" not in json.dumps(evidence)
    outcome = trace["investigation_outcome"]
    assert outcome["disposition"] == "blocked"
    assert "preview_rows" not in outcome
