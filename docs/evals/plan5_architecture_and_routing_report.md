# Plan 5 — Architecture and routing report

**Plan:** [`plans/2026-08-12_1230_production-readiness-understanding-phase-contract.md`](../../plans/2026-08-12_1230_production-readiness-understanding-phase-contract.md)
**Authoritative baseline:** `2f678b9` (Plan 4, PR #130)
**Branch at report:** `plan5/phase-a-runtime-map-correctness`
**D0 measurement head:** `9b23b20`
**Date:** 2026-08-13

Every routing number below is traceable to a committed artifact. This report does **not** claim that routing fully generalized. Frozen truth-set `--arm both` still reports the Plan 4 floor (`route_ok=64/76`, live `59/76`) because those arms stop at layers 1–2 by construction.

---

## 1. What Plan 5 changed

Plan 5 made the production-readiness architecture real, in the order the defects blocked each other. It did **not** patch residual routing with keyword heuristics, and it did **not** activate execution.

```
QUERY → known qualification → T1/T2/T3 sufficiently known?
   YES → trusted deterministic understanding
   NO (T4) → bounded semantic understanding (default OFF; advisory; deterministically validated)
        → RESOLVED QUERY CONTRACT (goal, ambiguity, required/prohibited caps, evidence, provenance)
        → FINAL SKILL (route/ownership signal, not the capability enumerator)
        → RESOURCE PLAN (steps+deps+evidence) + PHASE CONTRACT (mandatory-when-applicable lifecycle)
        → DETERMINISTIC MERGE → ONE RUNNABLE SCHEDULE
        → knowledge / SPL / MCP / validation / HIL, zero..N times, ordered by dependencies
        → evidence-gap evaluation → bounded refinement → ANSWER
```

### Phase A — runtime-map builder correctness

Committed artifacts: `tools/coverage_authoring/tests/test_question_runtime_map_idempotency.py`, `docs/evals/plan5/kb_overlap_diff.md`, `docs/input/mitre_enrichment/unpromoted_draft_drift_v1.json`, `docs/evals/protected_execution_baseline.json`.

- The runtime-map builder became **byte-idempotent** against `backend/app/coverage/question_runtime_map_v1.json` (sha256 `621232b2…` regenerated vs committed).
- Governed MITRE containment is preserved: regenerating the map no longer drops the 7 promoter-owned fields (`mitre_registry`, `mitre_registry_schema_version`, `mitre_requires_evidence`, `mitre_requires_alert_context`, `mitre_visibility_policy`, `mitre_candidate`, `mitre_blocked`) and therefore no longer re-routes 11 questions onto the unsuppressed fallback.
- The destructive authoring test (`write_all_question_maps`) was isolated to `tmp_path`; an interrupted run can no longer rewrite the committed map.
- The runtime map joined the durable protected manifest (`scripts/freeze_execution_baseline.py` `PROTECTED`). The committed manifest at `docs/evals/protected_execution_baseline.json` is now **15/15** (Plan 4's 14 + the map). `--check` fails closed when a declared member is missing.
- The 11-row MITRE DRAFT→runtime promotion (`7ee7a34` candidate anchors: `q0.q021/028/040`→T1071, `q0.q046/047/060/062/089`→T1110, `q0.q050/063/083`→T1059.001) remains **explicitly deferred** (`DEFERRED_SEPARATE_GOVERNED_PROMOTION`). The ledger is the audit gate; never edit it to silence new drift.

### Phase B — understanding before final route

Committed artifacts: `docs/architecture/routing_authority_map.md`, `backend/app/chat/contracts/resolved_query.py`, `docs/evals/plan5/tier_unification_measurement.md`, `docs/evals/plan5/b5_capability_enforcement_off_on.md`, `docs/evals/plan5/b6_evaluator_observability_matrix.md`.

- `ResolvedQueryContract` was introduced: typed, pre-route, carrying **no** skill and **no** execution authority (`resolved_query.py`).
- The provisional route was removed from understanding authority. Live `build_query_to_intent` calls at `canonical_planning_orchestrator.py:447` and `:516` no longer pass `routed_skill`; known-lane `primary_intent` is no longer overwritten with the routed skill; T0 no longer mutates `routed["skill"]` inside the intent stage.
- Tier vocabulary was unified on the live-path authority (`lane_router.py`); `match_tiers.py` imports the path sets. Measured disagreement: 0/105.
- Bounded T4 semantic understanding was added **default OFF** (`ai_soc_t4_semantic_understanding_enabled=false`, timeout 2.0s). T1–T3 never invoke it. Timeout/error keeps the deterministic contract. The hop cannot set a skill, cannot reduce required capabilities, and cannot widen capabilities not implied by the accepted family.
- Route-level live capability enforcement was measured and left **default OFF** (`ai_soc_live_capability_enforcement_enabled=false`).

**B5 lesson (binding amendment 5):** required capabilities are ultimately satisfied by the **complete governed schedule**, not necessarily by one primary skill. Route-level "one skill must grant everything" enforcement was rejected because it demoted the in-catalogue hunt `cisco.ot.029` from `spl_generation` to `knowledge_recall`, destroying its candidate SPL and HIL gate, while producing **zero** truth-set routing improvements. A plan whose primary skill is `spl_generation` may legitimately satisfy `{spl, mcp}` as `spl → validate_spl → mcp read/evidence → synthesis`. Capability compatibility remains a diagnostic/deny constraint; its automatic consequence must **not** be `veto → knowledge_recall`. `cisco.ot.029` was **not** patched with a special-case route rule.

### Phase C — phase contract + canonical execution

Committed artifacts: `backend/app/planner/phase_registry.py`, `phase_policy.py`, `phase_contract.py`, `phase_schedule_merge.py`, `docs/evals/plan5/c0_phase_surface_disagreement.md`, `docs/evals/plan5/c3_fallback_equivalence.md`, `docs/evals/plan5/c2_phase_merge_probe.json`.

- Canonical `PhaseRegistry`: closed catalog of 11 lifecycle phases. A name outside the catalog is rejected.
- Deterministic `PhasePolicy` resolver: `(ResolvedQueryContract, ResourcePlan, PhasePolicyInputs) → applicable/mandatory phases`. Applicability is a predicate over deterministic inputs only — never an LLM, never a heuristic, never a count. Lifecycle phases are **mandatory-when-applicable**, not universally mandatory (a knowledge-only turn carries no SPL chain).
- Per-run immutable `PhaseContract`: frozen once resolved. Neither the ResourcePlanner, the four advisory specialists, nor any LLM advisory may add, remove, reorder, or downgrade a contracted phase.
- ResourcePlan + PhaseContract merge into **one** dependency-valid schedule (`merge_schedule` at the single existing seam `planner/executor.py:286`). Schedule-level capability satisfaction is demonstrated: an `spl_generation`-primary plan of `spl → validate → mcp` reports `satisfied=True, granted={spl, mcp}` — the case route-level enforcement got wrong on `cisco.ot.029`.
- Execution architecture remains behind `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED=false`. Flag-off runs **zero** merge-seam code. Dispatch-v2 projected schedule still wins when present.
- No `DECISION_REQUIRED` seam was adopted. `_run_legacy_dispatch_fallback` was **not** retired. Inventory stays 2 SEAM / 4 DECISION_REQUIRED / 4 KEEP_SEPARATE, **0 adopted**.

**Phase-C findings carried forward (not fixed in Plan 5):**

1. `mitre_finalize` / `cve_adapter` execute inside `graph_node_context_finalize` (`pipeline.py` MITRE via `run_mitre_evidence_branch`, CVE via `_resolve_vulnerability_source_status`) while not being represented consistently by existing schedule surfaces. The PhaseRegistry names them as `pipeline_inline` owners; they remain absent from both hook loops. The PhaseContract records them in `inline_mandatory` so "absent from the schedule" cannot be misread as "not owed by this run".
2. `_run_legacy_dispatch_fallback` does not run `spl_postprocessor`. It remains safe because the MCP gate refuses unapproved/null `normalized_spl` (`mcp_execution_gate.py`), and the RP-graph `spl_validate` node still runs on the default spine. The fallback is safe by virtue of other gates, not by running the lifecycle it owes.

---

## 2. D0/D1 residual routing result

Source: [`docs/evals/plan5/residual_routing_after_architecture.md`](plan5/residual_routing_after_architecture.md) (producer `scripts/eval_residual_routing_after_architecture.py`; machine table + JSON). T4 side probe: [`docs/evals/plan5/d0_t4_semantic_side_probe.json`](plan5/d0_t4_semantic_side_probe.json). D1 decisions recorded in the plan's Approved decisions table.

**Residual cohort:** 25 rows = 3 D2 + 10 ownership + 12 paraphrase.

### Layer results

| Layer | resolved | unchanged | regressed |
|---|---|---|---|
| L1 frozen `select_route_from_understanding` | **0** | **25** | **0** |
| L4 `adjudicate_route` | **10** | **15** | **0** |
| L5 full `/chat` | **10** | **15** | **0** |

**L4 and L5 agree row-for-row.** The committed product route is the adjudicated route on all 25 rows. The frozen arms report **0 of the same 10** — exactly the blindness B6 documented (`docs/evals/plan5/b6_evaluator_observability_matrix.md`). Citing `--arm both` as "the architecture changed nothing" would be wrong on 10 rows.

B3 decontamination produced the routing improvements. Phase C improved execution readiness, **not** route counts. The old frozen truth-set arms do not observe the L4/L5 improvements **by construction**. Parity `120 exact` remains runtime-spine equivalence only, not routing correctness.

### Resolved by architecture (10)

All now commit `spl_generation` at L4 = L5, with contract `intent_family=spl_generation_only` / `answer_goal=spl_artifact` / `required_capabilities={spl}`, clearing `capability_inconsistent`:

- **All 7 measured SPL-needing ownership rows:** `rt.d1.003`, `rt.d1.005`, `rt.d1.006`, `rt.d1.011`, `rt.d1.012`, `rt.d1.013`, `rt.d1.014`
- **`rt.d2.003`**
- **`para.001`**
- **`para.010`**

### Unchanged but already route-correct (7)

`knowledge_recall` is inside each label's `acceptable_skills`:

- `rt.d2.010`
- `rt.d2.017`
- `para.002`
- `para.009`
- `para.011`
- `para.013`
- `para.014`

### Genuine remaining residue (8)

`para.003/004/005/006/007/008/012/015`

All eight reach T4 / `out_of_registry` / `clarification_required` with empty `required_capabilities`. D0/B4 side probe: semantic hop invoked **8/8**, accepted **0/8** (6 timeout at the 2.0s bound, 2 `empty_output` / `llm_model_slot_busy`). OFF and ON `ResolvedQueryContract` remain identical. No safe deterministic discriminator exists (every field is identical across the 8 and identical to a legitimately ambiguous T4 query).

### Regressed

**0** at any layer. Frozen `--arm both --check` still 0 regressions (`route_ok=64/76`, live `59/76`).

### D1 decisions (closed)

| Decision | Value | Scope |
|---|---|---|
| `D1_LIVE_POSTURE_ROUTE` | `RATIFIED_FOR_MEASURED_ROWS` | The 7 measured live-query/posture rows that now commit `spl_generation`. **Not** a generalization that `asset_identity_context` / `data_source_health` are always owned by `spl_generation`. No capability contract widening. |
| `D1_PARAPHRASE_RESIDUE` | `DEFERRED_T4_SEMANTIC_SERVING_LIMIT` | The 8 genuine unresolved paraphrases. Classified as a T4 semantic-understanding serving/latency/generalization limitation, **not** a routing-table defect. |

Explicitly **not** done for the 8 paraphrases: keyword heuristic; skill-contract widening; "clarification-by-design" relabel; T4 timeout raise merely to improve the metric; serving/model posture change inside Plan 5.

---

## 3. Default-OFF / non-activated posture

Repo defaults (`backend/app/config.py`):

| Flag / posture | Default | Plan 5 status |
|---|---|---|
| `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | **false** | Architecture proved; not activated. Flag-off runs zero merge-seam code. |
| Live route-level capability enforcement (`ai_soc_live_capability_enforcement_enabled`) | **false** | Measured OFF/ON; left OFF (`DEFAULT_OFF_ARCHITECTURALLY_DEFERRED`). `cisco.ot.029` is the measured reason. |
| T4 semantic understanding (`ai_soc_t4_semantic_understanding_enabled`) | **false** | Bounded (2.0s, no failover). T1–T3 never invoke. D0 measured 0/8 accepted at the current bound. |

**Not adopted / not enabled:**

- No `DECISION_REQUIRED` execution seam adopted (inventory 2 / 4 / 4, 0 adopted).
- `_run_legacy_dispatch_fallback` not retired.
- No unsafe live execution enabled (`execution_eligible` stays false on candidates; MCP gate still requires approved non-null `normalized_spl`).
- No 11-row MITRE DRAFT promotion.
- Six stale governance reports remain intentionally unrefreshed.

COE warning (unchanged): `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` is **false at repo default** and **true on the COE host**. Dispatch-v2 projected schedules still beat the execution-driven compiler. Any change to the dispatch builder or the fallback loop is live on COE the moment it lands.

---

## 4. Honesty constraints

- Do **not** claim routing fully generalized. L1 is unchanged on all 25 residual rows. Production improvement is L4/L5 only, and only on the 10 resolved rows.
- Do **not** cite frozen `--arm both` `64/76` as evidence that Plan 5 routing work had no effect — those arms do not call `adjudicate_route`.
- Do **not** cite parity `120 exact` as routing correctness. `run_production_parity_eval.py` compares the two runtime spines against each other and never reads `question_105_golden.jsonl`.
- Do **not** treat `spl_generation` as the owner of every `asset_identity_context` / `data_source_health` question. Ratification is row-scoped to the 7 measured live-posture queries.
- Plan 4 D3 advisory-finality is unchanged (`git diff 2f678b9 -- backend/app/routing/governance.py` was empty at B6 close).

---

## 5. Explicitly deferred future work

Out of scope for Plan 5; each needs its own plan and approval:

1. T4 semantic-understanding serving/SLO (latency target, model concurrency, alternate classifier) for the 8 residual paraphrases.
2. 11-row MITRE DRAFT→runtime promotion (`MITRE_DRAFT_RUNTIME_PROMOTION_RECONCILIATION`).
3. Activating `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` (default remains false).
4. Activating live route-level capability enforcement (rejected as the satisfaction locus; schedule-level is the target).
5. Adopting any `DECISION_REQUIRED` seam or retiring `_run_legacy_dispatch_fallback`.
6. Representing `mitre_finalize` / `cve_adapter` consistently on schedule surfaces (they already execute inline).
7. Refreshing the six stale governance reports, the 105 answer goldens, or the frozen routing truth-set baseline.

---

## 6. Traceability

| Claim | Artifact |
|---|---|
| Builder idempotency + containment | Plan 5 A2/A5 evidence; `test_question_runtime_map_idempotency.py`; `test_question_runtime_map_mitre_containment.py` |
| Protected manifest 15/15 | `docs/evals/protected_execution_baseline.json`; `scripts/freeze_execution_baseline.py --check` |
| 11-row DRAFT deferral | `docs/evals/plan5/a2_5_deferred_promotion_decision.md`; `docs/input/mitre_enrichment/unpromoted_draft_drift_v1.json` |
| B5 cisco.ot.029 / default-OFF | `docs/evals/plan5/b5_capability_enforcement_off_on.md` |
| Evaluator layer blindness | `docs/evals/plan5/b6_evaluator_observability_matrix.md` |
| Phase-surface disagreement | `docs/evals/plan5/c0_phase_surface_disagreement.md` |
| Compiler stage-drop closed (flag-on probe) | `docs/evals/plan5/c2_phase_merge_probe.json` (`merged_stage_drops=0/5`) |
| Fallback not equivalent, not retired | `docs/evals/plan5/c3_fallback_equivalence.md` |
| Residual 10/15/0 at L4=L5 | `docs/evals/plan5/residual_routing_after_architecture.md` + `.json` |
| T4 hop 8/8 invoked, 0/8 accepted | `docs/evals/plan5/d0_t4_semantic_side_probe.json` |
| D1 decisions | Plan 5 Approved decisions + D1 Evidence |
