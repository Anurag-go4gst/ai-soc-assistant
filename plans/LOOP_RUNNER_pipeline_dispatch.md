# Loop runner — Conditional Pipeline Canonical Dispatch

Agent-agnostic driver for `plans/2026-06-29_conditional-pipeline-canonical-dispatch.md`.
Use as the prompt for Codex CLI, Cursor Agent, or any autonomous coder.

---

## How to launch

### Codex CLI
```bash
cd /var/www/ai-soc-assistant
git checkout feat/pipeline-dispatch-v2   # or your branch
codex "$(cat plans/LOOP_RUNNER_pipeline_dispatch.md)"
```
Codex also auto-loads root `AGENTS.md` (canonical repo rules) — both apply.
Re-run the same command (or type `continue`) after each phase; Codex has no cross-turn scheduler.

### Cursor Agent
Open Agent mode, ensure `.cursor/rules/pipeline-dispatch-loop.mdc` is active, then paste:
`Follow plans/LOOP_RUNNER_pipeline_dispatch.md. Begin Phase 0.`

### Claude Code
`/loop work plans/2026-06-29_conditional-pipeline-canonical-dispatch.md per its Autonomous loop protocol; one phase per iteration; stop on all-done, gate-fails-twice, or decision-needed.`

---

## The task

Read `plans/2026-06-29_conditional-pipeline-canonical-dispatch.md` in full, then implement it one phase at a time.

**Phase order:** `0 → 0.5 → 1A → 2A → 3 → 4 → 2B → 2C → 5 → 6 → 7 → 8`

**Each iteration:**
1. Re-read the plan. Pick the first phase not yet committed (track via the plan `todos` frontmatter `status`).
2. Implement ONLY that phase. No scope bleed.
3. Run the plan's **Validation gates**.
4. Green → one scoped commit + flip todo `status: done` in plan frontmatter + update the CLAUDE.md plans table.
5. Red → fix within phase scope. Blocked / ambiguous / decision needed → STOP and report.
6. **STOP and report after each phase** before the next.

## Hard rules
- `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` code-default stays `false` until Phase 8 green (105/50 governance byte-identity). Operator `.env` may set `true` for probes — never commit `.env`.
- One commit per phase. Never combine phases.
- Stay on branch `feat/pipeline-dispatch-v2`.
- Keep `AI_SOC_TESTS_ALLOW_LIVE_LLM` unset.
- Targeted pytest per phase; full `./scripts/run_stage3_governance_regression.sh` only on Phase 8 or any phase touching a flag-off path.
- Obey the plan's **Anti-patterns to forbid** checklist as a pre-commit gate.

## Stop conditions
All todos `done`, OR a gate fails twice on the same phase, OR a decision is required.
