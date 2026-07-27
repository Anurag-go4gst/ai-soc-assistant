# SOC Assistant — Flag Cutover Matrix (Phase 11)

Documentation only. **Does not change runtime defaults.** Production and `.env.example` keep safe legacy/parity posture until operators explicitly flip flags in a target environment.

## Architecture posture

| Topic | Status |
|-------|--------|
| Phases 0–10 | Implemented and tested (crosswalk → validation package) |
| Adopted test/demo path | Governed **imperative** `/chat` pipeline with explicit flags |
| LangGraph fan-out/fan-in | **Shadow graph exists (Phase 12)** — `AI_SOC_LANGGRAPH_SHADOW_ENABLED` for tests/trace only; not default runtime |
| LangGraph dual-run parity | **Phase 13 evaluation only** — `scripts/run_langgraph_dual_parity_eval.py`; does not cut over `/chat` |
| Default production runtime | Canonical planning always on; MCP execution off in safe profiles |
| SPL/MCP execution | Remains **disabled** in all documented profiles below |

`LANGGRAPH_ORCHESTRATION_ENABLED` runs the legacy P1 linear LangGraph parity wrapper when explicitly enabled. The **Phase 12 planner-led shadow graph** (`backend/app/graph/planner_led_shadow_graph.py`) implements fan-out/fan-in topology for parity tests only via `AI_SOC_LANGGRAPH_SHADOW_ENABLED=false` (default). It is **not** the live `/chat` runtime path. Keep both flags **off** for manual demo and answer-quality testing.

---

## Profile 1 — Default-safe (production / CI / `.env.example`)

| Flag | Value |
|------|-------|
| `AI_SOC_PLANNER_PATH_SELECTION_ENABLED` | `false` |
| `AI_SOC_LLM_INTENT_ADVISOR_ENABLED` | `false` |
| `AI_SOC_CURATED_ENRICHMENT_ACTIVATION_ENABLED` | `false` |
| `AI_SOC_PLANNER_MITRE_BRANCH_ENABLED` | `false` |
| `AI_SOC_SPL_TEMPLATE_GOVERNANCE_ENABLED` | `false` |
| `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED` | `false` |
| `AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED` | `false` |
| `MCP_GLOBAL_EXECUTION_ENABLED` | `false` |
| `MCP_SERVER_MOCK_EXECUTION_ENABLED` | `false` |
| `LANGGRAPH_ORCHESTRATION_ENABLED` | `false` |
| `AI_SOC_LANGGRAPH_SHADOW_ENABLED` | `false` |
| `AI_SOC_LLM_SPL_FALLBACK_ENABLED` | `false` |

**Behavior:** Legacy backward-compatible `/chat` path. No mock or real Splunk MCP execution. No live LLM composer narration. Governance regression and harness run against this baseline.

---

## Profile 2 — Safe manual demo / answer-quality (recommended local COE)

Enable governed canonical planning + planner track + LLM composer **without** execution:

| Flag | Value |
|------|-------|
| `AI_SOC_PLANNER_PATH_SELECTION_ENABLED` | `true` |
| `AI_SOC_LLM_INTENT_ADVISOR_ENABLED` | `true` |
| `AI_SOC_CURATED_ENRICHMENT_ACTIVATION_ENABLED` | `true` |
| `AI_SOC_PLANNER_MITRE_BRANCH_ENABLED` | `true` |
| `AI_SOC_SPL_TEMPLATE_GOVERNANCE_ENABLED` | `true` |
| `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED` | `true` |
| `AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED` | `true` |
| `MCP_GLOBAL_EXECUTION_ENABLED` | `false` |
| `MCP_SERVER_MOCK_EXECUTION_ENABLED` | `false` |
| `LANGGRAPH_ORCHESTRATION_ENABLED` | `false` |
| `AI_SOC_LANGGRAPH_SHADOW_ENABLED` | `false` |
| `AI_SOC_LLM_SPL_FALLBACK_ENABLED` | `false` |

Also configure a local/openai-compatible endpoint (`AI_SOC_LLM_LOCAL_BASE_URL`) for live synthesis narration. Facts (severity, MITRE status, SPL, `execution_eligible=false`) remain deterministic authority.

**No-execution guarantee:** With both MCP execution flags `false`, candidate SPL is never executed via MCP (mock or real). SPL stays review-only; only approved `normalized_spl` could enter an execution gate, and the gate remains closed.

---

## Profile 3 — Not approved for Phase 11 demos

| Flag | Why off |
|------|---------|
| `MCP_GLOBAL_EXECUTION_ENABLED=true` | Enables MCP execution gate; violates no-execution demo contract |
| `MCP_SERVER_MOCK_EXECUTION_ENABLED=true` | Requires global flag; runs bounded mock rows |
| `LANGGRAPH_ORCHESTRATION_ENABLED=true` | Legacy P1 linear graph only — not the Phase 12 shadow topology |
| `AI_SOC_LANGGRAPH_SHADOW_ENABLED=true` | Tests/trace only — does not replace `/chat` unless harness invokes shadow runner |
| `AI_SOC_LLM_SPL_FALLBACK_ENABLED=true` | LLM SPL advisory bypass risk; keep off outside controlled lab |

---

## Cutover sequence (post SOC validation sign-off)

1. SOC reviews `docs/validation/*` sheets and promotes rows in the crosswalk (`validation_status=soc_approved`).
2. Run `./scripts/run_stage3_governance_regression.sh` green in target environment.
3. Flip flags incrementally per environment, re-running golden + governance regression after each step:
   - Canonical planning is always on (no env toggle).
   - Planner flags (`PATH_SELECTION`, `CURATED_ENRICHMENT`, `MITRE_BRANCH`, `SPL_TEMPLATE_GOVERNANCE`)
   - Optional: `AI_SOC_LLM_INTENT_ADVISOR_ENABLED`, synthesis flags (with configured local endpoint)
4. Keep `MCP_GLOBAL_EXECUTION_ENABLED=false` until COE supplies real Splunk MCP contract and approval workflow.
5. Phase 12 shadow graph parity must be accepted in CI before considering LangGraph as runtime; production cutover still uses imperative `/chat` with flags until explicitly approved.
6. Phase 13 dual-run parity (`python3 scripts/run_langgraph_dual_parity_eval.py --check`) must report **zero critical mismatches** before any LangGraph runtime cutover. Evaluation harness enables shadow graph in-process only; production defaults keep `LANGGRAPH_ORCHESTRATION_ENABLED=false` and `AI_SOC_LANGGRAPH_SHADOW_ENABLED=false`.

---

## Related artifacts

- Validation sheets: `docs/validation/README.md`
- Demo scenario checklist: `docs/demo/demo_scenarios_readiness.md`
- LangGraph dual-run parity report: `docs/evals/langgraph_dual_parity_summary.md`
- Real Splunk MCP gates: `docs/architecture/real_splunk_mcp_safety_contract.md`
