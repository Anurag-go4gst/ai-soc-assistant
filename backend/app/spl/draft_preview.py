"""Lab-only SPL draft preview — deterministic patterns, never governed or executable."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.config import settings
from app.safeguards.spl_validator import validate_spl
from app.spl.draft_quality import STANDARD_ID, evaluate_draft_quality

DRAFT_WARNING = (
    "Draft SPL preview only. Not governed. Not approved. Do not execute without SOC review."
)
DRAFT_PREVIEW_STATUS_MESSAGE = (
    "Governed SPL is not available/ready. A lab-only Draft SPL preview is shown for SOC review. "
    "It is not governed, not approved, and must not be executed. "
    "HIL approval is required before any future execution path."
)
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


@dataclass(frozen=True)
class DetectionFamily:
    family_id: str
    patterns: tuple[re.Pattern[str], ...]
    draft_spl: str
    assumptions: tuple[str, ...]
    required_source_fields: tuple[str, ...]


def _family(
    family_id: str,
    *,
    pattern_texts: tuple[str, ...],
    draft_spl: str,
    assumptions: tuple[str, ...],
    required_source_fields: tuple[str, ...],
) -> DetectionFamily:
    return DetectionFamily(
        family_id=family_id,
        patterns=tuple(re.compile(text, re.IGNORECASE) for text in pattern_texts),
        draft_spl=draft_spl.strip(),
        assumptions=assumptions,
        required_source_fields=required_source_fields,
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
        required_source_fields=(
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
        required_source_fields=(
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
        required_source_fields=(
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
        required_source_fields=(
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
        "esp_it_to_ot_connection",
        pattern_texts=(
            r"electronic\s+security\s+perimeter",
            r"\besp\b",
            r"corporate\s+it",
            r"\bot\b",
            r"control\s+center",
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
  AND (
    session_state_norm IN ("established", "built", "connected", "success")
    OR like(session_state_norm, "%establish%")
    OR like(session_state_norm, "%built%")
    OR like(session_state_norm, "%connected%")
  )
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
            "Established connections require session_state_norm establish/built/connected/success — blank session state is not treated as established.",
            "If session_state or connection_state is missing from your sourcetype, map it during source-profile review before relying on this draft.",
            "values() preserves src_zone, dest_zone, rule, app, protocol, dest_port, action, and session_state through stats.",
        ),
        required_source_fields=(
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
            "corporate_it_cidr",
            "ot_control_center_cidr",
            "_time",
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
        required_source_fields=(
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
)


def match_detection_family(user_query: str) -> str | None:
    text = (user_query or "").strip()
    if not text:
        return None
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
) -> dict[str, Any] | None:
    """Build a lab-only draft preview dict when the flag is enabled and query matches."""
    if not settings.ai_soc_spl_draft_preview_enabled:
        return None
    if _is_governed_spl_ready(spl_validation):
        return None
    resolved_family = family_id or match_detection_family(user_query)
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
    return {
        "draft_spl": draft_spl,
        "draft_status": DRAFT_STATUS,
        "draft_source": DRAFT_SOURCE,
        "quality_standard": STANDARD_ID,
        "detection_family": family.family_id,
        "assumptions": list(family.assumptions),
        "required_source_fields": list(family.required_source_fields),
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
    if not draft_preview:
        return base_message
    notice = str(draft_preview.get("not_catalog_approved_notice") or "")
    warning = str(draft_preview.get("warning") or DRAFT_WARNING)
    family = str(draft_preview.get("detection_family") or "unknown")
    suffix = (
        f"\n\nDraft SPL Preview ({family}): {notice} {warning}"
        " Placeholder index/sourcetype values must be confirmed before any review or execution."
    )
    if suffix.strip() in base_message:
        return base_message
    return f"{base_message.rstrip()}{suffix}"
