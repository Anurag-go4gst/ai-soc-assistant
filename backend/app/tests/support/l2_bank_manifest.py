"""L2 production `/chat` bank manifest — the single source of truth for the bank.

Workstream C (P3) owns this file. It is **test architecture only**: nothing here
imports product runtime, and no row may be made green by changing runtime.

Why a manifest instead of just more test functions
--------------------------------------------------
The bank has to answer three questions that a pile of ``def test_*`` cannot:

* *What invariant does this row own?* — duplicated invariants are how a bank grows
  to 120 rows while proving no more than it did at 20. ``INVARIANT_OWNER`` is unique
  across the bank and is checked mechanically.
* *Why is this row not green yet?* — a row blocked on P1/P2/P4 is a planned
  reservation, not a failure. It carries its blocking phase explicitly.
* *What may this row assert?* — a row whose contract has not merged must not guess
  field names. ``EXPECTED_STABLE_ORACLE_FIELDS`` is required to be empty for every
  non-active row, so speculation is a schema error rather than a review opinion.

Status vocabulary
-----------------
``ACTIVE_GREEN``
    Bound to a real test that runs today and passes. Product support was verified by
    probe before the row was written.
``PENDING_CONTRACT_P1`` / ``PENDING_CONTRACT_P2`` / ``PENDING_CONTRACT_P4``
    Reserved. The invariant is real, but its contract is owned by a phase that has
    not merged. Must have **no** bound test and **no** expected oracle fields.
``PENDING_CONTRACT_P5``
    Reserved for cross-stream reconciliation; same rules.
``PRODUCT_GAP``
    The capability does not exist. The row exists so the gap stays visible and is
    never quietly satisfied by weakening an expectation. Requires a
    ``FUTURE_DISPOSITION`` placeholder that only an operator/evidence may resolve.
``DEFERRED``
    Verified supported today, deliberately held out of the first ~23-row bank to keep
    it reviewable. Carries its probe evidence so P5 can activate it without re-deriving.

P0 rows
-------
The 13 P0 cases are registered here by their exact pytest node id and are **not**
rewritten, restyled, or moved. ``test_l2_bank_manifest.py`` asserts each one still
exists and still owns its invariant, so this manifest cannot drift from the file it
describes without turning red.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

CaseStatus = Literal[
    "ACTIVE_GREEN",
    "PENDING_CONTRACT_P1",
    "PENDING_CONTRACT_P2",
    "PENDING_CONTRACT_P4",
    "PENDING_CONTRACT_P5",
    "PRODUCT_GAP",
    "DEFERRED",
]

FutureDisposition = Literal["SUPPORTED_NOW", "DEFERRED", "SEPARATE_PRODUCT_PHASE", "UNDECIDED"]

Tier = Literal["L2", "L2-SLOW"]

ACTIVE_STATUSES: frozenset[str] = frozenset({"ACTIVE_GREEN"})

#: Statuses that must never carry a bound test or a speculative field expectation.
RESERVED_STATUSES: frozenset[str] = frozenset(
    {
        "PENDING_CONTRACT_P1",
        "PENDING_CONTRACT_P2",
        "PENDING_CONTRACT_P4",
        "PENDING_CONTRACT_P5",
        "PRODUCT_GAP",
        "DEFERRED",
    }
)


@dataclass(frozen=True)
class L2Case:
    """One architecture-bearing row of the production `/chat` bank."""

    case_id: str
    title: str
    user_intent: str
    invariant_owner: str
    tier: Tier
    dependency_phase: str
    mocks: tuple[str, ...]
    expected_stable_oracle_fields: tuple[str, ...]
    expected_analyst_visible_result: str
    prohibited_outputs: tuple[str, ...]
    current_status: CaseStatus
    why_this_case_exists: str
    #: pytest node id, relative to ``backend/``. Required iff status is ACTIVE_GREEN.
    bound_test: str | None = None
    #: Only meaningful for PRODUCT_GAP / DEFERRED rows.
    future_disposition: FutureDisposition = "UNDECIDED"
    #: Free-text probe evidence for rows whose support was measured but not activated.
    support_evidence: str = ""
    #: FINDINGS_LEDGER ids this row closes or reserves.
    findings: tuple[str, ...] = field(default_factory=tuple)


_P0 = "app/tests/test_p0_l2_production_chat_harness.py"
_JOURNEYS = "app/tests/test_l2_bank_journeys.py"


# ---------------------------------------------------------------------------
# Block 1 — the 13 P0 cases, preserved verbatim. Registered, never rewritten.
# ---------------------------------------------------------------------------

_P0_CASES: tuple[L2Case, ...] = (
    L2Case(
        case_id="L2.P0.01",
        title="Pure SPL utility authoring routes without investigation machinery",
        user_intent="Author a generic, non-company-specific SPL block for weekend events.",
        invariant_owner="INV.SPL.UTILITY_AUTHORING_ROUTE",
        tier="L2",
        dependency_phase="P0",
        mocks=("spl_policy_env",),
        expected_stable_oracle_fields=("selected_skill", "candidate_spl.generation_mode"),
        expected_analyst_visible_result="A candidate SPL block, or an honest authoring-unavailable mode.",
        prohibited_outputs=("executed SPL", "claimed execution"),
        current_status="ACTIVE_GREEN",
        why_this_case_exists="Utility authoring must not be dragged through investigation lifecycle.",
        bound_test=f"{_P0}::test_l2_pure_spl_utility_authoring_route",
        findings=("H-SPL-01",),
    ),
    L2Case(
        case_id="L2.P0.02",
        title="Approved review-only SPL is never executed",
        user_intent="Give me a review-only SPL for a named index/sourcetype. Do not execute it.",
        invariant_owner="INV.SPL.APPROVED_BUT_NOT_EXECUTED",
        tier="L2",
        dependency_phase="P0",
        mocks=("spl_policy_env",),
        expected_stable_oracle_fields=(
            "spl_validation.approved",
            "execution.status",
            "execution.executed_spl",
        ),
        expected_analyst_visible_result="Validated SPL shown for review; execution status skipped.",
        prohibited_outputs=("execution.status == executed", "non-null executed_spl"),
        current_status="ACTIVE_GREEN",
        why_this_case_exists="Validation approval must never imply execution authorization.",
        bound_test=f"{_P0}::test_l2_exact_bound_review_only_spl_not_executed",
    ),
    L2Case(
        case_id="L2.P0.03",
        title="Genuine investigation stays honest when MCP is unavailable",
        user_intent="Investigate a failed-login spike for a named user/host/IP.",
        invariant_owner="INV.MCP.UNAVAILABLE_HONEST_NON_EXECUTION",
        tier="L2",
        dependency_phase="P0",
        mocks=("spl_policy_env",),
        expected_stable_oracle_fields=("execution.status", "execution.executed_spl"),
        expected_analyst_visible_result="No claimed execution; honest non-execution.",
        prohibited_outputs=("fabricated result rows", "execution.status == executed"),
        current_status="ACTIVE_GREEN",
        why_this_case_exists="Default-off MCP must degrade honestly, not silently fabricate.",
        bound_test=f"{_P0}::test_l2_genuine_investigation_mcp_unavailable_honest",
    ),
    L2Case(
        case_id="L2.P0.04",
        title="Agentic flag posture with the smallest enabling set",
        user_intent="Investigate with resource-plan execution and plan-delta flags enabled.",
        invariant_owner="INV.FLAGS.AGENTIC_SMALLEST_ENABLING_SET",
        tier="L2",
        dependency_phase="P0",
        mocks=("settings_monkeypatch",),
        expected_stable_oracle_fields=(
            "selected_skill",
            "control_plane_trace.mcp_tool_readiness.schema_version",
        ),
        expected_analyst_visible_result="Routing still resolves; readiness trace is v2 or absent.",
        prohibited_outputs=("execution enabled as a side effect of planning flags",),
        current_status="ACTIVE_GREEN",
        why_this_case_exists="Planning flags must not transitively enable execution.",
        bound_test=f"{_P0}::test_l2_agentic_flag_posture_monkeypatch_smallest_set",
        findings=("H-MCP-03",),
    ),
    L2Case(
        case_id="L2.P0.05",
        title="Two productive plan-delta rounds carry distinct fingerprints",
        user_intent="Bounded second read-only round against the same capability.",
        invariant_owner="INV.DELTA.PRODUCTIVE_ROUND_DISTINCT_FINGERPRINT",
        tier="L2",
        dependency_phase="P0",
        mocks=("capability_snapshot_literal",),
        expected_stable_oracle_fields=("decision.status", "validated_delta.revision_fingerprint"),
        expected_analyst_visible_result="Both rounds accepted with different revision fingerprints.",
        prohibited_outputs=("unbounded rounds", "identical fingerprint accepted twice"),
        current_status="ACTIVE_GREEN",
        why_this_case_exists="A second round must be genuinely new work, provably.",
        bound_test=f"{_P0}::test_l2_plan_delta_two_rounds_distinct_fingerprints",
        findings=("H-MCP-04",),
    ),
    L2Case(
        case_id="L2.P0.06",
        title="Metadata capability fallback after a search gap",
        user_intent="Fall back to an index-metadata capability when search leaves a gap.",
        invariant_owner="INV.DELTA.METADATA_FALLBACK_EMPTY_ARGS",
        tier="L2",
        dependency_phase="P0",
        mocks=("capability_snapshot_literal",),
        expected_stable_oracle_fields=("decision.status", "validated_delta.tool_arguments"),
        expected_analyst_visible_result="Accepted metadata delta carrying no invented arguments.",
        prohibited_outputs=("invented tool arguments",),
        current_status="ACTIVE_GREEN",
        why_this_case_exists="Fallback must not smuggle arguments the analyst never approved.",
        bound_test=f"{_P0}::test_l2_metadata_fallback_via_plan_delta_after_search_gap",
        findings=("H-MCP-05",),
    ),
    L2Case(
        case_id="L2.P0.07",
        title="Unavailable capability produces an honest stop",
        user_intent="Request a capability the snapshot reports unavailable.",
        invariant_owner="INV.DELTA.UNAVAILABLE_CAPABILITY_REJECTED",
        tier="L2",
        dependency_phase="P0",
        mocks=("capability_snapshot_literal",),
        expected_stable_oracle_fields=("decision.status", "decision.reason"),
        expected_analyst_visible_result="Rejected with capability_not_available_on_snapshot.",
        prohibited_outputs=("proceeding against an unavailable capability",),
        current_status="ACTIVE_GREEN",
        why_this_case_exists="Snapshot availability is authority, not a hint.",
        bound_test=f"{_P0}::test_l2_unavailable_capability_honest_stop",
        findings=("H-MCP-07",),
    ),
    L2Case(
        case_id="L2.P0.08",
        title="Contradictory evidence stays inconclusive with both sides retained",
        user_intent="Evidence package contains mutually contradictory posture statements.",
        invariant_owner="INV.OUTCOME.CONTRADICTION_RETAINS_BOTH_SIDES",
        tier="L2",
        dependency_phase="P0",
        mocks=("structured_context_literal",),
        expected_stable_oracle_fields=(
            "outcome.disposition",
            "outcome.investigation_status",
            "outcome.findings",
            "outcome.evidence_refs",
        ),
        expected_analyst_visible_result="Inconclusive; both contradictory findings retained.",
        prohibited_outputs=("silently dropping one side", "completed status"),
        current_status="ACTIVE_GREEN",
        why_this_case_exists="Contradiction must be surfaced, never resolved by deletion.",
        bound_test=f"{_P0}::test_l2_contradictory_evidence_disposition_inconclusive_both_retained",
        findings=("H-EVID-01",),
    ),
    L2Case(
        case_id="L2.P0.09",
        title="Follow-up time delta invalidates the prior exact-call grant",
        user_intent="Re-run the same investigation over a different time window.",
        invariant_owner="INV.AUTH0.TIME_DELTA_INVALIDATES_GRANT",
        tier="L2",
        dependency_phase="P0",
        mocks=("call_grant_literal",),
        expected_stable_oracle_fields=("grants_match", "splunk_search_tool_arguments"),
        expected_analyst_visible_result="Prior grant does not authorize the new call.",
        prohibited_outputs=("grant reuse across changed SPL",),
        current_status="ACTIVE_GREEN",
        why_this_case_exists="Exact-call authorization is per-call, not per-session.",
        bound_test=f"{_P0}::test_l2_time_delta_invalidates_exact_call_grant",
        findings=("H-MCP-02", "H-FOLLOW-01"),
    ),
    L2Case(
        case_id="L2.P0.10",
        title="LLM-unavailable utility authoring degrades to a declared source",
        user_intent="Author utility SPL while the LLM draft path is disabled.",
        invariant_owner="INV.LLM.UTILITY_DEGRADATION_DECLARES_SOURCE",
        tier="L2",
        dependency_phase="P0",
        mocks=("settings_monkeypatch",),
        expected_stable_oracle_fields=("candidate_spl.utility_spl_draft_trace.final_raw_spl_source",),
        expected_analyst_visible_result="Draft source is declared, never implied to be a model.",
        prohibited_outputs=("claiming LLM authorship when the LLM was off",),
        current_status="ACTIVE_GREEN",
        why_this_case_exists="Degradation must stay attributable.",
        bound_test=f"{_P0}::test_l2_llm_unavailable_utility_authoring_degrades",
    ),
    L2Case(
        case_id="L2.P0.11",
        title="Unresolved semantic fidelity is not surfaced as satisfied",
        user_intent="LLM returns an SPL that drops the requested semantics.",
        invariant_owner="INV.SPL.SEMANTIC_FIDELITY_FAILS_CLOSED",
        tier="L2",
        dependency_phase="P0",
        mocks=("llm_raw_output_provider", "settings_monkeypatch"),
        expected_stable_oracle_fields=("candidate.candidate_spl", "validation.reject_reasons"),
        expected_analyst_visible_result="Empty candidate plus semantic_fidelity_unresolved reason.",
        prohibited_outputs=("surfacing an unfaithful candidate as approved",),
        current_status="ACTIVE_GREEN",
        why_this_case_exists="Semantic loss must fail closed at authoring time.",
        bound_test=f"{_P0}::test_l2_semantic_fidelity_unresolved_not_surfaced_as_satisfied",
        findings=("H-SPL-01",),
    ),
    L2Case(
        case_id="L2.P0.12",
        title="Containment observation is distinguished from a containment request",
        user_intent="Investigate a deny spike versus explicitly asking to block an IP.",
        invariant_owner="INV.SIGNALS.CONTAINMENT_OBSERVE_VS_REQUEST",
        tier="L2",
        dependency_phase="P0",
        mocks=(),
        expected_stable_oracle_fields=("query_signals.block_or_contain",),
        expected_analyst_visible_result="Only the imperative sets the containment signal.",
        prohibited_outputs=("treating description as instruction",),
        current_status="ACTIVE_GREEN",
        why_this_case_exists="Describing an attack is not requesting a write.",
        bound_test=f"{_P0}::test_l2_containment_observation_vs_request",
    ),
    L2Case(
        case_id="L2.P0.13",
        title="Follow-up entity correction invalidates prior grant and scope",
        user_intent="Use host X instead of host Y.",
        invariant_owner="INV.AUTH0.ENTITY_CORRECTION_INVALIDATES_GRANT",
        tier="L2",
        dependency_phase="P0",
        mocks=("call_grant_literal",),
        expected_stable_oracle_fields=("grants_match", "splunk_search_tool_arguments.search_query"),
        expected_analyst_visible_result="New call scoped to X with no trace of Y.",
        prohibited_outputs=("corrected entity leaking the prior entity",),
        current_status="ACTIVE_GREEN",
        why_this_case_exists="A correction must re-scope, not append.",
        bound_test=f"{_P0}::test_l2_entity_correction_invalidates_prior_grant_and_scope",
        findings=("H-FOLLOW-02",),
    ),
)


# ---------------------------------------------------------------------------
# Block 2 — new P3 rows that are green today. Each was probed before it was
# written; the probe result is quoted in ``why_this_case_exists`` where the
# behaviour is non-obvious.
# ---------------------------------------------------------------------------

_NEW_ACTIVE_CASES: tuple[L2Case, ...] = (
    L2Case(
        case_id="L2.P3.01",
        title="Governed SOC-KB retrieval returns a real SOP match",
        user_intent="What is the SOP for investigating a failed login spike?",
        invariant_owner="INV.RAG.SOP_MATCH_RETRIEVED",
        tier="L2",
        dependency_phase="P3",
        mocks=("soc_kb_retrieval_enabled",),
        expected_stable_oracle_fields=(
            "retrieval_status",
            "retrieved_entries",
            "confidence",
            "evidence_origin",
        ),
        expected_analyst_visible_result="retrieval_status 'retrieved' with at least one governed entry.",
        prohibited_outputs=("entries with no declared evidence_origin",),
        current_status="ACTIVE_GREEN",
        why_this_case_exists=(
            "The bank had no positive RAG row at all. Probed: status 'retrieved', 5 entries, "
            "confidence 1.0, evidence_origin 'stub_rag'."
        ),
        bound_test=f"{_JOURNEYS}::test_l2_rag_sop_match_returns_governed_entries",
        findings=("H-TRACE-03",),
    ),
    L2Case(
        case_id="L2.P3.02",
        title="Out-of-domain question yields an honest RAG no-match",
        user_intent="Ask something the SOC KB genuinely does not cover.",
        invariant_owner="INV.RAG.NO_MATCH_FABRICATES_NOTHING",
        tier="L2",
        dependency_phase="P3",
        mocks=("soc_kb_retrieval_enabled",),
        expected_stable_oracle_fields=(
            "retrieval_status",
            "retrieved_entries",
            "confidence",
            "evidence_origin",
        ),
        expected_analyst_visible_result="retrieval_status 'no_match', zero entries, zero confidence.",
        prohibited_outputs=("near-miss entries presented as a match", "non-zero confidence"),
        current_status="ACTIVE_GREEN",
        why_this_case_exists=(
            "No-match is the failure mode that invents citations. Probed: status 'no_match', "
            "0 entries, confidence 0.0, evidence_origin 'none'."
        ),
        bound_test=f"{_JOURNEYS}::test_l2_rag_no_match_returns_nothing_and_says_so",
        findings=("H-TRACE-03", "H-TRACE-08"),
    ),
    L2Case(
        case_id="L2.P3.03",
        title="Default production posture leaves SOC-KB retrieval disabled and says so",
        user_intent="Any KB-eligible question on a default-configured deployment.",
        invariant_owner="INV.RAG.DEFAULT_OFF_POSTURE_DECLARED",
        tier="L2",
        dependency_phase="P3",
        mocks=(),
        expected_stable_oracle_fields=("retrieval_status", "reasons", "retrieved_entries"),
        expected_analyst_visible_result="retrieval_status 'disabled' with soc_kb_retrieval_disabled reason.",
        prohibited_outputs=("'no_match' used to describe a disabled subsystem",),
        current_status="ACTIVE_GREEN",
        why_this_case_exists=(
            "'Disabled' and 'no_match' mean different things to an analyst. settings."
            "soc_kb_retrieval_enabled defaults False, so this is the shipped posture."
        ),
        bound_test=f"{_JOURNEYS}::test_l2_rag_disabled_by_default_is_declared_not_silent",
        findings=("H-TRACE-03",),
    ),
    L2Case(
        case_id="L2.P3.04",
        title="Empty evidence yields an incomplete outcome with nothing invented",
        user_intent="Investigation reaches outcome derivation having obtained no evidence.",
        invariant_owner="INV.OUTCOME.EMPTY_EVIDENCE_INVENTS_NOTHING",
        tier="L2",
        dependency_phase="P3",
        mocks=(),
        expected_stable_oracle_fields=(
            "outcome.investigation_status",
            "outcome.disposition",
            "outcome.findings",
            "outcome.evidence_refs",
        ),
        expected_analyst_visible_result="incomplete / inconclusive with empty findings and refs.",
        prohibited_outputs=("completed status", "any finding", "any evidence ref"),
        current_status="ACTIVE_GREEN",
        why_this_case_exists=(
            "P0.08 proves contradiction handling but never the zero-evidence floor. "
            "Probed: incomplete / inconclusive / [] / []."
        ),
        bound_test=f"{_JOURNEYS}::test_l2_empty_evidence_outcome_invents_no_findings",
        findings=("H-TRACE-08", "H-EVID-03"),
    ),
    L2Case(
        case_id="L2.P3.05",
        title="Policy block is an investigation status, not a security disposition",
        user_intent="Investigation blocked by policy before evidence sufficiency.",
        invariant_owner="INV.OUTCOME.BLOCKED_STATUS_NOT_SECURITY_VERDICT",
        tier="L2",
        dependency_phase="P3",
        mocks=(),
        expected_stable_oracle_fields=("outcome.investigation_status", "outcome.disposition"),
        expected_analyst_visible_result="investigation_status 'blocked' while disposition stays a security value.",
        prohibited_outputs=("disposition == 'blocked'", "policy block read as benign"),
        current_status="ACTIVE_GREEN",
        why_this_case_exists=(
            "architecture.md:103 states this separation explicitly and nothing in the bank held it. "
            "Probed: investigation_status 'blocked', disposition 'inconclusive'."
        ),
        bound_test=f"{_JOURNEYS}::test_l2_policy_block_is_status_not_security_disposition",
    ),
    L2Case(
        case_id="L2.P3.06",
        title="Negative evidence produces benign, not inconclusive",
        user_intent="Evidence affirmatively shows the suspected activity did not occur.",
        invariant_owner="INV.OUTCOME.NEGATIVE_EVIDENCE_IS_BENIGN",
        tier="L2",
        dependency_phase="P3",
        mocks=("canonical_facts_literal",),
        expected_stable_oracle_fields=("outcome.disposition", "outcome.investigation_status"),
        expected_analyst_visible_result="disposition 'benign'.",
        prohibited_outputs=("collapsing negative evidence into 'inconclusive'",),
        current_status="ACTIVE_GREEN",
        why_this_case_exists=(
            "'We looked and it is not there' is a different answer from 'we could not tell'. "
            "Probed: disposition 'benign' with investigation_status still 'incomplete'."
        ),
        bound_test=f"{_JOURNEYS}::test_l2_negative_evidence_yields_benign_disposition",
    ),
    L2Case(
        case_id="L2.P3.07",
        title="A repeated identical plan delta is refused as no-progress",
        user_intent="Second round proposes exactly the same read-only work as the first.",
        invariant_owner="INV.DELTA.DUPLICATE_IS_NO_PROGRESS",
        tier="L2",
        dependency_phase="P3",
        mocks=("capability_snapshot_literal",),
        expected_stable_oracle_fields=("decision.status", "decision.reason", "decision.validated_delta"),
        expected_analyst_visible_result="status 'no_progress', reason duplicate_effective_plan_delta, no delta.",
        prohibited_outputs=("accepting a duplicate as a productive round", "spending budget on a no-op"),
        current_status="ACTIVE_GREEN",
        why_this_case_exists=(
            "P0.05 proves distinct rounds are accepted; the complementary bound was untested. "
            "Probed: no_progress / duplicate_effective_plan_delta / validated_delta None."
        ),
        bound_test=f"{_JOURNEYS}::test_l2_duplicate_plan_delta_is_refused_as_no_progress",
        findings=("H-MCP-04",),
    ),
    L2Case(
        case_id="L2.P3.08",
        title="A write is never an investigation plan delta",
        user_intent="Propose a write-mode capability inside a read-only investigation delta.",
        invariant_owner="INV.DELTA.WRITE_IS_NOT_INVESTIGATION",
        tier="L2",
        dependency_phase="P3",
        mocks=("capability_snapshot_literal",),
        expected_stable_oracle_fields=("decision.status", "decision.reason", "decision.validated_delta"),
        expected_analyst_visible_result="Routed to remediation_recommended; no validated delta.",
        prohibited_outputs=("a write validated as read-only investigation work",),
        current_status="ACTIVE_GREEN",
        why_this_case_exists=(
            "architecture.md:1884 separates read-only investigation from remediation. "
            "Probed: remediation_recommended / writes_are_not_investigation_plan_delta / None."
        ),
        bound_test=f"{_JOURNEYS}::test_l2_write_access_mode_is_not_an_investigation_delta",
        findings=("H-REM-02",),
    ),
    L2Case(
        case_id="L2.P3.09",
        title="Remediation is offered once and declining leaves no plan",
        user_intent="Investigation completes; analyst declines the remediation offer.",
        invariant_owner="INV.REMEDIATION.OFFER_THEN_DECLINE_LEAVES_NO_PLAN",
        tier="L2",
        dependency_phase="P3",
        mocks=("remediation_planner_enabled", "investigation_outcome_literal"),
        expected_stable_oracle_fields=(
            "remediation_approval.status",
            "remediation_approval.allowed_actions",
            "remediation_approval.validated_plan",
        ),
        expected_analyst_visible_result="offered with [create, decline]; then declined with no plan.",
        prohibited_outputs=("a plan built without being asked", "more than one remediation CTA"),
        current_status="ACTIVE_GREEN",
        why_this_case_exists=(
            "The offer is the first point where investigation can leak into action. "
            "Probed: offered/[create,decline] then declined/validated_plan None."
        ),
        bound_test=f"{_JOURNEYS}::test_l2_remediation_offer_then_decline_builds_no_plan",
        findings=("H-REM-01",),
    ),
    L2Case(
        case_id="L2.P3.10",
        title="Approving a remediation plan authorizes nothing by itself",
        user_intent="Analyst creates and then approves a remediation plan.",
        invariant_owner="INV.REMEDIATION.APPROVAL_IS_NOT_EXECUTION",
        tier="L2",
        dependency_phase="P3",
        mocks=("remediation_planner_enabled", "investigation_outcome_literal"),
        expected_stable_oracle_fields=(
            "remediation_approval.status",
            "validated_plan.execution_authorized",
            "validated_plan.human_approval_required",
            "approved_remediation_envelope.envelope_version",
            "remediation_approval.execution_result",
        ),
        expected_analyst_visible_result=(
            "awaiting_approval then approved, with an envelope and no execution result."
        ),
        prohibited_outputs=(
            "execution_authorized true",
            "any execution_result",
            "remediation_execution present in state",
        ),
        current_status="ACTIVE_GREEN",
        why_this_case_exists=(
            "Approval produces an envelope that is the *input* to execution, never the "
            "authorization. Probed: approved / envelope_version 1 / execution_result None / "
            "no remediation_execution key."
        ),
        bound_test=f"{_JOURNEYS}::test_l2_remediation_approval_yields_envelope_without_execution",
        findings=("H-REM-01", "H-REM-02"),
    ),
)


# ---------------------------------------------------------------------------
# Block 3 — reserved rows. No bound test, no expected oracle fields.
#
# These are deliberately field-free. A reserved row that names a field is
# guessing at a contract another workstream has not published yet, and
# ``test_l2_bank_manifest.py`` turns that guess into a red test rather than a
# review argument. The *invariant* is stated in prose, which is exactly the part
# that does not change when the field names land.
# ---------------------------------------------------------------------------

_RESERVED_CASES: tuple[L2Case, ...] = (
    # --- P1: trace truth / stable oracle -----------------------------------
    L2Case(
        case_id="L2.R.P1.01",
        title="LLM lifecycle oracle distinguishes attempted from used",
        user_intent="A turn in which the LLM is called, responds, and is then rejected.",
        invariant_owner="INV.TRACE.LLM_ATTEMPTED_VS_USED",
        tier="L2",
        dependency_phase="P1",
        mocks=("llm_raw_output_provider",),
        expected_stable_oracle_fields=("trace_oracle.llm_lifecycle.states",),
        expected_analyst_visible_result="An attempted-but-rejected model call never reads as a used one.",
        prohibited_outputs=("one boolean collapsing attempt, response and acceptance",),
        current_status="ACTIVE_GREEN",
        why_this_case_exists="P1 freezes the PLANNED/ATTEMPTED/RESPONSE_RECEIVED/ACCEPTED/USED vocabulary.",
        bound_test=f"{_JOURNEYS}::test_l2_llm_lifecycle_attempted_is_not_used",
        findings=("H-TRACE-01",),
    ),
    L2Case(
        case_id="L2.R.P1.02",
        title="Fallback terminology is consistent across surfaces",
        user_intent="A turn that falls back from LLM authoring to a deterministic path.",
        invariant_owner="INV.TRACE.FALLBACK_LABEL_CONSISTENCY",
        tier="L2",
        dependency_phase="P1",
        mocks=("settings_monkeypatch",),
        expected_stable_oracle_fields=("spl_artifact_source",),
        expected_analyst_visible_result="One fallback concept, one name, everywhere it appears.",
        prohibited_outputs=("two names for one fallback state",),
        current_status="ACTIVE_GREEN",
        why_this_case_exists="P1 canonicalizes fallback as deterministic_fallback on the provenance surface.",
        bound_test=f"{_JOURNEYS}::test_l2_fallback_label_is_deterministic_fallback",
        findings=("H-TRACE-02",),
    ),
    L2Case(
        case_id="L2.R.P1.03",
        title="Artifact review is distinct from execution HIL",
        user_intent="A candidate SPL needing review while no execution is pending.",
        invariant_owner="INV.TRACE.ARTIFACT_REVIEW_VS_EXECUTION_HIL",
        tier="L2",
        dependency_phase="P1",
        mocks=(),
        expected_stable_oracle_fields=(
            "trace_oracle.spl_artifact.artifact_review_required",
            "trace_oracle.execution_review.execution_hil_required",
        ),
        expected_analyst_visible_result="Reviewing an artifact never presents as approving an execution.",
        prohibited_outputs=("one flag serving both meanings",),
        current_status="ACTIVE_GREEN",
        why_this_case_exists="P1 splits artifact_review_required from execution_hil_required.",
        bound_test=f"{_JOURNEYS}::test_l2_artifact_review_is_not_execution_hil",
        findings=("H-TRACE-04",),
    ),
    L2Case(
        case_id="L2.R.P1.04",
        title="Pure SPL authoring projects no InvestigationOutcome",
        user_intent="A pure SPL authoring request that produces diagnostics only.",
        invariant_owner="INV.TRACE.PURE_SPL_NO_INVESTIGATION_OUTCOME",
        tier="L2",
        dependency_phase="P1",
        mocks=("spl_policy_env",),
        expected_stable_oracle_fields=("investigation_outcome_applicable",),
        expected_analyst_visible_result="No empty investigation shell on a non-investigation product.",
        prohibited_outputs=("an InvestigationOutcome projected because diagnostics exist",),
        current_status="ACTIVE_GREEN",
        why_this_case_exists="architecture.md:286; P1 owns the applicability reproof.",
        bound_test=f"{_JOURNEYS}::test_l2_pure_spl_authoring_projects_no_investigation_outcome",
        findings=("H-TRACE-05",),
    ),
    L2Case(
        case_id="L2.R.P1.05",
        title="Stable oracle fields are separable from diagnostics",
        user_intent="Any turn; assert only the versioned oracle, never diagnostic detail.",
        invariant_owner="INV.TRACE.ORACLE_VERSUS_DIAGNOSTICS",
        tier="L2",
        dependency_phase="P1",
        mocks=(),
        expected_stable_oracle_fields=("trace_oracle.schema_version", "run_shape_transition.schema_version"),
        expected_analyst_visible_result="A documented, versioned oracle surface exists to assert against.",
        prohibited_outputs=("contract assertions on diagnostic ordering or timing",),
        current_status="ACTIVE_GREEN",
        why_this_case_exists="This row is why the rest of the bank can stay non-brittle.",
        bound_test=f"{_JOURNEYS}::test_l2_stable_oracle_excludes_diagnostics",
        findings=("H-TRACE-06",),
    ),
    L2Case(
        case_id="L2.R.P1.06",
        title="EvidenceState records only obtained evidence",
        user_intent="A turn where evidence was planned and attempted but never obtained.",
        invariant_owner="INV.EVIDENCE.PLANNED_IS_NOT_OBTAINED",
        tier="L2",
        dependency_phase="P1",
        mocks=("capability_snapshot_literal",),
        expected_stable_oracle_fields=("evidence_state.obtained", "evidence_state.missing"),
        expected_analyst_visible_result="Plans and failures never appear as evidence.",
        prohibited_outputs=("an attempt counted as evidence", "an empty projection counted as evidence"),
        current_status="ACTIVE_GREEN",
        why_this_case_exists="Non-negotiable invariant 6; P1 owns the EvidenceState truth matrix.",
        bound_test=f"{_JOURNEYS}::test_l2_planned_evidence_is_not_obtained",
        findings=("H-TRACE-08", "H-EVID-03"),
    ),
    # --- P2: SPL semantic V2 -----------------------------------------------
    L2Case(
        case_id="L2.R.P2.01",
        title="Rolling window over distinct accounts is preserved end to end",
        user_intent="Rolling distinct accounts per source over a 10-minute window.",
        invariant_owner="INV.SPL.ROLLING_WINDOW_PRESERVED",
        tier="L2",
        dependency_phase="P2",
        mocks=("llm_raw_output_provider",),
        expected_stable_oracle_fields=("analysis_shape", "analytical_window"),
        expected_analyst_visible_result="The rolling window survives authoring and postprocessing.",
        prohibited_outputs=("a rolling ask degraded to a flat aggregate",),
        current_status="ACTIVE_GREEN",
        why_this_case_exists="One of the three measured semantic failures that motivated P2.",
        bound_test=f"{_JOURNEYS}::test_l2_rolling_window_is_preserved_through_compiler",
        findings=("H-SPL-03", "H-SPL-06"),
    ),
    L2Case(
        case_id="L2.R.P2.02",
        title="Hourly failed-login trend over 24h keeps its temporal grain",
        user_intent="Hourly trend of failed logins across the last 24 hours.",
        invariant_owner="INV.SPL.TEMPORAL_GRAIN_PRESERVED",
        tier="L2",
        dependency_phase="P2",
        mocks=("llm_raw_output_provider",),
        expected_stable_oracle_fields=("temporal_grain",),
        expected_analyst_visible_result="Hourly buckets survive; the series is not collapsed.",
        prohibited_outputs=("a trend ask answered with a single total",),
        current_status="ACTIVE_GREEN",
        why_this_case_exists="Second of the three measured semantic failures.",
        bound_test=f"{_JOURNEYS}::test_l2_hourly_trend_keeps_temporal_grain",
        findings=("H-SPL-08", "H-SPL-09"),
    ),
    L2Case(
        case_id="L2.R.P2.03",
        title="Ordered sequence with a maximum gap is preserved",
        user_intent="Password change followed by a login within five minutes.",
        invariant_owner="INV.SPL.ORDERED_SEQUENCE_AND_MAX_GAP",
        tier="L2",
        dependency_phase="P2",
        mocks=("llm_raw_output_provider",),
        expected_stable_oracle_fields=("ordered_sequence", "sequence_max_gap"),
        expected_analyst_visible_result="Order and the five-minute bound both survive.",
        prohibited_outputs=("an unordered co-occurrence answering an ordered ask",),
        current_status="ACTIVE_GREEN",
        why_this_case_exists="Third of the three measured semantic failures.",
        bound_test=f"{_JOURNEYS}::test_l2_ordered_sequence_and_max_gap_are_preserved",
        findings=("H-SPL-10", "H-SPL-11", "H-SPL-21"),
    ),
    L2Case(
        case_id="L2.R.P2.04",
        title="Semantic fail-closed reason is analyst-readable, not just internal",
        user_intent="A request whose semantics the compiler cannot support.",
        invariant_owner="INV.SPL.FAIL_CLOSED_REASON_IS_VISIBLE",
        tier="L2",
        dependency_phase="P2",
        mocks=("llm_raw_output_provider",),
        expected_stable_oracle_fields=(),
        expected_analyst_visible_result="The analyst is told what was lost and why, in their language.",
        prohibited_outputs=("a bare reject code as the whole explanation",),
        current_status="PENDING_CONTRACT_P2",
        why_this_case_exists=(
            "P0.11 proves the gate fires; this row is about analyst-language explanation. "
            "P2 still publishes only reject_reasons/semantic_fidelity_unresolved — no separate "
            "analyst-readable fail-closed prose contract. Left pending rather than inventing a field."
        ),
        findings=("H-SPL-01",),
    ),
    L2Case(
        case_id="L2.R.P2.05",
        title="Normalization aliases are actually consumed downstream",
        user_intent="A request whose source profile declares field aliases.",
        invariant_owner="INV.SPL.NORMALIZATION_ALIAS_CONSUMED",
        tier="L2",
        dependency_phase="P2",
        mocks=("source_profile_literal",),
        expected_stable_oracle_fields=("normalization_requirements", "normalization_consumers"),
        expected_analyst_visible_result="Declared aliases appear in the authored SPL.",
        prohibited_outputs=("aliases declared then ignored",),
        current_status="ACTIVE_GREEN",
        why_this_case_exists="A normalization contract nothing consumes is decoration.",
        bound_test=f"{_JOURNEYS}::test_l2_normalization_aliases_are_consumed_in_compiled_spl",
        findings=("H-SPL-14",),
    ),
    L2Case(
        case_id="L2.R.P2.06",
        title="Analytical shapes are not silently truncated",
        user_intent="An all-events or time-series request that must not be capped at 100 rows.",
        invariant_owner="INV.SPL.NO_ARBITRARY_TRUNCATION",
        tier="L2",
        dependency_phase="P2",
        mocks=("llm_raw_output_provider",),
        expected_stable_oracle_fields=("result_limit",),
        expected_analyst_visible_result="No invented head/limit on a shape that forbids it.",
        prohibited_outputs=("an unrequested result cap on a trend or raw-events ask",),
        current_status="ACTIVE_GREEN",
        why_this_case_exists="Measured prompt-bias failure; P2/P4 jointly own the fix.",
        bound_test=f"{_JOURNEYS}::test_l2_analytical_shapes_are_not_arbitrarily_truncated",
        findings=("H-SPL-15", "H-SPL-17"),
    ),
    # --- P4: prompt / role policy / provenance ------------------------------
    L2Case(
        case_id="L2.R.P4.01",
        title="Prompt identity, version and content hash are deterministic",
        user_intent="Two identical turns must report identical prompt provenance.",
        invariant_owner="INV.PROMPT.PROVENANCE_DETERMINISTIC",
        tier="L2",
        dependency_phase="P4",
        mocks=("llm_raw_output_provider",),
        expected_stable_oracle_fields=("prompt_template_id", "prompt_version", "prompt_hash", "stable_prefix_hash"),
        expected_analyst_visible_result="Operators can tell exactly which prompt ran.",
        prohibited_outputs=("a hash that changes without the prompt changing",),
        current_status="ACTIVE_GREEN",
        why_this_case_exists="P4 defines the provenance schema; P8 depends on it for A/B. LIVE_AB_EVAL_PERFORMED=NO.",
        bound_test=f"{_JOURNEYS}::test_l2_prompt_provenance_is_deterministic",
        findings=("H-PROMPT-05",),
    ),
    L2Case(
        case_id="L2.R.P4.02",
        title="Blocked reasoning roles stay blocked and say so",
        user_intent="A turn that would reach a dormant reasoner if the allowlist were wrong.",
        invariant_owner="INV.PROMPT.DORMANT_ROLE_POSTURE_HELD",
        tier="L2",
        dependency_phase="P4",
        mocks=(),
        expected_stable_oracle_fields=("blocked_role_ids",),
        expected_analyst_visible_result="Dormant reasoners do not run and their posture is legible.",
        prohibited_outputs=("a reasoner activated as a side effect of another change",),
        current_status="ACTIVE_GREEN",
        why_this_case_exists="H-PROMPT-04 is an operator decision, not a default.",
        bound_test=f"{_JOURNEYS}::test_l2_blocked_reasoning_roles_stay_blocked",
        findings=("H-PROMPT-01", "H-PROMPT-04"),
    ),
    L2Case(
        case_id="L2.R.P4.03",
        title="Shape advice never becomes authority",
        user_intent="A turn where the shape advisor disagrees with the deterministic router.",
        invariant_owner="INV.PROMPT.SHAPE_ADVISOR_STAYS_ADVISORY",
        tier="L2",
        dependency_phase="P4",
        mocks=("llm_raw_output_provider",),
        expected_stable_oracle_fields=("shape_advisory.used", "shape_advisory.ignored_reason"),
        expected_analyst_visible_result="Deterministic shape wins; the advisory is recorded, not obeyed.",
        prohibited_outputs=("advisory output selecting the final answer shape",),
        current_status="ACTIVE_GREEN",
        why_this_case_exists="Mirrors the Plan 4 D3 routing lesson on the answer-shape axis.",
        bound_test=f"{_JOURNEYS}::test_l2_shape_advisor_stays_advisory",
        findings=("H-PROMPT-03",),
    ),
    L2Case(
        case_id="L2.R.P4.04",
        title="Prompt cache metadata never becomes authority or crosses sessions",
        user_intent="Two different sessions issuing the same prompt prefix.",
        invariant_owner="INV.PROMPT.CACHE_IS_NOT_AUTHORITY",
        tier="L2",
        dependency_phase="P4",
        mocks=(),
        expected_stable_oracle_fields=("cache_eligible", "cache_policy_version"),
        expected_analyst_visible_result="Cache state is observable but never decides anything.",
        prohibited_outputs=("cached content crossing an auth/session boundary",),
        current_status="ACTIVE_GREEN",
        why_this_case_exists="H-PROMPT-10 is a security invariant, not a performance one.",
        bound_test=f"{_JOURNEYS}::test_l2_prompt_cache_metadata_is_not_authority",
        findings=("H-PROMPT-06", "H-PROMPT-10"),
    ),
    # --- P5: cross-stream reconciliation ------------------------------------
    L2Case(
        case_id="L2.R.P5.01",
        title="Analyst rejection of a result is honoured on the next turn",
        user_intent="'That is wrong, those are service accounts.'",
        invariant_owner="INV.FOLLOWUP.USER_REJECTION_HONOURED",
        tier="L2",
        dependency_phase="P5",
        mocks=("session_pins",),
        expected_stable_oracle_fields=(),
        expected_analyst_visible_result="The rejected conclusion is not restated as fact.",
        prohibited_outputs=("repeating a rejected conclusion unchanged",),
        current_status="PENDING_CONTRACT_P5",
        why_this_case_exists=(
            "H-FOLLOW-05. P1 published trace_oracle_v1 and EvidenceState, but SessionPins has "
            "no rejected-conclusion field and production /chat has no governed follow-up "
            "contract that honours 'that is wrong' as a stable oracle. Left pending rather "
            "than inventing a pin or asserting EC S6 chip behaviour as production."
        ),
        findings=("H-FOLLOW-05",),
    ),
    L2Case(
        case_id="L2.R.P5.02",
        title="Analyst-supplied evidence enters as evidence, with its origin declared",
        user_intent="'Here is the ticket, the change window was approved.'",
        invariant_owner="INV.FOLLOWUP.USER_ADDED_EVIDENCE_ATTRIBUTED",
        tier="L2",
        dependency_phase="P5",
        mocks=("session_pins",),
        expected_stable_oracle_fields=(),
        expected_analyst_visible_result="User-supplied evidence is used and attributed to the user.",
        prohibited_outputs=("user assertion presented as retrieved system evidence",),
        current_status="PENDING_CONTRACT_P5",
        why_this_case_exists=(
            "H-FOLLOW-05 / H-EVID-03. source_type=manual maps to untrusted_input in "
            "minimal_evidence_state_v2, but that path is the skipped analyst_query "
            "placeholder, not ticket/change-window intake. No production seam accepts "
            "analyst-supplied SourceEvidence with declared user origin. Left pending."
        ),
        findings=("H-FOLLOW-05", "H-EVID-03"),
    ),
    # --- PRODUCT_GAP: kept visible, never satisfied by weakening ------------
    L2Case(
        case_id="L2.G.01",
        title="'Run that for yesterday' relative-time follow-up",
        user_intent="Re-run the previous query over yesterday.",
        invariant_owner="INV.GAP.RELATIVE_TIME_FOLLOWUP",
        tier="L2",
        dependency_phase="P5",
        mocks=(),
        expected_stable_oracle_fields=(),
        expected_analyst_visible_result="UNPROVEN — no measured support exists today.",
        prohibited_outputs=("marking this green by loosening the time assertion",),
        current_status="PRODUCT_GAP",
        why_this_case_exists="H-FOLLOW-03 is unproven, not merely untested. The row keeps it visible.",
        future_disposition="UNDECIDED",
        findings=("H-FOLLOW-03",),
    ),
    L2Case(
        case_id="L2.G.02",
        title="'Same campaign as last month' historical comparison",
        user_intent="Compare current activity against a prior period.",
        invariant_owner="INV.GAP.HISTORICAL_COMPARISON",
        tier="L2",
        dependency_phase="P2",
        mocks=(),
        expected_stable_oracle_fields=(),
        expected_analyst_visible_result="UNPROVEN — comparison semantics are not implemented.",
        prohibited_outputs=("answering a comparison with a single-period result",),
        current_status="PRODUCT_GAP",
        why_this_case_exists="H-SPL-12 / H-FOLLOW-04 both require a product capability decision.",
        future_disposition="UNDECIDED",
        findings=("H-SPL-12", "H-FOLLOW-04"),
    ),
    L2Case(
        case_id="L2.G.03",
        title="Explicit evidence-level contradiction adjudication",
        user_intent="Two sources disagree and the analyst asks which one to believe.",
        invariant_owner="INV.GAP.CONTRADICTION_ADJUDICATION",
        tier="L2",
        dependency_phase="P5",
        mocks=(),
        expected_stable_oracle_fields=(),
        expected_analyst_visible_result="UNPROVEN — P0.08 retains both sides but adjudicates neither.",
        prohibited_outputs=("picking a side without a stated adjudication rule",),
        current_status="PRODUCT_GAP",
        why_this_case_exists="H-EVID-02. Retention is implemented; adjudication is not.",
        future_disposition="UNDECIDED",
        findings=("H-EVID-02",),
    ),
    L2Case(
        case_id="L2.G.04",
        title="Execute then verify then monitor remediation lifecycle",
        user_intent="Apply the remediation and confirm it worked.",
        invariant_owner="INV.GAP.REMEDIATION_VERIFY_MONITOR",
        tier="L2",
        dependency_phase="P7",
        mocks=(),
        expected_stable_oracle_fields=(),
        expected_analyst_visible_result="UNPROVEN — approval yields an envelope; the loop ends there.",
        prohibited_outputs=("presenting approval as completed remediation",),
        current_status="PRODUCT_GAP",
        why_this_case_exists=(
            "H-REM-03. L2.P3.10 proves approval authorizes nothing; this row records that the "
            "verify/monitor half does not exist yet."
        ),
        future_disposition="UNDECIDED",
        findings=("H-REM-03",),
    ),
    L2Case(
        case_id="L2.G.05",
        title="Non-Splunk MCP playbooks",
        user_intent="Investigate using an MCP server that is not Splunk.",
        invariant_owner="INV.GAP.NON_SPLUNK_MCP_PLAYBOOK",
        tier="L2",
        dependency_phase="P11",
        mocks=(),
        expected_stable_oracle_fields=(),
        expected_analyst_visible_result="UNPROVEN — the registry is generic; no second server is proven.",
        prohibited_outputs=("claiming multi-server support from registry genericity alone",),
        current_status="PRODUCT_GAP",
        why_this_case_exists="H-MCP-10 requires a capability inventory before any row can be written.",
        future_disposition="UNDECIDED",
        findings=("H-MCP-10",),
    ),
    # --- DEFERRED: measured as supported, held out of the first bank --------
    L2Case(
        case_id="L2.D.01",
        title="Cancelling a remediation plan calls no connector",
        user_intent="Analyst cancels after seeing the plan.",
        invariant_owner="INV.REMEDIATION.CANCEL_CALLS_NOTHING",
        tier="L2",
        dependency_phase="P5",
        mocks=("remediation_planner_enabled",),
        expected_stable_oracle_fields=(
            "remediation_approval.status",
            "remediation_approval.safe_message",
            "approved_remediation_envelope",
        ),
        expected_analyst_visible_result="status 'cancelled' with an explicit no-connector message.",
        prohibited_outputs=("a partial write on cancel",),
        current_status="ACTIVE_GREEN",
        why_this_case_exists=(
            "Held out of the first ~23-row bank; P5 activates it. Cancel is the "
            "Approve/Edit/Cancel vocabulary's abort path and must call no connector."
        ),
        bound_test=f"{_JOURNEYS}::test_l2_remediation_cancel_calls_no_connector",
        future_disposition="SUPPORTED_NOW",
        support_evidence=(
            "Probed at ae03a250: handle_remediation_review(action='cancel') -> status 'cancelled', "
            "message 'Remediation cancelled. No connector was called and nothing was changed.'"
        ),
        findings=("H-REM-01",),
    ),
    L2Case(
        case_id="L2.D.02",
        title="Remediation planning is off by default",
        user_intent="A completed investigation on a default-configured deployment.",
        invariant_owner="INV.REMEDIATION.DEFAULT_OFF_POSTURE",
        tier="L2",
        dependency_phase="P5",
        mocks=(),
        expected_stable_oracle_fields=("remediation_approval",),
        expected_analyst_visible_result="No remediation CTA appears at all.",
        prohibited_outputs=("an unrequested action affordance on a default deployment",),
        current_status="ACTIVE_GREEN",
        why_this_case_exists=(
            "Held out of the first ~23-row bank; P5 activates it. Default-off is the "
            "deployment posture, not a test monkeypatch."
        ),
        bound_test=f"{_JOURNEYS}::test_l2_remediation_planning_is_off_by_default",
        future_disposition="SUPPORTED_NOW",
        support_evidence=(
            "Probed at ae03a250: settings.ai_soc_remediation_planner_enabled default is False and "
            "maybe_attach_remediation_offer returns state unchanged when it is false."
        ),
        findings=("H-REM-01",),
    ),
    L2Case(
        case_id="L2.D.03",
        title="Editing a remediation plan revalidates it before approval",
        user_intent="Analyst removes a step, then approves what remains.",
        invariant_owner="INV.REMEDIATION.EDIT_REVALIDATES",
        tier="L2",
        dependency_phase="P5",
        mocks=("remediation_planner_enabled",),
        expected_stable_oracle_fields=(
            "remediation_approval.status",
            "remediation_approval.allowed_actions",
            "remediation_approval.revalidation_warnings",
        ),
        expected_analyst_visible_result="status 'edited_revalidated' before approval is offered again.",
        prohibited_outputs=("approving an edited plan that was never revalidated",),
        current_status="ACTIVE_GREEN",
        why_this_case_exists=(
            "Held out of the first ~23-row bank; P5 activates it. Edit must revalidate "
            "before Approve is offered again; approval still executes nothing."
        ),
        bound_test=f"{_JOURNEYS}::test_l2_remediation_edit_revalidates_before_approval",
        future_disposition="SUPPORTED_NOW",
        support_evidence=(
            "Read at ae03a250: handle_remediation_review(action='edit') builds status "
            "'edited_revalidated' via _apply_edits + _approval_state. Journey now proves it."
        ),
        findings=("H-REM-01",),
    ),
)


CASES: tuple[L2Case, ...] = _P0_CASES + _NEW_ACTIVE_CASES + _RESERVED_CASES

P0_CASES: tuple[L2Case, ...] = _P0_CASES
NEW_ACTIVE_CASES: tuple[L2Case, ...] = _NEW_ACTIVE_CASES
RESERVED_CASES: tuple[L2Case, ...] = _RESERVED_CASES


def active_cases() -> tuple[L2Case, ...]:
    """Rows that must run and pass today."""
    return tuple(case for case in CASES if case.current_status in ACTIVE_STATUSES)


def reserved_cases() -> tuple[L2Case, ...]:
    """Rows that must NOT run today."""
    return tuple(case for case in CASES if case.current_status in RESERVED_STATUSES)


def cases_by_status(status: str) -> tuple[L2Case, ...]:
    return tuple(case for case in CASES if case.current_status == status)
