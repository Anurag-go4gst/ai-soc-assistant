"""Build analyst-facing response envelopes for Experience Center and live /chat."""

from __future__ import annotations

import re
from typing import Any

from app.config import settings
from app.schemas.responses import AnalystResponseEnvelope
from app.chat.contracts.answer_contract import build_answer_contract
from app.spl.t2_generation import is_t2_spl_native_review
from app.chat.final_answer_readability import (
    apply_draft_preview_readability,
    apply_final_answer_readability,
    unglue_priority_action,
)
from app.chat.network_boundary_display import resolve_analyst_use_case_label, scrub_auth_anomaly_display_text
from app.risk.severity_policy import (
    ANALYTICS_REVIEW_TYPE_NOTE,
    ANALYTICS_SEVERITY_NOT_ASSIGNED_LABEL,
)
from app.threat.mitre_evidence_preconditions import PRECONDITION_BY_ID, not_claimed_reason

_INVESTIGATION_GUIDANCE_USE_CASES = frozenset(
    {
        "edr_powershell_suspicious_command",
        "dns_beaconing_candidate",
        "edr_suspicious_process",
    }
)

_FAILED_LOGIN_NUMERIC_COLUMNS = (
    "Failed logins",
    "fail_count",
    "failed_logins",
    "failure_count",
)



_SUMMARY_PREFIX_MARKERS = (
    "summarize for shift handoff:",
    "give a concise analyst summary:",
    "provide an analyst summary:",
    "analyst summary:",
    "summarize:",
    "summary:",
)




def _advisory_mitre_threshold_rows(user_query: str) -> list[dict[str, str]]:
    normalized = " ".join(str(user_query or "").lower().split())
    technique = "ICS remote command sequence (example)"
    if "dnp3" in normalized:
        technique = "DNP3 restart/output change sequence (example)"
    elif "modbus" in normalized:
        technique = "Modbus write/function-code abuse (example)"
    elif "beacon" in normalized:
        technique = "DNS/command beaconing (example)"
    return [
        {"technique": technique, "status": "candidate", "notes": "Threshold review only; validate with telemetry."},
        {"technique": "Status labels", "status": "not_claimed", "notes": "Confirmed/Candidate/Not-claimed per evidence gates."},
    ]

def alert_summary_default_actions() -> list[str]:
    return [
        "Confirm affected assets, identities, sources, and the observation window.",
        "Corroborate the described sequence in auth, endpoint, and network telemetry.",
        "Decide whether the activity is sanctioned maintenance or needs escalation.",
    ]


def build_alert_summary_message(
    *,
    user_query: str,
    evidence_plan: dict[str, Any] | None = None,
    severity_label: str | None = None,
    mitre_rows: list[dict[str, Any]] | None = None,
) -> str:
    """Deterministic shift-handoff summary: situation, confidence, actions, unknowns."""
    situation = _alert_summary_situation(user_query)
    confidence_lines: list[str] = []
    if severity_label and not severity_label.startswith(ANALYTICS_SEVERITY_NOT_ASSIGNED_LABEL):
        confidence_lines.append(
            f"Severity posture: {severity_label} — analyst validation required before escalation."
        )
    else:
        confidence_lines.append(
            "Confidence: moderate — the narrative is taken from the analyst prompt; "
            "no live Splunk query or MCP execution corroborated this turn."
        )
    if mitre_rows:
        technique_bits = [
            f"{row.get('Technique')} ({row.get('Status')})"
            for row in mitre_rows[:3]
            if row.get("Technique")
        ]
        if technique_bits:
            confidence_lines.append(
                "MITRE context (candidate/review-only): " + ", ".join(technique_bits) + "."
            )

    plan = evidence_plan if isinstance(evidence_plan, dict) else {}
    actions = _safe_display_list(plan.get("checklist") or [])
    if not actions:
        actions = alert_summary_default_actions()
    unknowns = _safe_display_list(plan.get("limitations") or plan.get("unsupported_claims_avoid") or [])
    if not unknowns:
        unknowns = [
            "Whether the described activity is authorized or malicious.",
            "Full scope of hosts, users, or OT assets beyond the narrative.",
            "Whether severity assignment or containment is warranted without corroboration.",
        ]

    return "\n\n".join(
        [
            "Analyst summary (review-only)",
            f"Situation\n{situation}",
            "Confidence\n" + "\n".join(f"- {line}" for line in confidence_lines),
            "Recommended actions\n" + "\n".join(f"- {item}" for item in actions[:5]),
            "Unknowns / gaps\n" + "\n".join(f"- {item}" for item in unknowns[:4]),
            "No Splunk search or MCP execution was performed for this summary turn.",
        ]
    )


def _alert_summary_situation(user_query: str) -> str:
    text = str(user_query or "").strip()
    normalized = " ".join(text.lower().split())
    for marker in _SUMMARY_PREFIX_MARKERS:
        if normalized.startswith(marker):
            text = text[len(marker) :].strip()
            break
    if not text:
        return "Analyst requested a concise handoff summary; no corroborating telemetry was queried."
    return text[0].upper() + text[1:] if len(text) > 1 else text



_BINDING_CLARIFICATION = (
    "SPL draft requires source-profile slot binding before review. "
    "Confirm index, sourcetype, and field mappings in Settings, then re-ask."
)


def _resolve_spl_surfaces_from_contract(
    *,
    contract: Any | None,
    candidate_spl: dict[str, Any] | None,
    spl_validation: dict[str, Any] | None,
    spl_draft_preview: dict[str, Any] | None,
    synthesis_draft: dict[str, Any],
    source_evidence: list[dict[str, Any]],
    execution: dict[str, Any],
    spl_code: str | None,
    draft_spl_code: str | None,
) -> tuple[str | None, str | None, dict[str, Any] | None, list[dict[str, Any]]]:
    """Single SPL surface driven by AnswerContract / RunContract mirror fields."""
    draft_preview = spl_draft_preview if isinstance(spl_draft_preview, dict) else None
    resolved_spl = spl_code
    resolved_draft = draft_spl_code
    table: list[dict[str, Any]] = []

    cand = candidate_spl if isinstance(candidate_spl, dict) else {}
    if (
        is_t2_spl_native_review(spl_validation, cand)
        and str(cand.get("candidate_spl") or "").strip()
    ):
        resolved_draft = _candidate_spl_text(candidate_spl, spl_validation, synthesis_draft)
        resolved_spl = None
        draft_preview = None

    if (
        contract is not None
        and getattr(contract, "run_contract_mirrored", False)
        and (
            getattr(contract, "spl_candidate_renderable", False)
            or getattr(contract, "spl_normalized", False)
            or getattr(contract, "spl_block_reason", None)
        )
    ):
        if getattr(contract, "spl_normalized", False):
            resolved_spl = _candidate_spl_text(candidate_spl, spl_validation, synthesis_draft)
            resolved_draft = None
            draft_preview = None
        elif getattr(contract, "spl_candidate_renderable", False):
            resolved_draft = str((draft_preview or {}).get("draft_spl") or "") or resolved_draft
            if not getattr(contract, "spl_normalized", False):
                resolved_spl = None
        else:
            resolved_spl = None
            resolved_draft = None
            draft_preview = None
        if str(getattr(contract, "spl_block_reason", "") or "") == "missing_slot_binding":
            resolved_spl = None
            resolved_draft = None
            draft_preview = None

    mirrored = contract is not None and getattr(contract, "run_contract_mirrored", False)
    if mirrored:
        allow_results = bool(getattr(contract, "allow_results_table", False))
    else:
        allow_results = str(execution.get("status") or "") == "executed"
    if allow_results and str(execution.get("status") or "") == "executed":
        table = _splunk_table_from_evidence(source_evidence) or _as_table_rows(
            synthesis_draft.get("splunk_results_table")
        )
    return resolved_spl, resolved_draft, draft_preview, table


def build_analyst_response_for_live(
    *,
    user_query: str,
    message: str,
    analyst_summary: str | None,
    source_evidence: list[dict[str, Any]],
    mitre_mappings: list[Any],
    severity_label: str | None,
    synthesis_draft: dict[str, Any] | None,
    human_review: dict[str, Any] | None,
    selected_use_case_label: str | None = None,
    candidate_spl: dict[str, Any] | None = None,
    spl_validation: dict[str, Any] | None = None,
    execution: dict[str, Any] | None = None,
    mitre_decision: dict[str, Any] | None = None,
    intent_classification: dict[str, Any] | None = None,
    evidence_plan: dict[str, Any] | None = None,
    severity_decision: Any | None = None,
    answer_contract: Any | None = None,
    spl_draft_preview: dict[str, Any] | None = None,
    llm_spl_candidate: dict[str, Any] | None = None,
) -> AnalystResponseEnvelope | None:
    """Assemble analyst card payload from governed live pipeline outputs."""
    draft = synthesis_draft if isinstance(synthesis_draft, dict) else {}
    execution_payload = execution if isinstance(execution, dict) else {}
    draft_preview = spl_draft_preview if isinstance(spl_draft_preview, dict) else None
    llm_candidate = llm_spl_candidate if isinstance(llm_spl_candidate, dict) else None
    draft_spl_code = str(draft_preview.get("draft_spl") or "") or None if draft_preview else None
    spl_code = _candidate_spl_text(candidate_spl, spl_validation, draft)
    table: list[dict[str, Any]] = []
    decision_payload = mitre_decision if isinstance(mitre_decision, dict) else None
    mitre_rows = _mitre_display_rows(mitre_mappings, user_query=user_query)
    if not mitre_rows and decision_payload and decision_payload.get("answer_visible"):
        techniques = decision_payload.get("techniques") or []
        if isinstance(techniques, list) and techniques:
            mitre_rows = _mitre_display_rows(techniques, user_query=user_query)
    if not mitre_rows and not decision_payload:
        mitre_rows = _as_table_rows(draft.get("mitre_mappings"))
    not_claimed = _not_claimed_rows(decision_payload)
    playbook, sop_guidance, rag_meta = _playbook_from_rag(source_evidence)
    reference_facts = _reference_facts_from_evidence(source_evidence)
    recommended = _recommended_actions_from_draft(draft) or _recommended_from_rag(source_evidence)
    if not recommended and draft_preview:
        recommended = _safe_display_list(draft_preview.get("investigation_checklist") or [])
    binding_derived = bool(draft_preview and draft_preview.get("metadata_source") == "binding_derived")
    if binding_derived and draft_preview:
        initial_from_draft = _safe_display_list(draft_preview.get("initial_assessment") or [])
    else:
        initial_from_draft = []
    if not recommended and user_query and not binding_derived:
        from app.chat.signal_class_guidance import _TEMPLATES, classify_signal_class

        signal_class = classify_signal_class(user_query)
        template = _TEMPLATES.get(signal_class) or {}
        recommended = [str(item) for item in template.get("evidence") or [] if item]
    # Single AnswerContract: prefer the pipeline-built projection; build only as
    # a fallback so the builder never makes a second, divergent contract.
    contract = answer_contract
    plan = evidence_plan if isinstance(evidence_plan, dict) else {}
    has_display_plan = bool(
        plan.get("checklist")
        or plan.get("investigation_workflow")
        or plan.get("required_evidence_keys")
        or plan.get("limitations")
    )
    if contract is None and (True or has_display_plan):
        contract = build_answer_contract(
            intent_classification=intent_classification,
            evidence_plan=evidence_plan,
            mitre_decision=decision_payload,
            severity_decision=severity_decision,
            spl_validation=spl_validation if isinstance(spl_validation, dict) else None,
            execution=execution_payload,
            human_review=human_review if isinstance(human_review, dict) else None,
            mitre_mappings=mitre_mappings,
            user_query=user_query,
        )
    if str(plan.get("use_case_id") or "") == "soc_show_catalogue_index":
        from app.knowledge.mapping_exports import format_catalogue_inventory_answer

        inventory = format_catalogue_inventory_answer()
        lead = inventory.split("\n", 1)[0]
        envelope = AnalystResponseEnvelope(
            scenario_label=selected_use_case_label,
            finding_title=selected_use_case_label or "Catalogue index",
            one_sentence_finding=lead,
            direct_answer_summary=inventory,
            response_profile="knowledge_recall",
            execution_status=str(execution_payload.get("status") or "skipped") or None,
            spl_code=None,
            draft_spl_code=None,
            spl_draft_preview=None,
        )
        if contract is not None:
            envelope = apply_final_answer_readability(envelope, contract)
            envelope = envelope.model_copy(
                update={
                    "direct_answer_summary": inventory,
                    "one_sentence_finding": lead,
                    "spl_code": None,
                    "draft_spl_code": None,
                    "spl_draft_preview": None,
                    "response_profile": "knowledge_recall",
                }
            )
        return envelope
    spl_code, draft_spl_code, draft_preview, table = _resolve_spl_surfaces_from_contract(
        contract=contract,
        candidate_spl=candidate_spl if isinstance(candidate_spl, dict) else None,
        spl_validation=spl_validation if isinstance(spl_validation, dict) else None,
        spl_draft_preview=draft_preview,
        synthesis_draft=draft,
        source_evidence=source_evidence,
        execution=execution_payload,
        spl_code=spl_code,
        draft_spl_code=draft_spl_code,
    )
    if not (contract is not None and getattr(contract, "run_contract_mirrored", False)):
        cand = candidate_spl if isinstance(candidate_spl, dict) else {}
        if spl_code and cand.get("generation_mode") == "llm_spl_advisory_fallback":
            draft_spl_code = None
            draft_preview = None
        elif spl_code and isinstance(spl_validation, dict) and spl_validation.get("approved"):
            draft_spl_code = None
            draft_preview = None
    from app.chat.guidance_templates import (
        build_mitre_evidence_threshold_guidance,
        is_mitre_evidence_threshold_query,
    )

    if user_query and is_mitre_evidence_threshold_query(user_query):
        threshold_message = build_mitre_evidence_threshold_guidance(user_query)
        direct = str(message or "").strip() or threshold_message
        if len(direct) < 120:
            direct = threshold_message
        recommended = [
            "Apply Confirmed/Candidate/Not-claimed labels with explicit evidence thresholds.",
            "Corroborate OT/protocol logs and engineering workstation context.",
            "Do not declare technique-level conclusions from this question alone.",
        ]
        envelope = AnalystResponseEnvelope(
            finding_title="MITRE evidence thresholds",
            one_sentence_finding=direct[:1200],
            direct_answer_summary=direct[:2000],
            recommended_actions=recommended,
            analyst_checklist=recommended,
            investigation_steps=recommended,
            response_profile="knowledge_recall",
            execution_status=str(execution_payload.get("status") or "skipped") or None,
            mitre_mappings=_advisory_mitre_threshold_rows(user_query),
            severity_label=severity_label,
        )
        if contract is not None:
            preserved_mitre = list(envelope.mitre_mappings or [])
            envelope = apply_final_answer_readability(envelope, contract)
            envelope = envelope.model_copy(update={"mitre_mappings": preserved_mitre})
        return envelope
    intent = intent_classification if isinstance(intent_classification, dict) else {}
    if str(intent.get("intent_family") or "") == "cve_investigation":
        from app.chat.guidance_templates import build_cve_investigation_guidance

        cve_message = build_cve_investigation_guidance(user_query)
        direct = str(message or "").strip() or cve_message
        if not direct.startswith("CVE investigation"):
            direct = cve_message
        recommended = _safe_display_list(plan.get("checklist") or [])[:8] or [
            "Map installed package/version rows for affected software.",
            "Review exposure signals without live scanning.",
            "Check vulnerability_source onboarding before unpatched claims.",
            "List missing scanner/CMDB and exploit-attempt evidence.",
        ]
        envelope = AnalystResponseEnvelope(
            finding_title="CVE investigation guidance",
            one_sentence_finding=direct[:1200],
            direct_answer_summary=direct[:2000],
            recommended_actions=recommended,
            analyst_checklist=recommended,
            investigation_steps=recommended,
            response_profile="hybrid_alert_review",
            execution_status=str(execution_payload.get("status") or "skipped") or None,
            mitre_mappings=mitre_rows,
            severity_label=severity_label,
        )
        if contract is not None:
            envelope = apply_final_answer_readability(envelope, contract)
        return envelope
    if _is_reference_knowledge_plan(intent, plan):
        direct = _reference_summary(
            reference_facts,
            user_query=user_query,
            source_evidence=source_evidence,
        )
        lead = reference_one_sentence_lead(reference_facts, user_query=user_query)
        recommended = _safe_display_list(plan.get("checklist") or [])[:8] or [
            "Use the cited offline reference rows as taxonomy context only.",
            "Do not treat taxonomy relevance as observed activity in local telemetry.",
            "Collect live evidence separately before claiming exploitation, severity, or confirmed technique use.",
        ]
        envelope = AnalystResponseEnvelope(
            finding_title="Reference taxonomy lookup",
            one_sentence_finding=lead[:1200],
            direct_answer_summary=direct[:4000],
            recommended_actions=recommended,
            analyst_checklist=recommended,
            investigation_steps=recommended,
            response_profile="knowledge_recall",
            execution_status=str(execution_payload.get("status") or "skipped") or None,
            reference_facts=reference_facts[:10],
            retrieved_playbook=build_reference_source_playbook(
                reference_facts[:10],
                source_evidence=source_evidence,
            ),
            severity_label=severity_label,
        )
        if contract is not None:
            envelope = apply_final_answer_readability(envelope, contract)
        return envelope
    if str(intent.get("primary_intent") or "") == "cross_skill_investigation":
        from app.synthesis.deterministic_prose_stitch import build_cross_skill_investigation_message

        cross_message = build_cross_skill_investigation_message(user_query)
        direct = str(message or "").strip() or cross_message
        if "Cross-skill investigation plan" not in direct:
            direct = cross_message
        recommended = [
            "CVE leg: confirm affected versions and missing patch evidence.",
            "MITRE leg: apply candidate/not-claimed labels with evidence thresholds.",
            "GitHub leg: collect actor, PAT, commit timeline, workflow diff, and audit events.",
        ]
        envelope = AnalystResponseEnvelope(
            finding_title="Cross-skill investigation plan",
            one_sentence_finding=direct[:1200],
            direct_answer_summary=direct[:2000],
            recommended_actions=recommended,
            analyst_checklist=recommended,
            investigation_steps=recommended,
            response_profile="hybrid_alert_review",
            execution_status=str(execution_payload.get("status") or "skipped") or None,
            mitre_mappings=_advisory_mitre_threshold_rows(user_query),
            severity_label=severity_label,
        )
        if contract is not None:
            preserved_mitre = list(envelope.mitre_mappings or [])
            envelope = apply_final_answer_readability(envelope, contract)
            envelope = envelope.model_copy(update={"mitre_mappings": preserved_mitre})
        return envelope
    if str(intent.get("intent_family") or "") == "github_investigation":
        from app.chat.guidance_templates import build_github_investigation_guidance

        github_message = build_github_investigation_guidance(user_query)
        direct = str(message or "").strip() or github_message
        if not direct.startswith("GitHub investigation"):
            direct = github_message
        recommended = _safe_display_list(plan.get("checklist") or [])[:8]
        if not recommended:
            recommended = [
                "Actor / username: map PAT or OAuth identity to org/repo membership.",
                "Token type / PAT provenance: scope, creation, last use, rotation status.",
                "Commit SHA / timeline and workflow file diff in the observation window.",
                "Audit log events: repo.push, workflow_dispatch, oauth_access for the actor.",
            ]
        envelope = AnalystResponseEnvelope(
            finding_title="GitHub investigation guidance",
            one_sentence_finding=direct[:1200],
            direct_answer_summary=direct[:2000],
            recommended_actions=recommended,
            analyst_checklist=recommended,
            investigation_steps=recommended,
            response_profile="hybrid_alert_review",
            execution_status=str(execution_payload.get("status") or "skipped") or None,
            mitre_mappings=mitre_rows,
            severity_label=severity_label,
        )
        if contract is not None:
            envelope = apply_final_answer_readability(envelope, contract)
        return envelope
    if str(intent.get("intent_family") or "") == "alert_summary":
        summary_message = build_alert_summary_message(
            user_query=user_query,
            evidence_plan=plan,
            severity_label=severity_label,
            mitre_rows=mitre_rows,
        )
        direct = str(message or "").strip()
        if direct.startswith("Analyst summary (review-only)") and "Situation" in direct:
            pass  # _chat_message already rendered the summary body
        elif not direct or _ROUTING_COMPLETE_ONLY.search(direct) or "generic soc guidance path selected" in direct.lower():
            direct = summary_message
        elif direct == summary_message:
            pass
        else:
            direct = f"{summary_message}\n\n{direct}".strip()
        recommended = _safe_display_list(plan.get("checklist") or [])[:6] or alert_summary_default_actions()
        envelope = AnalystResponseEnvelope(
            finding_title="Analyst summary",
            one_sentence_finding=direct[:1200],
            direct_answer_summary=direct[:2000],
            recommended_actions=recommended,
            analyst_checklist=recommended,
            response_profile="hybrid_alert_review",
            execution_status=str(execution_payload.get("status") or "skipped") or None,
            mitre_mappings=mitre_rows,
            severity_label=severity_label,
        )
        if contract is not None:
            envelope = apply_final_answer_readability(envelope, contract)
        return envelope
    summary = _governed_summary(
        analyst_summary,
        mitre_rows,
        not_claimed,
        contract,
        intent_family=str(intent.get("intent_family") or "") or None,
        answer_mode=str(plan.get("answer_mode") or "") or None,
        playbook=playbook,
        sop_guidance=sop_guidance,
    )
    if not any([table, mitre_rows, not_claimed, playbook, summary, recommended, spl_code, draft_spl_code, llm_candidate]):
        minimal = build_minimal_guidance_envelope(
            user_query=user_query,
            message=message,
            contract=contract,
            evidence_plan=plan,
            human_review=human_review if isinstance(human_review, dict) else None,
            execution=execution_payload,
            mitre_rows=mitre_rows,
            draft_spl_code=draft_spl_code,
            spl_draft_preview=draft_preview,
            selected_use_case_label=selected_use_case_label,
        )
        if minimal is not None:
            return minimal
        return None
    resolved_use_case_label = resolve_analyst_use_case_label(
        use_case_id=str(plan.get("use_case_id") or "") or None,
        catalog_label=selected_use_case_label,
        user_query=user_query,
    )
    finding = scrub_auth_anomaly_display_text(
        _finding_title(
            message,
            user_query,
            resolved_use_case_label,
            intent_family=str(intent.get("intent_family") or "") or None,
            answer_mode=str(plan.get("answer_mode") or "") or None,
            playbook=playbook,
        ),
        user_query=user_query,
    )
    execution_status = str(execution_payload.get("status") or "") or None
    executed_spl = str(execution_payload.get("executed_spl") or "") or None
    if execution_status == "executed":
        response_profile = "spl_executed"
    elif spl_code and mitre_rows:
        response_profile = "hybrid_alert_review"
    elif spl_code:
        response_profile = "spl_only"
    elif plan.get("answer_mode") == "rag_only" or intent.get("intent_family") in {"sop_or_playbook", "policy_knowledge"}:
        response_profile = "knowledge_recall"
    elif mitre_rows or str(plan.get("use_case_id") or "") in _INVESTIGATION_GUIDANCE_USE_CASES:
        response_profile = "hybrid_alert_review"
    else:
        response_profile = None

    review_notice = None
    if not draft_preview and isinstance(human_review, dict) and human_review.get("required"):
        review_type = str(human_review.get("review_type") or "")
        if review_type != "intent_clarification":
            review_notice = str(
                human_review.get("safe_message_for_user") or "Analyst review is required before execution."
            )
    elif spl_code and execution_status != "executed":
        review_notice = "Candidate SPL — review only, not executed."

    severity_confidence, severity_rationale = _severity_confidence(
        user_query,
        execution_payload,
        intent_family=str(intent.get("intent_family") or "") or None,
        answer_mode=str(plan.get("answer_mode") or "") or None,
    )
    severity_safety_note = _severity_safety_note(user_query, response_profile)
    knowledge_profile = (
        plan.get("answer_mode") == "rag_only"
        or intent.get("intent_family") in {"sop_or_playbook", "policy_knowledge", "knowledge_only"}
    )
    display_severity = None if knowledge_profile else severity_label
    severity_not_assigned = bool(
        display_severity and display_severity.startswith(ANALYTICS_SEVERITY_NOT_ASSIGNED_LABEL)
    )
    if severity_not_assigned:
        severity_confidence = None
        severity_rationale = ANALYTICS_REVIEW_TYPE_NOTE
    if (
        not knowledge_profile
        and not severity_not_assigned
        and review_notice
        and severity_label
        and "review required" not in severity_label.lower()
    ):
        display_severity = f"{severity_label} — Review required"

    if (
        isinstance(draft_preview, dict)
        and isinstance(candidate_spl, dict)
        and candidate_spl.get("llm_fallback_used")
        and not str(candidate_spl.get("candidate_spl") or "").strip()
    ):
        draft_preview = {**draft_preview, "fallback_after_llm": True}
    spl_unbound_constraints = _spl_unbound_constraints(
        candidate_spl if isinstance(candidate_spl, dict) else None,
        draft_preview if isinstance(draft_preview, dict) else None,
    )

    envelope = AnalystResponseEnvelope(
        scenario_label=scrub_auth_anomaly_display_text(resolved_use_case_label, user_query=user_query),
        initial_assessment=initial_from_draft,
        severity_label=display_severity,
        severity_confidence=severity_confidence,
        severity_rationale=severity_rationale,
        severity_safety_note=severity_safety_note,
        finding_title=finding,
        one_sentence_finding=summary,
        splunk_status_line=_splunk_status_line(table, execution_payload),
        splunk_results_table=table,
        mitre_mappings=mitre_rows,
        not_claimed=not_claimed,
        retrieved_playbook=_enrich_playbook(playbook, rag_meta),
        sop_guidance=sop_guidance,
        recommended_actions=recommended,
        spl_code=spl_code,
        spl_draft_preview=draft_preview,
        spl_unbound_constraints=spl_unbound_constraints,
        draft_spl_code=draft_spl_code,
        llm_spl_candidate=llm_candidate,
        executed_spl=executed_spl,
        execution_status=execution_status,
        response_profile=response_profile,
        review_notice=review_notice,
        evidence_summary=summarize_failed_login_events(table),
    )
    if contract is not None:
        envelope = apply_final_answer_readability(envelope, contract)
    elif draft_spl_code:
        envelope = apply_draft_preview_readability(envelope)
    return envelope


def _spl_unbound_constraints(
    candidate_spl: dict[str, Any] | None,
    draft_preview: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    constraints: list[dict[str, Any]] = []
    if isinstance(draft_preview, dict):
        raw = draft_preview.get("unbound_constraints")
        if isinstance(raw, list):
            constraints.extend(item for item in raw if isinstance(item, dict))
    if isinstance(candidate_spl, dict):
        trace = candidate_spl.get("spl_binding_trace")
        if isinstance(trace, dict):
            raw = trace.get("unbound_constraints")
            if isinstance(raw, list):
                constraints.extend(item for item in raw if isinstance(item, dict))
        bindings = candidate_spl.get("user_constraint_bindings")
        if isinstance(bindings, dict):
            raw = bindings.get("unbound_constraints")
            if isinstance(raw, list):
                constraints.extend(item for item in raw if isinstance(item, dict))
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for item in constraints:
        key = (
            str(item.get("slot") or ""),
            str(item.get("value") or item.get("dropped_value") or ""),
            str(item.get("reason") or ""),
            str(item.get("source") or item.get("dropped_source") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(dict(item))
    return deduped


def build_minimal_guidance_envelope(
    *,
    user_query: str,
    message: str,
    contract: Any | None,
    evidence_plan: dict[str, Any],
    human_review: dict[str, Any] | None,
    execution: dict[str, Any],
    mitre_rows: list[dict[str, Any]],
    draft_spl_code: str | None,
    spl_draft_preview: dict[str, Any] | None,
    selected_use_case_label: str | None,
) -> AnalystResponseEnvelope | None:
    """Guidance-only envelope when evidence conclusions are unavailable."""
    checklist = _safe_display_list(evidence_plan.get("checklist") or [])
    investigation = _safe_display_list(evidence_plan.get("investigation_workflow") or [])
    limitations = _safe_display_list(evidence_plan.get("limitations") or [])
    required = [str(item) for item in evidence_plan.get("required_evidence_keys") or [] if item]
    if contract is not None:
        checklist = checklist or list(contract.analyst_checklist_safe)
        investigation = investigation or list(contract.investigation_steps)
        limitations = limitations or list(contract.limitations)
        required = required or list(contract.required_evidence)
    has_guidance = bool(checklist or investigation or limitations or required or draft_spl_code or spl_draft_preview)
    if not has_guidance and (not message or _ROUTING_COMPLETE_ONLY.search(message)):
        return None

    direct = str(message or "").strip()
    if contract is not None and contract.missing_evidence:
        direct = (
            f"{direct}\n\nEvidence still needed: "
            + "; ".join(str(item) for item in contract.missing_evidence[:8])
        ).strip()
    if checklist:
        checklist_block = "\n".join(f"- {item}" for item in checklist[:8])
        prefix = f"SOC review checklist:\n\n{checklist_block}"
        direct = f"{direct}\n\n{prefix}".strip() if direct else prefix
    recommended: list[str] = [str(item) for item in checklist[:6]]
    if not recommended:
        recommended = [str(item) for item in investigation[:4]]
    exec_label = str(execution.get("status") or "skipped")
    review_notice = None
    if isinstance(human_review, dict) and human_review.get("required"):
        review_notice = str(
            human_review.get("safe_message_for_user") or "Analyst review is required before execution."
        )
    elif draft_spl_code or spl_draft_preview:
        review_notice = "Candidate SPL — review only; Splunk search was not run."

    envelope = AnalystResponseEnvelope(
        scenario_label=scrub_auth_anomaly_display_text(selected_use_case_label, user_query=user_query),
        finding_title=selected_use_case_label or "SOC investigation guidance",
        one_sentence_finding=direct[:1200] if direct else "SOC investigation guidance",
        direct_answer_summary=direct[:1200] if direct else None,
        mitre_mappings=mitre_rows,
        recommended_actions=recommended,
        spl_code=None,
        draft_spl_code=draft_spl_code,
        spl_draft_preview=spl_draft_preview,
        execution_status=exec_label,
        response_profile="hybrid_alert_review",
        review_notice=review_notice,
        analyst_checklist=checklist,
        limitations=limitations,
    )
    if contract is not None:
        envelope = apply_final_answer_readability(envelope, contract)
        if recommended and not envelope.recommended_actions:
            envelope = envelope.model_copy(update={"recommended_actions": recommended})
    elif spl_draft_preview:
        envelope = apply_draft_preview_readability(envelope)
    return envelope


_ROUTING_COMPLETE_ONLY = re.compile(r"^routing complete\.?\s*spl is not required", re.IGNORECASE)


def _safe_display_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(item) for item in values if item]


def _reference_facts_from_evidence(source_evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for evidence in source_evidence:
        if evidence.get("source_type") != "reference_dataset":
            continue
        for row in evidence.get("preview_rows") or []:
            if isinstance(row, dict):
                facts.append(dict(row))
            if len(facts) >= 10:
                return facts
    return facts


def _is_reference_knowledge_plan(intent: dict[str, Any], plan: dict[str, Any]) -> bool:
    if str(intent.get("intent_family") or "") == "reference_knowledge":
        return True
    if "reference_lookup" in {str(item) for item in intent.get("answer_goal") or []}:
        return True
    if "reference_taxonomy_lookup" in {str(item) for item in plan.get("reasons") or []}:
        return True
    if "reference_dataset" in {str(item) for item in plan.get("required_evidence_keys") or []}:
        return True
    return "reference_registry" in {str(item) for item in plan.get("required_sources") or []}


_REFERENCE_GOVERNANCE_FOOTER = (
    "Note: Reference taxonomy only — not confirmed activity in your environment "
    "without separate live evidence."
)

_REFERENCE_DATASET_SOURCES: dict[str, dict[str, str]] = {
    "mitre_atlas": {
        "title": "MITRE ATLAS reference bundle",
        "id": "mitre_atlas",
        "version": "5.6.0",
        "citation": "docs/threat-intel/atlas/raw/ATLAS.yaml",
        "bundle_detail": (
            "ATLAS.yaml + atlas_casestudies_normalized.json + atlas_mitigations_normalized.json"
        ),
        "purpose": (
            "Operator-vendored MITRE ATLAS matrix with linked case studies and mitigations "
            "from the governed reference registry."
        ),
    },
    "mitre_attack_enterprise": {
        "title": "MITRE ATT&CK Enterprise reference export",
        "id": "mitre_attack_enterprise",
        "version": "enterprise-attack",
        "citation": "docs/threat-intel/attack/enterprise-attack.json",
        "bundle_detail": "Operator-vendored ATT&CK enterprise technique export",
        "purpose": "Local MITRE ATT&CK Enterprise technique definitions from the reference registry.",
    },
    "cve": {
        "title": "CVE reference snapshot",
        "id": "cve",
        "version": "local-snapshot",
        "citation": "operator-vendored CVE snapshot",
        "bundle_detail": "Governed local CVE reference rows",
        "purpose": "Offline CVE identifier lookup from the reference registry (not a live scanner feed).",
    },
}


def _reference_dataset_label(dataset: str) -> str:
    if dataset == "mitre_atlas":
        return "MITRE ATLAS"
    if dataset == "mitre_attack_enterprise":
        return "MITRE ATT&CK Enterprise"
    if dataset == "cve":
        return "CVE reference"
    return "Offline reference"


def _reference_evidence_id(source_evidence: list[dict[str, Any]] | None) -> str | None:
    for envelope in source_evidence or []:
        if envelope.get("source_type") != "reference_dataset":
            continue
        evidence_id = str(envelope.get("evidence_id") or "").strip()
        if evidence_id:
            return evidence_id
    return None


def build_reference_source_playbook(
    reference_facts: list[dict[str, Any]],
    *,
    source_evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    if not reference_facts:
        return None
    dataset = str(
        reference_facts[0].get("source_dataset") or reference_facts[0].get("dataset_id") or "reference_dataset"
    ).strip()
    catalog = _REFERENCE_DATASET_SOURCES.get(dataset, {})
    evidence_id = _reference_evidence_id(source_evidence)
    title = catalog.get("title") or f"{_reference_dataset_label(dataset)} reference bundle"
    return {
        "title": title,
        "id": catalog.get("id") or dataset,
        "version": catalog.get("version"),
        "purpose": catalog.get("purpose")
        or "Governed reference taxonomy lookup from the local operator-vendored bundle.",
        "citation": catalog.get("citation") or catalog.get("bundle_detail") or dataset,
        "retrieval_mode": "reference_registry",
        "source_evidence_id": evidence_id,
        "bundle_detail": catalog.get("bundle_detail"),
        "provenance_tier": str(reference_facts[0].get("provenance_tier") or "operator_vendored_reference"),
    }


def _reference_source_header(
    reference_facts: list[dict[str, Any]],
    *,
    source_evidence: list[dict[str, Any]] | None = None,
) -> str:
    playbook = build_reference_source_playbook(reference_facts, source_evidence=source_evidence)
    if not playbook:
        return "Reference registry lookup"
    parts = [str(playbook.get("title") or "Reference bundle")]
    version = str(playbook.get("version") or "").strip()
    if version:
        parts.append(f"v{version}" if not version.startswith("v") else version)
    citation = str(playbook.get("citation") or "").strip()
    if citation:
        parts.append(f"bundle: {citation}")
    bundle_detail = str(playbook.get("bundle_detail") or "").strip()
    if bundle_detail and bundle_detail != citation:
        parts.append(bundle_detail)
    parts.append("registry: reference_registry")
    evidence_id = str(playbook.get("source_evidence_id") or "").strip()
    if evidence_id:
        parts.append(f"evidence: {evidence_id}")
    return " · ".join(parts)


def _reference_first_sentence(text: str, *, max_len: int = 220) -> str:
    cleaned = " ".join(str(text or "").split())
    if not cleaned:
        return ""
    for sep in (". ", "? ", "! "):
        idx = cleaned.find(sep)
        if idx != -1:
            cleaned = cleaned[: idx + 1]
            break
    if len(cleaned) > max_len:
        return cleaned[: max_len - 1].rstrip() + "…"
    return cleaned


def _rank_atlas_case_studies(
    case_studies: list[dict[str, Any]],
    user_query: str | None,
) -> list[dict[str, Any]]:
    if not case_studies:
        return []
    query = " ".join(str(user_query or "").lower().split())
    tokens = {word for word in re.findall(r"[a-z0-9]{3,}", query)}
    if "mcp" in query:
        tokens.update({"mcp", "cursor", "tool", "server", "exfil", "poison"})
    if "prompt" in query or "injection" in query:
        tokens.update({"prompt", "injection", "indirect", "jailbreak"})
    if not tokens:
        return case_studies

    def score(item: dict[str, Any]) -> tuple[int, str]:
        blob = f"{item.get('name', '')} {item.get('id', '')}".lower()
        return (-sum(1 for token in tokens if token in blob), str(item.get("id") or ""))

    return sorted(case_studies, key=score)


def _reference_named_item(item: dict[str, Any], *, id_key: str, name_key: str) -> str:
    name = str(item.get(name_key) or "").strip()
    item_id = str(item.get(id_key) or "").strip()
    if name and item_id:
        return f"{name} ({item_id})"
    return name or item_id


def _reference_tactics_display(tactics_raw: Any, dataset: str) -> str | None:
    if isinstance(tactics_raw, list):
        tactics = [str(item).strip() for item in tactics_raw if str(item).strip()]
    else:
        tactics = [str(tactics_raw).strip()] if str(tactics_raw or "").strip() else []
    if not tactics:
        return None
    if dataset == "mitre_atlas":
        from app.knowledge.mapping_exports import atlas_tactic_label_map

        labels = atlas_tactic_label_map()
        rendered: list[str] = []
        for tactic in tactics:
            if tactic in labels:
                rendered.append(labels[tactic])
            elif "-" in tactic and not tactic.startswith("AML."):
                rendered.append(tactic.replace("-", " ").title())
            else:
                rendered.append(tactic)
        return ", ".join(dict.fromkeys(rendered))
    return ", ".join(tactics)


def reference_narration_seed(
    reference_facts: list[dict[str, Any]],
    *,
    user_query: str | None = None,
) -> str:
    """Compact governed reference facts for live-model narration (not the full analyst card)."""
    if not reference_facts:
        return (
            "No matching offline reference facts were found in the local registry snapshot. "
            "No live telemetry or environment exposure is claimed."
        )
    lines: list[str] = []
    if user_query and str(user_query).strip():
        lines.append(f"Analyst question: {str(user_query).strip()}")
    count = len(reference_facts)
    lines.append(f"Matched {count} governed reference {'entry' if count == 1 else 'entries'}:")
    for index, fact in enumerate(reference_facts[:5], start=1):
        reference_id = str(fact.get("reference_id") or fact.get("technique_id") or "").strip()
        name = str(fact.get("name") or "").strip()
        dataset = str(fact.get("source_dataset") or fact.get("dataset_id") or "reference_dataset").strip()
        title = " — ".join(item for item in (reference_id, name) if item).strip() or f"Reference {index}"
        description = _reference_first_sentence(str(fact.get("description") or ""))[:220]
        line = f"{index}. [{dataset}] {title}"
        if description and not any(
            token in description.lower() for token in ("not found", "unknown reference")
        ):
            line += f": {description}"
        lines.append(line)
    lines.append(
        "Taxonomy context only — do not claim confirmed activity, severity, or exploitation in local telemetry."
    )
    return "\n".join(lines).strip()[:1200]


def merge_reference_message_with_llm_intro(
    reference_summary: str,
    *,
    llm_intro: str | None,
) -> str:
    """Prepend live-model prose to the deterministic reference card when narration succeeded."""
    intro = str(llm_intro or "").strip()
    summary = str(reference_summary or "").strip()
    if not intro or intro == summary:
        return summary
    return f"{intro}\n\n{summary}"


def reference_one_sentence_lead(
    reference_facts: list[dict[str, Any]],
    *,
    user_query: str | None = None,
) -> str:
    del user_query
    if not reference_facts:
        return (
            "No matching offline reference facts were found in the local registry snapshot. "
            "No live telemetry or environment exposure is claimed."
        )
    count = len(reference_facts)
    first = reference_facts[0]
    reference_id = str(first.get("reference_id") or first.get("technique_id") or "").strip()
    name = str(first.get("name") or "").strip()
    dataset = str(first.get("source_dataset") or first.get("dataset_id") or "reference_dataset").strip()
    source_label = _reference_dataset_label(dataset)
    label = " ".join(item for item in (reference_id, name) if item).strip() or source_label
    if count == 1:
        return f"{source_label} reference lookup matched {label}."
    return (
        f"{source_label} reference lookup matched {count} techniques; "
        f"the strongest textual match is {label}."
    )


def _reference_summary(
    reference_facts: list[dict[str, Any]],
    *,
    user_query: str | None = None,
    source_evidence: list[dict[str, Any]] | None = None,
) -> str:
    if not reference_facts:
        return (
            "No matching offline reference facts were found in the local registry snapshot. "
            "No live telemetry or environment exposure is claimed."
        )
    first_dataset = str(
        reference_facts[0].get("source_dataset") or reference_facts[0].get("dataset_id") or "reference_dataset"
    ).strip()
    lines = [
        f"Source: {_reference_source_header(reference_facts, source_evidence=source_evidence)}",
        "",
        (
            "The following entries were resolved from the governed reference registry and relate to your question. "
            "They describe how adversaries may operate — not confirmed activity in your environment."
        ),
        "",
    ]
    for index, fact in enumerate(reference_facts[:5], start=1):
        reference_id = str(fact.get("reference_id") or fact.get("technique_id") or "").strip()
        name = str(fact.get("name") or "").strip()
        dataset = str(fact.get("source_dataset") or fact.get("dataset_id") or first_dataset).strip()
        title = " — ".join(item for item in (reference_id, name) if item).strip() or f"Reference {index}"
        lines.append(f"{index}. {title}")
        tactics = _reference_tactics_display(fact.get("tactics"), dataset)
        if tactics:
            lines.append(f"   Tactics: {tactics}")
        description = _reference_first_sentence(str(fact.get("description") or ""))
        if description and not any(
            token in description.lower() for token in ("not found", "unknown reference")
        ):
            lines.append(f"   Summary: {description}")
        if dataset == "mitre_atlas":
            enrichment = (fact.get("raw") or {}).get("atlas_enrichment") if isinstance(fact.get("raw"), dict) else None
            if isinstance(enrichment, dict):
                mitigation_items = [
                    item
                    for item in enrichment.get("mitigations") or []
                    if isinstance(item, dict) and str(item.get("name") or "").strip()
                ][:3]
                case_items = _rank_atlas_case_studies(
                    [
                        item
                        for item in enrichment.get("case_studies") or []
                        if isinstance(item, dict) and str(item.get("name") or "").strip()
                    ],
                    user_query,
                )[:3]
                if mitigation_items:
                    rendered = "; ".join(
                        _reference_named_item(item, id_key="id", name_key="name") for item in mitigation_items
                    )
                    lines.append(f"   Mitigations: {rendered}")
                if case_items:
                    rendered = "; ".join(
                        _reference_named_item(item, id_key="id", name_key="name") for item in case_items
                    )
                    lines.append(f"   Related incidents: {rendered}")
        elif dataset == "cve":
            description = str(fact.get("description") or "").strip()
            if description:
                lines.append(f"   Status: {description}")
        lines.append("")
    lines.append(_REFERENCE_GOVERNANCE_FOOTER)
    return "\n".join(lines).strip()


def reference_summary_line(
    reference_facts: list[dict[str, Any]],
    *,
    user_query: str | None = None,
    source_evidence: list[dict[str, Any]] | None = None,
) -> str:
    """Public entry point for the deterministic synthesis draft (lab_runner.py):
    render the same governed reference-taxonomy summary this builder uses,
    so `analyst_summary` and `analyst_response.one_sentence_finding` never diverge."""
    return _reference_summary(
        reference_facts,
        user_query=user_query,
        source_evidence=source_evidence,
    )


def summarize_failed_login_events(rows: list[dict[str, Any]]) -> str | None:
    """Explain total failed-login event count when the table supports it."""
    if not rows:
        return None
    total, parts = _sum_failed_login_events(rows)
    if total is None or not parts:
        return None
    breakdown = " + ".join(str(part) for part in parts)
    return (
        f"{total} total failed-login events across {len(parts)} source row(s) ({breakdown}). "
        "Counts are failure events, not a global distinct-user total; use per-source "
        '"Distinct users by source" columns only.'
    )


def attach_evidence_summary(payload: dict[str, Any]) -> dict[str, Any]:
    """Add computed evidence_summary when a splunk table is present."""
    table = payload.get("splunk_results_table") or []
    if not isinstance(table, list):
        return payload
    summary = summarize_failed_login_events([row for row in table if isinstance(row, dict)])
    if summary:
        return {**payload, "evidence_summary": summary}
    return payload


def _sum_failed_login_events(rows: list[dict[str, Any]]) -> tuple[int | None, list[int]]:
    values: list[int] = []
    for row in rows:
        for column in _FAILED_LOGIN_NUMERIC_COLUMNS:
            if column in row and isinstance(row[column], (int, float)):
                values.append(int(row[column]))
                break
    if not values:
        return None, []
    return sum(values), values


def _splunk_table_from_evidence(source_evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for envelope in source_evidence:
        if envelope.get("source_type") != "splunk_mcp":
            continue
        if str(envelope.get("collection_status") or "") != "collected":
            continue
        preview = envelope.get("preview_rows") or []
        if not isinstance(preview, list):
            continue
        rows = [row for row in preview if isinstance(row, dict)]
        if not rows:
            continue
        return [_normalize_splunk_row(row) for row in rows[:10]]
    return []


def _normalize_splunk_row(row: dict[str, Any]) -> dict[str, Any]:
    mapping = {
        "host": "Host",
        "src": "Source IP",
        "fail_count": "Failed logins",
        "failed_logins": "Failed logins",
        "distinct_users": "Distinct users by source",
        "distinct_users_by_source": "Distinct users by source",
        "first_seen": "First seen",
        "last_seen": "Last seen",
        "action": "Action",
        "user": "User",
    }
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        label = mapping.get(str(key), str(key).replace("_", " ").title())
        normalized[label] = value
    return normalized


def _mitre_display_rows(mappings: list[Any], *, user_query: str = "") -> list[dict[str, Any]]:
    query_l = user_query.lower()
    success_after_failure = (
        "successful login" in query_l
        and any(term in query_l for term in ("followed", "after failure", "after failures", "after failed"))
        and "no successful login" not in query_l
    )
    rows: list[dict[str, Any]] = []
    for item in mappings:
        payload = item.model_dump() if hasattr(item, "model_dump") else dict(item)
        status = str(payload.get("status") or "")
        confidence = (
            "High - evidence supported"
            if status in {"supported", "evidence_supported"}
            else "Medium"
            if status == "candidate"
            else "Moderate - analyst validation required"
        )
        technique_id = str(payload.get("technique_id") or "")
        evidence = str(payload.get("why") or "")
        if technique_id == "T1110.001" and status == "candidate":
            if success_after_failure:
                evidence = "Repeated failed logins indicate possible password guessing."
            else:
                evidence = (
                    "Repeated failed login attempts across multiple accounts from external IPs "
                    "may indicate password guessing / brute-force behavior."
                )
        if technique_id == "T1078" and status == "candidate":
            evidence = (
                "Successful login after repeated failures may indicate valid credential use, "
                "but compromise is not confirmed."
            )
        rows.append(
            {
                "Technique": technique_id,
                "Name": payload.get("name"),
                "Tactic": payload.get("tactic"),
                "Status": status.replace("_", " ").title(),
                "Evidence": evidence,
                "Confidence": confidence,
            }
        )
    return rows


def _not_claimed_rows(mitre_decision: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Build Not-Claimed rows from the MITRE decision.

    Reasons/names come from the tactic-general evidence-precondition table
    (Commit 1), not a per-technique dict — so any technique demoted for absent
    evidence renders with a governed reason, across all tactics.
    """
    if not mitre_decision:
        return []
    ids: list[str] = []
    for field in ("rejected_techniques", "not_claimed"):
        values = mitre_decision.get(field)
        if not isinstance(values, list):
            continue
        for value in values:
            technique_id = str(value)
            if technique_id and technique_id not in ids:
                ids.append(technique_id)
    rows: list[dict[str, Any]] = []
    for technique_id in ids:
        precondition = PRECONDITION_BY_ID.get(technique_id)
        rows.append(
            {
                "Technique": technique_id,
                "Name": precondition.name if precondition is not None else "Not claimed",
                "Status": "Not Claimed",
                "Reason": not_claimed_reason(technique_id),
            }
        )
    return rows


def _governed_summary(
    analyst_summary: str | None,
    mitre_rows: list[dict[str, Any]],
    not_claimed: list[dict[str, Any]],
    contract: Any | None,
    *,
    intent_family: str | None = None,
    answer_mode: str | None = None,
    playbook: dict[str, Any] | None = None,
    sop_guidance: dict[str, Any] | None = None,
) -> str | None:
    """One-sentence finding, driven by the AnswerContract — not query re-parsing.

    The success-after-failure framing keys on `contract.success_after_failure_context`
    (a deterministic projection), not literal substrings in the user query.
    """
    if intent_family in {"sop_or_playbook", "policy_knowledge"} or answer_mode == "rag_only":
        return None
    summary = (analyst_summary or "").strip() or None
    has_t1110_candidate = any(
        row.get("Technique") == "T1110.001" and str(row.get("Status") or "").lower() == "candidate"
        for row in mitre_rows
    )
    has_t1078_candidate = any(
        row.get("Technique") == "T1078" and str(row.get("Status") or "").lower() == "candidate"
        for row in mitre_rows
    )
    success_after_failure = bool(getattr(contract, "success_after_failure_context", False))
    if success_after_failure and has_t1110_candidate and has_t1078_candidate:
        return (
            "Repeated failed logins followed by a successful login from the same user in the last hour "
            "is a candidate authentication security event. Severity should increase to P1 if the user is "
            "privileged, the asset is critical, the source IP is suspicious, MFA was bypassed, or abnormal "
            "post-login activity is confirmed."
        )
    if has_t1110_candidate and not_claimed:
        return (
            "Based on the provided activity, this is a candidate authentication security event. "
            "T1110.001 Password Guessing is candidate-mapped because repeated failed login attempts "
            "across multiple accounts from external IPs may indicate password guessing / brute-force behavior."
        )
    if not summary:
        return None
    return summary.replace("security alert has been triggered", "activity can be treated as a candidate security event")


def _playbook_from_rag(
    source_evidence: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
    for envelope in source_evidence:
        if envelope.get("source_type") != "rag" or envelope.get("collection_status") != "collected":
            continue
        preview = envelope.get("preview_rows") or []
        if not isinstance(preview, list) or not preview:
            continue
        row = next((_rag_playbook_row(item) for item in preview if isinstance(item, dict) and _rag_playbook_row(item)), None)
        if row is None:
            continue
        doc_title = str(
            row.get("doc_title") or row.get("title") or row.get("entry_title") or "SOC knowledge document"
        )
        doc_id = str(row.get("citation") or row.get("entry_id") or "soc_kb").split("#")[0]
        version = str(row.get("doc_version") or "")
        playbook = {
            "title": doc_title,
            "id": doc_id,
            "version": f"v{version}" if version and not version.startswith("v") else version or None,
            "purpose": str(row.get("source_excerpt") or "Governed SOC knowledge guidance for this investigation."),
        }
        rag_meta = {
            "citation": row.get("citation"),
            "retrieval_mode": row.get("retrieval_mode") or envelope.get("provider_used") or "governed_soc_kb",
            "confidence": row.get("confidence"),
            "source_evidence_id": envelope.get("evidence_id"),
            "document_type": row.get("document_type"),
        }
        actions = [str(item) for item in row.get("recommended_actions") or []]
        sop_guidance = {
            "triage_steps": actions or [str(row.get("source_excerpt") or "")],
            "validation_notes": actions
            or [
                "Confirm scope against approved SOP before closure.",
                "Validate missing evidence items listed in the analysis summary.",
            ],
        }
        return playbook, sop_guidance, rag_meta
    return None, None, None


def _rag_playbook_row(row: dict[str, Any]) -> dict[str, Any] | None:
    document_type = str(row.get("document_type") or "").lower()
    entry_type = str(row.get("entry_type") or "").lower()
    if document_type in {"mitre_enterprise_reference", "mitre_ics_reference"}:
        return None
    if entry_type in {"mitre_mapping", "mitre_reference"}:
        return None
    return row


def _enrich_playbook(playbook: dict[str, Any] | None, rag_meta: dict[str, Any] | None) -> dict[str, Any] | None:
    if not playbook:
        return None
    if not rag_meta:
        return playbook
    return {**playbook, **{k: v for k, v in rag_meta.items() if v is not None}}


def _recommended_actions_from_draft(draft: dict[str, Any]) -> list[str]:
    actions = draft.get("recommended_actions")
    if not isinstance(actions, list):
        return []
    formatted: list[str] = []
    for index, item in enumerate(actions):
        text = unglue_priority_action(str(item))
        if re.match(r"^P[1-4]\s*[—-]\s*", text):
            formatted.append(re.sub(r"^P([1-4])\s*-\s*", r"P\1 — ", text))
        else:
            priority = "P1" if index == 0 else "P2" if index == 1 else "P3"
            formatted.append(f"{priority} — {text}")
    return formatted


def _recommended_from_rag(source_evidence: list[dict[str, Any]]) -> list[str]:
    for envelope in source_evidence:
        if envelope.get("source_type") != "rag":
            continue
        for row in envelope.get("preview_rows") or []:
            if not isinstance(row, dict):
                continue
            actions = row.get("recommended_actions")
            if isinstance(actions, list) and actions:
                return [_format_rag_action(str(item)) for item in actions[:6]]
    return []


def _format_rag_action(text: str) -> str:
    cleaned = unglue_priority_action(text)
    if re.match(r"^P[1-4]\s*[—-]\s*", cleaned):
        return cleaned
    return f"P2 — {cleaned.replace('_', ' ')}"


def _splunk_status_line(table: list[dict[str, Any]], execution: dict[str, Any] | None = None) -> str | None:
    if not table:
        return None
    execution = execution or {}
    if execution.get("status") == "executed":
        mode = "mock" if execution.get("splunk_result_envelope", {}).get("origin") == "fixture" else "governed"
        return f"Splunk MCP executed ({mode}) · {int(execution.get('result_count') or len(table))} row(s)"
    first = table[0]
    index = first.get("index") or first.get("Index") or "pgcil_soc"
    host = first.get("Host") or first.get("host")
    host_part = f" · host={host}" if host else ""
    return f"Splunk evidence [index={index}]{host_part} · governed retrieval window"


def _candidate_spl_text(
    candidate_spl: dict[str, Any] | None,
    spl_validation: dict[str, Any] | None,
    draft: dict[str, Any],
) -> str | None:
    if isinstance(spl_validation, dict) and spl_validation.get("normalized_spl"):
        return str(spl_validation["normalized_spl"])
    if isinstance(candidate_spl, dict) and candidate_spl.get("candidate_spl"):
        return str(candidate_spl["candidate_spl"])
    if draft.get("candidate_spl"):
        return str(draft["candidate_spl"])
    return None


def _finding_title(
    message: str,
    user_query: str,
    use_case_label: str | None,
    *,
    intent_family: str | None = None,
    answer_mode: str | None = None,
    playbook: dict[str, Any] | None = None,
) -> str | None:
    if intent_family in {"sop_or_playbook", "policy_knowledge"} or answer_mode == "rag_only":
        if isinstance(playbook, dict) and playbook.get("title"):
            return str(playbook["title"])
        return "Governed SOC knowledge"
    alert_match = re.search(r"\b(?:alert|alt)[\s:=]+([A-Za-z0-9][\w.-]*)", user_query, re.IGNORECASE)
    if alert_match:
        return f"Alert {alert_match.group(1)} review"
    text = (message or "").strip()
    if text and len(text) < 120 and not _is_generic_pipeline_message(text):
        return text
    if use_case_label:
        return use_case_label
    query = user_query.strip()
    if query:
        return query[:100] + ("…" if len(query) > 100 else "")
    return None


def _severity_confidence(
    user_query: str,
    execution: dict[str, Any],
    *,
    intent_family: str | None = None,
    answer_mode: str | None = None,
) -> tuple[str | None, str | None]:
    if intent_family in {"sop_or_playbook", "policy_knowledge"} or answer_mode == "rag_only":
        return None, None
    if execution.get("status") == "executed":
        return "High", None
    query_l = user_query.lower()
    if re.search(r"\balt-\d", query_l) or "for alert" in query_l:
        return (
            "Medium",
            "User supplied an alert pattern, but asset criticality, privilege status, source ownership, "
            "MFA, and post-login behavior are still missing.",
        )
    return None, None


def _severity_safety_note(user_query: str, response_profile: str | None) -> str | None:
    if response_profile != "hybrid_alert_review":
        return None
    query_l = user_query.lower()
    if "successful login" in query_l and any(
        term in query_l for term in ("followed", "after failure", "after failures", "after failed")
    ):
        return (
            "This is not confirmed account compromise; it is a candidate authentication security event "
            "pending validation."
        )
    return None


def _is_generic_pipeline_message(text: str) -> bool:
    lowered = text.lower()
    return (
        lowered.startswith("routing")
        or "spl validation complete" in lowered
        or "mcp execution is disabled" in lowered
        or "governed spl draft ready" in lowered
        or lowered.startswith("i need alert context")
        or lowered.startswith("a governed draft answer")
        or lowered.startswith("novel operation proposals stop")
        or lowered.startswith("governed knowledge path selected")
        or lowered.startswith("no governed kb/sop match")
    )


def _as_table_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]
