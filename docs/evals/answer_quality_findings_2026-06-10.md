# Tier-D Answer-Quality Findings — 2026-06-10 (T5.1, E4 escalation)

First run of `scripts/eval_answer_quality.py` over the 17-row sentinel set.
Verdict: `RESULT: FAIL (4/17 rows)` — **one finding class**, 13 rows.

## Finding AQ-001 — `limitations` section enabled with no content

`completeness_sections` fails on 13/17 rows (10 of 12 registry rows +
pg.dns.010, pg.clar.001, pg.unsafe.001): the analyst card enables the
`limitations` render section while the `limitations` list is empty.

**Root cause:** `backend/app/chat/contracts/answer_contract.py:471` sets
`"limitations": not knowledge_profile` — enabled unconditionally for every
non-knowledge answer — while limitations *content* is populated only from
`evidence_plan.limitations` or contract limitations
(`analyst_response_builder.py:245-250`), which today fills mainly for
curated/enriched use cases (q0.q049 PowerShell passes; most rows don't).

**Why not fixed here:** T5.1 is eval infrastructure. Making the flag
content-driven (or filling `_default_limitations` for all profiles) is
behavior work that changes the analyst card and requires a sentinel baseline
re-freeze under the additive-diff review rule. Per plan T5.1 pass criterion:
"if any row fails: record, escalate E4, do not weaken the check."

**Resolution (Anurag, 2026-06-10): option 1 — content-driven flag.** Landed in
`985f75e` (`render_sections.limitations` enabled only when deterministic
limitation text exists; sentinel baseline re-frozen to drop the empty
sections). `eval_answer_quality.py` is now wired into the governance
regression. Status: **RESOLVED**.

Original options considered:
1. Make `render_sections.limitations` content-driven (`bool(limitations)`) ✅
2. Populate default limitations for all non-knowledge profiles
3. Accept empty-limitations sections as design and scope the check accordingly

## Check-calibration fixes applied during this run (not weakenings)

- `P1–P4` tokens inside `recommended_actions`/`investigation_steps` are
  action-priority prefixes (EC calibration), not severity claims; severity
  grounding scans severity-bearing prose fields only.
- Non-execution honesty disclosure is owed only when the answer carries an
  SPL artifact or an execution was attempted; `draft_status` and
  `review_notice` count as disclosure surfaces.
- `review_notice` backs the `analyst_action_guidance` section on refusal/HIL
  answers.
- Compromise-claim negation must appear in the same field as the claim.

Per-row results: regenerate locally with
`PYTHONPATH=backend:. python3 scripts/eval_answer_quality.py --json docs/evals/out/answer_quality_sentinel.json`
(`docs/evals/out/` is gitignored by design).
