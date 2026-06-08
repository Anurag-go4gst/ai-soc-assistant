"""Lab-only SPL draft preview — deterministic patterns, never governed or executable."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.config import settings
from app.safeguards.spl_validator import validate_spl

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
  (match(TargetUserName, "(?i)domain\\s+admins|enterprise\\s+admins|administrators"))
| rename MemberName as added_user, SubjectUserName as actor, TargetUserName as group_name
| stats count as add_count values(added_user) as added_users earliest(_time) as first_seen latest(_time) as last_seen by actor group_name
| where add_count>3
| table actor group_name add_count added_users first_seen last_seen
| sort - add_count
| head 100
""",
        assumptions=(
            "Windows Security EventCodes 4728/4732/4756 represent global/universal/local group member additions.",
            "Privileged groups include Domain Admins, Enterprise Admins, and Administrators.",
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
| rename TargetUserName as target_user, ComputerName as lockout_computer
| stats count as lockout_count values(lockout_computer) as computers earliest(_time) as first_seen latest(_time) as last_seen by target_user
| table target_user lockout_count computers first_seen last_seen
| sort - lockout_count
| head 100
""",
        assumptions=(
            "EventCode 4740 indicates a user account was locked out.",
            "ComputerName is treated as the system where the lockout was observed.",
            "Index and sourcetype are placeholders — confirm against your Windows security log source profile.",
        ),
        required_source_fields=(
            "index",
            "sourcetype",
            "EventCode",
            "TargetUserName",
            "ComputerName",
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
  (ParentImage="*\\w3wp.exe" OR ParentImage="*\\apache.exe" OR ParentImage="*\\httpd.exe" OR ParentImage="*\\nginx.exe")
  (Image="*\\cmd.exe" OR Image="*\\powershell.exe")
| rename ParentImage as parent_process, Image as child_process, User as user, Computer as host
| table _time host user parent_process child_process CommandLine
| sort - _time
| head 100
""",
        assumptions=(
            "Sysmon EventCode 1 (Process Create) is used for parent/child process lineage.",
            "Web server parent processes include w3wp.exe, apache.exe, httpd.exe, and nginx.exe as examples.",
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
  (protocol="DNP3" OR protocol="Modbus" OR match(dnp3_function, "(?i)write") OR match(modbus_function, "(?i)write"))
  NOT (src_ip=<engineering_workstation_ip> OR src=<engineering_workstation_ip>)
| rename src_ip as source_ip, dest_ip as destination_ip, protocol as protocol_name, action as command_action
| table _time source_ip destination_ip protocol_name command_action dest_port payload_summary
| sort - _time
| head 100
""",
        assumptions=(
            "SCADA firewall logs expose protocol, action/function, and source/destination IPs.",
            "Engineering workstation IP is a placeholder allowlist entry.",
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
| rename src_ip as source_ip, dest_ip as destination_ip, src_zone as source_zone, dest_zone as destination_zone, dest_port as destination_port, app as application
| stats count as connection_count values(dest_port) as ports earliest(_time) as first_seen latest(_time) as last_seen by source_ip destination_ip application
| table source_ip destination_ip application connection_count ports first_seen last_seen
| sort - connection_count
| head 100
""",
        assumptions=(
            "ESP firewall zones label corporate IT and OT control center segments.",
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
  (match(app, "(?i)hmi|portal") OR dest_category="HMI" OR dest_category="OT")
| bin _time span=5m
| stats count as failed_attempts dc(user) as distinct_users values(user) as attempted_users by _time src_ip
| where failed_attempts>10
| table _time src_ip failed_attempts distinct_users attempted_users
| sort - failed_attempts
| head 100
""",
        assumptions=(
            "Authentication failure events are bucketed in 5-minute windows.",
            "Threshold of more than 10 failures per window is illustrative; tune per environment.",
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
        # Require stronger match for broad families; allow single strong signals for narrow ones.
        if best_id == "windows_account_lockout" and re.search(r"\b4740\b", text, re.IGNORECASE):
            return best_id
        if best_id == "sysmon_web_shell_spawn" and re.search(
            r"(w3wp\.exe|apache\.exe).*(cmd\.exe|powershell\.exe)", text, re.IGNORECASE
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

    validation = validate_spl(family.draft_spl)
    validator_status = "approved" if validation.get("approved") else "blocked"
    return {
        "draft_spl": family.draft_spl,
        "draft_status": DRAFT_STATUS,
        "draft_source": DRAFT_SOURCE,
        "detection_family": family.family_id,
        "assumptions": list(family.assumptions),
        "required_source_fields": list(family.required_source_fields),
        "source_profile_missing": _source_profile_missing(spl_validation),
        "governed_template_missing": _governed_template_missing(spl_validation),
        "validator_status": validator_status,
        "validator_reject_reasons": list(validation.get("reject_reasons") or []),
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
