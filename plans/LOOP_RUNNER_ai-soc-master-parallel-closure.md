# Loop runner: AI-SOC master parallel closure

Canonical plan: `plans/2026-08-25_1806_ai-soc-master-parallel-closure.md`

Use this file as the durable execution dashboard. Update it only during authorized implementation. Never infer state from chat history. The master plan owns scope, dependencies, file ownership, invariants, and phase acceptance criteria; this runner owns current execution state and evidence pointers.

## Control state

```yaml
CURRENT_PHASE: P4_1_CLEAN_WITH_ENVIRONMENT_RESIDUAL_P3_REBASE_REQUIRED
CURRENT_BASE_SHA: 7f763b5b12078534e96f1860474138b7dcc83707
INTEGRATION_SHA: FINAL_CLEAN_INTEGRATION_SHA_THIS_GOVERNANCE_COMMIT
EXECUTION_INTEGRATION_SHA: FINAL_CLEAN_INTEGRATION_SHA_THIS_GOVERNANCE_COMMIT
FINAL_CLEAN_INTEGRATION_SHA: FINAL_CLEAN_INTEGRATION_SHA_THIS_GOVERNANCE_COMMIT
P4_1_LAST_TEST_SHA: 7f763b5b12078534e96f1860474138b7dcc83707
P4_1_STATUS: CLEAN_WITH_ENVIRONMENT_RESIDUAL
P1_PRODUCT_INTEGRATION_SHA: fd77d58ea1e9690eec25a83aa90d46949c4512b5
P2_PRODUCT_INTEGRATION_SHA: 7fbdf83f4508886529121998256face8d3c9edf1
P4_PRODUCT_INTEGRATION_SHA: cdb146df32b0214aa96bac8d037891835b696a46
PLAN_PREPARATION_SHA: fe3548e475e61e77f5204e02f74efd28690abb86
P0_PRODUCT_BASELINE_SHA: 615069e6ca9cdb3d40b51d6a2f071346ecf3d6a2
CURRENT_LOOP: NONE
LOOP_ITERATION_ID: NONE
READY_FOR_OPERATOR_REVIEW: YES
PYVENV: /Users/aagarwal/Downloads/ai-soc-assistant-t4-architecture-20260821/.venv/bin/python
INTEGRATION_BRANCH: feat/complete-or-abstain-t4-ux
INTEGRATION_OWNER: CODEX
ACTIVE_WORKSTREAMS: []
BLOCKED_WORKSTREAMS:
  - P3 C EVAL: PARKED at 838659ada898b5a8bf071fda2b233c125f51ac00; exact rebase required onto FINAL_CLEAN_INTEGRATION_SHA in the next authorized iteration
  - P5 C/Integration: BLOCKED_PENDING_P3_REBASE
COMPLETED_WORKSTREAMS:
  - P0: Harness readiness at 615069e6ca9cdb3d40b51d6a2f071346ecf3d6a2
  - P0.1: RACES baseline advanced and verified at ae03a2502ab4c83797151a11d4effa47d9d4532b
  - P1: TRACE truth integrated at fd77d58ea1e9690eec25a83aa90d46949c4512b5; T1/T2/T3 PASS
  - P2: SPL semantic V2 integrated at 7fbdf83f4508886529121998256face8d3c9edf1; S1-S6 PASS
  - P4: Prompt/policy architecture integrated at cdb146df32b0214aa96bac8d037891835b696a46; PP1-PP6 PASS
  - P4.1: Residual baseline cleanup at P4_1_LAST_TEST_SHA 7f763b5b; CLEAN_WITH_ENVIRONMENT_RESIDUAL (GitHub clone root only)
NEXT_SAFE_PARALLEL_STARTS:
  - P3 exact rebase onto FINAL_CLEAN_INTEGRATION_SHA in a separately authorized iteration, then reprove E1. Combined P3 rebase plus PENDING_CONTRACT_P1/P2/P4 activation is the next operation; it must not start in this iteration.
RECONCILIATION_QUEUE:
  - REQUEST_ID: P1-T2-EVIDENCESTATE-OWNERSHIP
    REQUESTING_STREAM: A TRACE
    OWNING_STREAM: A TRACE / CODEX
    FILE_OR_CONTRACT: backend/app/evidence/minimal_evidence_state.py plus directly corresponding H-TRACE-03/H-TRACE-08 truth tests
    REQUIRED_CHANGE: execution metadata and plan_step_outcome/canonical plan facts must not become obtained evidence; distinguish required/missing/diagnostic facts from accepted obtained evidence
    WHY: P1 owns factual trace/evidence projection truth; this is not SPL semantics, routing, planning authority, MCP execution authority, or prompt policy
    DEPENDENT_ITEM: P1 T2/T3
    PROPOSED_TEST: execution-only and plan-only inputs never produce obtained RAG/MCP evidence; accepted collected evidence remains obtained
    STATUS: MERGED
    RESOLUTION_SHA: fd77d58ea1e9690eec25a83aa90d46949c4512b5
MERGE_QUEUE: []
PROTECTED_CHANGE_QUEUE: []
PROTECTED_CHANGE_HISTORY:
  - REQUEST_ID: P2-FINAL-RQC-PIPELINE-WIRING
    FILE: backend/app/chat/pipeline.py
    APPLIED_SHA: 5921f1d0cf569695db97ef0fd277ffdac8ec5338
    RACES_BASELINE_SHA: 5921f1d0cf569695db97ef0fd277ffdac8ec5338
    STATUS: APPLIED_VERIFIED
TEST_GATE_STATUS:
  PLAN_AUDIT: passed_zero_gaps_both_files
  FOCUSED: P4_prompt_policy_702_passed_post_P4_1
  L0: RACES_8_passed_post_P4_1; reasoning_reachability_2_passed
  L1: P1_trace_evidence_75_passed_1_skipped; P2_semantic_plus_LIVE_RQC_79_passed
  L2: P0_13_passed_post_P4_1
  L2_SLOW: not_started
  L3: not_started
  FRONTEND: P0_111_and_build_reported_green_at_base
  GOVERNANCE: P4_1_CLEAN_WITH_ENVIRONMENT_RESIDUAL
  LINUX: not_started
  LIVE_MCP: disabled_deferred_P11
  FULL_BACKEND_P4_1: 1_failed_6971_passed_45_skipped_6_xfailed
  NEW_FAILURES: NONE
RESIDUAL_FAILURE_LEDGER:
  - app/tests/test_canonical_handoff_e2e_probes.py::test_e2e_t1_spl_generation_canonical_graph_and_gate: PRE_EXISTING_FAILURE; P5/P9; blocks_P4_NO
  - app/tests/test_canonical_handoff_e2e_probes.py::test_e2e_environment_kb_user_explicit_precedence: PRE_EXISTING_FAILURE; P5/P9; blocks_P4_NO
  - app/tests/test_chat_control_plane_golden.py::test_known_questions_use_specific_raw_templates[Write SPL to find successful AWS Console logins by user in the last 24 hours-aws_console_success_logins_by_user-required_terms0-forbidden_terms0]: PRE_EXISTING_FAILURE; P5/P9; blocks_P4_NO
  - app/tests/test_evidence_loop_all_tier_discovery.py::test_live_data_spl_query_runs_real_discovery_hops_in_mock_mode: PRE_EXISTING_FAILURE; P5/P9; blocks_P4_NO
  - app/tests/test_github_skill_expansion_factory_baseline.py::test_factory_generators_check_against_committed_artifacts: PRE_EXISTING_FAILURE; P9 environment; blocks_P4_NO
  - app/tests/test_in_catalogue_contract_guard.py::test_full_guard_passes_against_baseline: PRE_EXISTING_FAILURE; P5/P9; blocks_P4_NO
  - app/tests/test_llm_primary_planning.py::test_in_catalogue_contract_guard_still_green: PRE_EXISTING_FAILURE; P5/P9; blocks_P4_NO
  - app/tests/test_migration_readiness.py::test_apply_pending_migrations_skips_recorded_versions: PRE_EXISTING_FAILURE; P9 environment; blocks_P4_NO
  - app/tests/test_migration_readiness.py::test_missing_migrations_fail_closed_from_active_event_loop: PRE_EXISTING_FAILURE; P9 environment; blocks_P4_NO
  - app/tests/test_migration_readiness.py::test_unexpected_readiness_error_surfaces_fail_closed: PRE_EXISTING_FAILURE; P9 environment; blocks_P4_NO
  - app/tests/test_pipeline_dispatch_phase2a.py::test_pipeline_dispatch_attached_after_cp_on_evidence_planning: PRE_EXISTING_FAILURE; P5/P9; blocks_P4_NO
  - app/tests/test_pipeline_dispatch_phase2a.py::test_pipeline_dispatch_cp_off_stub_attached_when_v2_enabled: PRE_EXISTING_FAILURE; P5/P9; blocks_P4_NO
  - app/tests/test_t2_spl_native_live.py::test_asa_ioc_lookup_live_review_only: PRE_EXISTING_FAILURE; B SPL P5/P9; blocks_P4_NO
  - app/tests/test_t2_spl_native_live.py::test_asa_ioc_lookup_checklist_is_operation_aware: PRE_EXISTING_FAILURE; B SPL P5/P9; blocks_P4_NO
P4_1_RESIDUAL_DISPOSITION:
  - test_e2e_t1_spl_generation_canonical_graph_and_gate: ORIGINAL PRE_EXISTING_FAILURE; P4_1 STALE_EXPECTATION; REPRO PASS; FIX 2303de66; CLOSED
  - test_e2e_environment_kb_user_explicit_precedence: ORIGINAL PRE_EXISTING_FAILURE; P4_1 STALE_EXPECTATION; REPRO PASS; FIX 2303de66; CLOSED
  - test_known_questions_use_specific_raw_templates[AWS Console...]: ORIGINAL PRE_EXISTING_FAILURE; P4_1 STALE_EXPECTATION; ORIGINAL_NODE_RETIRED replacement test_aws_console_success_logins_requires_governed_source_binding PASS; FIX 7f2663be; CLOSED
  - test_live_data_spl_query_runs_real_discovery_hops_in_mock_mode: ORIGINAL PRE_EXISTING_FAILURE; P4_1 STALE_EXPECTATION; ORIGINAL_NODE_RETIRED replacement test_explicit_spl_authoring_stays_review_only_in_mock_mode PASS; FIX 2303de66; CLOSED
  - test_factory_generators_check_against_committed_artifacts: ORIGINAL PRE_EXISTING_FAILURE; P4_1 ENVIRONMENT_FAILURE; REPRO FAIL; FIX NONE; OPEN_ENVIRONMENT_RESIDUAL
  - test_full_guard_passes_against_baseline: ORIGINAL PRE_EXISTING_FAILURE; P4_1 STALE_EXPECTATION; REPRO PASS; FIX 7f2663be; CLOSED
  - test_in_catalogue_contract_guard_still_green: ORIGINAL PRE_EXISTING_FAILURE; P4_1 STALE_EXPECTATION; REPRO PASS; FIX 7f2663be; CLOSED
  - test_apply_pending_migrations_skips_recorded_versions: ORIGINAL PRE_EXISTING_FAILURE; P4_1 TEST_DEFECT; REPRO PASS; FIX 06bdf411; CLOSED
  - test_missing_migrations_fail_closed_from_active_event_loop: ORIGINAL PRE_EXISTING_FAILURE; P4_1 TEST_DEFECT; REPRO PASS; FIX 06bdf411; CLOSED
  - test_unexpected_readiness_error_surfaces_fail_closed: ORIGINAL PRE_EXISTING_FAILURE; P4_1 TEST_DEFECT; REPRO PASS; FIX 06bdf411; CLOSED
  - test_pipeline_dispatch_attached_after_cp_on_evidence_planning: ORIGINAL PRE_EXISTING_FAILURE; P4_1 STALE_EXPECTATION; REPRO PASS; FIX 04fed4ab; CLOSED
  - test_pipeline_dispatch_cp_off_stub_attached_when_v2_enabled: ORIGINAL PRE_EXISTING_FAILURE; P4_1 STALE_EXPECTATION; REPRO PASS; FIX 04fed4ab; CLOSED
  - test_asa_ioc_lookup_live_review_only: ORIGINAL PRE_EXISTING_FAILURE; P4_1 STALE_EXPECTATION; REPRO PASS; FIX 7f763b5b; CLOSED
  - test_asa_ioc_lookup_checklist_is_operation_aware: ORIGINAL PRE_EXISTING_FAILURE; P4_1 STALE_EXPECTATION; REPRO PASS; FIX 7f763b5b; CLOSED
DECISION_LOG:
  - 2026-08-25: P0 accepted as completed baseline; do not redo.
  - 2026-08-25: fe3548e4 is PLAN_PREPARATION_SHA; first-wave work starts from the final operator-frozen EXECUTION_INTEGRATION_SHA.
  - 2026-08-25: P0.1 audit/proposal and apply are separate approvals; neither has executed.
  - 2026-08-25: Plan-only mission; no worktrees or product changes created.
  - 2026-08-25: plans/README.md intentionally not edited because mission allowed only two plan artifacts.
  - 2026-08-25: P1-T2-EVIDENCESTATE-OWNERSHIP accepted for A TRACE P1 T2/T3 only; P1 is BLOCKED_PENDING_REBASE to this governance commit, while P2/P3 need not interrupt active work.
  - 2026-08-25: P1 integrated by exact fast-forward at fd77d58e with T1/T2/T3 history preserved; 297 owned/cross-stream, P0 L2 13, and RACES 8 passed; P2 requires exact rebase, P3 remains parked, and P4 remains blocked on P2.
  - 2026-08-25: P2 integrated by exact fast-forward at 7fbdf83f with S1-S6 plus approved Final-RQC wiring and exact RACES baseline history preserved; P4 is ready only from POST_P2_INTEGRATION_SHA, while P3 remains parked.
  - 2026-08-26: P4 integrated by exact fast-forward at cdb146df with 25/18/7/0 role posture, seven frozen prompt-policy contracts, no runtime role activation, no live A/B, and an exact baseline-matched 14-failure residual set; P3 rebase is next and P5 remains blocked.
  - 2026-08-26: P4.1 residual cleanup closed 13 of 14 inherited nodes with bounded test commits; GitHub clone-root remains ENVIRONMENT_FAILURE; CLEAN_WITH_ENVIRONMENT_RESIDUAL; P3/P5/P6/P7 not started.
```

## P1 completion evidence (historical checkpoint)

```yaml
P1_STATUS: DONE
P1_SOURCE_SHA: fd77d58ea1e9690eec25a83aa90d46949c4512b5
P1_COMMITS_INTEGRATED:
  - 8fe81fd69ebf822a54578d08b5ccb5f4c03b5a76
  - 58d5c4615ec3e555b3e5317e78969a69cc72ffdb
  - fd77d58ea1e9690eec25a83aa90d46949c4512b5
T1_STATUS: PASS
T2_STATUS: PASS
T3_STATUS: PASS
TRACE_SCHEMA_VERSION: trace_oracle_v1
EVIDENCE_STATE_SCHEMA_VERSION: minimal_evidence_state_v2
RUN_SHAPE_TRANSITION_SCHEMA_VERSION: run_shape_transition_v2
H_TRACE_01: CLOSED_P1
H_TRACE_02: CLOSED_P1
H_TRACE_03: CLOSED_P1
H_TRACE_04: CLOSED_P1
H_TRACE_05: REPROVED_ALREADY_CORRECT_P1
H_TRACE_06: CLOSED_P1
H_TRACE_07: CLOSED_P1
H_TRACE_08: CLOSED_P1
PROTECTED_FILES_CHANGED: NONE
POST_INTEGRATION_TESTS: 297 passed; P0 L2 13 passed; RACES 8 passed
P2_REBASE_REQUIRED: YES
P2_LOGICAL_HEAD_BEFORE_REBASE: 2d71666f34fbee9e3e8df50b05281d5ec808c583
P2_REBASE_TARGET: POST_P1_INTEGRATION_SHA_FROZEN_EXTERNALLY_AFTER_THIS_EVIDENCE_COMMIT
P3_ACTION: PARKED
P4_ACTION: BLOCKED_UNTIL_P2
```

## P2 completion evidence

```yaml
P2_STATUS: DONE
P2_SOURCE_SHA: 7fbdf83f4508886529121998256face8d3c9edf1
P2_COMMITS_INTEGRATED:
  - 5952d254c48191170decd238d9b3f7080f082ab1
  - 639477c71d147ecb8b93dfbfd86fc59d7e6edb15
  - 6d4458b2fbf5df966a7a091bb602c81dc6d10b3c
  - a214946f961b7fbe60b4730704f2456c192bdfe6
  - 09072610fb3ad90e75f48625271067a02913f0cc
  - 1f379f7af74059c0652d2834d00b02bfa818cd41
  - 5921f1d0cf569695db97ef0fd277ffdac8ec5338
  - 7fbdf83f4508886529121998256face8d3c9edf1
S1_STATUS: PASS
S2_STATUS: PASS
S3_STATUS: PASS
S4_STATUS: PASS
S5_STATUS: PASS
S6_STATUS: PASS
CONTRACT_VERSION: spl_semantic_v2
SUPPORTED_ANALYSIS_SHAPES:
  - raw
  - aggregation
  - ranking
  - trend
  - rolling
  - sequence
COMPARISON_STATUS: PRODUCT_GAP
COMPARISON_REASON: unsupported_comparison_semantics
PROTECTED_REQUEST: P2-FINAL-RQC-PIPELINE-WIRING
PROTECTED_REQUEST_STATUS: APPLIED_VERIFIED
PROTECTED_PIPELINE_SHA: 5921f1d0cf569695db97ef0fd277ffdac8ec5338
RACES_BASELINE_SHA: 5921f1d0cf569695db97ef0fd277ffdac8ec5338
LIVE_RQC_01_10: PASS
UNFAITHFUL_SPL_CAN_BE_EMITTED: NO
CANDIDATE_SPL_EXECUTABLE: NO
ONE_REPAIR_MAXIMUM: PASS
FINAL_RQC_PROVENANCE: UNCHANGED
POST_INTEGRATION_TESTS: P2 128 passed; LIVE-RQC 10 passed; P1 cross-contract 80 passed; P0 L2 13 passed; RACES 8 passed
KNOWN_FAILURES: two canonical-handoff HIL mirror tests PRE_EXISTING_FAILURE at fd77d58e and 7fbdf83f
LIVE_LLM_USED: NO
LIVE_MCP_USED: NO
P3_ACTION: PARKED_AT_838659ADA898B5A8BF071FDA2B233C125F51AC00
P4_ACTION: READY_TO_START_FROM_POST_P2_INTEGRATION_SHA
```

## P4 completion evidence

```yaml
P4_STATUS: DONE
P4_BASE_SHA: 29933dda595be082b9274c74b4545975b1742cb1
P4_SOURCE_SHA: cdb146df32b0214aa96bac8d037891835b696a46
P4_COMMITS_INTEGRATED:
  - eee4ad668fca94c9c9eafacd7c48dac486c9697b
  - 3097fb2f04c830f75d48cdb0e03130f6471e252d
  - c523213c7135b097846008716105b67b66bc52f5
  - 6911e1f4ba90ec38dfd4f2c81a9ee29bc85e85df
  - d62f90f1a1b6e0300885100926653a611144117b
  - 7421bd2b0a535e59dd3dc3819d5667a725c5c165
  - cdb146df32b0214aa96bac8d037891835b696a46
ROLE_COUNT: 25
PRODUCTION_REACHABLE_ROLES: 18
BLOCKED_ROLES: 7
LEGACY_DEAD_ROLES: 0
BLOCKED_ROLE_IDS: mitre_reasoner, missing_evidence_reasoner, risk_rationale_reasoner, plan_delta_reasoner, pattern_reasoner, evidence_reasoner, hypothesis_reasoner
REASONING_ALLOWED_ROLES: investigation_planner only; unchanged
OUTSIDE_NORMAL_NAMESPACE_OBSERVATIONS: governed_composer, remediation_planner, semantic_t4, spl_repair
PROMPT_CONTRACT_VERSIONS: prompt_role_contract_v1, prompt_role_registry_v1, few_shot_catalog_v1, negative_example_catalog_v1, prompt_cache_policy_v1, prompt_ab_eval_contract_v1, prompt_studio_config_v1
ACTIVE_PROMPT_POSTURE: every role has one ACTIVE template and no CANDIDATE; template metadata does not enable runtime execution
LIVE_AB_EVAL_PERFORMED: NO
BLOCKED_REASONING_ROLES_ENABLED: NO
P1_CONTRACT_PRESERVED: YES
P2_CONTRACT_PRESERVED: YES
UNFAITHFUL_SPL_CAN_BE_EMITTED: NO
PRE_INTEGRATION_TESTS: P4 702; P0 L2 13; reasoning reachability 2; P1 49; P2 98; RACES 8
POST_INTEGRATION_TESTS: P4 702; P0 L2 plus reachability 15; P1 49; P2 98; RACES 8
FULL_BACKEND_BASE: 14 failed, 6256 passed, 45 skipped, 6 xfailed
FULL_BACKEND_P4: 14 failed, 6958 passed, 45 skipped, 6 xfailed
RESIDUAL_FAILURE_SET_IDENTICAL: YES
FAILURE_CLASSIFICATION: PRE_EXISTING_FAILURE
PROTECTED_FILES_CHANGED: NONE
LIVE_LLM_USED: NO
LIVE_MCP_USED: NO
P3_REBASE_REQUIRED: YES
P3_REBASE_TARGET: POST_P4_INTEGRATION_SHA_FROZEN_EXTERNALLY_AFTER_THIS_EVIDENCE_COMMIT
P5_ACTION: BLOCKED_PENDING_P3_REBASE
```

## Completed loop iteration: P4 integration

```text
ITERATION_ID: 2026-08-26-P4-INTEGRATION-01
WORKSTREAM: INTEGRATION / D POLICY
PHASE: P4
START_SHA: 29933dda595be082b9274c74b4545975b1742cb1
CHANGE_HYPOTHESIS: The seven bounded P4 commits can fast-forward without enabling blocked roles or regressing P1/P2 contracts.
FILES_TOUCHED: P4-owned backend/app/llm/policy modules and tests; backend/app/llm/prompts.py docstring only; governance evidence in the two canonical plan files.
FOCUSED_TEST: P4 702; P0 L2 13; reasoning reachability 2; P1 49; P2 98; RACES 8; exact full-backend base/P4 JUnit comparison.
RESULT: PASS; exact fast-forward to cdb146df; BASE_FAILURE_SET equals P4_FAILURE_SET with 14 inherited failures.
FAILURE_CLASSIFICATION: PRE_EXISTING_FAILURE
ACTION: Integrated P4; recorded role posture, contracts, residual ledger, and next-phase gate.
COMMIT_SHA_OR_NONE: cdb146df32b0214aa96bac8d037891835b696a46 plus governance evidence commit recorded externally as POST_P4_INTEGRATION_SHA.
NEXT_REASON: P3 must rebase exactly onto POST_P4_INTEGRATION_SHA and reprove E1 before P5 can start.
```

## P4.1 completion evidence

```yaml
P4_1_STATUS: CLEAN_WITH_ENVIRONMENT_RESIDUAL
P4_1_LAST_TEST_SHA: 7f763b5b12078534e96f1860474138b7dcc83707
P4_1_ANCESTOR_REQUIRED: 8413a8f1602df8c8932be709c86b403eb8e00196
P4_1_ANCESTOR_OK: YES
P4_1_COMMITS:
  - 06bdf4112f984b546c273162a19834adcafc24b2  # test(db): run migration readiness with anyio
  - 2303de667f573ddce445ec300b021d11c08f481d  # test(trace): align review-only authority expectations
  - 7f2663be03bf6462f95061cd91d9f14d4f951a4f  # test(catalogue): align governed source-binding expectations
  - 04fed4ab5becd71286716331a1c030be18c0cca6  # test(dispatch): align phase2a authority expectations
  - 7f763b5b12078534e96f1860474138b7dcc83707  # test(spl): align final-rqc semantic expectations
PROTECTED_FILES_CHANGED: NONE
LIVE_LLM_USED: NO
LIVE_MCP_USED: NO
Q0_Q089_UNINTENDED_DRIFT: NO
CISCO_IDENTITY_018_INTENDED_CHANGE: YES
START_FAILURE_SET_COUNT: 14
CURRENT_FAILURE_SET: test_github_skill_expansion_factory_baseline.py::test_factory_generators_check_against_committed_artifacts
NEW_FAILURES: NONE
FULL_BACKEND_P4: 14 failed, 6958 passed, 45 skipped, 6 xfailed
FULL_BACKEND_P4_1: 1 failed, 6971 passed, 45 skipped, 6 xfailed
CROSS_CONTRACT: P0_L2_13; LIVE_RQC_10; RACES_8; P4_prompt_702; P1_trace_evidence_75_passed_1_skipped; P2_semantic_LIVE_RQC_79; reachability_2
GITHUB_RESIDUAL: ENVIRONMENT_FAILURE; AI_SOC_GITHUB_SKILL_CLONE_ROOT / default clone absent; --check requires real clone
P3_REBASE_STARTED: NO
P5_STARTED: NO
P6_STARTED: NO
P7_STARTED: NO
```

## Completed loop iteration: P4.1 residual cleanup

```text
ITERATION_ID: 2026-08-26-P4-1-RESIDUAL-01
WORKSTREAM: INTEGRATION
PHASE: P4.1
START_SHA: 8413a8f1602df8c8932be709c86b403eb8e00196
CHANGE_HYPOTHESIS: The inherited 14-node P4 residual set is stale-expectation / test-defect / environment, not a product regression requiring protected edits.
FILES_TOUCHED: backend/app/tests only for bounded family commits; this iteration's governance is the two canonical plan files.
FOCUSED_TEST: 14-node plus replacements 13 passed / 1 GitHub fail; full backend 6971 passed / 1 failed; P0 L2 13; LIVE-RQC 10; RACES 8; P4 702.
RESULT: CLEAN_WITH_ENVIRONMENT_RESIDUAL
FAILURE_CLASSIFICATION: 13 CLOSED; 1 ENVIRONMENT_FAILURE
ACTION: Freeze FINAL_CLEAN_INTEGRATION_SHA after this evidence commit; do not start P3 rebase.
COMMIT_SHA_OR_NONE: P4_1_LAST_TEST_SHA 7f763b5b plus this governance evidence commit.
NEXT_REASON: One combined P3 rebase onto FINAL_CLEAN_INTEGRATION_SHA plus PENDING_CONTRACT_P1/P2/P4 activation, in a separately authorized iteration.
```

## Workstream registry

| Stream | Phase(s) | Agent | Branch | Start SHA | Status | Exclusive ownership |
|---|---|---|---|---|---|---|
| A TRACE | P1 | CODEX | `ws/trace-truth` | `2ba619df52d2c813f5f21186f6e711e593d62003` | DONE_AT_FD77D58E | Trace/provenance modules and tests; consumed P1 T2/T3-only ownership of `backend/app/evidence/minimal_evidence_state.py` and directly corresponding H-TRACE-03/H-TRACE-08 tests |
| B SPL | P2 | CURSOR | `ws/spl-semantic-v2` | `fcba3426c36e0e92554f01c4fe30056443285b1c` | DONE_AT_7FBDF83F | SPL semantic/compiler/fidelity/live SPL prompt modules and tests; protected pipeline request applied and verified |
| C EVAL | P3, P5, P6 | CLAUDE | `ws/l2-eval-bank` | `838659ada898b5a8bf071fda2b233c125f51ac00` | PARKED_REBASE_REQUIRED | L2 bank and test architecture only |
| D POLICY | P4 | CLAUDE | `ws/prompt-policy` | `29933dda595be082b9274c74b4545975b1742cb1` | DONE_AT_CDB146DF | Generic prompt/role/policy files and tests |
| E UI | P7 | CURSOR | `ws/production-ux` | unset | BLOCKED_P5 | Production non-EC frontend and tests |
| F PROMOTION | P8-P11 | CODEX/operator | `ws/promotion-coe` | unset | BLOCKED_P5 | L3/promotion/COE evidence only |

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
8. Run the focused test. A pre-fix red reproduction is evidence in the current iteration, not a commit. Classify it using the allowed
   failure classes below, implement the bounded fix, and rerun. Run phase-level gates only when acceptance criteria are otherwise met.
9. If the logical contract's focused gate is green and implementation commits are authorized, commit implementation plus its regression
   tests as one bounded logical change. Follow the canonical **Commit guidance**: explicit `git add <paths>` (never `-A`/`.`/`-a`),
   required trailers, never stage `.claude/settings.local.json`, and confirm no unapproved `RACES_FREEZE_PATHS` prefix is staged.
10. Update the canonical plan item status/evidence and this dashboard with SHA, command/result, failures, queues, and next unlock. A plan-status commit must be scoped and authorized like any other commit.
11. If a protected file or operator decision is needed, STOP before editing, enqueue the exact proposed diff and tests in `PROTECTED_CHANGE_QUEUE`, and report `OPERATOR_APPROVAL_REQUIRED`.
12. Never push, merge, deploy, enable live MCP, rotate/configure secrets, or alter production from this loop.

If the same verification gate fails twice on the same bounded item, mark the workstream blocked with exact failure evidence and stop. Do not weaken tests or thresholds.

## Loop iteration record

Increment `LOOP_ITERATION_ID` before each bounded attempt and append one immutable record. `CURRENT_LOOP` is
`<WORKSTREAM>/<PHASE>/<ITEM>` while active and returns to `NONE` only after the record is complete.

```text
ITERATION_ID:
WORKSTREAM:
PHASE:
START_SHA:
CHANGE_HYPOTHESIS:
FILES_TOUCHED:
FOCUSED_TEST:
RESULT:
FAILURE_CLASSIFICATION:
ACTION:
COMMIT_SHA_OR_NONE:
NEXT_REASON:
```

`FAILURE_CLASSIFICATION` must be exactly one of:

```text
PRODUCT_DEFECT
TEST_DEFECT
STALE_EXPECTATION
ENVIRONMENT_FAILURE
PRE_EXISTING_FAILURE
CROSS_WORKSTREAM_CONTRACT_DRIFT
EXPECTED_UNIMPLEMENTED_CAPABILITY
PROTECTED_CHANGE_REQUIRED
OPERATOR_DECISION_REQUIRED
```

Use `COMMIT_SHA_OR_NONE = NONE` for red reproduction evidence. Commit only after the bounded logical contract is green; that green
commit may include the implementation and the regression test whose earlier red result is recorded here.

## Eligibility rules

- `P0.1`, `P1`, `P2`, and P3 scaffold are the only first parallel start set, and all must use the same frozen
  `EXECUTION_INTEGRATION_SHA` returned after the final plan commit exists and is approved.
- `fe3548e475e61e77f5204e02f74efd28690abb86` is `PLAN_PREPARATION_SHA`; `615069e6` is the P0 product baseline. Neither is a
  hard-coded execution start requirement.
- No phase may record an L0 RACES gate green until `P0.1` is DONE; until then `test_races_freeze_files_unchanged_since_baseline` is inherited-red for every stream and must be reported as inherited, never as that stream's regression.
- P0.1 action A is read-only audit/proposal and must STOP with the nine-field packet. Action B apply requires a separate explicit
  operator approval. If B lands, set `EXECUTION_INTEGRATION_SHA` (and compatibility field `INTEGRATION_SHA`) to the exact P0.1 commit
  and mark every pre-P0.1 active stream
  `REBASE_REQUIRED = YES`; rebase is mandatory before L0 evidence, branch return, reconciliation, or merge.
- All backend commands use `$PYVENV` (absolute). `../.venv/bin/python` does not exist in a worktree because `.venv/` is gitignored.
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

For P0.1 action A, attach these additional fields and STOP: `PROTECTED_DIFF_AUDIT`, `AUTHORITY_IMPACT`, `HIL_IMPACT`, `RBAC_IMPACT`,
`AUTH0_IMPACT`, `EXECUTION_ELIGIBILITY_IMPACT`, `EC_IMPORT_IMPACT`, `ROLLBACK`, and `PROPOSED_BASELINE_DIFF`. Action B apply is a
separate approval; plan approval or audit approval never implies apply approval.

No protected file may be edited while approval is PENDING. `architecture.md` is not eligible even through this queue; an architecture conflict stops the plan for a separate decision.

## Merge queue and return packet

Queue order:

0. Approved P0.1 one-file baseline apply, if authorized; update `EXECUTION_INTEGRATION_SHA` and force active-stream rebases
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

Before accepting an entry, the integration owner confirms ownership, rebases/merges against the declared execution integration SHA,
reruns affected cross-stream tests, updates `CURRENT_BASE_SHA`, and records the new `EXECUTION_INTEGRATION_SHA`. Working streams never
push or merge themselves.

## Test gates

Use the host virtual environment unless a phase explicitly records another controlled runner.

```bash
# Focused backend
cd backend && "$PYVENV" -m pytest -q <test paths or node IDs>

# Harness independence
PYTHONPATH=backend:. "$PYVENV" -m test_harness.harness.runner --json

# Full backend promotion gate
cd backend && "$PYVENV" -m pytest -q -p no:cacheprovider

# Frontend
cd frontend && npm test && npm run build

# Governance on host venv
PATH="$(dirname "$PYVENV"):$PATH" ./scripts/run_stage3_governance_regression.sh
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

## Phase reopening

The DAG controls first eligibility; later evidence may reopen a DONE phase. Append this record, change that phase status openly, update
the findings ledger, and invalidate downstream evidence before any fix:

```text
REOPENED_PHASE:
TRIGGER:
INVALIDATED_EVIDENCE:
NEW_BASE_SHA:
OWNER:
DOWNSTREAM_PHASES_TO_RERUN:
```

Routing rules: P5 trace projection -> P1; P4/P8 semantic-contract gap -> P2; P8 prompt-only failure with intact semantics -> P4; P7
unrepresentable backend truth -> owning P1/P2/P4 seam; P9 regression -> owning phase and all affected downstream gates. Never silently
edit a completed phase or retain evidence produced against an invalidated SHA/contract.

## Plan/runner consistency check

- [x] SHA roles match: `PLAN_PREPARATION_SHA = fe3548e4`; `EXECUTION_INTEGRATION_SHA` is frozen externally after the final plan commit;
  `INTEGRATION_SHA` is only a compatibility alias after freeze.
- [x] `P0_PRODUCT_BASELINE_SHA` is `615069e6ca9cdb3d40b51d6a2f071346ecf3d6a2` and is not a worktree start SHA.
- [x] P0/P0.1/P1/P2/P4 are DONE; P3 is PARKED at `838659ad` with exact post-P4 rebase required; P5 is blocked pending that rebase; later phase and P11 posture is unchanged; current loop is NONE.
- [x] **P4.1** — Residual baseline cleanup
  - **Do:** Disposition the exact P4 14-node residual set; freeze `FINAL_CLEAN_INTEGRATION_SHA`; do not start P3.
  - **Verify:** `.cursor/hooks/audit-plan-discipline.sh` on both plan files; full backend `1 failed, 6971 passed, 45 skipped, 6 xfailed`; GitHub-only residual.
  - **Depends on:** P4 DONE
  - **Evidence:** P4.1 completion evidence block; `P4_1_LAST_TEST_SHA = 7f763b5b12078534e96f1860474138b7dcc83707`.
- [x] Dependencies and merge order match the canonical plan; P0.1, A, B, and D are complete, so C/P3 rebase and P5 are next.
- [x] Protected queue is empty; P1 reconciliation is consumed; `P2-FINAL-RQC-PIPELINE-WIRING` is APPLIED_VERIFIED at `5921f1d0` with the RACES baseline pinned to that exact SHA.
- [x] Post-P0.1 apply forces exact-SHA rebase before L0/return/integration.
- [x] Live MCP remains disabled and deferred to P11 plus separate approval.

Any failed row sets `CURRENT_PHASE: PLAN_CORRECTION_REQUIRED` and blocks implementation start.

**Verify:** Run `.cursor/hooks/audit-plan-discipline.sh` against both plan files, confirm zero gaps, then compare the control-state SHA,
phase statuses, eligibility rules, merge order, protected queue, current loop, rebase rule, and live-MCP posture to the canonical plan.

## Decision log

Append decisions; do not rewrite history.

| Date/time | Phase | Decision | Evidence/approval | Consequence |
|---|---|---|---|---|
| 2026-08-25 18:06 IST | Plan | P0 product behavior is frozen at `615069e6`; initial plan prepared at `fe3548e4` | Repository inspection | Final execution SHA is frozen externally after approved plan commit |
| 2026-08-25 18:06 IST | Plan | No README update in plan-only commit | Mission allowed only two plan files | Historical index update remains out of scope |
| 2026-08-25 18:06 IST | Plan | Live MCP is terminal P11 and default-off before then | Architecture and mission | No earlier stream may test real MCP |
| 2026-08-25 plan correction | P0.1 | Audit/proposal and apply are separate operator gates | Correction mission | P0.1 not executed; approved apply would force active-stream rebases |
| 2026-08-25 plan correction | Commit policy | Red reproduction is loop evidence, not permanent history | Correction mission | Commit only bounded green contracts |
| 2026-08-25 plan correction | Validation | Both plan-discipline audits passed with zero gaps | Audit output | Ready for operator review; implementation still blocked |
| 2026-08-25 reconciliation | P1 T2/T3 | Accept `P1-T2-EVIDENCESTATE-OWNERSHIP` and assign the bounded EvidenceState truth seam to A TRACE | Explicit operator ownership decision | Preserve T1 `db4e715f`; P1 rebases to this governance commit before T2; P2/P3 continue without immediate rebase |
| 2026-08-25 P1 integration | P1 | Fast-forward `fd77d58e`; preserve commits `8fe81fd6`, `58d5c461`, `fd77d58e`; freeze `trace_oracle_v1`, `minimal_evidence_state_v2`, `run_shape_transition_v2` | 297 owned/cross-stream tests, P0 L2 13, RACES 8; no protected paths | P1 DONE; P2 exact rebase required; P3 parked; P4 blocked until P2 |
| 2026-08-25 P2 integration | P2 | Fast-forward `7fbdf83f`; preserve S1-S6, protected wiring `5921f1d0`, and RACES commit; freeze `spl_semantic_v2` | P2 128, LIVE-RQC 10, P1 cross-contract 80, P0 L2 13, RACES 8; two baseline-matched HIL residuals | P2 DONE; P3 parked at `838659ad`; P4 ready from exact post-governance SHA |
| 2026-08-26 P4 integration | P4 | Fast-forward `cdb146df`; preserve seven bounded commits; freeze seven prompt-policy contract versions without runtime activation | P4 702, P0 L2 13, P1 49, P2 98, RACES 8; full backend exact 14-node residual match | P4 DONE; P3 exact rebase required onto post-P4 governance SHA; P5 blocked pending P3 |
| 2026-08-26 P4.1 residual cleanup | P4.1 | Bounded test-only alignment of 13 stale/test-defect residuals; GitHub clone-root left as environment residual | 14-node 13/1; full backend 6971 passed / 1 failed; P0 L2 13; LIVE-RQC 10; RACES 8; P4 702; NEW_FAILURES NONE | CLEAN_WITH_ENVIRONMENT_RESIDUAL; freeze FINAL_CLEAN_INTEGRATION_SHA; P3 remains parked |

## Runner stop

Stop and report when all eligible work is complete, the same gate fails twice, a protected change is needed, a dependency or authority premise is wrong, ownership conflicts, an unexplained regression appears, or operator/environment input is required. A stopped loop reports the exact blocker, evidence, safest next decision, and unchanged safety posture. It never resets, pushes, merges, deploys, edits architecture, or enables live MCP.
