from __future__ import annotations

from app.api.routes_chat import chat
from app.chat.contracts.answer_contract import build_answer_contract
from app.schemas.requests import ChatRequest


def _branch(**overrides) -> dict:
    payload = {
        "branch_authority": "planner_mitre_branch",
        "candidate_mitre": ["T1078"],
        "evidence_supported_mitre": ["T1110.001"],
        "requires_validation_mitre": ["T1059.001"],
        "not_claimed_mitre": ["T1003"],
        "ruled_out_mitre": ["T1562.001"],
    }
    payload.update(overrides)
    return payload


def _contract(**overrides):
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
            "checklist": [
                "Confirm source IP ownership.",
                "raw GitHub SKILL.md content should be removed",
                "https://github.com/example/repo/skills/SKILL.md",
            ],
            "unsupported_claims_avoid": ["account_compromise", "credential_dumping"],
            "answer_rules": ["Use candidate language until execution evidence exists."],
        },
        "mitre_decision": {"answer_visible": True, "not_claimed": ["T1003"]},
        "severity_decision": type(
            "Severity",
            (),
            {"severity_label": "P2 High", "missing_evidence": ["source_ownership"]},
        )(),
        "spl_validation": {
            "approved": True,
            "normalized_spl": "search index=pgcil_soc sourcetype=pgcil:auth earliest=-1h latest=now | stats count | head 100",
            "review_required": True,
        },
        "execution": {"status": "skipped", "block_reason": "mcp_not_allowed_by_evidence_plan"},
        "human_review": {"required": False},
        "mitre_mappings": [{"technique_id": "T1110.001"}],
        "mitre_branch_result": _branch(),
        "candidate_spl": {"assumptions": ["Template output is review-only."]},
    }
    payload.update(overrides)
    return build_answer_contract(**payload)


def test_missing_evidence_appears_in_answer_contract() -> None:
    contract = _contract()

    assert contract.missing_evidence == ["mfa_status", "source_ownership"]


def test_limitations_appear_in_answer_contract() -> None:
    contract = _contract()

    assert contract.limitations == ["Do not claim account compromise from failed logins alone."]
    assert contract.answer_rules_applied == ["Use candidate language until execution evidence exists."]


def test_analyst_checklist_is_safe_and_sanitized() -> None:
    contract = _contract()

    assert contract.analyst_checklist_safe == ["Confirm source IP ownership."]
    assert "SKILL.md" not in " ".join(contract.analyst_checklist_safe)
    assert "github.com" not in " ".join(contract.analyst_checklist_safe)


def test_unsupported_claims_avoid_is_carried_into_contract() -> None:
    contract = _contract()

    assert contract.unsupported_claims_avoid == ["account_compromise", "credential_dumping"]
    assert contract.assumptions == ["Template output is review-only."]


def test_candidate_and_evidence_supported_mitre_are_separated() -> None:
    contract = _contract()

    assert contract.candidate_mitre == ["T1078"]
    assert contract.evidence_supported_mitre == ["T1110.001"]
    assert contract.requires_validation_mitre == ["T1059.001"]
    assert contract.not_claimed_mitre == ["T1003"]
    assert contract.ruled_out_mitre == ["T1562.001"]


def test_metadata_only_mitre_does_not_become_evidence_supported() -> None:
    contract = _contract(
        mitre_branch_result=_branch(
            candidate_mitre=["T1566"],
            evidence_supported_mitre=[],
            metadata_only_candidates=["T1566"],
        ),
        mitre_mappings=[],
        mitre_decision={"answer_visible": False},
    )

    assert contract.candidate_mitre == ["T1566"]
    assert contract.evidence_supported_mitre == []


def test_spl_status_reflects_phase6_review_and_block_status() -> None:
    ready = _contract()
    blocked = _contract(
        spl_validation={
            "approved": False,
            "normalized_spl": None,
            "review_required": True,
            "reject_reasons": ["spl_template_not_allowed_by_enrichment"],
        },
        execution={"status": "skipped"},
    )

    assert ready.spl_status == "ready_for_review"
    assert blocked.spl_status == "review_required"


def test_spl_status_detail_is_canonical_and_consistent_for_active_template_block() -> None:
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

    detail = contract.spl_status_detail

    assert detail is not None
    assert detail["template_status"] == "active"
    assert detail["generation_status"] == "blocked"
    assert detail["review_required"] is True
    assert detail["block_reason"] == "spl_template_active_source_profile_missing"
    assert "index" in detail["required_fields"]
    assert "no active governed spl template" not in str(detail).lower()


def test_non_auth_contracts_drop_auth_limitation_phrases() -> None:
    for use_case_id, expected in (
        ("edr_powershell_suspicious_command", "command_line"),
        ("dns_beaconing_candidate", "periodicity"),
    ):
        contract = _contract(
            evidence_plan={
                "answer_mode": "hybrid",
                "spl_allowed": True,
                "mcp_allowed": False,
                "use_case_id": use_case_id,
                "missing_required_evidence": [expected, "mfa_status", "post_login_activity"],
                "limitations": [],
                "checklist": [],
                "unsupported_claims_avoid": [],
                "answer_rules": [],
            },
            severity_decision=type(
                "Severity",
                (),
                {"severity_label": "P2 High", "missing_evidence": ["source_ownership", "mfa_status"]},
            )(),
            use_case_id=use_case_id,
        )

        assert expected in contract.missing_evidence
        joined = " ".join(contract.missing_evidence).lower()
        assert "mfa_status" not in joined
        assert "post_login_activity" not in joined
        assert "source_ownership" not in joined


def test_execution_status_label_remains_review_only_or_not_executed() -> None:
    contract = _contract()

    assert contract.execution_status_label == "review_only_not_executed"
    assert contract.execution_status_display == "Review only — not executed"


def test_hil_status_reflects_missing_evidence_or_review_requirement() -> None:
    missing = _contract()
    required = _contract(human_review={"required": True, "review_type": "analyst_review"})

    assert missing.hil_status == "missing_evidence_review"
    assert required.hil_status == "required"


def test_backward_compatible_live_response_shape_remains_valid(monkeypatch) -> None:
    monkeypatch.setattr("app.config.settings.ai_soc_planner_mitre_branch_enabled", True)
    monkeypatch.setattr("app.config.settings.ai_soc_spl_template_governance_enabled", True)
    monkeypatch.setattr("app.config.settings.ai_soc_curated_enrichment_activation_enabled", True)

    response = chat(
        ChatRequest(
            message=(
                "For alert ALT-2024-0891 failed logins followed by successful login, "
                "what is the severity, MITRE mapping, and governed SPL I can review?"
            )
        )
    )

    assert response.answer_contract is not None
    assert "spl_status" in response.answer_contract
    assert "candidate_mitre" in response.answer_contract
    assert "evidence_supported_mitre" in response.answer_contract
    assert response.control_plane_trace is not None
    assert response.control_plane_trace["answer_contract_v2"] == response.answer_contract
