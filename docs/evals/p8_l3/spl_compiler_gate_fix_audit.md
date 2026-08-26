# Phase A audit — SPL compiler ↔ gate fix (`f066a2fe`)

**Verdict: `SPL_COMPILER_GATE_FIX = ACCEPT`. `SPL_PROMPT_PROMOTION = NO`
(`NO_SAFE_IMPROVEMENT`).**

Reviewed at `00ae5b53`, re-measured live against `foundation-sec-instruct` at
`http://10.52.1.13:8004/v1`.

## The eight audit questions

**1. Which compiler outputs changed?**
Three branches of `compile_plan_to_spl` (`backend/app/spl/llm_plan_compiler.py`):

| Shape | Change |
|---|---|
| trend | appends `\| sort 0 _time` after the timechart |
| rolling | `\| sort 0 _time` → `\| sort 0 + _time` |
| sequence | same sort form; appends `\| stats count as sequence_matches earliest(_time) … by <correlate>` and a `strftime` presentation stage |

**2. Which downstream gates previously rejected them?**

| Shape | Gate | Reason |
|---|---|---|
| rolling | `draft_quality` `SOC-STD-SPL-001-Q11` | lint requires the literal `sort 0 + _time` before `streamstats` |
| sequence | Q11 **and** `validate_spl` | `missing_aggregation` — the branch ended on `\| where`, no stats/timechart |
| sequence (after fix) | `draft_quality` `U02` | `earliest(_time)`/`latest(_time)` need a readable `strftime` after stats — hence the added presentation stage |
| trend | `validate_spl` | `missing_result_limit` |

The compiler was emitting SPL that its own deterministic gates refused, so
`generate_llm_spl_via_plan` returned `candidate_len=0` and the model's detection
plan was discarded before scoring — in **both** arms. That is why ACTIVE and
CANDIDATE previously scored identically on SPL.

**3. Were any validator requirements removed?  No.**
**4. Were any validator thresholds weakened?  No.**

Proven by content hash rather than by reading the diff — every gate file is
byte-identical between the integration base `9f12de89` and `00ae5b53`:

```
UNCHANGED  backend/app/safeguards/spl_validator.py
UNCHANGED  backend/app/spl/draft_quality.py
UNCHANGED  backend/app/orchestration/mcp_execution_gate.py
UNCHANGED  backend/app/spl/llm_fallback.py
UNCHANGED  backend/app/spl/spl_intent_spec.py
```

A whole-branch protected-path scan over `9f12de89..00ae5b53` returns **no
protected file touched**.

The one gate-adjacent edit is in `spl_semantic_fidelity.py`, which is a
semantic-loss *reporter*, not a safety validator. It makes `_DENIED_SPL_RE`
tolerate the quoted form the compiler actually emits (`action="denied"`), so a
filter that IS present is credited. A query with no denied/blocked filter still
reports the loss, pinned by
`test_p8_spl_shape_gate_contract.py::test_denied_filter_match_is_not_weakened_by_quote_tolerance`.
That is a false-negative fix, not a relaxation.

**5. Were any unsafe SPL forms newly accepted?  No.**
The stages the fix newly emits are `sort`, `stats`, `eval`, `fields`. Checked
against the live policy:

```
RISKY_COMMANDS: collect, delete, inputlookup, loadjob, map, outputlookup,
                rest, savedsearch, script, sendemail
newly emitted ∩ RISKY_COMMANDS = NONE
```

No macro, no subsearch, no external call, no wildcard broadening. The trend cap
is carried by `| sort 0 _time` (which `_result_limit_value` already reads) rather
than a `| head`, because the trend contract prohibits `arbitrary_head_100`,
`arbitrary_truncation` and `time_series_truncation` — using a head there would
have *created* a semantic loss.

**6. Did `normalized_spl` authority change?  No.**
`normalized_spl` is still produced only by `validate_spl` on approval, from an
unmodified validator.

**7. Did `candidate_spl` gain any execution path?  No.**
Measured on all three fixed shapes:

```
rolling   lab.approved=False lab.normalized_spl=None lab.execution_eligible=False
trend     lab.approved=False lab.normalized_spl=None lab.execution_eligible=False
sequence  lab.approved=False lab.normalized_spl=None lab.execution_eligible=False
```

The raw lab-candidate envelope stays `approved=false / normalized_spl=null /
execution_eligible=false`, exactly as the governance invariant requires, and is
pinned by `test_compiled_shape_is_never_execution_eligible`.

**8. Did exact-call authorization change?  No.**
`mcp_execution_gate.py` is byte-identical; nothing in this change touches
`canonical_arguments_hash`, HIL or RBAC.

## Architecture chain — verified intact

```
LLM semantic plan
  -> deterministic SPL compiler          (changed: emits gate-compliant SPL)
  -> candidate SPL                        (still review-only, never executable)
  -> deterministic validator/postprocessor(unchanged)
  -> normalized_spl                       (unchanged authority)
  -> exact-call authorization             (unchanged)
  -> MCP                                  (unchanged)
```

No bypass introduced, no candidate execution, no validator weakening.

## Reproduction

Five frozen SPL rows, **ACTIVE** prompt:

```
L3.SPL.01 spl_rolling     PASS sem=1.0 losses=[] authority=[]
L3.SPL.02 spl_trend       PASS sem=1.0 losses=[] authority=[]
L3.SPL.03 spl_sequence    PASS sem=1.0 losses=[] authority=[]
L3.SPL.04 spl_ranking     PASS sem=1.0 losses=[] authority=[]
L3.SPL.05 spl_raw_events  PASS sem=1.0 losses=[] authority=[]
ACTIVE frozen SPL rows: 5/5
```

`L3.AB.01` still correctly abstains (`no_candidate`, support_status
unsupported) — the fix did not make the fail-closed path produce a query.

Focused suite: `-k spl` → **1384 passed**, 1 xfailed.

## Why the SPL prompt candidate is NOT promoted

Both arms now score **5/5**. The gain is attributable to the compiler↔gate fix,
which is arm-independent, not to the shape-selected few-shots. The A/B
comparator reaches the same conclusion on its own:
`spl_advisory_generator: no_safe_improvement`.

The few-shots did measurably improve the *plan* the model returns (junk filters
such as `src_ip="not null"` and contradictory ANDed sequence event types are
gone), but that improvement is invisible to this bank because deterministic code
owns the SPL text. Promoting on an unmeasured benefit would be promoting on
faith.

`SPL_PROMPT_PROMOTION = NO`.
