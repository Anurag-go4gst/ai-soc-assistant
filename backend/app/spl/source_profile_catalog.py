"""Canonical source-profile slot vocabulary for COE UI and SPL placeholder mapping."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceProfileSlotDefinition:
    slot_id: str
    label: str
    category: str
    description: str
    example: str


SOURCE_PROFILE_SLOT_DEFINITIONS: tuple[SourceProfileSlotDefinition, ...] = (
    SourceProfileSlotDefinition("auth_index", "Auth index", "index", "Splunk index for authentication events", "pgcil_soc"),
    SourceProfileSlotDefinition("auth_sourcetype", "Auth sourcetype", "sourcetype", "Sourcetype for login / auth events", "pgcil:auth"),
    SourceProfileSlotDefinition("windows_index", "Windows index", "index", "Windows security / system events index", "pgcil_soc"),
    SourceProfileSlotDefinition("windows_security_sourcetype", "Windows security sourcetype", "sourcetype", "Windows Security log sourcetype", "WinEventLog:Security"),
    SourceProfileSlotDefinition("network_index", "Network index", "index", "Network traffic / flow index", "pgcil_soc"),
    SourceProfileSlotDefinition("network_traffic_sourcetype", "Network traffic sourcetype", "sourcetype", "Firewall / flow sourcetype", "pgcil:network"),
    SourceProfileSlotDefinition("dns_index", "DNS index", "index", "DNS query logs index", "pgcil_soc"),
    SourceProfileSlotDefinition("dns_sourcetype", "DNS sourcetype", "sourcetype", "DNS resolution sourcetype", "pgcil:dns"),
    SourceProfileSlotDefinition("endpoint_index", "Endpoint index", "index", "EDR / endpoint process index", "pgcil_soc"),
    SourceProfileSlotDefinition("endpoint_process_sourcetype", "Endpoint process sourcetype", "sourcetype", "EDR or Sysmon process sourcetype", "pgcil:edr"),
    SourceProfileSlotDefinition("firewall_index", "Firewall index", "index", "Perimeter firewall index", "pgcil_soc"),
    SourceProfileSlotDefinition("firewall_sourcetype", "Firewall sourcetype", "sourcetype", "Firewall deny/allow sourcetype", "pgcil:firewall"),
    SourceProfileSlotDefinition("vpn_index", "VPN index", "index", "VPN concentrator / remote access index", "pgcil_soc"),
    SourceProfileSlotDefinition("vpn_sourcetype", "VPN sourcetype", "sourcetype", "VPN authentication sourcetype", "pgcil:vpn"),
    SourceProfileSlotDefinition("sysmon_index", "Sysmon index", "index", "Sysmon operational index", "pgcil_soc"),
    SourceProfileSlotDefinition("sysmon_sourcetype", "Sysmon sourcetype", "sourcetype", "Microsoft-Windows-Sysmon sourcetype", "XmlWinEventLog:Microsoft-Windows-Sysmon/Operational"),
)


def list_source_profile_slot_definitions() -> list[dict[str, str]]:
    return [
        {
            "slot_id": item.slot_id,
            "label": item.label,
            "category": item.category,
            "description": item.description,
            "example": item.example,
        }
        for item in SOURCE_PROFILE_SLOT_DEFINITIONS
    ]
