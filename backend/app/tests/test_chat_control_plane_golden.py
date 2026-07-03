from __future__ import annotations

import re

import pytest

from app.api.routes_chat import chat
from app.chat import pipeline as chat_pipeline
from app.schemas.requests import ChatRequest
from app.spl.llm_fallback import LlmSplFallbackResult
from app.tests.support.chat_visible import assert_governed_spl_review_posture, visible_chat_prose
from app.tests.support.chat_visible import REVIEW_ONLY_NOTICE


_CLARIFICATION_GOVERNANCE_REASONS = frozenset(
    {
        "llm_spl_fallback_disabled",
        "spl_template_missing",
        "spl_template_governance_blocked",
        "spl_template_unavailable_no_free_spl_fallback",
    }
)


@pytest.fixture(autouse=True)
def _enable_control_plane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.control_plane_enabled", True)
    monkeypatch.setattr("app.config.settings.spl_allowed_sourcetypes", "pgcil:auth,aws:cloudtrail")


def _assert_spl_clarification_blocked(reject_reasons: list[str] | None) -> None:
    reasons = set(reject_reasons or [])
    assert reasons & _CLARIFICATION_GOVERNANCE_REASONS, (
        f"expected governance clarification reason, got {sorted(reasons)}"
    )


def _chat(query: str):
    response = chat(ChatRequest(message=query))
    assert response.query_to_intent is not None
    assert response.evidence_plan is not None
    assert response.route_adjudication is not None
    assert response.control_plane_trace is not None
    assert response.response_mode is not None
    assert response.synthesis_mode is not None
    return response


def _collapse_spl(spl: str) -> str:
    return re.sub(r"[\s|]+", " ", spl.lower()).strip()


def _assert_multiline_spl_present(envelope_spl: str | None, normalized_spl: str) -> None:
    assert envelope_spl is not None
    assert "\n" in envelope_spl
    assert _collapse_spl(envelope_spl) == _collapse_spl(normalized_spl)


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
    assert {row["Technique"] for row in mapping_rows} == {"T1110", "T1110.001", "T1110.003"}
    mapping_by_id = {row["Technique"]: row for row in mapping_rows}
    assert mapping_by_id["T1110.001"]["Name"] == "Password Guessing"
    assert mapping_by_id["T1110"]["Status"] == "Requires Validation"
    assert mapping_by_id["T1110.001"]["Status"] == "Requires Validation"
    assert mapping_by_id["T1110.003"]["Status"] == "Requires Validation"
    assert mapping_by_id["T1110.001"]["Confidence"] == "Moderate - analyst validation required"
    assert response.analyst_response.severity_label == "P3 Medium"
    assert "password" in str(mapping_by_id["T1110.001"]["Evidence"]).lower()
    assert "password policy discovery" not in str(mapping_by_id["T1110.001"]["Evidence"]).lower()

    not_claimed = {row["Technique"]: row for row in response.analyst_response.not_claimed}
    assert {"T1078", "T1003", "T1562.001"}.issubset(not_claimed)
    assert "No successful login" in str(not_claimed["T1078"]["Reason"])
    assert "No credential dumping evidence" in str(not_claimed["T1003"]["Reason"])
    assert "No defense impairment evidence" in str(not_claimed["T1562.001"]["Reason"])
    assert response.analyst_response.retrieved_playbook is None

    analyst_text = response.analyst_response.model_dump_json()
    assert "password policy discovery" not in analyst_text.lower()
    assert "security alert has been triggered" not in analyst_text.lower()


def test_generate_spl_top_failed_login_users_rejects_missing_slot_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_llm_spl_fallback_enabled", False)
    monkeypatch.setattr("app.spl.llm_fallback.settings.ai_soc_llm_spl_fallback_enabled", False)
    response = _chat("Generate SPL for the top failed-login users in the last 24 hours")
    assert response.evidence_plan["needs_spl"] is True
    # MCP eligibility on all tiers (2026-07 directive, item 2.1): a live-data ask
    # is architecturally eligible under control_plane_enabled. This test's real
    # invariant is the missing-slot-binding clarification path below, which is
    # unaffected — eligibility never substitutes for a valid, resolved SPL artifact.
    assert response.evidence_plan["mcp_allowed"] is True
    assert response.candidate_spl is not None
    assert response.candidate_spl.generation_mode == "clarification_required"
    assert response.candidate_spl.candidate_spl == ""
    assert response.spl_validation is not None
    assert response.spl_validation.approved is False
    _assert_spl_clarification_blocked(response.spl_validation.reject_reasons)
    assert response.response_mode == "clarification_required"
    assert response.execution is not None
    assert response.execution.block_reason == "spl_validation_failed"


def test_uncatalogued_spl_generation_requires_clarification_not_stage3c_stub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_llm_spl_fallback_enabled", False)
    monkeypatch.setattr("app.spl.llm_fallback.settings.ai_soc_llm_spl_fallback_enabled", False)
    # A bare SPL-generation modifier with no catalogued detection family: the
    # weak soc_generate_spl meta row matches (it must not override a real
    # detection family, but none is named here).
    response = _chat("Generate SPL for a bespoke asset inventory drift check")

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
    _assert_spl_clarification_blocked(response.spl_validation.reject_reasons)
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


def test_uncatalogued_spl_generation_uses_lab_only_llm_candidate_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Phase C: with the failover flag on, the governed candidate path now USES the
    # LLM advisory fallback for uncatalogued SPL (B01 wiring) — gated by relevance
    # and deterministic validation, and always lab-only (never governed/executable).
    # The SPL must be on-question (VPN/network) to pass the R5 relevance gate.
    spl = (
        "search index=<vpn_index> sourcetype=<vpn_sourcetype> earliest=-24h latest=now "
        "action=success | eval src_ip_norm=coalesce(src_ip, src) "
        "| eval user_norm=coalesce(user, src_user) "
        "| stats dc(src_ip_norm) as distinct_ips values(src_ip_norm) as source_ips by user_norm "
        "| where distinct_ips>1 | head 100"
    )
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_llm_spl_fallback_enabled", True)
    class _Telemetry:
        def record_step(self, *a, **k) -> None: ...

        def record_spl_validation(self, *a, **k) -> None: ...

    monkeypatch.setattr(
        chat_pipeline,
        "_routes_chat",
        lambda: type("_Routes", (), {"get_telemetry_connector": staticmethod(lambda: _Telemetry())})(),
    )
    monkeypatch.setattr(
        "app.chat.pipeline.generate_llm_spl_fallback",
        lambda *, user_query, **_kw: LlmSplFallbackResult(
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
            status="candidate_generated",
            confidence_score=0.76,
            confidence_label="medium",
            detection_family="vpn_impossible_travel",
            assumptions=["LLM mapped VPN impossible travel to allowed network/VPN source fields."],
            required_fields=["src_ip"],
            model="foundation-sec-test",
            latency_ms=12,
        ),
    )

    governed_candidate, governed_validation = chat_pipeline._candidate_spl_stage(
        trace_id="t",
        skill="spl_generation",
        user_query="Write SPL to detect impossible travel from VPN logs",
        template_id=None,
        use_case_id="soc_incident_triage",
    )
    assert governed_candidate is not None
    assert governed_validation is not None
    # LLM candidate now serves the governed failover path — but strictly lab-only.
    assert governed_candidate["generation_mode"] == "llm_spl_advisory_fallback"
    assert governed_candidate["execution_eligible"] is False
    assert governed_candidate["governed"] is False
    assert governed_candidate["catalog_approved"] is False
    assert governed_validation["approved"] is True
    assert governed_validation["normalized_spl"] == spl
    assert governed_validation["selected_candidate_spl_provider"] == "llm_spl_advisory_fallback"

    llm_candidate = chat_pipeline._llm_spl_candidate_stage(
        skill="spl_generation",
        user_query="Write SPL to detect impossible travel from VPN logs",
        request_enabled=True,
    )
    assert llm_candidate is not None
    assert llm_candidate["llm_spl_candidate"] == spl
    assert llm_candidate["llm_spl_candidate_status"] == "candidate_generated"
    assert llm_candidate["governed"] is False
    assert llm_candidate["catalog_approved"] is False
    assert llm_candidate["execution_enabled"] is False
    assert llm_candidate["execution_eligible"] is False
    assert llm_candidate["model"] == "foundation-sec-test"


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
    assert response.analyst_response.response_profile == "spl_only"
    assert_governed_spl_review_posture(response)
    assert response.execution is not None
    # MCP eligibility on all tiers (2026-07 directive, item 2.1): this fully
    # validated, approved template SPL is now architecturally eligible for
    # execution under control_plane_enabled, so the gate is actually reached
    # (requires_human_review) instead of skipped outright. execution_eligible
    # stays false on the candidate; nothing here executes without HIL approval.
    assert response.execution.status == "requires_human_review"
    assert response.execution.block_reason == "precondition_eval_failed"


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
    assert mapping_rows["T1110.001"]["Status"] == "Requires Validation"
    assert mapping_rows["T1110.001"]["Confidence"] == "Moderate - analyst validation required"
    assert mapping_rows["T1078"]["Status"] == "Candidate"
    assert mapping_rows["T1078"]["Confidence"] == "Medium"
    assert response.analyst_response.severity_label is not None
    assert "Review required" in (response.analyst_response.severity_label or "")
    assert response.analyst_response.execution_status_label == "Review only — not executed"
    assert response.analyst_response.severity_confidence == "Medium"
    assert response.analyst_response.severity_rationale
    assert response.analyst_response.response_profile == "hybrid_alert_review"
    assert response.analyst_response.finding_title == "Alert ALT-2024-0891 review"
    assert response.analyst_response.spl_code is not None
    assert 'alert_id="ALT-2024-0891"' in (response.analyst_response.spl_code or "")
    assert "\n" in (response.analyst_response.spl_code or "")
    assert response.analyst_response.direct_answer_summary
    assert "technique requiring validation" in response.analyst_response.direct_answer_summary
    assert "candidate technique" in response.analyst_response.direct_answer_summary
    assert "evidence-supported MITRE technique" not in response.analyst_response.direct_answer_summary
    assert "not claimed" in response.analyst_response.direct_answer_summary
    assert "governed SPL draft" in response.analyst_response.direct_answer_summary
    assert "Severity:" not in (response.analyst_response.direct_answer_summary or "")
    assert response.analyst_response.limitations == [
        "Privilege status missing",
        "Asset criticality missing",
        "Source IP ownership missing",
        "MFA result missing",
        "Post-login activity missing",
    ]
    assert len(response.analyst_response.mitre_mappings) >= 2
    assert len(response.analyst_response.not_claimed) >= 2

    not_claimed = {row["Technique"] for row in response.analyst_response.not_claimed}
    assert "T1078" not in not_claimed
    assert {"T1003", "T1562.001"}.issubset(not_claimed)

    assert response.execution is not None
    assert response.execution.executed_spl is None
    assert response.execution.block_reason == "mcp_not_allowed_by_evidence_plan"

    assert response.analyst_response.review_notice is None or REVIEW_ONLY_NOTICE.search(
        str(response.analyst_response.review_notice or "")
    )
    prose = visible_chat_prose(response).lower()
    assert "review only" in prose
    assert response.analyst_response.severity_safety_note
    assert "not confirmed account compromise" in response.analyst_response.severity_safety_note.lower()

    combined = response.analyst_response.model_dump_json().lower()
    assert "review only" in combined
    assert "governed spl draft" in (response.analyst_response.direct_answer_summary or "").lower()
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
    assert_governed_spl_review_posture(response)
