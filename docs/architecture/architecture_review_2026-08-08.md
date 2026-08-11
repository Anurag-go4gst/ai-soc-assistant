# Architecture review — canonical planning spine

**Date:** 2026-08-08 · **Against:** `master@1681f90` · **Scope:** live `/chat` path — lane routing, canonical planning seam, specialist fan-out, SPL ladder, MCP gate.

Method: read the compiled graph and call sites, then reproduce each claim against live code. Findings below are reproduced, not inferred. Nothing here is fixed in this pass — each item is a separately scoped change.

---

## Critical

None. The governance invariants hold as documented: non-`planned` outcomes have no graph edge to execution, `plan_evidence_from_canonical` is the sole plan creator under an authority context manager, candidate SPL stays non-executable, and the outcome contract rejects contradictory artifacts at construction.

---

## Important

### 1. Two divergent `T0–T4` implementations that can disagree after resolution

> **Revised 2026-08-08 after external review.** The first version of this finding overstated the problem in two ways, both corrected below. Original claims struck through and replaced.

`app/chat/lane_router.py` is authoritative for the processing lane. `app/catalogue/match_tiers.py` is a second, independent implementation.

**Correction 1 — the comparison must use `resolved_tier`, not `initial_tier`.** The original table compared `match_catalogue_tier` against the tier straight off the match path, before reference qualification runs. That is not a like-for-like comparison and it manufactured disagreements that do not exist. Re-run against the resolved tier:

| Query | `initial_tier` | **`resolved_tier`** (authoritative) | `match_catalogue_tier` | Verdict |
|---|---|---|---|---|
| `Explain CVE-2024-3400` | `T4` | **`T0`** | `T0` | **agree** — not a defect |
| `What is T1059` | `T4` | **`T0`** | `T0` | **agree** — not a defect |
| `Hunt for T1059 execution in our estate` | `T4` | **`T4`** (guided) | **`T0`** | **disagree — real** |
| `Which hosts are generating the most SMB traffic?` | `T1` | `T1` | `T1` | agree |
| `Did anything odd talk out of the OT segment overnight?` | `T4` | `T4` | `T4` | agree |

So the finding stands, but on **one** reproduction rather than two. The failing case is the important one: a question with a bare technique id *and* a hunt intent. Canonical routing correctly keeps it `T4`/guided; the bare-regex matcher calls it `T0` reference-knowledge.

**Correction 2 — `match_catalogue_tier` is NOT report-only, and must not be deleted or moved.** It also feeds a live path: `apply_live_catalogue_bind` (`app/catalogue/live_router_bind.py:85`) calls it to decide whether to bind a use case onto the routed payload, and that function is imported by `app/chat/pipeline.py:255`. The original recommendation ("delete it, or move it under `app/evals/`") would have removed live behaviour. **Withdrawn.**

Note the live bind gate refuses both `T0` and `T4` (`live_router_bind.py:62–65`), so today's `T1059` mis-tier lands on "skip the bind" either way — the same action the correct tier produces. That is luck, not design: a query the matcher wrongly calls `T0` when the true tier is `T1`–`T3` would silently skip a bind it should have applied.

**Correction 3 — the `fuzzy_alias_catalog` gap is narrower than stated.** `_T3_PATHS` in `match_tiers.py` does omit it, but the matcher can still reach `T3` independently through its own alias branch, so the omission is not straightforwardly a missing case. The real issue is the same semantic split as above: canonical routing can hold `T4` while the matcher reports `T3`. Not fully traced — treat as open.

**Revised recommendation.** Do not remove the second implementation. Instead:

1. Make `rp_node_specialist_skill` report the authoritative tier rather than recomputing one — `RoutingContext.catalogue_tier` is already in state:
   ```python
   routing = (state.get("canonical_planning_input") or {}).get("routing") or {}
   tier = routing.get("catalogue_tier")     # authoritative, post-resolution
   ```
2. Leave `match_catalogue_tier` where it is for the live bind, but **rename it to say what it is** (`match_catalogue_bind_tier`) and docstring it as "pre-resolution bind heuristic — not the canonical tier".
3. Add a test pinning the known split: a hunt-shaped query carrying a reference id must keep `resolved_tier == "T4"` regardless of what the bind heuristic returns.

Regression gates: `pytest app/tests/test_catalogue_bind_surface_agreement.py app/tests/test_live_catalogue_router_probes.py app/tests/test_resource_planner_dry_runs.py`, then `./scripts/run_stage3_governance_regression.sh` (dual-runtime parity must stay 120/0/0).

### 2. Unbounded substring match denies the T0 short-circuit

`app/chat/reference_qualification.py:99`:

```python
environment_scope = status_check or "our " in normalized or "our systems" in normalized
```

`"our "` is tested with no word boundary, so it matches inside **"f<u>our h</u>ours"**. Reproduced:

```
'What is CVE-2024-3400?'                              → t0=True   env=False
'What is CVE-2024-3400 over the last four hours?'     → t0=False  env=True    ← defect
```

**Scope correction (external review, 2026-08-08).** The original claim — "any query containing *four, hour, flour, sour, tour, your, pour*" — was too broad. The literal is `"our "` **with a trailing space**, so it only fires when `our` is followed by whitespace:

```
'... over the last four hours?'   → True    ("f-our h-ours")
'... an hour ago'                 → True    ("h-our ")
'... in the last hour?'           → False   (sentence-final, no trailing space)
'explain t1059 tour'              → False   (string-final)
'explain t1059 flour'             → False   (string-final)
```

Narrower than stated, still a real defect: any mid-sentence *four/hour* — including the very common "last four hours" and "an hour ago" time qualifiers — denies `T0`. Effect: a pure definitional reference question is routed down the guided lane instead, a slower and weaker answer for a question the reference registry could have answered outright.

It **fails safe** (can only deny `T0`, never grant it wrongly), which is why it has gone unnoticed. Fix is a word-boundary regex in place of the bare substring test.

**Do not bundle this with unrelated work.** Any change to reference-knowledge handling has to run the 10-probe reference contract (`/reference-probe-audit`) plus `/invariant-check`, as its own commit.

---

### How to fix (1) and (2)

**(1) Collapse to one tier definition.** `RoutingContext.catalogue_tier` is already in state by the time Stage 4 runs, so the specialist does not need to recompute anything:

```python
# app/graph/resource_planner_graph.py — rp_node_specialist_skill
# before: tier = match_catalogue_tier(query, understanding=state.get("query_understanding"))
routing = (state.get("canonical_planning_input") or {}).get("routing") or {}
tier = routing.get("catalogue_tier")          # authoritative — set by lane_router
```

Then either delete `match_tiers.py` or, if the probe/dry-run tests still need it, rename `match_catalogue_tier` → `probe_catalogue_tier`, move it under `app/evals/`, and add a test asserting it is imported by **no** module under `app/graph/` or `app/chat/`. That test is what stops the divergence coming back.

Regression gates for this change: `pytest app/tests/test_catalogue_bind_surface_agreement.py app/tests/test_live_catalogue_router_probes.py app/tests/test_resource_planner_dry_runs.py`, then `./scripts/run_stage3_governance_regression.sh` (dual-runtime parity must stay 120/0/0).

**(2) Word-boundary the marker match.** The whole class of defect comes from testing markers with `in` against a raw string. One helper removes it:

```python
import re

def _has_marker(text: str, markers: tuple[str, ...]) -> bool:
    """Match a marker phrase on word boundaries — 'our ' must not match 'four hours'."""
    return any(re.search(rf"\b{re.escape(m.strip())}\b", text) for m in markers)
```

Then replace every `any(m in normalized for m in ...)` and the bare `"our " in normalized` with `_has_marker(...)`. Note this is a **behaviour change on the T0 boundary**: queries currently denied `T0` by an accidental match will start resolving to `T0`. That is the intended fix, but it means the change must be gated on the reference-probe contract, not merged on unit tests alone.

Regression gates: `/reference-probe-audit` (all 10 probes, P1–P6 / N1–N4, diffed against the frozen baseline), `pytest app/tests/ -k reference`, `/invariant-check`, then the governance regression.

---

## Suggestions

1. **Marker lists are keyword matching, not intent understanding.** `_STATUS_MARKERS` contains `"vulnerable"` and `"exposure"`, so *"Explain the vulnerable component in CVE-2024-3400"* is classified as an environment status check and denied `T0`. It errs safe, but the qualifier reads in code as a semantic decision when it is a substring scan. Either tighten the markers to phrases that cannot appear in a definitional question (`"are we vulnerable"`, `"our exposure"` rather than bare `"vulnerable"`, `"exposure"`), or rename the function to say what it does. The word-boundary fix above does not solve this one — `"vulnerable"` is a genuine word match; the list itself is too broad.

2. **`specialist_mcp` and `specialist_spl` are stubs.** Both return fixed constants (`hop_count=0`, `spl_source="template_or_fallback"`) and inspect no state. They cost a `Send` fan-out and two merge slots for no information, and they make the parallel fan-out look wider than it is — a reader of the architecture reasonably assumes four specialists contribute four signals. Either give them real posture reporting (MCP: is a server configured, is execution enabled, which tools are selectable for this plan; SPL: does a governed template bind for this use case) or collapse the fan-out to the two that do work until they earn their place.

3. ~~**The SPL candidate ladder's conditional ordering is undocumented at the branch.**~~ **Withdrawn — this was wrong.** `pipeline.py:7409–7419` already carries an eleven-line comment explaining both the v2-off and v2-on behaviour in detail. I read that comment while tracing the ladder and still filed the suggestion; that is a review error, not a code gap.

   What *is* incomplete is the one-line summary in **`CLAUDE.md:65`**, which states only `governed templates → LLM-primary failover → lab draft last resort` — the non-catalogue half of a conditional branch. That line should be corrected to note that a mapped catalogue pattern with no rendered template takes the lab draft *before* the LLM. One doc line, no code change.

---

## Documentation defect found by review question (2026-08-08)

**"Dispatch — exactly one branch" was actively misleading**, and a reader caught it by reasoning about the diagram rather than the code: *what if D1, D2 and D3 are all required?*

The phrase describes the **entry point**, not the amount of work. Two of the four branches run multiple kinds of work:

- **D2 `composed_dispatch`** *is* the "all of the above" branch. `execute_plan_dispatch` walks the committed `ResourcePlan`'s steps in order and dispatches every step whose `purpose` is in `_DISPATCHABLE_PURPOSES` = `{knowledge_retrieval, spl_artifact, mcp_execution, cve_lookup, mitre_mapping}`, reusing the same workers the other branches use (`rag_early`, `workflow_spl`, `spl_source_resolve`, `execution`, `reference_finalize`).
- **D3 `workflow_spl`** is not SPL-only either — `_rp_after_workflow_spl` routes into `rag_early` when `needs_rag and rag_phase == "pre_mcp"` before continuing to source resolve and the gate.

Selection order in `_rp_dispatch_route` (`resource_planner_graph.py:458`) is: not-`planned` → D0; `answer_mode == "rag_only"` → D1; `has_composed_plan(state)` → D2; else D3. Note `rag_only` is tested **before** the composed check, so a knowledge answer is never widened into an investigation by the presence of plan steps.

Page corrected: Stage 6 now reads "exactly one *entry point*", with a table of how much work each branch can do and a section explaining what a composed plan is. No code change needed — the code was right, the description was not.

**Wider lesson for the docs:** phrases that sound like safety guarantees ("exactly one", "never", "always") need to name *what* is constrained. "Exactly one branch" and "exactly one entry point" describe the same code and mean very different things to a reader.

---

## Structural observations (no defect, worth deciding on)

These are not bugs. They are places where the architecture's shape will cost something later.

1. **One function is doing a great deal.** *(Attribution corrected — the original said `run_canonical_planning` is ~690 lines. That was the **file** length. Measured by AST:)*

   | Symbol | Lines | Size |
   |---|---|---|
   | `run_canonical_planning` | 86–120 | **35** — a thin entry point |
   | `graph_node_lane_and_canonical_planning` | 123–691 | **569** |

   The maintainability concern is unchanged, just correctly aimed: the 569-line node covers resume, intent, completeness, guided resolution, reference qualification, policy boundary, clarification persistence, and plan commit, with sub-stage boundaries existing only as comments. Collapsing the runtime fork was unambiguously right; the result is now the highest-traffic function in the system. If it grows further, promote its sub-stages to named functions with typed inputs so they can be tested without constructing a full pipeline state.

2. **Answer-mode override is policy expressed as a chain of `if`s.** `_answer_mode_from_canonical` encodes real routing policy as ordered conditionals. The catch-all bug it carries a comment about — every unmapped family silently becoming `live_investigation` — was exactly the failure mode of that shape.

   *(Refined after review.)* A simple `family → mode` table is **not** sufficient, because the logic keys on three fields with meaningful precedence: `processing_lane`, then `answer_goal`, then `intent_family`. What it needs is an **ordered decision table** with those three as columns, so precedence is data rather than statement order — and an explicit `None` row meaning "planner decides".

3. **`alert_summary` and SPL — the original claim was overstated.** I wrote that an alert-summary turn "can never open an SPL lane". Not true: the SPL check (`goal in {"spl_generation", "spl_artifact"}` or an SPL family) is evaluated **before** `family == "alert_summary"`, so a turn carrying both would return `live_investigation`. Normal classifier output deliberately gives alert summaries no SPL goal, and that policy is documented elsewhere. **Downgraded to a note:** the ordering dependency is invisible at the call site and only holds because of statement order — which is the same argument for (2).

4. **Telemetry classification can be bypassed.** *(Refined after review.)* Catalog construction *does* reject an unclassified event — `canonical_telemetry_catalog.py:41` raises `ValueError(f"event not classified in policy: {event}")`. But `emit_planning_event` (`planning_telemetry.py:131`) takes `event: str` and validates nothing, so a newly emitted event name reaches telemetry without ever passing the catalog. The gap is not "no validation exists" but "the validation is not on the emit path". Validating the event name inside `emit_planning_event` would close it.

---

## Priority

| # | Item | Severity | Effort | Do it when |
|---|------|----------|--------|------------|
| 1 | `CLAUDE.md:65` SPL ladder line incomplete | Suggestion | XS | Immediately — one doc line, no code |
| 2 | Tier divergence — specialist recomputes instead of reading `RoutingContext` | Important | S | Next scoped change; latent correctness trap, cheap to close. **Do not delete `match_tiers.py`** — it feeds the live bind |
| 3 | `"our "` substring defect | Important | S (fix) / M (gates) | Own commit, behind the reference-probe contract |
| 4 | Marker-list breadth (`vulnerable`, `exposure`) | Suggestion | M | Same commit as (3) — same file, same gates |
| 5 | `emit_planning_event` does not validate the event name | Suggestion | S | Cheap; closes a real bypass of the telemetry catalog |
| 6 | Specialist stubs (MCP / SPL) | Suggestion | M | When MCP/SPL posture is actually needed downstream |
| 7 | Answer-mode ordered decision table | Observation | M | Next time a family is mis-routed |
| 8 | Split `graph_node_lane_and_canonical_planning` (569 lines) | Observation | L | Only if it grows again |

---

## Review corrections log

This review was itself reviewed on 2026-08-08. Corrections applied above, recorded here so the error rate is visible rather than quietly patched:

| Original claim | Verdict | Correction |
|---|---|---|
| Two tier implementations diverge | **Partially correct** | Divergence real, but `match_catalogue_tier` is **not** report-only — it feeds `apply_live_catalogue_bind` on a live path. "Delete or move under evals" **withdrawn**. |
| `Explain CVE-2024-3400` mis-tiers | **Incorrect** | Compared `initial_tier` against the matcher. On `resolved_tier` both say `T0` — they agree. |
| `Hunt for T1059 … in our estate` mis-tiers | **Confirmed** | Canonical stays `T4`/guided; matcher says `T0`. The one real reproduction. |
| `fuzzy_alias_catalog` missing from T3 | **Partially correct** | Constant omits it, but the matcher reaches `T3` via its alias branch. Real issue is the `T4`-vs-`T3` semantic split — untraced, left open. |
| `"our "` substring defect | **Confirmed, over-scoped** | Requires a trailing space; `"last hour?"` does not reproduce. Narrowed. |
| Broad `vulnerable` / `exposure` markers | **Confirmed** | — |
| MCP/SPL specialists are stubs | **Confirmed** | — |
| SPL ladder needs a branch comment | **Incorrect / stale** | An 11-line comment already exists at `pipeline.py:7409`. Only `CLAUDE.md:65` is incomplete. **Withdrawn.** |
| `run_canonical_planning` is ~690 lines | **Wrong attribution** | It is 35 lines; the 569-line function is `graph_node_lane_and_canonical_planning`. Concern valid, target wrong. |
| Answer-mode should be a `family → mode` table | **Mostly correct** | Needs an *ordered* table across lane / goal / family — precedence matters. |
| `alert_summary` can never open SPL | **Overstated** | SPL goals are checked first, so contradictory input still yields `live_investigation`. Downgraded to a note. |
| Unknown telemetry events escape classification | **Mostly correct** | Catalog construction rejects them; `emit_planning_event` does not. Gap is on the emit path. |
| Replay / sole plan authority / outcome invariants | **Confirmed** | — |
| Counts 65 / 28 / 19–8 / 98–12–86 | **Confirmed** | — |

**Pattern in my own errors:** three of the four wrong findings came from comparing or citing the *wrong artifact* — pre-resolution tier instead of resolved tier, file length instead of function length, and a suggestion filed against code whose comment I had already read. Verify the exact symbol before filing.

---

## Checked and cleared

- **Committed-plan replay staleness** — `plan_evidence_from_canonical` replays on `(handoff_id, handoff_version)`. `handoff_id` is minted fresh per turn (`new_handoff_id()`), and resume bumps `next_version = handoff_version + 1`. Replay therefore only fires on a genuine retry of the same turn attempt. Not a defect.
- **Specialists calling a model** — none of the four do. Verified by reading all four node bodies.
- **Counts on the architecture page** — use-case catalog 65, planning events 8 + 20 = 28, skills registry 19 (8 routable), MITRE coverage 98 / 12 / 86. All read from live code.

---

## What is already strong

Recorded so the review is not read as a list of complaints. These are the decisions worth keeping and defending in a design discussion:

- **Topology as a safety mechanism.** A non-`planned` outcome has *no graph edge* to SPL generation or the MCP gate. Safety is a property of the compiled graph rather than a runtime check that can be bypassed by a bug upstream. This is the single best decision in the design.
- **One plan creator, enforced by a context manager.** `compose_resource_plan` only works inside `resource_plan_authority()`, so "sole creator" is mechanically true rather than a convention.
- **The outcome contract rejects bad states at construction.** A `clarification_required` outcome carrying an evidence plan raises immediately — a whole class of "confident answer from a failed turn" bug is unreachable.
- **Fail-closed persistence.** No memory or file fallback: an unavailable database produces `persistence_failed`, not a turn that pretends to have planned.
- **Two-phase response validation.** Refusing to emit `request.completed` for a response that failed assembly validation means the telemetry cannot record a success the system did not produce.
- **Fork detection as a test with a negative control.** The static architecture guard has to fail when a fork is deliberately reintroduced. That is the difference between a guard and a comment.
- **Honest degradation throughout.** Empty MCP results reported as empty, deferred tools recorded as deferred, evidence counts drawn only from collected telemetry, MITRE explicitly typed as metadata rather than evidence.

---

## Resolution — corrective plan outcomes (2026-08-10)

Every finding above was closed by `plans/2026-08-08_1824_architecture-review-corrective-actions.md`.
Recorded here so the review is read with its verdicts, not as an open list.

| # | Finding | Outcome |
|---|---|---|
| 1 | Tier divergence — specialist recomputes instead of reading `RoutingContext` | **Fixed (B0/B1).** One production tier authority. `initial_tier` / `resolved_tier` / `binding_candidate_tier` are now distinct, the parser path is preserved as `observed_match_path`, and the accepted path is `effective_catalogue_match_path`. `rp_node_specialist_skill` copies canonical routing instead of recomputing. |
| 2 | `"our "` unbounded substring denies `T0` | **Fixed (C0).** Boundary-aware phrase matching; the frozen 10-probe reference contract still passes. |
| 3 | Marker-list breadth (`vulnerable`, `exposure`) | **Fixed (C0).** Replaced with explicit environment-status phrases. |
| 4 | `emit_planning_event` bypasses the telemetry catalog | **Fixed (E1).** Unclassified events fail closed; a static inventory test pins the 8 audit-critical + 20 diagnostic partition. |
| 5 | MCP / SPL specialists are stubs | **Fixed (D1/D2).** Both now read the committed plan and registries and emit bounded, redacted readiness reports — `planned_hop_count`, `candidate_tool_names`, `execution_posture` on the MCP side; `slot_binding_status`, `spl_source`, `template_status` on the SPL side, with `execution_eligible` hard-validated false. |
| 6 | Answer-mode policy as a chain of `if`s | **Fixed (E0).** Ordered, inspectable policy across lane / answer goal / intent family; a contradictory `alert_summary` + SPL contract now fails closed instead of silently opening an SPL lane. |
| 7 | `graph_node_lane_and_canonical_planning` is oversized | **Fixed (F0).** Decomposed into four typed stages behind a 98-line seam. Measured 613 lines at execution time, not the 569 recorded here — E0/E1 had grown it further. |

### The defect this review missed

The highest-priority runtime defect was **not** in the review. `specialist_reports` was an
`Annotated[list, operator.add]` channel while every post-merge node returned full state, so the
list re-appended itself once per downstream node: **16,384** reports on a T0 reference turn and
**8,192** on T2/T3/T4, against four unique specialist lanes. Growth was exponential (doubling per
post-merge node), not linear, and it was masked by an `assert len(reports) >= 4`.

Fixed in **A1** with a deterministic reducer keyed on `(delegation_id, specialist_id)` that
deduplicates identical replays and fails closed on conflicting ones.

Two lessons worth keeping:

- **A `>=` assertion is not a cardinality test.** It passed throughout, at every magnitude.
- **Measure with the real dependencies attached.** The defect was first sized at 64 reports on a
  host with no reachable database: persistence failed closed, planning never reached `planned`,
  and the run took a much shorter path through the graph. The same probe against a live database
  returned 16,384. A reachable database is part of the measurement, not an optimisation of it.

---

## Plan 2 outcomes (2026-08-11)

Two decisions were taken after this review and are now implemented. Both were user/COE gates;
this section records what changed, not the deliberation (see
`plans/2026-08-10_1103_architecture-resource-plan-execution-and-adaptive-planning.md`).

### B1 — planning/discovery posture: `RETIRE`

Canonical plan creation is deterministic and stays that way. The three fragmented LLM planning
rails were retired as planning authorities: the fenced inline `llm_plan_bridge`, the discard-only
shadow planner (its trace already hard-blocked promotion), and the imperative guided-hybrid
`propose_investigation_plan_llm` proposer. What was **kept**: deterministic guided dispatch, its
validators and evidence collection; the four advisory Resource Planner specialists; and live
bounded pre-SPL MCP discovery under dispatch-v2. What was **kept for a stated reason**:
`MAX_MCP_HOPS`, which still bounds recipe call budgets and was therefore not deletable; and
`AI_SOC_GUIDED_LLM_ENABLED`, now scoped to budget/deadline only with no planning-call gate.

Retiring the proposer surfaced a real limitation, recorded rather than papered over: deterministic
guided planning had no round-varying input, so a second refinement round was an idempotent no-op.
No heuristic was added to fake one.

### Resource Planner topology and decision records

`resource_planner_graph_edges()` no longer unions documented topology into its own answer — it
returns runtime-derived edges (builder fixed edges, mapped conditional destinations, dynamic
`Send` fan-out) and reconciles the documented set by exact equality. The union had been masking
two fabricated edges through the orphan `route_setup`, which was proven unreachable and removed.
Every decision record's declared inputs/outputs was validated against real state channels and
then corrected to what the node actually reads and writes; trace-only nodes carry empty lists.
Refs remain descriptive — nothing consumes them for scheduling, and they must not become a
dataflow authority.

### C0 — ResourcePlan order semantics: `EXECUTION-DRIVEN`, default off

Measured first: reversing a composed plan's steps changed `step_walk_order` but left the dispatch
schedule byte-identical, so step order was lineage, not authority.

The execution contract now exists on the live `ResourcePlan` — one optional typed `execution`
block per step carrying dependencies, parallel group, produced/required evidence keys, a failover
target and bounded attempts — with validation that rejects cycles, dangling dependencies, unknown
evidence keys, invalid fallback targets, and any retry on a side-effecting step. A pure compiler
turns a validated contract into the executor's existing hook schedule, and typed handoffs make
each stage's inputs explicit, including the rule that only approved, non-empty
`spl_validation.normalized_spl` satisfies the MCP gate.

Activation is `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED`, **default false**. Flag-off returns the
fixed predicate schedule before any execution-contract code runs, so parity is structural. Where
dispatch-v2 has already projected a schedule, that projection wins and the execution-driven path
stands down. Flag-on today changes *which component holds ordering authority*, not the order any
turn runs: across a 12-probe tier/intent/order matrix the compiled schedule equalled the fixed
schedule on every composed plan, in both composed and reversed step order.

Guided-hybrid and session-SPL-refine dispatch bypass this seam entirely, so the execution-driven
path never applies to them.

---

## Plan 3 outcomes (2026-08-11)

Plan 3 charted the adoption path rather than rewiring it. One decision, one correctness
fix, one inventory, one capability wired. See
`plans/2026-08-11_0915_execution-driven-adoption-and-guided-refinement.md`.

### A0 — scheduling authority: `PHASE_POLICY_PLUS_RESOURCE_PLAN_SCHEDULING`

Measured first. Across 5 probes × 4 postures: the legacy predicate schedule returned the
dispatch-v2 projection unchanged in **10/10** v2-on rows, so it is a pass-through rather
than a third authority; the execution-driven compiler stood down (`dispatch_v2_projected_schedule`)
in every v2-on row; and dispatch-v2 emitted `spl_postprocessor` on every SPL probe and
`reference_finalize` on the MITRE probe, hooks the compiler's `SCHEDULABLE_HOOKS` excludes.
Making the compiler authoritative as-is would therefore have **dropped a stage on 4 of 5
probes**.

The decision rejects both "v2 wins" and "compiler wins". The two producers answer different
questions and get different authority:

- **Phase Policy** owns mandatory lifecycle/answer-shape phases — SPL chain integrity,
  `spl_postprocessor`, `reference_finalize`, MITRE/CVE finalization. System-owned; the
  planner may never add, remove or reorder them.
- **ResourcePlan** owns investigation/evidence work — resources, dependencies, handoffs,
  bounded attempts, safe parallelism. It must never express lifecycle hooks.
- A deterministic **merge seam** is the single producer of the runnable schedule.

`predicate_hook_disposition: SYSTEM_OWNED_LIFECYCLE_HOOKS` closes the stage-drop risk by
construction: the two hooks never become plan steps, so the compiler cannot omit them.
Dispatch-v2 is **not** disabled — its long-term role is phase-policy derivation, and any
adapter over its current `stage_schedule` is a migration mechanism, not the target.

**Decided, not built.** No Plan 3 item constructs the phase contract. This fixes the target
and the boundaries; the implementation is a separate plan.

### A1 — seam coverage: inventory only

Ten production-reachable paths were inventoried and pinned by structural test. Only
`composed_dispatch` (graph) and the imperative composed-plan branch reach
`execute_plan_dispatch`; `rag_only`, `workflow_spl`, guided-hybrid and session-SPL-refine do
not, and there is no guided-hybrid branch in the graph at all. Classification: 2 `SEAM`,
4 `DECISION_REQUIRED`, 4 `KEEP_SEPARATE`, **0 adopted** — every adopt candidate would change
production-default execution authority.

Beyond the expected list: `_run_legacy_dispatch_fallback` does not merely bypass the seam,
it holds its own `hook_nodes` map and executes the v2 projection itself — a **second
execution engine**. It is the strongest adopt candidate on merit and is pinned by test so it
can neither spread nor silently disappear.

### B0 — guided refinement is live and bounded

Guided investigation had been permanently one-round: the loop gated on
`refinement_recommended`, hardcoded false since the LLM proposer was retired, so
`MAX_GUIDED_INVESTIGATION_ROUNDS` was unreachable rather than enforced. The gate now runs on
evidence actually collected — produced-evidence keys before/after collection against the
guided rail's own `validated_resource_plan` — plus a plan fingerprint so a round that would
re-plan identically never runs. The cap is checked first, empty channels never count as
produced, and side-effect replay protection is the existing `HookReplayEnvelope` machinery.
Every outcome is traced in `plan_dispatch_trace.guided_refinement_reasons`.

### B1 — flag evaluation: neutral, default unchanged

With dispatch-v2 forced off so the compiler could activate (7 of 9 composed probes),
flag ON produced **zero** schedule differences. `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED`
remains default **false**; the evidence supports no default change.

The evaluation surfaced a more important inconsistency: on two probes the EvidencePlan
booleans say `needs_spl=True` while the composed ResourcePlan carries only `narration` (or
only a contract-blocked `mcp_execution`). Plan-derived scheduling concludes "nothing
schedulable" while predicate-derived scheduling builds a full SPL lane. The downgrade to
legacy currently masks the disagreement; under a compiler-authoritative model it would
become dropped work. Recorded as a known gap for the phase-contract plan.
