---
name: canonical-architecture-authority-convergence
overview: "Make final understanding, planning, evidence state, investigation outcome, SPL call authorization, synthesis, reliability, and continuity authoritative; admit advanced execution extensions only through measured evidence."
status: in_progress
date: 2026-08-15
canonical_plan: plans/2026-08-15_0602_canonical-architecture-authority-convergence.md
canonical_architecture: architecture.md
architecture_freeze_commit: a8f02e3c98b866bcb12c7d5b3db75b11e823609b
architecture_content_sha256: c1c4ba8a88d8f245752188a76442102978eceb0c1bdb410717b789649fb9a034
source_audit: docs/architecture/canonical_architecture_audit_2026-08-15.md
depends_on:
  - plans/2026-08-14_1130_resource-plan-authority-and-t4-integration.md completion or explicit user-approved supersession
---

# Plan 8 — canonical architecture authority convergence

## Objective

Converge the existing production Resource Planner toward the canonical target in [`architecture.md`](../architecture.md) without adding a new framework or service: one final `ResolvedQueryContract` must govern clarification, route ownership, ResourcePlan creation, and mandatory SPL constraints; `ResourcePlan + PhaseContract` must preserve governed lifecycle authority; a minimal derived `EvidenceState` and authoritative `InvestigationOutcome` must precede governed synthesis/actions; call-level authorization and untrusted-evidence boundaries must remain deterministic; and T4 reliability must use circuit breaking/backpressure with human-only restart. Detailed per-step evidence attribution, full step-instance execution, generic PlanDelta, and richer capability views remain evidence-gated extensions.

## Current status and execution lock

This plan is **in progress** at **P0 only**. Plan 7 is **CLOSED 25/25** and merged; it is no longer
the active authority-migration plan. Runtime implementation must not begin until P1 (audit-only
baseline) is complete. Plan 7 A6 posture remains `V2_OFF_PENDING_WIDER_EVIDENCE` as the recorded
STOP label; E2 later approved `ResourcePlan + PhaseContract` as sole **normal** authority with
dispatch-v2 retired to rollback/test-only. Plan 8 must not enable dispatch-v2 or infer a GO
decision. Plan 7 C3 remains `REMEDIATE_EXISTING_T4_IN_PLACE`; Plan 8 does not reopen or execute
that decision. A7’s legacy-fallback proof is complete
(`LEGACY_FALLBACK_ROLLBACK_ONLY_RETAIN_TEMPORARILY`); X3 consumes it and must not reopen A7.

The pre-implementation architecture-conformance review was completed on 2026-08-15 against the
frozen working-tree content of `architecture.md`. P0 below is the inheritance record against the
completed Plan 7 evidence. This documentation item does not start minimal EvidenceState,
InvestigationOutcome, SPL authorization, trust-boundary, reliability, step-instance, detailed
evidence-ledger, PlanDelta, capability-snapshot, or session implementation work.

## Pre-implementation freeze record

- **Plan status:** `queued`.
- **Checklist state:** 0/34 checked at freeze review.
- **Canonical architecture:** [`architecture.md`](../architecture.md), read-only for Plan 8.
- **Frozen architecture commit SHA:** `a8f02e3c98b866bcb12c7d5b3db75b11e823609b`.
- **Frozen architecture content SHA-256:**
  `c1c4ba8a88d8f245752188a76442102978eceb0c1bdb410717b789649fb9a034`.
- **Superseded freeze hash:**
  `6bef0b25a4a8a4810c3f0ce86e10c446736e5d0ed388557abf5fc04821508709` was superseded by explicit
  user decision before Plan 8 execution; it is not an implementation authority.
- **Registration integrity:** `architecture.md` content was not modified by the freeze-reference
  registration task. If the committed content does not match the recorded SHA-256, STOP with
  `ARCHITECTURE_FREEZE_REFERENCE_REQUIRED`. A coding agent may not edit `architecture.md` to clear
  this STOP.

Historical measured source audit: `docs/architecture/canonical_architecture_audit_2026-08-15.md`.

## Plan 7 disposition (P0, 2026-08-16)

Plan 7 **completed**; it was **not** superseded. Dated 2026-08-16. Copied from committed Plan 7
evidence without changing or reopening any STOP. Base: `origin/master` =
`c248cb40862335c30febdf588f3d5ca23a38d4a7` (merge of PR #134 Plan 7 on top of PR #132 Plan 6).
Plan 7 checklist: **25 checked / 0 unchecked**. Architecture freeze verified this session:
commit `a8f02e3c98b866bcb12c7d5b3db75b11e823609b` contains `architecture.md` with content
SHA-256 `c1c4ba8a88d8f245752188a76442102978eceb0c1bdb410717b789649fb9a034`; HEAD blob
`d8cec1a85651efa8ffd3d7367c85699e527cc7bd` is identical. `architecture.md` is read-only for
Plan 8 and was not modified by P0.

### Recorded E2 outcome (copied, not re-decided)

From `docs/evals/plan7/e2_decision.md` and Plan 7 Approved decisions § E2:

| Field | Value |
|---|---|
| `PLAN7_IMPLEMENTATION` | **COMPLETE** |
| `RESOURCEPLAN_AUTHORITY` | **APPROVED** — `ResourcePlan + PhaseContract` is the sole **normal** execution authority |
| `PRODUCTION_GO_LIVE` | **DEFERRED / NO-GO** |
| `REASON` | unresolved critical T4 serving stability blocker (**F3**) |
| `PLAN8_MAY_START_AFTER_PLAN7_CLOSURE` | **YES** |
| Accepted risks | **none recorded** |

This is a deferral on serving stability — not a rejection of the architecture, not a rollback,
and not a production-ready claim. Plan 8 must not infer GO.

### Copied Plan 7 STOPs (do not reopen)

| ID | Recorded decision | Artifact |
|---|---|---|
| **A2** | **OPTION A** — PhaseContract lifecycle is honoured independently of merge reachability. A resource-plan downgrade may remove unavailable resource work; it may **not** silently remove applicable mandatory lifecycle work. | `docs/evals/plan7/a2_stop_decision_packet.md` |
| **A3** | Implemented A2 exactly. Structural trigger only (`no_schedulable_step` + valid execution contract + non-empty `hook_bound_mandatory`). `spl_postprocessor` contract-inserted on every applicable seam row. Invalid/unsafe plans still fail closed. | `docs/evals/plan7/a3_ownership_fix.md`, A4 acceptance |
| **A6** | **`V2_OFF_PENDING_WIDER_EVIDENCE`**. dispatch-v2 stays OFF and is **not** restored as normal authority. v2-OFF was not claimed proven at A6; E2 later approved ResourcePlan as sole normal authority with v2 retired to rollback/test-only. Plan 8 must not enable v2. | `docs/evals/plan7/a6_stop_decision_packet.md` |
| **A7** | **`LEGACY_FALLBACK_ROLLBACK_ONLY_RETAIN_TEMPORARILY`**. Target Resource Planner graph cannot enter `_run_legacy_dispatch_fallback`; the retained rollback branch runs `workflow_spl → spl_postprocessor → spl_source_resolve → execution` and fails closed. Not deleted. X3 consumes this; A7 is not reopened. | `docs/evals/plan7/a7_fallback_lifecycle_proof.md` |
| **C3** | **`REMEDIATE_EXISTING_T4_IN_PLACE`**. Keep existing T4 architecture and Cisco Foundation-Sec 8B. No sidecar, cache, provider change, new model, keywords, or v2 restore. `VPS_T4_REMEDIATION_TIMEOUT = 120 s` on the VPS only; repo defaults unchanged. U3 revalidates; C3 is not reopened. | `docs/evals/plan7/c3_stop_decision_packet.md`, `c3_remediation_evidence.md` |
| **E2** | See table above. | `docs/evals/plan7/e2_decision.md` |

### Deployment posture (copied, not changed by P0)

Effective VPS target (Plan 7 D2/D3/E1; `AI_SOC_ENV_PROFILE=development`):

```text
LANGGRAPH_ORCHESTRATION_ENABLED            = true
AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED     = true
AI_SOC_PIPELINE_DISPATCH_V2_ENABLED        = false
AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED   = true
AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS = 120   (VPS only; not a repo default)
AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED = false
MCP_MODE                                   = mock
```

Repo `config.py` defaults were not required to change. `CONFIG_REBUILD_DRIFT` is **CLOSED for
the development profile only**; COE/production profiles remain unproven. P0 does not change
flags, defaults, or deployment.

### Gate evidence (copied from Plan 7 E1)

`docs/evals/plan7/e1_closure_gates.md` @ `6ecf6c4`: **11/11 PASS** — governance
`stage3_governance_regression: PASS` (harness 6/6); pytest `5335 passed / 0 failed`; truth-set
0 regressions (64/76); parity `exact=120 approved=0 critical=0`; Cisco `50/0/0`; probes 10/10;
sentinel 17/17; path 105/105; manifest 15/15; invariants 7/7. Parity `120 exact` is dual-runtime
equivalence, **not** routing/answer correctness. Cisco `50/0/0` is a deterministic/reference
evaluation and is **not** evidence that F3 serving is solved.

### Preserved invariants (Plan 8 may not weaken)

- **Sole normal authority:** `ResourcePlan + PhaseContract + deterministic compiler`. Do not
  rebuild this topology or restore dispatch-v2 as normal authority.
- **A3:** an unschedulable resource step cannot erase applicable mandatory lifecycle phases;
  invalid or unsafe plans still fail closed.
- **A7:** rollback-only fallback retained temporarily; not an alternative production executor.
- **Human-only Cisco restart:** no code/model/agent may restart Foundation-Sec. Plan 7 performed
  no model restart (`HUMAN_RESTART_REQUIRED` did not arise). REL0 may add health detection /
  circuit / backpressure only.
- **`candidate_spl` is never executable.** Only approved non-null `normalized_spl` may reach the
  MCP gate. Plan 7 measured `execution_eligible` null on every corpus row.
- **dispatch-v2 remains non-normal authority.** Fenced: with ResourcePlan execution ON, v2
  cannot win even if its flag is enabled (`V2_WINS = 0`).
- **Live MCP remains `live_mcp_unproven`.** `MCP_MODE=mock`; mock success is not live Splunk
  readiness.
- **MITRE 11-row DRAFT promotion remains deferred.**

### Inherited / already satisfied — do not rebuild

These are proven Plan 7 results. Later Plan 8 items may **consume** them (U3, X3, REL0, C1
verify) but must not re-implement or reopen them:

| Proven result | Plan 8 consumer | Rebuild? |
|---|---|---|
| ResourcePlan + PhaseContract sole normal authority | C0/C1/E0/X0/X3 | **no** |
| A2 OPTION A / A3 lifecycle insertion | C1 Verify (`test_plan7_a0_mandatory_phase_survives_no_schedulable_step.py`) | **no** |
| A6 `V2_OFF_PENDING_WIDER_EVIDENCE` + E2 v2 retired/fenced | X0/X3; no item may enable v2 | **no** |
| A7 `LEGACY_FALLBACK_ROLLBACK_ONLY_RETAIN_TEMPORARILY` | **X3** revalidates; does not reopen A7 | **no** |
| C3 `REMEDIATE_EXISTING_T4_IN_PLACE` + 120 s VPS-only bound | **U3** revalidates serving/contract; no new serving decision | **no** |
| `candidate_spl` non-executable / HIL/RBAC/MCP gates | SPL1/AUTH0/G0 | **no** (extend, do not replace) |
| Human-only Cisco restart | **REL0** | **no** automated restart |
| `CONFIG_REBUILD_DRIFT` closed (development) | G0 posture check | **no** repo-default change unless an item authorizes it |

### Carried forward into Plan 8 (unsolved, unaccepted)

| ID | Meaning | Plan 8 owner | Must not claim |
|---|---|---|---|
| **F1** | DB loss silently degrades authority to `canonical_non_planned` while still answering; no analyst-visible degrade signal | **REL0** (degradation signalling) | not an accepted risk |
| **F2** | `/v1/models` liveness ≠ usable inference health | **REL0** (detection); restart stays human-only | not an accepted risk |
| **F3** | `T4_SEMANTICALLY_VIABLE_BUT_VPS_SERVING_BLOCKER` | remains a **CRITICAL BLOCKER** for production GO | Plan 8 reliability work (REL0) may improve detection / backpressure / degradation; it **must not** claim to solve F3 serving capacity or VPS serving stability |

Locked-field upstream quality (T4 can no longer re-classify a paraphrase into an SPL-capable
family) also carries to Plan 8 understanding work (U0–U2/R0); it is not a serving-capacity fix.

### Remaining core Plan 8 work after P0

Mandatory current path still unchecked: **P1**, **S0**, **U0**, **U1**, **U2**, **REL0**, **R0**,
**R1**, **C0**, **SPL1**, **AUTH0**, **E0A**, **D0**, **OUT0**, **SEC0**, **O0**, **O1**, **O1A**
(17 `CORE_REQUIRED`) plus supporting **P8_ADVANCED_EXECUTION_EXTENSION_GATE**, **U3**, **SPL0**,
**X0**, **X2**, **X3**, **G0**, **G1**. Conditional extensions (`R2`, `C1`, `E0`, `E1`, `D1`,
`D2`, `X1`) stay gated. Architecture Phase 10 remains an explicit approved deferral.

P0 does **not** authorize P1 or any runtime change.

## Done definition

Plan 8 is complete only when:

- every mandatory core item is checked with real evidence;
- each applicable conditional item is either completed with evidence or explicitly dispositioned as `NOT_REQUIRED_FOR_CURRENT_SCOPE`;
- final RQC is authoritative before clarification, final ownership routing, and ResourcePlan creation;
- primary skill no longer vetoes legitimate cross-capability ResourcePlan work;
- deterministic EVIDENCE sufficiency runs before synthesis using existing governed evidence/context;
- a minimal derived EvidenceState is authoritative for required/obtained/missing/stale/invalidated/blocked evidence without duplicating raw evidence;
- a minimal governed InvestigationOutcome is established after EVIDENCE sufficiency and before synthesis/actions;
- follow-up evidence is reused only after scope/freshness/policy applicability checks against the new final RQC;
- mandatory final-RQC SPL constraints survive into normalized SPL or carry an explicit deterministic non-applicability reason;
- Splunk authorization is bound to the final normalized call and invalidated by material change;
- untrusted evidence/generated content remains data, never control or action authority;
- T4 has bounded concurrency/backpressure/circuit semantics and Cisco LLM restart remains explicit human/operator action only;
- T4 stays bounded, no-tools, and limited to permitted unresolved semantics;
- deterministic SPL validation, candidate-only SPL, HIL, RBAC, MCP, policy, and final-validation authority remain intact;
- generic follow-up uses controlled prior context rather than another phrase catalogue;
- inherited Plan 7 decisions are preserved;
- canonical Architecture Phase 10 has an explicit approved deferral;
- the final audit covers canonical phases 0–11 with zero unexplained `MISPLACED` authority findings and no unapproved `MISSING` role;
- there is no unapproved architecture, deployment, configuration, model/provider, timeout, or eval-baseline drift; and
- every implemented item has a focused green commit and evidence trail.

## Core convergence vs evidence-gated extensions

Every checklist item has exactly one freeze classification. `CORE_REQUIRED` means a current
architecture correction. `CONDITIONAL_EXTENSION` is not current scope without its named explicit
decision. `AUDIT_ONLY` may add or update tests/audit evidence but does not authorize runtime behavior
changes. `DOCUMENTATION_ONLY` changes plan/operating documentation only. Audit/documentation items
can still be mandatory prerequisites or closure gates.

| Item | Classification | Freeze disposition |
|---|---|---|
| P0 | DOCUMENTATION_ONLY | Mandatory inheritance record; no Plan 7 decision is reopened. |
| P1 | AUDIT_ONLY | Mandatory baseline/test evidence; no runtime correction. |
| P8_ADVANCED_EXECUTION_EXTENSION_GATE | AUDIT_ONLY | Mandatory human decision record before any conditional extension or G0. |
| S0 | CORE_REQUIRED | Shared staged `UNDERSTANDING`/`EVIDENCE` sufficiency adapter. |
| U0 | CORE_REQUIRED | Locked/unresolved deterministic understanding. |
| U1 | CORE_REQUIRED | Bounded, field-constrained, no-tools T4 input/call contract. |
| U2 | CORE_REQUIRED | Deterministic T4 validation/merge and derived-field recomputation. |
| U3 | AUDIT_ONLY | Revalidate inherited Plan 7 T4 posture; no serving decision. |
| REL0 | CORE_REQUIRED | Audit first; add circuit/backpressure behavior only where proven missing. |
| R0 | CORE_REQUIRED | Final RQC and clarification authority before planning. |
| R1 | CORE_REQUIRED | Final route/owner before the sole ResourcePlan creator. |
| R2 | CONDITIONAL_EXTENSION | Richer thin capability view only if explicitly measured/approved. |
| C0 | CORE_REQUIRED | ResourcePlan from final RQC without primary-skill capability veto. |
| C1 | CONDITIONAL_EXTENSION | Full step-instance compilation only if explicitly measured/approved. |
| SPL0 | AUDIT_ONLY | Mandatory nine-part SPL entity/lifecycle/authorization ownership audit. |
| SPL1 | CORE_REQUIRED | Mandatory final-RQC constraint flow and preservation correction. |
| AUTH0 | CORE_REQUIRED | Exact final normalized Splunk-call authorization. |
| E0A | CORE_REQUIRED | Minimal derived canonical EvidenceState. |
| E0 | CONDITIONAL_EXTENSION | Full step-instance runtime only if explicitly measured/approved. |
| E1 | CONDITIONAL_EXTENSION | Detailed per-step/producer EvidenceState only if explicitly measured/approved. |
| D0 | CORE_REQUIRED | Deterministic EVIDENCE sufficiency before outcome/synthesis. |
| D1 | CONDITIONAL_EXTENSION | Generic targeted PlanDelta only if explicitly measured/approved. |
| D2 | CONDITIONAL_EXTENSION | One bounded refinement round only if explicitly measured/approved. |
| OUT0 | CORE_REQUIRED | Minimal governed InvestigationOutcome seam. |
| SEC0 | CORE_REQUIRED | Untrusted-evidence/generated-content control and prompt boundary. |
| O0 | CORE_REQUIRED | Synthesis consumes InvestigationOutcome and governed evidence. |
| O1 | CORE_REQUIRED | Safe Phase 11 session continuity. |
| O1A | CORE_REQUIRED | Evidence applicability/reuse/invalidation for the new final RQC. |
| X0 | AUDIT_ONLY | Mandatory legacy/duplicate seam classification; no deletion. |
| X1 | CONDITIONAL_EXTENSION | Dead-seam deletion only with separate explicit authorization. |
| X2 | DOCUMENTATION_ONLY | Reconcile operating documentation to verified runtime. |
| X3 | AUDIT_ONLY | Preserve/revalidate inherited Plan 7 A7 fallback disposition. |
| G0 | AUDIT_ONLY | Mandatory verification gates and novel negative controls. |
| G1 | AUDIT_ONLY | Mandatory skeptical phases 0–11 architecture re-audit. |

### Mandatory current Plan 8 path

The 17 `CORE_REQUIRED` architecture corrections are:

`S0, U0, U1, U2, REL0, R0, R1, C0, SPL1, AUTH0, E0A, D0, OUT0, SEC0, O0, O1, O1A`

The 10 mandatory supporting audit/documentation controls are:

`P0, P1, P8_ADVANCED_EXECUTION_EXTENSION_GATE, U3, SPL0, X0, X2, X3, G0, G1`

Together these 27 items form the mandatory current path. The dependency graph below, not the
visual list order, governs execution.

### Evidence-gated extension package

`R2`, `C1`, `E0`, `E1`, `D1`, and `D2` are conditional advanced extensions. E1 now means only detailed per-step/producer-instance EvidenceState attribution; core minimal EvidenceState is E0A. `X1` is separately conditional on X0 proving a seam dead/duplicate and retirement being explicitly authorized.

The named STOP `P8_ADVANCED_EXECUTION_EXTENSION_GATE` asks:

> Does measured evidence from the core architecture baseline/current required use cases show that the existing runtime cannot satisfy a required canonical use case without full step-instance execution, detailed per-step EvidenceState attribution, a richer joined capability view, or targeted PlanDelta refinement?

Allowed decisions:

- `NOT_REQUIRED_FOR_CURRENT_SCOPE` — record each affected item as an explicit approved deferral, not an architecture failure.
- `REQUIRED_BY_MEASURED_USE_CASE` — execute only the minimum subset directly justified by the measured case.

No agent may self-approve `REQUIRED_BY_MEASURED_USE_CASE`. The gate is not permission for a new executor, runtime, or agentic planning loop.

## Architecture Phase 10 scope

Canonical Architecture Phase 10 — governed post-synthesis action execution (ticket creation, email send, CRM logging, remediation MCP/action tools) — is intentionally **DEFERRED** to the next governed implementation plan.

Plan 8 must preserve compatibility with Phase 10 but must not redesign, implement, disable, or widen existing action-execution paths. O1 maps to canonical **Phase 11**, session/follow-up state; canonical phases must not be renumbered.

Phase 10 compatibility means actions consume final RQC, InvestigationOutcome, an approved action intent/payload, deterministic policy, RBAC, HIL, and idempotency state. Free-form synthesis is never action authority.

## Coding-agent execution contract

Plan 8 is executed strictly one checklist item at a time. Before editing for an item, the coding agent must output:

```text
PLAN=Plan 8
ARCHITECTURE_SHA=<frozen architecture commit SHA>
CURRENT_ITEM=<ID>
DEPENDENCIES=<IDs>
DEPENDENCIES_COMPLETE=yes/no
ALLOWED_SCOPE=<files/components required by this item>
VERIFY=<exact verification command from the item>
```

If the architecture SHA is pending/missing, does not contain the recorded frozen content, or any
dependency is incomplete: **STOP**. `ARCHITECTURE_SHA` must be the recorded full commit SHA, not the
working-tree content hash or current HEAD by convenience.

Then the agent must:

1. Read `architecture.md`.
2. Read only the current item, its dependency evidence, referenced code, and referenced tests.
3. Do not implement later items opportunistically.
4. Prefer modifying existing components over creating new abstractions.
   Use: `reuse → reorder → minimally extend → deterministically validate → test`.
   Do not add an abstraction solely because Plan 8 terminology differs from existing code.
5. Use the exact terminology already present in the repository.
6. Do not rename architecture concepts merely for style.
7. Do not add a new LLM call where deterministic code already owns the decision.
8. Do not add keyword/query-ID special cases.
9. Do not broaden permissions/capabilities to make a test pass.
10. Do not alter deployment posture unless the current item explicitly authorizes it.
11. Do not refresh historical eval baselines.
12. Do not stash/reset/revert/clean unrelated work.
13. If unrelated or concurrent work overlaps the current item: **STOP**.
14. Implement the smallest change satisfying the item.
15. Run the item's exact Verify command.
16. Never weaken or delete a failing test to make the result green.
17. If the same Verify gate fails after two implementation attempts: **STOP** and report.
18. If a fix requires changing an architecture invariant or user-approved decision: **STOP**.
19. When Verify passes, record real Evidence in the plan.
20. Only then mark the item complete and commit.

Tests assert contracts, authority, and results—not exact LLM prose or exact latency unless the item explicitly tests latency.

## Git / commit discipline

Before execution, Plan 7 must be complete or explicitly superseded. Create/use a dedicated Plan 8 branch only with user approval; record the base SHA and approved base/`origin/master`; capture `git status --short`; never absorb unrelated dirty files.

Default rule: **one completed checklist item = one focused commit**.

```text
implement item
→ run exact Verify
→ Verify GREEN
→ record Evidence
→ mark item checked
→ inspect git diff
→ run the repository invariant check
→ commit
→ proceed
```

Do not commit a failing item or bundle unfinished future items. Focused code, tests, and that item's evidence normally ship together. Commit format: `plan8(<ITEM>): <concise outcome>`; documentation/checkpoints use the same form. If a later item exposes a regression, create a new corrective commit, re-run affected verification, and update evidence honestly—do not rewrite evidenced history.

Push only after a completed logical phase/checkpoint or required STOP. Do not push half-green work. PR/merge requires explicit user approval; merge to master remains user-controlled.

## Small-model terminology guard

| Term | Meaning |
|---|---|
| T1–T3 | deterministic understanding |
| T4 | bounded semantic understanding only |
| Final RQC | authoritative understood request |
| primary skill | ownership/entry signal only |
| ResourcePlan | work required to satisfy final RQC |
| PhaseContract | mandatory lifecycle/governance obligations |
| compiler | turns plan work into an executable schedule |
| RP graph | only execution hub |
| minimal EvidenceState | derived current evidence applicability view; not storage |
| EVIDENCE sufficiency | deterministic check before synthesis |
| InvestigationOutcome | authoritative structured investigation result |
| synthesis | governed narration/reasoning; no tool authority |
| Phase 10 actions | canonical but deferred from Plan 8 |
| session continuity | safe prior-turn context for the next normal run |

**DO NOT CONFUSE:** primary skill ≠ sole capability; T4 ≠ router; T4 ≠ planner; ResourcePlan ≠ PhaseContract; EvidenceState ≠ new database; minimal EvidenceState ≠ detailed per-step ledger; InvestigationOutcome ≠ LLM free-form answer; synthesis ≠ action authority; tool access ≠ authorization to execute a particular tool call; Splunk access ≠ authorization for arbitrary SPL; candidate SPL ≠ executable query; `spl_source_resolve` ≠ semantic query understanding; `spl_postprocessor` ≠ authority to invent query constraints; LLM failure detection ≠ permission to restart LLM; circuit breaker ≠ restart controller; human restart = explicit operator action only; follow-up context reuse ≠ evidence reuse; prior evidence ≠ automatically valid evidence for the current RQC; architecture target ≠ permission to implement every future extension.

## Invariants and non-goals

- Preserve deterministic authority over route policy, SPL validation, HIL, RBAC, MCP gating, severity/MITRE facts, allowed actions, and final answer validation.
- Preserve inherited Plan 7 A2/A3/A6/A7 dispositions and C3 `REMEDIATE_EXISTING_T4_IN_PLACE`; Plan 8 may reconcile evidence but may not reopen them.
- Preserve Plan 7 A3: an unschedulable resource step cannot erase applicable mandatory lifecycle phases; invalid or unsafe plans still fail closed.
- `candidate_spl` is never executable. Only approved, non-null `normalized_spl` may reach the MCP gate.
- Mandatory final-RQC constraints relevant to SPL must appear in `normalized_spl` or have an explicit deterministic non-applicability reason; silent dropping/widening and LLM-invented repairs are prohibited.
- A Splunk execution grant is bound to the authenticated identity, investigation/trace, connection/tool, source scope, normalized SPL fingerprint, time range, limits, policy/RBAC/HIL state, and expiry/one-run scope where applicable. Material call changes require re-authorization.
- T4 is an optional bounded semantic interpreter only. It cannot select routes/resources, grant capabilities, authorize tools or execution, decide sufficiency/policy, clear clarification/prohibitions, or call MCP. Final synthesis is governed narration only. Both model roles have deterministic timeout/error fallbacks.
- Cisco T4 may be health-checked, circuit-broken, and backpressured deterministically, but no code/model/agent automatically restarts it. Restart is explicit human/operator action followed by deterministic health verification.
- Instructions inside user input/evidence and prior assistant/LLM prose are untrusted data, not control authority. Prompt builders must delimit evidence from trusted system policy; evidence cannot grant capabilities, select routes, clear RBAC/HIL, change policy, authorize actions, or trigger remediation.
- Minimal EvidenceState is a deterministic derived view over existing governed evidence. It is not a database and does not duplicate raw evidence. Detailed per-step producer attribution remains conditional.
- InvestigationOutcome is the governed structured result after EVIDENCE sufficiency. Synthesis narrates it; Phase 10 actions consume it plus deterministic action controls, never arbitrary final prose.
- Primary skill is an ownership/entry decision, not an enumerator or veto for all resources used by the plan.
- There is one execution authority: `ResourcePlan → existing deterministic compile/schedule seam → existing Resource Planner execution hub`. A gate-authorized step-instance representation may refine that seam, but cannot create worker-node families, another execution graph/executor, or a new runtime abstraction.
- No new database, orchestration framework, planner microservice, capability service, persistence layer, or duplicated runtime.
- Do not refresh eval baselines, change deployment flags/defaults, or retire a fallback unless a checklist item explicitly authorizes and verifies it.
- No UI work is planned. If shared API types force a UI change, record drift and add the frontend build gate before coding it.
- Core authority topology stays: request + safe session context → deterministic T1–T3 → `UNDERSTANDING` sufficiency → optional bounded T4 for unresolved semantics → deterministic validation/merge → final RQC → clarification or final owner → ResourcePlan + PhaseContract → existing deterministic compile/schedule seam → existing RP execution hub → minimal derived EvidenceState → deterministic `EVIDENCE` sufficiency → InvestigationOutcome → governed narration → deterministic final validation → optional separately governed Phase 10 actions → safe Phase 11 continuity. Only a recorded `REQUIRED_BY_MEASURED_USE_CASE` decision may add the minimum justified full step-instance execution, detailed per-step evidence ledger, or one-round PlanDelta without changing those authority owners.

## Stop conditions

- Stop before **P0** unless the recorded full frozen architecture commit contains `architecture.md`
  with the recorded SHA-256.
- Stop before item **P1** if Plan 7 is neither complete nor explicitly superseded.
- Stop at **P8_ADVANCED_EXECUTION_EXTENSION_GATE** for an explicit decision; never self-approve `REQUIRED_BY_MEASURED_USE_CASE`.
- **U3** inherits/revalidates Plan 7 C3; stop rather than changing dispatch-v2, the model/provider, timeout/deadline, serving mode, flags, defaults, or production posture.
- Stop before any SPL generation/lifecycle code change until **SPL0** records the current extraction→RQC→generation→source-resolution→postprocessing→validation→authorization map.
- Stop if REL0 would require automatic Cisco LLM restart, a new sidecar/service, or a model/provider/timeout/deployment change. Restart remains human-only.
- If any item or verification requires a Cisco model/service restart, STOP with
  `HUMAN_RESTART_REQUIRED`, present the health/failure evidence, and request the human operation.
  The coding agent may resume only to verify readiness/health after the human reports the restart;
  it may never perform, trigger, schedule, or approve the restart.
- Stop before **X3** if P0 lacks a completed Plan 7 A7 result or an explicit user-approved supersession disposition.
- Stop and report drift if the final RQC cannot become pre-plan authority without changing a published API contract or deployment posture not covered here.
- Stop when the same verification gate fails twice on one item, or when a policy/authority tradeoff requires user direction.
- Complete only when the Done definition is satisfied, conditional items have explicit dispositions, and the final re-audit passes.

## Dependency order

### Core path

```text
P0 → P1 → S0 → U0 → U1 → U2 → R0 → R1 → C0
  → E0A → D0 → OUT0 → O0 → O1 → O1A → X0 → X2 → G0 → G1
```

Required core branches:

```text
P1 → SEC0 ───────────────────────────────→ O0
P1 → SPL0; SPL0 + R0 + C0 → SPL1 → AUTH0 → G0
U2 → U3 → REL0 ──────────────────────────→ G0
P0 → X3 ─────────────────────────────────→ G0
```

### Conditional advanced extension path

```text
P1 + measured core evidence
        ↓
P8_ADVANCED_EXECUTION_EXTENSION_GATE
   ├─ NOT_REQUIRED_FOR_CURRENT_SCOPE
   │    → record explicit deferrals
   │
   └─ REQUIRED_BY_MEASURED_USE_CASE
        → only the justified subset of:
          R2, C1, E0, E1, D1, D2
```

E1 means detailed per-step/producer-instance attribution only; E0A minimal EvidenceState is core and outside the gate. Conditional items depend on the gate's recorded `REQUIRED_BY_MEASURED_USE_CASE` decision plus only their genuine technical prerequisites; do not force the whole package. X1 is separately evidence-gated after X0. G0 requires recorded dispositions for the advanced package and X1.

## Checklist

### P — authority prerequisites and baseline

- [x] **P0 — Record Plan 7 disposition and freeze overlapping decisions**
  - **Do:** Add a dated disposition note stating whether Plan 7 completed or was explicitly superseded; copy its final A3, A6, A7, C3, deployment posture, and gate evidence without changing or reopening them. Attribute `V2_OFF_PENDING_WIDER_EVIDENCE` to A6 and `REMEDIATE_EXISTING_T4_IN_PLACE` to C3. If Plan 7 was superseded before A7 completion, record the explicit user-approved fallback disposition required before Plan 8 can start.
  - **Verify:** `rg -n "Plan 7 disposition|A3|A6|A7|C3|V2_OFF_PENDING_WIDER_EVIDENCE|REMEDIATE_EXISTING_T4_IN_PLACE|deployment posture" plans/2026-08-15_0602_canonical-architecture-authority-convergence.md`; confirm completed Plan 7 evidence or explicit user supersession/disposition is recorded.
  - **Depends on:** Plan 7 completion or explicit user-approved supersession.
  - **Evidence:** Plan 7 **completed** (not superseded): 25/25, merged PR #134 @ `c248cb40862335c30febdf588f3d5ca23a38d4a7` on top of Plan 6 PR #132. Dated disposition § **Plan 7 disposition (P0, 2026-08-16)** copies A2 OPTION A, A3, A6 `V2_OFF_PENDING_WIDER_EVIDENCE`, A7 `LEGACY_FALLBACK_ROLLBACK_ONLY_RETAIN_TEMPORARILY`, C3 `REMEDIATE_EXISTING_T4_IN_PLACE`, E2 `RESOURCEPLAN_AUTHORITY=APPROVED` / `PRODUCTION_GO_LIVE=DEFERRED / NO-GO`, deployment posture, and E1 11/11 gates. Architecture freeze verified: `a8f02e3c98b866bcb12c7d5b3db75b11e823609b` / SHA-256 `c1c4ba8a88d8f245752188a76442102978eceb0c1bdb410717b789649fb9a034`. F1/F2 → REL0; F3 `T4_SEMANTICALLY_VIABLE_BUT_VPS_SERVING_BLOCKER` remains CRITICAL BLOCKER (REL0 must not claim to solve serving capacity). Live MCP unproven; MITRE deferred. `architecture.md` unmodified. Verify: see command output recorded at check-off; P0 is DOCUMENTATION_ONLY — no runtime change.

- [x] **P1 — Capture a no-drift architecture baseline**
  - **Do:** Add/extend a baseline test corpus covering: explain-only SPL; supplied-alert investigation; failed VPN administrator logins from `203.0.113.24` yesterday; failed VPN logins by privileged users from Germany; a T4-heavy lateral-movement question; MITRE follow-up; “What about service accounts?”; an untrusted-evidence instruction; exact-call authorization mutation; and T4 saturation/failure without restart. Record final RQC constraints, clarification, route owner, plan/phase schedule, minimal evidence inputs, sufficiency, current result/outcome seams, SPL lifecycle/authorization, trust boundary, T4 reliability evidence, and execution authority.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_canonical_architecture_authority_baseline.py -q`
  - **Depends on:** P0.
  - **Evidence:** `app/tests/test_canonical_architecture_authority_baseline.py` — `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_canonical_architecture_authority_baseline.py -q` → **11 passed**. Corpus: explain-only SPL, supplied-alert, VPN admin `203.0.113.24` yesterday, privileged VPN from Germany, T4-heavy lateral movement (stubbed failing provider), MITRE follow-up, “What about service accounts?”, untrusted-evidence instruction, exact-call auth mutation, T4 saturation without restart. Snapshots record RQC/clarification/route/plan/evidence/sufficiency/outcome/SPL/trust/T4/execution keys. Invariants pinned: `execution_enabled=false`, `candidate_spl`/`validation` `execution_eligible` null/false, unapproved `normalized_spl=null`, MCP not executed, v2 OFF and not winning, ResourcePlan execution ON. AUTH0 recorded **PARTIAL**: mutated approved SPL is not fingerprint-rejected (same `mcp_global_execution_disabled` block). T4 timeout/fail keeps deterministic contract; `semantic_t4_understanding.py` has no restart/`runtime_control` import; planner/graph have no `request_control`/`restart_service`. AUDIT_ONLY — no runtime correction. Not evidence of F3 serving, live MCP, or GO. `architecture.md` unmodified.

- [ ] **P8_ADVANCED_EXECUTION_EXTENSION_GATE — Decide whether advanced execution extensions are required**
  - **Do:** Present P1 plus available core-item evidence for required canonical use cases. Record an explicit decision: `NOT_REQUIRED_FOR_CURRENT_SCOPE` or `REQUIRED_BY_MEASURED_USE_CASE`. For `NOT_REQUIRED_FOR_CURRENT_SCOPE`, explicitly defer R2/C1/E0/E1/D1/D2 without treating them as architecture failures. For `REQUIRED_BY_MEASURED_USE_CASE`, identify the exact failing use case and minimum justified subset. Do not self-approve the latter or generalize one case into an agentic-loop redesign.
  - **Verify:** `rg -n "P8_ADVANCED_EXECUTION_EXTENSION_GATE|NOT_REQUIRED_FOR_CURRENT_SCOPE|REQUIRED_BY_MEASURED_USE_CASE|measured use case|minimum justified subset" plans/2026-08-15_0602_canonical-architecture-authority-convergence.md`; decision and evidence citation are recorded, and every conditional item has an explicit disposition/dependency.
  - **Depends on:** P1 and sufficient measured core evidence to answer the gate. Invoke before any conditional item and resolve before G0.
  - **STOP:** explicit decision required; never self-approve `REQUIRED_BY_MEASURED_USE_CASE`.
  - **Evidence:** _(fill when decided)_

### S — shared sufficiency contract

- [x] **S0 — Introduce the staged sufficiency result without changing behavior**
  - **Do:** Add a small result/adapter contract over existing deterministic checks with `stage`, `status`, `required`, `available`, `missing`, `locked`, `unresolved`, `reason_codes`, and `next_action`. `next_action` is derived deterministically from existing policy/state. This object is not a planner, router, policy engine, or LLM authority. Do not replace existing qualification/completeness/context-sufficiency rules.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_shared_sufficiency_contract.py app/tests/test_context_sufficiency_stage3j.py -q`
  - **Depends on:** P1.
  - **Evidence:** `app/chat/contracts/staged_sufficiency.py` adapter only — `StagedSufficiencyResult` + `from_context_sufficiency` / `from_understanding_state`; `next_action` derived (`CONTINUE`/`CALL_T4`/`CLARIFY`/`DEGRADE`/`BLOCK`); EVIDENCE cannot `CALL_T4`. Existing `check_context_sufficiency` unchanged. Verify: `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_shared_sufficiency_contract.py app/tests/test_context_sufficiency_stage3j.py -q` → **23 passed**. Not wired into `/chat`. `architecture.md` unmodified.

### U — understanding, T4, and deterministic merge

- [x] **U0 — Emit explicit locked and unresolved RQC fields after T1–T3**
  - **Do:** Make the deterministic understanding stage evaluate job-aware requirements and produce an `UNDERSTANDING` sufficiency result. Classify explicit entities, user constraints, explicit time scope, deterministic facts/prohibitions, and already-established user/policy requirements as authoritative/observed fields; lock them against T4 changes. Name only genuinely unresolved semantic fields. Mark capability/evidence representations, route hints, and other downstream consequences as derived fields to be recomputed deterministically—without weakening locked requirements—after final understanding; do not build another understanding system.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_understanding_sufficiency.py app/tests/test_resolved_query_contract.py app/tests/test_canonical_architecture_authority_baseline.py -q`
  - **Depends on:** S0.
  - **Evidence:** `build_resolved_query_contract` now attaches `locked_fields` / `unresolved_fields` / `derived_field_names` / `understanding_sufficiency`. T1–T3 lock intent/answer_goal/entities/time; T4 names `semantic_goal` only; capabilities stay derived; clarification does not `CALL_T4`. Verify → **23 passed**. Neighbor `test_semantic_t4_understanding.py` **14 passed**. `architecture.md` unmodified.

- [x] **U1 — Make T4 invocation job-aware and field-constrained**
  - **Do:** Invoke the bounded semantic hop only when deterministic `UNDERSTANDING` sufficiency permits `CALL_T4`; give it the unresolved query fragment, authoritative/observed locked-field map, allowed semantic vocabulary, and a strict schema limited to unresolved semantic fields. T4 may propose `clarification_required=true` plus a focused `clarification_question` when meaning cannot be inferred safely. It may not clear a deterministic clarification/prohibition or directly grant capabilities, tools, resources, routes, actions, or authorization. Keep one call, deadline, no tool/MCP access, redacted tracing, and deterministic fallback.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_semantic_t4_understanding.py app/tests/test_t4_job_aware_invocation.py -q`
  - **Depends on:** U0.
  - **Evidence:** `maybe_enrich_t4_semantic` now requires `understanding_sufficiency.next_action==CALL_T4`; prompt carries `unresolved_query_fragment` + locked map; JSON schema omits `intent_family`/`required_capabilities`/`answer_goal`. Verify → **18 passed**. No Cisco restart path. `architecture.md` unmodified.

- [x] **U2 — Validate and merge only unresolved T4 fields**
  - **Do:** Reject changes to authoritative/observed or locked fields, unknown semantic values, contradictions, fabricated identifiers, direct capability/tool/resource/route/action/authorization grants, and invalid time scopes. Accept a proposed clarification only when it strengthens safety; never accept clearing of deterministic clarification or prohibitions. Merge only validated unresolved semantic interpretation, then deterministically recompute capability requirements, evidence requirements, route hints, and other derived fields without weakening locked requirements.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_semantic_t4_understanding.py app/tests/test_t4_contract_merge_authority.py app/tests/test_resolved_query_contract.py -q`
  - **Depends on:** U1.
  - **Evidence:** `_merge_proposal` now rejects locked `entities.*` / `time_scope` / `normalized_goal` changes, then recomputes required/prohibited capabilities from locked intent family (union locked prohibitions; never drop locked required). NEW `test_t4_contract_merge_authority.py`. Verify → **28 passed**. Neighbor T4 job-aware + C3 shapes/diagnostics + P1 baseline → **41 passed**. `architecture.md` unmodified.

- [x] **U3 — Revalidate the inherited Plan 7 T4 posture after contract changes**
  - **Do:** Re-run a reproducible read-only T4 serving/contract check after U2 and compare semantic acceptance, timeout, malformed output, clarification, locked-field integrity, and safety behavior with the final inherited Plan 7 posture. Preserve C3 `REMEDIATE_EXISTING_T4_IN_PLACE`; do not change model/provider, timeout/deadline, serving mode, flags/defaults, or deployment posture. Any new serving decision requires a separate explicit user-approved architecture/operations decision.
  - **Verify:** `PYTHONPATH=backend:. python3 scripts/eval_canonical_t4_serving.py --check`; `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_semantic_t4_understanding.py app/tests/test_t4_job_aware_invocation.py -q`; attach accepted/timeout/rejected counts and p50/p95 latency.
  - **Depends on:** U2 and inherited Plan 7 C3 evidence. Evidence-only; C3 is not reopened.
  - **Evidence:** NEW `scripts/eval_canonical_t4_serving.py --check` → **ok**, 0 safety failures. Pytest → **18 passed**. Host live hop: `provider_unavailable` (`host.docker.internal`; discarded C3 defect). In-container live: invoked **1** / accepted **1** / timed_out **0**, p50=p95 **62216 ms**; 4/4 C3 queries skipped (`CLARIFY`, U1). Locked facts preserved, widening 0. C3 `REMEDIATE_EXISTING_T4_IN_PLACE` preserved. **F3 not claimed solved.** No Cisco restart. `docs/evals/plan8/u3_t4_revalidation.md`. `architecture.md` unmodified.

- [x] **REL0 — Establish bounded T4 circuit/backpressure semantics with human-only restart**
  - **Do:** Audit the existing T4 client/serving seam for health detection, current concurrency/slot behavior, bounded queueing, repeated-failure evidence, circuit state, saturation handling, operator-visible diagnostics, the human restart procedure, and post-restart health verification. Reuse that seam to add only missing deterministic circuit-breaker/backpressure behavior. Permit `CLOSED`, `OPEN`, `HALF_OPEN` or equivalent states, bounded concurrency/queueing, deterministic timeout/degrade/clarification, and `HUMAN ACTION REQUIRED` diagnostics. Never automatically restart Cisco Foundation-Sec, authorize restart from a model/worker/agent/ResourcePlanner, add a restart loop, add a sidecar/service, or change model/provider/timeout/config/deployment posture. Thresholds remain deployment configuration.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_t4_circuit_breaker.py app/tests/test_t4_backpressure.py app/tests/test_t4_human_restart_authority.py app/tests/test_semantic_t4_understanding.py -q`; static trace proves no failure path invokes a restart command/API and records health evidence → OPEN/degrade → human action → external/manual restart → health verification → HALF_OPEN/CLOSED.
  - **Depends on:** U3. Preserve inherited C3 `REMEDIATE_EXISTING_T4_IN_PLACE`; no new serving decision is authorized.
  - **Evidence:** Extended existing `sidecar_governance.run_sidecar_llm_with_timeout` (slot semaphore reused). Circuit `CLOSED`/`OPEN`/`HALF_OPEN`; OPEN sheds with `human_action_required_model_restart`; `request_human_model_restart` / `record_manual_model_restart` never execute a restart; HALF_OPEN only after operator inference-health (not `/v1/models`). Verify → **25 passed**. Neighbor slot/D1/T4 → **19 passed**. Threshold `AI_SOC_T4_CIRCUIT_FAILURE_THRESHOLD` getenv default 3. **F3 not claimed solved. F1 DB signalling not in this T4 seam.** `architecture.md` unmodified.

### R — final RQC, route ownership, and ResourcePlan authority

- [x] **R0 — Make final RQC and clarification authoritative before planning**
  - **Do:** Reorder the canonical seam to complete deterministic/T4 merge and validation, then decide clarification from the final RQC. Clarification must terminate before ResourcePlan creation. Persist the final RQC in the durable handoff.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_final_rqc_precedes_planning.py app/tests/test_canonical_handoff_contract.py app/tests/test_canonical_architecture_authority_baseline.py -q`; static trace shows no call to `plan_evidence_from_canonical` before final RQC validation/clarification.
  - **Depends on:** U2. Deterministic convergence must work whether T4 is unavailable, times out, is disabled, or remains unsuitable for production serving.
  - **Evidence:** Clarification now reads `resolved_query.clarification_required` (final RQC) before `_commit_planned_outcome`. Handoff JSON stores `resolved_query_contract` beside canonical input (no DB migration). `plan_evidence_from_canonical` fail-closes on RQC clarification. T4 disabled in tests. Verify → **15 passed**. Neighbor planning/dual-runtime → **44 passed**. `architecture.md` unmodified.

- [x] **R1 — Commit final route ownership before the sole plan creator**
  - **Do:** Run deterministic route adjudication and create the final route contract from the final RQC before `plan_evidence_from_canonical`. Remove any second post-plan route mutation. Keep one final owner while preserving cross-capability work.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_final_route_precedes_resource_plan.py app/tests/test_route_adjudication_resolved_query.py app/tests/test_dual_runtime_single_orchestration.py -q`
  - **Depends on:** R0.
  - **Evidence:** `_bind_final_route_from_rqc` runs `graph_node_route_resolution`/`graph_node_route_contract` inside `_commit_planned_outcome` before `plan_evidence_from_canonical`; `canonical.routing.primary_skill` takes `final_route`. `run_canonical_planning` skips a second adjudication when `route_adjudication` is already present. Verify → **22 passed**. Neighbor architecture tests **36 passed** with R0. `architecture.md` unmodified.

- [ ] **R2 — CONDITIONAL: provide a thin planner-facing capability view only if measured necessary**
  - **Do:** Use existing resource, skill, phase, MCP, and model registry APIs directly wherever practical. Only if the advanced-extension gate records a stable joined view as necessary, add a thin immutable read-only adapter over metadata those authoritative registries already expose, with deterministic precedence. Unknown metadata stays `unknown`/`not_declared`; never invent estimates or add telemetry, measurement work, persistence, another registry/service, or another source of truth.
  - **Verify:** If implemented: `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_planner_capability_snapshot.py app/tests/test_resource_registry.py app/tests/test_mcp_registry.py -q`. If deferred: the gate evidence names R2 and records `NOT_REQUIRED_FOR_CURRENT_SCOPE` with the direct existing APIs used by C0.
  - **Depends on:** R1 and `P8_ADVANCED_EXECUTION_EXTENSION_GATE=REQUIRED_BY_MEASURED_USE_CASE` naming R2. Otherwise close with approved `NOT_REQUIRED_FOR_CURRENT_SCOPE` evidence.
  - **Evidence:** _(fill when done)_

### C — ResourcePlan and compilation

- [x] **C0 — Plan from final requirements, not the primary skill’s capability list**
  - **Do:** Change the sole ResourcePlan creator to consume final RQC, final ownership route, existing policy/session facts, and existing registered capabilities. Remove the composer’s primary-skill SPL deletion/MCP veto while preserving deterministic policy, onboarding, schedule-level capability, SPL, HIL/RBAC, and MCP gates. Use existing ResourcePlan fields and registry APIs. Add dependencies/evidence/fallback/retry/stop fields only if a required use case or failing verification proves a minimum schema evolution necessary; do not redesign the schema speculatively.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_plan_from_final_rqc.py app/tests/test_skill_contract_planning.py app/tests/test_phase_schedule_merge.py app/tests/test_canonical_architecture_authority_baseline.py -q`
  - **Depends on:** R1. R2 is not required unless C0 produces measured evidence and the advanced-extension gate explicitly authorizes it.
  - **Evidence:** Composer no longer deletes SPL/MCP from `knowledge_recall` skill contracts; `mcp_allowed=false` still blocks MCP via `mcp_not_allowed_by_evidence_plan`. Final RQC `required_capabilities` overlay `needs_spl`/`needs_mcp` in `plan_evidence_from_canonical` before compose. No new capability snapshot (R2 not required). Verify → **35 passed**. Neighbor `test_planner_composer_parity.py` updated for evidence-plan MCP block (not skill veto). `architecture.md` unmodified.

- [ ] **C1 — CONDITIONAL: compile step instances plus lifecycle boundaries**
  - **Do:** Extend the existing execution compiler/merge so each executable plan step has an ordered instance in dependency waves and a lifecycle binding. Repeatable read-only SPL/MCP/RAG steps may appear multiple times; side-effecting work remains `max_attempts=1`. Preserve deterministic ordering validation and Plan 7 A3 lifecycle insertion on `no_schedulable_step`.
  - **Verify:** If implemented: `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_plan_step_instance_schedule.py app/tests/test_resource_plan_execution_scheduler.py app/tests/test_phase_schedule_merge.py app/tests/test_plan7_a0_mandatory_phase_survives_no_schedulable_step.py app/tests/test_phase_refinement_bound.py -q`. If deferred: the gate evidence names C1 and records `NOT_REQUIRED_FOR_CURRENT_SCOPE` with the measured core cases satisfied by the existing compiler.
  - **Depends on:** C0 and `P8_ADVANCED_EXECUTION_EXTENSION_GATE=REQUIRED_BY_MEASURED_USE_CASE` naming C1. Otherwise close with approved `NOT_REQUIRED_FOR_CURRENT_SCOPE` evidence.
  - **Evidence:** _(fill when done)_

### SPL — constraint fidelity and call authorization

- [ ] **SPL0 — Audit current SPL entity, lifecycle, validation, and authorization ownership**
  - **Do:** Before changing SPL code, answer from production code: (1) where source IP, destination IP, host, user, domain, port, geography, and time are extracted; (2) which are stored in final RQC; (3) which fields reach `workflow_spl`/generation; (4) exactly what `spl_source_resolve` does; (5) exactly what `spl_postprocessor` does; (6) where `normalized_spl` is validated; (7) whether validation proves mandatory final-RQC constraints survived; (8) where Splunk/MCP authorization is enforced; and (9) whether authorization is tool-level only or bound to the final normalized call. Classify every role `EXISTS`, `PARTIAL`, `MISSING`, or `MISPLACED`. Preserve Plan 7 A2/A3 lifecycle ownership; this audit does not choose a new owner.
  - **Verify:** `rg -n "source_ip|destination_ip|host|user|domain|port|geo|time_scope|workflow_spl|spl_source_resolve|spl_postprocessor|normalized_spl|mcp_execution_gate|approval|confirmation|RBAC|HIL" backend/app/chat backend/app/query_understanding backend/app/spl backend/app/safeguards backend/app/orchestration backend/app/connectors/mcp`; attach a nine-answer code/line map and classifications to `docs/architecture/canonical_architecture_audit_2026-08-15.md` without changing runtime.
  - **Depends on:** P1. Must complete before SPL1, AUTH0, or any SPL generation/lifecycle implementation.
  - **Evidence:** _(fill when done)_

- [ ] **SPL1 — Preserve final-RQC entities and mandatory constraints through normalized SPL**
  - **Do:** Pass explicit final-RQC entities/constraints into ResourcePlan evidence requirements and the existing SPL generation seam. Keep `spl_source_resolve` responsible for governed source-profile field mapping and `spl_postprocessor`/deterministic validation responsible for mandatory-constraint preservation and execution policy. Every relevant mandatory RQC constraint must appear in `normalized_spl` or have an explicit deterministic non-applicability reason. Permit deterministic repair only through an existing unambiguous governed mapping; otherwise reject, request governed regeneration, or clarify. Never silently widen/drop a constraint or let an LLM invent an IP/user/host/domain/time filter.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_spl_rqc_constraint_flow.py app/tests/test_spl_mandatory_constraint_preservation.py app/tests/test_spl_source_resolve.py app/tests/test_review_only_spl_postprocessor.py app/tests/test_spl_validator.py -q`; include the failed-VPN-admin-login/source-IP/yesterday case and negative tests for silent source-IP, account-type, geography, and time-scope loss.
  - **Depends on:** SPL0, R0, and C0.
  - **Evidence:** _(fill when done)_

- [ ] **AUTH0 — Bind Splunk authorization to the final governed call**
  - **Do:** Extend existing policy/RBAC/HIL/MCP/confirmation seams where practical so an execution decision binds the authenticated identity, investigation/trace, Splunk connection/tool, source/index scope, validated `normalized_spl` plus fingerprint, time range, permitted operators, read-only/write classification, result/timeout/resource limits, HIL state, and expiry/one-run scope where available/applicable. A material change to normalized SPL, time/source scope, connection/tool, identity, or limits invalidates the grant and forces re-evaluation. Do not add an authorization service or treat generic Splunk/MCP access as per-call approval.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_splunk_call_authorization.py app/tests/test_mcp_execution_gate.py app/tests/test_explicit_run_spl_hil.py app/tests/test_mcp_rbac.py app/tests/test_mcp_execution_contract_e2e.py -q`; tests prove exact-call acceptance and rejection after normalized-SPL fingerprint, time range, source scope, connection/tool, identity, HIL, expiry, or limit changes.
  - **Depends on:** SPL1 and the authorization-granularity findings recorded by SPL0.
  - **Evidence:** _(fill when done)_

### E — execution hub and evidence attribution

- [x] **E0A — Establish the minimal canonical EvidenceState from existing governed state**
  - **Do:** Audit existing `SourceEvidence`, `StructuredContext`, `CanonicalFacts`, MCP/execution state, and final-evidence fields, then extend or project the minimum deterministic derived view containing required, obtained, missing, stale, invalidated, and blocked evidence plus provenance, trust class, scope, and observed-at/freshness metadata where available. Do not require plan-step IDs, create an evidence database/persistence layer, duplicate raw evidence, or change evidence authority. Use an equivalent existing production type if it already satisfies the role.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_minimal_evidence_state.py app/tests/test_source_evidence.py app/tests/test_structured_context.py app/tests/test_final_evidence_gate.py -q`; tests prove the view is derived from current state, preserves provenance/trust/scope, and does not duplicate raw evidence.
  - **Depends on:** C0 and S0.
  - **Evidence:** `MinimalEvidenceState` projects SourceEvidence/StructuredContext/RQC/`evidence_plan`/CanonicalFacts/FinalEvidenceGate; `GatedEvidenceState` remains classification/permission authority and does not satisfy the required/obtained/missing vocabulary. `graph_node_context_finalize` attaches `state["evidence_state"]` (declared on `ChatPipelineState`). No preview_rows/raw store. Verify → **28 passed**. `architecture.md` unmodified. Anchor note: `test_source_evidence.py` / `test_structured_context.py` did not previously exist; created as E0A derivation proofs (existing coverage remains in `test_evidence_context.py` / `test_source_evidence_envelope_sanitizer.py`).

- [ ] **E0 — CONDITIONAL: execute compiled step instances in the existing RP graph**
  - **Do:** Adapt the existing Resource Planner execution hub to consume and execute each compiled step instance with its declared inputs, deterministic policy gate, timeout/retry/fallback, and typed output. Primarily replace the collapsed capability-level hook consumption; do not create new worker-node families, another execution graph, a second executor, or another runtime abstraction. Keep the existing deterministic workers, HIL/RBAC, SPL validation, MCP eligibility, and execution boundaries authoritative.
  - **Verify:** If implemented: `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_planner_step_instance_execution.py app/tests/test_resource_planner_topology_contract.py app/tests/test_resource_plan_dispatch_switch.py app/tests/test_resource_plan_execution_handoffs.py -q`. If deferred: the gate evidence names E0 and records `NOT_REQUIRED_FOR_CURRENT_SCOPE` with the required cases satisfied by the existing RP hub.
  - **Depends on:** C1 and `P8_ADVANCED_EXECUTION_EXTENSION_GATE=REQUIRED_BY_MEASURED_USE_CASE` naming E0. Otherwise close with approved `NOT_REQUIRED_FOR_CURRENT_SCOPE` evidence.
  - **Evidence:** _(fill when done)_

- [ ] **E1 — CONDITIONAL: add detailed per-step/producer EvidenceState attribution**
  - **Do:** Only when the advanced gate proves it necessary, extend E0A's minimal view with plan `step_id`/producer-instance attribution, required/produced evidence keys, execution status, deterministic failure reason, and policy/sensitivity status wherever those values already exist. It is not an evidence database or new authority. Do not duplicate or mutate raw/historical evidence, store prompts/secrets/credentials, or use LLM confidence as authority.
  - **Verify:** If implemented: `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_evidence_state_attribution.py app/tests/test_minimal_evidence_state.py app/tests/test_source_evidence.py app/tests/test_structured_context.py -q`. If deferred: the gate evidence names E1 and records `NOT_REQUIRED_FOR_CURRENT_SCOPE`, with E0A remaining the complete core view.
  - **Depends on:** E0A and `P8_ADVANCED_EXECUTION_EXTENSION_GATE=REQUIRED_BY_MEASURED_USE_CASE` naming E1. E0 is required only if the measured attribution case needs executed step instances. Otherwise close with approved `NOT_REQUIRED_FOR_CURRENT_SCOPE` evidence.
  - **Evidence:** _(fill when done)_

### D — EVIDENCE sufficiency and bounded PlanDelta loop

- [x] **D0 — Move the real EVIDENCE sufficiency decision into the graph node**
  - **Do:** Replace the `pending_finalize` surface with the shared deterministic evaluator comparing final-RQC required evidence to E0A's minimal canonical EvidenceState. Return `SUFFICIENT`, `PARTIAL`, `INSUFFICIENT`, or `BLOCKED`, missing/stale/invalidated/blocked evidence, stop reason, and a deterministic next action before outcome/synthesis. Do not require detailed per-step attribution and do not turn sufficiency into new policy authority.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_planner_evidence_sufficiency.py app/tests/test_minimal_evidence_state.py app/tests/test_context_sufficiency_stage3j.py app/tests/test_canonical_architecture_authority_baseline.py -q`
  - **Depends on:** E0A.
  - **Evidence:** `rp_node_context_sufficiency` calls `attach_evidence_sufficiency` / `from_evidence_state` (S0 adapter) instead of `pending_finalize`. Stage 3J `context_sufficiency` modes remain on finalize; architecture vocab lives on `state["evidence_sufficiency"]`. Next action never `CALL_T4`. Verify → **32 passed**. Neighbor I/O contract updated for new refs. `architecture.md` unmodified.

- [ ] **D1 — CONDITIONAL: define and validate a targeted PlanDelta**
  - **Do:** Add an immutable targeted delta contract centered on `base_plan_fingerprint`, `target_missing_evidence`, `add_steps`, `modify_unexecuted_steps`, and deterministic rationale/reason codes. `COMPLETED` and `IN_PROGRESS` work, plus any work that has produced a side effect, is immutable; only pending/unresolved, unexecuted work may be modified, and new work may be added only for missing evidence. If future-compatible remove/reorder fields remain, restrict them to unresolved unexecuted work. Validate resource IDs, schemas, policies, dependencies, final-RQC capability bounds, max steps/cost, and fingerprints. A delta cannot change final RQC/route ownership, clear policy, replay side effects, widen capabilities, repeat the same effective plan, or mutate historical evidence.
  - **Verify:** If implemented: `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_plan_delta_contract.py app/tests/test_plan_delta_validation.py app/tests/test_phase_refinement_bound.py -q`. If deferred: the gate evidence names D1 and records `NOT_REQUIRED_FOR_CURRENT_SCOPE` with no required core case needing a delta.
  - **Depends on:** D0 and `P8_ADVANCED_EXECUTION_EXTENSION_GATE=REQUIRED_BY_MEASURED_USE_CASE` naming D1. Otherwise close with approved `NOT_REQUIRED_FOR_CURRENT_SCOPE` evidence.
  - **Evidence:** _(fill when done)_

- [ ] **D2 — CONDITIONAL: wire one bounded evidence-targeted refinement round**
  - **Do:** Enforce a deterministic `MAX_PLAN_DELTA_ROUNDS = 1` (or the equivalent existing constant, not a new deployment control). Flow: E0A minimal EvidenceState (plus E1 detail only when separately justified) → deterministic EVIDENCE sufficiency → if allowed and evidence is missing, create/validate/apply one PlanDelta → execute only new/unresolved work → update the same evidence view → re-evaluate once → outcome/synthesize, degrade, or block. Stop after that one refinement, or earlier on sufficient evidence, no progress, same effective fingerprint, policy block, resource exhaustion, timeout/cost budget, or failed delta validation. Never form an open plan/execute/reason loop.
  - **Verify:** If implemented: `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_planner_bounded_delta_loop.py app/tests/test_plan_delta_single_round.py app/tests/test_plan_delta_validation.py app/tests/test_phase_refinement_bound.py app/tests/test_resource_planner_topology_contract.py -q`. If deferred: the gate evidence names D2 and records `NOT_REQUIRED_FOR_CURRENT_SCOPE` with deterministic synthesize/degrade/block behavior sufficient for current scope.
  - **Depends on:** D1 and `P8_ADVANCED_EXECUTION_EXTENSION_GATE=REQUIRED_BY_MEASURED_USE_CASE` naming D2, plus only C1/E0/E1 prerequisites explicitly justified by the gate decision. Otherwise close with approved `NOT_REQUIRED_FOR_CURRENT_SCOPE` evidence.
  - **Evidence:** _(fill when done)_

### OUT — authoritative investigation result

- [x] **OUT0 — Audit and establish the minimal InvestigationOutcome seam**
  - **Do:** Audit `CanonicalFacts`, `FinalEvidenceGate`, `GovernedSynthesisPackage`, `AnswerContract`, canonical planning outcomes, DecisionRecord/audit logs, and action payload builders for an equivalent post-evidence structured result. Prefer minimally extending or projecting an existing governed final-result package; do not duplicate the pre-execution `CanonicalPlanningOutcome` or the audit-only `DecisionRecord`. Establish the smallest authoritative result after D0 and before synthesis/actions, using existing controlled vocabularies where possible for disposition (`suspicious`, `benign`, `inconclusive`, `blocked` or equivalent), findings, supported/unconfirmed hypotheses, evidence/missing-evidence refs, governed severity/risk facts, recommended actions, policy/action eligibility, and provenance/trace identity. Do not add a database, orchestration graph, decision service, or persistence layer.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_investigation_outcome.py app/tests/test_final_evidence_gate.py app/tests/test_synthesis_package_stage3k1a.py app/tests/test_decision_record.py app/tests/test_synthesis_narration_executor_safety.py -q`; tests prove synthesis inputs and action preparation read the governed outcome, free-form prose cannot change disposition/severity/policy/action eligibility, and no duplicate result authority exists.
  - **Depends on:** D0.
  - **Evidence:** `InvestigationOutcome` projects EvidenceState/sufficiency/FinalEvidenceGate/CanonicalFacts/ActionCapability; attached on `ChatPipelineState` before `run_governed_synthesis_lab`. LLM proposals cannot change disposition/severity/actions. Does not duplicate `CanonicalPlanningOutcome` or `DecisionRecord`. Verify → **46 passed**. `architecture.md` unmodified.

### SEC — untrusted evidence and prompt boundary

- [x] **SEC0 — Enforce trust classes and prompt-injection boundaries at existing seams**
  - **Do:** Audit current prompt builders, governed context packages, MCP/RAG/evidence sanitizers, evidence observer, and final synthesis inputs. Keep deterministic policy/schemas/config/authorization as trusted control; classify user text/uploads as untrusted input; classify logs, RAG documents, MCP/tool results, email/ticket/CRM/retrieved content as untrusted evidence; classify prior assistant/LLM prose as non-authoritative generated content. Delimit and label untrusted evidence as data separately from control instructions. Evidence/generated text cannot grant capabilities, select routes, clear RBAC/HIL, alter policy, authorize actions, or trigger remediation. Reuse existing prompt-building/filter/validator seams; add no security service/model.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_prompt_trust_boundary.py app/tests/test_mcp_result_injection_defense.py app/tests/test_mcp_result_safeguard_p0.py app/tests/test_evidence_observer_pipeline.py app/tests/test_synthesis_narration_executor_safety.py -q`; injection cases embedded in Splunk rows, RAG text, tickets/email/CRM-like content, tool output, and prior assistant prose remain data and cannot alter route/capability/RBAC/HIL/policy/action state.
  - **Depends on:** P1. Must be complete before O0; SPL/MCP execution gates remain separately authoritative.
  - **Evidence:** `app/safeguards/trust_boundary.py` labels architecture trust classes and delimits untrusted blocks. Wired into composer, live narration, and T4 user prompt. Existing MCP injection filter/safeguard/observer unchanged. Verify → **42 passed**. `architecture.md` unmodified.

### O — synthesis/output and session continuity

- [ ] **O0 — Bind synthesis to final RQC, InvestigationOutcome, and governed evidence**
  - **Do:** Pass the final RQC, InvestigationOutcome, minimal EvidenceState/supporting governed evidence, final route/plan summary, and EVIDENCE sufficiency result into the existing governed synthesis package. Keep the model narration-only/no-tools, deterministic disposition/severity/policy/action eligibility authoritative, trust delimiters mandatory, readiness/HIL gates mandatory, fallback deterministic, and final validator always-on. Free-form synthesis cannot become action authority.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_synthesis_final_contract_inputs.py app/tests/test_final_synthesis_skip_policy.py app/tests/test_final_answer_validator.py -q`
  - **Depends on:** OUT0 and SEC0.
  - **Evidence:** _(fill when done)_

- [ ] **O1 — Make safe Phase 11 session continuity a normal Phase 0/1 input**
  - **Do:** Minimally extend existing controlled session pins/handoffs so a new turn can use redacted final-RQC and InvestigationOutcome references, stable entity/time pins, evidence references plus scope/freshness/applicability status, clarification state, and trace/plan identity where needed. Resolve generic follow-up deltas such as “What about service accounts?” through deterministic Phase 1 sufficiency rather than another phrase-only special case. Preserve existing persistence, TTL, replacement/clear behavior, and Phase 10 action compatibility; do not create new session architecture.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_session_canonical_continuity.py app/tests/test_durable_session_store_s6d.py app/tests/test_batch5_session_context.py app/tests/test_canonical_architecture_authority_baseline.py -q`
  - **Depends on:** O0.
  - **Evidence:** _(fill when done)_

- [ ] **O1A — Revalidate prior evidence for a follow-up's final RQC**
  - **Do:** After deterministic session-delta resolution, evaluate prior evidence applicability against the new final RQC across relevant entity/account, host/device, IP/domain, geography, time/freshness, source/index, user/RBAC, investigation purpose, policy, and contradiction/supersession dimensions. Use existing vocabulary if equivalent; otherwise keep the minimum controlled statuses `REUSABLE`, `STALE`, `OUT_OF_SCOPE`, `SUPERSEDED`, `INVALIDATED`, `BLOCKED`. Only reusable evidence may satisfy the new EVIDENCE sufficiency result. Retain unusable historical evidence for provenance; do not delete it or solve follow-up with a phrase catalogue.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_session_evidence_applicability.py app/tests/test_minimal_evidence_state.py app/tests/test_session_canonical_continuity.py app/tests/test_canonical_architecture_authority_baseline.py -q`; the admin→service-account example keeps safe context but marks admin-only evidence out of scope and cannot treat it as sufficient for the service-account RQC.
  - **Depends on:** O1, E0A, and D0.
  - **Evidence:** _(fill when done)_

### X — retirement and documentation

- [ ] **X0 — Re-audit all legacy and duplicate planning/execution seams**
  - **Do:** Trace the retired LLM plan bridge, legacy evidence loop, guided refinement rail, linear graph, dispatch-v2 switch, session SPL-refine path, and imperative fallback. Classify each as production, rollback-only, test-only, or dead before deleting or redirecting anything.
  - **Verify:** `rg -n "llm_plan_bridge|evidence_loop|guided_hybrid_refinement|linear_graph_legacy|dispatch_v2|session_spl_refine|_run_legacy_dispatch_fallback" backend/app backend/app/tests`; attach an import/call graph and classification table to the audit.
  - **Depends on:** O1A.
  - **Evidence:** _(fill when done)_

- [ ] **X1 — CONDITIONAL: retire only explicitly authorized, proven duplicate/dead seams**
  - **Do:** If X0 proves a seam dead/duplicate and explicit retirement authorization is recorded, remove or fence only that seam. Otherwise record `NOT_REQUIRED_FOR_CURRENT_SCOPE` and retain it. Preserve rollback paths and compatibility adapters until separately authorized with parity evidence; no broad deletion by filename or age.
  - **Verify:** If retirement is authorized: `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_dual_runtime_single_orchestration.py app/tests/test_resource_planner_topology_contract.py app/tests/test_resource_plan_dispatch_switch.py -q`; `rg` confirms each retired symbol has no production importer. If retained/deferred: X0 evidence names X1 and records `NOT_REQUIRED_FOR_CURRENT_SCOPE` plus the retained seam classification.
  - **Depends on:** X0 plus explicit evidence-backed retirement authorization. This is separate from the advanced-execution gate.
  - **Evidence:** _(fill when done)_

- [ ] **X2 — Reconcile architecture and operating documentation**
  - **Do:** Update `AGENTS.md`, `CLAUDE.md`, phase/schedule docs, deployment posture, and architecture diagrams to match verified runtime authority. Resolve the contradiction over live final synthesis by recording the approved policy; do not change behavior as a documentation shortcut.
  - **Verify:** `rg -n "No final LLM synthesis|inert flag|dispatch-v2|PhaseContract|PlanDelta|ResolvedQueryContract" AGENTS.md CLAUDE.md docs/architecture docs/coe`; manually trace every claim to code, deployment evidence, or an explicit decision record.
  - **Depends on:** X0. X1 is conditional and does not block documentation reconciliation once its disposition is recorded.
  - **Evidence:** _(fill when done)_

- [ ] **X3 — Reconcile inherited Plan 7 A7 fallback disposition**
  - **Do:** Consume and preserve the already-recorded Plan 7 A7 result; do not reopen A7. If the inherited fallback is retained, preserve its structural tests and disposition. If Plan 7 retired it with proof, do not recreate it. If Plan 7 was explicitly superseded before A7 completion, consume the explicit user-approved P0 disposition before doing anything.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_session_spl_refine_fallback_lifecycle.py app/tests/test_resource_plan_dispatch_switch.py app/tests/test_dual_runtime_single_orchestration.py -q`; `docs/evals/plan7/a7_fallback_lifecycle_proof.md` answers lifecycle ownership, postprocessing, validation, MCP eligibility, HIL/RBAC, and duplicate-execution questions.
  - **Depends on:** P0 and completed Plan 7 A7 evidence, or the explicit supersession disposition recorded by P0.
  - **Evidence:** _(fill when done)_

### G — final gates and skeptical re-audit

- [ ] **G0 — Run targeted, broad, governance, and novel-query gates**
  - **Do:** Run every touched-package test, the full backend suite, governance regression, independent harness, routing/out-of-set probes when intent changes, the baseline corpus from P1, and novel paraphrases. Include outcome authority, evidence reuse/invalidation, SPL constraint-loss, exact-call authorization, prompt-injection, circuit/backpressure, and automatic-restart negative controls. Confirm no baseline artifact drift and no deployment flag/default/model/timeout change. Run frontend build only if drift added a frontend/shared-type change.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest`; `./scripts/run_stage3_governance_regression.sh`; `PYTHONPATH=backend:. python3 -m test_harness.harness.runner --json`; `python3 scripts/eval_out_of_set_intent_probe.py --check`; `git status --short`; plus `cd frontend && npm run build` only if frontend/shared types changed.
  - **Depends on:** X2, X3, REL0, AUTH0, SEC0, OUT0, O1A, a recorded `P8_ADVANCED_EXECUTION_EXTENSION_GATE` decision with every advanced item dispositioned, and an explicit X1 disposition.
  - **Evidence:** _(fill when done with pass/fail counts, commit, flags, and corpus results)_

- [ ] **G1 — Re-audit canonical phases 0–11 and close only with evidence**
  - **Do:** Re-run the source audit against the implemented tree for canonical phases 0–11. Explicitly classify minimal versus detailed EvidenceState, InvestigationOutcome, follow-up evidence applicability, SPL entity/constraint flow, source-resolution versus postprocessor ownership, call-level authorization, trust/prompt boundaries, and T4 circuit/backpressure/human-restart authority. Record production entry, authority owner, inputs/outputs, fallback, tests, and remaining gap for each role. Require zero unexplained `MISPLACED` authority findings and no unapproved `MISSING` role. Record Architecture Phase 10 as an explicit approved deferral and list all approved conditional deferrals; do not silently ignore them.
  - **Verify:** `.cursor/hooks/audit-plan-discipline.sh plans/2026-08-15_0602_canonical-architecture-authority-convergence.md`; review every checklist item’s **Verify** and **Evidence**; `rg -n "MISPLACED|MISSING|deferred|known gap" docs/architecture/canonical_architecture_audit_2026-08-15.md` and confirm each residual has an explicit disposition.
  - **Depends on:** G0.
  - **Evidence:** _(fill when done)_

## Verification gaps

None at amendment time. Commands referencing new tests/harnesses name the exact regression artifact an authorized item must create. SPL0 and OUT0 are audit-first so implementation extends actual production seams rather than presumed schemas. P0/X3 inherit Plan 7 decisions rather than reopening them. U3 revalidates the inherited C3 posture without changing it; REL0 cannot automate restart or alter serving posture. Conditional items cannot execute until the named gate/retirement decision explicitly authorizes them; a deferral is recorded evidence, not permission to leave the item ambiguous.

## Evidence discipline and re-audit

- Execute one item at a time: implement → run its exact verification → record command/result/commit or line evidence → check off → proceed.
- A code diff without a green Verify result is not evidence.
- Re-run affected earlier items after any contract/schema change.
- Before G1, skeptically re-walk inherited checkmarks, deployment posture, mandatory lifecycle preservation, candidate-only SPL, HIL/RBAC, model no-tools posture, and per-step multiplicity.

## Drift log

- **2026-08-15:** Plan authored from the read-only canonical architecture audit at `84ce333`. Plan 7 is still active; this plan is queued and all items remain unchecked.
- **2026-08-15:** Review correction decoupled U3 serving evidence from R0, separated authoritative/observed from deterministically derived understanding fields, constrained R2/E0/EvidenceState/PlanDelta scope, and fixed the refinement bound at one round. No checklist item was started.
- **2026-08-15:** Canonical-architecture amendment made the minimum authority convergence core mandatory and moved step-instance execution, a detailed unified/per-step EvidenceState ledger, PlanDelta/refinement, richer capability view, and dead-seam retirement behind explicit measured-evidence dispositions. Added coding-agent/commit discipline, deferred canonical Phase 10 actions, corrected U3/X3 inheritance, and expanded G1 to phases 0–11. Plan remains queued; no item started.
- **2026-08-15:** Architecture-control amendment made minimal derived EvidenceState, InvestigationOutcome, evidence applicability, SPL constraint preservation, exact-call Splunk authorization, untrusted-evidence prompt boundaries, and T4 circuit/backpressure with human-only restart core. Detailed per-step evidence attribution remains conditional. No Plan 8 item started; Plan 7 decisions, runtime, configuration, services, and baselines were untouched.
- **2026-08-15:** `P8_PRE_IMPLEMENTATION_PLAN_FREEZE` classified all 34 items, preserved 17 current
  architecture corrections, kept seven advanced items conditional, tightened one-item execution,
  invariant/commit, and human-restart STOP rules, and recorded the frozen architecture content hash.
  The architecture commit SHA is unavailable because `architecture.md` is untracked; execution must
  STOP until that full commit SHA is recorded. Plan remains queued with 0/34 checked; no runtime code
  or architecture content was changed.
- **2026-08-16:** **P0 complete.** Plan 7 CLOSED 25/25 and merged at
  `c248cb40862335c30febdf588f3d5ca23a38d4a7`; Plan 6 merged immediately beneath it. Architecture
  freeze re-verified (`a8f02e3` content SHA-256 matches working tree and freeze commit). Disposition
  recorded; overlapping A2/A3/A6/A7/C3/E2 decisions copied and not reopened. F1/F2/F3 carried
  forward unaccepted. Plan status `queued` → `in_progress`. Checklist **1/34**. No runtime code,
  flag, baseline, or `architecture.md` change. P1 not started.
- **2026-08-16:** **P1 complete.** AUDIT_ONLY baseline corpus in
  `backend/app/tests/test_canonical_architecture_authority_baseline.py` (**11 passed**). Safety
  invariants pinned; AUTH0 fingerprint-binding recorded PARTIAL; T4 failure has no restart path.
  No runtime/flag/`architecture.md` change. F3 serving not claimed. Next: S0.
- **2026-08-16:** **S0 complete.** Shared `StagedSufficiencyResult` adapter over existing
  completeness/context-sufficiency checks; no pipeline wiring; 23 passed. Next: U0.
- **2026-08-16:** **U0 complete.** T1–T3 emit locked/unresolved/derived maps and UNDERSTANDING
  sufficiency (`CALL_T4` only for T4 unresolved semantics). Next: U1.
- **2026-08-16:** **U1 complete.** T4 hop gated on CALL_T4; field-constrained prompt/schema.
  Next: U2.
