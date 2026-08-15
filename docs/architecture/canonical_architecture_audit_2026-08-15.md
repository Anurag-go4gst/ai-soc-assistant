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
