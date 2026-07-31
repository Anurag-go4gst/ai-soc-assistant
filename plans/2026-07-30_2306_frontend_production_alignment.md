---
name: frontend-production-alignment
overview: Two-PR delivery — PR A additive backend contract (G1/G2), PR B frontend alignment consuming authoritative fields only.
status: active
date: 2026-07-30
canonical_plan: plans/2026-07-30_2306_frontend_production_alignment.md
baseline_backend: d6c89e2
delivery: two-pr
pr_a_branch: feat/response-contract-bridge-g1-g2
pr_b_branch: feat/frontend-production-alignment
---

# Frontend production alignment (revised — two PRs, three waves)

## Delivery split

| PR | Branch | Scope |
|----|--------|-------|
| **A** | `feat/response-contract-bridge-g1-g2` | G1 `planning_outcome` + G2 execution uncertainty serialization only |
| **B** | `feat/frontend-production-alignment` | Frontend waves 1–3 on authoritative contracts (**no** interim planning heuristics) |

**G1/G2 are required for full P0 completion** — not optional follow-ups.

## Three implementation waves (PR B)

| Wave | Items | Goal |
|------|-------|------|
| **1** | F1–F5 | Types, mapper, banners, execution honesty, HIL posture, health vs migration |
| **2** | F6–F10 | Cockpit approval, SPL pairing, settings degraded, retry, citations |
| **3** | F9,F11,F12,F16 | Vitest 10 journeys, trace allowlist, a11y, build handoff |

Bundle splitting deferred unless trivial and non-blocking.

## Rollback (static frontend only)

1. Preserve timestamped backup of current `frontend/dist` before publish.
2. Restore backup directory over `frontend/dist`; ensure `chmod -R a+rX frontend/dist`.
3. No `git checkout` of `dist` (gitignored). No Nginx reload for ordinary static asset replacement.

## Release order (post-merge)

1. Deploy PR A (backend contract).
2. Verify `/health`, migrations, sample `planning_outcome` / `outcome_uncertain` serialization.
3. Build and atomically publish PR B `frontend/dist`.
4. Smoke: login, root, architecture page, migration indicator, clarification, policy block, planning failure, HIL-disabled, reconciliation fixture.

## PR A checklist

- [x] **A1** — `PlanningOutcomeSummary` + `ExecutionEnvelope` uncertainty fields on schema
  - **Verify:** `pytest app/tests/test_response_contract_bridge.py -q`
  - **Evidence:** 11 passed (2026-07-31)

- [x] **A2** — `response_contract_bridge.py` producer + `pipeline.py` enrich hook
  - **Verify:** grep `enrich_placeholder_response` in `pipeline.py`
  - **Evidence:** wired post-scorecard + rp_degraded

- [x] **A3** — Negative serialization tests (no internal leakage)
  - **Verify:** `test_sanitize_reconciliation_reason_rejects_arbitrary_text`
  - **Evidence:** in test_response_contract_bridge.py

- [x] **A4** — Production parity `--check`
  - **Verify:** `python3 scripts/run_langgraph_dual_parity_eval.py --check`
  - **Evidence:** `total=120 exact=120 approved=0 critical=0`

- [x] **A5** — Draft PR opened (stop before merge)
  - **Evidence:** https://github.com/Anurag-go4gst/ai-soc-assistant/pull/123 (draft, OPEN)

## PR B checklist (pending PR A merge base)

- [x] **B1** — Wave 1 contracts + safety components
  - **Verify:** grep `PlanningOutcomeBanner|ExecutionReconciliationCard|planningOutcome` in `frontend/src`
  - **Evidence:** types, mapper, banners, execution labels, TopBar migration readiness, HumanReviewCard posture

- [x] **B2** — Wave 2 journey completion
  - **Verify:** `ApprovalStatusPanel`, SPL pairing in `AnalystSummaryCard`, citations in `ChatBubble`
  - **Evidence:** cockpit read-only HIL; settings-degraded warning in TopBar; retry via existing chat/SSE paths

- [x] **B3** — Wave 3 vitest 10 journeys + a11y + trace allowlist
  - **Verify:** `npm test` — 11 journey contract tests; `SafeControlPlaneSection` + `buildSafeControlPlaneSummary`
  - **Evidence:** focus-on-appearance HIL, aria-live on progress panel, semantic headings in banners

- [x] **B4** — `npm ci && npm test && npm run build`
  - **Verify:** `npm test` 11/11; `npm run build` tsc+vite PASS (2026-07-31)
  - **Evidence:** `git diff --check` clean in PR B worktree

- [x] **B5** — Staging dist hashes recorded
  - **Verify:** `/tmp/ai-soc-frontend-staging-202607310558` + `/tmp/ai-soc-staging-hashes.txt`
  - **Evidence:** see release report §5

- [x] **B6** — Draft PR opened (stop before merge)
  - **Evidence:** PR B draft opened (see release report)

## Trace UI allowlist (normal analyst)

Allowed collapsed fields only: `canonical_status`, `dispatch_source`, `blocked_action_state` summary, LLM role/outcome counts, safe fallback/skip reason codes. No raw prompts, tokens, URLs, runtime context, or arbitrary JSON in primary UI.

## Accessibility (PR B)

Focus-on-appearance for pending HIL; semantic headings; keyboard-accessible controls; `aria-live` for progress completion/errors. No focus trap in HumanReviewCard.
