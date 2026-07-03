from __future__ import annotations

from pathlib import Path

import pytest

from app.chat.contracts.answer_contract import AnswerContract, build_answer_contract
from app.config import settings
from app.llm.clients import ChatResult, LocalChatError
from app.schemas.responses import AnalystResponseEnvelope
from app.synthesis.governed_answer_composer import (
    build_composer_prompt,
    build_composer_runtime_status,
    compose_governed_answer,
    composer_is_enabled,
    validate_composed_prose,
)


class _StubClient:
    def __init__(self, *, text: str = "", raises: bool = False, finish_reason: str | None = None) -> None:
        self._text = text
        self._raises = raises
        self._finish_reason = finish_reason
        self.calls = 0
        self.last_prompt = ""

    def generate(self, *, system_prompt: str, user_prompt: str, max_tokens: int, temperature: float) -> ChatResult:
        self.calls += 1
        self.last_prompt = user_prompt
        if self._raises:
            raise LocalChatError("transport_error:Boom")
        return ChatResult(
            text=self._text,
            model="stub-model",
            latency_ms=12,
            usage={"total_tokens": 5},
            finish_reason=self._finish_reason,
        )


def _contract(**overrides) -> AnswerContract:
    payload = {
        "intent_classification": {
            "intent_family": "hybrid_alert_review",
            "answer_goal": ["severity_assessment", "mitre_mapping", "spl_artifact"],
        },
        "evidence_plan": {
            "answer_mode": "live_investigation",
            "needs_mitre": True,
            "spl_allowed": True,
            "mcp_allowed": False,
            "requires_hil": True,
            "missing_required_evidence": ["mfa_status"],
            "limitations": ["Do not claim account compromise from failed logins alone."],
            "checklist": ["Confirm source IP ownership."],
            "unsupported_claims_avoid": ["account_compromise"],
            "answer_rules": ["Use candidate language until execution evidence exists."],
        },
        "mitre_decision": {"answer_visible": True, "not_claimed": ["T1003"]},
        "severity_decision": type("Severity", (), {"severity_label": "P2 High", "missing_evidence": []})(),
        "spl_validation": {
            "approved": True,
            "normalized_spl": "search index=pgcil_soc earliest=-1h latest=now | stats count | head 100",
            "review_required": True,
        },
        "execution": {"status": "skipped", "block_reason": "mcp_not_allowed_by_evidence_plan"},
        "human_review": {"required": False},
        "mitre_mappings": [{"technique_id": "T1110.001"}],
        "mitre_branch_result": {
            "branch_authority": "planner_mitre_branch",
            "candidate_mitre": ["T1078"],
            "evidence_supported_mitre": ["T1110.001"],
            "requires_validation_mitre": [],
            "not_claimed_mitre": ["T1003"],
            "ruled_out_mitre": [],
        },
        "candidate_spl": {"assumptions": ["Template output is review-only."]},
    }
    payload.update(overrides)
    return build_answer_contract(**payload)


def _envelope(**overrides) -> AnalystResponseEnvelope:
    payload = {
        "severity_label": "P2 High",
        "one_sentence_finding": "Deterministic Phase 8 summary with missing evidence and limitations.",
        "direct_answer_summary": "Deterministic Phase 8 summary with missing evidence and limitations.",
        "limitations": ["Do not claim account compromise from failed logins alone."],
        "missing_evidence": ["mfa_status"],
        "mitre_mappings": [{"Technique": "T1110.001", "Status": "Evidence Supported"}],
        "spl_code": "search index=pgcil_soc earliest=-1h latest=now | stats count | head 100",
        "execution_status_label": "Review only — not executed",
    }
    payload.update(overrides)
    return AnalystResponseEnvelope.model_validate(payload)


def _projection() -> dict:
    return {
        "use_case_id": "auth_success_after_failure",
        "analyst_checklist": ["Confirm source IP ownership."],
        "answer_rules": ["Use candidate language until execution evidence exists."],
        "limitations": ["Do not claim account compromise from failed logins alone."],
        "mitre_candidates_metadata_only": ["T1110.001", "T1078"],
    }


def _enable_composer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_final_synthesis_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_live_synthesis_enabled", True)


def test_runtime_status_reports_flags_and_provider_without_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_final_synthesis_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_llm_live_synthesis_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "mock")

    status = build_composer_runtime_status()

    assert status["control_plane_enabled"] is True
    assert status["ai_soc_llm_final_synthesis_enabled"] is False
    assert status["ai_soc_llm_live_synthesis_enabled"] is False
    assert status["composer_is_enabled"] is False
    assert status["provider_configured"] is False
    assert status["provider_skip_reason"] == "no_provider_configured"
    assert "api_key" not in str(status).lower()


def test_flags_off_returns_deterministic_phase8_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_llm_final_synthesis_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_llm_live_synthesis_enabled", False)

    fallback = _envelope()
    result = compose_governed_answer(
        contract=_contract(),
        enrichment_projection=_projection(),
        fallback_envelope=fallback,
        client=_StubClient(text="Unsafe invented prose."),
    )

    assert result.envelope.direct_answer_summary == fallback.direct_answer_summary
    assert result.llm_composer_enabled is False
    assert result.llm_composer_used is False
    assert result.llm_guard_status == "disabled"
    assert result.llm_fallback_used is False
    assert composer_is_enabled() is False


def test_prompt_uses_answer_contract_and_projection_only() -> None:
    contract = _contract()
    prompt = build_composer_prompt(contract, _projection())

    assert "AnswerContract, RunContract, FinalEvidenceGate" in prompt
    assert "Do not claim live results" in prompt
    assert "Missing evidence: mfa_status" in prompt
    assert "Do not claim account compromise" in prompt
    assert "Candidate MITRE (metadata only; never evidence-supported): T1078 (Valid Accounts)" in prompt
    assert (
        "Evidence-supported MITRE (only these may be called evidence-supported): "
        "T1110.001 (Password Guessing)" in prompt
    )
    assert "Authoritative MITRE names" in prompt
    assert "SPL status: ready_for_review" in prompt
    assert "Review only" in prompt or "Execution status" in prompt
    assert "skill.md" not in prompt.lower()
    assert "github.com" not in prompt.lower()


def test_sop_prompt_omits_live_investigation_fields() -> None:
    contract = build_answer_contract(
        intent_classification={
            "intent_family": "sop_or_playbook",
            "answer_goal": ["policy_citation", "procedural_steps"],
        },
        evidence_plan={"answer_mode": "rag_only", "spl_allowed": False, "mcp_allowed": False},
        mitre_decision={"answer_visible": True},
        severity_decision=type("Severity", (), {"severity_label": "P3 Medium", "missing_evidence": []})(),
        spl_validation=None,
        execution={"status": "skipped"},
        human_review={"required": False},
        mitre_mappings=[{"technique_id": "T1110.001"}],
    )

    prompt = build_composer_prompt(contract, {"analyst_checklist": ["Review approved SOP steps."]})

    assert "AnswerContract, RunContract, FinalEvidenceGate" in prompt
    assert "Do not claim live results" in prompt
    assert "Answer mode: governed SOP / knowledge recall." in prompt
    assert "Severity" not in prompt
    assert "MITRE" not in prompt
    assert "SPL status" not in prompt
    assert "HIL status" not in prompt
    assert "Human review" not in prompt


def test_sop_profile_skips_live_composer_even_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_composer(monkeypatch)
    contract = build_answer_contract(
        intent_classification={
            "intent_family": "sop_or_playbook",
            "answer_goal": ["policy_citation", "procedural_steps"],
        },
        evidence_plan={"answer_mode": "rag_only", "spl_allowed": False, "mcp_allowed": False},
        mitre_decision={"answer_visible": False},
        severity_decision=None,
        spl_validation=None,
        execution={"status": "skipped"},
        human_review={"required": False},
    )
    fallback = AnalystResponseEnvelope(
        response_profile="knowledge_recall",
        direct_answer_summary="Governed SOP retrieved. SPL and MCP were skipped as requested.",
    )
    client = _StubClient(
        text=(
            "The security event under review indicates that an unauthorized IP address attempted "
            "to connect to a sensitive server."
        )
    )

    result = compose_governed_answer(
        contract=contract,
        enrichment_projection=None,
        fallback_envelope=fallback,
        client=client,
    )

    assert client.calls == 0
    assert result.llm_composer_enabled is True
    assert result.llm_composer_used is False
    assert result.llm_guard_status == "skipped"
    assert result.envelope.direct_answer_summary == fallback.direct_answer_summary


def test_endpoint_and_dns_prompts_do_not_contain_auth_limitations() -> None:
    auth_phrases = ("privilege status", "asset criticality", "source ip ownership", "mfa", "post-login")
    cases = [
        (
            "edr_powershell_suspicious_command",
            ["command_line", "parent_process"],
            ["Encoded command is a suspicious indicator, not a standalone malware verdict."],
            ["Review Event ID 4104, script block text, parent process, and command line."],
        ),
        (
            "dns_beaconing_candidate",
            ["domain", "periodicity", "jitter"],
            ["Beaconing requires periodicity, jitter, and destination reputation validation."],
            ["Review DNS query cadence, destination rarity, byte profile, and host association."],
        ),
    ]
    for use_case_id, missing, limitations, checklist in cases:
        contract = build_answer_contract(
            intent_classification={
                "intent_family": "hybrid_alert_review",
                "answer_goal": ["spl_artifact", "mitre_mapping", "analyst_action_guidance"],
            },
            evidence_plan={
                "answer_mode": "hybrid",
                "spl_allowed": True,
                "mcp_allowed": False,
                "use_case_id": use_case_id,
                "missing_required_evidence": missing,
                "limitations": limitations,
                "checklist": checklist,
            },
            mitre_decision={"answer_visible": True},
            severity_decision=type(
                "Severity",
                (),
                {"severity_label": "P2 High", "missing_evidence": ["mfa_status", "post_login_activity"]},
            )(),
            spl_validation={
                "approved": False,
                "review_required": True,
                "review_required_reason": "spl_template_active_source_profile_missing",
                "spl_template_status": "active",
            },
            execution={"status": "skipped"},
            human_review={"required": False},
            use_case_id=use_case_id,
        )

        prompt = build_composer_prompt(contract, None).lower()

        for phrase in auth_phrases:
            assert phrase not in prompt


def test_active_template_missing_source_profile_wording_is_required() -> None:
    contract = _contract(
        spl_validation={
            "approved": False,
            "normalized_spl": None,
            "review_required": True,
            "review_required_reason": "spl_template_active_source_profile_missing",
            "spl_template_status": "active",
            "reject_reasons": ["missing_index"],
        },
        candidate_spl={"template_id": "edr_powershell_suspicious_command"},
        execution={"status": "skipped"},
    )

    prompt = build_composer_prompt(contract, None)

    assert "template_status=active" in prompt
    assert "block_reason=spl_template_active_source_profile_missing" in prompt
    assert "governed SPL template is active" in prompt

    ok, reason = validate_composed_prose(
        "No active governed SPL template is available for this use case. Missing evidence includes mfa_status. "
        "Do not claim account compromise from failed logins alone.",
        contract,
    )
    assert ok is False
    assert "active SPL template" in (reason or "")

    ok, reason = validate_composed_prose(
        "The governed SPL template is active, but source profile is missing, so SPL generation is "
        "blocked/review-required until index and sourcetype are confirmed. Missing evidence includes "
        "mfa_status. Do not claim account compromise from failed logins alone.",
        contract,
    )
    assert ok is True
    assert reason is None


def test_not_claimed_mitre_is_not_ruled_out_wording() -> None:
    contract = _contract(
        mitre_branch_result={
            "branch_authority": "planner_mitre_branch",
            "candidate_mitre": ["T1078"],
            "evidence_supported_mitre": [],
            "requires_validation_mitre": [],
            "not_claimed_mitre": ["T1003"],
            "ruled_out_mitre": ["T1562.001"],
        },
        mitre_mappings=[],
    )

    bad, bad_reason = validate_composed_prose(
        "T1078 remains candidate. T1003 is ruled out. T1562.001 is ruled out. "
        "Missing evidence includes mfa_status. Do not claim account compromise from failed logins alone. "
        "Review only — not executed.",
        contract,
    )
    assert bad is False
    assert "T1003" in (bad_reason or "")

    good, good_reason = validate_composed_prose(
        "T1078 remains candidate. T1003 is not claimed due to insufficient supporting evidence. "
        "T1562.001 is ruled out by available evidence. Missing evidence includes mfa_status. "
        "Do not claim account compromise from failed logins alone. Review only — not executed.",
        contract,
    )
    assert good is True
    assert good_reason is None


def test_candidate_mitre_remains_candidate_in_guard() -> None:
    contract = _contract()
    ok, reason = validate_composed_prose(
        "T1078 is evidence-supported valid account abuse.",
        contract,
    )
    assert ok is False
    assert reason is not None
    assert "T1078" in reason


def test_evidence_supported_mitre_allowed_when_contract_has_it() -> None:
    contract = _contract()
    ok, reason = validate_composed_prose(
        "T1110.001 is evidence-supported password guessing; missing evidence includes mfa_status. "
        "Do not claim account compromise from failed logins alone.",
        contract,
    )
    assert ok is True
    assert reason is None


def test_compromise_claim_without_support_is_blocked() -> None:
    contract = _contract()
    ok, reason = validate_composed_prose(
        "This is confirmed account compromise.",
        contract,
    )
    assert ok is False
    assert "compromise" in (reason or "").lower()


def test_spl_executed_claim_is_blocked() -> None:
    contract = _contract()
    ok, reason = validate_composed_prose(
        "The SPL was executed in Splunk and returned results.",
        contract,
    )
    assert ok is False
    assert "execution" in (reason or "").lower()


def test_spl_approval_claim_is_blocked() -> None:
    contract = _contract()
    ok, reason = validate_composed_prose(
        "The SPL is approved for execution now.",
        contract,
    )
    assert ok is False
    assert "approval" in (reason or "").lower()


def test_invented_severity_is_blocked() -> None:
    contract = _contract()
    ok, reason = validate_composed_prose(
        "This is a P1 critical incident requiring immediate action.",
        contract,
    )
    assert ok is False
    assert "severity" in (reason or "").lower()


def test_ignored_hil_status_is_blocked() -> None:
    contract = _contract(
        human_review={"required": True, "review_type": "analyst_review"},
        evidence_plan={
            "answer_mode": "live_investigation",
            "needs_mitre": True,
            "spl_allowed": True,
            "mcp_allowed": False,
            "requires_hil": True,
            "missing_required_evidence": [],
            "limitations": [],
            "checklist": [],
            "unsupported_claims_avoid": [],
            "answer_rules": [],
        },
    )
    ok, reason = validate_composed_prose(
        "Everything is ready and no further action is needed.",
        contract,
    )
    assert ok is False
    assert "review" in (reason or "").lower()


def test_removed_missing_evidence_and_limitations_is_blocked() -> None:
    contract = _contract()
    ok, reason = validate_composed_prose(
        "All evidence is complete and no caveats apply.",
        contract,
    )
    assert ok is False
    assert reason is not None


def test_raw_github_content_is_not_present_in_prompt_or_guard() -> None:
    contract = _contract(
        evidence_plan={
            "answer_mode": "live_investigation",
            "missing_required_evidence": ["mfa_status"],
            "limitations": ["Do not claim account compromise from failed logins alone."],
            "checklist": ["https://github.com/example/repo/skills/SKILL.md"],
            "unsupported_claims_avoid": ["account_compromise"],
            "answer_rules": [],
        }
    )
    prompt = build_composer_prompt(contract, None)
    assert "github.com" not in prompt.lower()
    assert "skill.md" not in prompt.lower()

    ok, reason = validate_composed_prose(
        "See https://github.com/example/repo/skills/SKILL.md for details.",
        contract,
    )
    assert ok is False
    assert "github" in (reason or "").lower() or "skill.md" in (reason or "").lower()


def test_guard_failure_uses_deterministic_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_composer(monkeypatch)
    fallback = _envelope()
    client = _StubClient(text="T1078 is evidence-supported valid account abuse.")
    result = compose_governed_answer(
        contract=_contract(),
        enrichment_projection=_projection(),
        fallback_envelope=fallback,
        client=client,
    )

    assert client.calls == 1
    assert result.llm_composer_used is False
    assert result.llm_guard_status == "blocked"
    assert result.llm_fallback_used is True
    assert result.envelope.direct_answer_summary == fallback.direct_answer_summary


def test_composer_sanitizes_before_display(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_composer(monkeypatch)
    fallback = _envelope()
    safe_text = (
        "T1110.001 is evidence-supported password guessing. Missing evidence includes mfa_status. "
        "Do not claim account compromise from failed logins alone. Review only — not executed."
    )
    client = _StubClient(
        text=(
            "<think>private chain</think>\n"
            "The user is asking about failed logins.\n\n"
            f"{safe_text}"
        )
    )

    result = compose_governed_answer(
        contract=_contract(),
        enrichment_projection=_projection(),
        fallback_envelope=fallback,
        client=client,
    )

    assert result.llm_composer_used is True
    assert result.envelope.direct_answer_summary == safe_text
    assert "removed_think_block" in (result.sanitizer_notes or [])
    assert "removed_reasoning_preamble" in (result.sanitizer_notes or [])


def test_composer_length_finish_reason_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_composer(monkeypatch)
    fallback = _envelope()
    client = _StubClient(text="Partial governed answer", finish_reason="length")

    result = compose_governed_answer(
        contract=_contract(),
        enrichment_projection=_projection(),
        fallback_envelope=fallback,
        client=client,
    )

    assert result.llm_composer_used is False
    assert result.llm_guard_status == "blocked"
    assert result.llm_fallback_used is True
    assert result.llm_finish_reason == "length"
    assert "governed_synthesis_truncated" in (result.llm_blocked_reason or "")
    assert result.envelope.direct_answer_summary == fallback.direct_answer_summary


def test_failed_login_bad_prose_blocks_t1078_evidence_supported_upgrade() -> None:
    contract = _contract()
    bad = (
        "The MITRE techniques identified with supporting evidence are "
        "T1110.001 (Password Policy Discovery) and T1078 (Valid Accounts)."
    )
    ok, reason = validate_composed_prose(bad, contract)
    assert ok is False
    assert reason is not None
    assert "T1078" in reason


def test_failed_login_bad_prose_blocks_wrong_t1110_name() -> None:
    contract = _contract()
    bad = (
        "The MITRE techniques identified with supporting evidence are "
        "T1110.001 (Password Policy Discovery) and T1078 (Valid Accounts)."
    )
    ok, reason = validate_composed_prose(bad, contract)
    assert ok is False
    assert reason is not None
    assert (
        "Password Policy Discovery" in reason
        or "Password Guessing" in reason
        or "T1078" in reason
    )


def test_guard_blocks_supporting_evidence_wording_for_candidate_only_mitre() -> None:
    contract = _contract()
    ok, reason = validate_composed_prose(
        "T1078 (Valid Accounts) is identified with supporting evidence for this alert.",
        contract,
    )
    assert ok is False
    assert reason is not None
    assert "T1078" in reason


def test_guard_blocks_mismatched_mitre_technique_name() -> None:
    contract = _contract()
    ok, reason = validate_composed_prose(
        "T1110.001 (Password Policy Discovery) is evidence-supported. "
        "Missing evidence includes mfa_status. "
        "Do not claim account compromise from failed logins alone.",
        contract,
    )
    assert ok is False
    assert reason is not None
    assert (
        "Password Policy Discovery" in reason
        or "Password Guessing" in reason
        or "T1078" in reason
    )


def test_missing_evidence_prose_must_match_contract_fields() -> None:
    contract = _contract()
    ok, reason = validate_composed_prose(
        "T1110.001 is evidence-supported password guessing. Missing evidence includes privilege status "
        "and post-login activity. Do not claim account compromise from failed logins alone.",
        contract,
    )
    assert ok is False
    assert reason is not None
    lowered = (reason or "").lower()
    assert "privilege" in lowered or "post-login" in lowered or "post_login" in lowered


def test_analyst_response_card_does_not_duplicate_spl_status_heading() -> None:
    source = Path(__file__).resolve().parents[3] / "frontend/src/components/AnalystResponseCard.tsx"
    assert "<SectionTitle>SPL status</SectionTitle>" not in source.read_text(encoding="utf-8")
    assert "'SPL status'" in source.read_text(encoding="utf-8")


def test_failed_login_safe_prose_uses_password_guessing_and_keeps_t1078_candidate() -> None:
    contract = _contract()
    ok, reason = validate_composed_prose(
        "T1110.001 (Password Guessing) is evidence-supported. T1078 (Valid Accounts) remains candidate. "
        "Missing evidence includes mfa_status. Do not claim account compromise from failed logins alone. "
        "Review only — not executed.",
        contract,
    )
    assert ok is True
    assert reason is None


def test_successful_compose_replaces_direct_answer_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_composer(monkeypatch)
    fallback = _envelope()
    safe_text = (
        "T1110.001 is evidence-supported password guessing. Missing evidence includes mfa_status. "
        "Do not claim account compromise from failed logins alone. Review only — not executed."
    )
    client = _StubClient(text=safe_text)
    result = compose_governed_answer(
        contract=_contract(),
        enrichment_projection=_projection(),
        fallback_envelope=fallback,
        client=client,
    )

    assert result.llm_composer_used is True
    assert result.llm_guard_status == "passed"
    assert result.llm_fallback_used is False
    assert result.envelope.direct_answer_summary == safe_text
    assert "github.com" not in client.last_prompt.lower()
