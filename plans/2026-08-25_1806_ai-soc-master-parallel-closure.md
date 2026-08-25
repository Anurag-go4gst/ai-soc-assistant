---
title: AI-SOC master parallel closure
created: 2026-08-25 18:06 Asia/Kolkata
status: draft_operator_review
canonical_plan: plans/2026-08-25_1806_ai-soc-master-parallel-closure.md
loop_runner: plans/LOOP_RUNNER_ai-soc-master-parallel-closure.md
coordination_branch: feat/complete-or-abstain-t4-ux
coordination_base_sha: 615069e6ca9cdb3d40b51d6a2f071346ecf3d6a2
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
- HEAD and coordination base: `615069e6ca9cdb3d40b51d6a2f071346ecf3d6a2`
- P0 commits: `f1f523cd`, `76971f24`, `d36b8a57`, `615069e6`
- P0 result: 13 L2 `/chat` cases, MCP argument continuity/readiness contracts, bounded two-round behavior, semantic-fidelity fail-closed behavior, containment regression, mocked transport, follow-up corrections, and contradictory-evidence safety are present.
- Current suite inventory is approximately 5,313 backend test functions in 688 test files. This is newer than the earlier audit estimate of 5,290/684 and does not change its conclusion: rationalize conservatively through ownership and parameterization, not deletion.
- Pre-existing unrelated worktree state at plan creation: `.claude/settings.local.json` modified. Preserve it and never stage it.
- Live MCP remains OFF. Real Splunk MCP schemas remain `REAL_SCHEMA_UNVERIFIED`.

## Non-negotiable invariants

1. `architecture.md` is read-only. A discovered architecture conflict is an operator decision, not an edit.
2. Final RQC remains the semantic request authority. SPL V2 extends `SplIntentSpec`; it does not add a second planner or reinterpret the raw query downstream.
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

`P1`, `P2`, and the scaffold-only portion of `P3` can start in parallel from the same SHA. `P4` may perform a read-only role/posture audit in parallel, but implementation waits for P2's semantic contract and may not edit SPL-owned prompt files. P5 requires rebasing the eval branch after P1, P2, and P4. P6 starts only after P5 is green. P7 and P8 can execute in parallel after P5 if they retain exclusive ownership. P9 waits for P6, P7, and P8. P10 and P11 are strictly serial and operator-gated.

## Worktrees and branches

Do not create these during plan authoring. At implementation start, the integration owner freezes and records `INTEGRATION_SHA`; every initially parallel branch starts exactly there.

| Stream | Branch | Worktree purpose | Initial dependency | Merge order |
|---|---|---|---|---|
| A TRACE | `codex/closure-trace-truth` | Trace vocabulary, projection truth, stable oracle tests | P0 | 1 |
| B SPL | `codex/closure-spl-semantic-v2` | Existing semantic contract/compiler/fidelity evolution | P0 | 2 |
| C EVAL | `codex/closure-l2-eval-bank` | Test-only L2 bank scaffold, later integration and rationalization | P0 scaffold; P1/P2/P4 for assertions | 4 then 5 |
| D POLICY | `codex/closure-prompt-policy` | Role posture, prompt provenance, policy configuration contract | P2 contract for implementation | 3 |
| E UI | `codex/closure-production-ux` | Production UI components/tests after contracts stabilize | P5 | 7 |
| F PROMOTION | `codex/closure-promotion-coe` | L3 bank, gate evidence, handoff, last-stage COE | P5/P6/P7 as specified | 6 then 8 |
| INTEGRATION | `feat/complete-or-abstain-t4-ux` | Reconcile branches; no feature authorship while streams are active | Frozen integration SHA | sole integrator |

Worktree directory names are operator-selected local paths such as `../ai-soc-wt-trace`; they are not contractual. Branch names and actual start SHAs are contractual and must be recorded in the loop runner.

## File ownership matrix

| Authority seam | Exclusive implementation owner | Allowed paths | Must not modify concurrently |
|---|---|---|---|
| Trace/control-plane truth | A / CODEX | `backend/app/chat/control_plane_trace.py`, `pipeline_visibility.py`, `investigation_shaped.py`, `canonical_facts_spine.py`, `backend/app/spl/spl_provenance_trace.py`, directly corresponding trace tests | `pipeline.py`, SPL semantic modules, UI |
| SPL semantic V2 | B / CURSOR | `backend/app/spl/spl_intent_spec.py`, `spl_semantic_fidelity.py`, `utility_spl_authoring.py`, `llm_fallback.py`, `llm_plan_compiler.py`, `review_only_spl_postprocessor.py`, source-profile/binding/resolver modules, SPL validators, directly corresponding tests | Trace projections, generic LLM role registry, eval-bank files, UI |
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

## Protected-file policy

`architecture.md` may only be read. `backend/app/chat/pipeline.py`, `frontend/src/components/ChatPanel.tsx`, and all current `RACES_FREEZE_PATHS` are protected. If completion requires one:

1. STOP before editing.
2. Put the exact minimal proposed diff, rationale, invariant impact, tests, and rollback in `PROTECTED_CHANGE_QUEUE`.
3. Record `OPERATOR_APPROVAL_REQUIRED` and do no dependent implementation.
4. After explicit approval, assign the change to the existing seam owner, apply only the approved diff, run the RACES/freeze tests and affected phase gates, and record the approval reference.

Advancing a RACES baseline is itself a protected change and cannot be used to hide unreviewed mutations.

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

## Test gate matrix

| Gate | Purpose | Minimum command/evidence | Required before DONE |
|---|---|---|---|
| FOCUSED | Fast edit loop | `cd backend && ../.venv/bin/python -m pytest -q <owned tests>` or `cd frontend && npm test -- <owned tests>` | Every code item |
| L0 | Static governance/freeze/authority | Named governance, trust-boundary, RACES, and architecture checks relevant to change | P1, P4, P7, P9 |
| L1 | Deterministic unit/contract | Owned module contract suites including adjacent generalization | P1, P2, P4, P6 |
| L2 | Mocked production `/chat` | P0 bank plus expanded approximately 23-case bank | P3, P5, P6, P7, P9 |
| L2-SLOW | Timeout/subprocess/lifecycle | Explicitly marked timeout, subprocess, and bounded retry tests | P5, P6, P9 |
| L3 | Live local LLM semantic | Frozen bank and report; endpoint/config recorded, no threshold changes | P8, P9 |
| FRONTEND | Production UI unit/build | `cd frontend && npm test && npm run build` | P7, P9 |
| GOVERNANCE | Canonical regression | `PATH="$PWD/.venv/bin:$PATH" ./scripts/run_stage3_governance_regression.sh` | P9 |
| LINUX | Isolated candidate validation | Exact candidate SHA in clean Linux environment; same named gates and residual comparison | P9 |
| LIVE-MCP | Real Splunk MCP COE | P11 schema/auth/lifecycle/empty/error/full-investigation protocol | P11 only |

Focused tests run per item. Phase gates run at phase completion. The full backend suite is a promotion gate, not a per-edit loop.

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

- [ ] **P1 - Trace truth closure**
  - **STATUS:** TODO
  - **OWNER:** Workstream A / CODEX
  - **BASE_SHA:** Frozen `INTEGRATION_SHA`, initially `615069e6ca9cdb3d40b51d6a2f071346ecf3d6a2`.
  - **DEPENDENCIES:** P0.
  - **ALLOWED_FILES:** A-owned trace/provenance modules and directly corresponding tests from the ownership matrix.
  - **PROTECTED_FILES:** `architecture.md`, `backend/app/chat/pipeline.py`, frontend RACES paths.
  - **MISSION:** Reproduce each suspected contradiction, then correct only factual/projection inconsistencies and freeze a stable oracle vocabulary.
  - **WHY_THIS_EXISTS:** Recent inspection found attempted-call versus used/live-call ambiguity, conflicting fallback labels, RAG skipped alongside obtained citation state, artifact review conflated with execution HIL, and pure SPL diagnostic projections that may look investigation-shaped.
  - **DO:** Trace real `/chat` paths for pure SPL, deterministic fallback, LLM attempt/failure/success, RAG no-match/match, MCP planned/unavailable/response, and HIL. Define versioned oracle states `PLANNED`, `ATTEMPTED`, `RESPONSE_RECEIVED`, `ACCEPTED`, `USED`, `FALLBACK`, `FAILED`, `SKIPPED`. Separate `artifact_review_required` from `execution_hil_required`. Keep diagnostic detail in explicitly non-oracle fields. Ensure EvidenceState only records accepted obtained evidence and pure SPL does not project `InvestigationOutcome` merely because diagnostics exist.
  - **DO_NOT:** Pin unstable timing/debug fields; infer evidence from plans; change execution policy; edit pipeline without the protected stop; force all sidecars into a single misleading boolean.
  - **Verify:** Focused trace/provenance/outcome suites; table-driven oracle tests for every vocabulary transition; P0 L2 bank; L0 RACES/freeze test. Re-run repros to prove each suspected issue fixed, already-correct, or explicitly not reproducible.
  - **ACCEPTANCE_CRITERIA:** One documented trace schema/version; no contradictory oracle combinations; artifact and execution review flags are distinct; EvidenceState truth tests pass; pure SPL has no fabricated investigation outcome; diagnostics remain observable without becoming contract assertions.
  - **STOP_CONDITIONS:** Required fix touches `pipeline.py` or another protected file; a vocabulary change breaks an external contract not owned by A; same gate fails twice.
  - **EXPECTED_COMMIT_GROUPS:** `test(trace): reproduce trace truth contradictions`; `fix(trace): close stable oracle and evidence projection gaps`.
  - **OUTPUT_REQUIRED:** Repro matrix, schema/version decision, branch return packet, exact tests, unresolved protected diff if any.
  - **NEXT_PHASE_UNLOCK:** P5 trace-dependent L2 assertions and P7 trace UX contract.
  - **Evidence:** Pending.

- [ ] **P2 - SPL semantic V2 contract, authoring, fidelity, and syntax**
  - **STATUS:** TODO
  - **OWNER:** Workstream B / CURSOR
  - **BASE_SHA:** Frozen `INTEGRATION_SHA`, initially `615069e6ca9cdb3d40b51d6a2f071346ecf3d6a2`.
  - **DEPENDENCIES:** P0. Coordinate names with P1, but no file dependency.
  - **ALLOWED_FILES:** B-owned SPL modules, governed source-profile modules, validators, and directly corresponding tests.
  - **PROTECTED_FILES:** `architecture.md`, `backend/app/chat/pipeline.py`, frontend RACES paths.
  - **MISSION:** Evolve the existing `SplIntentSpec` into the single semantic SPL contract consumed from Final RQC, then make deterministic and LLM authoring preserve it and fail closed on semantic loss.
  - **WHY_THIS_EXISTS:** Three real failures exposed generic gaps: rolling distinct accounts over 10m, hourly failed-login trend over 24h, and password-change then login within 5m. The semantic audit found missing analytical windows, event sets, entity roles, distinct relationships, measures, grain, ordered sequences, max gap, analysis/output shape, normalization consumers, and prohibitions.
  - **DO:** Add typed optional concepts for `search_horizon`, analytical window kind/size, required event sets, entity roles, relationships, measures, temporal grain, ordered sequence/max gap, analysis shape (`raw`, `aggregation`, `ranking`, `trend`, `rolling`, `sequence`, `comparison`), output shape, normalization requirements/consumers, and prohibitions. Populate from Final RQC and explicit constraints with governed source mappings; manual/COE mappings win and other sources fill blanks only. Update existing compiler/authoring paths, semantic fidelity V2, and lightweight structural checks. Feed repair an immutable semantic contract, prior candidate, deterministic loss list, and bounded correction scope. Resolve `head 100`, mandatory aggregation, placeholder, template bias, generic coalesce, default 24h, truncation, and `streamstats` ordering conflicts by analysis shape. Test the three real failures plus adjacent unseen variants.
  - **DO_NOT:** Add a second planner, query-specific patches, complete Splunk grammar, downstream raw-query reinterpretation, silent defaults that contradict RQC, more than one repair, candidate execution, or blanket source capabilities.
  - **Verify:** Focused SPL contract/fidelity/compiler/postprocessor/source-profile suites; exact and adjacent-generalization cases for every supported shape; negative tests for unresolved source fields, unsupported comparison/sequence, lost time grain, lost ordering, unwanted truncation, and malformed structure; P0 L2 bank.
  - **ACCEPTANCE_CRITERIA:** Existing representation is versioned/evolved; all genuinely supported shapes preserve the immutable contract; unsupported shapes fail closed with analyst-readable reason; three repros and adjacent cases pass without query literals in production code; syntax checks catch structural hazards without claiming full grammar coverage; one proposal plus at most one repair is enforced.
  - **STOP_CONDITIONS:** Final RQC cannot supply a required field without protected pipeline work; source authority precedence is ambiguous; new planner is proposed; a shape requires unapproved product capability; same gate fails twice.
  - **EXPECTED_COMMIT_GROUPS:** `test(spl): freeze semantic-v2 failures and generalization`; `feat(spl): evolve semantic contract and compiler`; `fix(spl): enforce fidelity-v2 bounded repair and structural checks`.
  - **OUTPUT_REQUIRED:** Contract field table, support/degrade matrix by shape, prompt conflict resolution record, branch return packet, exact tests.
  - **NEXT_PHASE_UNLOCK:** P4 implementation, P5 semantic L2 assertions, P8 L3 bank.
  - **Evidence:** Pending.

- [ ] **P3 - L2 production bank scaffold from 13 toward 23**
  - **STATUS:** TODO
  - **OWNER:** Workstream C / CLAUDE
  - **BASE_SHA:** Frozen `INTEGRATION_SHA`, initially `615069e6ca9cdb3d40b51d6a2f071346ecf3d6a2`.
  - **DEPENDENCIES:** P0 for scaffold; P1/P2/P4 for assertions against new contracts.
  - **ALLOWED_FILES:** C-owned L2 bank/test files only. No runtime code.
  - **PROTECTED_FILES:** All runtime and RACES paths.
  - **MISSION:** Define the first architecture-bearing approximately 23-case mocked production `/chat` bank, preserving the 13 P0 cases and making contract-dependent rows explicitly pending until their provider phases merge.
  - **WHY_THIS_EXISTS:** The P0 harness proved 13 critical paths, while the prior L2 audit identified gaps in complex SPL fidelity, RAG SOP/no-match, remediation lifecycle, follow-ups, and production degradation. Jumping to 80-120 rows before contracts stabilize would create noise and brittle assertions.
  - **DO:** Create a case manifest with invariant owner, required phase, mocks, expected stable-oracle fields, prohibited outputs, and tier. Add immediately supported RAG match/no-match, remediation offer/accept/reject or nearest supported lifecycle, and follow-up forms. Reserve contract-dependent rows for rolling/trend/sequence and trace vocabulary. Mark contradictory-evidence adjudication and comparison/historical behavior conditional unless product support is proven. Assert stable oracle and analyst-visible outcomes, not diagnostic ordering/timestamps.
  - **DO_NOT:** Modify runtime to satisfy a row; fabricate support; duplicate P0 rows without a new invariant; assert speculative P1/P2 fields; expand to 80-120 before the first bank is green.
  - **Verify:** Bank schema/unit collection, P0 13 unchanged, immediately supported new rows green, pending rows fail collection if accidentally treated as active, duplicate-invariant review.
  - **ACCEPTANCE_CRITERIA:** Approximately 23 intentional rows are catalogued; every row owns a distinct invariant; 13 remain green; unsupported/conditional rows are explicit; no runtime files changed.
  - **STOP_CONDITIONS:** A desired row needs product support not in P1/P2/P4; stable contract name is unavailable; C would need to edit runtime or another stream's tests.
  - **EXPECTED_COMMIT_GROUPS:** `test(l2): scaffold architecture-defining production chat bank`.
  - **OUTPUT_REQUIRED:** Case matrix, pending dependency list, branch return packet, exact collection/test result.
  - **NEXT_PHASE_UNLOCK:** P5 after rebase onto merged P1/P2/P4.
  - **Evidence:** Pending.

- [ ] **P4 - Prompt, role policy, provenance, and Studio configuration contract**
  - **STATUS:** TODO
  - **OWNER:** Workstream D / CLAUDE; B remains owner of `backend/app/spl/llm_fallback.py`.
  - **BASE_SHA:** Integration SHA after P2 merge for implementation. Read-only audit may start at P0.
  - **DEPENDENCIES:** P0 for audit; P2 contract for writes and final prompt semantics.
  - **ALLOWED_FILES:** D-owned generic LLM prompt/role/settings modules and tests. Requirements for B-owned SPL prompt go through reconciliation.
  - **PROTECTED_FILES:** `architecture.md`, `pipeline.py`, RACES paths, B-owned SPL files.
  - **MISSION:** Make every live role's policy posture intentional, remove prompt-policy contradictions, record prompt provenance, and define a governed Prompt & Policy Studio configuration model without silently activating dormant reasoners.
  - **WHY_THIS_EXISTS:** Current prompts can conflict on truncation, aggregation, placeholders, source normalization, and time. `mitre_reasoner`, `missing_evidence_reasoner`, `risk_rationale_reasoner`, and `plan_delta_reasoner` are blocked by an intentional allowlist; their posture must be decided, not accidentally changed. Operators also need version/hash/config provenance.
  - **DO:** Inventory actual call reachability and flags for every live/advisory/dormant role. Record one explicit decision per named reasoner: remain blocked, shadow-only, or separately operator-approved future activation. Review shape advisor authority and schema. Define immutable prompt ID/version/content hash, model/provider/config hash, policy version, role, attempt/repair, and redacted request correlation provenance. Define Studio backend config model with draft validation, allowlisted editable fields, RBAC/admin guard, redaction, size limits, audit history, activation/rollback semantics, and no secret echo. Send SPL prompt conflict requirements to B and verify B's resolution.
  - **DO_NOT:** Enable a reasoner silently; grant tool calling; make shape advice authoritative; expose secrets; add unauthenticated writes; edit `llm_fallback.py`; build Studio UI in this phase.
  - **Verify:** Role reachability/allowlist tests, prompt hash/version determinism, config validation/redaction/auth/rollback tests, SPL prompt reconciliation review, L0 prompt trust-boundary checks, P0 L2 bank.
  - **ACCEPTANCE_CRITERIA:** Every role has documented runtime posture and test; named reasoners remain blocked unless a separate explicit operator decision says otherwise; provenance is deterministic and redacted; Studio contract is implementable and governed; no direct LLM authority or MCP access.
  - **STOP_CONDITIONS:** Activation is required without operator approval; persistence/auth architecture is ambiguous; SPL prompt change is attempted outside B; protected path is required.
  - **EXPECTED_COMMIT_GROUPS:** `test(llm): freeze role posture and prompt provenance`; `feat(llm): add governed prompt-policy metadata and config contract`.
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
  - **EXPECTED_COMMIT_GROUPS:** `test(l2): close first expanded production journey bank`; optional seam-owner fix commits only after ownership handback.
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
  - **EXPECTED_COMMIT_GROUPS:** `test(cleanup): remove proven duplicate test artifacts`; `test(refactor): parameterize equivalent invariant cases`; `test(tiers): separate deterministic and slow gates`.
  - **OUTPUT_REQUIRED:** Before/after inventory, retirement ledger, tier matrix, branch packet, exact tests.
  - **NEXT_PHASE_UNLOCK:** P9 promotion full-suite comparison.
  - **Evidence:** Pending.

- [ ] **P7 - Production UI and trace/operator UX**
  - **STATUS:** TODO
  - **OWNER:** Workstream E / CURSOR
  - **BASE_SHA:** P5 green integration SHA; rebase after any backend contract movement.
  - **DEPENDENCIES:** P1, P2, P4, P5.
  - **ALLOWED_FILES:** E-owned production non-EC frontend components/hooks/types/tests and approved settings surfaces.
  - **PROTECTED_FILES:** `ChatPanel.tsx` and all RACES paths; EC components remain isolated and are not a production shortcut.
  - **MISSION:** Give analysts and operators truthful production surfaces for SPL review, semantic failure, execution decisions, investigation progress, remediation, degradation, and trace provenance.
  - **WHY_THIS_EXISTS:** P0 and backend contracts can be correct while production users still cannot distinguish candidate review from execution HIL, inspect semantic loss, or recover from unavailable capabilities. EC parity is not proof of production UX.
  - **DO:** Test and implement production surfaces for candidate SPL review; semantic warning/fail-closed reason; Run/Edit/Cancel with clear candidate-versus-approved state; separate artifact review and execution HIL; bounded progress; remediation offer/status; RAG/LLM/MCP degradation; stable trace oracle with diagnostics collapsed; prompt/config provenance where appropriate. Keep controls feature-complete and accessible. If wiring requires `ChatPanel.tsx`, stop with exact proposed diff first.
  - **DO_NOT:** Reuse EC state as production authority; expose secrets/raw prompts; imply MCP ran when planned/unavailable; enable execution flags; show empty InvestigationOutcome for pure SPL; edit protected paths without approval.
  - **Verify:** Focused component tests for each state; frontend full test/build; browser checks at desktop/mobile for overflow, action states, progress, and error recovery; RACES/freeze gate; production API contract fixtures from P5.
  - **ACCEPTANCE_CRITERIA:** All listed states are reachable and truthful; Run/Edit/Cancel/HIL semantics match backend authority; degradation is actionable; trace oracle is visible without brittle diagnostics; EC remains isolated; frontend tests/build green.
  - **STOP_CONDITIONS:** Protected path is required; backend contract is insufficient; UI would infer authority from diagnostics; same frontend gate fails twice.
  - **EXPECTED_COMMIT_GROUPS:** `test(ui): cover production investigation and SPL review states`; `feat(ui): expose governed production review and trace UX`.
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
  - **DO:** Define immutable rows and expected semantic constraints; record model/provider/prompt/config hashes and timeouts; measure semantic correctness, initial success, repair rate, fallback rate, latency distribution, schema failure, and intent loss. Keep one-proposal/one-repair accounting. Separate infrastructure unavailable from semantic failure. Freeze thresholds before running the candidate.
  - **DO_NOT:** Loosen thresholds after results; count deterministic fallback as model success; call Cisco/VPS merely to iterate prompts; include live MCP; mutate runtime from the eval branch.
  - **Verify:** Runner self-tests, frozen-bank hash, repeated live run sufficient to expose variance, machine-readable and human-readable report, L2 regression after any owning-stream fix.
  - **ACCEPTANCE_CRITERIA:** Every category has representative rows; metrics are reproducible and provenance-complete; threshold decision is recorded before candidate result; failures are assigned to owner or accepted explicitly, never hidden.
  - **STOP_CONDITIONS:** No approved/configured local LLM endpoint; prompt/config provenance missing; evaluator defect; threshold change requested after seeing results; same gate fails twice.
  - **EXPECTED_COMMIT_GROUPS:** `test(eval): freeze L3 semantic bank and metrics`; `docs(eval): record L3 candidate evidence`.
  - **OUTPUT_REQUIRED:** Bank hash, environment/provenance, metrics report, failure ledger, branch packet.
  - **NEXT_PHASE_UNLOCK:** P9 L3 promotion decision.
  - **Evidence:** Pending.

- [ ] **P9 - Promotion governance and residual failure adjudication**
  - **STATUS:** TODO
  - **OWNER:** Workstream F / integration CODEX
  - **BASE_SHA:** Candidate integration SHA containing P6, P7, and P8 outcomes.
  - **DEPENDENCIES:** P6, P7, P8.
  - **ALLOWED_FILES:** Promotion evidence, eval reports, plan/loop status; defects return to owning stream.
  - **PROTECTED_FILES:** Architecture and RACES paths; baseline advancement requires protected approval.
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

After the operator freezes and records one `INTEGRATION_SHA`:

1. Start P1 on A, P2 on B, and P3 scaffold on C from that exact SHA.
2. D may run a read-only role/posture audit, but must not make contract-dependent edits until P2 merges.
3. Do not start E or live evaluation. Do not create F's COE environment.
4. If P3 needs a field not yet merged, record the row as pending instead of guessing.

## Reconciliation and merge order

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
| RACES freeze test | Earlier baseline mismatch after reviewed pipeline change | Remeasure exact current result; baseline advance is protected | Branch-pre-existing/protected decision | Operator approval plus exact diff history, or block |
| Any newly observed plugin/environment failure | Unknown until P9 | Add exact test, baseline/candidate, dependency, evidence | Unclassified | Must be classified and adjudicated before GO |

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
| Second planner | PASS: P2 explicitly evolves `SplIntentSpec` from Final RQC. |

## Drift log and evidence discipline

- 2026-08-25: Mission estimate 5,290 tests/684 files measured as approximately 5,313 test functions/688 files. Plan retains the moderate rationalization conclusion and treats counts as targets, not acceptance criteria.
- 2026-08-25: General repo convention says list plans in `plans/README.md`, but this mission explicitly authorizes writes only to the new master plan and loop runner. README update is intentionally excluded and must not be smuggled into the plan-only commit.
- Every checked item must contain command/result evidence and exact SHA. Re-audit inherited checkmarks before P9; written code alone is never evidence.
- Wrong premise, redundant item, changed contract, or scope expansion goes to `DECISION_LOG` and pauses dependent work.

## Plan completion definition

The plan is complete only when P1-P10 are DONE with evidence and P11 is either DONE after separate authorization or remains explicitly DEFERRED with production GO withheld. This document's creation does not authorize implementation, worktrees, pushes, merges, deployment, live LLM calls, or live MCP.
