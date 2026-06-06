from __future__ import annotations

import pytest

from app.chat import pipeline as chat_pipeline
from app.spl.llm_fallback import LlmSplFallbackResult
from app.threat.mitre_decision import resolve_mitre_decision
from app.threat.mitre_registry_schema import MitreRegistryMetadata
from app.use_cases.content_enrichment import enrichment_spl_governance


def _intent() -> dict:
    return {
        "intent_family": "mitre_mapping",
        "answer_goal": ["mitre_mapping"],
        "requires_clarification": False,
    }


def _plan() -> dict:
    return {"answer_mode": "live_investigation"}


def _decision(use_case_id: str, present: list[str], candidates: list[str] | None = None):
    return resolve_mitre_decision(
        use_case_id=use_case_id,
        registry_metadata=MitreRegistryMetadata(
            mitre_candidate=candidates or [],
            mitre_requires_evidence=True,
            mitre_requires_alert_context=False,
            mapping_rationale="test",
        )
        if candidates is not None
        else None,
        intent_classification=_intent(),
        evidence_plan=_plan(),
        source_refs=["ev-1"],
        alert_context_present=True,
        negative_evidence={"present_evidence": present},
    )


def test_failed_login_spike_supports_bruteforce_but_not_valid_accounts() -> None:
    decision = _decision("auth_failed_login_spike", ["failed_login_pattern"])

    assert decision.evidence_statuses["T1110"] == "evidence_supported"
    assert decision.evidence_statuses["T1110.001"] == "evidence_supported"
    assert decision.evidence_statuses["T1110.003"] == "candidate"
    assert "T1078" in decision.rejected_techniques
    assert all(item["technique_id"] != "T1078" for item in decision.techniques)


def test_success_after_failures_supports_t1110_but_t1078_stays_candidate() -> None:
    decision = _decision(
        "auth_success_after_failure",
        ["failed_login_pattern", "successful_login"],
    )

    assert decision.evidence_statuses["T1110.001"] == "evidence_supported"
    assert decision.evidence_statuses["T1078"] == "candidate"
    assert next(item for item in decision.techniques if item["technique_id"] == "T1078")[
        "why"
    ].startswith("Successful login after repeated failures")


def test_success_after_failures_supports_t1078_only_with_stronger_misuse_evidence() -> None:
    decision = _decision(
        "auth_success_after_failure",
        ["failed_login_pattern", "successful_login", "source_ip_novelty"],
    )

    assert decision.evidence_statuses["T1078"] == "evidence_supported"


def test_powershell_status_requires_command_or_script_evidence() -> None:
    candidate = _decision("edr_powershell_suspicious_command", [])
    supported = _decision(
        "edr_powershell_suspicious_command",
        ["powershell_command_evidence", "encoded_command"],
    )

    assert candidate.evidence_statuses["T1059.001"] == "candidate"
    assert supported.evidence_statuses["T1059.001"] == "evidence_supported"


def test_phishing_single_sender_mismatch_is_candidate_only() -> None:
    single = _decision(
        "email_phishing_header_review",
        ["sender_return_path_mismatch"],
    )
    supported = _decision(
        "email_phishing_header_review",
        ["sender_return_path_mismatch", "email_auth_failure"],
    )

    assert single.evidence_statuses["T1566"] == "candidate"
    assert supported.evidence_statuses["T1566"] == "evidence_supported"


def test_c2_requires_multiple_beaconing_signals() -> None:
    single = _decision("dns_beaconing_candidate", ["periodicity", "network_telemetry"])
    supported = _decision("dns_beaconing_candidate", ["periodicity", "jitter_profile", "network_telemetry"])

    assert single.evidence_statuses["T1071"] == "candidate"
    assert supported.evidence_statuses["T1071"] == "evidence_supported"


def test_ransomware_requires_multiple_impact_signals() -> None:
    single = _decision("endpoint_ransomware_impact_review", ["file_rename_volume"])
    supported = _decision(
        "endpoint_ransomware_impact_review",
        ["file_rename_volume", "extension_pattern", "process_evidence"],
    )

    assert single.evidence_statuses["T1486"] == "candidate"
    assert supported.evidence_statuses["T1486"] == "evidence_supported"


def test_mitre_permitted_metadata_is_not_evidence() -> None:
    decision = resolve_mitre_decision(
        use_case_id="auth_failed_login_spike",
        registry_metadata=MitreRegistryMetadata(
            mitre_permitted=["T1110.001"],
            mitre_requires_evidence=True,
            mitre_requires_alert_context=False,
            mapping_rationale="permitted metadata only",
        ),
        intent_classification=_intent(),
        evidence_plan=_plan(),
        source_refs=["ev-1"],
        alert_context_present=True,
        negative_evidence={"present_evidence": []},
    )

    assert decision.registry_metadata is not None
    assert decision.registry_metadata.registry_role == "metadata_not_evidence"
    assert decision.evidence_statuses["T1110.001"] == "candidate"


class _Telemetry:
    def record_step(self, *a, **k) -> None: ...
    def record_spl_validation(self, *a, **k) -> None: ...


class _Profile:
    def model_dump(self) -> dict:
        return {}


def test_active_enriched_template_status_is_visible() -> None:
    out = chat_pipeline._candidate_from_default_template(
        trace_id="t",
        skill="attack_discovery",
        user_query="generate SPL for failed logins by source ip",
        template_id="auth_failed_login_spike",
        spl_governance=enrichment_spl_governance("auth_failed_login_spike"),
    )
    candidate, validation = out

    assert candidate is not None
    assert validation is not None
    assert candidate["spl_template_status"] == "active"
    assert validation["spl_template_status"] == "active"
    assert validation["approved"] is True
    assert validation["normalized_spl"]


def test_planned_enriched_template_status_blocks_free_spl_fallback() -> None:
    governance = enrichment_spl_governance("dns_beaconing_candidate")
    candidate, validation = chat_pipeline._candidate_clarification(
        trace_id="t",
        skill="attack_discovery",
        user_query="investigate periodic DNS beaconing with jitter",
        telemetry=_Telemetry(),
        profile=_Profile(),
        reason=str(governance["governed_limitation"]),
        spl_governance=governance,
    )

    assert candidate is not None
    assert validation is not None
    assert candidate["candidate_spl"] == ""
    assert candidate["spl_template_status"] == "planned"
    assert validation["approved"] is False
    assert validation["normalized_spl"] is None
    assert validation["governed_limitation"] == "spl_template_planned_no_free_spl_fallback"


def test_llm_fallback_cannot_bypass_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_llm_spl_fallback_enabled", True)
    bad = "search index=pgcil_soc sourcetype=pgcil:auth earliest=-60m latest=now | delete"
    monkeypatch.setattr(
        "app.chat.pipeline.generate_llm_spl_fallback",
        lambda *, user_query: LlmSplFallbackResult(
            candidate_spl=bad,
            approved=False,
            validation={
                "approved": False,
                "normalized_spl": None,
                "reject_reasons": ["blocked_command:delete"],
                "warnings": [],
                "enforced_limits": {},
                "policy_version": "v1",
            },
            clarification_required=True,
            clarification_reason="llm_spl_fallback_validation_failed",
        ),
    )

    candidate, validation = chat_pipeline._candidate_from_llm_fallback(
        trace_id="t",
        skill="spl_generation",
        user_query="x",
        telemetry=_Telemetry(),
        profile=_Profile(),
        spl_governance=enrichment_spl_governance("auth_failed_login_spike"),
    )

    assert candidate["execution_eligible"] is False
    assert validation["approved"] is False
    assert validation["normalized_spl"] is None
    assert "blocked_command:delete" in validation["reject_reasons"]
