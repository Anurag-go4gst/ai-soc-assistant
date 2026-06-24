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


def test_build_analyst_response_from_splunk_and_rag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Source-grounded splunk_mcp execution may render evidence-supported MITRE display."""
    monkeypatch.setattr("app.chat.analyst_response_builder.settings.control_plane_enabled", True)
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


def test_build_analyst_response_prefers_approved_normalized_spl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.chat.analyst_response_builder.settings.control_plane_enabled", True)
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


# --- C.2: single SPL surface (B15) + ambiguous routing (R1) -------------------
def _minimal_envelope(**overrides):
    base = dict(
        user_query="Which hosts generated the most DNS queries?",
        message="msg",
        analyst_summary="summary",
        source_evidence=[],
        mitre_mappings=[],
        severity_label=None,
        synthesis_draft=None,
        human_review=None,
    )
    base.update(overrides)
    return build_analyst_response_for_live(**base)


def test_b15_candidate_spl_suppresses_lab_draft():
    envelope = _minimal_envelope(
        candidate_spl={
            "candidate_spl": "search index=<dns_index> sourcetype=<dns_sourcetype> query=* | stats count by src_host | head 100",
            "generation_mode": "llm_spl_advisory_fallback",
        },
        spl_draft_preview={"draft_spl": "search index=<network_index> | stats count by src | head 100"},
    )
    assert envelope is not None
    assert envelope.spl_code is not None
    # Lab draft suppressed — single SPL surface (LLM lane).
    assert envelope.draft_spl_code is None
    assert envelope.spl_draft_preview is None


def test_b15_governed_template_keeps_draft_surfaces():
    # Governed template SPL is out of B15 scope — existing surfaces unchanged.
    envelope = _minimal_envelope(
        candidate_spl={
            "candidate_spl": "search index=<edr_index> foo | stats count by host | head 100",
            "generation_mode": "deterministic_template_render",
        },
        spl_draft_preview={"draft_spl": "search index=<edr_index> | stats count by host | head 100"},
    )
    assert envelope is not None
    assert envelope.draft_spl_code is not None  # not suppressed for governed templates


def test_b15_draft_kept_as_last_resort_when_llm_failed():
    envelope = _minimal_envelope(
        candidate_spl={"candidate_spl": "", "llm_fallback_used": True, "llm_fallback_status": "clarification_required"},
        spl_draft_preview={"draft_spl": "search index=<dns_index> query=* | stats count by src_host | head 100"},
    )
    assert envelope is not None
    # No candidate SPL exposed -> draft survives as the last-resort surface.
    assert envelope.draft_spl_code is not None
    assert envelope.spl_draft_preview is not None
    assert envelope.spl_draft_preview.get("fallback_after_llm") is True


def test_r1_ambiguous_families_helper():
    from app.spl.draft_preview import candidate_detection_families

    ambiguous = candidate_detection_families("Which hosts generate the most SMB traffic and biggest uploads?")
    assert len(ambiguous) > 1  # SMB top-talkers + exfil/lateral both plausible
    single = candidate_detection_families("Which hosts generated the most DNS queries?")
    assert len(single) <= 1


def test_recommended_actions_from_draft_unglues_p2review() -> None:
    from app.chat.analyst_response_builder import _recommended_actions_from_draft

    actions = _recommended_actions_from_draft(
        {
            "recommended_actions": [
                "P2Review failed-login volume and source distribution.",
            ]
        }
    )
    assert actions
    assert "P2Review" not in " ".join(actions)
    assert actions[0].startswith("P2 —")
