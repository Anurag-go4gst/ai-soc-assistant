# Stage 3 governance regression baseline

Canonical command:

```bash
./scripts/run_stage3_governance_regression.sh
```

## Expected green (fail-closed)

| Check | Expected |
|-------|----------|
| Backend pytest | **0 failed** (skipped tests documented only) |
| Test harness | **6/6** cases with `overall_pass=true` |
| Manifest promotion audit | exit 0 |
| 105-question operation map audit | exit 0 |
| cov.q046 baseline JSON | pilot id + ≥2 scenarios |
| cov.q046 Step 7 pytest | all pass |
| cov.q046 observation summary | `status=closed`, `unexpected_disagreement_count=0` |
| Stage 3M-S5 live MCP capture | blocked without flag |
| 105-Q shadow eval | `overall_pass=True` |
| SOC validation sheets `--check` | exit 0 (staleness gate) |
| SOC validation package pytest | `test_soc_validation_package_phase10.py` all pass |
| LangGraph dual-run parity `--check` | exit 0 (Phase 13) |
| SOC clean-answer eval `--check` | exit 0 (120 rows: 105 + 8 demo + 7 manual) |
| SOC clean-answer eval pytest | `test_soc_clean_answer_eval.py` all pass |
| SKILL_ENUM contract test | backend == harness |

## Recorded counts (2026-06-03)

- Backend pytest: 897 passed, 0 failed, 1 skipped, 6 xfailed baseline anchors
- Harness: 6/6

Re-run after any control-plane change; update counts when the suite grows.

## Chat control-plane suites

Default flag-off baseline:

```bash
cd backend
PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_current_chat_runtime_baseline.py -v
```

Expected: six xfailed behavioral snapshots after schema checks, zero errors.

Flag-on golden suite:

```bash
cd backend
CONTROL_PLANE_ENABLED=true PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_chat_control_plane_golden.py -q
```

Expected: seven passed, no xfail. The suite asserts intent, evidence plan, route adjudication, SPL/MCP gating, MITRE visibility, response/synthesis mode, and `control_plane_trace`.

Phase-specific modules added by the control plane:

- `test_current_chat_runtime_baseline.py`
- `test_query_to_intent.py`
- `test_evidence_planner.py`
- `test_evidence_plan_rag_only_skip.py`
- `test_route_adjudication.py`
- `test_llm_plan_validator.py`
- `test_spl_slot_binding_validator.py`
- `test_mitre_decision_runtime.py`
- `test_response_synthesis_honesty.py`
- `test_control_plane_trace.py`
- `test_chat_control_plane_golden.py`
- `test_soc_validation_package_phase10.py`
- `test_soc_demo_readiness_phase11.py`
- `test_langgraph_shadow_phase12.py`
- `test_langgraph_dual_parity_phase13.py`

## Phase 13 LangGraph dual-run parity (evaluation only)

```bash
python3 scripts/run_langgraph_dual_parity_eval.py
python3 scripts/run_langgraph_dual_parity_eval.py --check
```

- Compares imperative `/chat` pipeline vs planner-led shadow graph (`planner_led_shadow_graph.py`) on 105-map + demo + manual rows.
- Reports: `docs/evals/langgraph_dual_parity_report.json`, `langgraph_dual_parity_summary.md`, `langgraph_dual_parity_report.csv`
- `--check` fails on critical safety mismatches (execution enabled, MITRE upgrade, SPL mismatch, runtime_active upgrade, unsafe/HIL drift, path_type drift on runtime-active rows, total below expected).
- **Does not** replace `/chat` runtime; `LANGGRAPH_ORCHESTRATION_ENABLED` remains `false` by default.

Recorded baseline (2026-06-08): **120** rows, **120** exact matches, **0** critical mismatches.

## Phase 11–13 demo / LangGraph parity (documentation)

- Flag profiles: `docs/demo/flag_cutover_matrix.md`
- Manual demo checklist: `docs/demo/demo_scenarios_readiness.md`
- Phase 12 planner-led shadow graph: `test_langgraph_shadow_phase12.py` (requires `AI_SOC_LANGGRAPH_SHADOW_ENABLED=true` in test harness only)
- Phase 13 dual-run parity: `plans/2026-06-08_langgraph-shadow-dual-parity-phases12-13.md`
- Live demo path: imperative `/chat` — keep `LANGGRAPH_ORCHESTRATION_ENABLED=false`
- Default production runtime: legacy/parity (`CONTROL_PLANE_ENABLED=false`)

## Boundaries enforced

- `ROUTE_AUTHORITY_OPERATION_AUTHORITATIVE_ENABLED=false` (production defaults)
- `MCP_GLOBAL_EXECUTION_ENABLED=false`
- No live LLM / no live Splunk in this script
- Pattern #2 not allowlisted
