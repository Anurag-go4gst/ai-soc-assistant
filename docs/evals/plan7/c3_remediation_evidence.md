# Plan 7 C3 — `REMEDIATE_EXISTING_T4_IN_PLACE`: remediation and re-measurement

Preserves and does not rewrite: `c2_serving_viability.md` (PRE-C3 measurement),
`c3_stop_decision_packet.md` (the options), `c3_manual_vps_evidence.md` (user-run diagnostics).
This file records what changed and what was measured **after**.

## Effective runtime (verified by read-back from the running backend)

```
LANGGRAPH_ORCHESTRATION_ENABLED                  = true
AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED           = true
AI_SOC_PIPELINE_DISPATCH_V2_ENABLED              = false
AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED         = true
AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS = 120     <- VPS_T4_REMEDIATION_TIMEOUT
AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED       = false
MCP_MODE                                         = mock
```

Model/serving unchanged: Foundation-Sec-1.1-8B **Q8**, `llama-server -c 4000 -t 4 -np 1`, port
8081. No sidecar, no cache, no provider change, no new model. Repo default `config.py:414`
remains **2.0** — the 120 s value is VPS-only and is not an architectural constant.

Constrained decoding was already supported by the existing client
(`LocalChatClient.generate(response_format=…)`), so **no serving-architecture change was
required** and no STOP was owed on that point.

## PRE-C3 vs POST-C3 measurements

| | PRE-C3 (2.0 s, original prompt) | POST-C3 (120 s, hardened prompt) |
|---|---|---|
| T4 invoked on T4 rows | 17/17 | 9/9 and 4/4 |
| **accepted** | **0** | **2/9** then **1/4** |
| timed out | 17/17 @ ~2.0 s | 7/9, 2/4 @ 120 s |
| malformed/rejected | 0 | **1** (`schema_invalid`, `t4.out_of_registry` @ 99 s) |
| T4 elapsed on success | — | **78.3 s**, **111.7 s**, **115.1 s** |
| turn wall | ~90 s | ~190–212 s |
| clarification safety | preserved | preserved |
| false widening | 0 | 0 |

Runs: `docs/evals/plan6/runs/20260815T072648Z` (9 rows), `…/20260815T075657Z` (3 probes),
`…/20260815T080934Z` (4 rows), `…/20260815T083846Z` (4 rows post model restart).

### Host stability dominated the results

| Condition (same prompt, same model) | Outcome |
|---|---|
| Host thrashing (swap-in **588–759 MB/s**, `wa` 34–41 %, 148 MB free) — **with** schema | **>360 s timeout** |
| Host thrashing — **without** schema | **>360 s timeout** (rules out constrained decoding as the cause) |
| Immediately after `systemctl restart llama-server` | **83.4 s, valid JSON**, 168 tokens, 2.0 tok/s |

The 2/9 → 0/4 "regression" between runs was the box degrading, **not** the prompt or
`max_tokens`. `/v1/models` returned **200 throughout** the thrash, so a reachability probe cannot
detect this state — only a real generation probe can. Recorded for D1.

A second cost of the 120 s bound: `p6.repeat.refinement` returned **no route at all** — the turn
exceeded the 240 s client timeout.

## What actually changed (architecture, not prompt)

The prompt and the model are replaceable; the downstream contract is not. The load-bearing work
is in the seam.

### 1. Response-shape adapter (`_parse_proposal`)

A wrapped, echoed or chatty payload is now normalized instead of discarded:

- follows **one** answer wrapper (`output` / `answer` / `result` / `proposal` / `response`);
- drops echoed prompt scaffolding (`query`, `locked_fields_do_not_change`, `vocabulary`, …);
- drops unknown **non-authority** keys rather than failing the hop;
- **fails closed** on any authority-bearing key (`skill`, `route`, `normalized_spl`, `mcp_tool`,
  `execution_eligible`, `hil`, …) with the precise reason `authority_key_present`.

This directly fixes the measured `schema_invalid`: the model echoed the envelope and nested its
answer under `"output"` — because the few-shot examples were themselves shaped
`{query, unresolved, output}`. Examples are now rendered as flat `EXAMPLE n QUERY:` /
`EXAMPLE n ANSWER:` lines so there is no wrapper to imitate.

### 2. The three kinds of uncertainty are no longer interchangeable

```
semantic uncertainty      → may ask the analyst
evidence uncertainty      → continue investigating
investigation uncertainty → preserve hypotheses
```

`clarification_required=true` — and escalating `ambiguity_state` to `clarification_required`,
which is the same act — is accepted **only** when the query contains an unresolved referent.
Otherwise the merge records `clarification_without_unresolved_referent` and keeps the
deterministic verdict. Missing logs, thresholds or detection criteria can no longer become an
analyst question.

The referent detector deliberately excludes bare `that` / `it`: *"lookups **that** look
algorithmically generated"* is a relative pronoun, and treating it as a referent is exactly how a
clear hunt became a clarification.

### 3. Field semantics enforced deterministically

- **entities** — only concrete values (IP, CVE, domain/FQDN, `DOMAIN\user`, UNC, host-like token
  with a digit). A category such as *"algorithmically generated domains"* is refused with
  `entity_not_concrete`; recording it would fabricate an observation.
- **time_scope** — accepted only when grounded in the analyst's own words. An invented
  *"last 24 hours"* is refused with `time_scope_not_grounded_in_query`. Operational defaults
  belong to a later governed stage.

### 4. Locked fields are genuinely locked

`intent_family` and `answer_goal` are now **immutable** at this stage
(`locked_field_change_rejected:<field>`). Previously `_family_change_permitted` allowed a
capability-neutral family change — authority beyond what `architecture.md` §9 grants, and beyond
the resolver-owned field list. The single exception is bookkeeping: a clarification the merge
itself accepted sets `answer_goal="clarification"`.

**Consequence, stated plainly:** T4 can no longer re-classify a paraphrase into an SPL-capable
family. If an upstream contract locks a DNS hunt as `knowledge_recall` / `policy_citation`, this
stage completes meaning inside that contract and does not repair it. Fixing that is **upstream
(Plan 8) locked-field authority**, not a T4 change.

### 5. Vocabulary only for fields this stage may resolve

The full `intent_family` and capability vocabularies are no longer sent — offering a small model
the vocabulary for a locked field only invites conflict. Only `ambiguity_state` values are
supplied.

### 6. Observability

`debug_summary.resolved_query` now exposes `field_sources` and `semantic_t4_fields` (names and
source labels only, never values), so semantic addition can be measured rather than asserted.
**Instrument gap (fixed in the controlled re-measurement below):** both came back empty on the
bundles inspected, because the redaction runs twice and the second pass had no `provenance`. See
*Controlled C3 re-measurement*.

## Verification

| Check | Result |
|---|---|
| T4 seam tests (`test_plan7_c3_t4_response_shapes.py`, new) | **20 passed** |
| Existing T4 tests | **14 passed** |
| T4 / understanding / capability / debug slice | **210 passed, 1 skipped** |
| Planner / phase / dispatch / executor / routing / pipeline slice | **976 passed, 1 skipped** |
| A3 lifecycle invariant | green (inside the planner slice) |
| Deterministic fallback | green — prose-only output keeps the deterministic contract |
| T1–T3 calling T4 | no — `maybe_enrich_t4_semantic` returns early unless tier is T4 |
| Routing keyword heuristics added | **none** |
| Tool/MCP authority added to T4 | **none** — authority keys now fail the hop |
| dispatch-v2 | remains **OFF** |
| ResourcePlan authority | remains **ON** |

One existing test was edited: `test_model_cannot_set_a_skill` asserted the reason string
`schema_invalid`; it now asserts `authority_key_present`. The assertion's intent — a `skill` key
is rejected and never applied — is unchanged and still checked.

## C3 classification (superseded — see *Controlled C3 re-measurement* below)

**`T4_PROMPT_INTERFACE_STILL_BLOCKING`** — with the caveat that both remaining blockers are now
named and separable:

1. **Interface (fixed in this item, not yet re-measured end-to-end):** every observed failure
   shape — envelope echo, `output` wrapper, over-clarification, invented time scope, category
   entities — is now handled deterministically downstream. The user's LLM-Lab run confirms the
   model produces a correct flat answer once the contract is tight enough.
2. **Serving (unchanged):** at 120 s the model completes 2–3 times in 9–13 attempts, and only
   when the host is not paging. This is not fixable by prompt work.

**Superseded on 2026-08-15** by the controlled re-measurement, which was taken on a healthy host
against fixed instrumentation and shows the interface working (4/4 accepted). The classification
below stands only as the record of what was known before that run.

It is **not** `T4_VPS_VIABLE_FOR_PLAN7` — acceptance is neither reliable nor reproducible.
It is **not** `T4_MODEL_CAPABILITY_BLOCKER` — the model demonstrably produces the correct
contract when the interface is right. It is **not** `T4_SEMANTICALLY_VIABLE_BUT_VPS_LATENCY_BLOCKER`
alone, because the interface defects were real and are only now fixed, so latency has not yet
been measured against a corrected interface.

Per the E2 amendment, T4 remains a **hard GO requirement** and therefore a **CRITICAL BLOCKER**
until re-measured.

## Model health / restart (identified only — D1 owns the work)

- Recovery mechanism: `llama-server.service` (`Restart=on-failure`); `llm-control-watcher.service`
  applies UI-requested restart/stop/start via `.llm-control/`. Last recorded action:
  `sudo systemctl restart llama-server.service`, `ok=true`.
- Health surfaces: `GET /settings/llm/health` (probes `/v1/models`, TTL-cached, never raises),
  `GET /settings/llm/control-status`.
- Cold-start latency recorded separately: **83.4 s** for the first generation after restart.
- **Missing:** nothing wires *detect → restart → verify → at most one governed retry* into the
  T4 path, and the existing health probe cannot see a thrashing model. Carried to **D1**.

## Deferred to Plan 8

Explicit `LOCKED_FIELDS` / `UNRESOLVED_FIELDS` authority as a first-class contract. The current
seam passes both inside the existing contract, which is as far as it goes without a second RQC
and a final-RQC authority sequence. Now that locked fields are immutable here, **upstream
classification quality is the binding constraint on T4 usefulness** — recorded as a Plan 8
convergence dependency, not built here.

---

# Controlled C3 re-measurement (2026-08-15)

Third measurement stage. `c2_serving_viability.md` (PRE-C3) and the POST-C3 section above are
unchanged; this section is additive.

Artifact: `docs/evals/plan7/c3_remeasurement.json`. Harness:
`scripts/eval_plan7_c3_t4_measure.py` — drives the real `maybe_enrich_t4_semantic` seam with the
real live provider, so the shape adapter, every deterministic guard and the merge run exactly as
production would. No restart, no reconfiguration, no deployment change.

## Instrumentation defect that invalidated the previous measurement

`redact_resolved_query` runs **twice** on a live turn: once into `control_plane_trace`, then
again in `debug_summary` over that already-redacted dict. The second pass has no `provenance`,
so `field_sources` was recomputed as `{}` and overwrote the first pass. The `semantic_t4` block
survived only because it happened to have a flattened fallback; `field_sources`, added later, did
not. Fixed by giving it the same fallback. Pinned by
`test_field_sources_survive_a_second_redaction`.

Added, observation-only: `semantic_t4.proposed_fields` and `semantic_t4.accepted_fields` — names
and source labels only, never values — so "the model answered" and "deterministic validation kept
it" are separable facts. Tests assert the seam carries no values and does not move the
accept/reject boundary or attribute capabilities to `semantic_t4`.

## Two discarded/false-signal runs, recorded not hidden

1. **First controlled run was invalid.** All four cases failed in **1–7 ms** with
   `url_error:gaierror` on `host.docker.internal`, which resolves only inside the container; the
   harness ran on the host. Discarded rather than reported as T4 timeouts.
2. **An endpoint failure is reported as `timed_out`.** `run_sidecar_llm_with_timeout` maps any
   provider exception — DNS failure, refused connection, 5xx — onto `timed_out` with note
   `llm_assist_timed_out`. So "T4 timed out" in earlier measurements could mean *slow model* or
   *unreachable endpoint*, indistinguishably. This weakens the PRE/POST timeout counts above.
   **Carried to D1**; not changed here, because altering failure classification would change
   acceptance semantics inside a measurement item.

## Host state during the measurement

Load **0.70**, `si`/`so` **0**, `wa` **0%**, MemAvailable **8.8 GB**, swap 4095/4095 allocated but
not paging, `llama-server` `Ssl` RSS 8.6 GB, uptime 38 min at start (restarted **by the operator**;
Claude performed no restart). Healthy — no `HUMAN_RESTART_REQUIRED`.

Inference health was confirmed by a bounded inference probe, not by `/v1/models`: one warm-up
completed and was **accepted** at **55.3 s** cold.

## Results — 4/4 accepted, all inside the 120 s bound

| case | accepted | elapsed | proposed | accepted fields | rejected | locked preserved | widening |
|---|---|---|---|---|---|---|---|
| lateral_movement | ✅ | **39.4 s** | 6 | `normalized_goal`, `evidence_requirements` | `clarification_without_unresolved_referent` | ✅ | none |
| competing_hypotheses | ✅ | **39.1 s** | 6 | `normalized_goal`, `evidence_requirements` | `clarification_without_unresolved_referent` | ✅ | none |
| missing_context | ✅ | **28.6 s** | 6 | `clarification_required`, `normalized_goal`, `evidence_requirements` | — | ✅ | none |
| spl_capable_paraphrase | ✅ | **32.9 s** | 6 | `normalized_goal`, `evidence_requirements` | `clarification_without_unresolved_referent` | ✅ | none |

Warm-up 55.3 s cold; steady-state 28.6–39.4 s. p50 ≈ 36 s, p95 ≈ 39 s — comfortably inside 120 s.

## Useful semantic contribution, not schema-valid echo

| case | goal before → after | evidence requirements added |
|---|---|---|
| lateral_movement | "signs that something is moving sideways through the estate" → **"identify lateral movement within the network estate"** | 5, incl. authentication logons from unusual hosts, process execution with cross-subnet network activity |
| competing_hypotheses | "powershell on endpoints talking to new domains" → **"assess whether PowerShell activity with outbound DNS to new domains is malicious or routine administration"** | 4, incl. parent process/command line, domain registration age, *known software usage* as a competing explanation |
| missing_context | verbatim query → **"compare the current security event with the corresponding event from last week to determine if the situation is worsening"** | 3, incl. the missing current-event details |
| spl_capable_paraphrase | "any domain lookups that look algorithmically generated" → **"identify domain lookups that appear algorithmically generated"** | 4, incl. DGA-characteristic analysis and comparison against known benign patterns |

Competing hypotheses were preserved (case 2 names routine administration and known software as
explanations); no case asserted anything malicious as fact; no invented time scope; no category
strings recorded as entities.

## The binding limitation is upstream, and it is not T4's to fix

**Every one of the four deterministic base contracts is `intent_family=clarification_required`,
`answer_goal=clarification`, `required_capabilities=[]`** — including a clean lateral-movement
hunt and a DGA hunt.

Consequences, stated plainly:

- `clarification_added` is `false` on all four **because clarification was already true upstream**,
  not because T4 avoided adding it.
- The three `clarification_without_unresolved_referent` rejections were therefore **no-ops** on the
  final contract. This run does **not** demonstrate the guard preventing an over-clarification on
  an otherwise-unambiguous turn; that is demonstrated in unit tests
  (`test_evidence_uncertainty_may_not_become_an_analyst_question`), not here.
- With locked fields now immutable, **T4 cannot move these rows toward an SPL-capable family**, so
  no downstream SPL work can follow from them regardless of how good the semantic completion is.

This is the intended architecture boundary (`architecture.md` §9: T4 may not grant capabilities or
become routing authority) and is recorded as a **Plan 8 convergence dependency**: T1–T3 locked
facts → T4 completion → deterministic merge → **deterministic recomputation of evidence,
capability requirements and route hints** → final RQC. It was **not** patched with keywords or T4
route mutation.

## Classification

**`T4_SEMANTICALLY_VIABLE_BUT_VPS_SERVING_BLOCKER`.**

- **Semantics: proven.** 4/4 accepted with genuine, useful contribution; every guard held; locked
  facts preserved; zero capability widening. Not `T4_INTERFACE_DEFECT_REMAINS`, and not
  `T4_MODEL_CAPABILITY_BLOCKER`.
- **Serving: not proven.** The same configuration produced 2/9, then 1/4, then 4/4 on the same day
  — the variable was host paging, not the prompt. There is still no automated health detection or
  recovery (`/v1/models` returns 200 while the model is unusable), and endpoint failures are
  indistinguishable from timeouts in the trace. So `T4_VPS_VIABLE_FOR_PLAN7` is not supported:
  one clean run on a quiet, freshly-restarted host is not reproducibility.

T4 remains a **hard GO requirement** per the E2 amendment, and therefore a **critical blocker**
until serving stability and recovery are addressed in D1.
