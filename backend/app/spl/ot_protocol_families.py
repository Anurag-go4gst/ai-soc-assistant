"""OT-protocol lab draft families — tier-1 SPL, review-only, never executable.

Upgrades the out-of-registry OT/grid hunts (Google-25 testing ground) from guided
hypotheses to a concrete review-only SPL draft. Same governance as the Cisco Wave 2
families: aggregated stats + head, time-bound, placeholder index/sourcetype slots
resolved from the Environment KB, MCP execution stays off. MITRE anchors are
candidate-only (ATT&CK = behaviour, confirmed only with evidence).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.spl.cisco_draft_families import _base_assumptions, _tier1_stats_spl

if TYPE_CHECKING:
    from app.spl.draft_preview import DetectionFamily


def ot_protocol_detection_families() -> tuple[DetectionFamily, ...]:
    from app.spl.draft_preview import _family

    return (
        _family(
            "ot_scada_default_credentials",
            pattern_texts=(
                r"default\s+(?:or\s+vendor\s+)?credential",
                r"vendor\s+credential",
                r"known\s+default",
                r"\bscada\b.{0,40}(?:login|credential|logon)",
            ),
            draft_spl=_tier1_stats_spl(
                "ot_auth_index",
                "ot_auth_sourcetype",
                filter_clause="(*login* OR *logon* OR *auth*)",
                eval_lines=(
                    'eval user_norm=lower(coalesce(user, username, account, "unknown"))',
                    'eval device_norm=coalesce(dest, host, dvc, "unknown")',
                ),
                where_clause=(
                    'like(user_norm, "%admin%") OR like(user_norm, "%root%") '
                    'OR like(user_norm, "%operator%") OR like(user_norm, "%vendor%") '
                    'OR like(user_norm, "%default%") OR like(user_norm, "%service%")'
                ),
                stats_by="user_norm device_norm",
            ),
            assumptions=_base_assumptions(
                "Heuristic surface of logins by common default/vendor account names on SCADA hosts.",
            ),
            required_log_fields=("index", "sourcetype", "user", "dest", "_time"),
            required_source_profile_fields=("ot_auth_index", "ot_auth_sourcetype"),
            investigation_checklist=(
                "Compare flagged accounts against the vendor/default-credential inventory (lookup pending).",
                "Limitation: name-heuristic only until an authoritative default-account lookup is onboarded.",
                "MITRE (candidate, unconfirmed): T1078.001 Default Accounts — confirm only with successful-auth evidence.",
            ),
        ),
        _family(
            "ot_modbus_nonstandard_port",
            pattern_texts=(
                r"\bmodbus\b",
                r"non[-\s]?standard\s+port",
                r"\b502\b",
                r"port.{0,20}other\s+than",
            ),
            draft_spl=_tier1_stats_spl(
                "ot_network_index",
                "ot_modbus_sourcetype",
                filter_clause="(*modbus* OR app=modbus OR protocol=modbus)",
                eval_lines=(
                    'eval src_norm=coalesce(src_ip, src, source, "unknown")',
                    'eval dest_norm=coalesce(dest_ip, dest, destination, "unknown")',
                    'eval port_norm=coalesce(dest_port, port, destination_port, "0")',
                ),
                where_clause='NOT port_norm="502"',
                stats_by="src_norm dest_norm port_norm",
            ),
            assumptions=_base_assumptions(
                "Surfaces Modbus sessions on ports other than the standard 502.",
            ),
            required_log_fields=("index", "sourcetype", "src_ip", "dest_ip", "dest_port", "_time"),
            required_source_profile_fields=("ot_network_index", "ot_modbus_sourcetype"),
            investigation_checklist=(
                "Confirm whether any non-502 Modbus port is an approved gateway/relay before escalation.",
                "Limitation: protocol tag depends on DPI/sourcetype fidelity; raw TCP without app tag may be missed.",
                "MITRE (candidate, unconfirmed): T0830/T0885 (ICS) — non-standard control-protocol port use.",
            ),
        ),
        _family(
            "ot_ami_firmware_anomaly",
            pattern_texts=(
                r"smart\s+meter",
                r"\bami\b",
                r"firmware",
                r"(?:outdated|unauthorized).{0,20}firmware",
            ),
            draft_spl=_tier1_stats_spl(
                "ot_asset_index",
                "ot_meter_sourcetype",
                filter_clause="(*firmware* OR *meter* OR *ami*)",
                eval_lines=(
                    'eval device_norm=coalesce(device_name, host, asset, "unknown")',
                    'eval fw_norm=lower(coalesce(firmware_version, fw_version, version, "unknown"))',
                ),
                stats_by="device_norm fw_norm",
                stats_fields="count as event_count values(fw_norm) as firmware_versions",
                table_fields="device_norm fw_norm firmware_versions event_count",
            ),
            assumptions=_base_assumptions(
                "Inventories observed AMI/smart-meter firmware versions for drift review.",
            ),
            required_log_fields=("index", "sourcetype", "device_name", "firmware_version", "_time"),
            required_source_profile_fields=("ot_asset_index", "ot_meter_sourcetype"),
            investigation_checklist=(
                "Compare observed firmware versions against the approved baseline per meter model.",
                "Limitation: 'unauthorized' needs an approved-firmware baseline (lookup pending).",
                "MITRE (candidate, unconfirmed): T0857 System Firmware (ICS) — confirm only with a change/anomaly signal.",
            ),
        ),
        _family(
            "ot_rtu_connection_drops",
            pattern_texts=(
                r"\brtu\b",
                r"connection\s+drops?",
                r"(?:drop\s+frequency|frequency\s+of.{0,20}drops?)",
                r"control\s+cent(?:er|re)",
            ),
            draft_spl=_tier1_stats_spl(
                "ot_network_index",
                "ot_scada_sourcetype",
                filter_clause="(*disconnect* OR *timeout* OR *drop* OR *link_down* OR status=down)",
                eval_lines=(
                    'eval rtu_norm=coalesce(device_name, host, src, "unknown")',
                    'eval event_norm=lower(coalesce(event, status, message, "drop"))',
                ),
                where_clause='like(event_norm, "%drop%") OR like(event_norm, "%disconnect%") OR like(event_norm, "%down%") OR like(event_norm, "%timeout%")',
                stats_by="rtu_norm",
                stats_fields="count as drop_count",
                table_fields="rtu_norm drop_count",
            ),
            assumptions=_base_assumptions(
                "Counts RTU link-drop/disconnect events per device to the control center.",
            ),
            required_log_fields=("index", "sourcetype", "device_name", "status", "_time"),
            required_source_profile_fields=("ot_network_index", "ot_scada_sourcetype"),
            investigation_checklist=(
                "Correlate drop spikes with link maintenance, RF/comms outages, or substation power events.",
                "Limitation: drop semantics vary by vendor; tune event/status field mapping per deployment.",
                "MITRE (candidate, unconfirmed): T0815 Denial of Service (ICS) — only if drops are adversary-driven.",
            ),
        ),
        _family(
            "ot_dnp3_function_code",
            pattern_texts=(
                r"\bdnp\s?3\b",
                r"function\s+code",
                r"distribution\s+rtus?",
                r"unusual.{0,20}function",
            ),
            draft_spl=_tier1_stats_spl(
                "ot_network_index",
                "ot_dnp3_sourcetype",
                filter_clause="(*dnp3* OR app=dnp3 OR protocol=dnp3)",
                eval_lines=(
                    'eval src_norm=coalesce(src_ip, src, "unknown")',
                    'eval dest_norm=coalesce(dest_ip, dest, "unknown")',
                    'eval fc_norm=coalesce(function_code, dnp3_function, fc, "unknown")',
                ),
                stats_by="src_norm dest_norm fc_norm",
                stats_fields="count as event_count values(fc_norm) as function_codes",
                table_fields="src_norm dest_norm fc_norm function_codes event_count",
            ),
            assumptions=_base_assumptions(
                "Profiles DNP3 function codes per src/dest for outlier review against expected control verbs.",
            ),
            required_log_fields=("index", "sourcetype", "src_ip", "dest_ip", "function_code", "_time"),
            required_source_profile_fields=("ot_network_index", "ot_dnp3_sourcetype"),
            investigation_checklist=(
                "Flag write/control function codes (e.g. operate/direct-operate) from unexpected sources.",
                "Limitation: 'unusual' is relative to a per-link baseline that this draft does not yet hold.",
                "MITRE (candidate, unconfirmed): T0855 Unauthorized Command Message (ICS) — confirm with command context.",
            ),
        ),
        _family(
            "ot_plc_mode_change",
            pattern_texts=(
                r"\bplc",
                r"run\s+mode",
                r"(?:program\s+mode|stop\s+mode|stop\s+or\s+program)",
                r"mode\s+chang|switched\s+from.{0,20}mode",
            ),
            draft_spl=_tier1_stats_spl(
                "ot_network_index",
                "ot_scada_sourcetype",
                filter_clause="(*mode* OR *program* OR *stop* OR *run*)",
                eval_lines=(
                    'eval plc_norm=coalesce(device_name, host, dest, "unknown")',
                    'eval mode_norm=lower(coalesce(mode, plc_mode, state, message, "unknown"))',
                    'eval actor_norm=lower(coalesce(user, src, "unknown"))',
                ),
                where_clause='like(mode_norm, "%stop%") OR like(mode_norm, "%program%") OR like(mode_norm, "%remote%")',
                stats_by="plc_norm mode_norm actor_norm",
            ),
            assumptions=_base_assumptions(
                "Surfaces PLC run→stop/program mode transitions for change review.",
            ),
            required_log_fields=("index", "sourcetype", "device_name", "mode", "_time"),
            required_source_profile_fields=("ot_network_index", "ot_scada_sourcetype"),
            investigation_checklist=(
                "Confirm each mode change against an authorized engineering change window/ticket.",
                "Limitation: mode field naming is vendor-specific; map state/mode fields per PLC platform.",
                "MITRE (candidate, unconfirmed): T0858 Change Operating Mode (ICS) — confirm with engineering-station context.",
            ),
        ),
        _family(
            "ot_pmu_stream_gap",
            pattern_texts=(
                r"\bpmu\b",
                r"phasor",
                r"(?:stream\s+gap|data\s+stream|gaps?\s+or\s+interrupt)",
                r"interruption",
            ),
            draft_spl=_tier1_stats_spl(
                "ot_network_index",
                "ot_pmu_sourcetype",
                filter_clause="(*pmu* OR *phasor* OR *c37* OR *synchrophasor*)",
                eval_lines=(
                    'eval pmu_norm=coalesce(device_name, host, src, "unknown")',
                    'eval status_norm=lower(coalesce(status, stream_status, message, "ok"))',
                ),
                where_clause='like(status_norm, "%gap%") OR like(status_norm, "%loss%") OR like(status_norm, "%timeout%") OR like(status_norm, "%interrupt%") OR like(status_norm, "%missing%")',
                stats_by="pmu_norm status_norm",
            ),
            assumptions=_base_assumptions(
                "Counts PMU/synchrophasor stream gap/loss events per device for availability review.",
            ),
            required_log_fields=("index", "sourcetype", "device_name", "status", "_time"),
            required_source_profile_fields=("ot_network_index", "ot_pmu_sourcetype"),
            investigation_checklist=(
                "Correlate stream gaps with PDC health, GPS time-sync loss, or network congestion.",
                "Limitation: gaps inferred from status fields; true sample-rate gap detection needs PDC counters.",
                "MITRE (candidate, unconfirmed): T0815 Denial of Service (ICS) — only if gaps are adversary-induced.",
            ),
        ),
        _family(
            "ot_dmz_firewall_policy_change",
            pattern_texts=(
                r"firewall\s+polic",
                r"rule\s+chang",
                r"\bot\s+dmz\b",
                r"policy\s+or\s+rule",
            ),
            draft_spl=_tier1_stats_spl(
                "ot_firewall_index",
                "ot_firewall_sourcetype",
                filter_clause="(*config* OR *policy* OR *rule* OR *acl* OR change_type=*)",
                eval_lines=(
                    'eval actor_norm=lower(coalesce(user, admin, src_user, "unknown"))',
                    'eval device_norm=coalesce(host, dvc, device_name, "unknown")',
                    'eval change_norm=lower(coalesce(change_type, action, message, "change"))',
                ),
                where_clause='like(change_norm, "%polic%") OR like(change_norm, "%rule%") OR like(change_norm, "%acl%") OR like(change_norm, "%config%")',
                stats_by="device_norm actor_norm change_norm",
            ),
            assumptions=_base_assumptions(
                "Surfaces OT-DMZ firewall policy/rule/ACL change events for governance review.",
            ),
            required_log_fields=("index", "sourcetype", "user", "change_type", "_time"),
            required_source_profile_fields=("ot_firewall_index", "ot_firewall_sourcetype"),
            investigation_checklist=(
                "Match each policy/rule change to an approved change ticket and authorized admin.",
                "Limitation: change semantics depend on the firewall audit sourcetype being onboarded.",
                "MITRE (candidate, unconfirmed): T1562.004 Disable/Modify System Firewall — confirm intent vs authorized change.",
            ),
        ),
        _family(
            "windows_account_creation_4720",
            pattern_texts=(
                r"\b4720\b",
                r"accounts?\s+creat",
                r"active\s+directory",
                r"new\s+.{0,20}accounts?",
            ),
            draft_spl=_tier1_stats_spl(
                "windows_index",
                "windows_security_sourcetype",
                filter_clause="EventCode=4720",
                eval_lines=(
                    'eval new_account_norm=lower(coalesce(TargetUserName, target_user, account, "unknown"))',
                    'eval actor_norm=lower(coalesce(SubjectUserName, user, creator, "unknown"))',
                ),
                stats_by="actor_norm new_account_norm",
            ),
            assumptions=_base_assumptions(
                "Lists Active Directory account-creation events (Windows Security EventCode 4720).",
            ),
            required_log_fields=("index", "sourcetype", "EventCode", "TargetUserName", "SubjectUserName", "_time"),
            required_source_profile_fields=("windows_index", "windows_security_sourcetype"),
            investigation_checklist=(
                "Confirm each new account maps to an approved onboarding/JML request and authorized creator.",
                "Limitation: review the creation actor and privilege grants that follow (4728/4732) for escalation.",
                "MITRE (candidate, unconfirmed): T1136.002 Create Account: Domain Account.",
            ),
        ),
    )
