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
    payload["limitations"] = _limitations_display(contract)
    payload["section_order"] = list(contract.section_order)
    payload["render_sections"] = dict(contract.render_sections)
    payload["direct_answer_summary"] = _direct_answer_summary(envelope, contract)
    payload = _dedupe_labels(payload, contract)
    payload = _apply_section_visibility(payload, contract)
    payload["recommended_actions"] = _format_investigation_actions(payload.get("recommended_actions") or [])
    return AnalystResponseEnvelope.model_validate(payload)


def _direct_answer_summary(envelope: AnalystResponseEnvelope, contract: AnswerContract) -> str:
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


def _natural_hybrid_alert_summary(envelope: AnalystResponseEnvelope, contract: AnswerContract) -> str:
    mapped = len(envelope.mitre_mappings or [])
    blocked = len(envelope.not_claimed or [])
    parts: list[str] = []
    if mapped and blocked:
        parts.append(
            f"The alert has {mapped} candidate MITRE mapping{'s' if mapped != 1 else ''} "
            f"and {blocked} technique{'s' if blocked != 1 else ''} explicitly not claimed."
        )
    elif mapped:
        parts.append(
            f"The alert has {mapped} candidate MITRE mapping{'s' if mapped != 1 else ''}."
        )
    elif blocked:
        parts.append(
            f"The alert has {blocked} technique{'s' if blocked != 1 else ''} explicitly not claimed."
        )
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


def _limitations_display(contract: AnswerContract) -> list[str]:
    if contract.success_after_failure_context:
        return list(_ALERT_REVIEW_LIMITATIONS)

    items: list[str] = []
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
    if not items and contract.render_sections.get("limitations"):
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
        if re.match(r"^P[1-4]\s*[—-]\s*", text):
            formatted.append(re.sub(r"^P([1-4])\s*-\s*", r"P\1 — ", text))
            continue
        formatted.append(f"P2 — {text}")
    return formatted
