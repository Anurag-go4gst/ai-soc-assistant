# Plan 7 E0 — architecture authority report

Date: 2026-08-15

Plan: `plans/2026-08-14_1130_resource-plan-authority-and-t4-integration.md`

Frozen architecture: `architecture.md` at `a8f02e3c98b866bcb12c7d5b3db75b11e823609b`

This is an evidence synthesis, not a production decision. It does not approve a risk, change a
flag or default, close a Plan 8 dependency, or declare the system production-ready. E2 remains
the production decision gate.

## Post-E0 bounded convergence amendment (2026-08-15)

This amendment records the user-approved legacy-authority retirement work completed after the
original E0 synthesis. Where the original report below says A7 is open, dispatch-v2 normal
authority is unproven, or development-profile rebuild drift is confirmed, this amendment is the
current Plan 7 evidence:

- A7 disposition is **B — `LEGACY_FALLBACK_ROLLBACK_ONLY_RETAIN_TEMPORARILY`**. Production
  `/chat` on the target Resource Planner graph cannot import/call the fallback. The retained
  rollback branch now runs the mandatory postprocessor before source resolution/execution and
  fails closed when its mutation cannot be revalidated. Evidence:
  `docs/evals/plan7/a7_fallback_lifecycle_proof.md`.
- Dispatch-v2 is retired/fenced from normal authority. With ResourcePlan execution enabled, its
  flag projection and imperative schedule are refused; accidentally setting both flags true does
  not stand down ResourcePlan/PhaseContract. Legacy graph/parity symbols remain historical/test
  compatibility, not production selection.
- The reference checker now compares ResourcePlan, PhaseContract/merge, current dispatch,
  clarification/degrade, and execution fields. It does not read or reconstruct retired
  `pipeline_dispatch.decision` values. All ten rows pass the current baseline and all ten prior
  E1 drifts classify `EXPECTED_AUTHORITY_MIGRATION`.
- P6's `intent_clarification → spl_source_profile_clarification` change is an expected
  deterministic safety improvement: `spl_validation_failed`, `normalized_spl=null`, and
  execution `not_executed` make the missing source-profile prerequisite explicit.
- The tracked `development.env.example` now reconstructs all six approved target values while
  global `config.py` defaults and COE/production profiles remain unchanged. Therefore
  **`CONFIG_REBUILD_DRIFT = CLOSED` for the development profile**.
- Rollback now distinguishes runtime feature rollback from code/release rollback. Dispatch-v2 is
  not maintained as a second routine runtime authority; orchestration rollback deploys the last
  proven release and that release's profile.

This amendment does not mark E1 complete. One final full E1 rerun remains required before E2.

## Evidence basis

The principal committed evidence used here is:

- lifecycle defect, population, ownership and fix:
  `docs/evals/plan7/a0_missed_work_analysis.md`,
  `docs/evals/plan7/a1_structural_population.md`,
  `docs/evals/plan7/a2_stop_decision_packet.md`,
  `docs/evals/plan7/a3_ownership_fix.md`;
- authority acceptance and old-path status:
  `docs/evals/plan7/a4_authority_acceptance.md`,
  `docs/evals/plan7/a5_old_path_audit.md`,
  `docs/evals/plan7/a6_stop_decision_packet.md`, and the unchecked A7 item in
  `plans/2026-08-14_1130_resource-plan-authority-and-t4-integration.md`;
- T4 baseline, serving and controlled remeasurement:
  `docs/evals/plan7/b1_t4_on_baseline.md`,
  `docs/evals/plan7/c2_serving_viability.md`,
  `docs/evals/plan7/c3_manual_vps_evidence.md`,
  `docs/evals/plan7/c3_remediation_evidence.md`, and
  `docs/evals/plan7/c3_remeasurement.json`;
- integrated target evidence:
  `docs/evals/plan7/runs/20260815T131000Z/target_corpus.md`,
  `docs/evals/plan7/runs/20260815T140000Z/d1_reliability.md`,
  `docs/evals/plan7/runs/20260815T145000Z/d2_persistence.md`,
  `docs/evals/plan7/runs/20260815T151500Z/d3_rollback.md`, and
  `docs/evals/plan7/rollback_runbook.md`;
- accepted Plan 6 baseline and risks:
  `plans/2026-08-13_1440_production-activation-t4-serving-and-governance-readiness.md`,
  `docs/evals/plan6/f5_go_live_decision_packet.md`, and
  `docs/evals/plan6/e2_stop_decision.md`.

## Current authority posture

### Persistent VPS effective profile

The following values were read back from the running backend, survived force-recreate, were
restored after the rollback drill, and describe the host's current target posture
(`docs/evals/plan7/runs/20260815T145000Z/d2_persistence.md` and
`docs/evals/plan7/runs/20260815T151500Z/d3_rollback.md`):

| Setting | Effective value |
|---|---|
| `LANGGRAPH_ORCHESTRATION_ENABLED` | `true` |
| `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | `true` |
| `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` | `false` |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` | `true` |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS` | `120` |
| `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED` | `false` |
| `MCP_MODE` | `mock` |

The winning source is the untracked VPS `.env`, loaded after the tracked
`env/profiles/development.env.example`; the host selects `AI_SOC_ENV_PROFILE=development`
(`docs/evals/plan7/env_authority_chain.md`).

### Repository and tracked defaults

No repository default was changed to create the effective posture. The tracked development seed
and code defaults remain conservative or different from the target as shown below
(`docs/evals/plan7/runs/20260815T151500Z/d3_rollback.md`):

| Setting | Tracked development seed | Code default when absent |
|---|---|---|
| `LANGGRAPH_ORCHESTRATION_ENABLED` | `true` | `true` |
| `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | `false` | `false` |
| `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` | `true` | `false` |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` | absent | `false` |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS` | absent | `2.0` |
| `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED` | `false` | `false` |

The VPS-only `120`-second T4 bound is not a universal architectural constant, and this report
does not propose making it one (`docs/evals/plan7/c3_remediation_evidence.md`).

## The twelve Plan 7 success questions

### Q1

**QUESTION:** Why are `p6.multi.knowledge_spl_mcp` and `p6.live_posture.d1_003`
`no_schedulable_step`?

**VERDICT:** `PROVEN`

**EVIDENCE:** `docs/evals/plan7/a0_missed_work_analysis.md`.

**EXPLANATION:** Their resolved contracts owe the SPL lifecycle, but their ResourcePlans expose
no live purpose that `_compile_hooks` can map to a hook. The compiler returns
`no_schedulable_step`; the old merge then returned before applying the already-resolved
PhaseContract. With dispatch-v2 off, the predicate fallback produced an SPL candidate without
the mandatory `spl_postprocessor` phase. The control row with the same contract shape merged
normally, proving that the discriminator was the plan's schedulable purposes rather than query
identity.

**REMAINING_GAP:** None for the causal mechanism. Runtime variants produced by blocked steps
remain possible, which is why the structural trigger—not the observed query IDs—must remain the
test oracle (`docs/evals/plan7/a1_structural_population.md`).

### Q2

**QUESTION:** Who should own `spl_postprocessor`—ResourcePlan step, PhaseContract lifecycle,
compiler, execution seam, or a legacy behaviour needing migration?

**VERDICT:** `PROVEN`

**EVIDENCE:** the user-approved A2 decision in
`plans/2026-08-14_1130_resource-plan-authority-and-t4-integration.md`, with implementation proof
in `docs/evals/plan7/a3_ownership_fix.md`.

**EXPLANATION:** PhaseContract/PhasePolicy owns the mandatory lifecycle obligation. ResourcePlan
and its compiler own schedulable resource work. The merge is the deterministic point where those
authorities are combined. A resource-plan downgrade may remove unavailable resource work, but it
may not erase an applicable mandatory lifecycle phase. This is an explicit migration of the
lifecycle guarantee away from dispatch-v2 dependence, not a new ResourcePlan step and not an
execution-seam compensator.

**REMAINING_GAP:** The separate legacy fallback path has not yet been proven to respect that
ownership; that is A7, not a reason to move ownership again.

### Q3

**QUESTION:** What is the deterministic applicability condition under which it must execute?

**VERDICT:** `PROVEN`

**EVIDENCE:** `docs/evals/plan7/a1_structural_population.md` and
`docs/evals/plan7/a3_ownership_fix.md`.

**EXPLANATION:** The lifecycle-only merge path applies when the compiler downgraded, the plan
still resolves to a valid execution contract, and that PhaseContract declares at least one
hook-bound mandatory phase. For SPL specifically, PhasePolicy marks `spl_postprocessor`
mandatory when SPL is required by capabilities or candidate evidence; it does not depend on a
schedulable `spl_artifact` ResourcePlan step. Invalid or unsafe plans still fail closed.

**REMAINING_GAP:** A7 must prove that a path which bypasses this merge cannot bypass the same
mandatory validation.

### Q4

**QUESTION:** How many rows share that structural condition beyond the two examples?

**VERDICT:** `PROVEN_WITH_LIMITATION`

**EVIDENCE:** `docs/evals/plan7/a1_structural_population.md` and
`docs/evals/plan7/a3_ownership_fix.md`.

**EXPLANATION:** The pre-fix measured population was six distinct affected rows: five found in
the 175-row offline sweep and one runtime-only row. That is four rows beyond the two initial
examples. After A3, the same 175-row sweep found zero affected rows while compiler downgrade
verdicts remained unchanged (`docs/evals/plan7/a3_ownership_fix.md`).

**REMAINING_GAP:** Six is a lower bound, not a ceiling. The offline sweep used deterministic
routing and did not model every blocked-step/runtime state; the runtime-only member demonstrates
that limitation (`docs/evals/plan7/a1_structural_population.md`).

### Q5

**QUESTION:** With exec on, dispatch-v2 off and T4 on, is mandatory work missed anywhere or
duplicated anywhere?

**VERDICT:** `PROVEN_WITH_LIMITATION`

**EVIDENCE:** `docs/evals/plan7/a4_authority_acceptance.md`,
`docs/evals/plan7/runs/20260815T131000Z/target_corpus.md`, and
`docs/evals/plan7/runs/20260815T140000Z/d1_reliability.md`.

**EXPLANATION:** No missed mandatory phase, duplicate execution, or merge-plus-old-engine
double-run was observed in A4. The integrated target corpus completed 30 rows with zero errors;
no SPL seam row lacked `spl_postprocessor`, no candidate became executable, and no MCP action
executed (`docs/evals/plan7/runs/20260815T131000Z/target_corpus.md`). D1 observed one gate call
and zero allowed calls across its reliability run, with no duplicate side effect
(`docs/evals/plan7/runs/20260815T140000Z/d1_reliability.md`).

**REMAINING_GAP:** The statement is bounded to measured paths. A7 is unchecked, and the reachable
`session_spl_refine` legacy fallback was not exercised; universal lifecycle ownership is
therefore not proven.

### Q6

**QUESTION:** Can dispatch-v2 stay off as the normal authority?

**VERDICT:** `NOT_PROVEN`

**EVIDENCE:** the approved `V2_OFF_PENDING_WIDER_EVIDENCE` decision in
`plans/2026-08-14_1130_resource-plan-authority-and-t4-integration.md`, plus
`docs/evals/plan7/runs/20260815T131000Z/target_corpus.md`,
`docs/evals/plan7/runs/20260815T145000Z/d2_persistence.md`, and
`docs/evals/plan7/runs/20260815T151500Z/d3_rollback.md`.

**EXPLANATION:** Dispatch-v2 did stay off while ResourcePlan + PhaseContract carried the observed
target runs. D2 and the target-restoration half of D3 observed zero `V2_WINS` rows. That proves
the current target authority observation, but the approved A6 disposition expressly withholds a
production-normal claim.

**REMAINING_GAP:** A7 remains required before the GO gate. Full closure gates are E1, live MCP is
unproven, and bounded pre-SPL discovery has not been shown unnecessary. Therefore this report
does not upgrade `V2_OFF_PENDING_WIDER_EVIDENCE` on its own.

### Q7

**QUESTION:** Does any old path still execute where ResourcePlan + PhaseContract should own the
job?

**VERDICT:** `PROVEN_WITH_LIMITATION`

**EVIDENCE:** `docs/evals/plan7/a5_old_path_audit.md`,
`docs/evals/plan7/a6_stop_decision_packet.md`, and the unchecked A7 item in the current Plan 7.

**EXPLANATION:** No old engine executed beside the merge in the measured A4 traces, and the D0
target corpus observed no legacy-predicate, `session_spl_refine`, or guided-hybrid dispatch
(`docs/evals/plan7/runs/20260815T131000Z/target_corpus.md`). However,
`_run_legacy_dispatch_fallback` remains reachable through `session_spl_refine`, is classified as
migration debt, and still skips `spl_postprocessor` according to the committed A5/A6 evidence.

**REMAINING_GAP:** A7 has no completed evidence artifact. Lifecycle ownership, deterministic SPL
validation, MCP-gate input, HIL/RBAC authority and duplicate-execution behavior on that reachable
path are unproven. It is neither proven unreachable nor classified rollback-only.

### Q8

**QUESTION:** With T4 on, what is the measured invoked, accepted, timeout and fallback profile?

**VERDICT:** `PROVEN_WITH_LIMITATION`

**EVIDENCE:** `docs/evals/plan7/b1_t4_on_baseline.md`,
`docs/evals/plan7/c3_remediation_evidence.md`,
`docs/evals/plan7/c3_remeasurement.json`, and
`docs/evals/plan7/runs/20260815T140000Z/d1_reliability.md`.

**EXPLANATION:** At the original bound T4 was invoked on all 17 measured T4-tier rows, accepted
zero contracts and timed out on all 17 at about two seconds; no T1–T3 row invoked it and the
deterministic fallback preserved clarification and prevented widening
(`docs/evals/plan7/b1_t4_on_baseline.md`). After C3, the same target configuration produced two
accepted proposals in nine attempts, then one in four, followed by a controlled healthy-host run
with four accepted in four attempts; all four controlled cases preserved locked facts and
widened capabilities zero times (`docs/evals/plan7/c3_remediation_evidence.md`). D1 now
distinguishes timeout, provider-unavailable, malformed, pool and slot-busy outcomes and retains
the deterministic contract on failure (`docs/evals/plan7/runs/20260815T140000Z/d1_reliability.md`).

**REMAINING_GAP:** Acceptance is not reproducible under host paging. Earlier generic exception
mapping also weakened historical timeout counts; D1 corrected future classification but did not
rewrite old evidence.

### Q9

**QUESTION:** Does a viable T4 serving posture exist, and what does it prove?

**VERDICT:** `BLOCKED`

**EVIDENCE:** `docs/evals/plan7/c2_serving_viability.md`,
`docs/evals/plan7/c3_remediation_evidence.md`, and
`docs/evals/plan7/runs/20260815T140000Z/d1_reliability.md`.

**EXPLANATION:** The accepted classification is
`T4_SEMANTICALLY_VIABLE_BUT_VPS_SERVING_BLOCKER`. A controlled run proved semantic capability:
four of four proposals were accepted, useful semantic additions were observed, locked facts were
preserved in four of four cases, and capability widening was zero
(`docs/evals/plan7/c3_remediation_evidence.md`). Application integration is proven enough for
Plan 7 architecture testing: only T4-tier rows invoke the hop, output is constrained and then
deterministically validated/merged, and each failure class falls back deterministically
(`docs/evals/plan7/c3_remediation_evidence.md` and
`docs/evals/plan7/runs/20260815T140000Z/d1_reliability.md`). Serving reliability is not proven:
acceptance varied from two of nine to one of four to four of four as host paging changed, and
`/v1/models` remained HTTP 200 while inference was unusable
(`docs/evals/plan7/c3_remediation_evidence.md`).

**REMAINING_GAP:** Stable inference, usable health detection, recovery and reproducibility remain
unresolved. This is a current serving-infrastructure blocker, not a single favorable “T4 PASS.”

### Q10

**QUESTION:** Does the target profile survive restart, reliability, persistence and rollback?

**VERDICT:** `PROVEN_WITH_LIMITATION`

**EVIDENCE:** `docs/evals/plan7/runs/20260815T140000Z/d1_reliability.md`,
`docs/evals/plan7/runs/20260815T145000Z/d2_persistence.md`,
`docs/evals/plan7/runs/20260815T151500Z/d3_rollback.md`, and
`docs/evals/plan7/rollback_runbook.md`.

**EXPLANATION:** The application recreate preserved authority and all effective target values;
the reliability suite measured all ten required classes; rollback to the recorded Plan 6 posture
worked; target re-application worked; and D3 left the host in the target posture. The Cisco model
was not restarted during D1, D2 or D3, as those artifacts explicitly record.

**REMAINING_GAP:** `CONFIG_REBUILD_DRIFT = CONFIRMED`. The target survives backend recreate
through the current `.env`, but not reconstruction from the tracked development seed. F1, F2 and
F3 also remain open; therefore this is not full deployment/configuration resilience.

### Q11

**QUESTION:** Which Plan 6 accepted risks close, and which persist?

**VERDICT:** `PROVEN`

**EVIDENCE:** `docs/evals/plan6/f5_go_live_decision_packet.md`,
`docs/evals/plan6/e2_stop_decision.md`, and the reconciliation tables below.

**EXPLANATION:** None of the three explicit Plan 6 F5 accepted risks is silently declared closed.
Shared-VPS latency/serving instability remains and is now a blocker because T4 is a hard Plan 7
GO requirement. The MITRE promotion remains explicitly deferred. Mock-only MCP evidence remains
and live Splunk is still unproven. Separately, Plan 6's missed-lifecycle architecture defect is
closed by A3, while the retained legacy fallback remains open under A7.

**REMAINING_GAP:** E2 must decide the final disposition. This report does not self-accept any
risk.

### Q12

**QUESTION:** Is live Splunk/MCP still `live_mcp_unproven`?

**VERDICT:** `PROVEN`

**EVIDENCE:** `docs/evals/plan6/runs/f3_live_mcp.md`,
`docs/evals/plan6/f5_go_live_decision_packet.md`, and the `MCP_MODE=mock` read-backs in
`docs/evals/plan7/runs/20260815T140000Z/d1_reliability.md` and
`docs/evals/plan7/runs/20260815T151500Z/d3_rollback.md`.

**EXPLANATION:** The status is still `live_mcp_unproven`. Plan 7 proves orchestration,
PhaseContract/SPL lifecycle, MCP gating, exercised HIL/RBAC policy flow, and failure handling
against mock or unavailable MCP. It does not prove a real Splunk-backed SOC investigation.

**REMAINING_GAP:** Live Splunk/MCP is `NOT IN PRODUCTION SCOPE / UNPROVEN` for this report. A
controlled live, read-only, allowlisted and fully gated path has not been evidenced.

## ResourcePlan authority finding

ResourcePlan execution is active on the target VPS posture and dispatch-v2 is off. D2's target
smoke observed four ResourcePlan step-walk rows with the merge active, mandatory
`spl_postprocessor` inserted on every seam row and zero `V2_WINS` observations; candidate SPL
remained non-executable on all six smoke rows
(`docs/evals/plan7/runs/20260815T145000Z/d2_persistence.md`). D3 reproduced those same authority
discriminators after target restoration: merge active on four rows, T4 invoked on three rows,
mandatory lifecycle insertion intact, and zero `V2_WINS` observations
(`docs/evals/plan7/runs/20260815T151500Z/d3_rollback.md`). A3 therefore remains proven.

The observed target execution authority is:

`ResourcePlan + PhaseContract → deterministic merge/compiler → governed schedule`.

That observation is not yet a production-normal authority conclusion because A7 is open and E1
has not run.

### D3 `dispatch_source` caveat

`dispatch_source=resource_plan_step_walk` is not, by itself, evidence that ResourcePlan execution
authority ran. During deliberate rollback it still appeared on four of five smoke rows while the
ResourcePlan execution flag was off (`docs/evals/plan7/runs/20260815T151500Z/d3_rollback.md`).

The actual D3 discriminators are:

- `merge_active`: present on target ResourcePlan rows, absent on all rollback rows;
- `inserted_phases`: mandatory lifecycle insertion on target seam rows, none on rollback;
- `t4_invoked`: present only in the target posture, absent on rollback;
- executor state: with `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED=false` the executor returns early
  before execution-contract processing; with it `true` on target the merge runs, while candidate
  execution remains non-eligible;
- authority observation: the rollback exposed the expected v2 cursor, while restored target
  evidence recorded no `V2_WINS` ownership.

E1 and E2 must use these signals rather than the label alone.

## T4: three separate findings

### A. Semantic capability — `PROVEN`

The controlled C3 remeasurement accepted four of four cases, observed useful semantic additions,
preserved locked facts in all four, and widened capabilities zero times
(`docs/evals/plan7/c3_remediation_evidence.md` and
`docs/evals/plan7/c3_remeasurement.json`). This is enough to reject a model-capability-blocker
classification.

### B. Application integration — `PROVEN_WITH_LIMITATION`

T4 is invoked only at T4, receives constrained structured output, and remains downstream of
deterministic validation and merge. Authority-bearing output fails closed; malformed,
unavailable, timeout and slot-pressure cases retain deterministic fallback
(`docs/evals/plan7/c3_remediation_evidence.md` and
`docs/evals/plan7/runs/20260815T140000Z/d1_reliability.md`). This is sufficient for Plan 7
architecture testing, not proof of serving reliability.

### C. Serving reliability and production posture — `BLOCKED`

Acceptance varied materially under the same configuration as host paging changed, and API
liveness did not prove usable inference. Stable serving, health detection and recovery remain
unproven. The accepted classification remains
`T4_SEMANTICALLY_VIABLE_BUT_VPS_SERVING_BLOCKER`
(`docs/evals/plan7/c3_remediation_evidence.md`).

## Plan 8 authority dependency

D0 measured twelve T4 rows whose final locked contract still had
`clarification_required=true` and `required_capabilities=[]`, including all eight residual
paraphrases, even when the recorded T4 proposal was accepted
(`docs/evals/plan7/runs/20260815T131000Z/target_corpus.md`). This is not a T4 permission bug to
patch in Plan 7. T4 correctly cannot grant capabilities or overwrite locked T1–T3 fields.

The frozen Plan 8 dependency is:

```
T1–T3
  → locked/unresolved fields
  → T4 semantic completion
  → deterministic merge
  → deterministic recomputation of evidence/capability/route hints
  → final RQC
  → owner
  → ResourcePlan
```

Plan 7 does not implement or pre-approve that sequence.

## D1 findings carried forward

| Finding | Observed truth | Current disposition | Production implication |
|---|---|---|---|
| **F1 — DB-loss authority degradation** | DB failure can degrade a request to `canonical_non_planned` while it still answers; nothing executed and gates stayed intact (`docs/evals/plan7/runs/20260815T140000Z/d1_reliability.md`). | `KNOWN_PLAN8_DEPENDENCY` | Safe fallback was observed, but continued ResourcePlan authority and analyst-visible degradation under DB loss are unproven. It remains visible at E2; it is not claimed resolved. |
| **F2 — model API liveness is not inference health** | `/v1/models` remained HTTP 200 while inference was unusable (`docs/evals/plan7/c3_remediation_evidence.md`). | `KNOWN_PLAN8_DEPENDENCY`; future Plan 8 REL0 detection | Current automated health/recovery posture is unproven. Human restart remains an explicit operator action only. Detection work does not itself supply serving capacity. |
| **F3 — Cisco serving stability** | Same-day acceptance varied with host paging and a quiet/restarted host (`docs/evals/plan7/c3_remediation_evidence.md`). | `CURRENT SERVING INFRASTRUCTURE BLOCKER` | This is a current production blocker. Plan 8 may improve detection/backpressure, but it does not make serving capacity or stability appear. |

## Configuration persistence finding

The approved D3 disposition remains:

`TARGET_PERSISTENCE_SUFFICIENT_FOR_CURRENT_VPS_OPERATION_BUT_CONFIG_REBUILD_DRIFT_REMAINS_E2_BLOCKER`.

Proven by D2/D3: the target survives backend force-recreate through the current `.env`; rollback
to the Plan 6 posture works; target re-application works; and the host was left in target posture
(`docs/evals/plan7/runs/20260815T145000Z/d2_persistence.md` and
`docs/evals/plan7/runs/20260815T151500Z/d3_rollback.md`).

Not proven: reconstruction from the tracked development profile. Four of the six target flags
would not survive that rebuild: ResourcePlan execution, dispatch-v2, T4 enablement and the T4
timeout (`docs/evals/plan7/runs/20260815T151500Z/d3_rollback.md`). Therefore:

`CONFIG_REBUILD_DRIFT = CONFIRMED`.

Deployment/recreate persistence must not be described as full configuration resilience.

## A7 and the legacy fallback

Current evidence says `_run_legacy_dispatch_fallback` remains reachable through
`session_spl_refine`, is classified as migration debt, and skips `spl_postprocessor`. It was
observed zero times in the A4 corpus (`docs/evals/plan7/a5_old_path_audit.md`). A7 remains
unchecked and no `docs/evals/plan7/a7_fallback_lifecycle_proof.md` exists.

Consequently:

- production reachability: **reachable through `session_spl_refine`**, though unobserved in the
  target corpus; not proven unreachable;
- classification: **migration debt / unresolved execution seam**;
- ownership proof: **not proven** for this path;
- posture: **not rollback-only** on current evidence and not observed in target corpus;
- E2 effect: **critical blocker until A7 proves lifecycle validation, normalized-SPL-only MCP
  input, HIL/RBAC authority and no duplicate execution**.

The existing MCP gate refusing unapproved or null `normalized_spl` is a safety net, not a
substitute for the missing lifecycle proof (`docs/evals/plan7/a5_old_path_audit.md`). E0 neither
retires nor modifies the fallback.

## Plan 6 risk reconciliation

### Explicit Plan 6 F5 accepted risks

| PLAN6_RISK | PLAN7_STATUS | EVIDENCE | DISPOSITION |
|---|---|---|---|
| Shared-VPS absolute latency | T4 semantic capability is proven, but serving remains unstable and T4 is now a hard GO requirement. | `docs/evals/plan6/f5_go_live_decision_packet.md`; `docs/evals/plan7/c3_remediation_evidence.md` | **REMAINS** and is now part of the serving blocker |
| MITRE DRAFT drift / separate promotion | No promotion was authorized or performed; the Plan 6 decision still stands. | `docs/evals/plan6/e2_stop_decision.md` | **DEFERRED** |
| Mock-only MCP execution lane | `MCP_MODE=mock`; no live Splunk proof was added. | `docs/evals/plan6/runs/f3_live_mcp.md`; `docs/evals/plan7/runs/20260815T151500Z/d3_rollback.md` | **REMAINS** |

### Plan 6 architecture limitations carried into Plan 7

| PLAN6_RISK | PLAN7_STATUS | EVIDENCE | DISPOSITION |
|---|---|---|---|
| ResourcePlan lost mandatory lifecycle work with v2 off | A3 moved lifecycle ownership to PhaseContract and target evidence preserved it. | `docs/evals/plan7/a3_ownership_fix.md`; `docs/evals/plan7/a4_authority_acceptance.md` | **CLOSED** for the measured merge path |
| T4 semantic capability unproven/default-off | T4 is on and semantic capability is proven; serving reliability is a separate blocker. | `docs/evals/plan7/c3_remediation_evidence.md` | **SUPERSEDED** by the semantic-versus-serving split |
| Legacy execution seam retained | The fallback is still reachable and A7 is incomplete. | `docs/evals/plan7/a5_old_path_audit.md`; current Plan 7 A7 item | **REMAINS** |
| Plan 6 production decision | The user recorded `DEFER` because intended authority was not production-authoritative. Plan 7 E2 has not occurred. | `plans/2026-08-13_1440_production-activation-t4-serving-and-governance-readiness.md` | **DEFERRED** to E2 |

## Preliminary production-readiness matrix

This matrix prepares E2; it is not E2 and contains no GO decision. Vocabulary is intentionally
limited to `PASS`, `BLOCKER`, `UNPROVEN`, `DEFERRED`, and `NOT_IN_PRODUCTION_SCOPE`.

| Category | Preliminary verdict | Evidence and limit |
|---|---|---|
| Functional | `PASS` | The target corpus completed 30 rows with zero errors and zero unexplained deltas (`docs/evals/plan7/runs/20260815T131000Z/target_corpus.md`). |
| Safety | `PASS` | No candidate became executable, MCP did not execute, approved SPL never lacked normalized SPL, and mandatory SPL lifecycle was present on every seam row (`docs/evals/plan7/runs/20260815T131000Z/target_corpus.md`). |
| Performance | `BLOCKER` | Orchestration-only latency was bounded, but live T4 serving is unstable and remains a hard GO requirement (`docs/evals/plan7/runs/20260815T140000Z/d1_reliability.md`; `docs/evals/plan7/c3_remediation_evidence.md`). |
| Reliability | `BLOCKER` | Failure classes degrade deterministically, but F1/F2 remain dependencies and F3 remains the current serving blocker (`docs/evals/plan7/runs/20260815T140000Z/d1_reliability.md`). |
| Security/RBAC | `PASS` | HIL/RBAC remained authoritative on exercised target and failure paths; no MCP call was allowed (`docs/evals/plan7/a4_authority_acceptance.md`; `docs/evals/plan7/runs/20260815T140000Z/d1_reliability.md`). |
| Observability | `PASS` | T4 proposed/accepted field names and truthful failure classes are exposed without values; authority signals are present (`docs/evals/plan7/c3_remediation_evidence.md`; `docs/evals/plan7/runs/20260815T140000Z/d1_reliability.md`). |
| Deployment/recreate persistence | `PASS` | Current `.env` survives backend force-recreate and target restoration (`docs/evals/plan7/runs/20260815T145000Z/d2_persistence.md`; `docs/evals/plan7/runs/20260815T151500Z/d3_rollback.md`). |
| Configuration rebuild resilience | `BLOCKER` | `CONFIG_REBUILD_DRIFT = CONFIRMED`; tracked seed reconstruction restores the wrong authority posture (`docs/evals/plan7/runs/20260815T151500Z/d3_rollback.md`). |
| Rollback | `PASS` | Both rollback and target re-application were executed, and the host was left on target (`docs/evals/plan7/runs/20260815T151500Z/d3_rollback.md`). |
| Corpus | `PASS` | The integrated target corpus covered the required request classes and Plan 6 rows with zero regressions (`docs/evals/plan7/runs/20260815T131000Z/target_corpus.md`). |
| Production flags | `PASS` | Effective target values were read back after recreate and re-application; this verdict is only for the current VPS override, not tracked defaults (`docs/evals/plan7/runs/20260815T145000Z/d2_persistence.md`; `docs/evals/plan7/runs/20260815T151500Z/d3_rollback.md`). |
| ResourcePlan production authority | `UNPROVEN` | ResourcePlan + PhaseContract is the observed target authority and v2 is off, but A6 remains pending wider proof and A7 is incomplete. |
| T4 semantic capability | `PASS` | Controlled four-of-four acceptance with useful additions, locked facts preserved and no widening (`docs/evals/plan7/c3_remediation_evidence.md`). |
| T4 serving posture | `BLOCKER` | `T4_SEMANTICALLY_VIABLE_BUT_VPS_SERVING_BLOCKER`; stable inference and recovery are not proven (`docs/evals/plan7/c3_remediation_evidence.md`). |
| Execution seam posture | `BLOCKER` | A7 is unchecked; the reachable legacy fallback skips mandatory post-processing and lacks lifecycle proof (`docs/evals/plan7/a5_old_path_audit.md`). |
| MITRE governance | `DEFERRED` | The separate governed promotion remains deferred (`docs/evals/plan6/e2_stop_decision.md`). |
| Live MCP/Splunk scope | `NOT_IN_PRODUCTION_SCOPE` | Current evidence is mock/unavailable-MCP only; real Splunk-backed investigation remains unproven. |
| Critical blockers | `BLOCKER` | Current evidence establishes F3 serving stability, configuration rebuild drift, and unresolved A7 execution-seam proof as critical blockers. No risk is self-accepted here. |

## Critical blocker discipline

The current critical blockers are:

1. **F3 Cisco serving stability:** current serving infrastructure does not provide reproducible
   T4 inference. Plan 8 detection/backpressure work does not itself fix capacity or stability.
2. **`CONFIG_REBUILD_DRIFT`:** loss or regeneration of `.env` silently restores the wrong
   authority posture. Current-VPS recreate persistence does not close this.
3. **A7 execution seam:** the reachable legacy fallback lacks the mandatory proof E2 requires.

F1 makes production authority continuity and analyst-visible degradation under DB loss
unproven, even though safe non-execution was observed. F2 makes model health detection/recovery
unproven and directly compounds F3. They remain Plan 8 dependencies, not resolved Plan 7 facts.

E1 closure gates have not run. Their future result is `UNPROVEN` at E0, not a risk accepted by
this report.

## E0 conclusion

ResourcePlan + PhaseContract is the observed execution authority on the current target VPS,
dispatch-v2 is off, A3's lifecycle ownership survived, and candidate SPL remained
non-executable. T4 semantic capability and application integration are proven enough for Plan 7
architecture testing. T4 serving reliability, configuration rebuild resilience and the A7
legacy seam remain blockers. Live Splunk/MCP remains outside the proven production scope.

No production GO decision is made. E2 remains the user decision gate.
