# Loop runner — template

Agent-agnostic driver for any plan with a checklist. Copy and fill in `<slug>` / `<plan-path>`.

---

## How to launch

### Cursor Agent

```
loop-asap — execute plans/<your-plan>.md per .cursor/rules/plan-discipline.mdc
```

Or paste this file with paths filled in. Ensure `.cursor/rules/plan-discipline.mdc` is active.

### Codex / Claude Code

```bash
cd /var/www/ai-soc-assistant
# Read AGENTS.md + the canonical plan first
```

Prompt:

> Follow `plans/<your-plan>.md` using plan-discipline: audit checklist with `.cursor/hooks/audit-plan-discipline.sh`, fix gaps, then loop implement→verify→check-off until stop condition.

---

## The task

1. Read `plans/<your-plan>.md` in full. `grep` the repo — do not recreate shipped work.
2. Run `.cursor/hooks/audit-plan-discipline.sh plans/<your-plan>.md` — fix every GAP before coding.
3. Pick the first unchecked checklist item in **dependency order**.
4. **Loop:** implement → verify (item's **Verify** field) → record **Evidence** → check off → next item.
5. **Stop** when all items have evidence, same gate fails twice on one item, or a decision is needed.

## Hard rules

- Do not implement against prose-only plans — materialize checklist first.
- No check-off without evidence (test output, trace, or inspection note).
- Surface drift (wrong premise, redundant item, scope change) before continuing.
- Re-audit every item before declaring the plan complete.
- Obey `AGENTS.md` safety boundaries and verification gates.

## Stop conditions

- All checklist items `[x]` with recorded evidence, **or**
- Same verification fails twice on one item, **or**
- Decision needed — stop and ask the user
