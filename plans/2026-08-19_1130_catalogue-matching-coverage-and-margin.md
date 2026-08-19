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

- [ ] **3 — Coverage-weighted, specificity-aware scoring**
  - **Do:** replace the additive formula. Weight rarer terms higher (IDF over the
    catalogue), scale by coverage, drop the flat 0.62 floor.
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
