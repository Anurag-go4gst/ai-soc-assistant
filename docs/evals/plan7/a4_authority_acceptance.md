# Plan 7 A4 — ResourcePlan authority acceptance on the target posture

Run: `docs/evals/plan6/runs/20260814T134610Z/` (12 rows, harness exit 0,
`missing_qualification_tier` none). Baseline for comparison: the P0.4 pre-fix run
`20260814T125340Z` on the identical posture.

Effective flags read back from the running backend at run time:

| Flag | Value |
|---|---|
| `LANGGRAPH_ORCHESTRATION_ENABLED` | `true` |
| `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | `true` |
| `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` | **`false`** |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` | **`true`** |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS` | `2.0` |
| `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED` | `false` |
| `MCP_MODE` | `mock` |

## Acceptance criteria

| # | Criterion | Result |
|---|---|---|
| 1 | Missed mandatory work | **0** — merge now authoritative on **8/12** (was 6/12); the two `no_schedulable_step` rows now carry the full lifecycle |
| 2 | Duplicate execution | **0** — no repeated hook in `executed_hooks` on any of the 12 traces |
| 3 | Merge + old-engine double-run | **0** — no trace shows both a merged schedule and a legacy/predicate schedule (see A5) |
| 4 | Deterministic SPL validation preserved | **PASS** — `spl_postprocessor` present on every SPL row; `bb38d292` now refuses with `block_reason=spl_validation_failed` where before the phase never ran |
| 5 | Candidate SPL never executable evidence | **PASS** — `execution_eligible` is `null` on every row |
| 6 | Only validated non-null `normalized_spl` reaches the MCP gate | **PASS** — MCP `allowed=false` on both fixed rows; `requires_human_review` / `skipped` with explicit `block_reason` |
| 7 | HIL preserved | **PASS** — `required=true` wherever owed: `spl_source_profile_clarification`, `spl_revision`, `execution_approval` |
| 8 | RBAC preserved | **PASS** — gate authority unchanged; A3 touched scheduling only, never the gate |
| 9 | PhaseContract mandatory phases honoured | **PASS** — `phase_names` covers the contract on every merged row |
| 10 | Inline phases represented **and** executed | **PASS** — `p6.spl.mcp` shows `mitre_finalize` in both `phase_names` and `inline_executed` |
| 11 | Route/tier/fingerprint deltas | **0 deltas** — every row identical to the pre-fix run on route, `qualification_tier` and `resource_plan_fingerprint` |
| 12 | Query-specific fixes | **none** — see A3 |

## The two defect rows, before → after

| | before (P0.4) | after (A4) |
|---|---|---|
| `p6.multi.knowledge_spl_mcp` | `degrade=no_schedulable_step`, `phase_names=[]`, schedule `workflow_spl → spl_source_resolve → execution` | `degrade=merge`, all four phases, schedule `workflow_spl → spl_source_resolve → **spl_postprocessor** → execution` |
| `p6.live_posture.d1_003` | same defect | same fix |

`resource_downgrade=no_schedulable_step` appears on exactly those two traces with
`inserted_phases=['workflow_spl','spl_postprocessor','spl_source_resolve','execution']` — the A3
path firing precisely where measured, and nowhere else.

**New governed refusal that could not happen before.** On `bb38d292` the restored
`spl_postprocessor` produced `mcp.block_reason=spl_validation_failed` and HIL
`spl_source_profile_clarification` (`source_profile_slots_missing`). Before A3 that row reached
the gate with the validation phase never having run. This is the missed work being done, not a
regression.

## `spl_postprocessor` was contract-inserted on four *healthy* rows too

`bb48002c`, `6375205a`, `fecae988`, `21458b3f` each show `inserted_phases=['spl_postprocessor']`
with no resource downgrade. The compiler never schedules that phase by design, so **every** SPL
row depends on the merge to supply it. That widens the significance of the A3 fix: before it,
any route that lost the merge lost deterministic SPL validation.

## Ordering question from A3 — answered

Two orders coexist, both registry-valid (`spl_postprocessor` and `spl_source_resolve` are each
only `after=("workflow_spl",)`):

- compiled base present → `workflow_spl → spl_postprocessor → spl_source_resolve → execution`
- lifecycle-only insertion → `workflow_spl → spl_source_resolve → spl_postprocessor → execution`

On the target posture the second order is the one the two fixed rows execute, and it is
**behaviourally the safer of the two**: slots are resolved *before* deterministic post-processing,
which matches the governed rule that the real `validate_spl` runs post slot-resolution. The
observed outcome supports it — `bb38d292` correctly refused on unresolved source slots. Recorded
as an accepted, pinned difference rather than a silent assumption; no ordering code was changed.

## Latency

Comparable to the pre-fix run on the same posture (p50 ≈ 93 s). The two fixed rows stay fast
(1.4 s, 1.3 s) — they were never slow because of missing work; they were fast because they
skipped it, and the restored phases are deterministic and cheap.
