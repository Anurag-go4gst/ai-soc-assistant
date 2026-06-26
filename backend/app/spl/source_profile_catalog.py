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
    SourceProfileSlotDefinition("jump_host_index", "Jump-host index", "index", "Bastion / jump-host authentication and session index", "pgcil_soc"),
    SourceProfileSlotDefinition("jump_host_sourcetype", "Jump-host sourcetype", "sourcetype", "Windows/Linux/RDP/SSH jump-host session sourcetype", "pgcil:jump_host"),
    SourceProfileSlotDefinition("pam_index", "PAM index", "index", "Privileged access management session index", "pgcil_soc"),
    SourceProfileSlotDefinition("pam_sourcetype", "PAM sourcetype", "sourcetype", "CyberArk / BeyondTrust / Delinea / session broker sourcetype", "pgcil:pam"),
    SourceProfileSlotDefinition("sysmon_index", "Sysmon index", "index", "Sysmon operational index", "pgcil_soc"),
    SourceProfileSlotDefinition("sysmon_sourcetype", "Sysmon sourcetype", "sourcetype", "Microsoft-Windows-Sysmon sourcetype", "XmlWinEventLog:Microsoft-Windows-Sysmon/Operational"),
    SourceProfileSlotDefinition("cisco_firewall_index", "Cisco firewall index", "cisco_index", "Cisco Firepower / ASA firewall events index", "cisco_firewall"),
    SourceProfileSlotDefinition("cisco_firewall_sourcetype", "Cisco firewall sourcetype", "cisco_sourcetype", "Cisco firewall event sourcetype", "cisco:firepower"),
    SourceProfileSlotDefinition("cisco_ise_index", "Cisco ISE index", "cisco_index", "Cisco ISE / NAC authentication events index", "cisco_ise"),
    SourceProfileSlotDefinition("cisco_ise_sourcetype", "Cisco ISE sourcetype", "cisco_sourcetype", "Cisco ISE authentication/posture sourcetype", "cisco:ise"),
    SourceProfileSlotDefinition("cisco_ios_index", "Cisco IOS index", "cisco_index", "Cisco IOS / Catalyst network device events index", "cisco_ios"),
    SourceProfileSlotDefinition("cisco_ios_sourcetype", "Cisco IOS sourcetype", "cisco_sourcetype", "Cisco IOS syslog sourcetype", "cisco:ios"),
    SourceProfileSlotDefinition("stealthwatch_index", "Stealthwatch index", "cisco_index", "Cisco Stealthwatch / Secure Network Analytics index", "stealthwatch"),
    SourceProfileSlotDefinition("stealthwatch_sourcetype", "Stealthwatch sourcetype", "cisco_sourcetype", "Stealthwatch flow/anomaly sourcetype", "cisco:stealthwatch"),
    SourceProfileSlotDefinition("cisco_tacacs_index", "Cisco TACACS index", "cisco_index", "TACACS+ privilege/session events index", "cisco_tacacs"),
    SourceProfileSlotDefinition("cisco_tacacs_sourcetype", "Cisco TACACS sourcetype", "cisco_sourcetype", "TACACS+ event sourcetype", "cisco:tacacs"),
    SourceProfileSlotDefinition("cisco_wlc_index", "Cisco WLC index", "cisco_index", "Cisco wireless controller / rogue AP events index", "cisco_wlc"),
    SourceProfileSlotDefinition("cisco_wlc_sourcetype", "Cisco WLC sourcetype", "cisco_sourcetype", "Cisco WLC event sourcetype", "cisco:wlc"),
    SourceProfileSlotDefinition("cisco_duo_index", "Cisco Duo index", "cisco_index", "Cisco Duo MFA events index", "cisco_duo"),
    SourceProfileSlotDefinition("cisco_duo_sourcetype", "Cisco Duo sourcetype", "cisco_sourcetype", "Cisco Duo authentication sourcetype", "cisco:duo"),
    SourceProfileSlotDefinition("cisco_amp_index", "Cisco Secure Endpoint index", "cisco_index", "Cisco AMP / Secure Endpoint events index", "cisco_amp"),
    SourceProfileSlotDefinition("cisco_amp_sourcetype", "Cisco Secure Endpoint sourcetype", "cisco_sourcetype", "Cisco Secure Endpoint event sourcetype", "cisco:amp"),
    SourceProfileSlotDefinition("vpn_pool_zone", "VPN pool zone", "zone", "Firewall zone label for corporate Cisco VPN address pools", "CORP_VPN"),
    SourceProfileSlotDefinition("jump_host_zone", "Jump-host zone", "zone", "Firewall zone label for approved bastion / jump-host networks", "I-DMZ"),
    SourceProfileSlotDefinition("scada_core_zone", "Core SCADA zone", "zone", "Firewall zone label for the Core SCADA VLAN", "CORE_SCADA"),
    SourceProfileSlotDefinition("i_dmz_zone", "Industrial DMZ zone", "zone", "Firewall zone label for the Industrial DMZ", "I-DMZ"),
    SourceProfileSlotDefinition("internet_zone", "Internet zone", "zone", "Firewall zone label for public Internet egress", "INTERNET"),
    SourceProfileSlotDefinition("it_corporate_zone", "IT corporate zone", "zone", "Firewall zone label for corporate IT networks", "CORP_IT"),
    SourceProfileSlotDefinition("corporate_cidr", "Corporate CIDR", "network", "Corporate IT network CIDR for boundary hunts", "10.20.0.0/16"),
    SourceProfileSlotDefinition("ot_asset_cidr", "OT asset CIDR", "network", "OT asset network CIDR for OT-scoped hunts", "10.40.0.0/16"),
    SourceProfileSlotDefinition("approved_jump_host_ips", "Approved jump-host IPs", "remote_access", "Comma-separated approved jump-host IPs or CIDRs used for OT access", "10.30.5.10"),
    SourceProfileSlotDefinition("approved_external_systems", "Approved external systems", "remote_access", "Comma-separated approved external vendor/system identifiers", "VendorA,OEM-Remote"),
    SourceProfileSlotDefinition("pam_session_broker", "PAM session broker", "remote_access", "PAM/session-broker platform name used for privileged remote sessions", "CyberArk"),
    SourceProfileSlotDefinition("substation_mapping_lookup", "Substation mapping lookup", "lookup", "Lookup that maps IP/asset identity to substation or OT zone", "ot_asset_inventory.csv"),
    SourceProfileSlotDefinition("external_system_registry_lookup", "External system registry lookup", "lookup", "Lookup of approved external systems and remote access ownership", "external_system_registry.csv"),
    SourceProfileSlotDefinition("approved_modbus_targets_lookup", "Approved Modbus targets lookup", "lookup", "Lookup of approved Modbus/OT destination targets", "approved_modbus_targets.csv"),
    SourceProfileSlotDefinition("approved_ot_destination_cidr", "Approved OT destination CIDR", "network", "Approved OT destination network CIDR for destination anti-join filters", "10.40.0.0/16"),
    SourceProfileSlotDefinition("src_ip_field", "Source IP field", "field_mapping", "Preferred source IP field for network/OT telemetry", "src_ip"),
    SourceProfileSlotDefinition("dest_ip_field", "Destination IP field", "field_mapping", "Preferred destination IP field for network/OT telemetry", "dest_ip"),
    SourceProfileSlotDefinition("function_code_field", "Function code field", "field_mapping", "Preferred Modbus/DNP3 function-code field", "function_code"),
    SourceProfileSlotDefinition("internal_dns_ip", "Internal DNS IPs", "network", "Comma-separated internal DNS/Umbrella resolver IPs", "10.1.2.53,10.1.2.54"),
    SourceProfileSlotDefinition("western_grid_tag", "Western Grid tag", "ot", "Environment label for Western Grid substations", "Western_Grid"),
    SourceProfileSlotDefinition("northern_grid_tag", "Northern Grid tag", "ot", "Environment label for Northern Grid assets", "Northern_Grid"),
    SourceProfileSlotDefinition("sldc_node", "SLDC node", "ot", "State Load Despatch Center node/asset label", "SLDC"),
    SourceProfileSlotDefinition("vendor_maint_start_hour", "Vendor maintenance start hour", "compliance", "Approved OEM vendor maintenance start hour, 0-23", "22"),
    SourceProfileSlotDefinition("vendor_maint_end_hour", "Vendor maintenance end hour", "compliance", "Approved OEM vendor maintenance end hour, 0-23", "5"),
    # OT-protocol lab draft slots (ot_protocol_families.py) — review-only Google-25 hunts.
    SourceProfileSlotDefinition("ot_auth_index", "OT auth index", "ot_index", "Index for OT/SCADA host authentication events", "ot_soc"),
    SourceProfileSlotDefinition("ot_auth_sourcetype", "OT auth sourcetype", "ot_sourcetype", "Sourcetype for OT/SCADA login events", "ot:auth"),
    SourceProfileSlotDefinition("ot_network_index", "OT network index", "ot_index", "Index for OT protocol / SCADA network telemetry", "ot_soc"),
    SourceProfileSlotDefinition("ot_modbus_sourcetype", "OT Modbus sourcetype", "ot_sourcetype", "Sourcetype for Modbus TCP traffic", "ot:modbus"),
    SourceProfileSlotDefinition("ot_dnp3_sourcetype", "OT DNP3 sourcetype", "ot_sourcetype", "Sourcetype for DNP3 traffic", "ot:dnp3"),
    SourceProfileSlotDefinition("ot_scada_sourcetype", "OT SCADA sourcetype", "ot_sourcetype", "Sourcetype for SCADA/RTU/PLC status and control events", "ot:scada"),
    SourceProfileSlotDefinition("ot_pmu_sourcetype", "OT PMU sourcetype", "ot_sourcetype", "Sourcetype for PMU / synchrophasor (C37.118) streams", "ot:pmu"),
    SourceProfileSlotDefinition("ot_asset_index", "OT asset index", "ot_index", "Index for OT asset/meter inventory and firmware telemetry", "ot_soc"),
    SourceProfileSlotDefinition("ot_meter_sourcetype", "OT meter sourcetype", "ot_sourcetype", "Sourcetype for AMI / smart-meter firmware telemetry", "ot:meter"),
    SourceProfileSlotDefinition("ot_firewall_index", "OT firewall index", "ot_index", "Index for OT-DMZ firewall audit/config events", "ot_soc"),
    SourceProfileSlotDefinition("ot_firewall_sourcetype", "OT firewall sourcetype", "ot_sourcetype", "Sourcetype for OT-DMZ firewall policy/rule change events", "ot:firewall"),
)


SOURCE_PROFILE_SLOT_ALIASES: dict[str, str] = {
    # Legacy ESP/firewall draft placeholders. Canonical values are maintained
    # only in Settings -> Environment Knowledge; aliases avoid a parallel
    # hidden binding registry while old lab drafts continue to resolve.
    "esp_firewall_index": "firewall_index",
    "esp_firewall_sourcetype": "firewall_sourcetype",
    "corporate_it_zone": "it_corporate_zone",
    "corporate_it_zone_alt": "it_corporate_zone",
    "corporate_it_cidr": "corporate_cidr",
    "ot_control_center_zone": "scada_core_zone",
    "ot_control_center_zone_alt": "scada_core_zone",
    "ot_control_center_cidr": "ot_asset_cidr",
    "vendor_vpn_zone": "vpn_pool_zone",
    "ot_jump_zone": "jump_host_zone",
    "vpn_auth_sourcetype": "vpn_sourcetype",
    "jump_host_ips": "approved_jump_host_ips",
    "approved_ot_destination_allowlist": "approved_ot_destination_cidr",
    "engineering_workstation_cidr": "corporate_cidr",
}


def canonical_source_profile_slot(slot_id: str) -> str:
    """Return the canonical COE-maintained slot id for a placeholder."""
    key = str(slot_id or "").strip()
    return SOURCE_PROFILE_SLOT_ALIASES.get(key, key)


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
