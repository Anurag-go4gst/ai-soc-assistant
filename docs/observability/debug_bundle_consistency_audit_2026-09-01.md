# Debug bundle consistency audit — trace `8791eeb8-6814-4c0a-86d6-6bb69e9813f2`

Scope: trace/projection/observability only. No runtime-authority, SPL, routing,
execution, MCP, HIL-policy or evidence-framework change.

Reference run: P2 review-only SPL authoring
(`answer_mode=spl_utility_authoring`, `use_case_id=auth_success_after_failure`,
`spl_path=deterministic_compiler_draft`, MCP off, `llm_live_calls=0`).

Reproduced in-process (`resource_planner_graph`, COE profile env) with the same
`final_output` / `debug_summary` / `control_plane_trace` shape as the stored bundle.

## Field ownership map

| Field | Value in trace | Owning writer | Stage | Kind | Superseded later? |
|---|---|---|---|---|---|
| `run.metadata.llm_used` | `false` | `app/quality/store.py::_llm_used` | post-response | projection | no — legacy meaning is "LLM materially authored final SPL/synthesis" |
| `run.metadata.llm_live_calls` | `0` | `debug_summary.llm.live_calls` | post-response | projection | no |
| `final_output.hil_required` | `true` | `app/chat/final_output_trace.py` (`bool(human_review)`) | post-response | projection | — |
| `final_output.hil_reason` | `source_profile_slots_missing` | `app/spl/spl_source_resolve.py::build_spl_source_profile_review` via `pipeline.py::graph_node_spl_source_resolve` | `spl_source_resolve` | intermediate | **yes** — final binding summary shows `bindings_missing == []` |
| `debug_summary.hil.*` | required/reason mirror | `app/chat/debug_summary.py::_hil_block` | post-response | projection | same as above |
| `run_contract.effective_hil_required` | `false` | `app/chat/run_contract_builder.py` | finalize | authoritative | no |
| `evidence_plan.requires_hil` / `needs_hil` | `false` | evidence planner | planning | authoritative for plan | no |
| `query_to_intent.intent_classification.requires_hil` | `false` | query→intent | understanding | authoritative for intent | no |
| `evidence_plan.source_profile_binding_summary.source_profile_bindings_missing` | `[]` | source-profile binding | planning | authoritative | no |
| `…_bindings_applied` | index=`pgcil_soc`, sourcetype=`pgcil:auth` (`coe_store`) | source-profile binding | planning | authoritative | no |
| `debug_summary.spl.review_only_spl_postprocessor_trace.resolved_index` | `<your_index>` | `app/chat/review_only_spl_renderer.py` postprocessor | `spl_postprocessor` | authoritative for *display* | no |
| `…index_rewrite_reason` | `placeholder_over_draft_index` | same | same | authoritative | no |
| `evidence_state.obtained` | `["rag","executed_evidence","negative_evidence"]` | `app/evidence/minimal_evidence_state.py` | finalize | derived view | — |
| `evidence_state.missing` | includes `spl`, `mcp:splunk` | same | finalize | derived view | — |
| `evidence_plan.needs_rag` | `false` | evidence planner | planning | authoritative | no |
| `control_plane_trace.rag_trace.match_status` | `retrieved` | `retrieve_soc_kb` called from `pipeline.py:3513` (`graph_node_spl_source_resolve`) | `spl_source_resolve` | actual | — |
| `run_contract.spl_validated` | `false` | run-contract builder | finalize | authoritative for *execution* validation | no |
| `spl_artifact_handoff_summary.validator_status` | `rejected` | SPL degrade read model | finalize | projection | no |
| `debug_summary.spl.reject_reasons` | `["review_only_spl_authoring"]` | SPL validator | `spl_validation` | authoritative | no |
| `candidate_spl.utility_spl_draft_trace.semantic_fidelity_final.passed` | `true` | authoring fidelity | `workflow_spl` | authoritative for *authoring* | no |
| `candidate_spl.utility_spl_draft_trace.analyst_synthesis_source` | `DETERMINISTIC_SYNTHESIS_FALLBACK` | `app/spl/review_only_analyst_synthesis.py::attach_synthesis_trace` | synthesis | authoritative | no |
| `candidate_spl_generation.llm_spl_draft_*` | requested `true` / completed `false` / used `false` | utility SPL authoring | `workflow_spl` | authoritative | no |
| `run_contract.source_evidence_available` | `true` | run-contract builder | finalize | authoritative (counts *any* SourceEvidence) | no |
| `mcp_execution.*` | status `skipped`, `result_count 0` | MCP gate | `execution` | authoritative | no |
| `status` | `human_review` | run status | finalize | authoritative | no |

## Root causes

1. **HIL (Issue 1).** The review-only postprocessor deliberately substitutes
   `index=<your_index>` for display hygiene (`index_rewrite_reason=placeholder_over_draft_index`).
   `graph_node_spl_source_resolve` then sees an unresolved `<your_index>` slot and raises
   `source_profile_slots_missing`, even though the source-profile store resolved
   index and sourcetype (`bindings_missing == []`). The reason is a *deferred execution*
   requirement, not a current-turn blocker on a review-only, do-not-execute request.
2. **Source profile (Issue 2).** Trace reports both "binding applied = `pgcil_soc`"
   and a rendered `<your_index>` with no field distinguishing *resolved* from *exposed*.
3. **Synthesis (Issue 3).** `attach_synthesis_trace` already records
   `analyst_synthesis_source` / `analyst_synthesis_dropped_reasons` on
   `candidate_spl.utility_spl_draft_trace`, but nothing projects it into the bundle,
   so `llm_used=false` / `composer_attempted=false` / `narration_calls=0` read as
   "provenance unknown". Attempt flag and latency were not recorded at all.
4. **RAG (Issue 4).** `graph_node_rag_early` correctly skips RAG for SPL utility
   authoring. `graph_node_spl_source_resolve` then performs its *own* SOC-KB lookup
   (`workflow_stage="spl_source_resolve"`) purely to hint source-profile slots. That
   record lands in `SourceEvidence` and surfaces as runtime RAG evidence.
5. **`executed_evidence` (Issue 5).** `canonical_facts_spine._harvest_source_evidence`
   labels *every* SourceEvidence record as fact kind `executed_evidence`, including the
   RAG record above (`source_type=rag`, 5 KB chunks). `minimal_evidence_state` then sees
   `row_count=5` and marks `executed_evidence` obtained while MCP was skipped and
   `result_count == 0`. The fact's own `provenance.evidence_class` (`rag` vs `mcp_search`)
   already carries the correct discriminator and was simply not consulted.
6. **`spl` missing (Issue 6).** `spl` enters `required` from `evidence_plan.needs_spl` and
   means *executed SPL evidence*; nothing marks the review artifact, so it reads as a gap.
   `required`/`missing` feed `evidence_sufficiency` → `context_sufficiency`, so the list
   itself is runtime state and must not be rewritten; the semantics were invisible.
7. **Validation (Issue 7).** One vocabulary covers three different verdicts: authoring
   fidelity (passed), lab-candidate validation (`reject_reasons=["review_only_spl_authoring"]`),
   and execution promotion (not applicable).
8. **LLM SPL candidate (Issue 8).** Requested/completed/generated/dropped were emitted as
   independent booleans with no ordered lifecycle.
9. **`llm_used` (Issue 9).** One boolean over four roles.
10. **EvidencePlan (Issue 10).** Investigation checklist/DNS leg/MITRE candidates are catalogue
    metadata for this answer mode, unmarked as non-runtime.
11. **`source_evidence_available` (Issue 11).** True because a KB record exists; not
    distinguishable from live telemetry availability.
12. **`status=human_review` (Issue 12).** Artifact review, execution approval and a
    current-turn HIL block were not separable.

## Precedence adopted for FINAL EFFECTIVE STATE

```
resolved query / intent
  -> final ResourcePlan
  -> final source-profile resolution
  -> final SPL authoring / fidelity result
  -> final execution + HIL adjudication
  -> final synthesis result
  -> final output projection
```

Intermediate values stay in `control_plane_trace`, `timeline` and the legacy fields.
`debug_summary.effective_state` (also mirrored to `run.metadata.effective_state`)
is the final adjudicated read model.

## Consistency matrix — before vs after

Measured on an in-process replay of the same P2 request under the COE profile,
which reproduces the stored trace's `final_output` / `debug_summary` /
`control_plane_trace` shape and the same P2 SPL hash `537580db…`.

| Field | Before | After | Authoritative source | Why |
|---|---|---|---|---|
| `hil_required` (legacy) | `true` | `true` (unchanged) | `human_review` presence | legacy meaning preserved for existing consumers |
| `hil_reason` (legacy) | `source_profile_slots_missing` | unchanged | `graph_node_spl_source_resolve` | preserved; superseded status now stated explicitly |
| `effective_state.hil.current_turn_hil_required` | *absent* | `false` | review-only + do-not-execute + artifact delivered + bindings resolved | the turn delivered its artifact; nothing blocks the analyst now |
| `effective_state.hil.final_hil_reason` | *absent* | `null` | final source-profile resolution | invariant 2 |
| `effective_state.hil.execution_hil_required` | *absent* | `true` | execution not authorized | a future execution still needs approval |
| `effective_state.hil.execution_hil_reason` | *absent* | `review_only_placeholder_pending_binding` | postprocessor placeholder trace | bindings exist; the *draft* withholds the index |
| `effective_state.hil.initial_hil_candidate_reason` | *absent* | `source_profile_slots_missing` | `spl_source_resolve` | history retained, not erased |
| `run_contract.effective_hil_required` | `false` | unchanged | RunContract | already correct |
| `source_profile_bindings_missing` | `[]` | unchanged | binding summary | already correct |
| `effective_state.source_profile.slots.index.resolved_value` | *absent* | `pgcil_soc` | COE store | resolution is real |
| `…slots.index.exposed_in_review_draft` | *absent* | `false` | rendered SPL | display differs from resolution |
| `…slots.index.display_value` | *absent* | `<your_index>` | postprocessor | what the analyst actually sees |
| `…slots.index.withholding_reason` | *absent* | `review_only_placeholder_policy` | postprocessor `index_rewrite_reason` | intentional, not a gap |
| `…unbound_placeholders_in_review_draft` | *absent* | `[]` (P2), `['<dns_sourcetype>','<your_index>']` (P4) | rendered SPL | `bindings_missing == []` alone over-claims readiness |
| `spl_validated` (legacy) | `false` | unchanged | RunContract | execution-promotion verdict |
| `validator_status` (legacy) | `rejected` | unchanged | handoff read model | ditto, now defined in place |
| `effective_state.validation.authoring_fidelity_status` | *absent* | `passed` | `semantic_fidelity_final` | the authored SPL passed |
| `effective_state.validation.candidate_spl_validation_status` | *absent* | `withheld_review_only` | `reject_reasons` | deliberate withholding, not a defect |
| `effective_state.validation.execution_validation_status` | *absent* | `not_applicable_review_only` | review-only context | execution promotion never ran |
| `effective_state.validation.final_spl_rejected_by_validator` | *absent* | `false` | reject-reason analysis | the compiler SPL was not refused |
| `evidence_state.obtained` | `["rag","executed_evidence","negative_evidence"]` | `["rag","source_evidence","negative_evidence"]` | fact `provenance.evidence_class` | a RAG record cannot satisfy executed evidence |
| `evidence_state.missing` | unchanged | unchanged | required keys | `required`/`missing` are runtime state; untouched |
| `evidence_state.items[spl].applicability` | *absent* | `executed_spl_result` | required-key semantics | the gap is an executed result, not the artifact |
| `effective_state.evidence.spl_artifact.status` | *absent* | `obtained` | rendered artifact | invariant 4 |
| `effective_state.evidence.live_execution_evidence_available` | *absent* | `false` | MCP status + row count | invariant 1 |
| `source_evidence_available` (legacy) | `true` | unchanged | RunContract | now defined as "any SourceEvidence record" |
| `rag_trace.match_status` | `retrieved` | unchanged | retrieval | the event is real and stays |
| `rag_trace.retrieval_workflow_stage` | *absent* | `spl_source_resolve` | `retrieve_soc_kb` caller | names the stage that performed it |
| `effective_state.rag.runtime_rag_used` | *absent* | `false` | plan `needs_rag` + stage | not investigation RAG |
| `effective_state.rag.enrichment_lookup_used` | *absent* | `true` | same | classified, not suppressed |
| `llm_used` (legacy) | `false` | unchanged | `quality.store._llm_used` | correct under its own definition |
| `effective_state.llm.llm_used_for_synthesis` | *absent* | `false` | `analyst_synthesis_source` | role-scoped |
| `effective_state.llm.llm_used_for_spl_authoring` | *absent* | `false` | candidate lifecycle | role-scoped |
| `effective_state.llm.calls_attempted` / `calls_completed` | *absent* | `1` / `0` | budget records | attempts ≠ completions |
| `effective_state.synthesis.synthesis_source` | *absent* | `DETERMINISTIC_SYNTHESIS_FALLBACK` | `attach_synthesis_trace` | prose provenance is now recoverable |
| `effective_state.synthesis.synthesis_latency_ms` | *not recorded* | recorded | `_attempt_llm_synthesis` | new observability |
| `effective_state.llm_spl_candidate_lifecycle.*` | 4 flat booleans | ordered steps + `failure_stage` | `authoring_failure_stage` | where it stopped, not just that it did |
| MCP status / result_count | `skipped` / `0` | unchanged | MCP gate | already correct |
| `execution_eligible` / `approved` / `normalized_spl` | `false` / `false` / `null` | unchanged | validator | governance posture untouched |

## Out of scope — reported, not changed

`P1` and `P4` raise a genuine runtime `session_context_stale` / `session_context_stale_or_missing`
review (`pipeline.py::_session_stale_clarification_review`) even though the request is a
review-only SPL authoring ask with no alert context. It reproduces on a fresh session id
and is **not** a projection defect: the projection reports it faithfully and marks it
`superseded_by_final_resolution: false`. Suppressing it would be a HIL-policy change,
which this loop's stop conditions forbid. Whether a review-only authoring turn should
demand alert context is a separate decision.
