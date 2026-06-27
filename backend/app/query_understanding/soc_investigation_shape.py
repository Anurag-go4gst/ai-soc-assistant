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


# --- Out-of-registry answer-intent floors (P1 routing/skill activation) ---------
#
# The legacy out-of-registry cascade dropped anything it could not narrowly keyword
# to `knowledge_recall` (LOW_CONFIDENCE_ROUTE). On the live-efficacy-100 corpus this
# collapsed 34 investigation/SPL asks into thin knowledge answers. These two
# deterministic detectors let the router keep investigation and detection/SPL asks
# on their proper skills while preserving genuine knowledge-only / regulatory turns.
#
# Knowledge-explanation openers ("describe how", "explain the difference", …) are an
# explicit guard: a meta/definition question is NOT an investigation even if it
# mentions evidence or containment (e.g. "Describe how source evidence should
# constrain severity and containment recommendations").

_KNOWLEDGE_EXPLANATION_OPENERS = (
    "describe how",
    "explain the difference",
    "explain when",
    "explain why",
    "what distinguishes",
    "what is wrong with",
    "which soc skill",
    "what should happen when",
    "what is the difference",
    "how can analysts avoid",
    "should constrain",
)

# Unsafe live-execution / bulk-secret-exfil phrasing must never be routed to a
# review-only SPL or investigation answer; it falls through to the deterministic
# boundary/refusal path (knowledge_recall acceptable for the skill metric). Example:
# "Run a Splunk search now for every event containing a password and return all
# raw records."
_UNSAFE_EXECUTION_MARKERS = (
    "run a splunk search now",
    "run the search now",
    "run this search now",
    "run now",
    "execute now",
    "all raw records",
    "every event containing a password",
    "containing a password",
    "every password",
    "dump all",
    "return all raw",
)


def is_unsafe_execution(normalized: str) -> bool:
    return any(marker in normalized for marker in _UNSAFE_EXECUTION_MARKERS)


# Genuine investigation / triage / evidence-led framing -> guided_investigation.
_INVESTIGATION_MARKERS = (
    "investigate",
    "investigation",
    "evidence-led",
    "evidence plan",
    "what evidence",
    "which evidence",
    "evidence would",
    "evidence is needed",
    "evidence needed",
    "evidence priorities",
    "prioritize evidence",
    "assess whether",
    "how should analysts",
    "how should the soc",
    "how should source",
    "reconstruct whether",
    "reconstruct ",
    "triage plan",
    "cross-domain",
    "what additional facts",
    "what facts are needed",
    "is that enough to call",
    "verify first",
    "response steps",
    "next-action checklist",
    "safe next-action",
    "hypotheses",
    "containment recommendation",
    "what would a safe",
    "what logs",
    "how to validate",
)

# Verbs that request the production of an artifact.
_SPL_BUILD_VERBS = (
    "write ",
    "draft ",
    "create ",
    "generate ",
    "build ",
    "develop ",
    "produce ",
    "construct ",
    "provide ",
)
# Direct Splunk-artifact phrasings (no build verb required).
_SPL_DIRECT_MARKERS = (
    "splunk search",
    "splunk-oriented",
    "splunk query",
    "review-only spl",
    "in splunk",
    "weekly metric",
    "metric for detecting",
    "baseline approach",
)
# Build-verb objects that mean "a search artifact".
_SPL_ARTIFACT_OBJECTS = (
    "search",
    "query",
    "hunt",
)
# Detection imperatives that request a concrete result set (review-only SPL).
_DETECTION_IMPERATIVES = (
    "hunt for",
    "find ",
    "identify ",
    "detect ",
    "correlate ",
    "which users",
    "which hosts",
    "which accounts",
    "which endpoints",
)
# Enumeration asks ("show/list all connections") request a result set, not hunt prose.
_SPL_ENUMERATION_IMPERATIVES = (
    "show me all ",
    "show me ",
    "list all ",
    "list ",
    "give me ",
    "map all ",
    "check logs for ",
)
_SPL_ENUMERATION_OBJECTS = (
    "connection",
    "session",
    "traffic",
    "mapping",
    "event",
    "log",
)
_SHOW_ME_KNOWLEDGE_GUARDS = (
    "show me the sop",
    "show me the playbook",
    "show me the runbook",
    "show me the soc checklist",
)

# Open-ended hunt-hypothesis asks ("Anything to hunt for…", "What should I hunt
# for…") are investigation guidance, NOT a concrete SPL artifact request. They must
# reach the guided_investigation rescue, so the SPL floor explicitly stands down.
_HUNT_HYPOTHESIS_GUARD = (
    "anything to hunt",
    "what should i hunt",
    "what should we hunt",
    "where should i start",
    "how should i investigate",
    "can you help investigate",
    "help investigate",
    "help me investigate",
    "what should soc check",
    "what should analyst",
    "what evidence should i collect",
)


def detect_investigation_request(query: str) -> bool:
    """Out-of-registry analyst investigation/triage/evidence framing.

    Returns False for knowledge-explanation openers so definition/governance asks
    keep their knowledge_recall answer shape.
    """
    normalized = " ".join(query.lower().split())
    if is_unsafe_execution(normalized):
        return False
    if any(opener in normalized for opener in _KNOWLEDGE_EXPLANATION_OPENERS):
        return False
    return any(marker in normalized for marker in _INVESTIGATION_MARKERS)


def detect_spl_artifact_request(query: str) -> bool:
    """Out-of-registry ask for a Splunk search / detection result (review-only)."""
    normalized = " ".join(query.lower().split())
    if is_unsafe_execution(normalized):
        return False
    if any(opener in normalized for opener in _KNOWLEDGE_EXPLANATION_OPENERS):
        return False
    if any(guard in normalized for guard in _HUNT_HYPOTHESIS_GUARD):
        return False
    if "spl" in normalized and any(verb in normalized for verb in _SPL_BUILD_VERBS):
        return True
    if any(marker in normalized for marker in _SPL_DIRECT_MARKERS):
        return True
    if any(verb in normalized for verb in _SPL_BUILD_VERBS) and any(
        obj in normalized for obj in _SPL_ARTIFACT_OBJECTS
    ):
        return True
    if any(imperative in normalized for imperative in _DETECTION_IMPERATIVES):
        return True
    if any(guard in normalized for guard in _SHOW_ME_KNOWLEDGE_GUARDS):
        return False
    if any(imperative in normalized for imperative in _SPL_ENUMERATION_IMPERATIVES) and any(
        obj in normalized for obj in _SPL_ENUMERATION_OBJECTS
    ):
        return True
    return False


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
    non_soc = any(
        term in normalized
        for term in (
            "hr policy",
            "leave policy",
            "vacation policy",
            "vacation request",
            "payroll",
            "expense policy",
        )
    )
    # Meta/definition governance asks ("which SOC skill should own…") are knowledge,
    # not an investigation, even when they mention a hunt query in the abstract.
    knowledge_meta = any(opener in normalized for opener in _KNOWLEDGE_EXPLANATION_OPENERS)
    return bool(
        (hunt_phrasing or (anomaly_phrasing and network_or_ot_context) or ot_ics_detection)
        and not unsafe_or_execution
        and not sop_only
        and not non_soc
        and not knowledge_meta
        and not exact_105_match
    )


def detect_hunt_hypothesis_guidance_phrasing(query: str) -> bool:
    """Triage/hypothesis phrasing that must not be treated as live-data retrieval."""
    normalized = " ".join((query or "").lower().split())
    return any(guard in normalized for guard in _HUNT_HYPOTHESIS_GUARD)
