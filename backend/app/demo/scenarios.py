from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from app.orchestration.human_review import human_review, no_human_review
from app.orchestration.workflow_planner import plan_workflow
from app.safeguards.spl_validator import validate_spl

CREATED_AT = "2026-05-24T00:00:00Z"
EVIDENCE_ORIGIN = "coe_synthetic_fixture"
DEMO_BADGE = "COE synthetic demo"


@dataclass(frozen=True)
class DemoScenario:
    scenario_id: str
    label: str
    category: str
    query: str
    environment_mode: str
    expected_skill: str
    expected_sources: list[str]
    expected_sufficiency_mode: str
    mcp_execution_mode: str
    saia_available: bool
    rag_available: bool
    analyst_summary: str
    trace_explanation: list[str]
    candidate_spl: str | None = None
    source_evidence: list[dict[str, Any]] | None = None
    structured_context: dict[str, Any] | None = None
    confidence: float = 0.91


def list_demo_scenarios() -> list[dict[str, Any]]:
    return [_scenario_summary(item) for item in SCENARIOS.values()]


def run_demo_scenario(scenario_id: str) -> dict[str, Any]:
    scenario = SCENARIOS[scenario_id]
    trace_id = f"demo-{scenario.scenario_id}-{uuid4().hex[:8]}"
    workflow = plan_workflow(
        selected_skill=scenario.expected_skill,
        tool_plan=_tool_plan(scenario),
        query=scenario.query,
        trace_id=trace_id,
        telemetry=_NoopTelemetry(),
    )
    workflow["available_sources"] = list(scenario.expected_sources)
    workflow["missing_sources"] = []
    workflow["message"] = "Demo workflow plan created from COE synthetic fixture. No live execution has started."

    candidate_spl, spl_validation = _spl_payloads(scenario, trace_id)
    execution = _execution_payload(scenario, trace_id, spl_validation)
    source_evidence = _with_trace(deepcopy(scenario.source_evidence or []), trace_id)
    structured_context = _with_context_trace(deepcopy(scenario.structured_context or {}), scenario, trace_id, source_evidence)
    context_sufficiency = _context_sufficiency(scenario)
    review = _human_review(scenario, execution)

    return {
        "trace_id": trace_id,
        "demo_mode": True,
        "evidence_origin": EVIDENCE_ORIGIN,
        "no_live_customer_data": True,
        "demo_badge": DEMO_BADGE,
        "environment_mode": scenario.environment_mode,
        "mcp_execution_mode": scenario.mcp_execution_mode,
        "saia_available": scenario.saia_available,
        "rag_available": scenario.rag_available,
        "fallback_active": not scenario.saia_available,
        "analyst_summary": scenario.analyst_summary,
        "trace_explanation": list(scenario.trace_explanation),
        "message": scenario.analyst_summary,
        "note": (
            "COE synthetic fixture only. No live customer data, final LLM synthesis, answer guard, "
            "real Splunk execution, or external remediation integration was used."
        ),
        "user_query": scenario.query,
        "selected_skill": scenario.expected_skill,
        "tool_plan": _tool_plan(scenario),
        "confidence": scenario.confidence,
        "routing_mode": "deterministic_demo_fixture",
        "disagreement": False,
        "disagreement_reason": None,
        "workflow_plan": workflow,
        "candidate_spl": candidate_spl,
        "spl_validation": spl_validation,
        "execution": execution,
        "human_review": review,
        "source_evidence": source_evidence,
        "structured_context": structured_context,
        "context_sufficiency": context_sufficiency,
    }


def _scenario_summary(scenario: DemoScenario) -> dict[str, Any]:
    return {
        "scenario_id": scenario.scenario_id,
        "label": scenario.label,
        "category": scenario.category,
        "query": scenario.query,
        "environment_mode": scenario.environment_mode,
        "demo_badge": DEMO_BADGE,
        "expected_skill": scenario.expected_skill,
        "expected_sources": list(scenario.expected_sources),
        "expected_sufficiency_mode": scenario.expected_sufficiency_mode,
        "mcp_execution_mode": scenario.mcp_execution_mode,
        "saia_available": scenario.saia_available,
        "rag_available": scenario.rag_available,
        "evidence_origin": EVIDENCE_ORIGIN,
        "no_live_customer_data": True,
    }


def _tool_plan(scenario: DemoScenario) -> list[str]:
    if scenario.expected_skill == "knowledge_recall":
        return ["retrieve_governed_soc_kb", "structure_context", "context_sufficiency_gate"]
    if scenario.expected_skill == "spl_generation":
        return ["retrieve_spl_policy", "generate_candidate_spl", "validate_spl", "return_for_analyst_review"]
    return ["route_only", "build_source_evidence", "structure_context", "context_sufficiency_gate"]


def _spl_payloads(scenario: DemoScenario, trace_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not scenario.candidate_spl:
        return None, None
    validation = validate_spl(scenario.candidate_spl)
    provider = "stage_3c_stub_generator" if scenario.saia_available else "deterministic_fallback_generator"
    capability_profile = {
        "environment_mode": scenario.environment_mode,
        "mcp_available": True,
        "discovery_mode": "fixture_redacted_metadata",
        "saia_available": scenario.saia_available,
        "saia_usable": scenario.saia_available,
        "saia_configured_mode": "available" if scenario.saia_available else "unavailable",
        "fallback_required": not scenario.saia_available,
        "available_core_tools": ["splunk.search", "splunk.saved_search.read"],
        "available_saia_tools": ["saia_generate_spl"] if scenario.saia_available else [],
        "blocked_tool_categories": ["assistant_write", "admin", "remediation"],
    }
    candidate = {
        "trace_id": trace_id,
        "skill": scenario.expected_skill,
        "user_query": scenario.query,
        "candidate_spl": scenario.candidate_spl,
        "generation_mode": "fixture_stage_3c_stub",
        "confidence": 0.84,
        "assumptions": ["COE synthetic fixture; analyst must review before any execution."],
        "warnings": ["demo_fixture_not_live_data"],
        "selected_candidate_spl_provider": provider,
        "reason": "Demo scenario uses deterministic fixture SPL and existing validation policy.",
        "saia_available": scenario.saia_available,
        "saia_usable": scenario.saia_available,
        "fallback_required": not scenario.saia_available,
        "candidate_spl_generated": True,
        "validation_required": True,
        "execution_eligible": validation["approved"] and scenario.mcp_execution_mode == "mock_success",
        "capability_profile": capability_profile,
    }
    validation_payload = {
        "approved": validation["approved"],
        "normalized_spl": validation["normalized_spl"],
        "reject_reasons": validation["reject_reasons"],
        "warnings": validation["warnings"] + ["demo_fixture_not_live_data"],
        "enforced_limits": validation["enforced_limits"],
        "policy_version": validation["policy_version"],
        "selected_candidate_spl_provider": provider,
        "candidate_provider_reason": "Fixture SPL passed through deterministic validation.",
        "saia_available": scenario.saia_available,
        "fallback_required": not scenario.saia_available,
        "spl_explanation_provider": "deterministic_fixture",
        "spl_optimization_provider": "disabled_in_demo",
        "spl_guidance_provider": "governed_policy_fixture",
        "optimization_applied": False,
        "optimization_revalidation_status": {"approved": validation["approved"], "mode": "not_applied"},
        "capability_profile": capability_profile,
    }
    return candidate, validation_payload


def _execution_payload(scenario: DemoScenario, trace_id: str, spl_validation: dict[str, Any] | None) -> dict[str, Any]:
    if scenario.mcp_execution_mode == "not_required":
        return {
            "status": "skipped",
            "execution_intent": "none",
            "selected_mcp_server": None,
            "selected_mcp_tool": None,
            "tool_selection_status": "unavailable",
            "tool_selection_reason": "spl_not_required_for_demo_scenario",
            "executed_spl": None,
            "result_count": 0,
            "results_preview": [],
            "block_reason": None,
            "duration_ms": 0,
        }
    if scenario.mcp_execution_mode == "mock_success" and spl_validation and spl_validation.get("approved"):
        return {
            "status": "executed",
            "execution_intent": "mock_preview",
            "selected_mcp_server": "splunk",
            "selected_mcp_tool": "search",
            "tool_selection_status": "selected",
            "tool_selection_reason": "mock execution explicitly enabled for this fixture only",
            "executed_spl": spl_validation["normalized_spl"],
            "result_count": 3,
            "results_preview": _mock_rows_for(trace_id),
            "block_reason": None,
            "duration_ms": 7,
        }
    return {
        "status": "requires_human_review",
        "execution_intent": "validated_spl_review",
        "selected_mcp_server": "splunk" if spl_validation else None,
        "selected_mcp_tool": "search" if spl_validation else None,
        "tool_selection_status": "requires_human_review" if spl_validation else "unavailable",
        "tool_selection_reason": "execution disabled; candidate SPL is shown for analyst review only",
        "executed_spl": None,
        "result_count": 0,
        "results_preview": [],
        "block_reason": "mcp_global_execution_disabled" if spl_validation else None,
        "duration_ms": 0,
    }


def _human_review(scenario: DemoScenario, execution: dict[str, Any]) -> dict[str, Any]:
    if scenario.expected_sufficiency_mode in {"spl_review_only", "analyst_review_required"} or execution["status"] == "requires_human_review":
        return human_review(
            "demo_analyst_review",
            execution.get("block_reason") or scenario.expected_sufficiency_mode,
            "soc_analyst",
            ["review_fixture_evidence", "copy_candidate_spl", "do_not_execute_fixture_data"],
            "Review the synthetic fixture output. It is not live production evidence and is not executed.",
        )
    return no_human_review()


def _with_trace(evidence: list[dict[str, Any]], trace_id: str) -> list[dict[str, Any]]:
    for item in evidence:
        item["trace_id"] = trace_id
        item.setdefault("created_at", CREATED_AT)
    return evidence


def _with_context_trace(
    context: dict[str, Any],
    scenario: DemoScenario,
    trace_id: str,
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    context.setdefault("trace_id", trace_id)
    context["trace_id"] = trace_id
    context.setdefault("query", scenario.query)
    context.setdefault("selected_skill", scenario.expected_skill)
    context.setdefault("source_evidence_refs", [item["evidence_id"] for item in evidence])
    context.setdefault("policy_context_refs", ["stage-3j-d-demo-fixture-policy"])
    context.setdefault("assumptions", ["Fixture-backed demo path; no live customer telemetry."])
    context.setdefault("warnings", ["coe_synthetic_fixture"])
    context.setdefault("missing_evidence", [])
    context.setdefault("allowed_conclusions", ["Describe only fixture-supported behavior."])
    context.setdefault("prohibited_conclusions", ["Do not claim live production impact or execute remediation."])
    context.setdefault("context_quality", "sufficient")
    context.setdefault("synthesis_allowed", False)
    return context


def _context_sufficiency(scenario: DemoScenario) -> dict[str, Any]:
    status = scenario.expected_sufficiency_mode
    return {
        "status": status,
        "synthesis_allowed": False,
        "synthesis_readiness": status in {"full_answer", "partial_answer", "knowledge_only_answer"},
        "reasons": [
            "demo_fixture_has_source_refs",
            "final_synthesis_disabled_by_stage_boundary",
            f"evidence_origin:{EVIDENCE_ORIGIN}",
        ],
        "missing_evidence": [] if status != "partial_answer" else ["live_mcp_execution"],
        "human_review": None,
    }


def _evidence(
    evidence_id: str,
    source_type: str,
    source_name: str,
    result_count: int,
    fields: list[str],
    rows: list[dict[str, Any]],
    *,
    tool_name: str | None = None,
    query_or_request_summary: str | None = None,
    executed_spl: str | None = None,
    provider_used: str | None = None,
    output_type: str | None = "fixture_preview",
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "trace_id": "pending",
        "source_type": source_type,
        "source_name": source_name,
        "tool_name": tool_name,
        "collection_status": "collected",
        "query_or_request_summary": query_or_request_summary,
        "executed_spl": executed_spl,
        "result_count": result_count,
        "fields_returned": fields,
        "preview_rows": rows,
        "raw_result_hash": f"fixture:{evidence_id}",
        "raw_result_stored": False,
        "time_range": "synthetic last 60 minutes",
        "warnings": ["coe_synthetic_fixture", "no_live_customer_data"],
        "sensitivity_flags": [],
        "tool_category": "read_only_search" if source_type.startswith("splunk") else "governed_knowledge",
        "provider_used": provider_used,
        "saved_search_name": None,
        "output_type": output_type,
        "provenance": EVIDENCE_ORIGIN,
        "created_at": CREATED_AT,
    }


def _rag_row(entry_id: str, title: str, excerpt: str, refs: list[str]) -> dict[str, Any]:
    return {
        "entry_id": entry_id,
        "collection_id": "soc_kb",
        "document_type": "sop",
        "doc_title": "Brute-force Authentication Investigation SOP",
        "entry_title": title,
        "source_excerpt": excerpt,
        "source_refs": refs,
        "citation": refs[0],
        "allowed_use": ["analyst_guidance", "triage_checklist"],
        "recommended_actions": ["confirm scope", "review successful login correlation", "escalate if privileged account affected"],
        "reviewer_role": "soc_analyst",
        "doc_version": "2026.04",
        "status": "published",
        "approval_status": "approved",
        "environment": "coe_demo",
        "retrieval_mode": "fixture",
        "confidence": 0.91,
    }


def _context(
    scenario_id: str,
    skill: str,
    facts: list[dict[str, Any]],
    *,
    metrics: dict[str, Any] | None = None,
    mitre: list[dict[str, Any]] | None = None,
    refs: list[str] | None = None,
    fallback: bool = False,
    quality: str = "sufficient",
) -> dict[str, Any]:
    refs = refs or sorted({ref for fact in facts for ref in fact["source_refs"]})
    return {
        "trace_id": "pending",
        "query": "",
        "selected_skill": skill,
        "source_evidence_refs": refs,
        "structured_facts": facts,
        "entity_summary": {"scenario_id": scenario_id, "fixture": True},
        "metrics": metrics or {},
        "timeline_candidates": [],
        "mitre_candidates": mitre or [],
        "tool_outputs_summary": [{"source_refs": refs, "origin": EVIDENCE_ORIGIN}],
        "capability_profile_ref": "fixture:splunk_capability",
        "spl_generation_provider": "deterministic_fixture_fallback" if fallback else "stage_3c_stub_generator",
        "spl_explanation_provider": "deterministic_fixture",
        "spl_optimization_provider": "disabled_in_demo",
        "spl_guidance_provider": "governed_policy_fixture",
        "fallback_mode": fallback,
        "execution_provider": "mock_fixture" if scenario_id == "account_lockouts_over_time_spl" else None,
        "source_refs": refs,
        "policy_context_refs": ["stage-3j-d-demo-fixture-policy"],
        "sop_action_hints": [],
        "answer_constraints": ["No final LLM synthesis.", "No live customer data.", "Do not execute candidate_spl unless gated."],
        "mitre_grounding_refs": refs if mitre else [],
        "splunk_context_refs": [ref for ref in refs if ref.startswith("ev-splunk")],
        "tool_policy_refs": ["mcp_execution_default_disabled"],
        "environment_grounding_refs": ["coe_synthetic_fixture"],
        "knowledge_ambiguity": [],
        "validation_warnings": [],
        "assumptions": ["Fixture-backed demo data."],
        "warnings": ["coe_synthetic_fixture"],
        "missing_evidence": [],
        "allowed_conclusions": ["Only fixture-supported observations may be shown."],
        "prohibited_conclusions": ["No live production impact statement.", "No remediation execution."],
        "context_quality": quality,
        "synthesis_allowed": False,
    }


def _fact(fact_id: str, statement: str, refs: list[str], confidence: float = 0.9) -> dict[str, Any]:
    return {"fact_id": fact_id, "statement": statement, "source_refs": refs, "derivation": "demo_fixture", "confidence": confidence}


def _mock_rows_for(trace_id: str) -> list[dict[str, Any]]:
    return [
        {"_time": "2026-05-24T09:00:00Z", "action": "lockout", "count": 4, "trace_id": trace_id},
        {"_time": "2026-05-24T09:10:00Z", "action": "lockout", "count": 9, "trace_id": trace_id},
        {"_time": "2026-05-24T09:20:00Z", "action": "lockout", "count": 6, "trace_id": trace_id},
    ]


class _NoopTelemetry:
    def record_step(self, *args: Any, **kwargs: Any) -> None:
        return None


FAILED_SPIKE_SPL = "search index=pgcil_soc sourcetype=pgcil:auth earliest=-60m latest=now action=failure host=APP-01 | stats count as fail_count dc(user) as distinct_users by host, src | where fail_count >= 25 | sort -fail_count | head 100"
SUCCESS_AFTER_FAILURES_SPL = "search index=pgcil_soc sourcetype=pgcil:auth earliest=-60m latest=now | stats count(eval(action=\"failure\")) as fail_count count(eval(action=\"success\")) as success_count by user, src, host | where fail_count >= 5 AND success_count > 0 | sort -fail_count | head 100"
LOCKOUT_SPL = "search index=pgcil_soc sourcetype=pgcil:auth earliest=-24h latest=now action=lockout | timechart span=1h count as lockout_count | head 100"

SCENARIOS: dict[str, DemoScenario] = {
    "failed_login_spike_app01": DemoScenario(
        scenario_id="failed_login_spike_app01",
        label="Failed login spike on APP-01",
        category="Investigate",
        query="Investigate failed login spike on APP-01",
        environment_mode="connected_coe_demo",
        expected_skill="attack_discovery",
        expected_sources=["mcp:splunk", "rag:sop"],
        expected_sufficiency_mode="partial_answer",
        mcp_execution_mode="disabled",
        saia_available=True,
        rag_available=True,
        candidate_spl=FAILED_SPIKE_SPL,
        analyst_summary="Synthetic APP-01 auth evidence shows a failed-login spike candidate. MITRE T1110 is supported by the fixture; SOP guidance is attached for analyst review.",
        trace_explanation=[
            "Routed to attack_discovery because the query asks to investigate failed authentication activity.",
            "SPL is generated by the Stage 3C stub path and validated, but not executed.",
            "RAG SOP evidence is included only as SourceEvidence and StructuredContext.",
        ],
        source_evidence=[
            _evidence(
                "ev-splunk-failed-app01",
                "splunk_mcp",
                "Splunk auth fixture",
                3,
                ["index", "sourcetype", "host", "src", "action", "fail_count"],
                [
                    {"index": "pgcil_soc", "sourcetype": "pgcil:auth", "host": "APP-01", "src": "10.10.4.21", "action": "failure", "fail_count": 42},
                    {"index": "pgcil_soc", "sourcetype": "pgcil:auth", "host": "APP-01", "src": "10.10.4.22", "action": "failure", "fail_count": 31},
                ],
                tool_name="search",
                query_or_request_summary="Synthetic failed authentication aggregation for APP-01 in pgcil_soc/pgcil:auth.",
                executed_spl=None,
                provider_used="splunk_mcp_fixture",
            ),
            _evidence(
                "ev-rag-bruteforce-sop",
                "rag",
                "SOC KB fixture",
                1,
                ["entry_id", "document_type", "source_excerpt", "source_refs"],
                [_rag_row("sop-auth-001", "Brute-force triage", "Confirm affected asset, count source IPs, check for success-after-failure, then escalate privileged-user cases.", ["SOC-SOP-AUTH-001#triage"])],
                tool_name="retrieve_soc_kb",
                query_or_request_summary="Approved brute-force SOP guidance.",
                provider_used="governed_rag_fixture",
            ),
        ],
        structured_context=_context(
            "failed_login_spike_app01",
            "attack_discovery",
            [
                _fact("fact-fail-spike", "APP-01 has a synthetic failed-login spike in index pgcil_soc sourcetype pgcil:auth.", ["ev-splunk-failed-app01"]),
                _fact("fact-t1110", "MITRE T1110 is a supported candidate for repeated authentication failures.", ["ev-splunk-failed-app01", "ev-rag-bruteforce-sop"]),
            ],
            metrics={"fail_count_max": 42, "distinct_sources": 2},
            mitre=[{"technique_id": "T1110", "name": "Brute Force", "support": "supported", "source_refs": ["ev-splunk-failed-app01"]}],
            refs=["ev-splunk-failed-app01", "ev-rag-bruteforce-sop"],
            quality="partial",
        ),
    ),
    "successful_login_after_failures": DemoScenario(
        scenario_id="successful_login_after_failures",
        label="Successful login after failures",
        category="Investigate",
        query="Generate SPL for successful login after failures",
        environment_mode="connected_coe_demo",
        expected_skill="spl_generation",
        expected_sources=["spl_policy", "mcp:splunk"],
        expected_sufficiency_mode="spl_review_only",
        mcp_execution_mode="disabled",
        saia_available=True,
        rag_available=True,
        candidate_spl=SUCCESS_AFTER_FAILURES_SPL,
        analyst_summary="Candidate SPL correlates failure and success counts by user, source, and host. Execution remains disabled, so this is SPL review only.",
        trace_explanation=[
            "Uses a correlation SPL with both action=\"failure\" and action=\"success\".",
            "Does not reuse the failed-login-spike-only SPL.",
            "MCP execution gate leaves the query unexecuted for analyst review.",
        ],
        source_evidence=[
            _evidence("ev-splunk-success-after-fail", "splunk_mcp", "Splunk auth fixture", 2, ["user", "src", "host", "fail_count", "success_count"], [{"user": "svc_app", "src": "10.10.4.21", "host": "APP-01", "fail_count": 8, "success_count": 1}], tool_name="search", provider_used="splunk_mcp_fixture"),
        ],
        structured_context=_context(
            "successful_login_after_failures",
            "spl_generation",
            [_fact("fact-success-correlation", "The candidate SPL explicitly correlates failed and successful logins.", ["ev-splunk-success-after-fail"])],
            metrics={"correlation_keys": ["user", "src", "host"]},
            mitre=[{"technique_id": "T1078", "name": "Valid Accounts", "support": "analyst_review", "source_refs": ["ev-splunk-success-after-fail"]}],
            refs=["ev-splunk-success-after-fail"],
            quality="partial",
        ),
    ),
    "brute_force_sop_guidance": DemoScenario(
        scenario_id="brute_force_sop_guidance",
        label="Brute-force SOP guidance",
        category="Knowledge / SOP",
        query="Show SOP for brute-force investigation",
        environment_mode="knowledge_only_coe_demo",
        expected_skill="knowledge_recall",
        expected_sources=["rag:sop"],
        expected_sufficiency_mode="knowledge_only_answer",
        mcp_execution_mode="not_required",
        saia_available=True,
        rag_available=True,
        analyst_summary="Approved SOC KB guidance is returned without SPL generation. This demonstrates SOP recall with governed RAG only.",
        trace_explanation=[
            "Routes to knowledge_recall for SOP/playbook wording.",
            "No candidate SPL is generated by default.",
            "RAG evidence flows through SourceEvidence and StructuredContext only.",
        ],
        source_evidence=[
            _evidence("ev-rag-sop-only", "rag", "SOC KB fixture", 1, ["entry_id", "document_type", "source_excerpt", "source_refs"], [_rag_row("sop-auth-002", "Brute-force containment checklist", "Validate alert scope, preserve evidence, avoid automated lockouts until business owner review.", ["SOC-SOP-AUTH-001#containment"])], tool_name="retrieve_soc_kb", provider_used="governed_rag_fixture"),
        ],
        structured_context=_context(
            "brute_force_sop_guidance",
            "knowledge_recall",
            [_fact("fact-sop-guidance", "Approved brute-force SOP guidance is available from the governed SOC KB fixture.", ["ev-rag-sop-only"])],
            refs=["ev-rag-sop-only"],
        ),
    ),
    "account_lockouts_over_time_spl": DemoScenario(
        scenario_id="account_lockouts_over_time_spl",
        label="Account lockouts over time SPL",
        category="Generate SPL",
        query="Generate SPL for account lockouts over time",
        environment_mode="connected_coe_demo",
        expected_skill="spl_generation",
        expected_sources=["spl_policy", "mcp:splunk"],
        expected_sufficiency_mode="spl_review_only",
        mcp_execution_mode="mock_success",
        saia_available=True,
        rag_available=True,
        candidate_spl=LOCKOUT_SPL,
        analyst_summary="Lockout trend SPL uses action=lockout and passes deterministic validation. This fixture explicitly models mock execution with capped preview rows.",
        trace_explanation=[
            "Generates lockout-specific SPL using action=lockout.",
            "Runs deterministic SPL validation before any mock gate.",
            "Mock execution is fixture-only and does not call Splunk.",
        ],
        source_evidence=[
            _evidence("ev-splunk-lockout-trend", "splunk_mcp", "Splunk auth fixture", 3, ["_time", "lockout_count"], _mock_rows_for("fixture"), tool_name="search", executed_spl=LOCKOUT_SPL, provider_used="mock_mcp_fixture"),
        ],
        structured_context=_context(
            "account_lockouts_over_time_spl",
            "spl_generation",
            [_fact("fact-lockout-spl", "The candidate SPL trends action=lockout events over time.", ["ev-splunk-lockout-trend"])],
            metrics={"mock_result_rows": 3},
            refs=["ev-splunk-lockout-trend"],
            quality="partial",
        ),
    ),
    "mitre_mapping_auth_alert": DemoScenario(
        scenario_id="mitre_mapping_auth_alert",
        label="MITRE mapping for auth alert",
        category="MITRE Mapping",
        query="Map this alert to MITRE: notable signature=brute_force_success_after_failures index=pgcil_soc sourcetype=pgcil:auth host=APP-01",
        environment_mode="connected_coe_demo",
        expected_skill="alert_summary",
        expected_sources=["mcp:splunk", "rag:sop"],
        expected_sufficiency_mode="partial_answer",
        mcp_execution_mode="not_required",
        saia_available=True,
        rag_available=True,
        analyst_summary="Provided alert context grounds MITRE mapping. T1110 is supported; T1078 is an analyst-review candidate because success-after-failure context exists.",
        trace_explanation=[
            "Uses the provided alert context fixture rather than guessing from an empty MITRE prompt.",
            "Maps T1110 as supported from brute-force evidence.",
            "Keeps T1078 as analyst-review because valid-account use requires confirmation.",
        ],
        source_evidence=[
            _evidence("ev-splunk-mitre-alert", "splunk_mcp", "Splunk notable fixture", 1, ["signature", "index", "sourcetype", "host", "failed_then_success"], [{"signature": "brute_force_success_after_failures", "index": "pgcil_soc", "sourcetype": "pgcil:auth", "host": "APP-01", "failed_then_success": True}], tool_name="notable_lookup", provider_used="splunk_mcp_fixture"),
        ],
        structured_context=_context(
            "mitre_mapping_auth_alert",
            "alert_summary",
            [
                _fact("fact-alert-context", "The alert fixture provides auth context from pgcil_soc/pgcil:auth for APP-01.", ["ev-splunk-mitre-alert"]),
                _fact("fact-mitre-supported", "T1110 is supported by repeated failed-authentication context.", ["ev-splunk-mitre-alert"]),
                _fact("fact-mitre-review", "T1078 is candidate-only because success-after-failure exists but account legitimacy needs analyst review.", ["ev-splunk-mitre-alert"], 0.72),
            ],
            mitre=[
                {"technique_id": "T1110", "name": "Brute Force", "support": "supported", "source_refs": ["ev-splunk-mitre-alert"]},
                {"technique_id": "T1078", "name": "Valid Accounts", "support": "analyst_review", "source_refs": ["ev-splunk-mitre-alert"]},
            ],
            refs=["ev-splunk-mitre-alert"],
            quality="partial",
        ),
    ),
    "airgapped_no_saia_success_after_failures": DemoScenario(
        scenario_id="airgapped_no_saia_success_after_failures",
        label="Air-gapped success after failures",
        category="Air-gapped Mode",
        query="Air-gapped mode: generate SPL for successful login after failures without SAIA",
        environment_mode="airgapped_coe_demo",
        expected_skill="spl_generation",
        expected_sources=["spl_policy", "mcp:splunk"],
        expected_sufficiency_mode="spl_review_only",
        mcp_execution_mode="disabled",
        saia_available=False,
        rag_available=True,
        candidate_spl=SUCCESS_AFTER_FAILURES_SPL,
        analyst_summary="SAIA is unavailable in this air-gapped fixture, so deterministic fallback SPL generation is active while core Splunk MCP metadata remains available.",
        trace_explanation=[
            "SAIA/generative assistant tools are unavailable.",
            "Fallback provider generates advisory SPL without tool calling.",
            "Core Splunk MCP discovery is shown as available, with execution still disabled.",
        ],
        source_evidence=[
            _evidence("ev-splunk-airgap-metadata", "splunk_mcp", "Splunk capability fixture", 1, ["server", "tool", "status"], [{"server": "splunk", "tool": "search", "status": "available", "saia": "unavailable"}], tool_name="tool_discovery", provider_used="mcp_registry_fixture"),
        ],
        structured_context=_context(
            "airgapped_no_saia_success_after_failures",
            "spl_generation",
            [_fact("fact-airgap-fallback", "SAIA is unavailable and deterministic fallback is active; core Splunk MCP search metadata is available.", ["ev-splunk-airgap-metadata"])],
            metrics={"saia_available": False, "fallback_active": True},
            refs=["ev-splunk-airgap-metadata"],
            fallback=True,
            quality="partial",
        ),
    ),
}
