# LOOP_RUNNER — atlas-casestudies-mitigations-enrichment

**Canonical plan:** [`plans/2026-07-06_0337_atlas-casestudies-mitigations-enrichment.md`](2026-07-06_0337_atlas-casestudies-mitigations-enrichment.md)

## Start

```text
loop-asap — execute plans/2026-07-06_0337_atlas-casestudies-mitigations-enrichment.md
```

## Agent loop

1. Audit: `.cursor/hooks/audit-plan-discipline.sh plans/2026-07-06_0337_atlas-casestudies-mitigations-enrichment.md` — fix every GAP.
2. Pick first unchecked checklist item in dependency order (see the plan's "Dependency order" section — not strictly 1→22, several items run in parallel groups).
3. Implement **Do** only for that item.
4. Run **Verify** exactly as written.
5. Check off `- [x]` and fill **Evidence** (command output or observation).
6. Next item. Do not skip. Stop on decision-needed, gate fails twice, or all items done.
7. Re-audit all checkmarks before declaring complete.

## Known priority order (from the plan's Drift log)

Item 6 (the `search_domain` fallback fix) is highest priority — it's the
only code path the live captured probe in
`docs/evals/reference_knowledge_ask_chat_2026-07-05.txt` actually exercises.
Verify it against that exact captured query, not just synthetic test ids.
