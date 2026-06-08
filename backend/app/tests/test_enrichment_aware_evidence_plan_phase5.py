from __future__ import annotations

import json
from types import SimpleNamespace

from app.chat.evidence_planner import plan_evidence
from app.chat.intent_classifier import build_query_to_intent
from app.config import settings
from app.query_understanding.parser import understand_query


def _enriched_plan(query: str, use_case_id: str, monkeypatch):
    monkeypatch.setattr(settings, "ai_soc_planner_path_selection_enabled", True)
    qu = understand_query(query)
    q2i = build_query_to_intent(query=query, query_understanding=qu, routed_skill="attack_discovery")
    return plan_evidence(
        q2i.intent_classification,
        query_to_intent=q2i.model_dump(),
        routed={"skill": "attack_discovery"},
        query_understanding=qu,
        selected_use_case=SimpleNamespace(use_case_id=use_case_id),
    )


def test_auth_failed_login_spike_includes_enrichment_required_evidence(monkeypatch) -> None:
    plan = _enriched_plan(
        "Investigate failed login spike for user:alice host:APP-01 from 10.0.0.8 in the last 24 hours",
        "auth_failed_login_spike",
        monkeypatch,
    )

    assert plan.enrichment_driven is True
    assert plan.use_case_id == "auth_failed_login_spike"
    assert plan.runtime_support_status == "runtime_active"
    for key in ("user", "src", "host", "fail_count", "time_window", "first_failure", "last_failure"):
        assert key in plan.required_evidence_keys
    assert "Do not claim account compromise from failed logins alone." in plan.unsupported_claims_avoid or "account_compromise" in plan.unsupported_claims_avoid
    assert plan.checklist
    assert plan.required_sources
    assert plan.limitations


def test_auth_success_after_failure_preserves_sequence_evidence_expectations(monkeypatch) -> None:
    plan = _enriched_plan(
        "Investigate successful login after failures for user:bob host:APP-02 from 10.0.0.9 in the last 24 hours",
        "auth_success_after_failure",
        monkeypatch,
    )

    for key in ("user", "src", "host", "fail_count", "success_count", "first_failure", "last_success"):
        assert key in plan.required_evidence_keys
    assert "source_ip_novelty" in plan.required_evidence_keys
    assert "source_ip_novelty" in plan.missing_required_evidence
    assert "account_compromise" in plan.unsupported_claims_avoid


def test_dns_beaconing_candidate_includes_dns_beaconing_expectations(monkeypatch) -> None:
    plan = _enriched_plan(
        "Investigate periodic DNS beaconing from host:DNS-01 to a rare domain with jitter and bytes out",
        "dns_beaconing_candidate",
        monkeypatch,
    )

    for key in ("src", "dest", "domain", "periodicity", "jitter", "bytes_out", "DNS_query_count"):
        assert key in plan.required_evidence_keys
    assert "rare_domain_indicator" in plan.required_evidence_keys
    assert "c2_confirmed" in plan.unsupported_claims_avoid
    assert "T1071" in plan.mitre_candidates_metadata_only


def test_edr_powershell_suspicious_command_includes_process_command_expectations(monkeypatch) -> None:
    plan = _enriched_plan(
        "Investigate PowerShell command line process event id with script block text and encoded command on host:WIN-01",
        "edr_powershell_suspicious_command",
        monkeypatch,
    )

    for key in ("host", "user", "command_line", "script_block_text", "event_id", "parent_process"):
        assert key in plan.required_evidence_keys
    assert "encoded_command_flag" in plan.required_evidence_keys
    assert "network_connection" in plan.required_evidence_keys
    assert "malware" in plan.unsupported_claims_avoid
    assert "T1059.001" in plan.mitre_candidates_metadata_only


def test_missing_required_evidence_triggers_hil_or_clarification(monkeypatch) -> None:
    plan = _enriched_plan("Investigate failed login spike", "auth_failed_login_spike", monkeypatch)

    assert plan.missing_required_evidence
    assert "user" in plan.missing_required_evidence
    assert plan.needs_hil is True
    assert plan.needs_clarification is True
    assert plan.requires_hil is True
    assert plan.evidence_plan_reason == "curated_enrichment_required_evidence_missing"
    assert "missing_required_curated_evidence" in plan.reasons


def test_metadata_only_row_does_not_create_runtime_evidence_plan(monkeypatch) -> None:
    plan = _enriched_plan("Investigate suspicious email headers", "email_phishing_header_review", monkeypatch)

    assert plan.enrichment_driven is False
    assert plan.required_evidence_keys == []
    assert plan.missing_required_evidence == []
    assert plan.runtime_support_status == "metadata_only"
    assert plan.evidence_plan_reason == "curated_enrichment_not_runtime_active"


def test_enrichment_only_pilot_does_not_become_runtime_active(monkeypatch) -> None:
    plan = _enriched_plan("Triage this incident with the IR playbook", "soc_incident_triage", monkeypatch)

    assert plan.enrichment_driven is False
    assert plan.use_case_id == "soc_incident_triage"
    assert plan.runtime_support_status == "metadata_only"
    assert plan.required_evidence_keys == []


def test_mitre_candidates_remain_metadata_only_and_no_evidence_status_emitted(monkeypatch) -> None:
    plan = _enriched_plan(
        "Investigate failed login spike for user:alice host:APP-01 from 10.0.0.8 in the last 24 hours",
        "auth_failed_login_spike",
        monkeypatch,
    )
    payload = plan.model_dump()
    serialized = json.dumps(payload).lower()

    assert "T1110.001" in plan.mitre_candidates_metadata_only
    assert "evidence_supported" not in serialized
    assert "evidence_status" not in serialized


def test_flag_off_preserves_current_evidence_plan_behavior(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_planner_path_selection_enabled", False)
    query = "Investigate failed login spike for user:alice host:APP-01 from 10.0.0.8 in the last 24 hours"
    qu = understand_query(query)
    q2i = build_query_to_intent(query=query, query_understanding=qu, routed_skill="attack_discovery")

    plan = plan_evidence(
        q2i.intent_classification,
        query_to_intent=q2i.model_dump(),
        routed={"skill": "attack_discovery"},
        query_understanding=qu,
        selected_use_case=SimpleNamespace(use_case_id="auth_failed_login_spike"),
    )

    assert plan.enrichment_driven is False
    assert plan.required_evidence_keys == []
    assert plan.missing_required_evidence == []
    assert plan.use_case_id is None
    assert plan.runtime_support_status is None
