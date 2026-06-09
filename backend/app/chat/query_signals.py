"""Deterministic query-signal extraction for the control-plane intent stage."""

from __future__ import annotations

import re
from typing import Any

from app.query_understanding.models import QueryUnderstandingResult
from app.query_understanding.success_after_failure import detect_success_after_failure

_TECHNIQUE_ID_RE = re.compile(r"\bT\d{4}(?:\.\d{3})?\b", re.IGNORECASE)
_MAP_TO_MITRE_RE = re.compile(r"\bmap\b.{0,120}\b(?:mitre|att&ck)\b", re.IGNORECASE)
_LOG_SEARCH_RE = re.compile(
    r"\b(?:search|find|look for)\b.{0,80}\b(?:logs?|firewall|proxy|endpoint|vpn|dns|powershell)\b",
    re.IGNORECASE,
)


def _explicit_log_search_requested(normalized: str) -> bool:
    if _LOG_SEARCH_RE.search(normalized):
        return True
    return any(
        term in normalized
        for term in (
            "draft a splunk search",
            "draft splunk search",
            "draft spl",
            "write spl",
            "search logs",
            "search firewall logs",
            "search proxy logs",
            "search endpoint logs",
            "search firewall logs for",
            "find vpn logins",
            "find windows servers",
            "look for dns queries",
            "find successful logins",
            "find successful vpn logins",
            "find successful established connections",
        )
    )


def extract_query_signals(
    query: str,
    query_understanding: QueryUnderstandingResult | None = None,
) -> dict[str, Any]:
    normalized = " ".join(query.lower().split())
    qu = query_understanding

    policy_terms = any(
        term in normalized
        for term in (
            "escalation policy",
            "escalation matrix",
            "when should",
            "when to escalate",
            "policy for",
            "what is the policy",
            "escalation criteria",
            "escalation threshold",
        )
    )
    escalation_without_policy_word = "escalat" in normalized and "policy" not in normalized
    success_after_failure = detect_success_after_failure(normalized)
    failed_login = any(
        term in normalized
        for term in ("failed login", "failed logins", "failed-login", "login failure", "login failures")
    )
    spl_suppressed = _spl_generation_suppressed(normalized)
    explicit_log_search = _explicit_log_search_requested(normalized)
    spl_generation = (not spl_suppressed) and (
        _spl_generation_requested(normalized) or explicit_log_search
    )
    run_execution = any(
        term in normalized
        for term in (
            " and run",
            " then run",
            "run it",
            "run this",
            "execute it",
            "execute this",
            "search splunk",
            "run on ",
            "run in ",
        )
    )
    has_specific_scope = any(term in normalized for term in (" index=", "index ", "host=", "host ", "sourcetype=", "sourcetype ", "earliest=", "latest=", "last "))
    live_investigation_verbs = any(
        term in normalized
        for term in (
            "find ",
            "show ",
            "list ",
            "investigate",
            "search for",
            "search logs",
            "search firewall",
            "search proxy",
            "search endpoint",
            "look for",
            "top users",
            "which users",
        )
    ) or explicit_log_search
    negative_successful_login = any(
        term in normalized
        for term in ("no successful login", "no success", "no login success", "without successful login")
    )
    negative_endpoint_telemetry = any(
        term in normalized
        for term in ("no endpoint telemetry", "without endpoint telemetry", "no endpoint evidence")
    )
    negative_credential_dumping = any(
        term in normalized
        for term in ("no evidence of credential dumping", "no credential dumping", "without credential dumping")
    )
    positive_successful_login = success_after_failure or (
        "successful login" in normalized and not negative_successful_login
    )
    spray_breadth = bool(
        re.search(r"\bacross\s+\d+\s+(?:accounts|users)\b", normalized)
        or "many users" in normalized
        or "multiple users" in normalized
        or "password spray" in normalized
        or "password spraying" in normalized
    )
    source_ip_novelty = any(
        term in normalized
        for term in ("new source", "novel source", "unusual source", "new ip", "unusual ip", "unknown device")
    )
    valid_account_abuse = any(
        term in normalized
        for term in (
            "impossible travel",
            "suspicious device",
            "privilege use",
            "privileged action",
            "post-login activity",
            "post login activity",
            "account misuse",
        )
    )
    powershell_context = "powershell" in normalized or "script block" in normalized or "encodedcommand" in normalized
    powershell_command_evidence = powershell_context and any(
        term in normalized for term in ("command line", "command_line", "script block", "process", "event id", "event_id")
    )
    encoded_command = "encodedcommand" in normalized or "encoded command" in normalized or "-enc" in normalized
    suspicious_parent_process = any(
        term in normalized for term in ("parent process", "winword", "excel", "outlook", "wscript", "mshta")
    )
    download_cradle = any(term in normalized for term in ("download cradle", "invoke-webrequest", "iwr ", "http://", "https://"))
    endpoint_network_connection = powershell_context and any(term in normalized for term in ("network connection", "beacon", "outbound"))
    email_auth_failure = any(term in normalized for term in ("spf fail", "dkim fail", "dmarc fail", "authentication-results fail"))
    sender_return_path_mismatch = any(term in normalized for term in ("sender mismatch", "return-path mismatch", "reply-to mismatch", "reply_to mismatch"))
    malicious_url_or_domain = any(term in normalized for term in ("malicious url", "malicious domain", "url verdict", "domain verdict"))
    attachment_hash_verdict = any(term in normalized for term in ("attachment hash", "malicious attachment", "attachment verdict"))
    mail_gateway_verdict = any(term in normalized for term in ("gateway verdict", "mail gateway verdict", "secure email gateway"))
    periodicity = any(term in normalized for term in ("periodic", "periodicity", "regular interval"))
    jitter_profile = "jitter" in normalized
    repeated_destination = any(term in normalized for term in ("repeated destination", "repeated domain", "same domain", "same destination"))
    rare_domain = any(term in normalized for term in ("rare domain", "new domain", "low reputation domain"))
    byte_pattern = any(term in normalized for term in ("bytes out", "byte pattern", "small bytes", "outbound bytes"))
    host_association = any(term in normalized for term in ("host association", "host=", "src host", "user/host", "user host"))
    file_rename_volume = any(term in normalized for term in ("file rename", "rename count", "many files", "mass file"))
    extension_pattern = any(term in normalized for term in ("extension pattern", "new extension", "encrypted extension"))
    encryption_behavior = any(term in normalized for term in ("encryption behavior", "encrypted files", "encrypting files"))
    impacted_paths = any(term in normalized for term in ("affected paths", "impacted paths", "shared drive"))
    process_evidence = any(term in normalized for term in ("process_name", "process name", "process evidence"))
    shadow_copy_deletion = any(term in normalized for term in ("shadow copy", "vssadmin", "delete shadows"))
    service_stop = any(term in normalized for term in ("service stop", "stopped service", "net stop"))
    host_spread = any(term in normalized for term in ("host spread", "multiple hosts", "impacted host"))
    severity_request = "severity" in normalized
    review_only_spl = any(
        term in normalized
        for term in (
            "spl i can review",
            "review-only spl",
            "review only spl",
            "governed spl",
            "not execute",
            "but not execute",
            "without executing",
            "do not execute",
        )
    ) or (("spl" in normalized or "query" in normalized) and "review" in normalized and not run_execution)
    alert_context_present = bool(
        re.search(r"\balt-\d{4}-\d+\b", normalized)
        or re.search(r"\bfor alert\b", normalized)
        or re.search(r"\balert\s+[a-z0-9][\w.-]+\b", normalized)
    )
    explicit_mitre_context = (
        alert_context_present
        or bool(re.search(r"\b\d+\s+(?:failed login|failed-logins|login failure|failed authentication)", normalized))
        or bool(re.search(r"\bacross\s+\d+\s+(?:accounts|users|hosts|sources|ips)\b", normalized))
        or any(term in normalized for term in ("external ip", "external ips", "source ip", "source ips", "no successful login"))
    ) and (
        alert_context_present
        or success_after_failure
        or negative_successful_login
        or negative_endpoint_telemetry
        or negative_credential_dumping
    )
    mitre_explain = bool(_TECHNIQUE_ID_RE.search(query)) and any(
        term in normalized for term in ("explain", "what is", "describe", "meaning of")
    )
    analyst_action = any(
        term in normalized
        for term in (
            "analyst action",
            "what should i do",
            "what should we do",
            "next steps",
            "what do i do",
            "recommended action",
            "tell me what",
        )
    )
    playbook_procedure = any(
        term in normalized for term in ("playbook", "runbook", "sop", "standard operating procedure", "procedure steps")
    )
    knowledge_definition = normalized.startswith("what is ") or normalized.startswith("what are ")
    dga = "dga" in normalized or "domain generation" in normalized
    block_or_contain = any(
        term in normalized
        for term in ("block all", "block suspicious", "contain ", "isolate ", "quarantine ", "disable all")
    )
    procedural_investigation = any(
        term in normalized
        for term in (
            "investigation steps",
            "steps for investigation",
            "how to investigate",
            "investigation procedure",
        )
    ) or (
        "explain" in normalized
        and "step" in normalized
        and not live_investigation_verbs
        and not spl_generation
    )
    time_window_24h = any(term in normalized for term in ("last 24 hours", "last 24h", "past 24 hours", "24 hours", "24h"))
    exclude_service_accounts = "exclude service account" in normalized or "excluding service account" in normalized
    top_n_match = re.search(r"\b(?:top|first|limit|head)\s+(\d+)\b", normalized)
    dns_beaconing = any(
        term in normalized
        for term in ("dns beaconing", "beaconing candidate", "beaconing pattern", "dns beacon")
    ) or ("beaconing" in normalized and "dns" in normalized)
    security_log_investigation = any(
        term in normalized
        for term in (
            "dns",
            "firewall",
            "proxy",
            "endpoint",
            "vpn",
            "powershell",
            "ot server",
            "scada",
            "control room",
            "engineering workstation",
        )
    )
    investigation_triage_guidance = any(
        term in normalized
        for term in (
            "how should soc",
            "what should soc",
            "how should we",
            "what should we",
            "how should the analyst",
            "what should the analyst",
            "how should soc triage",
            "what should soc check",
            "what should soc investigate",
            "what should soc validate",
        )
    )
    guidance_alert_context = alert_context_present and investigation_triage_guidance
    use_case_review_guidance = (
        (not alert_context_present or guidance_alert_context)
        and not run_execution
        and (
            review_only_spl
            or (investigation_triage_guidance and security_log_investigation)
        )
        and (
            powershell_context
            or dns_beaconing
            or procedural_investigation
            or security_log_investigation
            or any(
                term in normalized
                for term in (
                    "analyst checklist",
                    "required evidence",
                    "evidence required",
                    "limitations",
                )
            )
        )
    )
    explicit_search_intent = bool(
        spl_generation
        or explicit_log_search
        or use_case_review_guidance
        or (
            live_investigation_verbs
            and not policy_terms
            and not block_or_contain
            and not spl_suppressed
        )
    )
    mitre_map = (not use_case_review_guidance) and (
        bool(_MAP_TO_MITRE_RE.search(query))
        or any(
            term in normalized
            for term in ("map to mitre", "map this to mitre", "map alert to mitre", "map this alert")
        )
        or (
            "mitre mapping" in normalized
            and alert_context_present
        )
    )
    hybrid_alert_review = (
        alert_context_present
        and (success_after_failure or failed_login)
        and mitre_map
        and (severity_request or review_only_spl)
        and not run_execution
    )

    mitre_requires_alert_context = bool(
        not use_case_review_guidance
        and qu
        and qu.clarification_needed
        and "mitre_mapping_requires_alert_context" in (qu.ambiguity_flags or [])
        and not explicit_mitre_context
    )

    return {
        "normalized_query": normalized,
        "policy_terms": policy_terms,
        "escalation_without_policy_word": escalation_without_policy_word,
        "failed_login": failed_login,
        "spl_generation": spl_generation,
        "spl_suppressed": spl_suppressed,
        "dns_beaconing": dns_beaconing,
        "use_case_review_guidance": use_case_review_guidance,
        "run_execution": run_execution,
        "has_specific_scope": has_specific_scope,
        "live_investigation_verbs": live_investigation_verbs,
        "mitre_map": mitre_map,
        "explicit_mitre_context": explicit_mitre_context,
        "negative_successful_login": negative_successful_login,
        "negative_endpoint_telemetry": negative_endpoint_telemetry,
        "negative_cred_dumping": negative_credential_dumping,
        "mitre_explain": mitre_explain,
        "analyst_action": analyst_action,
        "playbook_procedure": playbook_procedure,
        "knowledge_definition": knowledge_definition,
        "dga": dga,
        "block_or_contain": block_or_contain,
        "procedural_investigation": procedural_investigation,
        "time_window_24h": time_window_24h,
        "exclude_service_accounts": exclude_service_accounts,
        "top_n": int(top_n_match.group(1)) if top_n_match else None,
        "mitre_requires_alert_context": mitre_requires_alert_context,
        "explicit_log_search": explicit_log_search,
        "explicit_search_intent": explicit_search_intent,
        "investigation_triage_guidance": investigation_triage_guidance,
        "security_log_investigation": security_log_investigation,
        "success_after_failure": success_after_failure,
        "positive_successful_login": positive_successful_login,
        "spray_breadth": spray_breadth,
        "source_ip_novelty": source_ip_novelty,
        "valid_account_abuse": valid_account_abuse,
        "powershell_context": powershell_context,
        "powershell_command_evidence": powershell_command_evidence,
        "encoded_command": encoded_command,
        "suspicious_parent_process": suspicious_parent_process,
        "download_cradle": download_cradle,
        "endpoint_network_connection": endpoint_network_connection,
        "email_auth_failure": email_auth_failure,
        "sender_return_path_mismatch": sender_return_path_mismatch,
        "malicious_url_or_domain": malicious_url_or_domain,
        "attachment_hash_verdict": attachment_hash_verdict,
        "mail_gateway_verdict": mail_gateway_verdict,
        "periodicity": periodicity,
        "jitter_profile": jitter_profile,
        "repeated_destination": repeated_destination,
        "rare_domain": rare_domain,
        "byte_pattern": byte_pattern,
        "host_association": host_association,
        "file_rename_volume": file_rename_volume,
        "extension_pattern": extension_pattern,
        "encryption_behavior": encryption_behavior,
        "impacted_paths": impacted_paths,
        "process_evidence": process_evidence,
        "shadow_copy_deletion": shadow_copy_deletion,
        "service_stop": service_stop,
        "host_spread": host_spread,
        "severity_request": severity_request,
        "review_only_spl": review_only_spl,
        "alert_context_present": alert_context_present,
        "hybrid_alert_review": hybrid_alert_review,
        "projected_needs_rag": policy_terms
        or escalation_without_policy_word
        or playbook_procedure
        or procedural_investigation
        or (knowledge_definition and not spl_generation and not live_investigation_verbs),
        "projected_needs_spl": (
            spl_generation
            and not block_or_contain
            or (
                live_investigation_verbs
                and not policy_terms
                and not block_or_contain
                and not spl_suppressed
            )
        ),
        "projected_needs_mcp": (
            live_investigation_verbs
            and not spl_generation
            and not policy_terms
            and not block_or_contain
            and not mitre_map
        )
        or (spl_generation and run_execution and not block_or_contain),
        "requires_hil": block_or_contain,
        "projected_action_mode": "recommend_only" if block_or_contain else None,
    }


def _spl_generation_suppressed(normalized: str) -> bool:
    if not ("spl" in normalized or "query" in normalized):
        return False
    return any(
        term in normalized
        for term in (
            "do not generate spl",
            "don't generate spl",
            "do not generate a spl",
            "do not generate any spl",
            "no spl",
            "without spl",
            "unless required",
            "unless absolutely required",
        )
    )


def _spl_generation_requested(normalized: str) -> bool:
    explicit_verbs = (
        "generate spl",
        "write spl",
        "create spl",
        "produce spl",
        "build spl",
        "spl query",
        "draft spl",
        "draft a splunk search",
        "draft splunk search",
    )
    if any(term in normalized for term in explicit_verbs):
        return True
    if "spl for" in normalized and "review" not in normalized:
        return True
    if normalized.startswith("draft a splunk") or normalized.startswith("draft splunk"):
        return True
    return False
