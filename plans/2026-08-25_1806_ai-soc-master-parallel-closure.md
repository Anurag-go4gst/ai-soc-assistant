---
title: AI-SOC master parallel closure
created: 2026-08-25 18:06 Asia/Kolkata
status: ready_for_operator_review
ready_for_operator_review: true
canonical_plan: plans/2026-08-25_1806_ai-soc-master-parallel-closure.md
loop_runner: plans/LOOP_RUNNER_ai-soc-master-parallel-closure.md
coordination_branch: feat/complete-or-abstain-t4-ux
p0_product_baseline_sha: 615069e6ca9cdb3d40b51d6a2f071346ecf3d6a2
plan_preparation_sha: fe3548e475e61e77f5204e02f74efd28690abb86
execution_integration_sha: FROZEN_BY_OPERATOR_AT_IMPLEMENTATION_START
architecture_authority: architecture.md
architecture_policy: read_only
live_mcp: default_off_until_P11
---

# AI-SOC master parallel closure

## Objective

Close the remaining trace-truth, SPL semantic, prompt-policy, evaluation, production UX, and promotion work from the frozen P0 candidate without weakening deterministic authority or creating a second planner. Work proceeds from one declared integration SHA through isolated branches/worktrees, exclusive file ownership, focused verification, and explicit reconciliation.

This plan is executable without chat history. `architecture.md` is frozen authority. Repository code is authoritative when older prose has drifted. No phase may enable candidate SPL execution, direct LLM-to-MCP calls, live MCP, or nondeterministic policy authority.

## Verified starting state

- Repository: `/Users/aagarwal/Downloads/ai-soc-assistant-t4-architecture-20260821`
- Branch: `feat/complete-or-abstain-t4-ux`
- P0 candidate SHA (last product commit): `615069e6ca9cdb3d40b51d6a2f071346ecf3d6a2`
- `PLAN_PREPARATION_SHA`: `fe3548e475e61e77f5204e02f74efd28690abb86` (`docs(plan): add AI-SOC parallel closure loop`).
  This is historical preparation evidence, not an execution start requirement. `615069e6..fe3548e4` contains only the initial plan and
  loop runner, so P0 product behavior is unchanged.
- `EXECUTION_INTEGRATION_SHA`: `FROZEN_BY_OPERATOR_AT_IMPLEMENTATION_START`. The operator records the final reviewed plan commit after
  it exists; the plan does not embed its own future commit SHA. Every first-wave branch and loop record must use that same external SHA.
- P0 commits: `f1f523cd`, `76971f24`, `d36b8a57`, `615069e6`
- P0 result: 13 L2 `/chat` cases, MCP argument continuity/readiness contracts, bounded two-round behavior, semantic-fidelity fail-closed behavior, containment regression, mocked transport, follow-up corrections, and contradictory-evidence safety are present.
- Current suite inventory measured 2026-08-25 at `fe3548e4`: **5,313** backend test functions across **688** test files
  (`find backend -name 'test_*.py' | wc -l`; `grep -rh '^\s*def test_' backend --include='test_*.py' | wc -l`).
  Newer than the earlier audit estimate of 5,290/684; the conclusion is unchanged: rationalize conservatively through ownership and parameterization, not deletion.
- Pre-existing unrelated worktree state at plan creation: `.claude/settings.local.json` modified. Preserve it and never stage it.
- Live MCP remains OFF. Real Splunk MCP schemas remain `REAL_SCHEMA_UNVERIFIED`.
- **The RACES freeze gate is already RED at the coordination base and must not be mistaken for a regression.**
  Measured 2026-08-25 at `fe3548e4`:
  `cd backend && $PYVENV -m pytest -q app/tests/test_live_path_untouched_by_ec.py` -> `1 failed, 7 passed`.
  Failing test: `test_races_freeze_files_unchanged_since_baseline`, offender `backend/app/orchestration/mcp_execution_gate.py`,
  introduced by P0 commit `f1f523cd` against `RACES_BASELINE_SHA = 86be6f9fb3ad09adc53038e430fc94e44c1ab671`
  (`git log --oneline 86be6f9f..HEAD -- backend/app/orchestration/mcp_execution_gate.py`).
  Every stream inherits this failure. It is resolved once, by P0.1, before any phase may claim an L0 RACES gate green.

## Master operating status

Maintain this table and the loop runner together after every iteration, rebase, merge, reopening, or protected decision. `HEAD_SHA`
means the phase branch head, not the integration branch head. `NONE` means no implementation loop has started.

| PHASE | WORKSTREAM | OWNER | STATUS | BASE_SHA | HEAD_SHA | DEPENDENCIES | CURRENT_LOOP | LAST_GREEN_GATE | NEXT_ACTION | BLOCKER | MERGE_STATUS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| P0 | Historical | Historical owners | DONE | `615069e6` | `615069e6` | None | CLOSED | P0 L2 13 | Preserve | None | IN_BASE |
| P0.1 | Integration | CODEX/operator | TODO | frozen `EXECUTION_INTEGRATION_SHA` | NONE | P0 | NONE | Audit not run | Read-only proposal after approval to start audit | Operator approval required before apply | NOT_STARTED |
| P1 | A TRACE | CODEX | TODO | frozen `EXECUTION_INTEGRATION_SHA` | NONE | P0 | NONE | P0 inherited | Start after plan approval | L0 remains blocked until approved P0.1 apply lands | NOT_STARTED |
| P2 | B SPL | CURSOR | TODO | frozen `EXECUTION_INTEGRATION_SHA` | NONE | P0 | NONE | P0 inherited | Start after plan approval | None | NOT_STARTED |
| P3 | C EVAL | CLAUDE | TODO | frozen `EXECUTION_INTEGRATION_SHA` | NONE | P0 scaffold | NONE | P0 L2 13 | Start scaffold after plan approval | Contract rows wait P1/P2/P4 | NOT_STARTED |
| P4 | D POLICY | CLAUDE | TODO | P2 integration SHA | NONE | P2 for writes | NONE | P0 inherited | Read-only inventory may start | Writes blocked by P2 | NOT_STARTED |
| P5 | C/Integration | CODEX + CLAUDE | TODO | P1/P2/P4 integration SHA | NONE | P1/P2/P3/P4 | NONE | NONE | Wait | Dependencies | NOT_STARTED |
| P6 | C EVAL | CLAUDE | TODO | P5 green SHA | NONE | P5 | NONE | NONE | Wait | P5 | NOT_STARTED |
| P7 | E UI | CURSOR | TODO | P5 green SHA | NONE | P1/P2/P4/P5 | NONE | NONE | Wait | P5/protected wiring | NOT_STARTED |
| P8 | F EVAL | CODEX | TODO | P5 green SHA | NONE | P2/P4/P5 | NONE | NONE | Wait | P5/live local LLM | NOT_STARTED |
| P9 | F PROMOTION | CODEX | TODO | P6/P7/P8 candidate SHA | NONE | P6/P7/P8 | NONE | NONE | Wait | Dependencies | NOT_STARTED |
| P10 | Integration | CODEX/operator | TODO | P9 final SHA | NONE | P9 GO | NONE | NONE | Wait | Operator network approval | NOT_STARTED |
| P11 | F COE | Operator + CODEX | DEFERRED | Approved merged SHA | NONE | P10 + separate approval | NONE | NONE | Keep live MCP OFF | Separate COE authorization | NOT_STARTED |

`P0_PRODUCT_BASELINE_SHA = 615069e6ca9cdb3d40b51d6a2f071346ecf3d6a2`,
`PLAN_PREPARATION_SHA = fe3548e475e61e77f5204e02f74efd28690abb86`, and
`EXECUTION_INTEGRATION_SHA = FROZEN_BY_OPERATOR_AT_IMPLEMENTATION_START`. The operator returns the final literal execution SHA after
this plan is committed and approved; P0.1/P1/P2/P3 and every first-wave worktree use exactly that external value.

## Non-negotiable invariants

1. `architecture.md` is read-only. A discovered architecture conflict is an operator decision, not an edit.
2. Final RQC remains the semantic request authority. SPL V2 evolves the **existing** SPL intent spec; it does not add a second
   planner or reinterpret the raw query downstream. Repo fact, verified at `fe3548e4`: there is no `SplIntentSpec` class. The spec is a
   plain `dict[str, Any]` produced by `build_spl_intent_spec()` in `backend/app/spl/spl_intent_spec.py` and rendered by
   `spl_intent_spec_for_prompt()`. "Typed concepts" in P2 means introducing a typed model **behind** those two functions while their
   call sites keep working; it does not mean a second representation alongside the dict.
3. Candidate SPL remains non-executable. Only deterministically approved, non-null `normalized_spl` may approach the existing MCP execution gate.
4. LLM outputs are advisory. One initial SPL proposal plus at most one bounded repair is the maximum.
5. LLMs never call MCP. Global and per-server MCP execution remain default-off through P10.
6. EvidenceState records obtained evidence only. Plans, attempts, failures, diagnostics, and empty projection objects are not evidence.
7. Experience Center remains isolated from production `/chat` behavior and production UI.
8. No stream pushes or merges. P10 prepares operator handoff only; P11 is a separately approved COE activity.
9. No two active streams own the same file. Shared seams have one named owner and queued change requests.
10. A protected-file need causes STOP, an exact proposed diff, and operator approval before any mutation.

## Stop conditions

The execution loop stops when every phase is DONE with evidence, the same gate fails twice on one bounded item, a dependency premise is disproved, a protected path is required, a contract change crosses another stream's ownership, an unexplained regression appears, or operator/live-environment input is required. Do not silently adapt, weaken thresholds, update baselines, or classify a named failure as merely pre-existing.

## Dependency DAG

```text
P0 Harness readiness (DONE @ 615069e6)
 |
 +--> P1 Trace truth closure -----------+
 |                                      |
 +--> P2 SPL semantic V2 ---------------+--> P5 Integrated L2 closure --> P6 Test rationalization
 |          |                           |              |                         |
 |          +--> P4 Prompt/policy ------+              +--> P7 Production UI ---+--> P9 Promotion
 |                                                     |                         |       |
 +--> P3 L2 bank scaffold -----------------------------+--> P8 L3 live LLM ------+       +--> P10 PR/merge handoff
                                                                                             |
                                                                                             +--> P11 Live MCP COE
```

The picture above is illustrative. **This edge list is authoritative** when the two disagree:

```text
P0   -> P0.1, P1, P2, P3
P0.1 -> (unblocks every L0 RACES gate; blocks nothing else)
P1   -> P5
P2   -> P4, P5
P3   -> P5
P4   -> P5
P5   -> P6, P7, P8
P6   -> P9
P7   -> P9
P8   -> P9
P9   -> P10
P10  -> P11
```

`P1`, `P2`, and the scaffold-only portion of `P3` can start in parallel from the same SHA. `P4` may perform a read-only role/posture audit in parallel, but implementation waits for P2's semantic contract and may not edit SPL-owned prompt files. P5 requires rebasing the eval branch after P1, P2, and P4. P6 starts only after P5 is green. P7 and P8 can execute in parallel after P5 if they retain exclusive ownership. P9 waits for P6, P7, and P8. P10 and P11 are strictly serial and operator-gated.

## Worktrees and branches

Do not create these during plan authoring. At implementation start, the integration owner freezes and records
`EXECUTION_INTEGRATION_SHA`; every initially parallel branch starts exactly there.

If an explicitly approved P0.1 apply commit lands after P1/P2/P3 branches have started, the integration owner records the new exact
`EXECUTION_INTEGRATION_SHA` containing P0.1 and sets `REBASE_REQUIRED = YES` on every active pre-P0.1 branch. Those branches must rebase to that
exact SHA before recording any L0 gate, returning a branch packet, or entering reconciliation/merge. Their pre-rebase focused evidence
may remain as iteration history, but it is not integration evidence. No stream may self-select a different rebase target.

| Stream | Branch | Worktree purpose | Initial dependency | Merge order |
|---|---|---|---|---|
| A TRACE | `ws/trace-truth` | Trace vocabulary, projection truth, stable oracle tests | P0 | 1 |
| B SPL | `ws/spl-semantic-v2` | Existing semantic contract/compiler/fidelity evolution | P0 | 2 |
| C EVAL | `ws/l2-eval-bank` | Test-only L2 bank scaffold, later integration and rationalization | P0 scaffold; P1/P2/P4 for assertions | 4 then 5 |
| D POLICY | `ws/prompt-policy` | Role posture, prompt provenance, policy configuration contract | P2 contract for implementation | 3 |
| E UI | `ws/production-ux` | Production UI components/tests after contracts stabilize | P5 | 7 |
| F PROMOTION | `ws/promotion-coe` | L3 bank, gate evidence, handoff, last-stage COE | P5/P6/P7 as specified | 6 then 8 |
| INTEGRATION | `feat/complete-or-abstain-t4-ux` | Reconcile branches; no feature authorship while streams are active | Frozen integration SHA | sole integrator |

Worktree directory names are operator-selected local paths such as `../ai-soc-wt-trace`; they are not contractual. Branch names and actual start SHAs are contractual and must be recorded in the loop runner.

## File ownership matrix

| Authority seam | Exclusive implementation owner | Allowed paths | Must not modify concurrently |
|---|---|---|---|
| Trace/control-plane truth | A / CODEX | `backend/app/chat/control_plane_trace.py`, `pipeline_visibility.py`, `investigation_shaped.py`, `canonical_facts_spine.py`, `backend/app/spl/spl_provenance_trace.py`, `backend/app/spl/spl_artifact_trace_projection.py`, directly corresponding trace tests | `pipeline.py`, `schemas/responses.py`, SPL semantic modules, UI |
| SPL semantic V2 | B / CURSOR | `backend/app/spl/spl_intent_spec.py`, `spl_semantic_fidelity.py`, `utility_spl_authoring.py`, `llm_fallback.py`, `llm_plan_compiler.py`, `review_only_spl_postprocessor.py`, `request_authority.py`, `rqc_constraint_preservation.py`, `spl_source_resolve.py`, `source_profile_catalog.py`, `source_profile_resolver.py`, `source_profile_bindings.py`, `source_profile_store.py`, `slot_binding_merge.py`, `spl_slot_binding_validator.py`, `spl_relevance_check.py`, directly corresponding tests | `backend/app/safeguards/spl_validator.py` (**RACES-protected: read-only, protected diff required**), `backend/app/schemas/responses.py` (**protected**), `backend/app/graph/` (**protected**, incl. `resource_planner_graph.py`), trace projections, generic LLM role registry, eval-bank files, UI |
| Eval/test architecture | C / CLAUDE | `backend/app/tests/test_p0_l2_production_chat_harness.py` or a successor L2 bank owned solely by C, test-tier metadata/config, test inventory/report scripts and docs approved by phase scope | Runtime product modules, trace/SPL contract tests owned by A/B, protected files |
| Prompt/policy | D / CLAUDE | `backend/app/llm/prompts.py`, `adapter/role_registry.py`, `hybrid_role_graph.py`, `registry_settings.py`, prompt-policy schemas/config and corresponding tests; frontend Prompt Studio deferred to E | `backend/app/spl/llm_fallback.py` is a SHARED_SEAM owned by B; runtime pipeline; UI during D |
| Production UI | E / CURSOR | New or existing non-EC production components/hooks/tests, settings panels, frontend API/types after backend contracts merge | EC modules; `ChatPanel.tsx` without approval; backend authority logic |
| Promotion/COE | F / CODEX | Eval scripts/banks, evidence reports, promotion docs, operational test artifacts explicitly named in P8-P11 | Runtime behavior except separately approved defect fix returned to owning stream |
| Integration | CODEX integrator | Merge conflict resolution only in owning stream's presence; plan/loop evidence | No unilateral semantic rewrite; no last-writer-wins |

### Shared seams

- `backend/app/spl/llm_fallback.py`: B owns all edits. D supplies requirements through `RECONCILIATION_QUEUE` and reviews prompt-policy effects.
- Response/trace TypeScript types: E owns after P5 freezes backend names. A reviews semantic fidelity; A does not edit frontend files.
- L2 expected fields: C owns bank rows; A/B/D own contract semantics. C waits and rebases rather than pinning speculative fields.
- `backend/app/chat/pipeline.py`: protected, not owned by any stream. Exact proposed diff and operator approval are required.
- `frontend/src/components/ChatPanel.tsx` and every path in `RACES_FREEZE_PATHS`: protected, not owned until operator approval for a specific diff.

## FINDINGS_LEDGER

This ledger is append-only. A phase updates `STATUS` and `FINAL_DISPOSITION`; it never removes a row. Allowed statuses are
`CLOSED_P0`, `OPEN`, `PRODUCT_GAP`, `DEFERRED`, `NEEDS_REPROOF`, `OPERATOR_DECISION`, and `CLOSED`. A `PRODUCT_GAP` must receive an
explicit `SUPPORTED_NOW`, `DEFERRED`, or `SEPARATE_PRODUCT_PHASE` decision before its owner phase can close.

| FINDING_ID | SOURCE | DESCRIPTION | STATUS | OWNER_PHASE | DEPENDENCY | CLOSURE_TEST_OR_EVIDENCE | FINAL_DISPOSITION |
|---|---|---|---|---|---|---|---|
| H-MCP-01 | P0 harness | Planned MCP argument contract | CLOSED_P0 | P0 | None | P0 contract test | Preserve |
| H-MCP-02 | P0 harness | Plan -> AUTH0 argument continuity | CLOSED_P0 | P0 | None | P0 AUTH0 test | Preserve |
| H-MCP-03 | P0 harness | Readiness trace v2 | CLOSED_P0 | P0 | None | `mcp_tool_readiness_v2` tests | Preserve |
| H-MCP-04 | P0 harness | Productive same-tool second round | CLOSED_P0 | P0 | None | P0 two-round L2 row | Preserve |
| H-MCP-05 | P0 harness | Bounded failure alternate | CLOSED_P0 | P0 | None | P0 alternate L2 row | Preserve |
| H-MCP-06 | P0 harness | Mocked Streamable HTTP transport | CLOSED_P0 | P0 | None | Transport contract test | Preserve |
| H-MCP-07 | P0 harness | `read_only` versus `execution_gated` classification | CLOSED_P0 | P0 | None | Readiness classification test | Preserve |
| H-MCP-08 | MCP audit | Real metadata/tool schemas remain unverified | OPEN | P11 | P10 + COE approval | Redacted real schema hashes | Close in P11 |
| H-MCP-09 | Architecture | Live MCP remains default-off | DEFERRED | P11 | P10 + separate approval | COE gate and post-run flag evidence | P11 only |
| H-MCP-10 | Historic audit | Non-Splunk MCP playbooks | PRODUCT_GAP | P11 | Capability inventory | Supported-now proof or explicit product decision | Decision required |
| H-TRACE-01 | Trace audit | LLM attempted/response/accepted/used accounting | NEEDS_REPROOF | P1 | P0 | Lifecycle matrix tests | Close or mark already-correct in P1 |
| H-TRACE-02 | Trace audit | Fallback terminology consistency | NEEDS_REPROOF | P1 | P0 | Stable-oracle table tests | P1 |
| H-TRACE-03 | Trace audit | RAG skipped while `rag_citation` appears obtained | NEEDS_REPROOF | P1 | P0 | RAG no-match/match projection tests | P1 |
| H-TRACE-04 | Trace audit | Artifact review versus execution HIL | OPEN | P1 | P0 | Distinct flag contract tests | P1 |
| H-TRACE-05 | Trace audit | Pure-SPL InvestigationOutcome applicability | NEEDS_REPROOF | P1 | P0 | Pure-SPL L1/L2 rows | P1 |
| H-TRACE-06 | Trace audit | Stable trace oracle versus diagnostics | OPEN | P1 | P0 | Versioned schema tests | P1 |
| H-TRACE-07 | Provenance audit | `run_shape_transition` decision-site provenance | OPEN | P1 | P0 | Decision-site trace test | P1 |
| H-TRACE-08 | Architecture | No fabricated RAG/MCP evidence | OPEN | P1 | P0 | EvidenceState truth matrix | P1 |
| H-SPL-01 | Semantic audit | Final RQC -> SPL semantic compiler | OPEN | P2 | P0 | Contract propagation test | P2 |
| H-SPL-02 | Three-query audit | Search horizon versus analytical window | OPEN | P2 | H-SPL-01 | Rolling/trend tests | P2 |
| H-SPL-03 | Three-query audit | Rolling windows | OPEN | P2 | H-SPL-02 | 10m rolling plus adjacent row | P2 |
| H-SPL-04 | Semantic audit | Required event sets | OPEN | P2 | H-SPL-01 | Multi-event preservation test | P2 |
| H-SPL-05 | Semantic audit | Entity semantic roles | OPEN | P2 | H-SPL-01 | Source/account role tests | P2 |
| H-SPL-06 | Semantic audit | Distinct-count relationships | OPEN | P2 | H-SPL-05 | Source-to-distinct-account test | P2 |
| H-SPL-07 | Semantic audit | Explicit measures | OPEN | P2 | H-SPL-01 | Measure fidelity tests | P2 |
| H-SPL-08 | Three-query audit | Temporal grain | OPEN | P2 | H-SPL-01 | Hourly grain test | P2 |
| H-SPL-09 | Three-query audit | Trend/time-series shape | OPEN | P2 | H-SPL-08 | 24h hourly trend plus adjacent row | P2 |
| H-SPL-10 | Three-query audit | Ordered sequences | OPEN | P2 | H-SPL-04 | Password-change then login test | P2 |
| H-SPL-11 | Three-query audit | Sequence maximum gap | OPEN | P2 | H-SPL-10 | Five-minute gap fidelity test | P2 |
| H-SPL-12 | Historic audit | Comparison semantics | PRODUCT_GAP | P2/P5 | Capability decision | "same campaign as last month" decision/test | Decision required |
| H-SPL-13 | Semantic audit | Output shape | OPEN | P2 | H-SPL-01 | Raw/aggregate/rank/trend output tests | P2 |
| H-SPL-14 | Semantic audit | Normalization aliases consumed downstream | OPEN | P2 | Source bindings | Alias-use structural test | P2 |
| H-SPL-15 | Prompt audit | Arbitrary `head 100` or result truncation | OPEN | P2/P4 | Analysis shape | All-events/time-series negative test | P2/P4 |
| H-SPL-16 | Prompt audit | Unexpected threshold invention | OPEN | P2/P4 | Semantic prohibitions | Invented-constraint metric/test | P2/P4 |
| H-SPL-17 | Prompt audit | Alert-template bias in analytical SPL | OPEN | P2/P4 | Role prompt | Trend/raw negative tests | P2/P4 |
| H-SPL-18 | Semantic audit | Lightweight structural SPL syntax checks | OPEN | P2 | Semantic V2 | Structural validator tests | P2 |
| H-SPL-19 | Governance | One generation plus one repair bound | OPEN | P2/P4 | Runtime prompt path | Attempt-count test | P2/P4 |
| H-SPL-20 | Repair audit | Prior rejected candidate reaches repair | OPEN | P2/P4 | H-SPL-19 | Repair payload test | P2/P4 |
| H-SPL-21 | Postprocessor audit | Required ordering survives postprocessing | OPEN | P2 | Sequence/rolling shape | `streamstats` ordering test | P2 |
| H-PROMPT-01 | Role audit | Complete production/dormant role inventory | OPEN | P4 | P2 for final semantics | Call-site inventory and posture table | P4 |
| H-PROMPT-02 | Prompt audit | Role-specific prompts, not monolithic SOC prompt | OPEN | P4 | H-PROMPT-01 | Prompt contract review/tests | P4 |
| H-PROMPT-03 | Authority audit | Shape advisor remains advisory | OPEN | P4 | P2 | Authority/validator test | P4 |
| H-PROMPT-04 | Allowlist audit | Blocked reasoning-role posture is intentional | OPERATOR_DECISION | P4 | Role inventory | Decision per blocked role | Decision required |
| H-PROMPT-05 | Provenance audit | Prompt template version/hash | OPEN | P4 | Role contracts | Deterministic hash tests | P4 |
| H-PROMPT-06 | Correction mission | Provider-agnostic prompt caching readiness | OPEN | P4 | Versioned prompt assets | Stable-prefix/hash/cache tests | P4 |
| H-PROMPT-07 | Correction mission | Few-shot governance by semantic shape | OPEN | P4 | Role contracts | Versioned bank tests | P4 |
| H-PROMPT-08 | Correction mission | Negative-example governance | OPEN | P4 | Failure taxonomy | Versioned negative bank tests | P4 |
| H-PROMPT-09 | Correction mission | Prompt A/B semantic evaluation | OPEN | P8 | P4 + frozen L3 bank | Active-versus-candidate report | P8 |
| H-PROMPT-10 | Security | Prompt cache never becomes authority | OPEN | P4 | Cache design | Auth/session isolation tests | P4 |
| H-PROMPT-11 | Studio design | Prompt & Policy Studio governed config | OPEN | P4/P7 | Backend contract then UI | Auth/redaction/rollback and UI tests | P4/P7 |
| H-FOLLOW-01 | P0 harness | Supported time delta | CLOSED_P0 | P0 | None | P0 follow-up test | Preserve |
| H-FOLLOW-02 | P0 harness | Supported entity correction | CLOSED_P0 | P0 | None | P0 follow-up test | Preserve |
| H-FOLLOW-03 | Historic test audit | Phrase "run that for yesterday" unsupported until proven | PRODUCT_GAP | P5 | P1/P2 contracts | Exact L2 row or explicit decision | Decision required |
| H-FOLLOW-04 | Historic test audit | "same campaign as last month" comparison | PRODUCT_GAP | P5 | H-SPL-12 | Exact L2 row or explicit decision | Decision required |
| H-FOLLOW-05 | L2 audit | User rejection/correction and user-added evidence | OPEN | P5 | P1/P3 | L2 follow-up rows | P5 |
| H-EVID-01 | P0 harness | Contradictory evidence safe behavior | CLOSED_P0 | P0 | None | P0 contradiction row | Preserve |
| H-EVID-02 | Historic audit | Explicit evidence-level contradiction adjudication | PRODUCT_GAP | P5 | Product capability decision | Adjudication test or explicit decision | Decision required |
| H-EVID-03 | Trace audit | Source provenance truth | OPEN | P1/P5 | P1 oracle | Source projection L1/L2 tests | P1/P5 |
| H-REM-01 | UX audit | Exactly one authoritative remediation CTA | OPEN | P5/P7 | Remediation contract | L2 plus UI assertion | P5/P7 |
| H-REM-02 | Architecture | Planning versus execution separation | OPEN | P5/P7 | P1 review flags | L2 plus UI authority test | P5/P7 |
| H-REM-03 | Historic audit | Execute -> verify -> monitor lifecycle | PRODUCT_GAP | P5/P7 | Product capability decision | Lifecycle rows or explicit decision | Decision required |
| H-REM-04 | Architecture | Unavailable write integrations remain manual | OPEN | P5/P7 | Capability readiness | Degradation/manual CTA tests | P5/P7 |
| H-TESTUX-01 | L2 audit | First approximately 23 production cases | OPEN | P3/P5 | P1/P2/P4 | Expanded L2 bank | P5 |
| H-TESTUX-02 | Test audit | L0/L1/L2/L2-slow/L3/L4/L5 tiering | OPEN | P6 | P5 | Tier commands/report | P6 |
| H-TESTUX-03 | Test audit | Moderate rationalization | OPEN | P6 | P5 | Retirement ledger/collection diff | P6 |
| H-TESTUX-04 | Test audit | EC literal-copy low-value tests | NEEDS_REPROOF | P6 | P5 | Invariant/replacement disposition | P6 |
| H-TESTUX-05 | Frontend audit | Production frontend versus EC coverage imbalance | OPEN | P7 | P5 | Coverage/journey matrix | P7 |
| H-TESTUX-06 | UX audit | SPL review safety UI | OPEN | P7 | P2/P5 | Frontend journeys | P7 |
| H-TESTUX-07 | UX audit | HIL UI | OPEN | P7 | P1/P5 | Frontend journeys | P7 |
| H-TESTUX-08 | UX audit | Remediation UI | OPEN | P7 | H-REM rows | Frontend journeys | P7 |
| H-TESTUX-09 | UX audit | Degradation UI | OPEN | P7 | P5 | Frontend journeys | P7 |
| H-TESTUX-10 | Historic test audit | Dead planner test disposition | NEEDS_REPROOF | P6 | P5 | Keep/archive/replace decision with invariant owner | Decision required |
| H-TESTUX-11 | Historic test audit | Orphan eval bank disposition | NEEDS_REPROOF | P6 | P5 | Provenance/consumer/archive decision | Decision required |
| H-PROMO-01 | Promotion audit | Exact residual failure ledger | OPEN | P9 | P6/P7/P8 | Named baseline/candidate table | P9 |
| H-PROMO-02 | Routing audit | `rt.para.011` | OPEN | P9 | Routing gate | Exact layer/result and decision | P9 |
| H-PROMO-03 | Environment audit | GitHub clone-root environment | OPEN | P9 | Valid clone or operator block | Governance evidence | P9 |
| H-PROMO-04 | Environment audit | PostgreSQL/migration/plugin failures | OPEN | P9 | Required environments | Exact test IDs/results | P9 |
| H-PROMO-05 | Promotion | Mac/Linux same candidate SHA | OPEN | P9 | All candidate gates | SHA attestations | P9 |
| H-PROMO-06 | Freeze audit | RACES baseline and protected changes | OPERATOR_DECISION | P0.1/P9 | Explicit approvals | P0.1 packet plus final RACES gate | Decision required |
| H-PROMO-07 | Governance | Stage 3 governance | OPEN | P9 | Environment prerequisites | Canonical runner result | P9 |
| H-PROMO-08 | Architecture | Live MCP last | DEFERRED | P11 | P10 + separate approval | COE authorization/evidence | P11 only |

## Protected-file policy

`architecture.md` may only be read. The protected set is `architecture.md` plus every current `RACES_FREEZE_PATHS` prefix.
`RACES_FREEZE_PATHS` is **not** a frontend-only list, and it is **not** a prose description: it is
`RACES_FREEZE_PATHS = EC_FORBIDDEN_PREFIXES` in `backend/app/tests/test_live_path_untouched_by_ec.py`. Read that constant before
starting any phase. As measured at `fe3548e4` it is exactly these eleven prefixes:

```text
backend/app/api/routes_chat.py
backend/app/api/routes_chat_stream.py
backend/app/api/routes_actions.py
backend/app/chat/pipeline.py
backend/app/graph/
backend/app/planner/
backend/app/routing/
backend/app/schemas/responses.py
backend/app/orchestration/mcp_execution_gate.py
backend/app/safeguards/spl_validator.py
frontend/src/components/ChatPanel.tsx
```

Two of these were previously misassigned by this plan and are corrected in the ownership matrix: `backend/app/safeguards/spl_validator.py`
(read by B, owned by nobody) and `backend/app/schemas/responses.py` (needed by P1/P2/P7 for new contract fields, owned by nobody).
Expect at least one protected-diff request per phase; that is normal, not a plan failure. If completion requires one:

1. STOP before editing.
2. Put the exact minimal proposed diff, rationale, invariant impact, tests, and rollback in `PROTECTED_CHANGE_QUEUE`.
3. Record `OPERATOR_APPROVAL_REQUIRED` and do no dependent implementation.
4. After explicit approval, assign the change to the existing seam owner, apply only the approved diff, run the RACES/freeze tests and affected phase gates, and record the approval reference.

Advancing a RACES baseline is itself a protected change and cannot be used to hide unreviewed mutations.

How the gate actually fires (know this before you debug it):

- `test_races_freeze_files_not_in_working_tree` diffs `HEAD` against the **working tree**, so an *uncommitted* edit to a protected path
  turns it red in that worktree only.
- `test_races_freeze_files_unchanged_since_baseline` diffs `RACES_BASELINE_SHA...HEAD`, so a *committed* edit to a protected path turns
  it red for every branch descended from that commit, in every worktree, permanently, until the baseline is advanced.
- Both tests run `git` inside their own worktree (`REPO = Path(__file__).resolve().parents[3]`), so each stream sees its own state.

An approved protected change therefore has two halves: apply the approved diff, **and** advance `RACES_BASELINE_SHA` to that exact
commit with an audit comment in the same style as the existing ones in that file. Doing only the first half leaves every downstream
stream red and indistinguishable from a real regression.

## Agent assignment matrix

| Workstream | Agent | Why | Expected ownership | Dependency | Parallel safe with |
|---|---|---|---|---|---|
| A TRACE | CODEX | Best fit for cross-module authority tracing and integration reconciliation | Trace/provenance modules and stable-oracle tests | P0 | B and P3 scaffold |
| B SPL | CURSOR | Best fit for concentrated Python contract/compiler implementation and local feedback loops | All SPL semantic and live SPL prompt files | P0 | A and P3 scaffold |
| C EVAL | CLAUDE | Prior audit context and fit for bank design, invariant mapping, and parameterization | L2 bank and test architecture only | P0 scaffold; contracts for completion | A/B/D when files do not overlap |
| D POLICY | CLAUDE | Fit for role inventory, allowlist policy, provenance schema, and config model | Generic prompt/role/policy files | P2 before writes affecting semantic prompts | A; C scaffold |
| E UI | CURSOR | Fit for frontend implementation and browser-focused validation | Production non-EC UI and tests | P5 | P8 L3 after ownership check |
| F/INTEGRATION | CODEX | Single owner for reconciliation, gate evidence, and exact-SHA promotion | Integration records/evals; no feature seam takeover | Phase-specific | E and L3 only when files are exclusive |

Agent names express recommended responsibility, not permission for simultaneous edits in one tree. One agent owns each seam; another may review without writing.

## Branch return packet

Every branch returns this exact packet before reconciliation:

```text
START_SHA:
END_SHA:
COMMITS:
FILES_CHANGED:
PROTECTED_FILES_CHANGED: NONE | list with approval reference
TESTS: command plus result
KNOWN_FAILURES: exact test IDs and classification
CONTRACT_CHANGES:
REBASE_REQUIRED: YES | NO, target SHA
```

The integrator verifies the packet, rebases or merges against the declared integration SHA, reruns cross-stream tests, and asks the designated seam owner to resolve semantic conflicts. No last-writer-wins resolution.

## Commit guidance

Applies to every stream. A commit is an evidence record, not a checkpoint: if it cannot be described honestly in one line, it is more
than one commit.

### When to commit

Commit when one plan item's Verify command has passed and its Evidence is recorded — not before, not batched at phase end. Never commit
to get out of a broken state; revert instead. Never commit while a gate the item claims is red.

A pre-fix red reproduction is **iteration evidence, not a commit**. Record the exact command, failure, and classification in the loop
iteration, apply the bounded fix, and commit implementation plus its regression test only after the logical contract's focused gate is
green. Permanent deliberately-red commits are forbidden. This does not justify giant phase commits: commit each bounded green contract.

### What may be in one commit

- **Only files in the committing stream's `ALLOWED_FILES`.** A commit that touches another stream's seam is a merge conflict shipped
  early. Check with `git status --porcelain` before every `git add`.
- **One workstream, one logical change.** Do not combine trace work with SPL work, runtime with eval banks, or UI with backend contracts.
- Use `git add <explicit paths>`. **Never `git add -A`, `git add .`, or `git commit -a`** — those are how protected files and generated
  baseline drift enter a commit unnoticed.
- **Never stage `.claude/settings.local.json`.** It is modified in the tree for unrelated reasons and must stay that way. Also never
  stage `.venv/`, `__pycache__/`, `.pytest_cache/`, `frontend/dist/`, or `.cursor/hooks/.loop-asap-requested`.
- **Never let a protected path into a commit** without a recorded approval reference in the commit body. Verify immediately before
  committing: `git diff --cached --name-only` must contain no `RACES_FREEZE_PATHS` prefix.
- **Never refresh an eval baseline, golden file, or protected manifest as a side effect.** If one moved, that is a finding, not a
  formatting fix. Regenerated artifacts under `docs/evals/` and `backend/app/coverage/` need their own commit and their own justification.

### Message format

```text
<type>(<scope>): <imperative summary, <=72 chars, lowercase, no trailing period>

<why this change exists — the invariant or defect, not a restatement of the diff>

Plan: plans/2026-08-25_1806_ai-soc-master-parallel-closure.md
Item: <P#>
Tests: <exact command> -> <exact result>
Protected-approval: NONE | <approval reference>
```

`type` is one of `feat`, `fix`, `test`, `refactor`, `docs`, `chore`. `scope` matches the phase seam: `trace`, `spl`, `l2`, `llm`, `ui`,
`eval`, `races`, `promotion`, `plan`. Each phase's `EXPECTED_COMMIT_GROUPS` field and the choreography table give the expected sequence.

Do not add a `Co-Authored-By` trailer or any AI-attribution trailer in this repository unless the operator asks for one.

### Ordering within a phase

Reproduce-red -> record iteration evidence -> implement bounded fix -> verify green -> commit the logical contract. The green commit may
contain implementation and regression tests. If adjacent choreography entries collapse safely into one bounded green contract, do not
force an artificial commit; record the deviation in `DECISION_LOG` with purpose, files, and gates preserved.

### Plan and evidence commits

Updating this plan's checkboxes/Evidence or the loop runner dashboard is a `docs(plan):` commit scoped to `plans/` only. Never mix it
with code. Do not update `plans/README.md` — that write is explicitly out of scope (see the drift log).

### What no stream may ever do

`git push`, `git merge`, open a PR, `git rebase` onto anything other than the declared `EXECUTION_INTEGRATION_SHA`, `git commit --amend` or
`git rebase -i` on a commit already handed to the integrator, `git reset --hard`, force-anything, or `git checkout` a protected file to
discard an operator-approved diff. Reconciliation is the integrator's, and only the integrator's. P10 is where anything leaves the machine.

## Test gate matrix

| Gate | Purpose | Minimum command/evidence | Required before DONE |
|---|---|---|---|
| FOCUSED | Fast edit loop | `cd backend && "$PYVENV" -m pytest -q <owned tests>` or `cd frontend && npm test -- <owned tests>` | Every code item |
| L0 | Static governance/freeze/authority | Named governance, trust-boundary, RACES, and architecture checks relevant to change. **Precondition: P0.1 is DONE.** Until then `test_races_freeze_files_unchanged_since_baseline` is red for every stream and no L0 gate may be recorded green | P1, P4, P7, P9 |
| L1 | Deterministic unit/contract | Owned module contract suites including adjacent generalization | P1, P2, P4, P6 |
| L2 | Mocked production `/chat` | P0 bank plus expanded approximately 23-case bank | P3, P5, P6, P7, P9 |
| L2-SLOW | Timeout/subprocess/lifecycle | Explicitly marked timeout, subprocess, and bounded retry tests | P5, P6, P9 |
| L3 | Live local LLM semantic | Frozen bank and report; endpoint/config recorded, no threshold changes | P8, P9 |
| FRONTEND | Production UI unit/build | `cd frontend && npm test && npm run build` | P7, P9 |
| GOVERNANCE | Canonical regression | `PATH="$PWD/.venv/bin:$PATH" ./scripts/run_stage3_governance_regression.sh` | P9 |
| LINUX | Isolated candidate validation | Exact candidate SHA in clean Linux environment; same named gates and residual comparison | P9 |
| LIVE-MCP | Real Splunk MCP COE | P11 schema/auth/lifecycle/empty/error/full-investigation protocol | P11 only |

Focused tests run per item. Phase gates run at phase completion. The full backend suite is a promotion gate, not a per-edit loop.

### Interpreter in a worktree (read before running any gate)

`.venv/` is gitignored, so a freshly created worktree has **no** `.venv` and the relative form `../.venv/bin/python` fails there.
Every stream exports one absolute interpreter path and uses `$PYVENV` in every command and every recorded evidence line:

```bash
export PYVENV=/Users/aagarwal/Downloads/ai-soc-assistant-t4-architecture-20260821/.venv/bin/python
```

Sharing the main repo's interpreter across worktrees is safe and intended: `app` is **not** installed into that venv
(`$PYVENV -c 'import app'` raises `ModuleNotFoundError`). It resolves per-run from pytest's `pythonpath = ["."]` with
`testpaths = ["app/tests"]` in `backend/pyproject.toml`, so `cd <this-worktree>/backend && "$PYVENV" -m pytest` always imports
**this worktree's** code. Never `cd` to the main repo to run a stream's tests, and never record evidence from a `python`
resolved off `PATH` — record the command exactly as run, `$PYVENV` expanded.

The GOVERNANCE gate is the one exception and keeps its documented form, run from the worktree root:
`PATH="$(dirname "$PYVENV"):$PATH" ./scripts/run_stage3_governance_regression.sh`.

## Prompt engineering contract

P4 must inventory every production-reachable and intentionally dormant role found by repository call-site inspection. Each role gets one
record with all of these fields; `NOT_APPLICABLE` requires a reason and may not be left blank:

```text
ROLE_ID
RUNTIME_POSTURE
WHY_LLM
AUTHORITATIVE_INPUTS
NON_AUTHORITATIVE_CONTEXT
SYSTEM_INSTRUCTION
DYNAMIC_CONTEXT
OUTPUT_SCHEMA
FEW_SHOT_SET
NEGATIVE_EXAMPLE_SET
MODEL_CLASS
TEMPERATURE_OR_DECODING_POSTURE
TIMEOUT
RETRY_REPAIR_POLICY
ALLOWED_AUTHORITY
PROHIBITED_AUTHORITY
VALIDATOR
FALLBACK
TRACE_FIELDS
PROMPT_TEMPLATE_ID
PROMPT_VERSION
PROMPT_HASH
STABLE_PREFIX_HASH
CACHE_ELIGIBLE
```

### Initial role inventory

This is the minimum 24-role canonical inventory. P4 reconciles registry aliases and adds every additional production call site it finds;
an alias is not counted twice after its canonical role is proven. Dormant roles remain present with an intentional posture.

| # | ROLE_ID | Initial posture / note |
|---|---|---|
| 1 | `semantic_t4` | Governed semantic proposal after deterministic abstain |
| 2 | `intent_advisor` | Advisory; reconcile with `intent_shadow_classifier` call sites |
| 3 | `shape_advisor` | Advisory only |
| 4 | `spl_generation` | Candidate-only; reconcile registry alias `spl_advisory_generator` |
| 5 | `spl_repair` | Candidate-only, maximum one repair |
| 6 | `investigation_planner` | Advisory plan proposal, no execution authority |
| 7 | `missing_evidence_reasoner` | Intentionally allowlist-blocked pending explicit decision |
| 8 | `plan_delta_reasoner` | Intentionally allowlist-blocked pending explicit decision |
| 9 | `mitre_reasoner` | Intentionally allowlist-blocked pending explicit decision |
| 10 | `risk_rationale_reasoner` | Intentionally allowlist-blocked pending explicit decision |
| 11 | `governed_composer` | Narration-only; reconcile alias `analyst_summary_narration` |
| 12 | `evidence_observer` | Advisory observation only |
| 13 | `intent_shadow_classifier` | Registry role; reconcile with intent advisor |
| 14 | `analyst_response_drafter` | Registry role; authority/fallback audit required |
| 15 | `guided_investigation_plan_proposer` | Registry role; no action authority |
| 16 | `investigation_note_drafter` | Registry role; prose only |
| 17 | `pattern_reasoner` | Registry role; posture audit required |
| 18 | `evidence_reasoner` | Registry role; cannot create EvidenceState facts |
| 19 | `hypothesis_reasoner` | Registry role; review-only hypotheses |
| 20 | `template_render_parameter_assist` | Registry role; deterministic validation wins |
| 21 | `template_match_semantic_assist` | Registry role; advisory match only |
| 22 | `route_plan_candidate_generator` | Registry role; deterministic route authority wins |
| 23 | `answer_guard_assistant` | Registry role; current live reachability must be proven |
| 24 | `mitre_candidate_mapper` | Registry role; deterministic MITRE status/validation wins |

No monolithic SOC prompt is allowed. Each canonical role has the narrowest inputs and output schema needed by its one consumer.

### Role-specific prompt architecture

`spl_generation` receives only the immutable semantic contract, Final RQC constraints, governed source mappings, analysis/output shape,
required events, entity roles, search horizon, analytical window, measures/grouping/distinct/ranking, temporal/sequence semantics, and
prohibitions. It does not receive unrelated MITRE policy, remediation instructions, routing authority, MCP execution authority, or a
generic alert-template catalogue unless one item is specifically required and justified by this role's contract.

`spl_repair` receives the same immutable semantic contract, the previous rejected candidate, deterministic syntax/fidelity losses,
governed source bindings, and a bounded correction scope. It receives no permission to reinterpret the request. Runtime remains exactly
one generation plus at most one repair.

`semantic_t4` receives the original request and deterministic abstain/RQC boundary needed by the existing governed merge; it cannot
override locked deterministic facts. `intent_advisor` and `shape_advisor` receive only classification/shape context and remain advisory.
Planning roles receive governed RQC/EvidenceState/capability posture but no Auth0 grant or execution tool. Reasoning roles receive only
the evidence needed by their output schema and cannot invent evidence, severity, MITRE truth, actions, or SPL. `governed_composer`
receives deterministic outcomes and may rewrite narration only. `evidence_observer` can report observations but cannot mutate evidence.
P4 writes this same narrow-contract statement for every additional role in the inventory.

### Few-shot and negative-example governance

Few-shot assets are selected by reusable semantic shape (`RAW_EVENTS`, `AGGREGATION`, `RANKING`, `TREND`, `ROLLING`, `SEQUENCE`,
`COMPARISON`) or the equivalent narrow role concept, never one example per customer query. Each asset has ID, version, role, shape,
input contract, expected structured output, provenance, reviewer, and activation state. Adding/removing/reordering an active example
changes the prompt hash and stable-prefix hash and invalidates prompt-cache eligibility until revalidated.

SPL negative examples must cover at least: semantic noun treated as literal value (`accounts`), search horizon confused with analytical
window, grouping the wrong entity, required second event omitted, sequence order omitted, max event gap omitted, trend converted to an
alert template, invented threshold, arbitrary `head 100`, and normalized alias created but not consumed. Other roles maintain their own
authority/schema/unsupported-claim negative sets. Negative examples teach rejection/correction; they never loosen deterministic checks.

### Provider-agnostic prompt caching

The deterministic `STABLE_PREFIX` contains role definition, authority/security boundaries, output schema, stable instructions,
shape-specific few-shots, negative examples, and stable policy rules in canonical ordering. It contains no timestamp, trace/request ID,
random value, dynamic evidence, user/session data, Auth0 state, execution grant, or environment-specific secret.

The `DYNAMIC_SUFFIX` contains Final RQC, current semantic IR, governed source bindings, current request, current evidence, current
PlanDelta/tool result, and turn-specific state. Stable and dynamic serialization order is deterministic. Trace/config records
`prompt_template_id`, `prompt_version`, `prompt_hash`, `stable_prefix_hash`, `dynamic_context_hash`, provider, model, `cache_eligible`,
and provider-reported `cache_hit`, `cache_miss`, or `unknown`.

Cache invalidates on prompt version, role contract, schema, governance instruction, few-shot bank, negative-example bank, or stable
source-independent policy change. Caching is optimization only: cached material never grants authority and user/session output is never
reused as authoritative state.

### Prompt A/B evaluation

P8 compares `CURRENT_ACTIVE_PROMPT` and `CANDIDATE_PROMPT`, where feasible for each prompt-affecting role, on the same frozen semantic
bank, model/provider posture, decoding settings, and environment. Before either candidate run, freeze thresholds for semantic
correctness, schema validity, initial-pass rate, repair rate, fallback rate, invented-constraint rate, semantic-loss rate, latency, input
tokens, output tokens, cache eligibility, and provider-exposed cache hit/miss. Deterministic validation remains unchanged.

A candidate does not become active from one manual example or aggregate score alone. Activation requires row-level regression review,
governance/security non-regression, provenance-complete report, explicit approval, and rollback target. Infrastructure failures are
reported separately and do not count as semantic wins or losses.

## Commit choreography

Pre-fix red results stay in loop evidence. Every row below is an expected **green logical commit** and includes its own contract. A row
may collapse into an adjacent green row only with a recorded `DECISION_LOG` deviation.

| ID | PURPOSE | EXPECTED_FILES | DEPENDENCY | FOCUSED_GATE | BROADER_GATE | REBASE_REQUIREMENT |
|---|---|---|---|---|---|---|
| T1 | Versioned trace lifecycle vocabulary/tests | A trace modules/tests | P0 | Lifecycle matrix | P0 L2 | Initial SHA; rebase after P0.1 before L0/return |
| T2 | EvidenceState/RAG/outcome projection truth | A projection modules/tests | T1 | Evidence matrix | Trace L1/L2 | Latest integration SHA |
| T3 | Stable oracle/diagnostic separation | A schema tests/docs | T2 | Oracle schema tests | L0/L1/L2 | Latest integration SHA |
| S1 | Evolve semantic intent contract/tests | B semantic spec/tests | P0 | Contract tests | SPL L1 | Initial SHA; rebase after P0.1 before return |
| S2 | Bind Final RQC/source semantics | B authority/source files/tests | S1 | Binding tests | SPL L1/P0 L2 | Latest integration SHA |
| S3 | Preserve temporal/normalization dependencies | B compiler/postprocessor/tests | S2 | Shape tests | SPL L1 | Latest integration SHA |
| S4 | Expand fidelity/structural validation | B fidelity/validator tests | S3 | Negative tests | SPL L1/L2 | Latest integration SHA |
| S5 | Harden bounded repair | B fallback/repair tests | S4 | Attempt/payload tests | SPL L1/L2 | Latest integration SHA |
| S6 | Generalization/L2 semantic coverage | B-owned contract tests; C rows via queue | S5 | Adjacent cases | P0/expanded L2 | Latest integration SHA |
| PP1 | Freeze role posture/current prompt behavior | D role tests/evidence | P2 audit | Reachability tests | L0/L1 | After P2 merge |
| PP2 | Versioned role prompt contracts | D prompt/registry/tests | PP1 | Contract/hash tests | L1 | Latest integration SHA |
| PP3 | Narrow role prompts/remove conflicts | D files; B shared seam via queue | PP2 | Role prompt tests | L1/L2 | After B resolution |
| PP4 | Govern few-shot/negative banks | D assets/tests | PP3 | Asset/version tests | L1 | Latest integration SHA |
| PP5 | Cache-ready layout/provenance | D prompt/provenance/tests | PP4 | Hash/isolation tests | L0/L1 | Latest integration SHA |
| PP6 | Freeze active-vs-candidate eval contract | D/P8 eval schema/tests | PP5 | Eval self-tests | L1 | Latest integration SHA |
| E1 | Scaffold additional L2 journeys | C L2 bank only | P0 | Collection/P0 subset | L2 | Initial SHA; rebase after P0.1 before return |
| E2 | Activate stable trace/SPL/prompt rows | C L2 bank only | P1/P2/P4 | New rows | Full expanded L2 | Rebase after A/B/D |
| E3 | Close follow-up/RAG/remediation/degradation rows | C L2 bank only | E2 | Journey rows | L2/L2-slow | Latest integration SHA |
| R1 | Archive/provenance safe orphan assets | C tests/eval assets | P5 | Inventory checks | Collection | P5 SHA |
| R2 | Consolidate exact duplicates | C tests | R1 | Replacement tests | L0/L1/L2 | Latest integration SHA |
| R3 | Parameterize equivalent cases | C tests | R2 | Parameterized tests | L0/L1/L2 | Latest integration SHA |
| R4 | Classify deterministic/slow tiers | C test config/docs | R3 | Tier self-tests | Full suite | Latest integration SHA |
| U1 | Freeze production analyst safety journeys | E frontend tests | P5 | Component tests | Frontend test | P5 SHA |
| U2 | Expose governed SPL/review/HIL/degradation | E UI files/tests | U1 + protected approvals | Journey tests | Frontend test/build/RACES | Latest integration SHA |
| U3 | Expose approved prompt/trace observability | E UI/settings/tests | U2 + P4 | Observability tests | Frontend test/build | Latest integration SHA |
| L3-1 | Freeze semantic/prompt bank and thresholds | F eval bank/runner/tests | P5/P4 | Runner self-tests | L3 dry run | P5 SHA |
| L3-2 | Record active-vs-candidate evidence | F reports | L3-1 | Report validation | L3 + L2 regression | Exact candidate SHA |

## Phase re-entry and evidence invalidation

The DAG controls first eligibility; this section controls repair. A DONE phase is reopened explicitly when later evidence disproves its
contract. Never mutate a completed phase silently.

- P5 false trace projection -> reopen P1.
- P4 or P8 semantic-contract gap -> reopen P2.
- P8 prompt-specific failure with intact semantic contract -> reopen P4.
- P7 backend contract cannot represent truthful UI state -> reopen owning P1/P2/P4 seam.
- P9 candidate regression -> reopen owning phase, fix, invalidate downstream evidence, and rerun affected phases.

Every reopening records:

```text
REOPENED_PHASE:
TRIGGER:
INVALIDATED_EVIDENCE:
NEW_BASE_SHA:
OWNER:
DOWNSTREAM_PHASES_TO_RERUN:
```

The findings ledger row remains present and moves from `CLOSED` to `OPEN` or `NEEDS_REPROOF` with the reopening reference.

## Phase checklist

- [x] **P0 - Harness readiness baseline**
  - **STATUS:** DONE
  - **OWNER:** Historical P0 owners
  - **BASE_SHA:** `615069e6ca9cdb3d40b51d6a2f071346ecf3d6a2`
  - **DEPENDENCIES:** None for this plan.
  - **ALLOWED_FILES:** None; do not redo P0.
  - **PROTECTED_FILES:** All implementation files are out of scope for P0 replay.
  - **MISSION:** Establish the candidate from which remaining closure starts.
  - **WHY_THIS_EXISTS:** Earlier execution lacked a production-path harness for argument continuity, bounded rounds, failures, follow-ups, and semantic fail-closed behavior.
  - **DO:** Treat repository evidence and the four P0 commits as the frozen starting fact set.
  - **DO_NOT:** Reimplement, amend, or relabel P0.
  - **Verify:** Confirm HEAD descends from `615069e6` and the 13-case P0 file exists before starting a workstream.
  - **ACCEPTANCE_CRITERIA:** Coordination baseline recorded; live MCP OFF; P0 not reopened absent disproving evidence.
  - **STOP_CONDITIONS:** Any repository evidence contradicts the stated P0 facts.
  - **EXPECTED_COMMIT_GROUPS:** None.
  - **OUTPUT_REQUIRED:** Baseline entry in loop runner.
  - **NEXT_PHASE_UNLOCK:** P1, P2, and P3 scaffold.
  - **Evidence:** Verified at plan creation: branch and HEAD match; P0 test and readiness symbols exist.

- [ ] **P0.1 - Resolve the inherited RACES freeze failure before any L0 gate**
  - **STATUS:** TODO
  - **OWNER:** Integration owner / CODEX. Operator decides; no stream may decide this for itself.
  - **BASE_SHA:** Frozen `EXECUTION_INTEGRATION_SHA` recorded externally at implementation start.
  - **DEPENDENCIES:** P0. Blocks the L0 gate for P1, P4, P7, P9. Blocks nothing else — P1/P2/P3 start in parallel with it.
  - **ALLOWED_FILES:** `backend/app/tests/test_live_path_untouched_by_ec.py` (baseline SHA + audit comment only), after operator approval.
  - **PROTECTED_FILES:** Advancing `RACES_BASELINE_SHA` is itself a protected change.
  - **MISSION:** Turn a measured, inherited red gate into a recorded operator decision, so that no stream later reports it as its own regression.
  - **WHY_THIS_EXISTS:** Measured at `fe3548e4`: `test_races_freeze_files_unchanged_since_baseline` fails with offender
    `backend/app/orchestration/mcp_execution_gate.py`, from P0 commit `f1f523cd`, against `RACES_BASELINE_SHA = 86be6f9f`.
    Four phases require an L0 RACES gate and the plan forbids unexplained regressions. Without this item, every stream independently
    rediscovers the same failure, and the honest options are each individually forbidden: calling it "pre-existing" (banned by the stop
    conditions), advancing the baseline unilaterally (a protected change), or recording a red gate as green (banned).
  - **DO:** Execute two separately authorized actions. **A. READ-ONLY AUDIT / PROPOSAL:** reproduce the failure; inspect exactly
    `git show f1f523cd -- backend/app/orchestration/mcp_execution_gate.py`; produce `PROTECTED_DIFF_AUDIT`, `AUTHORITY_IMPACT`,
    `HIL_IMPACT`, `RBAC_IMPACT`, `AUTH0_IMPACT`, `EXECUTION_ELIGIBILITY_IMPACT`, `EC_IMPORT_IMPACT`, `ROLLBACK`, and
    `PROPOSED_BASELINE_DIFF`; then STOP. **B. APPLY:** only after a second, explicit operator approval for that exact diff, update the
    existing audit comment and advance `RACES_BASELINE_SHA` to `615069e6` and only to `615069e6`, commit the approved one-file change,
    run verification, and advance `EXECUTION_INTEGRATION_SHA` to the exact resulting P0.1 commit. Mark every already-active P1/P2/P3 branch
    `REBASE_REQUIRED = YES` to that new integration SHA before L0 evidence, branch return, reconciliation, or merge. If the audit finds
    weakened authority, do not propose advancement; return the product defect to the owning seam.
  - **DO_NOT:** Advance the baseline to `HEAD`; advance it without the audit comment; delete, skip, xfail, or narrow the freeze test;
    remove a prefix from `RACES_FREEZE_PATHS`; let any stream do this inside its own branch.
  - **Verify:** `cd backend && "$PYVENV" -m pytest -q app/tests/test_live_path_untouched_by_ec.py` -> `8 passed`.
    Confirm the detector still catches frozen paths (`test_races_freeze_detector_flags_frozen_paths_without_editing_them` green,
    not vacuous), and that `git diff --name-only 615069e6...HEAD` reports no protected path.
  - **ACCEPTANCE_CRITERIA:** Audit/proposal packet exists and stopped for approval; apply occurred only under a separate explicit
    approval; all 8 tests are green; baseline is `615069e6` with a written audit; `RACES_FREEZE_PATHS` is byte-unchanged; new
    new `EXECUTION_INTEGRATION_SHA` is recorded; every pre-P0.1 active stream is marked and rebased before L0/return/integration.
  - **STOP_CONDITIONS:** The `f1f523cd` audit finds weakened authority; operator withholds approval; the fix would need any other
    protected file; same gate fails twice.
  - **EXPECTED_COMMIT_GROUPS:** `chore(races): advance freeze baseline to 615069e6 with audit` — one commit, one file, approval reference in the body.
  - **OUTPUT_REQUIRED:** The nine named audit/proposal fields, explicit STOP record, separate apply approval reference, reproduction and
    post-fix output, old/new integration SHA, rebase-required list, and branch return packet.
  - **NEXT_PHASE_UNLOCK:** L0 RACES gate for P1, P4, P7, P9.
  - **Evidence:** Pending.

- [ ] **P1 - Trace truth closure**
  - **STATUS:** TODO
  - **OWNER:** Workstream A / CODEX
  - **BASE_SHA:** Frozen `EXECUTION_INTEGRATION_SHA`.
  - **DEPENDENCIES:** P0.
  - **ALLOWED_FILES:** A-owned trace/provenance modules and directly corresponding tests from the ownership matrix.
  - **PROTECTED_FILES:** `architecture.md` plus every enumerated `RACES_FREEZE_PATHS` prefix (see Protected-file policy). For A this most often means `backend/app/schemas/responses.py` when a new oracle field is needed — STOP and request the diff.
  - **MISSION:** Reproduce each suspected contradiction, then correct only factual/projection inconsistencies and freeze a stable oracle vocabulary.
  - **WHY_THIS_EXISTS:** Recent inspection found attempted-call versus used/live-call ambiguity, conflicting fallback labels, RAG skipped alongside obtained citation state, artifact review conflated with execution HIL, and pure SPL diagnostic projections that may look investigation-shaped.
  - **DO:** Trace real `/chat` paths for pure SPL, deterministic fallback, LLM attempt/failure/success, RAG no-match/match, MCP planned/unavailable/response, and HIL. Define versioned oracle states `PLANNED`, `ATTEMPTED`, `RESPONSE_RECEIVED`, `ACCEPTED`, `USED`, `FALLBACK`, `FAILED`, `SKIPPED`. Separate `artifact_review_required` from `execution_hil_required`. Keep diagnostic detail in explicitly non-oracle fields. Ensure EvidenceState only records accepted obtained evidence and pure SPL does not project `InvestigationOutcome` merely because diagnostics exist.
  - **DO_NOT:** Pin unstable timing/debug fields; infer evidence from plans; change execution policy; edit pipeline without the protected stop; force all sidecars into a single misleading boolean.
  - **Verify:** Focused trace/provenance/outcome suites; table-driven oracle tests for every vocabulary transition; P0 L2 bank; L0 RACES/freeze test. Re-run repros to prove each suspected issue fixed, already-correct, or explicitly not reproducible.
  - **ACCEPTANCE_CRITERIA:** One documented trace schema/version; no contradictory oracle combinations; artifact and execution review flags are distinct; EvidenceState truth tests pass; pure SPL has no fabricated investigation outcome; diagnostics remain observable without becoming contract assertions.
  - **STOP_CONDITIONS:** Required fix touches `pipeline.py` or another protected file; a vocabulary change breaks an external contract not owned by A; same gate fails twice.
  - **EXPECTED_COMMIT_GROUPS:** T1 -> T2 -> T3 from Commit choreography; red repros are loop evidence, not commits.
  - **OUTPUT_REQUIRED:** Repro matrix, schema/version decision, branch return packet, exact tests, unresolved protected diff if any.
  - **NEXT_PHASE_UNLOCK:** P5 trace-dependent L2 assertions and P7 trace UX contract.
  - **Evidence:** Pending.

- [ ] **P2 - SPL semantic V2 contract, authoring, fidelity, and syntax**
  - **STATUS:** TODO
  - **OWNER:** Workstream B / CURSOR
  - **BASE_SHA:** Frozen `EXECUTION_INTEGRATION_SHA`.
  - **DEPENDENCIES:** P0. Coordinate names with P1, but no file dependency.
  - **ALLOWED_FILES:** B-owned SPL modules, governed source-profile modules, validators, and directly corresponding tests.
  - **PROTECTED_FILES:** `architecture.md` plus every enumerated `RACES_FREEZE_PATHS` prefix (see Protected-file policy). For B this most often means `backend/app/safeguards/spl_validator.py`, `backend/app/schemas/responses.py`, and `backend/app/graph/resource_planner_graph.py` — all read-only here; STOP and request the diff.
  - **MISSION:** Evolve the existing `SplIntentSpec` into the single semantic SPL contract consumed from Final RQC, then make deterministic and LLM authoring preserve it and fail closed on semantic loss.
  - **WHY_THIS_EXISTS:** Three real failures exposed generic gaps: rolling distinct accounts over 10m, hourly failed-login trend over 24h, and password-change then login within 5m. The semantic audit found missing analytical windows, event sets, entity roles, distinct relationships, measures, grain, ordered sequences, max gap, analysis/output shape, normalization consumers, and prohibitions.
  - **DO:** Add typed optional concepts for `search_horizon`, analytical window kind/size, required event sets, entity roles, relationships, measures, temporal grain, ordered sequence/max gap, analysis shape (`raw`, `aggregation`, `ranking`, `trend`, `rolling`, `sequence`, `comparison`), output shape, normalization requirements/consumers, and prohibitions. Populate from Final RQC and explicit constraints with governed source mappings; manual/COE mappings win and other sources fill blanks only. Update existing compiler/authoring paths, semantic fidelity V2, and lightweight structural checks. Feed repair an immutable semantic contract, prior candidate, deterministic loss list, and bounded correction scope. Resolve `head 100`, mandatory aggregation, placeholder, template bias, generic coalesce, default 24h, truncation, and `streamstats` ordering conflicts by analysis shape. Test the three real failures plus adjacent unseen variants.
  - **DO_NOT:** Add a second planner, query-specific patches, complete Splunk grammar, downstream raw-query reinterpretation, silent defaults that contradict RQC, more than one repair, candidate execution, or blanket source capabilities.
  - **Verify:** Focused SPL contract/fidelity/compiler/postprocessor/source-profile suites; exact and adjacent-generalization cases for every supported shape; negative tests for unresolved source fields, unsupported comparison/sequence, lost time grain, lost ordering, unwanted truncation, and malformed structure; P0 L2 bank.
  - **ACCEPTANCE_CRITERIA:** Existing representation is versioned/evolved; all genuinely supported shapes preserve the immutable contract; unsupported shapes fail closed with analyst-readable reason; three repros and adjacent cases pass without query literals in production code; syntax checks catch structural hazards without claiming full grammar coverage; one proposal plus at most one repair is enforced.
  - **STOP_CONDITIONS:** Final RQC cannot supply a required field without protected pipeline work; source authority precedence is ambiguous; new planner is proposed; a shape requires unapproved product capability; same gate fails twice.
  - **EXPECTED_COMMIT_GROUPS:** S1 -> S2 -> S3 -> S4 -> S5 -> S6 from Commit choreography; red repros are loop evidence.
  - **OUTPUT_REQUIRED:** Contract field table, support/degrade matrix by shape, prompt conflict resolution record, branch return packet, exact tests.
  - **NEXT_PHASE_UNLOCK:** P4 implementation, P5 semantic L2 assertions, P8 L3 bank.
  - **Evidence:** Pending.

- [ ] **P3 - L2 production bank scaffold from 13 toward 23**
  - **STATUS:** TODO
  - **OWNER:** Workstream C / CLAUDE
  - **BASE_SHA:** Frozen `EXECUTION_INTEGRATION_SHA`.
  - **DEPENDENCIES:** P0 for scaffold; P1/P2/P4 for assertions against new contracts.
  - **ALLOWED_FILES:** C-owned L2 bank/test files only. No runtime code.
  - **PROTECTED_FILES:** All runtime code, plus `architecture.md` and every enumerated `RACES_FREEZE_PATHS` prefix. C writes tests only.
  - **MISSION:** Define the first architecture-bearing approximately 23-case mocked production `/chat` bank, preserving the 13 P0 cases and making contract-dependent rows explicitly pending until their provider phases merge.
  - **WHY_THIS_EXISTS:** The P0 harness proved 13 critical paths, while the prior L2 audit identified gaps in complex SPL fidelity, RAG SOP/no-match, remediation lifecycle, follow-ups, and production degradation. Jumping to 80-120 rows before contracts stabilize would create noise and brittle assertions.
  - **DO:** Create a case manifest with invariant owner, required phase, mocks, expected stable-oracle fields, prohibited outputs, and tier. Add immediately supported RAG match/no-match, remediation offer/accept/reject or nearest supported lifecycle, and follow-up forms. Reserve contract-dependent rows for rolling/trend/sequence and trace vocabulary. Mark contradictory-evidence adjudication and comparison/historical behavior conditional unless product support is proven. Assert stable oracle and analyst-visible outcomes, not diagnostic ordering/timestamps.
  - **DO_NOT:** Modify runtime to satisfy a row; fabricate support; duplicate P0 rows without a new invariant; assert speculative P1/P2 fields; expand to 80-120 before the first bank is green.
  - **Verify:** Bank schema/unit collection, P0 13 unchanged, immediately supported new rows green, pending rows fail collection if accidentally treated as active, duplicate-invariant review.
  - **ACCEPTANCE_CRITERIA:** Approximately 23 intentional rows are catalogued; every row owns a distinct invariant; 13 remain green; unsupported/conditional rows are explicit; no runtime files changed.
  - **STOP_CONDITIONS:** A desired row needs product support not in P1/P2/P4; stable contract name is unavailable; C would need to edit runtime or another stream's tests.
  - **EXPECTED_COMMIT_GROUPS:** E1 from Commit choreography; E2/E3 occur in P5 after rebase.
  - **OUTPUT_REQUIRED:** Case matrix, pending dependency list, branch return packet, exact collection/test result.
  - **NEXT_PHASE_UNLOCK:** P5 after rebase onto merged P1/P2/P4.
  - **Evidence:** Pending.

- [ ] **P4 - Prompt, role policy, provenance, and Studio configuration contract**
  - **STATUS:** TODO
  - **OWNER:** Workstream D / CLAUDE; B remains owner of `backend/app/spl/llm_fallback.py`.
  - **BASE_SHA:** Integration SHA after P2 merge for implementation. Read-only audit may start at P0.
  - **DEPENDENCIES:** P0 for audit; P2 contract for writes and final prompt semantics.
  - **ALLOWED_FILES:** D-owned generic LLM prompt/role/settings modules and tests. Requirements for B-owned SPL prompt go through reconciliation.
  - **PROTECTED_FILES:** `architecture.md` plus every enumerated `RACES_FREEZE_PATHS` prefix (see Protected-file policy), plus all B-owned SPL files (requirements go through `RECONCILIATION_QUEUE`).
  - **MISSION:** Make every live role's policy posture intentional, remove prompt-policy contradictions, record prompt provenance, and define a governed Prompt & Policy Studio configuration model without silently activating dormant reasoners.
  - **WHY_THIS_EXISTS:** Current prompts can conflict on truncation, aggregation, placeholders, source normalization, and time. `mitre_reasoner`, `missing_evidence_reasoner`, `risk_rationale_reasoner`, and `plan_delta_reasoner` are blocked by an intentional allowlist; their posture must be decided, not accidentally changed. Operators also need version/hash/config provenance.
  - **DO:** Complete every field in the Prompt engineering contract for all 24 minimum roles plus every additional repository call site.
    Reconcile aliases without hiding distinct prompts. Record an explicit posture decision for `mitre_reasoner`,
    `missing_evidence_reasoner`, `risk_rationale_reasoner`, and `plan_delta_reasoner`: remain blocked, shadow-only, or separately
    operator-approved future activation. Implement narrow role-specific prompt contracts, governed few-shot and negative-example assets,
    stable-prefix/dynamic-suffix hashing and cache provenance, and the active-versus-candidate evaluation contract. Review shape advisor
    authority/schema. Define Studio backend config with draft validation, allowlisted fields, RBAC/admin guard, redaction, size limits,
    audit history, activation/rollback, and no secret echo. Send SPL prompt requirements to B and verify B's resolution.
  - **DO_NOT:** Enable a reasoner silently; grant tool calling; make shape advice authoritative; expose secrets; add unauthenticated writes; edit `llm_fallback.py`; build Studio UI in this phase.
  - **Verify:** Role reachability/allowlist tests; 24-role-or-larger inventory completeness check; prompt/schema/few-shot/negative-bank
    hash determinism; stable-prefix isolation and cache invalidation tests; config validation/redaction/auth/rollback tests; prompt A/B runner
    contract self-tests; SPL prompt reconciliation review; L0 trust-boundary checks; P0 L2 bank.
  - **ACCEPTANCE_CRITERIA:** Every reachable/dormant role has all required contract fields and a tested posture; no monolithic prompt;
    named reasoners remain blocked unless separately approved; narrow SPL generation/repair payloads and one-repair bound are proven;
    few-shot/negative governance, cache-ready layout, trace provenance, A/B contract, and Studio model are deterministic, redacted, and
    authority-neutral; no direct LLM authority or MCP access.
  - **STOP_CONDITIONS:** Activation is required without operator approval; persistence/auth architecture is ambiguous; SPL prompt change is attempted outside B; protected path is required.
  - **EXPECTED_COMMIT_GROUPS:** PP1 -> PP2 -> PP3 -> PP4 -> PP5 -> PP6 from Commit choreography.
  - **OUTPUT_REQUIRED:** Role/posture table, prompt provenance schema, Studio config/permission model, reconciliation request/result, branch packet.
  - **NEXT_PHASE_UNLOCK:** P5 prompt-aware L2 rows, P7 Studio UI if approved in scope, P8 live prompt metrics.
  - **Evidence:** Pending.

- [ ] **P5 - Cross-stream reconciliation and approximately 23-case L2 closure**
  - **STATUS:** TODO
  - **OWNER:** Integration owner / CODEX with C as L2 bank owner.
  - **BASE_SHA:** Integration SHA containing P1, P2, and P4; C rebases onto it.
  - **DEPENDENCIES:** P1, P2, P3 scaffold, P4.
  - **ALLOWED_FILES:** C-owned L2 bank, owning-stream tests, and integration conflict resolutions approved by seam owner.
  - **PROTECTED_FILES:** All protected paths retain STOP governance.
  - **MISSION:** Reconcile stable trace, semantic SPL, and prompt-policy contracts into the first green architecture-defining production bank.
  - **WHY_THIS_EXISTS:** Parallel branches are useful only if their contracts compose on the real production path. This gate prevents isolated green unit tests from masking analyst-visible mismatch.
  - **DO:** Merge in declared order, rebase C, activate only rows whose capabilities now exist, run P0 plus approximately 23 L2 cases, classify conditional comparison/contradiction rows, and verify remediation/follow-up/degradation paths. Resolve shared seams through their owner. Record all contract changes and exact candidate SHA.
  - **DO_NOT:** Use last-writer-wins, weaken expected outcomes, edit runtime from C, mark unsupported product behavior green, or advance protected baselines.
  - **Verify:** Full expanded L2 bank, affected P1/P2/P4 L0/L1 suites, P0 13 subset, relevant L2-slow cases, harness independence command.
  - **ACCEPTANCE_CRITERIA:** P0 13 and all activated new rows green; each remaining conditional row has an owner/decision; no cross-stream contract mismatch; exact integration SHA recorded.
  - **STOP_CONDITIONS:** Unresolved ownership conflict; protected integration change; speculative field dependency; unexplained regression; same integration gate fails twice.
  - **EXPECTED_COMMIT_GROUPS:** E2 -> E3 from Commit choreography; optional seam-owner fixes return to and are committed by that owner.
  - **OUTPUT_REQUIRED:** Merge/rebase log, final case matrix, branch packets, tests, known failures, new integration SHA.
  - **NEXT_PHASE_UNLOCK:** P6, P7, and P8.
  - **Evidence:** Pending.

- [ ] **P6 - Conservative test rationalization and tiering**
  - **STATUS:** TODO
  - **OWNER:** Workstream C / CLAUDE
  - **BASE_SHA:** P5 green integration SHA.
  - **DEPENDENCIES:** P5.
  - **ALLOWED_FILES:** Test files/config/inventory only; runtime changes require handback to owning stream.
  - **PROTECTED_FILES:** RACES tests/baselines and product files unless separately approved; security/governance/adversarial tests are preservation-biased.
  - **MISSION:** Reduce maintenance cost without losing invariant coverage, targeting moderate movement toward approximately 4,850 test functions only where evidence supports it.
  - **WHY_THIS_EXISTS:** The prior audit found approximately 5,290 tests and under-parameterization, not indiscriminate excess. Current inventory is slightly larger. Safe gains come from housekeeping and equivalent case consolidation after L2 is stable.
  - **DO:** Wave 1 remove dead collection artifacts/duplicates only with proof. Wave 2 parameterize truly equivalent setup/assertion families. Wave 3 mark/move timeout/subprocess tests to L2-slow and document tier commands. For every retirement record old test ID, old invariant, replacement owner/test, green proof, and risk statement. Preserve failure diagnostics and case IDs.
  - **DO_NOT:** Chase the numeric target; delete security/governance/adversarial coverage; combine tests with materially different failure meaning; tier away required promotion coverage; refresh eval baselines incidentally.
  - **Verify:** Collection before/after diff, retirement ledger, replacement tests green, L0/L1/L2/L2-slow tier commands, full backend collection and phase-level full suite.
  - **ACCEPTANCE_CRITERIA:** Every removed test has the four-part retirement record; all preserved invariants are green; tier commands are deterministic; reduction is moderate and justified even if final count remains above 4,850.
  - **STOP_CONDITIONS:** Replacement ownership is unclear; failure diagnostics degrade; a proposed deletion changes an invariant; expanded L2 is not green; same gate fails twice.
  - **EXPECTED_COMMIT_GROUPS:** R1 -> R2 -> R3 -> R4 from Commit choreography.
  - **OUTPUT_REQUIRED:** Before/after inventory, retirement ledger, tier matrix, branch packet, exact tests.
  - **NEXT_PHASE_UNLOCK:** P9 promotion full-suite comparison.
  - **Evidence:** Pending.

- [ ] **P7 - Production UI and trace/operator UX**
  - **STATUS:** TODO
  - **OWNER:** Workstream E / CURSOR
  - **BASE_SHA:** P5 green integration SHA; rebase after any backend contract movement.
  - **DEPENDENCIES:** P1, P2, P4, P5.
  - **ALLOWED_FILES:** E-owned production non-EC frontend components/hooks/types/tests and approved settings surfaces.
  - **PROTECTED_FILES:** `architecture.md` plus every enumerated `RACES_FREEZE_PATHS` prefix (see Protected-file policy). `frontend/src/components/ChatPanel.tsx` is the one E will most likely need — STOP with an exact diff before wiring it. EC components remain isolated and are not a production shortcut.
  - **MISSION:** Give analysts and operators truthful production surfaces for SPL review, semantic failure, execution decisions, investigation progress, remediation, degradation, and trace provenance.
  - **WHY_THIS_EXISTS:** P0 and backend contracts can be correct while production users still cannot distinguish candidate review from execution HIL, inspect semantic loss, or recover from unavailable capabilities. EC parity is not proof of production UX.
  - **DO:** Test and implement production surfaces for candidate SPL review; semantic warning/fail-closed reason; **Approve / Edit / Cancel** with clear candidate-versus-approved state (use exactly this vocabulary — `architecture.md:512` mandates "Approve / Edit / Cancel" before any write; do not invent a "Run" control); separate artifact review and execution HIL; bounded progress; remediation offer/status; RAG/LLM/MCP degradation; stable trace oracle with diagnostics collapsed; prompt/config provenance where appropriate. Keep controls feature-complete and accessible. If wiring requires `ChatPanel.tsx`, stop with exact proposed diff first.
  - **DO_NOT:** Reuse EC state as production authority; expose secrets/raw prompts; imply MCP ran when planned/unavailable; enable execution flags; show empty InvestigationOutcome for pure SPL; edit protected paths without approval.
  - **Verify:** Focused component tests for each state; frontend full test/build; browser checks at desktop/mobile for overflow, action states, progress, and error recovery; RACES/freeze gate; production API contract fixtures from P5.
  - **ACCEPTANCE_CRITERIA:** All listed states are reachable and truthful; Approve/Edit/Cancel/HIL semantics match backend authority; degradation is actionable; trace oracle is visible without brittle diagnostics; EC remains isolated; frontend tests/build green.
  - **STOP_CONDITIONS:** Protected path is required; backend contract is insufficient; UI would infer authority from diagnostics; same frontend gate fails twice.
  - **EXPECTED_COMMIT_GROUPS:** U1 -> U2 -> U3 from Commit choreography.
  - **OUTPUT_REQUIRED:** State/journey matrix, screenshots or browser evidence, protected diff request if needed, branch packet.
  - **NEXT_PHASE_UNLOCK:** P9 production UX promotion gate.
  - **Evidence:** Pending.

- [ ] **P8 - L3 live local LLM semantic evaluation**
  - **STATUS:** TODO
  - **OWNER:** Workstream F / CODEX, with B/D reviewing semantic and prompt metrics.
  - **BASE_SHA:** P5 green integration SHA; use exact configured local candidate.
  - **DEPENDENCIES:** P2, P4, P5. Independent of P7 file ownership.
  - **ALLOWED_FILES:** New/owned L3 eval bank, runner, and evidence reports; defects return to B or D.
  - **PROTECTED_FILES:** Product runtime and protected paths; no evaluator-driven policy mutation.
  - **MISSION:** Freeze and execute a live local LLM semantic bank for simple SPL, rolling, trend, sequence, raw events, ranking, T4, follow-up, and composer behavior.
  - **WHY_THIS_EXISTS:** Mocked L2 proves orchestration and contracts but not model adherence, repair behavior, latency, schema reliability, or semantic intent preservation on Foundation-Sec/T4-class serving.
  - **DO:** Define immutable rows and expected semantic constraints; record model/provider/prompt/config hashes and timeouts; compare
    `CURRENT_ACTIVE_PROMPT` versus `CANDIDATE_PROMPT` on the same frozen bank wherever feasible. Freeze thresholds first. Measure
    semantic correctness, schema validity, initial-pass rate, repair rate, fallback rate, invented-constraint rate, semantic-loss rate,
    latency, input/output tokens, cache eligibility, and provider-exposed cache hit/miss. Keep one-proposal/one-repair accounting and
    separate infrastructure unavailability from semantic failure.
  - **DO_NOT:** Loosen thresholds after results; count deterministic fallback as model success; call Cisco/VPS merely to iterate prompts; include live MCP; mutate runtime from the eval branch.
  - **Verify:** Runner self-tests, frozen-bank hash, repeated live run sufficient to expose variance, machine-readable and human-readable report, L2 regression after any owning-stream fix.
  - **ACCEPTANCE_CRITERIA:** Every category has representative rows; active and candidate prompts use the same frozen inputs and
    posture; metrics are reproducible and provenance-complete; thresholds predate results; no deterministic threshold was loosened;
    activation requires row-level non-regression and explicit approval; failures are assigned or explicitly accepted, never hidden.
  - **STOP_CONDITIONS:** No approved/configured local LLM endpoint; prompt/config provenance missing; evaluator defect; threshold change requested after seeing results; same gate fails twice.
  - **EXPECTED_COMMIT_GROUPS:** L3-1 -> L3-2 from Commit choreography.
  - **OUTPUT_REQUIRED:** Bank hash, environment/provenance, metrics report, failure ledger, branch packet.
  - **NEXT_PHASE_UNLOCK:** P9 L3 promotion decision.
  - **Evidence:** Pending.

- [ ] **P9 - Promotion governance and residual failure adjudication**
  - **STATUS:** TODO
  - **OWNER:** Workstream F / integration CODEX
  - **BASE_SHA:** Candidate integration SHA containing P6, P7, and P8 outcomes.
  - **DEPENDENCIES:** P6, P7, P8.
  - **ALLOWED_FILES:** Promotion evidence, eval reports, plan/loop status; defects return to owning stream.
  - **PROTECTED_FILES:** `architecture.md` plus every enumerated `RACES_FREEZE_PATHS` prefix (see Protected-file policy); advancing any baseline requires protected approval.
  - **MISSION:** Prove one exact candidate SHA on Mac and isolated Linux, carrying every residual by exact test identity and promotion decision.
  - **WHY_THIS_EXISTS:** Prior full-suite runs contained named PostgreSQL, migration, GitHub skill clone, routing, and RACES-environment/state failures. Counts alone cannot distinguish regressions, and production GO remains deferred.
  - **DO:** Build a residual ledger with test name, baseline result, candidate result, classification, environment dependency, owner, evidence, and promotion decision. Include `rt.para.011`, GitHub skill clone root failure, PostgreSQL integration failures, migration/plugin environment failures, RACES baseline state, and any branch-pre-existing failure. Run Mac full backend, frontend test/build, RACES, architecture freeze, routing truth set, 105-path, Stage 3 governance, harness independence, and exact-SHA isolated Linux validation. Resolve or explicitly block unexplained deltas.
  - **DO_NOT:** Call residuals generically pre-existing; compare counts only; substitute plain pytest for governance; omit blocked governance steps; refresh baselines; push/merge/deploy; enable live MCP.
  - **Verify:** Named gate matrix completed with command, environment, SHA, result, artifacts, and named residual comparison. Re-audit every inherited DONE item against its Verify field.
  - **ACCEPTANCE_CRITERIA:** Zero unexplained regression; all gates green or explicitly operator-adjudicated by named residual; Mac and Linux use the same candidate SHA; architecture unchanged; live MCP OFF; final candidate SHA frozen.
  - **STOP_CONDITIONS:** Any unexplained regression; environment cannot execute a mandatory gate; protected baseline advance needed; Mac/Linux SHA differs; same gate fails twice.
  - **EXPECTED_COMMIT_GROUPS:** `docs(promotion): record exact-sha gate and residual evidence`; owning-stream fixes are separate commits before rerun.
  - **OUTPUT_REQUIRED:** Complete residual ledger, gate matrix, exact final candidate SHA, operator GO/NO-GO recommendation, branch packet.
  - **NEXT_PHASE_UNLOCK:** P10 only on operator-accepted GO.
  - **Evidence:** Pending.

- [ ] **P10 - PR and merge handoff**
  - **STATUS:** TODO
  - **OWNER:** Integration CODEX prepares; operator authorizes network actions and merge.
  - **BASE_SHA:** P9 final candidate SHA.
  - **DEPENDENCIES:** P9 GO.
  - **ALLOWED_FILES:** PR description/release evidence if needed; no new product behavior.
  - **PROTECTED_FILES:** All product/protected files unless promotion is reopened.
  - **MISSION:** Prepare a reviewable, ordered PR/merge packet without direct push or merge from any working stream.
  - **WHY_THIS_EXISTS:** Parallel implementation requires one reconciled history and explicit promotion evidence; stream-level pushes or merges bypass cross-contract verification.
  - **DO:** Confirm worktree cleanliness except declared unrelated files; list commits by stream; verify merge order A, B, D, C-bank, C-rationalization, F-L3, E-UI, F-promotion; prepare PR summary, tests, residuals, protected approvals, rollback, and post-merge exact-SHA validation commands. Wait for operator approval before push/PR/merge.
  - **DO_NOT:** Push, open PR, merge, deploy, squash away required evidence, or add fixes after the final gate without reopening P9.
  - **Verify:** `git diff`/history review, branch packets complete, candidate SHA equals P9, no unapproved file, operator review recorded.
  - **ACCEPTANCE_CRITERIA:** Handoff is complete and reproducible; operator can perform network actions; no implementation follows the frozen candidate without re-promotion.
  - **STOP_CONDITIONS:** Missing packet/evidence; candidate drift; operator has not approved network action; merge conflict changes behavior.
  - **EXPECTED_COMMIT_GROUPS:** None after P9 unless documentation-only handoff was predeclared and revalidated.
  - **OUTPUT_REQUIRED:** PR/merge packet and exact commands; explicit STOP awaiting operator.
  - **NEXT_PHASE_UNLOCK:** P11 only after approved merge/promotion and separate COE authorization.
  - **Evidence:** Pending.

- [ ] **P11 - Live Splunk MCP COE, last and separately approved**
  - **STATUS:** DEFERRED
  - **OWNER:** Workstream F / operator-led COE with CODEX evidence recorder.
  - **BASE_SHA:** Approved merged/promoted exact SHA from P10, synchronized on COE.
  - **DEPENDENCIES:** P10 operator-approved completion plus separate live-MCP authorization.
  - **ALLOWED_FILES:** COE evidence and separately approved configuration only; any code defect returns through a new branch and P9.
  - **PROTECTED_FILES:** Secrets, production config, architecture, runtime behavior, and execution flags without explicit operator action.
  - **MISSION:** Verify the real Splunk MCP contract and one bounded real investigation only after every prior gate.
  - **WHY_THIS_EXISTS:** Mock transport and metadata contracts exist, but endpoint/path, protocol, authentication, real tool schemas, chronology, grant lifecycle, and real empty/error behavior remain unverified.
  - **DO:** Keep flags OFF while verifying endpoint/path, protocol/version, TLS, auth mechanism without exposing credentials, redacted discovery, exact tool names/input/output schemas, chronology, grant/HIL lifecycle, timeout/cancel, empty result, server error, malformed response, and audit correlation. Then obtain operator approval for bounded flags and run one full real investigation with approved normalized SPL only. Disable flags afterward unless an explicit ongoing decision says otherwise.
  - **DO_NOT:** Use candidate SPL, let LLM call MCP, enable globally before schema proof, print secrets, use SAIA/write/admin tools, treat schema discovery as investigation success, or bypass HIL.
  - **Verify:** LIVE-MCP protocol checklist, redacted schema capture, negative lifecycle cases, one full investigation trace proving `PLANNED -> ATTEMPTED -> RESPONSE_RECEIVED -> ACCEPTED -> USED` only when factual, cleanup/flag posture check.
  - **ACCEPTANCE_CRITERIA:** `REAL_SCHEMA_UNVERIFIED` is replaced by exact verified evidence; auth/grant/chronology/error behavior pass; one bounded real investigation completes truthfully; no secret exposure; post-run flag posture recorded.
  - **STOP_CONDITIONS:** Any schema/auth mismatch, ambiguous tool authority, secret exposure risk, chronology/grant defect, unapproved flag change, candidate SHA drift, or same gate fails twice.
  - **EXPECTED_COMMIT_GROUPS:** Evidence-only commit if pre-approved; code fixes require a new implementation/promotion cycle.
  - **OUTPUT_REQUIRED:** Redacted COE report, exact SHA/config posture, tool schema hashes, lifecycle traces, incident/cleanup notes, final GO/NO-GO.
  - **NEXT_PHASE_UNLOCK:** None. Production GO remains a separate operator decision.
  - **Evidence:** Deferred pending all gates and authorization.

## First parallel start set

After the operator freezes and records one `EXECUTION_INTEGRATION_SHA`:

0. Each stream exports `PYVENV` (see the interpreter note in the test gate matrix) and confirms `git rev-parse HEAD` equals the frozen `EXECUTION_INTEGRATION_SHA`.
1. Start P0.1 on the integration owner, and P1 on A, P2 on B, P3 scaffold on C from that exact SHA. P0.1 runs alongside them; it blocks only their L0 RACES gates, not their work.
2. D may run a read-only role/posture audit, but must not make contract-dependent edits until P2 merges.
3. Do not start E or live evaluation. Do not create F's COE environment.
4. If P3 needs a field not yet merged, record the row as pending instead of guessing.

## Reconciliation and merge order

0. P0.1 RACES baseline advance, as soon as it is approved — before any stream records an L0 gate.
1. A TRACE, after P1 gates.
2. B SPL, rebased onto the new integration SHA and cross-tested with P1.
3. D POLICY, implemented/rebased after B; B resolves the shared SPL prompt seam.
4. C EVAL bank, rebased after A/B/D; complete P5.
5. C test rationalization after P5, never before.
6. F L3 evaluation artifacts and any separately promoted owning-stream fixes.
7. E UI after backend contracts; protected changes require approval before this merge.
8. F promotion evidence freezes the final candidate.
9. P10 operator handoff. No stream pushes or merges itself.
10. P11 live MCP only after approved promotion/merge and separate COE authorization.

## Residual failure ledger seed

P9 must remeasure by exact test ID. These are carried as hypotheses from prior measured baselines, not automatically accepted outcomes:

| Residual | Baseline evidence | Candidate requirement | Initial classification | Promotion rule |
|---|---|---|---|---|
| `rt.para.011` routing truth row | Known residual after empty-shell cull | Record exact current result and layer; no silent baseline refresh | Branch-pre-existing routing issue | Explicit accept/fix decision; no unexplained delta |
| `test_github_skill_expansion_factory_baseline.py::test_factory_generators_check_against_committed_artifacts` | Missing `AI_SOC_GITHUB_SKILL_CLONE_ROOT` clone on Mac | Run with valid clone or record exact operator/environment block | Environment dependency | Governance cannot be called green while omitted |
| `integration/test_canonical_retention_purge.py` family | 11 PostgreSQL-dependent failures in earlier full run | Compare exact IDs under available PostgreSQL | Environment dependency | Green in required env or explicit promotion block |
| `integration/test_handoff_postgres.py` family | 2 PostgreSQL-dependent failures | Same | Environment dependency | Same |
| `integration/test_telemetry_postgres.py` | 1 PostgreSQL-dependent failure | Same | Environment dependency | Same |
| `test_migration_readiness.py` family | 5 DB/migration-dependent failures | Compare exact IDs; include plugin/migration environment details | Environment dependency | Green in required env or explicit block |
| `test_live_path_untouched_by_ec.py::test_races_freeze_files_unchanged_since_baseline` | **Measured red at `fe3548e4`**: offender `backend/app/orchestration/mcp_execution_gate.py` from P0 `f1f523cd` vs `RACES_BASELINE_SHA = 86be6f9f` | Expected already resolved by P0.1; remeasure and confirm `8 passed`. If still red, P9 cannot proceed | Inherited, adjudicated in P0.1 | Green after the P0.1 approved baseline advance, or explicit operator block |
| Any newly observed plugin/environment failure | Unknown until P9 | Add exact test, baseline/candidate, dependency, evidence | Unclassified | Must be classified and adjudicated before GO |

## Plan/loop runner consistency self-test

Run this checklist after every structural plan edit and before operator review:

- [x] SHA roles: both files preserve `PLAN_PREPARATION_SHA = fe3548e4`, leave `EXECUTION_INTEGRATION_SHA` operator-frozen, and never require a plan to contain its own commit SHA.
- [x] Phase status: P0 DONE, P0.1-P10 TODO, P11 DEFERRED, and no active implementation stream.
- [x] Dependencies: authoritative edge list and runner eligibility rules agree.
- [x] Merge order: P0.1 apply first if approved, then A, B, D, C/P5, C/P6, F/P8, E/P7, F/P9.
- [x] Protected queue: empty; P0.1 audit/proposal has not run and no apply approval exists.
- [x] Current loop: `NONE`; `LOOP_ITERATION_ID = NONE`.
- [x] Rebase rule: every pre-P0.1 stream must rebase to the exact post-P0.1 integration SHA before L0/return/integration.
- [x] Live MCP posture: disabled/deferred until P11 plus separate approval.

If any row disagrees, set `READY_FOR_OPERATOR_REVIEW = NO`, correct both files, and rerun the plan audit.

## Plan self-audit

| Risk | Result |
|---|---|
| Circular dependencies | PASS: DAG is acyclic; P11 is terminal. |
| Dual file ownership | PASS: SPL live prompt belongs to B; frontend types belong to E; C owns only bank/test architecture. |
| Protected mutation | PASS: protected paths have no owner and require exact diff plus approval. |
| Implementation before dependency | PASS: D writes wait for P2; P5 waits for A/B/D; rationalization waits for green L2; UI/L3 wait for contracts. |
| Test retirement before replacement | PASS: P6 requires invariant, replacement owner, green proof, and risk. |
| Live MCP too early | PASS: default-off through P10; P11 requires separate approval. |
| Architecture edits | PASS: read-only in every phase. |
| Push/merge before promotion | PASS: streams never push/merge; P10 is handoff after P9. |
| Eval depends on unimplemented fields | PASS: P3 rows carry dependencies and remain pending; P5 activates after merge. |
| Brittle trace assertions | PASS: P1 defines stable oracle versus diagnostics; C asserts oracle only. |
| Second planner | PASS: P2 evolves the existing `build_spl_intent_spec()` representation from Final RQC; no `SplIntentSpec` class is invented. |
| Start SHA is readable by its own agents | PASS: the operator freezes the final reviewed plan commit externally and every first-wave branch uses it. |
| Protected set is enumerable, not described | PASS after review: the eleven `RACES_FREEZE_PATHS` prefixes are listed verbatim and cross-checked against the ownership matrix. |
| Owner assigned a protected file | PASS after review: `safeguards/spl_validator.py` and `schemas/responses.py` removed from B's allowed paths and marked protected. |
| Gate state represented honestly | PASS: inherited RACES red is explicit; P0.1 is operator-gated and blocks L0 claims without blocking early work. |
| Commands runnable in a worktree | PASS after review: `../.venv/bin/python` replaced by an absolute `$PYVENV`, since `.venv/` is gitignored and absent from new worktrees. |
| Commit discipline stated | PASS after review: see the commit guidance section. |
| PROMPT_CACHE_READY | PASS: stable-prefix/dynamic-suffix, invalidation, provenance, and authority isolation are specified. |
| FEW_SHOT_GOVERNANCE | PASS: shape-based versioned assets and hash invalidation are required. |
| NEGATIVE_EXAMPLE_GOVERNANCE | PASS: generic failure classes and version/hash rules are required. |
| PROMPT_AB_EVAL | PASS: active-versus-candidate frozen-bank metrics and pre-frozen thresholds are required in P8. |
| FINDINGS_LEDGER_COMPLETE | PASS: append-only 81-row ledger covers every correction-mission category and historic gap. |
| LOOP_ITERATION_SCHEMA | PASS: runner records all required iteration fields and classifications. |
| PHASE_REENTRY_SUPPORTED | PASS: trigger, invalidation, new base, owner, and rerun fields are specified. |
| START_SHA_CONSISTENT | PASS: first wave starts from one externally frozen `EXECUTION_INTEGRATION_SHA`; `fe3548e4` is preparation history and `615069e6` is product baseline only. |
| P0_1_REBASE_RULE | PASS: pre-P0.1 branches rebase to exact post-P0.1 integration SHA before L0/return/integration. |
| COMMIT_POLICY_CONSISTENT | PASS: red reproduction is iteration evidence; only bounded green contracts are committed. |
| COMMIT_SEQUENCE_EXPLICIT | PASS: T1-T3, S1-S6, PP1-PP6, E1-E3, R1-R4, U1-U3, and L3-1/L3-2 have files/dependencies/gates/rebase rules. |
| PLAN_LOOP_RUNNER_CONSISTENT | PASS: explicit cross-check covers SHA, status, dependencies, merge/protected queues, loop, rebase, and MCP. |

## Drift log and evidence discipline

- 2026-08-25: Mission estimate 5,290 tests/684 files measured as approximately 5,313 test functions/688 files. Plan retains the moderate rationalization conclusion and treats counts as targets, not acceptance criteria.
- 2026-08-25: General repo convention says list plans in `plans/README.md`, but this mission explicitly authorizes writes only to the new master plan and loop runner. README update is intentionally excluded and must not be smuggled into the plan-only commit.
- Every checked item must contain command/result evidence and exact SHA. Re-audit inherited checkmarks before P9; written code alone is never evidence.
- 2026-08-25 (plan review): six defects corrected before execution. (1) The product baseline and plan preparation SHA were separated;
  final cleanup removes the self-referential literal start SHA and requires an externally frozen `EXECUTION_INTEGRATION_SHA`.
  (2) `RACES_FREEZE_PATHS` enumerated verbatim; it is eleven mostly-backend prefixes, not "frontend RACES paths".
  (3) `backend/app/safeguards/spl_validator.py` and `backend/app/schemas/responses.py` withdrawn from workstream B's allowed paths —
  both are protected. (4) The RACES freeze gate is measured **red** at the coordination base from P0 `f1f523cd`; new item P0.1 adjudicates it.
  (5) `../.venv/bin/python` replaced by absolute `$PYVENV` because `.venv/` is gitignored and missing from every new worktree.
  (6) P7's "Run/Edit/Cancel" corrected to the `architecture.md:512` vocabulary "Approve / Edit / Cancel". Also: `SplIntentSpec` documented
  as a dict-returning function rather than a class, `spl_artifact_trace_projection.py` assigned to A, and the dependency DAG given an
  authoritative edge list because the ASCII drawing did not render the P6 -> P9 edge legibly.
- Wrong premise, redundant item, changed contract, or scope expansion goes to `DECISION_LOG` and pauses dependent work.

## Plan completion definition

The plan is complete only when P0.1 and P1-P10 are DONE with evidence and P11 is either DONE after separate authorization or remains explicitly DEFERRED with production GO withheld. This document's creation does not authorize implementation, worktrees, pushes, merges, deployment, live LLM calls, or live MCP.
