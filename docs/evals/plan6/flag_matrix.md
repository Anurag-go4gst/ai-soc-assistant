# Plan 6 — flag matrix

Live VPS values filled in **A4**, then **B0/B1** test arms, then **B1 restore Arm A**. Booleans/names only; no secrets. After B1 restore, exec is explicit `false` in operator `.env` (A4 had it unset; effective value is the same).

Flags stay independently controllable. Persistent VPS ON is not the same as a `config.py` default of true.

## Plan 5 activation flags

| Flag | Repo default | COE profile | Live VPS (A4) | Candidate final |
|---|---|---|---|---|
| `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | false (`config.py:410`) | **false** (F2 persist; not `true`) | **false** (F2 recreate docker) | **C0 KEEP OFF.** Repo default stays false. F2 persisted explicit `false`. F5 still records go-live. Arm C merge 5/12 was reachability proof, not production authority. |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` | false (`config.py:413`) | **omitted** (comment only; do not add `true`) | **false** (operator `.env` explicit OFF; F2 recreate docker) | **D3 KEEP DEFAULT-OFF.** Omit T4 from git profile. `D1_PARAPHRASE_RESIDUE = DEFERRED_T4_SEMANTIC_SERVING_LIMIT`. |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS` | 2.0 (`config.py:414`) | absent → 2.0 | **unset → effective 2.0** | **D3 KEEP 2.0s.** Do not raise. Independent of enable. |
| `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED` | false (`config.py:417`) | **false** (F2 persist) | **false** (F2 recreate docker; was unset at A4) | stays **OFF** unless new evidence reopens Plan 5 B5. Not a VPS activation arm. |
| `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` | false (`config.py:403`) | **true** (`coe.env.example`) | **true** (F2 recreate docker) | **C0 Field 2 N/A** (exec remains OFF). Keep v2 **ON** in current VPS/COE posture. `CHANGE_LADDER` was not selected. |

## Already-on VPS/COE (do not silently change)

| Flag | Repo default | COE profile | Live VPS (A4) | Notes |
|---|---|---|---|---|
| `LANGGRAPH_ORCHESTRATION_ENABLED` | true | true | **true** | Default `/chat` is `run_chat_via_resource_planner_graph`. |
| `AI_SOC_GUIDED_HYBRID_INVESTIGATION_ENABLED` | false | true | **true** | Do not silently change. |
| `AI_SOC_GUIDED_LLM_ENABLED` | false | true | **true** | Budget/deadline only. No planning-model hop. |
| `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED` | false | true | **true** | Both this and live-synthesis required for live composer. |
| `AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED` | false | true | **true** | Same pair. |
| `AI_SOC_T2_ANSWER_SHAPE_ENABLED` | false | true | **true** | T2 shape/surfacing/RAG. |
| `AI_SOC_T2_ANSWER_SURFACING_ENABLED` | false | true | **true** | |
| `AI_SOC_T2_RAG_SURFACING_ENABLED` | false | true | **true** | |
| `MCP_MODE` | (connector) | `mock` | **mock** | Mock MCP may validate architecture; live Splunk is F3. |
| `MCP_GLOBAL_EXECUTION_ENABLED` | false | true | **true** | COE mock execution path. |
| `MCP_SERVER_MOCK_EXECUTION_ENABLED` | false | true | **true** | Must stay mock unless F3 live test. |

## Retired / not flags

| Name | Status |
|---|---|
| `UNDERSTANDING_ROUTER_ON_LOW_CONFIDENCE` | Retired (Plan 4). Not a routing authority. |
| `CONTROL_PLANE_ENABLED` | Retired. Canonical planning is unconditional. |
| `AI_SOC_CANONICAL_PLANNING_ENABLED` | Retired / historical. |
| Schedule-shadow flag | **Does not exist.** `ROUTE_AUTHORITY_COMPARE_ENABLED` compares routes, not schedules. Plan 6 A3 is compute-both / execute-once, no new env flag. |

## Precedence reminder

`AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED=true` is **not** proof that Plan 5 `merge_schedule` is active. See `execution_path_map.md`.
