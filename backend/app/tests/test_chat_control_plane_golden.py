from __future__ import annotations

import pytest

from app.api.routes_chat import chat
from app.schemas.requests import ChatRequest


@pytest.fixture(autouse=True)
def _enable_control_plane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.control_plane_enabled", True)
    monkeypatch.setattr("app.config.settings.spl_allowed_sourcetypes", "pgcil:auth,aws:cloudtrail")


def _chat(query: str):
    response = chat(ChatRequest(message=query))
    assert response.query_to_intent is not None
    assert response.evidence_plan is not None
    assert response.route_adjudication is not None
    assert response.control_plane_trace is not None
    assert response.response_mode is not None
    assert response.synthesis_mode is not None
    return response


def test_policy_escalation_failed_login_rag_only_no_spl_mcp_or_visible_mitre() -> None:
    response = _chat("What is the escalation policy for repeated failed login alerts?")
    intent = response.query_to_intent["intent_classification"]
    assert intent["intent_family"] == "policy_knowledge"
    assert response.evidence_plan["answer_mode"] == "rag_only"
    assert response.route_adjudication["final_route"] == "knowledge_recall"
    assert response.candidate_spl is None
    assert response.spl_validation is None
    assert response.execution is not None
    assert response.execution.execution_intent == "none"
    assert response.mitre_mappings == []
    assert response.mitre_decision is not None
    assert response.mitre_decision["answer_visible"] is False


def test_hybrid_failed_login_action_encodes_requested_slots_and_keeps_hil() -> None:
    response = _chat(
        "Find accounts failing login in the last 24 hours, exclude service accounts, "
        "and tell me what analyst action I should take"
    )
    assert response.evidence_plan["answer_mode"] == "hybrid"
    assert response.evidence_plan["needs_spl"] is True
    assert response.evidence_plan["needs_mcp"] is True
    assert response.spl_validation is not None
    assert response.spl_validation.approved is True
    assert response.spl_validation.normalized_spl is not None
    assert "earliest=-24h" in response.spl_validation.normalized_spl
    assert "svc_*" in response.spl_validation.normalized_spl
    assert response.execution is not None
    assert response.execution.status == "requires_human_review"
    assert response.human_review is not None
    assert response.human_review.required is True
    assert response.mitre_mappings == []


def test_mitre_mapping_without_alert_context_requires_clarification() -> None:
    response = _chat("Map 148 failed logins across 12 accounts from external IPs to MITRE")
    assert response.evidence_plan["answer_mode"] == "clarification"
    assert response.route_adjudication["authority_source"] == "intent_clarification"
    assert response.human_review is not None
    assert response.human_review.required is True
    assert response.human_review.review_type == "intent_clarification"
    assert response.candidate_spl is None
    assert response.mitre_mappings == []


def test_generate_spl_top_failed_login_users_rejects_missing_slot_binding_no_mcp() -> None:
    response = _chat("Generate SPL for the top failed-login users in the last 24 hours")
    assert response.evidence_plan["needs_spl"] is True
    assert response.evidence_plan["mcp_allowed"] is False
    assert response.candidate_spl is not None
    assert response.spl_validation is not None
    assert response.spl_validation.approved is False
    assert "user_constraints_not_encoded" in response.spl_validation.reject_reasons
    assert response.execution is not None
    assert response.execution.block_reason == "mcp_not_allowed_by_evidence_plan"


def test_dga_investigation_steps_are_knowledge_rag_only() -> None:
    response = _chat("Explain investigation steps for DGA detection")
    intent = response.query_to_intent["intent_classification"]
    assert intent["intent_family"] == "knowledge_only"
    assert response.evidence_plan["answer_mode"] == "rag_only"
    assert response.candidate_spl is None
    assert response.execution is not None
    assert response.execution.execution_intent == "none"


def test_top_failed_login_users_exclude_service_accounts_encodes_slots_before_mcp() -> None:
    response = _chat(
        "Show top users with failed login count in the last 24 hours and exclude service accounts"
    )
    assert response.evidence_plan["answer_mode"] == "live_investigation"
    assert response.spl_validation is not None
    assert response.spl_validation.approved is True
    assert response.spl_validation.normalized_spl is not None
    assert "earliest=-24h" in response.spl_validation.normalized_spl
    assert "svc_*" in response.spl_validation.normalized_spl
    assert response.execution is not None
    assert response.execution.status in {"requires_human_review", "executed"}


def test_when_failed_login_alerts_escalated_is_policy_rag_only_no_visible_mitre() -> None:
    response = _chat("When should repeated failed login alerts be escalated?")
    intent = response.query_to_intent["intent_classification"]
    assert intent["intent_family"] in {"policy_knowledge", "sop_or_playbook"}
    assert response.evidence_plan["answer_mode"] == "rag_only"
    assert response.route_adjudication["final_route"] == "knowledge_recall"
    assert response.candidate_spl is None
    assert response.execution is not None
    assert response.execution.execution_intent == "none"
    assert response.mitre_mappings == []
    assert response.mitre_decision is not None
    assert response.mitre_decision["answer_visible"] is False


def test_aws_security_group_modifications_returns_raw_cloudtrail_spl_answer() -> None:
    response = _chat("Write SPL to determine who made modifications to any AWS security groups")

    assert response.selected_use_case is not None
    assert response.selected_use_case.use_case_id == "aws_security_group_modifications"
    assert response.route_plan_shadow is not None
    assert response.route_plan_shadow.candidate_reason == "deterministic_control_plane_route_plan"
    assert response.route_plan_shadow.matched_template_id == "aws_security_group_modifications"
    assert response.candidate_spl is not None
    assert response.candidate_spl.generation_mode == "deterministic_template_render"
    assert response.spl_validation is not None
    assert response.spl_validation.approved is True
    spl = response.spl_validation.normalized_spl or ""
    assert "index=pgcil_soc" in spl
    assert "sourcetype=aws:cloudtrail" in spl
    assert "eventSource=ec2.amazonaws.com" in spl
    assert "AuthorizeSecurityGroupIngress" in spl
    assert "RevokeSecurityGroupEgress" in spl
    assert "ModifySecurityGroupRules" in spl
    assert "userIdentity.arn" in spl
    assert "head 100" in spl
    assert "datamodel=" not in spl
    assert "tstats" not in spl
    assert response.analyst_response is not None
    assert response.analyst_response.spl_code == spl
    assert response.analyst_response.response_profile == "spl_only"
    assert response.message == "Governed SPL draft ready. It has passed deterministic validation and has not been executed."
    assert response.execution is not None
    assert response.execution.status == "skipped"
    assert response.execution.block_reason == "mcp_not_allowed_by_evidence_plan"


@pytest.mark.parametrize(
    ("query", "use_case_id", "required_terms", "forbidden_terms"),
    [
        (
            "Write SPL to find successful AWS Console logins by user in the last 24 hours",
            "aws_console_success_logins_by_user",
            [
                "sourcetype=aws:cloudtrail",
                "eventSource=signin.amazonaws.com",
                "eventName=ConsoleLogin",
                "responseElements.ConsoleLogin=Success",
                "login_count",
                "userIdentity.arn",
                "earliest=-24h",
            ],
            ["sourcetype=pgcil:auth", "action=failure", "datamodel=", "tstats"],
        ),
        (
            "Write SPL to determine who changed AWS IAM policies or attached policies to users or roles",
            "aws_iam_policy_modifications",
            [
                "sourcetype=aws:cloudtrail",
                "eventSource=iam.amazonaws.com",
                "AttachUserPolicy",
                "AttachRolePolicy",
                "PutUserPolicy",
                "PutRolePolicy",
                "change_count",
                "userIdentity.arn",
            ],
            ["sourcetype=pgcil:auth", "action=failure", "datamodel=", "tstats"],
        ),
        (
            "Show top users with failed login count in the last 24 hours and exclude service accounts",
            "auth_failed_login_top_users_exclude_service_accounts",
            [
                "sourcetype=pgcil:auth",
                "earliest=-24h",
                "action=failure",
                "NOT (user=\"svc_*\" OR user=\"service_*\" OR user=\"*_svc\")",
                "stats count as fail_count",
                "by user",
            ],
            ["earliest=-60m", "by host, src", "datamodel=", "tstats"],
        ),
    ],
)
def test_known_questions_use_specific_raw_templates(
    query: str,
    use_case_id: str,
    required_terms: list[str],
    forbidden_terms: list[str],
) -> None:
    response = _chat(query)

    assert response.selected_use_case is not None
    assert response.selected_use_case.use_case_id == use_case_id
    assert response.candidate_spl is not None
    assert response.candidate_spl.generation_mode == "deterministic_template_render"
    assert response.spl_validation is not None
    assert response.spl_validation.approved is True
    spl = response.spl_validation.normalized_spl or ""
    for term in required_terms:
        assert term in spl
    for term in forbidden_terms:
        assert term not in spl
    assert response.analyst_response is not None
    assert response.analyst_response.spl_code == spl
    assert response.message == "Governed SPL draft ready. It has passed deterministic validation and has not been executed."
