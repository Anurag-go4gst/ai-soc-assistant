# 105-Question Path Honoring — SMB Top-Talkers Analytics (q0.q010)

**Status:** Done (2026-06-09) — all gates green: focused tests 13/13, sample harness 22/22,
backend suite 1591 passed, Tier B `eval_105_path_honoring.py --check` passed (top_n 9/9
spl_review, clarification baseline 72), PowerGrid deterministic eval 50/50 `--check ok`,
frontend build passed.
**Date:** 2026-06-09

## Problem (verified by reproduction)

"Which hosts are generating the most SMB traffic?" → Query Understanding correctly returns
`exact_105_question` / `q0.q010` / `top_n_aggregation` / `aggregate_and_rank`, but:

1. `query_signals.py` has no analytics/ranking phrasing detection → `classify_intent` falls
   to the `clarification_required` fallback.
2. `intent.requires_clarification=True` makes `route_adjudication` force `knowledge_recall`
   *before* its existing exact-105 clause can fire (`_INTENT_COMPATIBLE_WITH_EXACT_105`
   already includes `spl_generation_only` — the adjudicator is fine; intent is the blocker).
3. `clarification_required` → evidence plan `needs_spl=false`, planner path
   `clarification_required`.
4. `decide_severity` returns `P3 Medium` (`default_no_policy`) for any query without an
   active use-case severity policy — including pure analytics questions.
5. `is_firewall_boundary_query` matches bare "smb traffic" → label defaults to
   "IT-to-OT network boundary traffic review".
6. `match_detection_family` has no SMB top-talkers family (only OT-scoped
   `firewall_ot_smb_lateral`), so no lab draft is produced.

## Target end-state matrix

One deliberate deviation from the draft matrix: **no new `path_type` enum value.**
`analytics_spl_review` would be a new planner enum consumed by UI, eval classifiers, and
`guidance_templates` path-type sets — that is an architecture change. Instead analytics
questions ride the existing `spl_review` path, with the analytics nature carried in
existing trace fields (`pattern_type=top_n_aggregation`,
`planning_or_analytic_skill=top_n`, intent reason). Same answer shape, zero enum ripple.

| Query type | Intent family | Path (`path_type`) | SPL | Severity | LLM |
|---|---|---|---|---|---|
| Exact 105 analytics (q0.q010, q0.q002, q0.q017, …) | `spl_generation_only` (new analytics branch) | `spl_review` (analytics markers in trace) | Yes — governed template if bound, else **lab-only draft preview**, review-only, never executed | **"Not assigned from this question alone"** unless alert evidence or active use-case policy | Composer optional; deterministic fallback |
| Exact 105 SOP/playbook | `sop_or_playbook` (unchanged) | `rag_only` | No | Not shown (knowledge profile already suppresses) | Optional |
| Exact 105 MITRE explanation | `mitre_explanation` (unchanged) | `rag_only` answer mode | No | Not shown | Deterministic facts; prose only |
| Exact 105 investigation | `hybrid_alert_review` / `hybrid_investigation_plus_policy` (unchanged) | `hybrid_investigation` / `spl_review_plus_rag` | Yes when evidence needed | Policy-based (severity matrix) | Optional |
| Explicit SPL request | `spl_generation_only` (unchanged) | `spl_review` | Yes | Phase 1: unchanged (P3 default stays). Phase 2 option: extend "Not assigned" guard after PowerGrid eval confirms no severity-wording expectations | Composer skipped for draft-preview answers (existing) |
| Generic SOC guidance | `knowledge_only` (unchanged) | `generic_soc_guidance` | No unless requested | Not shown | Safe fallback |
| Unsafe enforcement | `clarification_required`+HIL (unchanged) | `unsafe_blocked` | No enforcement SPL, draft suppressed (existing `unsafe_enforcement` override) | None | Deterministic block |

### Severity guard scoping (explicit decision)

Phase 1 guard fires only when ALL hold:
- analytics signal (`analytics_aggregation` or `exact_105_analytics`) present,
- no alert context (`alert_context_present=false`, no session alert pin),
- `decide_severity` matched `default_no_policy` (i.e., no active use-case severity policy).

Active severity policies always win. Explicit-SPL-without-alert keeps today's behavior in
Phase 1 to protect PowerGrid-50 green; extending to all no-alert SPL questions is a
follow-up after `run_powergrid_soc_question_eval.py --check` proves no severity-wording
dependency.

### Authority order → code mapping

| Spec rank | Mechanism |
|---|---|
| 1. unsafe/action block | `block_or_contain` / `explicit_run_spl` branches stay first in `classify_intent`; planner `unsafe_blocked`; draft preview suppressed |
| 2. exact 105 match | new analytics branch in `classify_intent` + existing `exact_105_registry` clause in route adjudicator (now reachable) |
| 3. exact catalog match | existing `use_case_review_guidance` / catalog routing (unchanged) |
| 4. near 105/catalog | existing provisional routing (unchanged) |
| 5. explicit SPL intent | existing `spl_generation` branches (unchanged, evaluated before new analytics branch) |
| 6. RAG/SOP/explanation | existing SOP/MITRE/knowledge branches (unchanged, evaluated before new analytics branch) |
| 7. generic SOC guidance | existing `knowledge_only`/fallthrough |
| 8. clarification fallback | stays as final fallback — analytics branch sits immediately above it |

Placement note: the new analytics branch goes **after** all existing branches and **before**
the clarification fallback. That means a 105 question phrased as SOP/MITRE/unsafe keeps its
knowledge/safety path (matrix rows 2/3/7); exact-105 analytics authority only rescues
queries that today die in clarification. This is what keeps PowerGrid-50 behavior frozen.

## End result for q0.q010 (concrete)

- intent: `spl_generation_only`, `requires_clarification=false`, confidence 0.9
- route adjudication: `final_route=attack_discovery` via `exact_105_registry` (execution still disabled)
- evidence plan: `needs_spl=true`, `spl_allowed=true`, `needs_mcp=false`, `answer_mode=live_investigation`
- planner: `path_type=spl_review`, branches `[spl, evidence, severity]`, `execution_enabled=false`
- severity: label "Not assigned from this question alone", rationale "Review type: analytics/query review.", no P3
- label: "SMB traffic analytics" (not IT-to-OT boundary)
- SPL: lab-only draft preview, new `network_smb_top_talkers` family —
  placeholders `<network_index>`/`<network_traffic_sourcetype>`, SMB indicator
  `dest_port IN (445,139) OR app/protocol/service ~ smb|cifs|microsoft-ds`,
  stats by source host/IP: connection count, total bytes (where available), distinct
  destinations, dest ports, first_seen/last_seen; `review_required=true`,
  `execution_eligible=false`, standard draft warning
- MITRE: unchanged gates; registry `mitre_permitted=[T1021.002]` stays metadata-only, no claim

## Final-answer presentation — one synthesis pattern for all answers

Verified UI chain: `ChatBubble` → `AnalystResponseCard` (structured phase timeline driven by
`AnswerContract.section_order` / `render_sections` through `apply_final_answer_readability`).
The structured layout already exists; one-paragraph answers happen when the chain is bypassed:

- `pipeline.py` builds the `AnswerContract` only when `control_plane_enabled` or a catalog
  evidence plan exists → uncovered questions (like q0.q010) render without sections.
- `apply_draft_preview_readability` nulls `direct_answer_summary` + `one_sentence_finding`
  → draft answers show SPL block with no analyst lead-in.
- `AnalystResponseCard` renders the summary as a single `<p>` → multiline summaries collapse
  into one paragraph.

### Canonical answer skeleton (deterministic, every answer)

1. **Direct answer / assessment** — 2–4 plain-language sentences (what this is, what I'd conclude so far)
2. **Severity + confidence** — policy-based, or "Not assigned from this question alone"
3. **Evidence** — results table when executed, or what the query will show
4. **MITRE status** — candidate / not-claimed (only when applicable; tier gate untouched)
5. **Query to review** — governed SPL or lab-only draft, status-labeled
6. **Investigation steps / analyst checklist**
7. **Limitations + missing evidence**
8. **Recommended next actions (P1–P4)**

This is exactly the existing `AnswerContract` section model — no new render system.

### Changes to enforce it

7. `app/chat/pipeline.py` — build the `AnswerContract` whenever `intent_classification`
   exists (drop the `control_plane_enabled or contract_evidence_plan` gate). Read-model
   only; verify no governance test asserts contract absence with the flag off.
8. `app/chat/final_answer_readability.py` — `apply_draft_preview_readability` composes a
   deterministic analyst lead-in for draft answers (direct answer + what the draft
   aggregates + review posture) instead of nulling the summary; forbidden-phrase scrub
   stays. Analytics answers get checklist/limitations populated from the detection family.
9. `frontend/src/components/AnalystResponseCard.tsx` — render header summary with the
   existing `splitParagraphs()` (multi-paragraph), not a single `<p>`. No layout redesign.

### q0.q010 on screen (end state)

> **[Not assigned from this question alone]**  *(severity badge)*
> **SMB traffic analytics — top SMB talkers**  *(title)*
> Review type: analytics/query review.  *(rationale line)*
> "This is a ranking/analytics question: identify which hosts generate the most SMB
> traffic. No governed SMB template is bound, so a lab-only draft SPL is provided for
> SOC review — it aggregates SMB sessions (ports 445/139 or smb/cifs/microsoft-ds apps)
> by source host: connection count, total bytes, distinct destinations, first/last seen."
> *(direct answer, 2–4 sentences)*
> Phase timeline: **Draft SPL preview** (lab-only chips, assumptions, draft SPL) →
> **Investigation steps** (validate top talkers: servers vs workstations, expected file
> servers/DCs/backup, pivot guidance) → **Limitations** (placeholders need source profile;
> bytes field vendor-specific) → **Plan** (P2-prioritized review actions)

## Rollout flags — single posture, zero new flags

**This work adds NO new flags, no new profiles.** Verified live `.env` on srv (2026-06-09):

| Flag | Live `.env` | `.env.example` | Posture |
|---|---|---|---|
| `CONTROL_PLANE_ENABLED` | `true` | `false` | ON — required for evidence plan / path_type / adjudication |
| `AI_SOC_SPL_DRAFT_PREVIEW_ENABLED` | `true` | `false` | ON — required for lab draft (incl. new SMB family) |
| `AI_SOC_PLANNER_PATH_SELECTION_ENABLED` | `true` | `false` | ON |
| `AI_SOC_CURATED_ENRICHMENT_ACTIVATION_ENABLED` | `true` | `false` | ON |
| `AI_SOC_PLANNER_MITRE_BRANCH_ENABLED` | `true` | `false` | ON |
| `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED` / `LIVE_SYNTHESIS` / `ANSWER_GUARD` | `true` | — | ON (guard on) |
| `MCP_GLOBAL_EXECUTION_ENABLED` | `false` | `false` | **OFF always** |
| `MCP_SERVER_MOCK_EXECUTION_ENABLED` | `false` | `false` | **OFF always** |

Action: align `.env.example` enable-flags to this all-on SOC posture (one commented block,
"SOC surface posture — all governance layers on; MCP execution never"), so eval/dev/prod
run the same shape. No draft-preview-bypass exception — flag semantics stay clean because
the flag is simply on everywhere.

## Control plane off — explicit degraded behavior (not enhanced)

Flag-independent fixes (apply even with CP off): intent no longer falls to clarification,
severity guard, boundary-label fix, SMB draft family (draft flag is separate from CP),
route skill already correct (`attack_discovery`).
CP-off remains legacy: `evidence_plan=None`, no route adjudication, planner trace-only —
answer shape degraded. **We do not build a synthetic CP-off evidence plan** — that would be
a second code path / hidden profile, exactly what we're removing. Supported posture is CP on.

## Registry-first analytics branch (authority order inside the branch)

`classify_intent` analytics branch checks in this order:
1. `candidate_mappings.match_path ∈ {exact_105_question, exact_105_plus_use_case_catalog}`
   AND registry metadata (`mapped_pattern_type == top_n_aggregation` or
   `proposed_primary_skill == aggregate_and_rank` / `proposed_operation_type == top_n`)
   → authoritative, no regex involved. The 9 top-N questions ride registry metadata, not
   re-encoded regexes.
2. Fallback only for near-match / out-of-registry paraphrase: `analytics_aggregation`
   regex signal ("which hosts … most", "top talkers", …), lower confidence.

## LLM synthesis — deterministic authority for analytics answers

Live synthesis narrates the deterministic draft only; it never sets facts. For the
analytics profile add explicit checks (test-backed):
- Composer/guard must NOT reintroduce "P3 Medium", "HIL not required", or
  "SPL not required" when the severity guard label and a draft preview are present
  (draft forbidden-phrase scrub already exists; extend the focused tests to assert
  severity wording survives composer fallback).
- Any guard/composer failure → deterministic skeleton ships as-is (existing fallback).

## Crosswalk note (deferred Phase 1.5)

q0.q010 crosswalk: `use_case_id=null`, `runtime_support_status=metadata_only`,
`missing_authoritative_mapping`. Lab draft path does not need it. Optional follow-up:
add a stable `use_case_id` row so enrichment projection can carry checklist/limitations —
separate commit, not in this change.

## Changes by file

1. `app/chat/query_signals.py` — add `analytics_aggregation` + `exact_105_analytics` signals.
2. `app/chat/intent_classifier.py` — analytics branch above clarification fallback.
3. `app/risk/severity_policy.py` — `apply_analytics_severity_guard()`; wired in
   `pipeline.py` finalize after `decide_severity`; builder maps the not-assigned label to
   rationale "Review type: analytics/query review."
4. `app/chat/network_boundary_display.py` — protocol-only terms ("smb traffic",
   "rdp traffic", "denied traffic") require a boundary-context term (it-to-ot, corporate
   it/to ot, ot network/segment/vlan/control room, firewall, zone, vlan, segment,
   substation, boundary, scada, esp, vendor vpn, jump server); bare-SMB analytics label
   fallback "SMB traffic analytics" / "Network traffic analytics".
5. `app/spl/draft_preview.py` — `network_smb_top_talkers` family; matcher order:
   OT-scoped SMB → `firewall_ot_smb_lateral` first (PowerGrid preserved), then SMB+ranking
   → top-talkers.
6. Tests — two tiers:
   - **Tier A (CI, runs inside pytest → automatically part of governance regression):**
     - `app/tests/test_105_path_honoring.py` — the 10 named focused tests from the task
       spec + composer/guard severity-wording assertions (LLM synthesis section).
     - `app/tests/test_105_path_regression_sample.py` — fast deterministic path-only
       harness: q0.q010 + **all 9 top_n_aggregation questions** + 5 SPL-gen + 5 RAG/SOP +
       unsafe rows; asserts question_ref, match_path, pattern_type, operation,
       intent_family, path_type, needs_spl/rag/mitre, severity behavior, answer_mode;
       no LLM, no network. Lives in `app/tests/` so `run_stage3_governance_regression.sh`
       picks it up without script changes.
   - **Tier B (pre-deploy, full 105):** `scripts/eval_105_path_honoring.py --check` —
     iterates all 105 entries of `question_runtime_map_v1.json` through
     understand→intent→evidence→planner (path fields only, no answer prose, no LLM).
     Differs from the existing stage3l 105 shadow eval, which asserts shadow *route*
     agreement only — Tier B asserts intent_family / path_type / needs_* / severity
     behavior / answer_mode per pattern_type class. Expectations are per-pattern-class
     (e.g., all top_n_aggregation → spl path, severity not-assigned w/o alert), not
     per-question prose.

## Verification order

1. New focused tests + harness.
2. `test_ws_powergrid_review_fixes.py`, `test_spl_draft_preview.py`,
   `test_powergrid_soc_question_eval.py` (note: `test_ws_manual_fixes.py` no longer exists
   on disk — only a stale .pyc; its coverage moved into the powergrid review fixes tests).
3. Presentation: grep/check no test asserts `answer_contract is None` with control plane
   off before removing the contract gate; `cd frontend && npm run build`.
4. Tier B: `python scripts/eval_105_path_honoring.py --check` (all 105, path-only, fast).
5. `python scripts/run_powergrid_soc_question_eval.py --profile deterministic --check`.
6. `.env.example` aligned to all-on SOC posture (MCP execution flags stay false).
7. No live_llm runs; governance regression covers Tier A automatically via pytest.

## Preserved invariants

MCP disabled; no LangGraph cutover; MITRE evidence-tier gate untouched; no new routable
skills or path_type enums; runtime_active rules untouched; drafts lab-only,
`execution_eligible=false`; Experience Center path untouched.
