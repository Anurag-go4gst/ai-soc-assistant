# Live `/chat` does not reach the Experience Center answer shape

Trace `fe4e3657-7ce5-4b3e-94db-5fb6a976ce52`, EC scenario **S4**.

## What the trace shows

Question (the S4 opener, `backend/app/demo/fixtures/s4/pack.py::S4_QUERY`):

> A critical zero-day affects our internet-facing VPN gateways. We have no
> detection rule or SOAR playbook yet for VPN detection. Determine whether we are
> exposed and what immediate controls we should apply.

Live answer:

> Investigation planning is complete. Provide source profile details or run a
> review-only search when logs are required; no MCP execution was performed.

With `llm_call_count: 0`, `analyst_summary: null`, `investigation_planning_trace:
null`, `investigation_outcome: null`, `proposed_actions: null`. No plan, no
findings, no remediation proposal, and no model call at all.

## Why

The chain is deterministic and each link is visible in the trace.

1. `extract_query_signals` returns exactly one true signal for this question:
   `security_log_investigation`. In particular `soc_actionable_hunt` is **false**.
2. `soc_actionable_hunt` requires `_has_detection_verb(...)` AND
   `_has_security_telemetry_subject(...)`. The subject fires (`vpn`, `detection`).
   The verb does not: `_DETECTION_VERB_RE`
   (`backend/app/chat/query_signals.py`) covers *retrieval* verbs — show, list,
   identify, detect, review, correlate, check, "are there" — and does not cover
   **determine**, assess, evaluate, investigate, "are we exposed", "do we have".
3. With `soc_actionable_hunt` false, `classify_intent` skips its
   `guided_investigation` rescue branch and falls to the terminal default:
   `intent_family="clarification_required"`, reason *"Insufficient deterministic
   intent signals"*.
4. `evidence_planner.py` then takes
   `if intent.requires_clarification or family == "clarification_required"` and
   returns an EvidencePlan with `needs_rag=False, needs_spl=False, needs_mcp=False,
   needs_mitre=False`, `answer_mode="clarification"`.

Every stage is switched off by a single missing verb. The code comment on
`soc_actionable_hunt` says the floor exists so SOC-shaped actionable hunts "land
on the guided floor instead of a hollow clarification dump" — this is precisely
that dump, reached because the verb class is too narrow.

**This is not caused by MCP being unavailable.** No MCP call was ever planned.

## The machinery already works — proof

The new eval includes `AS.P1`, which is `AS.S4` with one word changed:

| Row | Leading verb | Route | Plan | Findings | Remediation | Shape |
|---|---|---|---|---|---|---|
| `AS.S4` | **Determine** whether we are exposed… | `knowledge_recall` | — | — | — | 0.33 |
| `AS.P1` | **Assess** whether … are exposed… | `guided_investigation` | `validated_investigation_plan` | `investigation_outcome` | `remediation_approval` | **1.00 PASS** |

Same question, same absent MCP, same everything else. The full
plan → findings → remediation answer is already reachable; the answer shape
currently depends on which synonym the analyst typed.

## A naive fix makes it worse — measured, then reverted

Widening `_DETECTION_VERB_RE` to include determine/assess/evaluate/investigate
looks like the obvious one-line fix. It is not:

| | before | after widening |
|---|---|---|
| `AS.P1` | **PASS**, shape 1.00, `guided_investigation` | FAIL, shape 0.33, `spl_generation` |
| rows on `spl_generation` | 3 | 5 |
| pass rate | 0.1 | **0.0** |

`soc_actionable_hunt` is overloaded: besides the guided floor it also feeds the
broad detection/analytics floor (`query_signals.py` ~1288/1298), which routes
result-seeking asks to the governed SPL path — and that floor wins. Firing the
signal more often therefore moves these questions **away** from the guided
investigation shape and into SPL generation.

The change was reverted. It is recorded here so it is not retried.

## What a real fix needs (decision required — not taken here)

The guided floor must be reachable for posture/exposure determination **without**
also widening the SPL floor. Two candidate designs, both of which change
production routing authority for a whole query family and so need an explicit
decision:

- **A.** A separate `posture_determination` signal consumed *only* by
  `classify_intent`'s guided branch, leaving `soc_actionable_hunt` untouched.
- **B.** Precedence: when a question states an investigation objective and the
  registry has no match, guided outranks the broad SPL floor.

Neither is applied. `pipeline.py`, `planner/` and `routing/` are protected paths.

## Current measured baseline

`scripts/eval_investigation_answer_shape.py`, bank
`investigation_answer_shape_bank_v1.json` (10 rows):

- pass rate **1/10**, mean shape score **0.4833**
- stage coverage: **plan 1/10**, findings 10/10, remediation 2/10
- authority violations 0, executed remediation 0

The dominant gap is stage 1: nine of ten investigation-class questions never
state how they will investigate.

Run it with:

```bash
PYTHONPATH=backend:. python3 scripts/eval_investigation_answer_shape.py --write-report
```

It exits non-zero while the shape is unmet, so it can gate.
