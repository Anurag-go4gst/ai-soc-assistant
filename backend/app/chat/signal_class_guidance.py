"""Entity-aware signal-class guided generator for T2 hunts (WS-1)."""

from __future__ import annotations

import re
from typing import Any, Literal

from app.config import settings

SignalClass = Literal[
    "protocol_command",
    "timing_integrity",
    "identity_anomaly",
    "change_management",
    "removable_media",
    "egress_exfil",
    "recon_scan",
    "network_beacon",
    "wireless_physical",
    "process_aware_ot",
    "unknown",
]

_OT_PROTOCOL_TERMS: tuple[tuple[str, SignalClass], ...] = (
    ("dnp3", "protocol_command"),
    ("modbus", "protocol_command"),
    ("iec-104", "protocol_command"),
    ("iec 104", "protocol_command"),
    ("iec-61850", "protocol_command"),
    ("iec 61850", "protocol_command"),
    ("goose", "protocol_command"),
    ("modbus tcp", "protocol_command"),
    ("connection churn", "protocol_command"),
    ("firmware push", "change_management"),
    ("synchrophasor", "process_aware_ot"),
    ("mms", "protocol_command"),
    ("opc", "protocol_command"),
    ("unsolicited", "protocol_command"),
    ("register write", "protocol_command"),
    ("function code", "protocol_command"),
    ("ntp", "timing_integrity"),
    ("irig-b", "timing_integrity"),
    ("irig b", "timing_integrity"),
    ("time sync", "timing_integrity"),
    ("clock drift", "timing_integrity"),
    ("gps", "timing_integrity"),
    ("off-shift", "identity_anomaly"),
    ("impossible travel", "identity_anomaly"),
    ("operator login", "identity_anomaly"),
    ("sldc", "identity_anomaly"),
    ("remote access", "identity_anomaly"),
    ("external connection", "identity_anomaly"),
    ("external connections", "identity_anomaly"),
    ("vpn session", "identity_anomaly"),
    ("substation network", "identity_anomaly"),
    ("bastion", "identity_anomaly"),
    ("jump host", "identity_anomaly"),
    ("remote desktop", "identity_anomaly"),
    ("rdp session", "identity_anomaly"),
    ("firmware", "change_management"),
    ("config push", "change_management"),
    ("relay", "change_management"),
    ("off-window", "change_management"),
    ("maintenance window", "change_management"),
    ("usb", "removable_media"),
    ("removable media", "removable_media"),
    ("data diode", "egress_exfil"),
    ("diode", "egress_exfil"),
    ("egress", "egress_exfil"),
    ("exfil", "egress_exfil"),
    ("port 502", "recon_scan"),
    ("port scan", "recon_scan"),
    ("recon", "recon_scan"),
    ("beacon", "network_beacon"),
    ("chatter", "network_beacon"),
    ("new external", "network_beacon"),
    ("overnight", "network_beacon"),
    ("wireless", "wireless_physical"),
    ("rogue ap", "wireless_physical"),
    ("access point", "wireless_physical"),
    ("agc", "process_aware_ot"),
    ("frequency band", "process_aware_ot"),
    ("setpoint", "process_aware_ot"),
    ("pmu", "process_aware_ot"),
    ("pdc", "process_aware_ot"),
)

_CLASS_DETECTORS: tuple[tuple[SignalClass, re.Pattern[str]], ...] = (
    ("protocol_command", re.compile(r"\b(dnp3|modbus(?:\s+tcp)?|iec[\s-]?61850|iec[\s-]?104|goose|mms|opc|unsolicited|function code|register write|connection churn)\b", re.I)),
    ("timing_integrity", re.compile(r"\b(ntp|irig[\s-]?b|time[\s-]?sync|clock|gps|stratum)\b", re.I)),
    ("identity_anomaly", re.compile(r"\b(impossible travel|off[\s-]?shift|operator login|sldc|privileged user|remote access|external connections?|vpn sessions?|bastion|jump hosts?|remote desktop|rdp sessions?)\b", re.I)),
    ("change_management", re.compile(r"\b(firmware|config push|relay|off[\s-]?window|maintenance window|change ticket)\b", re.I)),
    ("removable_media", re.compile(r"\b(usb|removable media|6416|media control)\b", re.I)),
    ("egress_exfil", re.compile(r"\b(data diode|diode|egress|exfil|bytes out)\b", re.I)),
    ("recon_scan", re.compile(r"\b(port[\s-]?502|port scan|recon|scan)\b", re.I)),
    ("network_beacon", re.compile(r"\b(beacon|chatter|new external|overnight|dns)\b", re.I)),
    ("wireless_physical", re.compile(r"\b(wireless|rogue ap|access point|wifi)\b", re.I)),
    ("process_aware_ot", re.compile(r"\b(agc|frequency band|setpoint|grid operations|pmu|pdc)\b", re.I)),
)

_TEMPLATES: dict[SignalClass, dict[str, list[str]]] = {
    "protocol_command": {
        "hypotheses": [
            "Approved engineering or vendor maintenance command.",
            "Misconfigured master/slave polling or unsolicited response storm.",
            "Unauthorized write or function-code abuse on OT field gear.",
        ],
        "evidence": [
            "OT protocol logs: function code, register/object, source master, response timing.",
            "Engineering workstation and HMI session context for the same window.",
            "Change tickets and maintenance approvals for the affected RTU/PLC/relay.",
            "Peer asset comparison for command volume and first-seen masters.",
        ],
    },
    "timing_integrity": {
        "hypotheses": [
            "Planned NTP/IRIG-B source change or GPS antenna maintenance.",
            "Stratum drift or leap-second handling on a subset of clocks.",
            "Deliberate or accidental time-source tamper affecting OT sequencing.",
        ],
        "evidence": [
            "NTP/IRIG-B/PTP source health, stratum, and peer-offset logs.",
            "Cross-device timestamp skew on SCADA historians and relays.",
            "GPS/antenna alarms and recent configuration pushes to time appliances.",
            "Correlate security events only after clock integrity is established.",
        ],
    },
    "identity_anomaly": {
        "hypotheses": [
            "Shift roster change or shared operator credential use.",
            "VPN/geo anomaly on a legitimate remote operator.",
            "Compromised identity requiring session and device corroboration.",
        ],
        "evidence": [
            "Auth/VPN logs: user, source IP/geo, MFA result, device posture.",
            "Shift roster, badge/access, and HR-approved remote access records.",
            "OT session logs tied to the same user and observation window.",
            "Peer comparison of login times for the role/substation.",
        ],
    },
    "change_management": {
        "hypotheses": [
            "Approved firmware or relay configuration push in-window.",
            "Emergency restoration change outside the normal maintenance window.",
            "Unauthorized config/firmware change without ticket alignment.",
        ],
        "evidence": [
            "Change tickets: approver, window, asset list, rollback plan.",
            "Relay/IED config export diffs and firmware version before/after.",
            "Engineering workstation file-transfer and vendor tool logs.",
            "SCADA alarm history for config-download events.",
        ],
    },
    "removable_media": {
        "hypotheses": [
            "Authorized maintenance media use on an OT jump host.",
            "Policy gap allowing USB on a bridge host in a segmented zone.",
            "Malicious media introduction requiring endpoint corroboration.",
        ],
        "evidence": [
            "USB/media-control policy and exceptions for the site.",
            "Windows 6416 / EDR removable-media events on jump hosts.",
            "File-create/execution telemetry following media insert.",
            "Physical access logs for the same window.",
        ],
    },
    "egress_exfil": {
        "hypotheses": [
            "Expected historian or backup replication across the diode.",
            "Misrouted OT flow violating one-way policy.",
            "Covert exfiltration requiring byte-volume and destination corroboration.",
        ],
        "evidence": [
            "Diode/policy direction: allowed destinations and protocols.",
            "Firewall/session bytes, duration, and first/last seen for OT sources.",
            "DNS/proxy context where the architecture permits.",
            "Asset function and data-classification for the source OT system.",
        ],
    },
    "recon_scan": {
        "hypotheses": [
            "Vendor or asset-discovery scan during maintenance.",
            "Misconfigured monitoring hitting OT protocol ports.",
            "Internal reconnaissance preceding exploitation (candidate only).",
        ],
        "evidence": [
            "Fan-out: distinct destinations/ports from the source host.",
            "First-seen scan patterns vs baseline for the VLAN/zone.",
            "Endpoint/process context initiating the scan.",
            "Honesty: a port sweep alone does not confirm intrusion.",
        ],
    },
    "network_beacon": {
        "hypotheses": [
            "Approved vendor or maintenance communication changed.",
            "A configuration or routing change introduced a new destination.",
            "An OT asset is beaconing or transferring data unexpectedly.",
        ],
        "evidence": [
            "Firewall sessions: source asset, destination, port, bytes, duration, first/last seen.",
            "DNS/proxy context: resolved name, category, reputation, and peer hosts.",
            "OT inventory and change records: owner, function, maintenance window, vendor access.",
            "Endpoint telemetry where available: initiating process, user, and parent process.",
        ],
    },
    "wireless_physical": {
        "hypotheses": [
            "Authorized temporary wireless bridge for maintenance.",
            "Rogue AP or physical-layer bridge bypassing segmentation.",
            "Misidentified corporate SSID bleed into OT physical space.",
        ],
        "evidence": [
            "Wireless controller logs: SSID, BSSID, client, signal, location.",
            "Physical walk-down and approved maintenance wireless permits.",
            "Switch port/MAC tables for unexpected wireless uplinks.",
            "Correlate with OT traffic only after the RF path is confirmed.",
        ],
    },
    "process_aware_ot": {
        "hypotheses": [
            "Normal grid regulation or dispatch action within expected bands.",
            "Mis-tuned control loop or sensor drift mimicking attack.",
            "Unauthorized setpoint change requiring engineering corroboration.",
        ],
        "evidence": [
            "AGC/frequency/PMU/PDC telemetry vs operations shift notes.",
            "Relay/event files and SCADA setpoint change history.",
            "Grid operations approval for the observation window.",
            "Defer impact conclusions to grid operators; security overlay only.",
        ],
    },
}


def extract_ot_terms(query: str) -> list[str]:
    normalized = query.lower()
    found: list[str] = []
    for term, _ in _OT_PROTOCOL_TERMS:
        if term in normalized and term not in found:
            found.append(term)
    return found


def classify_signal_class(query: str, entities: dict[str, Any] | None = None) -> SignalClass:
    """Deterministic signal-class classifier over query + entities."""
    from app.chat.query_signals import is_cve_focus_query

    if is_cve_focus_query(query):
        return "unknown"
    normalized = " ".join(query.lower().split())
    entity_text = " ".join(
        str(item)
        for key in ("asset", "host", "user", "event_type", "zone_labels", "port_numbers")
        for item in ((entities or {}).get(key) or [])
    ).lower()
    combined = f"{normalized} {entity_text}".strip()
    for term, signal_class in _OT_PROTOCOL_TERMS:
        if term in combined:
            return signal_class
    for signal_class, pattern in _CLASS_DETECTORS:
        if pattern.search(combined):
            return signal_class
    if any(term in normalized for term in ("ot", "scada", "plc", "substation")):
        access_markers = (
            "remote",
            "access",
            "session",
            "login",
            "vpn",
            "bastion",
            "jump",
            "rdp",
            "desktop",
            "vendor",
            "credential",
            "external",
        )
        if any(marker in normalized for marker in access_markers):
            return "identity_anomaly"
        return "network_beacon"
    return "unknown"


def build_signal_class_guidance(query: str, entities: dict[str, Any] | None = None) -> str:
    """Shaped hypotheses + evidence for the resolved signal class."""
    signal_class = classify_signal_class(query, entities)
    template = _TEMPLATES.get(signal_class)
    ot_terms = extract_ot_terms(query)
    term_line = f"Detected OT/protocol signals: {', '.join(ot_terms)}.\n\n" if ot_terms else ""
    if template is None:
        return (
            "Guided investigation (review-only)\n\n"
            f"{term_line}"
            "No specialised OT family is mapped for this signal yet — using a generic hunt skeleton.\n\n"
            "Hypotheses\n- Expected operational activity or a recent approved change.\n"
            "- Telemetry drift producing an apparent anomaly.\n"
            "- Suspicious activity requiring corroboration across independent sources.\n\n"
            "Evidence to collect\n- Relevant OT/IT logs for a bounded time window.\n"
            "- Asset ownership, criticality, baseline, and recent change history.\n"
            "- Peer comparison and first-seen analysis.\n\n"
            "Limitations: no live query was run; no MITRE technique or severity is claimed."
        )
    hypotheses = template["hypotheses"]
    evidence = template["evidence"]
    entity_hosts = list((entities or {}).get("host") or (entities or {}).get("asset") or [])
    if entity_hosts:
        evidence = [*evidence, f"Scope to named assets/hosts: {', '.join(entity_hosts[:5])}."]
    return (
        f"Guided investigation — signal class: {signal_class.replace('_', ' ')} (review-only)\n\n"
        f"{term_line}"
        "Hypotheses\n- "
        + "\n- ".join(hypotheses)
        + "\n\nEvidence to collect\n- "
        + "\n- ".join(evidence)
        + "\n\nNext steps\n- Validate scope and time window.\n- Check existing detections and local playbooks."
        "\n- Corroborate before severity, MITRE, escalation, or response coordination decisions."
        "\n\nLimitations: no live query was run; no MITRE technique or incident severity is claimed."
    )
