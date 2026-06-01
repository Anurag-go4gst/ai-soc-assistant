"""Stage 3K-Q1F: LLM route-plan candidate generation (Instruct-only, shadow-only).

Produces a governed route-plan candidate JSON, expands it to the full route-plan
shape, and runs deterministic validation. Never authorizes execution or changes
the analyst-facing answer.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from app.config import settings
from app.llm.adapter import adapt_llm_output
from app.llm.sidecar_governance import (
    REASONING_REJECTION_ROUTING,
    SKIP_LLM_DISABLED,
    SKIP_NO_PROVIDER_CONFIGURED,
    SKIP_ROLE_NOT_CONFIGURED,
    SKIP_ROLE_NOT_ENABLED,
    adapter_dropped_field_notes,
    build_advisory_disagreement,
    resolve_sidecar_role_status,
    run_sidecar_llm_with_timeout,
)
from app.routing.llm_route_plan_json import extract_route_plan_candidate_json
from app.routing.route_plan_models import (
    ROUTE_PLAN_GENERATOR_MODEL_FAMILY,
    ROUTE_PLAN_GENERATOR_ROLE,
    RoutePlanPreflightResult,
    RoutePlanValidationResult,
)
from app.routing.route_plan_validator import validate_route_plan_candidate
from app.routing.supporter_registry import build_supporter_trace
from app.safeguards.spl_validator import APPROVED_DATAMODELS

ROUTE_PLAN_LLM_TIMEOUT_SECONDS = 3.0

DROP_JSON_EXTRACTION_FAILED = "json_extraction_failed"
DROP_SCHEMA_INVALID = "schema_invalid"
DROP_SPL_IN_CANDIDATE = "spl_in_candidate_forbidden"
DROP_UNKNOWN_DATAMODEL = "unknown_datamodel"
DROP_ROUTE_VALIDATION_FAILED = "route_plan_validation_failed"
DROP_ROUTING_SHADOW_DISABLED = "routing_shadow_disabled"
DROP_LLM_TIMED_OUT = "llm_timed_out"

FORBIDDEN_CANDIDATE_KEYS = frozenset(
    {
        "detection_ref",
        "lookup_name",
        "candidate_spl",
        "spl",
        "mcp",
        "template_id",
        "execution_eligible",
        "execution_authorized",
    }
)

SPL_FRAGMENT_PATTERN = re.compile(
    r"\||\bsearch\b|\btstats\b|\bfrom\b.*\bdatamodel\b|\bstats\b|\bhead\b",
    re.IGNORECASE,
)


@dataclass
class LlmRoutePlanCandidateResult:
    llm_called: bool = False
    llm_role: str | None = None
    llm_model_family: str | None = None
    llm_candidate_route_plan_available: bool = False
    llm_candidate_dropped_reasons: list[str] = field(default_factory=list)
    deterministic_route_plan_wins: bool = True
    disagreements: list[dict[str, Any]] = field(default_factory=list)
    candidate: dict[str, Any] | None = None
    validation: RoutePlanValidationResult | None = None
    extraction_warnings: list[str] = field(default_factory=list)
    adapter_warnings: list[str] = field(default_factory=list)
    resolved_provider: str | None = None
    resolved_model: str | None = None
    rejected_reason: str | None = None
    skipped_reason: str | None = None
    candidate_reason: str | None = None
    supporter_trace: dict[str, Any] | None = None

    def apply_to_shadow(self, shadow: dict[str, Any]) -> None:
        shadow["llm_called"] = self.llm_called
        shadow["llm_role"] = self.llm_role
        shadow["llm_model_family"] = self.llm_model_family
        shadow["llm_candidate_route_plan_available"] = self.llm_candidate_route_plan_available
        shadow["llm_candidate_dropped_reasons"] = list(self.llm_candidate_dropped_reasons)
        shadow["deterministic_route_plan_wins"] = self.deterministic_route_plan_wins
        shadow["disagreements"] = list(self.disagreements)
        if self.resolved_provider:
            shadow["llm_resolved_provider"] = self.resolved_provider
        if self.resolved_model:
            shadow["llm_resolved_model"] = self.resolved_model
        if self.rejected_reason:
            shadow["llm_rejected_reason"] = self.rejected_reason
        if self.skipped_reason:
            shadow["llm_skipped_reason"] = self.skipped_reason
        for note in self.extraction_warnings + self.adapter_warnings:
            if note not in shadow["warnings"]:
                shadow["warnings"].append(note)
        if self.supporter_trace is not None:
            shadow["supporter_trace"] = self.supporter_trace


def generate_llm_route_plan_candidate(
    user_query: str,
    *,
    preflight: RoutePlanPreflightResult,
    llm_raw_output_provider: Callable[[], str] | None = None,
    deterministic_primary_skill: str | None = None,
) -> LlmRoutePlanCandidateResult:
    """Generate a shadow route-plan candidate when governance allows."""
    result = LlmRoutePlanCandidateResult(
        llm_role=ROUTE_PLAN_GENERATOR_ROLE,
        llm_model_family=ROUTE_PLAN_GENERATOR_MODEL_FAMILY,
    )

    if not settings.routing_llm_shadow_enabled:
        result.skipped_reason = DROP_ROUTING_SHADOW_DISABLED
        result.llm_candidate_dropped_reasons = [DROP_ROUTING_SHADOW_DISABLED]
        return result

    assist_invoked = llm_raw_output_provider is not None
    role_status = resolve_sidecar_role_status(
        ROUTE_PLAN_GENERATOR_ROLE,
        reasoning_rejection_reason=REASONING_REJECTION_ROUTING,
        assist_invoked=assist_invoked,
    )
    result.resolved_provider = role_status.resolved_provider
    result.resolved_model = role_status.resolved_model

    if role_status.rejected_reason:
        result.rejected_reason = role_status.rejected_reason
        result.llm_candidate_dropped_reasons = [role_status.rejected_reason]
        return result

    if role_status.llm_assist_skipped_reason:
        result.skipped_reason = role_status.llm_assist_skipped_reason
        result.llm_candidate_dropped_reasons = [role_status.llm_assist_skipped_reason]
        return result

    if not assist_invoked:
        result.skipped_reason = SKIP_NO_PROVIDER_CONFIGURED
        result.llm_candidate_dropped_reasons = [SKIP_NO_PROVIDER_CONFIGURED]
        return result

    result.llm_called = True
    call = run_sidecar_llm_with_timeout(
        llm_raw_output_provider,
        timeout_seconds=ROUTE_PLAN_LLM_TIMEOUT_SECONDS,
    )
    if call.timed_out or not call.raw_output:
        result.llm_candidate_dropped_reasons = [DROP_LLM_TIMED_OUT]
        result.adapter_warnings.extend(call.notes)
        return result

    return _process_llm_raw_output(
        call.raw_output,
        user_query=user_query,
        preflight=preflight,
        result=result,
        deterministic_primary_skill=deterministic_primary_skill,
    )


def _process_llm_raw_output(
    raw_output: str,
    *,
    user_query: str,
    preflight: RoutePlanPreflightResult,
    result: LlmRoutePlanCandidateResult,
    deterministic_primary_skill: str | None,
) -> LlmRoutePlanCandidateResult:
    del preflight  # reserved for future prompt assembly

    extraction = extract_route_plan_candidate_json(raw_output)
    result.extraction_warnings = list(extraction.warnings)
    if not extraction.parsed_ok or extraction.payload is None:
        result.llm_candidate_dropped_reasons = [DROP_JSON_EXTRACTION_FAILED]
        return result

    adapter = adapt_llm_output(
        role=ROUTE_PLAN_GENERATOR_ROLE,
        raw_output=json.dumps(extraction.payload),
    )
    result.adapter_warnings.extend(adapter.warnings)
    if adapter.dropped_fields:
        result.adapter_warnings.extend(
            adapter_dropped_field_notes(
                adapter.dropped_fields,
                forbidden_keys=FORBIDDEN_CANDIDATE_KEYS,
                forbidden_substrings=("spl", "mcp", "lookup", "detection_ref", "template"),
            )
        )
        if "detection_ref" in adapter.dropped_fields:
            result.adapter_warnings.append("detection_ref_stripped")

    if not adapter.schema_valid or not adapter.accepted or adapter.normalized_payload is None:
        result.llm_candidate_dropped_reasons = [DROP_SCHEMA_INVALID]
        return result

    if _contains_forbidden_spl(adapter.normalized_payload):
        result.llm_candidate_dropped_reasons = [DROP_SPL_IN_CANDIDATE]
        return result

    if _payload_contains_key(extraction.payload, "detection_ref"):
        result.adapter_warnings.append("detection_ref_stripped")

    datamodel = adapter.normalized_payload.get("evidence_needs", {}).get("datamodel")
    if isinstance(datamodel, str) and datamodel not in APPROVED_DATAMODELS:
        result.llm_candidate_dropped_reasons = [DROP_UNKNOWN_DATAMODEL]
        return result

    candidate = expand_route_plan_candidate_payload(adapter.normalized_payload)
    validation = validate_route_plan_candidate(candidate)
    result.validation = validation
    result.candidate = candidate

    plan_for_supporters = validation.normalized_route_plan or candidate
    shadow_fragment = _shadow_fragment_from_plan(plan_for_supporters)
    result.supporter_trace = build_supporter_trace(
        plan_for_supporters,
        query=user_query,
        shadow=shadow_fragment,
        runtime_invoked=True,
    )

    if not validation.is_valid:
        result.llm_candidate_dropped_reasons = [DROP_ROUTE_VALIDATION_FAILED]
        return result

    result.llm_candidate_route_plan_available = True
    result.candidate_reason = "llm_shadow_candidate"
    result.disagreements = _compare_with_deterministic_route(
        validation.normalized_route_plan or candidate,
        deterministic_primary_skill=deterministic_primary_skill,
    )
    return result


def _shadow_fragment_from_plan(plan: dict[str, Any]) -> dict[str, Any]:
    fragment: dict[str, Any] = {
        "primary_skill": plan.get("primary_skill"),
        "pattern_id": plan.get("pattern_id"),
        "route_status": plan.get("route_status"),
        "source_class": plan.get("source_class"),
    }
    parameters = plan.get("parameters")
    if isinstance(parameters, dict):
        fragment["route_plan_parameters"] = dict(parameters)
    time_window = plan.get("time_window")
    if isinstance(time_window, str) and time_window.strip():
        fragment["route_plan_time_window"] = time_window
    return fragment


def expand_route_plan_candidate_payload(adapted: dict[str, Any]) -> dict[str, Any]:
    """Map compact LLM payload to full route-plan candidate dict."""
    evidence = dict(adapted.get("evidence_needs") or {})
    source_class = str(adapted.get("source_class") or "")
    primary_skill = str(adapted.get("primary_skill") or "")
    operation_type = str(adapted.get("operation_type") or "top_n")
    group_by_list = evidence.get("group_by") if isinstance(evidence.get("group_by"), list) else []
    group_field = str(group_by_list[0]) if group_by_list else "user"
    metric = evidence.get("metric") if isinstance(evidence.get("metric"), dict) else {}

    parameters: dict[str, Any] = {
        "group_by": {"field": group_field, "source_class": source_class},
        "metric": metric,
        "sort": {"field": "metric_value", "direction": "desc"},
        "limit": adapted.get("limit") if isinstance(adapted.get("limit"), int) else 10,
    }
    time_window = adapted.get("time_window")
    if time_window is not None:
        parameters["time_window"] = time_window

    pattern_id = f"llm_shadow_{primary_skill}_{operation_type}"
    post_enrichment: list[str] = []
    if primary_skill == "aggregate_and_rank":
        post_enrichment = ["notable_risk_lookup"]
        if source_class == "okta_authentication_logs" and operation_type == "top_n":
            pattern_id = "top_failed_okta_login_users"
            parameters["event_filter"] = {"event_type": "failed_login"}

    plan_time_window = time_window if isinstance(time_window, str) else "last 24 hours"
    if isinstance(time_window, dict):
        plan_time_window = time_window.get("earliest", "last 24 hours")

    return {
        "route_plan_id": f"rp_llm_shadow_{uuid.uuid4().hex[:12]}",
        "route_status": "route_ready",
        "primary_skill": primary_skill,
        "pattern_id": pattern_id,
        "operation_type": operation_type,
        "domain": "soc",
        "source_class": source_class,
        "entities": [group_field] if group_field else ["user"],
        "time_window": plan_time_window,
        "evidence_needs": evidence,
        "parameters": parameters,
        "missing_slots": [],
        "hard_preconditions": [],
        "model_advisory_metadata": {"rationale": adapted.get("rationale", "")},
        "deterministic_validation": {"validator": "stage3k_q1f"},
        "post_enrichment": post_enrichment,
    }


def _contains_forbidden_spl(payload: dict[str, Any]) -> bool:
    return bool(SPL_FRAGMENT_PATTERN.search(json.dumps(payload)))


def _payload_contains_key(payload: Any, key: str) -> bool:
    if isinstance(payload, dict):
        if key in payload:
            return True
        return any(_payload_contains_key(value, key) for value in payload.values())
    if isinstance(payload, list):
        return any(_payload_contains_key(item, key) for item in payload)
    return False


def _compare_with_deterministic_route(
    llm_plan: dict[str, Any],
    *,
    deterministic_primary_skill: str | None,
) -> list[dict[str, Any]]:
    if not deterministic_primary_skill:
        return []
    disagreements: list[dict[str, Any]] = []
    llm_skill = llm_plan.get("primary_skill")
    if llm_skill and llm_skill != deterministic_primary_skill:
        disagreements.append(
            build_advisory_disagreement(
                field="primary_skill",
                llm_value=llm_skill,
                deterministic_value=deterministic_primary_skill,
                reason_for_deterministic_win="deterministic_skill_router_authority",
            )
        )
    evidence = llm_plan.get("evidence_needs") if isinstance(llm_plan.get("evidence_needs"), dict) else {}
    parameters = llm_plan.get("parameters") if isinstance(llm_plan.get("parameters"), dict) else {}
    group_by = parameters.get("group_by") if isinstance(parameters.get("group_by"), dict) else {}
    llm_group = group_by.get("field")
    evidence_groups = evidence.get("group_by") if isinstance(evidence.get("group_by"), list) else []
    if evidence_groups and llm_group and evidence_groups[0] != llm_group:
        disagreements.append(
            build_advisory_disagreement(
                field="group_by",
                llm_value=evidence_groups[0],
                deterministic_value=llm_group,
                reason_for_deterministic_win="normalized_parameters_authority",
            )
        )
    return disagreements


def skipped_reason_to_candidate_reason(skipped: str | None) -> str:
    if skipped in {SKIP_LLM_DISABLED, SKIP_NO_PROVIDER_CONFIGURED, SKIP_ROLE_NOT_CONFIGURED, SKIP_ROLE_NOT_ENABLED}:
        return "live_llm_routing_disabled"
    if skipped == DROP_ROUTING_SHADOW_DISABLED:
        return "routing_shadow_disabled"
    return "live_llm_routing_disabled"
