from __future__ import annotations

from typing import Any

from app.api.routes_chat import chat
from app.config import settings
from app.schemas.requests import ChatRequest
from app.use_cases.content_enrichment import get_runtime_curated_enrichment


def _enable_phase7(monkeypatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_planner_path_selection_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_planner_mitre_branch_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_spl_template_governance_enabled", True)
    monkeypatch.setattr(settings, "soc_kb_retrieval_enabled", True)


def test_sop_playbook_question_goes_rag_only_and_skips_spl_mcp(monkeypatch) -> None:
    _enable_phase7(monkeypatch)
    monkeypatch.setattr("app.chat.pipeline.retrieve_soc_kb", _fake_retrieve_collected)

    response = chat(ChatRequest(message="Show SOP for failed login investigation"))

    assert response.evidence_plan["answer_mode"] == "rag_only"
    assert response.planning_decision["path_type"] == "rag_only"
    assert response.evidence_plan["spl_allowed"] is False
    assert response.evidence_plan["mcp_allowed"] is False
    assert response.candidate_spl is None
    assert response.spl_validation is None
    assert response.execution.status == "skipped"
    assert response.planning_decision["blocked_tools"][:2] == ["spl", "mcp"]


def test_generic_soc_question_uses_guidance_path_without_fake_use_case(monkeypatch) -> None:
    _enable_phase7(monkeypatch)
    monkeypatch.setattr("app.chat.pipeline.retrieve_soc_kb", _fake_retrieve_collected)

    response = chat(ChatRequest(message="What are general SOC triage steps for a suspicious alert?"))

    assert response.planning_decision["path_type"] == "generic_soc_guidance"
    assert response.selected_use_case is None
    assert response.planning_decision["use_case_id"] is None
    assert response.candidate_spl is None
    assert response.spl_validation is None
    assert response.execution.status == "skipped"
    assert not response.mitre_mappings


def test_kb_no_match_returns_safe_fallback_not_hallucinated_sop(monkeypatch) -> None:
    _enable_phase7(monkeypatch)
    monkeypatch.setattr("app.chat.pipeline.retrieve_soc_kb", _fake_retrieve_no_match)

    response = chat(ChatRequest(message="What is the runbook for printer toner inventory?"))

    assert "No governed KB/SOP match was found" in response.message
    assert response.context_sufficiency.status == "insufficient_evidence"
    assert "rag_no_match" in response.context_sufficiency.reasons
    assert response.analyst_response is None
    assert response.candidate_spl is None
    assert response.spl_validation is None
    assert response.execution.status == "skipped"


def test_mitre_only_without_alert_context_requests_context(monkeypatch) -> None:
    _enable_phase7(monkeypatch)
    monkeypatch.setattr("app.chat.pipeline.retrieve_soc_kb", _fake_retrieve_no_match)

    response = chat(ChatRequest(message="Map this to MITRE"))

    assert response.planning_decision["path_type"] == "mitre_context_required"
    assert response.human_review.required is True
    assert response.human_review.review_type == "intent_clarification"
    assert "alert context" in response.message.lower()
    assert response.candidate_spl is None
    assert response.spl_validation is None
    assert not response.mitre_mappings


def test_enrichment_only_pilot_does_not_become_runtime_active(monkeypatch) -> None:
    _enable_phase7(monkeypatch)

    assert get_runtime_curated_enrichment("email_phishing_header_review") is None


def test_brute_force_sop_with_spl_suppression_does_not_generate_spl(monkeypatch) -> None:
    _enable_phase7(monkeypatch)
    monkeypatch.setattr("app.chat.pipeline.retrieve_soc_kb", _fake_retrieve_collected)

    response = chat(
        ChatRequest(
            message=(
                "Show me the SOP for brute-force login investigation. "
                "Do not generate SPL unless required."
            )
        )
    )

    assert response.evidence_plan["answer_mode"] == "rag_only"
    assert response.planning_decision["path_type"] == "rag_only"
    assert response.query_to_intent["intent_classification"]["intent_family"] == "sop_or_playbook"
    assert response.query_to_intent["query_signals"]["spl_suppressed"] is True
    assert response.query_to_intent["query_signals"]["spl_generation"] is False
    assert response.candidate_spl is None
    assert response.spl_validation is None


def test_powershell_guidance_maps_to_endpoint_use_case_and_template(monkeypatch) -> None:
    _enable_phase7(monkeypatch)
    monkeypatch.setattr("app.config.settings.mcp_global_execution_enabled", False)

    response = chat(
        ChatRequest(
            message=(
                "For suspicious PowerShell command execution on an endpoint, give me the analyst "
                "checklist, required evidence, MITRE status, and governed SPL for review."
            )
        )
    )

    assert response.selected_use_case is not None
    assert response.selected_use_case.use_case_id == "edr_powershell_suspicious_command"
    assert response.candidate_spl is not None
    assert response.candidate_spl.template_id == "edr_powershell_suspicious_command"
    assert "pgcil:auth" not in (response.candidate_spl.candidate_spl or "")
    limitations = " ".join((response.analyst_response.limitations if response.analyst_response else []) or []).lower()
    assert "failed login" not in limitations
    assert "mfa" not in limitations
    assert response.mitre_decision is not None
    assert response.mitre_decision.get("answer_visible") is True
    assert "evidence_supported" not in set((response.mitre_decision.get("evidence_statuses") or {}).values())


def test_dns_beaconing_candidate_returns_guidance_without_alert_context(monkeypatch) -> None:
    _enable_phase7(monkeypatch)
    monkeypatch.setattr("app.config.settings.mcp_global_execution_enabled", False)

    response = chat(
        ChatRequest(
            message=(
                "For a DNS beaconing candidate, give me the investigation steps, evidence required, "
                "MITRE mapping, limitations, and review-only SPL."
            )
        )
    )

    assert response.selected_use_case is not None
    assert response.selected_use_case.use_case_id == "dns_beaconing_candidate"
    assert response.human_review.review_type != "intent_clarification"
    assert "alert context" not in (response.message or "").lower()
    assert response.planning_decision["path_type"] == "hybrid_investigation"
    checklist = response.evidence_plan.get("checklist") or []
    assert checklist
    assert response.mitre_decision is not None
    assert response.mitre_decision.get("answer_visible") is True
    assert (response.mitre_decision.get("evidence_statuses") or {}).get("T1071") == "candidate"
    assert "evidence_supported" not in set((response.mitre_decision.get("evidence_statuses") or {}).values())
    if response.candidate_spl is not None:
        assert response.candidate_spl.template_id == "dns_beaconing_candidate"


def test_brute_force_sop_answer_is_knowledge_only_without_alert_analysis_wording(monkeypatch) -> None:
    _enable_phase7(monkeypatch)
    monkeypatch.setattr("app.chat.pipeline.retrieve_soc_kb", _fake_retrieve_collected)

    response = chat(
        ChatRequest(
            message=(
                "Show me the SOP for brute-force login investigation. "
                "Do not generate SPL unless required."
            )
        )
    )

    assert response.analyst_response is not None
    assert response.analyst_response.response_profile == "knowledge_recall"
    summary = (response.analyst_response.direct_answer_summary or "").lower()
    assert response.analyst_response.direct_answer_summary == (
        "Governed SOP retrieved. SPL and MCP were skipped as requested."
    )
    assert "p3" not in (response.analyst_response.severity_label or "").lower()
    assert not response.analyst_response.mitre_mappings
    assert not response.analyst_response.not_claimed
    for forbidden in (
        "incident",
        "breach",
        "severity",
        "mitre",
        "execution",
        "full scope",
        "security pipeline",
        "candidate authentication security event",
    ):
        assert forbidden not in summary
    assert response.answer_contract is not None
    assert response.answer_contract["severity_label"] is None
    assert response.answer_contract["mitre_technique_ids"] == []
    assert response.answer_contract["spl_status"] == "not_required"
    assert response.answer_contract["hil_status"] == "not_required"
    assert response.candidate_spl is None
    assert response.spl_validation is None
    title = (response.analyst_response.finding_title or "").lower()
    assert "failed login" in title or "sop" in title


def test_powershell_answer_shows_required_evidence_and_checklist(monkeypatch) -> None:
    _enable_phase7(monkeypatch)

    response = chat(
        ChatRequest(
            message=(
                "For suspicious PowerShell command execution on an endpoint, give me the analyst "
                "checklist, required evidence, MITRE status, and governed SPL for review."
            )
        )
    )

    analyst = response.analyst_response
    assert analyst is not None
    assert analyst.investigation_steps or analyst.analyst_checklist
    assert analyst.required_evidence
    assert analyst.analyst_checklist
    assert (analyst.render_sections or {}).get("investigation_guidance") is True
    assert response.evidence_plan.get("checklist")
    for key in (
        "host",
        "user",
        "command_line",
        "script_block_text",
        "event_id",
        "parent_process",
        "encoded_command_flag",
        "network_connection",
    ):
        assert any(item.startswith(f"{key} —") for item in analyst.required_evidence)
        assert key in analyst.missing_evidence
    joined = " ".join(
        [
            *analyst.limitations,
            *analyst.required_evidence,
            *analyst.analyst_checklist,
            *(response.answer_contract or {}).get("missing_evidence", []),
        ]
    ).lower()
    for phrase in ("privilege status", "asset criticality", "source ip ownership", "mfa", "post-login"):
        assert phrase not in joined
    if analyst.spl_status_detail is not None:
        detail = analyst.spl_status_detail
        if detail.get("template_status") == "active":
            assert "no active governed spl template" not in str(analyst.model_dump()).lower()
        if detail.get("block_reason") == "spl_template_active_source_profile_missing":
            assert analyst.spl_code is None
            assert "Candidate SPL" not in str(analyst.model_dump())
            assert str(analyst.model_dump()).lower().count("source profile missing") == 1
    contract = response.answer_contract or {}
    assert not contract.get("ruled_out_mitre")
    assert "ruled out" not in str(analyst.direct_answer_summary or "").lower()


def test_powershell_answer_uses_endpoint_limitations_not_auth(monkeypatch) -> None:
    _enable_phase7(monkeypatch)
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", False)

    response = chat(
        ChatRequest(
            message=(
                "For suspicious PowerShell command execution on an endpoint, give me the analyst "
                "checklist, required evidence, MITRE status, and governed SPL for review."
            )
        )
    )

    limitations = " ".join((response.analyst_response.limitations if response.analyst_response else []) or []).lower()
    assert "mfa" not in limitations
    assert "post-login" not in limitations
    assert "privilege status" not in limitations
    assert "powershell" in limitations or "encoded command" in limitations
    spl = (response.candidate_spl.candidate_spl if response.candidate_spl else "") or ""
    assert "pgcil:auth" not in spl
    if response.candidate_spl is not None:
        assert response.candidate_spl.template_id in {None, "edr_powershell_suspicious_command"}


def test_dns_answer_shows_required_evidence_and_checklist(monkeypatch) -> None:
    _enable_phase7(monkeypatch)

    response = chat(
        ChatRequest(
            message=(
                "For a DNS beaconing candidate, give me the investigation steps, evidence required, "
                "MITRE mapping, limitations, and review-only SPL."
            )
        )
    )

    analyst = response.analyst_response
    assert analyst is not None
    assert analyst.investigation_steps or analyst.analyst_checklist
    assert analyst.required_evidence
    assert analyst.analyst_checklist
    assert (analyst.render_sections or {}).get("investigation_guidance") is True
    for key in (
        "src",
        "dest",
        "domain",
        "periodicity",
        "jitter",
        "bytes_out",
        "DNS_query_count",
        "rare_domain_indicator",
        "user_host_association",
    ):
        assert any(item.startswith(f"{key} —") for item in analyst.required_evidence)
        assert key in analyst.missing_evidence
    joined = " ".join(
        [
            *analyst.limitations,
            *analyst.required_evidence,
            *analyst.analyst_checklist,
            *(response.answer_contract or {}).get("missing_evidence", []),
        ]
    ).lower()
    for phrase in ("privilege status", "asset criticality", "source ip ownership", "mfa", "post-login"):
        assert phrase not in joined
    if analyst.spl_status_detail is not None and analyst.spl_status_detail.get("template_status") == "active":
        assert "no active governed spl template" not in str(analyst.model_dump()).lower()
        if analyst.spl_status_detail.get("block_reason") == "spl_template_active_source_profile_missing":
            assert analyst.spl_code is None
            assert "Candidate SPL" not in str(analyst.model_dump())
            assert str(analyst.model_dump()).lower().count("source profile missing") == 1
    contract = response.answer_contract or {}
    assert not contract.get("ruled_out_mitre")
    assert "ruled out" not in str(analyst.direct_answer_summary or "").lower()
    steps = " ".join(analyst.investigation_steps or analyst.analyst_checklist or []).lower()
    assert "periodicity" in steps or "jitter" in steps
    limitations = " ".join(analyst.limitations or []).lower()
    assert "periodic" in limitations or "beaconing" in limitations or "benign" in limitations
    if analyst.not_claimed:
        reasons = " ".join(str(row.get("Reason") or "") for row in analyst.not_claimed).lower()
        assert (
            "insufficient" in reasons
            or "not claimed" in reasons
            or "required supporting evidence was not present" in reasons
        )


def test_dns_answer_surfaces_guidance_without_duplicate_spl_source_profile_message(monkeypatch) -> None:
    _enable_phase7(monkeypatch)

    response = chat(
        ChatRequest(
            message=(
                "For a DNS beaconing candidate, give me the investigation steps, evidence required, "
                "MITRE mapping, limitations, and review-only SPL."
            )
        )
    )

    analyst = response.analyst_response
    assert analyst is not None
    payload = str(analyst.model_dump()).lower()
    if analyst.spl_status_detail and analyst.spl_status_detail.get("block_reason"):
        assert (analyst.review_notice or "").lower().count("source profile missing") == 0
        assert payload.count("template active but source profile missing") == 0
    if analyst.spl_status_detail:
        assert payload.count("source profile missing") <= 1


def test_dns_answer_uses_network_limitations_not_auth(monkeypatch) -> None:
    _enable_phase7(monkeypatch)
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", False)

    response = chat(
        ChatRequest(
            message=(
                "For a DNS beaconing candidate, give me the investigation steps, evidence required, "
                "MITRE mapping, limitations, and review-only SPL."
            )
        )
    )

    limitations = " ".join((response.analyst_response.limitations if response.analyst_response else []) or []).lower()
    assert "mfa" not in limitations
    assert "post-login" not in limitations
    assert "privilege status" not in limitations
    assert "periodic" in limitations or "beaconing" in limitations or "c2" in limitations


def test_failed_login_mitre_summary_bucket_counts_from_contract(monkeypatch) -> None:
    from app.chat.contracts.answer_contract import build_answer_contract
    from app.chat.final_answer_readability import apply_final_answer_readability
    from app.schemas.responses import AnalystResponseEnvelope

    _enable_phase7(monkeypatch)
    contract = build_answer_contract(
        intent_classification={
            "intent_family": "hybrid_alert_review",
            "answer_goal": ["mitre_mapping", "spl_artifact"],
        },
        evidence_plan={"answer_mode": "hybrid", "spl_allowed": True, "mcp_allowed": False},
        mitre_decision={"answer_visible": True, "not_claimed": ["T1562.001", "T1003"]},
        severity_decision=None,
        spl_validation={"approved": True, "normalized_spl": "search index=pgcil_soc | stats count | head 10"},
        execution={"status": "skipped"},
        human_review={"required": False},
        mitre_mappings=[
            {"technique_id": "T1110.001", "status": "evidence_supported"},
            {"technique_id": "T1078", "status": "candidate"},
        ],
        mitre_branch_result={
            "evidence_supported_mitre": ["T1110.001"],
            "candidate_mitre": ["T1078"],
            "requires_validation_mitre": [],
            "not_claimed_mitre": ["T1562.001", "T1003"],
            "ruled_out_mitre": [],
        },
    )
    envelope = AnalystResponseEnvelope(
        mitre_mappings=[
            {"Technique": "T1110.001", "Status": "Evidence Supported"},
            {"Technique": "T1078", "Status": "Candidate"},
        ],
        not_claimed=[
            {"Technique": "T1562.001", "Status": "Not Claimed"},
            {"Technique": "T1003", "Status": "Not Claimed"},
        ],
        spl_code="search index=pgcil_soc | stats count | head 10",
        response_profile="hybrid_alert_review",
    )
    summary = apply_final_answer_readability(envelope, contract).direct_answer_summary or ""
    assert "1 evidence-supported MITRE technique" in summary
    assert "1 candidate technique" in summary
    assert "2 techniques not claimed due to insufficient supporting evidence" in summary


def test_dns_t1071_candidate_does_not_trigger_blocked_finding_guard(monkeypatch) -> None:
    from app.chat.final_answer_validator import validate_final_answer
    from app.schemas.responses import AnalystResponseEnvelope

    _enable_phase7(monkeypatch)
    response = chat(
        ChatRequest(
            message=(
                "For a DNS beaconing candidate, give me the investigation steps, evidence required, "
                "MITRE mapping, limitations, and review-only SPL."
            )
        )
    )
    assert response.answer_contract is not None
    assert "T1071" not in (response.answer_contract.get("not_claimed_technique_ids") or [])
    analyst = response.analyst_response or AnalystResponseEnvelope(
        mitre_mappings=[{"Technique": "T1071", "Status": "Candidate"}],
    )
    guard = validate_final_answer(
        analyst_response=analyst,
        answer_contract=response.answer_contract,
        evidence_plan=response.evidence_plan,
        mitre_decision=response.mitre_decision,
    )
    assert "final.blocked_finding_claimed" not in (guard.failed_checks or [])


def test_pure_sop_question_does_not_select_spl_branch(monkeypatch) -> None:
    _enable_phase7(monkeypatch)
    monkeypatch.setattr("app.chat.pipeline.retrieve_soc_kb", _fake_retrieve_collected)

    response = chat(ChatRequest(message="What is the playbook for brute force?"))

    assert response.planning_decision["branches"] == ["rag"]
    assert "spl" in response.planning_decision["blocked_tools"]
    assert response.candidate_spl is None
    assert response.spl_validation is None


def _fake_retrieve_collected(**kwargs: Any) -> dict[str, Any]:
    return {
        "retrieval_status": "retrieved",
        "retrieved_entries": [
            {
                "entry_id": "kb-sop-auth-1",
                "doc_id": "coe-auth-sop-v1",
                "document_type": "sop",
                "doc_title": "Failed login investigation SOP",
                "title": "Failed login investigation SOP",
                "source_excerpt": "Review scope, source distribution, affected users, and escalation criteria.",
                "citation": "COE Sample Auth Investigation SOP v1.0 AUTH-001",
                "approval_status": "coe_reviewed",
                "validation_status": "runtime_eligible",
                "recommended_actions": ["review_scope", "check_privileged_accounts"],
            }
        ],
        "warnings": [],
    }


def _fake_retrieve_no_match(**kwargs: Any) -> dict[str, Any]:
    return {
        "retrieval_status": "no_match",
        "retrieved_entries": [],
        "warnings": ["no_approved_soc_kb_match"],
    }
