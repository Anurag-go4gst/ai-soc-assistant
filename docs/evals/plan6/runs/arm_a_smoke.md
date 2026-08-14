# Plan 6 Arm A observability smoke

Surface: VPS (`environment_identity=coe-vps`). Flags unchanged; no restart.
Harness: `python3 scripts/eval_plan6_vps_harness.py --arm A --environment-identity coe-vps`
Run dir: `docs/evals/plan6/runs/20260813T114521Z/`
Git SHA (HEAD, uncommitted Plan 6 work on tree): `1d32ac66dd6c707789db8b44574bd566af401952`
Harness exit: 0. `missing_qualification_tier`: none.

## Live flags (booleans/names only)

From `docker compose exec backend printenv` / env capture:

| Flag | Live |
|---|---|
| `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | unset → effective **false** |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` | unset → effective **false** |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS` | unset → effective **2.0** |
| `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED` | unset → effective **false** |
| `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` | **true** |
| `LANGGRAPH_ORCHESTRATION_ENABLED` | **true** |
| `MCP_MODE` | **mock** |
| `MCP_GLOBAL_EXECUTION_ENABLED` | **true** |
| `MCP_SERVER_MOCK_EXECUTION_ENABLED` | **true** |

`execution_enabled` was **false** on every Arm A row. `phase_names` empty (exec flag off, no merge). `degrade_reason` null on all 12 (expected: merge/v2-wins reasons require exec ON).

## Lane queries (T1 / T2–T3 / T4 / clarification)

| Lane | row_id | trace_id | qualification_tier | intent_family | fingerprint | dispatch_schedule |
|---|---|---|---|---|---|---|
| T1 (observed) | `p6.live_posture.d1_003` | `3dcc0565-7543-414e-8c1b-f082043619c7` | T1 | spl_generation_only | `59ad8ff3369b83a3` | yes |
| T2 (corpus t1 knowledge) | `p6.t1.knowledge` | `ff87b757-501b-448d-9779-57f9758ae7b4` | T2 | sop_or_playbook | `54643926bb51081e` | yes |
| T2–T3 | `p6.t2.known_nontrivial` | `818ee941-88aa-4589-96cc-9db1ad142316` | T2 | policy_knowledge | `54643926bb51081e` | yes |
| T4 | `p6.t4.out_of_registry` | `049b64bf-4f14-4254-8858-df2d9e23a981` | T4 | guided_investigation | `fd65002b17c46fa0` | yes |
| clarification | `p6.clarify` | `56c5c010-be86-4f71-b6be-dac8bdd87585` | T4 | clarification_required | none | no |

`p6.t1.knowledge` is labeled t1 in the corpus but resolved **T2** on this VPS. A T1 qualification is present on the ratified live-posture row.

## Field-presence list (`explainability.debug_summary`)

Present on all 12 `/debug` bundles:

- `resolved_query.qualification_tier`
- `resolved_query.intent_family`
- `resolved_query.answer_goal`
- `resolved_query.ambiguity_state`
- `schedule` object (`resource_plan_fingerprint` when a plan exists; `degrade_reason`; `dispatch_schedule`; `phase_names`)

Filling-first: missing `qualification_tier` would fail the harness. It did not.

## Remaining Arm A trace_ids

| row_id | trace_id | qualification_tier | route |
|---|---|---|---|
| p6.spl.draft | `4e90dcdc-5be3-4e4d-a6f9-e20e5d4469b9` | T2 | attack_discovery |
| p6.spl.mcp | `37907dbb-4749-40bf-b503-ef64e50d89ba` | T2 | attack_discovery |
| p6.multi.knowledge_spl_mcp | `2cf9dd20-fb17-4fb1-b8db-ca31bff653c6` | T2 | spl_generation |
| p6.unsafe | `cbf7da90-bf25-4b50-bf6f-c59623e30213` | T4 | knowledge_recall |
| p6.alert.summary | `5dfd4b74-c06a-4fee-ba22-593f59c295e9` | T2 | knowledge_recall |
| p6.repeat.refinement | `33b20e21-d244-4ec2-b087-dc6f890f42e5` | T4 | spl_generation |
| p6.fail.degraded | `b2ae19c2-7f20-45a2-9080-fce72190d957` | T2 | attack_discovery |
