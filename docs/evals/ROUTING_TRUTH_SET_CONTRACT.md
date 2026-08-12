# Routing Truth Set — contract

**Artifact:** `docs/evals/routing_truth_set_v1.json` · **Schema:** `backend/app/evals/routing_truth_set.py` (`SCHEMA_VERSION = 2026-08-12-routing-truth-set-v1`) · **Pins:** `backend/app/tests/test_routing_truth_set_schema.py` · **Owner plan:** `plans/2026-08-11_1834_routing-evaluation-and-authority-corrections.md` (R1.1)

## Why this exists

The 105-question golden set cannot tell a correct route from an incorrect one:

- every row matches `exact_105_*` and routes by registry table lookup, so routing is a table read, not a decision;
- its labels are circular — `test_query_understanding_stage3je.py:84` asserts the understanding router equals the `legacy_router_intent_hint` supplied by the same file;
- `spl_status` is `none` on **113 of 120** frozen answer rows, so a regression that suppressed SPL across the whole set would still report `120 exact`.

**Production parity measures answer stability, not routing correctness.** This set is the instrument for routing correctness. It is **labels-only**: it holds no answer text, never compares answer bytes, and is a separate artifact from `backend/app/evals/golden_answers/question_105_golden.jsonl`. Nothing in this contract authorises editing the answer goldens.

## Row schema

| Field | Type | Rule |
|---|---|---|
| `row_id` | string | Unique across the set. |
| `query` | string | Verbatim from a committed source — never invented for D2 rows. |
| `source` | string | Where the query came from (bank file + id, or golden `question_ref`). |
| `expected_intent_family` | enum | From `INTENT_FAMILIES`; every member is pinned to exist in `intent_classifier.py`, so a label can never name a family the runtime cannot produce. |
| `expected_answer_shape` | enum | The router's `AnswerShape` literals plus `clarification`. |
| `acceptable_skills` | **set** of skills | ≥1, no duplicates, each in `SKILL_ENUM`. |
| `required_capabilities` | subset of {`rag`,`spl`,`mcp`} | What the labelled intent needs to do its job. |
| `forbidden_capabilities` | subset of same | Must not overlap `required_capabilities`. |
| `ambiguous` | bool | `true` ⇒ `candidate_readings` must record ≥2 competing readings. |
| `label_confidence` | `high`\|`med`\|`low` | Adjudication confidence. |
| `rationale` | string | Mandatory, non-empty. Every label says why. |
| `labeled_without_registry_hint` | bool | Must be `true`. |

### `acceptable_skills` is a set, deliberately

Many SOC questions have more than one legitimate route. Requiring a single exact skill would manufacture failures on genuinely multi-valid rows and would pressure the labeller toward whatever the router already does — reproducing the circularity this set exists to escape.

### Staging: corpus before labels

`stage: "corpus"` rows carry `row_id` / `query` / `source` **only**; a label present at corpus stage is a validation error. `stage: "labeled"` rows carry the full adjudication. Validating a corpus file as `labeled` is the check that proves labelling actually happened, and the staging is what keeps assembly (R1.2) from being contaminated by adjudication (R1.3).

## The capability-consistency invariant

> A row is **`capability_inconsistent`** when the selected skill's contract denies a capability the row's label marks required — **even if `route_ok`**, and **even if the answer would still match an answer golden**.

Route correctness and capability consistency are **independent verdicts**:

- `route_ok` — selected skill ∈ `acceptable_skills`
- `route_wrong` — selected skill ∉ `acceptable_skills`
- `capability_inconsistent` — orthogonal to both

This orthogonality is the whole point. The D1 defect class is exactly a row where the route is defensible but the routed skill's contract denies the SPL the labelled intent needs, so the lane runs and contributes nothing. A benchmark that collapsed these two axes into one verdict would score those rows as passes.

### One capability authority, not two

`capability_consistency()` delegates to `skill_intent_compatibility._contract_grants`, which delegates to `composer._skill_permits`. This module does **not** hold a capability table, does not read `blocked_tools` / `default_workflow`, and does not reimplement permit logic — pinned by `test_capability_authority_is_not_reimplemented`. Plan 3 B2 established one implementation; a second copy would be a second authority by another name.

### Stated limit: RAG is labelled, not gated

`composer._PURPOSE_TOOL_HINTS` has permit keys for `spl` and `mcp` only. There is no RAG permit key, so `rag` is recorded in `required_capabilities` for reporting (E0) but **cannot** produce a `capability_inconsistent` verdict. Gating on it would require inventing a RAG permit table — precisely the second capability authority this contract forbids. The limit is documented rather than worked around.

Measured capability matrix at `93562c1`:

| Skill | `spl` | `mcp` |
|---|---|---|
| `attack_discovery` | ✅ | ✅ |
| `spl_generation` | ✅ | ❌ |
| `alert_summary` | ❌ | ❌ |
| `knowledge_recall` | ❌ | ❌ |
| `guided_investigation` | ❌ | ❌ |

## Label independence

`labeled_without_registry_hint: true` is a self-attestation and nothing more — the labeller has already seen production routes for many of these rows. Three mechanisms make independence checkable, all required by R1.3:

1. **Order commitment** — the completed label file is written and its SHA256 recorded *before* the evaluator runs (`file_sha256`). Any later edit must be recorded as an explicit relabel with its reason, never as a silent correction.
2. **Blind second labeller** — an independent labeller, given the queries and this contract but **not** the owning plan, the audit report, or any observed route, labels a ~20-row subset. Inter-labeller agreement is recorded as a number. Disagreements are findings to adjudicate, not rows to overwrite.
3. **Forced ambiguity** — the 7 `alert_summary` D1 rows (`notable_risk_lookup` ×5, `case_state_lookup` ×2) are `ambiguous=true` by rule. Their label *is* the R2.0 skill-ownership question; labelling them confidently would pre-decide the gate that exists to escalate them.

## Coverage limits

Stated so a green run is not read as more than it is:

- The evaluator is **deterministic-only**. Production runs `routing_mode=llm_assisted_semantic`, where the consumer-gated intent advisory can promote a route live. A green run is evidence about the **deterministic floor**, not about production routing. R1.5 records a small live-arm observation separately, never as a gate.
- Coverage of near-105 / semantic-105 / catalog-collapse paths is incidental — no quota forces it.
- The set does not measure answer quality, and must never be used to argue one.
