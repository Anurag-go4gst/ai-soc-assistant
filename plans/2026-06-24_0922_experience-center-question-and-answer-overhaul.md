# Experience Center — Question Set + Final-Answer Overhaul

**Status:** Implemented (code) — pending operator live capture. See "Implementation status" below.
**Date:** 2026-06-24
**Owner:** Anurag / V.AI SOC
**Branch (target):** new branch off `cp-cyclic-evidence-loop` (or master per release flow)

## Why

The Experience Center (EC) lets a prospect ask a SOC question and see the *exact*
production-shaped answer — full handshake theater (LLM + MCP shown as "called"),
no live LLM/MCP call, answers served from frozen pre-configured output. Two things
are weak today:

1. **Question selection** — both surfaces skew to auth/brute-force. `StarterPrompts.tsx`
   is 7/7 auth prompts; the 14 demo scenarios are ~9/14 auth/login/SOP-auth/MITRE-auth
   near-duplicates. Zero OT/ICS, zero regulatory, no breadth. Audience is **PGCIL /
   power-grid OT + exec** — the set must show platform range, not five flavors of
   "failed login."
2. **Final answers** — answers are hand-maintained fixtures in `app/demo/scenarios.py`
   (2365 lines). They **drift** from the now-better live pipeline (AnswerContract
   sectioning, regulatory T2 shaping, lineage). A prospect who later asks the same
   question in production gets a *different* answer → breaks the "this is what you'll
   see" promise. Depth is also uneven (critical-alerts fixture is rich; simple auth
   ones are thin).

## Decisions (locked with user 2026-06-24)

- **Themes:** OT/ICS + power-grid · Enterprise SOC breadth · Regulatory (CERT-In).
  Auth is NO LONGER the spine — reduced to one representative.
- **Answer source:** capture the **actual end-to-end run** once and freeze it. Two
  layers differ in fidelity and must be labelled honestly:
  - **LLM = real** — genuine on-prem model output, provenance-stamped. This is "the
    actual LLM answer."
  - **MCP = simulated lifecycle** until Splunk MCP goes live — the real search state
    machine (submit→poll→fetch) runs against an **injected `FakeTransport`**, so it is
    NOT a real backend call. Captured rows are representative/honest. `transport=fake`
    is recorded and surfaced; `live_mcp_called` stays `false`.
  - **Latency = real measured**, capped for demo UX (representative replay, not exact).
  EC replays this; EC == production answer shape by construction, refreshable. No
  hand-editing answer prose in `scenarios.py`.
- **Architecture (user):** EC *shows* the full `user query → final result` execution.
  At capture time the **LLM is genuinely invoked** (real call/latency) and the **MCP
  lifecycle genuinely runs against a simulated transport**; demo time replays the
  frozen recording with **no live calls**. Honesty rule: do not claim "real MCP
  called" while `transport=fake` — badge it as **simulated MCP lifecycle replay**. The
  captured LLM prose is the actual model answer (not invented).
- **Posture unchanged:** `live_llm_called=false`, `coe_synthetic_fixture`, MCP exec
  off, do-not-reveal-demo. No new flags ([[flag-posture-all-on-no-new-flags]],
  [[ec-sourced-from-production]]).

## Curated question set (v1 — all produce STRONG production answers)

Probed live `/chat` 2026-06-24; only questions that already answer strongly are in.

| # | Question | Skill (prod) | Why it's in |
|---|----------|--------------|-------------|
| 1 | Investigate failed login spike on APP-01 | spl_generation/auth | Auth keeper: SPL + MITRE + severity |
| 2 | Generate SPL for successful login after failures | spl_generation | Correlation nuance (P2) |
| 3 | Hunt for possible DNS beaconing or C2 from internal hosts | guided/hunt | Threat hunt + SPL |
| 4 | Critical alerts → MITRE rollup → CVE cross-ref (flagship) | alert_summary | Rich triage + honest CVE degrade (covers EDR triage) |
| 5 | What is our CERT-In 6-hour reporting obligation for a suspected OT incident? | knowledge_recall | Regulatory T2 (verified good) — India critical-infra hook |
| 6 | Show the SOP for brute-force investigation | knowledge_recall | Knowledge/RAG |
| 7 | **MITRE require-input → answer** (2-turn, see below) | knowledge_recall | Shows the system asking for required input, then mapping once given |
| 8 | Investigate anomalous Modbus/SCADA traffic to a substation RTU | guided_investigation (review-only) | OT relevance. **Correction (reviewer H2):** OT SPL templates are `enabled=false` (no lookup CSVs yet) — honest guided review-only, NO fabricated SPL. Not "has template." |
| 9 | Review unauthorized access to an OT/ICS HMI at a substation | guided_investigation (review-only) | OT IT-to-OT boundary review; same honest-degrade posture as #8 |
| 10 | Hunt for CI/CD supply-chain compromise (out of catalog) | guided_investigation | Honest out-of-catalog safe degrade |

**Scenario 7 — MITRE require-input → answer (two-turn showcase).** Demonstrates
intelligent input solicitation, not a dead-end refusal:
- **Turn 1:** user asks `Map this alert to MITRE` with no context → system returns
  `intent_clarification` listing the **required input** (alert title / rule name / SPL
  / notable id, or key fields: host, user, source IP, event type, time window).
- **Turn 2:** user supplies it, e.g.
  `Map this alert to MITRE: notable signature=brute_force_success_after_failures index=pgcil_soc sourcetype=pgcil:auth host=APP-01`
  → system returns the real MITRE mapping (candidate techniques + status + evidence).
- Both turns are captured/frozen as one linked scenario (`mitre_mapping_requires_context`
  → `mitre_mapping_auth_alert`); EC plays turn 1, accepts the provided input, then plays
  turn 2. This replaces the bare "honest refusal" with a require-input-then-deliver flow.

**Excluded (degrade thin in prod today — would need governed coverage first):**
bare "critical EDR alert on host X" (thin guided_investigation — flagship #4 covers
it), bare "ransomware hunt" (generic guidance). Add later only if we build real
governed use-cases for them (Track A.5, optional).

## Tracks

### Track A — Curate the question set
- Rewrite the EC scenario registry to the 10 above; remove auth near-duplicates
  (new_source_ip_logins, account_lockouts, success_after_failures_run + air-gapped
  variant, mitre_mapping_requires_context unless kept as a deliberate clarification
  demo, mcp_metadata_discovery — fold or drop).
- Re-bucket `DemoScenarioPicker` categories: **Alert Triage · Threat Hunt · SPL ·
  MITRE · Knowledge & Compliance · OT/ICS · Guided (out-of-catalog)**.
- Ensure `resolve_demo_scenario_id_for_query` aliases cover each curated question so
  a typed prompt matches the frozen scenario (EC parity path).

### Track B — Capture the REAL end-to-end run, freeze it, replay with REAL latency

Goal: each EC scenario is a frozen recording of a genuine `user query → final result`
run — **the actual LLM answer**, the actual MCP search lifecycle (assuming MCP live),
and the **actual per-stage latency** — replayed so it feels like a live production
run, with zero live calls at demo time.

**B1 — Capture harness `scripts/capture_ec_fixtures.py`**
Runs the **real (non-EC) `/chat` pipeline** once per curated question and records
everything. Capture conditions:
- `ai_soc_live_chat_ec_parity_enabled=false` during capture (must hit the live path,
  not the EC early-return). Capture is a separate process from EC serving.
- **LLM = real on-prem llama.cpp** (Foundation-Sec). `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED`
  + `AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED` true → the captured narration is a genuine
  model answer. Answer Guard runs. We freeze the **post-guard, post-authority-override
  final answer** (facts deterministic; only prose is the captured LLM output) — this
  is exactly what production returns, so it is "the actual LLM answer."
- **MCP = simulated search lifecycle via injected `FakeTransport`** ("assuming MCP is
  live", but NOT a real backend call). Reuse the transport-injection path from
  `test_splunk_mcp_transport.py`: submit → bounded poll → fetch genuinely execute,
  producing a real envelope and real-ish poll timing, with representative rows. **No
  fabricated rows** — honest representative result sets per scenario. Record
  `transport=fake` and keep `live_mcp_called=false` (Finding 1). Even if the nested
  lifecycle envelope carries `evidence_source: live` (a state-machine marker), the EC
  top-level truth is `live_mcp_called=false` — that flag wins. Swap `FakeTransport` →
  real Splunk MCP at go-live and `--refresh` (one flag/cred change).

**B2 — What the capture records (per scenario artifact)**
Stored as a versioned artifact `backend/app/demo/captures/<scenario_id>.json`:
- `schema_version` (int) — bumped on any artifact-shape change. **Strict loader
  validation** at import/load: unknown/old version → fallback policy (below), never a
  half-rendered demo (Finding 4).
- `final_response` — the frozen answer **body** (analyst_response, message, SPL,
  MITRE, sources, control_plane_trace, lineage, governance). **Excludes** `trace_id`,
  `turn_id`, timestamps — EC re-stamps those per run (`demo-<id>-<hex>`) so each demo
  looks freshly executed.
- `stage_latencies` — per stage record **both** `recorded_ms` (real measured, from
  trace spine `node.* duration_ms` / LLM `latency_ms` / MCP submit-poll-fetch) **and**
  `replayed_ms` (recorded capped at 5–6 s). Replay uses `replayed_ms`; `recorded_ms`
  kept for honesty/audit (Finding 5: this is *representative* replay, not exact).
- `provenance` — model id (`foundation-sec-1.1-8b-instruct-q8_0`), capture timestamp,
  git sha, prompt hash, `transport=fake|live`, `live_llm_called=true-at-capture`,
  `live_mcp_called=false`. Proves "actual LLM answer from model X on date Y"; drives
  the demo-time provenance badge (Finding 1) and staleness/refresh decisions.

**B2.1 — Loader + fallback policy (fail-safe, Finding 4)**
- Strict loader validates `schema_version` + required keys before serving.
- Fallback chain: **load capture → on missing/corrupt/version-mismatch, fall back to
  the legacy in-code fixture for that scenario → if neither, fail closed with an
  operator-facing error** (never a blank/partial answer in front of a prospect).
- **Contract test** validates every curated artifact loads + schema-validates at
  import time (CI), so a broken artifact is caught before a demo, not during.

**B6 — Provenance badge (Finding 1)**
- EC response/UI surfaces capture provenance: model id + capture date, and an explicit
  **"MCP: simulated lifecycle replay"** label whenever `transport=fake` (vs "MCP: live"
  once real). Language/badges are **gated off provenance**, not hardcoded — so the
  claim auto-corrects when a scenario is re-captured against real Splunk. Keeps the
  do-not-reveal-demo posture for the *answer*, while never overclaiming "real MCP."

**B3 — EC serving**
- `run_demo_scenario` loads the frozen artifact, re-stamps ids/timestamps, returns
  the body. Keeps `live_llm_called=false`, `coe_synthetic_fixture`, EC isolation
  (no telemetry trace). No live LLM/MCP call at demo time.

**B4 — Replay with REAL latency (end-to-end execution feel)**
- `InvestigationProgressPanel` consumes the recorded `stage_latencies` instead of
  synthetic jitter, so the staged playback (query understanding → routing → SPL
  validate → MCP registry→TLS→tools/list→submit sid→poll 1/3..3/3→DONE → LLM
  synthesis → final) advances on the **actual measured durations** of the captured
  run. The existing live elapsed ticker stays. User sees a true end-to-end execution.
- **Latency-cap guard (contention risk):** VPS LLM can spike 30–120s under CPU steal
  ([[vps-llm-cpu-steal-contention]]). Replaying worst-case = a 2-minute dead demo.
  Capture on a **low-contention run** (verify via gen-probe + `vmstat st` first) and
  cap each stage at **5–6 s** (target ~5s/stage). Playback feels like a real run
  (~30–40s total across stages) without dragging. Honest: real recorded latency,
  bounded to a representative-good run.

**B5 — Refresh**
- `--refresh <scenario_id>` re-captures one scenario (after pipeline improves, or when
  real Splunk MCP replaces `FakeTransport`). Durable parity mechanism (quality-loop:
  "fixtures come from captured live runs, not hand-rolled").

**Honesty gate:** no fabricated MCP rows or LLM claims beyond what the real layers
return; OT MITRE=0 stays 0 (no invented technique); representative rows must be
plausible real result shapes for that index/sourcetype.

### Track C — Unify the prompt surfaces
- `StarterPrompts.tsx` pulls its prompts from the same curated scenario list (single
  source of truth) — or remove it in favor of the picker. Kill the hardcoded
  auth-only array.

### Track D — Resolver redesign: aliasing + multi-turn state (Findings 2 & 3)

Current `resolve_demo_scenario_id_for_query` does **exact normalized equality, first
match** (`scenarios.py:82-94`) — brittle to phrasing and stateless. Two changes:

**D1 — Explicit per-scenario alias lists (Finding 3)**
- Add `aliases: list[str]` to `DemoScenario` (normalized at load). Resolver matches the
  incoming normalized query against the union of `query` + `aliases`, not just `query`.
- **Startup uniqueness validation (fail-fast):** assert no normalized alias maps to >1
  scenario; raise on overlap so a collision is caught at boot, not mid-demo.
- Deterministic tie-breaker retained + **logged** if an overlap somehow occurs.
- Unit test: every curated question (and its aliases) resolves to exactly one scenario;
  no alias overlap across scenarios.

**D2 — Multi-turn scenario state (Finding 2 — for scenario 7)**
- Add a deterministic conversation-state FSM keyed by **(session_id, scenario_id)**:
  step 0 = clarification turn, step 1 = answer turn. Stored in the existing chat
  session state.
- Turn 1 query → resolves scenario 7, serves the `intent_clarification` capture, sets
  active step = awaiting-input. Turn 2 (context provided, same session) → advances FSM,
  serves the mapped-answer capture.
- **Invalid/partial turn-2 input:** if the second turn lacks required fields, re-serve
  the clarification (deterministic), don't fall through to a wrong scenario.
- Tests: turn1→turn2 happy path; partial turn-2 re-clarifies; session isolation (two
  parallel sessions don't cross-contaminate step state); reset on new turn-1.
- Keep all other scenarios one-shot (FSM only engages for multi-turn scenarios).

### Track A.5 — (optional, later) close production gaps
- If we want bare-EDR-triage or ransomware questions, first add governed use-cases /
  templates so production answers them strongly, THEN add to EC and capture. Do NOT
  fake EC beyond production.

## Plan review — anomalies & resolutions (2026-06-24, second pass)

| # | Anomaly / bug in v1 | Resolution |
|---|---------------------|------------|
| 1 | "Capture with MCP available" — MCP not live yet | Capture via injected `FakeTransport` (real lifecycle, representative rows); swap to real Splunk + re-capture at go-live |
| 2 | Replaying real worst-case latency = 2-min dead demo (VPS CPU steal) | Capture on low-contention run (gen-probe + `vmstat st` gate) + cap each stage at 5–6 s |
| 3 | EC path is isolated (early-return, no telemetry) — can't capture through it | Capture runs the **non-EC live path** with `ai_soc_live_chat_ec_parity_enabled=false`; separate process from EC serving |
| 4 | Freezing whole response pins `trace_id`/`turn_id`/timestamps | Store answer **body only**; EC re-stamps ids/timestamps per run so each demo looks fresh |
| 5 | LLM output nondeterministic | Freeze the post-guard, post-authority-override final answer (facts deterministic, prose = captured LLM); provenance-stamp model+date+sha |
| 6 | Alias collision risk (two OT questions) could load wrong fixture | Strengthen `resolve_demo_scenario_id_for_query` disambiguation; one alias set per scenario, assert no overlap in a test |
| 7 | Capture LLM answer could leak raw events / secrets into frozen prose | Reuse `_safe_text` sanitizer + redaction on captured artifact; no raw MCP rows in prompt (already enforced) |

## Review pass 3 — code-grounded findings (resolved 2026-06-24)

Validated against `scenarios.py` (`live_mcp_called=false` exists `:49-50`; resolver
exact-normalized first-match `:82-94`).

| # | Finding | Resolution in plan |
|---|---------|--------------------|
| 1 H | "Real MCP run" inconsistent with `FakeTransport` | Decisions + B1 reworded to "simulated lifecycle replay"; B6 provenance badge gated on `transport=fake`; `live_mcp_called=false` always |
| 2 H | Two-turn MITRE under-scoped (no FSM; resolver one-shot) | Track D2: (session,scenario) FSM, step transitions, invalid-turn-2 re-clarify, isolation tests |
| 3 M | Aliasing still collides (exact-equality, first-match) | Track D1: explicit alias lists, fail-fast uniqueness at startup, no-overlap test, logged tie-breaker |
| 4 M | Artifact lacks schema version + fallback | B2 `schema_version` + strict loader; B2.1 fallback chain (capture→legacy fixture→fail closed) + contract test |
| 5 M | Latency cap silently breaks "exact replay" claim | B2 stores `recorded_ms` + `replayed_ms`; framed as *representative* replay, debug-surfaced |

**Open questions — answered:**
- *Fake transport → keep `live_mcp_called=false` unconditionally?* **Yes, always**, even
  if a nested lifecycle envelope says `evidence_source: live`. Top-level EC flag wins.
- */chat/stream parity capture in phase 1?* **No — `/chat` only in phase 1.** Stream
  parity is a later phase; keeps scope tight ([[two-answer-paths-ec-vs-live]]).
- *Enforce "no hand-edited prose" via CI?* **Partial.** CI can't regenerate (no model in
  CI) so it can't diff against a fresh capture. CI enforces: artifact schema-validates +
  loads + provenance present + staleness warning. A `--refresh`+manual-diff stays an
  operator step. Full CI regenerate-and-diff deferred (needs a model in CI).

## Verification

- EC answer for each curated question == a fresh live `/chat` answer for the same
  question (same sections/shape; deterministic facts identical; narration is the
  captured real LLM prose).
- Captured artifact carries provenance (model id, date, git sha, transport) and real
  `stage_latencies`; EC playback advances on those durations (capped).
- End-to-end journey visible: query → routing → SPL → MCP submit/poll/fetch → LLM
  synthesis → final, on real recorded timing.
- `live_llm_called=false`, `coe_synthetic_fixture` on every EC response; no telemetry
  trace emitted from EC path (EC isolated); no live LLM/MCP call at demo time.
- No fabricated rows/claims; OT MITRE=0 stays 0.
- Alias-collision test: each curated question (+ aliases) resolves to exactly one
  scenario id; startup fails fast on any alias overlap.
- Provenance badge: any `transport=fake` scenario shows "simulated MCP lifecycle
  replay"; `live_mcp_called=false` on every EC response regardless of nested envelope.
- Multi-turn FSM: scenario-7 turn1→turn2 happy path; partial turn-2 re-clarifies;
  parallel sessions isolated; new turn-1 resets step.
- Artifact contract test: every curated artifact loads + schema-validates at import;
  fallback chain exercised (corrupt artifact → legacy fixture → fail-closed error).
- Each stage artifact carries `recorded_ms` + `replayed_ms`; replay uses capped value.
- Frontend build green; governance regression green
  (`./scripts/run_stage3_governance_regression.sh`); no new env flags; MCP exec flags
  stay false.

## Open items / risks

- Capture env: on-prem llama.cpp must be reachable + low-contention for the one-time
  capture (real LLM answer). MCP not live yet → capture via injected `FakeTransport`
  (real lifecycle, representative rows); swap to real Splunk + `--refresh` at go-live.
- Latency realism vs demo-drag: replay recorded real latencies but cap per stage; pick
  a low-contention capture window. If contention makes even a single clean capture hard
  ([[vps-llm-cpu-steal-contention]]), capture off-peak or on a quiesced box.
- MITRE coverage for OT questions is thin (technique=0); acceptable/honest for v1.
- Re-capture cadence: refresh artifacts when the pipeline materially improves or model
  changes — provenance stamp tells us staleness.
- **Resolved:** `mitre_mapping_requires_context` is KEPT as the two-turn require-input→
  answer showcase (scenario 7), not dropped. EC must support a linked multi-turn replay
  (turn 1 clarification → accept input → turn 2 answer); confirm the EC chat path can
  carry a second turn against the same session (parity resolver matches both queries).
- **Resolved:** stage latency cap = **5–6 s/stage** (target ~5s), ~30–40s end-to-end.
- **Resolved:** `mitre_mapping_requires_context` is KEPT as the two-turn require-input→
  answer showcase (scenario 7 / FSM family) — implemented in Track D2.

## Implementation status (2026-06-24)

Built by 3 parallel agents (backend / frontend / review) + integration fixes.

**Done (code, validated):**
- Track A — curated 10 pickable scenarios; 7 categories (Alert Triage·Threat Hunt·SPL·
  MITRE·Knowledge & Compliance·OT/ICS·Guided); auth duplicates removed.
- Track D1 — `aliases` field + union match + fail-fast startup uniqueness; tie-breaker
  logged. **Canonical-query resolve = 0 failures** (every button text resolves to self).
- Track D2 — two-turn MITRE FSM (`ec_fsm_store`, `(session_id, family)`): clarification →
  mapped answer; partial re-clarifies; sessions isolated; turn-1 resets.
- Track B (loader) — `capture_loader.py`: `schema_version`, strict loader, fallback chain
  (artifact → legacy fixture → fail-closed), provenance + `ec_provenance` badge
  (`transport=fake` → "simulated MCP lifecycle replay"). `run_demo_scenario` re-stamps
  ids; EC posture preserved (`live_llm_called=false`, `live_mcp_called=false`,
  `coe_synthetic_fixture`).
- Track B (harness) — `scripts/capture_ec_fixtures.py` (`--scenario/--all/--mock-llm/
  --live-llm`, FakeTransport, trace-spine latency read). Validated with `--mock-llm`; no
  artifacts shipped (operator step).
- Track C — `StarterPrompts` now pulls from shared demo scenarios (no auth-only array);
  picker re-bucketed; `InvestigationProgressPanel` consumes `ec_stage_latencies` (jitter
  fallback) + MCP-transport badge.
- Validation: backend pytest 2813 passed; `test_ec_overhaul.py` 21 passed; governance
  regression PASS (soc_clean 120/120, SPL 16/16, power-grid 50/50); frontend build green.

**Integration fixes applied after agents (cross-agent seams):**
- Field-name mismatch: backend `ec_stage_latencies` vs frontend `stage_latencies` →
  frontend aligned to `ec_stage_latencies` (else latency replay was dead).
- **FSM stickiness bug:** an awaiting MITRE family re-served its clarification for ANY
  non-context query, hijacking unrelated questions in the session. Fixed precedence
  (exact match on another scenario wins over sticky re-clarify) + regression test.

**Reviewer findings — disposition:**
- H1 (latency from trace store, not response): harness reads trace spine post-run; EC
  serving still emits no trace. Confirmed in harness design.
- H2 (no Modbus template): resolved — OT scenarios are honest guided review-only (table
  corrected above); no fabricated SPL.
- H3 (EC was stateless): resolved — D2 FSM reads `session_id` in the EC branch.
- M1 (punctuation-exact normalization): button/canonical text resolves (0 failures);
  free-paraphrase typed input is best-effort and falls through to the live pipeline
  (honest). Broaden aliases later if needed.
- M2 (provenance key collision): resolved — capture-time provenance is a distinct
  `ec_provenance` block; the served EC posture flags are unchanged.
- M3 (MCP gate vs FakeTransport): **operator-verify at live capture** — confirm the
  harness splices the lifecycle envelope (gate stays off) rather than needing exec flags.
- M4 (verification equality): softened — deterministic facts/sections match a fresh live
  run; narration is the captured prose (not byte-equal). Drift remedy = `--refresh`.

**Operator follow-up (not done — needs the live model, off-peak/low-contention):**
```
AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED=true AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED=true \
  PYTHONPATH=backend:. python3 scripts/capture_ec_fixtures.py --live-llm --scenario <id>
```
Until run, scenarios serve the legacy fixtures (no `ec_stage_latencies` → jitter
fallback; no live-captured LLM prose). Verify M3 (splice vs gate) on the first capture.

## Tracking

Add to project CLAUDE.md "All plans" table on approval.
