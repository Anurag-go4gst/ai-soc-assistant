"""Deterministic detection for out-of-registry SOC investigation phrasing."""

from __future__ import annotations

_HYPOTHESIS_GUIDANCE_MARKERS = (
    "hunting hypotheses",
    "hypotheses should",
    "what hypotheses",
    "what should i validate",
    "what should we validate",
    "without a known ioc",
    "without known ioc",
    "no known ioc",
    "without an ioc",
    "no ioc list",
)

_CONCRETE_SPL_CATALOG_MARKERS = (
    "failed login",
    "failed logins",
    "login spike",
    "last 24 hours",
    "last 24h",
    "past 24 hours",
    "top ",
    "exclude service account",
    "write spl",
    "generate spl",
    "show spl",
    "run spl",
    "execute spl",
)


def detect_investigation_hypothesis_guidance(query: str) -> bool:
    """Analyst asks what to validate/hunt without requesting governed template SPL."""
    normalized = " ".join(query.lower().split())
    return any(term in normalized for term in _HYPOTHESIS_GUIDANCE_MARKERS)


def prefers_guided_investigation_over_catalog(query: str) -> bool:
    """Catalog keyword overlap must not override hypothesis/guidance-only hunt asks."""
    if not detect_investigation_hypothesis_guidance(query):
        return False
    normalized = " ".join(query.lower().split())
    return not any(term in normalized for term in _CONCRETE_SPL_CATALOG_MARKERS)


def detect_soc_investigation_shape(query: str, *, exact_105_match: bool = False) -> bool:
    normalized = " ".join(query.lower().split())
    hunt_phrasing = any(
        term in normalized
        for term in (
            "hunt",
            "anything to hunt",
            "what should i hunt",
            "where should i start",
            "how should i investigate",
            "what should soc check",
            "what should analyst",
            "what evidence should i collect",
        )
    )
    anomaly_phrasing = any(
        term in normalized
        for term in ("strange", "odd", "unusual", "suspicious", "anomaly", "abnormal")
    )
    network_or_ot_context = any(
        term in normalized
        for term in (
            "chatter",
            "beacon",
            "traffic",
            "new external",
            "new destination",
            "overnight",
            " ot ",
            "it-to-ot",
            "outbound",
            "unknown host",
            "scada",
        )
    ) or normalized.startswith("ot ")
    unsafe_or_execution = any(
        term in normalized
        for term in (
            "block this ip",
            "block the ip",
            "contain ",
            "isolate ",
            "quarantine ",
            "disable the account",
            "run the spl",
            "run spl",
            "execute spl",
            "execute the spl",
        )
    )
    sop_only = any(
        term in normalized
        for term in (
            "show me the sop",
            "show me the playbook",
            "show me the runbook",
            "show me the soc checklist",
            "soc checklist for",
            "checklist for",
        )
    )
    non_soc = any(term in normalized for term in ("hr policy", "vacation policy", "payroll", "expense policy"))
    return bool(
        (hunt_phrasing or (anomaly_phrasing and network_or_ot_context))
        and not unsafe_or_execution
        and not sop_only
        and not non_soc
        and not exact_105_match
    )
