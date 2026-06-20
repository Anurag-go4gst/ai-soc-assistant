"""Deterministic answer-shape router for T2 / out-of-catalog paths (WS-0)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from app.chat.signal_class_guidance import build_signal_class_guidance
from app.chat.multi_leg_evidence import compose_multi_leg_evidence, render_multi_leg_guidance
from app.config import settings

AnswerShape = Literal[
    "hunt",
    "ir_containment_advisory",
    "ti_advisory_mapping",
    "regulatory_knowledge",
    "source_health",
    "baselining",
    "timeline_reconstruction",
    "insider_dlp",
    "process_aware_ot",
    "supply_chain_firmware_integrity",
]

IN_CATALOG_MATCH_PATHS = frozenset(
    {
        "exact_105_question",
        "exact_105_plus_use_case_catalog",
        "semantic_105_question",
        "use_case_catalog",
    }
)

_SHAPE_PRECEDENCE: tuple[AnswerShape, ...] = (
    "ir_containment_advisory",
    "regulatory_knowledge",
    "process_aware_ot",
    "supply_chain_firmware_integrity",
    "insider_dlp",
    "timeline_reconstruction",
    "ti_advisory_mapping",
    "source_health",
    "baselining",
    "hunt",
)

_IR_CONTAINMENT = re.compile(
    r"\b(isolate|isolation|contain|containment|disconnect|quarantine|segment now|"
    r"shut down|cut off)\b.{0,48}\b(ot|scada|plc|substation|grid)\b|"
    r"\bshould (?:we|soc) (?:isolate|contain|disconnect)\b",
    re.IGNORECASE,
)
_REGULATORY = re.compile(
    r"\b(cert-?in|cea|reporting obligation|regulatory|compliance|6[\s-]?hour|"
    r"incident report|notify (?:cert|authority)|mandatory report)\b",
    re.IGNORECASE,
)
_TI_ADVISORY = re.compile(
    r"\b(threat intel|threat intelligence|ttp[s]?|ioc[s]?|advisory mapping|new advisory|"
    r"what (?:do we|can we) (?:detect|log) (?:for|today)|what we log today)\b",
    re.IGNORECASE,
)
_SOURCE_HEALTH = re.compile(
    r"\b(log source health|silent source|blind spot|coverage gap|missing logs|"
    r"ingestion gap|source health|data gap|log sources? (?:have )?stopped sending|"
    r"stopped sending events)\b",
    re.IGNORECASE,
)
_BASELINING = re.compile(
    r"\b(what is normal|what does normal|baseline|baselining|normal behavior|typical volume|"
    r"descriptive stats|establish a baseline)\b",
    re.IGNORECASE,
)
_TIMELINE = re.compile(
    r"\b(timeline|chronolog|sequence of events|causal link|reconstruct (?:the )?events|"
    r"order of operations)\b",
    re.IGNORECASE,
)
_INSIDER_DLP = re.compile(
    r"\b(insider|dlp|data loss|exfil.{0,24}user|user.{0,24}exfil|"
    r"privileged user.{0,32}(?:copy|upload|transfer))\b",
    re.IGNORECASE,
)
# Process-aware shape is reserved for grid-physics / frequency-control judgment
# (AGC, frequency band, setpoint, dispatch). Protocol tokens (GOOSE/MMS) and
# synchrophasor tokens (PMU/PDC) are hunt-shaped and resolved by the WS-1
# signal-class layer, not by this shape — keeping them here over-routed protocol
# hunts into a grid-physics deferral.
_PROCESS_AWARE = re.compile(
    r"\b(agc|automatic generation control|frequency band|grid operations|setpoint|"
    r"frequency deviation|grid-physics|generation control)\b",
    re.IGNORECASE,
)
_SUPPLY_CHAIN_FW = re.compile(
    r"\bsupply[\s-]?chain\b|"
    r"\b(?:firmware|code[\s-]?signing)\b.{0,60}\b(?:certificate|signing cert|key rotation|signed with|unexpected (?:cert|certificate|key))\b|"
    r"\bsigned with an unexpected\b",
    re.IGNORECASE,
)
_HUNT = re.compile(
    r"\b(hunt|investigate|suspicious|anomal|unusual|anything to|where should i start|"
    r"what should (?:soc|analyst)|evidence (?:to )?collect)\b",
    re.IGNORECASE,
)

_SHAPE_DETECTORS: tuple[tuple[AnswerShape, re.Pattern[str]], ...] = (
    ("ir_containment_advisory", _IR_CONTAINMENT),
    ("regulatory_knowledge", _REGULATORY),
    ("process_aware_ot", _PROCESS_AWARE),
    ("supply_chain_firmware_integrity", _SUPPLY_CHAIN_FW),
    ("insider_dlp", _INSIDER_DLP),
    ("timeline_reconstruction", _TIMELINE),
    ("ti_advisory_mapping", _TI_ADVISORY),
    ("source_health", _SOURCE_HEALTH),
    ("baselining", _BASELINING),
    ("hunt", _HUNT),
)


@dataclass(frozen=True)
class AnswerShapeResult:
    primary_shape: AnswerShape
    secondary_shape: AnswerShape | None = None
    matched_shapes: tuple[AnswerShape, ...] = ()


def is_regulatory_reporting_query(query: str) -> bool:
    """True when the query is a regulatory / reporting-obligation ask (WS-7a)."""
    normalized = " ".join(query.lower().split())
    return bool(_REGULATORY.search(normalized))


def is_supply_chain_firmware_query(query: str) -> bool:
    """True for vendor firmware / code-signing integrity asks (WS pk.009)."""
    normalized = " ".join(query.lower().split())
    if "supply chain" in normalized or "supply-chain" in normalized:
        return True
    firmware = any(term in normalized for term in ("firmware", "code-signing", "code signing"))
    integrity = any(
        term in normalized
        for term in (
            "certificate",
            "signing cert",
            "key rotation",
            "signed with",
            "unexpected cert",
            "unexpected certificate",
            "unexpected code",
        )
    )
    return firmware and integrity


def should_bypass_shape_router(match_path: str | None) -> bool:
    """Happy-path bypass: in-catalog matches keep legacy finalize/render."""
    return str(match_path or "") in IN_CATALOG_MATCH_PATHS


def classify_answer_shape(query: str, *, entities: dict[str, Any] | None = None) -> AnswerShapeResult:
    """Deterministic shape classifier — keyword + entity signals only."""
    _ = entities
    normalized = " ".join(query.lower().split())
    matched: list[AnswerShape] = []
    for shape, pattern in _SHAPE_DETECTORS:
        if pattern.search(normalized):
            matched.append(shape)
    if not matched:
        return AnswerShapeResult(primary_shape="hunt", matched_shapes=("hunt",))
    ordered = [shape for shape in _SHAPE_PRECEDENCE if shape in matched]
    primary = ordered[0]
    secondary = ordered[1] if len(ordered) > 1 else None
    return AnswerShapeResult(
        primary_shape=primary,
        secondary_shape=secondary,
        matched_shapes=tuple(ordered),
    )


def build_shaped_guidance(
    query: str,
    *,
    entities: dict[str, Any] | None = None,
    match_path: str | None = None,
) -> str:
    """Build analyst guidance for the resolved answer shape."""
    if not settings.ai_soc_t2_answer_shape_enabled or should_bypass_shape_router(match_path):
        from app.chat.guidance_templates import build_guided_investigation_guidance

        return build_guided_investigation_guidance(query, entities)
    result = classify_answer_shape(query, entities=entities)
    primary = _build_primary_shape_guidance(query, result.primary_shape, entities=entities)
    sections = [primary]
    if result.secondary_shape is not None:
        sections.append(_build_secondary_section(query, result.secondary_shape, entities=entities))
    multi_leg = render_multi_leg_guidance(compose_multi_leg_evidence(query))
    if multi_leg:
        sections.append(multi_leg)
    return "\n\n---\n\n".join(sections)


def _build_primary_shape_guidance(
    query: str,
    shape: AnswerShape,
    *,
    entities: dict[str, Any] | None,
) -> str:
    if shape == "hunt":
        return build_signal_class_guidance(query, entities)
    if shape == "ir_containment_advisory":
        return _ir_containment_guidance(query)
    if shape == "ti_advisory_mapping":
        return _ti_advisory_guidance(query)
    if shape == "regulatory_knowledge":
        return _regulatory_knowledge_guidance(query, entities=entities)
    if shape == "source_health":
        return _source_health_guidance(query)
    if shape == "baselining":
        return _baselining_guidance(query)
    if shape == "timeline_reconstruction":
        return _timeline_guidance(query)
    if shape == "insider_dlp":
        return _insider_dlp_guidance(query, entities)
    if shape == "process_aware_ot":
        return _process_aware_guidance(query, entities)
    if shape == "supply_chain_firmware_integrity":
        return build_supply_chain_firmware_guidance(query)
    from app.chat.guidance_templates import build_guided_investigation_guidance

    return build_guided_investigation_guidance(query, entities)


def _build_secondary_section(
    query: str,
    shape: AnswerShape,
    *,
    entities: dict[str, Any] | None,
) -> str:
    label = shape.replace("_", " ").title()
    body = _build_primary_shape_guidance(query, shape, entities=entities)
    return f"Secondary focus ({label}):\n\n{body}"


def _ir_containment_guidance(query: str) -> str:
    _ = query
    return (
        "IR / containment advisory (review-only — no automated enforcement)\n\n"
        "Staged guidance:\n"
        "- Confirm scope: affected OT assets, zones, and blast radius before any isolation.\n"
        "- Coordinate with grid operations / control-room before disconnecting SCADA paths.\n"
        "- Preserve forensic state: snapshot configs, session logs, and recent change tickets.\n"
        "- Prefer monitored segmentation over abrupt shutdown unless safety requires immediate action.\n"
        "- Document approvers and rollback plan; human-in-the-loop required for any enforcement.\n\n"
        "Limitations: no containment action was performed. Automated block/disable/quarantine "
        "remains blocked until analyst approval."
    )


def _ti_advisory_guidance(query: str) -> str:
    _ = query
    return (
        "Threat-intel advisory mapping (review-only)\n\n"
        "| TTP / IOC theme | What we can log today | Hunt / detection gap |\n"
        "|---|---|---|\n"
        "| OT protocol abuse | Firewall/session, DPI where deployed | Field-level OT command semantics may be missing |\n"
        "| Identity pivot | Auth/VPN/EDR where present | Jump-host ↔ OT correlation may need asset registry |\n"
        "| Egress / C2 | Proxy/DNS/firewall egress | Data-diode directionality must be validated locally |\n\n"
        "Next steps: map the cited advisory TTPs to your onboarded indexes/sourcetypes; "
        "flag gaps honestly rather than implying live detection coverage."
    )


def _regulatory_knowledge_guidance(query: str, *, entities: dict[str, Any] | None = None) -> str:
    _ = entities
    normalized = " ".join(query.lower().split())
    if "cert" in normalized or "6 hour" in normalized or "6-hour" in normalized:
        checklist = [
            "Confirm whether the event meets your organization's CERT-In / sector reporting threshold.",
            "Collect incident facts: scope, affected systems, timeline, and containment status.",
            "Engage legal/compliance and CISO before external notification.",
            "Verify current statutory timelines against your governed SOC-KB — do not rely on this assistant as legal authority.",
        ]
    else:
        checklist = [
            "Identify the applicable regulatory framework (CEA, sectoral, or internal policy).",
            "Gather evidence package: logs, asset list, impact assessment.",
            "Route to compliance/CISO for authoritative interpretation.",
        ]
    items = "\n".join(f"- {item}" for item in checklist)
    return (
        "Regulatory / reporting guidance (knowledge-only — no SPL)\n\n"
        f"SOC review checklist:\n\n{items}\n\n"
        "Disclaimer: verify with compliance/CISO — this is not legal authority. "
        "No Splunk search was generated for this reporting-obligation question."
    )


def _source_health_guidance(query: str) -> str:
    _ = query
    return (
        "Log-source health / coverage review\n\n"
        "Checklist:\n"
        "- List expected OT/IT sources for the scope (firewall, DNS, VPN, EDR, OT historian).\n"
        "- Compare ingest volume and last-seen timestamps against baseline.\n"
        "- Flag silent or lagging sources before hunting on incomplete telemetry.\n"
        "- Correlate gaps with change tickets or collector maintenance.\n\n"
        "Limitations: this is a coverage assessment shape — not a detection hunt."
    )


def _baselining_guidance(query: str) -> str:
    _ = query
    return (
        "Baselining / descriptive statistics (not a detection hunt)\n\n"
        "Approach:\n"
        "- Define the asset cohort and observation window.\n"
        "- Use stats/timechart for volume, peer comparison, and seasonality — not threshold alerts.\n"
        "- Document expected operational bands with operations/engineering input.\n"
        "- Promote to detection only after baseline sign-off.\n\n"
        "Suggested SPL posture: descriptive stats (`stats`/`timechart`) for analyst review only."
    )


def _timeline_guidance(query: str) -> str:
    _ = query
    return (
        "Timeline reconstruction (review-only)\n\n"
        "Steps:\n"
        "- Anchor on earliest and latest corroborated events across independent sources.\n"
        "- Build host/user/session ordering; note causal links only when evidence supports them.\n"
        "- Call out gaps explicitly — do not infer attack stage without logs.\n"
        "- Use chronology reviewer output when cyclic evidence collection is enabled.\n\n"
        "Honesty: correlation ≠ causation; state uncertainty where logs are incomplete."
    )


def _insider_dlp_guidance(query: str, entities: dict[str, Any] | None) -> str:
    users = list((entities or {}).get("user") or [])
    user_hint = f" Pivot on user(s): {', '.join(users)}." if users else ""
    return (
        "Insider / DLP investigation (review-only)\n\n"
        "Hypotheses:\n"
        "- Policy-approved data movement or backup activity.\n"
        "- Misconfigured sync or automation copying sensitive files.\n"
        "- Intentional exfiltration requiring user-behavior corroboration.\n\n"
        "Evidence to collect:\n"
        "- Identity: account type, role changes, MFA/device context.\n"
        "- Egress: proxy/DLP/email/USB events tied to the same user and window.\n"
        "- Asset: host/file paths, volume, destination, first-seen.\n"
        f"{user_hint}\n\n"
        "Limitations: user-centric pivot required; do not claim insider threat without multi-signal alignment."
    )


def _process_aware_guidance(query: str, entities: dict[str, Any] | None) -> str:
    _ = entities
    from app.chat.guidance_templates import build_conceptual_mitre_guidance

    judgment = build_conceptual_mitre_guidance(query)
    return (
        "Process-aware OT review (defer to grid operations + security overlay)\n\n"
        f"{judgment}\n\n"
        "Grid-physics framing:\n"
        "- Separate normal AGC/frequency regulation from unauthorized setpoint changes.\n"
        "- Review engineering logs, relay event files, and operations shift notes.\n"
        "- Escalate to grid operations before technique-level conclusions.\n\n"
        "Limitations: security analytics alone cannot prove grid instability intent."
    )


def build_supply_chain_firmware_guidance(query: str) -> str:
    """Judgment + investigation substance for vendor firmware / code-signing asks.

    WS-5d: pairs the deterministic "not enough to confirm" judgment with concrete
    steps to separate a legitimate vendor key rotation from a supply-chain
    compromise — never judgment alone.
    """
    from app.chat.guidance_templates import build_conceptual_mitre_guidance

    judgment = build_conceptual_mitre_guidance(query)
    return (
        "Supply-chain firmware integrity review (review-only)\n\n"
        f"{judgment}\n\n"
        "Separate legitimate key rotation from compromise:\n"
        "- Verify the code-signing certificate: issuer chain, validity window, and thumbprint "
        "against the vendor's known-good signing key.\n"
        "- Confirm an out-of-band vendor advisory or change ticket authorizing a key rotation "
        "for this firmware release.\n"
        "- Compare the firmware hash/version against the vendor's published release manifest.\n"
        "- Correlate the push: source host/account, delivery channel, and whether all targeted "
        "devices were updated in one window (a single mass push raises risk).\n"
        "- Hold rollout, stage to a test bench, and preserve the prior firmware image for rollback.\n\n"
        "Limitations: an unexpected signing certificate alone does NOT confirm compromise — "
        "corroborate certificate provenance, vendor authorization, and firmware hash first. Any "
        "MITRE mapping stays candidate (e.g. candidate T0857 System Firmware / supply-chain) "
        "until provenance is verified."
    )


def shape_suppresses_spl(shape: AnswerShape) -> bool:
    """Pure knowledge shapes must not surface an SPL draft.

    `baselining` is intentionally NOT suppressed: per plan WS-0 it should surface
    a descriptive-stats (`stats`/`timechart`) draft for analyst review, distinct
    from a detection hunt. Only `regulatory_knowledge` and `source_health`
    (coverage assessment, not a query) suppress the SPL artifact.
    """
    return shape in {"regulatory_knowledge", "source_health"}
