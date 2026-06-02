"""Deterministic query-signal extraction for the control-plane intent stage."""

from __future__ import annotations

import re
from typing import Any

from app.query_understanding.models import QueryUnderstandingResult

_TECHNIQUE_ID_RE = re.compile(r"\bT\d{4}(?:\.\d{3})?\b", re.IGNORECASE)


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
    live_investigation_verbs = any(
        term in normalized
        for term in ("find ", "show ", "list ", "investigate", "search for", "look for", "top users", "which users")
    )
    mitre_map = any(
        term in normalized
        for term in ("map to mitre", "map this to mitre", "mitre mapping", "map alert to mitre", "map this alert")
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

    mitre_requires_alert_context = bool(
        qu
        and qu.clarification_needed
        and "mitre_mapping_requires_alert_context" in (qu.ambiguity_flags or [])
    )

    return {
        "normalized_query": normalized,
        "policy_terms": policy_terms,
        "escalation_without_policy_word": escalation_without_policy_word,
        "failed_login": failed_login,
        "spl_generation": spl_generation,
        "live_investigation_verbs": live_investigation_verbs,
        "mitre_map": mitre_map,
        "mitre_explain": mitre_explain,
        "analyst_action": analyst_action,
        "playbook_procedure": playbook_procedure,
        "knowledge_definition": knowledge_definition,
        "dga": dga,
        "block_or_contain": block_or_contain,
        "procedural_investigation": procedural_investigation,
        "time_window_24h": time_window_24h,
        "exclude_service_accounts": exclude_service_accounts,
        "mitre_requires_alert_context": mitre_requires_alert_context,
        "projected_needs_rag": policy_terms
        or escalation_without_policy_word
        or playbook_procedure
        or procedural_investigation
        or (knowledge_definition and not spl_generation and not live_investigation_verbs),
        "projected_needs_spl": spl_generation
        and not block_or_contain
        or (live_investigation_verbs and not policy_terms and not block_or_contain),
        "projected_needs_mcp": live_investigation_verbs
        and not spl_generation
        and not policy_terms
        and not block_or_contain
        and not mitre_map,
        "requires_hil": block_or_contain,
        "projected_action_mode": "recommend_only" if block_or_contain else None,
    }
