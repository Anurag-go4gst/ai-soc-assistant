#!/usr/bin/env python3
"""Build reviewed answer-pack runtime projections."""
from __future__ import annotations
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "backend" / "app" / "use_cases" / "answer_packs.json"
_COMMON_CAVEAT = (
    "Reviewed answer pack enriches EvidencePlan only; it does not authorize "
    "live result claims or SPL execution."
)
PACKS = {
    "q0.q046": {
        "case_id": "q0.q046",
        "use_case_id": "auth_failed_login_spike",
        "review_status": "reviewed",
        "provenance": "coe_reviewed_answer_pack_seed",
        "required_evidence": ["failed_login_count", "user", "time_window"],
        "optional_evidence": ["source_ip", "host"],
        "source_needs": ["authentication_logs"],
        "dependency_gaps": ["coe_enrichment_required"],
        "mitre_candidates": ["T1110"],
        "must_not_claim": [
            "account_compromise_without_successful_login_evidence",
            "confirmed_brute_force_without_threshold_context",
        ],
        "caveats": [_COMMON_CAVEAT],
        "spl_family_suggestion": "auth_failed_login_spike",
        "spl_template_id": "auth_failed_login_spike",
    },
    "auth_failed_login_spike": {
        "use_case_id": "auth_failed_login_spike",
        "review_status": "reviewed",
        "provenance": "coe_reviewed_answer_pack_seed",
        "required_evidence": ["failed_login_count", "user", "time_window"],
        "optional_evidence": ["source_ip", "host"],
        "source_needs": ["authentication_logs"],
        "mitre_candidates": ["T1110"],
        "must_not_claim": [
            "account_compromise_without_successful_login_evidence",
            "confirmed_brute_force_without_threshold_context",
        ],
        "caveats": [_COMMON_CAVEAT],
        "spl_family_suggestion": "auth_failed_login_spike",
        "spl_template_id": "auth_failed_login_spike",
    },
    "q0.q004": {
        "case_id": "q0.q004",
        "use_case_id": "lookup_correlation",
        "review_status": "reviewed",
        "provenance": "batch_d_weak_known_lookup_row",
        "answer_shape": "ioc_host_lookup_review",
        "required_evidence": ["indicator_match", "host", "time_window"],
        "optional_evidence": ["src_ip", "dest_ip", "action"],
        "source_needs": ["firewall_or_proxy_logs", "local_ioc_lookup"],
        "dependency_gaps": ["local_lookup_table_required", "ioc_feed_binding"],
        "mitre_candidates": ["T1071", "T1041"],
        "must_not_claim": [
            "confirmed_malware_without_lookup_hit_context",
            "live_ioc_feed_queried_without_operator_binding",
        ],
        "caveats": [_COMMON_CAVEAT, "Lookup dependency must be operator-bound before execution."],
        "spl_validator_id": "ioc_lookup_correlation.v1",
    },
    "q0.q006": {
        "case_id": "q0.q006",
        "use_case_id": "dns_beaconing_candidate",
        "review_status": "reviewed",
        "provenance": "batch_d_weak_known_detection_binding_row",
        "answer_shape": "dns_beaconing_hunt_review",
        "required_evidence": ["dns_query_name", "query_volume", "time_window"],
        "optional_evidence": ["src_ip", "dest_ip", "domain_entropy"],
        "source_needs": ["dns_logs"],
        "dependency_gaps": ["detection_binding_unavailable", "baseline_policy_missing"],
        "mitre_candidates": ["T1071.004"],
        "must_not_claim": [
            "confirmed_c2_without_dns_volume_baseline",
            "beaconing_verdict_without_peer_comparison",
        ],
        "caveats": [_COMMON_CAVEAT],
        "spl_family_suggestion": "dns_beaconing_candidate",
        "spl_template_id": "dns_beaconing_candidate",
    },
    "q0.q002": {
        "case_id": "q0.q002",
        "use_case_id": "net_new_outbound_destination",
        "review_status": "reviewed",
        "provenance": "batch_d_weak_known_source_profile_row",
        "answer_shape": "network_top_talkers_review",
        "required_evidence": ["src_ip", "connection_count", "time_window"],
        "optional_evidence": ["dest_ip", "bytes", "sourcetype"],
        "source_needs": ["network_firewall_logs"],
        "dependency_gaps": ["source_profile_bindings_missing", "environment_mapping_drift"],
        "must_not_claim": [
            "exfiltration_without_volume_baseline",
            "asset_criticality_without_inventory_context",
        ],
        "caveats": [_COMMON_CAVEAT, "Bind firewall index/sourcetype from Environment KB before review."],
        "spl_validator_id": "network_top_talkers.v1",
    },
    "q0.q003": {
        "case_id": "q0.q003",
        "use_case_id": "windows_privileged_group_changes",
        "review_status": "reviewed",
        "provenance": "batch_d_weak_known_hybrid_knowledge_row",
        "answer_shape": "privileged_group_change_review",
        "required_evidence": ["group_change_event", "user", "time_window"],
        "optional_evidence": ["host", "admin_workstation"],
        "source_needs": ["windows_security_logs"],
        "dependency_gaps": ["windows_source_profile_binding"],
        "mitre_candidates": ["T1098"],
        "must_not_claim": [
            "confirmed_privilege_abuse_without_change_context",
            "live_query_executed_without_review",
        ],
        "caveats": [_COMMON_CAVEAT, "Hybrid knowledge/RAG enrichment is advisory only."],
        "spl_validator_id": "windows_privileged_group.v1",
    },
    "q0.q010": {
        "case_id": "q0.q010",
        "use_case_id": "network_smb_top_talkers",
        "review_status": "reviewed",
        "provenance": "coe_binding_fix_smb_top_talkers",
        "answer_shape": "network_smb_top_talkers_review",
        "required_evidence": ["host", "connection_count", "time_window"],
        "optional_evidence": ["dest_ip", "bytes", "dest_port", "sourcetype"],
        "source_needs": ["network_traffic_logs"],
        "dependency_gaps": ["row_authority_not_ready"],
        "mitre_candidates": ["T1021.002"],
        "must_not_claim": [
            "lateral_movement_confirmed_without_peer_context",
            "exfiltration_without_volume_baseline",
        ],
        "caveats": [_COMMON_CAVEAT, "Bind network index/sourcetype from Environment KB before execution."],
        "spl_family_suggestion": "network_smb_top_talkers",
        "spl_validator_id": "network_top_talkers.v1",
    },
}
def main() -> int:
    payload = {"version": 1, "provenance": "reviewed_runtime_projection", "packs": PACKS}
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(str(OUTPUT))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
