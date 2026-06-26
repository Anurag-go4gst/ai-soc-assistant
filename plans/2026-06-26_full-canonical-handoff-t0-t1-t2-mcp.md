---
name: Full canonical handoff for T0/T1/T2 and MCP-live readiness
overview: "Report-first plan to preserve the shipped /chat architecture while strengthening row authority, Environment KB normalization, EvidencePlan, ResourcePlan, MCP seam, and weak-known promotion/demotion across T0/T1/T2."
status: proposed
dependencies:
  - plans/2026-06-24_run-contract-canonical-state.md
  - plans/2026-06-25_final-evidence-gate-cross-stream.md
  - plans/2026-06-25_spl-query-fidelity-completion.md
  - plans/2026-06-15_0821_wazuh-mcp-adoption-and-flagship-ec-scenario.md
todos:
  - id: phase1-row-authority-report
    content: Add row authority classifier in report/trace mode, extending existing 105/catalogue metadata without runtime behavior change
    status: completed
  - id: phase2-env-kb-binding-into-plan-inputs
    content: Feed Environment KB/source-profile and row metadata into existing canonical bindings/provisional plan inputs without recreating UserConstraintBindings
    status: pending
  - id: phase3-evidence-plan-enrichment
    content: Enrich EvidencePlan with row authority and dependency summaries while avoiding duplicate finalize-only render permissions
    status: pending
  - id: phase4-resource-plan-consumption
    content: Wire execution/evidence consumers to read existing ResourcePlan steps in parity with EvidencePlan booleans
    status: pending
  - id: phase5-provisional-adjudication-enrichment
    content: Enrich route adjudication's provisional EvidencePlan inputs and add drift tracing against final EvidencePlan
    status: pending
  - id: phase6-loop-extension
    content: Extend the existing evidence_loop assessor for weak-known dependency gaps and RunContract parity
    status: pending
  - id: phase7-mcp-seam
    content: Prove MCP off/mock/live uses the same ResourcePlan MCP step through existing gates and envelopes
    status: pending
  - id: phase8-answer-pack-unification
    content: Define reviewed answer packs as an export/unification of content_enrichment/runtime-map/golden data, not a fourth parallel store
    status: pending
  - id: phase9-promotion-demotion
    content: Add auditable weak-known promotion/demotion lifecycle gated by review and golden tests
    status: pending
  - id: phase10-evals
    content: Run targeted and governance eval gates without committing accidental baseline drift
    status: pending
  - id: followup-mcp-allowed-none-normalization
    content: Normalize nullable MCP allowance into explicit blocked/allowed gate state before ResourcePlan or execution consumers
    status: completed
  - id: followup-containment-banner
    content: Render containment/action-blocked banner from canonical blocked action state, not a parallel UI-only condition
    status: completed
isProject: false
---

# Full Canonical Handoff for T0/T1/T2 and MCP-Live Readiness

## Status

Proposed for review before implementation.

Implementation progress / reality check:

- Phase 1 has both report artifacts and runtime row-authority projection. It is no longer strictly report-only; runtime behavior must remain flag-gated where it can affect routing.
- Phase 2/3 are partial. EvidencePlan carries optional `row_authority_summary`, `normalized_slot_summary`, and `source_profile_binding_summary`, but several plan-named end-to-end assertions are still missing.
- Phase 4/7 are partial. ResourcePlan composition emits MCP steps, and skill-contract vetoes are represented; MCP-off live-investigation steps must be blocked on the same MCP step rather than omitted or route-replaced.
- Phase 5 is partial. Drift tracing exists, and row-authority advisory trace now makes weak exact-105 rows visible without changing route authority. Runtime enforcement / promotion must remain a later flag-gated step; route adjudication must not permanently rely on raw exact-105 allowlists alone.
- Phase 6 is partial. Dependency-gap projection helpers exist, but loop coverage is mostly focused/unit level rather than broad end-to-end loop tests.
- Phase 8 is not complete. Reviewed answer-pack projection is skeletal; there is no populated `answer_packs.json`, so the loader is empty unless tests monkeypatch data.
- Phase 9 is trace-only. Promotion lifecycle summaries are visible, but `can_skip_llm_for_t0` is not wired into runtime synthesis/LLM scheduling authority.
- Phase 10 has been revalidated manually in this session because the wrapper can stall in this environment. Backend pytest and downstream gates passed, but generated eval report drift remains uncommitted in the worktree.
- The nullable `mcp_allowed` follow-up is implemented for execution-gate, evidence-loop, and RunContract consumers; `mcp_allowed_normalized` records fail-closed trace provenance.
- The containment banner follow-up is implemented in API + frontend from canonical blocked-action state.

## Objective

Preserve and strengthen the shipped `/chat` graph architecture for all known and unknown SOC questions:

```text
query
  -> intent
  -> route_resolution (adjudication with provisional intent-only EvidencePlan)
  -> route_contract (canonical skill seed)
  -> evidence_planning (final EvidencePlan + ResourcePlan)
  -> discovery_loop / SPL / execution
  -> context_finalize (FinalEvidenceGate -> RunContract -> governed answer)
```

This plan must not create a parallel weak-case architecture. T0, T1, and T2 all use the same canonical handoff. The difference between tiers is authority/readiness and whether LLM enrichment is allowed, not a separate runtime path.

The plan also ensures MCP can be enabled later without breaking the graph. When MCP becomes live, execution should consume the same canonical resource/evidence contract rather than requiring a second wiring pass.

## Non-Negotiable Boundaries

- No parallel answer engine for weak T0, T1, or T2.
- No raw LLM output as runtime authority.
- No LLM override of user-explicit, COE/manual, Environment KB, source-profile, or safety-gate fields.
- No candidate SPL execution.
- No live-result claim without MCP execution evidence.
- No severity or confirmed MITRE status from draft SPL, catalogue metadata, Environment KB, or LLM alone.
- MCP execution remains globally and per-server gated until explicitly enabled.
- LLMs never call MCP directly.
- ResourcePlan is a projection/handoff from EvidencePlan, not an independent router.

## Current Repo-State Assessment

The existing architecture is directionally correct.

EvidencePlan is already a real control-plane lever:

- `app/chat/evidence_planner.py` sets `answer_mode`, `needs_*`, `spl_allowed`, `mcp_allowed`, required evidence, limitations, checklist, and resource plan.
- `app/routing/route_adjudication.py` uses EvidencePlan to choose knowledge-only versus live/hybrid route behavior.
- `app/chat/run_contract_builder.py`, `app/chat/final_answer_validator.py`, and `app/chat/analyst_response_builder.py` consume EvidencePlan decisions.
- `app/planner/composer.py` composes ResourcePlan from EvidencePlan and adds ordered steps, resource IDs, policy checks, fallbacks, and planned discovery decisions.

The weak areas are handoff discipline and input richness:

- Exact 105 match is still sometimes treated as strong T0 even when source/template/lookup/context bindings are thin.
- Weak exact rows can lose known row identity if treated like generic T2.
- EvidencePlan is often derived from broad `intent_family`, then enriched, instead of from a fully normalized canonical binding.
- ResourcePlan is composed and traced, but execution still commonly reads older booleans/workflow fields rather than treating ResourcePlan steps as the explicit execution handoff.
- Environment KB/source-profile details must be inserted before EvidencePlan is finalized and must flow into downstream nodes.

## Already Shipped: Do Not Recreate

| Existing work | Keep / extend here |
|---|---|
| `plans/2026-06-24_run-contract-canonical-state.md` | RouteContract order, RunContract authority holder, no legacy `routed.skill` authority reads |
| `plans/2026-06-25_final-evidence-gate-cross-stream.md` | Finalize-only render permissions and cross-stream evidence/claim gates |
| `plans/2026-06-25_spl-query-fidelity-completion.md` | UserConstraintBindings, slot precedence, validator-gated LLM slots, source-profile substitution |
| `app/planner/composer.py` | Existing EvidencePlan -> ResourcePlan composer and parity assumptions |
| `app/chat/evidence_loop.py` | Existing bounded evidence loop / cyclic hub |
| `app/use_cases/content_enrichment.py` + catalogue enrichment files | Input to reviewed answer-pack unification, not a store to bypass |
| `app/connectors/mcp/splunk_mcp.py` + MCP gate/envelope tests | Existing MCP transport/gate path; Phase 7 proves the seam rather than rebuilding MCP |

## Review Notes: Bugs, Divergence Risks, and Corrections

This plan is an extension of the existing architecture, not a replacement for it. It must be reviewed against the completed RunContract canonical-state work in `plans/2026-06-24_run-contract-canonical-state.md`.

### Critical Correction: Shipped Pipeline Order Is Authoritative

The conceptual flow remains:

```text
query -> intent -> evidence plan -> route -> execution -> loop or synthesis
```

The shipped implementation resolves a practical ordering issue discovered in RunContract work: route adjudication runs before final evidence planning using a provisional, intent-only EvidencePlan so final evidence planning receives a canonical skill and does not freeze stale `needs_mcp` / HIL decisions.

Authoritative node order:

```text
query
  -> query_to_intent
  -> route_resolution (adjudication + provisional EvidencePlan)
  -> route_contract (RouteContract)
  -> evidence_planning (final EvidencePlan + ResourcePlan)
  -> discovery_loop / workflow_spl / execution
  -> context_finalize (FinalEvidenceGate -> RunContract)
```

Meaning:

- EvidencePlan remains the primary decision object for resource needs.
- RouteContract prevents stale legacy route fields from leaking forward.
- Phase 5 enriches the provisional adjudication inputs and adds drift checks against final EvidencePlan; it does not move final EvidencePlan before route resolution.
- No implementation should create a second "weak T0 route" outside this graph.

### Potential Bug: ResourcePlan as Independent Authority

ResourcePlan must not become a second planner. It is a typed projection and execution handoff from EvidencePlan.

Correct:

```text
EvidencePlan -> ResourcePlan -> execution step consumption
```

Incorrect:

```text
ResourcePlan reclassifies intent, changes route, or overrides EvidencePlan booleans
```

### Potential Bug: Environment KB Treated as Evidence

Environment KB/source profiles may bind sources, fields, lookups, CIDRs, zones, and defaults. They do not prove that an event occurred.

Correct:

- Environment KB can fill `source_profile`, `index`, `sourcetype`, fields, lookup names, zones, and constraints.
- It can satisfy "can we construct a query?" prerequisites.
- It cannot satisfy "did this happen?" evidence requirements.

### Potential Bug: Weak Exact Rows Lose Known-Row Identity

Weak exact rows must not be sent to generic T2 as if the registry missed. They keep their `question_ref`, pattern, dependency, and MITRE/source metadata.

### Potential Bug: MCP-Live Requires A New Path Later

MCP-live must be a gate flip on the existing ResourcePlan MCP step, not a new route path. The same query should show:

```text
MCP off       -> planned / blocked lineage
mock MCP on   -> same MCP step executes with mock envelope
real MCP on   -> same MCP step executes after real gates and approval
```

### Potential Bug: Answer Packs Become A Parallel Answer Engine

Offline LLM answer packs enrich EvidencePlan only. They never bypass intent, route, ResourcePlan, RunContract, FinalEvidenceGate, or governed synthesis.

### Control Plane Flag Split

Baseline definition (avoid ambiguity): production default is `CONTROL_PLANE_ENABLED=false`, but the pytest/governance harness runs with `SAFE_ENV_DEFAULTS["CONTROL_PLANE_ENABLED"]="true"`. "Governance regression passes in both modes" therefore means: (a) the existing harness (CP-on) stays green, and (b) a targeted CP-off run of the baseline-sensitive suites stays green. State which mode each new test asserts in.

Many pieces in this plan are `CONTROL_PLANE_ENABLED=true` behavior. CP-off must remain baseline-compatible:

- CP-off may expose report/trace artifacts only when already safe.
- CP-on owns row authority enrichment, final EvidencePlan enrichment, evidence loop, and MCP seam tests.
- Governance regression must pass in both baseline and CP-on targeted modes where applicable.

## Tier Semantics

### Vocabulary Mapping

The repo already uses T0/T1/T2 in multiple contexts. To avoid implementation drift, this plan's new terms are row authority statuses, not replacements for existing `registry_tier`, SPL shape tier, or skip reasons.

| Term | Owner | Meaning |
|---|---|---|
| `row_authority_status` | this plan | Whether a known row is authority-ready, weak-known, unsupported, etc. |
| `registry_tier` / `t0_exact_authority` | `catalog.json` / `routing_authority.py` | Catalogue row skip/advisory authority metadata |
| `intent_advisor_skip_reason` | query-to-intent sidecar | Whether intent sidecar ran or skipped |
| `composer_weak_case` | synthesis/composer | Narration eligibility only; not a route tier |
| `T2 shape` | SPL fidelity modules | SPL-native shape extraction/repair, not a row authority class |
| T2 guided/out-of-registry | plans/evals | Out-of-registry or not-yet-promoted review-only enrichment |

### Authority-Ready Known Rows

Authority-ready known rows are the only rows that may skip enrichment end-to-end.

```text
authority_ready = known row + reviewed/authority-ready operation + required bindings present + governance checks pass
```

This maps to T0-style behavior only after tests prove readiness.

### Weak Known Rows

Weak exact rows are not out-of-registry. They are known rows that are not authority-ready.

Use a status such as:

```text
exact_known_weak_needs_enrichment
```

These rows still preserve:

- `question_ref`
- `mapped_pattern_type`
- `use_case_id` or catalogue relation
- `dependency_class`
- `promotion_status`
- `manifest_coverage_id`
- MITRE registry metadata
- source/profile hints
- normalized slots

They may run T2-like enrichment, but through the same canonical path.

### T1

T1 includes catalogue/native workflows such as SPL-native meta tasks. T1 is advisory-eligible unless a row explicitly opts into T0 authority.

### T2

T2 remains out-of-registry or not-yet-promoted semantic coverage. It still uses the same graph:

```text
query -> intent -> evidence_plan -> route -> execution/evidence -> loop or synthesize
```

## Canonical Handoff Contract

Every tier must pass one canonical state forward:

```text
QueryUnderstanding
  + IntentClassification
  + UserConstraintBindings / normalized slots
  + Environment KB fills
  + selected known-case/catalogue metadata
  + EvidencePlan
  + ResourcePlan
  + FinalEvidenceGate / RunContract at finalize
```

Downstream nodes should not re-derive authority from raw query keywords, raw LLM prose, or trace-only planning metadata.

Finalize-only gate rule:

- Upstream handoff ends at EvidencePlan + ResourcePlan.
- FinalEvidenceGate is computed in `context_finalize`; it is not an upstream planner input.
- RunContract projects gate permissions for render/HIL/evidence trust.
- EvidencePlan must not grow parallel `allow_*` render fields that compete with FinalEvidenceGate.

## Authority Precedence

```text
user explicit
> COE/manual catalog and Environment KB
> deterministic extractors
> reviewed known-case answer pack
> live LLM advisory
> template defaults
```

Rules:

- Lower-precedence values may fill blanks only.
- Conflicts must be recorded.
- LLM values must be dropped or downgraded when they conflict with higher authority.
- Environment KB is configuration/context, not live telemetry evidence.

## Phase 1: Row Authority Classifier

Add a deterministic classifier for known rows in report/trace mode. Extend or map onto existing runtime-map readiness fields such as `s3_authority_ready`; do not introduce a disconnected authority column without a migration story.

Inputs:

- exact/near/semantic match path
- `question_ref`
- `use_case_id`
- `dependency_class`
- `promotion_status`
- `manifest_coverage_id`
- `manifest_readiness` (confirm this field still exists before use — currently thin, 1 file; if it is not a live signal, derive readiness from `manifest_coverage_id` + `promotion_status` instead and drop this input)
- `route_blocked`
- `default_spl_template`
- source-profile availability
- lookup/detection/context dependency status
- reviewed answer-pack status

Outputs (`row_authority_status` enum) and their mapping to the existing boolean `s3_authority_ready` (the classifier derives the enum; `s3_authority_ready` is projected from it — one direction only, no disconnected column):

| `row_authority_status` | `s3_authority_ready` | May skip LLM? | Reason |
|---|:---:|:---:|---|
| `exact_known_authority_ready` | true | yes | known + reviewed op + bindings + gov pass |
| `catalog_authority_ready` | true | yes | catalogue row opted into T0 authority |
| `exact_known_weak_needs_enrichment` | false | no | exact match but thin bindings |
| `catalog_weak_needs_enrichment` | false | no | catalogue row not authority-ready |
| `exact_known_needs_lookup` | false | no | lookup dependency unmet |
| `exact_known_needs_detection_binding` | false | no | detection binding unmet |
| `exact_known_needs_context_binding` | false | no | asset/identity context unmet |
| `exact_known_needs_clarification` | false | no | HIL clarification baseline |
| `exact_known_unsupported` | false | no | `route_blocked` / no safe answer shape |
| `out_of_registry_t2` | false | no | semantic / not-yet-promoted |

`s3_authority_ready` stays the single readiness boolean consumers already read; the enum adds the *reason*. No second authority column is introduced.

Acceptance:

- Report identifies exact weak rows that should not be considered authority-ready solely because they are exact.
- Exact authority-ready rows can still skip LLM.
- Unsupported rows remain honest and do not get generic invented guidance.
- Status is visible in trace/report and can be passed into EvidencePlan in later phases.
- No intent-advisor skip behavior changes in this report-only phase.
- Report artifact is written to a fixed, non-baseline path (e.g. `docs/evals/row_authority_report.{md,json}`) so Phase 10 can treat it as a tracked artifact and reject accidental golden/eval drift.

Tests:

- `test_row_authority_classifier_exact_manifest_ready_is_t0`
- `test_row_authority_classifier_exact_not_in_manifest_is_weak_known`
- `test_row_authority_classifier_lookup_dependency_is_not_authority_ready`
- `test_row_authority_classifier_route_blocked_is_unsupported`
- `test_row_authority_report_maps_q046_to_exact_known_weak_needs_enrichment`
- `test_row_authority_report_marks_q028_unsupported`

Test names use exact enum values from the table above — no free-text status strings.

Phase exit gate:

- Report lists every 105 row and catalogue row by authority status.
- Report cross-checks known special cases: 4 no-SPL rows (`q0.q045`, `q0.q103`, `q0.q104`, `q0.q105`), unsupported `q0.q028`, and the 10 manifest-promoted rows. `q0.q045` is the clarification baseline and resolves to a single status `exact_known_needs_clarification` (no-SPL is a consequence of that status, not a competing classification — one row, one status).
- No runtime behavior change yet, except optional trace-only status exposure.
- Existing T1/T2 SPL-native tests still pass.

## Phase 2: Canonical Normalization Before EvidencePlan

Feed Environment KB/source-profile and row metadata into existing canonical bindings and provisional plan inputs. Do not recreate UserConstraintBindings or SPL fidelity work already completed in `2026-06-25_spl-query-fidelity-completion.md`.

Required canonical fields:

- indexes / sourcetypes
- source profile
- event codes
- users / hosts / assets
- src/dest IPs
- src/dest zones
- ports/services/actions
- time window
- lookups
- thresholds
- aggregation subject
- MITRE/CVE/CVC entities
- source availability and source health

Before implementing, split this field list into two columns and put it in the phase PR description: **already in `UserConstraintBindings` / normalized slots** (from `2026-06-25_spl-query-fidelity-completion.md` — do not recreate: indexes, sourcetypes, users, hosts, src/dest IPs, ports/services, time window, thresholds) versus **genuinely new handoff additions** (source-profile binding provenance, lookups, zones, aggregation subject, MITRE/CVE entities, source health). Only the new column is in scope here. Recreating an existing binding field is a review-reject.

Environment KB/source-profile fills must occur before live LLM advisory values are merged. Scope this phase to missing handoff pieces:

- row-authority-aware binding
- Environment KB -> EvidencePlan / provisional plan input
- weak-exact identity preservation
- source/profile fill provenance

Acceptance:

- Weak exact rows keep known row identity and normalized slots.
- Environment KB fields flow into EvidencePlan, ResourcePlan, SPL generation, and final answer lineage.
- LLM fills blanks only.

Tests:

- `test_canonical_binding_preserves_question_ref_for_weak_exact`
- `test_environment_kb_fills_source_profile_before_llm_slots`
- `test_llm_slot_cannot_override_environment_kb_index`
- `test_user_explicit_index_beats_environment_kb_and_llm`
- `test_normalized_slots_include_lookup_zone_and_time_window`

Phase exit gate:

- Canonical binding object is visible in debug/trace for selected probes.
- EvidencePlan can be built from canonical bindings without re-reading raw LLM slots.
- No downstream SPL path depends directly on raw `entity_slots_candidate` when bindings exist.
- Environment KB plan/addendum rules are honored: COE/manual values win; RAG/session/MCP may fill blanks only.

## Phase 3: EvidencePlan as Primary Decision Object

Extend EvidencePlan, using existing model conventions, so it carries:

- known-row authority status
- normalized slot summary
- source/profile binding summary
- required evidence keys
- missing evidence keys
- lookup/detection/context dependency status
- answer shape
- resource needs
- `needs_rag`
- `needs_spl`
- `needs_mcp`
- `needs_mitre`
- `needs_lookup`
- `needs_detection_binding`
- `spl_allowed`
- `mcp_allowed`

EvidencePlan remains the authority for route and execution planning.

Do not add finalize-only render permissions here. Live-result language, results-table, severity visibility, and MITRE visibility remain FinalEvidenceGate/RunContract authority.

Acceptance:

- Route adjudication consumes EvidencePlan, not trace-only metadata.
- RunContract and FinalEvidenceGate can explain why a row loops, degrades, clarifies, or synthesizes.
- Weak known rows are distinguishable from generic T2.

Tests:

- `test_evidence_plan_carries_known_weak_status`
- `test_evidence_plan_carries_source_profile_binding_summary`
- `test_evidence_plan_marks_lookup_dependency_missing`
- `test_evidence_plan_marks_detection_binding_missing`
- `test_evidence_plan_needs_mcp_only_when_live_evidence_required`
- `test_evidence_plan_environment_kb_is_not_collected_telemetry`

Phase exit gate:

- EvidencePlan includes the authority status and binding summaries for T0/T1/T2 probes.
- Route adjudication tests prove EvidencePlan changes route outcomes when it should.
- RunContract/FinalEvidenceGate test fixtures still agree with EvidencePlan decisions.

## Phase 4: Wire Existing ResourcePlan Into Execution Handoff

ResourcePlan remains derived from EvidencePlan:

```text
EvidencePlan -> ResourcePlan
```

ResourcePlan must not independently classify the query or override EvidencePlan.

The composer already exists. This phase wires execution/evidence consumers to treat ResourcePlan steps as the explicit handoff, while maintaining parity with existing booleans during migration:

- RAG step: approved corpus and no-match behavior.
- SPL step: governed template, lab draft family, or LLM candidate path.
- MCP step: gated execution resource, required SPL validation, required approvals.
- MITRE step: evidence preconditions and visibility policy.
- Narration step: governed synthesis/fallback policy.

Acceptance:

- `project_booleans(ResourcePlan)` stays consistent with EvidencePlan needs.
- Execution can consume ResourcePlan step IDs and resource IDs.
- Existing booleans stay during transition but tests assert parity with ResourcePlan.
- ResourcePlan provenance records resource decisions, fallbacks, and blocked reasons.

Tests:

- `test_resource_plan_project_booleans_matches_evidence_plan`
- `test_resource_plan_spl_step_uses_governed_template_when_available`
- `test_resource_plan_spl_step_degrades_to_lab_family_when_template_unavailable`
- `test_resource_plan_mcp_step_requires_approved_normalized_spl`
- `test_resource_plan_skill_contract_vetoes_blocked_mcp`
- `test_resource_plan_does_not_change_intent_or_route`

Phase exit gate:

- ResourcePlan parity tests pass for one T0 authority-ready row, one weak exact row, one T1 SPL-native row, and one T2 out-of-registry row.
- Execution code may still read legacy booleans, but a test proves ResourcePlan and booleans cannot drift for covered probes.

## Phase 5: Route Uses Intent + EvidencePlan

Route adjudication already runs before final EvidencePlan. This phase enriches the provisional adjudication inputs and adds drift checking after final EvidencePlan.

Adjudication authority should be based on:

```text
IntentClassification + provisional EvidencePlan + QueryUnderstanding + row_authority_status + canonical bindings summary
```

It should not use raw LLM text or loose keyword routing as authority.

Acceptance:

- Weak exact rows route according to provisional EvidencePlan and row-authority status.
- RAG-only EvidencePlan forces knowledge route.
- Hybrid/live EvidencePlan forces investigation/SPL route as appropriate.
- Exact authority-ready rows preserve exact registry route.
- If final EvidencePlan disagrees with route adjudication, record a drift record. "Fail closed" here means: **keep the already-selected route, drop only the unsupported capability** (e.g. final plan says `mcp_allowed=false` after route picked a live route → route stays, MCP step is marked blocked, answer degrades to honest no-live-evidence). It does **not** mean re-running route resolution or re-coupling final-plan→route — that would undo the RunContract ordering fix. The route is never silently switched; the capability is narrowed and the drift is traced.

Drift handling is capability-narrowing, not route-replacement:

```text
route_authority stays           (RouteContract is canonical)
disagreeing capability blocked  (e.g. needs_mcp/spl_allowed downgraded)
drift_record traced             (route_authority_compare / control_plane_trace)
answer degrades honestly        (no live language for the dropped capability)
```

Tests:

- `test_route_adjudication_exact_authority_ready_preserves_registry_route`
- `test_route_adjudication_weak_exact_uses_evidence_plan_live_or_hybrid`
- `test_route_adjudication_rag_only_blocks_spl_and_mcp`
- `test_route_adjudication_policy_intent_overrides_exact_analytics`
- `test_route_adjudication_ignores_raw_llm_route_when_evidence_plan_blocks`
- `test_final_evidence_plan_route_drift_is_recorded`
- `test_final_evidence_plan_drift_narrows_capability_keeps_route`

Phase exit gate:

- Route decisions are explainable from IntentClassification + provisional EvidencePlan + QueryUnderstanding + row authority.
- No user-visible route surface reads legacy `routed.skill` as authority after RunContract exists.

## Phase 6: Execution and Evidence Loop

Extend the existing `app/chat/evidence_loop.py` and execution path. Do not rebuild the cyclic hub.

Execution consumes ResourcePlan-compatible state and produces evidence or missing-evidence state.

Loop decision:

```text
if required evidence missing:
    return to evidence planning with missing_evidence
elif unsafe or unsupported:
    clarify or degrade honestly
else:
    synthesize governed answer
```

Acceptance:

- Missing source profile, lookup, detection binding, or MCP unavailable status returns structured missing evidence.
- Final answer never pretends missing evidence was collected.
- Loop/degrade/synthesis decision is visible in trace.

Tests:

- `test_evidence_loop_missing_lookup_returns_to_evidence_plan`
- `test_evidence_loop_missing_source_profile_requests_clarification`
- `test_evidence_loop_unsupported_dependency_degrades_honestly`
- `test_evidence_loop_terminates_within_bound`
- `test_final_answer_no_live_language_without_collected_evidence`
- `test_run_contract_loop_decision_matches_evidence_loop_decision`

Phase exit gate:

- Loop decisions are bounded and visible in control-plane trace.
- RunContract and FinalEvidenceGate agree on collected evidence count, allowed live language, MITRE visibility, and severity visibility.

## Phase 7: MCP-Live Seam

The MCP-live future must be seamless because ResourcePlan already names MCP needs and policy checks. This extends existing MCP gate/transport/envelope code; it does not create a new MCP framework.

Precondition for a seamless seam: the composer must emit the MCP `PlanStep` **whenever the EvidencePlan needs live evidence**, even when MCP is off — present-but-blocked, carrying a `blocked_reason`, not absent. "Same step executes" only holds if the step exists in all three postures. If the composer currently omits the MCP step when `mcp_allowed=false`, add the blocked step first (a Phase 4 parity addition), then prove the seam here.

Before MCP live:

- MCP step is planned and present with `blocked_reason` (not omitted).
- MCP execution remains blocked by global/per-server flags.
- Final answer says planned or unavailable, not live.

When MCP live is enabled:

- The same ResourcePlan MCP step is consumed.
- Execution gate checks global flag, server flag, RBAC/session, approved normalized SPL, tool allowlist, and HIL approval where required.
- Results return as SourceEvidence / governed execution envelope.
- EvidencePlan is updated with collected evidence or missing/empty result status.
- Graph decides loop-back or synthesis.

MCP live must not require:

- a new route path
- LLM tool calling
- bypassing SPL validation
- bypassing ResourcePlan
- new answer renderer semantics

Acceptance:

- With MCP off, same query produces planned/blocked execution lineage.
- With mock MCP on, same ResourcePlan step executes through the gate.
- With real MCP on later, same step can execute after validation/approval.
- Empty results can trigger bounded broaden/loop logic without fabricating findings.
- MCP results are never treated as raw LLM input; they enter as SourceEvidence / execution envelope.

Tests:

- `test_composer_emits_blocked_mcp_step_when_off_and_live_evidence_needed`
- `test_mcp_off_preserves_planned_resource_step_and_block_reason`
- `test_mock_mcp_executes_same_resource_plan_step`
- `test_mcp_gate_rejects_without_approved_normalized_spl`
- `test_mcp_gate_rejects_when_global_flag_disabled`
- `test_mcp_gate_rejects_disallowed_tool_even_if_llm_suggests_it`
- `test_mcp_result_enters_source_evidence_not_llm_context`
- `test_empty_mcp_result_triggers_bounded_broaden_or_honest_empty_state`

Phase exit gate:

- MCP off/mock tests prove no route-path fork.
- Real MCP remains default-off.
- No LLM tool-calling flag is required or enabled.

## Phase 8: Offline LLM Answer Packs Feed EvidencePlan Only

Offline LLM output can enrich thin catalogues, but not become a parallel runtime answer engine.

An "answer pack" is not a fourth independent store by default. It should be a reviewed export/unification of:

- runtime map row metadata
- `content_enrichment` / curated enrichment records
- MITRE/CVE/CVC enrichment drafts
- golden answer expectations
- LLM audit output and provenance

Known-case answer pack fields:

- case ID (`q0.qNNN`, `cisco.*`, `uc:*`)
- answer shape
- required evidence
- source needs
- source/profile hints
- lookup/detection/context dependency
- MITRE candidates and preconditions
- CVE/CVC context
- caveats / must-not-claim items
- SPL family/template suggestion
- provenance and review status

Runtime use:

```text
reviewed answer pack -> EvidencePlan enrichment -> ResourcePlan -> route/execution/synthesis
```

Acceptance:

- Raw LLM prose is not consumed as authority.
- Only reviewed/normalized packs can affect runtime.
- Packs fill blanks below Environment KB and deterministic sources.
- Promotion to T0 requires pack review plus golden tests.

Tests:

- `test_answer_pack_raw_status_not_loaded_at_runtime`
- `test_answer_pack_reviewed_status_enriches_evidence_plan`
- `test_answer_pack_cannot_override_environment_kb`
- `test_answer_pack_mitre_candidate_stays_candidate_without_evidence`
- `test_answer_pack_spl_family_suggestion_requires_template_or_validator`

Phase exit gate:

- Offline builder emits packs and audit report only.
- Runtime loader accepts reviewed packs only.
- Golden rows exist for any pack promoted into runtime.

## Phase 9: Promotion and Demotion Lifecycle

### Where Lifecycle State Lives (resolves the Phase 8 "no new store" tension)

Phase 8 forbids a fourth *answer* store; it does not forbid a *status* ledger. Keep them separate:

- **Authority of record** for `promotion_status` stays the existing reviewed source — the catalogue / runtime-map row metadata (`promotion_status`, `manifest_coverage_id`). Promotion/demotion edits that existing field; it does not create a parallel answer store.
- The answer-pack export (Phase 8) is **derived/read-only** — it reflects `promotion_status`, never owns it. No circular write: classifier reads status → enriches plan; lifecycle writes status → in the catalogue/runtime-map; export re-projects.
- Demotion at runtime is **non-destructive**: it sets an in-trace `effective_promotion_status` (e.g. `demoted_this_turn` + reason) for the current turn without rewriting the stored catalogue value. Persistent demotion of the stored value requires the same review path as promotion.

```text
catalogue / runtime-map row.promotion_status   = authority of record (reviewed writes only)
runtime classifier                             = reads it, never writes it
answer-pack export (Phase 8)                   = derived projection, read-only
runtime demotion                               = per-turn effective_promotion_status in trace, non-destructive
```

Weak known row lifecycle:

```text
exact_known_weak_needs_enrichment
  -> offline/live advisory collection
  -> normalization
  -> validation
  -> COE review
  -> golden tests
  -> exact_known_authority_ready
```

Demotion triggers:

- missing source profile
- missing template or invalid template
- lookup/detection/context dependency unavailable
- failed golden answer
- MITRE/CVE/CVC validation conflict
- environment mapping drift
- MCP execution evidence required but unavailable

Acceptance:

- Promotion/demotion status is data-driven and auditable.
- No plan frontmatter/todos are marked complete until tests pass.

Tests:

- `test_promotion_requires_reviewed_pack_and_passing_golden`
- `test_demotion_on_environment_mapping_drift`
- `test_demotion_on_failed_golden`
- `test_demotion_on_mitre_validation_conflict`
- `test_t0_promoted_row_skips_llm_only_after_authority_ready`
- `test_runtime_demotion_is_non_destructive_to_stored_promotion_status`

Phase exit gate:

- Promotion report is deterministic and reproducible.
- Demotion reasons are visible in row authority report and trace.

## Phase 10: Test and Eval Gates

Targeted tests:

- weak exact row does not hard-skip LLM solely due to exact match
- weak exact row preserves `question_ref`, pattern type, use case, dependency class
- Environment KB fills canonical bindings before LLM values
- EvidencePlan carries source/profile bindings and missing evidence
- ResourcePlan steps match EvidencePlan needs
- route adjudication uses EvidencePlan decisions
- execution reads ResourcePlan-compatible state
- MCP off/on-mock paths share the same ResourcePlan step
- final answer lineage distinguishes planned, unavailable, mock executed, and real executed

Eval gates:

- affected backend pytest
- out-of-set intent probe when intent/routing changes
- out-of-catalog OT probe when T2/guided behavior changes
- governance regression before claiming control-plane work done
- frontend build if UI trace/lineage changes

## Phase Transition Flow

Each phase must satisfy three gates before the next phase starts:

1. **Contract gate:** the phase's new data is present in the canonical state and does not duplicate an existing authority object.
2. **Consumer gate:** at least one downstream consumer reads the canonical field in test or trace, or the phase is explicitly report-only.
3. **Regression gate:** targeted tests pass, and existing governance-sensitive tests do not regress.

Recommended sequence:

```text
Phase 1 report-only classifier
  -> Phase 2 Environment KB + row metadata into existing canonical bindings/provisional inputs
  -> Phase 3 EvidencePlan enrichment
  -> Phase 4 execution consumes existing ResourcePlan-compatible state
  -> Phase 5 enrich provisional adjudication inputs + drift trace
  -> Phase 6 extend existing evidence loop
  -> Phase 7 MCP off/mock seam
  -> Phase 8 reviewed answer-pack unification
  -> Phase 9 promotion/demotion lifecycle
  -> Phase 10 full eval/gov gate
```

Do not skip from Phase 1 directly to runtime demotion/promotion. Weak-known demotion is safe only after Phase 2 proves canonical normalization and Environment KB fill are preserved.

## Completion Matrix

| Phase | Runtime behavior change allowed? | Primary artifact | Required proof |
|---|---:|---|---|
| 1 | No, trace/report only | row authority report | exact rows classified without route changes |
| 2 | Limited trace/binding only | existing canonical binding + provisional inputs | Environment KB precedes LLM and preserves known-row identity |
| 3 | Yes, EvidencePlan enrichment | EvidencePlan fields | route/run/final gates can explain decisions from EvidencePlan |
| 4 | Limited, parity first | existing ResourcePlan | execution can consume ResourcePlan safely |
| 5 | Yes, route decisions | RouteAdjudication provisional inputs | route uses enriched provisional plan and records final-plan drift |
| 6 | Yes, loop/degrade decisions | execution/evidence loop | bounded loop or honest synthesis/degrade |
| 7 | Mock only by default | MCP seam | off/mock share same ResourcePlan step |
| 8 | Reviewed packs only | answer-pack export/unification | packs enrich EvidencePlan, never bypass graph |
| 9 | Yes, gated promotion | promotion report | T0 promotion requires reviewed pack + golden pass |
| 10 | No feature change | regression reports | governance and targeted evals pass |

## Flag-Split Eval Matrix

| Gate | CP off | CP on |
|---|:---:|:---:|
| Row authority report | yes | yes |
| Existing governance regression | yes | yes |
| Route uses enriched provisional plan | no | yes |
| EvidencePlan/ResourcePlan parity | trace only | yes |
| Evidence loop / MCP seam | no | yes |
| RunContract / FinalEvidenceGate parity | yes | yes |
| Frontend build, if lineage/debug UI changes | yes | yes |

Additional phase-specific evals:

- `scripts/eval_105_path_honoring.py` for 105 path preservation.
- SPL query fidelity tests / A-H probes when binding or SPL handoff changes.
- `scripts/eval_out_of_set_intent_probe.py --check` when intent/adjudication changes.
- `scripts/eval_out_of_catalog_ot_probe.py --check` when guided/T2 behavior changes.
- Row authority report as a new non-baseline artifact; do not commit accidental golden/eval drift.

## Anti-Patterns To Reject In Review

- Adding a new weak-case endpoint or renderer outside `/chat`.
- Letting answer packs return final prose directly.
- Letting ResourcePlan override EvidencePlan.
- Letting MCP execution infer SPL from query text instead of approved normalized SPL.
- Letting LLM-suggested tools populate selected MCP tools.
- Treating Environment KB/source profiles as collected telemetry.
- Marking exact 105 as T0-ready without source/template/lookup/context readiness.
- Moving to the next phase with only trace assertions when a downstream consumer is supposed to use the new contract.

## Tracked Code Follow-Ups From Review

These implementation issues are not blockers for the report-only Phase 1 audit, but they must be closed before the MCP seam or containment/degrade behavior is considered complete.

### 1. Normalize `mcp_allowed=None`

Problem: nullable MCP allowance can accidentally behave differently across route, ResourcePlan, and execution-gate consumers.

Required behavior:

- Normalize `mcp_allowed=None` into an explicit gate state before MCP execution or ResourcePlan decisions.
- Fail closed for execution: unset/unknown must not allow MCP.
- Preserve trace fidelity: record whether normalized `false` came from explicit policy denial, default-off config, or unset/unknown input.
- Do not route-replace. If a selected route needs live evidence but MCP allowance normalizes false, keep the route and emit the same blocked MCP `PlanStep` described in Phase 7.

Regression test:

- `test_mcp_allowed_none_normalizes_to_blocked_gate_without_route_replace`

Acceptance:

- Final trace has an explicit normalized MCP decision.
- No consumer sees ambiguous `None` as truthy/allowed.
- Analyst-visible workflow still shows the blocked MCP evidence step when live evidence was needed.

### 2. Containment Banner Consistency

Status: implemented in API response read model + frontend banner; covered by `test_containment_banner_renders_from_canonical_blocked_action_state`.

Problem: containment or response-action asks can degrade/deny correctly in policy while failing to show a clear analyst-facing containment banner.

Required behavior:

- Unsafe or unavailable containment actions must render a consistent banner/message from canonical state, not ad hoc text.
- The banner must be driven by RunContract, FinalEvidenceGate, or ResourcePlan facts, not by a parallel UI-only condition.
- The selected route must be preserved; unsupported containment is capability-narrowed to guidance/recommendation and marked blocked, not replaced with an unrelated route.
- The banner must distinguish blocked by policy/governance, MCP disabled/unavailable, and missing required slots/evidence.

Regression test:

- `test_containment_banner_renders_from_canonical_blocked_action_state`

Acceptance:

- A containment-shaped query with execution disabled produces a blocked action state and visible containment banner.
- No candidate SPL or MCP action becomes executable because of the banner.
- The same canonical blocked state is available to both API consumers and frontend rendering.

## Worked Example: One Weak-Exact Row End-to-End (`q0.q046`)

Concrete trace so the abstract phases have one shared reference. `q046` is an exact-105 match but not authority-ready (thin bindings) — the canonical weak-known case.

```text
Phase 1  classifier  -> row_authority_status = exact_known_weak_needs_enrichment
                        s3_authority_ready = false   (does NOT skip LLM)
                        question_ref/use_case_id/dependency_class preserved (not sent to generic T2)

Phase 2  binding     -> Environment KB fills source_profile/index/sourcetype BEFORE any LLM slot
                        existing UserConstraintBindings reused; only new provenance/lookup/zone added
                        weak-exact identity kept

Phase 3  EvidencePlan -> carries known-weak status + source-profile binding summary
                        needs_spl=true, needs_mcp only if live evidence required
                        no finalize-only render permission added here

Phase 4  ResourcePlan -> composed from EvidencePlan; project_booleans == needs_*
                        SPL step = governed template or lab family; MCP step present-but-blocked if off

Phase 5  route       -> uses provisional EvidencePlan + row_authority_status (not raw LLM/keywords)
                        if final plan drifts -> keep route, narrow capability, trace drift

Phase 6  loop        -> missing lookup/source-profile -> return to evidence planning, honest missing-evidence

Phase 7  MCP seam    -> off: blocked step + planned lineage; mock: same step executes; real: same step + gates

Phase 8  answer pack -> reviewed pack enriches this row's EvidencePlan only; raw LLM prose never authority

Phase 9  lifecycle   -> stays exact_known_weak_needs_enrichment until reviewed pack + golden pass promote it;
                        runtime demotion is per-turn/non-destructive to stored promotion_status
```

## First Implementation Slice

Do not start by rewiring execution.

Recommended first PR:

1. Add row authority classifier in report/trace mode.
2. Add canonical handoff assertions for selected T0/T1/T2 probes.
3. Add ResourcePlan parity assertions against EvidencePlan.
4. Add MCP seam tests showing off/mock behavior uses the same planned step.
5. Produce a report of exact 105 rows split into authority-ready versus weak-known.

No runtime behavior change until the report and tests prove the current handoff gaps.

## Success Definition

The same canonical graph handles all tiers:

```text
T0: known + authority-ready -> deterministic path, optional no LLM
T1: known/catalog/native -> canonical path, advisory when appropriate
T2: unknown/weak -> canonical path, enrichment allowed
MCP off: planned/blocked lineage
MCP on: same ResourcePlan step executes through gates
```

No prior work is lost. Environment KB, source profiles, SPL validation, MITRE governance, ResourcePlan, RunContract, FinalEvidenceGate, and governed synthesis all remain in the single original architecture.
