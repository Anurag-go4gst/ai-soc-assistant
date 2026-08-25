# Loop runner: AI-SOC master parallel closure

Canonical plan: `plans/2026-08-25_1806_ai-soc-master-parallel-closure.md`

Use this file as the durable execution dashboard. Update it only during authorized implementation. Never infer state from chat history. The master plan owns scope, dependencies, file ownership, invariants, and phase acceptance criteria; this runner owns current execution state and evidence pointers.

## Control state

```yaml
CURRENT_PHASE: OPERATOR_PLAN_REVIEW
CURRENT_BASE_SHA: 615069e6ca9cdb3d40b51d6a2f071346ecf3d6a2
INTEGRATION_BRANCH: feat/complete-or-abstain-t4-ux
INTEGRATION_OWNER: CODEX
ACTIVE_WORKSTREAMS: []
BLOCKED_WORKSTREAMS:
  - P1-P11: plan not yet operator-approved for implementation
COMPLETED_WORKSTREAMS:
  - P0: Harness readiness at 615069e6ca9cdb3d40b51d6a2f071346ecf3d6a2
NEXT_SAFE_PARALLEL_STARTS:
  - P1 TRACE after operator freezes INTEGRATION_SHA
  - P2 SPL after operator freezes the same INTEGRATION_SHA
  - P3 L2 scaffold after operator freezes the same INTEGRATION_SHA
RECONCILIATION_QUEUE: []
MERGE_QUEUE: []
PROTECTED_CHANGE_QUEUE: []
TEST_GATE_STATUS:
  PLAN_AUDIT: pending
  FOCUSED: not_started
  L0: not_started
  L1: not_started
  L2: P0_13_reported_green_at_base
  L2_SLOW: not_started
  L3: not_started
  FRONTEND: P0_111_and_build_reported_green_at_base
  GOVERNANCE: not_started_for_new_candidate
  LINUX: not_started
  LIVE_MCP: disabled_deferred_P11
RESIDUAL_FAILURE_LEDGER:
  - rt.para.011: carry_forward_remeasure_required
  - github_skill_clone_root: carry_forward_environment_dependency
  - postgres_integration_families: carry_forward_exact_ids_required
  - migration_and_plugin_environment: carry_forward_exact_ids_required
  - RACES_baseline_state: carry_forward_protected_decision_if_still_failing
DECISION_LOG:
  - 2026-08-25: P0 accepted as completed baseline; do not redo.
  - 2026-08-25: Plan-only mission; no worktrees or product changes created.
  - 2026-08-25: plans/README.md intentionally not edited because mission allowed only two plan artifacts.
```

## Workstream registry

| Stream | Phase(s) | Agent | Branch | Start SHA | Status | Exclusive ownership |
|---|---|---|---|---|---|---|
| A TRACE | P1 | CODEX | `codex/closure-trace-truth` | unset | BLOCKED_REVIEW | Trace/provenance modules and tests |
| B SPL | P2 | CURSOR | `codex/closure-spl-semantic-v2` | unset | BLOCKED_REVIEW | SPL semantic/compiler/fidelity/live SPL prompt modules and tests |
| C EVAL | P3, P5, P6 | CLAUDE | `codex/closure-l2-eval-bank` | unset | BLOCKED_REVIEW | L2 bank and test architecture only |
| D POLICY | P4 | CLAUDE | `codex/closure-prompt-policy` | unset | BLOCKED_P2_FOR_WRITES | Generic prompt/role/policy files and tests |
| E UI | P7 | CURSOR | `codex/closure-production-ux` | unset | BLOCKED_P5 | Production non-EC frontend and tests |
| F PROMOTION | P8-P11 | CODEX/operator | `codex/closure-promotion-coe` | unset | BLOCKED_P5 | L3/promotion/COE evidence only |

## Loop entry checks

Run before every bounded item:

```bash
pwd
git rev-parse --show-toplevel
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git status --short
git log --oneline -12
```

Required root is `/Users/aagarwal/Downloads/ai-soc-assistant-t4-architecture-20260821` or the explicitly recorded worktree root. Never reset on SHA mismatch. Record the mismatch, determine whether the branch is correctly rebased, and stop if it is unexplained. Preserve unrelated changes, especially `.claude/settings.local.json`; do not stage them.

Before implementation of any plan item, read:

```text
AGENTS.md
architecture.md
docs/ai/t4_semantic_prompting_playbook.md  # mandatory for prompt/schema/few-shot/merge work
.claude/skills/execute-plan-item/SKILL.md
.claude/skills/invariant-check/SKILL.md
plans/2026-08-25_1806_ai-soc-master-parallel-closure.md
plans/LOOP_RUNNER_ai-soc-master-parallel-closure.md
```

Audit the canonical plan before first implementation and after structural plan edits:

```bash
.cursor/hooks/audit-plan-discipline.sh plans/2026-08-25_1806_ai-soc-master-parallel-closure.md
```

## One loop iteration

1. Inspect repository SHA, branch, and status using the entry checks.
2. Read the canonical plan and this dashboard; honor the newest operator decision.
3. Locate the first eligible TODO item in dependency order. Do not select a blocked phase because an agent is idle.
4. Check every dependency and confirm the phase BASE_SHA or required rebase SHA.
5. Check exclusive file ownership before editing. If another active stream owns a needed file, add a bounded request to `RECONCILIATION_QUEUE` and stop that item.
6. Restate the one bounded checklist item, its invariant, allowed files, protected files, and exact verification.
7. Execute only that item. Follow `implement -> verify -> evidence -> check off`; do not bundle adjacent cleanup.
8. Run focused tests. Run phase-level gates only when the phase's acceptance criteria are otherwise met.
9. If green and explicitly authorized to commit implementation, commit one logical change with only owned files. Never include unrelated or generated baseline drift.
10. Update the canonical plan item status/evidence and this dashboard with SHA, command/result, failures, queues, and next unlock. A plan-status commit must be scoped and authorized like any other commit.
11. If a protected file or operator decision is needed, STOP before editing, enqueue the exact proposed diff and tests in `PROTECTED_CHANGE_QUEUE`, and report `OPERATOR_APPROVAL_REQUIRED`.
12. Never push, merge, deploy, enable live MCP, rotate/configure secrets, or alter production from this loop.

If the same verification gate fails twice on the same bounded item, mark the workstream blocked with exact failure evidence and stop. Do not weaken tests or thresholds.

## Eligibility rules

- `P1`, `P2`, and P3 scaffold are the only first parallel start set, and all must use the same frozen SHA.
- P4 read-only audit may overlap, but P4 writes wait for P2 and cannot touch B-owned `llm_fallback.py`.
- P5 waits for merged P1/P2/P4 and rebased P3.
- P6 waits for green expanded L2.
- P7 and P8 may overlap after P5 only because E owns frontend and F owns eval artifacts. Any runtime defect returns to A/B/D.
- P9 waits for P6/P7/P8.
- P10 waits for P9 GO and stops for operator network actions.
- P11 is last, default-off, and requires separate COE approval.

## Reconciliation queue schema

```text
REQUEST_ID:
REQUESTING_STREAM:
OWNING_STREAM:
FILE_OR_CONTRACT:
REQUIRED_CHANGE:
WHY:
DEPENDENT_ITEM:
PROPOSED_TEST:
STATUS: QUEUED | ACCEPTED | REJECTED | MERGED
RESOLUTION_SHA:
```

The owning stream implements or rejects the request. The integrator never resolves semantic conflicts by selecting the latest version.

## Protected change queue schema

```text
REQUEST_ID:
PHASE:
PROTECTED_FILE:
EXACT_PROPOSED_DIFF:
WHY_NO_UNPROTECTED_ALTERNATIVE:
INVARIANTS_AFFECTED:
TESTS_REQUIRED:
ROLLBACK:
OPERATOR_APPROVAL: PENDING | APPROVED(reference) | REJECTED
```

No protected file may be edited while approval is PENDING. `architecture.md` is not eligible even through this queue; an architecture conflict stops the plan for a separate decision.

## Merge queue and return packet

Queue order:

1. A P1 trace
2. B P2 SPL, rebased after A
3. D P4 policy, implemented/rebased after B
4. C P3/P5 L2 bank, rebased after A/B/D
5. C P6 rationalization after expanded L2 green
6. F P8 L3 artifacts and separately promoted fixes
7. E P7 UI and any approved protected diff
8. F P9 promotion evidence

Each entry must attach:

```text
START_SHA:
END_SHA:
COMMITS:
FILES_CHANGED:
PROTECTED_FILES_CHANGED: NONE | list with approval reference
TESTS: exact commands and results
KNOWN_FAILURES: exact test IDs and classifications
CONTRACT_CHANGES:
REBASE_REQUIRED: YES | NO, target SHA
```

Before accepting an entry, the integration owner confirms ownership, rebases/merges against the declared integration SHA, reruns affected cross-stream tests, updates `CURRENT_BASE_SHA`, and records the new integration SHA. Working streams never push or merge themselves.

## Test gates

Use the host virtual environment unless a phase explicitly records another controlled runner.

```bash
# Focused backend
cd backend && ../.venv/bin/python -m pytest -q <test paths or node IDs>

# Harness independence
PYTHONPATH=backend:. .venv/bin/python -m test_harness.harness.runner --json

# Full backend promotion gate
cd backend && ../.venv/bin/python -m pytest -q -p no:cacheprovider

# Frontend
cd frontend && npm test && npm run build

# Governance on host venv
PATH="$PWD/.venv/bin:$PATH" ./scripts/run_stage3_governance_regression.sh
```

Do not run the full backend suite after each small edit. Run FOCUSED per item, the phase's L0/L1/L2/L2-slow gates at phase completion, and the full Mac/Linux matrix at P9. Never substitute an easier command for a blocked mandatory gate.

## Residual failure ledger schema

Seed entries are in the canonical plan. Expand them by exact identity:

| Test or row ID | Baseline SHA/result | Candidate SHA/result | Classification | Environment dependency | Evidence | Promotion decision | Owner |
|---|---|---|---|---|---|---|---|
| `rt.para.011` | remeasure | pending | routing residual | none known | pending | pending | integration |
| GitHub skill factory exact test | missing clone root in prior Mac run | pending | environment | `AI_SOC_GITHUB_SKILL_CLONE_ROOT` | pending | pending | promotion |
| PostgreSQL integration exact IDs | 14 prior env failures | pending | environment | PostgreSQL | pending | pending | promotion |
| migration readiness exact IDs | 5 prior env failures | pending | environment | DB/migrations/plugins | pending | pending | promotion |
| RACES freeze exact test | prior baseline-state failure | pending | protected decision | reviewed baseline | pending | pending | operator |

"Pre-existing" alone is not a classification. Record whether the same named test failed at the declared baseline, why, what environment is required, and whether promotion accepts, fixes, or blocks it.

## Phase completion update

For each phase completion, update both files with:

```text
STATUS: DONE
START_SHA:
END_SHA:
COMMITS:
VERIFY_COMMANDS_AND_RESULTS:
ACCEPTANCE_CRITERIA_EVIDENCE:
DRIFT_OR_SCOPE_CHANGES:
KNOWN_FAILURES:
PROTECTED_APPROVALS:
NEXT_PHASE_UNLOCK:
```

Then re-walk every item against its `Verify` and `ACCEPTANCE_CRITERIA`; do not inherit a checkmark merely because code exists.

## Decision log

Append decisions; do not rewrite history.

| Date/time | Phase | Decision | Evidence/approval | Consequence |
|---|---|---|---|---|
| 2026-08-25 18:06 IST | Plan | P0 is the frozen starting candidate at `615069e6` | Repository inspection | P1/P2/P3 scaffold are first starts after review |
| 2026-08-25 18:06 IST | Plan | No README update in plan-only commit | Mission allowed only two plan files | Historical index update remains out of scope |
| 2026-08-25 18:06 IST | Plan | Live MCP is terminal P11 and default-off before then | Architecture and mission | No earlier stream may test real MCP |

## Runner stop

Stop and report when all eligible work is complete, the same gate fails twice, a protected change is needed, a dependency or authority premise is wrong, ownership conflicts, an unexplained regression appears, or operator/environment input is required. A stopped loop reports the exact blocker, evidence, safest next decision, and unchanged safety posture. It never resets, pushes, merges, deploys, edits architecture, or enables live MCP.
