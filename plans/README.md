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
| [`2026-07-28_1610_canonical-outcome-invariant-hardening.md`](2026-07-28_1610_canonical-outcome-invariant-hardening.md) | **Done** — Workstreams **A+B** complete. Loop-asap closed 2026-07-28 (1/5 follow-ups). Implementation in `.worktree-canonical-outcome-invariant` @ `a6c8d28` (not merged to main). Gap matrix: [`docs/evals/canonical_cutover_gap_reconciliation.md`](../docs/evals/canonical_cutover_gap_reconciliation.md). |
| [`2026-07-28_1630_per-step-dispatch-idempotency-and-uncertain-execution-safety.md`](2026-07-28_1630_per-step-dispatch-idempotency-and-uncertain-execution-safety.md) | **Proposed** — Workstream **D**: hook-level SPL/MCP idempotency; typed replay payloads; leases; `REQUIRES_RECONCILIATION`. After A. |
| [`2026-07-28_1630_live-synthesis-performance-baseline-and-slo.md`](2026-07-28_1630_live-synthesis-performance-baseline-and-slo.md) | **Proposed** — Workstream **E**: cold/warm baseline before SLO; probes outside CI. Independent of A. |
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

## Execution

```bash
.cursor/hooks/audit-plan-discipline.sh plans/<file>.md
# then:
# loop-asap — execute plans/<file>.md
```
