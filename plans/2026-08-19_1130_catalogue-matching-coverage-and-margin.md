---
name: catalogue-matching-coverage-and-margin
overview: "Replace substring-containment binding with coverage/specificity scoring, a margin-based escalation to T4, and negative/co-signal use-case metadata"
status: draft
date: 2026-08-19
canonical_plan: plans/2026-08-19_1130_catalogue-matching-coverage-and-margin.md
loop_runner: plans/LOOP_RUNNER_TEMPLATE.md
---

# Catalogue matching — coverage, margin, and negative metadata

## Objective

T2 use-case binding currently commits on **substring containment with additive
confidence**. One matched term out of a forty-word question binds a use case at
0.91 and closes `spl_allowed` / `mcp_allowed`. Done means: a bind is scored by
how much of the ask it explains, an uncontested weak match escalates instead of
committing, and a use case can express what it must *not* match. Route
correctness is judged by the routing truth set, never by parity or the 105
goldens.

## Measured starting point (2026-08-19, `48fb2e1` + `492157b`)

Observed on the live path, in-container, real DB, host flags:

```
query   : "A critical zero-day affects our internet-facing VPN gateways.
           We have no detection rule or SOAR playbook yet for VPN detection.
           Determine whether we are exposed and what immediate controls we should apply."
bind    : soc_show_sop @ 0.91, matched=['playbook']   (65-use-case catalogue)
result  : knowledge_recall, spl_allowed=False, mcp_allowed=False
visible : "Governed SOP retrieved. SPL and MCP were skipped as requested."
```

Scoring, `app/use_cases/registry.py::match_use_cases`:

```python
matched = [p for p in patterns if p.lower() in normalized]
confidence = min(0.95, 0.62 + 0.05*len(matched) + boosts)
```

Truth set after the negation fix and the 9 new rows: **68/85 route_ok,
18 capability_inconsistent**.

## Approach selection — measured, not chosen by intuition (2026-08-19)

Three candidates were run against the 96-row truth set and the 105 catalogue
questions before picking one. Reproduce with
`scripts/eval_catalogue_bind_experiment.py`.

| approach | false knowledge bind | missed procedure | 105-question binds changed |
|---|---|---|---|
| **A** current: substring + `0.62 + 0.05*n` | **2** | 0 | — (baseline) |
| **B** coverage x IDF specificity + margin | **0** | **0** | **1** |
| **C** repo trigram+token cosine ported from the 105 tier | 0 | 3 (best sweep: 1) | not run |

`false knowledge bind` = the label requires SPL and the matcher bound a
knowledge use case — the failure that produced "Governed SOP retrieved ... as
requested" on a P1 zero-day.

**Chosen: B.** C is rejected on evidence, not preference: swept at
0.10/0.15/0.20/0.25/0.30 it never reaches zero on both axes (best case still
misses a procedure row), because cosine over a use case's whole surface text
discards the precision of the curated `intent_patterns`. Worth recording that
the repo already runs C's *design* — threshold 0.65, margin 0.05, candidate
floor 0.45 — for the 105-question tier in
`app/coverage/semantic_question_index.py`. Reusing that design for the 65-use-case
catalogue was the obvious first hypothesis and the measurement rejected it.

**Threshold has a plateau, so it is not a guess.** Sweeping B's coverage floor:

```
floor   false_knowledge / missed_procedure / 105-binds-changed
0.10          2 / 0 / 1
0.14          1 / 0 / 1
0.18          0 / 0 / 1     <-- plateau starts
0.22          0 / 0 / 1     <-- recommended (middle of plateau)
0.26          0 / 0 / 1
0.30          0 / 1 / 1     <-- starts dropping real procedure asks
```

Recommended floor **0.22**, the middle of a plateau three steps wide, not an
edge value.

**Honest caveat on the margin gate:** margins of 0.00 / 0.06 / 0.12 produce
identical results on this corpus — candidates rarely tie closely enough for it
to fire. The margin is retained as the escalation seam item 4 needs, but it has
**not** yet earned its place on measured evidence and must not be described as
proven.

**One bind changes on the 105** and needs adjudication before item 3 lands:
`"Which users authenticated to VPN after repeated MFA failures"` moves
`auth_failed_login_spike` -> `auth_mfa_failure_spike`. That looks like a
correction rather than a regression, but the 105 are frozen and it is the
owner's call.

## Defect classes (all four are structural, not vocabulary)

1. **No coverage measure.** Match *count* is scored; the fraction of the query
   explained is not. One term in 40 words scores like one in 4.
2. **0.62 floor.** Any single hit is already near-authoritative.
3. **No margin test.** An uncontested weak match is treated as confident. There
   is no "runner-up is close ⇒ ambiguous ⇒ escalate".
4. **Positive-only metadata.** `intent_patterns` + display name + examples. No
   exclusions, no required co-signals, no scope vocabulary. The catalogue cannot
   express "match `playbook`, but not when the user is determining exposure".

Consequence worth stating separately: **T4 semantic understanding only runs when
T1–T3 fail to bind.** A confident misfire suppresses the layer that would catch
it. T4 is enabled on this host and never fired for the query above.

## Stop conditions

- All items checked with recorded evidence, **or**
- The same verification gate fails twice on one item, **or**
- A decision is needed — stop and ask. Known decision points: refreezing the
  protected truth-set baseline (item 6), and any change to the 105 exact-match
  path (out of scope here).

## Dependency order

1 → 2 → 3 → 4 → 5 → 6

## Checklist

- [ ] **1 — Instrument coverage/margin without changing behaviour**
  - **Do:** compute and record, per bind, `coverage_ratio` (matched span ÷ query
    length), `top_score`, `runner_up_score`, `margin`; emit into the existing
    routing trace. No thresholds, no behaviour change.
  - **Verify:** `python3 scripts/eval_routing_truth_set.py --arm deterministic`
    reports **68/85 route_ok, 18 capability_inconsistent** (byte-identical to
    the pre-change run); trace shows the new fields on all 96 rows.
  - **Depends on:** —
  - **Evidence:**

- [ ] **2 — Measure the distribution before choosing thresholds**
  - **Do:** dump coverage/margin for all 96 truth-set rows plus the 105 goldens;
    identify where correct binds and misfires separate.
  - **Verify:** a committed table under `docs/evals/` showing the two populations;
    no threshold may be proposed in item 3 without a row in this table.
  - **Depends on:** 1
  - **Evidence:**

- [ ] **3 — Coverage-weighted, specificity-aware scoring (approach B)**
  - **Do:** replace the additive formula with `coverage x IDF specificity` as
    prototyped in `scripts/eval_catalogue_bind_experiment.py`, coverage floor
    **0.22** (plateau midpoint), drop the flat 0.62 floor. Resolve the
    `auth_mfa_failure_spike` bind change with the owner first.
  - **Verify:** `rt.neg.001` and `rt.verb.001-003` stop binding a knowledge use
    case; `rt.neg.005/006` still bind `soc_show_sop`; truth set shows
    `capability_inconsistent` **strictly below 18** and `route_ok` **not below
    68**; full pytest 0 failures.
  - **Depends on:** 2
  - **Evidence:**

- [ ] **4 — Margin-based escalation instead of committing**
  - **Do:** bind only when `top_score` clears the item-2 coverage floor **and**
    beats the runner-up by the item-2 margin; otherwise emit no bind and let
    T4 / the deterministic floors decide.
  - **Verify:** a query matching two use cases within the margin escalates rather
    than binding; the 105 exact rows are unaffected (`--arm deterministic`
    unchanged on `rt.d1.*`); parity `120 exact` still holds.
  - **Depends on:** 3
  - **Evidence:**

- [ ] **5 — Negative and co-signal metadata on use cases**
  - **Do:** add optional `exclusion_patterns` and `requires_signals` to the use-case
    schema; populate for `soc_show_sop` first (exclude when live-investigation
    intent is present). Schema addition must be backward compatible — absent
    fields behave exactly as today.
  - **Verify:** `soc_show_sop` no longer binds `rt.neg.001`; every use case without
    the new fields produces a byte-identical bind to the pre-change run.
  - **Depends on:** 4
  - **Evidence:**

- [ ] **6 — DECISION: should the new rows gate?**
  - **Do:** `--check` is per-row against `routing_truth_set_baseline_v1.json`, so
    the 9 new rows are measured but **not gating**. Making them gate means
    refreezing that baseline, which is a **protected artifact**
    (`docs/evals/protected_execution_baseline.json`, `--check` 15/15).
  - **Verify:** decision recorded in this file with the owner's words; if refrozen,
    `scripts/freeze_execution_baseline.py --check` passes in the same run.
  - **Depends on:** 5
  - **Evidence:**

## Out of scope

- The T1 exact-105 path and `question_runtime_map_v1.json` (frozen).
- `architecture.md` (frozen, read-only).
- Widening `live_investigation_verbs` / `has_specific_scope` term lists as a
  *fix*. They may become scoring inputs under item 3, but adding terms is the
  per-phrase treadmill this plan exists to end.
- Anything that gives the LLM tool-selection authority. Selection stays
  deterministic.

## Non-goals / invariants to preserve

- Route correctness is measured by the truth set, not by parity or the 105
  goldens (Plan 4).
- `capability_inconsistent` and route correctness stay independent verdicts.
- No new env flag (house policy). This ships on existing seams or not at all.
