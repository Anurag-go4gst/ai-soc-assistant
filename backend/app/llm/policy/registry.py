"""P4 PP2/PP3 — the governed role contract registry.

One narrow contract per role. There is deliberately no monolithic SOC prompt here:
each role names only the inputs its single consumer needs, which is what stops the
truncation/aggregation/placeholder/normalization/time conflicts P4 exists to remove.

Ownership note
--------------
Contracts for `spl_advisory_generator` and `spl_repair` *describe* the seam workstream
B owns (`app/spl/llm_fallback.py`, `utility_spl_authoring.py`). D does not edit those
files. Where the described contract and B's live prompt differ, the difference goes to
RECONCILIATION_QUEUE rather than being implemented here.
"""

from __future__ import annotations

from app.llm.policy.contracts import RoleContract
from app.llm.policy.role_inventory import facts_for, role_ids
from app.llm.sidecar_clients import _ROLE_TIMEOUT_SECONDS

REGISTRY_VERSION = "prompt_role_registry_v1"

_JSON_ONLY = (
    "Return only valid JSON matching the schema. No markdown, no prose outside JSON, "
    "no chain-of-thought, scratchpad, planning text or <think> tags."
)
_ADVISORY = (
    "Your output is advisory. Deterministic code decides routing, clarification, "
    "authorization, validation, RBAC, HIL and execution. If you disagree with a "
    "deterministic value, report the disagreement; do not override it."
)
_NO_INVENT = (
    "Never invent evidence, sources, identifiers, severity, MITRE support, row counts "
    "or results. Absent information is reported as missing, not guessed."
)


def _timeout(role_id: str) -> float | None:
    return _ROLE_TIMEOUT_SECONDS.get(role_id)


def _posture(role_id: str) -> str:
    return facts_for(role_id).posture


def _c(**kwargs) -> RoleContract:
    """Build a contract, defaulting posture from the live inventory."""
    kwargs.setdefault("runtime_posture", _posture(kwargs["role_id"]))
    kwargs.setdefault("timeout_seconds", _timeout(kwargs["role_id"]))
    return RoleContract(**kwargs)


# --- shared trace field set -------------------------------------------------
_PROVENANCE_TRACE = (
    "role_id",
    "prompt_template_id",
    "prompt_version",
    "prompt_hash",
    "stable_prefix_hash",
    "dynamic_context_hash",
    "cache_eligible",
)

_CONTRACTS: tuple[RoleContract, ...] = (
    # ---------------------------------------------------------------- understanding
    _c(
        role_id="semantic_t4",
        why_llm=(
            "Deterministic parsing abstains on genuinely ambiguous phrasing; a bounded "
            "semantic proposal recovers those turns without giving the model authority."
        ),
        authoritative_inputs=("raw_user_query", "deterministic_resolved_query_contract_locked_fields"),
        non_authoritative_context=("prior_turn_summary",),
        system_instruction=(
            "You propose semantic values only for fields the deterministic parser left "
            "unresolved. Locked deterministic facts are immutable and must be echoed "
            f"unchanged. {_NO_INVENT} {_ADVISORY} {_JSON_ONLY}"
        ),
        dynamic_context=("unresolved_schema_names", "prompt_locked_fields", "supplied_context"),
        output_schema="SemanticT4Proposal (app/chat/semantic_t4_understanding.py)",
        few_shot_set="NOT_APPLICABLE: bypasses the shared few-shot bank; schema-limited prompt",
        negative_example_set="negative:understanding_v1",
        model_class="general_structured_reasoner",
        decoding="deterministic",
        retry_repair_policy="none: single bounded call, deterministic abstain on failure",
        allowed_authority=("propose_unresolved_semantic_fields",),
        extra_prohibited_authority=("overriding_locked_deterministic_facts",),
        validator="_parse_proposal + abstain_acceptance merge gate",
        fallback="deterministic abstain / clarification",
        trace_fields=_PROVENANCE_TRACE + ("semantic_t4.invoked", "semantic_t4.accepted"),
        prompt_template_id="tmpl.semantic_t4",
        prompt_version="1.0.0",
        owning_workstream="D_POLICY",
    ),
    _c(
        role_id="intent_shadow_classifier",
        why_llm="Paraphrase coverage the deterministic keyword registries do not reach.",
        authoritative_inputs=("raw_user_query", "allowed_intent_enum", "allowed_skill_enum"),
        non_authoritative_context=("use_case_catalogue_subset",),
        system_instruction=(
            "Classify the query into the allowed enums only. Never invent a use_case_id "
            f"or an entity. Deterministic clarification and route selection win. {_ADVISORY} {_JSON_ONLY}"
        ),
        dynamic_context=("raw_query", "allowed_enums", "allowed_pipeline_stages"),
        output_schema="QueryUnderstandingCandidate",
        few_shot_set="fewshot:intent_v1",
        negative_example_set="negative:routing_authority_v1",
        model_class="small_structured_classifier",
        decoding="deterministic",
        retry_repair_policy="none: advisory hop, deterministic route on failure",
        allowed_authority=("propose_intent_classification", "propose_skill_hint"),
        validator="adapt_llm_output + governance._advisory_may_replace_skill",
        fallback="deterministic route selection",
        trace_fields=_PROVENANCE_TRACE + ("intent_advisory.status",),
        prompt_template_id="tmpl.intent_shadow_classifier",
        prompt_version="1.0.0",
    ),
    _c(
        role_id="shape_advisor",
        why_llm="Answer-shape hinting for out-of-catalogue phrasing.",
        authoritative_inputs=("resolved_query_contract_shape_context",),
        non_authoritative_context=("prior_answer_shape",),
        system_instruction=(
            "Propose an answer shape. The deterministic answer-shape router decides; "
            f"your output never selects the shape. {_ADVISORY} {_JSON_ONLY}"
        ),
        dynamic_context=("shape_context",),
        output_schema="ShapeAdvisorPayload",
        few_shot_set="fewshot:shape_v1",
        negative_example_set="negative:routing_authority_v1",
        model_class="small_structured_classifier",
        decoding="deterministic",
        retry_repair_policy="none: 10s advisory hop, deterministic shape on failure",
        allowed_authority=("propose_answer_shape",),
        extra_prohibited_authority=("selecting_final_answer_shape",),
        validator="adapt_llm_output(ShapeAdvisorPayload)",
        fallback="deterministic answer_shape_router",
        trace_fields=_PROVENANCE_TRACE + ("shape_advisory.status",),
        prompt_template_id="tmpl.shape_advisor",
        prompt_version="1.0.0",
    ),
    # ---------------------------------------------------------------- SPL (B-owned seam)
    _c(
        role_id="spl_advisory_generator",
        why_llm="Author a candidate detection plan for requests no governed template covers.",
        authoritative_inputs=(
            "spl_semantic_v2_immutable_contract",
            "final_rqc_constraints",
            "governed_source_mappings",
            "analysis_and_output_shape",
            "required_event_sets",
            "entity_roles",
            "search_horizon",
            "analytical_window",
            "measures_grouping_distinct_ranking",
            "temporal_and_sequence_semantics",
            "semantic_prohibitions",
        ),
        non_authoritative_context=("source_profile_hints",),
        system_instruction=(
            "Author a candidate SPL detection plan that preserves the supplied semantic "
            "contract exactly. Do not reinterpret the request. Do not add a result cap, "
            "threshold or filter that the contract does not require. The candidate is "
            f"review-only and is never execution eligible. {_NO_INVENT} {_ADVISORY} {_JSON_ONLY}"
        ),
        dynamic_context=("semantic_contract", "source_bindings", "shape"),
        output_schema="SplAdvisoryCandidate",
        few_shot_set="fewshot:spl_shape_v1",
        negative_example_set="negative:spl_semantic_v1",
        model_class="general_structured_reasoner",
        decoding="deterministic",
        retry_repair_policy="one generation; at most one repair via spl_repair (P2 bound)",
        allowed_authority=("propose_candidate_spl",),
        extra_prohibited_authority=(
            "marking_candidate_execution_eligible",
            "receiving_mitre_policy",
            "receiving_remediation_policy",
            "receiving_generic_alert_template_catalogue",
        ),
        validator="validate_spl_lab_candidate + spl_semantic_fidelity + adapt_llm_output",
        fallback="deterministic lab draft / clarification",
        trace_fields=_PROVENANCE_TRACE + ("candidate_spl.generation_mode",),
        prompt_template_id="tmpl.spl_advisory_generator",
        prompt_version="1.0.0",
        owning_workstream="B_SPL",
    ),
    _c(
        role_id="spl_repair",
        why_llm="Correct a rejected candidate against deterministic loss findings, once.",
        authoritative_inputs=(
            "spl_semantic_v2_immutable_contract",
            "previous_rejected_candidate",
            "deterministic_syntax_and_fidelity_losses",
            "governed_source_bindings",
            "bounded_correction_scope",
        ),
        non_authoritative_context=("prior_validation_warnings",),
        system_instruction=(
            "Repair the supplied candidate so it satisfies the named deterministic "
            "losses. You may not reinterpret the request, change the semantic contract, "
            f"or broaden scope. Exactly one repair attempt exists. {_ADVISORY} {_JSON_ONLY}"
        ),
        dynamic_context=("rejected_candidate", "loss_findings", "semantic_contract"),
        output_schema="SplAdvisoryCandidate",
        few_shot_set="fewshot:spl_repair_v1",
        negative_example_set="negative:spl_semantic_v1",
        model_class="general_structured_reasoner",
        decoding="deterministic",
        timeout_seconds=120.0,
        retry_repair_policy="hard bound: exactly one repair attempt, no second repair (P2)",
        allowed_authority=("propose_repaired_candidate_spl",),
        extra_prohibited_authority=(
            "reinterpreting_the_request",
            "second_repair_attempt",
            "marking_candidate_execution_eligible",
        ),
        validator="validate_spl_lab_candidate + spl_semantic_fidelity",
        fallback="fail closed with semantic_fidelity_unresolved",
        trace_fields=_PROVENANCE_TRACE + ("candidate_spl.utility_spl_repair_attempt",),
        prompt_template_id="tmpl.spl_repair",
        prompt_version="1.0.0",
        owning_workstream="B_SPL",
    ),
    _c(
        role_id="template_match_semantic_assist",
        why_llm="Match a paraphrase to a governed template the lexical matcher misses.",
        authoritative_inputs=("governed_template_catalogue", "user_query"),
        non_authoritative_context=("prior_match_attempt",),
        system_instruction=(
            "Propose which governed template matches. Deterministic matching decides; "
            f"never propose a template id outside the supplied catalogue. {_ADVISORY} {_JSON_ONLY}"
        ),
        dynamic_context=("query", "candidate_template_ids"),
        output_schema="TemplateMatchSemanticAssistPayload",
        few_shot_set="fewshot:template_match_v1",
        negative_example_set="negative:unsupported_claims_v1",
        model_class="small_structured_classifier",
        decoding="deterministic",
        retry_repair_policy="none: advisory hop",
        allowed_authority=("propose_template_match",),
        validator="adapt_llm_output(TemplateMatchSemanticAssistPayload)",
        fallback="deterministic template matcher",
        trace_fields=_PROVENANCE_TRACE,
        prompt_template_id="tmpl.template_match_semantic_assist",
        prompt_version="1.0.0",
    ),
    _c(
        role_id="template_render_parameter_assist",
        why_llm="Fill blank template slots the deterministic binder could not resolve.",
        authoritative_inputs=("governed_template_slots", "resolved_bindings"),
        non_authoritative_context=("query_paraphrase",),
        system_instruction=(
            "Fill only slots reported unresolved. Never overwrite a bound slot. "
            f"Deterministic validation wins on every conflict. {_NO_INVENT} {_ADVISORY} {_JSON_ONLY}"
        ),
        dynamic_context=("unresolved_slots", "bound_slots"),
        output_schema="TemplateRenderParameterAssistPayload",
        few_shot_set="fewshot:template_render_v1",
        negative_example_set="negative:spl_semantic_v1",
        model_class="small_structured_classifier",
        decoding="deterministic",
        retry_repair_policy="none: advisory hop",
        allowed_authority=("propose_unresolved_slot_values",),
        extra_prohibited_authority=("overwriting_bound_slots",),
        validator="adapt_llm_output + deterministic slot binder",
        fallback="HIL clarification for unresolved slots",
        trace_fields=_PROVENANCE_TRACE,
        prompt_template_id="tmpl.template_render_parameter_assist",
        prompt_version="1.0.0",
    ),
    # ---------------------------------------------------------------- planning
    _c(
        role_id="investigation_planner",
        why_llm="Propose an investigation shape over governed capability posture.",
        authoritative_inputs=("governed_rqc", "minimal_evidence_state_v2", "capability_snapshot"),
        non_authoritative_context=("prior_plan_proposal",),
        system_instruction=(
            "Propose a read-only investigation plan within the approved envelope. You "
            "receive no execution tool, no Auth0 grant and no MCP access. Deterministic "
            f"validation and the execution gate decide what runs. {_ADVISORY} {_JSON_ONLY}"
        ),
        dynamic_context=("rqc", "evidence_state", "capability_snapshot"),
        output_schema="InvestigationPlanProposal JSON",
        few_shot_set="fewshot:planning_v1",
        negative_example_set="negative:planning_authority_v1",
        model_class="investigation_reasoner",
        decoding="deterministic",
        retry_repair_policy="none: advisory proposal, deterministic plan on failure",
        allowed_authority=("propose_read_only_investigation_plan",),
        extra_prohibited_authority=("widening_the_approved_envelope",),
        validator="deterministic plan validation before dispatch",
        fallback="deterministic guided dispatch",
        trace_fields=_PROVENANCE_TRACE + ("plan_dispatch_trace.proposal_status",),
        prompt_template_id="tmpl.investigation_planner",
        prompt_version="1.0.0",
    ),
    _c(
        role_id="guided_investigation_plan_proposer",
        why_llm="Suggest next guided investigation steps for out-of-registry hunts.",
        authoritative_inputs=("guided_context", "available_evidence_keys"),
        non_authoritative_context=("prior_round_summary",),
        system_instruction=(
            "Propose guided investigation steps. Review-only: you authorize no action "
            f"and no tool call. {_NO_INVENT} {_ADVISORY} {_JSON_ONLY}"
        ),
        dynamic_context=("guided_context", "evidence_keys"),
        output_schema="guided_investigation_plan_propose JSON",
        few_shot_set="fewshot:planning_v1",
        negative_example_set="negative:planning_authority_v1",
        model_class="small_structured_classifier",
        decoding="deterministic",
        retry_repair_policy="none: 15s advisory hop",
        allowed_authority=("propose_guided_steps",),
        validator="adapt_llm_output + deterministic guided dispatch",
        fallback="deterministic guided catalogue",
        trace_fields=_PROVENANCE_TRACE,
        prompt_template_id="tmpl.guided_investigation_plan_proposer",
        prompt_version="1.0.0",
    ),
    _c(
        role_id="plan_delta_reasoner",
        why_llm="Propose one bounded read-only delta when evidence has a named gap.",
        authoritative_inputs=("approved_investigation_envelope", "missing_evidence", "capability_snapshot"),
        non_authoritative_context=("prior_revisions",),
        system_instruction=(
            "Propose exactly one bounded read-only plan delta inside the approved "
            "envelope. You may not widen objective, targets, entities, time scope or "
            "source scope, may not propose a write, and may not execute or authorize "
            f"anything. Deterministic validate_plan_delta decides. {_ADVISORY} {_JSON_ONLY}"
        ),
        dynamic_context=("envelope", "missing_evidence", "capability_snapshot", "prior_revisions"),
        output_schema="PlanDeltaProposal",
        few_shot_set="fewshot:planning_v1",
        negative_example_set="negative:planning_authority_v1",
        model_class="investigation_reasoner",
        decoding="deterministic",
        retry_repair_policy="none: one proposal per round, bounded by hop budget",
        allowed_authority=("propose_bounded_read_only_delta",),
        extra_prohibited_authority=(
            "executing_a_plan_delta",
            "authorizing_a_plan_delta",
            "widening_capabilities",
            "creating_a_second_planning_loop",
        ),
        validator="app/chat/investigation_plan_delta.py::validate_plan_delta",
        fallback="deterministic stop with honest gap",
        trace_fields=_PROVENANCE_TRACE + ("plan_delta.decision_status",),
        prompt_template_id="tmpl.plan_delta_reasoner",
        prompt_version="1.0.0",
    ),
    _c(
        role_id="remediation_planner",
        why_llm="Narrow a deterministic remediation plan to what the outcome warrants.",
        authoritative_inputs=("investigation_outcome", "capability_snapshot", "deterministic_plan_steps"),
        non_authoritative_context=("analyst_free_text",),
        system_instruction=(
            "Narrow the supplied deterministic remediation steps. You may not invent a "
            "step, mark anything executable, or authorize a write. Approval is a human "
            f"action and execution is governed by the action gate. {_ADVISORY} {_JSON_ONLY}"
        ),
        dynamic_context=("outcome", "capability_snapshot", "candidate_steps"),
        output_schema="ValidatedRemediationPlan narrowing proposal",
        few_shot_set="NOT_APPLICABLE: deterministic step catalogue supplies the shapes",
        negative_example_set="negative:planning_authority_v1",
        model_class="general_structured_reasoner",
        decoding="deterministic",
        retry_repair_policy="none: 30s advisory hop, deterministic plan on failure",
        allowed_authority=("narrow_deterministic_remediation_steps",),
        extra_prohibited_authority=("inventing_remediation_steps", "marking_a_step_executable"),
        validator="app/chat/remediation_plan_validator.py::validate_remediation_plan",
        fallback="deterministic remediation plan unchanged",
        trace_fields=_PROVENANCE_TRACE + ("remediation_planning_trace.plan_source",),
        prompt_template_id="tmpl.remediation_planner",
        prompt_version="1.0.0",
    ),
    _c(
        role_id="route_plan_candidate_generator",
        why_llm="Shadow route-plan candidate for comparison against the deterministic plan.",
        authoritative_inputs=("resolved_query_contract", "registry_skill_enum"),
        non_authoritative_context=("prior_route",),
        system_instruction=(
            "Propose a candidate route plan for shadow comparison only. Deterministic "
            f"route selection is final. {_ADVISORY} {_JSON_ONLY}"
        ),
        dynamic_context=("rqc", "allowed_skills"),
        output_schema="RoutePlanCandidateLlmPayload",
        few_shot_set="fewshot:intent_v1",
        negative_example_set="negative:routing_authority_v1",
        model_class="general_structured_reasoner",
        decoding="deterministic",
        retry_repair_policy="none: shadow hop",
        allowed_authority=("propose_shadow_route_plan",),
        validator="adapt_llm_output + governance._advisory_may_replace_skill",
        fallback="deterministic route plan",
        trace_fields=_PROVENANCE_TRACE + ("control_plane_trace.resource_plan_shadow",),
        prompt_template_id="tmpl.route_plan_candidate_generator",
        prompt_version="1.0.0",
    ),
    # ---------------------------------------------------------------- reasoning (blocked)
    _c(
        role_id="pattern_reasoner",
        why_llm="Summarize cross-evidence patterns an analyst would otherwise assemble by hand.",
        authoritative_inputs=("accepted_source_evidence", "correlation_scope"),
        non_authoritative_context=("diagnostic_notes",),
        system_instruction=(
            "Summarize patterns that hold across the supplied accepted evidence within "
            f"the given correlation scope. {_NO_INVENT} {_ADVISORY} {_JSON_ONLY}"
        ),
        dynamic_context=("accepted_evidence", "correlation_scope"),
        output_schema="ReasoningAdvisoryResult",
        few_shot_set="fewshot:reasoning_v1",
        negative_example_set="negative:evidence_truth_v1",
        model_class="investigation_reasoner",
        decoding="low_variance",
        retry_repair_policy="none: advisory hop",
        allowed_authority=("summarize_accepted_evidence",),
        validator="adapt_llm_output(ReasoningAdvisoryResult)",
        fallback="deterministic evidence summary floor",
        trace_fields=_PROVENANCE_TRACE,
        prompt_template_id="tmpl.pattern_reasoner",
        prompt_version="1.0.0",
    ),
    _c(
        role_id="mitre_reasoner",
        why_llm="Narrate MITRE relevance once deterministic mapping has fixed the status.",
        authoritative_inputs=("deterministic_mitre_status", "accepted_source_evidence"),
        non_authoritative_context=("candidate_technique_hints",),
        system_instruction=(
            "Explain the deterministic MITRE mapping. You may not add, remove or "
            f"re-rank techniques, and may not assert support the mapping denies. {_NO_INVENT} {_ADVISORY} {_JSON_ONLY}"
        ),
        dynamic_context=("mitre_status", "accepted_evidence"),
        output_schema="ReasoningAdvisoryResult",
        few_shot_set="fewshot:reasoning_v1",
        negative_example_set="negative:evidence_truth_v1",
        model_class="investigation_reasoner",
        decoding="low_variance",
        retry_repair_policy="none: advisory hop",
        allowed_authority=("narrate_deterministic_mitre_status",),
        extra_prohibited_authority=("asserting_mitre_technique_support",),
        validator="adapt_llm_output + deterministic MITRE status override",
        fallback="deterministic MITRE status text",
        trace_fields=_PROVENANCE_TRACE,
        prompt_template_id="tmpl.mitre_reasoner",
        prompt_version="1.0.0",
    ),
    _c(
        role_id="missing_evidence_reasoner",
        why_llm="Phrase which evidence is missing and why it matters, for the analyst.",
        authoritative_inputs=("minimal_evidence_state_v2_missing", "answer_contract_limitations"),
        non_authoritative_context=("attempted_capability_list",),
        system_instruction=(
            "Describe the named missing evidence. A planned, attempted, failed or empty "
            f"result is not evidence and must never be described as obtained. {_NO_INVENT} {_ADVISORY} {_JSON_ONLY}"
        ),
        dynamic_context=("missing_evidence", "limitations"),
        output_schema="ReasoningAdvisoryResult",
        few_shot_set="fewshot:reasoning_v1",
        negative_example_set="negative:evidence_truth_v1",
        model_class="investigation_reasoner",
        decoding="low_variance",
        retry_repair_policy="none: advisory hop",
        allowed_authority=("describe_named_missing_evidence",),
        validator="adapt_llm_output(ReasoningAdvisoryResult)",
        fallback="deterministic limitations list",
        trace_fields=_PROVENANCE_TRACE,
        prompt_template_id="tmpl.missing_evidence_reasoner",
        prompt_version="1.0.0",
    ),
    _c(
        role_id="evidence_reasoner",
        why_llm="Relate accepted evidence items to the specific investigation question.",
        authoritative_inputs=("accepted_source_evidence", "investigation_question"),
        non_authoritative_context=("execution_metadata",),
        system_instruction=(
            "Reason only over accepted evidence, and only about the supplied question. "
            "Execution metadata, plans and diagnostics are not evidence. "
            f"{_NO_INVENT} {_ADVISORY} {_JSON_ONLY}"
        ),
        dynamic_context=("accepted_evidence", "question"),
        output_schema="ReasoningAdvisoryResult",
        few_shot_set="fewshot:reasoning_v1",
        negative_example_set="negative:evidence_truth_v1",
        model_class="investigation_reasoner",
        decoding="low_variance",
        retry_repair_policy="none: advisory hop",
        allowed_authority=("relate_accepted_evidence",),
        extra_prohibited_authority=("creating_evidence_state_facts",),
        validator="adapt_llm_output(ReasoningAdvisoryResult)",
        fallback="deterministic evidence summary floor",
        trace_fields=_PROVENANCE_TRACE,
        prompt_template_id="tmpl.evidence_reasoner",
        prompt_version="1.0.0",
    ),
    _c(
        role_id="hypothesis_reasoner",
        why_llm="Offer review-only hypotheses for an analyst to accept or discard.",
        authoritative_inputs=(
            "accepted_source_evidence",
            "investigation_question",
            "confirmed_findings",
        ),
        non_authoritative_context=("prior_hypotheses",),
        system_instruction=(
            "Offer hypotheses clearly marked as unconfirmed, excluding anything already "
            "listed as a confirmed finding. A hypothesis is never a finding and never a "
            f"security verdict. {_NO_INVENT} {_ADVISORY} {_JSON_ONLY}"
        ),
        dynamic_context=("accepted_evidence", "question", "confirmed_findings"),
        output_schema="ReasoningAdvisoryResult",
        few_shot_set="fewshot:reasoning_v1",
        negative_example_set="negative:evidence_truth_v1",
        model_class="investigation_reasoner",
        decoding="low_variance",
        retry_repair_policy="none: advisory hop",
        allowed_authority=("propose_unconfirmed_hypotheses",),
        extra_prohibited_authority=("promoting_a_hypothesis_to_a_finding",),
        validator="adapt_llm_output(ReasoningAdvisoryResult)",
        fallback="omit hypotheses",
        trace_fields=_PROVENANCE_TRACE,
        prompt_template_id="tmpl.hypothesis_reasoner",
        prompt_version="1.0.0",
    ),
    _c(
        role_id="risk_rationale_reasoner",
        why_llm="Explain a deterministic severity label in analyst language.",
        authoritative_inputs=("deterministic_severity_label", "accepted_source_evidence"),
        non_authoritative_context=("mitre_narration",),
        system_instruction=(
            "Explain the supplied severity. You may not change, raise or lower it, and "
            f"may not imply a different disposition. {_NO_INVENT} {_ADVISORY} {_JSON_ONLY}"
        ),
        dynamic_context=("severity_label", "accepted_evidence"),
        output_schema="SeverityRationaleAdvisory",
        few_shot_set="fewshot:reasoning_v1",
        negative_example_set="negative:evidence_truth_v1",
        model_class="investigation_reasoner",
        decoding="low_variance",
        retry_repair_policy="none: advisory hop",
        allowed_authority=("explain_deterministic_severity",),
        extra_prohibited_authority=("changing_the_severity_label",),
        validator="adapt_llm_output + deterministic severity override",
        fallback="deterministic severity text",
        trace_fields=_PROVENANCE_TRACE,
        prompt_template_id="tmpl.risk_rationale_reasoner",
        prompt_version="1.0.0",
    ),
    # ---------------------------------------------------------------- evidence + threat
    _c(
        role_id="evidence_observer",
        why_llm="Report observations over governed evidence without mutating it.",
        authoritative_inputs=("accepted_source_evidence",),
        non_authoritative_context=("tool_result_metadata",),
        system_instruction=(
            "Report observations only. You cannot add, remove or alter an evidence item, "
            f"and cannot turn a plan or a failure into an observation. {_NO_INVENT} {_ADVISORY} {_JSON_ONLY}"
        ),
        dynamic_context=("accepted_evidence",),
        output_schema="EvidenceObserverPayload",
        few_shot_set="fewshot:reasoning_v1",
        negative_example_set="negative:evidence_truth_v1",
        model_class="general_structured_reasoner",
        decoding="deterministic",
        retry_repair_policy="none: advisory hop",
        allowed_authority=("report_observations",),
        extra_prohibited_authority=("mutating_evidence_state",),
        validator="adapt_llm_output(EvidenceObserverPayload)",
        fallback="omit observations",
        trace_fields=_PROVENANCE_TRACE,
        prompt_template_id="tmpl.evidence_observer",
        prompt_version="1.0.0",
    ),
    _c(
        role_id="mitre_candidate_mapper",
        why_llm="Propose candidate ATT&CK techniques for deterministic validation.",
        authoritative_inputs=("governed_mitre_registry", "accepted_source_evidence"),
        non_authoritative_context=("free_text_alert_name",),
        system_instruction=(
            "Propose candidate technique IDs from the supplied registry only. Never "
            "invent an ID. Deterministic validation sets the final MITRE status and "
            f"visibility. {_NO_INVENT} {_ADVISORY} {_JSON_ONLY}"
        ),
        dynamic_context=("registry_subset", "accepted_evidence"),
        output_schema="MitreCandidateMapperPayload",
        few_shot_set="fewshot:reasoning_v1",
        negative_example_set="negative:unsupported_claims_v1",
        model_class="general_structured_reasoner",
        decoding="deterministic",
        retry_repair_policy="none: advisory hop",
        allowed_authority=("propose_candidate_technique_ids",),
        extra_prohibited_authority=("setting_final_mitre_status", "inventing_technique_ids"),
        validator="adapt_llm_output + deterministic MITRE registry validation",
        fallback="deterministic MITRE candidates only",
        trace_fields=_PROVENANCE_TRACE,
        prompt_template_id="tmpl.mitre_candidate_mapper",
        prompt_version="1.0.0",
    ),
    # ---------------------------------------------------------------- composition
    _c(
        role_id="governed_composer",
        why_llm="Turn deterministic outcome structures into readable analyst prose.",
        authoritative_inputs=("investigation_outcome", "minimal_evidence_state_v2", "deterministic_facts"),
        non_authoritative_context=("diagnostic_trace",),
        system_instruction=(
            "Narrate the supplied deterministic result. Every fact -- severity, "
            "disposition, MITRE status, actions, counts, execution state -- is fixed and "
            "must be restated, never revised. A planned, attempted, failed, empty or "
            f"diagnostic item is not a fact. {_NO_INVENT} {_ADVISORY} {_JSON_ONLY}"
        ),
        dynamic_context=("outcome", "evidence_state", "facts"),
        output_schema="narrative prose bound to deterministic facts",
        few_shot_set="fewshot:composer_v1",
        negative_example_set="negative:composer_v1",
        model_class="composer",
        decoding="low_variance",
        retry_repair_policy="none: deterministic draft on failure",
        allowed_authority=("rewrite_narration",),
        extra_prohibited_authority=(
            "changing_a_security_verdict",
            "changing_severity_or_disposition",
            "introducing_facts_absent_from_evidence_state",
        ),
        validator="answer guard + deterministic fact pinning",
        fallback="deterministic analyst summary draft",
        trace_fields=_PROVENANCE_TRACE + ("synthesis.live_llm_called",),
        prompt_template_id="tmpl.governed_composer",
        prompt_version="1.0.0",
    ),
    _c(
        role_id="analyst_summary_narration",
        why_llm="Narrate the analyst summary card without altering its facts.",
        authoritative_inputs=("deterministic_analyst_summary_fields",),
        non_authoritative_context=("prior_turn_prose",),
        system_instruction=(
            "Rewrite the supplied summary fields as prose. Facts are immutable. "
            f"{_NO_INVENT} {_ADVISORY} {_JSON_ONLY}"
        ),
        dynamic_context=("summary_fields",),
        output_schema="AnalystSummaryNarrationPayload",
        few_shot_set="fewshot:composer_v1",
        negative_example_set="negative:composer_v1",
        model_class="composer",
        decoding="low_variance",
        retry_repair_policy="none: deterministic draft on failure",
        allowed_authority=("rewrite_summary_prose",),
        extra_prohibited_authority=("changing_a_security_verdict",),
        validator="adapt_llm_output(AnalystSummaryNarrationPayload)",
        fallback="deterministic summary text",
        trace_fields=_PROVENANCE_TRACE,
        prompt_template_id="tmpl.analyst_summary_narration",
        prompt_version="1.0.0",
    ),
    _c(
        role_id="analyst_response_drafter",
        why_llm="Draft the structured analyst response body from governed inputs.",
        authoritative_inputs=("deterministic_answer_contract", "accepted_source_evidence"),
        non_authoritative_context=("diagnostic_trace",),
        system_instruction=(
            "Draft the analyst response from the supplied contract. Draft-only: it is "
            f"validated before display and carries no authority. {_NO_INVENT} {_ADVISORY} {_JSON_ONLY}"
        ),
        dynamic_context=("answer_contract", "accepted_evidence"),
        output_schema="AnalystResponseDraft",
        few_shot_set="fewshot:composer_v1",
        negative_example_set="negative:composer_v1",
        model_class="composer",
        decoding="deterministic",
        retry_repair_policy="none: deterministic draft on failure",
        allowed_authority=("draft_analyst_response",),
        validator="adapt_llm_output(AnalystResponseDraft) + output validator",
        fallback="deterministic response body",
        trace_fields=_PROVENANCE_TRACE,
        prompt_template_id="tmpl.analyst_response_drafter",
        prompt_version="1.0.0",
    ),
    _c(
        role_id="investigation_note_drafter",
        why_llm="Draft an investigation note for the analyst record.",
        authoritative_inputs=("investigation_outcome", "accepted_source_evidence"),
        non_authoritative_context=("diagnostic_trace",),
        system_instruction=(
            "Draft a factual investigation note from the supplied outcome. Prose only; "
            f"no new facts, no recommendations beyond those supplied. {_NO_INVENT} {_ADVISORY} {_JSON_ONLY}"
        ),
        dynamic_context=("outcome", "accepted_evidence"),
        output_schema="investigation_note JSON/text",
        few_shot_set="fewshot:composer_v1",
        negative_example_set="negative:composer_v1",
        model_class="composer",
        decoding="deterministic",
        retry_repair_policy="none: deterministic draft on failure",
        allowed_authority=("draft_investigation_note",),
        validator="output validator + sanitize_user_facing_prose",
        fallback="deterministic note text",
        trace_fields=_PROVENANCE_TRACE,
        prompt_template_id="tmpl.investigation_note_drafter",
        prompt_version="1.0.0",
    ),
    _c(
        role_id="answer_guard_assistant",
        why_llm="Second-opinion check for unsupported claims in drafted prose.",
        authoritative_inputs=("drafted_prose", "accepted_source_evidence"),
        non_authoritative_context=("diagnostic_trace",),
        system_instruction=(
            "Flag claims in the draft that the supplied evidence does not support. You "
            "flag; the deterministic guard decides. You may not rewrite the draft or "
            f"approve it. {_ADVISORY} {_JSON_ONLY}"
        ),
        dynamic_context=("draft", "accepted_evidence"),
        output_schema="answer guard advisory flags",
        few_shot_set="fewshot:composer_v1",
        negative_example_set="negative:unsupported_claims_v1",
        model_class="general_structured_reasoner",
        decoding="deterministic",
        retry_repair_policy="none: advisory hop",
        allowed_authority=("flag_unsupported_claims",),
        extra_prohibited_authority=("approving_a_draft", "rewriting_a_draft"),
        validator="app/answer_guard/rules.py deterministic guard",
        fallback="deterministic answer guard rules only",
        trace_fields=_PROVENANCE_TRACE + ("answer_guard.verdict",),
        prompt_template_id="tmpl.answer_guard_assistant",
        prompt_version="1.0.0",
    ),
)

ROLE_CONTRACTS: dict[str, RoleContract] = {c.role_id: c for c in _CONTRACTS}


def contract_for(role_id: str) -> RoleContract:
    try:
        return ROLE_CONTRACTS[role_id]
    except KeyError as exc:
        raise KeyError(f"no prompt contract registered for role: {role_id}") from exc


def contracts() -> tuple[RoleContract, ...]:
    return _CONTRACTS


def missing_contract_role_ids() -> tuple[str, ...]:
    """Inventory roles with no contract. Must be empty."""
    return tuple(rid for rid in role_ids() if rid not in ROLE_CONTRACTS)
