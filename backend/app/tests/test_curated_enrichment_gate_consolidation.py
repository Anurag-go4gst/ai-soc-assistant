from __future__ import annotations

import json
from types import SimpleNamespace

from app.chat.evidence_planner import plan_evidence
from app.chat.intent_classifier import build_query_to_intent
from app.config import settings
from app.query_understanding.parser import understand_query
from app.threat.mitre_registry_enrichment import (
    registry_mitre_metadata,
    registry_mitre_metadata_for_runtime,
)
from app.use_cases.content_enrichment import (
    enrichment_spl_governance,
    enrichment_spl_governance_for_runtime,
    get_runtime_curated_enrichment,
    load_curated_enrichment_context,
)


def test_runtime_active_pilot_loads_when_curated_activation_flag_on(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)

    context = get_runtime_curated_enrichment("auth_failed_login_spike")

    assert context is not None
    assert context.use_case_id == "auth_failed_login_spike"
    assert context.runtime_support_status == "runtime_active"


def test_runtime_active_pilot_blocked_when_curated_activation_flag_off(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", False)

    assert get_runtime_curated_enrichment("auth_failed_login_spike") is None
    assert load_curated_enrichment_context("auth_failed_login_spike") is not None


def test_enrichment_only_pilot_blocked_by_runtime_wrapper(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)

    assert get_runtime_curated_enrichment("email_phishing_header_review") is None
    assert get_runtime_curated_enrichment("soc_incident_triage") is None


def test_registry_mitre_metadata_for_runtime_blocks_enrichment_only(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)

    legacy = registry_mitre_metadata(use_case_id="email_phishing_header_review")
    runtime = registry_mitre_metadata_for_runtime(use_case_id="email_phishing_header_review")

    assert legacy is not None
    assert legacy.mitre_candidate
    assert runtime is None


def test_enrichment_spl_governance_for_runtime_blocks_enrichment_only(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)

    legacy = enrichment_spl_governance("email_phishing_header_review")
    runtime = enrichment_spl_governance_for_runtime("email_phishing_header_review")

    assert legacy is not None
    assert legacy["governed_enrichment_load_allowed"] is False
    assert runtime is None


def test_legacy_enrichment_spl_governance_remains_backward_compatible() -> None:
    governance = enrichment_spl_governance("auth_failed_login_spike")

    assert governance is not None
    assert governance["use_case_id"] == "auth_failed_login_spike"
    assert governance["activation"]["planner_runtime_activation_allowed"] is True


def test_evidence_plan_uses_gated_enrichment_only(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)
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

    assert plan.enrichment_driven is True
    assert plan.use_case_id == "auth_failed_login_spike"
    assert plan.required_evidence_keys


def test_evidence_plan_emits_no_evidence_supported_mitre(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)

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
    serialized = json.dumps(plan.model_dump()).lower()

    assert "T1110.001" in plan.mitre_candidates_metadata_only
    assert "evidence_supported" not in serialized
    assert "evidence_status" not in serialized
