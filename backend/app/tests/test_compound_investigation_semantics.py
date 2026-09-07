"""Compound investigation semantics: negation scope, catalog, and evidence-leg parity."""

from __future__ import annotations

from typing import Any

from app.actions.remediation_execution import execute_approved_remediation
from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.contracts.explicit_user_constraints import build_explicit_user_constraints
from app.chat.contracts.remediation_plan import ApprovedRemediationEnvelope, RemediationStep
from app.chat.intent_classifier import build_query_to_intent
from app.chat.multi_leg_evidence import compose_multi_leg_evidence
from app.chat.pipeline import build_live_chat_response
from app.chat.query_signals import extract_query_signals
from app.config import settings
from app.planner.composer import compose_resource_plan
from app.planner.resource_plan_authority import resource_plan_authority
from app.query_understanding.parser import understand_query
from app.query_understanding.success_after_failure import detect_success_after_failure
from app.routing.governance import _advisory_may_replace_skill
from app.routing.select_route_from_understanding import select_route_from_understanding
from app.schemas.requests import ChatRequest
from app.spl.spl_slot_binding_validator import extract_natural_language_slots
from app.use_cases.registry import match_use_cases

PRIMARY_QUERY = (
    "Investigate whether the successful SSH login from 198.51.100.42, after "
    "25 failed login attempts, indicates a compromised account. Check the relevant "
    "evidence, investigate any suspicious activity after the successful login, "
    "and tell me your conclusion and recommended next action.\n"
    "Do not execute any remediation."
)

MFA_QUERY = (
    "Investigate whether repeated failed MFA attempts followed by a successful "
    "sign-in from the same source indicate account compromise. Correlate the "
    "successful sign-in with subsequent account activity and tell me what evidence "
    "supports or weakens the compromise hypothesis. Recommend the next action but "
    "do not execute remediation."
)

POWERSHELL_QUERY = (
    "Investigate suspicious PowerShell execution followed by an outbound network "
    "connection and a downloaded child process. Tell me your conclusion and "
    "recommended next action. Do not execute any remediation."
)


def _payload(message: str) -> dict[str, Any]:
    return build_live_chat_response(ChatRequest(message=message)).model_dump(mode="json")


def _answer_text(payload: dict[str, Any]) -> str:
    analyst = payload.get("analyst_response") or {}
    parts = [
        payload.get("message") or "",
        analyst.get("summary") if isinstance(analyst, dict) else "",
        analyst.get("narrative") if isinstance(analyst, dict) else "",
        str(payload.get("analyst_summary") or ""),
    ]
    return "\n".join(str(part or "") for part in parts).lower()


def test_h1_do_not_remediate_does_not_set_review_only_spl() -> None:
    signals = extract_query_signals(PRIMARY_QUERY)
    assert signals["success_after_failure"] is True
    assert signals["do_not_execute_remediation"] is True
    assert signals["review_only_spl"] is False
    assert signals["live_data_request"] is True
    q2i = build_query_to_intent(
        query=PRIMARY_QUERY,
        query_understanding=understand_query(PRIMARY_QUERY),
        routed_skill="attack_discovery",
    )
    assert q2i.intent_classification.intent_family in {
        "live_investigation",
        "hybrid_investigation_plus_policy",
    }
    assert q2i.intent_classification.intent_family != "hybrid_alert_review"


def test_negation_a_investigate_without_remediation_allows_read() -> None:
    query = "Investigate failed logins for user alice. Do not execute any remediation."
    signals = extract_query_signals(query)
    assert signals["do_not_execute_remediation"] is True
    assert signals["review_only_spl"] is False
    constraints = build_explicit_user_constraints(query_signals=signals)
    assert constraints.execution_prohibited is False
    assert "do_not_execute_remediation" in constraints.prohibitions


def test_negation_b_write_spl_do_not_run_is_review_only() -> None:
    signals = extract_query_signals("Write the SPL but do not run it.")
    assert signals["review_only_spl"] is True
    assert signals["do_not_execute_remediation"] is False


def test_negation_c_do_not_run_searches_prohibits_read() -> None:
    signals = extract_query_signals("Investigate failed logins but do not run any searches.")
    assert signals["review_only_spl"] is True
    assert signals["live_data_request"] is False


def test_negation_d_recommend_containment_do_not_contain() -> None:
    query = "Investigate the SSH brute force and recommend containment, but do not contain."
    signals = extract_query_signals(query)
    assert signals["do_not_execute_remediation"] is True
    assert signals["review_only_spl"] is False


def test_h3_compound_query_binds_success_after_failure_not_spike() -> None:
    assert detect_success_after_failure(" ".join(PRIMARY_QUERY.lower().split())) is True
    matches = match_use_cases(PRIMARY_QUERY)
    assert matches
    assert matches[0].use_case_id == "auth_success_after_failure"
    assert all(item.use_case_id != "auth_failed_login_spike" for item in matches)


def test_simple_failed_login_spike_still_binds() -> None:
    matches = match_use_cases("Investigate failed login spike on APP-01")
    assert matches
    assert matches[0].use_case_id == "auth_failed_login_spike"


def test_h2_action_semantic_does_not_collapse_compound_sequence() -> None:
    slots = extract_natural_language_slots(PRIMARY_QUERY)
    assert slots.get("action_semantic") != "failed_login"
    qu = understand_query(PRIMARY_QUERY)
    assert "authentication_failure" in qu.entities.event_type
    assert "authentication_success" in qu.entities.event_type


def test_h4_auth_legs_and_post_login_have_resource_steps() -> None:
    composition = compose_multi_leg_evidence(PRIMARY_QUERY)
    assert composition is not None
    domains = [leg["domain"] for leg in composition["evidence_legs"]]
    assert "auth_failure" in domains
    assert "auth_success" in domains
    assert "post_login_activity" in domains
    plan = EvidencePlan(
        answer_mode="live_investigation",
        rag_phase="post_mcp",
        needs_rag=False,
        needs_spl=True,
        needs_mcp=True,
        needs_mitre=True,
        spl_allowed=True,
        mcp_allowed=False,
        policy_context_required=False,
        policy_context_recommended=False,
        evidence_legs=list(composition["evidence_legs"]),
        correlation=dict(composition["correlation"]),
        use_case_id="auth_failed_login_spike",
    )
    with resource_plan_authority():
        resource = compose_resource_plan(
            plan,
            intent_family="live_investigation",
            use_case_id="auth_failed_login_spike",
            skill_id="attack_discovery",
        )
    spl = resource.step_by_id("spl")
    assert spl is not None
    assert spl.resource_id == "spl_template_family:auth_success_after_failure"
    post = resource.step_by_id("leg_post_login_activity")
    assert post is not None
    assert post.status == "planned"
    assert resource.provenance.get("evidence_leg_parity") == "required_legs_have_explicit_outcome"


def test_primary_query_e2e_mcp_off_abstains_without_fake_evidence() -> None:
    payload = _payload(PRIMARY_QUERY)
    signals = ((payload.get("query_to_intent") or {}).get("query_signals") or {})
    intent = ((payload.get("query_to_intent") or {}).get("intent_classification") or {})
    ep = payload.get("evidence_plan") or {}
    ar = payload.get("analyst_response") or {}
    assert signals.get("review_only_spl") is False
    assert signals.get("do_not_execute_remediation") is True
    assert intent.get("intent_family") in {"live_investigation", "hybrid_investigation_plus_policy"}
    assert ep.get("needs_mcp") is True
    selected = payload.get("selected_use_case") or {}
    assert selected.get("use_case_id") == "auth_success_after_failure"
    run_contract = payload.get("run_contract") or {}
    assert int(run_contract.get("collected_evidence_count") or 0) == 0
    assert run_contract.get("allow_severity_assessment") is False
    execution = payload.get("execution") or {}
    assert execution.get("status") != "executed"
    assert execution.get("executed_spl") in (None, "")
    assert execution.get("block_reason") != "mcp_not_allowed_by_evidence_plan"
    outcome = payload.get("investigation_outcome") or {}
    assert list(outcome.get("findings") or []) == []
    text = _answer_text(payload)
    assert "governed soc kb entries" not in text
    assert "no suspicious activity" not in text
    rem_exec = payload.get("remediation_execution") or {}
    assert rem_exec in ({}, None) or not rem_exec.get("executed_any")
    severity = str((ar.get("severity_label") if isinstance(ar, dict) else "") or "")
    assert not severity.lower().startswith("p2")
    assert "p1" not in severity.lower()


def test_second_mfa_query_preserves_compound_graph() -> None:
    signals = extract_query_signals(MFA_QUERY)
    assert signals["success_after_failure"] is True
    assert signals["do_not_execute_remediation"] is True
    assert signals["review_only_spl"] is False
    composition = compose_multi_leg_evidence(MFA_QUERY)
    assert composition is not None
    domains = {leg["domain"] for leg in composition["evidence_legs"]}
    assert "auth_failure" in domains
    assert "auth_success" in domains
    q2i = build_query_to_intent(
        query=MFA_QUERY,
        query_understanding=understand_query(MFA_QUERY),
        routed_skill="attack_discovery",
    )
    assert q2i.intent_classification.intent_family != "hybrid_alert_review"


def test_third_query_generic_not_auth_only() -> None:
    signals = extract_query_signals(POWERSHELL_QUERY)
    assert signals["do_not_execute_remediation"] is True
    assert signals["review_only_spl"] is False
    composition = compose_multi_leg_evidence(POWERSHELL_QUERY)
    assert composition is not None
    domains = {leg["domain"] for leg in composition["evidence_legs"]}
    assert "endpoint_process" in domains or "firewall_network" in domains
    assert not domains <= {"auth_failure", "auth_success", "post_login_activity"}


def test_empty_investigation_outcome_cannot_invent_confirmed_compromise() -> None:
    payload = _payload(PRIMARY_QUERY)
    outcome = payload.get("investigation_outcome") or {}
    text = _answer_text(payload)
    if not outcome.get("findings") and not outcome.get("evidence_refs"):
        assert "confirmed compromise" not in text
        assert "compromise is confirmed" not in text
        assert "we confirmed a successful login" not in text


def test_do_not_execute_remediation_refuses_write_gate() -> None:
    envelope = ApprovedRemediationEnvelope(
        envelope_version=1,
        remediation_objective="Notify the owning team.",
        approved_steps=[
            RemediationStep(
                step_id="rem.01.email_send",
                capability_id="email_send",
                description="Send notification.",
                execution_mode="execute",
                availability="available",
                verification="Confirm delivery.",
                action_arguments={"recipient": "soc@example.com"},
            )
        ],
        plan_fingerprint="fingerprint-compound",
    )
    result = execute_approved_remediation(
        approved_envelope=envelope,
        context={"do_not_execute_remediation": True},
    )
    assert result.executed_any is False
    assert result.refused_reason == "user_prohibited_remediation_execution"
    assert result.receipts == []


def test_catalogue_keyword_does_not_override_compound_contract() -> None:
    matches = match_use_cases(PRIMARY_QUERY)
    assert matches[0].use_case_id == "auth_success_after_failure"


def test_default_investigation_plan_hil_not_invented() -> None:
    """Architecture permits direct governed reads; do not invent a second HIL."""
    assert settings.ai_soc_investigation_plan_before_resource_plan_enabled is False
    payload = _payload(PRIMARY_QUERY)
    approval = payload.get("investigation_approval") or {}
    assert approval.get("status") not in {"awaiting_approval", "edited_revalidated"}


def test_user_reported_success_is_not_source_evidence() -> None:
    payload = _payload(PRIMARY_QUERY)
    records = payload.get("source_evidence") or []
    for record in records:
        assert record.get("collection_status") != "collected"
        assert int(record.get("result_count") or 0) == 0
        provenance = str(record.get("evidence_source") or record.get("provenance") or "").lower()
        assert "user_reported" not in provenance
        assert "user_query" not in provenance
    outcome = payload.get("investigation_outcome") or {}
    assert list(outcome.get("findings") or []) == []


def test_failed_tool_is_not_negative_evidence() -> None:
    payload = _payload(PRIMARY_QUERY)
    text = _answer_text(payload)
    assert "no successful login" not in text
    assert "absence of post-login activity" not in text
    assert "no suspicious activity" not in text


def test_malformed_llm_advisory_cannot_replace_compound_route() -> None:
    qu = understand_query(PRIMARY_QUERY)
    route, _provenance = select_route_from_understanding(qu, PRIMARY_QUERY)
    assert route.get("skill") == "attack_discovery"
    assert list(route.get("tool_plan") or []) != ["needs_clarification"]
    assert _advisory_may_replace_skill(route, deterministic_uncertain=True) is False


def test_evidence_leg_without_covering_step_is_explicit() -> None:
    plan = EvidencePlan(
        answer_mode="live_investigation",
        rag_phase="post_mcp",
        needs_rag=False,
        needs_spl=False,
        needs_mcp=False,
        needs_mitre=False,
        spl_allowed=False,
        mcp_allowed=False,
        policy_context_required=False,
        policy_context_recommended=False,
        evidence_legs=[
            {"domain": "auth_failure", "entity": "user", "fields": ["user"]},
            {"domain": "auth_success", "entity": "user", "fields": ["user"]},
        ],
    )
    with resource_plan_authority():
        resource = compose_resource_plan(plan, intent_family="live_investigation")
    failure = resource.step_by_id("leg_auth_failure")
    success = resource.step_by_id("leg_auth_success")
    assert failure is not None and failure.status == "skipped_unavailable"
    assert success is not None and success.status == "skipped_unavailable"


def test_do_not_execute_does_not_classify_as_ot_network_beacon() -> None:
    from app.chat.signal_class_guidance import classify_signal_class

    assert classify_signal_class(MFA_QUERY) != "network_beacon"
    assert classify_signal_class(PRIMARY_QUERY) != "network_beacon"
    assert classify_signal_class(PRIMARY_QUERY) != "recon_scan"
    assert classify_signal_class(MFA_QUERY) != "recon_scan"


def test_mfa_visible_plan_is_compound_auth_not_ot_beacon() -> None:
    from app.chat.investigation_plan_builder import build_deterministic_investigation_plan
    from app.chat.investigation_plan_relevance import (
        plan_text_blob,
        required_auth_anchors_present,
        unjustified_primary_pivots,
    )

    plan = build_deterministic_investigation_plan(query=MFA_QUERY)
    blob = plan_text_blob(plan)
    assert unjustified_primary_pivots(blob, query=MFA_QUERY) == []
    anchors = required_auth_anchors_present(blob)
    assert anchors["authentication_failure"] is True
    assert anchors["authentication_success"] is True
    assert anchors["post_login_activity"] is True
    assert "network beacon" not in blob.lower()
    assert "ot inventory" not in blob.lower()
    assert "review-only" not in plan.investigation_objective.lower()


def test_ssh_visible_plan_preserves_failure_success_post_login() -> None:
    from app.chat.investigation_plan_builder import build_deterministic_investigation_plan
    from app.chat.investigation_plan_relevance import plan_text_blob, required_auth_anchors_present

    plan = build_deterministic_investigation_plan(query=PRIMARY_QUERY)
    blob = plan_text_blob(plan)
    anchors = required_auth_anchors_present(blob)
    assert anchors["authentication_failure"] is True
    assert anchors["authentication_success"] is True
    assert anchors["post_login_activity"] is True
    assert "failed-login spike only" not in blob.lower()


def test_powershell_plan_is_endpoint_network_not_auth_only() -> None:
    from app.chat.investigation_plan_builder import build_deterministic_investigation_plan
    from app.chat.investigation_plan_relevance import plan_text_blob

    query = (
        "Investigate a suspicious PowerShell execution followed by an outbound network "
        "connection and a downloaded child process. Determine whether the events are "
        "related, evaluate the relevant endpoint and network evidence, and tell me "
        "whether the activity appears malicious. Recommend the next action but do not "
        "execute remediation."
    )
    plan = build_deterministic_investigation_plan(query=query)
    blob = plan_text_blob(plan).lower()
    assert "powershell" in blob or "process" in blob
    assert "network" in blob or "outbound" in blob
    assert "network beacon" not in blob
    assert "ot inventory" not in blob


def test_catalogue_match_is_known_registry_not_ood() -> None:
    from app.query_understanding.semantic_intent import build_semantic_intent_envelope

    qu = understand_query(MFA_QUERY)
    assert qu.deterministic_match_path == "use_case_catalog"
    envelope = build_semantic_intent_envelope(
        query_understanding=qu,
        routed={"skill": "attack_discovery", "tool_plan": ["route_only", "attack_discovery"]},
        route_plan_shadow={},
        route_authority=None,
        primary_operation="attack_discovery",
        coverage_id=None,
    )
    assert envelope["path_type"] == "known_registry"


def test_live_investigation_path_is_not_generic_soc_guidance() -> None:
    from app.chat.planning_decision import compute_planning_decision_trace_only

    decision = compute_planning_decision_trace_only(
        intent_classification={
            "intent_family": "live_investigation",
            "requires_clarification": False,
        },
        evidence_plan={
            "answer_mode": "live_investigation",
            "needs_spl": False,
            "needs_mcp": True,
            "needs_rag": False,
            "needs_mitre": False,
        },
        routed={"skill": "attack_discovery", "tool_plan": ["attack_discovery"]},
    )
    assert decision.path_type == "hybrid_investigation"
    assert decision.path_type != "generic_soc_guidance"


def test_scoped_live_compound_does_not_clarify_missing_user_fields() -> None:
    from app.chat.known_detail_completion import evaluate_known_detail_completion

    q2i = build_query_to_intent(
        query=PRIMARY_QUERY,
        query_understanding=understand_query(PRIMARY_QUERY),
        routed_skill="attack_discovery",
    )
    completeness = evaluate_known_detail_completion(
        use_case_id="auth_success_after_failure",
        query_to_intent=q2i.model_dump(),
        query_understanding=understand_query(PRIMARY_QUERY),
    )
    assert completeness.clarification_required is False
    assert completeness.divert_to_guided is False


def test_approved_live_plan_keeps_mcp_required_when_source_unavailable() -> None:
    from app.chat.contracts.investigation_envelope import ApprovedInvestigationEnvelope
    from app.chat.contracts.investigation_plan import ValidatedInvestigationPlan
    from app.chat.contracts.resolved_query import ResolvedQueryContract
    from app.chat.investigation_run_compiler import build_approved_investigation_evidence_plan

    rqc = ResolvedQueryContract(
        normalized_goal=MFA_QUERY,
        intent_family="live_investigation",
        answer_goal="live_results",
        ambiguity_state="unambiguous",
        required_capabilities=frozenset({"spl", "mcp"}),
        evidence_requirements=["authentication_events"],
        entities={"event_type": ["authentication_failure", "authentication_success"]},
        time_scope="last 24 hours",
        qualification_tier="T4",
        qualification_source="test",
        understanding_source="deterministic_qualification",
    )
    plan = ValidatedInvestigationPlan(
        investigation_objective="Investigate MFA success after failure",
        evidence_needed=["authentication failure", "authentication success", "post-login activity"],
        data_categories=["auth"],
        capability_bindings=[],
        human_review_required=True,
    )
    envelope = ApprovedInvestigationEnvelope(
        envelope_version=2,
        objective="Investigate MFA success after failure",
        targets=["account"],
        entities=rqc.entities,
        time_scope="last 24 hours",
        approved_evidence_categories=["auth"],
        allowed_read_only_capabilities=[],
    )
    evidence, search_capabilities = build_approved_investigation_evidence_plan(
        envelope=envelope,
        validated_plan=plan,
        resolved_query_contract=rqc,
        handoff_id="cpi:loop",
        handoff_version=2,
        use_case_id="auth_success_after_failure",
    )
    assert search_capabilities == []
    assert evidence.needs_mcp is True
    assert evidence.mcp_available is False
    assert evidence.mcp_allowed is False
    assert evidence.answer_mode == "live_investigation"
    assert "read_source_required_but_unavailable" in evidence.reasons
    assert evidence.answer_mode != "guided_investigation"

