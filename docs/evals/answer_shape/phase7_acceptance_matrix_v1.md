# Phase 7.1 — Convergence acceptance matrix

**Plan:** `plans/2026-08-26_1030_production-answer-shape-spl-mcp-convergence.md`  
**Worktree:** `/Users/aagarwal/Downloads/ai-soc-wt-post-p10-convergence`  
**Branch:** `ws/post-p10-answer-tool-convergence`  
**HEAD at close:** _(stamp on commit)_  
**Attested_at_utc:** `2026-08-27T03:00:00Z` (local run window)  
**Verdict:** **ACCEPTED** — all critical gates green or named operator-adjudicated residuals; zero unexplained new failure node-IDs vs plan 0.4.

Phases 4 / 5 / 6 are complete (4.2 = SKIPPED_BY_EVIDENCE). DEFERRED_* / OPTIONAL_PHASE_S untouched. No push / merge / deploy. `architecture.md` READ ONLY.

---

## Gate matrix

| Gate | Result | Evidence |
|---|---|---|
| Backend pytest (venv) | **7154 passed**, 0 failed, 45 skipped, 6 xfailed | `/tmp/p7_gov3.txt` after mock-label assert fix `3f65f758` |
| Frontend vitest | **126 passed** / 28 files | `/tmp/p7_frontend_test.txt` |
| Frontend build | **PASS** (`tsc` + vite + postbuild chmod) | `/tmp/p7_frontend_build.txt` |
| Protected execution baseline | **15/15** unchanged | `scripts/freeze_execution_baseline.py --check` |
| RACES isolation | **8 passed** | `pytest app/tests/test_live_path_untouched_by_ec.py` |
| Test harness | **6/6** | governance log |
| Convergence bank `--check` | **PASS** byte-identical (`total=10 pass=5 product_gap=3 deferred=2 fail=0`) | `eval_convergence_expectations.py --check` |
| Phase 6 shape scorecard | ACCEPTED | `docs/evals/answer_shape/phase6_shape_scorecard_v1.md` |
| Sentinel / Tier-D AQ / OT probes | PASS | governance prefix |
| 105-Q shadow routes | `overall_pass=True` (all buckets 0 fail) | `docs/evals/out/stage3l_105_shadow_eval.json` (gitignored) |
| LangGraph dual parity | **120 exact / 0 critical**; pytest 32 passed slice | `--check ok` |
| SOC clean-answer | **120/120**; critical=0 | `--check ok` |
| Cisco power-grid catalogue | **50/0/0** | deterministic wave3 `--check` |
| Pipeline dispatch matrix | **5/5** | `--check ok` |
| SPL template audit | **19/19** review_required=0 | `llm_template_audit.py` |
| Golden answer Tier 0 | **5 passed / 2 failed** | Named residuals below (not greenwashed) |
| Full `run_stage3_governance_regression.sh` exit | Fails closed on Tier-0×2 | Expected given inherited residuals; remaining gates re-run PASS |
| J7 + email-send HIL + S4 + mock 5.6/5.7 | **49 passed** targeted | `/tmp/p7_targeted.txt` |
| P8 frozen bank | Canonical hash **match** `5f78ccbe1940149a67dcd1052140c44c854ec42a409d7644b47e5357010dbf51` | `scripts/eval_p8_l3_live.py` canonical bytes; file SHA `9f4376c0…` unchanged vs `6b63df61` |
| Browser QA vs attested `.env` ports | **ENVIRONMENT_UNRESOLVED** | No worktree `.env`; Docker socket denied — not treated as product fail |
| Live LLM / production traces | **ENVIRONMENT_UNRESOLVED** | Carried from 0.2 / LOOP_RUNNER |

---

## Named residuals (operator-adjudicated — not PASS)

| ID | Class | Notes |
|---|---|---|
| `tier0.top_failed_login_spl_missing_binding_clarification` | `accepted_inherited_residual` | P9/P10 packet; block_reason/response_mode expectations pre-date this plan |
| `tier0.aws_security_group_modifications_spl_only` | `accepted_inherited_residual` | P9/P10 packet; `mcp_not_allowed_by_evidence_plan` vs expected HIL status |
| `CV.MULTI.01A/B/C` | `PRODUCT_GAP` | Design-case capture gaps; unit seams prove RQC/Phase-10 |
| `CV.SOP.01`, `CV.SPL.01` | `DEFERRED_LIVE_MEASURE` | Bank rows |
| Two production `trace_id`s | `ENVIRONMENT_UNRESOLVED` | Item 0.2 |
| Browser QA | `ENVIRONMENT_UNRESOLVED` | No attested runtime ports this host |
| Live Foundation-Sec endpoints | `ENVIRONMENT_UNRESOLVED` | URLError / wired-disabled as prior |

Zero **new unexplained** pytest failure node-IDs vs 0.4 product intent. The only suite failure before close was stale mock display assert — fixed in `3f65f758` to match Phase 5.6 honesty label.

---

## Closing criteria A–P

| # | Status | Proof |
|---|---|---|
| A | PASS | Multi-goal Final RQC + MULTI bank rows + Phase 1–2 |
| B | PASS | Investigation / SOP / remediation / email coexistence (Phases 2–3) |
| C | PASS | PENDING_CONDITION persistence + UI (2.5 / 6.x) |
| D | PASS | J7 suites green |
| E | PASS | Dual eligibility gates (3.1–3.3) |
| F | PASS | EMAIL DRAFT ≠ SEND (3.6–3.7) |
| G | PASS | Recipient roles / draft card (3.6) |
| H | PASS | Deterministic MCP selection (5.2) |
| I | PASS | Invariant — LLM never calls MCP |
| J | PASS | Mock simulated labelling (5.6) |
| K | PASS | Mock cannot grant write/send (5.7) |
| L | PASS | Phase 4 SPL honesty + validator untouched |
| M | PASS | Phase 6 shape scorecard (shape ≠ EC prose) |
| N | PASS | RACES 8 + live-path isolation |
| O | PASS | No second planner/MCP framework |
| P | PASS | Residuals named; no silent baseline rewrite |

---

## Deferred / out of scope (untouched)

- `DEFERRED_P11_MCP_READINESS`
- `DEFERRED_ACTION_CAPABILITY_GENERALIZATION`
- `OPTIONAL_PHASE_S` (SPL efficiency lints / SPL optimization rules)
- `DEFERRED_TECH_DEBT` pipeline dead-branch cleanup
- Live MCP / P11
- Push / merge / deploy

**Stop:** Convergence plan accepted. SPL optimization rules are a **follow-on**, not part of this plan.
