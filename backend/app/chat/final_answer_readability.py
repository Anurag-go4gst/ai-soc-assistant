"""Final answer readability layer — presentation only; no authority changes."""

from __future__ import annotations

import re
from typing import Any

from app.chat.contracts.answer_contract import AnswerContract
from app.schemas.responses import AnalystResponseEnvelope

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


def apply_final_answer_readability(
    envelope: AnalystResponseEnvelope,
    contract: AnswerContract | None,
) -> AnalystResponseEnvelope:
    if contract is None:
        return envelope
    payload = envelope.model_dump()
    payload["spl_code"] = _format_spl_multiline(payload.get("spl_code"))
    payload["executed_spl"] = _format_spl_multiline(payload.get("executed_spl"))
    payload["execution_status_label"] = contract.execution_status_display
    payload["spl_status"] = contract.spl_status
    payload["hil_status"] = contract.hil_status
    payload["missing_evidence"] = list(contract.missing_evidence)
    payload["analyst_checklist"] = list(contract.analyst_checklist_safe)
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
    payload["direct_answer_summary"] = _direct_answer_summary(envelope, contract)
    payload = _apply_knowledge_profile_cleanup(payload, contract)
    payload = _dedupe_labels(payload, contract)
    payload = _apply_section_visibility(payload, contract)
    payload["recommended_actions"] = _format_investigation_actions(payload.get("recommended_actions") or [])
    return AnalystResponseEnvelope.model_validate(payload)


def _direct_answer_summary(envelope: AnalystResponseEnvelope, contract: AnswerContract) -> str:
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
        elif section == "live_results" and envelope.splunk_results_table:
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
    payload["spl_code"] = None
    payload["executed_spl"] = None
    payload["review_notice"] = None
    payload["spl_status"] = "not_required"
    payload["spl_status_detail"] = None
    return payload


def _sop_knowledge_summary(envelope: AnalystResponseEnvelope, contract: AnswerContract) -> str:
    parts = ["Governed SOP retrieved."]
    if contract.spl_status == "not_required":
        parts.append("SPL and MCP were skipped as requested.")
    playbook = envelope.retrieved_playbook if isinstance(envelope.retrieved_playbook, dict) else {}
    title = str(playbook.get("title") or "").strip()
    purpose = str(playbook.get("purpose") or "").strip()
    if title:
        parts.append(f"SOP: {title}.")
    if purpose:
        parts.append(purpose if purpose.endswith(".") else f"{purpose}.")
    checklist = list(contract.analyst_checklist_safe or [])
    if checklist:
        preview = "; ".join(checklist[:3])
        parts.append(f"Checklist: {preview}.")
    return " ".join(parts)


def _hybrid_mitre_bucket_counts(
    envelope: AnalystResponseEnvelope,
    contract: AnswerContract,
) -> tuple[int, int, int, int]:
    evidence_supported = len(contract.evidence_supported_mitre)
    candidate = len(contract.candidate_mitre)
    requires_validation = len(contract.requires_validation_mitre)
    not_claimed = len(contract.not_claimed_mitre) + len(contract.ruled_out_mitre)

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

    if not_claimed == 0 and envelope.not_claimed:
        not_claimed = len(
            [
                row
                for row in envelope.not_claimed
                if isinstance(row, dict) and str(row.get("Technique") or "")
            ]
        )
    return evidence_supported, candidate, requires_validation, not_claimed


def _natural_hybrid_alert_summary(envelope: AnalystResponseEnvelope, contract: AnswerContract) -> str:
    parts: list[str] = []
    summary_bits: list[str] = []
    evidence_supported, candidate, requires_validation, not_claimed = _hybrid_mitre_bucket_counts(
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
            f"{not_claimed} technique{'s' if not_claimed != 1 else ''} explicitly not claimed"
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
    return " ".join(parts) if parts else str(envelope.one_sentence_finding or "")


def _dedupe_labels(payload: dict[str, Any], contract: AnswerContract) -> dict[str, Any]:
    exec_label = contract.execution_status_display or ""
    review_notice = str(payload.get("review_notice") or "")
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
        text = _EVIDENCE_LABELS.get(str(key), str(key).replace("_", " "))
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

    if contract.success_after_failure_context:
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
        and contract.render_sections.get("limitations")
        and contract.intent_family == "hybrid_alert_review"
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
