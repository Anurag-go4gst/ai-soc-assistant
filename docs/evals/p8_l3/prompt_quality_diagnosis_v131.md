# P8 L3 — prompt-quality diagnosis and candidate v1.3.0 A/B

Branch `ws/p8-prompt-fewshot-closure`, worktree `/Users/aagarwal/Downloads/ai-soc-p8-prompt-fewshot`,
from `feat/complete-or-abstain-t4-ux` @ `9f12de89`.

Frozen bank `docs/evals/p8_l3/bank_v1.json`, canonical hash
`5f78ccbe1940149a67dcd1052140c44c854ec42a409d7644b47e5357010dbf51`, 16 rows.
Thresholds `thresholds_v1.json` unchanged (`semantic_correctness >= 0.50`,
`schema_validity >= 0.80`, `initial_pass_rate >= 0.40`). No bank row, threshold,
grader rule or validator was relaxed.

## Headline

The earlier `MODEL_CAPABILITY_CANDIDATE` reading does not survive measurement.
Every failing category traced to a defect on our side of the model boundary.

| Role | Classification | Mechanism |
|---|---|---|
| `spl_advisory_generator` | `VALIDATOR_CONTRACT_MISMATCH`, then `PROMPT_FIXED` | Compiler emitted SPL its own gates rejected; then junk filters from an exemplar-less prompt |
| `investigation_planner` | `PROMPT_FIXED` | Wrapper key, then token-ceiling truncation — both format, not reasoning |
| `semantic_t4` | `PROMPT_FIXED` (2 of 4 rows), see residue | Guided-decoding schema marked nothing required; v1 few-shots were bank questions |

## 1. The SPL failure was never the model

`generate_llm_spl_via_plan` returned no candidate at all for rolling, trend and
sequence — `candidate_len=0`, `spl_losses=['no_candidate']`. The model's detection
plan was discarded before it could matter, in **both** arms, which is why the two
arms scored identically.

Measured causes, all deterministic:

| Shape | Gate that rejected our own compiled SPL | Detail |
|---|---|---|
| rolling | `draft_quality` `SOC-STD-SPL-001-Q11` | compiler wrote `sort 0 _time`; the lint requires `sort 0 + _time` |
| sequence | Q11 **and** `validate_spl` `missing_aggregation` | branch ended on `\| where`, no stats/timechart stage |
| trend | `validate_spl` `missing_result_limit` | `\| timechart` with no result cap |

Fixed on the compiler side; no gate was relaxed. Trend carries its result limit
via `| sort 0 _time` (which `_result_limit_value` reads) rather than a head cap,
because the trend contract prohibits `arbitrary_head_100`, `arbitrary_truncation`
and `time_series_truncation`. Sequence summarises the already-matched A→B pairs
*after* the ordering/gap decision, so the sequence semantics are not collapsed.

Two fidelity checks were also quote-blind against the compiler's own output
(`action="denied"` did not satisfy the token `action=denied`; likewise
`action="failure"` for the `failed_login` event set). Both credited a filter that
was genuinely present; a query with no such filter still reports the loss, pinned
by test.

**Consequence for attribution:** with the compiler fixed, SPL is **5/5 in both
arms**. The SPL recovery is attributable to the compiler↔gate fix, *not* to the
few-shots. The comparator correctly reports `spl_advisory_generator:
no_safe_improvement`.

The few-shots did measurably improve the *plan* the model returns — that effect is
real but invisible to this bank, because deterministic code owns the SPL text:

| Shape | Plan filters before | after |
|---|---|---|
| rolling | `src_ip="not null"`, `user="distinct"` | `action="failure"` |
| trend | `function_code="failed_login"` (wrong domain field) | `action="failed"` |
| sequence | `event_type="password_change"` AND `event_outcome="success"` — contradictory, matches nothing | `[]` (correct: the compiler builds the ordered selection) |

The compiler now also drops non-predicate matches (`*`, `not null`, `any`) rather
than trusting the prompt to avoid them.

## 2. T4 — the schema, not the instruction

On all four frozen rows the model returned **empty** `competing_hypotheses` and
**empty** `evidence_requirements` — the two fields every T4 row is scored on —
while emitting the two keys the prompt explicitly told it to omit.

Root cause: `_SEMANTIC_T4_SCHEMA` lists every property and marks **none** required,
so under constrained decoding a fully compliant response may omit all of them, and
does. The candidate arm now requires the fields the frozen `SemanticT4Proposal`
contract already declares, and withholds the legacy aliases (`ambiguity_state`,
`confidence`) so the model answers in the frozen spelling. This asks the model for
*more*, not less; the frozen contract, the merge and every deterministic authority
are untouched.

**Contamination finding.** The v1.2.0 candidate's five T4 few-shots were
near-verbatim frozen-bank questions — `L3.T4.02` and `L3.T4.03` verbatim,
`L3.T4.01` and `L3.T4.04` paraphrased. Besides contaminating the measurement, they
demonstrably bled: on `L3.T4.01` the model returned a goal about comparing "with
last week", copied from a neighbouring example. They are withdrawn, not re-tuned.
`few_shot_catalog_v1` states the rule directly — examples teach a shape, not a
query — and a test now pins that no SPL shape example is a bank question.

Note the **ACTIVE** base few-shot pair in `semantic_t4_understanding.py` also
contains `L3.T4.03` verbatim, and primes "lateral movement" into unrelated answers.
That is ACTIVE code and was left alone under the no-in-place-edit rule; it is
flagged here as a separate finding.

## 3. Planner — both failures were format

ACTIVE wrapped the payload in an `investigation_plan` key (rejected by
`additionalProperties: false`). Candidate v1.2.0 ran past the 700-token ceiling
mid-object (`dropped:truncated`, `no_balanced_json_object`). One compact
exact-schema exemplar showing the twelve required keys at the top level, and how
terse the values must be, fixes both: `plan_source: llm_proposed_validated`,
`dropped_reasons: []`.

## 4. Frozen A/B — `ab_v131_*`

Both arms: same 16 rows, same bank hash, same runner, same endpoint
(`http://10.52.1.13:8004/v1`, `foundation-sec-instruct`), thresholds frozen.

| Metric | ACTIVE | CANDIDATE | Delta | Gate |
|---|---|---|---|---|
| semantic_correctness | 0.5833 | **0.9167** | +0.3334 | ≥0.50 both pass |
| schema_validity | 0.9375 | **1.0000** | +0.0625 | ≥0.80 both pass |
| initial_pass_rate | 0.4667 | **0.6667** | +0.2000 | ≥0.40 both pass |
| t4_accept_rate | 0.0000 | **1.0000** | +1.0000 | record |
| spl_success_rate | 1.0000 | 1.0000 | 0.0000 | record |
| planner_schema_rate | 0.0000 | **1.0000** | +1.0000 | record |
| fallback_rate | 0.1250 | 0.0625 | −0.0625 | record |
| timeout_rate | 0.0000 | 0.0000 | 0.0000 | record |
| authority_violations | 0 | 0 | 0 | must be 0 |
| evidence_hallucinations | 0 | 0 | 0 | must be 0 |
| latency p50 / p95 / max (ms) | 765 / 3229 / 3790 | 343 / 1703 / 2687 | −422 / −1526 / −1103 | record |

Per-shape SPL, both arms: rolling PASS, trend PASS, sequence PASS, ranking PASS,
raw PASS; `L3.AB.01` correctly abstains.

Binding proven for all three roles: selected template is
`tmpl.<role>.candidate` v1.3.0-candidate and the selected instruction hash equals
the system prompt hash on the actual provider request, on every row.

## 5. Residue — 2 rows, honestly classified

**`L3.T4.03`** (`compare this with what happened last week…`) —
`MODEL_SEMANTIC_FAILURE`, with a measured mechanism. Requiring the two scored
arrays is what fixes T4.01/02/04, and it is also what suppresses the clarify
outcome: with `required=[…hypotheses, evidence…]` the model answers
`clarification_required=false`; with those fields optional the same model answers
`true` and names the missing referent correctly. The clean encoding is a two-branch
`anyOf` (resolve-shape or clarify-shape), which is what the contract actually
means — but on this vLLM build `anyOf` degrades badly (dropped `normalized_goal`,
empty arrays, one truncated response). Recorded as a serving-stack limitation, not
a prompt defect. Note the deterministic contract already carries
`answer_goal='clarification'` for this row, so the product still clarifies; only
the T4 proposal field the seam scores is wrong.

**`L3.T4.04`** (`any domain lookups that look algorithmically generated`) — **not a
model failure and not reachable by any prompt.** The row's second constraint
requires `required_capabilities` to contain one of spl/search/log, but the
deterministic contract for this query sets `required_capabilities=frozenset()` and
locks `prohibited_capabilities=['mcp','spl']`, and `required_capabilities` is in
T4's blocked set, so T4 may not set it. The constraint cannot be satisfied while
the deterministic contract stays as it is. The bank was **not** changed; this is
recorded as a bank/product mismatch for operator review.

## 6. Prompt size and cache discipline

| Role | ACTIVE system | CANDIDATE system | Δ ≈ tokens |
|---|---|---|---|
| semantic_t4 | 666 ch | 2011 ch | +336 |
| spl_advisory_generator | 777 ch | 1778 ch | +250 |
| investigation_planner | 560 ch | 1348 ch | +197 |

The SPL shape example (148–199 tokens) goes in the **user** prompt, so the
cacheable system prefix stays byte-identical across requests. Despite the larger
prompts, measured p50 latency fell 55% and p95 fell 47% — well-formed output ends
sooner and fewer turns fall back.

## 7. Not done here

- No ACTIVE template was edited; activation is a separate operator decision.
- No blocked reasoning role was enabled; the allowlist is still
  `{investigation_planner}`.
- Production was not switched to Qwen72B or to Foundation-Sec-8B Reasoning.
- J7 remediation gating, the ChatPanel DemoScenarioPicker and default-visible
  diagnostics were not touched.
