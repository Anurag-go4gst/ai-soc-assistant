"""Cisco Environment KB Wave 2 lab draft families — tier-1 SPL, never executable."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.spl.draft_preview import DetectionFamily

_LAB_ONLY = "This draft is lab-only; not governed, not approved, and not executed."
_SLOT_NOTE = (
    "Replace index/sourcetype placeholders from your Environment KB Cisco source profile slots."
)


def _tier1_stats_spl(
    index_slot: str,
    sourcetype_slot: str,
    *,
    filter_clause: str,
    eval_lines: tuple[str, ...] = (),
    where_clause: str | None = None,
    stats_by: str,
    stats_fields: str = "count as event_count",
    table_fields: str | None = None,
) -> str:
    eval_block = "".join(f"\n| {line}" for line in eval_lines)
    where_block = f"\n| where {where_clause}" if where_clause else ""
    table = table_fields or f"{stats_by} event_count"
    return f"""
search index=<{index_slot}> sourcetype=<{sourcetype_slot}> earliest=-24h latest=now {filter_clause}{eval_block}{where_block}
| stats {stats_fields} earliest(_time) as first_seen_epoch latest(_time) as last_seen_epoch by {stats_by}
| eval first_seen=strftime(first_seen_epoch, "%Y-%m-%d %H:%M:%S")
| eval last_seen=strftime(last_seen_epoch, "%Y-%m-%d %H:%M:%S")
| fields - first_seen_epoch last_seen_epoch
| table {table} first_seen last_seen
| sort - event_count
| head 100
""".strip()


def _base_assumptions(*extra: str) -> tuple[str, ...]:
    return (*extra, _SLOT_NOTE, _LAB_ONLY)


def cisco_detection_families() -> tuple[DetectionFamily, ...]:
    from app.spl.draft_preview import _family

    return (
        _family(
            "cisco_routing_protocol_anomaly",
            pattern_texts=(
                r"\bospf\b",
                r"\bbgp\b",
                r"routing\s+(?:protocol|update|anomal)",
                r"unauthorized\s+routing",
            ),
            draft_spl=_tier1_stats_spl(
                "cisco_ios_index",
                "cisco_ios_sourcetype",
                filter_clause="(*ospf* OR *bgp* OR *routing*)",
                eval_lines=(
                    'eval protocol_norm=lower(coalesce(protocol, routing_protocol, message, "%"))',
                    'eval action_norm=lower(coalesce(action, event_action, change_type, "%"))',
                    'eval router_norm=coalesce(host, dvc, device_name, src, "unknown")',
                ),
                where_clause='like(protocol_norm, "%ospf%") OR like(protocol_norm, "%bgp%") OR like(action_norm, "%update%")',
                stats_by="router_norm protocol_norm action_norm",
            ),
            assumptions=_base_assumptions(
                "Surfaces OSPF/BGP routing updates and anomalies from Cisco IOS telemetry.",
            ),
            required_log_fields=("index", "sourcetype", "host", "protocol", "action", "_time"),
            required_source_profile_fields=("cisco_ios_index", "cisco_ios_sourcetype"),
            investigation_checklist=(
                "Validate routing peers and expected maintenance windows before escalation.",
                "Correlate with change tickets for authorized routing policy updates.",
            ),
        ),
        _family(
            "cisco_cleartext_to_rtu",
            pattern_texts=(
                r"cleartext",
                r"\brtu\b",
                r"unencrypted\s+(?:traffic|session)",
            ),
            draft_spl=_tier1_stats_spl(
                "network_index",
                "network_traffic_sourcetype",
                filter_clause="*",
                eval_lines=(
                    'eval src_norm=coalesce(src_ip, src, source, "unknown")',
                    'eval dest_norm=coalesce(dest_ip, dest, destination, "unknown")',
                    'eval proto_norm=lower(coalesce(protocol, proto, transport, ""))',
                    'eval encrypt_norm=lower(coalesce(encryption, tls_version, cipher, "none"))',
                ),
                where_clause='like(dest_norm, "%rtu%") OR dest_port=502 OR dest_port=20000',
                stats_by="src_norm dest_norm proto_norm encrypt_norm",
            ),
            assumptions=_base_assumptions(
                "Flags cleartext or weakly protected sessions targeting RTU/OT endpoints.",
            ),
            required_log_fields=("index", "sourcetype", "src_ip", "dest_ip", "protocol", "_time"),
            required_source_profile_fields=("network_index", "network_traffic_sourcetype"),
            investigation_checklist=(
                "Confirm whether cleartext is expected for legacy OT protocols in this segment.",
            ),
        ),
        _family(
            "cisco_ios_port_security",
            pattern_texts=(
                r"port\s+security",
                r"mac\s+(?:address\s+)?flap",
                r"security\s+violation",
            ),
            draft_spl=_tier1_stats_spl(
                "cisco_ios_index",
                "cisco_ios_sourcetype",
                filter_clause="(*port*security* OR *flap* OR *violation*)",
                eval_lines=(
                    'eval switch_norm=coalesce(host, dvc, device_name, "unknown")',
                    'eval interface_norm=coalesce(interface, port, if_name, "unknown")',
                    'eval mac_norm=lower(coalesce(mac, src_mac, address, "unknown"))',
                    'eval action_norm=lower(coalesce(action, status, event_action, ""))',
                ),
                stats_by="switch_norm interface_norm mac_norm action_norm",
            ),
            assumptions=_base_assumptions(
                "Summarizes Cisco IOS port-security violations and MAC flapping alerts.",
            ),
            required_log_fields=("index", "sourcetype", "host", "interface", "mac", "action", "_time"),
            required_source_profile_fields=("cisco_ios_index", "cisco_ios_sourcetype"),
            investigation_checklist=(
                "Verify whether the MAC belongs to a known substation device or rogue endpoint.",
            ),
        ),
        _family(
            "cisco_stealthwatch_scan",
            pattern_texts=(
                r"stealthwatch",
                r"network\s+scan",
                r"port\s+scan",
            ),
            draft_spl=_tier1_stats_spl(
                "network_index",
                "network_traffic_sourcetype",
                filter_clause="*",
                eval_lines=(
                    'eval scanner_norm=coalesce(src_ip, src, source, "unknown")',
                    'eval target_norm=coalesce(dest_ip, dest, destination, "unknown")',
                    'eval signature_norm=coalesce(signature, alert_name, event_name, "scan")',
                ),
                stats_fields="count as scan_events dc(dest_port) as distinct_ports",
                stats_by="scanner_norm target_norm signature_norm",
                table_fields="scanner_norm target_norm signature_norm scan_events distinct_ports",
            ),
            assumptions=_base_assumptions(
                "Stealthwatch or flow-derived scan detection — high port diversity is indicative only.",
            ),
            required_log_fields=("index", "sourcetype", "src_ip", "dest_ip", "dest_port", "_time"),
            required_source_profile_fields=("network_index", "network_traffic_sourcetype"),
            investigation_checklist=(
                "Exclude authorized vulnerability scanners before treating as hostile reconnaissance.",
            ),
        ),
        _family(
            "cisco_sgt_classification_failure",
            pattern_texts=(
                r"\bsgt\b",
                r"security\s+group\s+tag",
                r"classification\s+fail",
            ),
            draft_spl=_tier1_stats_spl(
                "cisco_ios_index",
                "cisco_ios_sourcetype",
                filter_clause="(*sgt* OR *security*group*tag*) (*fail* OR *unknown* OR result=failure OR status=failure)",
                eval_lines=(
                    'eval device_norm=coalesce(host, dvc, endpoint, "unknown")',
                    'eval sgt_norm=coalesce(sgt, security_group_tag, tag, "unknown")',
                    'eval result_norm=lower(coalesce(result, status, action, "failure"))',
                ),
                stats_by="device_norm sgt_norm result_norm",
            ),
            assumptions=_base_assumptions(
                "SGT classification failures from Cisco TrustSec/ISE integration logs.",
            ),
            required_log_fields=("index", "sourcetype", "host", "sgt", "result", "_time"),
            required_source_profile_fields=("cisco_ios_index", "cisco_ios_sourcetype"),
            investigation_checklist=(
                "Confirm endpoint authorization policy and expected SGT mappings during review.",
            ),
        ),
        _family(
            "cisco_icmp_anomaly",
            pattern_texts=(
                r"\bicmp\b",
                r"packet\s+size",
                r"baseline\s+anomal",
            ),
            draft_spl=_tier1_stats_spl(
                "cisco_firewall_index",
                "cisco_firewall_sourcetype",
                filter_clause="protocol=icmp OR proto=icmp OR *icmp*",
                eval_lines=(
                    'eval src_norm=coalesce(src_ip, src, source, "unknown")',
                    'eval dest_norm=coalesce(dest_ip, dest, destination, "unknown")',
                    'eval size_norm=coalesce(packets, packet_size, bytes, 0)',
                ),
                stats_fields="count as icmp_events avg(size_norm) as avg_packet_size",
                stats_by="src_norm dest_norm",
                table_fields="src_norm dest_norm icmp_events avg_packet_size",
            ),
            assumptions=_base_assumptions(
                "ICMP size/volume anomalies from firewall or flow telemetry — not proof of tunneling.",
            ),
            required_log_fields=("index", "sourcetype", "src_ip", "dest_ip", "protocol", "bytes", "_time"),
            required_source_profile_fields=("cisco_firewall_index", "cisco_firewall_sourcetype"),
            investigation_checklist=(
                "Compare against baseline ICMP patterns for substation management networks.",
            ),
        ),
        _family(
            "cisco_ios_config_change",
            pattern_texts=(
                r"config(?:uration)?\s+chang",
                r"audit\s+trail",
                r"running-config",
            ),
            draft_spl=_tier1_stats_spl(
                "cisco_ios_index",
                "cisco_ios_sourcetype",
                filter_clause="(*config* OR *CFGLOG* OR *audit*)",
                eval_lines=(
                    'eval device_norm=coalesce(host, dvc, device_name, "unknown")',
                    'eval user_norm=lower(coalesce(user, username, operator, "unknown"))',
                    'eval command_norm=coalesce(command, cmd, message, "unspecified")',
                ),
                stats_by="device_norm user_norm command_norm",
            ),
            assumptions=_base_assumptions(
                "Cisco IOS configuration audit trail — correlate with approved change windows.",
            ),
            required_log_fields=("index", "sourcetype", "host", "user", "command", "_time"),
            required_source_profile_fields=("cisco_ios_index", "cisco_ios_sourcetype"),
            investigation_checklist=(
                "Match config changes to CMDB owner and maintenance tickets before escalation.",
            ),
        ),
        _family(
            "cisco_tacacs_privilege",
            pattern_texts=(
                r"tacacs",
                r"privilege\s+level\s*15",
                r"elevate\s+privilege",
            ),
            draft_spl=_tier1_stats_spl(
                "cisco_tacacs_index",
                "cisco_tacacs_sourcetype",
                filter_clause="*",
                eval_lines=(
                    'eval user_norm=lower(coalesce(user, username, account, "unknown"))',
                    'eval device_norm=coalesce(host, nas_ip, device, "unknown")',
                    'eval priv_norm=coalesce(privilege, priv_level, level, "unknown")',
                ),
                where_clause='priv_norm=15 OR like(priv_norm, "%15%")',
                stats_by="user_norm device_norm priv_norm",
            ),
            assumptions=_base_assumptions(
                "TACACS+ privilege-15 elevation events on grid routers and switches.",
            ),
            required_log_fields=("index", "sourcetype", "user", "host", "privilege", "_time"),
            required_source_profile_fields=("cisco_tacacs_index", "cisco_tacacs_sourcetype"),
            investigation_checklist=(
                "Verify technician identity and whether privilege-15 was authorized for the asset.",
            ),
        ),
        _family(
            "cisco_ise_mab",
            pattern_texts=(
                r"\bmab\b",
                r"mac\s+authentication\s+bypass",
                r"single\s+mac",
            ),
            draft_spl=_tier1_stats_spl(
                "cisco_ise_index",
                "cisco_ise_sourcetype",
                filter_clause="(*mab* OR *mac*auth*)",
                eval_lines=(
                    'eval mac_norm=lower(coalesce(calling_station_id, mac, mac_address, "unknown"))',
                    'eval switch_norm=coalesce(nas_ip, network_device_name, switch, "unknown")',
                    'eval result_norm=lower(coalesce(result, status, auth_result, ""))',
                ),
                stats_by="mac_norm switch_norm result_norm",
            ),
            assumptions=_base_assumptions(
                "ISE MAB authentication events — repeated MACs may indicate shared ports or cloning.",
            ),
            required_log_fields=("index", "sourcetype", "calling_station_id", "nas_ip", "result", "_time"),
            required_source_profile_fields=("cisco_ise_index", "cisco_ise_sourcetype"),
            investigation_checklist=(
                "Confirm whether the MAC is authorized for the switch port and VLAN assignment.",
            ),
        ),
        _family(
            "cisco_ise_posture",
            pattern_texts=(
                r"ise\s+posture",
                r"posture\s+fail",
                r"engineering\s+workstation",
            ),
            draft_spl=_tier1_stats_spl(
                "cisco_ise_index",
                "cisco_ise_sourcetype",
                filter_clause="(*posture* OR *compliance*)",
                eval_lines=(
                    'eval endpoint_norm=coalesce(endpoint_id, mac, ip, host, "unknown")',
                    'eval posture_norm=lower(coalesce(posture_status, compliance_status, result, "failed"))',
                    'eval profile_norm=coalesce(endpoint_profile, device_type, "unknown")',
                ),
                where_clause='like(posture_norm, "%fail%") OR like(posture_norm, "%non%compliant%")',
                stats_by="endpoint_norm profile_norm posture_norm",
            ),
            assumptions=_base_assumptions(
                "Cisco ISE posture failures for engineering workstations and OT-adjacent endpoints.",
            ),
            required_log_fields=("index", "sourcetype", "endpoint_id", "posture_status", "result", "_time"),
            required_source_profile_fields=("cisco_ise_index", "cisco_ise_sourcetype"),
            investigation_checklist=(
                "Review remediation status and whether the endpoint should be on the OT access VLAN.",
            ),
        ),
        _family(
            "cisco_ise_quarantine",
            pattern_texts=(
                r"quarantine",
                r"shut\s+down",
                r"dynamic\s+(?:vlan|port)",
            ),
            draft_spl=_tier1_stats_spl(
                "cisco_ise_index",
                "cisco_ise_sourcetype",
                filter_clause="(*quarantine* OR *CoA* OR *shutdown*)",
                eval_lines=(
                    'eval endpoint_norm=coalesce(endpoint_id, mac, ip, "unknown")',
                    'eval switch_norm=coalesce(nas_ip, network_device_name, "unknown")',
                    'eval interface_norm=coalesce(port, interface, "unknown")',
                    'eval action_norm=lower(coalesce(action, coa_action, result, "quarantine"))',
                ),
                stats_by="endpoint_norm switch_norm interface_norm action_norm",
            ),
            assumptions=_base_assumptions(
                "ISE quarantine/CoA events that dynamically restrict switch interfaces.",
            ),
            required_log_fields=("index", "sourcetype", "endpoint_id", "nas_ip", "action", "_time"),
            required_source_profile_fields=("cisco_ise_index", "cisco_ise_sourcetype"),
            investigation_checklist=(
                "Confirm quarantine was triggered by policy and not a false positive posture assessment.",
            ),
        ),
        _family(
            "cisco_wlc_rogue_ap",
            pattern_texts=(
                r"rogue",
                r"unauthorized\s+wireless",
                r"\bwlc\b",
            ),
            draft_spl=_tier1_stats_spl(
                "cisco_wlc_index",
                "cisco_wlc_sourcetype",
                filter_clause="(*rogue* OR *unauthorized*)",
                eval_lines=(
                    'eval ap_norm=coalesce(ap_name, bssid, mac, "unknown")',
                    'eval client_norm=coalesce(client_mac, station, "unknown")',
                    'eval ssid_norm=coalesce(ssid, wlan, "unknown")',
                ),
                stats_by="ap_norm client_norm ssid_norm",
            ),
            assumptions=_base_assumptions(
                "WLC rogue/unauthorized wireless client detections near substation perimeters.",
            ),
            required_log_fields=("index", "sourcetype", "ap_name", "client_mac", "ssid", "_time"),
            required_source_profile_fields=("cisco_wlc_index", "cisco_wlc_sourcetype"),
            investigation_checklist=(
                "Physically locate rogue APs and confirm they are not authorized maintenance hotspots.",
            ),
        ),
        _family(
            "cisco_duo_mfa_fatigue",
            pattern_texts=(
                r"\bduo\b",
                r"mfa\s+fatigue",
                r"push\s+spam",
            ),
            draft_spl=_tier1_stats_spl(
                "cisco_ise_index",
                "cisco_ise_sourcetype",
                filter_clause="(*duo* OR *mfa* OR *push*)",
                eval_lines=(
                    'eval user_norm=lower(coalesce(user, username, account, "unknown"))',
                    'eval result_norm=lower(coalesce(result, factor, auth_result, ""))',
                    'eval src_norm=coalesce(src_ip, ip, source, "unknown")',
                ),
                stats_fields="count as mfa_events dc(result_norm) as distinct_results",
                stats_by="user_norm src_norm",
                table_fields="user_norm src_norm mfa_events distinct_results",
            ),
            assumptions=_base_assumptions(
                "Duo/MFA push fatigue patterns — high push volume alone is not compromise proof.",
            ),
            required_log_fields=("index", "sourcetype", "user", "result", "src_ip", "_time"),
            required_source_profile_fields=("cisco_ise_index", "cisco_ise_sourcetype"),
            investigation_checklist=(
                "Interview the user for unsolicited push notifications before account containment.",
            ),
        ),
        _family(
            "cisco_ise_profile_shift",
            pattern_texts=(
                r"device\s+profile",
                r"profile\s+shift",
                r"endpoint\s+profile",
            ),
            draft_spl=_tier1_stats_spl(
                "cisco_ise_index",
                "cisco_ise_sourcetype",
                filter_clause="(*profile* OR *endpoint*profil*)",
                eval_lines=(
                    'eval endpoint_norm=coalesce(endpoint_id, mac, ip, "unknown")',
                    'eval old_profile=coalesce(previous_profile, old_profile, "unknown")',
                    'eval new_profile=coalesce(endpoint_profile, new_profile, device_type, "unknown")',
                ),
                where_clause="old_profile!=new_profile",
                stats_by="endpoint_norm old_profile new_profile",
            ),
            assumptions=_base_assumptions(
                "Dynamic ISE endpoint profile changes that may indicate spoofing or misclassification.",
            ),
            required_log_fields=("index", "sourcetype", "endpoint_id", "endpoint_profile", "_time"),
            required_source_profile_fields=("cisco_ise_index", "cisco_ise_sourcetype"),
            investigation_checklist=(
                "Validate whether the profile shift matches a known device replacement or re-image.",
            ),
        ),
        _family(
            "cisco_tacacs_stale_session",
            pattern_texts=(
                r"stale\s+session",
                r"persistent\s+tacacs",
                r"long[\s-]lived\s+session",
            ),
            draft_spl=_tier1_stats_spl(
                "cisco_tacacs_index",
                "cisco_tacacs_sourcetype",
                filter_clause="*",
                eval_lines=(
                    'eval user_norm=lower(coalesce(user, username, "unknown"))',
                    'eval device_norm=coalesce(host, nas_ip, device, "unknown")',
                    'eval session_norm=coalesce(session_id, session, "unknown")',
                ),
                stats_by="user_norm device_norm session_norm",
            ),
            assumptions=_base_assumptions(
                "Persistent TACACS+ sessions on core grid switches — duration thresholds need operator tuning.",
            ),
            required_log_fields=("index", "sourcetype", "user", "host", "session_id", "_time"),
            required_source_profile_fields=("cisco_tacacs_index", "cisco_tacacs_sourcetype"),
            investigation_checklist=(
                "Confirm sessions were closed after maintenance and not left open across shift changes.",
            ),
        ),
        _family(
            "ot_goose_burst",
            pattern_texts=(
                r"\bgoose\b",
                r"iec\s*61850",
                r"burst\s+pattern",
            ),
            draft_spl=_tier1_stats_spl(
                "network_index",
                "network_traffic_sourcetype",
                filter_clause="(*goose* OR *61850*)",
                eval_lines=(
                    'eval src_norm=coalesce(src_ip, src, source, "unknown")',
                    'eval dest_norm=coalesce(dest_ip, dest, destination, "unknown")',
                    'eval app_norm=lower(coalesce(app, protocol, service, "goose"))',
                ),
                stats_fields="count as goose_events",
                stats_by="src_norm dest_norm app_norm",
                table_fields="src_norm dest_norm app_norm goose_events",
            ),
            assumptions=_base_assumptions(
                "IEC 61850 GOOSE burst patterns from OT network telemetry.",
            ),
            required_log_fields=("index", "sourcetype", "src_ip", "dest_ip", "protocol", "_time"),
            required_source_profile_fields=("network_index", "network_traffic_sourcetype"),
            investigation_checklist=(
                "Correlate GOOSE bursts with relay testing or fault conditions before treating as malicious.",
            ),
        ),
        _family(
            "ot_mms_write",
            pattern_texts=(
                r"\bmms\b",
                r"manufacturing\s+message",
                r"mms\s+write",
            ),
            draft_spl=_tier1_stats_spl(
                "network_index",
                "network_traffic_sourcetype",
                filter_clause="(*mms* OR *61850*)",
                eval_lines=(
                    'eval src_norm=coalesce(src_ip, src, source, "unknown")',
                    'eval dest_norm=coalesce(dest_ip, dest, destination, "unknown")',
                    'eval action_norm=lower(coalesce(action, operation, function, ""))',
                ),
                where_clause='like(action_norm, "%write%") OR like(action_norm, "%set%")',
                stats_by="src_norm dest_norm action_norm",
            ),
            assumptions=_base_assumptions(
                "MMS write/set operations against substation IEDs — expected during authorized maintenance only.",
            ),
            required_log_fields=("index", "sourcetype", "src_ip", "dest_ip", "action", "_time"),
            required_source_profile_fields=("network_index", "network_traffic_sourcetype"),
            investigation_checklist=(
                "Verify source IP is an approved engineering workstation before escalation.",
            ),
        ),
        _family(
            "iccp_disconnect",
            pattern_texts=(
                r"\biccp\b",
                r"connection\s+drop",
                r"data\s+link",
            ),
            draft_spl=_tier1_stats_spl(
                "network_index",
                "network_traffic_sourcetype",
                filter_clause="(*iccp* OR *tase.2*)",
                eval_lines=(
                    'eval link_norm=coalesce(session, link_id, connection, "unknown")',
                    'eval src_norm=coalesce(src_ip, src, "unknown")',
                    'eval dest_norm=coalesce(dest_ip, dest, "unknown")',
                    'eval state_norm=lower(coalesce(state, status, action, "disconnect"))',
                ),
                stats_by="link_norm src_norm dest_norm state_norm",
            ),
            assumptions=_base_assumptions(
                "ICCP/TASE.2 link disconnect frequency between control centers.",
            ),
            required_log_fields=("index", "sourcetype", "src_ip", "dest_ip", "state", "_time"),
            required_source_profile_fields=("network_index", "network_traffic_sourcetype"),
            investigation_checklist=(
                "Check whether disconnects align with scheduled ICCP maintenance or network outages.",
            ),
        ),
        _family(
            "ot_modbus_exception",
            pattern_texts=(
                r"modbus",
                r"exception\s+code",
                r"\bplc\b",
            ),
            draft_spl=_tier1_stats_spl(
                "network_index",
                "network_traffic_sourcetype",
                filter_clause="(*modbus* OR dest_port=502)",
                eval_lines=(
                    'eval src_norm=coalesce(src_ip, src, source, "unknown")',
                    'eval dest_norm=coalesce(dest_ip, dest, destination, "unknown")',
                    'eval exception_norm=coalesce(exception_code, function_code, status, "unknown")',
                ),
                stats_by="src_norm dest_norm exception_norm",
            ),
            assumptions=_base_assumptions(
                "Modbus exception responses from PLCs — may indicate probing or misconfigured masters.",
            ),
            required_log_fields=("index", "sourcetype", "src_ip", "dest_ip", "exception_code", "_time"),
            required_source_profile_fields=("network_index", "network_traffic_sourcetype"),
            investigation_checklist=(
                "Map exception codes to vendor documentation before attributing to attack activity.",
            ),
        ),
        _family(
            "ot_firmware_drift",
            pattern_texts=(
                r"firmware\s+drift",
                r"firmware\s+version",
                r"version\s+mismatch",
            ),
            draft_spl=_tier1_stats_spl(
                "network_index",
                "network_traffic_sourcetype",
                filter_clause="(*firmware* OR *version*)",
                eval_lines=(
                    'eval asset_norm=coalesce(host, device, asset, "unknown")',
                    'eval reported_norm=coalesce(firmware_version, version, sw_version, "unknown")',
                    'eval expected_norm=coalesce(expected_version, baseline_version, "unknown")',
                ),
                where_clause="reported_norm!=expected_norm",
                stats_by="asset_norm reported_norm expected_norm",
            ),
            assumptions=_base_assumptions(
                "Firmware/version drift against CMDB baseline — requires authoritative expected versions.",
            ),
            required_log_fields=("index", "sourcetype", "host", "firmware_version", "_time"),
            required_source_profile_fields=("network_index", "network_traffic_sourcetype"),
            investigation_checklist=(
                "Confirm expected firmware baseline from asset registry before declaring unauthorized drift.",
            ),
        ),
        _family(
            "ot_master_spoof",
            pattern_texts=(
                r"master\s+spoof",
                r"rogue\s+master",
                r"duplicate\s+master",
            ),
            draft_spl=_tier1_stats_spl(
                "network_index",
                "network_traffic_sourcetype",
                filter_clause="(*master* OR *spoof*)",
                eval_lines=(
                    'eval master_norm=coalesce(master_id, src_ip, src, "unknown")',
                    'eval rtu_norm=coalesce(dest_ip, dest, rtu, "unknown")',
                    'eval role_norm=lower(coalesce(role, station_type, "master"))',
                ),
                stats_by="master_norm rtu_norm role_norm",
            ),
            assumptions=_base_assumptions(
                "Suspected rogue/duplicate master station activity against RTU endpoints.",
            ),
            required_log_fields=("index", "sourcetype", "src_ip", "dest_ip", "role", "_time"),
            required_source_profile_fields=("network_index", "network_traffic_sourcetype"),
            investigation_checklist=(
                "Identify authorized master IPs and compare against unexpected source addresses.",
            ),
        ),
        _family(
            "ot_ems_db_change",
            pattern_texts=(
                r"\bems\b",
                r"database\s+(?:schema|update)",
                r"sql\s+update",
            ),
            draft_spl=_tier1_stats_spl(
                "network_index",
                "network_traffic_sourcetype",
                filter_clause="(*schema* OR *database* OR *sql*)",
                eval_lines=(
                    'eval user_norm=lower(coalesce(user, db_user, account, "unknown"))',
                    'eval host_norm=coalesce(host, src_ip, source, "unknown")',
                    'eval action_norm=lower(coalesce(action, operation, query_type, "change"))',
                ),
                stats_by="user_norm host_norm action_norm",
            ),
            assumptions=_base_assumptions(
                "EMS/SCADA database schema or file updates performed directly on OT historians.",
            ),
            required_log_fields=("index", "sourcetype", "user", "host", "action", "_time"),
            required_source_profile_fields=("network_index", "network_traffic_sourcetype"),
            investigation_checklist=(
                "Match EMS DB changes to approved change tickets and vendor maintenance windows.",
            ),
        ),
        _family(
            "ot_dpi_malformed",
            pattern_texts=(
                r"malformed",
                r"unassigned\s+protocol",
                r"\bdpi\b",
            ),
            draft_spl=_tier1_stats_spl(
                "network_index",
                "network_traffic_sourcetype",
                filter_clause="(*malformed* OR *anomal* OR *dpi*)",
                eval_lines=(
                    'eval src_norm=coalesce(src_ip, src, source, "unknown")',
                    'eval dest_norm=coalesce(dest_ip, dest, destination, "unknown")',
                    'eval proto_norm=lower(coalesce(protocol, app, signature, "unknown"))',
                ),
                stats_by="src_norm dest_norm proto_norm",
            ),
            assumptions=_base_assumptions(
                "Industrial DPI alerts for malformed or unassigned protocol payloads.",
            ),
            required_log_fields=("index", "sourcetype", "src_ip", "dest_ip", "protocol", "_time"),
            required_source_profile_fields=("network_index", "network_traffic_sourcetype"),
            investigation_checklist=(
                "Validate DPI signature tuning to reduce false positives on legacy OT protocols.",
            ),
        ),
        _family(
            "ot_solar_setpoint_change",
            pattern_texts=(
                r"setpoint",
                r"solar",
                r"operational\s+modif",
            ),
            draft_spl=_tier1_stats_spl(
                "network_index",
                "network_traffic_sourcetype",
                filter_clause="(*setpoint* OR *solar* OR *inverter*)",
                eval_lines=(
                    'eval asset_norm=coalesce(host, device, inverter, "unknown")',
                    'eval param_norm=coalesce(parameter, tag, point, "setpoint")',
                    'eval user_norm=lower(coalesce(user, operator, account, "unknown"))',
                ),
                stats_by="asset_norm param_norm user_norm",
            ),
            assumptions=_base_assumptions(
                "Solar/inverter operational setpoint modifications from OT telemetry or EMS logs.",
            ),
            required_log_fields=("index", "sourcetype", "host", "parameter", "value", "_time"),
            required_source_profile_fields=("network_index", "network_traffic_sourcetype"),
            investigation_checklist=(
                "Confirm setpoint changes align with grid operations dispatch instructions.",
            ),
        ),
        _family(
            "ot_tftp_hmi",
            pattern_texts=(
                r"\btftp\b",
                r"\bhmi\b",
                r"firmware\s+transfer",
            ),
            draft_spl=_tier1_stats_spl(
                "network_index",
                "network_traffic_sourcetype",
                filter_clause="(*tftp* OR dest_port=69)",
                eval_lines=(
                    'eval src_norm=coalesce(src_ip, src, source, "unknown")',
                    'eval dest_norm=coalesce(dest_ip, dest, destination, "unknown")',
                    'eval file_norm=coalesce(filename, file, url, "unknown")',
                ),
                stats_by="src_norm dest_norm file_norm",
            ),
            assumptions=_base_assumptions(
                "TFTP transfers targeting HMI/OT assets — often maintenance-related but review-only here.",
            ),
            required_log_fields=("index", "sourcetype", "src_ip", "dest_ip", "filename", "_time"),
            required_source_profile_fields=("network_index", "network_traffic_sourcetype"),
            investigation_checklist=(
                "Verify TFTP source is an authorized patch server before treating as suspicious.",
            ),
        ),
        _family(
            "physical_access_impossible",
            pattern_texts=(
                r"impossible",
                r"badge",
                r"physical\s+access",
            ),
            draft_spl=_tier1_stats_spl(
                "network_index",
                "network_traffic_sourcetype",
                filter_clause="(*badge* OR *access* OR *pacs*)",
                eval_lines=(
                    'eval user_norm=lower(coalesce(user, badge_id, cardholder, "unknown"))',
                    'eval site_norm=coalesce(site, location, facility, "unknown")',
                    'eval reader_norm=coalesce(reader, door, device, "unknown")',
                ),
                stats_fields="count as access_events dc(site_norm) as distinct_sites",
                stats_by="user_norm",
                table_fields="user_norm access_events distinct_sites",
            ),
            assumptions=_base_assumptions(
                "Physical access events summarized for impossible-travel style review across sites.",
            ),
            required_log_fields=("index", "sourcetype", "user", "site", "reader", "_time"),
            required_source_profile_fields=("network_index", "network_traffic_sourcetype"),
            investigation_checklist=(
                "Correlate badge events with shift schedules and travel time between sites.",
            ),
        ),
        _family(
            "cii_scan_detection",
            pattern_texts=(
                r"\bcii\b",
                r"critical\s+infrastructure",
                r"scan\s+detect",
            ),
            draft_spl=_tier1_stats_spl(
                "network_index",
                "network_traffic_sourcetype",
                filter_clause="*",
                eval_lines=(
                    'eval scanner_norm=coalesce(src_ip, src, source, "unknown")',
                    'eval target_norm=coalesce(dest_ip, dest, destination, "unknown")',
                    'eval signature_norm=coalesce(signature, alert_name, category, "cii_scan")',
                ),
                stats_fields="count as scan_events dc(dest_port) as distinct_ports",
                stats_by="scanner_norm target_norm signature_norm",
                table_fields="scanner_norm target_norm signature_norm scan_events distinct_ports",
            ),
            assumptions=_base_assumptions(
                "CII-oriented scan detection from IDS/flow telemetry — confirm authorized scanners.",
            ),
            required_log_fields=("index", "sourcetype", "src_ip", "dest_ip", "signature", "_time"),
            required_source_profile_fields=("network_index", "network_traffic_sourcetype"),
            investigation_checklist=(
                "Exclude vulnerability management scanners mapped in the asset registry.",
            ),
        ),
        _family(
            "ot_dual_master_conflict",
            pattern_texts=(
                r"dual\s+master",
                r"two\s+master",
                r"master\s+conflict",
            ),
            draft_spl=_tier1_stats_spl(
                "network_index",
                "network_traffic_sourcetype",
                filter_clause="(*master* OR *rtu*)",
                eval_lines=(
                    'eval rtu_norm=coalesce(dest_ip, dest, rtu, "unknown")',
                    'eval master_norm=coalesce(master_id, src_ip, src, "unknown")',
                ),
                stats_fields="count as master_events dc(master_norm) as distinct_masters",
                stats_by="rtu_norm",
                table_fields="rtu_norm master_events distinct_masters",
            ),
            assumptions=_base_assumptions(
                "Dual-master conflicts where multiple masters address the same RTU simultaneously.",
            ),
            required_log_fields=("index", "sourcetype", "src_ip", "dest_ip", "master_id", "_time"),
            required_source_profile_fields=("network_index", "network_traffic_sourcetype"),
            investigation_checklist=(
                "Identify which master is authoritative and whether failover testing explains the conflict.",
            ),
        ),
        _family(
            "ntp_stratum_change",
            pattern_texts=(
                r"\bntp\b",
                r"stratum",
                r"time\s+sync",
            ),
            draft_spl=_tier1_stats_spl(
                "network_index",
                "network_traffic_sourcetype",
                filter_clause="(*ntp* OR dest_port=123)",
                eval_lines=(
                    'eval host_norm=coalesce(host, src_ip, device, "unknown")',
                    'eval stratum_norm=coalesce(stratum, ntp_stratum, time_stratum, "unknown")',
                    'eval server_norm=coalesce(ntp_server, dest_ip, dest, "unknown")',
                ),
                stats_by="host_norm stratum_norm server_norm",
            ),
            assumptions=_base_assumptions(
                "NTP stratum changes that may affect OT timestamp integrity across substations.",
            ),
            required_log_fields=("index", "sourcetype", "host", "stratum", "dest_ip", "_time"),
            required_source_profile_fields=("network_index", "network_traffic_sourcetype"),
            investigation_checklist=(
                "Verify NTP hierarchy changes against approved time-source migration plans.",
            ),
        ),
        _family(
            "loto_breaker_correlation",
            pattern_texts=(
                r"\bloto\b",
                r"lockout",
                r"breaker",
            ),
            draft_spl=_tier1_stats_spl(
                "network_index",
                "network_traffic_sourcetype",
                filter_clause="(*loto* OR *lockout* OR *breaker*)",
                eval_lines=(
                    'eval ticket_norm=coalesce(ticket, work_order, loto_id, "unknown")',
                    'eval asset_norm=coalesce(asset, breaker, device, "unknown")',
                    'eval state_norm=lower(coalesce(state, status, action, "unknown"))',
                ),
                stats_by="ticket_norm asset_norm state_norm",
            ),
            assumptions=_base_assumptions(
                "LOTO/breaker state correlation for safety-critical maintenance tracking.",
            ),
            required_log_fields=("index", "sourcetype", "ticket", "asset", "state", "_time"),
            required_source_profile_fields=("network_index", "network_traffic_sourcetype"),
            investigation_checklist=(
                "Confirm LOTO ticket status matches breaker state before clearing alerts.",
            ),
        ),
        _family(
            "agc_frequency_anomaly",
            pattern_texts=(
                r"\bagc\b",
                r"frequency",
                r"grid\s+frequency",
            ),
            draft_spl=_tier1_stats_spl(
                "network_index",
                "network_traffic_sourcetype",
                filter_clause="(*agc* OR *frequency* OR *hz*)",
                eval_lines=(
                    'eval asset_norm=coalesce(host, device, plant, "unknown")',
                    'eval param_norm=coalesce(parameter, tag, signal, "frequency")',
                    'eval value_norm=coalesce(value, measurement, reading, 0)',
                ),
                stats_fields="count as sample_count avg(value_norm) as avg_value",
                stats_by="asset_norm param_norm",
                table_fields="asset_norm param_norm sample_count avg_value",
            ),
            assumptions=_base_assumptions(
                "AGC/frequency execution tracking parameters — operational context required for severity.",
            ),
            required_log_fields=("index", "sourcetype", "host", "parameter", "value", "_time"),
            required_source_profile_fields=("network_index", "network_traffic_sourcetype"),
            investigation_checklist=(
                "Review with grid operations before treating frequency deviations as security incidents.",
            ),
        ),
        _family(
            "endpoint_tooling_install",
            pattern_texts=(
                r"tooling\s+install",
                r"newly\s+deploy",
                r"asset\s+tracking",
            ),
            draft_spl=_tier1_stats_spl(
                "network_index",
                "network_traffic_sourcetype",
                filter_clause="(*install* OR *deploy* OR *tool*)",
                eval_lines=(
                    'eval host_norm=coalesce(host, src_nt_host, computer, "unknown")',
                    'eval tool_norm=coalesce(tool, software, product, "unknown")',
                    'eval user_norm=lower(coalesce(user, installer, account, "unknown"))',
                ),
                stats_by="host_norm tool_norm user_norm",
            ),
            assumptions=_base_assumptions(
                "Host asset tracking entries for newly deployed tooling on OT-adjacent endpoints.",
            ),
            required_log_fields=("index", "sourcetype", "host", "tool", "user", "_time"),
            required_source_profile_fields=("network_index", "network_traffic_sourcetype"),
            investigation_checklist=(
                "Validate tooling installs against software allowlists and change tickets.",
            ),
        ),
        _family(
            "dns_query_window_review",
            pattern_texts=(
                r"list\s+all\s+dns",
                r"dns\s+requests?\s+during",
                r"observation\s+window",
                r"during\s+the\s+window",
            ),
            draft_spl="""
search index=<dns_index> sourcetype=<dns_sourcetype> earliest=-24h latest=now (query=* OR question=*)
| eval src_host_norm=lower(coalesce(src_host, src, src_ip, host, "unknown"))
| eval domain_norm=lower(coalesce(query, question, domain, ""))
| eval resolver_norm=lower(coalesce(dns_server, dest, dest_ip, ""))
| stats
    count as dns_query_count
    earliest(_time) as first_seen_epoch
    latest(_time) as last_seen_epoch
    by src_host_norm domain_norm resolver_norm
| eval first_seen=strftime(first_seen_epoch, "%Y-%m-%d %H:%M:%S")
| eval last_seen=strftime(last_seen_epoch, "%Y-%m-%d %H:%M:%S")
| fields - first_seen_epoch last_seen_epoch
| table src_host_norm domain_norm resolver_norm dns_query_count first_seen last_seen
| sort - dns_query_count
| head 100
""".strip(),
            assumptions=_base_assumptions(
                "Aggregated DNS query review for an observation window — not a raw event dump.",
                "Use source-profile time bounds to narrow earliest/latest during analyst review.",
            ),
            required_log_fields=("index", "sourcetype", "src_ip", "query", "dest_ip", "_time"),
            required_source_profile_fields=("dns_index", "dns_sourcetype"),
            investigation_checklist=(
                "Confirm resolver targets match internal Umbrella/resolver policy before flagging bypass.",
                "Exclude infrastructure resolvers and recursive forwarders from analyst judgment.",
            ),
        ),
        _family(
            "cisco_firewall_geo_egress",
            pattern_texts=(
                r"outbound",
                r"foreign\s+countr",
                r"geo\s+egress",
                r"egress.*countr",
            ),
            draft_spl=_tier1_stats_spl(
                "cisco_firewall_index",
                "cisco_firewall_sourcetype",
                filter_clause="action=allowed OR action=accept",
                eval_lines=(
                    'eval src_norm=coalesce(src_ip, src, source, "unknown")',
                    'eval dest_norm=coalesce(dest_ip, dest, destination, "unknown")',
                    'eval country_norm=coalesce(dest_country, Country, country, "unknown")',
                    'eval zone_norm=coalesce(src_zone, from_zone, "ot")',
                ),
                stats_by="src_norm dest_norm country_norm zone_norm",
            ),
            assumptions=_base_assumptions(
                "Outbound firewall connections from OT zones to foreign countries — geo fields required.",
            ),
            required_log_fields=("index", "sourcetype", "src_ip", "dest_ip", "dest_country", "action", "_time"),
            required_source_profile_fields=("cisco_firewall_index", "cisco_firewall_sourcetype"),
            investigation_checklist=(
                "Validate country enrichment is current and exclude approved vendor egress destinations.",
            ),
        ),
        _family(
            "cisco_firewall_dns_bypass",
            pattern_texts=(
                r"bypass.*dns",
                r"umbrella",
                r"external\s+domain",
                r"direct\s+resolv",
            ),
            draft_spl=_tier1_stats_spl(
                "cisco_firewall_index",
                "cisco_firewall_sourcetype",
                filter_clause="(dest_port=53 OR *dns*)",
                eval_lines=(
                    'eval src_norm=coalesce(src_ip, src, source, "unknown")',
                    'eval resolver_norm=coalesce(dest_ip, dest, dns_server, "unknown")',
                    'eval domain_norm=lower(coalesce(query, domain, url, ""))',
                ),
                where_clause='NOT cidrmatch("<internal_umbrella_resolver_cidr>", resolver_norm)',
                stats_by="src_norm resolver_norm domain_norm",
            ),
            assumptions=_base_assumptions(
                "Substation endpoints resolving external domains via non-internal Cisco Umbrella resolvers.",
            ),
            required_log_fields=("index", "sourcetype", "src_ip", "dest_ip", "query", "_time"),
            required_source_profile_fields=("cisco_firewall_index", "cisco_firewall_sourcetype"),
            investigation_checklist=(
                "Confirm internal Umbrella resolver CIDR before declaring DNS policy bypass.",
            ),
        ),
        _family(
            "ssh_weak_cipher",
            pattern_texts=(
                r"weak\s+cipher",
                r"ssh",
                r"tls\s+1\.0",
                r"deprecated\s+cipher",
            ),
            draft_spl=_tier1_stats_spl(
                "network_index",
                "network_traffic_sourcetype",
                filter_clause="(*ssh* OR *tls* OR dest_port=22 OR dest_port=443)",
                eval_lines=(
                    'eval src_norm=coalesce(src_ip, src, source, "unknown")',
                    'eval dest_norm=coalesce(dest_ip, dest, destination, "unknown")',
                    'eval cipher_norm=lower(coalesce(cipher, ssl_cipher, encryption, "unknown"))',
                    'eval proto_norm=lower(coalesce(protocol, app, "ssh"))',
                ),
                where_clause='like(cipher_norm, "%3des%") OR like(cipher_norm, "%rc4%") OR like(cipher_norm, "%des%") OR like(proto_norm, "%tls%1.0%")',
                stats_by="src_norm dest_norm cipher_norm proto_norm",
            ),
            assumptions=_base_assumptions(
                "Administrative SSH/TLS sessions using weak or deprecated cipher suites.",
            ),
            required_log_fields=("index", "sourcetype", "src_ip", "dest_ip", "cipher", "protocol", "_time"),
            required_source_profile_fields=("network_index", "network_traffic_sourcetype"),
            investigation_checklist=(
                "Verify cipher policy baselines with network engineering before remediation.",
            ),
        ),
        _family(
            "cisco_amp_process_injection",
            pattern_texts=(
                r"process\s+injection",
                r"\bamp\b",
                r"cross-process",
            ),
            draft_spl=_tier1_stats_spl(
                "cisco_amp_index",
                "cisco_amp_sourcetype",
                filter_clause="(*injection* OR *cross*process* OR *amp*)",
                eval_lines=(
                    'eval host_norm=coalesce(computer, host, src_nt_host, "unknown")',
                    'eval parent_norm=coalesce(parent_process, ParentImage, "unknown")',
                    'eval child_norm=coalesce(process, Image, child_process, "unknown")',
                    'eval action_norm=lower(coalesce(action, event_type, disposition, "detect"))',
                ),
                stats_by="host_norm parent_norm child_norm action_norm",
            ),
            assumptions=_base_assumptions(
                "Cisco Secure Endpoint cross-process injection detections on OT-adjacent hosts.",
            ),
            required_log_fields=("index", "sourcetype", "computer", "ParentImage", "Image", "action", "_time"),
            required_source_profile_fields=("cisco_amp_index", "cisco_amp_sourcetype"),
            investigation_checklist=(
                "Validate injection chain against known EDR false-positive patterns before containment.",
            ),
        ),
        _family(
            "endpoint_hosts_file_change",
            pattern_texts=(
                r"hosts\s+file",
                r"hosts\s+modif",
                r"etc[/\\]hosts",
            ),
            draft_spl=_tier1_stats_spl(
                "endpoint_index",
                "endpoint_process_sourcetype",
                filter_clause="(*hosts* OR *drivers*etc*)",
                eval_lines=(
                    'eval host_norm=coalesce(computer, host, src_nt_host, "unknown")',
                    'eval user_norm=lower(coalesce(user, SubjectUserName, account, "unknown"))',
                    'eval path_norm=lower(coalesce(file_path, TargetFilename, object, "unknown"))',
                    'eval action_norm=lower(coalesce(action, event_action, "modify"))',
                ),
                where_clause='like(path_norm, "%hosts%")',
                stats_by="host_norm user_norm path_norm action_norm",
            ),
            assumptions=_base_assumptions(
                "Windows hosts-file modifications on mapped substation engineering workstations.",
            ),
            required_log_fields=("index", "sourcetype", "computer", "user", "file_path", "_time"),
            required_source_profile_fields=("endpoint_index", "endpoint_process_sourcetype"),
            investigation_checklist=(
                "Confirm whether the change was performed by authorized patching or malware activity.",
            ),
        ),
    )
