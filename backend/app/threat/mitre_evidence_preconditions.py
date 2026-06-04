"""MITRE evidence preconditions — data-driven, tactic-general.

Replaces per-use-case "not claimed" hardcoding (`_DEFAULT_NOT_CLAIMED`,
`_not_claimed_for_context`) with a reusable rule: a MITRE technique may only be
presented as a candidate when its *required positive evidence* is present. When
a required precondition is absent (or explicitly negated by observed signals),
the technique is "evidence-negated" and is demoted to Not Claimed with a stable
reason — for authentication, DNS/DGA, phishing, malware, network, exfiltration,
and lateral movement alike.

This module makes no authority decision; it is a lookup consumed by
`mitre_decision.resolve_mitre_decision`. The set of present evidence keys is
produced by `chat.negative_evidence_extractor`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TechniquePrecondition:
    """One technique's required positive evidence and its Not-Claimed reason."""

    technique_id: str
    name: str
    required_evidence: tuple[str, ...]
    not_claimed_reason: str


# Positive-evidence keys (see negative_evidence_extractor for how they are set).
# A technique is evidence-negated when ANY required key is absent from the
# present-evidence set. Keys with no live signal yet (exfil, etc.) are inert
# until their evidence/signal lands, but the rule already generalizes to them.
PRECONDITIONS: tuple[TechniquePrecondition, ...] = (
    TechniquePrecondition(
        "T1078",
        "Valid Accounts",
        ("successful_login",),
        "No successful login or confirmed valid credential use.",
    ),
    TechniquePrecondition(
        "T1003",
        "OS Credential Dumping",
        ("credential_dumping_evidence",),
        "No credential dumping evidence.",
    ),
    TechniquePrecondition(
        "T1562.001",
        "Impair Defenses: Disable or Modify Tools",
        ("endpoint_telemetry",),
        "No defense impairment evidence; missing endpoint telemetry is not proof of disabled defenses.",
    ),
    TechniquePrecondition(
        "T1041",
        "Exfiltration Over C2 Channel",
        ("outbound_transfer",),
        "No outbound data transfer observed.",
    ),
    TechniquePrecondition(
        "T1071",
        "Application Layer Protocol",
        ("network_telemetry",),
        "No supporting network/command-and-control telemetry observed.",
    ),
    TechniquePrecondition(
        "T1021",
        "Remote Services",
        ("lateral_movement_evidence",),
        "No lateral movement or remote-service authentication observed.",
    ),
)

PRECONDITION_BY_ID: dict[str, TechniquePrecondition] = {
    item.technique_id: item for item in PRECONDITIONS
}


def precondition_negated(technique_id: str, present_evidence: set[str]) -> bool:
    """True when the technique has a precondition whose required evidence is absent.

    Techniques with no precondition entry are never demoted by this rule.
    """
    precondition = PRECONDITION_BY_ID.get(technique_id)
    if precondition is None:
        return False
    return any(key not in present_evidence for key in precondition.required_evidence)


def not_claimed_reason(technique_id: str) -> str:
    """Stable, technique-general Not-Claimed reason for trace and analyst card."""
    precondition = PRECONDITION_BY_ID.get(technique_id)
    if precondition is None:
        return "Required supporting evidence was not present in the supplied scenario."
    return precondition.not_claimed_reason
