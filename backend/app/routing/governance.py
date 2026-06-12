from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.coverage.question_runtime_map import question_runtime_entry
from app.query_understanding.models import QueryUnderstandingResult
from app.routing.skills import valid_skill
from app.use_cases.registry import get_use_case, match_use_cases

ROUTING_MODE_DETERMINISTIC_ONLY = "deterministic_only"
ROUTING_MODE_LLM_SHADOW_ONLY = "llm_shadow_only"
ROUTING_MODE_LLM_ASSISTED_SEMANTIC = "llm_assisted_semantic"
ROUTING_MODE_LLM_PRIMARY_LAB = "llm_primary_lab"

ALLOWED_OUTPUT_TYPES = {"investigation", "clarification", "spl", "knowledge", "summary"}
ALLOWED_PRIORITIES = {"P1", "P2", "P3", "P4"}
ALLOWED_SOURCE_TYPES = {
    "splunk_auth_evidence",
    "splunk_metadata_discovery",
    "soc_kb_playbook",
    "mitre_lookup",
    "identity_context",
    "asset_context",
    "firewall_pivot",
    "edr_post_login_activity",
    "vpn_context",
    "dns_context",
}

CONTEXT_DEPENDENT_REFERENCES = (
    "this alert",
    "this incident",
    "this event",
    "this login",
    "this user",
    "this host",
    "map this",
    "analyze this",
)
CONTEXT_MARKERS = (
    "index=",
    "sourcetype=",
    "rule:",
    "rule ",
    "alert:",
    "notable",
    "signature=",
    "event id",
    "eventid",
    "host=",
    "user=",
    "src_ip=",
    "source ip",
    "time window",
)
CLARIFICATION_QUESTION = (
    "Please provide the alert title, rule name, SPL, notable event details, or key fields "
    "such as host, user, source IP, event type, and time window."
)


@dataclass(frozen=True)
class LLMEvidenceNeed:
    need_id: str
    source_type: str
    why: str
    priority: str
    suggested_tool_hint: str = ""
    requires_validation: bool = True


@dataclass
class LLMSemanticAdvisoryResult:
    raw_query: str
    llm_primary_intent_candidate: str | None = None
    llm_use_case_candidate: str | None = None
    llm_question_ref_candidate: str | None = None
    llm_coverage_id_candidate: str | None = None
    llm_selected_skill_candidate: str | None = None
    llm_requested_output_type_candidate: str | None = None
    llm_evidence_needs: list[dict[str, Any]] = field(default_factory=list)
    llm_optional_pivots: list[str] = field(default_factory=list)
    llm_suggested_sources: list[str] = field(default_factory=list)
    llm_suggested_mcp_tools: list[str] = field(default_factory=list)
    llm_reasoning_summary: str | None = None
    llm_clarification_candidate: str | None = None
    llm_confidence_metadata: dict[str, Any] = field(default_factory=dict)
    schema_valid: bool = True
    registry_valid: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RouteDecisionRecord:
    raw_query: str
    routing_mode: str
    deterministic_intent: str | None
    deterministic_use_case_id: str | None
    deterministic_question_ref: str | None
    deterministic_match_path: str | None
    deterministic_selected_skill: str | None
    deterministic_confidence_metadata: dict[str, Any]
    llm_intent_candidate: str | None
    llm_use_case_candidate: str | None
    llm_question_ref_candidate: str | None
    llm_coverage_id_candidate: str | None
    llm_selected_skill_candidate: str | None
    llm_confidence_metadata: dict[str, Any]
    selected_intent: str | None
    selected_use_case_id: str | None
    selected_question_ref: str | None
    selected_coverage_id: str | None
    selected_skill: str
    selected_by: str
    selection_reason: str
    adjudication_status: str
    adjudication_reason: str
    deterministic_reconsidered_after_llm: bool
    disagreements: list[str]
    guard_checks: list[str]
    evidence_needs: list[dict[str, Any]]
    deterministic_tool_mapping_summary: list[dict[str, Any]]
    learning_record_enabled: bool
    timestamp: str

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def build_llm_semantic_advisory(raw_query: str, llm_route: dict[str, Any] | None) -> LLMSemanticAdvisoryResult | None:
    if not llm_route:
        return None
    metadata = llm_route.get("metadata") if isinstance(llm_route.get("metadata"), dict) else {}
    advisory = LLMSemanticAdvisoryResult(
        raw_query=raw_query,
        llm_primary_intent_candidate=_optional_str(metadata.get("primary_intent") or metadata.get("intent")),
        llm_use_case_candidate=_optional_str(metadata.get("use_case_id") or metadata.get("candidate_use_case_id")),
        llm_question_ref_candidate=_optional_str(metadata.get("question_ref") or metadata.get("nearest_question_ref")),
        llm_coverage_id_candidate=_optional_str(metadata.get("coverage_id") or metadata.get("candidate_coverage_id")),
        llm_selected_skill_candidate=_optional_str(metadata.get("selected_skill") or llm_route.get("skill")),
        llm_requested_output_type_candidate=_optional_str(metadata.get("requested_output_type")),
        llm_optional_pivots=[str(item) for item in metadata.get("optional_pivots", []) if item],
        llm_suggested_sources=[str(item) for item in metadata.get("suggested_sources", []) if item],
        llm_suggested_mcp_tools=[str(item) for item in metadata.get("suggested_mcp_tools", []) if item],
        llm_reasoning_summary=_optional_str(metadata.get("reasoning_summary") or "; ".join(llm_route.get("reasons", [])[:2])),
        llm_clarification_candidate=_optional_str(metadata.get("clarification")),
        llm_confidence_metadata={"skill_confidence": llm_route.get("confidence"), **dict(metadata.get("confidence_metadata", {}))},
    )
    advisory.llm_evidence_needs = [_normalize_evidence_need(item, advisory) for item in metadata.get("evidence_needs", []) if isinstance(item, dict)]
    _validate_advisory(advisory)
    return advisory


def deterministic_use_case_id(query: str) -> str | None:
    matches = match_use_cases(query, limit=1)
    return matches[0].use_case_id if matches else None


def requires_context_clarification(query: str) -> bool:
    normalized = " ".join(query.lower().split())
    if not any(reference in normalized for reference in CONTEXT_DEPENDENT_REFERENCES):
        return False
    return not any(marker in normalized for marker in CONTEXT_MARKERS)


def clarification_route(query: str) -> dict[str, Any]:
    return {
        "skill": "knowledge_recall",
        "tool_plan": ["needs_clarification"],
        "confidence": 1.0,
        "reasons": ["deterministic clarification required for context-dependent request", CLARIFICATION_QUESTION],
        "requested_output_type": "clarification",
    }


def normalize_assisted_selection(
    *,
    query: str,
    deterministic: dict[str, Any],
    advisory: LLMSemanticAdvisoryResult | None,
    understanding: QueryUnderstandingResult | None = None,
) -> tuple[dict[str, Any], str, list[str], list[str]]:
    selected = dict(deterministic)
    selected_by = "deterministic"
    disagreements: list[str] = []
    guard_checks = ["llm_confidence_metadata_only", "deterministic_registry_controls_final_route"]
    det_use_case = deterministic_use_case_id(query)
    if understanding is None:
        return selected, selected_by, disagreements, guard_checks
    deterministic_uncertain = _deterministic_uncertain(deterministic, understanding)

    if advisory is None:
        return selected, selected_by, disagreements, guard_checks

    llm_skill = advisory.llm_selected_skill_candidate
    if llm_skill and llm_skill != deterministic.get("skill"):
        disagreements.append("selected_skill")
    if llm_skill and not valid_skill(llm_skill):
        advisory.warnings.append(f"unknown_llm_selected_skill_rejected:{llm_skill}")
        guard_checks.append("unknown_llm_skill_rejected")

    llm_use_case = advisory.llm_use_case_candidate
    if llm_use_case and llm_use_case != det_use_case:
        disagreements.append("use_case_id")
    if llm_use_case and get_use_case(llm_use_case) is None:
        advisory.warnings.append(f"unknown_llm_use_case_id_rejected:{llm_use_case}")
        guard_checks.append("unknown_llm_use_case_rejected")

    llm_question_ref = advisory.llm_question_ref_candidate
    if llm_question_ref and question_runtime_entry(llm_question_ref) is None:
        advisory.warnings.append(f"unknown_llm_question_ref_rejected:{llm_question_ref}")
        guard_checks.append("unknown_llm_question_ref_rejected")

    validated = _validated_llm_route_candidate(advisory)
    if deterministic_uncertain and validated:
        selected = {
            "skill": validated["skill"],
            "tool_plan": _tool_plan_for_skill(validated["skill"]),
            "confidence": max(float(deterministic.get("confidence", 0.0)), 0.64),
            "reasons": list(deterministic.get("reasons", []))
            + [
                "LLM advisory candidate validated against deterministic registries",
                f"validated_source:{validated['source']}",
            ],
        }
        selected_by = "llm_advisory_validated"
        guard_checks.append("llm_candidate_registry_validated")
        guard_checks.append("deterministic_reconsidered_after_llm")
        return selected, selected_by, sorted(set(disagreements)), guard_checks

    if (llm_skill and llm_skill == deterministic.get("skill")) or (llm_use_case and llm_use_case == det_use_case):
        selected_by = "llm_assisted_semantic_normalized"
        selected["reasons"] = list(selected.get("reasons", [])) + ["LLM advisory agreed after deterministic registry normalization"]

    return selected, selected_by, sorted(set(disagreements)), guard_checks


def build_route_decision_record(
    *,
    query: str,
    routing_mode: str,
    deterministic: dict[str, Any],
    advisory: LLMSemanticAdvisoryResult | None,
    selected: dict[str, Any],
    selected_by: str,
    selection_reason: str,
    disagreements: list[str],
    guard_checks: list[str],
    deterministic_tool_mapping_summary: list[dict[str, Any]] | None = None,
    learning_record_enabled: bool = True,
    understanding: QueryUnderstandingResult | None = None,
    qu_failed: bool = False,
    adjudication_status: str | None = None,
    adjudication_reason: str | None = None,
) -> RouteDecisionRecord:
    det_use_case = deterministic_use_case_id(query)
    if understanding is not None and understanding.mapped_use_case_ids and not det_use_case:
        det_use_case = understanding.mapped_use_case_ids[0]

    selected_question_ref = understanding.mapped_question_ref if understanding else None
    selected_coverage_id = understanding.mapped_coverage_id if understanding else None
    if selected_by == "llm_advisory_validated" and advisory:
        validated = _validated_llm_route_candidate(advisory)
        if validated:
            selected_question_ref = validated.get("question_ref")
            selected_coverage_id = validated.get("coverage_id")

    if adjudication_status is None or adjudication_reason is None:
        if qu_failed or understanding is None:
            adjudication_status = "skipped_qu_failed"
            adjudication_reason = "Query understanding unavailable; deterministic failover only."
        else:
            adjudication_status, adjudication_reason = _adjudication_status(
                selected_by=selected_by,
                deterministic=deterministic,
                understanding=understanding,
                advisory=advisory,
            )

    qu_confidence = understanding.confidence if understanding else None
    qu_match_path = understanding.deterministic_match_path if understanding else "qu_unavailable"
    qu_question_ref = understanding.mapped_question_ref if understanding else None
    qu_advisory_recommended = understanding.llm_advisory_recommended if understanding else True
    qu_registry_consistency = understanding.registry_consistency if understanding else "not_evaluated"
    qu_registry_warnings = list(understanding.registry_warnings) if understanding else []

    return RouteDecisionRecord(
        raw_query=query,
        routing_mode=routing_mode,
        deterministic_intent=str(deterministic.get("skill")),
        deterministic_use_case_id=det_use_case,
        deterministic_question_ref=qu_question_ref,
        deterministic_match_path=qu_match_path,
        deterministic_selected_skill=str(deterministic.get("skill")),
        deterministic_confidence_metadata={
            "confidence": deterministic.get("confidence"),
            "query_understanding_confidence": qu_confidence,
            "llm_advisory_recommended": qu_advisory_recommended,
            "registry_consistency": qu_registry_consistency,
            "registry_warnings": qu_registry_warnings,
            "qu_failed": qu_failed,
        },
        llm_intent_candidate=advisory.llm_primary_intent_candidate if advisory else None,
        llm_use_case_candidate=advisory.llm_use_case_candidate if advisory else None,
        llm_question_ref_candidate=advisory.llm_question_ref_candidate if advisory else None,
        llm_coverage_id_candidate=advisory.llm_coverage_id_candidate if advisory else None,
        llm_selected_skill_candidate=advisory.llm_selected_skill_candidate if advisory else None,
        llm_confidence_metadata=advisory.llm_confidence_metadata if advisory else {},
        selected_intent=str(selected.get("skill")),
        selected_use_case_id=det_use_case,
        selected_question_ref=selected_question_ref,
        selected_coverage_id=selected_coverage_id,
        selected_skill=str(selected.get("skill")),
        selected_by=selected_by,
        selection_reason=selection_reason,
        adjudication_status=adjudication_status,
        adjudication_reason=adjudication_reason,
        deterministic_reconsidered_after_llm=selected_by == "llm_advisory_validated",
        disagreements=sorted(set(disagreements)),
        guard_checks=guard_checks,
        evidence_needs=advisory.llm_evidence_needs if advisory else [],
        deterministic_tool_mapping_summary=deterministic_tool_mapping_summary or [],
        learning_record_enabled=learning_record_enabled,
        timestamp=datetime.now(UTC).isoformat(),
    )


def _normalize_evidence_need(item: dict[str, Any], advisory: LLMSemanticAdvisoryResult) -> dict[str, Any]:
    source_type = str(item.get("source_type") or "").strip()
    priority = str(item.get("priority") or "P3").strip().upper()
    if source_type not in ALLOWED_SOURCE_TYPES:
        advisory.warnings.append(f"unknown_source_type_rejected:{source_type}")
        source_type = "unknown"
    if priority not in ALLOWED_PRIORITIES:
        advisory.warnings.append(f"unknown_priority_rejected:{priority}")
        priority = "P3"
    return LLMEvidenceNeed(
        need_id=str(item.get("need_id") or source_type or "unknown"),
        source_type=source_type,
        why=str(item.get("why") or ""),
        priority=priority,
        suggested_tool_hint=str(item.get("suggested_tool_hint") or ""),
        requires_validation=True,
    ).__dict__


def _deterministic_uncertain(deterministic: dict[str, Any], understanding: Any) -> bool:
    match_path = getattr(understanding, "deterministic_match_path", "")
    if match_path in {"exact_105_question", "exact_105_plus_use_case_catalog", "use_case_catalog"}:
        return (
            float(deterministic.get("confidence", 0.0)) < 0.70
            or deterministic.get("tool_plan") == ["needs_clarification"]
            or getattr(understanding, "llm_advisory_recommended", False)
        )
    return (
        float(deterministic.get("confidence", 0.0)) < 0.70
        or deterministic.get("tool_plan") == ["needs_clarification"]
        or getattr(understanding, "llm_advisory_recommended", False)
        or match_path in {"near_105_question", "out_of_registry"}
    )


def _validated_llm_route_candidate(advisory: LLMSemanticAdvisoryResult | None) -> dict[str, Any] | None:
    if advisory is None:
        return None
    question_ref = advisory.llm_question_ref_candidate
    if question_ref:
        entry = question_runtime_entry(question_ref)
        if entry:
            skill = _entry_skill(entry)
            if valid_skill(skill):
                return {
                    "source": "question_runtime_map_105",
                    "skill": skill,
                    "question_ref": entry.get("question_ref"),
                    "coverage_id": entry.get("manifest_coverage_id"),
                }
    use_case_id = advisory.llm_use_case_candidate
    if use_case_id:
        use_case = get_use_case(use_case_id)
        if use_case and valid_skill(use_case.primary_skill):
            return {
                "source": "use_case_catalog",
                "skill": use_case.primary_skill,
                "question_ref": None,
                "coverage_id": None,
            }
    skill = advisory.llm_selected_skill_candidate
    if skill and valid_skill(skill):
        return {
            "source": "skill_registry",
            "skill": skill,
            "question_ref": None,
            "coverage_id": None,
        }
    return None


def _entry_skill(entry: dict[str, Any]) -> str:
    for key in ("legacy_router_intent_hint", "proposed_primary_skill"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "knowledge_recall"


def _tool_plan_for_skill(skill: str) -> list[str]:
    plans = {
        "alert_summary": ["retrieve_alert_context", "prepare_time_bounded_summary"],
        "spl_generation": ["draft_spl_spec", "validate_spl_before_execution"],
        "attack_discovery": ["classify_auth_pattern", "prepare_spl_spec", "require_spl_validation"],
        "knowledge_recall": ["retrieve_approved_context", "summarize_bounded_reference"],
        "guided_investigation": ["prepare_guided_investigation", "require_analyst_validation"],
        "action_planning": ["retrieve_approved_context", "prepare_action_plan"],
    }
    return list(plans.get(skill, ["retrieve_approved_context", "summarize_bounded_reference"]))


def _adjudication_status(
    *,
    selected_by: str,
    deterministic: dict[str, Any],
    understanding: Any,
    advisory: LLMSemanticAdvisoryResult | None,
) -> tuple[str, str]:
    if selected_by == "llm_advisory_validated":
        return "accepted", "LLM candidate validated against deterministic registry and used because deterministic path was uncertain."
    if advisory is None:
        if getattr(understanding, "llm_advisory_recommended", False):
            return "recommended_not_called", "Query understanding recommended LLM advisory, but no advisory was available in this routing mode."
        return "not_needed", "Deterministic path was sufficient."
    if _validated_llm_route_candidate(advisory) is None:
        return "rejected", "LLM candidate did not validate against known question, use-case, or skill registries."
    if not _deterministic_uncertain(deterministic, understanding):
        return "not_needed", "Deterministic path was confident; LLM advisory recorded for comparison only."
    return "rejected", "LLM candidate was not accepted after deterministic policy checks."


def _validate_advisory(advisory: LLMSemanticAdvisoryResult) -> None:
    if advisory.llm_selected_skill_candidate and not valid_skill(advisory.llm_selected_skill_candidate):
        advisory.registry_valid = False
        advisory.warnings.append(f"unknown_llm_selected_skill_rejected:{advisory.llm_selected_skill_candidate}")
    if advisory.llm_use_case_candidate and get_use_case(advisory.llm_use_case_candidate) is None:
        advisory.registry_valid = False
        advisory.warnings.append(f"unknown_llm_use_case_id_rejected:{advisory.llm_use_case_candidate}")
    if advisory.llm_requested_output_type_candidate and advisory.llm_requested_output_type_candidate not in ALLOWED_OUTPUT_TYPES:
        advisory.warnings.append(f"unknown_requested_output_type_rejected:{advisory.llm_requested_output_type_candidate}")
    advisory.registry_valid = not advisory.warnings


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
