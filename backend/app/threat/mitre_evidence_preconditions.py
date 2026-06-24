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
from functools import lru_cache
from typing import Any

# Evidence tiers — MITRE `evidence_supported` requires source-grounded tier only.
EVIDENCE_TIER_SOURCE_GROUNDED = "source_grounded"
EVIDENCE_TIER_SIGNAL_ONLY = "signal_only"
EVIDENCE_TIER_STUB_OR_METADATA = "stub_or_metadata"

_SOURCE_GROUNDED_SOURCE_TYPES = frozenset({"splunk_mcp"})
_STUB_SOURCE_TYPES = frozenset({"manual", "splunk_mcp_saia", "rag", "soc_kb"})
_NON_EXECUTED_STATUSES = frozenset({"skipped", "blocked", "denied", "pending"})


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
    TechniquePrecondition(
        "T1048",
        "Exfiltration Over Alternative Protocol",
        ("outbound_transfer",),
        "No outbound data transfer observed; large volume alone does not prove "
        "exfiltration over an alternative protocol.",
    ),
    TechniquePrecondition(
        "T1071.004",
        "Application Layer Protocol: DNS",
        ("network_telemetry",),
        "No supporting DNS command-and-control/tunneling telemetry observed; DNS "
        "volume alone is not proof of DNS-based C2.",
    ),
)

PRECONDITION_BY_ID: dict[str, TechniquePrecondition] = {
    item.technique_id: item for item in PRECONDITIONS
}

# Tactic-level positive-evidence keys for techniques promoted from the MITRE-audit
# (G5). Each is the conservative signal a finding must carry before the technique
# can leave Not-Claimed. Most keys are inert until their extractor signal lands —
# so a promoted candidate stays Not-Claimed by default (candidate-tier discipline).
# ATT&CK v19.1 tactic display names (incl. renames "Stealth", "Defense Impairment").
TACTIC_EVIDENCE: dict[str, tuple[str, str]] = {
    "Reconnaissance": ("recon_evidence", "No reconnaissance activity evidence observed."),
    "Resource Development": ("resource_development_evidence", "No adversary resource-development evidence observed."),
    "Initial Access": ("initial_access_evidence", "No initial-access evidence observed."),
    "Execution": ("process_execution_evidence", "No process/command execution evidence observed."),
    "Persistence": ("persistence_evidence", "No persistence-mechanism evidence observed."),
    "Privilege Escalation": ("privilege_escalation_evidence", "No privilege-escalation evidence observed."),
    "Defense Evasion": ("defense_evasion_evidence", "No defense-evasion evidence observed."),
    "Defense Impairment": ("defense_evasion_evidence", "No defense-impairment evidence observed."),
    "Stealth": ("defense_evasion_evidence", "No stealth/defense-evasion evidence observed."),
    "Credential Access": ("credential_access_evidence", "No credential-access evidence observed."),
    "Discovery": ("discovery_evidence", "No discovery-activity evidence observed."),
    "Lateral Movement": ("lateral_movement_evidence", "No lateral-movement evidence observed."),
    "Collection": ("collection_evidence", "No data-collection evidence observed."),
    "Command and Control": ("network_telemetry", "No supporting command-and-control network telemetry observed."),
    "Exfiltration": ("outbound_transfer", "No outbound data-transfer evidence observed."),
    "Impact": ("impact_evidence", "No system/data impact evidence observed."),
}


_G5_PROVENANCE = "mitre_audit_v19.1_promote_g5"


@lru_cache(maxsize=1)
def _promoted_tactic_index() -> dict[str, str]:
    """{technique_id: tactic} for ONLY the G5 audit-promoted techniques.

    Derived preconditions apply solely to bulk-promoted candidates; the original
    curated subset keeps its explicit-or-none behavior. Reads the raw subset JSON
    because the ``candidate_provenance`` stamp is dropped by the MitreTechnique
    model. Lazy + cached to avoid a circular import (mitre_kb imports this module).
    """
    import json
    from pathlib import Path

    try:
        path = Path(__file__).with_name("mitre_attack_subset.json")
        payload = json.loads(path.read_text(encoding="utf-8"))
        return {
            str(t.get("technique_id")): str(t.get("tactic") or "")
            for t in payload.get("techniques", [])
            if isinstance(t, dict) and t.get("candidate_provenance") == _G5_PROVENANCE
        }
    except Exception:  # noqa: BLE001 - precondition derivation is best-effort
        return {}


def get_precondition(technique_id: str) -> TechniquePrecondition | None:
    """Explicit curated precondition first; else derive one from the technique's
    tactic (for audit-promoted subset techniques). None when neither applies."""
    explicit = PRECONDITION_BY_ID.get(technique_id)
    if explicit is not None:
        return explicit
    tactic = _promoted_tactic_index().get(technique_id)
    if not tactic:
        return None
    mapped = TACTIC_EVIDENCE.get(tactic)
    if mapped is None:
        return None
    key, reason = mapped
    return TechniquePrecondition(technique_id, technique_id, (key,), reason)


def precondition_negated(technique_id: str, present_evidence: set[str]) -> bool:
    """True when the technique has a precondition whose required evidence is absent.

    Techniques with no precondition entry are never demoted by this rule.
    """
    precondition = get_precondition(technique_id)
    if precondition is None:
        return False
    return any(key not in present_evidence for key in precondition.required_evidence)


def not_claimed_reason(technique_id: str) -> str:
    """Stable, technique-general Not-Claimed reason for trace and analyst card."""
    precondition = get_precondition(technique_id)
    if precondition is None:
        return "Required supporting evidence was not present in the supplied scenario."
    return precondition.not_claimed_reason


def resolve_evidence_tier(
    *,
    source_evidence: list[dict[str, Any]] | None = None,
    execution: dict[str, Any] | None = None,
    source_profile_missing: bool = False,
) -> str:
    """Classify whether present signals can support evidence-supported MITRE claims.

    Query-signal-only and stub/metadata envelopes never qualify as source-grounded.
    """
    if source_profile_missing:
        return EVIDENCE_TIER_SIGNAL_ONLY

    exec_status = str((execution or {}).get("status") or "")
    if exec_status in _NON_EXECUTED_STATUSES:
        return EVIDENCE_TIER_STUB_OR_METADATA
    if exec_status == "executed":
        for item in source_evidence or []:
            if not isinstance(item, dict):
                continue
            source_type = str(item.get("source_type") or "")
            collection_status = str(item.get("collection_status") or "")
            warnings = {str(w) for w in item.get("warnings") or []}
            if (
                source_type in _SOURCE_GROUNDED_SOURCE_TYPES
                and collection_status == "collected"
                and "spl_not_required_for_skill" not in warnings
            ):
                return EVIDENCE_TIER_SOURCE_GROUNDED

    envelopes = [item for item in (source_evidence or []) if isinstance(item, dict)]
    if not envelopes:
        return EVIDENCE_TIER_SIGNAL_ONLY

    if all(
        str(item.get("source_type") or "") in _STUB_SOURCE_TYPES
        or str(item.get("collection_status") or "") in {"skipped", "stub", "metadata"}
        for item in envelopes
    ):
        return EVIDENCE_TIER_STUB_OR_METADATA

    return EVIDENCE_TIER_SIGNAL_ONLY


def cap_mitre_status_for_evidence_tier(status: str, evidence_tier: str) -> str:
    """Downgrade evidence-supported when tier is not source-grounded."""
    normalized = str(status or "candidate")
    if normalized != "evidence_supported":
        return normalized
    if evidence_tier == EVIDENCE_TIER_SOURCE_GROUNDED:
        return normalized
    return "requires_validation" if evidence_tier == EVIDENCE_TIER_STUB_OR_METADATA else "candidate"


def evaluate_pilot_mitre_evidence_status(
    *,
    use_case_id: str | None,
    technique_id: str,
    present_evidence: set[str],
) -> dict[str, Any]:
    """Evidence-status resolver for Batch 3 pilot enrichments.

    The resolver intentionally reads observed evidence keys only. MITRE registry
    metadata decides what is allowed to be considered; it is not evidence.
    """
    tid = technique_id.upper()
    use_case = str(use_case_id or "")
    evidence = set(present_evidence)

    status = "candidate"
    reason = "Technique is registry-permitted metadata; supporting evidence is still required."
    matched: set[str] = set()

    if use_case == "auth_failed_login_spike":
        if tid in {"T1110", "T1110.001"}:
            if "failed_login_pattern" in evidence:
                status = "evidence_supported"
                reason = "Repeated failed-login evidence is present for the brute-force/password-guessing pattern."
                matched = {"failed_login_pattern"}
        elif tid == "T1110.003":
            if "spray_breadth" in evidence:
                status = "evidence_supported"
                reason = "Breadth evidence across users or sources supports a password-spraying pattern."
                matched = {"spray_breadth"}
        elif tid == "T1078":
            if "valid_account_abuse" in evidence:
                status = "evidence_supported"
                reason = "Valid-account abuse evidence is present beyond failed logins."
                matched = {"valid_account_abuse"}
            else:
                status = "not_claimed"
                reason = "Failed logins alone do not support Valid Accounts or account compromise."

    elif use_case == "auth_success_after_failure":
        if tid == "T1110.001" and {"failed_login_pattern", "successful_login"}.issubset(evidence):
            status = "evidence_supported"
            reason = "Repeated failures before a successful login support password guessing."
            matched = {"failed_login_pattern", "successful_login"}
        elif tid == "T1078":
            strong = _first_present(
                evidence,
                {
                    "valid_account_abuse",
                    "source_ip_novelty",
                    "impossible_travel",
                    "suspicious_device",
                    "privilege_use",
                    "post_login_activity",
                },
            )
            if strong:
                status = "evidence_supported"
                reason = "Successful-login context includes stronger account-misuse evidence."
                matched = strong
            else:
                status = "candidate"
                reason = "Successful login after failures observed; Valid Accounts remains candidate pending misuse evidence."

    elif use_case == "edr_powershell_suspicious_command":
        ps_evidence = _present_subset(
            evidence,
            {
                "powershell_command_evidence",
                "script_block_evidence",
                "encoded_command",
                "suspicious_parent_process",
                "download_cradle",
                "endpoint_network_connection",
            },
        )
        if tid in {"T1059", "T1059.001"} and ps_evidence:
            status = "evidence_supported"
            reason = "PowerShell command, script-block, parent-process, encoded-command, or network evidence is present."
            matched = ps_evidence

    elif use_case == "email_phishing_header_review":
        phishing_evidence = _present_subset(
            evidence,
            {
                "email_auth_failure",
                "sender_return_path_mismatch",
                "malicious_url_or_domain",
                "attachment_hash_verdict",
                "mail_gateway_verdict",
            },
        )
        if tid in {"T1566", "T1566.001", "T1566.002"}:
            if _has_strong_phishing_support(phishing_evidence):
                status = "evidence_supported"
                reason = "Email/header investigation has multiple or strong phishing indicators."
                matched = phishing_evidence
            elif phishing_evidence:
                status = "candidate"
                reason = "Single email/header indicator is suspicious but not enough to confirm phishing."
                matched = phishing_evidence

    elif use_case == "dns_beaconing_candidate":
        c2_evidence = _present_subset(
            evidence,
            {
                "periodicity",
                "jitter_profile",
                "repeated_destination",
                "rare_domain",
                "byte_pattern",
                "host_association",
            },
        )
        if tid == "T1071":
            if len(c2_evidence) >= 2:
                status = "evidence_supported"
                reason = "Multiple beaconing signals support application-layer C2 as evidence-supported."
                matched = c2_evidence
            elif c2_evidence:
                status = "candidate"
                reason = "A single beaconing signal is candidate-only; C2 is not confirmed."
                matched = c2_evidence

    elif use_case == "critical_notable_mitre_review":
        alert_evidence = _present_subset(
            evidence,
            {
                "critical_alert_count",
                "hosts_with_critical",
                "mitre_technique",
                "mitre_tactic",
                "urgency",
                "rule_name",
            },
        )
        if tid in {"T1110.001", "T1078", "T1059.001"}:
            if len(alert_evidence) >= 2:
                status = "candidate"
                reason = "Critical-alert fixture carries technique annotations; analyst validation required before supported mapping."
                matched = alert_evidence
            elif alert_evidence:
                status = "candidate"
                reason = "Single alert indicator is candidate-only for MITRE mapping."
                matched = alert_evidence

    elif use_case == "endpoint_ransomware_impact_review":
        ransomware_evidence = _present_subset(
            evidence,
            {
                "file_rename_volume",
                "extension_pattern",
                "encryption_behavior",
                "impacted_paths",
                "process_evidence",
                "shadow_copy_deletion",
                "service_stop",
                "host_spread",
            },
        )
        if tid == "T1486":
            if len(ransomware_evidence) >= 2:
                status = "evidence_supported"
                reason = "Multiple impact/encryption signals support Data Encrypted for Impact."
                matched = ransomware_evidence
            elif ransomware_evidence:
                status = "candidate"
                reason = "A single file or impact signal is not enough to confirm ransomware."
                matched = ransomware_evidence
        elif tid == "T1490" and "shadow_copy_deletion" in evidence:
            status = "evidence_supported"
            reason = "Recovery-inhibition evidence is present."
            matched = {"shadow_copy_deletion"}
        elif tid == "T1489" and "service_stop" in evidence:
            status = "evidence_supported"
            reason = "Service-stop evidence is present."
            matched = {"service_stop"}

    if status == "candidate" and precondition_negated(tid, evidence):
        status = "not_claimed"
        reason = not_claimed_reason(tid)
        matched = set()

    return {
        "status": status,
        "reason": reason,
        "evidence_keys": sorted(matched),
    }


def _present_subset(evidence: set[str], keys: set[str]) -> set[str]:
    return {key for key in keys if key in evidence}


def _first_present(evidence: set[str], keys: set[str]) -> set[str]:
    return _present_subset(evidence, keys)


def _has_strong_phishing_support(keys: set[str]) -> bool:
    if "malicious_url_or_domain" in keys or "attachment_hash_verdict" in keys or "mail_gateway_verdict" in keys:
        return True
    return len(keys) >= 2 and keys != {"sender_return_path_mismatch"}
