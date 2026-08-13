# Plan 5 D0 — residual routing after the architecture

**Measurement only.** No routing rule added, no skill contract widened, no frozen baseline refreshed,
no `cisco.ot.029`-style special case. Producer: `scripts/eval_residual_routing_after_architecture.py`
(machine table: `residual_routing_after_architecture_generated.md` + `.json`).

Phase C is deliberately **not** judged here by route-correct percentage — it fixes execution readiness
*after* understanding and routing. The question D0 answers is whether **B3/B4** expose better inputs for
the residual rows, and at **which layer** any change is visible.

## Instruments, and why more than one

B6 proved the frozen truth-set arms observe layers 1–2 only. So each residual row is measured at five layers:

| Layer | Instrument |
|---|---|
| L1 | `select_route_from_understanding` — the frozen deterministic arm |
| L2 | `route_skill` — the frozen live arm |
| L3 | `ResolvedQueryContract` — the Plan 5 B1/B3 understanding |
| L4 | `adjudicate_route` with the contract — the Plan 5 B5 seam |
| L5 | full `/chat` (`build_live_chat_response`) — the committed route and the analyst-visible surface |

**Measurement posture (L5):** host DB at `127.0.0.1:5434`; `TELEMETRY_MODE=none`;
`AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED=false` / `AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED=false` so no live model
narrates prose (facts are deterministic either way). The local model endpoint is unreachable from a host
process, so any LLM advisory hop degraded to deterministic — recorded, not hidden.

## Result — 25 residual rows (3 D2 · 10 ownership · 12 paraphrase)

| Layer | resolved | unchanged | regressed |
|---|---|---|---|
| L1 `select_route_from_understanding` | 0 | 25 | 0 |
| L4 `adjudicate_route` | **10** | 15 | **0** |
| L5 full `/chat` | **10** | 15 | **0** |

**L4 and L5 agree row-for-row.** The committed product route is the adjudicated route on all 25 rows, so
the L4 measurement is not a paper result. And the frozen arms report **0 of the same 10** — exactly the
blindness B6 documented. Anyone citing `--arm both` as "the architecture changed nothing" would be wrong
on 10 rows.

### Resolved by architecture (10)

| Row | Query | Before (Plan 4 baseline) | After (L4 = L5) |
|---|---|---|---|
| `rt.d1.003` | Did anyone get added to Administrators? | `knowledge_recall`, capability_inconsistent | `spl_generation` |
| `rt.d1.005` | Which users accessed privileged applications unusually? | same | `spl_generation` |
| `rt.d1.006` | Which accounts were disabled or re-enabled today? | same | `spl_generation` |
| `rt.d1.011` | Which logs are missing from key security sources? | same | `spl_generation` |
| `rt.d1.012` | Which sources stopped sending events recently? | same | `spl_generation` |
| `rt.d1.013` | Which users performed privileged actions from non-admin workstations? | same | `spl_generation` |
| `rt.d1.014` | For any flagged host or user, what is its asset criticality, business owner, identity/privilege status? | same | `spl_generation` |
| `rt.d2.003` | Signs of Kerberoasting against domain controllers in the finance subnet? | `knowledge_recall`, capability_inconsistent | `spl_generation` |
| `rt.para.001` | which sources sent out the largest number of outbound sessions | same | `spl_generation` |
| `rt.para.010` | who currently carries the highest risk score | same | `spl_generation` |

All ten carry the same new contract signature: `intent_family=spl_generation_only`,
`answer_goal=spl_artifact`, `required_capabilities={spl}`, `ambiguity_state=unambiguous`. That is B3's
decontaminated understanding doing the work — the label's required `spl` capability is now granted by the
committed route, so `capability_inconsistent` clears on all ten.

**`rt.d2.003` is resolved** — one of the three Plan 4 D2 rows, and the one Plan 4 called undiscriminable.

### Unchanged (15) — split honestly

Seven of the fifteen are **already route-correct** and need nothing: `rt.d2.010`, `rt.d2.017`,
`rt.para.002`, `rt.para.009`, `rt.para.011`, `rt.para.013`, `rt.para.014`. For `rt.d2.010/017` and the
three `para` rows, `knowledge_recall` is inside the label's `acceptable_skills`; `para.002` and `para.011`
were already correct at baseline.

The genuine residue is **8 paraphrase rows** — `rt.para.003/004/005/006/007/008/012/015` — all wrong in the
same way and with an **identical** contract signature:

```
qualification_tier      T4
qualification_source    out_of_registry
intent_family           clarification_required
answer_goal             clarification
ambiguity_state         clarification_required
required_capabilities   {}          <- empty, so capability enforcement sees no contradiction
evidence_requirements   []
confidence              0.45
entities                the 16-key slot SCHEMA, identical on every row (no extracted values)
time_scope              None
```

They collapse to `knowledge_recall` via `intent_clarification`, and the label wants an SPL-capable route.

### Regressed (0)

No residual row moved from route-correct to route-wrong at any layer, and no row gained
`capability_inconsistent`. Independently confirmed by the frozen gate: truth set `--arm both --check`
still **0 regressions** (`route_ok 64/76`, live `59/76`).

## Ownership classes — what actually happened

`asset_identity_context` / `data_source_health` (10 rows) are no longer routed as knowledge questions in
production: 7 of them now commit `spl_generation`, and the remaining 3 (`para.009/013/014`) sit in the
clarification collapse. **This is a de-facto answer to the ownership question that no one explicitly
approved** — it arrived as a consequence of decontaminating the understanding, not as a policy decision.
It is inside the labels' acceptable sets, so it scores as correct, but it deserves an explicit ratification
or objection at D1 rather than silent acceptance.

## Does B4's T4 semantic hop expose a discriminator? Measured: **no, not at its current bound**

Side probe on the 8 residual rows, run **inside the backend container** where the model endpoint resolves
(`docs/evals/plan5/d0_t4_semantic_side_probe.json`; flag toggled in-process, `.env` untouched):

| Outcome | Rows |
|---|---|
| hop invoked | **8 / 8** |
| proposal accepted | **0 / 8** |
| rejected `timed_out` (2.0 s wall-clock bound) | 6 |
| rejected `empty_output`, note `llm_model_slot_busy` | 2 |

The contract was **identical** OFF and ON on all 8 rows (`understanding_source` stayed
`deterministic_qualification`). The bounded hop behaved exactly as designed — it never widened a
capability, never set a skill, and degraded to the deterministic contract — but on this host the single-slot
8B model cannot answer inside 2.0 s, so B4 currently contributes **no** semantic signal to these rows.
That is an infrastructure/bound question, not a routing-rule question.

## Conclusions carried into D1

1. **10 of 25 residual rows are resolved by the architecture**, visible only at L4/L5 — including
   `rt.d2.003` and all 7 SPL-needing ownership rows. 0 regressions.
2. **The residue is 8 paraphrase rows with one shared failure mode**: T4/out-of-registry queries collapsing
   to `clarification_required` with empty required capabilities.
3. **The contract exposes no deterministic discriminator for them today.** Every field is identical across
   all 8, and identical to what a legitimately-ambiguous query would produce; `entities` holds the slot
   schema, not extracted values, so there is nothing row-specific to key on. A rule keyed on
   `tier=T4 ∧ family=clarification_required` would fire on every genuinely ambiguous out-of-registry query
   as well — that is capability widening by another name, not a discriminator.
4. **B4 is the designed mechanism and it is currently unusable at its bound** (0/8 accepted, 6 timeouts,
   2 slot-busy). Raising the bound or changing the serving posture is a product/infra decision.
5. **The ownership shift to `spl_generation` needs explicit ratification**, since it changed live behaviour
   for asset-identity and data-source-health questions without an ownership decision being taken.
