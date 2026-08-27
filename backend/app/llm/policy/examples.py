"""P4 PP4 — governed few-shot and negative-example catalogues.

Two rules shape everything here.

**Examples teach a shape, not a query.** An asset keyed to a customer's literal
question teaches the model to memorise that question. Every few-shot below is keyed to
a reusable semantic shape (or the equivalent narrow role concept) and its `input_shape`
describes a class of requests, never one.

**Posture is copied from the product, not asserted.** The SPL shapes come from
``app.spl.spl_intent_spec``: `SUPPORTED_ANALYSIS_SHAPES` and
`UNSUPPORTED_ANALYSIS_SHAPES`. `comparison` is unsupported in P2, so its entry is
marked `UNSUPPORTED_GAP` and is not activatable. A few-shot that demonstrated a working
comparison would teach the model that a product gap is a product feature, and would
make the gap invisible at exactly the moment it matters.

Negative examples teach rejection and correction. They never loosen a deterministic
check, and every one names the deterministic rule that actually enforces it -- an
example whose rule does not exist is a story, not a guardrail.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.spl.spl_intent_spec import SUPPORTED_ANALYSIS_SHAPES, UNSUPPORTED_ANALYSIS_SHAPES

FEW_SHOT_CATALOG_VERSION = "few_shot_catalog_v1"
NEGATIVE_EXAMPLE_CATALOG_VERSION = "negative_example_catalog_v1"

ActivationState = Literal["ACTIVE", "CANDIDATE", "RETIRED", "UNSUPPORTED_GAP"]

#: Semantic shapes the few-shot bank may key on.
SEMANTIC_SHAPES: tuple[str, ...] = (
    "RAW_EVENTS",
    "AGGREGATION",
    "RANKING",
    "TREND",
    "ROLLING",
    "SEQUENCE",
    "COMPARISON",
)

#: Map plan-facing shape names onto P2's live vocabulary.
_SHAPE_TO_P2: dict[str, str] = {
    "RAW_EVENTS": "raw",
    "AGGREGATION": "aggregation",
    "RANKING": "ranking",
    "TREND": "trend",
    "ROLLING": "rolling",
    "SEQUENCE": "sequence",
    "COMPARISON": "comparison",
}


def p2_shape_for(shape: str) -> str:
    return _SHAPE_TO_P2[shape]


def shape_is_supported(shape: str) -> bool:
    """Authority is P2's own tuples, never a local opinion."""
    return _SHAPE_TO_P2[shape] in SUPPORTED_ANALYSIS_SHAPES


def shape_is_declared_unsupported(shape: str) -> bool:
    return _SHAPE_TO_P2[shape] in UNSUPPORTED_ANALYSIS_SHAPES


@dataclass(frozen=True)
class FewShotExample:
    example_id: str
    role_id: str
    purpose: str
    input_shape: str
    expected_output_shape: str
    authority_boundary: str
    version: str
    activation: ActivationState
    set_id: str
    #: Only for SPL-shaped assets; NONE for role-concept assets.
    semantic_shape: str | None = None


@dataclass(frozen=True)
class NegativeExample:
    example_id: str
    role_id: str
    purpose: str
    failure_mode: str
    #: What the model must do instead.
    corrected_behaviour: str
    #: The deterministic rule that enforces this. Must name real machinery.
    enforcing_rule: str
    version: str
    activation: ActivationState
    set_id: str


# ---------------------------------------------------------------------------
# Few-shot bank
# ---------------------------------------------------------------------------

_SPL_SHAPE_SHOTS: tuple[FewShotExample, ...] = tuple(
    FewShotExample(
        example_id=f"fs.spl.{shape.lower()}",
        role_id="spl_advisory_generator",
        purpose=f"Demonstrate the {shape} analysis shape end to end.",
        input_shape=f"A semantic contract whose analysis_shape is {_SHAPE_TO_P2[shape]}.",
        expected_output_shape=(
            f"A candidate SPL preserving the {shape} semantics, with execution_eligible false."
        ),
        authority_boundary="Candidate only; never execution eligible; no invented threshold or cap.",
        version="1.0.0",
        activation="ACTIVE" if shape_is_supported(shape) else "UNSUPPORTED_GAP",
        set_id="fewshot:spl_shape_v1",
        semantic_shape=shape,
    )
    for shape in SEMANTIC_SHAPES
)

_OTHER_SHOTS: tuple[FewShotExample, ...] = (
    FewShotExample(
        example_id="fs.spl.repair.loss_named",
        role_id="spl_repair",
        purpose="Repair exactly the named deterministic loss and nothing else.",
        input_shape="A rejected candidate plus a named fidelity/syntax loss list.",
        expected_output_shape="The same candidate with only the named losses corrected.",
        authority_boundary="One repair only; may not reinterpret the request or widen scope.",
        version="1.0.0",
        activation="ACTIVE",
        set_id="fewshot:spl_repair_v1",
    ),
    # OPTIONAL_PHASE_S H1 — the Layer 3 set is deliberately abstain-weighted. The live
    # six-case evaluation showed this model claiming OPTIMIZED for cosmetic negative-form
    # swaps and for wildcard removal, so the examples teach "doing nothing succeeds".
    FewShotExample(
        example_id="fs.spl.optimization.negative_form_abstain",
        role_id="spl_optimization_llm",
        purpose="Swapping NOT field=v for field!=v is cosmetic, not an optimization.",
        input_shape="A candidate whose base search carries a broad NOT / != predicate.",
        expected_output_shape="NO_SAFE_OPTIMIZATION with candidate_spl equal to the input.",
        authority_boundary="The forms differ on missing/null fields; abstain rather than guess.",
        version="1.0.0",
        activation="ACTIVE",
        set_id="fewshot:spl_optimization_abstain_v1",
    ),
    FewShotExample(
        example_id="fs.spl.optimization.wildcard_abstain",
        role_id="spl_optimization_llm",
        purpose="Never remove, add or move a wildcard to satisfy an efficiency rule.",
        input_shape="A candidate with a leading or embedded wildcard search term.",
        expected_output_shape="NO_SAFE_OPTIMIZATION with candidate_spl equal to the input.",
        authority_boundary="Wildcard changes alter matching semantics; never equivalence.",
        version="1.0.0",
        activation="ACTIVE",
        set_id="fewshot:spl_optimization_abstain_v1",
    ),
    FewShotExample(
        example_id="fs.spl.optimization.unchanged_abstain",
        role_id="spl_optimization_llm",
        purpose="An already-efficient or byte-identical revision is never OPTIMIZED.",
        input_shape="A candidate with no material safe improvement available.",
        expected_output_shape="NO_SAFE_OPTIMIZATION with candidate_spl equal to the input.",
        authority_boundary="Doing nothing is a successful outcome, not a failed attempt.",
        version="1.0.0",
        activation="ACTIVE",
        set_id="fewshot:spl_optimization_abstain_v1",
    ),
    FewShotExample(
        example_id="fs.spl.optimization.governed_time_abstain",
        role_id="spl_optimization_llm",
        purpose="Never invent relative_time() or drop governed earliest/latest bounds.",
        input_shape="A candidate carrying governed time bounds and an unrelated gap.",
        expected_output_shape="NO_SAFE_OPTIMIZATION with candidate_spl equal to the input.",
        authority_boundary="Governed time scope is authority; the model never re-derives it.",
        version="1.0.0",
        activation="ACTIVE",
        set_id="fewshot:spl_optimization_abstain_v1",
    ),
    FewShotExample(
        example_id="fs.spl.optimization.or_to_in_positive",
        role_id="spl_optimization_llm",
        purpose="The one safe positive: collapse a same-field OR chain into IN().",
        input_shape="A base search with repeated field=value alternatives on one field.",
        expected_output_shape="OPTIMIZED with field IN (...) using only the input values.",
        authority_boundary="No value may appear that was absent from the input.",
        version="1.0.0",
        activation="ACTIVE",
        set_id="fewshot:spl_optimization_abstain_v1",
    ),
    FewShotExample(
        example_id="fs.intent.paraphrase",
        role_id="intent_shadow_classifier",
        purpose="Map a paraphrase onto an allowed intent enum without inventing entities.",
        input_shape="A natural-language request whose intent is in the allowed enum.",
        expected_output_shape="QueryUnderstandingCandidate with enum values only.",
        authority_boundary="Advisory; deterministic routing decides.",
        version="1.0.0",
        activation="ACTIVE",
        set_id="fewshot:intent_v1",
    ),
    FewShotExample(
        example_id="fs.intent.unresolved_referent",
        role_id="intent_shadow_classifier",
        purpose="Set clarification_needed when the referent ('this alert') has no context.",
        input_shape="A request containing an unresolved demonstrative referent.",
        expected_output_shape="clarification_needed true with clarification output type.",
        authority_boundary="Deterministic clarification guard remains authoritative.",
        version="1.0.0",
        activation="ACTIVE",
        set_id="fewshot:intent_v1",
    ),
    FewShotExample(
        example_id="fs.shape.knowledge_vs_spl",
        role_id="shape_advisor",
        purpose="Distinguish a knowledge question from an SPL authoring request.",
        input_shape="A request that could read as either conceptual or query-producing.",
        expected_output_shape="ShapeAdvisorPayload naming one shape.",
        authority_boundary="Advisory; the deterministic answer-shape router decides.",
        version="1.0.0",
        activation="ACTIVE",
        set_id="fewshot:shape_v1",
    ),
    FewShotExample(
        example_id="fs.template.match_paraphrase",
        role_id="template_match_semantic_assist",
        purpose="Match a paraphrase to a catalogue template id.",
        input_shape="A query plus a bounded candidate template id list.",
        expected_output_shape="A template id drawn from the supplied list.",
        authority_boundary="Never propose an id outside the supplied catalogue.",
        version="1.0.0",
        activation="ACTIVE",
        set_id="fewshot:template_match_v1",
    ),
    FewShotExample(
        example_id="fs.template.fill_unresolved_slot",
        role_id="template_render_parameter_assist",
        purpose="Fill only the slots reported unresolved.",
        input_shape="A slot list split into bound and unresolved.",
        expected_output_shape="Values for unresolved slots only.",
        authority_boundary="Never overwrite a bound slot.",
        version="1.0.0",
        activation="ACTIVE",
        set_id="fewshot:template_render_v1",
    ),
    FewShotExample(
        example_id="fs.planning.bounded_read_only",
        role_id="investigation_planner",
        purpose="Propose a read-only plan inside the approved envelope.",
        input_shape="An approved envelope, evidence state and capability snapshot.",
        expected_output_shape="A plan proposal using only allowed read-only capabilities.",
        authority_boundary="No execution, no envelope widening, no write.",
        version="1.0.0",
        activation="ACTIVE",
        set_id="fewshot:planning_v1",
    ),
    FewShotExample(
        example_id="fs.planning.gap_targeted_delta",
        role_id="plan_delta_reasoner",
        purpose="Target one named evidence gap with one bounded delta.",
        input_shape="An envelope plus a named missing-evidence key.",
        expected_output_shape="One PlanDeltaProposal addressing that gap.",
        authority_boundary="Deterministic validate_plan_delta decides; no self-authorization.",
        version="1.0.0",
        activation="ACTIVE",
        set_id="fewshot:planning_v1",
    ),
    FewShotExample(
        example_id="fs.reasoning.evidence_bounded",
        role_id="pattern_reasoner",
        purpose="Reason only over accepted evidence and say when it is insufficient.",
        input_shape="An accepted-evidence list, possibly empty.",
        expected_output_shape="ReasoningAdvisoryResult, empty when evidence is absent.",
        authority_boundary="No invented evidence, severity or MITRE support.",
        version="1.0.0",
        activation="ACTIVE",
        set_id="fewshot:reasoning_v1",
    ),
    FewShotExample(
        example_id="fs.composer.restate_not_revise",
        role_id="governed_composer",
        purpose="Narrate a deterministic outcome without altering any fact.",
        input_shape="An InvestigationOutcome plus minimal EvidenceState.",
        expected_output_shape="Prose restating severity, disposition and status verbatim.",
        authority_boundary="Facts immutable; no new claim may appear in prose.",
        version="1.0.0",
        activation="ACTIVE",
        set_id="fewshot:composer_v1",
    ),
)

FEW_SHOT_EXAMPLES: tuple[FewShotExample, ...] = _SPL_SHAPE_SHOTS + _OTHER_SHOTS


# ---------------------------------------------------------------------------
# Negative bank
# ---------------------------------------------------------------------------

_SPL_NEGATIVES: tuple[NegativeExample, ...] = (
    NegativeExample(
        example_id="neg.spl.semantic_noun_literalised",
        role_id="spl_advisory_generator",
        purpose="'distinct accounts' is a relationship, not a literal field value.",
        failure_mode="Emits `accounts=*` or `field=accounts` instead of dc(user).",
        corrected_behaviour="Express the distinct-count relationship over the entity role.",
        enforcing_rule="app/spl/spl_semantic_fidelity.py distinct/measure preservation",
        version="1.0.0",
        activation="ACTIVE",
        set_id="negative:spl_semantic_v1",
    ),
    NegativeExample(
        example_id="neg.spl.horizon_window_confused",
        role_id="spl_advisory_generator",
        purpose="Search horizon and analytical window are different bounds.",
        failure_mode="Uses the 10m rolling window as earliest=-10m, losing the 24h horizon.",
        corrected_behaviour="Keep earliest at the horizon; express the window in the analytic.",
        enforcing_rule="spl_intent_spec search_horizon vs analytical_window (spl_semantic_v2)",
        version="1.0.0",
        activation="ACTIVE",
        set_id="negative:spl_semantic_v1",
    ),
    NegativeExample(
        example_id="neg.spl.wrong_grouping_entity",
        role_id="spl_advisory_generator",
        purpose="Grouping entity comes from the declared entity role.",
        failure_mode="Groups by user when the contract declares group_by source address.",
        corrected_behaviour="Group by the entity carrying the group_by role.",
        enforcing_rule="spl_intent_spec ENTITY_ROLE_NAMES + fidelity grouping check",
        version="1.0.0",
        activation="ACTIVE",
        set_id="negative:spl_semantic_v1",
    ),
    NegativeExample(
        example_id="neg.spl.missing_event_population",
        role_id="spl_advisory_generator",
        purpose="Every required event set must appear.",
        failure_mode="Emits only the login event for a password-change-then-login request.",
        corrected_behaviour="Include both required event sets.",
        enforcing_rule="spl_semantic_fidelity required event-set preservation",
        version="1.0.0",
        activation="ACTIVE",
        set_id="negative:spl_semantic_v1",
    ),
    NegativeExample(
        example_id="neg.spl.lost_sequence_order",
        role_id="spl_advisory_generator",
        purpose="An ordered sequence is not a co-occurrence.",
        failure_mode="Emits an unordered correlation for an explicit 'A then B' request.",
        corrected_behaviour="Preserve ordering in the analytic.",
        enforcing_rule="spl_semantic_fidelity ordered-sequence preservation",
        version="1.0.0",
        activation="ACTIVE",
        set_id="negative:spl_semantic_v1",
    ),
    NegativeExample(
        example_id="neg.spl.lost_max_gap",
        role_id="spl_advisory_generator",
        purpose="A maximum event gap is part of the semantics.",
        failure_mode="Drops the 'within 5 minutes' bound.",
        corrected_behaviour="Carry the max gap into the sequence analytic.",
        enforcing_rule="spl_semantic_fidelity max-gap preservation",
        version="1.0.0",
        activation="ACTIVE",
        set_id="negative:spl_semantic_v1",
    ),
    NegativeExample(
        example_id="neg.spl.trend_became_alert",
        role_id="spl_advisory_generator",
        purpose="A trend request is not a detection rule.",
        failure_mode="Converts an hourly trend into a threshold alert with `where count > N`.",
        corrected_behaviour="Emit the time series; invent no threshold.",
        enforcing_rule="spl_semantic_fidelity analysis-shape preservation (trend)",
        version="1.0.0",
        activation="ACTIVE",
        set_id="negative:spl_semantic_v1",
    ),
    NegativeExample(
        example_id="neg.spl.invented_threshold",
        role_id="spl_advisory_generator",
        purpose="Thresholds come from the request, never from the model.",
        failure_mode="Adds `| where count > 5` with no basis in the contract.",
        corrected_behaviour="Emit no threshold unless the contract carries one.",
        enforcing_rule="spl_semantic_fidelity prohibition set (invented constraint)",
        version="1.0.0",
        activation="ACTIVE",
        set_id="negative:spl_semantic_v1",
    ),
    NegativeExample(
        example_id="neg.spl.arbitrary_head_100",
        role_id="spl_advisory_generator",
        purpose="An all-events or time-series shape must not be truncated.",
        failure_mode="Appends `| head 100` to a trend or raw-events candidate.",
        corrected_behaviour="Leave result_cap null for shapes that forbid truncation.",
        enforcing_rule="llm_fallback shape-aware examples (skip_forced_head) + fidelity cap check",
        version="1.0.0",
        activation="ACTIVE",
        set_id="negative:spl_semantic_v1",
    ),
    NegativeExample(
        example_id="neg.spl.unused_normalized_alias",
        role_id="spl_advisory_generator",
        purpose="A declared alias must be consumed downstream.",
        failure_mode="Creates `eval src_ip=coalesce(...)` then groups by the raw field.",
        corrected_behaviour="Use the alias everywhere it was declared for.",
        enforcing_rule="spl_semantic_fidelity normalization-consumer check",
        version="1.0.0",
        activation="ACTIVE",
        set_id="negative:spl_semantic_v1",
    ),
    NegativeExample(
        example_id="neg.spl.candidate_treated_executable",
        role_id="spl_advisory_generator",
        purpose="A candidate is review-only.",
        failure_mode="Returns execution_eligible true or claims the query was run.",
        corrected_behaviour="Always emit execution_eligible false and claim no results.",
        enforcing_rule="validate_spl_lab_candidate pins approved=false / normalized_spl=null",
        version="1.0.0",
        activation="ACTIVE",
        set_id="negative:spl_semantic_v1",
    ),
)

_ROLE_NEGATIVES: tuple[NegativeExample, ...] = (
    NegativeExample(
        example_id="neg.evidence.planned_as_obtained",
        role_id="missing_evidence_reasoner",
        purpose="A planned call is not evidence.",
        failure_mode="Describes a planned MCP call as though its results were obtained.",
        corrected_behaviour="Report the evidence as still missing.",
        enforcing_rule="minimal_evidence_state_v2 records obtained evidence only",
        version="1.0.0",
        activation="ACTIVE",
        set_id="negative:evidence_truth_v1",
    ),
    NegativeExample(
        example_id="neg.evidence.failed_call_as_evidence",
        role_id="evidence_reasoner",
        purpose="A failed or empty call is not evidence.",
        failure_mode="Treats a timeout or empty result set as a negative finding.",
        corrected_behaviour="Report the attempt as failed and the evidence as absent.",
        enforcing_rule="trace_oracle_v1 FAILED/EMPTY states are not obtained evidence",
        version="1.0.0",
        activation="ACTIVE",
        set_id="negative:evidence_truth_v1",
    ),
    NegativeExample(
        example_id="neg.evidence.fabricated_provenance",
        role_id="evidence_observer",
        purpose="Provenance is recorded, never authored.",
        failure_mode="Attributes an observation to a source that produced nothing.",
        corrected_behaviour="Cite only supplied evidence refs.",
        enforcing_rule="SourceEvidence refs are deterministic; observer cannot mutate them",
        version="1.0.0",
        activation="ACTIVE",
        set_id="negative:evidence_truth_v1",
    ),
    NegativeExample(
        example_id="neg.authority.override_deterministic",
        role_id="intent_shadow_classifier",
        purpose="An advisory never overrules a resolved deterministic route.",
        failure_mode="Asserts a different skill and expects it to be used.",
        corrected_behaviour="Report the disagreement; the deterministic route stands.",
        enforcing_rule="governance._advisory_may_replace_skill (Plan 4 D3)",
        version="1.0.0",
        activation="ACTIVE",
        set_id="negative:routing_authority_v1",
    ),
    NegativeExample(
        example_id="neg.authority.shape_advice_as_decision",
        role_id="shape_advisor",
        purpose="Shape advice is advisory.",
        failure_mode="Presents its shape as the selected answer shape.",
        corrected_behaviour="Propose only; the deterministic router selects.",
        enforcing_rule="app/chat/answer_shape_router.py decides before any advisory",
        version="1.0.0",
        activation="ACTIVE",
        set_id="negative:routing_authority_v1",
    ),
    NegativeExample(
        example_id="neg.planning.delta_widens_scope",
        role_id="plan_delta_reasoner",
        purpose="A delta may not widen the approved envelope.",
        failure_mode="Adds a target, entity, index or longer time scope than approved.",
        corrected_behaviour="Stay inside the envelope or report the gap as unresolvable.",
        enforcing_rule="validate_plan_delta material_*_expansion -> hil_required",
        version="1.0.0",
        activation="ACTIVE",
        set_id="negative:planning_authority_v1",
    ),
    NegativeExample(
        example_id="neg.planning.write_as_investigation",
        role_id="plan_delta_reasoner",
        purpose="Investigation is read-only.",
        failure_mode="Proposes a containment or write capability as an investigation delta.",
        corrected_behaviour="Route it to remediation planning instead.",
        enforcing_rule="validate_plan_delta writes_are_not_investigation_plan_delta",
        version="1.0.0",
        activation="ACTIVE",
        set_id="negative:planning_authority_v1",
    ),
    NegativeExample(
        example_id="neg.planning.self_authorized_tool_call",
        role_id="investigation_planner",
        purpose="A plan is not an authorization.",
        failure_mode="Emits a plan that claims the tool call is approved.",
        corrected_behaviour="Propose; the execution gate and HIL authorize.",
        enforcing_rule="mcp_execution_gate + exact-call AUTH0 grant",
        version="1.0.0",
        activation="ACTIVE",
        set_id="negative:planning_authority_v1",
    ),
    NegativeExample(
        example_id="neg.composer.changed_verdict",
        role_id="governed_composer",
        purpose="Narration cannot move a security verdict.",
        failure_mode="Describes an inconclusive outcome as confirmed malicious.",
        corrected_behaviour="Restate the deterministic disposition exactly.",
        enforcing_rule="deterministic fact pinning + answer guard",
        version="1.0.0",
        activation="ACTIVE",
        set_id="negative:composer_v1",
    ),
    NegativeExample(
        example_id="neg.composer.blocked_read_as_benign",
        role_id="governed_composer",
        purpose="A policy block is not a clean bill of health.",
        failure_mode="Narrates investigation_status blocked as 'nothing found'.",
        corrected_behaviour="State that the investigation was blocked and why.",
        enforcing_rule="InvestigationOutcomeV2 separates status from security disposition",
        version="1.0.0",
        activation="ACTIVE",
        set_id="negative:composer_v1",
    ),
    NegativeExample(
        example_id="neg.claims.unsupported_assertion",
        role_id="answer_guard_assistant",
        purpose="Unsupported claims are flagged, not softened.",
        failure_mode="Passes a claim that no evidence ref supports.",
        corrected_behaviour="Flag it and name the missing support.",
        enforcing_rule="app/answer_guard/rules.py unsupported_claims_avoid",
        version="1.0.0",
        activation="ACTIVE",
        set_id="negative:unsupported_claims_v1",
    ),
    NegativeExample(
        example_id="neg.claims.invented_technique_id",
        role_id="mitre_candidate_mapper",
        purpose="Technique IDs come from the registry.",
        failure_mode="Emits a plausible-looking ID absent from the supplied registry.",
        corrected_behaviour="Propose only supplied IDs, or none.",
        enforcing_rule="deterministic MITRE registry validation sets final status",
        version="1.0.0",
        activation="ACTIVE",
        set_id="negative:unsupported_claims_v1",
    ),
    NegativeExample(
        example_id="neg.understanding.invented_locked_fact",
        role_id="semantic_t4",
        purpose="Locked deterministic facts are immutable.",
        failure_mode="Returns a different value for a field the parser already resolved.",
        corrected_behaviour="Echo locked fields unchanged; propose only unresolved ones.",
        enforcing_rule="abstain_acceptance merge gate rejects locked-field contradiction",
        version="1.0.0",
        activation="ACTIVE",
        set_id="negative:understanding_v1",
    ),
)

NEGATIVE_EXAMPLES: tuple[NegativeExample, ...] = _SPL_NEGATIVES + _ROLE_NEGATIVES


# ---------------------------------------------------------------------------
# Accessors — activation-aware. Only ACTIVE assets reach a prompt.
# ---------------------------------------------------------------------------


def few_shot_set(set_id: str) -> tuple[FewShotExample, ...]:
    """Assets in canonical (sorted) order. Ordering is part of the prefix hash."""
    return tuple(
        sorted(
            (e for e in FEW_SHOT_EXAMPLES if e.set_id == set_id and e.activation == "ACTIVE"),
            key=lambda e: e.example_id,
        )
    )


def negative_set(set_id: str) -> tuple[NegativeExample, ...]:
    return tuple(
        sorted(
            (e for e in NEGATIVE_EXAMPLES if e.set_id == set_id and e.activation == "ACTIVE"),
            key=lambda e: e.example_id,
        )
    )


def all_few_shot_set_ids() -> tuple[str, ...]:
    return tuple(sorted({e.set_id for e in FEW_SHOT_EXAMPLES}))


def all_negative_set_ids() -> tuple[str, ...]:
    return tuple(sorted({e.set_id for e in NEGATIVE_EXAMPLES}))


def unsupported_gap_examples() -> tuple[FewShotExample, ...]:
    return tuple(e for e in FEW_SHOT_EXAMPLES if e.activation == "UNSUPPORTED_GAP")
