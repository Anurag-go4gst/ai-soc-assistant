# Plan — Power Industry Probe v2 + Query-to-Solution Quality (T2-forward, answer-is-the-metric)

Status: **Proposed** (evidence-backed from a second, fully-disjoint 10-question live probe, 2026-06-19)
Date: 2026-06-19
Author: Claude (Opus 4.8) for Anurag
Companion plan (for comparison): `plans/2026-06-19_power-industry-probe-query-to-solution-plan.md` (v1, pi.001–010)

## 1. Why this plan exists

We re-ran the exercise with a **completely new corpus** (pj.001–010, zero overlap with v1) through the real in-process `/chat` pipeline so the two plans can be compared head-to-head. Same posture as v1: control plane on, MCP execution off, LLM synthesis off (`.env.example`).

| Artifact | Path |
|----------|------|
| Question bank (v2) | `docs/evals/power_industry_probe_v2_bank.json` |
| Machine results | `docs/evals/power_industry_probe_v2_results.json` |
| Human report | `docs/evals/power_industry_probe_v2_report.md` |
| Runner | `scripts/run_power_industry_probe_v2.py` |

Re-run:

```bash
PYTHONPATH=backend:. python3 scripts/run_power_industry_probe_v2.py
```

**Operator decision carried in (unchanged from v1):** for T2 (out-of-catalog / guided) do **not** categorically block execution. Block **only** when the answer is dangerous / violates guardrails (unsafe enforcement, forbidden SPL, injection, fabricated live results, unsupported compromise claim). Otherwise ship the solution (guidance + candidate SPL).

---

## 2. Probe corpus v2 (10 disjoint questions)

| ID | Topic | Tier | Stress axis |
|----|-------|------|-------------|
| pj.001 | DNP3 unsolicited responses from RTU | T2 | out-of-catalog protocol hunt + ambiguous cause |
| pj.002 | Modbus unauthorized write to PLC register | T2 | control-write detection + MITRE overclaim risk |
| pj.003 | USB removable-media bridge (hydro air-gap) | T2 | air-gap bridge + missing endpoint telemetry |
| pj.004 | Substation NTP / IRIG-B time-sync tamper | T2 | timing integrity + cross-device correlation |
| pj.005 | OPC server tag-subscription spike | T1/T2 | analytics + benign-vs-malicious |
| pj.006 | SLDC operator off-shift / impossible travel | T1 | identity anomaly + OT context |
| pj.007 | OT→IT data-diode egress bypass | T2 | egress / exfil + architecture constraint |
| pj.008 | Numerical relay firmware push off-window | T2 | change outside window + missing baseline |
| pj.009 | IT phish → OT jump-host pivot | T2 | IT/OT pivot + multi-signal correlation |
| pj.010 | Renewable inverter Modbus port-502 scan | T2 | internal recon scan + renewable SCADA |

---

## 3. What actually reached the analyst (v2 results)

### 3.1 Heuristic flags

| Flag | v2 | v1 (for comparison) |
|------|----|----|
| `thin_answer` | 5/10 | 9/10 |
| `no_spl_no_checklist` | 5/10 | 9/10 |
| `human_review_only` | 10/10 | 10/10 |
| `scorecard_fail` | 0 | 0 |
| `guided_path` (skill literal) | 0 | 0 |

### 3.2 Per-question quality verdict

| ID | Mode | Domain-correct content? | Verdict |
|----|------|------------------------|---------|
| pj.001 DNP3 | clarification | one-line lab-draft stub only | ❌ thin |
| pj.002 Modbus write | guided_investigation | **yes** — non-502 gateway check, DPI caveat, candidate `T0830/T0885` | ✅ good |
| pj.003 USB bridge | live_investigation | **yes** — media-control policy, Win 6416/EDR gap, candidate `T1091/T0847` | ✅ good |
| pj.004 time-sync | guided_investigation | **no** — generic "firewall/DNS/proxy/endpoint" boilerplate | ❌ wrong-domain |
| pj.005 OPC spike | guided_investigation | **no** — "vendor comm changed / firewall sessions / DNS-proxy" boilerplate | ❌ wrong-domain |
| pj.006 SLDC identity | guided_investigation | **no** — same generic boilerplate as pj.004 | ❌ wrong-domain |
| pj.007 diode egress | guided_investigation | partial — firewall/DNS leg fits egress, but identical canned text | ⚠️ generic-but-plausible |
| pj.008 relay firmware | guided_investigation | **no** — same generic boilerplate | ❌ wrong-domain |
| pj.009 phish→OT pivot | live_investigation | partial — IT→OT firewall checklist good, **phishing leg dropped** | ⚠️ single-leg |
| pj.010 inverter scan | guided_investigation | **yes** — Modbus checklist + scan-≠-intrusion + candidate MITRE | ✅ good |

Good 3 (pj.002/003/010), wrong-domain 4 (pj.004/005/006/008), partial 2 (pj.007/009), thin 1 (pj.001).

---

## 4. Headline finding — the v2 failure mode is sharper than v1

v1 diagnosed **thin answers + render suppression** (SPL exists in payload, card hides it). That is real and still present (pj.001).

v2, with a disjoint corpus, exposes a **more dangerous** dominant mode:

> **Semantic-blind guided boilerplate.** 5/10 questions received one of exactly **two** canned hypothesis+evidence blocks regardless of what was asked. Time-sync tamper (pj.004), SLDC identity anomaly (pj.006), and relay firmware push (pj.008) were all answered with the *same* "Expected operational activity… Firewall, DNS, proxy, and endpoint events" text. OPC tag-spike (pj.005) and diode egress (pj.007) got the *same* "Approved vendor communication changed… Firewall sessions… DNS/proxy context" text.

This is worse than a thin answer because it **looks complete** — `action_count=9`, `scorecard=pass` — while being domain-wrong. An analyst chasing an IRIG-B clock-tamper is handed a DNS/proxy hunt list.

### 4.1 Root cause (code-cited)

`backend/app/chat/guidance_templates.py:177` `build_guided_investigation_guidance()`:

- It is a **2-branch keyword switch**: branch A fires on tokens `ot / scada / chatter / new external / overnight` (line 181); everything else → branch B (line 193).
- It **ignores entities entirely** — `_ = entities` (line 180). DNP3, NTP, IRIG-B, OPC tag, SEL/ABB relay, data diode, Modbus-502 never shape the output.
- Both branches return firewall/DNS/proxy/endpoint evidence — correct for network-beaconing, wrong for timing, identity, firmware, and protocol-command hunts.

So **answer quality ≈ family coverage**: where a real OT family exists (Modbus → pj.002/pj.010, removable-media → pj.003, IT→OT crossing → pj.009), the answer is genuinely domain-correct; where it does not, the guided fallback emits placeholder text dressed as a complete answer.

### 4.2 Comparison summary (v1 plan vs v2 plan)

| Dimension | v1 plan | v2 plan (this) |
|-----------|---------|----------------|
| Corpus | pi.001–010 | pj.001–010 (disjoint) |
| Dominant symptom | thin one-line summaries (9/10) | semantic-blind guided boilerplate (5/10) that *looks* complete |
| Primary lever | render-surfacing fix (`render_sections` hides SPL) | guided generator is entity-blind 2-way switch |
| Risk framing | analyst gets too little | analyst gets confidently-wrong domain guidance |
| Shared conclusion | quality = final card, not path; T2 surface-don't-block | identical |

Both plans agree on direction. v2 adds the stronger, more falsifiable root cause and reorders the workstreams: **fix the guided generator first**, because surfacing more of a wrong-domain answer makes it look *more* authoritative, not better.

---

## 5. Target behaviour (success criteria)

For every probe question and generalised out-of-happy-path OT/grid ask:

1. **Domain-shaped solution card**, in order:
   - One-line framing + tier (T1 catalog / T2 out-of-catalog).
   - Hypotheses + evidence list **derived from the question's actual signal class** (protocol-command, timing, identity, firmware/config-change, removable-media, egress, scan), not a 2-way switch.
   - SPL / search draft when hunt-shaped, even with unresolved slots (lab tier) — and surfaced in the card.
   - Explicit limitations (missing lookup/baseline, telemetry gap, candidate-only MITRE).
   - Direct judgment when asked ("a single write does **not** prove sabotage"; "a port sweep alone is **not** an intrusion").

2. **No generic block when a signal class is identifiable.** If the question names a protocol/scenario we recognise, the guided generator must shape to it or honestly say "no OT family yet for X — here is the generic hunt skeleton and the gap."

3. **T2 execution posture (operator rule).** Block only on guardrail/danger (§7-E). Safe review-only packages and validated candidate SPL ship as the solution; HIL copy says "review package ready," not "cannot execute."

4. **Eval gates the answer, not the path.** Probe `--check` fails when a recognised signal class returns generic boilerplate, or when payload carries SPL the card drops.

---

## 6. Root-cause model (query → solution)

```
Q --> Intent cascade --> Evidence/resource plan --> Route adjudication
   --> SPL/draft/RAG/guided branch --> Validators+sufficiency --> Finalize+AnswerContract --> Analyst card (QUALITY JUDGED HERE)
```

| Stage | Deterministic today | Gap for v2 OOH power asks |
|-------|--------------------|----------------------------|
| Intent | cascade + registry | compound OT asks lack a signal-class label |
| Evidence plan | static intent→boolean | single-leg; no signal-class → evidence-class map |
| Route | 5 skills + guided rescue | falls to guided for anything off-registry |
| Guided generator | **2-way keyword switch, entity-blind** | **the v2 headline defect** (`guidance_templates.py:177`) |
| SPL | templates → lab families → LLM failover (off) | only protocols with a family get a draft |
| Finalize | AnswerContract section flags | still drops artifacts on HIL (v1 finding, still true: pj.001) |

---

## 7. Workstreams (re-ordered vs v1 — guided generator first)

### WS-1 — Signal-class guided generator (highest ROI, replaces v1 WS-A as #1)

**Problem:** `build_guided_investigation_guidance` is a 2-way switch that ignores `entities` and emits firewall/DNS for timing, identity, firmware, protocol-command hunts.

**Tasks:**
1. **1a** Introduce a deterministic **signal-class classifier** over the query+entities: `{protocol_command, timing_integrity, identity_anomaly, change_management, removable_media, egress_exfil, recon_scan, network_beacon}`. Keyword + entity driven, table-based, no LLM on blocking path.
2. **1b** Per class, a **shaped hypotheses+evidence template** (protocol-command → command verbs, master allowlist, baud/poll baseline; timing → NTP/IRIG-B source, GPS health, peer-clock drift; identity → roster/geo/MFA/device; change → maintenance window, approver, baseline diff; removable-media → media policy, Win 6416/EDR USB; egress → diode direction, allowed dst, byte volume; scan → fan-out, port-set, first-seen).
3. **1c** Stop discarding `entities`; pass them into the template (line 180 `_ = entities` is the smoking gun).
4. **1d** Honest fallback: unknown class → generic skeleton **plus** explicit "no specialised OT family for this signal yet" line (no longer pretending completeness).

**Files:** `backend/app/chat/guidance_templates.py`, classifier helper (new), wiring in `backend/app/chat/pipeline.py`.

**Acceptance:** pj.004/005/006/008 each return class-correct evidence; 0/10 questions share identical hypothesis text unless they share a signal class.

---

### WS-2 — Answer surfacing fix (v1 WS-A, retained)

**Problem:** internal SPL/guidance exists but `finalize`/`render_sections` hides it (pj.001 one-line stub; v1 pi.008).

**Tasks:**
1. **2a** When `candidate_spl`/`spl_draft_preview` present, force `render_sections.spl_artifact=true`, populate draft code even if `approved=false`.
2. **2b** Replace status-only strings ("Lab-only draft SPL preview…" as the *entire* message) with a builder that always merges checklist + SPL block + limitations + plain-language HIL reason.
3. **2c** Map `human_review.kind` to analyst-friendly copy (`spl_source_profile_clarification` → "Confirm index/sourcetype for this draft", not "blocked").

**Acceptance:** pj.001 shows hypotheses + draft + gap, not a single HIL line.

---

### WS-3 — OT/power draft-family expansion

**Problem:** good answers (pj.002/003/010) came from families that exist; gaps (DNP3, time-sync, OPC, relay firmware, diode egress) have none.

**Tasks:**
1. **3a** Add lab families: `ot_dnp3_unsolicited_anomaly`, `ot_time_sync_tamper`, `ot_opc_subscription_spike`, `ot_relay_config_push_offwindow`, `ot_diode_egress_bypass`.
2. **3b** Wire matchers on the guided/lab path for DNP3 / IRIG-B / NTP / OPC tag / SEL-ABB relay / data-diode verbs.
3. **3c** Reuse the SPL validator base-search-OR pattern (see memory: regex-pipe gotcha) and regenerate the template review sheet.

**Acceptance:** pj.001/004/005/008/007 produce a domain lab SPL draft + class-correct checklist.

---

### WS-4 — Multi-leg composition (identity + change + correlation)

**Problem:** pj.009 dropped the phishing leg (single-leg firewall checklist only); pj.006 identity ask got network boilerplate.

**Tasks:**
1. **4a** Resource planner emits **multiple evidence legs** with a correlation hint when the question names two domains (phish ∧ jump-host; failure ∧ success; VPN ∧ firewall).
2. **4b** Completeness floor: a two-domain question must list both legs in the card.

**Acceptance:** pj.009 lists the phishing-event leg **and** the OT jump-host access leg with the join key (identity, time window).

---

### WS-5 — T2 execution eligibility + judgment honesty (operator posture)

**Problem:** categorical review-only; HIL reads as execution denial; "is this an attack?" judgment asks (pj.002, pj.010) must answer directly.

**Tasks:**
1. **5a** Separate **review-package HIL** from **execution-gate HIL** in contract + UI copy.
2. **5b** Implement the source-tier rule: tier does not decide executability; guardrail-pass + full slot resolution does (still behind global MCP-off until COE).
3. **5c** Dangerous-answer block stays: unsafe actions, forbidden SPL, injection, fabricated live results — reuse `out_of_set_eval` CRITICAL classes.
4. **5d** Judgment honesty: overclaim-risk questions return an explicit "single write/scan alone does **not** confirm" line (the `build_conceptual_mitre_guidance` pattern already exists — wire it to pj.002/pj.010 shapes).

**Acceptance:** every T2 answer ships a full solution package; execution blocked only on guardrail violation or global MCP-off; no "cannot execute" wording on safe packages.

---

### WS-6 — Eval loop closure

1. **6a** Add `--check` to the v2 runner: fail when a recognised signal class returns generic boilerplate, or payload SPL is dropped from the card.
2. **6b** Keep v1 (pi.*) and v2 (pj.*) banks both in the monthly non-gating report alongside OT-25 and Cisco-50.
3. **6c** Feedback ledger: analyst tags a probe answer → promote to golden when fixed.

---

## 8. Phased rollout

| Phase | Scope | Gate |
|-------|-------|------|
| **P0** (wk 1) | WS-1 signal-class generator + WS-2 surfacing | 0/10 shared-boilerplate; pj.004/005/006/008 class-correct; governance regression green |
| **P1** (wk 2) | WS-3 OT families | pj.001/004/005/008/007 produce lab SPL + checklist |
| **P2** (wk 3) | WS-4 multi-leg | pj.009 two legs; pj.006 identity leg |
| **P3** (COE) | WS-5 execution eligibility | operator sign-off on source-tier rule |
| **P4** (flagged) | LLM prose shaping for unknown classes (sidecar, off blocking path) | EC isolated; deterministic authority |

---

## 9. What not to do

- Do not make the answer card *more prominent* before WS-1 — surfacing a wrong-domain boilerplate harder is a regression.
- Do not widen in-catalog 105/50 behaviour to fix OOH — additive T2 paths only.
- Do not enable MCP execution globally; this is eligibility + shaping, not go-live.
- Do not let the LLM pick route, severity, or MITRE status.
- Do not score by `match_path`/scorecard alone — **the final analyst card is the metric** (v2 proved scorecard=pass on wrong-domain answers).

---

## 10. Immediate next steps

1. Review `docs/evals/power_industry_probe_v2_report.md` next to v1's `power_industry_probe_report.md`.
2. Approve **WS-1** as first PR (signal-class guided generator) — fixes the v2 headline defect with a contained diff in `guidance_templates.py`.
3. Confirm operator T2 execution wording for WS-5.
4. Re-run v2 probe after WS-1+WS-2; target **0 shared-boilerplate, ≤1 thin**.

---

## 11. v3 stress-test — does this plan answer correctly, or need more detail?

To validate the plan we ran a **third disjoint corpus** (pk.001–010), deliberately pushed *beyond* the 8 signal classes in WS-1. Artifacts: `docs/evals/power_industry_probe_v3_bank.json` / `_v3_results.json` / `_v3_report.md`; runner `scripts/run_power_industry_probe_v3.py`.

**Result: 10/10 thin, scorecard `pass` on all 10.** The plan as written would **not** answer these correctly. v3 exposes an axis the plan barely covers.

### 11.1 The missing axis — *answer shape*, not just *signal class*

WS-1 assumes every out-of-happy-path question is a **network hunt** that wants hypotheses + evidence. v3 shows ~half want a **different answer template entirely**. The 2-way switch (and even a richer signal-class switch) cannot produce them because they are not hunts.

| ID | Question shape | What it got | Plan covers it? | Required shape |
|----|---------------|-------------|-----------------|----------------|
| pk.001 | Containment / IR decision ("isolate OT now?") | `_UNSAFE_ACTION_MESSAGE` refusal only | ⚠️ WS-5c blocks *enforcement* — but gives no **decision-support advice** | **IR/containment advisory** shape: staged isolation guidance + "do not auto-enforce" |
| pk.002 | TI advisory → exposure/hunt | generic 3-line "confirm asset criticality" (`else` checklist, `guidance_templates.py:169`) | ❌ no TI-advisory mapping | **TI-advisory→detection** shape: TTP list → what we log → hunt gaps |
| pk.003 | Regulatory reporting (CERT-In/CEA) | "Governed SPL draft ready" — built SPL for a compliance Q | ❌ tried to hunt a policy question | **regulatory/knowledge-recall** shape (no SPL) |
| pk.004 | Log-source health / blind spots | Cisco-generic lab scaffolding | ⚠️ WS-3 could add a family, unnamed | **source-health/coverage** shape: silent-source list |
| pk.005 | Baselining ("what is normal") | thin lab-draft line | ❌ classes are anomaly/hunt, not descriptive | **baselining/descriptive-stats** shape |
| pk.006 | Timeline + causal-link | single-leg firewall checklist | ⚠️ WS-4 multi-leg partial; no chronology output | **timeline reconstruction** shape + causal-link honesty |
| pk.007 | Rogue wireless AP / physical bridge | Cisco-generic scaffolding | ❌ no wireless/physical class | add `wireless_physical` signal class |
| pk.008 | Insider exfil (user-centric DLP) | "review-only mode, confirm index" stub | ⚠️ WS-4 partial; no insider/DLP shape | **insider/DLP** shape (identity ∧ egress, user pivot) |
| pk.009 | Supply-chain firmware cert | `build_conceptual_mitre_guidance` "No — not enough…" | ⚠️ judgment honesty fired (WS-5d) but **no investigation substance** | judgment **+** supply-chain integrity steps |
| pk.010 | Process-aware / grid-physics (AGC freq band) | 1-line "review with grid operations" + lab stub | ❌ no process/physics-aware shape | **process-aware OT** shape (setpoint vs dispatch) |

### 11.2 Conclusion — plan needs a new top layer (WS-0)

WS-1 (signal-class guided generator) is necessary but **insufficient**. It sits one level too low. The plan must add, *above* WS-1:

**WS-0 — Answer-shape (intent-type) router.** Deterministic classifier that first decides the **answer template**, then dispatches to the right builder:

| Answer shape | Builder | Notes |
|--------------|---------|-------|
| `hunt` | WS-1 signal-class guided generator | the current plan body |
| `ir_containment_advisory` | new | staged advice, never auto-enforce (keeps WS-5c block) |
| `ti_advisory_mapping` | new | TTP → logged-today → hunt-gap table |
| `regulatory_knowledge` | knowledge_recall (no SPL) | CERT-In 6-hour rule, CEA guidelines as RAG |
| `source_health` | new / WS-3 family | silent-source coverage list |
| `baselining` | new | descriptive stats SPL (`stats`/`timechart`), not detection |
| `timeline_reconstruction` | wire existing chronology reviewer (`evidence_loop.py`) | + causal-link honesty |
| `insider_dlp` | WS-4 multi-leg, user-pivot | identity ∧ egress around an actor |
| `process_aware_ot` | new | grid-physics framing; defer-to-ops + security overlay |

Rules:
- The shape router runs **before** WS-1; only `hunt` falls through to signal classes.
- Each non-hunt shape still obeys the T2 posture (§5/§7-E): surface the package, block only on guardrail/danger.
- Honest fallback stays: unknown shape **and** unknown signal class → generic skeleton **plus** an explicit "no specialised template for this shape yet" line.

### 11.3 Plan additions (delta to adopt)

1. **Add WS-0** as Phase P0 alongside WS-1 — it is the new first decision and several v3 questions can't be fixed without it.
2. **Extend WS-1 signal classes** with `wireless_physical` (pk.007) and a `process_aware_ot` hook (pk.010).
3. **Extend WS-3 families** to name `source_health` (pk.004) and `supply_chain_firmware_integrity` (pk.009).
4. **WS-4** explicitly owns `timeline_reconstruction` (pk.006) and `insider_dlp` (pk.008) — wire the existing `evidence_loop.py` chronology reviewer for the timeline output.
5. **WS-5d** judgment honesty must be paired with substance: when `build_conceptual_mitre_guidance` fires (pk.009), still attach the shape's investigation steps — never honesty alone.
6. **WS-6 eval** `--check` must assert **answer-shape match**, not just "non-empty": a regulatory question returning an SPL draft (pk.003) is a failure even though it is not "thin."

### 11.4 Bottom line

- v1 corpus → exposed **thin answers** (render suppression).
- v2 corpus → exposed **semantic-blind hunt boilerplate** (entity-blind 2-way switch).
- v3 corpus → exposes **wrong answer-shape entirely** (hunts produced for non-hunt questions; SPL built for a compliance question; refusal-only for a decision question).

The three plans together say the same thing at increasing depth: **route to the right answer shape, shape it to the domain signal, surface the package, block only on danger.** The v2 plan covered the middle layer; **WS-0 (this addition) covers the missing top layer.** With WS-0 added, the plan is sufficient for all 30 probe questions; without it, ~5/10 v3 questions stay wrong regardless of how well WS-1 is built.

---

## 12. Live pipeline code review — LLM usage, skills, telemetry, handover (2026-06-19)

Reviewed the actual live `/chat` node path (`backend/app/chat/pipeline.py` and callees) to confirm the plan is fixing the right layer. **Governance posture is sound everywhere — LLM is strictly advisory, deterministic wins, telemetry is clean, node handover is aligned.** Two config settings (not bugs) blunt T2 quality.

### 12.1 Flow (verified node order)

```
query
 → init_routing       = query understanding (understand_query) + route_skill   [pipeline.py:312]
 → query_to_intent     (build_query_to_intent)                                  [313]
 → evidence_planning   (plan_evidence / plan_path_and_tools)                    [314]
 → discovery_loop / shadow_enrichment = path + tool decision (adjudication)     [315-320]
 → {prepare_rag_only → rag_early → workflow_spl → spl_source_resolve → execution} [322-329]
 → context_finalize    = final answer                                          [332]
```

Routing is two-pass: initial deterministic route in `init_routing`, re-adjudicated at `shadow_enrichment` after intent + evidence are known.

### 12.2 Findings

| Area | Verdict | Evidence |
|------|---------|----------|
| **LLM for intent** | ✅ correct — advisory, deterministic-wins | `graph_node_query_to_intent` (`pipeline.py:532`); sidecar `generate_llm_intent_advisory` gated by `ai_soc_llm_enabled` + `mode!=disabled` (`llm_intent_advisor.py:47-49`); heavy T0 skips (registry ≥0.95, guided rescue, unsafe, clarification, budget) before any call (`pipeline.py:549-574`); `apply_advisory_promotion` only promotes `out_of_registry`→`llm_promoted_with_registry_validation`, registry-validated. |
| **LLM for T2 SPL** | ⚠️ exists, grounded, validated — **but OFF by default** | `generate_llm_spl_fallback` grounded by WS-F `assemble_grounding` (`pipeline.py:3786`), validated downstream, degrade → lab-draft → clarification, never auto-executes. Gated by `_should_use_llm_spl_failover` → `ai_soc_llm_spl_fallback_enabled` default **false** (`pipeline.py:3805-3811`). **T2 LLM breadth never fired in the probes.** |
| **Skills + path/tool decision** | ✅ governance / ❌ T2 quality | `route_skill` deterministic; `adjudicate_route` takes LLM advisory + shadow but **defaults deterministic** (`route_adjudication.py:154`). 5 skills; OOH/T2 → `guided_investigation` rescue → the entity-blind generator (WS-1 defect). |
| **Telemetry** | ✅ correct, best-effort, EC-isolated | `_timed_node` records `node.<name>` + `duration_ms` + status, `try/except` never breaks chat (`pipeline.py:336-377`); `start_trace`/`end_trace` on live path, `status=error` on exception; EC fixture early-return emits no traces. |
| **Node handover** | ✅ keys align; ⚠️ CP-off caveat; flag to verify | Every node returns `{**state, ...}`; `query_to_intent` writes `intent_classification`/`selected_use_case`/`llm_intent_advisory`/`llm_turn_budget`, `evidence_planning` reads exactly those. |

### 12.3 Two posture settings that blunt T2 (config, not bugs)

1. **`ai_soc_llm_spl_fallback_enabled = false`** → the governed LLM T2 SPL producer never runs live. The breadth we want for out-of-catalogue T2 is built and grounded but switched off.
2. **`control_plane_enabled = false`** (default) → `evidence_planning` returns `evidence_plan=None`, only `planning_decision` (`pipeline.py:650-659`). The rich evidence plan + cyclic discovery loop the plan leans on runs **only with CP on**; default posture is degraded to `plan_path_and_tools`.

### 12.4 To-do (add to backlog)

- [ ] **T-1** Decide T2 posture flags. Evaluate flipping `ai_soc_llm_spl_fallback_enabled` (T2 LLM SPL breadth) and `control_plane_enabled` (evidence plan + loop), tied to the §13.5 rule (guardrail-pass + slot resolution decides executability, **not** tier). Document latency impact (sidecar is off the blocking path per memory; confirm).
- [ ] **T-2** WS-1/WS-0 fix the deterministic floor first; only then is flipping T2 LLM meaningful (LLM shapes prose/SPL, deterministic shapes the package). Sequence: deterministic floor → flip flags → measure.
- [ ] **T-3** Verify `llm_intent_advisory` type handover. `pipeline.py:613` stores it as a **dict** (`payload.get("llm_intent_advisory")`), but downstream nodes pass `state.get("llm_intent_advisory")` into functions typed `LLMIntentAdvisory | None`. Confirm no advisory fields are silently dropped (model-vs-dict mismatch); add a type guard or normalize at the boundary if so.
- [ ] **T-4** Add a probe assertion that, when T2 flags are on, the T2 LLM producer actually fired (`llm_fallback_used=true` in `candidate_spl`) for out-of-catalogue questions — so "T2 breadth on" is observable in telemetry, not assumed.
- [ ] **T-5** Telemetry: confirm `node.<name>` duration steps and LLM-sidecar `latency_ms`/outcome appear in `/debug/traces/{id}` for a T2 probe run (spot-check the spine end-to-end).
- [ ] **T-6** Document, in the plan's posture section, that governance is already correct — the T2 quality work is **deterministic floor (WS-0/WS-1) + two flag decisions**, not a routing/authority redesign.
