# LOOP_RUNNER — spl-authoring-fidelity

**Canonical plan:** [`plans/2026-08-31_1230_spl-authoring-fidelity.md`](2026-08-31_1230_spl-authoring-fidelity.md)

## Start

```text
loop-asap — execute plans/2026-08-31_1230_spl-authoring-fidelity.md
```

## Agent loop

1. Audit: `.cursor/hooks/audit-plan-discipline.sh plans/2026-08-31_1230_spl-authoring-fidelity.md` — fix every GAP.
2. Pick first unchecked checklist item in dependency order (`0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10`).
3. Implement **Do** only for that item.
4. Run **Verify** exactly as written.
5. Check off `- [x]` and fill **Evidence**.
6. Next item. Stop on decision-needed, gate fails twice, or all items done.
7. Re-audit all checkmarks before declaring complete.

## Guards

- `/invariant-check` before any commit touching SPL/LLM authoring.
- Do not edit `architecture.md`, `pipeline.py`, `spl_validator.py`, `spl/policy.py`.
- Do not start P11 or enable live MCP.

## Stop

- All items `- [x]` with Evidence, or
- Same Verify fails twice, or
- A decision is needed that the plan does not already settle.
