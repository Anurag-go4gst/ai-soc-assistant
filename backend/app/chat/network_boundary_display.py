"""Analyst-facing labels and checklists for firewall / IT-OT boundary questions."""

from __future__ import annotations

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


def is_firewall_boundary_query(user_query: str) -> bool:
    normalized = " ".join((user_query or "").lower().split())
    return any(
        term in normalized
        for term in (
            "firewall",
            "ot vlan",
            "control room",
            "it-to-ot",
            "it to ot",
            "corporate it",
            "ot network",
            "ot segment",
            "scada",
            "substation",
            "electronic security perimeter",
            "vendor vpn",
            "jump server",
            "denied traffic",
            "rdp traffic",
            "smb traffic",
        )
    )


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
