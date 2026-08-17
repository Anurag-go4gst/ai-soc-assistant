# LOOP_RUNNER — races-investigation-execution-ux

**Canonical plan:** [`plans/2026-08-17_races-investigation-execution-ux.md`](2026-08-17_races-investigation-execution-ux.md) (rev 2, **active**)

## Start

```text
loop-asap — execute plans/2026-08-17_races-investigation-execution-ux.md
```

Primary worktree: `/var/www/ai-soc-assistant` on `feat/races-investigation-execution-ux`.

Do **not** edit `ChatPanel.tsx` here. Legacy demoMode work is Workstream B in `/var/www/ai-soc-assistant-legacy-ec` after the H1-4 checkpoint commit.

## Agent loop

1. Audit: `.cursor/hooks/audit-plan-discipline.sh plans/2026-08-17_races-investigation-execution-ux.md`
2. Pick first unchecked item whose Depends on are checked. Prefer Workstream A order. H7-* only in the legacy worktree (H7-0 may be created from A after H1-4).
3. Implement **Do** only.
4. Run **Verify** exactly.
5. Check off and fill **Evidence**.
6. Next item. Continue automatically when EC-scoped. STOP on hard STOP list.
7. Re-audit before declaring complete.

## Guards

- `/invariant-check` before commits touching demo/pipeline-adjacent/frontend EC.
- Freeze on A: ChatPanel, routes_chat, pipeline, graph, planner, routing, PlaceholderResponse, SPL validator behavior, MCP gate.
- Tests never send real email.
- Do not reopen `plans/2026-08-16_2310_races-experience-center.md`.

## Stop

`loop-asap stop`, all items evidenced, same Verify fails twice, or a hard STOP in the plan.
