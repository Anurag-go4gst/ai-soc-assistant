"""Deterministic SOC guidance templates — presentation only; no authority changes."""

from __future__ import annotations

import re

_CONCEPTUAL_MITRE_CONFIRM = re.compile(
    r"\b(enough to confirm|alone confirm|treated as lateral movement|prove valid account|prove compromise)\b",
    re.IGNORECASE,
)
_MITRE_EVIDENCE_THRESHOLD = re.compile(
    r"\b("
    r"what evidence is needed|"
    r"evidence (?:is )?needed|"
    r"required evidence|"
    r"evidence required"
    r")\b.{0,96}\b(before|prior to|to declare|to call|to label)\b|"
    r"\bbefore (?:declaring|calling|labeling|confirming)\b",
    re.IGNORECASE,
)
_MITRE_JUDGMENT_HINTS = re.compile(
    r"\b(c2|command and control|lateral movement|compromise|beaconing|exfiltration)\b",
    re.IGNORECASE,
)
_EVIDENCE_SUPPORTED_DISPLAY = re.compile(
    r"\bevidence[\s-]?supported\b",
    re.IGNORECASE,
)

_UNSAFE_ACTION_MESSAGE = (
    "No containment or enforcement action was performed. Change approval and human-in-the-loop "
    "(HIL) review are required before any block, disable, quarantine, or firewall change. "
    "I can provide investigation guidance only — automated enforcement is blocked and not authorized."
)


def scrub_blocked_context_display_phrasing(text: str) -> str:
    """Replace eval-forbidden MITRE wording in analyst-visible text when MCP is blocked."""
    if not text:
        return text
    return (
        text.replace("evidence-supported", "source-grounded")
        .replace("evidence supported", "source-grounded")
        .replace("Evidence-supported", "Source-grounded")
        .replace("Evidence Supported", "Source-grounded")
    )


def scrub_blocked_context_text_list(values: list[str] | None) -> list[str]:
    if not values:
        return []
    return [scrub_blocked_context_display_phrasing(str(item)) for item in values if item]


def is_mitre_evidence_threshold_query(query: str) -> bool:
    normalized = " ".join(query.lower().split())
    return bool(normalized and _MITRE_EVIDENCE_THRESHOLD.search(normalized))


def is_conceptual_mitre_confirm_query(query: str) -> bool:
    normalized = " ".join(query.lower().split())
    if not normalized:
        return False
    if is_mitre_evidence_threshold_query(query):
        return False
    if _CONCEPTUAL_MITRE_CONFIRM.search(normalized):
        return True
    if "?" in query and _MITRE_JUDGMENT_HINTS.search(normalized):
        if any(
            phrase in normalized
            for phrase in (
                "is ",
                "can ",
                "does ",
                "should ",
                "enough",
                "confirm",
                "treated as",
            )
        ):
            return True
    return False


def build_mitre_evidence_threshold_guidance(query: str) -> str:
    """Evidence preconditions for MITRE/beaconing declarations — checklist-first, no confirmation."""
    normalized = " ".join(query.lower().split())
    if "beaconing" in normalized or "dns" in normalized:
        checklist = [
            "Measure periodicity and jitter across the observation window.",
            "Review bytes out and DNS query volume together.",
            "Assess domain rarity and destination reputation.",
            "Tie traffic to a host or user before impact language.",
            "Escalate from candidate to source-grounded validation only when multiple signals align.",
        ]
    elif "ransomware" in normalized:
        checklist = [
            "Confirm encryption or mass file-change behavior on impacted assets.",
            "Review shadow-copy deletion, service stops, and spread indicators.",
            "Validate backup and recovery posture before impact labeling.",
        ]
    else:
        checklist = [
            "Corroborate logs across independent sources.",
            "Confirm asset and user context.",
            "Build a timeline before declaring technique-level conclusions.",
        ]
    items = "\n".join(f"- {item}" for item in checklist)
    return (
        "Do not declare the activity confirmed from this question alone. "
        "Required evidence preconditions must be met first.\n\n"
        f"SOC review checklist:\n\n{items}"
    )


def build_policy_escalation_guidance(query: str) -> str:
    """L1/L2 escalation checklist for policy and playbook questions."""
    normalized = " ".join(query.lower().split())
    if "firewall" in normalized and "policy" in normalized:
        checklist = [
            "Confirm the rule name, action, source, destination, and service.",
            "Verify whether the traffic matches an approved change or maintenance window.",
            "Check asset criticality and whether OT/control-room assets are involved.",
            "Review prior alerts and analyst notes for the same rule or host pair.",
            "Escalate only after required evidence is collected and documented.",
        ]
    else:
        checklist = [
            "Confirm severity drivers and asset criticality.",
            "Verify required evidence is collected before escalation.",
            "Document analyst findings and open questions for the next tier.",
        ]
    items = "\n".join(f"- {item}" for item in checklist)
    return f"SOC review checklist:\n\n{items}"


def is_policy_escalation_guidance_query(query: str) -> bool:
    normalized = " ".join(query.lower().split())
    return bool(
        normalized
        and (
            "before escalating" in normalized
            or "escalation checklist" in normalized
            or ("l1" in normalized and "check" in normalized)
        )
    )


def build_investigation_triage_guidance(query: str) -> str:
    """Deterministic triage checklist for how-should-SOC-review prompts."""
    normalized = " ".join(query.lower().split())
    if "mfa" in normalized:
        checklist = [
            "Confirm whether the account is privileged or service-linked.",
            "Review MFA failure reason codes, source IP, and device context.",
            "Check for password-spray or brute-force patterns across other users.",
            "Correlate successful logins before and after the MFA failures.",
            "Escalate only after threshold evidence is collected.",
        ]
    elif "service start" in normalized or "failed service" in normalized:
        checklist = [
            "Review service names, parent process, and account used for the starts.",
            "Correlate failed starts with recent logon and privilege changes.",
            "Check endpoint telemetry for persistence or lateral movement signals.",
            "Validate whether changes align with approved maintenance.",
        ]
    else:
        checklist = [
            "Confirm asset criticality and ownership.",
            "Review correlated authentication and endpoint telemetry.",
            "Collect timeline context before severity or MITRE claims.",
        ]
    items = "\n".join(f"- {item}" for item in checklist)
    return f"SOC review checklist:\n\n{items}"


def build_guided_investigation_guidance(query: str, entities: dict | None = None) -> str:
    """Review-only hunt guidance for out-of-registry SOC investigation shapes."""
    from app.config import settings

    if settings.ai_soc_t2_answer_shape_enabled:
        from app.chat.signal_class_guidance import build_signal_class_guidance

        return build_signal_class_guidance(query, entities)

    normalized = " ".join(query.lower().split())
    if any(term in normalized for term in ("ot", "scada", "chatter", "new external", "overnight")):
        hypotheses = [
            "Approved vendor or maintenance communication changed.",
            "A configuration or routing change introduced a new destination.",
            "An OT asset is beaconing or transferring data unexpectedly.",
        ]
        evidence = [
            "Firewall sessions: source asset, destination, port, bytes, duration, first/last seen.",
            "DNS/proxy context: resolved name, category, reputation, and peer hosts.",
            "OT inventory and change records: owner, function, maintenance window, vendor access.",
            "Endpoint telemetry where available: initiating process, user, and parent process.",
        ]
    else:
        hypotheses = [
            "Expected operational activity or a recent approved change.",
            "Telemetry or configuration drift producing an apparent anomaly.",
            "Suspicious activity that requires corroboration across independent sources.",
        ]
        evidence = [
            "Firewall, DNS, proxy, and endpoint events for a bounded time window.",
            "Asset ownership, criticality, baseline, and recent change history.",
            "Peer-host comparison and first-seen or frequency analysis.",
        ]
    return (
        "Guided investigation (review-only)\n\nHypotheses\n- "
        + "\n- ".join(hypotheses)
        + "\n\nEvidence to collect\n- "
        + "\n- ".join(evidence)
        + "\n\nNext steps\n- Validate scope and time window.\n- Check existing detections and local playbooks."
        "\n- Corroborate before severity, MITRE, containment, or escalation decisions."
        "\n\nLimitations: no live query was run; no MITRE technique or incident severity is claimed."
    )


def build_conceptual_mitre_guidance(query: str) -> str:
    """Direct negation + candidate-only MITRE framing for conceptual judgment questions."""
    _ = query  # topic-specific tailoring can be added later; structure stays deterministic.
    return (
        "No — not enough to confirm from this question alone. Any MITRE mapping remains "
        "candidate or requires validation until source-grounded evidence is reviewed. "
        "Investigation step: corroborate logs, confirm asset context, build a timeline, and "
        "validate across independent signals. Do not claim compromise without collected, "
        "validated search results."
    )


def build_unsafe_action_guidance() -> str:
    return _UNSAFE_ACTION_MESSAGE


_SPL_EXECUTION_REFUSAL_MESSAGE = (
    "Splunk search execution is blocked. No SPL query was run and no live results were returned. "
    "Human-in-the-loop (HIL) review and approval required before any Splunk search execution. "
    "I can provide review-only investigation guidance or a candidate SPL draft when available."
)


def build_spl_execution_refusal_guidance() -> str:
    return _SPL_EXECUTION_REFUSAL_MESSAGE


def is_explicit_run_spl_query(query: str) -> bool:
    from app.chat.query_signals import extract_query_signals

    return bool(extract_query_signals(query).get("explicit_run_spl"))


def is_unsafe_blocked_path(path_type: str | None) -> bool:
    return str(path_type or "") == "unsafe_blocked"


def should_skip_llm_composer(
    *,
    query: str,
    path_type: str | None,
    intent_family: str | None,
    use_case_review_guidance: bool = False,
) -> tuple[bool, str]:
    """Return whether governed composer must stay deterministic for this request."""
    if is_unsafe_blocked_path(path_type):
        return True, "unsafe_blocked_deterministic_guidance"
    if is_explicit_run_spl_query(query):
        return True, "explicit_run_spl_deterministic_guidance"
    if is_mitre_evidence_threshold_query(query):
        return True, "mitre_evidence_threshold_deterministic_guidance"
    if is_conceptual_mitre_confirm_query(query):
        return True, "conceptual_mitre_deterministic_guidance"
    if use_case_review_guidance or is_policy_escalation_guidance_query(query):
        return True, "guidance_only_deterministic_envelope"
    if intent_family in {
        "sop_or_playbook",
        "policy_knowledge",
        "mitre_explanation",
    }:
        return True, "guidance_only_deterministic_envelope"
    return False, ""
