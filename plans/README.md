# Plans index

Implementation specs live here (versioned in git). **Agent rules** live in [`AGENTS.md`](../AGENTS.md) — read that first, then the active plan for your task.

## Active work (check before coding)

| Track | Plan | Status |
|-------|------|--------|
| Intent cascade | [`2026-06-17_1730_intent-node-cascade-hardening.md`](2026-06-17_1730_intent-node-cascade-hardening.md) | **Done** (Batch 0–0.2) |
| Cisco Environment KB + 50-Q catalogue | `.cursor/plans/environment_kb_cisco_catalogue_1eddd12f.plan.md` (local) — copy to `plans/` when Batch 1 starts | **Next** — read Review Addendum §A–D before implementation |
| Final resolution (routing + answer quality) | `plans/` + branch `cp-final-resolution-answer-quality` | **Done** — focused 20-probe 100/100 mean (`fdc8fac`) |
| Cross-stream FinalEvidenceGate | [`2026-06-25_final-evidence-gate-cross-stream.md`](2026-06-25_final-evidence-gate-cross-stream.md) | **Done** — gate computed in `graph_node_context_finalize()`, not as a new router edge |
| SPL query fidelity | [`2026-06-25_spl-query-fidelity-completion.md`](2026-06-25_spl-query-fidelity-completion.md) | **Done** — user-constraint bindings, table-driven render, draft source-profile auto-fill |
| Full canonical handoff T0/T1/T2 + MCP seam | [`2026-06-26_full-canonical-handoff-t0-t1-t2-mcp.md`](2026-06-26_full-canonical-handoff-t0-t1-t2-mcp.md) | **Done** — shipped on the canonical `/chat` graph; persistent promotion writes and row-authority report artifact refresh remain deferred |
| Master roadmap | [`AI_SOC_MASTER_PLAN.md`](AI_SOC_MASTER_PLAN.md) | Active |

## Canonical references

| Doc | Use when |
|-----|----------|
| [`AGENTS.md`](../AGENTS.md) | Safety, execution playbook, verification (all agents) |
| [`CLAUDE.md`](../CLAUDE.md) | Claude Code entry + stack/gotchas |
| [`docs/evals/regression_baseline.md`](../docs/evals/regression_baseline.md) | Expected green counts |
| [`plans/AI_SOC_MASTER_PLAN.md`](AI_SOC_MASTER_PLAN.md) | Long-range tracks A–D |

## Before claiming a plan todo is pending

1. `grep` / read tests for existing implementation.
2. Check plan **Review Addendum** or repo-state tables (plans often lag the tree).
3. Extend existing modules; do not recreate loaders, maps, or test files that already exist.
