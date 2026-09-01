# LOOP_RUNNER — spl-pattern-guided-llm-authoring

**Canonical plan:** [`plans/2026-09-01_1112_spl-pattern-guided-llm-authoring.md`](2026-09-01_1112_spl-pattern-guided-llm-authoring.md)

## Start

```text
loop-asap — execute plans/2026-09-01_1112_spl-pattern-guided-llm-authoring.md
```

## Agent loop

1. Audit: `.cursor/hooks/audit-plan-discipline.sh plans/2026-09-01_1112_spl-pattern-guided-llm-authoring.md` — fix every GAP.
2. Pick first unchecked checklist item in dependency order (`0 → 1 → …`). P1 and P2 pattern work is closed. P3 starts at **9a**. Do not reopen P1/P2.
3. Implement **Do** only for that item.
4. Run **Verify** exactly as written.
5. Check off `- [x]` and fill **Evidence**.
6. Next item. Stop on decision-needed, gate fails twice, P1 live fail, or all items done.

## Guards

- `/invariant-check` before any commit touching SPL/LLM authoring.
- Do not edit `architecture.md`, `pipeline.py`, `spl_validator.py`, `spl/policy.py`.
- Do not start P11 or enable live MCP.
- Do not create a second few-shot repository or a second SPL compiler.

## Stop

- All items `- [x]` with Evidence, or
- Same Verify fails twice, or
- P1/P2/P3/P4 cannot pass within two correction iterations, or
- A decision is needed that the plan does not already settle.
