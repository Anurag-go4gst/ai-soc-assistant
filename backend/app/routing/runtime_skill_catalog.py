from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.routing.route_plan_models import RuntimeSkill


RUNTIME_SKILL_CATALOG: dict[str, dict[str, Any]] = {
    RuntimeSkill.AGGREGATE_AND_RANK.value: {
        "skill_id": RuntimeSkill.AGGREGATE_AND_RANK.value,
        "purpose": "Aggregate events by entity or field, compute a metric, sort, and limit ranked results.",
        "allowed_operation_types": ["top_n", "bottom_n", "rank", "aggregate"],
        "required_slots": ["source_class", "time_window", "group_by", "metric"],
        "optional_slots": ["event_filter", "sort", "limit", "filters", "exclusions"],
        "hard_preconditions": ["source_available", "metric_defined", "grouping_field_defined"],
        "allowed_post_enrichments": ["entity_context_lookup", "notable_risk_lookup"],
        "allows_sub_invocations": False,
        "governance_constraints": ["no_spl_execution", "candidate_plan_only", "deterministic_validation_required"],
        "examples": ["Top users by failed login count in the last 24 hours."],
        "non_examples": ["Run a detection SPL authored by the model."],
    },
    RuntimeSkill.THRESHOLD_ANOMALY.value: {
        "skill_id": RuntimeSkill.THRESHOLD_ANOMALY.value,
        "purpose": "Compare a metric against an approved threshold or baseline policy.",
        "allowed_operation_types": ["threshold_check", "baseline_compare", "spike_detection"],
        "required_slots": ["source_class", "time_window", "metric", "threshold_ref"],
        "optional_slots": ["group_by", "filters", "exclusions"],
        "hard_preconditions": ["threshold_or_baseline_policy_available"],
        "allowed_post_enrichments": ["entity_context_lookup", "lookup_correlation"],
        "allows_sub_invocations": False,
        "governance_constraints": ["no_model_authored_threshold_policy", "deterministic_validation_required"],
        "examples": ["Users with failed-login spikes above the default baseline."],
        "non_examples": ["Invent an excessive threshold from confidence."],
    },
    RuntimeSkill.SEQUENCE_DETECTION.value: {
        "skill_id": RuntimeSkill.SEQUENCE_DETECTION.value,
        "purpose": "Bind ordered event conditions to an approved sequence pattern.",
        "allowed_operation_types": ["sequence_match", "ordered_pattern"],
        "required_slots": ["source_class", "time_window", "detection_ref"],
        "optional_slots": ["entities", "filters", "exclusions"],
        "hard_preconditions": ["vetted_sequence_detection_available"],
        "allowed_post_enrichments": ["entity_context_lookup", "lookup_correlation", "notable_risk_lookup"],
        "allows_sub_invocations": False,
        "governance_constraints": ["no_llm_authored_detection_spl", "deterministic_validation_required"],
        "examples": ["Failed login followed by successful login from a new country."],
        "non_examples": ["Create new persistence SPL from text."],
    },
    RuntimeSkill.LOOKUP_CORRELATION.value: {
        "skill_id": RuntimeSkill.LOOKUP_CORRELATION.value,
        "purpose": "Correlate local events or entities with an approved local lookup.",
        "allowed_operation_types": ["lookup_match", "lookup_exclusion", "ioc_correlation"],
        "required_slots": ["source_class", "time_window", "lookup_ref", "match_field"],
        "optional_slots": ["filters", "entities"],
        "hard_preconditions": ["approved_lookup_available"],
        "allowed_post_enrichments": ["entity_context_lookup"],
        "allows_sub_invocations": False,
        "governance_constraints": ["no_external_threat_intel_call", "local_lookup_only"],
        "examples": ["Hosts that contacted IPs in an approved IOC lookup."],
        "non_examples": ["Call a live external threat-intel API."],
    },
    RuntimeSkill.BEHAVIORAL_DETECTION_BINDING.value: {
        "skill_id": RuntimeSkill.BEHAVIORAL_DETECTION_BINDING.value,
        "purpose": "Reference a vetted behavioral detection binding without generating detection logic.",
        "allowed_operation_types": ["detection_binding", "detection_lookup"],
        "required_slots": ["detection_ref", "time_window"],
        "optional_slots": ["source_class", "entities", "filters"],
        "hard_preconditions": ["vetted_detection_available"],
        "allowed_post_enrichments": ["entity_context_lookup", "notable_risk_lookup"],
        "allows_sub_invocations": False,
        "governance_constraints": ["no_llm_authored_detection_spl", "no_write_actions"],
        "examples": ["Use the vetted impossible-travel detection reference."],
        "non_examples": ["Write new SPL for beaconing."],
    },
    RuntimeSkill.METADATA_DISCOVERY.value: {
        "skill_id": RuntimeSkill.METADATA_DISCOVERY.value,
        "purpose": "Discover available fields, sources, or metadata without enrichment or execution chains.",
        "allowed_operation_types": ["field_discovery", "source_discovery", "schema_discovery"],
        "required_slots": ["domain"],
        "optional_slots": ["source_class", "time_window"],
        "hard_preconditions": ["metadata_source_available"],
        "allowed_post_enrichments": [],
        "allows_sub_invocations": False,
        "governance_constraints": ["no_post_enrichment", "no_behavioral_binding"],
        "examples": ["Which fields are available for Okta authentication logs?"],
        "non_examples": ["Discover fields then run a behavioral detection."],
    },
    RuntimeSkill.ENTITY_CONTEXT_LOOKUP.value: {
        "skill_id": RuntimeSkill.ENTITY_CONTEXT_LOOKUP.value,
        "purpose": "Look up approved local context for a supplied entity.",
        "allowed_operation_types": ["entity_lookup", "asset_lookup", "identity_lookup"],
        "required_slots": ["entities"],
        "optional_slots": ["source_class", "time_window"],
        "hard_preconditions": ["entity_supplied"],
        "allowed_post_enrichments": [],
        "allows_sub_invocations": False,
        "governance_constraints": ["no_spl_execution", "no_action_chain"],
        "examples": ["Is user alice privileged?"],
        "non_examples": ["Execute SPL after context lookup."],
    },
    RuntimeSkill.NOTABLE_RISK_LOOKUP.value: {
        "skill_id": RuntimeSkill.NOTABLE_RISK_LOOKUP.value,
        "purpose": "Retrieve approved risk or notable context for supplied entities or notable identifiers.",
        "allowed_operation_types": ["risk_lookup", "notable_lookup"],
        "required_slots": ["entities"],
        "optional_slots": ["time_window", "source_class"],
        "hard_preconditions": ["entity_or_notable_supplied"],
        "allowed_post_enrichments": ["entity_context_lookup", "entity_timeline"],
        "allows_sub_invocations": False,
        "governance_constraints": ["read_only", "approved_context_only"],
        "examples": ["Show notable risk for ranked users."],
        "non_examples": ["Create a remediation ticket."],
    },
    RuntimeSkill.MULTI_SIGNAL_CORRELATION.value: {
        "skill_id": RuntimeSkill.MULTI_SIGNAL_CORRELATION.value,
        "purpose": "Combine flat validated sub-results from approved runtime skills.",
        "allowed_operation_types": ["correlate_signals", "combine_sub_results"],
        "required_slots": ["time_window", "sub_invocations"],
        "optional_slots": ["entities", "source_class", "filters"],
        "hard_preconditions": ["flat_sub_invocations_only", "each_sub_invocation_validated"],
        "allowed_post_enrichments": ["entity_context_lookup", "notable_risk_lookup"],
        "allows_sub_invocations": True,
        "governance_constraints": ["max_depth_2", "no_nested_multi_signal", "no_nested_sub_invocations"],
        "examples": ["Correlate threshold anomalies with a vetted behavioral detection."],
        "non_examples": ["A workflow chain with branching execution steps."],
    },
    RuntimeSkill.ENTITY_TIMELINE.value: {
        "skill_id": RuntimeSkill.ENTITY_TIMELINE.value,
        "purpose": "Build a timeline for an explicit entity while preserving entity identity.",
        "allowed_operation_types": ["timeline", "event_sequence"],
        "required_slots": ["entities", "time_window"],
        "optional_slots": ["source_class", "filters"],
        "hard_preconditions": ["entity_preserved"],
        "allowed_post_enrichments": ["entity_context_lookup"],
        "allows_sub_invocations": False,
        "governance_constraints": ["entity_must_be_explicit", "read_only"],
        "examples": ["Timeline for host web01 in the last 24 hours."],
        "non_examples": ["Timeline for this host without context."],
    },
}


def get_runtime_skill_catalog() -> dict[str, dict[str, Any]]:
    return deepcopy(RUNTIME_SKILL_CATALOG)


def get_skill_contract(skill_id: str) -> dict[str, Any] | None:
    contract = RUNTIME_SKILL_CATALOG.get(skill_id)
    return deepcopy(contract) if contract else None
