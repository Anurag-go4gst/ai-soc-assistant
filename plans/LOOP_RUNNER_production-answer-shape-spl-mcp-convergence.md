# LOOP_RUNNER — post-P10 answer & tool-orchestration convergence

**Canonical plan:** [`plans/2026-08-26_1030_production-answer-shape-spl-mcp-convergence.md`](2026-08-26_1030_production-answer-shape-spl-mcp-convergence.md)

**Framing:** POST-P10 PRODUCTION ANSWER & TOOL-ORCHESTRATION CONVERGENCE.  
Not P8 closure. Not a P9/P10 prerequisite. Not P11 / live MCP.

| Label | SHA |
|---|---|
| VERIFIED_RELEASE_BASELINE_SHA | `6b63df610ff4a0994a593537ab46c71464afe570` |
| LAST_PRODUCT_CHANGE_SHA | `c109402d69956df455a780fd49a191fa173ab7ac` |

**Final product decision:** **B4** — PRESERVE CONDITIONAL INTENT WITHOUT WEAKENING EVIDENCE AUTHORITY.  
Lifecycle: REQUESTED → PENDING_CONDITION → ELIGIBLE → APPROVED → EXECUTED.  
J7 remains true. B1/B2/B3 are retired.

## Execution status (living)

| Field | Value |
|---|---|
| **Worktree** | `/Users/aagarwal/Downloads/ai-soc-wt-post-p10-convergence` |
| **Branch** | `ws/post-p10-answer-tool-convergence` |
| **HEAD (shipped)** | `3ed1ec36` |
| **Checklist** | **20 checked** / 22 unchecked (through **3.6**) |
| **Next item** | **3.7** — Separate HIL-authorized send proof |
| **0.2 note** | `DONE_WITH_ENVIRONMENT_UNRESOLVED_INPUTS` — two production traces unavailable; design-case diagnostic only |
| **Shipped product commits** | RQC `09c3f97a` → pending UI `67246132` → J7 gate `010279f1` → J7 pins `72c74c13` → B4 dual gates `f0678916` → Phase-10 email lane `135748a9` → roles `fb53883d` → governed draft `3ed1ec36` |
| **LLM status** | `ENVIRONMENT_UNRESOLVED`: configured local-primary/reasoning probes red (`URLError`); Qwen intentionally wired-disabled |

Do **not** execute from the Cursor product-tip checkout alone — use this worktree.

## Architecture anchors (do not drift)

1. **Investigation HIL vocabulary:** visible **Approve / Edit / Cancel** → wire `run` / `edit` / `cancel`. Approve → `investigation_review_action = "run"` → immutable **ApprovedInvestigationEnvelope**. Do **not** revert UI to “Run investigation.” Remediation also uses Approve/Edit/Cancel as a **separate write HIL**.
2. **ResourcePlan = read-only investigation only.** Ticket/email/remediation are **Final RQC requested actions**, then Phase 10 after InvestigationOutcome — **not** ResourcePlan steps.
3. **Final RQC is the primary contract gap.** Preflight/extend first: `backend/app/chat/contracts/resolved_query.py`, `backend/app/chat/resolved_query_builder.py`. Do **not** smuggle into provenance / `workflow_plan` / unrelated metadata. Do **not** jump first to `schemas/responses.py`.
4. **Two eligibility gates — do not collapse:**
   - **REMEDIATION PLAN ELIGIBILITY** = completed + evidence-backed suspicious + J7/policy → plan may PRESENT; no write without Approve; does **not** require `compromise_confirmed` merely to show a plan.
   - **USER-CONDITIONAL ACTION ELIGIBILITY** = REQUESTED + exact governed predicate + action policy/HIL.
   - `suspicious` ≠ `compromise_confirmed`.
5. **Mock MCP is envelope-bound.** Before investigation Approve: mock invocation = NO. After Approve → wire `run` → envelope_version=N: every material mock call needs a **new** exact-call AUTH bound to envelope_version + tool/server + normalized args + normalized_spl (where applicable) + RBAC/policy. Changing envelope_version invalidates the prior grant. Mock follows the same auth architecture as eventual live MCP.
6. Phases **4 / 5 / 6 are parallelizable**, not necessarily concurrent — a single `loop-asap` worker may run them sequentially. Phase **7** waits for Phase 4 complete|SKIPPED_BY_EVIDENCE + Phase 5 complete + Phase 6 complete.

## Preconditions (check once, before the first iteration)

1. Isolated worktree from the verified release baseline (create at implementation start only):
   ```bash
   git worktree add ../ai-soc-wt-post-p10-convergence \
     -b ws/post-p10-answer-tool-convergence \
     6b63df610ff4a0994a593537ab46c71464afe570
   ```
2. `architecture.md` is READ ONLY for this entire loop.
3. Item **0.1** re-attests: remote `origin/master`, worktree `HEAD`, and runtime/VPS SHA if runtime validation is used. Do not rewrite historical `docs/evals/p10_handoff/handoff_meta.json`.
4. Do not trust stale master-plan status tables that still say P8 FAIL / P9–P10 TODO — P8/P9/P10 are closed.
5. Item **0.4** baseline is recorded before any behaviour change.
6. MCP stays OFF on default profiles. P11 is NOT STARTED. No push / merge / deploy from this loop.
7. Resource Planner hub + existing registries remain sole **investigation** authority — no second planner/registry/email framework. Conditional actions stay on Final RQC → Phase 10.

## Start

```text
loop-asap — execute plans/2026-08-26_1030_production-answer-shape-spl-mcp-convergence.md
```

> **Cursor only.** `loop-asap` is armed by `.cursor/hooks/before-submit-plan-discipline-arm.sh` and continued by
> `.cursor/hooks/stop-loop-asap-handoff.sh` (`loop_limit: 5`), both read from `.cursor/hooks.json`.
> **Claude Code does not fire these hooks** — there, run the steps below manually and call
> `audit-plan-discipline.sh` by hand.

## Agent loop

1. **Audit:** `.cursor/hooks/audit-plan-discipline.sh plans/2026-08-26_1030_production-answer-shape-spl-mcp-convergence.md` — fix every `GAP:`.
2. **Pick** the first unchecked item whose **Depends on** are satisfied. Authoritative DAG:
   ```text
   0.1 → 0.2 → 0.3 → 0.4
    → 1.1 → 1.2 → 1.3 → 1.4 → 1.5
    → 2.1 → 2.2 → 2.3 → 2.4 → 2.5
    → 3.1 → 3.2 → 3.3 → 3.4 → 3.5 → 3.6 → 3.7
         ├─→ 4.1 → 4.2 → 4.3 → 4.4          # SPL stream (parallelizable)
         ├─→ 5.1 → … → 5.7                  # mock-MCP stream (parallelizable)
         └─→ 6.1 → … → 6.9                  # answer/UI after Phase 3
    → 7.1   # waits for Phase 4 complete|skipped-by-evidence, Phase 5, Phase 6
   ```
   After Phase 3, Phases 4 / 5 / 6 are **parallelizable** (a single worker may still execute them sequentially). Phase 6 items that render MCP/mock execution state may depend on Phase **5.5–5.6**. Do **not** block unrelated answer-shape work on mock-MCP completion. One owner per file — no conflicting ownership.
   Phase 7 waits for: Phase 4 complete **or** explicitly SKIPPED_BY_EVIDENCE; Phase 5 complete; Phase 6 complete.
3. **Implement Do** — that item only. No adjacent cleanups, no bundling, no DEFERRED_*/OPTIONAL_PHASE_S scope creep.
4. **Run Verify exactly as written**, including named bank `row_id`s.
5. **Guards** (below) before check-off if the item touched runtime code.
6. **Check off** with a formal terminal state (below) and fill **Evidence** with observed output — never intent.
7. **Commit** per the plan’s Commit conditions, then next item.
8. **Stop at phase boundaries** for operator review when material architecture changed (especially after Phase 1 RQC contract decisions and after Phase 3 dual-gate / B4 wiring).

Stop on decision-needed, the same gate failing twice, or all items in a terminal completion state (DONE or legitimate SKIPPED_BY_EVIDENCE). Re-audit every checkmark before declaring the plan complete.

## Checklist terminal states

| State | Meaning |
|---|---|
| **DONE** | Item executed and Verify passed; Evidence recorded |
| **SKIPPED_BY_EVIDENCE** | Item’s explicit precondition was disproved by an earlier measured gate; evidence and reason recorded (e.g. `4.2 = SKIPPED_BY_EVIDENCE` because `G-TMPL = 0` material failures after 4.1) |
| **DEFERRED_BY_PLAN** | Only for items already declared `DEFERRED_*` / `OPTIONAL_PHASE_S` (not on critical path) |
| **BLOCKED** | Not completion — stop and ask |

A phase is **complete** only when every item in that phase is **DONE** or legitimately **SKIPPED_BY_EVIDENCE** per its written precondition. Do **not** falsely tick SKIPPED work as DONE, and do **not** implement unnecessary work when SKIPPED_BY_EVIDENCE applies.

Mark in the plan checklist as `- [x]` with Evidence starting `SKIPPED_BY_EVIDENCE: <reason>` when skipping.

## Conditional-action state authority

| Transition | Authority |
|---|---|
| REQUESTED → PENDING_CONDITION | Deterministic plan/contract normalization |
| PENDING_CONDITION → ELIGIBLE | Deterministic governed predicate evaluation **only** |
| ELIGIBLE → APPROVED | Explicit HIL only where approval is required |
| APPROVED → EXECUTED | Deterministic authorized connector/action executor **only** |

**LLM may not perform any lifecycle transition** — including treating an LLM-generated email draft as APPROVED or EXECUTED.

## Guards — before checking off any runtime-touching item

```bash
/invariant-check
```
All 7 groups must PASS. One FAIL blocks the commit.

```bash
cd backend && python3 -m pytest -q
```
Zero **new** failure node-IDs versus the 0.4 baseline. Diff names from `-rf`, never counts; do not trust `.pytest_cache` `lastfailed` across filtered runs.

```bash
PYTHONPATH=backend:. python3 scripts/eval_convergence_expectations.py --check
```
Any diff versus baseline must be the intended change named in the commit body. **Never** auto-rewrite the expectation baseline to make a run green.

**J7 / dual gates:** incomplete / inconclusive / knowledge-only → no remediation plan PRESENT / no write. Completed + suspicious may PRESENT a remediation plan under REMEDIATION PLAN ELIGIBILITY without requiring user `compromise_confirmed`. USER-CONDITIONAL ACTION ELIGIBILITY stays separate (REQUESTED + exact predicate). Conditional intent may be PENDING_CONDITION only (visible without treating it as ELIGIBLE).

**Governed predicates / lifecycle:** LLM may propose/explain conditions and draft prose; only the Conditional-action state authority table above may advance REQUESTED→…→EXECUTED. LLM may not transition any lifecycle state.

**EvidenceState:** progress/execution telemetry (planned/attempted/failed/skipped/empty/retry) never becomes SourceEvidence.

**Envelope-bound mock:** no material mock MCP before ApprovedInvestigationEnvelope; grants bound to `envelope_version` + exact call; stale envelope fails closed.

**No live MCP. No mock evidence authority. No email send without HIL. No hardcoded evaluation-query solutions in product code. No second registry/planner. ResourcePlan stays read-only investigation.**

At every **phase boundary**:

```bash
./scripts/run_stage3_governance_regression.sh
cd frontend && npm test && npm run build
```

**Ports are environment-derived.** Read `AI_SOC_BACKEND_HOST_PORT` / `AI_SOC_FRONTEND_HOST_PORT` from the target deployment’s `.env` each run. Never hard-code historical 8011/8012/3010/3013.

## Trace diagnosis (0.3)

Each trace: exactly one `PRIMARY_FAILURE_SEAM` + zero or more `CONTRIBUTING_SEAMS`.  
Primary = earliest/root architectural seam that materially prevented the intended outcome.  
No bare `"unknown"` — use `ENVIRONMENT_UNRESOLVED` if environment blocks classification.

## Governance-sensitive / protected items

- `resolved_query.py` / `resolved_query_builder.py` (**primary RQC gap**): audit/extend first for requested conditional actions; no provenance/`workflow_plan` smuggling; `schemas/responses.py` only after RQC owns the fields.
- `remediation_runtime.py` (and any J7 seam): before edit, record CURRENT CONTRACT → PROPOSED CONTRACT → WHY J7 REMAINS TRUE → POSITIVE TEST → NEGATIVE TEST → ROLLBACK. Not “unfrozen = safe.” Keep REMEDIATION PLAN ELIGIBILITY vs USER-CONDITIONAL ACTION ELIGIBILITY distinct.
- Freeze / RACES / `pipeline.py` / `schemas/responses.py` / chat routes / MCP gate / ChatPanel: exact packet + operator approval + RACES baseline advance in the **same** commit when freeze paths change.
- Historical P8 packets: verify HEAD first; mark SUPERSEDED/CLOSED if already present; never re-apply blindly.
- Extend Final RQC (owns requested conditional actions) → ApprovedInvestigationEnvelope → ResourcePlan (**read-only investigation**) → EvidenceState / InvestigationOutcome → Phase 10 action/remediation lane only. **Reuse a field only when its current semantics exactly match.** No field smuggling. **No second planner/registry.**

## Deferred — do not pull onto the critical path

- `DEFERRED_P11_MCP_READINESS` — durable discovery snapshot  
- `DEFERRED_ACTION_CAPABILITY_GENERALIZATION` — create_ticket proposable bucket  
- `OPTIONAL_PHASE_S` — SPL efficiency lints  
- `DEFERRED_TECH_DEBT` — dead `pipeline.py` branch cleanup  

## Stop

- `loop-asap stop`, or
- Every checklist item is **DONE** or legitimately **SKIPPED_BY_EVIDENCE** (with Evidence), or
- Same Verify fails twice on one item, or
- Protected/governance-sensitive diff without packet/approval, or
- New env flag **name** required, or
- 0.1 baseline/remote/VPS SHA mismatch unresolved, or
- J7 would be weakened, or
- Remediation-plan eligibility collapsed into user-conditional predicates (or vice versa), or
- Conditional actions placed inside ResourcePlan, or
- Mock MCP invoked before ApprovedInvestigationEnvelope or without envelope-bound AUTH, or
- Mock evidence would gain write/remediation authority, or
- Free-text condition would become action authority, or
- LLM would perform a conditional-action lifecycle transition, or
- Attempt to implement deferred items as required scope, or
- Unexplained regression in Phase 7 matrix.

## Evidence rules

- Evidence is **observed output**, not intent.
- A failing Verify is recorded as failing. Never check off on a partial pass.
- Baselines change only when a contract makes the old value wrong; name that contract in the completion report.
- No secrets in code, tests, fixtures, docs, plan files, or trace artifacts.
- Nothing is pushed; nothing is merged; nothing is deployed from this loop.
