"""Build analyst-facing response envelopes for Experience Center and live /chat."""

from __future__ import annotations

import re
from typing import Any

from app.config import settings
from app.schemas.responses import AnalystResponseEnvelope
from app.chat.contracts.answer_contract import build_answer_contract
from app.chat.final_answer_readability import apply_final_answer_readability
from app.threat.mitre_evidence_preconditions import PRECONDITION_BY_ID, not_claimed_reason

_FAILED_LOGIN_NUMERIC_COLUMNS = (
    "Failed logins",
    "fail_count",
    "failed_logins",
    "failure_count",
)


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
) -> AnalystResponseEnvelope | None:
    """Assemble analyst card payload from governed live pipeline outputs."""
    draft = synthesis_draft if isinstance(synthesis_draft, dict) else {}
    execution_payload = execution if isinstance(execution, dict) else {}
    spl_code = _candidate_spl_text(candidate_spl, spl_validation, draft)
    table = _splunk_table_from_evidence(source_evidence) or _as_table_rows(draft.get("splunk_results_table"))
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
    recommended = _recommended_actions_from_draft(draft) or _recommended_from_rag(source_evidence)
    # Single AnswerContract: prefer the pipeline-built projection; build only as
    # a fallback so the builder never makes a second, divergent contract.
    contract = answer_contract
    if contract is None and settings.control_plane_enabled:
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
    plan = evidence_plan if isinstance(evidence_plan, dict) else {}
    intent = intent_classification if isinstance(intent_classification, dict) else {}
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
    if not any([table, mitre_rows, not_claimed, playbook, summary, recommended, spl_code]):
        return None
    finding = _finding_title(
        message,
        user_query,
        selected_use_case_label,
        intent_family=str(intent.get("intent_family") or "") or None,
        answer_mode=str(plan.get("answer_mode") or "") or None,
        playbook=playbook,
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
    else:
        response_profile = None

    review_notice = None
    if isinstance(human_review, dict) and human_review.get("required"):
        review_notice = str(human_review.get("safe_message_for_user") or "Analyst review is required before execution.")
    elif spl_code and execution_status != "executed":
        review_notice = "Candidate SPL — review only, not executed."

    severity_confidence, severity_rationale = _severity_confidence(
        user_query,
        execution_payload,
        intent_family=str(intent.get("intent_family") or "") or None,
        answer_mode=str(plan.get("answer_mode") or "") or None,
    )
    severity_safety_note = _severity_safety_note(user_query, response_profile)
    display_severity = severity_label
    if review_notice and severity_label and "review required" not in severity_label.lower():
        display_severity = f"{severity_label} — Review required"

    envelope = AnalystResponseEnvelope(
        scenario_label=selected_use_case_label,
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
        executed_spl=executed_spl,
        execution_status=execution_status,
        response_profile=response_profile,
        review_notice=review_notice,
        evidence_summary=summarize_failed_login_events(table),
    )
    if contract is not None:
        envelope = apply_final_answer_readability(envelope, contract)
    return envelope


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
        text = str(item)
        if text.startswith(("P1", "P2", "P3", "P4")):
            formatted.append(text.replace(" - ", " — ", 1) if " - " in text else text)
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
                return [f"P2 — {str(item)}" for item in actions[:6]]
    return []


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
