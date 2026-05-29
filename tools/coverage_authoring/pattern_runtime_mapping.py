"""Stage 3L-S6: Taxonomy pattern → compact runtime skill mapping (author-time canon).

Aligned with docs/soc_runtime_skill_route_plan_stage3k_q05.md § Taxonomy-to-Runtime Mapping.
"""

from __future__ import annotations

from typing import Any, Final

# pattern_type → proposed runtime route (not manifest authority).
PATTERN_TO_RUNTIME: Final[dict[str, dict[str, Any]]] = {
    "top_n_aggregation": {
        "proposed_primary_skill": "aggregate_and_rank",
        "proposed_operation_type": "top_n",
        "dependency_class": "source_binding",
    },
    "threshold_anomaly": {
        "proposed_primary_skill": "threshold_anomaly",
        "proposed_operation_type": "threshold_check",
        "dependency_class": "threshold_baseline_plus_source",
    },
    "time_trend": {
        "proposed_primary_skill": "aggregate_and_rank",
        "proposed_operation_type": "aggregate",
        "dependency_class": "source_binding",
    },
    "new_or_unusual_source": {
        "proposed_primary_skill": "threshold_anomaly",
        "proposed_operation_type": "baseline_compare",
        "dependency_class": "baseline_policy",
    },
    "success_after_failure": {
        "proposed_primary_skill": "sequence_detection",
        "proposed_operation_type": "sequence_match",
        "dependency_class": "source_plus_threshold",
    },
    "ioc_correlation": {
        "proposed_primary_skill": "lookup_correlation",
        "proposed_operation_type": "ioc_correlation",
        "dependency_class": "local_lookup",
    },
    "threat_intel_enrichment": {
        "proposed_primary_skill": "lookup_correlation",
        "proposed_operation_type": "lookup_match",
        "dependency_class": "local_lookup",
    },
    "notable_risk_lookup": {
        "proposed_primary_skill": "notable_risk_lookup",
        "proposed_operation_type": "risk_lookup",
        "dependency_class": "notable_risk_source",
    },
    "case_state_lookup": {
        "proposed_primary_skill": "notable_risk_lookup",
        "proposed_operation_type": "notable_lookup",
        "dependency_class": "case_history_source",
    },
    "asset_identity_context": {
        "proposed_primary_skill": "entity_context_lookup",
        "proposed_operation_type": "entity_lookup",
        "dependency_class": "enrichment_lookup",
    },
    "dns_beaconing_dga_behavior": {
        "proposed_primary_skill": "behavioral_detection_binding",
        "proposed_operation_type": "detection_binding",
        "dependency_class": "detection_binding",
    },
    "lateral_movement": {
        "proposed_primary_skill": "behavioral_detection_binding",
        "proposed_operation_type": "detection_binding",
        "dependency_class": "detection_binding",
    },
    "suspicious_process_powershell": {
        "proposed_primary_skill": "behavioral_detection_binding",
        "proposed_operation_type": "detection_binding",
        "dependency_class": "detection_binding",
    },
    "persistence_scheduled_task_service": {
        "proposed_primary_skill": "behavioral_detection_binding",
        "proposed_operation_type": "detection_binding",
        "dependency_class": "detection_binding",
    },
    "data_source_health": {
        "proposed_primary_skill": "metadata_discovery",
        "proposed_operation_type": "source_discovery",
        "dependency_class": "metadata_inventory",
    },
    "cloud_activity": {
        "proposed_primary_skill": "behavioral_detection_binding",
        "proposed_operation_type": "detection_binding",
        "dependency_class": "source_detection_blocked",
        "route_blocked": True,
    },
    "dlp_exfiltration": {
        "proposed_primary_skill": "threshold_anomaly",
        "proposed_operation_type": "threshold_check",
        "dependency_class": "source_threshold_or_detection",
    },
    "multi_signal_correlation": {
        "proposed_primary_skill": "multi_signal_correlation",
        "proposed_operation_type": "correlate_signals",
        "dependency_class": "composed_dependencies",
    },
    "safe_metadata_discovery": {
        "proposed_primary_skill": "metadata_discovery",
        "proposed_operation_type": "field_discovery",
        "dependency_class": "metadata_inventory",
    },
    "other_or_unclear": {
        "proposed_primary_skill": None,
        "proposed_operation_type": None,
        "dependency_class": "policy_definition",
        "route_blocked": True,
    },
}

LEGACY_ROUTER_INTENT_BY_PATTERN: Final[dict[str, str]] = {
    "top_n_aggregation": "attack_discovery",
    "threshold_anomaly": "attack_discovery",
    "time_trend": "attack_discovery",
    "new_or_unusual_source": "attack_discovery",
    "success_after_failure": "attack_discovery",
    "ioc_correlation": "attack_discovery",
    "threat_intel_enrichment": "knowledge_recall",
    "notable_risk_lookup": "alert_summary",
    "case_state_lookup": "alert_summary",
    "asset_identity_context": "knowledge_recall",
    "dns_beaconing_dga_behavior": "attack_discovery",
    "lateral_movement": "attack_discovery",
    "suspicious_process_powershell": "attack_discovery",
    "persistence_scheduled_task_service": "attack_discovery",
    "data_source_health": "knowledge_recall",
    "cloud_activity": "attack_discovery",
    "dlp_exfiltration": "attack_discovery",
    "multi_signal_correlation": "attack_discovery",
    "safe_metadata_discovery": "knowledge_recall",
    "other_or_unclear": "attack_discovery",
}

AUTHORITY_PILOT_QUESTION_REF: Final[str] = "q0.q046"
AUTHORITY_PILOT_COVERAGE_ID: Final[str] = "cov.q046.excessive_failed_logins_sample"
