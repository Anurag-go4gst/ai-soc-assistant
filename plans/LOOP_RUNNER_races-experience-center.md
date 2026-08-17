# LOOP_RUNNER — races-experience-center

**Canonical plan:** [`plans/2026-08-16_2310_races-experience-center.md`](2026-08-16_2310_races-experience-center.md)

## Start

```text
loop-asap — execute plans/2026-08-16_2310_races-experience-center.md
```

> **Cursor only.** `loop-asap` is armed by `.cursor/hooks/before-submit-plan-discipline-arm.sh` and
> continued by `.cursor/hooks/stop-loop-asap-handoff.sh` (`loop_limit: 5`). **Claude Code does not
> fire these hooks** — run the seven steps manually and call `audit-plan-discipline.sh` by hand.

## Agent loop

1. Audit: `.cursor/hooks/audit-plan-discipline.sh plans/2026-08-16_2310_races-experience-center.md` — fix every GAP.
2. Pick the first unchecked checklist item **in the dependency order below**, not document-section order.
3. Implement **Do** only for that item.
4. Run **Verify** exactly as written.
5. Check off `- [x]` and fill **Evidence** (command output or observation).
6. Next item. Do not skip. Stop on a named STOP gate, gate fails twice, or all items done.
7. Re-audit all checkmarks before declaring complete.

## Dependency order

```text
L0 → A1 A2 A3 A4 A5 A6 A8 → A7 → L-A
  → B1 → B2 B3 B4 → B5 → L-B
  → C1 → C2 C3
  → D1 D2 D3
  → E1 E2 E3 E4
  → F1 → F2 F3
  → G1 G2 G3 G4 → G5
```

Preferred single-agent walk:

`L0, A1, A2, A3, A4, A5, A6, A8, A7, L-A, B1, B2, B3, B4, B5, L-B, C1, C2, C3, D1, D2, D3, E1, E2, E3, E4, F1, F2, F3, G1, G2, G3, G4, G5`

First item: **L0** (live-path freeze). Do not start A1 until L0 is checked with Evidence.
After A: **STOP at L-A**. Do not start B/C until L-A Evidence includes live-path pytest green and `/invariant-check` PASS.

## Guards (run before checking off any item that touched runtime code)

- `/invariant-check` — 7 groups. Required after A, B, F, G and after any item that touched `trace_panels.py`, `scenarios.py`, or `/demo` routes.
- **Live-path slice** (must stay green; this is the non-impact proof):

```bash
cd backend && PYTHONPATH=../backend:.. python3 -m pytest \
  app/tests/test_live_path_untouched_by_ec.py \
  app/tests/test_live_chat_ec_parity.py \
  app/tests/test_canonical_architecture_authority_baseline.py \
  app/tests/test_mcp_execution_gate.py \
  app/tests/test_governance_trace_chat_stage3m_ui.py -q
```

`test_live_chat_ec_parity.py::test_live_chat_ec_parity_off_uses_pipeline` is the live `/chat` pin (`demo_mode is False`).

- Freeze files must remain unmodified (`git diff --name-only` empty):
  `routes_chat.py`, `routes_chat_stream.py`, `chat/pipeline.py`, `graph/`, `planner/`, `routing/`,
  `schemas/responses.py`, `routes_actions.py`, `mcp_execution_gate.py`, `spl_validator.py`,
  `frontend/src/components/ChatPanel.tsx`.

- Do **not** change `run_demo_scenario()` so `PlaceholderResponse(**payload)` fails.
- Do **not** enable `AI_SOC_LIVE_CHAT_EC_PARITY_ENABLED`.
- Do **not** modify `architecture.md`.
- Do **not** modify `ChatPanel.tsx`.
- No new env flags.
- **Do not start B1 (or C) until L-A Evidence records invariant-check PASS** plus live-path pytest green.

## Hard loop rules (RACES-specific)

1. **Evolve, do not rebuild.** Keep `_run_demo_scenario_legacy` unless a measured gap requires an EC-only extension.
2. **EC envelope is `/demo`-only.** `ExperienceCenterResponse` must not appear in `routes_chat.py` or `pipeline.py`.
3. **A4 scope.** Only `_generic_experience_center_panels`. Live `build_governance_trace` in `pipeline.py` omits `scenario_id` and must stay that way.
4. **F2 ChatPanel freeze.** Do not edit `ChatPanel.tsx`. Existing picker/intercept stays. Flagships are `/scenarios` only. `git diff -- frontend/src/components/ChatPanel.tsx` empty for the whole plan.
5. **Phase 10 SUCCESS is EC-simulated.** Never call `/api/actions`. Never import `ProposedActionsPanel` from `frontend/src/components/ec/`.
6. **S1 30+30 and S5 14→15** are `ec_scenario_policy`, not production policy. Real `validate_spl` is read-only; if it rejects, fix the fixture SPL.

## Commit / PR / merge / build (summary)

Canonical detail: [`plans/2026-08-16_2310_races-experience-center.md`](2026-08-16_2310_races-experience-center.md) § Commit / PR / merge / build.

- Branch: `feat/races-experience-center`. Never commit on `master`.
- Commit after each **batch** whose Verify passed (`races(<item>): …`). `/invariant-check` 7/7 before runtime commits.
- Draft PR after L-A. Ready after G4. **Merge (`gh pr merge --merge`) only if the user explicitly asks.**
- Build: `cd frontend && npm run build` after B5 / F / G2. Live-path pytest slice before every non-docs commit.
- Never commit freeze files, `architecture.md`, `.env`, or ChatPanel.tsx.

## Stop

- Type `loop-asap stop`, or
- All items `- [x]` with Evidence, or
- Same Verify fails twice on one item, or
- A decision is needed that the plan does not already settle (especially any live-path file edit).

## Evidence rules

- Evidence is **observed output**, not intent. Paste the command result or name the artifact.
- A failing Verify is recorded as failing. Never check an item off on a partial pass.
- Baselines and fixtures are changed only when a contract makes the old value wrong, and the
  completion report must name that contract.
- After L-A, L-B, and G4, Evidence must include the live-path pytest line count and `git diff --name-only` of freeze files.
- After a commit batch: `git show --stat -1` in Evidence. After G5: PR URL if opened; merge SHA only if the user asked to merge.
