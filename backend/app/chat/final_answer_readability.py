"""Final answer readability layer — presentation only; no authority changes."""

from __future__ import annotations

import re
from typing import Any

from app.chat.contracts.answer_contract import AnswerContract
from app.chat.guidance_templates import scrub_blocked_context_display_phrasing
from app.schemas.responses import AnalystResponseEnvelope
from app.spl.draft_preview import (
    DRAFT_PREVIEW_FORBIDDEN_PHRASES,
    DRAFT_PREVIEW_STATUS_MESSAGE,
    build_draft_preview_analyst_message,
)

_EXECUTION_LABELS = {
    "review_only_not_executed": "Review only — not executed",
    "validated_not_executed": "Validated — not executed",
    "execution_pending_mcp_unavailable": "Execution pending — MCP unavailable",
    "executed_mock_evidence": "Executed — mock evidence",
    "executed_live_evidence": "Executed — live evidence",
    "blocked_approval_required": "Blocked — approval required",
}

_ALERT_REVIEW_LIMITATIONS = [
    "Privilege status missing",
    "Asset criticality missing",
    "Source IP ownership missing",
    "MFA result missing",
    "Post-login activity missing",
]

_LIMITATION_LABELS = {
    "success_after_failure": "Success-after-failure confirmation missing",
    "privileged_account_impacted": "Privilege status missing",
    "critical_asset": "Asset criticality missing",
    "confirmed_success": "Successful login confirmation missing",
    "source_ownership": "Source IP ownership missing",
    "mfa_status": "MFA result missing",
    "post_login_activity": "Post-login activity missing",
    "host": "Host context missing",
    "user": "User context missing",
    "command_line": "Command line missing",
    "script_block_text": "Script block logs missing",
    "event_id": "Event ID missing",
    "parent_process": "Parent process missing",
    "encoded_command_flag": "Encoded-command indicator missing",
    "network_connection": "Network connection context missing",
    "src": "Source host/IP missing",
    "dest": "Destination missing",
    "domain": "DNS domain missing",
    "periodicity": "Periodicity measurement missing",
    "jitter": "Jitter measurement missing",
    "bytes_out": "Outbound bytes missing",
    "DNS_query_count": "DNS query volume missing",
    "rare_domain_indicator": "Domain rarity assessment missing",
    "user_host_association": "User/host association missing",
}

_EXCLUDED_LIMITATIONS_WHEN_SUCCESS_STATED = {"confirmed_success", "success_after_failure"}

_AGG_SPLIT = re.compile(r"\s+(?=(?:count|values|min|max|sum|avg|list|dc|earliest|latest)\()", re.IGNORECASE)

# Analyst lead-in for draft-preview answers. Must not repeat the DRAFT_WARNING
# phrase ("Lab-only draft SPL preview…") — narrative tests require it to appear
# exactly once across message + summary + review notice.
_DRAFT_FAMILY_LEAD_INS = {
    "network_smb_top_talkers": (
        "This is an analytics/ranking question: identify which hosts generate the most "
        "SMB traffic. No governed SPL template is bound for it yet, so a draft search is "
        "provided for SOC review. It aggregates SMB sessions (ports 445/139 or "
        "smb/cifs/microsoft-ds applications) by source host — connection count, total "
        "bytes, distinct destinations, and first/last seen. The draft is review-only and "
        "has not been executed."
    ),
}
_DRAFT_GENERIC_LEAD_IN = (
    "A governed SPL template is not bound for this question yet, so a draft search is "
    "provided for SOC review. Validate the index, sourcetype, and field placeholders "
    "against your source profile; the draft is review-only and has not been executed."
)


def _draft_preview_lead_in(spl_draft_preview: Any) -> str:
    preview = spl_draft_preview if isinstance(spl_draft_preview, dict) else {}
    family = str(preview.get("detection_family") or "")
    return _DRAFT_FAMILY_LEAD_INS.get(family, _DRAFT_GENERIC_LEAD_IN)


def apply_draft_preview_readability(envelope: AnalystResponseEnvelope) -> AnalystResponseEnvelope:
    """Presentation-only overlay when a lab draft SPL preview is shown without AnswerContract."""
    if not envelope.draft_spl_code:
        return envelope
    payload = envelope.model_dump()
    payload["draft_spl_code"] = _format_spl_multiline(payload.get("draft_spl_code"))
    payload["render_sections"] = dict(payload.get("render_sections") or {})
    payload["section_order"] = list(payload.get("section_order") or [])
    payload["render_sections"]["draft_spl_preview"] = True
    if "draft_spl_preview" not in payload["section_order"]:
        payload["section_order"] = ["draft_spl_preview", *payload["section_order"]]
    payload["spl_status"] = "review_required"
    payload["hil_status"] = "required"
    draft_preview = payload.get("spl_draft_preview") if isinstance(payload.get("spl_draft_preview"), dict) else {}
    payload["spl_status_detail"] = {
        "template_status": "unavailable",
        "generation_status": "draft_preview",
        "generation": "draft_preview_lab",
        "review_required": True,
        "block_reason": "governed_spl_not_ready",
        "reason": "draft_preview_lab",
        "reason_display": "Draft preview — HIL/SOC review required.",
        "required_log_fields": list(draft_preview.get("required_log_fields") or []),
        "required_source_profile_fields": list(
            draft_preview.get("required_source_profile_fields") or []
        ),
        "required_fields": list(draft_preview.get("required_log_fields") or []),
    }
    payload["direct_answer_summary"] = _draft_preview_lead_in(payload.get("spl_draft_preview"))
    payload["analyst_checklist"] = list(draft_preview.get("investigation_checklist") or [])
    payload = _scrub_draft_preview_contradictions(payload)
    payload["one_sentence_finding"] = None
    return AnalystResponseEnvelope.model_validate(payload)


def apply_final_answer_readability(
    envelope: AnalystResponseEnvelope,
    contract: AnswerContract | None,
) -> AnalystResponseEnvelope:
    if contract is None:
        return apply_draft_preview_readability(envelope)
    payload = envelope.model_dump()
    payload["spl_code"] = _format_spl_multiline(payload.get("spl_code"))
    payload["draft_spl_code"] = _format_spl_multiline(payload.get("draft_spl_code"))
    payload["executed_spl"] = _format_spl_multiline(payload.get("executed_spl"))
    payload["execution_status_label"] = contract.execution_status_display
    payload["spl_status"] = contract.spl_status
    payload["hil_status"] = contract.hil_status
    payload["missing_evidence"] = list(contract.missing_evidence)
    payload["analyst_checklist"] = list(contract.analyst_checklist_safe)
    payload["investigation_steps"] = list(contract.investigation_steps)
    payload["unsupported_claims_avoid"] = list(contract.unsupported_claims_avoid)
    payload["mitre_status_summary"] = {
        "candidate": list(contract.candidate_mitre),
        "evidence_supported": list(contract.evidence_supported_mitre),
        "requires_validation": list(contract.requires_validation_mitre),
        "not_claimed": list(contract.not_claimed_mitre),
        "ruled_out": list(contract.ruled_out_mitre),
    }
    payload["limitations"] = _limitations_display(contract)
    payload["required_evidence"] = _required_evidence_display(contract)
    payload["spl_status_detail"] = contract.spl_status_detail
    payload["section_order"] = list(contract.section_order)
    payload["render_sections"] = dict(contract.render_sections)
    if payload.get("draft_spl_code"):
        payload["render_sections"]["draft_spl_preview"] = True
        if "draft_spl_preview" not in payload["section_order"]:
            payload["section_order"] = ["draft_spl_preview", *list(payload["section_order"])]
        payload["spl_status"] = "review_required"
        draft_preview = payload.get("spl_draft_preview") if isinstance(payload.get("spl_draft_preview"), dict) else {}
        payload["spl_status_detail"] = {
            "template_status": "unavailable",
            "generation_status": "draft_preview",
            "generation": "draft_preview_lab",
            "review_required": True,
            "block_reason": "governed_spl_not_ready",
            "reason": "draft_preview_lab",
            "reason_display": "Draft preview — HIL/SOC review required.",
            "required_log_fields": list(draft_preview.get("required_log_fields") or []),
            "required_source_profile_fields": list(
                draft_preview.get("required_source_profile_fields") or []
            ),
            "required_fields": list(draft_preview.get("required_log_fields") or []),
        }
        payload["hil_status"] = "required"
        payload["analyst_checklist"] = list(draft_preview.get("investigation_checklist") or [])
        payload["direct_answer_summary"] = None
        payload = _scrub_draft_preview_contradictions(payload)
    payload["direct_answer_summary"] = _direct_answer_summary(envelope, contract)
    payload = _apply_knowledge_profile_cleanup(payload, contract)
    payload = _dedupe_labels(payload, contract)
    payload = _apply_section_visibility(payload, contract)
    payload["recommended_actions"] = _scrub_blocked_context_actions(
        _format_investigation_actions(payload.get("recommended_actions") or []),
        contract,
    )
    if payload.get("investigation_steps"):
        payload["investigation_steps"] = _scrub_blocked_context_actions(
            [str(item) for item in payload.get("investigation_steps") or []],
            contract,
        )
    if payload.get("direct_answer_summary"):
        payload["direct_answer_summary"] = _maybe_scrub_direct_answer_summary(
            str(payload["direct_answer_summary"]),
            contract,
        )
    return AnalystResponseEnvelope.model_validate(payload)


def _scrub_draft_preview_contradictions(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove narrative lines that contradict a visible lab draft SPL preview."""
    for key in (
        "finding_title",
        "one_sentence_finding",
        "review_notice",
        "splunk_status_line",
        "foundation_sec_analysis",
    ):
        value = payload.get(key)
        if isinstance(value, str) and _contains_draft_forbidden_phrase(value):
            payload[key] = None
    return payload


def _contains_draft_forbidden_phrase(text: str) -> bool:
    lowered = (text or "").lower()
    return any(phrase in lowered for phrase in DRAFT_PREVIEW_FORBIDDEN_PHRASES)


def _direct_answer_summary(envelope: AnalystResponseEnvelope, contract: AnswerContract) -> str:
    if envelope.draft_spl_code:
        return _draft_preview_lead_in(envelope.spl_draft_preview)
    if contract.intent_family == "mitre_explanation":
        text = envelope.one_sentence_finding or envelope.direct_answer_summary
        if text:
            return str(text)
    if contract.intent_family in {"sop_or_playbook", "policy_knowledge"} or (
        contract.answer_mode == "rag_only" and contract.spl_status == "not_required"
    ):
        return _sop_knowledge_summary(envelope, contract)
    if contract.intent_family == "hybrid_alert_review":
        return _natural_hybrid_alert_summary(envelope, contract)

    lines: list[str] = []
    include_severity = "severity_assessment" not in contract.answer_goal
    for section in contract.section_order:
        if section == "severity_assessment" and include_severity and envelope.severity_label:
            conf = envelope.severity_confidence or contract.severity_confidence
            line = f"Severity: {envelope.severity_label}"
            if conf:
                line = f"{line} (confidence {conf})"
            lines.append(line)
        elif section == "mitre_mapping" and contract.render_sections.get("mitre_mapping"):
            mapped = len(envelope.mitre_mappings or [])
            blocked = len(envelope.not_claimed or [])
            if mapped:
                lines.append(f"MITRE: {mapped} candidate mapping(s) require validation.")
            if blocked:
                lines.append(f"MITRE: {blocked} technique(s) not claimed.")
        elif section == "spl_artifact" and envelope.spl_code and contract.execution_status_display:
            lines.append(f"SPL: {contract.execution_status_display}.")
        elif section == "policy_citation" and envelope.retrieved_playbook:
            title = str((envelope.retrieved_playbook or {}).get("title") or "SOC policy guidance")
            lines.append(f"Policy: {title}.")
        elif (
            section == "live_results"
            and envelope.splunk_results_table
            and contract.execution_status_label in {"executed_mock_evidence", "executed_live_evidence"}
        ):
            lines.append(f"Live results: {len(envelope.splunk_results_table)} row(s) retrieved.")
    if not lines and envelope.one_sentence_finding:
        return str(envelope.one_sentence_finding)
    return " ".join(lines)


def _apply_knowledge_profile_cleanup(payload: dict[str, Any], contract: AnswerContract) -> dict[str, Any]:
    if contract.answer_mode != "rag_only" and contract.intent_family not in {
        "sop_or_playbook",
        "policy_knowledge",
        "knowledge_only",
    }:
        return payload
    payload["severity_label"] = None
    payload["severity_confidence"] = None
    payload["severity_rationale"] = None
    payload["severity_safety_note"] = None
    payload["mitre_mappings"] = []
    payload["not_claimed"] = []
    payload["mitre_status_summary"] = {
        "candidate": [],
        "evidence_supported": [],
        "requires_validation": [],
        "not_claimed": [],
        "ruled_out": [],
    }
    payload["limitations"] = []
    payload["investigation_steps"] = []
    payload["analyst_checklist"] = []
    payload["required_evidence"] = []
    payload["missing_evidence"] = []
    payload["spl_code"] = None
    payload["executed_spl"] = None
    payload["review_notice"] = None
    payload["spl_status"] = "not_required"
    payload["spl_status_detail"] = None
    return payload


def _sop_knowledge_summary(envelope: AnalystResponseEnvelope, contract: AnswerContract) -> str:
    return "Governed SOP retrieved. SPL and MCP were skipped as requested."


def _hybrid_mitre_bucket_counts(
    envelope: AnalystResponseEnvelope,
    contract: AnswerContract,
) -> tuple[int, int, int, int, int]:
    evidence_supported = len(contract.evidence_supported_mitre)
    candidate = len(contract.candidate_mitre)
    requires_validation = len(contract.requires_validation_mitre)
    not_claimed = len(contract.not_claimed_mitre)
    ruled_out = len(contract.ruled_out_mitre)

    if not any((evidence_supported, candidate, requires_validation)) and envelope.mitre_mappings:
        for row in envelope.mitre_mappings:
            if not isinstance(row, dict):
                continue
            status = str(row.get("Status") or "").lower()
            if "evidence supported" in status or status == "supported":
                evidence_supported += 1
            elif "candidate" in status:
                candidate += 1
            elif "validation" in status:
                requires_validation += 1

    if not_claimed == 0 and ruled_out == 0 and envelope.not_claimed:
        not_claimed = len(
            [
                row
                for row in envelope.not_claimed
                if isinstance(row, dict) and str(row.get("Technique") or "")
            ]
        )
    return evidence_supported, candidate, requires_validation, not_claimed, ruled_out


def _natural_hybrid_alert_summary(envelope: AnalystResponseEnvelope, contract: AnswerContract) -> str:
    parts: list[str] = []
    summary_bits: list[str] = []
    evidence_supported, candidate, requires_validation, not_claimed, ruled_out = _hybrid_mitre_bucket_counts(
        envelope,
        contract,
    )

    if evidence_supported:
        summary_bits.append(
            f"{evidence_supported} evidence-supported MITRE technique{'s' if evidence_supported != 1 else ''}"
        )
    if candidate:
        summary_bits.append(f"{candidate} candidate technique{'s' if candidate != 1 else ''}")
    if requires_validation:
        summary_bits.append(
            f"{requires_validation} technique{'s' if requires_validation != 1 else ''} requiring validation"
        )
    if not_claimed:
        summary_bits.append(
            f"{not_claimed} technique{'s' if not_claimed != 1 else ''} not claimed due to insufficient supporting evidence"
        )
    if ruled_out:
        summary_bits.append(
            f"{ruled_out} technique{'s' if ruled_out != 1 else ''} ruled out by available evidence"
        )

    if summary_bits:
        if len(summary_bits) == 1:
            parts.append(f"The alert has {summary_bits[0]}.")
        else:
            parts.append(f"The alert has {', '.join(summary_bits[:-1])}, and {summary_bits[-1]}.")
    if envelope.spl_code and contract.execution_status_display:
        if contract.execution_status_display.startswith("Review only"):
            parts.append(
                "A governed SPL draft is available for review only and has not been executed."
            )
        else:
            parts.append(f"A governed SPL draft is available ({contract.execution_status_display.lower()}).")
    elif envelope.draft_spl_code:
        parts.append(DRAFT_PREVIEW_STATUS_MESSAGE)
    return " ".join(parts) if parts else str(envelope.one_sentence_finding or "")


def _dedupe_labels(payload: dict[str, Any], contract: AnswerContract) -> dict[str, Any]:
    exec_label = contract.execution_status_display or ""
    review_notice = str(payload.get("review_notice") or "")
    spl_detail = contract.spl_status_detail or {}
    review_lower = review_notice.lower()
    if spl_detail:
        blocked = spl_detail.get("generation_status") == "blocked"
        source_profile_block = (
            spl_detail.get("block_reason") == "spl_template_active_source_profile_missing"
            or "source profile missing" in review_lower
        )
        generic_candidate_notice = (
            "candidate spl" in review_lower
            and ("review only" in review_lower or "not executed" in review_lower)
        )
        if not payload.get("spl_code") or source_profile_block or (blocked and generic_candidate_notice):
            payload["review_notice"] = None
            review_notice = ""
    if exec_label and review_notice:
        if "review only" in review_notice.lower() or "not executed" in review_notice.lower():
            payload["review_notice"] = exec_label
    if payload.get("direct_answer_summary"):
        payload["one_sentence_finding"] = None
    return payload


def _apply_section_visibility(payload: dict[str, Any], contract: AnswerContract) -> dict[str, Any]:
    render = contract.render_sections
    if not render.get("mitre_mapping"):
        payload["mitre_mappings"] = []
    if not render.get("not_claimed"):
        payload["not_claimed"] = []
    if not render.get("policy_citation") and not render.get("procedural_steps"):
        if contract.answer_mode == "rag_only" or (
            contract.intent_family in {"spl_generation_only", "hybrid_alert_review"}
            and "policy_citation" not in contract.answer_goal
        ):
            payload["retrieved_playbook"] = None
            payload["sop_guidance"] = None
    if not (
        render.get("analyst_action_guidance")
        or render.get("policy_citation")
        or render.get("procedural_steps")
        or render.get("investigation_guidance")
    ):
        payload["recommended_actions"] = []
    if not render.get("live_results"):
        payload["splunk_results_table"] = []
        payload["splunk_status_line"] = None
        payload["evidence_summary"] = None
    if contract.answer_mode == "rag_only" and not render.get("spl_artifact"):
        payload["spl_code"] = None
        payload["executed_spl"] = None
        payload["review_notice"] = None
    return payload


_EVIDENCE_LABELS = {
    "host": "Host context",
    "user": "User context",
    "command_line": "Command line",
    "script_block_text": "Script block logs",
    "event_id": "Event ID",
    "parent_process": "Parent process",
    "encoded_command_flag": "Encoded-command indicator",
    "network_connection": "Network connection context",
    "src": "Source host/IP",
    "dest": "Destination",
    "domain": "DNS domain",
    "periodicity": "Periodicity measurement",
    "jitter": "Jitter measurement",
    "bytes_out": "Outbound bytes",
    "DNS_query_count": "DNS query volume",
    "rare_domain_indicator": "Domain rarity assessment",
    "user_host_association": "User/host association",
    "privileged_account_impacted": "Privilege status",
    "critical_asset": "Asset criticality",
    "source_ownership": "Source IP ownership",
    "mfa_status": "MFA result",
    "post_login_activity": "Post-login activity",
}


def _required_evidence_display(contract: AnswerContract) -> list[str]:
    labels: list[str] = []
    for key in contract.required_evidence:
        raw_key = str(key)
        label = _EVIDENCE_LABELS.get(raw_key, raw_key.replace("_", " "))
        text = f"{raw_key} — {label}"
        if text not in labels:
            labels.append(text)
    return labels


def _is_auth_hybrid_contract(contract: AnswerContract) -> bool:
    use_case_id = str(contract.use_case_id or "")
    if use_case_id:
        return use_case_id.startswith("auth_")
    return contract.intent_family == "hybrid_alert_review"


def _limitations_display(contract: AnswerContract) -> list[str]:
    if contract.answer_mode == "rag_only" or contract.intent_family in {
        "sop_or_playbook",
        "policy_knowledge",
        "knowledge_only",
    }:
        return []

    if contract.success_after_failure_context and _is_auth_hybrid_contract(contract):
        return list(_ALERT_REVIEW_LIMITATIONS)

    if (
        contract.intent_family == "hybrid_alert_review"
        and _is_auth_hybrid_contract(contract)
        and contract.missing_evidence
    ):
        items = []
        for key in contract.missing_evidence:
            if key in _EXCLUDED_LIMITATIONS_WHEN_SUCCESS_STATED:
                continue
            normalized = str(key).replace("_", " ").lower()
            items.append(
                _LIMITATION_LABELS.get(
                    str(key),
                    normalized if "missing" in normalized else f"{normalized} missing",
                )
            )
        if items:
            return items

    if contract.limitations:
        return list(contract.limitations)

    items: list[str] = []
    auth_only_keys = set(_AUTH_LIMITATION_KEYS)
    use_case_id = str(contract.use_case_id or "")
    for key in contract.missing_evidence:
        if key in _EXCLUDED_LIMITATIONS_WHEN_SUCCESS_STATED:
            continue
        if str(key) in auth_only_keys and not use_case_id.startswith("auth_"):
            continue
        normalized = str(key).replace("_", " ").lower()
        items.append(
            _LIMITATION_LABELS.get(
                str(key),
                normalized if "missing" in normalized else f"{normalized} missing",
            )
        )
    if (
        not items
        and contract.intent_family == "hybrid_alert_review"
        and _is_auth_hybrid_contract(contract)
    ):
        items = list(_ALERT_REVIEW_LIMITATIONS)
    deduped: list[str] = []
    for item in items:
        if item not in deduped:
            deduped.append(item)
    return deduped


_STATS_INDENT = "    "


def _format_spl_multiline(spl: Any) -> str | None:
    if not spl or not isinstance(spl, str):
        return None if spl is None else str(spl)
    text = spl.strip()
    if not text:
        return text
    parts = [part.strip() for part in text.split("|") if part.strip()]
    if len(parts) <= 1:
        return text
    lines: list[str] = [parts[0]]
    for part in parts[1:]:
        if part.lower().startswith("stats"):
            lines.append(_expand_stats_pipe(part))
        else:
            lines.append(f"| {part}")
    return "\n".join(lines)


def _expand_stats_pipe(part: str) -> str:
    text = part.strip()
    by_split = re.split(r"\s+by\s+", text, maxsplit=1, flags=re.IGNORECASE)
    head = by_split[0]
    group_by = by_split[1].strip() if len(by_split) > 1 else ""

    stats_body = re.sub(r"^stats\s+", "", head, flags=re.IGNORECASE).strip()
    if not stats_body:
        return f"| {text}"

    aggregations = [item.strip() for item in _AGG_SPLIT.split(stats_body) if item.strip()]
    lines = ["| stats"]
    for agg in aggregations:
        lines.append(f"{_STATS_INDENT}{agg}")
    if group_by:
        lines.append(f"{_STATS_INDENT}by {group_by}")
    return "\n".join(lines)


def _execution_blocked_for_display(contract: AnswerContract) -> bool:
    return str(contract.execution_status_label or "") not in {
        "executed_mock_evidence",
        "executed_live_evidence",
    }


def _scrub_blocked_context_actions(actions: list[str], contract: AnswerContract) -> list[str]:
    if not _execution_blocked_for_display(contract):
        return actions
    return [scrub_blocked_context_display_phrasing(item) for item in actions]


def _maybe_scrub_direct_answer_summary(text: str, contract: AnswerContract) -> str:
    if not _execution_blocked_for_display(contract):
        return text
    return scrub_blocked_context_display_phrasing(text)


def _format_investigation_actions(actions: list[Any]) -> list[str]:
    formatted: list[str] = []
    for item in actions:
        text = str(item).strip()
        glued = re.match(r"^(P[1-4])([A-Za-z])", text)
        if glued:
            text = f"{glued.group(1)} — {text[len(glued.group(1)):].lstrip(' -—')}"
        if re.match(r"^P[1-4]\s*[—-]\s*", text):
            formatted.append(re.sub(r"^P([1-4])\s*-\s*", r"P\1 — ", text))
            continue
        if re.match(r"^Step\s+\d+\s*:", text, flags=re.IGNORECASE):
            formatted.append(text)
            continue
        human = text.replace("_", " ")
        formatted.append(f"P2 — {human}")
    return formatted


_AUTH_LIMITATION_KEYS = frozenset(
    {
        "privileged_account_impacted",
        "critical_asset",
        "source_ownership",
        "mfa_status",
        "post_login_activity",
        "success_after_failure",
        "confirmed_success",
    }
)
