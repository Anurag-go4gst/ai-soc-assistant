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
  (EventCode=4728 OR EventCode=4732 OR EventCode=4756)
  (
    like(lower(coalesce(TargetUserName, target_user_name, group_name, "")), "%domain admins%")
    OR like(lower(coalesce(TargetUserName, target_user_name, group_name, "")), "%enterprise admins%")
    OR like(lower(coalesce(TargetUserName, target_user_name, group_name, "")), "%administrators%")
  )
| eval actor=coalesce(SubjectUserName, subject_user_name, user, "")
| eval added_user=coalesce(MemberName, member_name, MemberSid, "")
| eval group_name=coalesce(TargetUserName, target_user_name, group, "")
| eval event_time=_time
| stats count as add_count values(added_user) as added_users min(event_time) as first_seen_epoch max(event_time) as last_seen_epoch by actor group_name
| eval first_seen=strftime(first_seen_epoch, "%F %T")
| eval last_seen=strftime(last_seen_epoch, "%F %T")
| fields - first_seen_epoch last_seen_epoch
| where add_count>3
| table actor group_name add_count added_users first_seen last_seen
| sort - add_count
| head 100
""",
        assumptions=(
            "Windows Security EventCodes 4728/4732/4756 represent global/universal/local group member additions.",
            "Privileged groups include Domain Admins, Enterprise Admins, and Administrators (substring match via like()).",
            "Actor/added user/group fields use coalesce() across common Windows Security aliases.",
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
| eval target_user=coalesce(TargetUserName, target_user_name, user, "")
| eval caller_host=coalesce(Caller_Computer_Name, CallerComputerName, caller_computer_name, src_nt_host, Workstation_Name, ComputerName, "")
| eval lockout_source=caller_host
| eval lockout_time=_time
| stats count as lockout_count values(caller_host) as caller_hosts min(lockout_time) as first_seen_epoch max(lockout_time) as last_seen_epoch by target_user
| eval first_seen=strftime(first_seen_epoch, "%F %T")
| eval last_seen=strftime(last_seen_epoch, "%F %T")
| fields - first_seen_epoch last_seen_epoch
| table target_user lockout_count caller_hosts lockout_source first_seen last_seen
| sort - lockout_count
| head 100
""",
        assumptions=(
            "EventCode 4740 indicates a user account was locked out.",
            "Caller/source host uses coalesce(Caller_Computer_Name, CallerComputerName, caller_computer_name, src_nt_host, Workstation_Name, ComputerName).",
            "lockout_source reflects the forensic caller host, not only the reporting computer field.",
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
| eval parent_image=lower(coalesce(ParentImage, parent_image, ParentProcessName, ""))
| eval child_image=lower(coalesce(Image, image, ProcessName, ""))
| eval command_line=coalesce(CommandLine, command_line, "")
| eval host=coalesce(Computer, host, dest, "")
| eval user=coalesce(User, user, user_name, "")
| where (
    like(parent_image, "%\\\\w3wp.exe")
    OR like(parent_image, "%\\\\apache.exe")
    OR like(parent_image, "%\\\\httpd.exe")
    OR like(parent_image, "%\\\\tomcat.exe")
    OR like(parent_image, "%\\\\nginx.exe")
  )
  AND (
    like(child_image, "%\\\\cmd.exe")
    OR like(child_image, "%\\\\powershell.exe")
    OR like(child_image, "%\\\\pwsh.exe")
  )
| eval event_epoch=_time
| table event_epoch host user parent_image child_image command_line
| eval spawn_time=strftime(event_epoch, "%F %T")
| sort - spawn_time
| head 100
""",
        assumptions=(
            "Sysmon EventCode 1 (Process Create) is used for parent/child process lineage.",
            "Web server parents include w3wp.exe, apache.exe, httpd.exe, tomcat.exe, and nginx.exe.",
            "Shell children include cmd.exe, powershell.exe, and pwsh.exe; paths use escaped backslashes with like().",
            "Process image fields use coalesce() across ParentImage/Image aliases.",
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
search index=<scada_firewall_index> sourcetype=<scada_firewall_sourcetype> earliest=-24h latest=now
  (protocol="DNP3" OR protocol="Modbus" OR protocol="dnp3" OR protocol="modbus")
| eval protocol_name=lower(coalesce(protocol, proto, protocol_name, ""))
| eval dnp3_fn=lower(coalesce(dnp3_function, dnp3_func, ""))
| eval modbus_fn=lower(coalesce(modbus_function, modbus_func, ""))
| eval command_action=lower(coalesce(action, command, event_action, ""))
| eval source_ip=coalesce(src_ip, src, source, "")
| eval destination_ip=coalesce(dest_ip, dest, destination, "")
| where (
    like(dnp3_fn, "%write%")
    OR like(modbus_fn, "%write%")
    OR like(command_action, "%write%")
    OR like(command_action, "%modify%")
  )
  AND NOT cidrmatch("<engineering_workstation_cidr>", source_ip)
| eval event_epoch=_time
| eval event_time_readable=strftime(event_epoch, "%F %T")
| table event_time_readable source_ip destination_ip protocol_name command_action dest_port payload_summary
| sort - event_time_readable
| head 100
""",
        assumptions=(
            "SCADA firewall logs expose protocol, action/function, and source/destination IPs.",
            "Shift-left protocol filter in base search; write/modify narrowed after coalesce().",
            "Engineering workstation allowlist uses cidrmatch() with placeholder CIDR.",
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
search index=<esp_firewall_index> sourcetype=<esp_firewall_sourcetype> earliest=-24h latest=now
  src_zone=<corporate_it_zone> dest_zone=<ot_control_center_zone> action=allowed
| eval source_ip=coalesce(src_ip, src, source, "")
| eval destination_ip=coalesce(dest_ip, dest, destination, "")
| eval source_zone=coalesce(src_zone, source_zone, "")
| eval destination_zone=coalesce(dest_zone, destination_zone, "")
| eval destination_port=coalesce(dest_port, destination_port, "")
| eval application=coalesce(app, application, "")
| eval event_time=_time
| stats count as connection_count values(destination_port) as ports min(event_time) as first_seen_epoch max(event_time) as last_seen_epoch by source_ip destination_ip application
| eval first_seen=strftime(first_seen_epoch, "%F %T")
| eval last_seen=strftime(last_seen_epoch, "%F %T")
| fields - first_seen_epoch last_seen_epoch
| table source_ip destination_ip application connection_count ports first_seen last_seen
| sort - connection_count
| head 100
""",
        assumptions=(
            "ESP firewall zones label corporate IT and OT control center segments.",
            "Source/destination IPs and zones use coalesce() across common firewall aliases.",
            "Only successful/allowed connections are surfaced; denied flows may need a separate query.",
            "Zone names and field extractions are placeholders — confirm against your ESP source profile.",
        ),
        required_source_fields=(
            "index",
            "sourcetype",
            "src_zone",
            "dest_zone",
            "src_ip",
            "dest_ip",
            "action",
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
search index=<substation_index> sourcetype=<hmi_or_os_auth_sourcetype> earliest=-24h latest=now action=failure
| eval action_norm=lower(coalesce(action, status, result, ""))
| eval user_name=coalesce(user, username, src_user, "")
| eval source_ip=coalesce(src_ip, src, source, "")
| eval app_name=lower(coalesce(app, application, service, ""))
| eval dest_category_norm=upper(coalesce(dest_category, category, ""))
| where action_norm="failure"
  AND (
    like(app_name, "%hmi%")
    OR like(app_name, "%portal%")
    OR dest_category_norm="HMI"
    OR dest_category_norm="OT"
  )
| bin _time span=5m
| stats count as failed_attempts dc(user_name) as distinct_users values(user_name) as attempted_users min(_time) as window_start_epoch by _time source_ip
| eval window_start=strftime(window_start_epoch, "%F %T")
| fields - window_start_epoch
| where failed_attempts>10
| table window_start source_ip failed_attempts distinct_users attempted_users
| sort - failed_attempts
| head 100
""",
        assumptions=(
            "Authentication failure events are bucketed in 5-minute windows; readable time appears after bin/stats.",
            "Threshold of more than 10 failures per window is illustrative; tune per environment.",
            "User, source, and app fields use coalesce(); HMI/portal matching uses like() on app name.",
            "HMI/OS portal field names vary — confirm dest_category/app mappings for substation assets.",
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
    quality = evaluate_draft_quality(draft_spl, extra_text=assumptions_text)
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
