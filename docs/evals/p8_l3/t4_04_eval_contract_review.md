# L3.T4.04 — evaluation-contract review

**Classification: `EVALUATION_CONTRACT_MISMATCH`.**

The frozen row is **not** marked PASS, its score is **not** adjusted, and the
bank is **not** edited. `bank_v1.json` stays immutable evidence at
`5f78ccbe1940149a67dcd1052140c44c854ec42a409d7644b47e5357010dbf51`.

## The frozen row

```json
{
  "row_id": "L3.T4.04",
  "category": "t4_semantic",
  "seam": "t4",
  "role_id": "semantic_t4",
  "query": "any domain lookups that look algorithmically generated",
  "expected_constraints": [
    "goal is DGA/domain-generation hunt",
    "downstream evidence need is SPL-capable without T4 selecting the skill"
  ],
  "prohibited": ["execution_eligible true"]
}
```

The runner scores the row on two booleans
(`scripts/p8_l3_live_seams.py::run_t4_row`):

```python
elif row_id == "L3.T4.04":
    constraints_hit.append(any(tok in goal for tok in ("dga", "algorithm", "domain generation", "nxdomain", "dns")))
    caps = " ".join(enriched.required_capabilities or []).lower()
    constraints_hit.append(any(tok in caps for tok in ("spl", "search", "log")))
```

Constraint 1 passes: the model returns a DGA/domain-generation goal.
Constraint 2 requires `required_capabilities` to contain spl/search/log.

## The deterministic input contract, measured

For this exact query:

```
deterministic required_capabilities    : []
deterministic prohibited_capabilities  : ['mcp', 'spl']
deterministic intent_family            : clarification_required
deterministic answer_goal              : clarification
locked_fields                          : ambiguity_state, answer_goal, intent_family,
                                         prohibited_capabilities, qualification_source,
                                         qualification_tier
capabilities_for_intent_family('clarification_required')
                                       -> required=[]  prohibited=['mcp','spl']
```

So the only stage that may produce `required_capabilities` produces the empty
set, and `spl` is explicitly **prohibited** — and that prohibition is locked.

## The T4 output contract, measured

```
fields OFFERED to T4                   : clarification_reason, clarification_required,
                                         competing_hypotheses, evidence_requirements,
                                         normalized_goal, semantic_ambiguity,
                                         semantic_confidence
'required_capabilities' offered?       : False
'required_capabilities' in FROZEN_SEMANTIC_T4_PROPOSAL_FIELDS? : False
```

`required_capabilities` is excluded from the offered schema by
`semantic_t4_understanding.py::_job_aware_unresolved_schema_names`, whose
`blocked` set names it directly, and it is not a frozen proposal field. In
`contracts/semantic_t4_proposal.py` it sits in the group commented:

> Legacy / merge-reject-only. Never offered in the frozen schema. Kept so a
> model that still emits them is rejected by merge rather than silently dropped
> without a governance reason.

## Answering the three required questions

**Can T4 legally set `required_capabilities`?  No.**
The merge (`semantic_t4_understanding.py`) is explicit:

```python
# A proposal may carry required_capabilities/prohibited_capabilities as schema
# data, but they never become authority, so nothing below reads
# `proposed_required` as a source.
required = set(deterministic.required_capabilities)
...
field_sources["required_capabilities"] = "deterministic_qualification"
```

`field_sources` is hard-coded to `deterministic_qualification`; it can never
read `semantic_t4`. Anything extra the proposal asks for is recorded as
`capability_widening_rejected`.

**Can T4 legally invent `spl`?  No — twice over.**
`spl` is in the locked `prohibited_capabilities`, and the merge then applies

```python
required -= prohibited - set(deterministic.required_capabilities)
```

so even a capability that reached `required` by some other path is subtracted
again because it is prohibited and not deterministically required.

**Does the upstream deterministic stage produce those capabilities?  No.**
Both `deterministic.required_capabilities` and
`capabilities_for_intent_family('clarification_required')` return the empty set
for this query.

## Why the expectation is unreachable

Constraint 2 can only be satisfied if `required_capabilities` gains an
spl/search/log entry. Every route to that is closed by design:

| Route | Closed by |
|---|---|
| T4 proposes it | Not in the offered schema; not a frozen proposal field |
| T4 proposes it anyway | `field_sources` hard-coded to deterministic; `capability_widening_rejected` |
| Deterministic stage supplies it | Returns `[]` for this query and family |
| Family derivation supplies it | `capabilities_for_intent_family` returns `[]` |
| Anything supplies `spl` | Locked `prohibited_capabilities` subtracts it |

Making the row pass would require giving T4 capability authority — the exact
thing architecture §T4 forbids ("semantic proposal only … no execution
authority"). **The row is not measuring the model. It is measuring an
expectation the deterministic contract forbids.**

This is why the row must not be "fixed" from the prompt side: a prompt that
coaxed the model into emitting `required_capabilities` would still be rejected
by merge, and would only add a `capability_widening_rejected` governance event.

## Evidence

Code:
- `backend/app/chat/contracts/semantic_t4_proposal.py` — `FROZEN_SEMANTIC_T4_PROPOSAL_FIELDS`, merge-reject-only group
- `backend/app/chat/semantic_t4_understanding.py` — `_job_aware_unresolved_schema_names` `blocked` set; capability merge block
- `backend/app/chat/resolved_query_builder.py` — `capabilities_for_intent_family`
- `scripts/p8_l3_live_seams.py::run_t4_row` — the two scored booleans

Tests: `backend/app/tests/test_p8_prompt_candidates.py::test_candidate_t4_schema_decides_clarification_before_describing_the_goal`
pins that neither arm offers T4 `required_capabilities`, `prohibited_capabilities`
or `intent_family`.

Measured result across every attempt (v1.2.0, v1.3.0, v1.4.0-candidate):
constraint 1 passes, constraint 2 fails, `semantic_correctness = 0.50`, with
zero authority violations. The 0.50 is a ceiling, not a shortfall.

## Recommendation — a future governed bank correction

Not applied in this loop; the bank is immutable here.

A future `bank_v2` should re-express constraint 2 as something T4 can actually
be judged on. The row's stated intent — "downstream evidence need is SPL-capable
**without T4 selecting the skill**" — is really about `evidence_requirements`
naming a log/telemetry category, which T4 *may* legally produce and does. A
faithful restatement would be:

```python
ev = " ".join(enriched.evidence_requirements or []).lower()
constraints_hit.append(any(tok in ev for tok in ("dns", "log", "telemetry", "query")))
```

That measures the same intent through the field T4 owns, and would have to be
frozen before it is run, per `prompt_ab_eval_contract_v1`.

Until then L3.T4.04 remains a recorded frozen-row FAIL with this classification
attached. Reporting it as a product/model failure would be inaccurate; silently
scoring it as a pass would be worse.
