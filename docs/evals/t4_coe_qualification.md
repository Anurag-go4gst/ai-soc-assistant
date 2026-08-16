# T4 COE qualification pack

Reusable pack for later execution on the **COE dedicated LLM server**.
It reuses the current production T4 prompt builder, schema, and deterministic
merge. It does **not** parallel-implement T4, redesign T4, change
model/provider/timeout, or close F3.

Machine artifact (exact prompts, locked/unresolved fields):
[`t4_coe_qualification.json`](t4_coe_qualification.json).

## F3 disposition

| Claim | Status |
|---|---|
| T4 semantic capability | **proven** (Plans 6–8) |
| Current VPS serving | **not production viable** |
| F3 | **open** until COE serving qualification **passes** |
| This pack | prepares measurement; **does not assume COE will pass** |

The harness never auto-closes F3 (`f3_closed` stays `false`).

## Invariants (do not weaken)

- `/v1/models` HTTP 200 is **liveness, not inference health**.
- T4 cannot grant route, capability, or tool authority.
- No automatic Cisco restart. **HUMAN restart only**.
- Production prompt/schema/merge only:
  `app.chat.semantic_t4_understanding` + `SemanticT4Proposal`.

## Commands

Emit exact production prompts (no model call):

```bash
PYTHONPATH=backend:. python3 scripts/eval_t4_coe_qualification.py --emit-prompts \
  --out docs/evals/t4_coe_qualification.json --check
```

Future COE live run (configured existing T4 provider; do **not** run repeatedly
on this VPS):

```bash
PYTHONPATH=backend:. python3 scripts/eval_t4_coe_qualification.py --live \
  --chat-smoke --out docs/evals/t4_coe_qualification_live.json
```

`--live` does not change timeout, model, or provider. It enables the existing
T4 flag in-process for measurement only. **`--live` refuses the 2.0s code-default
timeout** — set `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS` explicitly in
`.env` first. That value is operator-supplied measurement config, not an SLO.
Do not copy the VPS 120s bound.

## Eight evaluation cases

Existing Plan 6/7/8 (or production few-shot) queries. No new keyword routing
rules.

| ID | Class | Query | Source |
|---|---|---|---|
| `lateral_movement` | lateral movement | signs that something is moving sideways through the estate | Plan 7 C3 / Plan 8 U3 |
| `dga_dns_c2` | DGA / DNS C2 | any domain lookups that look algorithmically generated | Plan 6 `para.003` / Plan 7 C3 / Plan 8 U3 |
| `powershell_malicious_vs_admin` | malicious vs administrative PowerShell | endpoints where PowerShell ran in a way that looks off | Plan 6 `para.008` / `rt.para.008` |
| `identity_compromise` | identity compromise | repeated failed admin logons on a server then one that succeeded | production T4 few-shot A |
| `potential_exfiltration` | potential exfiltration | anyone shipping unusually large volumes of data outward | Plan 6 `para.007` / `rt.para.007` |
| `missing_referent_clarification` | ambiguous / missing referent | compare this with what happened last week and tell me if it is getting worse | Plan 7 C3 / Plan 8 U3 |
| `insufficient_evidence_inconclusive` | insufficient evidence / inconclusive | Is unusual DNS traffic from an OT server enough to confirm command and control? | power-grid question bank / WS1 grounding |
| `competing_hypotheses` | competing hypotheses | powershell on endpoints talking to new domains | Plan 7 C3 / Plan 8 U3 |

Each case record includes: base locked fields, unresolved fields, exact T4
prompt, raw proposal, schema valid, proposed/accepted/rejected fields + reason,
locked fields preserved, clarification result, evidence requirements, direct
route/capability widening, latency, provider failure kind.

Production U1 job-aware gating is recorded as `production_next_action`. After
Plan 8 U1, several Plan 7 C3 paraphrases are already `CLARIFY` and would not
invoke T4. Hunt-shaped cases in this pack use the same CALL_T4 measurement
overlay as Plan 7 C3 shape tests (`live_investigation` / unambiguous / T4) so
COE can measure the hop. That overlay is **not** a keyword router and does not
change production `/chat`. The missing-referent case stays production `CLARIFY`.

---

## A. SEMANTIC QUALIFICATION

**Question:** can the current production T4 hop complete unresolved semantics
without taking route/capability/tool authority?

**How:** `--emit-prompts` captures the exact production system+user prompt and
locked/unresolved maps. `--live` (COE) runs `maybe_enrich_t4_semantic` and
records parse/merge outcomes. Injected contract checks (no model) pin fail-closed
behaviour.

**Pass language (for a later COE reviewer — not asserted here):**

- Locked `intent_family` / `answer_goal` / prohibitions preserved.
- No direct route or capability widening.
- Clarification accepted only for an unresolved referent; a hunt is not missing
  context.
- Competing hypotheses / insufficient-evidence cases do not prematurely classify
  malice.
- Evidence requirements may be added; they are not execution authority.

**This VPS emit-prompts run:** exact production prompts captured for the
measurement contracts; live semantic acceptance **not measured here**. See JSON
`cases[]`. F3 remains open. Expected `t4_call_permitted`:

- Hunt-shaped classes: `true` (C3 CALL_T4 overlay when production is `CLARIFY`)
- `missing_referent_clarification`: `false` (production U1 skip)
- `insufficient_evidence_inconclusive`: `true` (production `CALL_T4`)

Injected contract checks (always run, no Cisco call):

| Check | Expected |
|---|---|
| Malformed output | `schema_invalid`; deterministic contract kept |
| Authority keys (`skill` / `route`) | `authority_key_present`; no widening |
| Provider unavailable | `failure_kind=provider_unavailable`; no restart |
| Slot busy (synthetic) | `failure_kind=slot_busy` |
| Human restart packet | `restart_authorized=false` |

---

## B. SERVING QUALIFICATION

**Question:** can the COE dedicated LLM server serve production T4 with
acceptable inference health, latency, error rate, and bounded concurrency?

**This section is unmeasured until `--live` runs on COE.** Empty/null metrics
are intentional. **Do not treat a future COE run as a pass unless the numbers
are recorded and a human accepts them.** F3 stays open until that happens.

`/v1/models=200` is recorded only as **liveness**. Inference health is a
**bounded generation** probe (`app.llm.runtime_health.measure_runtime`), never
`/v1/models`.

| Metric | How `--live` measures | Emit-prompts (this pack) |
|---|---|---|
| Inference health | bounded generation tok/s + stall class | not measured |
| `/v1/models` liveness | labelled `liveness_not_inference_health` | not measured |
| Cold latency | first invoked hop `elapsed_ms` | not measured |
| Warm latency | subsequent invoked hop `elapsed_ms` | not measured |
| p50 / p95 | invoked-hop `elapsed_ms` | not measured |
| Timeout / error rate | `timed_out` / `provider_failure_kind` over 8 cases | not measured |
| Concurrency 2 | parallel T4 hops, `n=2` | not measured |
| Concurrency 3 | parallel T4 hops, `n=3` | not measured |
| Slot pressure | `failure_kind=slot_busy` under n=2/3 | synthetic contract only |
| Malformed / unavailable | injected checks + live failures | injected checks only |
| Application T4 integration | production `maybe_enrich_t4_semantic` + optional `--chat-smoke` `/chat` | seam named; `/chat` not run |

Live serving JSON keys (filled only by `--live`):
`serving.inference_health`, `serving.latency.{cold_ms,warm_ms,p50_ms,p95_ms}`,
`serving.timeout_error_rate`, `serving.concurrency.{n2,n3}`,
`serving.slot_pressure`, `serving.application_t4_integration.chat_smoke`.

**F3 remains open.** A green COE table would still need an explicit human
closure; this harness will not set `f3_closed=true`.
