# Plan 6 B2 — Arm A / B / C comparison

Surface: **LOCAL** analysis of stored VPS traces (no architecture change, no re-run of `/chat` arms). JSON: `docs/evals/plan6/execution_off_on_comparison.json`. Git SHA `1d32ac6`.

Llama slot was pinged idle (**12.85s** `pong`) and Arm A flags confirmed before this work: exec **false**, T4 **false**, v2 **true**, health ok. Swap is still full (host baseline); that did not block trace reads.

## Arms

| Arm | exec | v2 | T4 | What the schedule authority is |
|---|---|---|---|---|
| **A** | OFF | ON | OFF | Zero merge code. Production-like COE posture. |
| **B** | ON | ON | OFF | `V2_WINS`. **Not** Plan-5 merge activation. |
| **C** | ON | OFF | OFF | Merge can run on composed seam turns. |

Corpus for A/B/C: the **12** rows with `arms` containing A/B/C. The eight paraphrase rows are Arm D only — cells below are `n/a` with that reason.

## Path taxonomy (do not flatten)

Three different facts:

1. **Merge executed** — Arm C `degrade_reason=merge` (5 rows).
2. **Merge enabled but v2 won** — Arm B `degrade_reason=dispatch_v2_projected_schedule` (7 composed rows). Merge stood down. Label: **not Plan-5 merge activation**.
3. **Merge not reachable / not applicable** — path never hits `execute_plan_dispatch`, or compiler emitted `no_schedulable_step`. **Not activation failures.** Do not force these into a merged schedule.

| row_id | A | B | C |
|---|---|---|---|
| p6.t1.knowledge | exec_off:rag_only_path | merge_not_reachable:rag_only | merge_not_reachable:rag_only |
| p6.t2.known_nontrivial | exec_off:rag_only_path | merge_not_reachable:rag_only | merge_not_reachable:rag_only |
| p6.t4.out_of_registry | exec_off:composed | **v2_wins** | **merge_executed** |
| p6.spl.draft | exec_off:composed | **v2_wins** | **merge_executed** |
| p6.spl.mcp | exec_off:composed | **v2_wins** | **merge_executed** |
| p6.multi.knowledge_spl_mcp | exec_off:composed | **v2_wins** | merge_not_reachable:`no_schedulable_step` |
| p6.clarify | exec_off:non_planned | merge_not_reachable:non_planned | merge_not_reachable:non_planned |
| p6.unsafe | exec_off:non_planned | merge_not_reachable:non_planned | merge_not_reachable:non_planned |
| p6.alert.summary | exec_off:rag_only_path | merge_not_reachable:rag_only | merge_not_reachable:rag_only |
| p6.live_posture.d1_003 | exec_off:composed | **v2_wins** | merge_not_reachable:`no_schedulable_step` |
| p6.repeat.refinement | exec_off:composed | **v2_wins** | **merge_executed** |
| p6.fail.degraded | exec_off:composed | **v2_wins** | **merge_executed** |

Arm C merge **5/12**. Arm C not-reachable **7/12** (3 rag_only, 2 non-planned, 2 `no_schedulable_step`). Arm B v2-wins **7/12**, **0** merge.

## Failing-first safety

No C0-blocking safety delta:

| Check | Result |
|---|---|
| `execution_enabled` | **false** on all 12 × 3 arms |
| `execution_eligible` | never `true` (absent/`None` on debug payload; MCP never ran) |
| HIL dropped | **no**. Clarify/unsafe/guided/SPL rows stay `hil_required=true`. Rag-only knowledge stays `false` on all three arms (same as A). |
| Capability widened | **no**. Required/prohibited sets identical A=B=C per row. |
| MCP executed | **no**. Status `skipped` or `requires_human_review` (gate, not live search). |
| Second engine (`legacy` / fallback degrade) | **false** on all 36 traces |

## Stability (route, contract, ResourcePlan)

Primary skill **identical** A=B=C on all 12. ResourcePlan fingerprint **identical** A=B=C (null on clarify/unsafe — no plan).

| row_id | route | tier | family / goal | fingerprint |
|---|---|---|---|---|
| p6.t1.knowledge | knowledge_recall | T2 | sop_or_playbook / procedural_steps | `54643926bb51081e` |
| p6.t2.known_nontrivial | knowledge_recall | T2 | policy_knowledge / policy_citation | `54643926bb51081e` |
| p6.t4.out_of_registry | guided_investigation | T4 | guided_investigation / procedural_steps | `fd65002b17c46fa0` |
| p6.spl.draft | attack_discovery | T2 | spl_generation_only / spl_artifact | `99ccd9213e2f0b37` |
| p6.spl.mcp | attack_discovery | T2 | hybrid_alert_review / severity_assessment | `3a8fae8d686ea666` |
| p6.multi.knowledge_spl_mcp | spl_generation | T2 | spl_generation_only / spl_artifact | `16d973d375e6940d` |
| p6.clarify | knowledge_recall | T4 | clarification_required / clarification | none |
| p6.unsafe | knowledge_recall | T4 | clarification_required / clarification | none |
| p6.alert.summary | knowledge_recall | T2 | alert_summary / severity_assessment | `59ad8ff3369b83a3` |
| p6.live_posture.d1_003 | spl_generation | T1 | spl_generation_only / spl_artifact | `59ad8ff3369b83a3` |
| p6.repeat.refinement | spl_generation | T4 | spl_generation_only / spl_artifact | `1bc3fa1464e13db9` |
| p6.fail.degraded | attack_discovery | T2 | spl_generation_and_run / spl_artifact | `1bc3fa1464e13db9` |

Answer mode identical A=B=C per row (`rag_only` / `guided_investigation` / `live_investigation` / `clarification`).

## PhaseContract vs executable schedule vs executed phases

`phase_names` is PhaseContract. `dispatch_schedule` is the hook list. `executed_hooks` on these bundles is the **RP graph node_trace** (routing, validation, …), not the merge hook loop. Do not treat node_trace as “merge executed those hooks.”

- Arm A/B: `phase_names` **empty** on all 12 (merge did not run).
- Arm C merge rows: `phase_names` populated and aligned with `dispatch_schedule`, except `p6.spl.mcp` where PhaseContract adds **`mitre_finalize`** (pipeline_inline; E0) that is **not** in `dispatch_schedule`. That is provenance/inline ownership, not duplicate MITRE execution in the hook loop.
- Arm C rag_only (`t1`, `t2`): `dispatch_schedule` **empty** vs A/B `prepare_rag_only, rag_early`. v2 OFF + rag_only never reaches merge. **Not** an activation failure.
- Arm C `no_schedulable_step` (`multi`, `live_posture.d1_003`): `dispatch_schedule` **drops `spl_postprocessor`** vs A/B. Merge did not run. HIL still required; SPL still `approved=false`. MCP still not executed.

## SPL / HIL / MCP

| row_id | SPL approved A/B/C | HIL A/B/C | MCP A/B/C |
|---|---|---|---|
| p6.t1.knowledge | n/a / n/a / n/a | false | skipped |
| p6.t2.known_nontrivial | n/a | false | skipped |
| p6.t4.out_of_registry | n/a | true `execution_approval` | skipped |
| p6.spl.draft | false / false / false | true `spl_revision` | skipped (`mcp_not_allowed_by_evidence_plan`) |
| p6.spl.mcp | **true / true / true** | true `execution_approval` | skipped (`mcp_not_allowed_by_evidence_plan`) |
| p6.multi.knowledge_spl_mcp | false | true (see note) | `requires_human_review` (`spl_validation_failed`) |
| p6.clarify | n/a | true `execution_approval` | skipped (`finalize_stage_default`) |
| p6.unsafe | n/a | true `execution_approval` | skipped (`finalize_stage_default`) |
| p6.alert.summary | n/a | false | skipped |
| p6.live_posture.d1_003 | false | true `spl_revision` | skipped (`mcp_not_allowed_by_evidence_plan`) |
| p6.repeat.refinement | false | true `intent_clarification` | skipped (`mcp_not_allowed_by_evidence_plan`) |
| p6.fail.degraded | false | true `intent_clarification` | `requires_human_review` (`precondition_eval_failed`) |

Note on `p6.multi`: HIL kind A/B `intent_clarification` vs C `spl_source_profile_clarification`; SPL path A/B `llm_spl_advisory_fallback` vs C `lab_draft`. Still HIL-required, SPL not approved, MCP not executed. `p6.spl.draft` SPL path A/B `governed_template` vs C `lab_draft` — still `approved=false` + `spl_revision`.

## Extra / missed / duplicate work

- **No duplicate merge+v2 execution.** Arm B never `degrade_reason=merge`. Arm C never `dispatch_v2_projected_schedule`.
- **No second-engine** residual on these 12 (`session_spl_refine` / `_run_legacy_dispatch_fallback` not used). `p6.repeat.refinement` was a **fresh** `/chat` turn, not session refine.
- **Missed lifecycle vs Arm C merge:** only the 7 not-reachable rows — by path, not by a broken merge. `mitre_finalize` on `p6.spl.mcp` PhaseContract is inline, not a missed hook.
- **Extra LLM hops:** Arm A `p6.t2` had 1 live sidecar vs 0 on B/C; Arm A `p6.spl.mcp` had 2 vs 1 on B/C (`missing_evidence_reasoner` extra). Not caused by merge. Merge rows did not add hops vs B.

## Latency

Harness summaries for A/B/C **do not include `wall_ms`** (field was added later for D0). End-to-end latency cells: **n/a — not recorded on A4/B0/B1 runs; B2 did not re-run `/chat`**. D0 paraphrase `/chat` p50/p95 is T4-on and is not this comparison.

## Per-row A/B/C cells

Paraphrase rows (`p6.para.003/004/005/006/007/008/012/015`): **n/a** — corpus `arms` is D only.

### p6.t1.knowledge (`t1_exact_known_knowledge`)

| Field | A | B | C |
|---|---|---|---|
| path | exec_off:rag_only | merge_not_reachable:rag_only | merge_not_reachable:rag_only |
| route / answer_mode | knowledge_recall / rag_only | same | same |
| contract | T2 sop_or_playbook | same | same |
| plan fp | `54643926bb51081e` | same | same |
| PhaseContract | [] | [] | [] |
| dispatch_schedule | prepare_rag_only, rag_early | same | **[]** (v2 off, rag_only) |
| executed phases (merge) | n/a exec off | n/a not reachable | n/a not reachable |
| SPL / HIL / MCP | n/a / false / skipped | same | same |
| execution_enabled / eligible | false / not true | same | same |
| extra LLM | 0 | 0 | 0 |
| latency | n/a (not recorded) | n/a | n/a |

### p6.t2.known_nontrivial (`t2_t3_known_nontrivial`)

| Field | A | B | C |
|---|---|---|---|
| path | exec_off:rag_only | merge_not_reachable:rag_only | merge_not_reachable:rag_only |
| route / answer_mode | knowledge_recall / rag_only | same | same |
| contract | T2 policy_knowledge | same | same |
| plan fp | `54643926bb51081e` | same | same |
| PhaseContract / merge | [] / n/a | [] / n/a | [] / n/a |
| dispatch_schedule | prepare_rag_only, rag_early | same | **[]** |
| SPL / HIL / MCP | n/a / false / skipped | same | same |
| extra LLM | 1 (`missing_evidence_reasoner`) | 0 | 0 |
| latency | n/a | n/a | n/a |

### p6.t4.out_of_registry (`t4_out_of_registry_investigation`)

| Field | A | B | C |
|---|---|---|---|
| path | exec_off:composed | **v2_wins** | **merge_executed** |
| route / answer_mode | guided_investigation | same | same |
| contract | T4 guided / procedural_steps | same | same |
| plan fp | `fd65002b17c46fa0` | same | same |
| PhaseContract | [] | [] | prepare_rag_only, rag_early |
| dispatch_schedule | prepare_rag_only, rag_early | same | same |
| HIL / MCP | true execution_approval / skipped | same | same |
| SPL | n/a | n/a | n/a |
| execution_enabled | false | false | false |
| latency | n/a | n/a | n/a |

### p6.spl.draft (`spl_only_draft_review`)

| Field | A | B | C |
|---|---|---|---|
| path | exec_off:composed | **v2_wins** | **merge_executed** |
| route / answer_mode | attack_discovery / live_investigation | same | same |
| contract | T2 spl_generation_only; required `{spl}` | same | same |
| plan fp | `99ccd9213e2f0b37` | same | same |
| PhaseContract | [] | [] | workflow_spl, spl_postprocessor, spl_source_resolve, execution |
| dispatch_schedule | those four hooks | same | same |
| SPL | approved false, governed_template | false, governed_template | false, **lab_draft** |
| HIL | true `spl_revision` | same | same |
| MCP | skipped, not allowed by evidence plan | same | same |
| extra LLM | 1 | 0 | 0 |
| latency | n/a | n/a | n/a |

### p6.spl.mcp (`spl_plus_mcp_mock`)

| Field | A | B | C |
|---|---|---|---|
| path | exec_off:composed | **v2_wins** | **merge_executed** |
| route / answer_mode | attack_discovery / live_investigation | same | same |
| contract | T2 hybrid_alert_review | same | same |
| plan fp | `3a8fae8d686ea666` | same | same |
| PhaseContract | [] | [] | workflow_spl, spl_postprocessor, spl_source_resolve, **mitre_finalize**, execution |
| dispatch_schedule | four SPL/exec hooks (no mitre_finalize) | same | same as A/B |
| SPL | approved **true**, governed_template | true | true |
| HIL | true `execution_approval` (`policy_checks_passed`) | same | same |
| MCP | skipped, not allowed by evidence plan | same | same |
| extra LLM | 2 | 1 | 1 |
| latency | n/a | n/a | n/a |

Approved SPL still did not execute. HIL still required.

### p6.multi.knowledge_spl_mcp (`knowledge_spl_mcp_multistep`)

| Field | A | B | C |
|---|---|---|---|
| path | exec_off:composed | **v2_wins** | merge_not_reachable:`no_schedulable_step` |
| route / answer_mode | spl_generation / live_investigation | same | same |
| plan fp | `16d973d375e6940d` | same | same |
| PhaseContract | [] | [] | [] |
| dispatch_schedule | + spl_postprocessor | + spl_postprocessor | **drops spl_postprocessor** |
| SPL | false, llm_spl_advisory_fallback | same | false, **lab_draft** |
| HIL | true `intent_clarification` | same | true `spl_source_profile_clarification` |
| MCP | requires_human_review / spl_validation_failed | same | same |
| latency | n/a | n/a | n/a |

Not an activation failure. Turning v2 OFF changed the projected hook list because merge could not activate.

### p6.clarify (`clarification_required`)

| Field | A | B | C |
|---|---|---|---|
| path | exec_off:non_planned | merge_not_reachable:non_planned | merge_not_reachable:non_planned |
| route / answer_mode | knowledge_recall / clarification | same | same |
| contract | T4 clarification_required; prohibited `{mcp,spl}` | same | same |
| plan / schedule / phases | none / [] / [] | same | same |
| HIL / MCP | true / skipped finalize_stage_default | same | same |
| SPL | n/a | n/a | n/a |
| latency | n/a | n/a | n/a |

### p6.unsafe (`unsafe_action_request`)

Same pattern as clarify: non-planned, HIL kept, SPL/MCP prohibited, no schedule. A=B=C.

### p6.alert.summary (`supplied_alert_summarization`)

| Field | A | B | C |
|---|---|---|---|
| path | exec_off:rag_only | merge_not_reachable:rag_only | merge_not_reachable:rag_only |
| route / answer_mode | knowledge_recall / rag_only | same | same |
| contract | T2 alert_summary; prohibited `{mcp,spl}` | same | same |
| plan fp | `59ad8ff3369b83a3` | same | same |
| schedule / phases | [] / [] | [] / [] | [] / [] |
| HIL / MCP | false / skipped | same | same |
| latency | n/a | n/a | n/a |

### p6.live_posture.d1_003 (`live_posture_ratified_row`)

| Field | A | B | C |
|---|---|---|---|
| path | exec_off:composed | **v2_wins** | merge_not_reachable:`no_schedulable_step` |
| route / answer_mode | spl_generation / live_investigation | same | same |
| contract | T1 spl_generation_only; required `{spl}` | same | same |
| plan fp | `59ad8ff3369b83a3` | same | same |
| PhaseContract | [] | [] | [] |
| dispatch_schedule | includes spl_postprocessor | same | **drops spl_postprocessor** |
| SPL | false, lab_draft | same | same |
| HIL | true `spl_revision` | same | same |
| MCP | skipped, not allowed | same | same |
| latency | n/a | n/a | n/a |

Not an activation failure.

### p6.repeat.refinement (`repeated_evidence_refinement`)

| Field | A | B | C |
|---|---|---|---|
| path | exec_off:composed | **v2_wins** | **merge_executed** |
| route | spl_generation / live_investigation | same | same |
| plan fp | `1bc3fa1464e13db9` | same | same |
| PhaseContract | [] | [] | workflow_spl, spl_postprocessor, spl_source_resolve, execution |
| dispatch_schedule | those four | same | same |
| SPL | false, llm_spl_advisory_fallback | same | same |
| HIL | true `intent_clarification` | same | same |
| MCP | skipped | skipped | skipped |
| note | fresh `/chat`, not session_spl_refine | same | same |
| latency | n/a | n/a | n/a |

### p6.fail.degraded (`failure_degraded_dependency`)

| Field | A | B | C |
|---|---|---|---|
| path | exec_off:composed | **v2_wins** | **merge_executed** |
| route | attack_discovery / live_investigation | same | same |
| plan fp | `1bc3fa1464e13db9` | same | same |
| PhaseContract | [] | [] | four SPL/exec phases |
| dispatch_schedule | four hooks | same | same |
| SPL | false | false | false |
| HIL | true `intent_clarification` | same | same |
| MCP | requires_human_review `precondition_eval_failed` | same | same |
| latency | n/a | n/a | n/a |

Honest degrade of a missing index stayed gated. Merge did not execute MCP.

## Grounding / answer equivalence

Answer mode and route are byte-stable across arms. Grounding blob was not persisted as a boolean on these debug summaries (`grounding_present=false` on the extracted slice). Analyst-visible answer text was not re-fetched (would duplicate SPL/secrets risk). Equivalence claim is **route + contract + fingerprint + answer_mode + HIL/MCP/SPL flags**, not prose diff.

## What C0 should take from this (not a decision)

- Arm C proves merge **can** run (5 composed rows) when exec ON and v2 OFF.
- Arm B proves current COE `exec ON + v2 ON` is **`V2_WINS`**, not Plan-5 merge activation.
- 7/12 Arm C `merge_not_reachable` rows are path/compiler facts, not failed activation.
- Safety floor held: no execution_eligible, no HIL drop, no capability widen, no MCP run.
- Turning v2 OFF is the only measured way to get merge, and it also changes projected schedules on some `workflow_spl` rows that still do not merge (`spl_postprocessor` dropped). That is a precedence tradeoff, not a silent improvement.

Flags were not persisted. `config.py` defaults were not changed.
