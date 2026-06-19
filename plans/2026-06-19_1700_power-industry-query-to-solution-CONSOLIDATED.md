# Plan — Power Industry Query-to-Solution Quality (CONSOLIDATED, T2-forward)

Status: **Proposed** — consolidates two independent plans + a 30-question live probe + a live-code review.
Date: 2026-06-19
Author: Claude (Opus 4.8) for Anurag

## 0. Sources merged

| Source | Corpus | Strength it brings |
|--------|--------|--------------------|
| Cursor plan — `plans/2026-06-19_power-industry-probe-query-to-solution-plan.md` | pi.001–010 + pi2.001–010 | Surfacing fix, OT families, multi-signal, RAG/entity/T1 gaps (WS-G/H/I), T2 audit checklist, execution eligibility, eval loop |
| Claude plan — `plans/2026-06-19_1530_power-industry-probe-v2-query-to-solution-plan.md` | pj.001–010 (v2) + pk.001–010 (v3) | Answer-shape router (WS-0), entity-aware signal generator (WS-1), 20 more disjoint probes, live pipeline code review (§12) |

Both plans reach the **same direction** independently. This plan keeps every workstream from both, removes duplication, and adds the two layers only the v2/v3 work surfaced (answer-shape routing + posture-flag decisions).

Evidence base = **40 live probes** (30 disjoint pj/pk + pi2 overlap set) + per-line code review:
- Banks: `power_industry_probe_bank.json` (pi), `power_industry_probe_bank_2.json` (pi2, Cursor), `power_industry_probe_v2_bank.json` (pj), `power_industry_probe_v3_bank.json` (pk)
- Reports: matching `*_report.md` / `*_results.json` under `docs/evals/`
- Runners: `run_power_industry_probe.py`, `run_power_industry_probe_v2.py`, `run_power_industry_probe_v3.py`
- **Canonical regression set:** pi + pj + pk (30 disjoint). **pi2** = Cursor cross-check bank (overlaps pk/pj on RAG/entity/MITRE — keep for WS-G/H/I gates, do not add a 4th general bank).

---

## 1. Operator decision (carried, unchanged)

For **T2 (out-of-catalogue / guided)**: do **not** categorically block the **solution package** (guidance, checklist, candidate/lab SPL). **Candidate SPL generation and surfacing are never withheld** solely because the question is out-of-catalogue. **MCP execution** remains gated: block only on guardrail-fail / dangerous (unsafe enforcement, forbidden SPL, injection, fabricated live results, unsupported compromise claim) **or** global MCP-off. Candidate SPL is never auto-executed (`execution_eligible=false` until validation + HIL + operator flags). Source-tier does **not** decide executability — guardrail-pass + full slot resolution does (`plans/2026-06-16_1258_spl-cve-mitre-enhancement-plan.md` §13.5, COE-gated).

---

## 2. Consolidated root cause — three layers, one law

Three corpora exposed the defect at increasing depth:

| Corpus | Dominant failure | Layer |
|--------|------------------|-------|
| v1 (pi) | **Thin answers** — SPL exists in payload, card hides it | Render / surfacing |
| v2 (pj) | **Semantic-blind hunt boilerplate** — entity-blind 2-way switch, 5/10 identical text | Signal shaping |
| v3 (pk) | **Wrong answer-shape entirely** — hunt produced for non-hunt Qs; SPL built for a compliance Q; refusal-only for a decision Q (10/10 thin) | Answer-shape routing |

**The law (both plans agree):** *route to the right answer shape → shape it to the domain signal → surface the full package → block only on danger.*

Code-confirmed weak links (Claude §12):
- `build_guided_investigation_guidance` (`guidance_templates.py:177`) is a 2-branch keyword switch that **discards entities** (`_ = entities`, line 180).
- T2 LLM SPL producer exists + grounded + validated (`pipeline.py:3805`) but **did not fire in probes**: code default `ai_soc_llm_spl_fallback_enabled=false`; `.env.example` has `true` but `AI_SOC_LLM_ENABLED=false` blocks all LLM calls in probe posture.
- Rich evidence plan + cyclic loop requires `control_plane_enabled=true` (`pipeline.py:650`). Code default is `false`; **probe runs overlay `.env.example` (`CONTROL_PLANE_ENABLED=true`)** via `sentinel_runtime` — do not confuse probe posture with bare dev defaults.
- Scorecard reports `pass` on wrong-domain / wrong-shape answers → **scorecard is not the metric; the analyst card is.**

---

## 3. Pipeline flow (verified)

```
query
 → init_routing      = query understanding + route_skill        [pipeline.py:312]
 → query_to_intent   (LLM advisory, deterministic-wins)         [313]
 → evidence_planning (plan_evidence / plan_path_and_tools)      [314]
 → discovery_loop / shadow_enrichment = path + tool decision    [315-320]
 → {prepare_rag_only→rag_early→workflow_spl→spl_source_resolve→execution} [322-329]
 → context_finalize  = final answer (QUALITY JUDGED HERE)       [332]
```

Governance posture verified sound: LLM strictly advisory, deterministic wins, telemetry per-node + best-effort + EC-isolated, node handover (`{**state,...}`) keys aligned.

---

## 4. Target behaviour (success criteria)

For every probe and generalised OOH OT/grid ask, the analyst card must:

1. **Route to the right answer shape** (WS-0) before any hunt template.
2. **Shape hunts to the domain signal** (WS-1), entity-aware — no generic block when a signal class is identifiable.
3. **Surface the full package** (WS-2): checklist/hypotheses + SPL draft (even placeholder/lab tier) + limitations + plain-language HIL reason.
4. **Compose multiple legs** (WS-4) when two domains are named; reconstruct timeline + state causal-link honesty.
5. **Answer judgment directly** ("a single write/scan alone does **not** prove sabotage") with substance, never honesty-only.
6. **Honour T2 execution posture** (WS-5): surface package; block only on guardrail/danger.
7. **Be eval-gated on shape + substance** (WS-6), not on path/scorecard.

---

## 5. Consolidated workstreams

WS-0 and WS-1 are the new top + middle layers (Claude); WS-2…WS-6 carry Cursor's WS-A…WS-F with Claude refinements.

### WS-0 — Answer-shape (intent-type) router  *(NEW — Claude v3)*
Deterministic classifier that decides the **answer template** before WS-1 dispatch. Only `hunt` falls through to signal classes.

| Shape | Builder | Probe it fixes |
|-------|---------|----------------|
| `hunt` | WS-1 signal-class generator | most pj.* |
| `ir_containment_advisory` | new — staged advice, never auto-enforce (keep WS-5c block) | pk.001 |
| `ti_advisory_mapping` | new — TTP → logged-today → hunt-gap table | pk.002 |
| `regulatory_knowledge` | knowledge_recall, **no SPL** | pk.003 (CERT-In 6h / CEA) |
| `source_health` | new / WS-3 family | pk.004 |
| `baselining` | new — descriptive stats (`stats`/`timechart`), not detection | pk.005 |
| `timeline_reconstruction` | wire existing `evidence_loop.py` chronology reviewer + causal-link honesty | pk.006 |
| `insider_dlp` | WS-4 multi-leg, user pivot | pk.008 |
| `process_aware_ot` | new — grid-physics framing (defer-to-ops + security overlay) | pk.010 |

Honest fallback: unknown shape **and** unknown class → generic skeleton **plus** explicit "no specialised template yet" line.

**WS-0 hard constraints:**
- **Deterministic only.** The shape router is a deterministic classifier (keyword + entity + intent signals). An LLM advisory **may inform** the candidate shape but **must never decide** it — same authority rule as routing/MITRE (verified §12). No LLM on the shape-selection blocking path.
- **Happy-path bypass (regression guard).** Exact-105 / semantic-105 / catalog matches **skip WS-0 entirely** and keep their current finalize/render path. WS-0 activates only on `out_of_registry` / guided / weak-match paths. This prevents the new top layer from re-shaping in-catalogue 105/50 answers.
- **Multi-shape precedence.** When a question matches more than one shape (e.g. pk.009 = judgment + supply-chain investigation), resolve by fixed precedence: `ir_containment_advisory` > `regulatory_knowledge` > `process_aware_ot` > `insider_dlp` > `timeline_reconstruction` > `ti_advisory_mapping` > `source_health` > `baselining` > `hunt`. Safety/decision/compliance shapes win over hunt; the lower-precedence shape is attached as a secondary section, not dropped.
- **`regulatory_knowledge` honesty.** Reporting-obligation answers (CERT-In 6h, CEA guidelines) are **RAG/KB-cited only**, carry a "verify with compliance/CISO — this is not legal authority" disclaimer, and never fabricate a statutory timeline that is not in the cited KB.

### WS-1 — Signal-class guided generator  *(Claude v2 — replaces the entity-blind switch)*
Deterministic signal-class classifier `{protocol_command, timing_integrity, identity_anomaly, change_management, removable_media, egress_exfil, recon_scan, network_beacon, wireless_physical, process_aware_ot}` over query + **entities** (stop the `_ = entities` discard). Per-class shaped hypotheses + evidence. Fixes pj.004/005/006/008 wrong-domain boilerplate; adds wireless (pk.007) + process-aware (pk.010) hooks.

**Subtask — OT-term extraction (do not assume entities are populated).** Passing `entities` only helps if `query_understanding` actually extracts OT tokens (DNP3, IRIG-B, NTP, GOOSE, MMS, OPC, Modbus, IEC-104, SEL/ABB relay, PMU/PDC, data diode, AGC). Verify the upstream extractor emits these; if not, WS-1 ships its own OT-protocol keyword extractor feeding the classifier. Acceptance includes "each OT token maps to exactly one signal class."

**Files:** `backend/app/chat/guidance_templates.py`, new classifier (+ OT-term extractor if upstream lacks it), wire in `pipeline.py`.

### WS-2 — Answer surfacing fix  *(Cursor WS-A + Claude WS-2)*
When `candidate_spl`/`spl_draft_preview` present → force `render_sections.spl_artifact=true`, populate draft code even if `approved=false`. Replace status-only strings with a builder merging checklist + SPL block + limitations + plain-language HIL reason. Map `human_review.kind` → analyst-friendly copy (`spl_source_profile_clarification` → "Confirm index/sourcetype for this draft", not "blocked"). Fixes pi.008, pj.001/pk.008 stubs.
**Files:** `pipeline.py`, contract/AnswerContract builder, analyst summary skeleton.

### WS-3 — OT/power draft-family expansion  *(Cursor WS-B + Claude WS-3)*
Add lab families: `ot_goose_burst_anomaly`, `ot_remote_switch_restoration_context` (Cursor), `ot_dnp3_unsolicited_anomaly`, `ot_time_sync_tamper`, `ot_opc_subscription_spike`, `ot_relay_config_push_offwindow`, `ot_diode_egress_bypass`, `source_health`, `supply_chain_firmware_integrity` (Claude). Wire matchers; reuse SPL validator base-search-OR pattern (memory: regex-pipe gotcha); regenerate template review sheet.

### WS-4 — Multi-signal / multi-leg composition  *(Cursor WS-C + Claude WS-4)*
Resource planner emits **multiple evidence legs** + correlation hint when two domains named (phish ∧ jump-host, VPN ∧ firewall, failure ∧ success). Completeness floor: two-domain question lists both legs. Explicitly owns `timeline_reconstruction` (pk.006, wire `evidence_loop.py` chronology) and `insider_dlp` (pk.008). Fixes pi.003/pi.007, pj.009, pk.006/008.

### WS-5 — T2 execution eligibility + judgment honesty  *(Cursor WS-E + Claude WS-5)*
Separate **review-package HIL** from **execution-gate HIL** in contract + UI copy. Implement the **spl-cve plan §13.5** source-tier rule (guardrail-pass + slot resolution, not tier, behind global MCP-off until COE). *(Note: "spl-cve plan §13.5" = `2026-06-16` plan; distinct from this plan's own §13.5 "LLM checks (T2)".)* Dangerous-answer block stays via `out_of_set_eval` CRITICAL classes. Judgment honesty paired with substance: `build_conceptual_mitre_guidance` fires + attaches the shape's investigation steps (pj.002, pj.010, pk.009) — never honesty alone.

### WS-6 — Eval loop closure  *(Cursor WS-F + Claude WS-6)*
`--check` mode on all three runners: fail when (a) a recognised signal class returns generic boilerplate, (b) payload SPL is dropped from the card, **(c) answer-shape mismatch** (e.g. regulatory Q returns an SPL draft = fail even if not "thin"). Keep pi/pj/pk banks + OT-25 + Cisco-50 in the monthly non-gating report. Feedback ledger → promote-to-golden when fixed.

---

## 6. Posture-flag decisions  *(NEW — Claude §12, code-grounded)*

Governance is already correct; T2 quality is **deterministic floor + two flag decisions**, not an authority redesign.

- [ ] **T-1** To actually fire the T2 LLM producer, **all** of: `ai_soc_llm_spl_fallback_enabled=true` (already in `.env.example`) **and** `ai_soc_llm_enabled=true` **and** `ai_soc_llm_mode` non-`mock` (live / `openai_compatible`) **and** a reachable provider endpoint. `.env.example` is at `AI_SOC_LLM_ENABLED=false, AI_SOC_LLM_MODE=mock`, so the producer is inert in probes — flag-on alone is not enough. Tie to spl-cve plan §13.5.
- [ ] **T-2** `control_plane_enabled` is **already `true`** in canonical `.env.example` posture (so the rich evidence plan + cyclic loop *did* run in the probes). Open item is **deploy parity**: confirm live/prod runtime matches `.env.example` (CP on); the bare dev default is `false` and degrades to `plan_path_and_tools`. Not "decide to enable" — "confirm prod posture."
- [ ] **T-3** Verify `llm_intent_advisory` dict-vs-model handover (`pipeline.py:613` stores dict; consumers typed `LLMIntentAdvisory`). Normalize at boundary if fields drop.
- [ ] **T-4** Probe assertion: when T2 flags on, T2 LLM producer actually fired (`llm_fallback_used=true`) for out-of-catalogue Qs.
- [ ] **T-5** Spot-check `/debug/traces/{id}`: `node.<name>` durations + LLM sidecar `latency_ms`/outcome present for a T2 run.
- [ ] **T-6 (rollback guard)** Each shared-path WS (WS-0 router, WS-1 generator, WS-2 render) ships behind a guard/flag so a regression is a one-line revert, not a rebuild. WS-0 happy-path bypass (§5) is the primary guard; WS-2 render changes gated so in-catalogue 105/50 cards stay byte-identical.
- [ ] **Sequence:** WS-0/WS-1 deterministic floor first → then flip flags → then measure. LLM shapes prose/SPL; deterministic shapes the package.

---

## 7. Phased rollout

**§14 is the authoritative rollout table** (it adds P0.5/P0.6 for WS-7). This stub is kept only as a pointer — do not maintain two tables. See §14.

---

## 8. What not to do (merged)

- Do not make the card more prominent before WS-0/WS-1 — surfacing a wrong-shape/wrong-domain answer harder is a regression.
- Do not widen in-catalog 105/50 to fix OOH — additive T2 paths only.
- Do not enable MCP execution globally; this is eligibility + shaping, not go-live.
- Do not let LLM pick route, severity, or MITRE status — advisory only, deterministic wins (verified §12).
- Do not score by `match_path`/scorecard — the **final analyst card** is the metric (proven: scorecard `pass` on wrong-shape v3 answers).

---

## 9. Immediate next steps

1. Review the three reports side by side (`_report.md`, `_v2_report.md`, `_v3_report.md`).
2. Approve **WS-0 + WS-1 + WS-2** as the P0 PR — top + middle + surfacing layers; largest analyst impact, contained diffs (`guidance_templates.py`, contract builder, new shape/signal classifiers).
3. COE confirm T2 execution wording (WS-5 / §13.5).
4. Decide T-1/T-2 posture flags (§6) — separate, reversible config calls.
5. Re-run all three probes after P0; target **0 shared-boilerplate, ≤2 thin across 30, 0 shape-mismatch**.

---

## 10. References

- Cursor plan: `plans/2026-06-19_power-industry-probe-query-to-solution-plan.md`
- Claude v2/v3 plan (code review §12, shape router §11): `plans/2026-06-19_1530_power-industry-probe-v2-query-to-solution-plan.md`
- T2 tier decision / §13.5: `plans/2026-06-16_1258_spl-cve-mitre-enhancement-plan.md`
- Resource planner / answer-quality evals: `plans/2026-06-10_0356_skills-llm-mcp-utilization-and-paraphrase-readiness.md`
- Guided generator defect: `backend/app/chat/guidance_templates.py:177`
- T2 LLM producer gate: `backend/app/chat/pipeline.py:3805`; evidence-plan gate: `pipeline.py:650`

---

## 11. Consolidation review (Cursor, 2026-06-19) — bugs fixed, omissions closed

### 11.1 What the consolidated plan gets right

- **Three-layer root cause** (surfacing → signal shaping → answer-shape) matches independent probe evidence.
- **WS-0 before WS-1** ordering is correct — v3 proved signal-class alone cannot fix non-hunt questions.
- **Code citations** on `guidance_templates.py:177` / `_ = entities` are accurate (verified in tree).
- **Scorecard ≠ metric** — essential; both plans and all four banks prove it.
- **Do not surface wrong answers harder** — correct guardrail for P0 sequencing.

### 11.2 Bugs / inaccuracies corrected in this revision

| Issue | Was | Fix |
|-------|-----|-----|
| Operator wording | "SPL generation is never blocked" (ambiguous vs auto-exec) | Clarified: **surface** candidate/lab SPL always for T2; **MCP execution** gated; never auto-execute raw candidate |
| LLM SPL "off by default" | Implied probes ran with fallback off | Code default `false`; `.env.example` has `SPL_FALLBACK=true` but **`AI_SOC_LLM_ENABLED=false`** blocks all LLM in probes |
| Control plane | "default false" without probe caveat | Probes use `sentinel_runtime` → overlays `.env.example` (`CONTROL_PLANE_ENABLED=true`) |
| Corpus count | 30 only | **40 total**: pi(10) + pj(10) + pk(10) + pi2(10); **30 disjoint** for primary gates |
| pi2 bank | Missing from §0 | Added — Cursor `power_industry_probe_bank_2.json` (pi2.*) |

### 11.3 Omissions now added (from Cursor plan)

| Cursor WS | Consolidated home | Notes |
|-----------|-------------------|-------|
| WS-A surfacing | **WS-2** | merged |
| WS-B OT families | **WS-3** | merged |
| WS-C multi-signal | **WS-4** | merged |
| WS-D T2 LLM prose | **P3** + §13 T2 audit | was under-specified as posture flags only |
| WS-E execution/HIL | **WS-5** | merged |
| WS-F eval | **WS-6** | merged |
| **WS-G RAG/playbook surfacing** | **WS-7a** (NEW below) | pi2.001, pk.003 — regulatory/playbook body not just shape router |
| **WS-H entity-bound** | **WS-7b** (NEW below) | pi2.009 — shape router alone insufficient |
| **WS-I T1 headlines** | **WS-7c** (NEW below) | pi2.005/006 — SPL in card but 91-char headline |
| §13 T2 LLM/skills audit | **§13 below** | trace fields + 6-row rubric |
| Implementation blockers | **§11.4** | uncommitted routing work + governance fail |

### 11.4 Implementation blockers (do not start P0 on dirty tree)

Uncommitted backend routing changes on branch `cp-cyclic-evidence-loop` (`pipeline.py`, `skill_router.py`, `select_route_from_understanding.py`, `draft_preview.py`, `guidance_templates.py`) reportedly cause:

- **~4 pytest failures** (routing disagreement telemetry, LLM-assisted connector calls=0, guided advisory drop reasons).
- **Sentinel gate FAIL** (q002,q006,q009,q010,q015 — likely `.env.example` sourcetype expansion + pipeline interaction).
- **eval baseline drift** in `soc_clean_answer_eval_*`, `langgraph_dual_parity_*` (these files are modified in the tree — confirmed).

**Caveat:** the exact counts above are Cursor's and are **current-branch baseline state, not introduced by this plan** — reproduce them at P0 time, do not treat as fixed. The structural facts (dirty tree, modified eval baselines, modified routing files) are confirmed.

**P0 gate must include `./scripts/run_stage3_governance_regression.sh` green** after rebasing or landing routing fixes. Revert unrelated baseline drift before merge.

### 11.5 WS-7 — Cursor-only gaps (fold into P0 / P0.5)

#### WS-7a — RAG / playbook surfacing (Cursor WS-G)
When `answer_mode ∈ {rag_only, knowledge_only_answer}` and SOC-KB hits exist, render playbook steps in the analyst card (not "SPL and MCP are skipped" stub). **No `execution_approval` HIL** on pure knowledge turns. Fixes **pi2.001**, complements **WS-0 `regulatory_knowledge`** for pk.003.

#### WS-7b — Entity / asset-bound investigation (Cursor WS-H)
Detect relay ID / substation / hostname tokens; emit asset-scoped checklist + explicit "compromise not confirmed" line. Optional Environment KB pin for entity-scoped SPL. Fixes **pi2.009** (not fully covered by WS-0 shapes).

#### WS-7c — T1 catalog headline enrichment (Cursor WS-I)
When `render_sections.spl_artifact=true` but `message` is status-only, headline = hunt objective + review-only disclaimer + ≥3 use-case steps. Fixes **pi2.005/006** and pi.006-class answers.

**Revised phase gate (add to §7):** P0.5 = WS-7a; P0.6 = WS-7b/7c after P0.

---

## 12. Corpus inventory and when to stop adding questions

| Bank | IDs | Role | Primary gate? |
|------|-----|------|---------------|
| pi | 10 | v1 thin-answer / render suppression | yes |
| pj | 10 | v2 semantic-blind boilerplate | yes |
| pk | 10 | v3 wrong answer-shape | yes |
| pi2 | 10 | Cursor cross-check (RAG, entity, MITRE, MCP honesty) | secondary (WS-7) |

**Do not add a 5th general bank.** Re-run **pi + pj + pk (30)** after each phase; use **pi2 (10)** for WS-7 regression only. Add ≤5 targeted questions only if a single workstream still fails after implementation.

Combined headline (all banks): governance-safe; analyst-useful **~5/20** on pi+pi2 early banks, **~3/10** good on pj, **0/10** thin on pk pre-WS-0.

### 12.1 Baseline scoreboard (pre-P0, measure deltas against this)

| Bank | thin/weak | wrong-domain or wrong-shape | genuinely useful | scorecard fail |
|------|-----------|-----------------------------|------------------|----------------|
| pi (10) | 9 | — (render-suppressed) | 1 (pi.002) | 0 |
| pj (10) | 5 | 4 wrong-domain + 2 partial | 3 (pj.002/003/010) | 0 |
| pk (10) | 10 | ~5 wrong-shape | 0 | 0 |
| **target post-P0** | **≤2 / 30** | **0 shared-boilerplate, 0 shape-mismatch** | **≥20 / 30** | **0** |

Re-run `pi+pj+pk` after each phase and fill this table; pi2 tracked separately under WS-7.

---

## 13. T2 LLM / skills audit checklist (from Cursor plan — retained)

**Purpose:** Before P3 (LLM prose/SPL shaping), verify what actually runs on six fixed T2 rows. Skills must shape **analyst-visible** sections, not only `selected_skill` label.

### 13.1 Trace fields (capture per question)

| Field | Path |
|-------|------|
| Route | `selected_skill`, `answer_contract.answer_mode` |
| Registry | `query_to_intent.candidate_mappings.match_path`, `routing.routing_provenance.authority_source` |
| LLM intent | `control_plane_trace.llm_advisory_trace` (`llm_called`, `llm_dropped_reasons`) |
| LLM composer | `control_plane_trace.llm_composer` (`llm_composer_used`, skipped reason) |
| Grounding | `control_plane_trace.guided_hunt_grounding` |
| Resource plan | `evidence_plan.resource_plan`, `control_plane_trace.resource_plan_shadow` |
| Render | `answer_contract.render_sections`, `analyst_response.draft_spl_code` |
| Narration | `narration_visibility` |
| HIL | `human_review.kind` |

**Snippet:** see Cursor plan §13 or run via `PYTHONPATH=backend:. python3` chat harness with `sentinel_runtime()`.

### 13.2 Pass/fail rubric (summary)

| Verdict | Criteria |
|---------|----------|
| **PASS** | Domain-relevant checklist/hypotheses OR SPL in card; no governance violations; shape matches question |
| **REVIEW** | Safe but thin or missing one leg |
| **FAIL** | Wrong-domain boilerplate, shape mismatch, empty card with payload artifacts, compromise/live-row fabrication |

### 13.3 Fixed six audit rows

| ID | Bank | Primary gap today | WS |
|----|------|-------------------|-----|
| pi.002 | pi | no SPL in card | WS-2, WS-3 |
| pi.004 | pi | PMU prose only | WS-1, WS-2 |
| pi.007 | pi | wrong family | WS-4 |
| pi.010 | pi | clarification stub | WS-3, WS-0 |
| pi2.008 | pi2 | generic guided | WS-1, WS-3 |
| pi2.009 | pi2 | no entity checklist | WS-7b |

**Baseline (pre-P0):** 0/6 PASS; 2/6 REVIEW; 4/6 FAIL.

### 13.4 Skills checks (T2)

1. `evidence_plan.resource_plan` lists evidence legs beyond route label?
2. Skill contract injects `triage_checklist` into `answer_contract` when `enrichment_driven`?
3. `guided_hunt_grounding` includes skill/SOC-KB chunks, not only MITRE/ATLAS?

**PASS:** ≥1 skill-derived section visible on guided rows. **FAIL:** generic fallback only.

### 13.5 LLM checks (T2)

| Check | PASS when |
|-------|-----------|
| Skip documented | `llm_dropped_reasons` or composer skip reason present |
| Weak-case | Eligible → composer attempted when `AI_SOC_LLM_ENABLED=true` + provider up |
| Authority | LLM does not override severity/MITRE/SPL approval |
| Fallback | Composer failure → deterministic package still complete |
| T2 banner | `limitations` include out-of-catalog / unverified line |

**P3 gate:** ≥4/6 audit rows PASS on §13.2 **after** P0 (WS-0/1/2/7); then enable LLM shaping in lab.

### 13.6 Audit → workstream map

| Finding | WS |
|---------|-----|
| SPL in payload, not card | WS-2 |
| T1 thin headline | WS-7c |
| Playbook body missing | WS-7a |
| Wrong OT family | WS-3 |
| Multi-signal single leg | WS-4 |
| Entity ask generic | WS-7b |
| Generic guided prose | WS-1 (+ WS-D in P3) |
| Wrong answer shape | WS-0 |
| Unsafe/knowledge wrong HIL | WS-5 |
| Skill label only | WS2 (`2026-06-10` plan) + grounding |

### 13.7 Exit criteria

1. Archive trace JSON: `docs/evals/t2_llm_skills_audit_<date>.json`
2. Map every FAIL → one primary WS (§13.6)
3. After P0: ≥4/6 PASS before P3 LLM lab
4. After P3: ≥5/6 PASS including domain relevance + T2 banner

---

## 14. Updated phased rollout (supersedes §7 table)

| Phase | Scope | Gate |
|-------|-------|------|
| **P0** wk1 | WS-0 + WS-1 + WS-2 | 0/30 shared-boilerplate; 0 shape-mismatch on pk; **≤2 thin across the 30**; **in-catalogue 105/50 cards byte-identical** (happy-path no-regression); governance regression **green** |
| **P0.5** wk1–2 | WS-7a RAG surfacing | pi2.001 + pk.003 pass |
| **P0.6** wk2 | WS-7b entity + WS-7c T1 headlines | pi2.009, pi2.005/006 pass |
| **P1** wk2 | WS-3 OT families | pi/pj pk family gaps closed |
| **P2** wk3 | WS-4 multi-leg + timeline | pi.003/007, pj.009, pk.006/008 |
| **P3** wk3–4 | §13 T2 audit + T-1/T-3/T-4 + LLM prose sidecar (WS-D) | ≥4/6 audit PASS; EC isolated |
| **P4** COE | WS-5 execution eligibility (spl-cve plan §13.5) | operator sign-off; MCP global-off unchanged |

---

## 15. References (updated)

- Cursor plan (full WS-G/H/I + audit): `plans/2026-06-19_power-industry-probe-query-to-solution-plan.md`
- Claude v2/v3 plan: `plans/2026-06-19_1530_power-industry-probe-v2-query-to-solution-plan.md`
- pi2 bank: `docs/evals/power_industry_probe_bank_2.json`
- T2 tier / §13.5: `plans/2026-06-16_1258_spl-cve-mitre-enhancement-plan.md`
- Resource planner / skills: `plans/2026-06-10_0356_skills-llm-mcp-utilization-and-paraphrase-readiness.md`
- Guided generator defect: `backend/app/chat/guidance_templates.py:177-180`
- LLM SPL gate: `backend/app/chat/pipeline.py:3805-3811`
- Evidence-plan gate: `backend/app/chat/pipeline.py:650-659`
- Probe posture overlay: `backend/app/evals/sentinel_eval.py` (`sentinel_runtime`)
