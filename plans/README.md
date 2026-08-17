# Plans index

Canonical location for all implementation plans. **Always** save new plans here (not only under `.cursor/plans/`).

## Naming

```
plans/YYYY-MM-DD_HHMM_<slug>.md
```

Examples: `2026-07-04_1610_danger-tiered-mcp-command-intent.md`, `2026-07-04_0428_intent-advisor-value-o5c-live-scorecard.md`.

Frontmatter must include `canonical_plan: plans/<filename>.md` and a checklist with **Do / Verify / Depends on / Evidence** per [`.cursor/templates/plan-checklist-template.md`](../.cursor/templates/plan-checklist-template.md).

If Cursor also writes a plan under `.cursor/plans/` or `/root/.cursor/plans/`, **copy or promote it into `plans/` immediately** so agents and humans can find it. Shared truth is `plans/`; Cursor-local copies are optional mirrors only.

## Active work

| Plan | Status |
|------|--------|
| [`2026-08-17_races-investigation-execution-ux.md`](2026-08-17_races-investigation-execution-ux.md) | **Active (rev 2).** Shared EC execution-progress shell, S1–S7 operational completeness, allowlisted real outbound EC email, then legacy ChatPanel `demoMode` convergence in a separate worktree. Production `/chat` live semantics frozen. Branch: `feat/races-investigation-execution-ux`. |
| [`2026-08-16_2310_races-experience-center.md`](2026-08-16_2310_races-experience-center.md) | **Done (34/34) — merged PR [#143](https://github.com/Anurag-go4gst/ai-soc-assistant/pull/143) @ `d4f9210`.** Isolated Experience Center flagships + Lab. Do not reopen. Follow-on UX is the 2026-08-17 plan. |
| [`2026-08-15_0602_canonical-architecture-authority-convergence.md`](2026-08-15_0602_canonical-architecture-authority-convergence.md) | **Done (34/34) — Plan 8, PR pending user merge.** Frozen [`architecture.md`](../architecture.md) unmodified. Final RQC, ResourcePlan+PhaseContract, minimal EvidenceState, InvestigationOutcome, exact-call authorization, trust boundaries, T4 circuit. Production GO **deferred**. F3 and live MCP unproven. Advanced extensions `NOT_REQUIRED_FOR_CURRENT_SCOPE`. |
| [`2026-08-14_1130_resource-plan-authority-and-t4-integration.md`](2026-08-14_1130_resource-plan-authority-and-t4-integration.md) | **Done (25/25) — Plan 7, merged.** `ResourcePlan + PhaseContract` sole normal authority; dispatch-v2 fenced; A7 rollback-only fallback retained temporarily. `PRODUCTION_GO_LIVE=DEFERRED / NO-GO` (F3). |
| [`2026-08-13_1440_production-activation-t4-serving-and-governance-readiness.md`](2026-08-13_1440_production-activation-t4-serving-and-governance-readiness.md) | **Done (37/37) — Plan 6, merged PR #132.** Outcome **`P6_PRODUCTION_GO_LIVE = DEFER`**. Historical while authority was still dispatch-v2. MCP scope **`live_mcp_unproven`**. Report: [`docs/evals/plan6_activation_and_t4_report.md`](../docs/evals/plan6_activation_and_t4_report.md). |
| [`2026-08-12_1230_production-readiness-understanding-phase-contract.md`](2026-08-12_1230_production-readiness-understanding-phase-contract.md) | **Done (28/28, 2026-08-13) — merged PR #131 @ `3d22260`, the current authoritative baseline.** Plan 5 on pre-merge baseline `2f678b9`. **A** runtime-map builder byte-idempotent; MITRE containment preserved; protected manifest **15/15**; 11-row DRAFT promotion deferred. **B** `ResolvedQueryContract`; T4 semantic hop and live route-level capability enforcement **default OFF**; B5: required caps are satisfied by the complete governed schedule (`cisco.ot.029`). **C** `PhaseRegistry` + `PhasePolicy` + `PhaseContract` + merge seam; execution flag stays false; no seam adopted; fallback not retired. **D0/D1** residual 25 rows L4=L5 **10/15/0**; `RATIFIED_FOR_MEASURED_ROWS` + `DEFERRED_T4_SEMANTIC_SERVING_LIMIT`. Closure: governance PASS ×2, pytest `5247 passed`, parity `120 exact`, Cisco 50/0/0, probes 10/10, sentinel 17/17, path 105/105, manifest 15/15, invariants 7/7. Report: [`docs/evals/plan5_architecture_and_routing_report.md`](../docs/evals/plan5_architecture_and_routing_report.md). |
| [`2026-08-11_1834_routing-evaluation-and-authority-corrections.md`](2026-08-11_1834_routing-evaluation-and-authority-corrections.md) | **Done (19/19, 2026-08-12) — merged PR #130 @ `2f678b9`, the pre-Plan-5 authoritative baseline.** Closure gates: governance regression PASS, backend `5119 passed / 0 failed`, parity `120 exact`, Cisco 50/50, harness 6/6, probes 10/10, out-of-set PASS, truth-set `--check` 0 regressions, manifest 14/14, invariants 7/7. — Plan 4. Built the independent routing truth set (87 rows, blind-labelled; 20/20 inter-labeller agreement on both gating axes) because the repo had no instrument that could tell a correct route from an incorrect one — the 105 goldens are exact-match, circular, and matched production routing on 1/105. **D3** restored deterministic finality over the LLM advisory (capability downgrades 5→0). **R2.1** corrected three pattern→skill classes (`d1` 0/8 → 8/8). **D2's 39-row premise disproved** — a 3-row defect, unfixed, no safe deterministic discriminator. Route-correct **56/77 → 64/76**; live **51 → 59/76**. `UNDERSTANDING_ROUTER_ON_LOW_CONFIDENCE` **retired as a measured no-op**. Plan 5 superseded the open gaps (runtime-map idempotency, decontaminated understanding, measured ownership ratification, paraphrase residue reclassified as T4 serving/latency). Report: [`docs/evals/routing_evaluation_report_v1.md`](../docs/evals/routing_evaluation_report_v1.md) |
| [`2026-08-11_0915_execution-driven-adoption-and-guided-refinement.md`](2026-08-11_0915_execution-driven-adoption-and-guided-refinement.md) | **Done (9/9, 2026-08-11)** — Plan 3. H0 degrade fix; A0 scheduling authority decided (`PHASE_POLICY_PLUS_RESOURCE_PLAN_SCHEDULING`, not yet built); A1 seam inventory + structural pins, 0 adopted; B0 bounded guided refinement live; B1 flag OFF/ON neutral, default false; B2 fail-closed capability compatibility. Deferred/unapproved: `UNDERSTANDING_ROUTER_ON_LOW_CONFIDENCE`. |
| [`2026-08-10_1103_architecture-resource-plan-execution-and-adaptive-planning.md`](2026-08-10_1103_architecture-resource-plan-execution-and-adaptive-planning.md) | **Done (27/27, `ba9169e`)** — Plan 2 closed 2026-08-11. B1 = `RETIRE` (three LLM planning rails retired; deterministic guided dispatch, four advisory specialists and live pre-SPL discovery kept). C0 = `EXECUTION-DRIVEN` behind `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` (**default false**; flag-off runs zero execution-contract code). Topology is runtime-derived, `route_setup` removed, decision-record I/O corrected. Closure: governance PASS, backend `4978 passed` twice, parity `120 exact`, probes 10/10 + 11/11, manifest 13/13. |
| [`2026-08-10_0555_architecture-audit-query-understanding-and-plan-creation.md`](2026-08-10_0555_architecture-audit-query-understanding-and-plan-creation.md) | **Audit (read-only)** — query intake → tier assignment → T4 planning → node-to-node coupling. Its `## Post-G1 disposition` section is the only authority on open status and is the source for Plan 2. |
| [`2026-08-08_1824_architecture-review-corrective-actions.md`](2026-08-08_1824_architecture-review-corrective-actions.md) | **Done** — 16/16, final commit `e5c1937`. Tier authority, reference qualification, specialist-report fan-in bound, and all four permanent specialists with deterministic MCP/SPL posture reports. Closed; not reopened by Plan 2. |
| [`2026-07-28_1610_canonical-outcome-invariant-hardening.md`](2026-07-28_1610_canonical-outcome-invariant-hardening.md) | **Done** — Workstreams **A+B** merged @ `7ce1474` (PR #112). Gap matrix: [`docs/evals/canonical_cutover_gap_reconciliation.md`](../docs/evals/canonical_cutover_gap_reconciliation.md). |
| [`2026-07-28_1630_live-synthesis-performance-baseline-and-slo.md`](2026-07-28_1630_live-synthesis-performance-baseline-and-slo.md) | **Phase 1 deployed** — Workstream **E** instrumentation @ `6a7fe54` (PR #116). Live baseline harness wiring + SLO deferred. |
| [`2026-07-28_1630_per-step-dispatch-idempotency-and-uncertain-execution-safety.md`](2026-07-28_1630_per-step-dispatch-idempotency-and-uncertain-execution-safety.md) | **Done** — P0 side-effecting MCP/guided execute idempotency @ `42bc899` (PR #115). P1/P2 deferred. |
| [`2026-07-24_2310_guided-detail-tools-consumable-handoff.md`](2026-07-24_2310_guided-detail-tools-consumable-handoff.md) | **Done (rev 17)** — Guided detail tools / canonical planning architecture. Checklist **41/41**. Gate 1, dual-runtime parity **120 exact / 0 approved / 0 critical**, Nginx smoke **6/6** (`0ec5322`), full pytest + governance green. Completion report: [`docs/evals/canonical_cutover_completion_report.md`](../docs/evals/canonical_cutover_completion_report.md). Loop runner retained for history: [`LOOP_RUNNER_guided-detail-tools-consumable-handoff.md`](LOOP_RUNNER_guided-detail-tools-consumable-handoff.md) |
| [`2026-07-23_1315_resource-planner-north-star-cutover.md`](2026-07-23_1315_resource-planner-north-star-cutover.md) | **Done** (`feat/resource-planner-north-star`) — RP graph default production spine; imperative rollback flag-off only; linear LangGraph retired from `api`+`graph` (`linear_graph_legacy` test harness); item **12** complete (12a–12d); governance regression PASS 2026-07-24 |
| [`2026-07-23_1305_ideal-langgraph-resource-planner.md`](2026-07-23_1305_ideal-langgraph-resource-planner.md) | **Done** — hierarchical RP + specialists; `/chat` wired to RP graph when `LANGGRAPH_ORCHESTRATION_ENABLED=true`; imperative default preserved |
| [`2026-07-06_0337_atlas-casestudies-mitigations-enrichment.md`](2026-07-06_0337_atlas-casestudies-mitigations-enrichment.md) | **Draft** — 22 items, 4 phases: A structured case-studies/mitigations in reference_registry (zero today, fixed to cover both resolve_ids and search_domain paths after review), B RAG narrative depth, C real MITRE ATT&CK-reference crosswalk (34/170 techniques) surfaced via grounding_assembler + wired into the actual analyst-visible surface (skill_contribution.py), D remediation-visibility-only text (execution deferred to a separate follow-up plan); reference_taxonomy stays claim-restricted by design, pinned by test |
| [`2026-07-04_1736_intent-mcp-tool-routing-hardening.md`](2026-07-04_1736_intent-mcp-tool-routing-hardening.md) | **Done** — 23/23 items; tool routing + observer + reference-knowledge path; suite 4067 green, governance regression PASS |
| [`2026-07-04_2105_providers-mcp-connection-hub.md`](2026-07-04_2105_providers-mcp-connection-hub.md) | **Done** — Providers Splunk save + execution switch; MCP tab other MCPs; B1–B9 review fixes |
| [`2026-07-04_1730_hybrid-intent-deterministic-llm-coordination.md`](2026-07-04_1730_hybrid-intent-deterministic-llm-coordination.md) | **Done** — hybrid advisory OOR-only; command modes excluded; governance green |
| [`2026-07-04_1610_danger-tiered-mcp-command-intent.md`](2026-07-04_1610_danger-tiered-mcp-command-intent.md) | **Done** — OOR command modes on canonical `spl_and_run` spine (not guided); postprocessor + source_resolve; read-only auto; SPL HIL; governance regression green after `_resolve_path_type` command-signal fix |
| [`2026-07-04_0428_intent-advisor-value-o5c-live-scorecard.md`](2026-07-04_0428_intent-advisor-value-o5c-live-scorecard.md) | **Done** — consumer-gated intent advisor, O5c live trigger, live scorecard |
| [`2026-07-02_1327_dynamic-resource-planning-out-of-catalogue.md`](2026-07-02_1327_dynamic-resource-planning-out-of-catalogue.md) | **Done** — LLM-primary planner, all-tier MCP eligibility, CanonicalFacts, action lane |

## Always kept

- [`AI_SOC_MASTER_PLAN.md`](AI_SOC_MASTER_PLAN.md) — master roadmap and stage-level architecture history.
- [`README.md`](README.md) — this index.

## Operational references

- [`AGENTS.md`](../AGENTS.md) — repository operating rules, plan discipline, verification gates.
- [`CLAUDE.md`](../CLAUDE.md) — project context, stack, and deployment notes.
- [`docs/coe/COE_ROLLOUT_CONFIGURATION.md`](../docs/coe/COE_ROLLOUT_CONFIGURATION.md) — COE rollout profile and smoke checklist.
- [`docs/coe/COE_PRODUCTION_READINESS_RUNBOOK.md`](../docs/coe/COE_PRODUCTION_READINESS_RUNBOOK.md) — executable COE qualification, rollback, GO matrix.

## Execution

```bash
.cursor/hooks/audit-plan-discipline.sh plans/<file>.md
# then:
# loop-asap — execute plans/<file>.md
```
