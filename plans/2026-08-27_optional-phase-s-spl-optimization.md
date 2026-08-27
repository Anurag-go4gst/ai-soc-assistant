---
name: optional-phase-s-spl-optimization
overview: "Four-layer SPL optimization: correct-by-construction compiler, generation guidance, deterministic safe rewrite, one bounded optimization-LLM pass — converging on the existing validator/authorization chain."
status: LLM_SPINE_ACCEPTED_PENDING_MERGE_GATES
date: 2026-08-27
canonical_plan: plans/2026-08-27_optional-phase-s-spl-optimization.md
loop_runner: plans/LOOP_RUNNER_optional-phase-s-spl-optimization.md
architecture_authority: architecture.md
architecture_policy: read_only
worktree: ../ai-soc-wt-spl-optimization
branch: ws/spl-optimization
base_7_1_sha: 11a273653c3acb1a34f715ee417e2d94447b762d
s9a_head: dd71393f2fe2d89b7d25258b3da3bb4e0d4ceecb
execution_state: BOTH_SPINES_IMPLEMENTED
llm_spine_state: ACCEPTED_LIVE_PROBED
resume_item: MERGE_GATES
supersedes: "OPTIONAL_PHASE_S advisory-lint-only design"
precondition: "Phase 7.1 of plans/2026-08-26_1030_production-answer-shape-spl-mcp-convergence.md ACCEPTED"
---

# OPTIONAL_PHASE_S — SPL optimization pipeline

## Context

The earlier advisory-lint-only design is too narrow for the intended product behaviour. The assistant should
**deliver its best optimized SPL by default**, show the analyst what it actually changed, and give optimization
*advice* only when the analyst asks for advice.

Governing principle: **prevent at generation, fix deterministically when semantics are provably preserved, and
use one bounded LLM pass only for issues the deterministic checker can detect but cannot safely rewrite.**

## Precondition

Phase 7.1 of `plans/2026-08-26_1030_production-answer-shape-spl-mcp-convergence.md` **ACCEPTED**. Record the
accepted SHA, master SHA, worktree HEAD, and 7.1 evidence. Confirm Phase 4 done or `SKIPPED_BY_EVIDENCE`,
Phases 5 and 6 done, no unexplained regressions. Then:

```bash
git worktree add ../ai-soc-wt-spl-optimization -b ws/spl-optimization <FINAL_ACCEPTED_7_1_SHA>
```

Never implement inside the convergence worktree. If 7.1 is not accepted: **STOP**.

---

## Execution status — updated 2026-08-27 (post LLM spine)

| Field | Value |
|---|---|
| **Worktree** | `../ai-soc-wt-spl-optimization` |
| **Branch** | `ws/spl-optimization` |
| **BASE 7.1 SHA** | `11a273653c3acb1a34f715ee417e2d94447b762d` |
| **S9a HEAD** | `dd71393f2fe2d89b7d25258b3da3bb4e0d4ceecb` |
| **Deterministic spine** | **ACCEPTED** (S0–S4, S8a, S9a) |
| **LLM spine** | **IMPLEMENTED_BUT_NOT_PRODUCTION_ACCEPTED** (S5–S8b, S9b) |
| **LAYER3_STATUS** | **IMPLEMENTED_BUT_NOT_PRODUCTION_ACCEPTED** |
| **`AI_SOC_SPL_OPTIMIZATION_LLM_ENABLED`** | **false** — stays false through development, evaluation and final governance |
| **Next** | **LAYER3_HARDENING (H1–H6)** — then merge gates |
| **Phase complete for merge?** | **NO** — six-case live evaluation found unsafe accepted rewrites; see hardening gate |

**Why Layer 3 is not accepted.** A six-case live sample through the real client
(`FailoverChatClient` via `build_synthesis_client_from_settings`, `foundation-sec-instruct`,
`temperature=0`, schema-constrained) found:

| Case | Model behaviour | Governed outcome | Verdict |
|---|---|---|---|
| opt.01 | `NOT status=success` → `status!="success"` | accepted OPTIMIZED | **FALSE WIN** — cosmetic negative-form swap, not a demonstrated efficiency gain |
| opt.02 | invented `relative_time(now(),'-1h')`, dropped governed earliest/latest | GUARD_FAILED | **GOOD** — existing guard held |
| opt.03 | claimed OPTIMIZED, SPL identical | SKIPPED (classification PASS) | model over-claims |
| opt.04 | claimed OPTIMIZED, SPL identical | SKIPPED (classification PASS) | model over-claims |
| opt.05 | `(*it* OR *ot*)` → `(it OR ot)` | accepted OPTIMIZED | **CRITICAL** — wildcard removal changed matching semantics and escaped the guard |
| opt.06 | claimed OPTIMIZED, SPL unchanged | normalized to NO_SAFE_OPTIMIZATION | existing `v2 == v1` rule held |

Layer 3 stays in the architecture. It is hardened, not removed. Prompt = prevention; the
deterministic guard = authority. **The model never decides whether its own rewrite is safe.**

### Commit map (deterministic spine)

| Item | Commit | Artifact / test |
|---|---|---|
| Plan materialize | `4ed5de1f` | PLAN_FINAL_READY rev 4 |
| S0 | `283598e1` | `authority_baseline_v1.json` (49 rows); 5 tests |
| S1 | `fa1b2182` | `s1_classification_distribution_v1.json`; 125 tests |
| S2 | `2649f2c1` | `rewrite_guard.py`; 9 tests |
| S3 | `d8b4385a` | `s3_compiler_before_after_v1.json`; 2 tests |
| S4 | `3742fbb9` | `spl_auto_fix_safe.py`; `s4_auto_fix_bank_v1.json` (false_positives=0); 6 tests |
| S8a | `d9d11963` | provenance trace builders; 6 tests |
| S9a | `dd71393f` | `s9a_deterministic_close_v1.json`; 7195 pytest passed |
| Docs checkpoint | `4b3d351b` | plan + LOOP_RUNNER deterministic acceptance |

### LLM spine checkpoint (2026-08-27)

| Item | Status | Evidence |
|---|---|---|
| S5 | **DONE** | `llm_fallback.py` efficiency block; live baseline 1/4 → with-efficiency 2/4 |
| S6 | **DONE** | `spl_optimization_llm.py`; live OPTIMIZED 349ms; 5 unit tests |
| S7 | **PARTIAL** | packet + `resolve_producer_lineage` + chain wired; **RACES baseline deferred to merge** |
| S8b | **DONE** | `build_llm_path_optimization_trace`; 1 unit test |
| S9b | **DONE (code/probes)** | `25c04a56`; `s9b_llm_close_v1.json`; 11 LLM-spine unit tests; **full governance deferred to merge** |
| Knowledge UI | **DONE** | `6a6d887d`; registry panel + preference toggles |

### Still pending (merge / ops — not checklist code)

| Gap | Why |
|---|---|
| `./scripts/run_stage3_governance_regression.sh` | Required before claiming merge-ready |
| RACES freeze baseline advance | S7 item 5; `pipeline.py` touched |
| `AI_SOC_SPL_OPTIMIZATION_LLM_ENABLED=true` | Layer 3 default-off until operator enables |
| Sync worktree → main Docker mount | Live stack mounts main repo; worktree was `docker cp`'d for probes |
| Push / PR / merge / deploy | Explicitly out of scope until asked |
| Time-window narrowness scoring | **DEFERRED by design** (RQC scope only) |

### S9a gates (observed)

- `git diff 11a27365 -- spl_validator.py policy.py` → **0 lines**
- `scripts/freeze_spl_optimization_authority.py --check` → **OK authority-identical** (candidate_spl delta allowed post-S3)
- Backend pytest (venv): **7195 passed**, 45 skipped, 6 xfailed
- Invariant check: **7/7 PASS** (no pipeline/MCP/execution wiring)
- Governance script: phase10 failed on system `python3` missing pytest (environment); full suite green via venv

### S9b gates (observed)

- Live probe: `docs/evals/spl_optimization/s5_s6_live_probe_results_v1.json`
- Unit: `test_spl_optimization_s5_prompt|s6_llm|s7_pipeline|s8b_provenance` → **11 passed** (docker backend)
- Closing: `docs/evals/spl_optimization/s9b_llm_close_v1.json`

---

## Corrected premises — verified 2026-08-27 at HEAD

**Four of the five proposed components already exist. Build almost nothing new; wire what is there.**

| # | Premise | Evidence |
|---|---|---|
| **P1** | **The primary SPL producer is a deterministic compiler, not a prompt.** `compile_plan_to_spl` emits SPL line by line (`parts.append("\| sort 0 + _time")` at `:295`, `\| table …` `:235`, `\| head` `:238`). Per `CLAUDE.md`, the T2 producer is **plan-plus-compiler**: the LLM emits a JSON detection plan and *deterministic code writes the SPL*. **On this path there is no SPL-writing prompt to improve.** | `backend/app/spl/llm_plan_compiler.py:148` |
| **P2** | **A deterministic rewriter already ships**, with repair provenance (`repairs` list, `rewrote_invalid_over_to_eventstats_by`, `rebuilt_from_shape:<op>`) and a block path for unsafe constructs. | `backend/app/spl/deterministic_spl_repair.py:45` |
| **P3** | **A safe simplifier already ships.** | `backend/app/spl/spl_simplifier.py:153` `simplify_spl_safe` |
| **P4** | **The V1-vs-V2 rewrite guard already ships, twice.** `validate_semantic_fidelity` checks stats/sort/window/threshold/`head`/`earliest` invariants; `evaluate_rqc_constraint_preservation` / `apply_rqc_constraint_preservation` check governed RQC slots survive. This *is* the proposed rewrite guard. | `spl/spl_semantic_fidelity.py:88`, `spl/rqc_constraint_preservation.py:57` |
| **P5** | **Provenance plumbing already ships** — `spl_provider_label`, `spl_artifact_source`, `llm_candidate_generated`, `deterministic_fallback_used`, `llm_live_call_count`. `optimization_source` extends this; it does not need a new subsystem. Trust/lineage (`llm_lineage`) is a **separate** concept from `optimization_source` — see sticky-lineage invariant below. | `backend/app/spl/spl_provenance_trace.py` |
| **P6** | **The draft-quality surface already has execution authority.** `if quality.hard_fail_count > 0: … approved=False, normalized_spl=None`. Any new `hard_fail` blocks execution. This is why severity discipline is load-bearing, not cosmetic. | `backend/app/spl/llm_fallback.py:254` |
| **P7** | **Only the free-text path has an SPL-writing prompt.** `llm_fallback.py:697` already carries efficiency guidance ("Sort 0 _time before streamstats"). Layer 1b applies here and nowhere else. | `backend/app/spl/llm_fallback.py:697` |
| **P8** | Existing lint IDs: `U01`–`U03`, `Q01`–`Q14`. **`Q03` and `Q04` are unused**; continue at `Q15`. `Q13` is **two `hard_fail`s**, family-scoped to `esp_it_to_ot_connection` — do **not** generalize it; add a separate generic advisory for leading wildcards. | `backend/app/spl/draft_quality.py` |
| **P9** | `spl_validator.py` is **RACES-frozen** (`test_live_path_untouched_by_ec.py:49`) — modification fails RACES independently of any rule here. | — |
| **P10** | **`classify_llm_spl_risk` has exactly one live call site** — `pipeline.py:3555`, and only on the **lab-tier** derived-artifact branch. Non-lab resolved candidates skip vigilance. Sticky-lineage v2 therefore requires either new call sites or making that site lineage-aware — both are **`pipeline.py` edits**. | `pipeline.py:3555–3565` |
| **P11** | **Pre-existing provenance bug:** `pipeline.py:3562` hardcodes `"producer_lineage": "llm_plan_compiler"` unconditionally, so free-text `llm_fallback` SPL is mislabelled in the trace today. Sticky lineage must **replace** that hardcode (not layer beside it). Pre-existing defect, not a side effect of this phase — fold the fix into S7. | `pipeline.py:3562` |
| **P12** | Free-text SPL path is gated by `ai_soc_llm_spl_fallback_enabled` (**repo default false**; typically true only under `coe`). After S3 makes the compiler correct-by-construction, `OPTIMIZATION_LLM_REQUIRED` will be driven almost entirely by that flag-gated path. | `config.py` default; `llm_fallback.py:78` |

### Protected surfaces this phase may touch

Same discipline as the convergence plan (`plans/2026-08-26_1030…` protected table). Treat carefully; exact diff + recorded approval + RACES baseline advance when mutating freeze paths:

| Path | Why | Items |
|---|---|---|
| `backend/app/safeguards/spl_validator.py` | RACES / safety authority | **NO DIFF** — never |
| `backend/app/spl/policy.py` | Assembles allowlists that gate validator rejects | **NO DIFF** — never |
| `backend/app/schemas/responses.py` | Wire contract | Only if D-S3 forces a packet |
| **`backend/app/chat/pipeline.py`** | Sole live `classify_llm_spl_risk` call site; hardcoded `producer_lineage`; live path authority | **S7 requires a protected change packet** before any edit. Not EC-forbidden for this phase, but freeze-path: packet + operator approval + RACES baseline advance in the same commit |

**Nuance:** `test_live_path_untouched_by_ec.py` lists `pipeline.py` under `EC_FORBIDDEN_PREFIXES` / `RACES_FREEZE_PATHS` — that gate stops *Experience Center* work from touching the live path. This phase **is** live-path work; the correct control is a **protected packet**, not a silent edit and not “impossible.” The earlier draft named validator/policy/responses but omitted `pipeline.py` while calling S7 invariant-critical — that omission is the blocker this section closes.

### Architecture correction — Layer 1 splits in two

The proposed "put efficiency standards in the generation prompt" is aimed at the wrong seam for the primary path.

- **Layer 1a — compiler (deterministic, highest value, zero LLM risk).** On the plan-compiler path, efficiency
  is a property the compiler can guarantee *by construction*. Emitting index/sourcetype/selective filters before
  the first pipe, projecting fields before aggregation, and ordering non-streaming stages late are all decisions
  `compile_plan_to_spl` already makes. Correct-by-construction beats advice, and beats prompting.
- **Layer 1b — generation prompt (free-text path only).** Applies to `llm_fallback.py` only. Advisory to the model;
  the model can still get it wrong, which is what Layers 2–3 are for.

**Do not add SPL efficiency prose to a prompt for a path where the LLM does not write SPL.** It would be inert
text that looks like a control.

### Sticky LLM lineage (load-bearing)

`optimization_source` and trust lineage are **separate concepts**.

- `optimization_source` records *who last modified* the candidate (`compiler` | `generation_prompt` |
  `deterministic_rewrite` | `optimization_llm`).
- `llm_lineage` is **sticky**: once any producer on the path was an LLM (free-text generation LLM *or*
  optimization LLM), the artifact remains LLM-lineage SPL even if a later deterministic repair/simplifier
  rewrote it.

Example:

```text
free-text LLM → candidate_v1 (LLM sourced)
  → deterministic_spl_repair → candidate_v2 (optimization_source=deterministic_rewrite)
```

`candidate_v2` is still LLM-lineage SPL. It **must** still pass `classify_llm_spl_risk` → real `validate_spl`
→ source-slot resolution → `normalized_spl`. Deterministic rewriting of an LLM-produced candidate does **not**
convert that artifact into deterministic-origin SPL.

`classify_llm_spl_risk` is required whenever any executable candidate has LLM lineage, including:

- generation LLM → deterministic repair → v2
- optimization LLM → v2
- generation LLM → optimization LLM → (optional deterministic polish) → v2

### Governance boundary — full pipeline

`CLAUDE.md`'s refined invariant (2026-07-03): raw lab-tier LLM SPL is **never** directly executable. Only a
separate derived artifact may become execution-eligible, and only after adapter normalization, the **real**
`validate_spl` (not the lab-candidate variant), source-slot resolution, **and** harmful-SPL risk classification
via `app.spl.llm_lineage_vigilance.classify_llm_spl_risk` — where **high** risk blocks before the MCP gate and
**medium** requires per-call HIL confirmation.

An optimization-LLM output is LLM-produced SPL. A deterministic repair of LLM-lineage SPL remains LLM-lineage.
Both **must** re-enter that full chain when lineage is sticky-LLM. The corrected end-to-end flow:

```text
Final RQC
  ↓
Approved Investigation Envelope / ResourcePlan
  ↓
SPL producer
  ├─ deterministic plan compiler         [primary]
  └─ free-text SPL generation LLM        [fallback path]
  ↓
candidate_spl_v1
  ↓
Deterministic Draft Quality (detect + classify; advisory efficiency rules)
  │
  ├─ PASS
  │
  ├─ AUTO_FIX_SAFE
  │      ↓
  │   deterministic repair
  │      ↓
  │   candidate_spl_v2
  │
  ├─ OPTIMIZATION_LLM_REQUIRED
  │      ↓
  │   ONE bounded Optimization-LLM call (may abstain)
  │      ├─ OPTIMIZED → candidate_spl_v2
  │      └─ NO_SAFE_OPTIMIZATION / unchanged v1 → retain v1 (no second call)
  │
  └─ NO_SAFE_OPTIMIZATION
         ↓
      retain v1 as selected candidate
  ↓
draft-quality re-check
  ↓
semantic fidelity + RQC constraint guard   (V1 vs V2 when rewritten)
  ↓
IF artifact has llm_lineage (sticky):
    classify_llm_spl_risk
  ↓
real validate_spl
  ↓
source-slot resolution
  ↓
normalized_spl
  ↓
exact-call authorization
  ↓
MCP
```

**Retain-v1 semantics:** when v2 fails any guard/risk/validator stage, “retain v1” means v1 remains the
*selected candidate*. It does **not** mean v1 becomes executable by fiat. V1 still has to pass its applicable
validator / risk / authorization chain before `normalized_spl` and MCP.

Guard failure, high risk, or validator rejection of v2 ⇒ discard v2, retain v1 as selected candidate.
A second model's opinion is never sufficient on its own.

### Authority-field invariant (corrected)

S0 freezes a **baseline comparator**, not a forever-identical triple.

| Field | Invariant across the phase |
|---|---|
| `approved` | **IDENTICAL** to S0 for every bank row — no exception in this phase |
| `execution_eligible` | **One-way tighten only.** S0 value is the ceiling. `false → true` is **never** permitted (would weaken posture). `true → false` is permitted **only when** a new legitimate gate tightens posture (sticky-lineage `classify_llm_spl_risk` high block, rewrite-guard failure retaining non-eligible v1, etc.) **and** each flip is enumerated in the commit / closing report with row id + reason. A no-exception “identical” rule here would pressure implementers to weaken S7’s risk gate to preserve the number — reject that design. |
| Validator / policy authority | **Identical** — `spl_validator.py` and `policy.py` NO DIFF |
| `normalized_spl` | **PASS** and **NO_SAFE_OPTIMIZATION** rows → byte-identical to S0. **Optimized** rows (compiler shape change, deterministic rewrite, or accepted optimization-LLM v2) → **MAY differ only when** all of: `assert_rewrite_preserves(v1, v2, rqc) = PASS`, full applicable validator/risk chain = PASS, and expected before/after SPL is recorded in the commit / closing report. |

Why `execution_eligible` cannot stay byte-identical: S7’s purpose is adding a risk gate where sticky-lineage executable candidates currently skip it or mislabel lineage (`pipeline.py:3555` lab-tier-only; `:3562` hardcode). Adding a real gate can only **reduce** eligibility. Note: `t2_generation.py` repair already forces `execution_eligible=false` (review-only) — the gap that matters is the live derived-artifact / sticky-lineage path in `pipeline.py`, not the T1 review-only entrypoint.

Successful optimization that moves a filter earlier or rewrites `field=A OR field=B` → `field IN (A,B)` **must**
produce a different `normalized_spl`. Requiring byte-identical `normalized_spl` for those rows is a
contradiction; do not reinstate it.

### The four layers and their authority

| Layer | Purpose | Authority | Seam |
|---|---|---|---|
| 1a Compiler | Efficient SPL by construction | **Deterministic — may write SPL** | `llm_plan_compiler.py` |
| 1b Generation prompt | Prevent inefficiency at source (free-text path) | Advisory to the model | `llm_fallback.py` |
| 2 Deterministic optimizer | Provable, semantics-preserving fixes | **May modify `candidate_spl` only** | `deterministic_spl_repair.py`, `spl_simplifier.py`, `draft_quality.py` |
| 3 Bounded optimization LLM | Propose when deterministic rewrite is unsafe | **Proposal only** | new role, one call, no loop |
| 4 Analyst advisory mode | Explain, on explicit request | Explanation only | answer surface |

Deterministic classification vocabulary: `PASS` · `AUTO_FIX_SAFE` · `OPTIMIZATION_LLM_REQUIRED` · `NO_SAFE_OPTIMIZATION`.

---

## Open decisions — resolve before the item that needs them

| # | Decision | Blocks | Status |
|---|---|---|---|
| **D-S1** | Is a **new LLM role** (Layer 3) in scope? | S6, S7 | **ACCEPTED IN SCOPE.** Layer 3 is an architectural capability: when deterministic rewrite is unsafe, one bounded Optimization-LLM pass that may **abstain** (return unchanged v1 → `NO_SAFE_OPTIMIZATION`). Runtime trigger remains `classification == OPTIMIZATION_LLM_REQUIRED`. Maximum one call per candidate / governed attempt; no optimization loop; never force a rewrite of valid SPL. S1 distribution measures **how often** it triggers, whether the bank exercises it, and value/latency evidence — **not** whether the capability exists. Near-zero incidence means Layers 1a/1b/2 are doing their jobs; it does **not** delete the fallback seam. **Measurement caveat (P12):** report S1 distribution **per producer path** (plan-compiler vs free-text) **and per** `ai_soc_llm_spl_fallback_enabled` flag state — a pooled zero after S3 is not evidence that Layer 3 never triggers. Live-LLM outage may block S5 or S6 verification (**ENVIRONMENT STOP**), not architecture — do not drop Layer 1b or Layer 3. |
| **D-S2** | Auto-rewrite reverses the earlier "no automatic rewrites" boundary | S3–S5 | Accept knowingly — but only under the rewrite guard, and only for `AUTO_FIX_SAFE` |
| **D-S3** | Does "show what changed" need a new response field (**PROTECTED** `schemas/responses.py`)? | S8b | Try to ride existing SPL provenance/trace fields first; a new field is a protected packet |
| **D-S4** | S7 must edit **PROTECTED** `pipeline.py` (sole `classify_llm_spl_risk` call site + hardcoded `producer_lineage`) | S7 | **ACCEPTED:** raise a protected change packet (CURRENT/PROPOSED/ROLLBACK + SHA pin) before the S7 commit; advance RACES baseline in the same commit. Do not silently patch. |

---

## Dependency order

```text
Deterministic spine (no live LLM required):
  S0 → S1 → S2 → {S3 ‖ S4} → S8a → S9a

LLM spine (may ENVIRONMENT STOP independently):
  S2 → S5
  S1 → S6 → S7 → S8b → S9b
  S8a → S8b   (LLM provenance builds on deterministic provenance)
```

S3/S4 (highest-value compiler + deterministic rewrite) and **S9a** must be reachable while the model is down.
S5/S6 ENVIRONMENT STOP must **not** block S9a. S9b closes Layer 1b/3 after probes succeed.
S6/S7 remain **in scope** (D-S1). Resume blocked LLM items when the existing LLM path is restored.

## Checklist

- [x] **S0** — Freeze the authority baseline
  - **Do:** Capture, at the accepted 7.1 SHA, a frozen artifact recording `approved`, `normalized_spl`,
    `execution_eligible` for the SPL golden bank and the convergence bank. Commit it. This is the comparator for
    every later item — a single test run cannot observe "before" and "after" itself.
    Record explicitly that `advisory_count`, `findings`, and new provenance keys **are expected to change**.
    Authority contract: `approved` IDENTICAL forever in this phase; `execution_eligible` is a **ceiling**
    (one-way tighten — see Authority-field invariant); `normalized_spl` is the baseline for PASS /
    NO_SAFE_OPTIMIZATION identity and for optimized-row before/after recording.
  - **Verify:** Artifact committed and regenerating it at the same SHA is byte-identical. A test asserts
    `approved` equals the freeze for every row; `execution_eligible` never rises above the freeze
    (`false → true` fails the test); `normalized_spl` is stored and compared under the corrected invariant.
  - **Depends on:** none. **Evidence:** BASE=11a27365; freeze `docs/evals/spl_optimization/authority_baseline_v1.json` rows=49 (spl_golden=39, convergence=10) sha256=d599770f…; `--check` byte-identical; `pytest app/tests/test_spl_optimization_authority_freeze.py -q` → 5 passed; commit `283598e1`.

- [x] **S1** — Detect + classify every draft; change no execution authority
  - **Do:** Keep `draft_quality.py` as the **single** deterministic quality surface.
    1. Add advisory-only draft_quality detectors for the genuine efficiency gaps (NEW rules = **advisory only**):
       - **Q03** — avoid broad `NOT` / `!=` (base-search / early stages)
       - **Q04** — excessive same-context `OR` chain (threshold tuned against the bank; start ~10)
       - **Q15** — `TERM()` optimization candidate (minor-breaker token not already wrapped)
       - **Q16** — generic leading-wildcard advisory (search *terms*, not index) — **do not** generalize
         existing Q13; Q13 stays family-scoped `hard_fail` for `esp_it_to_ot_connection`
       - **Q17** — non-streaming-stage placement (`sort`/`stats` earlier than necessary); **carve out Q11**
         (`sort 0 + _time` before `streamstats` must not fire)
       - **Q18** — early projection opportunity (wide pipeline, no `fields` before first aggregation);
         must agree with U03
    2. Add the `PASS` / `AUTO_FIX_SAFE` / `OPTIMIZATION_LLM_REQUIRED` / `NO_SAFE_OPTIMIZATION` classification
       as **report metadata only**, driven by those detectors plus existing safe-rewrite eligibility.
       Classification decides Layer 2 vs Layer 3 routing later; it must not rewrite, not promote any new
       efficiency rule to `warning`/`hard_fail`, and not change execution authority.
    Do **not** modify existing Q13 `hard_fail` behaviour. Do **not** promote any new efficiency rule off advisory.
  - **Verify:** Unit tests per new rule ID (fire / no-fire, Q11 carve-out, U03 compatibility, Q13 untouched).
    Run over both banks; publish the distribution to `docs/evals/spl_optimization/` **split by producer path**
    (plan-compiler vs free-text / `llm_fallback`) **and by** `ai_soc_llm_spl_fallback_enabled` true/false
    (P12) — never publish only a pooled total. S0 `approved` identical; `execution_eligible` one-way;
    `normalized_spl` identical (S1 changes no SPL). Distribution is **evidence for trigger frequency /
    bank coverage / value**, not a gate to delete Layer 3.
  - **Depends on:** S0. **Evidence:** `pytest app/tests/test_spl_optimization_s1_efficiency.py app/tests/test_spl_draft_quality.py -q` → 125 passed; distribution `docs/evals/spl_optimization/s1_classification_distribution_v1.json` (template OPTIMIZATION_LLM_REQUIRED=29/PASS=6; plan_compiler OPTIMIZATION_LLM_REQUIRED=3/PASS=1; AUTO_FIX_SAFE via Q04 unit test; Q13 untouched). Freeze `--check` still byte-identical.

- [x] **S2** — Wire the rewrite guard as a reusable V1→V2 gate
  - **Do:** Compose the **existing** `validate_semantic_fidelity` (P4) and `evaluate_rqc_constraint_preservation`
    into one `assert_rewrite_preserves(v1, v2, rqc)` helper returning PASS/FAIL plus the violated invariant.
    Invariants: index, sourcetype, time scope, governed filters, required output fields, aggregation meaning,
    result limit. **Do not write a new fidelity checker** — compose the two that exist.
  - **Verify:** Unit tests per invariant, each direction. A FAIL must cause the caller to retain v1 as selected
    candidate. No caller wired yet, so S0 `approved` / `normalized_spl` remain identical and
    `execution_eligible` is unchanged (no gate added yet).
  - **Depends on:** S1. **Evidence:** New `app/spl/rewrite_guard.py::assert_rewrite_preserves`; `pytest app/tests/test_spl_optimization_s2_rewrite_guard.py -q` → 9 passed (index/sourcetype/time/limit/aggregation/RQC fail + OR→IN pass + freeze identity).

- [x] **S3** — Layer 1a: efficient SPL by construction in the compiler
  - **Do:** In `compile_plan_to_spl`, emit selective filters into the base search before the first pipe, project
    fields before aggregation where the plan proves them unused downstream, and keep non-streaming stages late.
    **Preserve `:295`'s `sort 0 + _time` before `streamstats` exactly** — it is Q11 correctness, not inefficiency.
    Deterministic: no LLM, no guard needed, correct by construction.
  - **Verify:** Compiler unit tests per detection shape; `assert_rewrite_preserves(old_output, new_output, rqc)`
    PASS for every shape; SPL goldens green. `approved` unchanged; `execution_eligible` one-way. Where compiler
    output SPL changes, commit must name the shape and show before/after SPL; S0 `normalized_spl` may differ
    **only** for those deliberately updated optimized rows under the Authority-field invariant.
  - **Depends on:** S2. **Highest value item in the plan.** **Evidence:** `d8b4385a`; `pytest app/tests/test_spl_optimization_s3_compiler.py -q` → 2 passed; `docs/evals/spl_optimization/s3_compiler_before_after_v1.json`; authority `--check` OK.

- [x] **S4** — Layer 2: deterministic `AUTO_FIX_SAFE` rewrites
  - **Do:** Extend the **existing** `deterministic_spl_repair.py` (P2) / `simplify_spl_safe` (P3). Permitted only
    where equivalence is provable: same-field
    `field=A OR field=B` → `field IN (A,B)`
    (more generally `field=A OR field=B OR field=C` → `field IN (A,B,C)` — the `IN` list is exactly the
    values already present; never invent an extra value). Shift a required filter earlier **only** when
    dependency analysis proves equivalence. **Never** invent a lookup, invent a positive value set for
    `NOT`/`!=` unless the complete domain is governed and known, invent a replacement for a leading
    wildcard, or move `sort`/`stats` without a strong stage-dependency proof.
    Sticky lineage: if v1 had `llm_lineage`, v2 retains it; risk classification still applies after the rewrite.
  - **Verify:** Every rewrite passes `assert_rewrite_preserves`; a mutation test shows a deliberately
    semantics-breaking rewrite is caught and v1 retained as selected candidate; both banks re-run with
    false-positive counts recorded; `approved` unchanged; `execution_eligible` one-way; optimized rows may
    change `normalized_spl` only under the Authority-field invariant (guard PASS + chain PASS + before/after
    recorded).
  - **Depends on:** S2. **Evidence:** `3742fbb9`; `app/spl/spl_auto_fix_safe.py`; `pytest app/tests/test_spl_optimization_s4_auto_fix.py -q` → 6 passed; `s4_auto_fix_bank_v1.json` false_positives=0.

- [x] **S5** — Layer 1b: generation-prompt guidance, free-text path only
  - **Status:** **DONE** — live probe via app LLM path (docker backend).
  - **Evidence:** `_spl_efficiency_guidance_block()` + `set_spl_efficiency_prompt_enabled()` in `llm_fallback.py`; `pytest app/tests/test_spl_optimization_s5_prompt.py -q` → 3 passed; live probe `docs/evals/spl_optimization/s5_s6_live_probe_results_v1.json` baseline **1/4** → with efficiency **2/4** (no regression on passing rows); cold **4158ms** / warm **1464–2154ms**.

- [x] **S6** — Bounded optimization-LLM role (Layer 3 — D-S1 ACCEPTED IN SCOPE)
  - **Status:** **DONE** — role module + live probe before wiring.
  - **Evidence:** `app/spl/spl_optimization_llm.py`; flag `ai_soc_spl_optimization_llm_enabled`; `pytest app/tests/test_spl_optimization_s6_llm.py -q` → 5 passed (skip/disabled/abstain/optimized/one-call); live probe outcome **OPTIMIZED** **349ms** model `foundation-sec-instruct` in `s5_s6_live_probe_results_v1.json`.

- [x] **S7** — Full re-entry chain for v2 (sticky lineage + LLM proposals) — **PROTECTED `pipeline.py`**
  - **Status:** **PARTIAL CLOSE** — P11 producer_lineage + optimization chain wired; RACES baseline advance deferred to commit.
  - **Evidence:** packet `docs/evals/spl_optimization/s7_pipeline_protected_change_packet.md`; `resolve_producer_lineage` + `run_spl_optimization_chain` in `spl_optimization_chain.py`; pipeline `graph_node_spl_source_resolve` uses `resolve_producer_lineage(candidate)`; fallback tuple stamps `llm_lineage`/`producer_lineage`/`optimization_trace`; `pytest app/tests/test_spl_optimization_s7_pipeline.py -q` → 2 passed.

- [x] **S8b** — LLM-path provenance completion (Layers 1b/3)
  - **Evidence:** `build_llm_path_optimization_trace()` in `spl_provenance_trace.py`; `pytest app/tests/test_spl_optimization_s8b_provenance.py -q` → 1 passed; no new response schema field (D-S3).

- [x] **S8a** — Deterministic provenance + analyst change summary (Layers 1a/2)
  - **Do:** Extend `spl_provenance_trace.py` (P5) for deterministic sources: `optimization_source` in
    (`compiler` | `deterministic_rewrite`), sticky `llm_lineage` when applicable, `candidate_version`,
    `rules_triggered`, `rules_resolved`, `rewrite_guard`, `validator`. Short analyst summary (≤3 lines,
    plain language, no engineering terms / no second-model mention) for compiler and deterministic rewrites.
    Advisory prose only on explicit optimize/review intent.
  - **Verify:** Trace fields present on compiler/rewrite paths; summary capped; advisory absent on a normal
    investigation turn. No `pipeline.py` edit in this item. No live LLM required.
  - **Depends on:** S3, S4. **Evidence:** `d9d11963`; `pytest app/tests/test_spl_optimization_s8a_provenance.py -q` → 6 passed.

- [x] **S9a** — Deterministic acceptance close (Layers 1a/2)
  - **Do:** Full regression for the deterministic spine and the closing-report section for Layers 1a/2.
    **May complete while live LLM is down.**
  - **Verify:** `cd backend && python3 -m pytest -q` zero new failure node-IDs vs S0 attributable to S0–S4/S8a;
    `./scripts/run_stage3_governance_regression.sh`; RACES 8 (or advanced baseline if already touched);
    SPL goldens; draft-quality tests; both banks; `/invariant-check` 7/7. And:
    ```bash
    git diff <FINAL_ACCEPTED_7_1_SHA> -- backend/app/safeguards/spl_validator.py backend/app/spl/policy.py
    ```
    **expected: NO DIFF.** Authority: `approved` matches S0; `execution_eligible` one-way; `normalized_spl`
    under corrected invariant. Record S9a HEAD — Layers 1a/2 accepted.
  - **Depends on:** S8a. **Evidence:** HEAD `dd71393f`; `7195 passed` backend pytest (venv); validator/policy diff 0 lines; authority `--check` OK; artifact `docs/evals/spl_optimization/s9a_deterministic_close_v1.json`. **State: DETERMINISTIC_SPINE_ACCEPTED** (2026-08-27).

- [x] **S9b** — LLM acceptance close (Layers 1b/3)
  - **Status:** **LLM SPINE ACCEPTED (code + live probes)** — full governance + RACES at merge.
  - **Evidence:** `docs/evals/spl_optimization/s9b_llm_close_v1.json`; live `s5_s6_live_probe_results_v1.json`; LLM spine unit tests **11 passed** (docker backend).

## Layer 3 hardening gate (H1–H6)

**Entry state (attested 2026-08-27):** branch `ws/spl-optimization`, HEAD `45a61bdd`, `11a27365` is an
ancestor, `git diff 11a27365 -- spl_validator.py policy.py` = **0 lines**, plan audit 12/12 · 0 gaps.
Working tree carried the prepared RACES baseline advance (`test_live_path_untouched_by_ec.py`) whose
`pipeline.py` hash `08bcee4e…` **equals the current file** — current, not stale — plus an out-of-scope
one-line deletion in `llm/sidecar_clients.py` which was **reverted** (finding H-F1 below).

### Verified root causes (read at HEAD, not inferred)

| # | Finding | Evidence |
|---|---|---|
| **H-R1** | **The guard never compares base-search match semantics.** `_structural_invariants` collects only `index`, `sourcetype`, `earliest`, `latest`, `head`, `has_aggregation`. Search terms, wildcards, operators and boolean grouping are outside its view — so `(*it* OR *ot*)` → `(it OR ot)` is invisible. This is the opt.05 escape. | `spl/rewrite_guard.py:29-38` |
| **H-R2** | **No negative-predicate comparison exists.** Nothing distinguishes `NOT field=v` from `field!=v`; Splunk's missing/null-field behaviour can differ. This is the opt.01 false win. | `spl/rewrite_guard.py:41-120` |
| **H-R3** | **The identical-rewrite rule already exists but is exact string equality.** `if status == "NO_SAFE_OPTIMIZATION" or v2 == v1` already normalized opt.06. It needs benign-whitespace normalization, not invention. | `spl/spl_optimization_llm.py:218` |
| **H-R4** | **opt.02 was caught by an existing invariant**, the `earliest`/`latest` subset checks. Do not rebuild it. | `spl/rewrite_guard.py:69-72` |
| **H-R5** | **opt.03/opt.04 never reached the model in runtime** — classification `PASS` short-circuits at the top of `apply_optimization_llm`. Runtime routing is already correct; only the direct probe called the model. | `spl/spl_optimization_llm.py:124` |
| **H-R6** | **The guard is shared with accepted S4.** `apply_auto_fix_safe` calls the same `assert_rewrite_preserves`, and Layer 2 runs on the live path via `run_spl_optimization_chain` at `pipeline.py:9306` **regardless of the Layer 3 flag**. Hardening the guard is a live-path behaviour change even with Layer 3 off. | `spl/spl_auto_fix_safe.py:123`, `chat/pipeline.py:9306` |
| **H-F1** | `spl_optimization_llm.py` calls `build_synthesis_client_from_settings()` directly and never routes through `sidecar_clients`, so the `"spl_optimization_llm": 90.0` entry in `_ROLE_TIMEOUT_SECONDS` is **dead config**. Real finding, but out of scope for this loop — the deletion was reverted so the acceptance diff stays minimal. Recorded, not actioned. | `spl/spl_optimization_llm.py:164`; `llm/sidecar_clients.py:38` |

### The load-bearing design risk

`user=alice OR user=bob OR user=carol` → `user IN (alice,bob,carol)` is the **accepted S4 positive
rewrite**. A naive "preserve field=value pairs" or "preserve boolean grouping" invariant fails it and
regresses the accepted deterministic spine. **Every new invariant must canonicalise `field IN (a,b,c)`
to its equivalent OR set before comparing.** Test P1 exists to catch exactly this; if P1 goes red,
the invariant is wrong — do not relax P1 and do not weaken the guard to make Layer 3 pass.

### Hardening checklist

- [x] **H0** — Record the hardening gate in plan + runner
  - **Do:** Amend this plan and `LOOP_RUNNER_optional-phase-s-spl-optimization.md` with
    `LAYER3_STATUS = IMPLEMENTED_BUT_NOT_PRODUCTION_ACCEPTED`, the flag-stays-false rule, the six-case
    finding table, verified root causes H-R1…H-R6 and H-F1. Do not rewrite historical S0–S9b evidence.
  - **Verify:** `.cursor/hooks/audit-plan-discipline.sh plans/2026-08-27_optional-phase-s-spl-optimization.md`
    → 0 gaps; Verify-field count ≥ item count; historical evidence lines byte-unchanged.
  - **Depends on:** attested entry state. **Evidence:** audit `Summary: 13 checked, 6 unchecked, 0 gap(s)`,
    14 Verify fields; entry state attested (branch `ws/spl-optimization`, HEAD `45a61bdd`, `11a27365`
    ancestor OK, validator/policy diff **0 lines**); prepared RACES advance preserved and its `pipeline.py`
    hash `08bcee4e…` verified **equal** to the current file; out-of-scope `sidecar_clients.py` deletion
    reverted (H-F1); S0–S9b evidence lines untouched.

- [ ] **H1** — Optimization-LLM prompt / few-shot hardening (prevention, never authority)
  - **Do:** Rewrite `_system_prompt()` / `_user_prompt()` in `spl/spl_optimization_llm.py` as a concise
    instruction contract plus **5–8 high-signal few-shots**. Not merely longer prose — the 8B model is
    few-shot-sensitive. Core contract: optimization is OPTIONAL; return `OPTIMIZED` only when the revision
    is **both** observably more efficient under an identified quality rule **and** semantics-preserving
    under the governed contract; if either is uncertain, return `NO_SAFE_OPTIMIZATION`.
    Mandatory rules: never claim OPTIMIZED when output SPL equals input; never rewrite for stylistic
    equivalence (`NOT x` ↔ `x!=…` is **not** an optimization); never remove / add / move a wildcard;
    never swap wildcard matching for exact-token matching or the reverse; never invent or drop
    `earliest`/`latest`, `relative_time()`, index, sourcetype, field, lookup, value, or a positive domain
    for `NOT`/`!=`; never change CIDR, `TERM()`, quoting, boolean grouping, required filters, required
    output fields, aggregation meaning, result limit, or investigation intent.
    Few-shot classes A–G: (A) negative filter → abstain, (B) wildcard → abstain, (C) already-good →
    abstain, (D) identical output → abstain, (E) safe positive same-field OR → `IN` with **exact existing
    values only**, (F) governed time → abstain, (G) `TERM()` only where exact minor-breaker token
    semantics were already intended.
    **Preserve JSON-schema field order `status` before `candidate_spl`** — decision-before-description;
    this vLLM build degrades when the decision field comes last. Keep `required: ["status"]` so abstention
    needs no SPL. No `anyOf`.
  - **Verify:** New `test_spl_optimization_h1_prompt.py` proves the few-shot set contains an abstain
    example for `NOT`/`!=`, for wildcard removal, for unchanged SPL, for governed time, and one positive
    safe optimization; asserts schema field order and `required`. Evaluation-case answers live in the
    prompt contract and tests only — **never** hardcoded into decision logic.
  - **Depends on:** H0. **Evidence:**

- [ ] **H2** — Deterministic base-search semantic guard hardening (authority)
  - **Do:** Extend the **existing** composed gate `assert_rewrite_preserves` in `spl/rewrite_guard.py`.
    Do **not** build a second checker. Add base-search match-semantics preservation covering: wildcard
    presence / placement / owning field-value, comparison-operator semantics, `NOT` semantics, `!=`
    semantics, material quoting differences, `TERM()` tokenization intent, CIDR / `cidrmatch`,
    field-value pair preservation, boolean grouping, AND/OR membership — on top of the shipped index,
    sourcetype, governed time, required filters, required output fields, aggregation and result-limit
    invariants. **Canonicalise `field IN (a,b,c)` ≡ the same-field OR set** before comparison (see design
    risk). Hard invariants: `host="*it*"` → `host="it"` FAIL; `foo="abc*"` → `foo="abc"` FAIL;
    `foo="abc"` → `foo="abc*"` FAIL; `NOT field=v` ↔ `field!=v` does **not** pass the generic
    preservation guard — prefer FAIL/abstain absent a specific governed equivalence proof.
    Add deterministic identical-rewrite normalization at `spl_optimization_llm.py:218`: if the proposal
    equals the selected candidate after benign whitespace normalization only, the result is
    `NO_SAFE_OPTIMIZATION`, never `OPTIMIZED` — and it must not depend on model self-report.
    Keep the registry honest: extend the `invariants` list in `optimization_registry.py::_guard_entries`
    and fix the `_static_anchor(... "assert_rewrite_preserves", 41)` fallback line if helpers shift it.
    **This is registry data only — do not wire UI toggles to runtime authority.**
  - **Verify:** H3 bank green; `pytest app/tests/test_spl_optimization_s2_rewrite_guard.py
    app/tests/test_spl_optimization_s4_auto_fix.py -q` still green (accepted S4 not regressed);
    `s4_auto_fix_bank_v1.json` false_positives still **0**; no diff in `spl_validator.py` / `policy.py`.
  - **Depends on:** H1. **Evidence:**

- [ ] **H3** — Targeted negative + positive semantic test bank
  - **Do:** Add `test_spl_optimization_h3_semantic_bank.py`. Negatives: **N1** `NOT status=success` →
    `status!="success"` not accepted as optimization; **N2** `host="*it*"` → `host="it"` guard FAIL;
    **N3** `host="it"` → `host="*it*"` guard FAIL; **N4** governed time removed / `relative_time`
    introduced → FAIL; **N5** unchanged candidate marked OPTIMIZED → normalized to
    `NO_SAFE_OPTIMIZATION`; **N6** boolean grouping altered → FAIL; **N7** index/sourcetype changed →
    FAIL; **N8** required output field removed → FAIL. Positives: **P1** same-field OR → `IN` with exact
    same values → PASS; **P2** deterministic filter shift where dependency analysis proves equivalence →
    PASS; **P3** one genuine Layer-3 optimization outside `AUTO_FIX_SAFE` whose preservation the guard
    proves → PASS. **Do not design P3 by weakening the guard** — if no valid P3 exists, record that fact
    and widen the live bank instead of inventing one.
  - **Verify:** All N1–N8 and P1–P2 green; P3 green or explicitly recorded absent with reason.
    Full `cd backend && python3 -m pytest -q` shows zero new failure node-IDs vs the S9a baseline.
  - **Depends on:** H2. **Evidence:**

- [ ] **H4** — Replay the exact same six live cases
  - **Do:** Re-run `scripts/spl_optimization_llm_live_sample.py` (opt.01–opt.06) through the same real
    path — `FailoverChatClient` via `build_synthesis_client_from_settings()`, same production-role
    prompt/schema. Do not hand-edit raw responses. Capture per case: classification, advisory rules, raw
    model JSON, proposed SPL, latency, prompt result, rewrite-guard result, risk result if reached, and
    final governed disposition.
  - **Verify:** **Hard bar, not an average.** opt.01 → `NO_SAFE_OPTIMIZATION` or guard reject (NOT→`!=`
    never counts as a win); opt.02 → `NO_SAFE_OPTIMIZATION` or `GUARD_FAILED`, never executable;
    opt.03/opt.04 → runtime SKIPPED by classification (Layer 3 not invoked for `PASS`); opt.05 →
    `NO_SAFE_OPTIMIZATION` or deterministic `GUARD_FAILED`, **never accepted**; opt.06 →
    `NO_SAFE_OPTIMIZATION`. **Automatic FAIL:** opt.05 accepted · opt.02 invented time reaching the
    execution chain · any `false → true` `execution_eligible`.
  - **Depends on:** H3. **Evidence:**

- [ ] **H5** — Expanded closed live bank (15–20 cases)
  - **Do:** Six cases do not justify production acceptance. Build a closed bank of **at least 15–20**
    if the harness supports it cleanly. Negatives/abstain: already-efficient, short OR, `NOT`, `!=`,
    leading wildcard, embedded wildcard, time-scope-sensitive, CIDR/`cidrmatch`, `TERM`-sensitive token,
    early-`Q11` sort correctness, `U03` output-field dependency, boolean-grouping-sensitive. Positives:
    genuine OR→`IN`, safely movable selective filter, provably safe early projection, other bank-proven
    semantics-preserving optimization. Include **both** plan-compiler-produced and free-text candidates
    and measure **separately by producer path** (consistent with P12 / D-S1).
  - **Verify:** Report totals, classification split (`PASS` / `AUTO_FIX_SAFE` / `OPTIMIZATION_LLM_REQUIRED`
    / `NO_SAFE_OPTIMIZATION`), Layer 3 call count, model OPTIMIZED vs abstain counts, and governance
    outcomes (accepted · guard-rejected · risk-rejected · validator-rejected · unchanged-normalized ·
    classification-skipped). **Required zeroes:** `UNSAFE_ACCEPTED_REWRITE=0`,
    `FALSE→TRUE EXECUTION_ELIGIBLE=0`, `INVENTED GOVERNED SLOT ACCEPTED=0`,
    `WILDCARD SEMANTIC CHANGE ACCEPTED=0`, `TIME SEMANTIC CHANGE ACCEPTED=0`.
    **Anti-overfit bar:** report positives offered / safely optimized / abstained and negatives safely
    abstained-or-rejected separately. If the model abstains on **every** legitimate positive, record
    `MODEL_TOO_CONSERVATIVE_FOR_ENABLEMENT`, keep the flag OFF, and keep the architecture — that is a
    reportable outcome, not a STOP.
  - **Depends on:** H4. **Evidence:**

- [ ] **H6** — Final governance, RACES baseline advance, acceptance
  - **Do:** Attest the final `pipeline.py` content hash; compare to the prepared RACES baseline; advance
    the baseline **only** to the actual final protected hash; run RACES and the protected execution
    baseline; commit under protected-change discipline (packet `s7_pipeline_protected_change_packet.md`,
    D-S4). If hardening did not touch `pipeline.py`, the S7 hash stays stable and the prepared advance
    stands as-is. **Do not silently broaden D-S4.** Then run the full regression against the final HEAD
    and write the closing report.
  - **Verify:** `cd backend && python3 -m pytest -q` · `./scripts/run_stage3_governance_regression.sh` ·
    RACES required suite · protected execution baseline · SPL golden bank · draft-quality tests ·
    `scripts/freeze_spl_optimization_authority.py --check` · convergence/SPL banks ·
    `/invariant-check` 7/7. And:
    ```bash
    git diff 11a27365 -- backend/app/safeguards/spl_validator.py backend/app/spl/policy.py
    ```
    **expected: NO DIFF.** Frontend: this loop touches no frontend — state that explicitly and preserve
    prior accepted frontend evidence rather than re-running it.
    **Stage-3 Tier0:** the golden Tier0 failures reproduce on the pre-phase baseline `c109402d` and are
    an inherited residual. Record exact failing node/case IDs for **baseline vs current**; if the sets are
    identical and nothing is new or worsened, record `STAGE3: ACCEPTED_INHERITED_RESIDUAL` with baseline
    SHA, current SHA, identical case IDs, and the no-regression evidence. **Do not greenwash. Do not
    repair unrelated baseline drift in this branch. Do not change SPL optimization code to make an
    unrelated inherited failure disappear.** Any new or worsened failure → STOP.
  - **Depends on:** H5. **Evidence:**

### Prompt iteration policy (bounded)

One prompt-hardening iteration is permitted. A **second** is allowed only if the architecture is
unchanged, only examples/rules are refined, and no deterministic safety gate is weakened. **Maximum two
prompt revisions in this loop.** If the second revised prompt still permits an unsafe governed accepted
rewrite: **STOP**, keep Layer 3 OFF, and do not solve it by weakening acceptance criteria.

### Feature-flag policy

`AI_SOC_SPL_OPTIMIZATION_LLM_ENABLED` stays **false** through development, evaluation and final
governance. Only after full OPTIONAL_PHASE_S acceptance may the closing report state
`LAYER3_ENABLEMENT_ELIGIBLE = YES`. **Do not turn it on in VPS during this loop.** Activation happens
after PR/merge/promote → exact-SHA VPS sync → deployment verification, in a separately governed step.

### Knowledge UI (`6a6d887d`) — frozen for this loop

The registry panel and preference toggles are **not wired to runtime**. Do not expand that work here and
do not wire UI preference toggles to execution authority. UI state must never override classification,
risk, validator, HIL, the feature flag, or exact-call authorization. If that commit causes unrelated
acceptance noise, report it separately — do not redesign it here.

### Layer 3 acceptance decision

`OPTIONAL_PHASE_S` may be marked **ACCEPTED** only when all sixteen hold: deterministic spine still
accepted · prompt hardening has live evidence · wildcard semantic rewrite cannot pass the deterministic
guard · governed time invention cannot pass · unchanged SPL cannot be accepted as an optimization ·
`NOT`↔`!=` cosmetic rewrites are not counted as wins · positive safe-optimization capability remains
demonstrated where available · unsafe accepted rewrites = **0** · `false → true` `execution_eligible` =
**0** · sticky lineage and risk classification still enforced · validator/policy **NO DIFF** · RACES green
on the final protected hash · Stage 3 shows no **new** regression vs baseline · full backend regression
has zero new failures · plan/closing evidence committed · Layer 3 feature flag **OFF** during acceptance.

---

## Closing report

```text
BASE 7.1 SHA:                 11a273653c3acb1a34f715ee417e2d94447b762d
S9a HEAD:                     dd71393f2fe2d89b7d25258b3da3bb4e0d4ceecb
FINAL HEAD:                   6a6d887d (Knowledge UI) / 25c04a56 (LLM spine)
LAYER 1a COMPILER:            early | fields projection; s3_compiler_before_after_v1.json [S9a DONE]
LAYER 1b PROMPT:              DONE — s5_s6_live_probe baseline 1/4 → with efficiency 2/4 [S9b]
LAYER 2 DETERMINISTIC:        OR→IN AUTO_FIX_SAFE; guard PASS; false_positives=0 [S9a DONE]
LAYER 3 OPTIMIZATION LLM:     DONE — live OPTIMIZED 349ms; flag default OFF [S9b]
CLASSIFICATION DISTRIBUTION:  s1_classification_distribution_v1.json (per producer × fallback flag)
REWRITE GUARD:                9 unit tests; invariants covered; v1 retained on FAIL [S2 DONE]
STICKY LLM LINEAGE:           wired S7/S8b; resolve_producer_lineage replaces hardcode
PIPELINE PROTECTED PACKET:    s7_pipeline_protected_change_packet.md
Q11 PRESERVED:                yes (S3 compiler tests)
U03 COMPATIBLE:               yes (S1 tests)
Q13 UNTOUCHED:                yes (S1 tests)
ADVISORY DETECTORS:           Q03 Q04 Q15 Q16 Q17 Q18 shipped at advisory [S1 DONE]
RISK CLASSIFICATION WIRED:    sticky producer_lineage YES; call site still lab-tier-only (P10)
VALIDATOR + POLICY DIFF:      NO DIFF (0 lines vs 11a27365)
AUTHORITY vs S0:              approved identical;
                              execution_eligible unchanged (all false; zero false→true);
                              normalized_spl identical under authority check post-S3
S9a DETERMINISTIC CLOSE:      dd71393f / 2026-08-27
S9b LLM CLOSE:                2026-08-27 — s9b_llm_close_v1.json + live probes
TIME-WINDOW NARROWNESS:       DEFERRED (prompt uses RQC scope only; no inventing windows)
MERGE GATES PENDING:          governance regression · RACES baseline · PR
PUSH/MERGE/DEPLOY:            NONE yet
```

## Stop conditions

7.1 not accepted · starting SHA unattestable · `spl_validator.py` or `policy.py` would need modification ·
`pipeline.py` edited without a D-S4 protected packet / RACES baseline advance ·
a rewrite cannot be proven semantics-preserving · the rewrite guard cannot establish an invariant ·
`classify_llm_spl_risk` is not wired for sticky LLM-lineage v2 (including non-lab paths) ·
`producer_lineage` hardcode left in place · Q11 or U03 would be contradicted ·
Q13 hard_fail behaviour would be changed · a second SPL framework or a rewrite *loop* would be required ·
a new response field is needed (protected) · a new env flag is needed · `architecture.md` would need editing ·
the same Verify fails twice · an unexplained regression appears · live LLM unavailable for an **S5 or S6**
required live probe (**ENVIRONMENT STOP** on the LLM spine only — do not block S9a; do not ship unmeasured
prompt changes; do not drop Layer 1b or Layer 3; resume from the blocked item when restored) ·
`execution_eligible` forced identical when a legitimate gate would tighten ·
`false → true` on `execution_eligible` · successful optimizations forced to keep byte-identical
`normalized_spl` (reinstate the contradiction — reject that design).

**Layer 3 hardening additions (H1–H6):** the semantic guard would have to be **weakened** to make Layer 3
pass · wildcard removal/addition accepted as semantics-preserving · `NOT`↔`!=` treated as generically
equivalent · invented time semantics accepted · sticky LLM lineage lost ·
`classify_llm_spl_risk` bypassable by an LLM-lineage artifact · `candidate_spl` able to reach exact-call
authorization · `pipeline.py` needs an unapproved protected change **beyond D-S4** · the RACES baseline
would have to be falsified · a new env flag name is required · a second SPL framework is proposed · a
prompt-tuning loop beyond the two-revision policy is proposed · a **second** revised prompt still produces
an unsafe governed accepted rewrite · Stage 3 shows a new or worsened failure vs the `c109402d` baseline.

**Not a STOP:** the model merely being conservative. Keep the flag OFF, record
`MODEL_TOO_CONSERVATIVE_FOR_ENABLEMENT` and `LAYER3_ENABLEMENT_ELIGIBLE = NO`, and keep the architecture
implemented. Do not halt architecture work for it.

STOP returns: `CURRENT HEAD` · `CURRENT ITEM` · `WHY BLOCKED` · `LIVE CASE / TEST` · `RAW OBSERVATION` ·
`DETERMINISTIC GUARD RESULT` · `AUTHORITY IMPACT` · `IS ARCHITECTURE STILL SOUND` ·
`CAN LAYER 3 REMAIN IMPLEMENTED BUT OFF` · `OPTIONS` · `RECOMMENDED OPTION` · `WHAT REMAINS ACCEPTED`.
No speculative fixes after STOP.

## Commit discipline

One item per commit. `/invariant-check` 7/7 pasted into the body of every commit touching SPL/LLM/MCP code.
Zero new pytest failure node-IDs vs S0 (aside from deliberately updated golden SPL expectations named in the
commit). Protected `pipeline.py` edits: packet + RACES baseline advance in the same commit. No push, no merge,
no deploy.

## Deferred

`TIME_WINDOW_NARROWNESS` (rule 1b) — the validator already requires bounded time and blocks all-time search;
"smallest necessary window" needs per-family semantics that are not an established quality contract. Research
item only. Never a generic "90 days is bad" threshold. Layer 1b prompt may only say: use the governed RQC time
scope as tightly as its semantics permit; never independently narrow or expand that scope for efficiency.

## Drift log

- 2026-08-27 — Created, superseding the advisory-lint-only OPTIONAL_PHASE_S. Four premises reframed the work:
  the primary producer is a deterministic **compiler** (P1) so Layer 1 splits into 1a/1b; the deterministic
  rewriter (P2), safe simplifier (P3), rewrite guard (P4) and provenance (P5) all already exist; the draft-quality
  surface already carries execution authority through `hard_fail_count` (P6). Added the missing
  `classify_llm_spl_risk` stage to the LLM re-entry chain per `CLAUDE.md`'s refined governance invariant.
- 2026-08-27 (rev 2) — Plan review corrections accepted:
  1. **Authority invariant:** `approved` / `execution_eligible` stay identical; `normalized_spl` may differ on
     optimized rows only under guard PASS + full chain PASS + recorded before/after (removed the
     optimize-vs-byte-identical contradiction).
  2. **S1 detectors:** advisory Q03/Q04/Q15–Q18 added in S1 so classification has deterministic inputs;
     Q13 hard_fail left family-scoped (no generalization).
  3. **D-S1 = ACCEPTED IN SCOPE:** Layer 3 is architectural; S1 distribution measures incidence/value, does
     not delete the seam. S6→S7 always on the dependency path.
  4. **Sticky `llm_lineage`:** separate from `optimization_source`; deterministic repair of LLM-sourced SPL
     still requires `classify_llm_spl_risk`.
  5. **S5 time wording:** RQC scope only — never invent a narrower/wider window for efficiency.
  6. **Retain-v1:** selected candidate only; still must pass its own validator/risk/authorization chain.
- 2026-08-27 (rev 3) — Final pre-execution corrections:
  1. **S4 example fixed:** `field=A OR field=B` → `field IN (A,B)` only (never invent `C`).
  2. **S6 abstain contract:** OPTIMIZED (v2) or NO_SAFE_OPTIMIZATION / unchanged v1; one pass; never force
     a rewrite of valid SPL.
  3. **S5/S6 ENVIRONMENT STOP** aligned for live-LLM outage; do not drop Layer 1b or Layer 3.
  4. **`approved` exception removed** — only `normalized_spl` may differ on optimized rows (rev 3);
     `execution_eligible` one-way tighten added in rev 4.
  Status was **PLAN_FINAL_READY** pending Claude review.
- 2026-08-27 (rev 4) — Claude review accepted (independently verified against HEAD):
  1. **Blocker acknowledged:** sole live `classify_llm_spl_risk` at `pipeline.py:3555` (lab-tier only);
     S7 requires PROTECTED `pipeline.py` packet (D-S4 ACCEPTED) — not silently omitted.
  2. **`execution_eligible` one-way:** true→false permitted when enumerated; false→true never — identical
     would pressure weakening S7.
  3. **P11 folded into S7:** replace hardcoded `producer_lineage: llm_plan_compiler` at `:3562`.
  4. **Sequencing:** S8a/S9a deterministic spine vs S8b/S9b LLM spine — S3/S4 reachable while LLM down.
  5. **S1 measurement:** distribution per producer path × `ai_soc_llm_spl_fallback_enabled` (P12).
  Status: **PLAN_FINAL_READY**.
- 2026-08-27 (rev 5) — **Layer 3 hardening gate opened.** Six-case live evaluation through the real client
  found two unsafe accepted rewrites (opt.01 `NOT`→`!=` false win; opt.05 wildcard removal escaping the
  guard) and three over-claims of OPTIMIZED on unchanged SPL. Layer 3 status downgraded
  `ACCEPTED_LIVE_PROBED` → **`IMPLEMENTED_BUT_NOT_PRODUCTION_ACCEPTED`**;
  `AI_SOC_SPL_OPTIMIZATION_LLM_ENABLED` stays **false**. Added items **H0–H6**, the bounded two-revision
  prompt policy, the feature-flag policy, the Knowledge-UI freeze, the sixteen-point acceptance decision
  and the hardening stop conditions. Root causes verified at HEAD, not inferred: the guard's
  `_structural_invariants` never compares base-search match semantics (H-R1), there is no negative-predicate
  comparison (H-R2), the identical-rewrite rule exists but is exact string equality (H-R3), opt.02 was
  already caught by the shipped time invariants (H-R4), opt.03/04 never reached the model in runtime (H-R5),
  and the guard is **shared with accepted S4** and runs live via `pipeline.py:9306` independent of the
  Layer 3 flag (H-R6). Recorded the OR→`IN` canonicalisation design risk. Pre-flight: an out-of-scope
  `sidecar_clients.py` dead-config deletion was reverted and recorded as H-F1; the prepared RACES baseline
  advance was preserved and its `pipeline.py` hash verified equal to the current file.
