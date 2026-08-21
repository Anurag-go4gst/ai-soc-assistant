---
name: understanding-authority-and-response-ux
overview: "Implement frozen architecture.md complete-or-abstain understanding authority, Final-RQC product applicability, provenance, and SOC response/UI workspace corrections."
status: active
date: 2026-08-21
canonical_plan: plans/2026-08-21_1937_understanding-authority-and-response-ux.md
loop_runner: plans/LOOP_RUNNER_understanding-authority-and-response-ux.md
architecture_freeze_commit: 49c5a4945ae4ff2a319a43980110f220076c1489
base_merge_commit: 49e545d9b7993dc185519a21b18e2ec26ecce40b
feature_branch: feat/complete-or-abstain-t4-ux
---

# Understanding authority + response / UI UX

## Objective

Bring production `/chat` into conformance with the frozen `architecture.md` (commit `49c5a494`) understanding model:

```text
T1–T3 COMPLETE + CONFIDENT → ACCEPT complete contract → skip T4
  OR
T1–T3 ABSTAIN → T4 semantic proposal → DET validation → Final RQC
```

Then ensure Final RQC (not T4 usage, MCP availability, or missing evidence) selects the product lifecycle, and that the analyst UI presents one coherent SOC workspace answer (no duplicate remediation CTAs, no investigation conclusion on pure SPL authoring, readable prose + wide structured content).

**Done** means: all checklist items checked with evidence; architecture.md unchanged from freeze SHA; focused + required regression gates green; Mac UI acceptance recorded for the firewall SPL authoring scenario without InvestigationOutcome/BLOCK/remediation pollution.

## Architecture authority (frozen — do not edit)

Read-only source: `architecture.md` @ `49c5a494`.

Invariants this plan must not weaken:

- T1–T3 complete-or-abstain (no partial semantic contract + field-level T4 fill)
- Explicit user literals remain binding DET constraints after abstain; T4 must not contradict; DET must reject
- Derived observations are non-authoritative hints only
- T4 is meaning-only (no route / ResourcePlan / CapabilitySnapshot / MCP / RBAC / HIL / remediation authority)
- One Final RQC; owner/capabilities/evidence/route hints DET-derived after validation
- InvestigationOutcome only for investigation-shaped Final RQCs
- Future T3 embeddings = candidate retrieval/ranking only (not implemented here)
- candidate_spl non-executable; normalized_spl + exact-call; one RP hub; PlanDelta bounds; remediation separation; no raw CoT

Related but **separate** plan (do not overwrite or merge):
[`plans/2026-08-21_0034_agentic-investigation-production.md`](2026-08-21_0034_agentic-investigation-production.md) — investigation envelope / PlanDelta product track.

## Mac / environment posture (implementation + acceptance)

```text
ENVIRONMENT=MAC
LLM: available when office network path reaches endpoints; otherwise honest degrade
Splunk MCP: not configured / unavailable → capability unavailable / fail-closed execution
Missing MCP must NOT disable architecture or invent investigation BLOCK for SPL authoring
```

## Stop conditions

- All checklist items checked with recorded evidence, **or**
- Same Verify gate fails twice on one item, **or**
- Architecture interpretation ambiguous / would require editing `architecture.md`, **or**
- New authority decision required, **or**
- Implementation seems to need a second router, second T4 service, or T4 investigation runtime, **or**
- Security / HIL / RBAC / exact-call would be weakened, **or**
- Legitimate existing work would need deletion

## Dependency order

`P0 → P1 → P2 → P3 → P4 → P5 → P6 → P7 → P8`

## Prohibited globally

- Modify `architecture.md`
- Special-case individual user questions (including firewall phrasing)
- Keyword patches / firewall-only rules
- Implement embeddings now
- Second router / second planner / second T4 / T4 investigation runtime
- Fake LLM or MCP availability
- Hide failing tests to continue
- Merge or push unless operator requests

## Existing modules to reuse (audit-first)

| Concern | Prefer |
|---|---|
| T1 exact / near / semantic 105 | `query_understanding/parser.py`, `coverage/question_runtime_map.py`, `coverage/semantic_question_index.py` |
| T2/T3 catalogue | `use_cases/registry.py`, `catalogue/match_tiers.py`, `chat/lane_router.py` |
| Route floors | `routing/select_route_from_understanding.py`, `routing/skill_router.py` |
| Intent / RQC | `chat/intent_classifier.py`, `chat/resolved_query_builder.py`, `chat/contracts/resolved_query.py` |
| T4 | `chat/semantic_t4_understanding.py`, `chat/contracts/semantic_t4_proposal.py` |
| Canonical planning | `chat/canonical_planning_orchestrator.py` |
| Evidence plan / outcome | `chat/evidence_planner.py`, `evidence/evidence_sufficiency.py`, `chat/contracts/investigation_outcome.py` |
| SPL fidelity | `spl/request_authority.py`, `chat/review_only_spl_renderer.py` |
| Provenance | `control_plane_trace`, `route_plan_shadow`, `investigation_lineage`, `provenance.semantic_t4` |
| UI composition | `ChatBubble.tsx`, `InvestigationOutcomeCard.tsx`, `RemediationPlanApprovalCard.tsx`, `AnalystResponseCard.tsx`, `ChatPanel.tsx` |

## Checklist

- [ ] **P0** — Baseline + architecture freeze gate
  - **Do:** Record branch, base SHA `49e545d9`, architecture freeze SHA `49c5a494`, clean worktree (ignore local `.claude/` only), Mac profile/flags, LLM/MCP posture, and pin `architecture.md` as read-only for this plan. Confirm no equivalent active plan exists beyond this file. Do not change runtime code.
  - **Verify:** `git rev-parse HEAD`; `git status --short` shows only optional local tool noise; `git show 49c5a494:architecture.md | rg -n 'COMPLETE|ABSTAIN|MUST reject|MUST NOT materially contradict|InvestigationOutcome applies|embedding / vector'`; `test ! -w` is not required — instead prove no `architecture.md` diff during later phases.
  - **Depends on:** none
  - **Evidence:** _(fill when done)_
  - **Commit:** none (docs evidence in plan Evidence only) or `docs(plan): record P0 baseline` if an evidence file is added under `docs/evals/`

- [ ] **P1** — T1–T3 complete-or-abstain acceptance gate
  - **Do:** AUDIT FIRST the live path `understand_query` → `match_use_cases` → `lane_for_match_path` → known vs guided. Implement a single DET acceptance gate: ACCEPT only when match is complete, confident, margin-sufficient, compatible, and fully governed; otherwise ABSTAIN with no partial semantic commit. Keep a clean T3 candidate interface so future lexical∪embedding candidates can share the gate. Do not implement embeddings. Do not special-case queries.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_t1_t4_authority_boundary.py app/tests/test_spl_query_fidelity.py -q` plus NEW focused tests (create `app/tests/test_complete_or_abstain_understanding.py`) covering: exact 105 ACCEPT+T4 skipped; strong catalogue paraphrase ACCEPT; single generic source token cannot bind rich detection; unclear objective ABSTAIN; unknown SOC ask ABSTAIN.
  - **Depends on:** P0
  - **Evidence:** _(fill when done)_
  - **Commit:** one logical commit for P1 only

- [ ] **P2** — T4 full semantic fallback + DET validation
  - **Do:** On ABSTAIN only, call T4 with original query, trusted schema/vocabulary, meaning-aid capability descriptions, few-shots, **EXPLICIT_USER_LITERAL_CONSTRAINTS**, and optional derived hints. Remove partial locked intent/goal handoff from abstained T1–T3. DET validates schema + literals + prohibitions + query consistency; reject material literal contradictions (e.g. `10.0.0.8`/`2h`/`do_not_execute` cannot become `10.0.0.5`/`24h`/execute). After accept, DET derives Final RQC, owner, capabilities, evidence needs, route hints — T4 must not commit those fields.
  - **Verify:** NEW tests in `app/tests/test_t4_complete_or_abstain_validation.py` (or extend `test_t4_contract_merge_authority.py` only if still the owning seam after audit): T4 skipped on ACCEPT; T4 invoked on ABSTAIN; literal contradiction rejected; derived hints non-binding; no `primary_skill`/ResourcePlan/MCP grant from T4 proposal. Run `/invariant-check` on the diff.
  - **Depends on:** P1
  - **Evidence:** _(fill when done)_
  - **Commit:** one logical commit for P2 only

- [ ] **P3** — Final-RQC product applicability
  - **Do:** AUDIT FIRST `evidence_planner.py` (`spl_generation_only` → `live_investigation` + `needs_mcp` + `mcp_allowed=false`), `derive_investigation_outcome`, `maybe_attach_remediation_offer`, and finalize packaging. Make product lifecycle selection depend on Final RQC answer goal / investigation shape — not on T4_USED, MCP unavailable, or missing live rows. Pure SPL authoring must use review-only SPL composition without InvestigationOutcome blocked/BLOCK/remediation. Investigation-shaped RQCs still enter the common investigation lifecycle regardless of T1–T3 vs T4 understanding path.
  - **Verify:** NEW `app/tests/test_final_rqc_product_applicability.py` including generic coverage for SPL-authoring shaped RQC (no InvestigationOutcome investigation_status packaging / no remediation_offer_required by default) and investigation-shaped RQC still eligible for outcome. Reproduce the firewall SPL authoring *shape* via signals/fixtures without hardcoding that sentence as a special case. `/invariant-check`.
  - **Depends on:** P2
  - **Evidence:** _(fill when done)_
  - **Commit:** one logical commit for P3 only

- [ ] **P4** — Deterministic understanding provenance
  - **Do:** Extend existing provenance (`control_plane_trace` / `route_plan_shadow` / `investigation_lineage` / RQC `provenance`) with a concise deterministic strip: T1/T2/T3 accept-or-abstain, T4 used/skipped, final intent, final owner. Surface under existing “How this answer was produced”. No new tracing framework. No chain-of-thought.
  - **Verify:** Unit/contract test that provenance fields are present and deterministic for ACCEPT and ABSTAIN→T4 paths; frontend or lineage consumer test if a UI field is added. `rg` proves no new telemetry catalog event invented without closed-catalog registration.
  - **Depends on:** P3
  - **Evidence:** _(fill when done)_
  - **Commit:** one logical commit for P4 only

- [ ] **P5** — Response ownership + outcome/remediation semantics
  - **Do:** Define one primary response profile from Final RQC. Fix `ChatBubble` stacking so SPL authoring does not show InvestigationOutcomeCard + local remediation CTA + RemediationPlanApprovalCard + AnalystResponseCard together. Remove or demote the **local** OutcomeCard remediation Yes/Not-now so only backend-governed `RemediationPlanApprovalCard` is authoritative when remediation applies. Investigation / knowledge / remediation profiles remain governed.
  - **Verify:** Frontend tests for composition by profile; backend packaging tests that SPL-authoring turns omit investigation_outcome.investigation_status and remediation_approval when not applicable. `cd frontend && npm test -- --run ChatBubble` (or the owning test file created/updated). `npm run build`.
  - **Depends on:** P3, P4
  - **Evidence:** _(fill when done)_
  - **Commit:** one logical commit for P5 only

- [ ] **P6** — UI/UX SOC workspace improvement
  - **Do:** Widen the structured answer workspace (center column `w-full` / sensible desktop max) while keeping prose ~68–80ch. Allow SPL/code, tables, plans, evidence, traces to use broader width. Clear hierarchy: direct answer → supporting artifact → next action when applicable → collapsible technical/authority details. Fix user-facing process vocabulary so sufficiency `BLOCK` does not read as containment “block IP/firewall”. Responsive: laptop, wide desktop, mobile.
  - **Verify:** `cd frontend && npm test && npm run build`; manual Mac screenshot checklist recorded in Evidence for: no duplicate answers, no duplicate remediation controls, no investigation conclusion on SPL-only, wider workspace, readable prose, SPL not cramped, collapsed “How this answer was produced” / technical path.
  - **Depends on:** P5
  - **Evidence:** _(fill when done)_
  - **Commit:** one logical commit for P6 only

- [ ] **P7** — Full regression + Mac end-to-end acceptance
  - **Do:** Run required suites and product scenarios A–K from the operator brief (exact, paraphrase, firewall SPL authoring shape, explicit review-only SPL with do-not-execute, rich Cisco detection, ambiguous suspicious, unknown investigation, MITRE, multi-turn time/entity correction, literal survival). Record LLM/MCP honest degrade on Mac. Do not fake services.
  - **Verify:** `./scripts/run_stage3_governance_regression.sh`; targeted authority/fidelity/HIL/MCP suites green; frontend build green; scenario matrix table filled in Evidence with pass/fail. Classify any failure as regression / env / pre-existing.
  - **Depends on:** P1–P6
  - **Evidence:** _(fill when done)_
  - **Commit:** optional evidence-only commit under `docs/evals/` if needed

- [ ] **P8** — Release / git synchronization record
  - **Do:** Confirm `architecture.md` byte-identical to freeze commit `49c5a494` for that file content path (`git diff 49c5a494 -- architecture.md` empty). Clean worktree. Record CODE_SHA, ENVIRONMENT=MAC, PROFILE, LLM_STATE, MCP_STATE, TEST_RESULTS, UI_ACCEPTANCE. Do not deploy to VPS/COE in this plan.
  - **Verify:** `git status --short`; `git diff 49c5a494 -- architecture.md`; Evidence block complete.
  - **Depends on:** P7
  - **Evidence:** _(fill when done)_
  - **Commit:** none unless recording an eval report file

## Product scenarios (P7 matrix)

| ID | Scenario | Expected |
|---|---|---|
| A | Exact governed T1–T3 happy path | ACCEPT; T4 skipped |
| B | Known catalogue paraphrase | ACCEPT when complete/confident |
| C | Firewall SPL authoring shape | Final RQC SPL authoring; no InvestigationOutcome BLOCK/remediation pollution |
| D | Explicit review-only SPL with index/sourcetype/time + do not execute | Literals survive; review-only; no execute |
| E | Known rich Cisco detection | ACCEPT when complete |
| F | “Is this activity suspicious?” | ABSTAIN / clarify as appropriate |
| G | Unknown investigation | ABSTAIN → T4 → investigation-shaped RQC when warranted |
| H | Explicit MITRE | ACCEPT when governed match complete |
| I | Multi-turn 30d → 3d | Time correction preserved |
| J | Entity/time 10.0.0.5/24h → 10.0.0.8/2h | Literals corrected and enforced |
| K | Explicit do not execute through T4 path | DET rejects execute=true |

## Verification gaps (flag before coding)

- Exact frontend test file names for ChatBubble composition may need creation during P5 audit-first.
- Which existing suite already covers 105/105 path acceptance must be confirmed in P0/P7 (`question` evals / governance script) — do not invent a second 105 harness.

## Drift log

- 2026-08-21: Architecture freeze landed as `49c5a494` on master before this plan; feature branch `feat/complete-or-abstain-t4-ux` carries prior auth/COE/SPL/UI commits plus this plan. Do not re-amend architecture.md here.
- Separate agentic investigation production plan remains independent; this plan owns understanding authority + response/UI applicability, not envelope/PlanDelta feature buildout.
