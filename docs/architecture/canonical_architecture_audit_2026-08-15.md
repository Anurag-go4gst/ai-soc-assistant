# Canonical architecture audit — 2026-08-15

> **RECONSTRUCTED AFTER SHARED-WORKTREE LOSS.**
>
> The original of this file was untracked when a parallel session checked
> `/var/www/ai-soc-assistant` off the Plan 7 branch on 2026-08-15 at 16:25:32 UTC. It was never a
> git object, so no wording survived and none is guessed at here. This is a **fresh, concise
> reconstruction** assembled only from three committed sources: the frozen `architecture.md`
> (`a8f02e3`, content SHA-256 `c1c4ba8a88d8f245752188a76442102978eceb0c1bdb410717b789649fb9a034`),
> committed Plan 7 evidence under `docs/evals/plan7/`, and the requirements stated in
> `plans/2026-08-15_0602_canonical-architecture-authority-convergence.md`.
>
> **It makes no architecture decision and changes no runtime.** Where the original may have
> carried finer-grained code/line mappings, this reconstruction marks the role
> `AUDIT_RECONSTRUCTION_GAP` rather than inventing one. Plan 8 **SPL0** and **G1** are the items
> that fill those in against the implemented tree; this file is their attachment target, not a
> substitute for them.

**Scope.** Measured current state as of Plan 7 closure (`a546ab0`, Plan 7 25/25). Classifications
use the Plan 8 vocabulary: `EXISTS` / `PARTIAL` / `MISSING` / `MISPLACED`.
**Plan 8 G1 (below) supersedes this table for post-implementation status.** This reconstruction
remains the Plan 7 starting baseline.

**Not in scope.** No new architecture decision, no owner reassignment, no runtime change, no
reopening of a Plan 7 recorded STOP.

## Authority baseline established by Plan 7

| Property | State at Plan 7 closure | Evidence |
|---|---|---|
| Normal execution authority | `ResourcePlan + PhaseContract` — **sole** | `a4_authority_acceptance.md`, `e1_closure_gates.md` |
| dispatch-v2 | Retired to rollback/test-only; fenced — with ResourcePlan execution ON, v2 cannot win even if its flag is enabled | `a5_old_path_audit.md`, `a6_stop_decision_packet.md` |
| `V2_WINS` | **0** rows across the measured corpus | `d2_persistence.md`, `d3_rollback.md` |
| Mandatory lifecycle | A2 = OPTION A; a resource downgrade may remove unavailable resource work but **not** applicable mandatory lifecycle work; `spl_postprocessor` contract-inserted on every seam row | `a2_stop_decision_packet.md`, `a3_ownership_fix.md` |
| Legacy fallback | `LEGACY_FALLBACK_ROLLBACK_ONLY_RETAIN_TEMPORARILY`; target graph cannot enter it; rollback path fails closed | `a7_fallback_lifecycle_proof.md` |
| T4 semantic hop | Enabled, reasoning-only; never routing, capability, or tool authority; locked `intent_family` / `answer_goal` immutable | `c3_remediation_evidence.md` |
| T4 serving | **BLOCKER** — `T4_SEMANTICALLY_VIABLE_BUT_VPS_SERVING_BLOCKER` | `c3_stop_decision_packet.md`, `e2_decision.md` |
| Production go-live | **DEFERRED / NO-GO** | `e2_decision.md` |
| Live MCP / Splunk | `live_mcp_unproven`; `MCP_MODE=mock` throughout | `e2_decision.md` |

## Canonical role audit

| # | Canonical role (`architecture.md`) | Class | Measured basis / residual |
|---|---|---|---|
| 1 | Deterministic authority over LLM output (§2.1, §2.8) | `EXISTS` | Advisory-only LLM surfaces; deterministic finality restored in Plan 4 D3 and unchanged; E1 invariants 7/7 |
| 2 | T1–T3 before T4; T4 only for unresolved meaning (§2.2) | `EXISTS` | T4 is a bounded hop behind `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED`; deterministic tiers run first and fail closed |
| 3 | Final `ResolvedQueryContract` authoritative before clarification / final ownership / ResourcePlan creation (§2.3) | `PARTIAL` | A typed RQC is emitted before route adjudication (Plan 5 B). Plan 8 P1 requires it to be **final and authoritative** at all three of those points; that convergence is not done |
| 4 | Primary skill means ownership, not capability veto (§2.4) | `PARTIAL` | Plan 5 B5 rejected "one primary skill must grant everything"; live route-level capability enforcement remains **default OFF**. Removing the residual veto is Plan 8 scope |
| 5 | Composable resources (§2.5) | `EXISTS` | ResourcePlan composes multi-resource work; four advisory specialists remain read-only auditors |
| 6 | Side effects separated from reasoning (§2.6) | `EXISTS` | D1 measured `side_effect_totals.allowed: 0`; MCP gate is the only side-effecting authority; candidate SPL never executable |
| 7 | Structured `InvestigationOutcome` precedes narration and action (§2.7, §InvestigationOutcome) | `MISSING` | No minimal governed `InvestigationOutcome` entity exists between evidence sufficiency and synthesis/actions. Plan 8 core scope |
| 8 | Minimal canonical `EvidenceState` (§Minimal canonical EvidenceState) | `MISSING` | Required/obtained/missing/stale/invalidated/blocked is not a derived first-class state today. Plan 8 core scope |
| 9 | Evidence reuse / invalidation across turns | `MISSING` | Not implemented; Plan 8 scope |
| 10 | ResourcePlan compiler (§ResourcePlan compiler) | `EXISTS` | Deterministic compiler live and authoritative at Plan 7 closure |
| 11 | `PhaseRegistry → PhasePolicy → PhaseContract` (§PhaseRegistry…) | `EXISTS` | Closed registry, deterministic resolver, per-run immutable contract; merge seam active |
| 12 | Source resolution vs postprocessing ownership (§Source resolution versus postprocessing) | `PARTIAL` | `spl_source_resolve` and `spl_postprocessor` both exist and the A3 fix guarantees the postprocessor is not silently dropped. The **nine-answer entity/constraint-flow map** the architecture calls for is `AUDIT_RECONSTRUCTION_GAP` — Plan 8 **SPL0** owns it |
| 13 | Authorization bound to the governed call (§Authorization is bound to the governed call) | `PARTIAL` | Deterministic policy + per-call analyst confirmation + HIL/RBAC hold at the MCP gate (D1 row 9: MCP-down → `requires_human_review`, nothing fabricated). Whether authorization is **tool-level only or bound to the final normalized call** is `AUDIT_RECONSTRUCTION_GAP` — Plan 8 **AUTH0** |
| 14 | Trust boundary for untrusted evidence / prompt content | `PARTIAL` | Injection filter and data minimizer exist; no prompts, reasoning, RAG chunks, or credentials reach MCP. A consolidated boundary statement is Plan 8 scope |
| 15 | Model health, circuit breaking, backpressure, **human-only restart** (§Model health…) | `MISSING` | **F2**: `/v1/models` returns 200 through an unusable model. No circuit breaker or backpressure subsystem. Human-only restart is honoured operationally (no automated restart exists, and none was performed in Plan 7). Plan 8 **REL0** |
| 16 | Degradation signalling | `MISSING` | **F1**: DB loss degrades authority to `canonical_non_planned` and still answers, with no analyst-visible degrade signal. Safe but silent. Plan 8 **REL0** |
| 17 | Clarification (§Clarification) | `EXISTS` | Three-uncertainty rule enforced deterministically; clarification only for an unresolved referent. P6 `spl_source_profile_clarification` is accepted current safety behaviour |
| 18 | Action flow / LLM role in actions (§Action flow, §LLM role in actions) | `PARTIAL` | Action lane exists behind a default-off flag; LLM is advisory. Governed action authority after `InvestigationOutcome` is Plan 8 scope |
| 19 | Architecture Phase 10 | `deferred` | Explicit approved deferral; carried, not silently ignored |
| 20 | Detailed per-step evidence attribution, full step-instance execution, generic `PlanDelta`, richer capability views | `deferred` | Evidence-gated extensions by the plan's own framing; not admitted without measured evidence |

## Residual dispositions

Every residual above has an explicit disposition, as Plan 8 G1's Verify requires.

| Residual | Disposition |
|---|---|
| `MISSING` — `EvidenceState`, `InvestigationOutcome`, evidence reuse/invalidation | Plan 8 core scope; not a Plan 7 defect |
| `MISSING` — circuit breaking / backpressure / degradation signalling (**F1**, **F2**) | Plan 8 **REL0**; carried from Plan 7 unaccepted and unsolved |
| `PARTIAL` — final RQC authority, primary-skill veto | Plan 8 **P1** and following |
| `PARTIAL` + `AUDIT_RECONSTRUCTION_GAP` — SPL entity/constraint flow map, call-level authorization | Plan 8 **SPL0** / **AUTH0** must produce the nine-answer code/line map against the implemented tree |
| `deferred` — Architecture Phase 10, evidence-gated extensions | Approved deferrals, listed rather than ignored |
| **T4 serving (F3)** | **CRITICAL BLOCKER**, not an accepted risk, not downgraded; blocks production GO |
| Live Splunk/MCP | `live_mcp_unproven` — outside proven production scope |
| MITRE promotion | Deferred; 11-row DRAFT drift ledger unchanged |
| `CONFIG_REBUILD_DRIFT` | Closed for the development profile only; COE/production profiles unproven |

**No `MISPLACED` authority finding is recorded in this reconstruction.** That is a statement about
what this file can substantiate from committed evidence, not a claim that none exists — Plan 8 G1
requires zero *unexplained* `MISPLACED` findings, measured against the implemented tree.

## Integrity note

`architecture.md` was not modified by this reconstruction. If its committed content ever stops
matching the recorded SHA-256, the correct action is to STOP with
`ARCHITECTURE_FREEZE_REFERENCE_REQUIRED` — a coding agent may not edit `architecture.md` to clear
that STOP.

## Plan 8 SPL0 — nine-answer SPL entity / lifecycle / authorization map

AUDIT_ONLY against the implemented tree at Plan 8 SPL0 (2026-08-16). **No runtime change.**
Does not reopen Plan 7 A2 OPTION A or A3 `spl_postprocessor` lifecycle ownership.
Verify `rg` over the listed packages returned **4715** matching lines.

| # | Question | Class | Code/line map |
|---|---|---|---|
| 1 | Where source IP, dest IP, host, user, domain, port, geography, and time are extracted | `PARTIAL` | `backend/app/query_understanding/parser.py` `_entities()` **213–251**: `IP_RE` **19** → `source_ip`; `destination_ip=[]` always; `HOST_RE` **23** / `_HOST_BARE_RE` **25** → `host`; `USER_RE` **24** / bare/leading user → `user`; `PORT_RE` **72** → `port_numbers`; `normalize_time_window` `backend/app/query_understanding/time_window.py` **8–29** (`yesterday` → `earliest=-1d@d latest=@d` **27–28**). **No** dedicated domain or geography extractor. Bare `from Germany` can be captured as **host**, not geo. |
| 2 | Which of those are stored in final RQC | `PARTIAL` | `build_resolved_query_contract` `backend/app/chat/resolved_query_builder.py` **122–140**: `entities = _entities_map(query_understanding)` (**163–173**), `time_scope` from `time_window`. RQC schema `backend/app/chat/contracts/resolved_query.py` **61–62**. Session continuity may add `account_type`/`geo` later (O1); T1 parser still has no geo field. |
| 3 | Which fields reach `workflow_spl` / generation | `PARTIAL` | `graph_node_workflow_spl` `backend/app/chat/pipeline.py` **2777–2858** consumes `effective_query` / `request.message`, `query_understanding`, skill, template/use-case, discovery context. It does **not** read `state["resolved_query_contract"]` as a first-class SPL input. Entity filters therefore reach generation only if they remain in the query text or template slots. |
| 4 | Exactly what `spl_source_resolve` does | `EXISTS` (source slots only) | `graph_node_spl_source_resolve` `pipeline.py` **3257–3322** calls `resolve_spl_source_profile` `backend/app/spl/spl_source_resolve.py` **104+**. Fills `<placeholder>` source-profile slots (index/sourcetype) from policy/COE/session/RAG; `del user_query` **114**. Does **not** inject RQC entity/time/geo constraints. Plan 7 A2/A3 ownership unchanged. |
| 5 | Exactly what `spl_postprocessor` does | `EXISTS` (review-only hygiene) | `graph_node_spl_postprocessor` `pipeline.py` **2542–2579** → `finalize_review_only_spl` `backend/app/spl/review_only_spl_postprocessor.py` **1–17, 226–491**. Index resolution, lookback hardening, `sort 0` removal, weekend locale. **Never** authorizes execution; does **not** prove RQC entity constraints survived. A3 still requires this phase on applicable seams. |
| 6 | Where `normalized_spl` is validated | `EXISTS` | `validate_spl` `backend/app/safeguards/spl_validator.py` **63–76**, `_validate_raw_search` **79–142**: commands, index/sourcetype allowlists, `earliest`/`latest` presence, aggregation, result cap, secrets/macros. Gate requires `approved=true` and non-null `normalized_spl` (`mcp_execution_gate.py` **55–76**, `catalogue_execution_eligibility.py` **53–55**). |
| 7 | Whether validation proves mandatory final-RQC constraints survived | `MISSING` | `validate_spl` does not accept or compare an RQC. No check that `source_ip` / account class / geo / `time_scope` appear in `normalized_spl` or have a non-applicability reason. This is the SPL1 gap. |
| 8 | Where Splunk/MCP authorization is enforced | `EXISTS` | `evaluate_mcp_execution` `backend/app/orchestration/mcp_execution_gate.py` **55+**: preconditions, `select_mcp_tool`, data-silence, HIL confirmation (`execution_confirmation.py` **97–118**), RBAC via `session_role_for_mcp_gate`, global/per-server execution flags. Candidate SPL never executed. |
| 9 | Tool-level only vs bound to the final normalized call | `PARTIAL` | Replay fingerprint `build_mcp_execution_fingerprint` `backend/app/chat/hook_replay_contract.py` **116–137** hashes tool, server, `normalized_spl`, intent, earliest/latest, saved-search name — **hook idempotency only** (`mcp_execution_gate.py` **778–786**). P1 baseline recorded AUTH0 **PARTIAL**: a mutated approved `normalized_spl` is not rejected for fingerprint mismatch at the live gate. Not a per-call grant bound to identity + source scope + expiry. AUTH0 owns that binding. |

**SPL1 implication:** pass final-RQC entities into generation and require `normalized_spl` to contain each mandatory constraint or an explicit non-applicability reason. Do not change `spl_source_resolve` into an entity injector.

**AUTH0 implication:** extend the existing MCP/HIL/RBAC gate so a material change to normalized SPL, time/source, tool/connection, identity, or limits invalidates authorization. Do not add an authorization service.

`architecture.md` unmodified. Plan 7 A2/A3 lifecycle owners unchanged.

## Plan 8 X0 — legacy / duplicate planning and execution seam classification

AUDIT_ONLY at Plan 8 X0 (2026-08-16). **No deletion, redirect, or runtime change.**
Verify `rg -n "llm_plan_bridge|evidence_loop|guided_hybrid_refinement|linear_graph_legacy|dispatch_v2|session_spl_refine|_run_legacy_dispatch_fallback" backend/app backend/app/tests` → **402** matching lines.

Normal production authority remains `ResourcePlan + PhaseContract` via the existing Resource Planner hub (`run_chat_via_resource_planner_graph`). No seam below is classified **dead**. None is authorized for X1 retirement.

### Import / call graph

```text
production /chat
  → resource_planner_graph.run_chat_via_resource_planner_graph
      → canonical planning → execute_plan_dispatch          [production]
      → _run_guided_hybrid_dispatch
          → guided_hybrid_refinement.evaluate_guided_refinement  [production]
      → if session SPL refine:
            _run_legacy_dispatch_fallback(session_spl_refine)    [rollback-only]

flag-gated dispatch-v2 (ai_soc_pipeline_dispatch_v2_enabled, repo default false)
  → pipeline.dispatch_v2_route_after_* / projected hook schedule
  → executor.py may label dispatch_authority=pipeline_dispatch_v2
  → fenced: cannot win while ResourcePlan execution is ON (Plan 7 A6)

test-only linear_graph_legacy
  → _compiled_chat_graph_cp (tests only; not /chat)
      → graph_node_evidence_planning
          → evidence_loop HUB (canonical turns fail closed without harness flag)

llm_plan_bridge.propose_validated_llm_plan
  → planner.plan_promotion_merge / resource_plan_shadow / tests
  → not a pipeline symbol on canonical turns (Plan 2 B1 RETIRE)
```

### Classification table

| Seam | Class | Production importers | Notes |
|---|---|---|---|
| `llm_plan_bridge` | **test-only** | none on canonical `/chat`; `plan_promotion_merge.py`, `resource_plan_shadow.py`, tests | Plan 2 B1 RETIRE. `apply_llm_primary_resource_plan` / `run_resource_plan_shadow` are not pipeline symbols (`test_retired_resource_planning_surfaces.py`). Module retained as a validation library. Not dead. |
| `evidence_loop` (HUB / `graph_node_evidence_planning`) | **rollback-only** | `pipeline.py` still defines the fenced node; `linear_graph_legacy.py` wires it | Canonical turns return `canonical_forbids_legacy_evidence_planning` unless `legacy_langgraph_harness`. Helpers (`record_hop`, `MAX_MCP_HOPS`) remain for guided collection / hop bounds. Not dead. |
| `guided_hybrid_refinement` | **production** | `pipeline.py` `_run_guided_hybrid_dispatch` **6063**; `guided_answer_contract.py` | Plan 3 B0 bounded refinement is live, model-free, cap 3. Not a duplicate executor. |
| `linear_graph_legacy` | **test-only** | tests only (`test_evidence_loop_graph.py`, `test_control_plane_trace.py`, `test_recipe_selection_live_wiring.py`) | Harness graph. Production chat uses Resource Planner graph. Not dead. |
| `dispatch_v2` | **rollback-only** | `pipeline.py` route helpers; `contracts/pipeline_dispatch.py`; `executor.py` label | Repo default `ai_soc_pipeline_dispatch_v2_enabled=false`. Plan 7 A6: fenced, not normal authority. Not dead. |
| `session_spl_refine` | **rollback-only** | `pipeline.py` **660–665**, **5942**, **6990** | Seam inventory `imperative:session_spl_refine` = `ROLLBACK_ONLY` (`test_execution_seam_coverage.py`). Enters `_run_legacy_dispatch_fallback`. Target RP graph has no caller. |
| `_run_legacy_dispatch_fallback` | **rollback-only** | `pipeline.py` **5848** via session-SPL-refine and missing-composed-plan rollback | Plan 7 A7 `LEGACY_FALLBACK_ROLLBACK_ONLY_RETAIN_TEMPORARILY`. Own hook loop; skips `spl_postprocessor` unless the rollback path inserts it. Target graph must not enter it. X3 revalidates; do not reopen A7. |

**X1 implication:** no seam is proven dead, and this audit records **no** explicit retirement authorization. X1 must record `NOT_REQUIRED_FOR_CURRENT_SCOPE` and retain all seven seams.

`architecture.md` unmodified.

## Plan 8 G1 — re-audit of canonical phases 0–11 (post-implementation)

Measured against the implemented tree after G0 (`8603519`, 2026-08-16). **No runtime change in this section.** `architecture.md` unmodified. Production GO remains **DEFERRED / NO-GO**. F3 and live MCP remain unproven.

### Role table (production entry / owner / I/O / fallback / tests / residual)

| # | Role | Class | Production entry | Owner | Inputs → outputs | Fallback | Tests | Remaining gap |
|---|---|---|---|---|---|---|---|---|
| 1 | Deterministic authority over LLM | `EXISTS` | `/chat` RP graph | adapter + registries | LLM advisory → deterministic overrides | discard advisory | P1 baseline; Plan 4 D3 | none for Plan 8 |
| 2 | T1–T3 before T4 | `EXISTS` | `understand_query` then U1 gate | query understanding | locked/unresolved maps → `CALL_T4` only | skip T4 | `test_understanding_sufficiency.py` | F3 serving |
| 3 | Final RQC before clarify / owner / plan | `EXISTS` | `build_resolved_query_contract` then R0/R1 | RQC | UNDERSTANDING → final RQC | clarification | `test_final_rqc_precedes_planning.py` | dest-IP/domain/geo extraction still PARTIAL at parser |
| 4 | Primary skill = ownership not veto | `EXISTS` | C0 overlay `required_capabilities` | planner | RQC caps → `needs_spl`/`needs_mcp` | `mcp_not_allowed_by_evidence_plan` | `test_resource_plan_from_final_rqc.py` | live route-level capability enforcement still default OFF (Plan 5 B) |
| 5 | Composable resources | `EXISTS` | `compose_resource_plan` | RP hub | EvidencePlan → ResourcePlan | specialists advisory only | C0 / composer tests | R2 snapshot deferred |
| 6 | Side effects vs reasoning | `EXISTS` | MCP gate only | `evaluate_mcp_execution` | approved `normalized_spl` → mock/live call | HIL / skip | AUTH0 + HIL two-turn | live MCP unproven |
| 7 | InvestigationOutcome before synthesis/actions | `EXISTS` (minimal) | `graph_node_context_finalize` after D0 | `investigation_outcome.py` | EvidenceState/sufficiency/facts → disposition/findings | no LLM mutation | `test_investigation_outcome.py` | Phase 10 actions deferred; not a duplicate of CanonicalPlanningOutcome |
| 8 | Minimal EvidenceState | `EXISTS` (derived) | same finalize node | `minimal_evidence_state.py` | SourceEvidence/RQC/plan/facts/gate/execution → required/obtained/missing/stale/invalidated/blocked | missing items defaulted | `test_minimal_evidence_state.py` | detailed per-step E1 deferred |
| 9 | Evidence reuse / invalidation | `EXISTS` | O1 pins + O1A | session + applicability | prior refs + new RQC → IN_SCOPE/OUT_OF_SCOPE/STALE | do not reuse out-of-scope | `test_session_canonical_continuity.py`, `test_session_evidence_applicability.py` | not a durable evidence DB |
| 10 | ResourcePlan compiler | `EXISTS` | `plan_evidence_from_canonical` | composer + phase merge | plan + PhaseContract → schedule | unsupported → fixed schedule | Plan 7 A3 pins | C1 step-instances deferred |
| 11 | PhaseRegistry/Policy/Contract | `EXISTS` | merge seam | phase modules | registry + policy → immutable contract | flag-off skips execution-contract code on repo default; this host development profile ON | `test_phase_schedule_merge.py` | none |
| 12 | Source resolve vs postprocessor | `EXISTS` (owners unchanged) | `spl_source_resolve` then `spl_postprocessor` | A2/A3 | placeholders → hygiene SPL | HIL on unresolved slots | `test_spl_source_resolve.py`, `test_review_only_spl_postprocessor.py` | dest-IP/domain/geo extraction still parser-PARTIAL |
| 13 | Call-bound authorization | `EXISTS` | pending MCP confirmation | `splunk_call_authorization.py` | fingerprint of SPL/time/source/tool/identity/limits → grant | `exact_call_grant_invalidated`; `update_spl` is a new revalidated call | `test_splunk_call_authorization.py` | live MCP unproven |
| 14 | Trust / prompt boundary | `EXISTS` | T4 + synthesis prompts | `trust_boundary.py` | untrusted body → `BEGIN/END {TRUST_CLASS}` | fail closed on injection | `test_prompt_trust_boundary.py` | none for Plan 8 |
| 15 | T4 circuit / backpressure / human restart | `PARTIAL` | sidecar T4 hop | `sidecar_governance.py` | failures → CLOSED/OPEN/HALF_OPEN | `human_action_required_model_restart`; never auto-restart | `test_t4_circuit_breaker.py` | **F2** `/v1/models` ≠ inference health (REL0 uses operator probe, not solved as serving). **F3** CRITICAL BLOCKER not claimed solved |
| 16 | Degradation signalling (F1) | `MISSING` (approved residual) | DB-loss path | planning degrade | DB down → `canonical_non_planned` still answers | silent | P1 / Plan 7 F1 | **F1** not closed; REL0 was T4 circuit only |
| 17 | Clarification | `EXISTS` | R0 | RQC unresolved | three-uncertainty rule | human review | P1 corpus | none |
| 18 | Action flow / LLM in actions | `PARTIAL` | action lane default-off | InvestigationOutcome + policy | outcome → recommended actions | LLM cannot change eligibility | `test_investigation_outcome.py` | **Architecture Phase 10** deferred |
| 19 | Architecture Phase 10 | `deferred` | n/a | next plan | n/a | preserve compatibility only | n/a | ticket/email/CRM/remediation MCP not in Plan 8 |
| 20 | Advanced execution extensions | `deferred` | n/a | `P8_ADVANCED_EXECUTION_EXTENSION_GATE=NOT_REQUIRED_FOR_CURRENT_SCOPE` | n/a | existing RP hub / E0A / D0 | gate evidence | R2, C1, E0, E1, D1, D2, X1 retained/not required |

### SPL0 Q7 / Q9 update

| SPL0 Q | Plan 8 start | After G0 | Disposition |
|---|---|---|---|
| 7 RQC-constraint survival | `MISSING` | `EXISTS` | `apply_rqc_constraint_preservation` in `graph_node_workflow_spl`; unmapped silent loss fail-closed; governed template without a slot is `non_applicable:no_governed_template_slot` |
| 3 fields reach `workflow_spl` | `PARTIAL` (no RQC read) | `EXISTS` for constraint check | RQC consumed at preservation; generation still uses query/template slots plus RQC bindings |
| 9 call-bound auth | `PARTIAL` | `EXISTS` | AUTH0 exact-call grant on pending confirmation |

### Unexplained MISPLACED / unapproved MISSING

- **MISPLACED:** **0**. No authority sits on the wrong owner relative to `architecture.md`.
- **Unapproved MISSING:** **0**. The only remaining `MISSING` role is **F1 degradation signalling**, explicitly carried as an unaccepted residual (REL0 did not close it). F3 is a serving **blocker**, not a missing role.
- **Approved deferrals:** Architecture Phase 10; R2; C1; E0; E1; D1; D2; X1 (`NOT_REQUIRED_FOR_CURRENT_SCOPE`); MITRE 11-row DRAFT promotion; live MCP/Splunk (`live_mcp_unproven`).

`architecture.md` unmodified. Production GO not claimed.
