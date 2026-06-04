from __future__ import annotations

import pytest

from app.api.routes_chat import chat
from app.schemas.requests import ChatRequest
from app.spl.llm_fallback import LlmSplFallbackResult


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


def _assert_multiline_spl_present(envelope_spl: str | None, normalized_spl: str) -> None:
    assert envelope_spl is not None
    assert "\n" in envelope_spl
    assert all(part.strip() in envelope_spl for part in normalized_spl.split("|"))


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


def test_policy_escalation_l2_question_returns_sop_not_spl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.mcp_global_execution_enabled", False)
    monkeypatch.setattr("app.config.settings.soc_kb_retrieval_enabled", True)
    response = _chat(
        "What is the escalation policy for repeated failed login alerts, and when should it be assigned to L2?"
    )

    assert response.evidence_plan["answer_mode"] == "rag_only"
    assert response.route_adjudication["final_route"] == "knowledge_recall"
    assert response.candidate_spl is None
    assert response.spl_validation is None
    assert response.analyst_response is not None
    assert response.analyst_response.retrieved_playbook is not None
    assert response.analyst_response.recommended_actions
    assert response.mitre_mappings == []


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


def test_hybrid_failed_login_playbook_returns_spl_and_playbook_without_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.config.settings.mcp_global_execution_enabled", False)
    monkeypatch.setattr("app.config.settings.soc_kb_retrieval_enabled", True)
    response = _chat(
        "Find users with the highest failed login count in the last 24 hours, "
        "exclude service accounts, and tell me the analyst next action as per our playbook."
    )

    assert response.evidence_plan["answer_mode"] == "hybrid"
    assert response.spl_validation is not None
    assert response.spl_validation.approved is True
    spl = response.spl_validation.normalized_spl or ""
    assert "earliest=-24h" in spl
    assert "svc_*" in spl
    assert response.execution is not None
    assert response.execution.executed_spl is None
    assert response.analyst_response is not None
    _assert_multiline_spl_present(response.analyst_response.spl_code, spl)
    assert response.analyst_response.retrieved_playbook is not None
    assert response.analyst_response.recommended_actions


def test_mitre_mapping_without_alert_context_requires_clarification() -> None:
    response = _chat("Map 148 failed logins across 12 accounts from external IPs to MITRE")
    assert response.evidence_plan["answer_mode"] == "clarification"
    assert response.route_adjudication["authority_source"] == "intent_clarification"
    assert response.human_review is not None
    assert response.human_review.required is True
    assert response.human_review.review_type == "intent_clarification"
    assert response.candidate_spl is None
    assert response.mitre_mappings == []


def test_mitre_failed_login_context_maps_t1110_and_blocks_negated_techniques(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.config.settings.mcp_global_execution_enabled", False)
    response = _chat(
        "Map 148 failed login attempts across 12 accounts from external IPs to MITRE. "
        "There is no successful login, no endpoint telemetry, and no evidence of credential dumping."
    )

    assert response.evidence_plan["needs_mitre"] is True
    assert response.candidate_spl is None
    assert response.spl_validation is None
    ids = {item.technique_id for item in response.mitre_mappings or []}
    assert "T1110.001" in ids
    assert "T1078" not in ids
    assert "T1003" not in ids
    assert response.mitre_decision is not None
    assert response.mitre_decision["answer_visible"] is True
    assert "T1078" in response.mitre_decision["rejected_techniques"]
    assert "T1003" in response.mitre_decision["rejected_techniques"]
    assert "T1562.001" in response.mitre_decision["rejected_techniques"]

    assert response.analyst_response is not None
    mapping_rows = response.analyst_response.mitre_mappings
    assert {row["Technique"] for row in mapping_rows} == {"T1110.001"}
    t1110 = mapping_rows[0]
    assert t1110["Name"] == "Password Guessing"
    assert t1110["Status"] == "Candidate"
    assert t1110["Confidence"] == "Medium"
    assert "password guessing" in str(t1110["Evidence"]).lower()
    assert "password policy discovery" not in str(t1110["Evidence"]).lower()

    not_claimed = {row["Technique"]: row for row in response.analyst_response.not_claimed}
    assert {"T1078", "T1003", "T1562.001"}.issubset(not_claimed)
    assert "No successful login" in str(not_claimed["T1078"]["Reason"])
    assert "No credential dumping evidence" in str(not_claimed["T1003"]["Reason"])
    assert "No defense impairment evidence" in str(not_claimed["T1562.001"]["Reason"])
    assert response.analyst_response.retrieved_playbook is None

    analyst_text = response.analyst_response.model_dump_json()
    assert "password policy discovery" not in analyst_text.lower()
    assert "security alert has been triggered" not in analyst_text.lower()


def test_generate_spl_top_failed_login_users_rejects_missing_slot_binding_no_mcp() -> None:
    response = _chat("Generate SPL for the top failed-login users in the last 24 hours")
    assert response.evidence_plan["needs_spl"] is True
    assert response.evidence_plan["mcp_allowed"] is False
    assert response.candidate_spl is not None
    assert response.candidate_spl.generation_mode == "clarification_required"
    assert response.candidate_spl.candidate_spl == ""
    assert response.spl_validation is not None
    assert response.spl_validation.approved is False
    assert "llm_spl_fallback_disabled" in response.spl_validation.reject_reasons
    assert response.response_mode == "clarification_required"
    assert response.execution is not None
    assert response.execution.block_reason == "mcp_not_allowed_by_evidence_plan"


def test_uncatalogued_spl_generation_requires_clarification_not_stage3c_stub() -> None:
    response = _chat("Write SPL to detect impossible travel from VPN logs")

    assert response.selected_use_case is not None
    assert response.selected_use_case.use_case_id == "soc_generate_spl"
    assert response.candidate_spl is not None
    assert response.candidate_spl.generation_mode == "clarification_required"
    assert response.candidate_spl.candidate_spl == ""
    assert response.candidate_spl.selected_candidate_spl_provider == "none"
    assert response.candidate_spl.llm_fallback_status == "clarification_required"
    assert response.spl_validation is not None
    assert response.spl_validation.approved is False
    assert response.spl_validation.normalized_spl is None
    assert response.spl_validation.selected_candidate_spl_provider == "none"
    assert response.spl_validation.llm_fallback_status == "clarification_required"
    assert "llm_spl_fallback_disabled" in response.spl_validation.reject_reasons
    assert response.response_mode == "clarification_required"
    assert response.human_review is not None
    assert response.human_review.required is True
    assert response.human_review.review_type == "intent_clarification"
    assert response.execution is not None
    assert response.execution.executed_spl is None
    trace = response.control_plane_trace or {}
    generation = trace.get("candidate_spl_generation") or {}
    assert generation["generation_mode"] == "clarification_required"
    assert generation["selected_candidate_spl_provider"] == "none"
    assert generation["llm_fallback_status"] == "clarification_required"


def test_uncatalogued_spl_generation_uses_governed_llm_fallback_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spl = (
        "search index=pgcil_soc sourcetype=pgcil:auth earliest=-60m latest=now "
        "action=failure | stats count as fail_count by src_ip | sort -fail_count | head 100"
    )
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_llm_spl_fallback_enabled", True)
    monkeypatch.setattr(
        "app.chat.pipeline.generate_llm_spl_fallback",
        lambda *, user_query: LlmSplFallbackResult(
            candidate_spl=spl,
            approved=True,
            validation={
                "approved": True,
                "normalized_spl": spl,
                "reject_reasons": [],
                "warnings": [],
                "enforced_limits": {},
                "policy_version": "spl-validator-v1",
            },
            assumptions=["LLM mapped VPN impossible travel to allowed auth source fields."],
            required_fields=["src_ip"],
            model="foundation-sec-test",
            latency_ms=12,
        ),
    )

    response = _chat("Write SPL to detect impossible travel from VPN logs")

    assert response.candidate_spl is not None
    assert response.candidate_spl.generation_mode == "llm_spl_advisory_fallback"
    assert response.candidate_spl.selected_candidate_spl_provider == "llm_spl_advisory_fallback"
    assert response.candidate_spl.llm_supported is True
    assert response.candidate_spl.llm_fallback_used is True
    assert response.candidate_spl.llm_fallback_status == "approved"
    assert response.candidate_spl.execution_eligible is False
    assert response.candidate_spl.llm_model == "foundation-sec-test"
    assert response.spl_validation is not None
    assert response.spl_validation.approved is True
    assert response.spl_validation.selected_candidate_spl_provider == "llm_spl_advisory_fallback"
    assert response.spl_validation.llm_supported is True
    assert response.spl_validation.llm_fallback_used is True
    assert response.spl_validation.llm_fallback_status == "approved"
    assert response.spl_validation.llm_model == "foundation-sec-test"
    assert response.execution is not None
    assert response.execution.executed_spl is None
    generation = (response.control_plane_trace or {}).get("candidate_spl_generation") or {}
    assert generation["selected_candidate_spl_provider"] == "llm_spl_advisory_fallback"
    assert generation["llm_supported"] is True
    assert generation["llm_fallback_used"] is True
    assert generation["llm_fallback_status"] == "approved"
    assert generation["execution_eligible"] is False


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
    _assert_multiline_spl_present(response.analyst_response.spl_code, spl)
    assert all(part.strip() in (response.analyst_response.spl_code or "") for part in spl.split("|"))
    assert response.analyst_response.response_profile == "spl_only"
    assert response.message == "Governed SPL draft ready. It has passed deterministic validation and has not been executed."
    assert response.execution is not None
    assert response.execution.status == "skipped"
    assert response.execution.block_reason == "mcp_not_allowed_by_evidence_plan"


def test_alt_2024_0891_success_after_failure_hybrid_alert_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.config.settings.mcp_global_execution_enabled", False)
    query = (
        "For alert ALT-2024-0891 (failed logins followed by a successful login from the same user "
        "in the last hour), what's the severity, MITRE mapping with status, and a governed SPL "
        "I can review—but not execute"
    )
    response = _chat(query)

    intent = response.query_to_intent["intent_classification"]
    assert intent["intent_family"] == "hybrid_alert_review"
    assert "severity_assessment" in intent["answer_goal"]
    assert "mitre_mapping" in intent["answer_goal"]
    assert "spl_artifact" in intent["answer_goal"]

    assert response.evidence_plan["needs_spl"] is True
    assert response.evidence_plan["needs_mcp"] is False
    assert response.evidence_plan["mcp_allowed"] is False
    assert response.evidence_plan["action_mode"] == "recommend_only"

    assert response.selected_use_case is not None
    assert response.selected_use_case.use_case_id == "auth_success_after_failure"
    assert response.severity_decision is not None
    assert response.severity_decision.severity_label.startswith("P2")

    assert response.candidate_spl is not None
    assert response.spl_validation is not None
    assert response.spl_validation.approved is True
    spl = response.spl_validation.normalized_spl or ""
    assert "host=APP-01" not in spl
    assert 'alert_id="ALT-2024-0891"' in spl
    assert " by user " in spl
    assert "action=failure OR action=success" in spl or (
        'action="failure"' in spl and 'action="success"' in spl
    )
    assert "fail_count" in spl
    assert "success_count" in spl
    assert "last_success" in spl

    ids = {item.technique_id for item in response.mitre_mappings or []}
    assert "T1110.001" in ids
    assert "T1078" in ids
    assert "T1003" not in ids
    assert "T1562.001" not in ids

    assert response.analyst_response is not None
    mapping_rows = {row["Technique"]: row for row in response.analyst_response.mitre_mappings}
    assert mapping_rows["T1110.001"]["Status"] == "Candidate"
    assert mapping_rows["T1078"]["Status"] == "Candidate"
    assert response.analyst_response.severity_label is not None
    assert response.analyst_response.execution_status_label == "Review only — not executed"
    assert response.analyst_response.severity_confidence == "Medium"
    assert response.analyst_response.severity_rationale
    assert response.analyst_response.response_profile == "hybrid_alert_review"
    assert response.analyst_response.finding_title == "Alert ALT-2024-0891 review"
    assert response.analyst_response.spl_code is not None
    assert 'alert_id="ALT-2024-0891"' in (response.analyst_response.spl_code or "")
    assert "\n" in (response.analyst_response.spl_code or "")
    assert response.analyst_response.direct_answer_summary
    assert len(response.analyst_response.mitre_mappings) >= 2
    assert len(response.analyst_response.not_claimed) >= 2

    not_claimed = {row["Technique"] for row in response.analyst_response.not_claimed}
    assert "T1078" not in not_claimed
    assert {"T1003", "T1562.001"}.issubset(not_claimed)

    assert response.execution is not None
    assert response.execution.executed_spl is None
    assert response.execution.block_reason == "mcp_not_allowed_by_evidence_plan"

    assert response.analyst_response.review_notice == "Review only — not executed"
    assert response.analyst_response.severity_safety_note
    assert "not confirmed account compromise" in response.analyst_response.severity_safety_note.lower()

    combined = response.analyst_response.model_dump_json().lower()
    assert "review only" in combined
    assert "spl:" in (response.analyst_response.direct_answer_summary or "").lower()
    assert response.analyst_response.not_claimed
    for technique_id in ("T1003", "T1562.001"):
        row = next(item for item in response.analyst_response.not_claimed if item["Technique"] == technique_id)
        assert row["Status"] == "Not Claimed"


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
    _assert_multiline_spl_present(response.analyst_response.spl_code, spl)
    assert response.message == "Governed SPL draft ready. It has passed deterministic validation and has not been executed."
