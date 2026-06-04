"""Deterministic query-signal extraction for the control-plane intent stage."""

from __future__ import annotations

import re
from typing import Any

from app.query_understanding.models import QueryUnderstandingResult

_TECHNIQUE_ID_RE = re.compile(r"\bT\d{4}(?:\.\d{3})?\b", re.IGNORECASE)
_MAP_TO_MITRE_RE = re.compile(r"\bmap\b.{0,120}\b(?:mitre|att&ck)\b", re.IGNORECASE)


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
    failed_login = any(
        term in normalized
        for term in ("failed login", "failed logins", "failed-login", "login failure", "login failures")
    )
    spl_generation = any(
        term in normalized
        for term in ("generate spl", "write spl", "create spl", "produce spl", "build spl", "spl for", "spl query")
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
        for term in ("find ", "show ", "list ", "investigate", "search for", "look for", "top users", "which users")
    )
    mitre_map = bool(_MAP_TO_MITRE_RE.search(query)) or any(
        term in normalized
        for term in ("map to mitre", "map this to mitre", "mitre mapping", "map alert to mitre", "map this alert")
    )
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
    success_after_failure = any(
        term in normalized
        for term in (
            "successful login after",
            "success after",
            "success following",
            "after failures",
            "followed by a successful login",
            "followed by successful login",
            "failures followed by",
            "failure followed by",
        )
    ) or (
        "successful login" in normalized
        and any(term in normalized for term in ("followed", "after failure", "after failures", "after failed"))
    )
    positive_successful_login = success_after_failure or (
        "successful login" in normalized and not negative_successful_login
    )
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
    hybrid_alert_review = (
        alert_context_present
        and (success_after_failure or failed_login)
        and mitre_map
        and (severity_request or review_only_spl)
        and not run_execution
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

    mitre_requires_alert_context = bool(
        qu
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
        "success_after_failure": success_after_failure,
        "positive_successful_login": positive_successful_login,
        "severity_request": severity_request,
        "review_only_spl": review_only_spl,
        "alert_context_present": alert_context_present,
        "hybrid_alert_review": hybrid_alert_review,
        "projected_needs_rag": policy_terms
        or escalation_without_policy_word
        or playbook_procedure
        or procedural_investigation
        or (knowledge_definition and not spl_generation and not live_investigation_verbs),
        "projected_needs_spl": spl_generation
        and not block_or_contain
        or (live_investigation_verbs and not policy_terms and not block_or_contain),
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
