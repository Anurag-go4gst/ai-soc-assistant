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
