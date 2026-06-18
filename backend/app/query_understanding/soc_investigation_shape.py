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


# OT/ICS/grid hunt context. Detection-imperative phrasing ("flag/detect/identify
# <protocol or asset>") over these tokens is investigation-shaped even without an
# explicit "hunt"/"anomaly" word, so out-of-registry OT-protocol asks reach the
# guided_investigation rescue (where RAG grounding + LLM enrichment can engage)
# instead of dropping to a thin knowledge_recall answer.
_OT_ICS_CONTEXT = (
    "modbus",
    "dnp3",
    "dnp 3",
    "iec-104",
    "iec 104",
    "iec-101",
    "iec-61850",
    "iec 61850",
    "goose",
    "iccp",
    "scada",
    " plc",
    " rtu",
    " ied",
    " hmi",
    " ics ",
    "ot dmz",
    "ami ",
    "smart meter",
    "pmu",
    "phasor",
    "synchrophasor",
    "substation",
    "breaker",
    "relay",
    "setpoint",
    "inverter",
    "firmware",
    "purdue",
    "agc",
    "sldc",
    "feeder",
    "distribution transformer",
    "energy management system",
    # IT/identity hunt cues for out-of-registry detection asks with no OT token
    # (concurrent-session / impossible-travel, AD account-lifecycle event codes).
    "concurrent",
    "two different locations",
    "two separate locations",
    "impossible travel",
    "event code 4720",
    "event code 4624",
    "event code 4625",
    "account creation",
    "newly created account",
    "credential dumping",
)
_DETECTION_VERBS = (
    "flag ",
    "detect ",
    "identify ",
    "show ",
    "list ",
    "alert on",
    "find ",
    "surface ",
    "monitor ",
    "look for",
)


def detect_soc_investigation_shape(query: str, *, exact_105_match: bool = False) -> bool:
    normalized = " ".join(query.lower().split())
    # Pad so leading-space context tokens (e.g. " plc", " rtu") match at the edges.
    padded = f" {normalized} "
    ot_ics_detection = any(verb in padded for verb in _DETECTION_VERBS) and any(
        ctx in padded for ctx in _OT_ICS_CONTEXT
    )
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
        (hunt_phrasing or (anomaly_phrasing and network_or_ot_context) or ot_ics_detection)
        and not unsafe_or_execution
        and not sop_only
        and not non_soc
        and not exact_105_match
    )
