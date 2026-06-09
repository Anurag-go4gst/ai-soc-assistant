"""Unit tests for live/demo analyst response envelope builder."""

from __future__ import annotations

import pytest

from app.chat.analyst_response_builder import (
    attach_evidence_summary,
    build_analyst_response_for_live,
    summarize_failed_login_events,
)
from app.threat.mitre_kb import MitreMappingDecision


def test_summarize_failed_login_events_sums_per_source_rows() -> None:
    rows = [
        {"Host": "APP-01", "Failed logins": 42},
        {"Host": "APP-01", "Failed logins": 31},
        {"Host": "APP-01", "Failed logins": 28},
    ]
    summary = summarize_failed_login_events(rows)
    assert summary is not None
    assert "101" in summary
    assert "42 + 31 + 28" in summary
    assert "distinct-user" in summary.lower()


def test_attach_evidence_summary_adds_footnote() -> None:
    payload = attach_evidence_summary(
        {
            "splunk_results_table": [
                {"Failed logins": 10},
                {"Failed logins": 5},
            ],
        }
    )
    assert payload.get("evidence_summary")
    assert "15" in str(payload["evidence_summary"])


def test_build_analyst_response_from_splunk_and_rag() -> None:
    """Source-grounded splunk_mcp execution may render evidence-supported MITRE display."""
    envelope = build_analyst_response_for_live(
        user_query="failed logins on APP-01",
        message="SPL validation complete. MCP execution is disabled.",
        analyst_summary="Governed summary for analysts.",
        source_evidence=[
            {
                "source_type": "splunk_mcp",
                "collection_status": "collected",
                "preview_rows": [
                    {
                        "host": "APP-01",
                        "src": "10.10.4.21",
                        "fail_count": 42,
                        "distinct_users": 7,
                    },
                ],
            },
            {
                "source_type": "rag",
                "collection_status": "collected",
                "evidence_id": "ev-rag-test",
                "provider_used": "governed_soc_kb",
                "preview_rows": [
                    {
                        "doc_title": "Brute-force Authentication Investigation",
                        "citation": "SOC-SOP-AUTH-001#triage",
                        "doc_version": "2026.04",
                        "source_excerpt": "Triage brute-force authentication alerts.",
                        "recommended_actions": [
                            "Confirm no successful login followed the failure sequence.",
                        ],
                    },
                ],
            },
        ],
        mitre_mappings=[
            MitreMappingDecision(
                technique_id="T1110.001",
                name="Password Guessing",
                tactic="Credential Access",
                status="evidence_supported",
                why="Repeated failures",
            ),
        ],
        mitre_decision={
            "answer_visible": True,
            "techniques": [
                {
                    "technique_id": "T1110.001",
                    "name": "Password Guessing",
                    "tactic": "Credential Access",
                    "status": "evidence_supported",
                    "why": "Repeated failures",
                },
            ],
            "rejected_techniques": [],
        },
        severity_label="P2 High",
        synthesis_draft=None,
        human_review=None,
        selected_use_case_label="Brute-force spike",
        execution={
            "status": "executed",
            "splunk_result_envelope": {"origin": "fixture"},
        },
        intent_classification={
            "intent_family": "hybrid_alert_review",
            "answer_goal": ["mitre_mapping", "live_results", "policy_citation"],
        },
        evidence_plan={
            "answer_mode": "hybrid",
            "needs_mitre": True,
            "mcp_allowed": True,
            "spl_allowed": True,
        },
    )
    assert envelope is not None
    assert envelope.severity_label == "P2 High"
    assert envelope.finding_title == "Brute-force spike"
    assert envelope.direct_answer_summary
    assert "evidence-supported MITRE technique" in envelope.direct_answer_summary
    assert envelope.splunk_results_table
    assert envelope.splunk_results_table[0]["Failed logins"] == 42
    assert envelope.evidence_summary
    assert envelope.retrieved_playbook is not None
    assert envelope.retrieved_playbook.get("citation") == "SOC-SOP-AUTH-001#triage"
    assert envelope.retrieved_playbook.get("source_evidence_id") == "ev-rag-test"
    assert envelope.mitre_mappings
    assert envelope.mitre_mappings[0]["Technique"] == "T1110.001"
    assert envelope.mitre_mappings[0]["Status"] == "Evidence Supported"
    assert envelope.mitre_mappings[0]["Confidence"] == "High - evidence supported"


def test_build_analyst_response_returns_none_without_substance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.chat.analyst_response_builder.settings.control_plane_enabled", False)
    envelope = build_analyst_response_for_live(
        user_query="hello",
        message="Routing complete. SPL is not required at this stage.",
        analyst_summary=None,
        source_evidence=[],
        mitre_mappings=[],
        severity_label=None,
        synthesis_draft=None,
        human_review=None,
    )
    assert envelope is None


def test_build_analyst_response_prefers_approved_normalized_spl() -> None:
    envelope = build_analyst_response_for_live(
        user_query="write spl",
        message="SPL validation complete. MCP execution is disabled.",
        analyst_summary=None,
        source_evidence=[],
        mitre_mappings=[],
        severity_label=None,
        synthesis_draft=None,
        human_review=None,
        candidate_spl={"candidate_spl": "search index=* earliest=-24h latest=now | stats count | head 100"},
        spl_validation={
            "approved": True,
            "normalized_spl": (
                "search index=pgcil_soc sourcetype=aws:cloudtrail earliest=-24h latest=now "
                "| stats count | head 100"
            ),
        },
    )
    assert envelope is not None
    assert envelope.spl_code == (
        "search index=pgcil_soc sourcetype=aws:cloudtrail earliest=-24h latest=now\n"
        "| stats\n"
        "    count\n"
        "| head 100"
    )
