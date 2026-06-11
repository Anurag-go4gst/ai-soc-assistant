"""Lab-only SPL draft preview — deterministic patterns, never governed or executable."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.chat.network_boundary_display import (
    DENIED_TRAFFIC_SCOPE_NOTICE,
    ESTABLISHED_TRAFFIC_SCOPE_NOTICE,
    FIREWALL_BOUNDARY_CHECKLIST,
)
from app.config import settings
from app.safeguards.spl_validator import validate_spl
from app.spl.draft_quality import STANDARD_ID, evaluate_draft_quality

_FIREWALL_LOG_FIELDS: tuple[str, ...] = (
    "index",
    "sourcetype",
    "src_zone",
    "dest_zone",
    "src_ip",
    "dest_ip",
    "action",
    "session_state",
    "connection_state",
    "protocol",
    "dest_port",
    "rule",
    "_time",
)
_FIREWALL_PROFILE_FIELDS: tuple[str, ...] = (
    "corporate_it_zone",
    "ot_control_center_zone",
    "corporate_it_cidr",
    "ot_control_center_cidr",
)

DRAFT_WARNING = (
    "Lab-only draft SPL preview. Not governed, not approved, not executed. "
    "HIL/SOC review is required before any future execution path."
)
DRAFT_PREVIEW_STATUS_MESSAGE = DRAFT_WARNING
DRAFT_PREVIEW_FORBIDDEN_PHRASES: tuple[str, ...] = (
    "spl does not require review",
    "does not require review",
    "no spl analysis has been conducted",
    "no spl analysis",
    "hil is not required",
    "hil analysis is not necessary",
    "no human intelligence",
    "analysis is not necessary",
    "spl is not required",
)
DRAFT_STATUS = "draft_preview_not_governed"
DRAFT_SOURCE = "deterministic_pattern"

# Null-safe byte total used in analytics drafts (avoids null()+number null arithmetic).
_BYTES_TOTAL_EXPR = "coalesce(bytes, coalesce(bytes_out,0)+coalesce(bytes_in,0), 0)"

# Analyst-facing labels for common draft families (presentation only; no authority change).
FAMILY_PRESENTATION: dict[str, dict[str, str]] = {
    "network_smb_top_talkers": {
        "title": "SMB top talkers — network analytics",
        "review_type": "analytics_review",
        "review_type_display": "Analytics review — lab draft SPL, not executed",
    },
    "esp_it_to_ot_connection": {
        "title": "IT-to-OT firewall boundary review",
        "review_type": "investigation_review",
        "review_type_display": "Investigation review — lab draft SPL, source profile required, not executed",
    },
    "vpn_new_country_login": {
        "title": "VPN login from unseen country",
        "review_type": "investigation_review",
        "review_type_display": "Investigation review — lab draft SPL, VPN source profile required, not executed",
    },
    "auth_success_after_failure": {
        "title": "Success-after-failure authentication correlation",
        "review_type": "investigation_review",
        "review_type_display": "Investigation review — lab draft SPL, auth source profile required, not executed",
    },
    "auth_failed_login_threshold": {
        "title": "Failed-login threshold hunt",
        "review_type": "investigation_review",
        "review_type_display": "Investigation review — lab draft SPL, not executed",
    },
    "dns_beaconing_hunt": {
        "title": "DNS beaconing / high-volume query hunt",
        "review_type": "investigation_review",
        "review_type_display": "Investigation review — lab draft SPL, DNS source profile required, not executed",
    },
    "endpoint_powershell_suspicious": {
        "title": "Suspicious PowerShell activity hunt",
        "review_type": "investigation_review",
        "review_type_display": "Investigation review — lab draft SPL, endpoint source profile required, not executed",
    },
    "windows_identity_privileged_activity": {
        "title": "Privileged identity activity hunt",
        "review_type": "investigation_review",
        "review_type_display": "Investigation review — lab draft SPL, not executed",
    },
    "windows_privileged_group_changes": {
        "title": "Privileged group membership changes",
        "review_type": "investigation_review",
        "review_type_display": "Investigation review — lab draft SPL, not executed",
    },
}


def family_presentation(family_id: str) -> dict[str, str]:
    """Return analyst-facing title/review labels for a detection family."""
    default = {
        "title": family_id.replace("_", " ").replace("-", " ").title(),
        "review_type": "lab_draft",
        "review_type_display": "Lab draft preview — not governed, not executed",
    }
    return {**default, **FAMILY_PRESENTATION.get(family_id, {})}


@dataclass(frozen=True)
class DetectionFamily:
    family_id: str
    patterns: tuple[re.Pattern[str], ...]
    draft_spl: str
    assumptions: tuple[str, ...]
    required_log_fields: tuple[str, ...]
    required_source_profile_fields: tuple[str, ...] = ()
    investigation_checklist: tuple[str, ...] = ()
    scope_notice: str | None = None

    @property
    def required_source_fields(self) -> tuple[str, ...]:
        """Backward-compatible union for callers expecting a single list."""
        return self.required_log_fields + self.required_source_profile_fields


def _family(
    family_id: str,
    *,
    pattern_texts: tuple[str, ...],
    draft_spl: str,
    assumptions: tuple[str, ...],
    required_log_fields: tuple[str, ...],
    required_source_profile_fields: tuple[str, ...] = (),
    investigation_checklist: tuple[str, ...] = (),
    scope_notice: str | None = None,
) -> DetectionFamily:
    return DetectionFamily(
        family_id=family_id,
        patterns=tuple(re.compile(text, re.IGNORECASE) for text in pattern_texts),
        draft_spl=draft_spl.strip(),
        assumptions=assumptions,
        required_log_fields=required_log_fields,
        required_source_profile_fields=required_source_profile_fields,
        investigation_checklist=investigation_checklist,
        scope_notice=scope_notice,
    )


DETECTION_FAMILIES: tuple[DetectionFamily, ...] = (
    _family(
        "windows_privileged_group_changes",
        pattern_texts=(
            r"privileged\s+group",
            r"domain\s+admins?",
            r"enterprise\s+admins?",
            r"\b4728\b",
            r"\b4732\b",
            r"\b4756\b",
            r"added?\s+(?:someone|a\s+user|to)\b.*\bgroup",
        ),
        draft_spl="""
search index=<windows_index> sourcetype=<windows_security_sourcetype> earliest=-7d latest=now
  (EventCode=4728 OR EventCode=4732 OR EventCode=4756) *admin*
| eval group_norm=lower(coalesce(TargetUserName, group_name, group, Group_Name, ""))
| eval actor_norm=lower(coalesce(SubjectUserName, user, Account_Name, ""))
| eval added_user_norm=lower(coalesce(MemberName, member, Target_Account_Name, ""))
| where (
    like(group_norm, "%domain admins%")
    OR like(group_norm, "%enterprise admins%")
    OR like(group_norm, "%administrators%")
    OR like(group_norm, "%privileged%")
    OR like(group_norm, "%admin%")
  )
  AND NOT like(actor_norm, "%$")
| stats count as add_count values(added_user_norm) as added_users earliest(_time) as first_seen_epoch latest(_time) as last_seen_epoch by actor_norm added_user_norm group_norm
| eval first_seen=strftime(first_seen_epoch, "%Y-%m-%d %H:%M:%S")
| eval last_seen=strftime(last_seen_epoch, "%Y-%m-%d %H:%M:%S")
| fields - first_seen_epoch last_seen_epoch
| where add_count>3
| table actor_norm added_user_norm group_norm add_count added_users first_seen last_seen
| sort - add_count
| head 100
""",
        assumptions=(
            "Windows Security EventCodes 4728/4732/4756 represent global/universal/local group member additions.",
            "Shift-left EventCode filter in base search; optional *admin* keyword is broad only.",
            "Privileged groups matched after group_norm coalesce(); machine accounts suppressed via NOT like(actor_norm, \"%$\").",
            "Threshold of more than 3 additions in 7 days is illustrative; tune per environment.",
            "Index and sourcetype are placeholders — confirm against your Windows security log source profile.",
        ),
        required_log_fields=(
            "index",
            "sourcetype",
            "EventCode",
            "SubjectUserName",
            "MemberName",
            "TargetUserName",
            "_time",
        ),
    ),
    _family(
        "windows_account_lockout",
        pattern_texts=(
            r"\b4740\b",
            r"account\s+lockout",
            r"lockout\s+events?",
        ),
        draft_spl="""
search index=<windows_index> sourcetype=<windows_security_sourcetype> earliest=-24h latest=now EventCode=4740
| eval target_user_norm=lower(coalesce(TargetUserName, user, target_user_name, Account_Name, "unknown"))
| eval caller_host_norm=lower(coalesce(Caller_Computer_Name, CallerComputerName, caller_computer_name, src_nt_host, Workstation_Name, "unknown"))
| stats count as lockout_count values(caller_host_norm) as caller_hosts earliest(_time) as first_seen_epoch latest(_time) as last_seen_epoch by target_user_norm
| eval first_seen=strftime(first_seen_epoch, "%Y-%m-%d %H:%M:%S")
| eval last_seen=strftime(last_seen_epoch, "%Y-%m-%d %H:%M:%S")
| fields - first_seen_epoch last_seen_epoch
| table target_user_norm lockout_count caller_hosts first_seen last_seen
| sort - lockout_count
| head 100
""",
        assumptions=(
            "EventCode 4740 indicates a user account was locked out.",
            "caller_host_norm uses Caller_Computer_Name/CallerComputerName forensic fields — not ComputerName alone (may be DC/collector).",
            "earliest(_time)/latest(_time) preserved in stats; readable strftime only at presentation.",
            "Index and sourcetype are placeholders — confirm against your Windows security log source profile.",
        ),
        required_log_fields=(
            "index",
            "sourcetype",
            "EventCode",
            "TargetUserName",
            "Caller_Computer_Name",
            "CallerComputerName",
            "Workstation_Name",
            "_time",
        ),
    ),
    _family(
        "sysmon_web_shell_spawn",
        pattern_texts=(
            r"sysmon",
            r"w3wp\.exe",
            r"apache\.exe",
            r"web\s+server",
            r"cmd\.exe",
            r"powershell\.exe",
        ),
        draft_spl="""
search index=<endpoint_index> sourcetype=XmlWinEventLog:Microsoft-Windows-Sysmon/Operational earliest=-24h latest=now EventCode=1
| eval parent_image_norm=lower(coalesce(ParentImage, ParentProcessName, parent_process_path, ""))
| eval child_image_norm=lower(coalesce(Image, ProcessName, process_path, ""))
| eval command_line_norm=coalesce(CommandLine, process_command_line, cmdline, "")
| eval host=coalesce(Computer, host, dest, "")
| eval user=coalesce(User, user, user_name, "")
| where (
    like(parent_image_norm, "%\\\\w3wp.exe")
    OR like(parent_image_norm, "%\\\\apache.exe")
    OR like(parent_image_norm, "%\\\\httpd.exe")
    OR like(parent_image_norm, "%\\\\tomcat.exe")
    OR like(parent_image_norm, "%\\\\nginx.exe")
  )
  AND (
    like(child_image_norm, "%\\\\cmd.exe")
    OR like(child_image_norm, "%\\\\powershell.exe")
    OR like(child_image_norm, "%\\\\pwsh.exe")
  )
| sort 0 - _time
| eval spawn_time=strftime(_time, "%Y-%m-%d %H:%M:%S")
| table spawn_time host user parent_image_norm child_image_norm command_line_norm
| head 100
""",
        assumptions=(
            "Sysmon EventCode 1 (Process Create) is used for parent/child process lineage.",
            "Web server parents include w3wp.exe, apache.exe, httpd.exe, tomcat.exe, and nginx.exe.",
            "Shell children include cmd.exe, powershell.exe, and pwsh.exe; paths use escaped backslashes with like().",
            "Sorted by native _time; spawn_time strftime added before table presentation only.",
            "Index and sourcetype are placeholders — confirm Sysmon collection in your environment.",
        ),
        required_log_fields=(
            "index",
            "sourcetype",
            "EventCode",
            "ParentImage",
            "Image",
            "CommandLine",
            "Computer",
            "User",
            "_time",
        ),
    ),
    _family(
        "scada_dnp3_modbus_write",
        pattern_texts=(
            r"scada",
            r"\bdnp3\b",
            r"\bmodbus\b",
            r"plc",
            r"substation",
            r"write|modify",
        ),
        draft_spl="""
search index=<scada_firewall_index> sourcetype=<scada_firewall_sourcetype> earliest=-24h latest=now (*dnp3* OR *modbus*)
| eval protocol_norm=lower(coalesce(protocol, proto, protocol_name, ""))
| eval command_norm=lower(coalesce(action, command, event_action, function, function_code, ""))
| eval src_ip_norm=coalesce(src_ip, src, source, source_ip, "")
| eval dest_ip_norm=coalesce(dest_ip, dest, destination, dest_ip, "")
| where (
    like(protocol_norm, "%dnp3%")
    OR like(protocol_norm, "%modbus%")
  )
  AND (
    like(command_norm, "%write%")
    OR like(command_norm, "%modify%")
    OR like(command_norm, "%control%")
  )
  AND NOT cidrmatch("<engineering_workstation_cidr>", src_ip_norm)
| sort 0 - _time
| eval event_time_readable=strftime(_time, "%Y-%m-%d %H:%M:%S")
| table event_time_readable src_ip_norm dest_ip_norm protocol_norm command_norm dest_port payload_summary
| head 100
""",
        assumptions=(
            "SCADA firewall logs expose protocol, action/function, and source/destination IPs.",
            "Shift-left (*dnp3* OR *modbus*) in base search; write/modify/control narrowed after coalesce().",
            "Engineering workstation allowlist uses cidrmatch() with placeholder CIDR — do not invent real CIDRs.",
            "Field names vary by firewall vendor — map DNP3/Modbus write/modify semantics during review.",
        ),
        required_log_fields=(
            "index",
            "sourcetype",
            "src_ip",
            "dest_ip",
            "protocol",
            "action",
            "_time",
        ),
    ),
    _family(
        "firewall_ot_egress_denied",
        pattern_texts=(
            r"denied\s+traffic",
            r"blocked\s+traffic",
            r"denied.*\bot\b",
            r"\bot\b.*internet",
            r"egress.*\bot\b",
        ),
        draft_spl="""
search index=<ot_firewall_index> sourcetype=<ot_firewall_sourcetype> earliest=-24h latest=now (action=denied OR action=blocked OR action=drop OR action=reject)
| eval src_zone_norm=lower(coalesce(src_zone, source_zone, zone_src, ""))
| eval dest_zone_norm=lower(coalesce(dest_zone, destination_zone, zone_dest, ""))
| eval src_ip_norm=coalesce(src_ip, src, source, "")
| eval dest_ip_norm=coalesce(dest_ip, dest, destination, "")
| eval action_norm=lower(coalesce(action, status, result, disposition, ""))
| eval protocol_norm=lower(coalesce(protocol, proto, protocol_name, transport, ""))
| eval dest_port_norm=coalesce(dest_port, destination_port, dport, "")
| eval rule_norm=coalesce(rule, rule_name, policy_name, "")
| where (
    src_zone_norm IN ("<ot_zone>", "<ot_zone_alt>")
    OR cidrmatch("<ot_asset_cidr>", src_ip_norm)
  )
  AND (
    dest_zone_norm IN ("<internet_zone>", "untrust", "external")
    OR NOT cidrmatch("<ot_asset_cidr>", dest_ip_norm)
  )
| stats
    count as denied_count
    values(src_zone_norm) as src_zones
    values(dest_zone_norm) as dest_zones
    values(rule_norm) as firewall_rules
    values(protocol_norm) as protocols
    values(dest_port_norm) as dest_ports
    values(action_norm) as actions
    earliest(_time) as first_seen_epoch
    latest(_time) as last_seen_epoch
    by src_ip_norm dest_ip_norm
| eval first_seen=strftime(first_seen_epoch, "%Y-%m-%d %H:%M:%S")
| eval last_seen=strftime(last_seen_epoch, "%Y-%m-%d %H:%M:%S")
| fields - first_seen_epoch last_seen_epoch
| table src_ip_norm dest_ip_norm src_zones dest_zones firewall_rules protocols dest_ports actions denied_count first_seen last_seen
| sort - denied_count
| head 100
""",
        assumptions=(
            "Shift-left denied/blocked/drop/reject actions in base search; no established-session filter for denied egress review.",
            "OT source zones/CIDR placeholders must be confirmed from your OT firewall source profile.",
            "Internet/untrust destination zones vary by vendor — map dest_zone or external CIDR during review.",
        ),
        required_log_fields=_FIREWALL_LOG_FIELDS,
        required_source_profile_fields=("ot_zone", "ot_asset_cidr", "internet_zone"),
        investigation_checklist=FIREWALL_BOUNDARY_CHECKLIST,
        scope_notice=DENIED_TRAFFIC_SCOPE_NOTICE,
    ),
    _family(
        "firewall_vendor_vpn_jump",
        pattern_texts=(
            r"vendor\s+vpn",
            r"jump\s+server",
            r"vpn.*\bot\b",
        ),
        draft_spl="""
search index=<esp_firewall_index> sourcetype=<esp_firewall_sourcetype> earliest=-24h latest=now (action=allowed OR action=accept OR action=permit OR action=success)
| eval src_zone_norm=lower(coalesce(src_zone, source_zone, zone_src, ""))
| eval dest_zone_norm=lower(coalesce(dest_zone, destination_zone, zone_dest, ""))
| eval src_ip_norm=coalesce(src_ip, src, source, "")
| eval dest_ip_norm=coalesce(dest_ip, dest, destination, "")
| eval action_norm=lower(coalesce(action, status, result, disposition, ""))
| eval session_state_norm=lower(coalesce(session_state, connection_state, state, session_status, tcp_state, ""))
| eval dest_host_norm=lower(coalesce(dest_host, hostname, dest_hostname, ""))
| where (
    src_zone_norm IN ("<vendor_vpn_zone>", "vpn", "vendor_vpn")
    OR like(src_zone_norm, "%vpn%")
  )
  AND (
    dest_zone_norm IN ("<ot_jump_zone>", "ot_jump", "jump")
    OR like(dest_host_norm, "%jump%")
  )
  AND session_state_norm IN ("established", "built", "connected", "tcp_established")
| stats
    count as connection_count
    values(src_zone_norm) as src_zones
    values(dest_zone_norm) as dest_zones
    values(rule) as firewall_rules
    values(session_state_norm) as session_states
    earliest(_time) as first_seen_epoch
    latest(_time) as last_seen_epoch
    by src_ip_norm dest_ip_norm
| eval first_seen=strftime(first_seen_epoch, "%Y-%m-%d %H:%M:%S")
| eval last_seen=strftime(last_seen_epoch, "%Y-%m-%d %H:%M:%S")
| fields - first_seen_epoch last_seen_epoch
| table src_ip_norm dest_ip_norm src_zones dest_zones firewall_rules session_states connection_count first_seen last_seen
| sort - connection_count
| head 100
""",
        assumptions=(
            "Vendor VPN to OT jump-server access uses strict established session states only.",
            "Replace <vendor_vpn_zone> and <ot_jump_zone> from your firewall source profile.",
            "If your vendor encodes session state differently, map values during source-profile review — do not add fuzzy like() in default SPL.",
        ),
        required_log_fields=_FIREWALL_LOG_FIELDS,
        required_source_profile_fields=("vendor_vpn_zone", "ot_jump_zone"),
        investigation_checklist=FIREWALL_BOUNDARY_CHECKLIST,
        scope_notice=ESTABLISHED_TRAFFIC_SCOPE_NOTICE,
    ),
    _family(
        "firewall_it_ot_rdp",
        pattern_texts=(
            r"\brdp\b",
            r"remote\s+desktop",
            r"\b3389\b",
        ),
        draft_spl="""
search index=<esp_firewall_index> sourcetype=<esp_firewall_sourcetype> earliest=-24h latest=now (action=allowed OR action=accept OR action=permit OR action=success)
| eval src_zone_norm=lower(coalesce(src_zone, source_zone, zone_src, ""))
| eval dest_zone_norm=lower(coalesce(dest_zone, destination_zone, zone_dest, ""))
| eval src_ip_norm=coalesce(src_ip, src, source, "")
| eval dest_ip_norm=coalesce(dest_ip, dest, destination, "")
| eval protocol_norm=lower(coalesce(protocol, proto, protocol_name, transport, ""))
| eval dest_port_norm=coalesce(dest_port, destination_port, dport, "")
| eval session_state_norm=lower(coalesce(session_state, connection_state, state, session_status, tcp_state, ""))
| where (
    src_zone_norm IN ("<corporate_it_zone>", "<corporate_it_zone_alt>")
    OR cidrmatch("<corporate_it_cidr>", src_ip_norm)
  )
  AND (
    dest_zone_norm IN ("<ot_control_center_zone>", "<ot_control_center_zone_alt>")
    OR cidrmatch("<ot_control_center_cidr>", dest_ip_norm)
  )
  AND (
    dest_port_norm IN ("3389", "3388")
    OR like(protocol_norm, "%rdp%")
  )
  AND session_state_norm IN ("established", "built", "connected", "tcp_established")
| stats
    count as connection_count
    values(src_zone_norm) as src_zones
    values(dest_zone_norm) as dest_zones
    values(rule) as firewall_rules
    values(protocol_norm) as protocols
    values(dest_port_norm) as dest_ports
    values(session_state_norm) as session_states
    earliest(_time) as first_seen_epoch
    latest(_time) as last_seen_epoch
    by src_ip_norm dest_ip_norm
| eval first_seen=strftime(first_seen_epoch, "%Y-%m-%d %H:%M:%S")
| eval last_seen=strftime(last_seen_epoch, "%Y-%m-%d %H:%M:%S")
| fields - first_seen_epoch last_seen_epoch
| table src_ip_norm dest_ip_norm src_zones dest_zones firewall_rules protocols dest_ports session_states connection_count first_seen last_seen
| sort - connection_count
| head 100
""",
        assumptions=(
            "RDP IT-to-OT crossing draft filters dest_port 3389/3388 or RDP protocol label.",
            "Established sessions use strict session_state_norm IN() values only.",
            "Replace zone/CIDR placeholders from your ESP firewall source profile.",
        ),
        required_log_fields=_FIREWALL_LOG_FIELDS,
        required_source_profile_fields=_FIREWALL_PROFILE_FIELDS,
        investigation_checklist=FIREWALL_BOUNDARY_CHECKLIST,
        scope_notice=ESTABLISHED_TRAFFIC_SCOPE_NOTICE,
    ),
    _family(
        "firewall_ot_smb_lateral",
        pattern_texts=(
            r"\bsmb\b",
            r"\b445\b",
            r"ot\s+network\s+segment",
            r"between\s+ot",
        ),
        draft_spl="""
search index=<ot_firewall_index> sourcetype=<ot_firewall_sourcetype> earliest=-24h latest=now (action=allowed OR action=accept OR action=permit OR action=success)
| eval src_zone_norm=lower(coalesce(src_zone, source_zone, zone_src, ""))
| eval dest_zone_norm=lower(coalesce(dest_zone, destination_zone, zone_dest, ""))
| eval src_ip_norm=coalesce(src_ip, src, source, "")
| eval dest_ip_norm=coalesce(dest_ip, dest, destination, "")
| eval protocol_norm=lower(coalesce(protocol, proto, protocol_name, transport, ""))
| eval dest_port_norm=coalesce(dest_port, destination_port, dport, "")
| eval app_norm=lower(coalesce(app, application, service, ""))
| where (
    src_zone_norm IN ("<ot_segment_a_zone>", "<ot_segment_b_zone>")
    OR cidrmatch("<ot_segment_cidr>", src_ip_norm)
  )
  AND (
    dest_zone_norm IN ("<ot_segment_a_zone>", "<ot_segment_b_zone>")
    OR cidrmatch("<ot_segment_cidr>", dest_ip_norm)
  )
  AND (
    dest_port_norm IN ("445", "139")
    OR like(app_norm, "%smb%")
    OR like(protocol_norm, "%smb%")
  )
| stats
    count as connection_count
    values(src_zone_norm) as src_zones
    values(dest_zone_norm) as dest_zones
    values(rule) as firewall_rules
    values(app_norm) as applications
    values(protocol_norm) as protocols
    values(dest_port_norm) as dest_ports
    earliest(_time) as first_seen_epoch
    latest(_time) as last_seen_epoch
    by src_ip_norm dest_ip_norm
| eval first_seen=strftime(first_seen_epoch, "%Y-%m-%d %H:%M:%S")
| eval last_seen=strftime(last_seen_epoch, "%Y-%m-%d %H:%M:%S")
| fields - first_seen_epoch last_seen_epoch
| table src_ip_norm dest_ip_norm src_zones dest_zones firewall_rules applications protocols dest_ports connection_count first_seen last_seen
| sort - connection_count
| head 100
""",
        assumptions=(
            "OT segment SMB lateral-movement draft scopes allowed SMB (445/139) between OT zones.",
            "Replace <ot_segment_a_zone>, <ot_segment_b_zone>, and <ot_segment_cidr> from your OT firewall profile.",
            "This draft does not apply established-session filters — SMB session semantics vary by vendor.",
        ),
        required_log_fields=_FIREWALL_LOG_FIELDS,
        required_source_profile_fields=("ot_segment_a_zone", "ot_segment_b_zone", "ot_segment_cidr"),
        investigation_checklist=FIREWALL_BOUNDARY_CHECKLIST,
        scope_notice=ESTABLISHED_TRAFFIC_SCOPE_NOTICE,
    ),
    _family(
        "network_smb_top_talkers",
        pattern_texts=(
            r"\bsmb\b",
            r"\bcifs\b",
            r"\b445\b",
            r"top\s+talkers?",
            r"generating\s+the\s+most",
            r"most\s+smb\s+traffic",
        ),
        draft_spl=f"""
search index=<network_index> sourcetype=<network_traffic_sourcetype> earliest=-24h latest=now (dest_port=445 OR dest_port=139 OR app=smb OR app=cifs OR app="microsoft-ds" OR service=smb OR service=cifs OR service="microsoft-ds")
| eval src_host_norm=lower(coalesce(src_host, src_nt_host, hostname, src, src_ip, "unknown"))
| eval src_ip_norm=coalesce(src_ip, src, source, "")
| eval dest_ip_norm=coalesce(dest_ip, dest, destination, "")
| eval dest_port_norm=coalesce(dest_port, destination_port, dport, "")
| eval app_norm=lower(coalesce(app, application, service, svc, protocol, proto, ""))
| eval action_norm=lower(coalesce(action, status, result, disposition, ""))
| eval bytes_total={_BYTES_TOTAL_EXPR}
| where dest_port_norm IN ("445", "139")
    OR like(app_norm, "%smb%")
    OR like(app_norm, "%cifs%")
    OR like(app_norm, "%microsoft-ds%")
| stats
    count as connection_count
    sum(bytes_total) as total_bytes
    dc(dest_ip_norm) as distinct_destinations
    values(dest_port_norm) as dest_ports
    values(app_norm) as applications
    values(action_norm) as actions
    earliest(_time) as first_seen_epoch
    latest(_time) as last_seen_epoch
    by src_host_norm src_ip_norm
| eval first_seen=strftime(first_seen_epoch, "%Y-%m-%d %H:%M:%S")
| eval last_seen=strftime(last_seen_epoch, "%Y-%m-%d %H:%M:%S")
| fields - first_seen_epoch last_seen_epoch
| table src_host_norm src_ip_norm connection_count total_bytes distinct_destinations dest_ports applications actions first_seen last_seen
| sort - connection_count
| head 100
""",
        assumptions=(
            "Top-SMB-talkers analytics draft ranks source hosts by SMB session volume; it is not an incident detection.",
            "SMB indicator is dest_port 445/139 OR app/protocol/service containing smb, cifs, or microsoft-ds.",
            "bytes_total uses null-safe coalesce(bytes, coalesce(bytes_out,0)+coalesce(bytes_in,0), 0) — vendors that omit byte counts return 0; validate during source-profile review.",
            "No action filter is applied: allowed and denied sessions are both counted; add action filters during SOC review if needed.",
            "Replace <network_index> and <network_traffic_sourcetype> from your network/firewall traffic source profile.",
            "This draft is lab-only; not governed, not approved, and not executed.",
        ),
        required_log_fields=(
            "index",
            "sourcetype",
            "src_ip",
            "src_host",
            "dest_ip",
            "dest_host",
            "dest_port",
            "app",
            "protocol",
            "bytes",
            "bytes_out",
            "bytes_in",
            "action",
            "_time",
        ),
        required_source_profile_fields=(
            "network_index",
            "network_traffic_sourcetype",
        ),
        investigation_checklist=(
            "Confirm the traffic source profile (index, sourcetype, byte-count fields) before trusting volumes.",
            "Expect file servers, domain controllers, and backup systems among top SMB talkers — validate against asset inventory.",
            "Flag workstations or unexpected segments ranking high for SMB volume for follow-up review.",
            "Pivot on distinct_destinations and dest_ports for fan-out patterns before drawing any lateral-movement conclusion.",
            "Do not declare compromise from SMB volume ranking alone.",
        ),
    ),
    _family(
        "esp_it_to_ot_connection",
        pattern_texts=(
            r"electronic\s+security\s+perimeter",
            r"\besp\b",
            r"corporate\s+it",
            r"\bot\b",
            r"control\s+center",
            r"firewall\s+log",
            r"ot\s+vlan",
        ),
        draft_spl="""
search index=<esp_firewall_index> sourcetype=<esp_firewall_sourcetype> earliest=-24h latest=now (action=allowed OR action=accept OR action=permit OR action=success)
| eval src_zone_norm=lower(coalesce(src_zone, source_zone, zone_src, ""))
| eval dest_zone_norm=lower(coalesce(dest_zone, destination_zone, zone_dest, ""))
| eval src_ip_norm=coalesce(src_ip, src, source, "")
| eval dest_ip_norm=coalesce(dest_ip, dest, destination, "")
| eval app_norm=lower(coalesce(app, application, service, ""))
| eval protocol_norm=lower(coalesce(protocol, proto, protocol_name, transport, ""))
| eval dest_port_norm=coalesce(dest_port, destination_port, dport, "")
| eval action_norm=lower(coalesce(action, status, result, disposition, ""))
| eval session_state_norm=lower(coalesce(session_state, connection_state, state, session_status, tcp_state, ""))
| where (
    src_zone_norm IN ("<corporate_it_zone>", "<corporate_it_zone_alt>")
    OR cidrmatch("<corporate_it_cidr>", src_ip_norm)
  )
  AND (
    dest_zone_norm IN ("<ot_control_center_zone>", "<ot_control_center_zone_alt>")
    OR cidrmatch("<ot_control_center_cidr>", dest_ip_norm)
  )
  AND session_state_norm IN ("established", "built", "connected", "tcp_established")
| stats
    count as connection_count
    values(src_zone_norm) as src_zones
    values(dest_zone_norm) as dest_zones
    values(rule) as firewall_rules
    values(app_norm) as applications
    values(protocol_norm) as protocols
    values(dest_port_norm) as dest_ports
    values(action_norm) as actions
    values(session_state_norm) as session_states
    earliest(_time) as first_seen_epoch
    latest(_time) as last_seen_epoch
    by src_ip_norm dest_ip_norm
| eval first_seen=strftime(first_seen_epoch, "%Y-%m-%d %H:%M:%S")
| eval last_seen=strftime(last_seen_epoch, "%Y-%m-%d %H:%M:%S")
| fields - first_seen_epoch last_seen_epoch
| table src_ip_norm dest_ip_norm src_zones dest_zones firewall_rules applications protocols dest_ports actions session_states connection_count first_seen last_seen
| sort - connection_count
| head 100
""",
        assumptions=(
            "ESP firewall zones label corporate IT and OT control center segments.",
            "Shift-left (action=allowed OR action=accept OR action=permit OR action=success) in base search; IT→OT boundary uses exact zone IN() labels and/or cidrmatch() CIDR placeholders.",
            "Replace <corporate_it_zone>, <ot_control_center_zone>, <corporate_it_cidr>, and <ot_control_center_cidr> from your ESP source profile; remove unused _alt zone tokens or replace with real alternates.",
            "Established connections require strict session_state_norm IN (established, built, connected, tcp_established) — blank session state is not treated as established.",
            "If session_state or connection_state is missing from your sourcetype, map it during source-profile review before relying on this draft.",
            "Vendor-specific fuzzy session matching belongs in source-profile review guidance only, not in default draft SPL.",
            "values() preserves src_zone, dest_zone, rule, app, protocol, dest_port, action, and session_state through stats.",
        ),
        required_log_fields=_FIREWALL_LOG_FIELDS,
        required_source_profile_fields=_FIREWALL_PROFILE_FIELDS,
        investigation_checklist=FIREWALL_BOUNDARY_CHECKLIST,
        scope_notice=ESTABLISHED_TRAFFIC_SCOPE_NOTICE,
    ),
    _family(
        "vpn_new_country_login",
        pattern_texts=(
            r"\bvpn\b",
            r"countr",
            r"not\s+seen",
            r"unseen",
            r"new\s+countr",
            r"never\s+seen",
            r"first[\s-]?seen",
        ),
        draft_spl="""
search index=<vpn_index> sourcetype=<vpn_auth_sourcetype> earliest=-90d latest=now (action=success OR action=allowed OR action=permit OR action=login OR result=success)
| eval user_norm=lower(coalesce(user, username, src_user, ""))
| eval src_ip_norm=coalesce(src_ip, src, source, "")
| eval country_norm=upper(coalesce(geo_country, src_country, country, ""))
| eval action_norm=lower(coalesce(action, status, result, event_action, ""))
| eval app_norm=lower(coalesce(app, application, vpn_app, ""))
| eval mfa_norm=lower(coalesce(mfa_result, mfa_status, authentication_result, ""))
| eval device_norm=coalesce(device_id, device, endpoint_id, "")
| eval user_agent_norm=coalesce(user_agent, http_user_agent, "")
| where user_norm!="" AND country_norm!=""
| eventstats min(_time) as first_country_seen by user_norm country_norm
| where _time=first_country_seen AND first_country_seen>=relative_time(now(),"-24h@h")
| sort 0 - _time
| eval login_time=strftime(_time, "%Y-%m-%d %H:%M:%S")
| table login_time user_norm src_ip_norm country_norm action_norm app_norm mfa_norm device_norm user_agent_norm
| head 100
""",
        assumptions=(
            "Shift-left VPN success/login actions in base search; tune action values to your VPN auth sourcetype.",
            "First-seen country uses eventstats min(_time) by user+country within the 90-day lookback; the 24h filter flags the country's first appearance. No fragile streamstats current=f.",
            "Per-login fields (src_ip, action, app, mfa, device, user_agent) are kept at event level by eventstats, not collapsed by stats.",
            "Replace <vpn_index> and <vpn_auth_sourcetype> from your VPN source profile before review.",
            "Map geo_country, src_country, or country to the field your VPN logs populate; geo enrichment accuracy varies by egress IP.",
            "This draft is lab-only; not governed, not approved, and not executed.",
        ),
        required_log_fields=(
            "index",
            "sourcetype",
            "user",
            "src_ip",
            "geo_country",
            "action",
            "_time",
        ),
        required_source_profile_fields=(
            "vpn_index",
            "vpn_auth_sourcetype",
            "geo_country_field",
        ),
        investigation_checklist=(
            "Confirm VPN auth sourcetype and country field mapping from the source profile.",
            "Validate geo enrichment accuracy for VPN egress IPs before treating country as novel.",
            "Review MFA outcome and device context when those fields are available.",
            "Correlate with IdP/VPN vendor admin activity before escalation.",
        ),
    ),
    _family(
        "auth_success_after_failure",
        pattern_texts=(
            r"success.*after.*fail",
            r"after\s+(?:repeated\s+)?fail",
            r"fail.*then.*success",
            r"success(?:ful)?\s+log\s*in.*fail",
        ),
        draft_spl="""
search index=<auth_index> sourcetype=<auth_sourcetype> earliest=-24h latest=now (action=success OR action=failure OR action=failed OR action=denied OR result=success OR result=failure)
| eval user_norm=lower(coalesce(user, username, src_user, ""))
| eval src_ip_norm=coalesce(src_ip, src, source, "")
| eval host_norm=lower(coalesce(dest, host, dest_host, ""))
| eval action_norm=lower(coalesce(action, status, result, event_action, ""))
| eval outcome=case(match(action_norm, "fail|denied|invalid"), "failure", match(action_norm, "success|allowed|permit"), "success", true(), "other")
| where user_norm!="" AND outcome!="other"
| eval failure_time=if(outcome="failure", _time, null())
| eval success_time=if(outcome="success", _time, null())
| stats count(failure_time) as failure_count count(success_time) as success_count min(failure_time) as first_failure_epoch max(success_time) as last_success_epoch values(src_ip_norm) as source_ips values(host_norm) as hosts by user_norm
| where failure_count>=5 AND success_count>=1 AND last_success_epoch>first_failure_epoch
| eval first_failure=strftime(first_failure_epoch, "%Y-%m-%d %H:%M:%S")
| eval last_success=strftime(last_success_epoch, "%Y-%m-%d %H:%M:%S")
| fields - first_failure_epoch last_success_epoch
| table user_norm failure_count success_count source_ips hosts first_failure last_success
| sort - failure_count
| head 100
""",
        assumptions=(
            "Correlates repeated failures followed by a later success for the SAME user; success must occur after the first failure.",
            "Shift-left success/failure/denied actions in base search; outcome bucketed via match() on action_norm.",
            "Source IPs and hosts are preserved with values() so analysts can see whether failures and the success share a source/host.",
            "Failure threshold (>=5) is illustrative — tune per environment; lower for high-value accounts.",
            "Replace <auth_index> and <auth_sourcetype> from your authentication source profile before review.",
            "This draft is lab-only; not governed, not approved, and not executed.",
        ),
        required_log_fields=(
            "index",
            "sourcetype",
            "user",
            "src_ip",
            "action",
            "_time",
        ),
        required_source_profile_fields=(
            "auth_index",
            "auth_sourcetype",
        ),
        investigation_checklist=(
            "Confirm the success genuinely followed the failure burst (not interleaved noise).",
            "Check whether the successful login came from the same source IP/host as the failures.",
            "Review MFA outcome and device posture for the successful login when available.",
            "Correlate with password-reset, IdP admin, or lockout events before escalation.",
        ),
    ),
    _family(
        "substation_hmi_brute_force",
        pattern_texts=(
            r"substation",
            r"\bhmi\b",
            r"brute[\s-]?force",
            r"failed\s+(?:to\s+)?log\s*in",
            r"failed\s+login",
        ),
        draft_spl="""
search index=<substation_index> sourcetype=<hmi_or_os_auth_sourcetype> earliest=-24h latest=now (failure OR fail OR denied)
| eval src_ip_norm=coalesce(src_ip, src, source, "")
| eval user_norm=lower(coalesce(user, username, src_user, "unknown"))
| eval dest_norm=lower(coalesce(dest, host, asset, target, "unknown"))
| eval app_norm=lower(coalesce(app, application, portal, service, ""))
| eval action_norm=lower(coalesce(action, status, result, event_action, ""))
| where (
    like(action_norm, "%fail%")
    OR like(action_norm, "%denied%")
  )
  AND (
    like(app_norm, "%hmi%")
    OR like(app_norm, "%portal%")
    OR like(dest_norm, "%hmi%")
    OR like(dest_norm, "%ot%")
  )
| sort 0 + _time
| streamstats time_window=5m count as fail_count dc(user_norm) as distinct_users values(user_norm) as targeted_users by src_ip_norm
| where fail_count>10
| eval window_end=strftime(_time, "%Y-%m-%d %H:%M:%S")
| table window_end src_ip_norm fail_count distinct_users targeted_users
| sort - fail_count
| head 100
""",
        assumptions=(
            "Shift-left (failure OR fail OR denied) in base search; HMI/portal targeting via like() on app_norm/dest_norm.",
            "Rolling 5-minute window uses sort 0 + _time then streamstats time_window=5m — not bin/stats.",
            "Threshold of more than 10 failures per window is illustrative; tune per environment.",
            "HMI/OS portal field names vary — confirm app/dest mappings for substation assets.",
        ),
        required_log_fields=(
            "index",
            "sourcetype",
            "action",
            "user",
            "src_ip",
            "app",
            "dest_category",
            "_time",
        ),
    ),
    _family(
        "auth_failed_login_threshold",
        pattern_texts=(
            r"failed\s+logins?",
            r"login\s+failures?",
            r"authentication\s+failures?",
            r"excessive|spike|most\s+failed",
        ),
        draft_spl="""
search index=<auth_index> sourcetype=<auth_sourcetype> earliest=-24h latest=now (action=failure OR action=failed OR action=denied OR result=failure)
| eval user_norm=lower(coalesce(user, username, src_user, "unknown"))
| eval src_ip_norm=coalesce(src_ip, src, source, "")
| eval dest_norm=lower(coalesce(dest, host, dest_host, ""))
| eval action_norm=lower(coalesce(action, status, result, event_action, ""))
| stats
    count as fail_count
    dc(user_norm) as distinct_users
    values(dest_norm) as targets
    earliest(_time) as first_seen_epoch
    latest(_time) as last_seen_epoch
    by src_ip_norm user_norm
| eval first_seen=strftime(first_seen_epoch, "%Y-%m-%d %H:%M:%S")
| eval last_seen=strftime(last_seen_epoch, "%Y-%m-%d %H:%M:%S")
| fields - first_seen_epoch last_seen_epoch
| where fail_count>20
| table src_ip_norm user_norm fail_count distinct_users targets first_seen last_seen
| sort - fail_count
| head 100
""",
        assumptions=(
            "Generic failed-login threshold hunt ranks source/user pairs by failure count in 24 hours.",
            "The threshold (more than 20 failures) is illustrative — tune per environment; lower for privileged accounts.",
            "Counts are failure events per source/user pair, not a global distinct-user total.",
            "Replace <auth_index> and <auth_sourcetype> from your authentication source profile.",
            "This draft is lab-only; not governed, not approved, and not executed.",
        ),
        required_log_fields=(
            "index",
            "sourcetype",
            "user",
            "src_ip",
            "action",
            "_time",
        ),
        required_source_profile_fields=("auth_index", "auth_sourcetype"),
        investigation_checklist=(
            "Check whether failures are concentrated on one account or sprayed across many.",
            "Look for any success following the failure burst (success-after-failure correlation).",
            "Validate source IP ownership before escalation.",
            "Do not declare brute-force compromise from failure counts alone.",
        ),
    ),
    _family(
        "network_traffic_top_talkers",
        pattern_texts=(
            r"top\s+talkers?",
            r"most\s+(?:outbound\s+)?connections",
            r"most\s+traffic",
            r"highest\s+volume",
        ),
        draft_spl="""
search index=<network_index> sourcetype=<network_traffic_sourcetype> earliest=-24h latest=now (dest_port=* OR bytes=* OR bytes_out=*)
| eval src_host_norm=lower(coalesce(src_host, src_nt_host, hostname, src, src_ip, "unknown"))
| eval src_ip_norm=coalesce(src_ip, src, source, "")
| eval dest_ip_norm=coalesce(dest_ip, dest, destination, "")
| eval dest_port_norm=coalesce(dest_port, destination_port, dport, "")
| eval bytes_total={_BYTES_TOTAL_EXPR}
| stats
    count as connection_count
    sum(bytes_total) as total_bytes
    dc(dest_ip_norm) as distinct_destinations
    values(dest_port_norm) as dest_ports
    earliest(_time) as first_seen_epoch
    latest(_time) as last_seen_epoch
    by src_host_norm src_ip_norm
| eval first_seen=strftime(first_seen_epoch, "%Y-%m-%d %H:%M:%S")
| eval last_seen=strftime(last_seen_epoch, "%Y-%m-%d %H:%M:%S")
| fields - first_seen_epoch last_seen_epoch
| table src_host_norm src_ip_norm connection_count total_bytes distinct_destinations dest_ports first_seen last_seen
| sort - connection_count
| head 100
""",
        assumptions=(
            "Generic top-talkers analytics draft ranks sources by connection count and byte volume; it is not an incident detection.",
            "bytes_total uses null-safe coalesce(bytes, coalesce(bytes_out,0)+coalesce(bytes_in,0), 0).",
            "Swap the sort key to total_bytes when volume matters more than session count.",
            "Replace <network_index> and <network_traffic_sourcetype> from your network traffic source profile.",
            "This draft is lab-only; not governed, not approved, and not executed.",
        ),
        required_log_fields=(
            "index",
            "sourcetype",
            "src_ip",
            "dest_ip",
            "dest_port",
            "bytes",
            "_time",
        ),
        required_source_profile_fields=("network_index", "network_traffic_sourcetype"),
        investigation_checklist=(
            "Validate top talkers against asset inventory (servers and backup systems rank high legitimately).",
            "Pivot on distinct_destinations and dest_ports before drawing conclusions from volume alone.",
            "Do not declare compromise from traffic ranking alone.",
        ),
    ),
    _family(
        "ioc_destination_match",
        pattern_texts=(
            r"\bioc\b",
            r"known\s+malicious",
            r"suspicious\s+(?:external\s+)?(?:domains?|ips?|destinations?)",
            r"threat\s+intel",
            r"blocklist|blacklist",
        ),
        draft_spl="""
search index=<network_index> sourcetype=<network_traffic_sourcetype> earliest=-24h latest=now (dest_ip=* OR dest=* OR query=*)
| eval src_host_norm=lower(coalesce(src_host, src_nt_host, hostname, src, src_ip, "unknown"))
| eval dest_ip_norm=coalesce(dest_ip, dest, destination, "")
| eval domain_norm=lower(coalesce(query, question, dest_host, url_domain, ""))
| eval action_norm=lower(coalesce(action, status, result, disposition, ""))
| where dest_ip_norm IN ("<ioc_ip_1>", "<ioc_ip_2>", "<ioc_ip_3>")
    OR domain_norm IN ("<ioc_domain_1>", "<ioc_domain_2>", "<ioc_domain_3>")
| stats
    count as match_count
    values(domain_norm) as matched_domains
    values(action_norm) as actions
    earliest(_time) as first_seen_epoch
    latest(_time) as last_seen_epoch
    by src_host_norm dest_ip_norm
| eval first_seen=strftime(first_seen_epoch, "%Y-%m-%d %H:%M:%S")
| eval last_seen=strftime(last_seen_epoch, "%Y-%m-%d %H:%M:%S")
| fields - first_seen_epoch last_seen_epoch
| table src_host_norm dest_ip_norm matched_domains actions match_count first_seen last_seen
| sort - match_count
| head 100
""",
        assumptions=(
            "IOC values are review-time placeholders filled from your governed local IOC list; a lookup-table integration is planned (Stage 3K Q2) and not assumed here.",
            "The lookup command is outside the current allowed SPL command policy, so IOC matching uses explicit IN() placeholder lists.",
            "Both destination IPs and DNS/HTTP domains are matched; drop whichever side your sourcetype does not populate.",
            "An IOC match is an investigation trigger, not a compromise verdict — verify direction, action (allowed vs blocked), and asset context.",
            "Replace <network_index> and <network_traffic_sourcetype> from your network traffic source profile.",
            "This draft is lab-only; not governed, not approved, and not executed.",
        ),
        required_log_fields=(
            "index",
            "sourcetype",
            "src_ip",
            "dest_ip",
            "query",
            "action",
            "_time",
        ),
        required_source_profile_fields=("network_index", "network_traffic_sourcetype", "local_ioc_list"),
        investigation_checklist=(
            "Confirm IOC list provenance and freshness before acting on matches.",
            "Check whether matched traffic was allowed or blocked at the control point.",
            "Validate asset owner and business context of matching sources before escalation.",
            "Do not declare compromise from an IOC match alone.",
        ),
    ),
    _family(
        "dns_beaconing_hunt",
        pattern_texts=(
            r"beacon",
            r"\bdga\b",
            r"command[\s-]and[\s-]control|\bc2\b",
            r"regular\s+intervals?",
            r"long\s+(?:dns\s+)?(?:names?|quer)",
            r"top[\s-]level\s+domains?|\btld\b",
        ),
        draft_spl="""
search index=<dns_index> sourcetype=<dns_sourcetype> earliest=-24h latest=now (query=* OR question=*)
| eval src_host_norm=lower(coalesce(src_host, src, src_ip, host, "unknown"))
| eval domain_norm=lower(coalesce(query, question, domain, ""))
| eval domain_length=len(domain_norm)
| eval reply_norm=lower(coalesce(reply_code, rcode, answer, ""))
| stats
    count as query_count
    dc(domain_norm) as distinct_domains
    avg(domain_length) as avg_domain_length
    max(domain_length) as max_domain_length
    range(_time) as active_span_seconds
    earliest(_time) as first_seen_epoch
    latest(_time) as last_seen_epoch
    by src_host_norm domain_norm
| eval first_seen=strftime(first_seen_epoch, "%Y-%m-%d %H:%M:%S")
| eval last_seen=strftime(last_seen_epoch, "%Y-%m-%d %H:%M:%S")
| fields - first_seen_epoch last_seen_epoch
| where query_count>50 OR max_domain_length>60
| table src_host_norm domain_norm query_count distinct_domains avg_domain_length max_domain_length active_span_seconds first_seen last_seen
| sort - query_count
| head 100
""",
        assumptions=(
            "Beaconing/DGA hunt surfaces repeated queries to the same domain and unusually long names; true periodicity and jitter need timing analysis during review.",
            "Thresholds (more than 50 queries, names longer than 60 characters) are illustrative — tune per environment.",
            "High query counts to CDN, telemetry, or security vendor domains are common false positives — validate domain reputation first.",
            "Replace <dns_index> and <dns_sourcetype> from your DNS source profile.",
            "This draft is lab-only; not governed, not approved, and not executed.",
        ),
        required_log_fields=(
            "index",
            "sourcetype",
            "src_ip",
            "query",
            "_time",
        ),
        required_source_profile_fields=("dns_index", "dns_sourcetype"),
        investigation_checklist=(
            "Check domain age, reputation, and registrar before treating repetition as beaconing.",
            "Review inter-query timing for regular intervals or jitter during analyst review.",
            "Correlate candidate domains with proxy/firewall egress for actual payload transfer.",
            "Do not declare command-and-control from query volume alone.",
        ),
    ),
    _family(
        "network_new_or_rare_behavior",
        pattern_texts=(
            r"unusual\s+protocols?",
            r"rare\s+ports?",
            r"after\s+hours",
            r"peer[\s-]to[\s-]peer|\bp2p\b",
            r"(?:new|never\s+seen|first[\s-]?seen)\s+(?:source|destination|port|protocol)",
        ),
        draft_spl="""
search index=<network_index> sourcetype=<network_traffic_sourcetype> earliest=-7d latest=now (dest_port=* OR protocol=*)
| eval src_host_norm=lower(coalesce(src_host, src_nt_host, hostname, src, src_ip, "unknown"))
| eval dest_ip_norm=coalesce(dest_ip, dest, destination, "")
| eval dest_port_norm=coalesce(dest_port, destination_port, dport, "")
| eval protocol_norm=lower(coalesce(protocol, proto, protocol_name, transport, app, ""))
| stats
    count as connection_count
    dc(src_host_norm) as distinct_sources
    values(src_host_norm) as sources
    earliest(_time) as first_seen_epoch
    latest(_time) as last_seen_epoch
    by protocol_norm dest_port_norm
| eval first_seen=strftime(first_seen_epoch, "%Y-%m-%d %H:%M:%S")
| eval last_seen=strftime(last_seen_epoch, "%Y-%m-%d %H:%M:%S")
| fields - first_seen_epoch last_seen_epoch
| where distinct_sources<=2 OR connection_count<=5
| table protocol_norm dest_port_norm connection_count distinct_sources sources first_seen last_seen
| sort + connection_count
| head 100
""",
        assumptions=(
            "Rarity hunt ranks protocol/port combinations used by few sources or few sessions over a 7-day window; rare is not automatically malicious.",
            "Rarity thresholds (at most 2 sources, at most 5 connections) are illustrative — tune per environment size.",
            "For after-hours review, add an hour-of-day filter (for example date_hour) during SOC review; business hours vary per site.",
            "Replace <network_index> and <network_traffic_sourcetype> from your network traffic source profile.",
            "This draft is lab-only; not governed, not approved, and not executed.",
        ),
        required_log_fields=(
            "index",
            "sourcetype",
            "src_ip",
            "dest_ip",
            "dest_port",
            "protocol",
            "_time",
        ),
        required_source_profile_fields=("network_index", "network_traffic_sourcetype"),
        investigation_checklist=(
            "Validate rare protocol/port pairs against approved application inventory.",
            "Check whether the rare behavior aligns with maintenance or vendor activity windows.",
            "Pivot to the involved hosts' other traffic before escalation.",
            "Do not declare compromise from rarity alone.",
        ),
    ),
    _family(
        "network_threshold_anomaly",
        pattern_texts=(
            r"unusually\s+high",
            r"high\s+connection\s+counts?",
            r"spike",
            r"(?:largest|highest)\s+(?:dns\s+)?(?:response\s+)?volumes?",
            r"excessive",
        ),
        draft_spl="""
search index=<network_index> sourcetype=<network_traffic_sourcetype> earliest=-24h latest=now (dest_ip=* OR dest=*)
| eval src_host_norm=lower(coalesce(src_host, src_nt_host, hostname, src, src_ip, "unknown"))
| eval dest_ip_norm=coalesce(dest_ip, dest, destination, "")
| eval dest_port_norm=coalesce(dest_port, destination_port, dport, "")
| eval bytes_total={_BYTES_TOTAL_EXPR}
| stats
    count as connection_count
    sum(bytes_total) as total_bytes
    values(dest_port_norm) as dest_ports
    earliest(_time) as first_seen_epoch
    latest(_time) as last_seen_epoch
    by src_host_norm dest_ip_norm
| eval first_seen=strftime(first_seen_epoch, "%Y-%m-%d %H:%M:%S")
| eval last_seen=strftime(last_seen_epoch, "%Y-%m-%d %H:%M:%S")
| fields - first_seen_epoch last_seen_epoch
| where connection_count>500
| table src_host_norm dest_ip_norm connection_count total_bytes dest_ports first_seen last_seen
| sort - connection_count
| head 100
""",
        assumptions=(
            "Threshold hunt flags source-to-destination pairs with abnormally high session counts in 24 hours.",
            "The threshold (more than 500 connections to one destination) is illustrative — derive a per-environment baseline during review.",
            "Monitoring, backup, and proxy infrastructure legitimately exceed simple thresholds — validate against known services.",
            "Replace <network_index> and <network_traffic_sourcetype> from your network traffic source profile.",
            "This draft is lab-only; not governed, not approved, and not executed.",
        ),
        required_log_fields=(
            "index",
            "sourcetype",
            "src_ip",
            "dest_ip",
            "dest_port",
            "bytes",
            "_time",
        ),
        required_source_profile_fields=("network_index", "network_traffic_sourcetype"),
        investigation_checklist=(
            "Compare flagged pairs against a normal-day baseline before calling them anomalous.",
            "Check destination ownership (internal service vs external unknown).",
            "Review byte volume direction for exfiltration-shaped transfers.",
            "Do not declare compromise from connection counts alone.",
        ),
    ),
    _family(
        "endpoint_powershell_suspicious",
        pattern_texts=(
            r"encodedcommand|encoded\s+command|-enc\b",
            r"suspicious\s+powershell",
            r"script\s+block",
            r"download\s*string|downloadfile|invoke-expression|\biex\b",
            r"office\s+(?:parent|spawn)|winword|excel|outlook",
        ),
        draft_spl="""
search index=<endpoint_index> sourcetype=<endpoint_process_sourcetype> earliest=-24h latest=now (powershell OR pwsh)
| eval host_norm=lower(coalesce(Computer, host, dest, "unknown"))
| eval user_norm=lower(coalesce(User, user, user_name, "unknown"))
| eval parent_image_norm=lower(coalesce(ParentImage, ParentProcessName, parent_process_name, ""))
| eval command_line_norm=lower(coalesce(CommandLine, process_command_line, cmdline, ScriptBlockText, ""))
| where like(command_line_norm, "%-enc%")
    OR like(command_line_norm, "%encodedcommand%")
    OR like(command_line_norm, "%downloadstring%")
    OR like(command_line_norm, "%downloadfile%")
    OR like(command_line_norm, "%invoke-expression%")
    OR like(command_line_norm, "%frombase64string%")
    OR like(command_line_norm, "%-nop%")
    OR like(parent_image_norm, "%winword.exe")
    OR like(parent_image_norm, "%excel.exe")
    OR like(parent_image_norm, "%outlook.exe")
    OR like(parent_image_norm, "%wscript.exe")
    OR like(parent_image_norm, "%mshta.exe")
| sort 0 - _time
| eval event_time=strftime(_time, "%Y-%m-%d %H:%M:%S")
| table event_time host_norm user_norm parent_image_norm command_line_norm
| head 100
""",
        assumptions=(
            "Suspicious PowerShell hunt keys on encoded/download/IEX indicators and Office/script parent processes.",
            "Sourcetype placeholder accepts Sysmon EventCode 1, Windows 4688 with command line, or EDR process telemetry — map fields during review.",
            "Parent-image matching uses filename suffixes without path backslashes to stay vendor-neutral.",
            "Administrative automation can legitimately use encoded commands — decode and review content before judgment.",
            "Replace <endpoint_index> and <endpoint_process_sourcetype> from your endpoint source profile.",
            "This draft is lab-only; not governed, not approved, and not executed.",
        ),
        required_log_fields=(
            "index",
            "sourcetype",
            "CommandLine",
            "ParentImage",
            "Computer",
            "User",
            "_time",
        ),
        required_source_profile_fields=("endpoint_index", "endpoint_process_sourcetype"),
        investigation_checklist=(
            "Decode any encoded command content before assessing intent.",
            "Validate the parent process chain and signing status.",
            "Check for follow-on network connections from the same host.",
            "Do not declare compromise from PowerShell indicators alone.",
        ),
    ),
    _family(
        "network_data_exfil_volume",
        pattern_texts=(
            r"exfil",
            r"largest\s+uploads?",
            r"upload(?:ed|s)?\s+(?:the\s+)?most",
            r"outbound\s+(?:data|bytes|volume)",
            r"data\s+(?:left|leaving|transfer)",
        ),
        draft_spl="""
search index=<network_index> sourcetype=<proxy_or_firewall_sourcetype> earliest=-24h latest=now (bytes_out=* OR bytes=*)
| eval src_host_norm=lower(coalesce(src_host, src_nt_host, hostname, src, src_ip, "unknown"))
| eval user_norm=lower(coalesce(user, username, src_user, "unknown"))
| eval dest_domain_norm=lower(coalesce(dest_host, url_domain, domain, dest_ip, dest, ""))
| eval bytes_out_norm=coalesce(bytes_out, bytes, 0)
| stats
    sum(bytes_out_norm) as total_bytes_out
    count as request_count
    dc(dest_domain_norm) as distinct_destinations
    values(dest_domain_norm) as destinations
    earliest(_time) as first_seen_epoch
    latest(_time) as last_seen_epoch
    by src_host_norm user_norm
| eval first_seen=strftime(first_seen_epoch, "%Y-%m-%d %H:%M:%S")
| eval last_seen=strftime(last_seen_epoch, "%Y-%m-%d %H:%M:%S")
| fields - first_seen_epoch last_seen_epoch
| where total_bytes_out>104857600
| table src_host_norm user_norm total_bytes_out request_count distinct_destinations destinations first_seen last_seen
| sort - total_bytes_out
| head 100
""",
        assumptions=(
            "Outbound-volume hunt ranks source host/user pairs by bytes sent in 24 hours.",
            "The 100 MB threshold (104857600 bytes) is illustrative — baseline per environment; backups and cloud sync are common legitimate heavy senders.",
            "bytes_out semantics differ by vendor (client-to-server vs server-to-client) — confirm direction mapping during source-profile review.",
            "Replace <network_index> and <proxy_or_firewall_sourcetype> from your egress source profile.",
            "This draft is lab-only; not governed, not approved, and not executed.",
        ),
        required_log_fields=(
            "index",
            "sourcetype",
            "src_ip",
            "user",
            "dest_host",
            "bytes_out",
            "_time",
        ),
        required_source_profile_fields=("network_index", "proxy_or_firewall_sourcetype"),
        investigation_checklist=(
            "Validate destination category (sanctioned cloud storage vs unknown).",
            "Compare volume against the host's historical baseline.",
            "Correlate with DLP or endpoint file-access events when available.",
            "Do not declare exfiltration from volume alone.",
        ),
    ),
    _family(
        "lateral_movement_internal",
        pattern_texts=(
            r"lateral\s+movement",
            r"internal\s+(?:hosts?|systems?).{0,40}(?:connect|access)",
            r"admin(?:istrative)?\s+shares?|\badmin\$",
            r"(?:winrm|psexec|wmic?\b)",
            r"fan[\s-]?out",
        ),
        draft_spl="""
search index=<network_index> sourcetype=<internal_traffic_sourcetype> earliest=-24h latest=now (dest_port=445 OR dest_port=3389 OR dest_port=5985 OR dest_port=5986 OR dest_port=135)
| eval src_host_norm=lower(coalesce(src_host, src_nt_host, hostname, src, src_ip, "unknown"))
| eval src_ip_norm=coalesce(src_ip, src, source, "")
| eval dest_ip_norm=coalesce(dest_ip, dest, destination, "")
| eval dest_port_norm=coalesce(dest_port, destination_port, dport, "")
| stats
    dc(dest_ip_norm) as distinct_targets
    count as connection_count
    values(dest_port_norm) as dest_ports
    earliest(_time) as first_seen_epoch
    latest(_time) as last_seen_epoch
    by src_host_norm src_ip_norm
| eval first_seen=strftime(first_seen_epoch, "%Y-%m-%d %H:%M:%S")
| eval last_seen=strftime(last_seen_epoch, "%Y-%m-%d %H:%M:%S")
| fields - first_seen_epoch last_seen_epoch
| where distinct_targets>5
| table src_host_norm src_ip_norm distinct_targets connection_count dest_ports first_seen last_seen
| sort - distinct_targets
| head 100
""",
        assumptions=(
            "Lateral-movement hunt ranks internal sources by fan-out across admin protocols (SMB 445, RDP 3389, WinRM 5985/5986, RPC 135).",
            "The fan-out threshold (more than 5 distinct targets) is illustrative — management and vulnerability-scan hosts legitimately exceed it.",
            "Scope the search to internal-to-internal traffic during review (add source/destination CIDR filters from your profile).",
            "Replace <network_index> and <internal_traffic_sourcetype> from your internal traffic source profile.",
            "This draft is lab-only; not governed, not approved, and not executed.",
        ),
        required_log_fields=(
            "index",
            "sourcetype",
            "src_ip",
            "dest_ip",
            "dest_port",
            "_time",
        ),
        required_source_profile_fields=("network_index", "internal_traffic_sourcetype"),
        investigation_checklist=(
            "Exclude known administration and scanning hosts before review.",
            "Correlate fan-out sources with authentication events on the targets.",
            "Check timing — bursts in short windows are more suspicious than spread-out activity.",
            "Do not declare lateral movement from connection fan-out alone.",
        ),
    ),
    _family(
        "endpoint_persistence_schtask_service",
        pattern_texts=(
            r"scheduled\s+tasks?|schtasks",
            r"persistence",
            r"new\s+services?\b|service\s+(?:creation|install)",
            r"\b4698\b|\b7045\b|\b4697\b",
            r"run\s+keys?|autorun",
        ),
        draft_spl="""
search index=<windows_index> sourcetype=<windows_security_or_system_sourcetype> earliest=-7d latest=now (EventCode=4698 OR EventCode=4697 OR EventCode=7045)
| eval host_norm=lower(coalesce(Computer, host, dest, "unknown"))
| eval user_norm=lower(coalesce(SubjectUserName, user, Account_Name, "unknown"))
| eval object_name_norm=lower(coalesce(TaskName, task_name, Service_Name, ServiceName, service_name, ""))
| eval object_command_norm=lower(coalesce(TaskContent, ImagePath, image_path, Service_File_Name, command, ""))
| eval event_code_norm=coalesce(EventCode, signature_id, "")
| stats
    count as creation_count
    values(object_command_norm) as commands
    values(event_code_norm) as event_codes
    earliest(_time) as first_seen_epoch
    latest(_time) as last_seen_epoch
    by host_norm user_norm object_name_norm
| eval first_seen=strftime(first_seen_epoch, "%Y-%m-%d %H:%M:%S")
| eval last_seen=strftime(last_seen_epoch, "%Y-%m-%d %H:%M:%S")
| fields - first_seen_epoch last_seen_epoch
| table host_norm user_norm object_name_norm commands event_codes creation_count first_seen last_seen
| sort - first_seen
| head 100
""",
        assumptions=(
            "Persistence hunt covers scheduled-task creation (4698), service install (4697 security / 7045 system), over 7 days.",
            "Task/service command content fields vary by source — TaskContent XML vs ImagePath; map during review.",
            "Software deployment and patching create tasks/services legitimately — baseline known names first.",
            "Registry run-key persistence needs Sysmon EventCode 12/13 and is not covered by this draft.",
            "Replace <windows_index> and <windows_security_or_system_sourcetype> from your Windows source profile.",
            "This draft is lab-only; not governed, not approved, and not executed.",
        ),
        required_log_fields=(
            "index",
            "sourcetype",
            "EventCode",
            "TaskName",
            "ServiceName",
            "SubjectUserName",
            "Computer",
            "_time",
        ),
        required_source_profile_fields=("windows_index", "windows_security_or_system_sourcetype"),
        investigation_checklist=(
            "Review the task/service command line and binary path for unsigned or user-writable locations.",
            "Validate the creating account's role and normal behavior.",
            "Correlate creation time with other alerts on the same host.",
            "Do not declare persistence-based compromise from creation events alone.",
        ),
    ),
    _family(
        "notable_risk_review",
        pattern_texts=(
            r"notable\s+events?",
            r"risk\s+(?:scores?|events?|objects?)",
            r"accumulated\s+risk",
            r"(?:alerts?|incidents?)\s+.{0,30}(?:open|unresolved|high|critical)",
            r"high\s+or\s+critical",
        ),
        draft_spl="""
search index=<notable_index> sourcetype=<notable_or_risk_sourcetype> earliest=-24h latest=now (status=* OR risk_score=* OR urgency=*)
| eval risk_object_norm=lower(coalesce(risk_object, object, user, dest, host, "unknown"))
| eval rule_norm=lower(coalesce(search_name, rule, rule_name, source, ""))
| eval status_norm=lower(coalesce(status, status_label, disposition, ""))
| eval urgency_norm=lower(coalesce(urgency, severity, priority, ""))
| eval risk_score_norm=coalesce(risk_score, risk_score_sum, score, 0)
| stats
    count as event_count
    sum(risk_score_norm) as total_risk_score
    dc(rule_norm) as distinct_rules
    values(rule_norm) as rules
    values(status_norm) as statuses
    values(urgency_norm) as urgencies
    earliest(_time) as first_seen_epoch
    latest(_time) as last_seen_epoch
    by risk_object_norm
| eval first_seen=strftime(first_seen_epoch, "%Y-%m-%d %H:%M:%S")
| eval last_seen=strftime(last_seen_epoch, "%Y-%m-%d %H:%M:%S")
| fields - first_seen_epoch last_seen_epoch
| table risk_object_norm total_risk_score event_count distinct_rules rules statuses urgencies first_seen last_seen
| sort - total_risk_score
| head 100
""",
        assumptions=(
            "Notable/risk review ranks risk objects (users/hosts/assets) by accumulated risk score and notable/risk event count.",
            "Field names assume an ES-style notable or risk index — search_name, status, urgency, risk_score; map your SIEM's equivalents during review.",
            "For open/unresolved filtering, add status_norm IN (\"new\", \"open\", \"in progress\") during review — status vocabularies vary per deployment.",
            "Risk scores rank attention order; they are not a compromise verdict.",
            "Replace <notable_index> and <notable_or_risk_sourcetype> from your notable/risk source profile.",
            "This draft is lab-only; not governed, not approved, and not executed.",
        ),
        required_log_fields=(
            "index",
            "sourcetype",
            "risk_object",
            "search_name",
            "status",
            "urgency",
            "risk_score",
            "_time",
        ),
        required_source_profile_fields=("notable_index", "notable_or_risk_sourcetype"),
        investigation_checklist=(
            "Confirm the notable/risk index and status vocabulary from your SIEM configuration.",
            "Review distinct contributing rules — many rules on one object outranks one noisy rule.",
            "Cross-check top risk objects against asset criticality before prioritizing.",
            "Do not declare compromise from risk-score ranking alone.",
        ),
    ),
    _family(
        "windows_identity_privileged_activity",
        pattern_texts=(
            r"privileged\s+(?:actions?|applications?|access|logon)",
            r"non[\s-]?admin\s+workstations?",
            r"accounts?\s+(?:were\s+)?(?:disabled|re-?enabled)",
            r"\b4672\b|\b4722\b|\b4725\b|\b4738\b",
            r"added\s+to\s+administrators",
        ),
        draft_spl="""
search index=<windows_index> sourcetype=<windows_security_sourcetype> earliest=-24h latest=now (EventCode=4672 OR EventCode=4722 OR EventCode=4725 OR EventCode=4738 OR EventCode=4648)
| eval user_norm=lower(coalesce(SubjectUserName, TargetUserName, user, Account_Name, "unknown"))
| eval host_norm=lower(coalesce(Computer, host, dest, "unknown"))
| eval event_code_norm=coalesce(EventCode, signature_id, "")
| eval activity_norm=case(event_code_norm=="4672", "privileged_logon", event_code_norm=="4722", "account_enabled", event_code_norm=="4725", "account_disabled", event_code_norm=="4738", "account_changed", event_code_norm=="4648", "explicit_credentials", true(), "other")
| where NOT like(host_norm, "%<admin_workstation_pattern>%")
| stats
    count as activity_count
    values(activity_norm) as activities
    values(event_code_norm) as event_codes
    dc(host_norm) as distinct_hosts
    values(host_norm) as hosts
    earliest(_time) as first_seen_epoch
    latest(_time) as last_seen_epoch
    by user_norm
| eval first_seen=strftime(first_seen_epoch, "%Y-%m-%d %H:%M:%S")
| eval last_seen=strftime(last_seen_epoch, "%Y-%m-%d %H:%M:%S")
| fields - first_seen_epoch last_seen_epoch
| table user_norm activities event_codes activity_count distinct_hosts hosts first_seen last_seen
| sort - activity_count
| head 100
""",
        assumptions=(
            "Identity/privileged-activity hunt covers privileged logon (4672), account enable/disable (4722/4725), account change (4738), and explicit-credential use (4648).",
            "The NOT like(host_norm, ...) filter excludes approved admin workstations — replace <admin_workstation_pattern> from your asset inventory; remove the filter to see all hosts.",
            "Privileged-application access beyond Windows events needs application audit logs — map during review.",
            "Service accounts generate routine privileged logons — baseline before judging volume.",
            "Replace <windows_index> and <windows_security_sourcetype> from your Windows security source profile.",
            "This draft is lab-only; not governed, not approved, and not executed.",
        ),
        required_log_fields=(
            "index",
            "sourcetype",
            "EventCode",
            "SubjectUserName",
            "TargetUserName",
            "Computer",
            "_time",
        ),
        required_source_profile_fields=("windows_index", "windows_security_sourcetype", "admin_workstation_pattern"),
        investigation_checklist=(
            "Validate which workstations are approved for administrative use before flagging.",
            "Review account enable/disable actors and change tickets for authorization.",
            "Correlate privileged logons with the user's normal working pattern.",
            "Do not declare privilege misuse from event counts alone.",
        ),
    ),
    _family(
        "data_source_health_review",
        pattern_texts=(
            r"logs?\s+(?:are\s+)?missing",
            r"stopped\s+sending",
            r"not\s+sending\s+(?:events|logs)",
            r"(?:ingestion|data\s+source)\s+health",
            r"sources?\s+.{0,20}(?:silent|stale|gap)",
        ),
        draft_spl="""
search index=<monitored_index> earliest=-7d latest=now sourcetype=*
| eval sourcetype_norm=lower(coalesce(sourcetype, "unknown"))
| eval host_norm=lower(coalesce(host, "unknown"))
| stats
    count as event_count
    dc(host_norm) as reporting_hosts
    earliest(_time) as first_event_epoch
    latest(_time) as last_event_epoch
    by sourcetype_norm
| eval last_event=strftime(last_event_epoch, "%Y-%m-%d %H:%M:%S")
| eval first_event=strftime(first_event_epoch, "%Y-%m-%d %H:%M:%S")
| eval hours_since_last_event=round((now() - last_event_epoch) / 3600, 1)
| fields - first_event_epoch last_event_epoch
| where hours_since_last_event>24
| table sourcetype_norm event_count reporting_hosts hours_since_last_event first_event last_event
| sort - hours_since_last_event
| head 100
""",
        assumptions=(
            "Source-health review flags sourcetypes whose newest event is older than 24 hours within a 7-day window.",
            "A sourcetype absent for the whole 7 days will not appear at all — compare the result against your expected-source inventory during review.",
            "The 24-hour staleness threshold is illustrative — low-volume sources (weekly exports) need a longer threshold.",
            "Run once per monitored index; tstats/metadata variants are faster but outside the current allowed SPL command policy.",
            "Replace <monitored_index> from your logging inventory.",
            "This draft is lab-only; not governed, not approved, and not executed.",
        ),
        required_log_fields=(
            "index",
            "sourcetype",
            "host",
            "_time",
        ),
        required_source_profile_fields=("monitored_index", "expected_source_inventory"),
        investigation_checklist=(
            "Compare flagged sourcetypes against the expected-source inventory for true gaps.",
            "Check forwarder/collector health for sources that stopped sending.",
            "Verify whether silence aligns with planned maintenance or decommissioning.",
            "Treat silent security sources as a detection-coverage risk, not an incident by itself.",
        ),
    ),
    _family(
        "network_multi_signal_review",
        pattern_texts=(
            r"both\s+dns\s+and\s+network",
            r"dns\s+and\s+network\s+anomal",
            r"multiple\s+(?:signals?|anomalies|detections?)",
            r"outbound\s+traffic\s+after\s+dns",
            r"domains?\s+and\s+ips?",
        ),
        draft_spl="""
search index=<network_index> (sourcetype=<dns_sourcetype> OR sourcetype=<firewall_sourcetype>) earliest=-24h latest=now (query=* OR dest_ip=* OR dest=*)
| eval src_host_norm=lower(coalesce(src_host, src_nt_host, hostname, src, src_ip, "unknown"))
| eval domain_norm=lower(coalesce(query, question, ""))
| eval dest_ip_norm=coalesce(dest_ip, dest, destination, "")
| eval signal_type=if(domain_norm!="", "dns", "network")
| stats
    count as event_count
    dc(signal_type) as signal_types_seen
    values(signal_type) as signals
    dc(domain_norm) as distinct_domains
    dc(dest_ip_norm) as distinct_destinations
    earliest(_time) as first_seen_epoch
    latest(_time) as last_seen_epoch
    by src_host_norm
| eval first_seen=strftime(first_seen_epoch, "%Y-%m-%d %H:%M:%S")
| eval last_seen=strftime(last_seen_epoch, "%Y-%m-%d %H:%M:%S")
| fields - first_seen_epoch last_seen_epoch
| where signal_types_seen>1
| table src_host_norm signals event_count distinct_domains distinct_destinations first_seen last_seen
| sort - event_count
| head 100
""",
        assumptions=(
            "Multi-signal review surfaces hosts present in both DNS and network/firewall telemetry within the window — co-presence, not causal correlation.",
            "True DNS-then-connection sequencing needs per-event timing analysis during review; this draft only flags overlap candidates.",
            "Replace <network_index>, <dns_sourcetype>, and <firewall_sourcetype> from your source profiles; split into two searches if the sourcetypes live in different indexes.",
            "This draft is lab-only; not governed, not approved, and not executed.",
        ),
        required_log_fields=(
            "index",
            "sourcetype",
            "src_ip",
            "query",
            "dest_ip",
            "_time",
        ),
        required_source_profile_fields=("network_index", "dns_sourcetype", "firewall_sourcetype"),
        investigation_checklist=(
            "Verify the DNS query actually preceded the network connection during review.",
            "Check resolved-IP vs contacted-IP overlap for the candidate hosts.",
            "Validate domains and destinations against reputation sources.",
            "Do not declare correlation-based compromise from co-presence alone.",
        ),
    ),
)


# Registry-first fallback: exact-105 pattern_type → detection family, used only
# when the keyword matcher finds nothing (keyword matches keep priority so
# OT/PowerGrid-specific families are never displaced).
PATTERN_TYPE_FAMILY_FALLBACK: dict[str, str] = {
    "top_n_aggregation": "network_traffic_top_talkers",
    "ioc_correlation": "ioc_destination_match",
    "dns_beaconing_dga_behavior": "dns_beaconing_hunt",
    "new_or_unusual_source": "network_new_or_rare_behavior",
    "other_or_unclear": "network_new_or_rare_behavior",
    "threshold_anomaly": "network_threshold_anomaly",
    "suspicious_process_powershell": "endpoint_powershell_suspicious",
    "dlp_exfiltration": "network_data_exfil_volume",
    "lateral_movement": "lateral_movement_internal",
    "persistence_scheduled_task_service": "endpoint_persistence_schtask_service",
    "multi_signal_correlation": "network_multi_signal_review",
    "success_after_failure": "auth_success_after_failure",
    "notable_risk_lookup": "notable_risk_review",
    "data_source_health": "data_source_health_review",
    "threat_intel_enrichment": "ioc_destination_match",
    # asset_identity_context is deliberately unmapped: its enrichment-lookup row
    # (asset criticality / business owner) has no SPL answer; the listable
    # identity rows are caught by explicit keyword rules instead.
}


def match_detection_family(user_query: str) -> str | None:
    text = (user_query or "").strip()
    if not text:
        return None
    normalized = " ".join(text.lower().split())
    if re.search(r"\b(denied|blocked|drop|reject)\b", normalized) and (
        "ot" in normalized or "internet" in normalized or "egress" in normalized
    ):
        return "firewall_ot_egress_denied"
    if "vendor vpn" in normalized and "jump" in normalized:
        return "firewall_vendor_vpn_jump"
    if re.search(r"\bvpn\b", normalized) and re.search(r"\bcountr", normalized):
        if re.search(r"not\s+seen|unseen|new\s+countr|never\s+seen|not\s+seen\s+before", normalized):
            return "vpn_new_country_login"
    if (
        re.search(r"success", normalized)
        and re.search(r"fail", normalized)
        and re.search(r"\bafter\b|following|then|repeated", normalized)
    ):
        return "auth_success_after_failure"
    if re.search(r"\brdp\b|remote desktop|\b3389\b", normalized):
        return "firewall_it_ot_rdp"
    # Generic failed-login analytics route to the auth threshold family; only
    # HMI/substation/OT phrasing keeps the substation brute-force draft.
    if (
        re.search(r"failed\s+log|login\s+failure|authentication\s+failure", normalized)
        and not re.search(r"\bhmi\b|substation|control\s+room|scada", normalized)
        and not re.search(r"success", normalized)
        and not re.search(r"\b4740\b|lockout|locked", normalized)
    ):
        return "auth_failed_login_threshold"
    if re.search(r"added\s+to\s+(?:administrators|domain\s+admins)", normalized):
        return "windows_privileged_group_changes"
    if (
        re.search(r"privileged\s+(?:actions?|applications?|access|logon)", normalized)
        or re.search(r"accounts?\s+(?:were\s+)?(?:disabled|re-?enabled)", normalized)
        or re.search(r"non[-\s]?admin\s+workstations?", normalized)
    ):
        return "windows_identity_privileged_activity"
    if re.search(r"(?:alerts?|notables?)\s+.{0,40}(?:still\s+open|open\s+and\s+unresolved|unresolved)", normalized):
        return "notable_risk_review"
    if "smb" in normalized and re.search(r"\bot\b", normalized):
        return "firewall_ot_smb_lateral"
    if "smb" in normalized and re.search(
        r"\b(?:most|top|talkers?|highest|largest|busiest|volume)\b", normalized
    ):
        return "network_smb_top_talkers"
    best_id: str | None = None
    best_score = 0
    for family in DETECTION_FAMILIES:
        score = sum(1 for pattern in family.patterns if pattern.search(text))
        if score > best_score:
            best_score = score
            best_id = family.family_id
    if best_score < 2 and best_id not in {
        "windows_account_lockout",
        "sysmon_web_shell_spawn",
    }:
        if best_id == "windows_account_lockout" and re.search(r"\b4740\b", text, re.IGNORECASE):
            return best_id
        if best_id == "sysmon_web_shell_spawn" and re.search(
            r"(w3wp\.exe|apache\.exe).*(cmd\.exe|powershell\.exe|pwsh\.exe)", text, re.IGNORECASE
        ):
            return best_id
        return None
    return best_id


def _family_by_id(family_id: str) -> DetectionFamily | None:
    for family in DETECTION_FAMILIES:
        if family.family_id == family_id:
            return family
    return None


def _is_governed_spl_ready(spl_validation: dict[str, Any] | None) -> bool:
    if not isinstance(spl_validation, dict):
        return False
    return bool(spl_validation.get("approved") and spl_validation.get("normalized_spl"))


def _source_profile_missing(spl_validation: dict[str, Any] | None) -> bool:
    if not isinstance(spl_validation, dict):
        return False
    reject_reasons = {str(item) for item in spl_validation.get("reject_reasons") or []}
    if {"missing_index", "missing_sourcetype", "index_or_datamodel"} & reject_reasons:
        return True
    reason = str(
        spl_validation.get("review_required_reason")
        or spl_validation.get("llm_fallback_reason")
        or spl_validation.get("candidate_provider_reason")
        or ""
    )
    return reason == "spl_template_active_source_profile_missing"


def _governed_template_missing(spl_validation: dict[str, Any] | None) -> bool:
    if not isinstance(spl_validation, dict):
        return True
    reason = str(
        spl_validation.get("review_required_reason")
        or spl_validation.get("llm_fallback_reason")
        or spl_validation.get("candidate_provider_reason")
        or ""
    )
    template_status = str(spl_validation.get("spl_template_status") or "")
    if reason in {
        "spl_template_missing",
        "spl_template_unavailable_no_free_spl_fallback",
        "spl_template_planned_no_free_spl_fallback",
        "spl_template_unknown_no_free_spl_fallback",
        "spl_template_not_allowed_by_enrichment",
        "spl_template_sop_only_no_active_investigation_support",
    }:
        return True
    if template_status in {"missing", "unavailable", "planned", "unknown", "sop_only"}:
        return True
    if spl_validation.get("llm_fallback_status") == "clarification_required":
        return True
    return not _is_governed_spl_ready(spl_validation)


def build_draft_preview(
    user_query: str,
    *,
    spl_validation: dict[str, Any] | None = None,
    family_id: str | None = None,
    unsafe_enforcement: bool = False,
    pattern_type: str | None = None,
) -> dict[str, Any] | None:
    """Build a lab-only draft preview dict when the flag is enabled and query matches.

    Family resolution order: explicit family_id, then the keyword matcher, then the
    exact-105 registry pattern_type fallback (registry authority for questions the
    keyword matcher does not know).
    """
    if not settings.ai_soc_spl_draft_preview_enabled:
        return None
    # Unsafe enforcement intent overrides all SPL/search intent: never surface a
    # draft (investigation or otherwise) when the request is to block/contain.
    if unsafe_enforcement:
        return None
    if _is_governed_spl_ready(spl_validation):
        return None
    resolved_family = family_id or match_detection_family(user_query)
    if resolved_family is None and pattern_type:
        resolved_family = PATTERN_TYPE_FAMILY_FALLBACK.get(pattern_type)
    family = _family_by_id(resolved_family) if resolved_family else None
    if family is None:
        return None

    draft_spl = family.draft_spl
    assumptions_text = " ".join(family.assumptions)
    quality = evaluate_draft_quality(
        draft_spl,
        extra_text=assumptions_text,
        detection_family=family.family_id,
    )
    quality_payload = quality.to_dict()
    validation = validate_spl(draft_spl)
    validator_status = "approved" if validation.get("approved") else "blocked"
    presentation = family_presentation(family.family_id)
    return {
        "draft_spl": draft_spl,
        "draft_status": DRAFT_STATUS,
        "draft_source": DRAFT_SOURCE,
        "quality_standard": STANDARD_ID,
        "detection_family": family.family_id,
        "family_title": presentation["title"],
        "review_type": presentation["review_type"],
        "review_type_display": presentation["review_type_display"],
        "assumptions": list(family.assumptions),
        "required_log_fields": list(family.required_log_fields),
        "required_source_profile_fields": list(family.required_source_profile_fields),
        "required_source_fields": list(family.required_source_fields),
        "investigation_checklist": list(family.investigation_checklist),
        "scope_notice": family.scope_notice,
        "source_profile_missing": _source_profile_missing(spl_validation),
        "governed_template_missing": _governed_template_missing(spl_validation),
        "validator_status": validator_status,
        "validator_reject_reasons": list(validation.get("reject_reasons") or []),
        "quality_status": quality_payload["quality_status"],
        "hard_fail_count": quality_payload["hard_fail_count"],
        "warning_count": quality_payload["warning_count"],
        "advisory_count": quality_payload["advisory_count"],
        "quality_findings": quality_payload["findings"],
        "draft_lint_status": "passed" if quality.hard_fail_count == 0 else "failed",
        "draft_lint_violations": quality.violation_ids(),
        "draft_quality": quality_payload,
        "review_required": True,
        "execution_enabled": False,
        "execution_eligible": False,
        "governed": False,
        "catalog_approved": False,
        "warning": DRAFT_WARNING,
        "not_catalog_approved_notice": "Not catalog-approved / review required.",
    }


def maybe_attach_draft_preview_message(
    base_message: str,
    draft_preview: dict[str, Any] | None,
) -> str:
    """Return base message unchanged — draft preview warnings are consolidated upstream."""
    return base_message


def build_draft_preview_analyst_message(draft_preview: dict[str, Any] | None) -> str:
    """Single analyst-facing warning block with optional checklist and scope notice."""
    if not draft_preview:
        return DRAFT_PREVIEW_STATUS_MESSAGE
    parts: list[str] = []
    checklist = draft_preview.get("investigation_checklist") or []
    if checklist:
        parts.append("SOC review checklist:")
        parts.extend(f"- {item}" for item in checklist)
    scope = draft_preview.get("scope_notice")
    if isinstance(scope, str) and scope.strip():
        parts.append(scope.strip())
    parts.append(str(draft_preview.get("warning") or DRAFT_PREVIEW_STATUS_MESSAGE))
    return "\n\n".join(parts)
