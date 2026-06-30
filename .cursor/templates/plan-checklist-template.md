---
name: <plan-slug>
overview: "<one-line objective>"
status: draft | active | done
date: YYYY-MM-DD
canonical_plan: plans/<filename>.md
loop_runner: plans/LOOP_RUNNER_<slug>.md
---

# <Plan title>

## Objective

One paragraph: what "done" means for the whole plan.

## Stop conditions

- All checklist items checked with recorded evidence, **or**
- Same verification gate fails twice on one item, **or**
- Decision needed (tradeoff / ambiguous requirement / COE deferral) — **stop and ask**

## Dependency order

List item IDs in execution order (blocking items first):

`1 → 2 → 3 → …`

## Checklist

Each item must be atomic with an explicit verification method. Do not start implementation until every item has **Verify**.

- [ ] **1** — Example atomic task
  - **Do:** Implement `foo()` in `backend/app/example.py`
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_example.py::test_foo -q`
  - **Depends on:** none
  - **Evidence:** _(fill when done)_

- [ ] **2** — Example dependent task
  - **Do:** Wire `foo()` into pipeline handoff
  - **Verify:** `pytest app/tests/test_pipeline_handoff.py -k foo -q`; trace `pipeline.py` calls `foo` before `bar`
  - **Depends on:** 1
  - **Evidence:** _(fill when done)_

## Verification gaps (flag before coding)

_List any item that still lacks a concrete Verify method._

## Drift log

_Record plan premise changes, redundant items, or scope shifts — user must acknowledge before continuing._
