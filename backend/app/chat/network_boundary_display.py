"""Analyst-facing labels and checklists for firewall / IT-OT boundary questions."""

from __future__ import annotations

import re

NETWORK_USE_CASE_DISPLAY: dict[str, str] = {
    "ot_it_to_ot_auth_anomaly": "IT-to-OT network boundary traffic review",
}

FIREWALL_BOUNDARY_CHECKLIST: tuple[str, ...] = (
    "Confirm approved corporate IT and OT zone labels or CIDR ranges.",
    "Identify source IT hosts and destination OT/control-room assets.",
    "Review firewall rule name, action, app, protocol, destination port, and session state.",
    "Compare traffic with approved change or maintenance window.",
    "Escalate if traffic is unauthorized, recurring, high-volume, or targets critical OT assets.",
    "Do not declare compromise from firewall traffic alone.",
)

ESTABLISHED_TRAFFIC_SCOPE_NOTICE = (
    "This draft is scoped to allowed/established traffic. If you want all attempts, including "
    "denied/blocked traffic, remove or adjust the action/session-state filters during SOC review."
)

DENIED_TRAFFIC_SCOPE_NOTICE = (
    "This draft is scoped to denied/blocked/dropped OT egress traffic. Allowed or established "
    "sessions are excluded unless you adjust action filters during SOC review."
)


# Terms that establish a network-boundary context on their own.
_BOUNDARY_CONTEXT_TERMS: tuple[str, ...] = (
    "firewall",
    "ot vlan",
    "control room",
    "it-to-ot",
    "it to ot",
    "corporate it",
    "corporate to ot",
    "ot network",
    "ot segment",
    "scada",
    "substation",
    "electronic security perimeter",
    "vendor vpn",
    "jump server",
    "zone",
    "vlan",
    "segment",
    "boundary",
)

# Bare OT/ESP word mentions also establish boundary context ("denied traffic
# from OT to the internet"); \b keeps "most"/"hosts" from matching "ot".
_BOUNDARY_WORD_RE = re.compile(r"\b(?:ot|esp)\b")

_ANALYTICS_RANK_RE = re.compile(r"\b(?:most|top|highest|largest|busiest)\b")


def is_firewall_boundary_query(user_query: str) -> bool:
    """Boundary review requires boundary context; protocol-only phrases such as
    bare "SMB traffic" or "RDP traffic" no longer imply an IT-to-OT review."""
    normalized = " ".join((user_query or "").lower().split())
    if any(term in normalized for term in _BOUNDARY_CONTEXT_TERMS):
        return True
    return bool(_BOUNDARY_WORD_RE.search(normalized))


def analytics_traffic_label(user_query: str) -> str | None:
    """Display label for ranking/analytics traffic questions without boundary context."""
    normalized = " ".join((user_query or "").lower().split())
    if not normalized or is_firewall_boundary_query(normalized):
        return None
    if not _ANALYTICS_RANK_RE.search(normalized):
        return None
    if "smb" in normalized:
        return "SMB traffic analytics"
    if any(
        term in normalized
        for term in ("traffic", "talker", "bytes", "upload", "download", "connection", "dns quer")
    ):
        return "Network traffic analytics"
    return None


def resolve_analyst_use_case_label(
    *,
    use_case_id: str | None,
    catalog_label: str | None,
    user_query: str,
) -> str | None:
    if use_case_id and use_case_id in NETWORK_USE_CASE_DISPLAY:
        return NETWORK_USE_CASE_DISPLAY[use_case_id]
    if catalog_label and _contains_auth_anomaly_label(catalog_label) and is_firewall_boundary_query(user_query):
        return _infer_boundary_label(user_query)
    if is_firewall_boundary_query(user_query):
        return _infer_boundary_label(user_query)
    if not catalog_label:
        return analytics_traffic_label(user_query)
    return catalog_label


def scrub_auth_anomaly_display_text(text: str | None, *, user_query: str) -> str | None:
    if not isinstance(text, str) or not text.strip():
        return text
    if not _contains_auth_anomaly_label(text) and not is_firewall_boundary_query(user_query):
        return text
    if _contains_auth_anomaly_label(text):
        return _infer_boundary_label(user_query)
    return text


def _contains_auth_anomaly_label(text: str) -> bool:
    lowered = text.lower()
    return "authentication anomaly" in lowered or "auth anomaly" in lowered


def _infer_boundary_label(user_query: str) -> str:
    normalized = " ".join((user_query or "").lower().split())
    if "vendor vpn" in normalized and "jump" in normalized:
        return "Vendor VPN to OT jump-server access review"
    if any(term in normalized for term in ("denied", "blocked", "egress")) and "ot" in normalized:
        return "OT egress firewall review"
    if "smb" in normalized and "ot" in normalized:
        return "OT segmentation policy review"
    if "rdp" in normalized:
        return "IT-to-OT firewall traffic review"
    if "vlan" in normalized:
        return "OT firewall boundary review"
    return "IT-to-OT network boundary traffic review"
