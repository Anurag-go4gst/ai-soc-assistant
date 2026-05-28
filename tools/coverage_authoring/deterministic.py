"""Deterministic coverage entry drafting from question text (no LLM)."""

from __future__ import annotations

import re
from typing import Any

from app.coverage.coverage_models import CoverageGovernance, CoverageReadiness, PatternCoverageEntry
from app.detections.detection_binder import bind_detection

from registries import RegistrySnapshot, bind_family, evidence_contract_exists

GOVERNANCE_FALSE = CoverageGovernance(
    execution_authorized=False,
    spl_execution_enabled=False,
    mcp_execution_enabled=False,
    llm_final_synthesis_enabled=False,
    answer_guard_enabled=False,
    sample_only=False,
    execution_eligible=False,
)


def slugify(text: str, *, max_len: int = 48) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug[:max_len].strip("_") or "draft"


def draft_entry_deterministic(
    question: str,
    question_ref: str,
    pattern_type: str | None,
    snapshot: RegistrySnapshot,
) -> PatternCoverageEntry:
    normalized = f" {' '.join(question.lower().split())} "
    coverage_id = f"cov.{question_ref}.draft_{slugify(question)}"

    if _is_missing_context_notable(normalized):
        return _negative_notable(coverage_id, question, question_ref)

    if "known malicious ip" in normalized or "known bad ip" in normalized:
        return _ioc_ip_entry(coverage_id, question, question_ref, snapshot)

    if "malicious domain" in normalized and "lookup" in normalized:
        return _ioc_domain_entry(coverage_id, question, question_ref, snapshot)

    if " ioc" in normalized or "ioc lookup" in normalized:
        return _ioc_generic_entry(coverage_id, question, question_ref, snapshot)

    if "dga" in normalized:
        return _detection_entry(coverage_id, question, question_ref, "dga", snapshot)

    if "beaconing" in normalized or "command-and-control" in normalized:
        family = "beaconing" if "beaconing" in normalized else "c2"
        return _detection_entry(coverage_id, question, question_ref, family, snapshot)

    if "both" in normalized and "dns" in normalized and "network" in normalized:
        return _multi_signal_entry(coverage_id, question, question_ref)

    if pattern_type == "ioc_correlation" or pattern_type == "threat_intel_enrichment":
        return _ioc_generic_entry(coverage_id, question, question_ref, snapshot)

    if pattern_type in {"dns_beaconing_dga_behavior", "lateral_movement", "suspicious_process_powershell"}:
        family = _family_from_pattern(pattern_type)
        return _detection_entry(coverage_id, question, question_ref, family, snapshot)

    if pattern_type == "multi_signal_correlation":
        return _multi_signal_entry(coverage_id, question, question_ref)

    if pattern_type == "top_n_aggregation":
        return _template_aggregate_dependency_missing(coverage_id, question, question_ref, snapshot)

    if pattern_type == "threshold_anomaly":
        return _threshold_dependency_missing(coverage_id, question, question_ref, snapshot)

    if "excessive" in normalized and "failed login" in normalized:
        return _threshold_dependency_missing(coverage_id, question, question_ref, snapshot)

    if "most" in normalized and ("outbound" in normalized or "dns quer" in normalized):
        return _template_aggregate_dependency_missing(coverage_id, question, question_ref, snapshot)

    return _generic_dependency_missing(coverage_id, question, question_ref)


def _is_missing_context_notable(normalized: str) -> bool:
    return "this notable" in normalized or "this alert" in normalized or "this incident" in normalized


def _negative_notable(coverage_id: str, question: str, question_ref: str) -> PatternCoverageEntry:
    return PatternCoverageEntry(
        coverage_id=coverage_id,
        question_ref=question_ref,
        question=question,
        coverage_group="negative_cannot_route",
        primary_skill="entity_timeline",
        route_plan_shape={
            "route_status": "clarification_required",
            "primary_skill": "entity_timeline",
            "pattern_id": "notable_event_timeline",
            "operation_type": "timeline",
            "source_class": "notable_risk",
            "entities": ["notable_id"],
            "time_window": "last_24_hours",
            "parameters": {},
            "evidence_needs": {},
        },
        template_ref=None,
        evidence_contract_ref="raw_events:notable_id:timeline",
        readiness=CoverageReadiness.BLOCKED_MISSING_CONTEXT,
        clarification_required=["notable_id"],
        expected_route_status="clarification_required",
        expected_blockers=["missing_contextual_reference"],
        governance=GOVERNANCE_FALSE.model_copy(),
        notes="Q4A deterministic draft: contextual notable reference requires analyst context.",
    )


def _ioc_ip_entry(
    coverage_id: str,
    question: str,
    question_ref: str,
    snapshot: RegistrySnapshot,
) -> PatternCoverageEntry:
    lookup_ref = "known_bad_ip" if "known_bad_ip" in snapshot.lookup_refs else None
    blockers = [] if lookup_ref else ["missing_dependency:lookup_ref:known_bad_ip"]
    readiness = CoverageReadiness.IOC_DEPENDENT if lookup_ref else CoverageReadiness.DEPENDENCY_MISSING
    evidence = (
        "ranked_entities:host:malicious_contact_count"
        if evidence_contract_exists("ranked_entities:host:malicious_contact_count")
        else "ranked_entities:host:malicious_contact_count"
    )
    if not evidence_contract_exists(evidence):
        blockers.append("missing_dependency:evidence_contract_ref")
        readiness = CoverageReadiness.DEPENDENCY_MISSING

    return PatternCoverageEntry(
        coverage_id=coverage_id,
        question_ref=question_ref,
        question=question,
        coverage_group="ioc_dependent",
        primary_skill="lookup_correlation",
        route_plan_shape=_lookup_route_plan("hosts_contacting_known_malicious_ips", "known_bad_ip"),
        template_ref=None,
        lookup_ref=lookup_ref,
        evidence_contract_ref=evidence,
        readiness=readiness,
        clarification_required=["time_window"],
        expected_route_status="cannot_route_missing_lookup",
        expected_blockers=blockers or ["missing_configured_lookup:ioc"],
        governance=GOVERNANCE_FALSE.model_copy(),
        notes="Q4A draft: enable IOC_REGISTRY_ENABLED=true for local Q2 lookup at review time.",
    )


def _ioc_domain_entry(
    coverage_id: str,
    question: str,
    question_ref: str,
    snapshot: RegistrySnapshot,
) -> PatternCoverageEntry:
    lookup_ref = "known_bad_domain" if "known_bad_domain" in snapshot.lookup_refs else None
    blockers = [] if lookup_ref else ["missing_dependency:lookup_ref:known_bad_domain"]
    readiness = CoverageReadiness.IOC_DEPENDENT if lookup_ref else CoverageReadiness.DEPENDENCY_MISSING
    evidence = "ranked_entities:host:malicious_domain_contact_count"
    if not evidence_contract_exists(evidence):
        blockers.append("missing_dependency:evidence_contract_ref")
        readiness = CoverageReadiness.DEPENDENCY_MISSING

    return PatternCoverageEntry(
        coverage_id=coverage_id,
        question_ref=question_ref,
        question=question,
        coverage_group="ioc_dependent",
        primary_skill="lookup_correlation",
        route_plan_shape=_lookup_route_plan("hosts_reaching_known_malicious_domains", "known_bad_domain"),
        template_ref=None,
        lookup_ref=lookup_ref,
        evidence_contract_ref=evidence,
        readiness=readiness,
        clarification_required=["time_window"],
        expected_route_status="cannot_route_missing_lookup",
        expected_blockers=blockers or ["missing_configured_lookup:ioc"],
        governance=GOVERNANCE_FALSE.model_copy(),
        notes="Q4A draft: local domain IOC lookup via Q2 registry.",
    )


def _ioc_generic_entry(
    coverage_id: str,
    question: str,
    question_ref: str,
    snapshot: RegistrySnapshot,
) -> PatternCoverageEntry:
    entry = _ioc_ip_entry(coverage_id, question, question_ref, snapshot)
    return entry.model_copy(
        update={
            "expected_blockers": ["missing_configured_lookup:ioc"],
            "notes": "Q4A draft: IOC correlation; confirm lookup_ref during human review.",
        }
    )


def _detection_entry(
    coverage_id: str,
    question: str,
    question_ref: str,
    family: str,
    snapshot: RegistrySnapshot,
) -> PatternCoverageEntry:
    detection_ref, contract = bind_family(family)
    blockers: list[str] = []
    readiness = CoverageReadiness.DETECTION_DEPENDENT
    if family not in snapshot.detection_families:
        blockers.append(f"missing_dependency:detection_family:{family}")
        readiness = CoverageReadiness.DEPENDENCY_MISSING
    if detection_ref is None:
        blockers.append(f"missing_vetted_detection:{family}")
        readiness = CoverageReadiness.DEPENDENCY_MISSING
    elif detection_ref not in snapshot.detection_refs_bindable:
        blockers.append(f"unvetted_detection_ref:{detection_ref}")
        readiness = CoverageReadiness.DEPENDENCY_MISSING

    evidence = contract or "ranked_entities_dga_v1"
    if contract and not evidence_contract_exists(contract):
        blockers.append("missing_dependency:evidence_contract_ref")
        readiness = CoverageReadiness.DEPENDENCY_MISSING
    elif not evidence_contract_exists(evidence):
        blockers.append("missing_dependency:evidence_contract_ref")
        readiness = CoverageReadiness.DEPENDENCY_MISSING

    return PatternCoverageEntry(
        coverage_id=coverage_id,
        question_ref=question_ref,
        question=question,
        coverage_group="detection_dependent",
        primary_skill="behavioral_detection_binding",
        route_plan_shape={
            "route_status": "route_ready",
            "primary_skill": "behavioral_detection_binding",
            "pattern_id": f"{family}_binding",
            "operation_type": "detection_binding",
            "source_class": "dns_logs",
            "entities": ["host"],
            "time_window": "last_24_hours",
            "parameters": {"detection_family": family, "time_window": "last_24_hours"},
            "evidence_needs": {"detection_required": True, "detection_family": family},
        },
        template_ref=None,
        detection_family=family,
        detection_ref=detection_ref,
        evidence_contract_ref=evidence,
        readiness=readiness,
        clarification_required=["time_window"],
        expected_route_status="cannot_route_missing_detection",
        expected_blockers=blockers or [f"missing_vetted_detection:{family}"],
        governance=GOVERNANCE_FALSE.model_copy(),
        notes="Q4A draft: Q3 registry binding only; no detection SPL execution.",
    )


def _multi_signal_entry(coverage_id: str, question: str, question_ref: str) -> PatternCoverageEntry:
    return PatternCoverageEntry(
        coverage_id=coverage_id,
        question_ref=question_ref,
        question=question,
        coverage_group="multi_signal",
        primary_skill="multi_signal_correlation",
        route_plan_shape={
            "route_status": "route_ready",
            "primary_skill": "multi_signal_correlation",
            "pattern_id": "correlate_dns_and_network_anomalies",
            "operation_type": "correlate_signals",
            "source_class": "identity_and_endpoint",
            "entities": ["host"],
            "time_window": "last_24_hours",
            "parameters": {"time_window": "last_24_hours"},
            "evidence_needs": {"signals": ["dns_anomaly", "network_anomaly"]},
            "sub_invocations": [],
        },
        template_ref=None,
        evidence_contract_ref="multi_signal:dns_and_network_anomaly_flags",
        readiness=CoverageReadiness.DEPENDENCY_MISSING,
        clarification_required=["threshold_ref", "time_window"],
        expected_route_status="clarification_required",
        expected_blockers=[
            "missing_threshold_or_baseline_policy",
            "missing_dependency:multi_signal_baselines",
        ],
        governance=GOVERNANCE_FALSE.model_copy(),
        notes="Q4A draft: multi-signal shape valid; per-signal detections/baselines not fully seeded.",
    )


def _template_aggregate_dependency_missing(
    coverage_id: str,
    question: str,
    question_ref: str,
    snapshot: RegistrySnapshot,
) -> PatternCoverageEntry:
    blockers = [
        "missing_dependency:template_ref",
        "sample_only_templates_not_promoted_by_q4a",
    ]
    if not snapshot.production_template_refs:
        blockers.append("no_production_aggregate_template_available")
    return PatternCoverageEntry(
        coverage_id=coverage_id,
        question_ref=question_ref,
        question=question,
        coverage_group="template_only",
        primary_skill="aggregate_and_rank",
        route_plan_shape=_aggregate_route_plan("pending_aggregate_pattern"),
        template_ref=None,
        evidence_contract_ref="ranked_entities:entity:metric",
        readiness=CoverageReadiness.DEPENDENCY_MISSING,
        clarification_required=["time_window"],
        expected_route_status="route_ready",
        expected_blockers=blockers + ["missing_dependency:evidence_contract_ref"],
        governance=GOVERNANCE_FALSE.model_copy(),
        notes="Q4A does not auto-select sample_only CIM templates; assign production template_ref manually.",
    )


def _threshold_dependency_missing(
    coverage_id: str,
    question: str,
    question_ref: str,
    snapshot: RegistrySnapshot,
) -> PatternCoverageEntry:
    template_ref = None
    evidence = "raw_search_table:host:failed_logins"
    blockers = ["missing_dependency:threshold_ref"]
    if "auth_failed_login_spike" in snapshot.production_template_refs:
        template_ref = "auth_failed_login_spike"
        if evidence_contract_exists(evidence):
            readiness = CoverageReadiness.SOURCE_READY
            blockers = []
        else:
            readiness = CoverageReadiness.DEPENDENCY_MISSING
            blockers.append("missing_dependency:evidence_contract_ref")
    else:
        readiness = CoverageReadiness.DEPENDENCY_MISSING
        blockers.append("missing_dependency:template_ref")

    return PatternCoverageEntry(
        coverage_id=coverage_id,
        question_ref=question_ref,
        question=question,
        coverage_group="template_only",
        primary_skill="threshold_anomaly",
        route_plan_shape={
            "route_status": "route_ready",
            "primary_skill": "threshold_anomaly",
            "pattern_id": "auth_failed_login_spike",
            "operation_type": "threshold",
            "source_class": "okta_authentication_logs",
            "entities": ["host"],
            "time_window": "last_1_hour",
            "parameters": {
                "metric": {"type": "count", "field": "failed_logins"},
                "threshold_ref": "failed_login_spike_default",
                "time_window": "last_1_hour",
            },
            "evidence_needs": {"datamodel": "Authentication"},
        },
        template_ref=template_ref,
        evidence_contract_ref=evidence,
        readiness=readiness,
        clarification_required=["threshold_ref", "time_window"],
        expected_route_status="route_ready",
        expected_blockers=blockers,
        governance=GOVERNANCE_FALSE.model_copy(),
        notes="Q4A draft: threshold policy must be SOC-approved before promotion.",
    )


def _generic_dependency_missing(
    coverage_id: str,
    question: str,
    question_ref: str,
) -> PatternCoverageEntry:
    return PatternCoverageEntry(
        coverage_id=coverage_id,
        question_ref=question_ref,
        question=question,
        coverage_group="template_only",
        primary_skill="aggregate_and_rank",
        route_plan_shape=_aggregate_route_plan("unclassified_pattern"),
        template_ref=None,
        evidence_contract_ref="ranked_entities:entity:metric",
        readiness=CoverageReadiness.DEPENDENCY_MISSING,
        clarification_required=["time_window"],
        expected_route_status="clarification_required",
        expected_blockers=["missing_dependency:coverage_classification"],
        governance=GOVERNANCE_FALSE.model_copy(),
        notes="Q4A could not classify question; complete fields during human review.",
    )


def _lookup_route_plan(pattern_id: str, lookup_ref: str) -> dict[str, Any]:
    return {
        "route_status": "route_ready",
        "primary_skill": "lookup_correlation",
        "pattern_id": pattern_id,
        "operation_type": "correlate_lookup",
        "source_class": "network_traffic",
        "entities": ["host", "dest_ip"],
        "time_window": "today",
        "parameters": {"lookup_ref": lookup_ref, "match_field": "dest_ip", "time_window": "today"},
        "evidence_needs": {"lookup_required": True, "lookup_name": "ioc"},
    }


def _aggregate_route_plan(pattern_id: str) -> dict[str, Any]:
    return {
        "route_status": "route_ready",
        "primary_skill": "aggregate_and_rank",
        "pattern_id": pattern_id,
        "operation_type": "top_n",
        "source_class": "network_traffic",
        "entities": ["src_ip"],
        "time_window": "last_24_hours",
        "parameters": {
            "group_by": {"field": "src_ip", "source_class": "network_traffic"},
            "metric": {"type": "count", "field": "connection_count"},
            "sort": {"field": "metric_value", "direction": "desc"},
            "limit": 10,
            "time_window": "last_24_hours",
        },
        "evidence_needs": {
            "datamodel": "Network_Traffic",
            "group_by": ["src_ip"],
            "metric": {"type": "count", "field": "connection_count"},
        },
    }


def _family_from_pattern(pattern_type: str) -> str:
    mapping = {
        "dns_beaconing_dga_behavior": "dga",
        "lateral_movement": "lateral_movement",
        "suspicious_process_powershell": "encoded_powershell",
    }
    return mapping.get(pattern_type, "dga")
