# Experience Center — architecture fidelity + credibility audit

**Date:** 2026-08-18
**Scope:** all 7 EC flagship scenarios (S1–S7), `backend/app/demo/**`, `frontend/src/components/ec/**`
**Contract audited against:** `architecture.md` @ `c1c4ba8a88d8f245752188a76442102978eceb0c1bdb410717b789649fb9a034`
**Questions:** (1) Does EC fake a live experience without calling LLM/MCP/RAG? (2) Does anything contradict `architecture.md`? (3) Would a CTO/CSO believe it, and does it justify an AI SOC?

Every finding below was measured by executing the EC turn builders, not read from docs.

---

## Verdict

| Question | Verdict |
|---|---|
| No live LLM / MCP / RAG calls | **PASS** — mechanically enforced, no gaps found |
| Contradicts `architecture.md` | **2 findings** (A1, A2) — both are *animation* contradictions; the code is correct |
| Believable to a CTO/CSO | **AT RISK** — Layer 1 is clean; the animated journey and Layer-2 copy are saturated with demo tells |
| Justifies an AI SOC | **AT RISK** — the 6 architecture phases that differentiate an AI SOC are the ones EC does not show |

Severity buckets used throughout, per the distinction you drew:

- **A — contradicts architecture** (must fix)
- **B — under-represents architecture** (value gap; showing what is not built is fine, hiding what *is* built is not)
- **C — honest but unbelievable** (presentation)
- **D — value framing** (not an architecture issue)
- **OK — consistent, do not "fix"**

---

## 1. Purity: does EC fake live without calling anything?

**PASS. No gaps found.** This is the strongest part of the build.

| Control | Measured |
|---|---|
| No live-client imports in `app/demo/**` | `grep -rnE "call_tool\|httpx\|requests\.\|aiohttp\|openai\|llama\|chat_completion\|invoke_llm\|LlmClient\|RagRetriev\|embed"` → **zero** hits outside fixture *strings* (`splunk_mcp_fixture` etc.) |
| Runtime provenance | `ec_provenance` = `live_llm_called:false`, `live_mcp_called:false`, `live_rag_called:false`, `simulated_mcp:true` |
| Execution envelope | `execution` = `production_mcp_executed:false`, `executed_spl:null`, `block_reason:"live_mcp_not_called"` |
| Side effects | `production_side_effect:false` on every action |
| Import isolation | `test_live_path_untouched_by_ec.py` asserts `pipeline.py`/`graph/`/`planner/` never import `app.demo`, and `app/demo/**` never imports `routes_actions` or references `ChatPanel` |
| LLM realism without a live call | `capture_loader.py` replays *genuinely captured* post-guard model answers with `live_llm_called=false`, caps each replayed stage at `MAX_REPLAYED_STAGE_MS=6000`, and re-stamps `trace_id`/timestamps per run so each demo looks freshly executed |
| Fail-closed | Capture missing/corrupt/schema-mismatch → falls back to in-code fixture → if neither usable, operator-facing error. Never a blank or partial answer |

**The one asset nobody can see (see B3):** `ec_provenance.production_validator_read_only = true`. The **real production `validate_spl`** runs against the EC SPL. The SPL on screen is genuinely production-validated. That is the single most defensible claim in the whole demo and it is currently rendered nowhere.

---

## 2. A — Contradicts architecture (must fix)

### A1 · S5 Cisco upgrade animates with **no HIL approval stage** — highest-stakes scenario

`ec_journeys.py:490–504` `_cisco_action()`, non-verify branch:

```text
Selecting Cisco device  →  Connecting to Cisco device  →  Recording device receipt
```

Compare `_firewall_action()` (~line 477), non-verify branch:

```text
Selecting firewall controller  →  Connecting to firewall  →  Approval required  [semantic_type="hil"]
```

A device firmware upgrade is `SIDE_EFFECTING` under `architecture.md` §20 and **invariant 37** ("Side-effecting MCP tools require policy/RBAC/HIL/idempotency controls"). The underlying action FSM *does* gate correctly (`APPROVED` → `EXECUTED`), so this is a representation defect — but it is on the surface a CSO actually watches, in the one scenario where an approval gate is the whole point.

**Recommend:** add the `("Approval required", "hil", …)` stage to the `_cisco_action` non-verify branch, mirroring `_firewall_action`. Small, local, EC-only.

### A2 · "Applying governed LLM advisory" animates **before** "Building InvestigationOutcome" — all 7 scenarios

Measured stage order (identical in S1–S7): `… correlate → llm-advisory → outcome`.

`architecture.md` §2.7 and **invariant 27**: InvestigationOutcome precedes narration; narration creates no decision authority. **Invariant 26**: LLM-proposed findings become authoritative only after deterministic validation.

The code is correct — the stage activity is `"Applying severity, MITRE, and SPL governance overrides…"`, i.e. deterministic authority overriding the model. But a stage titled *"Applying governed LLM advisory"* rendered **before** *"Building InvestigationOutcome"* reads to any technical viewer as the LLM shaping the outcome. The animation states the architecture backwards.

**Recommend:** either swap the two stages, or retitle to make the direction explicit — e.g. `"Validating LLM advisory against deterministic authority"`.

---

## 3. B — Under-represents architecture (value gap)

### B1 · EC shows ~6 of 12 architecture phases — and the 6 it drops are the AI-SOC differentiators

`INITIAL_ARCHITECTURE_STEP_COUNT` hard-enforces exactly 10 stages for every scenario (`ec_journeys.py:176`). The fixed keys are:

```text
understand · resource-plan · mcp-select · mcp-connect · evidence
spl-validate · mcp-execute · correlate · llm-advisory · outcome
```

Not represented anywhere in the animation:

| Architecture phase | Why it matters to the "why AI SOC" question |
|---|---|
| Phase 2 — **T4 semantic understanding** `[LLM]` (§9) | The one stage where a model resolves meaning a rule cannot. Entirely absent. |
| Phase 4 — **final ResolvedQueryContract** (§12) | The authoritative contract that makes the rest deterministic |
| §12 — **clarification terminates before planning** | Shows the system refusing to guess |
| Phase 6 — **ResourcePlan compiler → PhaseContract** (§15) | Mandatory lifecycle controls that cannot be compiled away (invariant 10) |
| Phase 8 — **evidence sufficiency gate** (§18) | Folded silently into `outcome`; the gate itself is never shown |
| §10 — T4 serving, circuit breaking, backpressure | Operational maturity story |

**Consequence — this is the direct answer to your concern.** What remains on screen is *select a tool → run a search → correlate → write it up*. That is a SOAR playbook. A CIO watching it has no reason to conclude an AI SOC is required, because the reasoning layer that requires one is invisible. The Layer-1 *answers* are excellent (§6); the *journey* does not explain where they came from.

**Recommend:** treat the 10-stage constant as the constraint it is and re-spend the budget. At minimum surface a T4/understanding stage and an evidence-sufficiency stage. Showing "T4 not required — T1–T3 resolved this query" is itself a strong, honest, architecture-accurate stage.

### B2 · "Final synthesis disabled for Experience Center" — advertised in all 7 scenarios

From `_LLM_ACTIVITY`, on every scenario's LLM stage. Per `CLAUDE.md`, live narration-only synthesis **is built** (`AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED` + `AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED`, facts stay deterministic). EC is advertising the absence of a shipped capability, seven times.

**Recommend:** reword to what is true and positive — the deterministic facts are authority, and narration is a separate governed capability that EC deliberately does not exercise. "Disabled" reads as "not built".

### B3 · Every honesty-and-credibility marker is in the payload and rendered nowhere

`grep -rn "production_validator_read_only\|live_llm_called\|live_mcp_called\|demo_fixture_not_live_data" frontend/src/components/ec/ frontend/src/pages/ScenariosPage.tsx` → **matches in test files only**. No EC component renders any of them.

So the demo simultaneously: (a) narrates "Replaying…" all over the animation, and (b) hides the fact that a real production validator ran. Exactly backwards.

**Recommend:** a persistent, compact EC provenance badge — `live LLM: no · live MCP: no · SPL validator: production, read-only`. It is more honest than the current state *and* more credible.

### B4 · S5 `approve_upgrade` and `execute_upgrade` render identical journeys

Both produce `Selecting Cisco device → Connecting to Cisco device → Recording device receipt`. Approval and execution are visually indistinguishable, which erases the HIL story even after A1 is fixed.

---

## 4. C — Honest but unbelievable (presentation)

### C1 · Layer 1 is clean; the animation the CIO *watches* is not

Regex scan for `replay|fixture|simulat|mock|demo|not production|disabled|placeholder|stub` across analyst-visible Layer-1 fields (`finding_title`, `assessment`, `what_we_found`, `important_evidence`, `unconfirmed_findings`, `recommended_actions`, `missing_evidence`) over all 7 scenarios:

**2 leaks total.**

- S1 `recommended_actions` — `"Verify a simulated firewall rule only after execute"`
- S5 `important_evidence` — `"Policy is EC scenario policy, not vendor production guidance"`

That is genuinely good discipline. But the **animated journey activity text**, which plays while the CIO watches, is saturated:

```text
Replaying approved saved search…
Replaying first governed Splunk search… / Replaying second governed search…
Fixture replay: current_version=14…
Loading captured Foundation-sec instruct signal…
Final synthesis disabled for Experience Center
```

**The fix is not less honesty — it is relocating honesty.** Provenance belongs on a persistent badge/drawer (B3), not narrated inside stage activity. `Executing governed Splunk search` **+ a `simulated` badge** is honest *and* believable. `Replaying first governed Splunk search…` is honest *and* unbelievable. Same information, opposite demo outcome.

### C2 · Layer-2 projection copy is a wall of negations

Per-scenario count of demo-tell strings on visitor-visible Layer-2 surfaces (`ec_status_summary`, `ec_projection.*`, `ec_evidence_state`): **S1 = 27, S2 = 17, S3 = 13, S5 = 11, S4/S6/S7 = 10**.

Repeated on every scenario:

```text
No ResourcePlan graph execution.
Experience Center projects controls; production PhaseContract is unused.
not production SPL policy   /   not production PhasePolicy
Evidence packaged from fixture and simulated connectors.
```

Correct, and correctly placed in Layer 2. But it is phrased entirely as what did *not* happen. Pair each with what *did* — "production SPL validator ran read-only and approved this query" — and the same drawer becomes a proof panel instead of a disclaimer wall.

### C3 · `route_source=ec_fixture_selected` is surfaced in Understanding, on every scenario

It sits in `ec_projection.understanding.items` — the *first* Layer-2 panel a curious viewer opens. It tells them the answer was selected before any reasoning is shown. Accurate; badly placed. Move it to the provenance badge with the rest of the honesty markers.

---

## 5. D — Value framing (not architecture issues)

### D1 · S6's recommended actions describe the product's constraints, not SOC actions

```text
If the question changes to service accounts, collect that evidence separately
Do not reuse administrator evidence after a scope change
```

The **scenario** is excellent and genuinely AI-SOC-differentiating — it demonstrates `architecture.md` **invariant 24** (evidence reuse must pass applicability/freshness against the new RQC) and **invariant 25** (historical evidence stays for provenance while being unusable). No rule engine does that. Only the copy is weak: a CIO reads product limitations instead of analytical rigour.

**Recommend:** reframe as an analyst-facing finding — e.g. "Administrator evidence does not carry over to a service-account question; that scope needs its own collection."

### D2 · S3 is the weakest "why an AI SOC" case in the set

Retrieve a process document, fill mandatory fields, draft a team email. As presented, that is workflow automation. It *is* redeemed by reusing confirmed SIEM evidence with no new Splunk search (invariant 24 again) — but that is buried in a stage title, not the headline.

**Recommend:** lead S3 with the evidence-reuse claim, not the email.

### D3 · S4 stage ordering is backwards

`Validating governed IOC hunt SPL` (stage 6) plays **before** `Identifying exploitation evidence gap` (stage 7). You cannot validate a gap hunt before the gap is identified. Plain ordering defect.

---

## 6. OK — Consistent; do not "fix" these

- **Cisco device MCP, CMDB, SOAR, ITSM, email, EDR.** None appear in `architecture.md` as built components — but §20 *New MCP tools* explicitly names ServiceNow / Jira / CRM / EDR / SOAR / email / IAM, and **invariant 36** permits new MCP integrations through existing registries with no orchestration redesign. CMDB falls in the `READ_ONLY` "asset lookup" class. All architecturally consistent. This is exactly the permitted "show what is not built yet" case.
- **`source_type: splunk_saved_search`** (no `_fixture` suffix) on `ev-s1-existing-search` / `ev-s2-detection` — `provenance: simulated_mcp` carries the truth. Fine.
- **Layer-1 answer quality is the strongest asset in the demo.** All 7 scenarios cleanly separate confirmed / unconfirmed / missing: S1 *"compromise not confirmed"*, S2 *"execution blocked · breach not confirmed"*, S7 *"do not force an incident"*. Refusing to over-conclude on partial evidence **is** the AI-SOC value proposition, and it lands.

### One naming risk worth fixing

In `architecture.md`, **"Cisco" means Cisco Foundation-Sec 8B — the LLM** (4 occurrences, all about model serving and restart authority; invariants 34–35). In EC S5, "Cisco MCP" / "Connecting to Cisco device" means a network router. A CTO can conflate *"their LLM is Cisco"* with *"they control Cisco routers"*, in either direction.

**Recommend:** label them distinctly on screen — `Cisco IOS-XE device MCP` vs `Cisco Foundation-Sec 8B (LLM)`.

---

## 7. Recommended order of work

| # | Finding | Effort | Why first |
|---|---|---|---|
| 1 | **A1** — add HIL stage to `_cisco_action` | trivial | Architecture contradiction, highest-stakes scenario, one code block |
| 2 | **B3** — render the provenance badge | small | Unblocks C1/C2/C3; converts hidden honesty into visible credibility |
| 3 | **C1** — move provenance out of stage activity into the badge | small | Largest believability gain per line changed |
| 4 | **A2** — reorder or retitle the LLM-advisory stage | trivial | Architecture contradiction |
| 5 | **B1** — re-spend the 10-stage budget on T4 / RQC / sufficiency | medium | Largest *value* gain; answers "why an AI SOC" |
| 6 | **B2 / B4 / C2 / D1 / D2 / D3** | small each | Copy and ordering polish |

### Overlap with the active defect-remediation plan

`plans/2026-08-18_1522_ec-experience-center-defect-remediation.md` (rev 2) already owns some of these lines — **do not open a second edit against them**:

- **Item 8** already reworks the S5 initial policy stages (`S5_INITIAL_TITLES[6]`/`[7]`) — fold any C1 rewording of those two stages into item 8 rather than a new change.
- **Items 2–3** already add the Layer-1 `source_evidence` panel — B3's provenance badge is adjacent but distinct; keep it separate.
- **Item 6** already fixes the S5 `missing_evidence` disagreement.

Everything else in this audit is **new scope** and should be a follow-up plan, not smuggled into the current branch.
