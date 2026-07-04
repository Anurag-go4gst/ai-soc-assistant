# LOOP_RUNNER — providers-mcp-connection-hub

**Canonical plan:** [`plans/2026-07-04_2105_providers-mcp-connection-hub.md`](2026-07-04_2105_providers-mcp-connection-hub.md)

## Start

```text
loop-asap — execute plans/2026-07-04_2105_providers-mcp-connection-hub.md
```

## Agent loop

1. Audit: `.cursor/hooks/audit-plan-discipline.sh plans/2026-07-04_2105_providers-mcp-connection-hub.md` — fix every GAP.
2. Pick first unchecked checklist item in dependency order (`1 → 2 → … → 8`).
3. Implement **Do** only for that item.
4. Run **Verify** exactly as written.
5. Check off `- [x]` and fill **Evidence** (command output or observation).
6. Next item. Do not skip. Stop on decision-needed, gate fails twice, or all items done.
7. Re-audit all checkmarks before declaring complete.

## Stop

- Type `loop-asap stop`, or
- All items `- [x]` with Evidence, or
- Same Verify fails twice on one item.
