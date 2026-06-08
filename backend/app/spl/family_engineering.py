"""SOC-STD-SPL-001 family-specific SPL engineering instructions (lab draft + LLM fallback)."""

from __future__ import annotations

UNIVERSAL_ENGINEERING_BLOCK = """
Universal SPL engineering standards (SOC-STD-SPL-001 — all families):

U1. Line-1 index-filter / shift-left
- Static filters known from the request must appear in the base search before the first pipe when possible:
  EventCode, action, status, protocol, sourcetype, known raw keywords.
- Examples: EventCode=4740; EventCode=1; EventCode=4728 OR 4732 OR 4756; action=allowed; (failure OR fail OR denied).
- Do not force normalized coalesce() conditions onto line 1.
- Delaying obvious static filters until after the first pipe is a lint finding.

U2. Native _time rule
- Do not use strftime(_time, ...) before bin/stats/streamstats/timechart.
- Keep _time numeric for aggregation and windowing.
- Apply strftime only at final presentation (after aggregation or on epoch aliases).
- If earliest(_time) or latest(_time) is used in stats, add readable first_seen/last_seen via strftime after stats.

U3. Stats inclusion rule
- Any field required in the final table after stats/streamstats must be:
  (a) in the by clause, or (b) preserved via values(), latest(), earliest(), count(), dc(), list(), etc.
- Especially preserve: src_zone, dest_zone, rule, app, caller_host, command_line, parent_image, child_image,
  target_user, added_user, group_name (or their *_norm aliases).
""".strip()

FAMILY_ENGINEERING_BLOCKS: dict[str, str] = {
    "windows_privileged_group_changes": """
1. Privileged Group Changes / Active Directory
- Base search must shift-left:
  index=<windows_index> sourcetype=<windows_security_sourcetype> (EventCode=4728 OR EventCode=4732 OR EventCode=4756)
- Optional broad raw keyword may include *admin*, but final group logic must happen after normalization.
- Normalize:
  group_norm = lower(coalesce(TargetUserName, group_name, group, Group_Name, ""))
  actor_norm = lower(coalesce(SubjectUserName, user, Account_Name, ""))
  added_user_norm = lower(coalesce(MemberName, member, Target_Account_Name, ""))
- Match groups: domain admins, enterprise admins, administrators, privileged/admin groups where configured.
- Suppress machine accounts: NOT like(actor_norm, "%$")
- Aggregate by actor_norm, added_user_norm, group_norm.
- Use earliest(_time)/latest(_time) in stats, then strftime at the end.
""".strip(),
    "windows_account_lockout": """
2. Windows Account Lockout / Event 4740
- Base search:
  index=<windows_index> sourcetype=<windows_security_sourcetype> EventCode=4740
- Normalize:
  target_user_norm = lower(coalesce(TargetUserName, user, target_user_name, Account_Name, "unknown"))
  caller_host_norm = lower(coalesce(Caller_Computer_Name, CallerComputerName, caller_computer_name, src_nt_host, Workstation_Name, "unknown"))
- Do not use only ComputerName as the lockout source because it may be the DC/collector.
- Use values(caller_host_norm) in stats.
- Preserve earliest/latest numeric timestamps, format only at the end.
""".strip(),
    "sysmon_web_shell_spawn": """
3. Sysmon Web Server Spawning Shell
- Base search:
  index=<endpoint_index> sourcetype=XmlWinEventLog:Microsoft-Windows-Sysmon/Operational EventCode=1
- Normalize:
  parent_image_norm = lower(coalesce(ParentImage, ParentProcessName, parent_process_path, ""))
  child_image_norm = lower(coalesce(Image, ProcessName, process_path, ""))
  command_line_norm = coalesce(CommandLine, process_command_line, cmdline, "")
- Web parents: w3wp.exe, apache.exe, httpd.exe, tomcat.exe, nginx.exe
- Shell children: cmd.exe, powershell.exe, pwsh.exe
- Use escaped Windows paths: like(parent_image_norm, "%\\\\w3wp.exe") like(child_image_norm, "%\\\\powershell.exe")
- Sort by native _time, then add spawn_time=strftime(_time, "%Y-%m-%d %H:%M:%S") before table.
""".strip(),
    "scada_dnp3_modbus_write": """
4. SCADA DNP3/Modbus Write/Modify
- Base search:
  index=<scada_firewall_index> sourcetype=<scada_firewall_sourcetype> (*dnp3* OR *modbus*)
- Normalize:
  protocol_norm = lower(coalesce(protocol, proto, protocol_name, ""))
  command_norm = lower(coalesce(action, command, event_action, function, function_code, ""))
  src_ip_norm = coalesce(src_ip, src, source, source_ip, "")
  dest_ip_norm = coalesce(dest_ip, dest, destination, dest_ip, "")
- Match protocol dnp3/modbus and write/modify/control actions.
- Exclude engineering workstation/network using cidrmatch("<engineering_workstation_cidr>", src_ip_norm) or an allowlist placeholder.
- Do not invent actual CIDRs; use placeholders and assumptions.
""".strip(),
    "esp_it_to_ot_connection": """
5. ESP IT to OT Boundary
- Base search:
  index=<esp_firewall_index> sourcetype=<esp_firewall_sourcetype> action=allowed
- Optional raw hints: (*it* AND *ot*) only as a broad hint if useful, not as final authority.
- Normalize:
  src_zone_norm = lower(coalesce(src_zone, source_zone, zone_src, ""))
  dest_zone_norm = lower(coalesce(dest_zone, destination_zone, zone_dest, ""))
  src_ip_norm = coalesce(src_ip, src, source, "")
  dest_ip_norm = coalesce(dest_ip, dest, destination, "")
  app_norm = lower(coalesce(app, application, service, protocol, ""))
- Confirm corporate IT to OT using zones and/or cidrmatch placeholders.
- Preserve values(src_zone_norm), values(dest_zone_norm), values(rule), values(app_norm) in stats.
""".strip(),
    "substation_hmi_brute_force": """
6. Substation OS/HMI Brute Force
- Base search:
  index=<substation_index> sourcetype=<hmi_or_os_auth_sourcetype> (failure OR fail OR denied)
- Normalize:
  src_ip_norm = coalesce(src_ip, src, source, "")
  user_norm = lower(coalesce(user, username, src_user, "unknown"))
  dest_norm = lower(coalesce(dest, host, asset, target, "unknown"))
  app_norm = lower(coalesce(app, application, portal, service, ""))
  action_norm = lower(coalesce(action, status, result, event_action, ""))
- Target HMI/portal/OT: like(app_norm, "%hmi%") OR like(app_norm, "%portal%") OR like(dest_norm, "%hmi%") OR like(dest_norm, "%ot%")
- Do not use broken multiline regex such as "(?i)hmi\\n| portal".
- Use rolling window:
  | sort 0 + _time
  | streamstats time_window=5m count as fail_count dc(user_norm) as distinct_users values(user_norm) as targeted_users by src_ip_norm
  | where fail_count > 10
- Format readable time at the end.
""".strip(),
}


def universal_engineering_prompt() -> str:
    """Universal SOC-STD-SPL-001 engineering rules for LLM SPL fallback."""
    return UNIVERSAL_ENGINEERING_BLOCK


def family_engineering_prompt() -> str:
    """Concatenated family-specific engineering blocks for LLM SPL fallback."""
    return "Family-specific SPL engineering (apply when detection_family matches):\n\n" + "\n\n".join(
        FAMILY_ENGINEERING_BLOCKS.values()
    )


def full_engineering_prompt() -> str:
    """Universal + family-specific engineering instructions."""
    return f"{UNIVERSAL_ENGINEERING_BLOCK}\n\n{family_engineering_prompt()}"
