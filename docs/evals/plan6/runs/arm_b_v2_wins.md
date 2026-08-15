# Plan 6 Arm B — exec ON + dispatch-v2 ON (`v2` wins)

This is **not** Plan-5 merge activation. Success is seeing `degrade_reason=dispatch_v2_projected_schedule` on composed turns that project a v2 schedule. `degrade_reason=merge` while v2 still projects would be a ladder break (STOP).

## Flags

Set `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED=true` in operator `.env` (appended; was unset). `docker compose restart` did **not** load the new key; `docker compose up -d --force-recreate --no-deps backend` did.

| Flag | Arm B live |
|---|---|
| `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | **true** |
| `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` | **true** |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` | unset → false |
| `MCP_MODE` | mock |

Git SHA: `1d32ac66dd6c707789db8b44574bd566af401952`
Harness: `python3 scripts/eval_plan6_vps_harness.py --arm A --environment-identity coe-vps-arm-b` (Arm A corpus = no paraphrases)
Run dir: `docs/evals/plan6/runs/20260813T122303Z/`
Harness exit 0. Local Verify: `test_phase_merge_activation.py` → 9 passed.

## `degrade_reason` by row

| row_id | route | degrade_reason | notes |
|---|---|---|---|
| p6.t1.knowledge | knowledge_recall | null | rag_only; no v2 projection |
| p6.t2.known_nontrivial | knowledge_recall | null | rag_only |
| p6.t4.out_of_registry | guided_investigation | **dispatch_v2_projected_schedule** | composed |
| p6.spl.draft | attack_discovery | **dispatch_v2_projected_schedule** | composed |
| p6.spl.mcp | attack_discovery | **dispatch_v2_projected_schedule** | composed |
| p6.multi.knowledge_spl_mcp | spl_generation | **dispatch_v2_projected_schedule** | composed |
| p6.clarify | knowledge_recall | null | clarification; no schedule |
| p6.unsafe | knowledge_recall | null | clarification |
| p6.alert.summary | knowledge_recall | null | rag_only |
| p6.live_posture.d1_003 | spl_generation | **dispatch_v2_projected_schedule** | composed |
| p6.repeat.refinement | spl_generation | **dispatch_v2_projected_schedule** | composed |
| p6.fail.degraded | attack_discovery | **dispatch_v2_projected_schedule** | composed |

**Zero** rows reported `degrade_reason=merge`. Ladder not broken. `phase_names` empty on all rows (merge did not run). `execution_enabled` false on all 12.

## Trace_ids (composed / v2-wins)

- `p6.t4.out_of_registry` `733465cc-6e1a-4728-80e0-c02d0522a664`
- `p6.spl.draft` `6ab799d4-5cd3-4b46-86f8-472346289f14`
- `p6.spl.mcp` `9698c954-db8f-4b01-b402-e8b79e42cc3b`
- `p6.multi.knowledge_spl_mcp` `f6f6b11c-c5fb-4a90-aa4a-77a60ded7285`
- `p6.live_posture.d1_003` `f8903bd5-0c72-4c29-8eab-edb06ee61b88`
- `p6.repeat.refinement` `a349c4aa-62fd-4323-be72-6ff1ce68923a`
- `p6.fail.degraded` `54733eeb-e7a1-434a-ba64-1e2a98376578`
