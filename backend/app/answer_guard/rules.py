from __future__ import annotations

import re
from typing import Any, Iterable

from pydantic import BaseModel

from app.actions.capability_policy import BLOCKED_EXECUTION_ACTIONS
from app.risk.severity_policy import PRIORITY_ENUM
from app.safeguards.spl_validator import validate_spl
from app.threat.mitre_kb import MITRE_MAPPING_STATUSES

GUARD_IDS = (
    "guard.clarification",
    "guard.json_schema",
    "guard.registry",
    "guard.evidence_presence",
    "guard.aggregate_overclaim",
    "guard.sop_fidelity",
    "guard.mitre_status",
    "guard.severity_authority",
    "guard.action_tier",
    "guard.spl_execution",
    "guard.priority_enum",
    "guard.internal_leakage",
    "guard.splunk_table_fidelity",
)
GUARD_STATUSES = ("pass", "warn", "fail")
GUARD_SEVERITIES = ("info", "warning", "blocking_candidate")
ALLOWED_MITRE_STATUSES = MITRE_MAPPING_STATUSES
ALLOWED_PRIORITIES = PRIORITY_ENUM
BLOCKED_ACTIONS = BLOCKED_EXECUTION_ACTIONS
INTERNAL_LEAKAGE_TERMS = ("SourceEvidence", "StructuredContext", "routing", "workflow", "fixture", "synthetic", "demo", "not executed", "disabled", "final synthesis")
AGGREGATE_FIELDS = ("total_failed_logins", "distinct_source_ips", "global_distinct_users", "affected_accounts_count")


class GuardResult(BaseModel):
    guard_id: str
    status: str
    severity: str
    message: str
    affected_field: str | None = None
    evidence_ref: str | None = None
    suggested_resolution: str | None = None


def pass_result(guard_id: str, message: str = "Guard passed.") -> GuardResult:
    return GuardResult(guard_id=guard_id, status="pass", severity="info", message=message)


def guard_clarification(payload: dict[str, Any], deterministic_context: dict[str, Any] | None = None) -> list[GuardResult]:
    deterministic_context = deterministic_context or {}
    if deterministic_context.get("clarification_required") and payload.get("clarification_needed") is False:
        return [_finding("guard.clarification", "fail", "blocking_candidate", "LLM attempted to skip deterministic clarification.", "clarification_needed")]
    return [pass_result("guard.clarification")]


def guard_json_schema(adapter_result: Any) -> list[GuardResult]:
    if getattr(adapter_result, "parsed_ok", False) and getattr(adapter_result, "schema_valid", False):
        return [pass_result("guard.json_schema")]
    return [_finding("guard.json_schema", "fail", "blocking_candidate", "Adapter output did not pass JSON/schema validation.")]


def guard_registry(adapter_result: Any) -> list[GuardResult]:
    if getattr(adapter_result, "accepted", False):
        return [pass_result("guard.registry")]
    return [_finding("guard.registry", "fail", "blocking_candidate", "Adapter output was not accepted by registry validation.")]


def guard_aggregate_overclaim(payload: dict[str, Any], evidence: dict[str, Any]) -> list[GuardResult]:
    findings: list[GuardResult] = []
    for field in AGGREGATE_FIELDS:
        if field in payload:
            if field not in evidence:
                findings.append(_finding("guard.aggregate_overclaim", "fail", "blocking_candidate", f"Structured aggregate `{field}` is not supplied by evidence.", field))
            elif payload[field] != evidence[field]:
                findings.append(_finding("guard.aggregate_overclaim", "fail", "blocking_candidate", f"Structured aggregate `{field}` differs from evidence.", field))

    text = _visible_text(payload, fields=("analyst_summary", "foundation_sec_analysis", "finding_title"))
    if "global_distinct_users" not in evidence and re.search(r"\b\d+\s+(targeted\s+)?accounts?\b", text, flags=re.IGNORECASE):
        findings.append(
            _finding(
                "guard.aggregate_overclaim",
                "warn",
                "warning",
                "Prose appears to claim a global distinct account count without `global_distinct_users` evidence.",
                "analyst_summary",
                suggested_resolution="Use wording such as `global distinct account count is not yet available`.",
            )
        )
    return findings or [pass_result("guard.aggregate_overclaim")]


def guard_evidence_presence(payload: dict[str, Any], evidence: dict[str, Any]) -> list[GuardResult]:
    requirements = {
        "privileged_account_impacted": "identity_evidence",
        "app_critical": "cmdb_evidence",
        "source_ip_approved_system": "asset_owner_evidence",
        "source_ip_malicious": "threat_intel_evidence",
        "post_login_malicious_activity": "post_login_activity_evidence",
        "compromise_confirmed": "compromise_evidence",
    }
    findings: list[GuardResult] = []
    for field, evidence_key in requirements.items():
        if field in payload and payload[field] is not None and not evidence.get(evidence_key):
            findings.append(_finding("guard.evidence_presence", "fail", "blocking_candidate", f"`{field}` requires `{evidence_key}`.", field))

    text = _visible_text(payload, fields=("analyst_summary", "foundation_sec_analysis"))
    prose_patterns = (
        r"\bprivileged accounts? (were )?(not )?(targeted|impacted)\b",
        r"\bAPP-01 (is|is not) critical\b",
        r"\bsource IP (is|was) (malicious|owned by an approved system)\b",
        r"\bpost-login malicious activity\b",
        r"\bcompromise confirmed\b",
    )
    if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in prose_patterns):
        findings.append(_finding("guard.evidence_presence", "warn", "warning", "Prose contains evidence-sensitive claim; verify evidence before enforcement.", "analyst_summary"))
    return findings or [pass_result("guard.evidence_presence")]


def guard_sop_fidelity(payload: dict[str, Any], rag_context: dict[str, Any]) -> list[GuardResult]:
    playbook = payload.get("retrieved_playbook") or {}
    if not isinstance(playbook, dict):
        return [pass_result("guard.sop_fidelity")]

    findings: list[GuardResult] = []
    for field in ("sop_id", "version", "title"):
        if field in playbook and field in rag_context and playbook[field] != rag_context[field]:
            findings.append(_finding("guard.sop_fidelity", "fail", "blocking_candidate", f"SOP `{field}` does not match governed RAG context.", f"retrieved_playbook.{field}", _ref(rag_context)))
    if "sop_id" in playbook and "sop_id" in rag_context and playbook["sop_id"] != rag_context["sop_id"]:
        findings.append(_finding("guard.sop_fidelity", "fail", "blocking_candidate", "Hallucinated or mismatched SOP ID.", "retrieved_playbook.sop_id", _ref(rag_context)))

    provided_guidance = list(rag_context.get("guidance") or [])
    llm_guidance = list(playbook.get("guidance") or [])
    if llm_guidance and provided_guidance and llm_guidance != provided_guidance:
        findings.append(_finding("guard.sop_fidelity", "fail", "blocking_candidate", "SOP guidance does not match governed RAG guidance.", "retrieved_playbook.guidance", _ref(rag_context)))
    return _dedupe_results(findings) or [pass_result("guard.sop_fidelity")]


def guard_mitre_status(payload: dict[str, Any], deterministic_mitre: dict[str, str]) -> list[GuardResult]:
    findings: list[GuardResult] = []
    for item in payload.get("mitre_mappings") or []:
        if not isinstance(item, dict):
            continue
        technique_id = str(item.get("technique_id") or "")
        llm_status = str(item.get("status") or "")
        deterministic_status = deterministic_mitre.get(technique_id)
        if llm_status and llm_status not in ALLOWED_MITRE_STATUSES:
            findings.append(_finding("guard.mitre_status", "fail", "blocking_candidate", "MITRE status is not in the allowed enum.", f"mitre_mappings.{technique_id}.status"))
        if deterministic_status and llm_status and llm_status != deterministic_status:
            findings.append(_finding("guard.mitre_status", "fail", "blocking_candidate", "LLM MITRE status cannot override deterministic MITRE status.", f"mitre_mappings.{technique_id}.status"))
    return findings or [pass_result("guard.mitre_status")]


def guard_severity_authority(payload: dict[str, Any], deterministic_severity: str | None) -> list[GuardResult]:
    llm_severity = payload.get("severity_label") or payload.get("selected_severity")
    if deterministic_severity and llm_severity and llm_severity != deterministic_severity:
        return [_finding("guard.severity_authority", "fail", "blocking_candidate", "LLM severity cannot override severity matrix output.", "severity_label")]
    return [pass_result("guard.severity_authority")]


def guard_action_tier(payload: dict[str, Any], action_policy: dict[str, Any]) -> list[GuardResult]:
    allowed_actions = set(action_policy.get("allowed_actions") or [])
    current_tier = int(action_policy.get("current_tier") or 1)
    findings: list[GuardResult] = []
    for action in payload.get("recommended_actions") or payload.get("actions") or []:
        action_id = _action_id(action)
        if action_id in BLOCKED_ACTIONS and (current_tier <= 1 or action_id not in allowed_actions):
            findings.append(_finding("guard.action_tier", "fail", "blocking_candidate", f"Action `{action_id}` is not allowed by the current action tier.", "recommended_actions"))
        elif allowed_actions and action_id not in allowed_actions:
            findings.append(_finding("guard.action_tier", "fail", "blocking_candidate", f"Action `{action_id}` is outside allowed action policy.", "recommended_actions"))
    return findings or [pass_result("guard.action_tier")]


def guard_priority_enum(payload: dict[str, Any]) -> list[GuardResult]:
    findings: list[GuardResult] = []
    for field in ("priority", "recommended_priority", "severity_priority"):
        if field in payload and payload[field] not in ALLOWED_PRIORITIES:
            findings.append(_finding("guard.priority_enum", "fail", "blocking_candidate", f"`{field}` must use P1/P2/P3/P4.", field))
    return findings or [pass_result("guard.priority_enum")]


def guard_spl_execution(payload: dict[str, Any], *, validate_candidate: bool = False) -> list[GuardResult]:
    findings: list[GuardResult] = []
    if payload.get("execution_eligible") is True:
        findings.append(_finding("guard.spl_execution", "fail", "blocking_candidate", "LLM-generated SPL is never execution eligible.", "execution_eligible"))
    if validate_candidate and payload.get("candidate_spl"):
        validation = validate_spl(str(payload["candidate_spl"]))
        if not validation["approved"]:
            findings.append(_finding("guard.spl_execution", "fail", "blocking_candidate", "Candidate SPL failed deterministic validation.", "candidate_spl"))
    if payload.get("sent_to_mcp") or payload.get("mcp_payload", {}).get("candidate_spl"):
        findings.append(_finding("guard.spl_execution", "fail", "blocking_candidate", "Candidate SPL must not be sent to MCP.", "candidate_spl"))
    return findings or [pass_result("guard.spl_execution")]


def guard_internal_leakage(payload: dict[str, Any]) -> list[GuardResult]:
    findings: list[GuardResult] = []
    structured_fields = ("heading", "title", "label", "status_badge")
    prose_fields = ("analyst_summary", "foundation_sec_analysis")
    for field in structured_fields:
        value = str(payload.get(field) or "")
        term = _first_internal_term(value)
        if term:
            findings.append(_finding("guard.internal_leakage", "fail", "blocking_candidate", f"Visible structured field leaks internal term `{term}`.", field))
    for field in prose_fields:
        value = str(payload.get(field) or "")
        term = _first_internal_term(value)
        if term:
            findings.append(_finding("guard.internal_leakage", "warn", "warning", f"Visible prose mentions internal term `{term}`.", field))
    return findings or [pass_result("guard.internal_leakage")]


def guard_splunk_table_fidelity(payload_rows: list[dict[str, Any]], evidence_rows: list[dict[str, Any]], *, strict: bool = True) -> list[GuardResult]:
    findings: list[GuardResult] = []
    evidence_keys = [_row_key(row) for row in evidence_rows]
    payload_keys = [_row_key(row) for row in payload_rows]
    evidence_by_key = dict(zip(evidence_keys, evidence_rows))
    allowed_fields = set().union(*(row.keys() for row in evidence_rows)) if evidence_rows else set()
    compare_fields = ("host", "source_ip", "src", "count", "failed_logins", "first_seen", "last_seen", "action")

    for row in payload_rows:
        key = _row_key(row)
        if key not in evidence_by_key:
            findings.append(_finding("guard.splunk_table_fidelity", "fail", "blocking_candidate", "Model added a Splunk result row not present in evidence.", "splunk_results_table"))
            continue
        evidence_row = evidence_by_key[key]
        invented_fields = set(row) - allowed_fields
        if invented_fields:
            findings.append(_finding("guard.splunk_table_fidelity", "fail", "blocking_candidate", "Model invented Splunk result table fields.", "splunk_results_table"))
        for field in compare_fields:
            if field in row and field in evidence_row and row[field] != evidence_row[field]:
                findings.append(_finding("guard.splunk_table_fidelity", "fail", "blocking_candidate", f"Model altered Splunk table field `{field}`.", f"splunk_results_table.{field}"))

    omitted = [key for key in evidence_keys if key not in payload_keys]
    if omitted:
        findings.append(
            _finding(
                "guard.splunk_table_fidelity",
                "fail" if strict else "warn",
                "blocking_candidate" if strict else "warning",
                "Model omitted one or more Splunk evidence rows.",
                "splunk_results_table",
            )
        )
    return _dedupe_results(findings) or [pass_result("guard.splunk_table_fidelity")]


def _finding(
    guard_id: str,
    status: str,
    severity: str,
    message: str,
    affected_field: str | None = None,
    evidence_ref: str | None = None,
    suggested_resolution: str | None = None,
) -> GuardResult:
    return GuardResult(
        guard_id=guard_id,
        status=status,
        severity=severity,
        message=message,
        affected_field=affected_field,
        evidence_ref=evidence_ref,
        suggested_resolution=suggested_resolution,
    )


def _visible_text(payload: dict[str, Any], *, fields: Iterable[str]) -> str:
    return "\n".join(str(payload.get(field) or "") for field in fields)


def _ref(context: dict[str, Any]) -> str | None:
    refs = context.get("source_refs") or []
    return str(refs[0]) if refs else None


def _action_id(action: Any) -> str:
    if isinstance(action, dict):
        action = action.get("action") or action.get("id") or action.get("name") or ""
    return str(action).strip()


def _first_internal_term(value: str) -> str | None:
    for term in INTERNAL_LEAKAGE_TERMS:
        pattern = r"(?<!\w)" + re.escape(term) + r"(?!\w)"
        if re.search(pattern, value, flags=re.IGNORECASE):
            return term
    return None


def _row_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("host"),
        row.get("source_ip", row.get("src")),
        row.get("user"),
        row.get("action"),
        row.get("first_seen"),
        row.get("last_seen"),
    )


def _dedupe_results(results: list[GuardResult]) -> list[GuardResult]:
    seen: set[tuple[str, str | None, str]] = set()
    deduped: list[GuardResult] = []
    for result in results:
        key = (result.guard_id, result.affected_field, result.message)
        if key not in seen:
            deduped.append(result)
            seen.add(key)
    return deduped
