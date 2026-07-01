# Loop runner — Guided Hybrid Investigation Orchestrator

Canonical plan: [`plans/2026-07-01_1545_guided-readonly-mcp-discovery-lane.md`](2026-07-01_1545_guided-readonly-mcp-discovery-lane.md)

- **REV3** = target architecture (§1–§13)
- **REV4 batch 1** = phases P1–P8 (implement now; no LLM, no safe SPL execution, no MCP collection)
- **REV4 batch 2** = LLM propose, evidence collection, safe SPL catalog, docs

---

## How to launch

### Cursor Agent (recommended)

```
loop-asap — execute plans/2026-07-01_1545_guided-readonly-mcp-discovery-lane.md per AGENTS.md — REV4 batch 1 phases P1–P8 only. Start with P1 and stop after each phase with evidence. Do not implement batch 2 deferrals. Apply the final clarifications: P7 gating must be in guided_hybrid path/shared helper, P8 must not execute MCP or safe SPL collection in batch 1, and split P4 if needed.
```

**Pacing:** Implement **P1 only** first; review evidence before allowing P2–P4.

### Codex / Claude Code

```bash
cd /var/www/ai-soc-assistant
.cursor/hooks/audit-plan-discipline.sh plans/2026-07-01_1545_guided-readonly-mcp-discovery-lane.md
```

Prompt:

> Follow REV4 batch 1 (P1–P8) only. Start with P1; stop after each phase with evidence. Handoff fix: guided ResourcePlan behind validated InvestigationPlan. P7: gate SPL preview in hybrid path/shared helper — not legacy rag-only only. P8: no MCP or safe SPL collection execution in batch 1. Split P4 into P4a/P4b/P4c if implementation fails. Flag-off byte-identical.

---

## The task

1. Read canonical plan §14 (REV4 batch 1) + §1 handoff audit context.
2. Run audit script — fix every `GAP:` before P1 code.
3. Execute **P1 → P2 → P3 → P4 → P5 → P6 → P8 → P7** in dependency order. **Stop after each phase** with evidence; do not batch phases without review.
4. **Do not** start batch 2 items.
5. **Stop** when P1–P8 have evidence, flag-off byte-identical, or same gate fails twice.

## Hard rules (batch 1)

- **One flag:** `AI_SOC_GUIDED_HYBRID_INVESTIGATION_ENABLED` only.
- **Flag off:** byte-identical `/chat` for guided sample query.
- **CP off:** feature no-op.
- **Guided only:** do not change `compose_resource_plan` for other skills.
- **Defer** early compose at evidence_planning when guided + flag on.
- **Never** use shadow `resource_decisions` as step authority.
- **Never** widen `mcp_allowed` or `freeform_spl_execution_allowed`.
- **Never** schedule `graph_node_execution` for guided hybrid.
- **P8:** compose + validate planned steps only — **no** MCP discovery or safe SPL catalog hop execution.
- **P7:** SPL preview gate on hybrid path or shared helper — **not** `prepare_rag_only` alone.
- **P4 split:** P4a fields/posture → P4b skip early compose → P4c `compose_guided_resource_plan` if P4 is too large.
- **LLM:** not in batch 1.

## Verification gates (by phase)

| After | Command |
|-------|---------|
| P1 | `pytest app/tests/test_guided_hybrid_trace_baseline.py -q` |
| P2 | `pytest app/tests/test_investigation_plan.py -q` |
| P3 | `pytest app/tests/test_guided_investigation_validator_a.py -q` |
| P4 | `pytest app/tests/test_compose_guided_resource_plan.py -q` |
| P5 | `pytest app/tests/test_guided_capability_validator.py -q` |
| P6 | trace inspection (flag on) — `guided_handoff` segments |
| P8 | `pytest app/tests/test_guided_hybrid_dispatch.py -q` — no collection hops |
| P7 | `pytest app/tests/test_guided_spl_review_gate.py -q` — hybrid path gate |

## Sample probe query

```
How should I investigate unusual outbound traffic from an OT host overnight?
```

**Flag off (P1):** §1.2 unchanged; `prepare_rag_only→rag_early`; no execution; byte-identical.

**Flag on (P8):** hybrid dispatch; validators; **no** collection; `final_route=guided_investigation`.

## Batch 2 deferrals (do not implement now)

- Bounded LLM InvestigationPlan propose
- Safe SPL catalog execution hop
- MCP read-only collection hops
- Refinement, AnswerContract safe-catalog fields, HIL promotion, full docs/governance

## Stop and ask user when

- After **P1** — user review before P2–P4
- COE must sign `guided_safe_spl_catalog.json` (batch 2)
- Second failure on flag-off byte-identity
- Any catalog skill dispatch regression
