"""Deterministic detection for out-of-registry SOC investigation phrasing."""

from __future__ import annotations


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
