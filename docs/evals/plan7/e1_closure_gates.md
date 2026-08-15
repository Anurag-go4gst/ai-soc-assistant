# Plan 7 E1 Closure Gates

Date: 2026-08-15 UTC

Branch: `feat/plan7-resource-plan-authority-t4`

Starting HEAD: `0d896ee`

Architecture freeze: `a8f02e3c98b866bcb12c7d5b3db75b11e823609b`

Closure test suite result: **BLOCKED**

Production readiness result: **NOT DECIDED — E2 NOT EXECUTED**

E1 is verification only. No product behavior, target flag, provider/model, timeout,
tracked deployment default, baseline, or `architecture.md` change was made.

## Bounded convergence update after the blocked E1 attempt

The table below remains the truthful record of the first E1 attempt (10/11 gates; old reference
checker 0/10). The user then authorized a bounded convergence, not an E1 rerun. That work is now
complete:

| Item | Current result |
|---|---|
| A7 | B — `LEGACY_FALLBACK_ROLLBACK_ONLY_RETAIN_TEMPORARILY`; target graph cannot enter it; rollback path now includes deterministic postprocessing and fails closed |
| dispatch-v2 | retired/fenced from normal authority; both flags true still leaves ResourcePlan/PhaseContract authoritative |
| reference checker | authority source migrated from `pipeline_dispatch.decision` to ResourcePlan + PhaseContract/merge + current dispatch/clarification/execution |
| 10 probes | **10/10 PASS** against current target semantics; all prior drifts `EXPECTED_AUTHORITY_MIGRATION` |
| P6 | expected safety improvement: source-profile clarification, failed validation, null normalized SPL, no execution |
| development reconstruction | all six target values reproduced by `development.env.example` + unchanged repo defaults |
| `CONFIG_REBUILD_DRIFT` | **CLOSED for development profile** |
| rollback | runtime feature rollback separated from orchestration code/release rollback; v2 is not a second normal runtime authority |

Focused verification (not full E1): A7/topology **66 passed**; authority/lifecycle **208
passed**; compatibility/probe/profile **46 passed**; MCP gate/contract **43 passed**; reference
probes **10/10**; plan-discipline audit is rerun after the A7 check-off; invariant review **7/7
PASS**. Evidence: `docs/evals/plan7/a7_fallback_lifecycle_proof.md`,
`docs/evals/reference_knowledge_baseline.md`, and `docs/evals/plan7/rollback_runbook.md`.

**E1 remains unchecked.** A single final full E1 rerun is now appropriate; it was deliberately
not started in this convergence.

## Gate results

| Gate | Command | Expected | Actual | Verdict | Evidence path | Notes |
|---|---|---:|---:|---|---|---|
| Governance regression | `./scripts/run_stage3_governance_regression.sh` | PASS | PASS | PASS | command output, 2026-08-15 | Host-local run completed. Full backend segment: 5,329 passed, 3 skipped, 6 xfailed; harness 6/6; dual parity 120 exact; clean-answer 120/120; Cisco 50/0/0; dispatch matrix 5/5. Initial restricted-sandbox attempts stalled after local DB access was denied; classified `HISTORICAL_ENVIRONMENT_DRIFT`, then rerun unchanged in the intended host-local environment. |
| Full backend pytest | `cd backend && PYTHONPATH=../backend:.. python3 -m pytest -q` | Green vs P0 | 5,329 passed, 3 skipped, 6 xfailed, 0 failed; 2 warnings | PASS | command output, 2026-08-15 | 525.20 s. Warnings: LangGraph pending deprecation and the existing `DbTelemetryConnector` unawaited-coroutine warning exercised by the sanitized-error-envelope test. |
| Routing truth set | `PYTHONPATH=backend:. python3 scripts/eval_routing_truth_set.py --arm both --check --baseline docs/evals/routing_truth_set_baseline_v1.json` | 0 regressions | 0 regressions; 64/76 route_ok; unsafe 12/12 contained | PASS | command output, 2026-08-15 | A parity result is not used as routing proof. |
| Production parity | `PYTHONPATH=backend:. python3 scripts/run_production_parity_eval.py --out-dir /tmp/plan7-e1-parity.eogBK6 --check` | 120 exact | total 120; base 105; exact 120; approved 0; critical 0 | PASS | `/tmp/plan7-e1-parity.eogBK6/production_runtime_parity.json` | Scratch output only. This does not prove routing correctness. |
| Cisco deterministic suite | `AI_SOC_DISABLE_DOTENV=1 AI_SOC_SPL_DRAFT_PREVIEW_ENABLED=false python3 scripts/run_cisco_powergrid_question_eval.py --profile deterministic --min-wave wave3 --check` | 50/0/0 | PASS 50; REVIEW 0; FAIL 0; CRITICAL 0 | PASS | command output, 2026-08-15 | Deterministic/reference evaluation only; it does not resolve F3 serving stability. |
| Reference probes | Host `DATABASE_URL` transformed to `127.0.0.1:5434` without echo, then `TELEMETRY_MODE=none PYTHONPATH=backend:. python3 scripts/audit_reference_probes.py --check` | 10/10 | 0 PASS; 10 DRIFT comparisons | **BLOCKED — KNOWN_PLAN7_BLOCKER** | command output and read-only authoritative-trace inspection, 2026-08-15 | The checker reads `control_plane_trace.pipeline_dispatch.decision`, which is absent with the approved target `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED=false`; therefore all ten legacy `request_mode` and `stage_schedule` fields become null/empty. The target authority is present under `control_plane_trace.plan_dispatch`, but its schedules materially differ from the frozen v2 contract: P1–P4 include the ResourcePlan preparation phase; P5 has no committed plan; P6/N1 use the governed SPL lifecycle ending at `execution`; N3 schedules SPL/source-resolution/execution. P6 also has a real `human_review_type` delta (`intent_clarification` to `spl_source_profile_clarification`). Projecting old values would hide drift, so no harness rewrite, baseline refresh, or target-flag override was made. This is the Plan 6 reference-probe environment/gate-fidelity carry-forward now exposed against Plan 7 authority, not `CONFIG_REBUILD_DRIFT`. |
| Sentinel | `PYTHONPATH=backend:. python3 scripts/eval_sentinel.py --check` | 17/17 | 17/17 | PASS | command output, 2026-08-15 | No drift. |
| 105 path honoring | `PYTHONPATH=backend:. python3 scripts/eval_105_path_honoring.py --check` | 105/105 | 105/105; errors 0; clarification 1 (baseline 1) | PASS | command output, 2026-08-15 | All gates passed. |
| Protected manifest | `python3 scripts/freeze_execution_baseline.py --check` | current N/N | 15/15 unchanged | PASS | command output, 2026-08-15 | No baseline recapture or protected-artifact change. |
| Architecture invariants | Manual `/invariant-check` procedure | 7/7 | 7/7 | PASS | this artifact, “Invariant review” | E1 scope is evidence-only; no runtime/test/flag/architecture diff. |
| Plan discipline | `.cursor/hooks/audit-plan-discipline.sh plans/2026-08-14_1130_resource-plan-authority-and-t4-integration.md` | 0 gaps | 22 checked; 3 unchecked; 0 gaps | PASS | command output, 2026-08-15 | E1 remains unchecked because the reference gate is not 10/10. |

## Reference-probe classification

The failing check is **not** repaired in E1. The old checker compares frozen
dispatch-v2 decision fields; Plan 7's approved target deliberately has dispatch-v2
OFF and executes from ResourcePlan/PhaseContract authority. Read-only trace inspection
proved that the new authoritative schedules are present and that treating the missing
legacy trace as equivalent would mask material differences, including P5, N3, and the
P6 clarification contract.

Classification: **`KNOWN_PLAN7_BLOCKER`** (`REFERENCE_PROBE_AUTHORITY_DRIFT`), with a
proven harness-fidelity component. It is not safe to classify the entire result as
`HARNESS_DEFECT`, because at least P6 contains an analyst-visible contract delta and
the ResourcePlan schedules are not one-for-one legacy projections.

No baseline was refreshed. No test was weakened. No product behavior was changed.

## Target and carried posture

| Field | Status |
|---|---|
| `TARGET_FLAGS` | `LANGGRAPH_ORCHESTRATION_ENABLED=true`; `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED=true`; `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED=false`; `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED=true`; `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS=120`; `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED=false` |
| `MCP_MODE` | `mock` |
| `C3_CLASSIFICATION` | `T4_SEMANTICALLY_VIABLE_BUT_VPS_SERVING_BLOCKER` |
| `KNOWN_F1` | Unchanged Plan 8 dependency: DB loss may silently degrade authority to `canonical_non_planned`. |
| `KNOWN_F2` | Unchanged Plan 8 dependency: `/v1/models` liveness is not usable inference health. |
| `KNOWN_F3` | Unchanged Plan 7 critical blocker: Cisco serving stability. Green deterministic Cisco evaluation is not contrary evidence. |
| `CONFIG_REBUILD_DRIFT` | **CONFIRMED, unchanged.** Recreate persistence is proven; rebuild-from-tracked-seed persistence is not. |
| `A7_STATUS` | **UNRESOLVED.** Reachable legacy fallback remains unproven; E1 did not alter or accept it. |
| `LIVE_MCP_STATUS` | `live_mcp_unproven`; mock MCP success is not live Splunk readiness. |

## Historical report cleanup

The passing governance wrapper rewrote only the six expected stale reports. They were
restored individually; no bulk `docs/evals/` checkout was used:

1. `docs/evals/langgraph_dual_parity_report.json`
2. `docs/evals/langgraph_dual_parity_summary.md`
3. `docs/evals/soc_clean_answer_eval_report.json`
4. `docs/evals/soc_clean_answer_eval_report.csv`
5. `docs/evals/soc_clean_answer_eval_summary.md`
6. `docs/evals/llm_template_audit_report.md`

## Invariant review

1. LLM ↔ MCP mediation: **PASS** — no code or connector changes.
2. SPL executability: **PASS** — no SPL, validator, eligibility, or execution changes.
3. EC/demo purity: **PASS** — `backend/app/demo/` untouched.
4. Secrets/redaction: **PASS** — no secret value recorded; the host DB DSN was never echoed.
5. State/dual path: **PASS** — no state channel or dispatch implementation changed.
6. Flags/posture: **PASS** — no flag/default/port change; target flags were read only.
7. Test honesty: **PASS** — no test/fixture/baseline changed or weakened.

## E1 completion status

E1's explicit probe criterion is `10/10`; the actual result is `0/10` with ten
truthful DRIFT comparisons. Therefore **E1 MUST REMAIN UNCHECKED** and no E1 pass
commit or push is permitted. E2 is not structurally reached.
